"""Commande /event et !event (alias !events, !e) — Statut des événements réseau.

Ce module permet de consulter en temps réel la disponibilité et le temps d'attente
pour l'ensemble des défis et événements communautaires de Root :
- Hash Challenge (/hash)
- Code PIN (/pin)
"""

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.time_format import format_duration


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

    # ── Rendu & Affichage ────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Formate et expédie le rapport d'état des événements dans un RootEmbed."""
        is_slash = bool(getattr(ctx, "interaction", None))
        prefix = "/" if is_slash else (getattr(ctx, "clean_prefix", None) or getattr(ctx, "prefix", "+r"))

        # Le service renvoie {'events': {hash: {...}, pin: {...}, ...}}
        events_data = (result or {}).get("events", {})

        lines = []

        # 1. 🧩 Hash Challenge
        hash_info = events_data.get("hash", {})
        lines.append(text.get(ctx, "g_event_hash_name", prefix=prefix))
        if hash_info.get("status") == "active":
            desc = text.get(ctx, "g_event_hash_desc")
            lines.append(text.get(ctx, "g_event_status_active", desc=desc, prefix=prefix, cmd="hash"))
        else:
            remaining_str = format_duration(hash_info.get("remaining_seconds", 0))
            lines.append(text.get(ctx, "g_event_status_cooldown", remaining=remaining_str))

            if hash_info.get("last_found_by"):
                user_id = hash_info["last_found_by"]
                winner_display = await self._format_user_display(user_id)
                lines.append(text.get(
                    ctx,
                    "g_event_last_winner",
                    winner=winner_display,
                    server=hash_info.get("last_found_on", "Inconnu"),
                ))

        lines.append("")

        # 2. 🔐 Code PIN
        pin_info = events_data.get("pin", {})
        lines.append(text.get(ctx, "g_event_pin_name", prefix=prefix))
        if pin_info.get("status") == "active":
            desc = text.get(ctx, "g_event_pin_desc")
            lines.append(text.get(ctx, "g_event_status_active", desc=desc, prefix=prefix, cmd="pin"))
        else:
            remaining_str = format_duration(pin_info.get("remaining_seconds", 0))
            lines.append(text.get(ctx, "g_event_status_cooldown", remaining=remaining_str))

            if pin_info.get("last_found_by"):
                user_id = pin_info["last_found_by"]
                winner_display = await self._format_user_display(user_id)
                lines.append(text.get(
                    ctx,
                    "g_event_last_winner",
                    winner=winner_display,
                    server=pin_info.get("last_found_on", "Inconnu"),
                ))

        lines.append("")

        # 3. 🔍 Décryptage
        decode_info = events_data.get("decode", {})
        lines.append(text.get(ctx, "g_event_decode_name", prefix=prefix))
        if decode_info.get("status") == "active":
            desc = text.get(ctx, "g_event_decode_desc")
            lines.append(text.get(ctx, "g_event_status_active", desc=desc, prefix=prefix, cmd="decode"))
        else:
            remaining_str = format_duration(decode_info.get("remaining_seconds", 0))
            lines.append(text.get(ctx, "g_event_status_cooldown", remaining=remaining_str))

            if decode_info.get("last_found_by"):
                user_id = decode_info["last_found_by"]
                winner_display = await self._format_user_display(user_id)
                lines.append(text.get(
                    ctx,
                    "g_event_last_winner",
                    winner=winner_display,
                    server=decode_info.get("last_found_on", "Inconnu"),
                ))

        lines.append("")

        # 4. ⚠️ Anomaly
        anomaly_info = events_data.get("anomaly", {})
        lines.append(text.get(ctx, "g_event_anomaly_name", prefix=prefix))
        if anomaly_info.get("status") == "active":
            desc = text.get(ctx, "g_event_anomaly_desc")
            lines.append(text.get(ctx, "g_event_status_active", desc=desc, prefix=prefix, cmd="anomaly"))
        else:
            remaining_str = format_duration(anomaly_info.get("remaining_seconds", 0))
            lines.append(text.get(ctx, "g_event_status_cooldown", remaining=remaining_str))

            if anomaly_info.get("last_found_by"):
                user_id = anomaly_info["last_found_by"]
                winner_display = await self._format_user_display(user_id)
                lines.append(text.get(
                    ctx,
                    "g_event_last_winner",
                    winner=winner_display,
                    server=anomaly_info.get("last_found_on", "Inconnu"),
                ))

        lines.append("")

        # 5. 📦 Buffer
        buffer_info = events_data.get("buffer", {})
        lines.append(text.get(ctx, "g_event_buffer_name", prefix=prefix))
        if buffer_info.get("status") == "active":
            desc = text.get(ctx, "g_event_buffer_desc")
            lines.append(text.get(ctx, "g_event_status_active", desc=desc, prefix=prefix, cmd="buffer"))
        else:
            remaining_str = format_duration(buffer_info.get("remaining_seconds", 0))
            lines.append(text.get(ctx, "g_event_status_cooldown", remaining=remaining_str))

            if buffer_info.get("last_found_by"):
                user_id = buffer_info["last_found_by"]
                winner_display = await self._format_user_display(user_id)
                lines.append(text.get(
                    ctx,
                    "g_event_last_winner",
                    winner=winner_display,
                    server=buffer_info.get("last_found_on", "Inconnu"),
                ))

        lines.append("")

        # 6. 📡 Signal
        signal_info = events_data.get("signal", {})
        lines.append(text.get(ctx, "g_event_signal_name", prefix=prefix))
        if signal_info.get("status") == "active":
            desc = text.get(ctx, "g_event_signal_desc")
            lines.append(text.get(ctx, "g_event_status_active", desc=desc, prefix=prefix, cmd="signal"))
        else:
            remaining_str = format_duration(signal_info.get("remaining_seconds", 0))
            lines.append(text.get(ctx, "g_event_status_cooldown", remaining=remaining_str))

            if signal_info.get("last_found_by"):
                user_id = signal_info["last_found_by"]
                winner_display = await self._format_user_display(user_id)
                lines.append(text.get(
                    ctx,
                    "g_event_last_winner",
                    winner=winner_display,
                    server=signal_info.get("last_found_on", "Inconnu"),
                ))

        lines.append("")

        # 7. 🛰️ Packet
        packet_info = events_data.get("packet", {})
        lines.append(text.get(ctx, "g_event_packet_name", prefix=prefix))
        if packet_info.get("status") == "active":
            desc = text.get(ctx, "g_event_packet_desc")
            lines.append(text.get(ctx, "g_event_status_active", desc=desc, prefix=prefix, cmd="packet"))
        else:
            remaining_str = format_duration(packet_info.get("remaining_seconds", 0))
            lines.append(text.get(ctx, "g_event_status_cooldown", remaining=remaining_str))

            if packet_info.get("last_found_by"):
                user_id = packet_info["last_found_by"]
                winner_display = await self._format_user_display(user_id)
                lines.append(text.get(
                    ctx,
                    "g_event_last_winner",
                    winner=winner_display,
                    server=packet_info.get("last_found_on", "Inconnu"),
                ))

        content = "\n".join(lines)
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

