"""
Gestionnaire de persistance et de requêtes pour la table SQL 'daily_event_stats'.

Permet le suivi des statistiques d'événements sur 24 heures pour la modération et la détection anti-triche :
- Enregistrement des participations (tentatives de réponse).
- Enregistrement des victoires d'événements.
- Extraction du récapitulatif 24h trié par nombre de victoires.
- Remise à zéro quotidienne des compteurs.
"""

from datetime import datetime


class DailyEventStatsDB:
    """Accès aux données pour la table daily_event_stats."""

    @staticmethod
    def record_participation(tx, discord_id: int, date_key: str | None = None):
        """Incrémente le compteur de participations (tentatives) du joueur."""
        d_key = date_key or (tx.now.strftime("%Y-%m-%d") if hasattr(tx, "now") else None)
        try:
            tx.execute(
                """
                INSERT INTO daily_event_stats (discord_id, date_key, events_won, events_participated)
                VALUES (%s, %s, 0, 1)
                ON DUPLICATE KEY UPDATE events_participated = events_participated + 1
                """,
                (discord_id, d_key),
            )
        except Exception:
            tx.execute(
                """
                INSERT INTO daily_event_stats (discord_id, events_won, events_participated)
                VALUES (%s, 0, 1)
                ON DUPLICATE KEY UPDATE events_participated = events_participated + 1
                """,
                (discord_id,),
            )

    @staticmethod
    def record_win(tx, discord_id: int, date_key: str | None = None):
        """Incrémente le compteur de victoires d'événements du joueur."""
        d_key = date_key or (tx.now.strftime("%Y-%m-%d") if hasattr(tx, "now") else None)
        try:
            tx.execute(
                """
                INSERT INTO daily_event_stats (discord_id, date_key, events_won, events_participated)
                VALUES (%s, %s, 1, 0)
                ON DUPLICATE KEY UPDATE events_won = events_won + 1
                """,
                (discord_id, d_key),
            )
        except Exception:
            tx.execute(
                """
                INSERT INTO daily_event_stats (discord_id, events_won, events_participated)
                VALUES (%s, 1, 0)
                ON DUPLICATE KEY UPDATE events_won = events_won + 1
                """,
                (discord_id,),
            )

    @staticmethod
    def get_summary(tx, limit: int = 50, date_str: str | None = None) -> list[dict]:
        """Retourne le classement trié par victoires décroissantes puis participations."""
        if date_str:
            try:
                res = tx.all(
                    """
                    SELECT discord_id, events_won, events_participated
                    FROM daily_event_stats
                    WHERE date_key = %s AND (events_won > 0 OR events_participated > 0)
                    ORDER BY events_won DESC, events_participated DESC
                    LIMIT %s
                    """,
                    (date_str, limit),
                )
                if res is not None:
                    return res
            except Exception:
                pass
        return tx.all(
            """
            SELECT discord_id, events_won, events_participated
            FROM daily_event_stats
            WHERE events_won > 0 OR events_participated > 0
            ORDER BY events_won DESC, events_participated DESC
            LIMIT %s
            """,
            (limit,),
        ) or []

    @staticmethod
    def purge_older_than(tx, cutoff_date_str: str) -> None:
        """Supprime les statistiques antérieures à la date limite (rétention 24h glissante)."""
        try:
            tx.execute("DELETE FROM daily_event_stats WHERE date_key < %s", (cutoff_date_str,))
        except Exception:
            pass

    @staticmethod
    def get_user_event_stats(tx, discord_id: int, since_date_str: str | None = None) -> dict:
        """Retourne le cumul des victoires et participations d'un joueur (sur les 24h retenues)."""
        if since_date_str:
            try:
                row = tx.one(
                    """
                    SELECT 
                        COALESCE(SUM(events_won), 0) AS total_won,
                        COALESCE(SUM(events_participated), 0) AS total_participated
                    FROM daily_event_stats
                    WHERE discord_id = %s AND date_key >= %s
                    """,
                    (discord_id, since_date_str),
                )
                if row:
                    return {
                        "events_won": int(row.get("total_won") or 0),
                        "events_participated": int(row.get("total_participated") or 0),
                    }
            except Exception:
                pass
        row = tx.one(
            """
            SELECT events_won, events_participated
            FROM daily_event_stats
            WHERE discord_id = %s
            """,
            (discord_id,),
        )
        if not row:
            return {"events_won": 0, "events_participated": 0}
        return {
            "events_won": int(row.get("events_won") or 0),
            "events_participated": int(row.get("events_participated") or 0),
        }

    @staticmethod
    def reset(tx):
        """Réinitialise tous les compteurs de la table (purge complète)."""
        tx.execute("DELETE FROM daily_event_stats")

    @staticmethod
    def get_last_report_date(tx) -> str | None:
        """Retourne la date (YYYY-MM-DD) du dernier rapport quotidien consigné."""
        row = tx.one("SELECT last_found_on FROM events WHERE event = 'daily_moderation_report'")
        return row["last_found_on"] if row else None

    @staticmethod
    def set_last_report_date(tx, date_str: str, now_dt: datetime):
        """Enregistre la date (YYYY-MM-DD) et l'horodatage du dernier rapport quotidien."""
        tx.execute(
            """
            INSERT INTO events (event, next_at, last_found_on, last_reward)
            VALUES ('daily_moderation_report', %s, %s, 0.00)
            ON DUPLICATE KEY UPDATE
                next_at = VALUES(next_at),
                last_found_on = VALUES(last_found_on)
            """,
            (now_dt, date_str),
        )

