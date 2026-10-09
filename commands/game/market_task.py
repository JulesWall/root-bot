"""Tâche de fond du cours dynamique du RTM.

Toutes les 15 minutes UTC (alignées sur les quarts d'heure, sans dérive), lit les deux
dernières bougies clôturées de BTC, ETH et SOL, calcule la moyenne simple de leurs
variations et compose le cours du RTM avec le cours précédent.

- Aucun appel à l'exchange en dehors de cette tâche (jamais depuis un callback Discord).
- Échec ou donnée périmée : le cours n'est pas modifié, le flux est marqué « retardé ».
- Redémarrage : un seul cycle (la dernière paire de bougies) est appliqué, sans rattrapage.
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
                cooldown = int(alert.get('cooldown_minutes', 60))

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
                    cooldown=cooldown,
                )

                state = VisualState.REUSSITE if direction == 'above' else VisualState.ATTENTION
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

    @market_loop.before_loop
    async def before_market_loop(self):
        """Attend Discord puis charge le cours persistant avant le premier cycle."""
        await self.bot.wait_until_ready()
        await self.service.init_market()

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
