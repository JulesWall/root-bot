"""
Gestionnaire de persistance et de requêtes pour la table SQL 'hourly_logs'.

Permet le suivi, la journalisation et l'audit anti-triche des récompenses horaires (/hourly) :
- Enregistrement de chaque exécution validée (horodatage, gain, bonus, série, statut de combo).
- Synthèse globale et classement (top) des joueurs les plus assidus sur 24h pour la modération.
- Extraction des journaux chronologiques d'un joueur pour l'audit en direct (!hourlyaudit).
- Calcul des métriques statistiques de dispersion et de risque d'automatisation (bot).
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Any


def _normalize_hourly_row(row: dict) -> dict:
    """Normalise une ligne hourly_logs (Decimal, bool, types stables)."""
    return {
        "id": row.get("id"),
        "discord_id": row["discord_id"],
        "claimed_at": row.get("claimed_at"),
        "interval_seconds": row.get("interval_seconds"),
        "base_usd": Decimal(str(row.get("base_usd") or 0)),
        "bonus_pct": Decimal(str(row.get("bonus_pct") or 0)),
        "total_usd": Decimal(str(row.get("total_usd") or 0)),
        "streak": int(row.get("streak") or 0),
        "combo_lost": bool(row.get("combo_lost", 0)),
    }


class HourlyStatsDB:
    """Accès aux données pour la table hourly_logs."""

    @staticmethod
    def record_hourly(
        tx,
        discord_id: int,
        claimed_at: datetime,
        interval_seconds: int | None,
        base_usd: Decimal,
        bonus_pct: Decimal,
        total_usd: Decimal,
        streak: int,
        combo_lost: bool = False,
    ) -> None:
        """Enregistre une récompense /hourly réussie pour un joueur."""
        tx.execute(
            """
            INSERT INTO hourly_logs (discord_id, claimed_at, interval_seconds, base_usd, bonus_pct, total_usd, streak, combo_lost)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                discord_id,
                claimed_at,
                interval_seconds,
                base_usd,
                bonus_pct,
                total_usd,
                streak,
                1 if combo_lost else 0,
            ),
        )

    @staticmethod
    def get_summary(
        tx,
        limit_users: int = 50,
        since_dt: datetime | None = None,
        claims_since_dt: datetime | None = None,
    ) -> list[dict]:
        """Retourne la synthèse de la période avec la liste des récompenses par joueur.

        Args:
            tx: Transaction MySQL active.
            limit_users: Nombre maximum d'utilisateurs à renvoyer.
            since_dt: Borne temporelle inférieure facultative pour les totaux (ex: dernières 24h).
            claims_since_dt: Borne temporelle inférieure facultative pour l'historique d'analyse (ex: dernières 48h).

        Returns:
            Une liste de dictionnaires ordonnée par claim_count DESC :
            [
                {
                    'discord_id': int,
                    'claim_count': int,
                    'total_usd': Decimal,
                    'max_streak': int,
                    'max_bonus_pct': Decimal,
                    'claims': list[dict],
                },
                ...
            ]
        """
        if since_dt is not None:
            top_users = tx.all(
                """
                SELECT 
                    discord_id,
                    COUNT(*) AS claim_count,
                    COALESCE(SUM(total_usd), 0.00) AS total_usd,
                    MAX(streak) AS max_streak,
                    MAX(bonus_pct) AS max_bonus_pct
                FROM hourly_logs
                WHERE claimed_at >= %s
                GROUP BY discord_id
                ORDER BY claim_count DESC, total_usd DESC
                LIMIT %s
                """,
                (since_dt, limit_users),
            ) or []
        else:
            top_users = tx.all(
                """
                SELECT 
                    discord_id,
                    COUNT(*) AS claim_count,
                    COALESCE(SUM(total_usd), 0.00) AS total_usd,
                    MAX(streak) AS max_streak,
                    MAX(bonus_pct) AS max_bonus_pct
                FROM hourly_logs
                GROUP BY discord_id
                ORDER BY claim_count DESC, total_usd DESC
                LIMIT %s
                """,
                (limit_users,),
            ) or []

        if not top_users:
            return []

        user_ids = [row["discord_id"] for row in top_users]
        if not user_ids:
            return []

        actual_claims_since = claims_since_dt if claims_since_dt is not None else since_dt
        placeholders = ", ".join(["%s"] * len(user_ids))
        if actual_claims_since is not None:
            params = tuple(user_ids) + (actual_claims_since,)
            rows = tx.all(
                f"""
                SELECT id, discord_id, claimed_at, interval_seconds, base_usd, bonus_pct, total_usd, streak, combo_lost
                FROM hourly_logs
                WHERE discord_id IN ({placeholders}) AND claimed_at >= %s
                ORDER BY claimed_at ASC
                """,
                params,
            ) or []
        else:
            rows = tx.all(
                f"""
                SELECT id, discord_id, claimed_at, interval_seconds, base_usd, bonus_pct, total_usd, streak, combo_lost
                FROM hourly_logs
                WHERE discord_id IN ({placeholders})
                ORDER BY claimed_at ASC
                """,
                tuple(user_ids),
            ) or []

        logs_by_user: dict[int, list[dict]] = defaultdict(list)
        for r in rows:
            uid = r["discord_id"]
            logs_by_user[uid].append(_normalize_hourly_row(r))

        summary = []
        for user_row in top_users:
            uid = user_row["discord_id"]
            user_logs = logs_by_user.get(uid, [])
            summary.append({
                "discord_id": uid,
                "claim_count": int(user_row["claim_count"]),
                "total_usd": Decimal(str(user_row["total_usd"])),
                "max_streak": int(user_row.get("max_streak") or 0),
                "max_bonus_pct": Decimal(str(user_row.get("max_bonus_pct") or 0)),
                "claims": user_logs,
            })

        return summary

    @staticmethod
    def purge_older_than(tx, cutoff_dt: datetime) -> None:
        """Supprime les logs antérieurs à la date limite (rétention 48h)."""
        tx.execute("DELETE FROM hourly_logs WHERE claimed_at < %s", (cutoff_dt,))

    @staticmethod
    def reset(tx) -> None:
        """Supprime l'historique hourly_logs (purge complète).

        Le combo joueur (hourly_last_at, hourly_combo_bonus, hourly_streak) n'est pas touché.
        """
        tx.execute("DELETE FROM hourly_logs")

    @staticmethod
    def get_last_report_date(tx) -> str | None:
        """Retourne la date (YYYY-MM-DD) du dernier rapport quotidien hourly consigné."""
        row = tx.one("SELECT last_found_on FROM events WHERE event = 'daily_hourly_report'")
        return row["last_found_on"] if row else None

    @staticmethod
    def set_last_report_date(tx, date_str: str, now_dt: datetime) -> None:
        """Enregistre la date (YYYY-MM-DD) du dernier rapport quotidien hourly."""
        tx.execute(
            """
            INSERT INTO events (event, next_at, last_found_on, last_reward)
            VALUES ('daily_hourly_report', %s, %s, 0.00)
            ON DUPLICATE KEY UPDATE
                next_at = VALUES(next_at),
                last_found_on = VALUES(last_found_on)
            """,
            (now_dt, date_str),
        )

    @staticmethod
    def get_user_hourly_logs(tx, discord_id: int, limit: int = 50, since_dt: datetime | None = None) -> list[dict]:
        """Récupère l'historique chronologique des exécutions /hourly d'un joueur."""
        if since_dt is not None:
            rows = tx.all(
                """
                SELECT id, discord_id, claimed_at, interval_seconds, base_usd, bonus_pct, total_usd, streak, combo_lost
                FROM hourly_logs
                WHERE discord_id = %s AND claimed_at >= %s
                ORDER BY claimed_at DESC
                LIMIT %s
                """,
                (discord_id, since_dt, limit),
            ) or []
        else:
            rows = tx.all(
                """
                SELECT id, discord_id, claimed_at, interval_seconds, base_usd, bonus_pct, total_usd, streak, combo_lost
                FROM hourly_logs
                WHERE discord_id = %s
                ORDER BY claimed_at DESC
                LIMIT %s
                """,
                (discord_id, limit),
            ) or []
        # Les N plus récents, restitués du plus ancien au plus récent.
        return list(reversed([_normalize_hourly_row(r) for r in rows]))


# Réexport des fonctions d'analyse unifiées pour compatibilité ascendante sans duplication
from utils.claim_analysis import (
    extract_intervals as extract_hourly_intervals,
    calculate_player_hourly_metrics,
)

