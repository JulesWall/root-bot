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
    def record_participation(tx, discord_id: int):
        """Incrémente le compteur de participations (tentatives) du joueur sur 24h."""
        tx.execute(
            """
            INSERT INTO daily_event_stats (discord_id, events_won, events_participated)
            VALUES (%s, 0, 1)
            ON DUPLICATE KEY UPDATE events_participated = events_participated + 1
            """,
            (discord_id,),
        )

    @staticmethod
    def record_win(tx, discord_id: int):
        """Incrémente le compteur de victoires d'événements du joueur sur 24h."""
        tx.execute(
            """
            INSERT INTO daily_event_stats (discord_id, events_won, events_participated)
            VALUES (%s, 1, 0)
            ON DUPLICATE KEY UPDATE events_won = events_won + 1
            """,
            (discord_id,),
        )

    @staticmethod
    def get_summary(tx, limit: int = 50) -> list[dict]:
        """Retourne le classement des 24h trié par victoires décroissantes puis participations."""
        return tx.all(
            """
            SELECT discord_id, events_won, events_participated
            FROM daily_event_stats
            WHERE events_won > 0 OR events_participated > 0
            ORDER BY events_won DESC, events_participated DESC
            LIMIT %s
            """,
            (limit,),
        )

    @staticmethod
    def reset(tx):
        """Réinitialise tous les compteurs de la table pour une nouvelle journée de 24h."""
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

