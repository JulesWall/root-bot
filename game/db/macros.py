"""
Gestionnaire d'accès aux données pour les macros de joueurs (tables 'macros', 'macro_steps', 'macro_runs').

Prend en charge :
- Le stockage jusqu'à 3 macros par joueur.
- Le stockage de 1 à 5 étapes séquentielles par macro.
- Le suivi des exécutions (rate limit : cooldown 15s, quota 60/h).
"""

from datetime import datetime, timedelta
import json
import re

from game.game_error import GameError

MAX_MACROS_PER_PLAYER = 3
MAX_STEPS_PER_MACRO = 5
MAX_RUNS_PER_HOUR = 60
MACRO_COOLDOWN_SECONDS = 15

NAME_REGEX = re.compile(r"^[a-z0-9_-]{1,32}$")
RESERVED_NAMES = frozenset({"create", "delete", "list", "view", "edit", "run", "help"})


def validate_macro_name(name: str) -> str:
    """Normalise et valide le nom d'une macro."""
    if not name or not isinstance(name, str):
        raise GameError("macro_name_invalid")
    normalized = name.strip().lower()
    if not NAME_REGEX.match(normalized):
        raise GameError("macro_name_invalid")
    if normalized in RESERVED_NAMES:
        raise GameError("macro_name_reserved", name=normalized)
    return normalized


class MacrosDB:
    """DAO pour la gestion des macros, de leurs étapes et de leurs limitations d'exécution."""

    @staticmethod
    def count_user_macros(tx, discord_id: int) -> int:
        """Retourne le nombre total de macros possédées par le joueur."""
        row = tx.one("SELECT COUNT(*) AS count FROM macros WHERE discord_id = %s", (discord_id,))
        return int(row.get("count", 0)) if row else 0

    @staticmethod
    def list_user_macros(tx, discord_id: int) -> list[dict]:
        """Retourne la liste des macros d'un joueur avec le décompte de leurs étapes."""
        rows = tx.all(
            """
            SELECT m.id, m.discord_id, m.name, m.created_at, m.updated_at,
                   COUNT(s.position) AS steps_count
            FROM macros m
            LEFT JOIN macro_steps s ON m.id = s.macro_id
            WHERE m.discord_id = %s
            GROUP BY m.id, m.discord_id, m.name, m.created_at, m.updated_at
            ORDER BY m.name ASC
            """,
            (discord_id,),
        ) or []
        return rows

    @staticmethod
    def get_macro(tx, discord_id: int, name: str) -> dict | None:
        """
        Récupère une macro complète et ordonnée pour son propriétaire.
        Retourne None si la macro n'existe pas ou appartient à un tiers.
        """
        clean_name = name.strip().lower()
        macro_row = tx.one(
            """
            SELECT id, discord_id, name, created_at, updated_at
            FROM macros
            WHERE discord_id = %s AND name = %s
            """,
            (discord_id, clean_name),
        )
        if not macro_row:
            return None

        macro_id = macro_row["id"]
        step_rows = tx.all(
            """
            SELECT position, method, args_json
            FROM macro_steps
            WHERE macro_id = %s
            ORDER BY position ASC
            """,
            (macro_id,),
        ) or []

        steps = []
        for s in step_rows:
            raw_args = s.get("args_json")
            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except Exception:
                    parsed_args = {}
            elif isinstance(raw_args, dict):
                parsed_args = raw_args
            else:
                parsed_args = {}
            steps.append({
                "position": int(s["position"]),
                "method": str(s["method"]),
                "args": parsed_args,
            })

        return {
            "id": macro_id,
            "discord_id": discord_id,
            "name": clean_name,
            "created_at": macro_row["created_at"],
            "updated_at": macro_row["updated_at"],
            "steps": steps,
        }

    @staticmethod
    def create_macro(tx, discord_id: int, name: str, steps: list[dict]) -> dict:
        """
        Crée une macro avec ses étapes.
        Lève GameError si la limite de macros ou d'étapes est dépassée, ou si le nom est déjà pris.
        """
        clean_name = validate_macro_name(name)

        if not steps:
            raise GameError("macro_empty")
        if len(steps) > MAX_STEPS_PER_MACRO:
            raise GameError("macro_steps_limit", max_steps=MAX_STEPS_PER_MACRO)

        current_count = MacrosDB.count_user_macros(tx, discord_id)
        if current_count >= MAX_MACROS_PER_PLAYER:
            raise GameError("macro_limit", max_macros=MAX_MACROS_PER_PLAYER)

        existing = tx.one(
            "SELECT id FROM macros WHERE discord_id = %s AND name = %s",
            (discord_id, clean_name),
        )
        if existing:
            raise GameError("macro_name_taken", name=clean_name)

        macro_id = tx.execute(
            """
            INSERT INTO macros (discord_id, name, created_at, updated_at)
            VALUES (%s, %s, %s, %s)
            """,
            (discord_id, clean_name, tx.now, tx.now),
        )

        for pos, step in enumerate(steps, start=1):
            method = str(step.get("method", "")).strip().lower()
            args = step.get("args", {})
            args_json = json.dumps(args, ensure_ascii=False)
            tx.execute(
                """
                INSERT INTO macro_steps (macro_id, position, method, args_json)
                VALUES (%s, %s, %s, %s)
                """,
                (macro_id, pos, method, args_json),
            )

        return MacrosDB.get_macro(tx, discord_id, clean_name)

    @staticmethod
    def delete_macro(tx, discord_id: int, name: str) -> bool:
        """Supprime une macro appartenant au joueur."""
        clean_name = name.strip().lower()
        macro = tx.one(
            "SELECT id FROM macros WHERE discord_id = %s AND name = %s",
            (discord_id, clean_name),
        )
        if not macro:
            return False

        macro_id = macro["id"]
        tx.execute("DELETE FROM macro_steps WHERE macro_id = %s", (macro_id,))
        tx.execute("DELETE FROM macros WHERE id = %s", (macro_id,))
        return True

    @staticmethod
    def reserve_run(tx, discord_id: int) -> dict:
        """
        Vérifie atomiquement les quotas et cooldown d'exécution, puis enregistre un nouveau run.
        Lève GameError('macro_cooldown') ou GameError('macro_quota') si une contrainte est enfreinte.
        """
        now = tx.now
        one_hour_ago = now - timedelta(hours=1)

        # 1. Purge des anciens runs (> 1 heure)
        tx.execute(
            "DELETE FROM macro_runs WHERE discord_id = %s AND started_at < %s",
            (discord_id, one_hour_ago),
        )

        # 2. Récupération des runs de la dernière heure
        rows = tx.all(
            """
            SELECT started_at
            FROM macro_runs
            WHERE discord_id = %s AND started_at >= %s
            ORDER BY started_at DESC
            """,
            (discord_id, one_hour_ago),
        ) or []

        # 3. Vérification du Cooldown de 15 secondes
        if rows:
            last_run = rows[0]["started_at"]
            elapsed = (now - last_run).total_seconds()
            if elapsed < MACRO_COOLDOWN_SECONDS:
                remaining = max(1, int(MACRO_COOLDOWN_SECONDS - elapsed))
                raise GameError("macro_cooldown", remaining=remaining)

        # 4. Vérification du Quota glissant de 60 runs par heure
        if len(rows) >= MAX_RUNS_PER_HOUR:
            # Calcul du temps jusqu'au premier run qui libérera un slot
            oldest_run = rows[-1]["started_at"]
            free_in = max(1, int(3600 - (now - oldest_run).total_seconds()))
            raise GameError("macro_quota", max_runs=MAX_RUNS_PER_HOUR, remaining=free_in)

        # 5. Enregistrement du run
        run_id = tx.execute(
            "INSERT INTO macro_runs (discord_id, started_at) VALUES (%s, %s)",
            (discord_id, now),
        )

        return {
            "run_id": run_id,
            "started_at": now,
            "runs_in_last_hour": len(rows) + 1,
        }

