"""
Gestionnaire de persistance et de requêtes pour la table SQL 'daily_claim_logs'.

Permet le suivi et l'audit des récoltes de minage (/claim) sur la journée calendaire :
- Enregistrement de chaque claim validé avec son horodatage et son intervalle.
- Extraction des claims par joueur triés par nombre de récoltes décroissant.
- Extraction ciblée pour l'audit détaillé d'un joueur suspect.
- Remise à zéro quotidienne après émission du rapport de modération.
- Suivi de la date du dernier rapport pour rattrapage automatique en cas de coupure.
"""

from datetime import datetime
from decimal import Decimal


class DailyClaimStatsDB:
    """Accès aux données pour la table daily_claim_logs."""

    @staticmethod
    def record_claim(
        tx,
        discord_id: int,
        claimed_at: datetime,
        interval_seconds: int | None,
        amount: Decimal,
        is_auto: bool = False,
    ) -> None:
        """Enregistre un claim réussi pour un joueur."""
        tx.execute(
            """
            INSERT INTO daily_claim_logs (discord_id, claimed_at, interval_seconds, amount, is_auto)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (discord_id, claimed_at, interval_seconds, amount, 1 if is_auto else 0),
        )

    @staticmethod
    def get_summary(
        tx,
        limit_users: int = 50,
        since_dt: datetime | None = None,
        claims_since_dt: datetime | None = None,
    ) -> list[dict]:
        """Retourne la liste ordonnée des joueurs de la période avec leurs claims respectifs.

        Args:
            tx: Transaction MySQL active.
            limit_users: Nombre maximum d'utilisateurs à renvoyer.
            since_dt: Borne inférieure facultative pour les totaux (ex: dernières 24h).
            claims_since_dt: Borne inférieure facultative pour l'historique de claims (ex: dernières 24h).

        Returns:
            Une liste de dictionnaires au format :
            [
                {
                    'discord_id': int,
                    'claim_count': int,
                    'manual_count': int,
                    'auto_count': int,
                    'total_amount': Decimal,
                    'claims': [{'claimed_at': datetime, 'interval_seconds': int | None, 'amount': Decimal, 'is_auto': bool}, ...]
                },
                ...
            ]
        """
        # 1. Récupération des joueurs les plus actifs par nombre de claims décroissant
        if since_dt is not None:
            top_users = tx.all(
                """
                SELECT discord_id, COUNT(*) AS claim_count, SUM(amount) AS total_amount,
                       SUM(CASE WHEN is_auto = 1 THEN 1 ELSE 0 END) AS auto_count,
                       SUM(CASE WHEN is_auto = 0 THEN 1 ELSE 0 END) AS manual_count
                FROM daily_claim_logs
                WHERE claimed_at >= %s
                GROUP BY discord_id
                ORDER BY claim_count DESC
                LIMIT %s
                """,
                (since_dt, limit_users),
            )
        else:
            top_users = tx.all(
                """
                SELECT discord_id, COUNT(*) AS claim_count, SUM(amount) AS total_amount,
                       SUM(CASE WHEN is_auto = 1 THEN 1 ELSE 0 END) AS auto_count,
                       SUM(CASE WHEN is_auto = 0 THEN 1 ELSE 0 END) AS manual_count
                FROM daily_claim_logs
                GROUP BY discord_id
                ORDER BY claim_count DESC
                LIMIT %s
                """,
                (limit_users,),
            )

        if not top_users:
            return []

        user_ids = [row["discord_id"] for row in top_users]
        if not user_ids:
            return []

        # 2. Récupération de tous les claims chronologiques pour ces utilisateurs
        actual_claims_since = claims_since_dt if claims_since_dt is not None else since_dt
        placeholders = ", ".join(["%s"] * len(user_ids))
        if actual_claims_since is not None:
            params = tuple(user_ids) + (actual_claims_since,)
            rows = tx.all(
                f"""
                SELECT discord_id, claimed_at, interval_seconds, amount, is_auto
                FROM daily_claim_logs
                WHERE discord_id IN ({placeholders}) AND claimed_at >= %s
                ORDER BY claimed_at ASC
                """,
                params,
            )
        else:
            rows = tx.all(
                f"""
                SELECT discord_id, claimed_at, interval_seconds, amount, is_auto
                FROM daily_claim_logs
                WHERE discord_id IN ({placeholders})
                ORDER BY claimed_at ASC
                """,
                tuple(user_ids),
            )

        claims_by_user = {uid: [] for uid in user_ids}
        for row in rows:
            uid = row["discord_id"]
            claims_by_user[uid].append({
                "claimed_at": row["claimed_at"],
                "interval_seconds": row["interval_seconds"],
                "amount": row["amount"],
                "is_auto": bool(row.get("is_auto", 0)),
            })

        summary = []
        for user_row in top_users:
            uid = user_row["discord_id"]
            user_claims = claims_by_user.get(uid, [])
            auto_count = int(user_row.get("auto_count") if user_row.get("auto_count") is not None else sum(1 for c in user_claims if c.get("is_auto")))
            manual_count = int(user_row.get("manual_count") if user_row.get("manual_count") is not None else (len(user_claims) - auto_count))
            summary.append({
                "discord_id": uid,
                "claim_count": int(user_row["claim_count"]),
                "manual_count": manual_count,
                "auto_count": auto_count,
                "total_amount": user_row["total_amount"],
                "claims": user_claims,
            })

        return summary

    @staticmethod
    def get_user_claims(tx, discord_id: int, since_dt: datetime | None = None) -> list[dict]:
        """Retourne la liste chronologique complète des claims d'un joueur."""
        if since_dt is not None:
            rows = tx.all(
                """
                SELECT claimed_at, interval_seconds, amount, is_auto
                FROM daily_claim_logs
                WHERE discord_id = %s AND claimed_at >= %s
                ORDER BY claimed_at ASC
                """,
                (discord_id, since_dt),
            )
        else:
            rows = tx.all(
                """
                SELECT claimed_at, interval_seconds, amount, is_auto
                FROM daily_claim_logs
                WHERE discord_id = %s
                ORDER BY claimed_at ASC
                """,
                (discord_id,),
            )
        return [
            {
                "claimed_at": r["claimed_at"],
                "interval_seconds": r["interval_seconds"],
                "amount": r["amount"],
                "is_auto": bool(r.get("is_auto", 0)),
            }
            for r in rows
        ]

    @staticmethod
    def purge_older_than(tx, cutoff_dt: datetime) -> None:
        """Supprime les logs antérieurs à la date limite (rétention 24h glissante)."""
        tx.execute("DELETE FROM daily_claim_logs WHERE claimed_at < %s", (cutoff_dt,))

    @staticmethod
    def reset(tx) -> None:
        """Réinitialise tous les logs de la table (purge complète)."""
        tx.execute("DELETE FROM daily_claim_logs")

    @staticmethod
    def get_last_report_date(tx) -> str | None:
        """Retourne la date (YYYY-MM-DD) du dernier rapport quotidien de claims consigné."""
        row = tx.one("SELECT last_found_on FROM events WHERE event = 'daily_claim_report'")
        return row["last_found_on"] if row else None

    @staticmethod
    def set_last_report_date(tx, date_str: str, now_dt: datetime) -> None:
        """Enregistre la date (YYYY-MM-DD) et l'horodatage du dernier rapport quotidien de claims."""
        tx.execute(
            """
            INSERT INTO events (event, next_at, last_found_on, last_reward)
            VALUES ('daily_claim_report', %s, %s, 0.00)
            ON DUPLICATE KEY UPDATE
                next_at = VALUES(next_at),
                last_found_on = VALUES(last_found_on)
            """,
            (now_dt, date_str),
        )

