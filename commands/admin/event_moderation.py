"""
Cog d'administration et surveillance : Rapport quotidien 24h des événements (Anti-Triche).

Fonctionnalités :
1. Tâche planifiée automatique (tasks.loop) déclenchée chaque jour à 00:00 (heure de Paris).
2. Récupère les statistiques d'événements sur 24h depuis la table MySQL daily_event_stats.
3. Transmet le récapitulatif dans le salon LOG_MODERATION_EVENT_STATS_CHANNEL_ID sans repli automatique.
4. Réinitialise à zéro la table daily_event_stats pour la journée suivante.
5. Commande préfixe !dailyreport (réservée OP) permettant de tester ou forcer l'émission du rapport.
"""

import asyncio
from datetime import datetime, time
import logging
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from game.db.daily_event_stats import DailyEventStatsDB
from utils.check import Check

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


class EventModeration(commands.Cog):
    """Cog d'administration gérant le rapport 24h des événements avec rattrapage automatique."""

    def __init__(self, bot):
        self.bot = bot
        self.check = Check()
        self._report_lock = asyncio.Lock()
        self.daily_report_loop.start()

    def cog_unload(self):
        """Arrête la tâche d'arrière-plan au déchargement du Cog."""
        self.daily_report_loop.cancel()

    @tasks.loop(time=_get_paris_midnight())
    async def daily_report_loop(self):
        """Déclenche le rapport quotidien et la réinitialisation chaque nuit à minuit (heure de Paris)."""
        logger.info("Déclenchement du rapport quotidien des événements (minuit Paris)...")
        try:
            res = await self._run_daily_report()
            if res == 'busy':
                logger.warning("Rapport quotidien planifié ignoré : un rapport est déjà en cours d'exécution.")
        except Exception:
            logger.exception("Erreur lors de l'exécution automatique du rapport quotidien d'événements")

    @daily_report_loop.before_loop
    async def before_daily_report_loop(self):
        """Attend la synchronisation complète du bot avant de démarrer la boucle et effectue le rattrapage."""
        await self.bot.wait_until_ready()
        await self._check_and_catch_up()

    async def _check_and_catch_up(self):
        """Vérifie au démarrage si le rapport de minuit a été manqué (bot éteint) et le rattrape."""
        try:
            database = self.bot.root_service.database
            today_str = _get_paris_today_str()
            last_date = await database.run(DailyEventStatsDB.get_last_report_date, readonly=True)

            logger.info("Vérification rapport 24h au démarrage : dernier rapport=%s, aujourd'hui=%s", last_date, today_str)

            if last_date is None:
                # Premier lancement : si des données sont déjà en attente, on les envoie
                summary = await database.run(DailyEventStatsDB.get_summary, readonly=True)
                if summary:
                    logger.info("Rattrapage au démarrage : des données d'événements sont en attente, envoi du rapport...")
                    await self._run_daily_report()
                else:
                    await database.run(lambda tx: DailyEventStatsDB.set_last_report_date(tx, today_str, tx.now))
                return

            if last_date < today_str:
                logger.info("Rattrapage au démarrage : minuit est passé depuis le dernier rapport (%s < %s), envoi en cours...", last_date, today_str)
                await self._run_daily_report()
            else:
                logger.info("Rapport quotidien pour la période actuelle (%s) déjà envoyé.", today_str)
        except Exception:
            logger.exception("Erreur lors de la vérification du rattrapage du rapport quotidien")

    async def _run_daily_report(self) -> str:
        """Lit les statistiques, envoie le rapport, purge la table et met à jour la date.
        
        Retourne 'busy' si déjà en cours, 'success' après réussite complète.
        Lève une exception si l'envoi ou la purge échoue (les compteurs sont alors préservés).
        """
        if self._report_lock.locked():
            logger.warning("Un rapport quotidien est déjà en cours d'exécution.")
            return 'busy'

        async with self._report_lock:
            database = self.bot.root_service.database
            summary = await database.run(DailyEventStatsDB.get_summary, readonly=True)
            # Envoi du rapport : toute exception interrompt l'exécution avant la purge
            await self.bot.discord_logger.log_daily_event_report(summary)

            today_str = _get_paris_today_str()

            def _reset_and_update_date(tx):
                DailyEventStatsDB.reset(tx)
                DailyEventStatsDB.set_last_report_date(tx, today_str, tx.now)

            await database.run(_reset_and_update_date)
            logger.info("Rapport 24h envoyé, compteurs réinitialisés et date mise à jour (%s).", today_str)
            return 'success'

    @commands.command(name="dailyreport")
    async def manual_daily_report(self, ctx):
        """Déclenche manuellement le rapport 24h des événements (réservé aux OP)."""
        if not await self.check.is_op(self.bot, ctx.author.id):
            return
        if self._report_lock.locked():
            await ctx.send("⚠️ Un rapport quotidien est déjà en cours d'exécution.")
            return

        await ctx.send("⏳ Génération et envoi du rapport 24h en cours...")
        try:
            status = await self._run_daily_report()
            if status == 'busy':
                await ctx.send("⚠️ Un rapport quotidien est déjà en cours d'exécution.")
            else:
                await ctx.send("✅ Rapport quotidien généré et compteurs réinitialisés.")
        except Exception:
            logger.exception("Erreur lors de l'exécution manuelle du rapport quotidien d'événements")
            await ctx.send("❌ Échec lors de la génération ou de l'envoi du rapport. Les compteurs n'ont pas été réinitialisés.")


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(EventModeration(bot))

