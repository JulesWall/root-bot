"""Tâche de fond du cours dynamique du RTM.

Toutes les 15 minutes UTC (alignées sur les quarts d'heure, sans dérive), lit les deux
dernières bougies clôturées de BTC, ETH et SOL, calcule la moyenne simple de leurs
variations et compose le cours du RTM avec le cours précédent.

- Aucun appel à l'exchange en dehors de cette tâche (jamais depuis un callback Discord).
- Échec ou donnée périmée : le cours n'est pas modifié, le flux est marqué « retardé ».
- Redémarrage : rattrapage automatique des créneaux de 15 minutes manquants sur 7 jours.
"""

import logging
import time

from discord.ext import tasks

from commands.game.commandgame import BaseGameCog
from game.market_feed import MarketFeed, MarketFeedError
from game.math_config import MathConfig

logger = logging.getLogger(__name__)


class MarketTask(BaseGameCog):
    """Cog sans commande : collecte et enregistrement du cours RTM."""

    def __init__(self, bot):
        self.bot = bot
        self.feed = MarketFeed()
        self._done_slot: int | None = None
        self._delayed_slot: int | None = None
        self._last_attempt: float = 0.0
        if MathConfig.market_settings().get('enabled'):
            self.market_loop.start()
            self.purge_loop.start()

    def cog_unload(self):
        """Arrête les tâches et ferme la session de l'exchange."""
        self.market_loop.cancel()
        self.purge_loop.cancel()
        self.bot.loop.create_task(self.feed.close())

    @tasks.loop(seconds=15)
    async def market_loop(self):
        """Déclenche un cycle dès qu'un nouveau quart d'heure UTC est clos."""
        try:
            settings = MathConfig.market_settings()
            if not settings.get('enabled'):
                return
            interval = int(settings['interval_seconds'])
            now = time.time()
            slot = int(now // interval) * interval
            elapsed = now - slot
            if elapsed < int(settings['close_margin_seconds']) or self._done_slot == slot:
                return
            if now - self._last_attempt < int(settings['retry_seconds']):
                return
            self._last_attempt = now
            await self._run_cycle(slot, elapsed, settings)
        except Exception:
            logger.exception("[Market] Erreur inattendue dans la boucle de marché")

    async def _run_cycle(self, slot: int, elapsed: float, settings: dict):
        """Collecte, applique le cycle et journalise l'état du flux."""
        try:
            payload = await self.feed.fetch_closes()
        except MarketFeedError as exc:
            logger.warning("[Market] Collecte échouée : %s", exc)
            payload = None
        except Exception as exc:
            logger.warning("[Market] Collecte échouée (%s)", type(exc).__name__)
            payload = None

        if payload is None:
            if elapsed > int(settings['max_staleness_seconds']) and self._delayed_slot != slot:
                self._delayed_slot = slot
                await self.service.mark_market_delayed()
                logger.warning("[Market] Flux retardé, cours inchangé (créneau %s)", slot)
            return

        result = await self.service.apply_market_cycle(
            payload['market_ts'], payload['closes'], payload['source'],
        )
        self._done_slot = slot
        if result['status'] == 'applied':
            logger.info(
                "[Market] %s UTC : BTC %+.4f%% ETH %+.4f%% SOL %+.4f%% moy %+.4f%% -> 1 RTM = %s USD%s",
                payload['market_ts'], result['btc_pct'], result['eth_pct'], result['sol_pct'],
                result['avg_pct'], result['price_after'], ' (plafonné)' if result['capped'] else '',
            )
            alerts = result.get('triggered_alerts') or []
            if alerts:
                await self._notify_alerts(alerts, result['price_after'])

            # Exécution et notification des ventes automatiques de RTM
            try:
                auto_sells = await self.service.process_auto_sells(
                    payload['market_ts'], result['price_after']
                )
                if auto_sells:
                    await self._notify_auto_sells(auto_sells, result['price_after'])
            except Exception:
                logger.exception("[Market] Erreur lors du traitement des ventes automatiques")
        else:
            logger.info("[Market] Cycle %s déjà appliqué, cours inchangé.", payload['market_ts'])

    async def _notify_alerts(self, alerts: list[dict], current_price):
        """Envoie une notification en message privé pour chaque alerte de cours déclenchée."""
        from decimal import Decimal
        import discord
        from utils import text
        from utils.language_manager import fetch_user_language
        from utils.root_embed import RootEmbed
        from utils.root_theme import VisualState

        for alert in alerts:
            discord_id = int(alert['discord_id'])
            try:
                user = self.bot.get_user(discord_id)
                if user is None:
                    try:
                        user = await self.bot.fetch_user(discord_id)
                    except Exception:
                        user = None
                if not user:
                    continue

                direction = alert['direction']
                threshold = Decimal(str(alert['threshold_usd']))

                lang = await fetch_user_language(discord_id) or 'fr'
                dir_label = (
                    text.get_for_lang(lang, 'g_market_alerts_dir_above')
                    if direction == 'above'
                    else text.get_for_lang(lang, 'g_market_alerts_dir_below')
                )
                rate_str = text.format_usd(current_price)
                threshold_str = text.format_usd(threshold)

                msg_content = text.get_for_lang(
                    lang,
                    'g_market_alert_triggered_dm',
                    rate=rate_str,
                    dir_label=dir_label,
                    threshold=threshold_str,
                )

                state = VisualState.SUCCESS if direction == 'above' else VisualState.ATTENTION
                embed = RootEmbed(
                    action='market',
                    title=text.get_for_lang(lang, 'g_market_alerts_dm_title'),
                    content=msg_content,
                    state=state,
                    locale=lang,
                    footer="ROOT OS · Marché",
                )
                await user.send(embed=embed)
                logger.info("[Market] Alerte envoyée en DM au joueur %s (seuil %s USD)", discord_id, threshold_str)
            except discord.Forbidden:
                logger.info("[Market] DM bloqué pour le joueur %s (MP fermés)", discord_id)
            except Exception:
                logger.warning("[Market] Échec de transmission d'alerte pour le joueur %s", discord_id, exc_info=True)

    async def _notify_auto_sells(self, auto_sells: list[dict], current_price):
        """Notifie chaque joueur en DM du succès de sa vente automatique et journalise dans #blockchain."""
        import discord
        from utils import text
        from utils.language_manager import fetch_user_language
        from utils.root_embed import RootEmbed
        from utils.root_theme import VisualState
        from utils.logger import Logger

        bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)

        for run in auto_sells:
            discord_id = int(run['discord_id'])
            action = run.get('action', 'sell')
            rtm_amt = run['rtm_amount']
            usd_amt = run['usd_amount']
            rate = run['rate']

            # Journalisation blockchain (best-effort)
            try:
                await bot_logger.log_blockchain_transaction(
                    from_id=discord_id,
                    to_address="0xROOTIUM_DEX",
                    rtm_amount=rtm_amt,
                    tx_type='AUTO BUY' if action == 'buy' else 'AUTO SELL',
                    usd_amount=usd_amt,
                )
            except Exception:
                pass

            # Notification privée
            try:
                user = self.bot.get_user(discord_id)
                if user is None:
                    try:
                        user = await self.bot.fetch_user(discord_id)
                    except Exception:
                        user = None
                if not user:
                    continue

                lang = await fetch_user_language(discord_id) or 'fr'
                repeat_mode = run.get('repeat_mode', 'once')
                repeat_info = (
                    text.get_for_lang(lang, 'g_market_auto_sell_dm_repeat')
                    if repeat_mode == 'repeat'
                    else text.get_for_lang(lang, 'g_market_auto_sell_dm_once')
                )

                dm_key = 'g_market_auto_buy_triggered_dm' if action == 'buy' else 'g_market_auto_sell_triggered_dm'
                title_key = 'g_market_auto_buy_dm_title' if action == 'buy' else 'g_market_auto_sell_dm_title'

                content = text.get_for_lang(
                    lang,
                    dm_key,
                    rtm=text.format_rtm(rtm_amt),
                    usd=text.format_usd(usd_amt),
                    rate=text.format_usd(rate),
                    usd_total=text.format_usd(run.get('new_dollars', 0)),
                    rtm_total=text.format_rtm(run.get('new_rootium', 0)),
                    repeat_info=repeat_info,
                )

                embed = RootEmbed(
                    action='market',
                    title=text.get_for_lang(lang, title_key),
                    content=content,
                    state=VisualState.SUCCESS,
                    locale=lang,
                    footer="ROOT OS · Marché",
                )
                await user.send(embed=embed)
                logger.info(
                    "[Market] Reçu d'ordre auto (%s) envoyé en DM au joueur %s (RTM: %s, USD: %s)",
                    action, discord_id, rtm_amt, usd_amt,
                )
            except discord.Forbidden:
                logger.info("[Market] DM d'ordre auto bloqué pour le joueur %s (MP fermés)", discord_id)
            except Exception:
                logger.warning(
                    "[Market] Échec d'envoi du DM d'ordre auto pour le joueur %s",
                    discord_id, exc_info=True,
                )

    @market_loop.before_loop
    async def before_market_loop(self):
        """Attend Discord, charge le cours persistant et rattrape l'historique avant le premier cycle."""
        await self.bot.wait_until_ready()
        await self.service.init_market()
        await self._catch_up_history()

    async def _catch_up_history(self):
        """Rattrape les créneaux de 15 minutes manquants sur 7 jours au démarrage."""
        try:
            settings = MathConfig.market_settings()
            if not settings.get('enabled'):
                return

            result = await self.service.catch_up_market(self.feed)
            if not result:
                return

            status = result.get('status')
            if status in ('applied', 'up_to_date'):
                interval = int(settings['interval_seconds'])
                now = time.time()
                self._done_slot = int(now // interval) * interval

            if status == 'applied':
                count = result.get('inserted', 0)
                latest_price = result.get('latest_price')
                latest_ts = result.get('latest_ts')

                logger.info(
                    "[Market] Rattrapage terminé : %d créneau(x) calculé(s) et inséré(s) (cours: %s USD)",
                    count, latest_price,
                )

                alerts = result.get('triggered_alerts') or []
                if alerts and latest_price:
                    await self._notify_alerts(alerts, latest_price)

                if latest_ts and latest_price:
                    try:
                        auto_sells = await self.service.process_auto_sells(latest_ts, latest_price)
                        if auto_sells:
                            await self._notify_auto_sells(auto_sells, latest_price)
                    except Exception:
                        logger.exception("[Market] Erreur lors du traitement des ventes automatiques post-rattrapage")
            elif status == 'up_to_date':
                logger.info("[Market] Historique de marché complet sur 7 jours, aucun rattrapage nécessaire.")
        except Exception:
            logger.exception("[Market] Erreur inattendue lors du rattrapage de marché au démarrage")

    @tasks.loop(hours=24)
    async def purge_loop(self):
        """Purge quotidienne de l'historique au-delà de la rétention."""
        try:
            deleted = await self.service.purge_market_history()
            if deleted:
                logger.info("[Market] %d ligne(s) d'historique purgée(s)", deleted)
        except Exception:
            logger.exception("[Market] Échec de la purge de l'historique")

    @purge_loop.before_loop
    async def before_purge_loop(self):
        """Attend la synchronisation complète du bot avant de démarrer la purge."""
        await self.bot.wait_until_ready()


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(MarketTask(bot))
