"""Commande /hourly et !hourly (alias !hr) — Récompense horaire et combo minuté.

Ce module permet aux joueurs d'obtenir une prime en dollars toutes les heures :
- Gain de base aléatoire entre 30 et 90 USD (tirage uniforme).
- Délai de rechargement (cooldown) strict de 60 minutes.
- Fenêtre de combo de 20 minutes (entre 1h00 et 1h20 après la précédente récolte) :
  Un bonus de pourcentage (20 - temps - 60)% s'accumule sans limite de plafond.
- Au-delà de 1h20 : le combo est perdu (réinitialisé à 0%, série ramenée à 1).
- Traçabilité complète via le système de logs de modération.
"""

from decimal import Decimal

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils.text import format_usd, get as text_get


def _pct(value) -> str:
    """Affiche un pourcentage sans décimale inutile."""
    amount = Decimal(str(value or 0))
    if amount == amount.to_integral_value():
        return str(int(amount))
    return f"{amount:.1f}"


class Hourly(BaseGameCog):
    """Cog gérant la commande /hourly et le système de combo."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="hourly",
        description=EN["hourly"],
        description_localizations={"fr": FR["hourly"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def hourly(self, ctx):
        """Réclamer sa récompense horaire en USD avec bonus de combo."""
        await self._invoke(ctx, "hourly")

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="hourly", aliases=["hr"], help=FR["hourly"])
    async def prefix_hourly(self, ctx):
        """Commande préfixe !hourly (alias !hr)."""
        await self._invoke(ctx, "hourly")

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Affiche le rapport de récompense horaire et déclenche la journalisation."""
        base_usd = result["base_usd"]
        bonus_pct = result["bonus_pct"]
        step_bonus_pct = result["step_bonus_pct"]
        total_usd = result["total_usd"]
        new_dollars = result["new_dollars"]
        streak = result["streak"]
        combo_lost = result["combo_lost"]
        is_first = result["is_first"]
        next_ts = result["next_available_ts"]
        combo_ts = result["combo_deadline_ts"]
        interval_seconds = result.get("interval_seconds")

        values = {
            "total": format_usd(total_usd),
            "balance": format_usd(new_dollars),
            "bonus": _pct(bonus_pct),
            "step": _pct(step_bonus_pct),
            "streak": streak,
            "next_ts": next_ts,
            "combo_ts": combo_ts,
        }
        if is_first:
            key = "g_hourly_first"
        elif combo_lost:
            key = "g_hourly_broken"
        elif step_bonus_pct > 0:
            key = "g_hourly_combo"
        else:
            key = "g_hourly_held"
        content = text_get(ctx, key, **values)
        mentions = discord.AllowedMentions.none()

        if getattr(ctx, "interaction", None):
            await ctx.respond(content, allowed_mentions=mentions)
        else:
            await ctx.send(content, allowed_mentions=mentions)

        # Journalisation Discord asynchrone
        try:
            author = getattr(ctx, "author", None) or getattr(ctx, "user", None)
            if author:
                await self.bot.discord_logger.log_hourly(
                    ctx=ctx,
                    user=author,
                    base_usd=base_usd,
                    bonus_pct=bonus_pct,
                    total_usd=total_usd,
                    streak=streak,
                    interval_seconds=interval_seconds,
                    combo_lost=combo_lost,
                    is_first=is_first,
                    step_bonus_pct=step_bonus_pct,
                    new_dollars=new_dollars,
                )
        except Exception:
            pass


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Hourly(bot))

