"""
Gestionnaire de synchronisation et de mise à jour des messages actifs de défis.

Ce module suit les messages affichant une grille ou un défi en cours (active_info).
Dès qu'un joueur résout le défi, tous les messages actifs enregistrés sont automatiquement
édités pour avertir immédiatement les observateurs que le défi a été remporté, évitant ainsi
qu'ils continuent à chercher pour rien.
"""

import asyncio
from datetime import datetime, timezone
import logging

import discord

from utils.time_format import format_duration

logger = logging.getLogger(__name__)


class ChallengeTracker:
    """Registre en mémoire des messages actifs de mini-jeux avec diffusion de fin de manche."""

    # Dictionnaire {game_key: list[discord.Message]}
    _active_messages: dict[str, list[discord.Message]] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def register_message(cls, game_key: str, message: discord.Message | None):
        """Enregistre la référence d'un message affichant le défi en cours."""
        if not message or not isinstance(message, discord.Message):
            return
        async with cls._lock:
            cls._active_messages.setdefault(game_key, [])
            cls._active_messages[game_key].append(message)

    @classmethod
    async def notify_win(
        cls,
        game_key: str,
        winner_id: int,
        next_at: datetime | None,
        solved_message_id: int | None = None,
    ):
        """
        Édite tous les messages actifs enregistrés pour cette catégorie de défi,
        sauf éventuellement le message qui vient de notifier la victoire.
        """
        async with cls._lock:
            messages = cls._active_messages.pop(game_key, [])

        if not messages:
            return

        now = datetime.now(timezone.utc)
        if next_at:
            if next_at.tzinfo is None:
                next_at_utc = next_at.replace(tzinfo=timezone.utc)
            else:
                next_at_utc = next_at
            remaining_secs = max(0, int((next_at_utc - now).total_seconds()))
            ts = int(next_at_utc.timestamp())
            remaining_str = format_duration(remaining_secs)
            time_display = f"<t:{ts}:R> (`{remaining_str}`)"
        else:
            time_display = "bientôt"

        notice_content = (
            f"🏆 <@{winner_id}> a résolu le défi !\n"
            f"⏱️ Prochain événement disponible {time_display}."
        )

        for msg in messages:
            if solved_message_id and getattr(msg, "id", None) == solved_message_id:
                continue
            try:
                await msg.edit(content=notice_content, embed=None, view=None)
            except (discord.NotFound, discord.Forbidden):
                pass
            except Exception as exc:
                logger.debug("Échec de l'édition du message de défi %s: %s", getattr(msg, "id", None), exc)

