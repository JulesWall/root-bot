"""
Cog d'administration et surveillance : Rapports 24h et Audit des récoltes /hourly.

Fonctionnalités :
1. Commandes préfixes réservées exclusivement aux administrateurs (OP) :
   - !hourlyreport (alias !tophourly, !dailyhourly) : synthèse et classement des récoltes horaires sur 24h.
   - !hourlyaudit <@joueur|id> : audit approfondi anti-triche et détection de macros / bots d'un joueur suspect.
"""

from decimal import Decimal
import logging

import discord
from discord.ext import commands

from game.db.hourly_stats import HourlyStatsDB, calculate_player_hourly_metrics
from utils.check import Check
from utils.text import format_usd
from utils.time_format import format_duration

logger = logging.getLogger(__name__)


class HourlyModeration(commands.Cog):
    """Cog d'administration pour la modération et l'audit des récompenses /hourly."""

    def __init__(self, bot):
        self.bot = bot
        self.check = Check()

    # ── Commandes Préfixes OP ────────────────────────────────────────────────
    @commands.command(name="hourlyreport", aliases=["tophourly", "dailyhourly"])
    async def manual_hourly_report(self, ctx):
        """Affiche le classement et le rapport des récoltes horaires des dernières 24h (réservé aux OP)."""
        if not await self.check.is_op(self.bot, ctx.author.id):
            return

        database = self.bot.root_service.database
        summary = await database.run(HourlyStatsDB.get_summary, readonly=True)

        total_claims = summary.get("total_claims", 0)
        total_usd = summary.get("total_usd", Decimal("0"))
        unique_players = summary.get("unique_players", 0)
        top_users = summary.get("top_users", [])

        embed = discord.Embed(
            title="⏱️ Rapport de Modération — Récompenses Horaires (24h)",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        embed.description = (
            f"• **Total récoltes :** `{total_claims}` claims\n"
            f"• **Joueurs actifs :** `{unique_players}` joueurs uniques\n"
            f"• **Volume distribué :** 💵 `{format_usd(total_usd)}`\n"
        )

        if top_users:
            rows = []
            for i, u in enumerate(top_users[:15], 1):
                uid = u["discord_id"]
                cnt = u["claim_count"]
                u_usd = format_usd(u["total_usd"])
                streak = u.get("max_streak", 1)
                bonus = Decimal(str(u.get("max_bonus_pct", 0)))
                rows.append(f"**{i}.** <@{uid}> (`{uid}`) — `{cnt}` claims (🔥 `{streak}` · `+{bonus:.1f}%`) — `{u_usd}`")
            embed.add_field(name="🏆 Top Joueurs Assidus (24h)", value="\n".join(rows), inline=False)
        else:
            embed.add_field(name="🏆 Top Joueurs Assidus (24h)", value="*Aucun claim horaire enregistré sur les dernières 24h.*", inline=False)

        embed.set_footer(text="Root Security • Modération Hourly")
        await ctx.send(embed=embed)

        # Envoi miroir optionnel dans le salon de logs dédié
        try:
            await self.bot.discord_logger.log_daily_hourly_report(summary)
        except Exception:
            pass

    @commands.command(name="hourlyaudit")
    async def audit_player_hourly(self, ctx, user: discord.User):
        """Audite en direct les récoltes horaires d'un joueur suspect (réservé aux OP)."""
        if not await self.check.is_op(self.bot, ctx.author.id):
            return

        database = self.bot.root_service.database
        logs = await database.run(lambda tx: HourlyStatsDB.get_user_hourly_logs(tx, user.id, limit=50), readonly=True)

        if not logs:
            await ctx.send(f"ℹ️ Aucun historique de /hourly enregistré pour {user.mention} (`{user.id}`).")
            return

        analysis = calculate_player_hourly_metrics(logs)
        badge = analysis["risk_badge"]
        claim_count = analysis["claim_count"]
        total_usd = format_usd(analysis["total_usd"])
        max_streak = analysis["max_streak"]
        max_bonus = analysis["max_bonus_pct"]

        mean_str = format_duration(analysis["mean_interval_sec"]) if analysis["mean_interval_sec"] is not None else "N/A"
        reg_pct = analysis["regularity_pct"]
        reg_str = f"{reg_pct:.1f}%" if reg_pct is not None else "N/A"
        std_str = f"± {format_duration(analysis['std_dev_sec'])}" if analysis["std_dev_sec"] is not None else "N/A"

        color = (
            discord.Color.red() if analysis["risk_level"] == "HIGH"
            else (discord.Color.gold() if analysis["risk_level"] == "MEDIUM" else discord.Color.green())
        )

        embed = discord.Embed(
            title=f"{badge} Audit Anti-Triche Hourly — {user.name}",
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Joueur", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="Récoltes Enregistrées", value=f"`{claim_count}` claims (`{total_usd}`)", inline=True)
        embed.add_field(name="Niveau de Risque", value=f"{badge} **{analysis['risk_level']}**", inline=True)
        embed.add_field(name="Série Max", value=f"🔥 `{max_streak}`", inline=True)
        embed.add_field(name="Bonus Max Atteint", value=f"⚡ `+{max_bonus:.1f}%`", inline=True)
        embed.add_field(name="Indice de Constance", value=f"`{reg_str}`", inline=True)
        embed.add_field(name="Intervalle Moyen", value=f"`{mean_str}`", inline=True)
        embed.add_field(name="Écart-type (Dispersion)", value=f"`{std_str}`", inline=True)

        if analysis.get("alerts"):
            alerts_str = "\n".join([f"• ⚠️ {a}" for a in analysis["alerts"]])
            embed.add_field(name="Anomalies Détectées", value=alerts_str, inline=False)

        # Affichage des derniers intervalles récents (jusqu'à 8)
        last_intervals = []
        for l in logs[-8:]:
            if l.get("interval_seconds") is not None:
                iv = format_duration(l["interval_seconds"] or 0)
                pct = l.get("bonus_pct", Decimal("0"))
                last_intervals.append(f"`{iv} (+{pct:.0f}%)`")
        if last_intervals:
            embed.add_field(
                name="Derniers intervalles enregistrés",
                value=" ➔ ".join(last_intervals),
                inline=False,
            )

        embed.set_footer(text="Root Security • Audit Hourly")
        await ctx.send(embed=embed)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(HourlyModeration(bot))

