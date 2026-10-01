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
import time

import discord

from utils.root_embed import RootEmbed
from utils.root_theme import VisualState
from utils.time_format import format_duration

logger = logging.getLogger(__name__)

# Nombre maximal de messages actifs suivis par type de mini-jeu
MAX_ACTIVE_MESSAGES: int = 10
# Durée de vie maximale d'un message actif avant expiration (1 heure)
MESSAGE_TTL_SECONDS: float = 3600.0


class ChallengeTracker:
    """Registre en mémoire des messages actifs de mini-jeux avec diffusion de fin de manche."""

    # Dictionnaire {game_key: list[discord.Message]}
    _active_messages: dict[str, list[discord.Message]] = {}
    # Registre des horodatages pour les objets discord.Message dotés de __slots__ sans __dict__
    _message_timestamps: dict[int, float] = {}
    _lock = asyncio.Lock()

    @classmethod
    def _get_registered_at(cls, msg: discord.Message, default: float) -> float:
        """Récupère le timestamp d'enregistrement (attribut si présent ou registre interne par id)."""
        custom_ts = getattr(msg, "_challenge_registered_at", None)
        if custom_ts is not None:
            return custom_ts
        msg_id = getattr(msg, "id", None)
        if msg_id is not None:
            return cls._message_timestamps.get(msg_id, default)
        return default

    @classmethod
    async def register_message(cls, game_key: str, message: discord.Message | None):
        """Enregistre la référence d'un message affichant le défi en cours avec limitation et déduplication."""
        if not message or not isinstance(message, discord.Message):
            return

        now = time.monotonic()
        msg_id = getattr(message, "id", None)
        if msg_id is not None:
            cls._message_timestamps[msg_id] = now

        try:
            setattr(message, "_challenge_registered_at", now)
        except (AttributeError, TypeError):
            pass

        async with cls._lock:
            messages = cls._active_messages.setdefault(game_key, [])
            # Nettoyage des messages expirés selon le TTL
            kept_messages = []
            for m in messages:
                reg_time = cls._get_registered_at(m, now)
                if (now - reg_time) < MESSAGE_TTL_SECONDS:
                    kept_messages.append(m)
                else:
                    mid = getattr(m, "id", None)
                    if mid is not None:
                        cls._message_timestamps.pop(mid, None)
            messages = kept_messages

            # Déduplication par ID de message
            if msg_id is not None:
                messages = [m for m in messages if getattr(m, "id", None) != msg_id]
            messages.append(message)
            # Plafonnement aux MAX_ACTIVE_MESSAGES les plus récents (évite la saturation de l'API Discord)
            if len(messages) > MAX_ACTIVE_MESSAGES:
                dropped = messages[:-MAX_ACTIVE_MESSAGES]
                for d in dropped:
                    did = getattr(d, "id", None)
                    if did is not None:
                        cls._message_timestamps.pop(did, None)
                messages = messages[-MAX_ACTIVE_MESSAGES:]
            cls._active_messages[game_key] = messages

    @classmethod
    async def notify_win(
        cls,
        game_key: str,
        winner_id: int,
        next_at: datetime | None,
        solved_message_id: int | None = None,
    ):
        """
        Édite les messages actifs enregistrés pour cette catégorie de défi,
        sauf le message ayant notifié la victoire, de manière concurrente et bornée.
        """
        async with cls._lock:
            messages = cls._active_messages.pop(game_key, [])

        if not messages:
            return

        now_utc = datetime.now(timezone.utc)
        now_mono = time.monotonic()
        if next_at:
            if next_at.tzinfo is None:
                next_at_utc = next_at.replace(tzinfo=timezone.utc)
            else:
                next_at_utc = next_at
            remaining_secs = max(0, int((next_at_utc - now_utc).total_seconds()))
            ts = int(next_at_utc.timestamp())
            remaining_str = format_duration(remaining_secs)
            time_display = f"<t:{ts}:R> (`{remaining_str}`)"
        else:
            time_display = "bientôt"

        notice_content = (
            f"🏆 <@{winner_id}> a résolu le défi !\n"
            f"⏱️ Prochain événement disponible {time_display}."
        )

        seen_ids = set()
        to_edit = []
        for msg in messages:
            msg_id = getattr(msg, "id", None)
            if msg_id is not None:
                cls._message_timestamps.pop(msg_id, None)
            if solved_message_id is not None and msg_id == solved_message_id:
                continue
            if msg_id is not None:
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)
            # Ignorer les messages ayant dépassé le TTL
            reg_time = cls._get_registered_at(msg, now_mono)
            if (now_mono - reg_time) >= MESSAGE_TTL_SECONDS:
                continue
            to_edit.append(msg)

        if not to_edit:
            return

        embed = RootEmbed(
            None,
            action=game_key,
            content=notice_content,
            title="ROOT OS · Défi résolu",
            state=VisualState.SUCCESS,
        )

        async def _safe_edit(msg: discord.Message):
            try:
                await msg.edit(content=notice_content, embed=embed, view=None)
            except (discord.NotFound, discord.Forbidden):
                pass
            except Exception as exc:
                logger.debug("Échec de l'édition du message de défi %s: %s", getattr(msg, "id", None), exc)

        # Exécution concurrente sans bloquer séquentiellement
        await asyncio.gather(*[_safe_edit(m) for m in to_edit], return_exceptions=True)

