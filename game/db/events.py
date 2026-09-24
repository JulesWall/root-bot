"""
Gestionnaire de persistance et d'état pour la table SQL 'events'.

Gère les événements globaux du bot (notamment le mini-jeu Hash Challenge) :
- Enregistrement du prochain horodatage disponible (next_at).
- Traçabilité du dernier joueur ayant trouvé le hash (last_found_by) et du serveur d'origine (last_found_on).
- Récompense distribuée (last_reward).
"""

from datetime import datetime
from decimal import Decimal


class EventsDB:
    """Accès aux données pour la table events."""

    @staticmethod
    def get(tx, event_name: str = 'hash') -> dict | None:
        """Récupère l'état d'un événement donné."""
        return tx.one("SELECT * FROM events WHERE event = %s", (event_name,))

    @staticmethod
    def save(
        tx,
        event_name: str,
        next_at: datetime,
        last_found_by: int | None = None,
        last_found_on: str | None = None,
        last_reward: Decimal = Decimal('0.00')
    ) -> dict:
        """
        Insère ou met à jour l'événement en base via UPSERT (ON DUPLICATE KEY UPDATE).
        """
        tx.execute(
            """
            INSERT INTO events (event, next_at, last_found_by, last_found_on, last_reward)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                next_at = VALUES(next_at),
                last_found_by = VALUES(last_found_by),
                last_found_on = VALUES(last_found_on),
                last_reward = VALUES(last_reward)
            """,
            (event_name, next_at, last_found_by, last_found_on, last_reward)
        )
        return tx.one("SELECT * FROM events WHERE event = %s", (event_name,))

    @staticmethod
    def record_availability(
        tx,
        event_name: str,
        opened_at: datetime,
        solved_at: datetime,
        duration_seconds: int,
        winner_id: int | None = None,
        reward: Decimal = Decimal('0.00'),
    ) -> None:
        """Enregistre une résolution d'événement avec le temps pendant lequel il est resté disponible."""
        tx.execute(
            """
            INSERT INTO event_availability_logs
                (event, opened_at, solved_at, duration_seconds, winner_id, reward)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (event_name, opened_at, solved_at, max(0, int(duration_seconds)), winner_id, reward),
        )

    @staticmethod
    def get_recent_wins_for_user(tx, winner_id: int, limit: int = 20, since_dt: datetime | None = None) -> list[dict]:
        """Récupère l'historique récent des victoires d'un joueur depuis event_availability_logs."""
        if since_dt is not None:
            return tx.all(
                """
                SELECT id, event, opened_at, solved_at, duration_seconds, winner_id, reward
                FROM event_availability_logs
                WHERE winner_id = %s AND solved_at >= %s
                ORDER BY solved_at DESC
                LIMIT %s
                """,
                (winner_id, since_dt, limit),
            ) or []
        return tx.all(
            """
            SELECT id, event, opened_at, solved_at, duration_seconds, winner_id, reward
            FROM event_availability_logs
            WHERE winner_id = %s
            ORDER BY solved_at DESC
            LIMIT %s
            """,
            (winner_id, limit),
        ) or []

    @staticmethod
    def get_resolution_metrics_by_user(tx, since_dt: datetime | None = None) -> dict[int, list[dict]]:
        """Récupère les résolutions d'événements groupées par joueur pour la période considérée."""
        if since_dt is not None:
            rows = tx.all(
                """
                SELECT event, opened_at, solved_at, duration_seconds, winner_id, reward
                FROM event_availability_logs
                WHERE winner_id IS NOT NULL AND solved_at >= %s
                ORDER BY solved_at ASC
                """,
                (since_dt,),
            ) or []
        else:
            rows = tx.all(
                """
                SELECT event, opened_at, solved_at, duration_seconds, winner_id, reward
                FROM event_availability_logs
                WHERE winner_id IS NOT NULL
                ORDER BY solved_at ASC
                """,
            ) or []

        grouped = {}
        for r in rows:
            wid = int(r["winner_id"])
            if wid not in grouped:
                grouped[wid] = []
            grouped[wid].append(r)
        return grouped


