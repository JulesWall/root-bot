"""Commande /event et !event (alias !events, !e) — Statut des événements réseau.

Ce module permet de consulter en temps réel la disponibilité et le temps d'attente
pour l'ensemble des défis et événements communautaires de Root :
- Hash Challenge (/hash)
- Code PIN (/pin)
"""

from datetime import datetime, timezone
import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from game.events_manager import EventsManager
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text


class Event(BaseGameCog):
    """Cog gérant l'affichage des statuts et comptes à rebours des événements."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="event",
        description=EN["event"],
        description_localizations={"fr": FR["event"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def event(self, ctx):
        """Consulter le statut et le temps restant avant chaque événement réseau."""
        await self._invoke(ctx, "event")

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="event", aliases=["events", "e"], help=FR["event"])
    async def prefix_event(self, ctx):
        """Commande préfixe !event (alias !events, !e)."""
        await self._invoke(ctx, "event")

    @staticmethod
    def _sort_events(events_dict: dict) -> list[tuple[str, dict]]:
        """
        Trie les mini-jeux par ordre chronologique d'apparition :
        - Événements actifs en premier (du plus ancien au plus récent).
        - Événements en cooldown ensuite (du plus proche au plus lointain).
        """
        def _sort_key(item):
            name, data = item
            is_active = data.get("status") == "active"
            nxt = data.get("next_at")
            if nxt is not None and getattr(nxt, "tzinfo", None) is not None:
                dt = nxt.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                dt = nxt
            idx = EventsManager.SUPPORTED_EVENTS.index(name) if name in EventsManager.SUPPORTED_EVENTS else 999
            if is_active:
                return (0, dt or datetime.min, idx)
            else:
                return (1, dt or datetime.max, idx)

        return sorted(events_dict.items(), key=_sort_key)

    # ── Rendu & Affichage ────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Formate et expédie le rapport d'état des événements dans un RootEmbed."""
        is_slash = bool(getattr(ctx, "interaction", None))
        prefix = "/" if is_slash else (getattr(ctx, "clean_prefix", None) or getattr(ctx, "prefix", "+r"))

        # Le service renvoie {'events': {hash: {...}, pin: {...}, ...}}
        events_data = (result or {}).get("events", {})
        sorted_events = self._sort_events(events_data)

        blocks = []
        for event_key, event_info in sorted_events:
            lines = []
            lines.append(text.get(ctx, f"g_event_{event_key}_name", prefix=prefix))

            if event_info.get("status") == "active":
                desc = text.get(ctx, f"g_event_{event_key}_desc")
                lines.append(text.get(ctx, "g_event_status_active", desc=desc, prefix=prefix, cmd=event_key))
            else:
                next_at = event_info.get("next_at")
                if next_at and hasattr(next_at, "timestamp"):
                    if getattr(next_at, "tzinfo", None) is None:
                        next_at_utc = next_at.replace(tzinfo=timezone.utc)
                    else:
                        next_at_utc = next_at
                    ts = int(next_at_utc.timestamp())
                else:
                    rem_sec = event_info.get("remaining_seconds", 0)
                    ts = int(discord.utils.utcnow().timestamp()) + rem_sec

                time_display = f"<t:{ts}:T> (<t:{ts}:R>)"
                lines.append(text.get(ctx, "g_event_status_cooldown", timestamp=ts, remaining=time_display))

                if event_info.get("last_found_by"):
                    user_id = event_info["last_found_by"]
                    winner_display = await self._format_user_display(user_id)
                    lines.append(text.get(
                        ctx,
                        "g_event_last_winner",
                        winner=winner_display,
                        server=event_info.get("last_found_on", "Inconnu"),
                    ))

            blocks.append("\n".join(lines))

        content = "\n\n".join(blocks)
        await self._send_embed(ctx, "event", content)

    async def _format_user_display(self, user_id: int) -> str:
        """Résout le pseudo du joueur pour un affichage lisible <@id> (`username`)."""
        winner_obj = self.bot.get_user(user_id)
        if not winner_obj:
            try:
                winner_obj = await self.bot.fetch_user(user_id)
            except Exception:
                winner_obj = None

        if winner_obj:
            winner_name = getattr(winner_obj, "name", str(user_id))
            return f"<@{user_id}> (`{winner_name}`)"
        return f"<@{user_id}>"


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Event(bot))

