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
from utils.root_embed import RootEmbed
from utils.text import format_usd


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
        bonus_usd = result["bonus_usd"]
        total_usd = result["total_usd"]
        new_dollars = result["new_dollars"]
        streak = result["streak"]
        combo_lost = result["combo_lost"]
        is_first = result["is_first"]
        next_ts = result["next_available_ts"]
        combo_ts = result["combo_deadline_ts"]
        interval_seconds = result.get("interval_seconds")

        # Construction du texte descriptif
        lines = []

        if is_first:
            lines.append("> 🟢 **Première récolte effectuée !** Reviens dans 1 heure pour amorcer ton combo.")
        elif combo_lost:
            lines.append("> ⚠️ **Combo interrompu !** Le délai d'1h20 a été dépassé. Ton bonus a été réinitialisé à 0%.")
        else:
            lines.append(f"> ⚡ **Combo maintenu !** Tu obtiens **+{step_bonus_pct:.0f}%** de bonus sur ce créneau.")

        lines.append("")
        lines.append(f"• **Gain de base :** 💵 `{format_usd(base_usd)}`")

        if bonus_pct > Decimal("0"):
            lines.append(f"• **Bonus cumulé :** 🔥 `+{bonus_pct:.1f}%` (+`{format_usd(bonus_usd)}`)")

        lines.append(f"• **Total crédité :** 💵 **`{format_usd(total_usd)}`**")
        lines.append(f"• **Nouveau solde :** 💳 `{format_usd(new_dollars)}`")
        lines.append(f"• **Série active :** 🔥 **`{streak}`** heure(s) consécutive(s)")
        lines.append("")
        lines.append(f"⏱️ **Prochain créneau :** <t:{next_ts}:R> (<t:{next_ts}:t>)")
        lines.append(f"🎯 **Fin de fenêtre combo :** <t:{combo_ts}:t> (<t:{combo_ts}:R>)")

        embed = RootEmbed(ctx, "hourly", "\n".join(lines))

        if getattr(ctx, "interaction", None):
            await ctx.respond(embed=embed)
        else:
            await ctx.send(embed=embed)

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
                )
        except Exception:
            pass


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Hourly(bot))

