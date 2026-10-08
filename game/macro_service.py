"""
Service métier d'orchestration des macros joueurs.

Prend en charge :
- La création, la suppression et la consultation des macros.
- L'exécution séquentielle pas-à-pas des étapes via RootService.execute.
- La gestion atomique du cooldown (15s) et du quota (60 runs/h).
- L'arrêt immédiat en cas d'erreur sans annulation des étapes passées.
"""

import logging
from typing import Any

from game.db.database import player_lock_name
from game.db.macros import MacrosDB, validate_macro_name
from game.game_error import GameError
from game.macro_catalog import MACRO_CATALOG, validate_step_args

logger = logging.getLogger(__name__)


# Erreurs de temporisation/cooldown non bloquantes lors de l'exécution d'une macro
NON_FATAL_COOLDOWN_ERRORS = frozenset({
    "hourly_cooldown",
    "claim_cooldown",
    "cooldown",
    "contract_not_ready",
    "contract_in_progress",
    "upgrade_in_progress",
    "compile_in_progress",
    "scan_in_progress",
    "hack_target_in_progress",
})


class MacroService:
    """Service d'automatisation des macros joueurs."""

    def __init__(self, root_service):
        self.root_service = root_service

    @property
    def database(self):
        return self.root_service.database

    async def list_macros(self, discord_id: int) -> list[dict]:
        """Retourne la liste des macros possédées par le joueur."""
        return await self.database.run(
            lambda tx: MacrosDB.list_user_macros(tx, discord_id),
            readonly=True,
        )

    async def get_macro(self, discord_id: int, name: str) -> dict | None:
        """Récupère une macro par son nom pour le joueur spécifié."""
        clean_name = name.strip().lower()
        return await self.database.run(
            lambda tx: MacrosDB.get_macro(tx, discord_id, clean_name),
            readonly=True,
        )

    async def create_macro(self, discord_id: int, name: str, steps: list[dict]) -> dict:
        """
        Crée ou enregistre une nouvelle macro pour le joueur.
        Valide chaque étape selon le catalogue.
        """
        clean_name = validate_macro_name(name)

        if not steps:
            raise GameError("macro_empty")

        validated_steps = []
        for s in steps:
            method = str(s.get("method", "")).strip().lower()
            raw_args = s.get("args", {})
            clean_args = validate_step_args(method, raw_args)
            validated_steps.append({"method": method, "args": clean_args})

        def _tx_create(tx):
            return MacrosDB.create_macro(tx, discord_id, clean_name, validated_steps)

        return await self.database.run(
            _tx_create,
            locks=[player_lock_name(discord_id)],
        )

    async def delete_macro(self, discord_id: int, name: str) -> bool:
        """Supprime une macro appartenant au joueur."""
        clean_name = name.strip().lower()

        def _tx_delete(tx):
            deleted = MacrosDB.delete_macro(tx, discord_id, clean_name)
            if not deleted:
                raise GameError("macro_not_found", name=clean_name)
            return True

        return await self.database.run(
            _tx_delete,
            locks=[player_lock_name(discord_id)],
        )

    async def run_macro(self, actor: int, guild: int | None, name: str) -> dict:
        """
        Exécute séquentiellement la macro demandée.

        Flux d'exécution :
        1. Résolution de la macro + réservation atomique (cooldown & quota) dans une transaction courte.
        2. Libération du verrou pour éviter tout deadlock avec les appels RootService.execute.
        3. Exécution séquentielle de chaque étape via RootService.execute.
        4. Interruption en cas de GameError avec retour du statut précis.
        """
        clean_name = name.strip().lower()

        # Phase 1 : Résolution et réservation atomique
        def _reserve(tx):
            macro = MacrosDB.get_macro(tx, actor, clean_name)
            if not macro:
                raise GameError("macro_not_found", name=clean_name)
            # Réservation : applique le cooldown 15s et le quota 60/h
            reservation = MacrosDB.reserve_run(tx, actor)
            return macro, reservation

        macro_data, reservation = await self.database.run(
            _reserve,
            locks=[player_lock_name(actor)],
        )

        steps = macro_data.get("steps", [])
        step_results = []
        stopped_at = None
        error_info = None

        # Phase 2 : Exécution séquentielle
        for pos, step in enumerate(steps, start=1):
            method = step["method"]
            args = dict(step.get("args", {}))

            try:
                # Ré-application de la validation défensive au cas où les données en base aient varié
                call_args = validate_step_args(method, args)
                exec_res = await self.root_service.execute(actor, guild, method, **call_args)
                step_results.append({
                    "position": pos,
                    "method": method,
                    "success": True,
                    "result": exec_res,
                })
            except GameError as ge:
                step_error = {
                    "key": ge.key,
                    "values": ge.values,
                }
                is_cooldown = ge.key in NON_FATAL_COOLDOWN_ERRORS
                step_results.append({
                    "position": pos,
                    "method": method,
                    "success": False,
                    "skipped": is_cooldown,
                    "error": step_error,
                })
                # Ne bloque pas les commandes suivantes même en cas d'erreur
                continue
            except Exception as exc:
                logger.exception("Erreur inattendue lors de l'étape %d de la macro '%s'", pos, clean_name)
                step_error = {
                    "key": "macro_step_failed",
                    "values": {"pos": pos, "command": method, "reason": str(exc)},
                }
                step_results.append({
                    "position": pos,
                    "method": method,
                    "success": False,
                    "skipped": False,
                    "error": step_error,
                })
                # Ne bloque pas les commandes suivantes
                continue

        return {
            "macro_name": clean_name,
            "total_steps": len(steps),
            "executed_steps": len(step_results),
            "stopped_at": stopped_at,
            "error": error_info,
            "steps": step_results,
        }

