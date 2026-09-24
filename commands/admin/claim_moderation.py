"""
Cog d'administration et surveillance : Rapport quotidien 24h des récoltes /claim (Anti-Triche & Détection de Bots).

Fonctionnalités :
1. Tâche planifiée automatique (tasks.loop) déclenchée chaque nuit à 00:00 (heure de Paris).
2. Récupère les statistiques de claims et la chronologie de chaque joueur depuis daily_claim_logs.
3. Analyse statistique avancée (moyenne, écart-type, constance globale et détection de streak automatisé).
4. Transmet le récapitulatif dans le salon de logs de modération dédié (sans aucun affichage public).
5. Réinitialise à zéro la table daily_claim_logs pour la journée suivante après envoi réussi.
6. Commande préfixe réservée aux administrateurs (OP) :
   - !claimaudit <@joueur|id> : audite en direct le comportement d'un joueur suspect sur les dernières 48h.
"""

import asyncio
from datetime import datetime, time, timedelta
import logging
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from game.db.daily_claim_stats import DailyClaimStatsDB
from utils.check import Check
from utils.claim_analysis import calculate_player_claim_metrics
from utils.text import format_rtm
from utils.time_format import format_duration

logger = logging.getLogger(__name__)


def _get_paris_midnight():
    """Génère l'objet time pour minuit avec le fuseau Europe/Paris."""
    try:
        return time(hour=0, minute=0, tzinfo=ZoneInfo("Europe/Paris"))
    except Exception:
        return time(hour=0, minute=0)


def _get_paris_today_str() -> str:
    """Retourne la date du jour au format YYYY-MM-DD pour le fuseau Europe/Paris."""
    try:
        return datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


class ClaimModeration(commands.Cog):
    """Cog d'administration gérant le rapport 24h des récoltes et la détection d'automatisation."""

    def __init__(self, bot):
        self.bot = bot
        self.check = Check()
        self._report_lock = asyncio.Lock()
        self.daily_claim_report_loop.start()

    def cog_unload(self):
        """Arrête la tâche d'arrière-plan au déchargement du Cog."""
        self.daily_claim_report_loop.cancel()

    @tasks.loop(time=_get_paris_midnight())
    async def daily_claim_report_loop(self):
        """Déclenche le rapport quotidien et la réinitialisation chaque nuit à minuit (heure de Paris)."""
        logger.info("Déclenchement du rapport quotidien des claims (minuit Paris)...")
        try:
            res = await self._run_daily_report()
            if res == 'busy':
                logger.warning("Rapport quotidien de claims ignoré : un rapport est déjà en cours d'exécution.")
        except Exception:
            logger.exception("Erreur lors de l'exécution automatique du rapport quotidien de claims")

    @daily_claim_report_loop.before_loop
    async def before_daily_claim_report_loop(self):
        """Attend la synchronisation complète du bot avant de démarrer la boucle et effectue le rattrapage."""
        await self.bot.wait_until_ready()
        await self._check_and_catch_up()

    async def _check_and_catch_up(self):
        """Vérifie au démarrage si le rapport de minuit a été manqué (bot éteint) et le rattrape."""
        try:
            database = self.bot.root_service.database
            today_str = _get_paris_today_str()
            last_date = await database.run(DailyClaimStatsDB.get_last_report_date, readonly=True)

            logger.info("Vérification rapport claims au démarrage : dernier rapport=%s, aujourd'hui=%s", last_date, today_str)

            if last_date is None:
                # Premier lancement : si des données sont déjà en attente, on les envoie
                summary = await database.run(DailyClaimStatsDB.get_summary, readonly=True)
                if summary:
                    logger.info("Rattrapage au démarrage : des données de claims sont en attente, envoi du rapport...")
                    await self._run_daily_report()
                else:
                    await database.run(lambda tx: DailyClaimStatsDB.set_last_report_date(tx, today_str, tx.now))
                return

            if last_date < today_str:
                logger.info("Rattrapage au démarrage : minuit est passé depuis le dernier rapport (%s < %s), envoi en cours...", last_date, today_str)
                await self._run_daily_report()
            else:
                logger.info("Rapport quotidien de claims pour la période actuelle (%s) déjà envoyé.", today_str)
        except Exception:
            logger.exception("Erreur lors de la vérification du rattrapage du rapport quotidien de claims")

    async def _run_daily_report(self) -> str:
        """Lit les statistiques des 24h, envoie le rapport, purge les logs > 48h et met à jour la date.

        Retourne 'busy' si déjà en cours, 'success' après réussite complète.
        Lève une exception si l'envoi ou la purge échoue (les logs sont alors préservés).
        """
        if self._report_lock.locked():
            logger.warning("Un rapport quotidien de claims est déjà en cours d'exécution.")
            return 'busy'

        async with self._report_lock:
            database = self.bot.root_service.database
            summary = await database.run(
                lambda tx: DailyClaimStatsDB.get_summary(
                    tx,
                    limit_users=50,
                    since_dt=tx.now - timedelta(hours=24),
                    claims_since_dt=tx.now - timedelta(hours=48),
                ),
                readonly=True,
            )

            # Envoi du rapport : toute exception interrompt l'exécution avant la purge
            await self.bot.discord_logger.log_daily_claim_report(summary)

            today_str = _get_paris_today_str()

            def _purge_and_update_date(tx):
                cutoff_48h = tx.now - timedelta(hours=48)
                DailyClaimStatsDB.purge_older_than(tx, cutoff_48h)
                DailyClaimStatsDB.set_last_report_date(tx, today_str, tx.now)

            await database.run(_purge_and_update_date)
            logger.info("Rapport claims 24h envoyé, logs > 48h purgés et date mise à jour (%s).", today_str)
            return 'success'

    # ── Commandes Préfixes OP ────────────────────────────────────────────────
    @commands.command(name="claimaudit")
    async def audit_player_claims(self, ctx, user: discord.User):
        """Audite en direct les récoltes d'un joueur suspect (historique 48h, réservé aux OP)."""
        if not await self.check.is_op(self.bot, ctx.author.id):
            return

        database = self.bot.root_service.database
        claims = await database.run(lambda tx: DailyClaimStatsDB.get_user_claims(tx, user.id), readonly=True)

        if not claims:
            await ctx.send(f"ℹ️ Aucun claim enregistré sur les dernières 48h pour {user.mention} (`{user.id}`).")
            return

        analysis = calculate_player_claim_metrics(claims)
        badge = analysis["risk_badge"]
        claim_count = analysis["claim_count"]
        total_rtm = format_rtm(analysis["total_amount"])

        mean_str = format_duration(analysis["mean_interval_sec"]) if analysis["mean_interval_sec"] is not None else "N/A"
        reg_pct = analysis["regularity_pct"]
        reg_str = f"{reg_pct:.1f}%" if reg_pct is not None else "N/A"
        std_str = f"± {format_duration(analysis['std_dev_sec'])}" if analysis["std_dev_sec"] is not None else "N/A"

        color = (
            discord.Color.red() if analysis["risk_level"] == "HIGH"
            else (discord.Color.gold() if analysis["risk_level"] == "MEDIUM" else discord.Color.green())
        )

        embed = discord.Embed(
            title=f"{badge} Audit Anti-Triche Claim — {user.name}",
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        auto_count = analysis.get("auto_claim_count", 0)
        manual_count = analysis.get("manual_claim_count", claim_count)
        if auto_count > 0:
            recoltes_str = f"`{claim_count}` claims (👤 `{manual_count}` · 🤖 `{auto_count}`) (`{total_rtm} RTM`)"
        else:
            recoltes_str = f"`{claim_count}` claims (`{total_rtm} RTM`)"

        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Joueur", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="Récoltes (48h)", value=recoltes_str, inline=True)
        embed.add_field(name="Niveau de Risque", value=f"{badge} **{analysis['risk_level']}**", inline=True)
        embed.add_field(name="Intervalle Moyen", value=f"`{mean_str}`", inline=True)
        embed.add_field(name="Écart-type (Dispersion)", value=f"`{std_str}`", inline=True)
        embed.add_field(name="Indice de Constance", value=f"`{reg_str}`", inline=True)

        if analysis.get("status") == "INSUFFICIENT_DATA":
            embed.add_field(
                name="Statut",
                value="⚪ Données manuelles insuffisantes (< 2 récoltes manuelles)",
                inline=False,
            )

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
        for c in claims[-8:]:
            if c.get("interval_seconds") is not None:
                iv = format_duration(c["interval_seconds"] or 0)
                if c.get("is_auto"):
                    iv += " [AUTO]"
                last_intervals.append(iv)
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
    bot.add_cog(ClaimModeration(bot))

