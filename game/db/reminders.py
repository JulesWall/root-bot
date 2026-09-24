"""
Gestionnaire d'accès aux données pour la table SQL 'reminders'.

Permet la planification, la consultation, l'annulation et la distribution
des rappels personnalisés et alertes de jeu (/rmd).
"""

from datetime import datetime
from game.game_error import GameError

MAX_ACTIVE_REMINDERS_PER_PLAYER = 10


class RemindersDB:
    """DAO pour la gestion des rappels et alertes temporelles."""

    @staticmethod
    def count_user_reminders(tx, discord_id: int) -> int:
        """Retourne le nombre de rappels actuellement programmés pour un joueur."""
        row = tx.one("SELECT COUNT(*) AS count FROM reminders WHERE discord_id = %s", (discord_id,))
        return int(row.get("count", 0)) if row else 0

    @staticmethod
    def create_reminder(
        tx,
        discord_id: int,
        remind_at: datetime,
        message: str = "Rappel",
        channel_id: int | None = None,
        guild_id: int | None = None,
        reminder_type: str = "custom",
        target_event: str | None = None,
    ) -> dict:
        """Enregistre un nouveau rappel après vérification du quota maximal."""
        current_count = RemindersDB.count_user_reminders(tx, discord_id)
        if current_count >= MAX_ACTIVE_REMINDERS_PER_PLAYER:
            raise GameError("reminder_limit_reached", max_count=MAX_ACTIVE_REMINDERS_PER_PLAYER)

        clean_message = (message or "Rappel")[:200]

        rid = tx.execute(
            """
            INSERT INTO reminders (
                discord_id, channel_id, guild_id, reminder_type, target_event, message, created_at, remind_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                discord_id,
                channel_id,
                guild_id,
                reminder_type,
                target_event,
                clean_message,
                tx.now,
                remind_at,
            ),
        )

        return {
            "id": rid,
            "discord_id": discord_id,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "reminder_type": reminder_type,
            "target_event": target_event,
            "message": clean_message,
            "created_at": tx.now,
            "remind_at": remind_at,
        }

    @staticmethod
    def get_user_reminders(tx, discord_id: int) -> list[dict]:
        """Retourne tous les rappels actifs d'un joueur ordonnés par échéance croissante."""
        return tx.all(
            """
            SELECT id, discord_id, channel_id, guild_id, reminder_type, target_event, message, created_at, remind_at
            FROM reminders
            WHERE discord_id = %s
            ORDER BY remind_at ASC
            """,
            (discord_id,),
        ) or []

    @staticmethod
    def delete_reminder(tx, reminder_id: int, discord_id: int) -> bool:
        """Supprime un rappel spécifique appartenant au joueur. Renvoie True si supprimé."""
        affected = tx.execute(
            "DELETE FROM reminders WHERE id = %s AND discord_id = %s",
            (reminder_id, discord_id),
        )
        return bool(affected)

    @staticmethod
    def clear_user_reminders(tx, discord_id: int) -> int:
        """Supprime tous les rappels actifs d'un joueur et renvoie le nombre supprimé."""
        affected = tx.execute(
            "DELETE FROM reminders WHERE discord_id = %s",
            (discord_id,),
        )
        return int(affected or 0)

    @staticmethod
    def deliver_expired_reminders(tx) -> list[dict]:
        """
        Sélectionne tous les rappels dont l'échéance est dépassée (remind_at <= now),
        les supprime en transaction et les retourne pour expédition de notification.
        """
        rows = tx.all(
            """
            SELECT id, discord_id, channel_id, guild_id, reminder_type, target_event, message, created_at, remind_at
            FROM reminders
            WHERE remind_at <= %s
            ORDER BY remind_at ASC
            """,
            (tx.now,),
        )
        if not rows:
            return []

        ids = [r["id"] for r in rows if r.get("id")]
        if ids:
            format_strings = ",".join(["%s"] * len(ids))
            tx.execute(f"DELETE FROM reminders WHERE id IN ({format_strings})", tuple(ids))

        return rows

    @staticmethod
    def reschedule_claim_reminder(tx, discord_id: int, new_remind_at: datetime) -> int:
        """
        Reprogramme l'échéance des rappels de claim actifs pour un joueur.
        Permet de synchroniser les alertes /rmd claim lorsque le joueur vide
        sa mémoire vive plus tôt que prévu ou fait évoluer son matériel.
        Retourne le nombre de rappels mis à jour.
        """
        existing = tx.one(
            "SELECT id FROM reminders WHERE discord_id = %s AND reminder_type = 'claim' LIMIT 1",
            (discord_id,),
        )
        if not existing:
            return 0

        tx.execute(
            """
            UPDATE reminders
            SET remind_at = %s
            WHERE discord_id = %s AND reminder_type = 'claim'
            """,
            (new_remind_at, discord_id),
        )
        return 1

