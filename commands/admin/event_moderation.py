"""
Cog d'administration et surveillance : Rapport quotidien 24h des événements (Anti-Triche).

Fonctionnalités :
1. Tâche planifiée automatique (tasks.loop) déclenchée chaque jour à 00:00 (heure de Paris).
2. Récupère les statistiques d'événements sur 24h depuis daily_event_stats et event_availability_logs.
3. Transmet le récapitulatif dans le salon LOG_MODERATION_EVENT_STATS_CHANNEL_ID sans repli automatique.
4. Purge les statistiques antérieures à 24 heures (glissantes) pour permettre l'audit post-rapport.
5. Commande préfixe !eventaudit <@joueur|id> (réservée OP) pour auditer un joueur suspect sur 24h (glissantes).
"""

import asyncio
from datetime import datetime, time, timedelta
import logging
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from game.db.daily_event_stats import DailyEventStatsDB
from game.db.events import EventsDB
from utils.check import Check
from utils.event_analysis import calculate_player_event_metrics
from utils.text import format_usd

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
        """Déclenche le rapport quotidien et la purge chaque nuit à minuit (heure de Paris)."""
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
        """Lit les statistiques des dernières 24h, envoie le rapport, purge les données > 24h et met à jour la date.
        
        Retourne 'busy' si déjà en cours, 'success' après réussite complète.
        Lève une exception si l'envoi ou la purge échoue (les compteurs sont alors préservés).
        """
        if self._report_lock.locked():
            logger.warning("Un rapport quotidien est déjà en cours d'exécution.")
            return 'busy'

        async with self._report_lock:
            database = self.bot.root_service.database
            today_str = _get_paris_today_str()
            try:
                yesterday_str = (datetime.now(ZoneInfo("Europe/Paris")) - timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

            summary = await database.run(
                lambda tx: DailyEventStatsDB.get_summary(tx, limit=50, date_str=yesterday_str),
                readonly=True,
            )

            # Extraire les résolutions réelles sur les 24h écoulées pour qualifier les vitesses
            resolution_map = await database.run(
                lambda tx: EventsDB.get_resolution_metrics_by_user(tx, since_dt=tx.now - timedelta(hours=24)),
                readonly=True,
            )

            # Envoi du rapport : toute exception interrompt l'exécution avant la purge
            await self.bot.discord_logger.log_daily_event_report(summary, resolution_map)

            def _purge_and_update_date(tx):
                try:
                    cutoff_date = (datetime.now(ZoneInfo("Europe/Paris")) - timedelta(days=1)).strftime("%Y-%m-%d")
                except Exception:
                    cutoff_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                DailyEventStatsDB.purge_older_than(tx, cutoff_date)
                DailyEventStatsDB.set_last_report_date(tx, today_str, tx.now)

            await database.run(_purge_and_update_date)
            logger.info("Rapport 24h événements envoyé, données > 24h purgées et date mise à jour (%s).", today_str)
            return 'success'

    # ── Commandes Préfixes OP ────────────────────────────────────────────────
    @commands.command(name="eventaudit")
    async def audit_player_event(self, ctx, user: discord.User):
        """Audite en direct l'activité sur les mini-jeux d'un joueur (historique 24h glissante, réservé aux OP)."""
        if not await self.check.is_op(self.bot, ctx.author.id):
            return

        database = self.bot.root_service.database
        try:
            since_date_str = (datetime.now(ZoneInfo("Europe/Paris")) - timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            since_date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        stats = await database.run(
            lambda tx: DailyEventStatsDB.get_user_event_stats(tx, user.id, since_date_str=since_date_str),
            readonly=True,
        )
        recent_wins = await database.run(
            lambda tx: EventsDB.get_recent_wins_for_user(tx, user.id, limit=20, since_dt=tx.now - timedelta(hours=24)),
            readonly=True,
        )

        won = stats.get("events_won", 0)
        part = stats.get("events_participated", 0)

        if won == 0 and part == 0 and not recent_wins:
            await ctx.send(f"ℹ️ Aucune activité sur les événements sur les dernières 24h pour {user.mention} (`{user.id}`).")
            return

        analysis = calculate_player_event_metrics(won, part, recent_wins)
        badge = analysis["risk_badge"]
        risk_level = analysis["risk_level"]
        color = (
            discord.Color.red() if risk_level == "HIGH"
            else (discord.Color.gold() if risk_level == "MEDIUM" else discord.Color.green())
        )

        embed = discord.Embed(
            title=f"{badge} Audit Anti-Triche Événements — {user.name}",
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Joueur", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="Victoires / Participations (24h)", value=f"🏆 `{won}` / 🎯 `{part}`", inline=True)
        embed.add_field(name="Taux de Réussite", value=f"`{analysis['win_rate_pct']:.1f}%`", inline=True)
        embed.add_field(name="Niveau de Risque", value=f"{badge} **{risk_level}**", inline=True)

        if analysis["mean_duration_sec"] is not None:
            mean_d = f"{analysis['mean_duration_sec']:.1f}s"
            min_d = f"{analysis['min_duration_sec']}s"
            embed.add_field(name="Vitesse de Résolution", value=f"Moyenne : `{mean_d}` · Record : `{min_d}`", inline=True)

        if analysis["instant_wins_count"] > 0:
            embed.add_field(name="🚨 Résolutions Instantanées (<= 2s)", value=f"`{analysis['instant_wins_count']}` victoires", inline=True)

        # Répartition des victoires par type d'événement
        event_counts = {}
        for w in recent_wins:
            ev = w.get("event", "inconnu")
            event_counts[ev] = event_counts.get(ev, 0) + 1
        if event_counts:
            repartition_str = " · ".join([f"**{ev}** : `{cnt}`" for ev, cnt in event_counts.items()])
            embed.add_field(name="Répartition des Victoires Récentes", value=repartition_str, inline=False)

        # Chronologie des 10 dernières victoires
        if recent_wins:
            lines = []
            for w in recent_wins[:10]:
                dur = w.get("duration_seconds", 0)
                ev = w.get("event", "?")
                r_val = w.get("reward", 0)
                dur_tag = f"⚡ `{dur}s`" if dur > 2 else f"🚨 `{dur}s` [INSTANT]"
                dt_val = w.get("solved_at")
                dt_str = dt_val.strftime("%d/%m %H:%M") if dt_val and hasattr(dt_val, "strftime") else "?"
                lines.append(f"• `{dt_str}` — **{ev}** — {dur_tag} — `{format_usd(r_val)}`")
            embed.add_field(name="Dernières Victoires Enregistrées (jusqu'à 10)", value="\n".join(lines), inline=False)

        embed.set_footer(text="Root Security • Audit de Modération Événements")
        await ctx.send(embed=embed)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(EventModeration(bot))


