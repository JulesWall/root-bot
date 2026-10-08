"""
Cog d'administration et surveillance : Rapport quotidien 24h et audit des récoltes /hourly.

Fonctionnalités :
1. Tâche planifiée automatique (tasks.loop) déclenchée chaque nuit à 00:00 (heure de Paris).
2. Envoie le classement dans le salon LOG_MODERATION_HOURLY_STATS_CHANNEL_ID.
3. Purge les enregistrements de plus de 24 heures (glissantes) après un envoi réussi. Le combo joueur est conservé.
4. Commande préfixe réservée aux OP :
   - !hourlyaudit <@joueur|id> : audit sur l'historique conservé (24h glissantes).
"""

import asyncio
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
import logging
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from game.db.hourly_stats import HourlyStatsDB, calculate_player_hourly_metrics
from utils.check import Check
from utils.text import format_usd
from utils.time_format import format_duration

logger = logging.getLogger(__name__)

_RISK_LABELS = {
    "LOW": "FAIBLE",
    "MEDIUM": "MOYEN",
    "HIGH": "ÉLEVÉ",
}


def _risk_label(level: str | None) -> str:
    return _RISK_LABELS.get(level or "", level or "FAIBLE")


def _get_paris_midnight():
    """Minuit, fuseau Europe/Paris."""
    try:
        return time(hour=0, minute=0, tzinfo=ZoneInfo("Europe/Paris"))
    except Exception:
        return time(hour=0, minute=0)


def _get_paris_today_str() -> str:
    """Date du jour YYYY-MM-DD en heure de Paris."""
    try:
        return datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _unix_ts(dt) -> int | None:
    if dt is None or not hasattr(dt, "timestamp"):
        return None
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


class HourlyModeration(commands.Cog):
    """Cog d'administration pour la modération et l'audit des récompenses /hourly."""

    def __init__(self, bot):
        self.bot = bot
        self.check = Check()
        self._report_lock = asyncio.Lock()
        self.daily_hourly_report_loop.start()

    def cog_unload(self):
        """Arrête la tâche d'arrière-plan au déchargement du Cog."""
        self.daily_hourly_report_loop.cancel()

    @tasks.loop(time=_get_paris_midnight())
    async def daily_hourly_report_loop(self):
        """Envoie le rapport hourly et purge l'historique ancien chaque nuit à minuit (Paris)."""
        logger.info("Déclenchement du rapport quotidien hourly (minuit Paris)...")
        try:
            res = await self._run_daily_report()
            if res == "busy":
                logger.warning("Rapport hourly ignoré : un rapport est déjà en cours d'exécution.")
        except Exception:
            logger.exception("Erreur lors de l'exécution automatique du rapport quotidien hourly")

    @daily_hourly_report_loop.before_loop
    async def before_daily_hourly_report_loop(self):
        """Attend que le bot soit prêt, puis rattrape un minuit manqué."""
        await self.bot.wait_until_ready()
        await self._check_and_catch_up()

    async def _check_and_catch_up(self):
        """Envoie le rapport au démarrage si minuit est passé depuis le dernier envoi."""
        try:
            database = self.bot.root_service.database
            today_str = _get_paris_today_str()
            last_date = await database.run(HourlyStatsDB.get_last_report_date, readonly=True)
            logger.info("Vérification rapport hourly au démarrage : dernier rapport=%s, aujourd'hui=%s", last_date, today_str)

            if last_date is None:
                summary = await database.run(HourlyStatsDB.get_summary, readonly=True)
                if summary:
                    logger.info("Rattrapage au démarrage : des récoltes hourly sont en attente, envoi du rapport...")
                    await self._run_daily_report()
                else:
                    await database.run(lambda tx: HourlyStatsDB.set_last_report_date(tx, today_str, tx.now))
                return

            if last_date < today_str:
                logger.info("Rattrapage hourly : minuit est passé (%s < %s), envoi en cours...", last_date, today_str)
                await self._run_daily_report()
            else:
                logger.info("Rapport hourly de la période actuelle (%s) déjà envoyé.", today_str)
        except Exception:
            logger.exception("Erreur lors du rattrapage du rapport quotidien hourly")

    async def _run_daily_report(self) -> str:
        """Envoie le rapport 24h dans le salon configuré, puis purge les logs > 24h.

        Retourne 'busy' si un rapport est déjà en cours, 'success' après la purge.
        Lève une exception si l'envoi échoue : l'historique est alors conservé.
        """
        if self._report_lock.locked():
            logger.warning("Un rapport quotidien hourly est déjà en cours d'exécution.")
            return "busy"

        async with self._report_lock:
            database = self.bot.root_service.database
            summary = await database.run(
                lambda tx: HourlyStatsDB.get_summary(
                    tx,
                    limit_users=50,
                    since_dt=tx.now - timedelta(hours=24),
                    claims_since_dt=tx.now - timedelta(hours=24),
                ),
                readonly=True,
            )
            await self.bot.discord_logger.log_daily_hourly_report(summary)

            today_str = _get_paris_today_str()

            def _purge_and_update_date(tx):
                cutoff_24h = tx.now - timedelta(hours=24)
                HourlyStatsDB.purge_older_than(tx, cutoff_24h)
                HourlyStatsDB.set_last_report_date(tx, today_str, tx.now)

            await database.run(_purge_and_update_date)
            logger.info("Rapport hourly 24h envoyé, historique > 24h purgé, date mise à jour (%s).", today_str)
            return "success"

    # ── Commandes Préfixes OP ────────────────────────────────────────────────
    @commands.command(name="hourlyaudit")
    async def audit_player_hourly(self, ctx, user: discord.User):
        """Audite en direct les récoltes horaires d'un joueur suspect (historique 24h glissante, réservé aux OP)."""
        if not await self.check.is_op(self.bot, ctx.author.id):
            return

        database = self.bot.root_service.database
        logs = await database.run(
            lambda tx: HourlyStatsDB.get_user_hourly_logs(tx, user.id, limit=100, since_dt=tx.now - timedelta(hours=24)),
            readonly=True,
        )

        if not logs:
            await ctx.send(f"ℹ️ Aucun historique de /hourly sur les dernières 24h pour {user.mention} (`{user.id}`).")
            return

        player = await database.run(
            lambda tx: tx.one("SELECT * FROM players WHERE discord_id=%s", (user.id,)),
            readonly=True,
        )

        analysis = calculate_player_hourly_metrics(logs)
        badge = analysis["risk_badge"]
        claim_count = analysis["claim_count"]
        total_usd = format_usd(analysis["total_usd"])
        max_streak = analysis["max_streak"]
        max_bonus = analysis["max_bonus_pct"]
        if player:
            current_streak = int(player.get("hourly_streak") or 0)
            current_bonus = Decimal(str(player.get("hourly_combo_bonus") or 0))
            current_streak_str = f"🔥 `{current_streak}`"
            current_bonus_str = f"⚡ `+{current_bonus:.1f}%`"
        else:
            current_streak_str = "`N/A`"
            current_bonus_str = "`N/A`"

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
        embed.add_field(name="Récoltes (24h)", value=f"`{claim_count}` claims (`{total_usd}`)", inline=True)
        embed.add_field(name="Niveau de Risque", value=f"{badge} **{analysis['risk_level']}**", inline=True)
        embed.add_field(name="Série actuelle / max", value=f"{current_streak_str} · Max : 🔥 `{max_streak}`", inline=True)
        embed.add_field(name="Bonus actuel / max", value=f"{current_bonus_str} · Max : ⚡ `+{max_bonus:.1f}%`", inline=True)
        embed.add_field(name="Indice de Constance", value=f"`{reg_str}`", inline=True)
        embed.add_field(name="Intervalle Moyen", value=f"`{mean_str}`", inline=True)
        embed.add_field(name="Écart-type (Dispersion)", value=f"`{std_str}`", inline=True)

        if analysis.get("active_24h"):
            embed.add_field(name="⚠️ Alerte Sommeil", value="Activité observée sur 24h sans longue pause", inline=False)

        streak = analysis.get("suspicious_streak")
        if streak:
            s_mean = format_duration(streak["mean_sec"])
            s_std = format_duration(streak["std_dev_sec"])
            s_reg = f"{streak['regularity_pct']:.1f}%"
            s_diff = f"{streak['mean_diff_sec']:.1f}s"
            embed.add_field(
                name="🔍 Séquence Maximale de Constance (Rolling Window)",
                value=(
                    f"• **Nombre de claims** : `{streak['count']}` consécutifs\n"
                    f"• **Intervalle moyen** : `{s_mean}` (± `{s_std}`)\n"
                    f"• **Régularité locale** : `{s_reg}`\n"
                    f"• **Variation consécutive moyenne** : `{s_diff}`"
                ),
                inline=False,
            )

        # Affichage des derniers intervalles récents (jusqu'à 8)
        last_intervals = []
        for r in logs[-8:]:
            if r.get("interval_seconds") is not None:
                iv = format_duration(r["interval_seconds"] or 0)
                st = r.get("streak", 1)
                bp = Decimal(str(r.get("bonus_pct", 0)))
                last_intervals.append(f"{iv} [🔥 {st} | +{bp:.1f}%]")
        if last_intervals:
            embed.add_field(
                name="Derniers intervalles enregistrés",
                value=" ➔ ".join([f"`{iv}`" for iv in last_intervals]),
                inline=False,
            )

        embed.set_footer(text="Root Security • Audit de Modération")
        await ctx.send(embed=embed)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(HourlyModeration(bot))


