"""
Lecture des cotations BTC/ETH/SOL via CCXT (asynchrone) pour le cours dynamique du RTM.

Le RTM reste une monnaie interne : seules des données publiques de marché (OHLCV)
sont lues, aucun ordre n'est jamais envoyé à un exchange.
La dernière bougie retournée par un exchange peut être en cours : elle est
systématiquement écartée, seules deux bougies **clôturées consécutives** sont retenues.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

from game.math_config import MathConfig

logger = logging.getLogger(__name__)


class MarketFeedError(Exception):
    """Erreur de collecte du marché (message sans information sensible)."""


def select_closed_pair(ohlcv_by_symbol: dict, now_ms: int, interval_ms: int,
                       max_staleness_s: int) -> dict | None:
    """Sélectionne, pour tous les actifs, les deux dernières bougies clôturées consécutives.

    `ohlcv_by_symbol` : `{symbole: [[open_ts_ms, o, h, l, c, v], ...]}`.
    Retourne `{'market_ts': datetime UTC naïf, 'closes': {symbole: (prev, now)}}`
    ou `None` si un actif manque, si les horodatages divergent ou si la donnée est trop ancienne.
    `market_ts` désigne l'ouverture de la dernière bougie clôturée.
    """
    if not ohlcv_by_symbol:
        return None

    pairs = {}
    for symbol, candles in ohlcv_by_symbol.items():
        closed = {int(c[0]): c for c in (candles or []) if int(c[0]) + interval_ms <= now_ms}
        if not closed:
            return None
        last_ts = max(closed)
        prev = closed.get(last_ts - interval_ms)
        if prev is None:
            return None
        pairs[symbol] = (last_ts, Decimal(str(prev[4])), Decimal(str(closed[last_ts][4])))

    stamps = {value[0] for value in pairs.values()}
    if len(stamps) != 1:
        return None
    last_ts = stamps.pop()
    if (now_ms - (last_ts + interval_ms)) / 1000 > max_staleness_s:
        return None

    return {
        'market_ts': datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc).replace(tzinfo=None),
        'closes': {sym: (value[1], value[2]) for sym, value in pairs.items()},
    }


class MarketFeed:
    """Client CCXT asynchrone (un seul exchange, un seul marché cohérent)."""

    def __init__(self):
        self._exchange = None
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        """Ouvre l'exchange configuré et vérifie qu'il sert l'OHLCV à l'intervalle voulu."""
        async with self._lock:
            if self._exchange is not None:
                return
            import ccxt.async_support as ccxt

            settings = MathConfig.market_settings()
            name = settings['exchange']
            if not hasattr(ccxt, name):
                raise MarketFeedError(f"Exchange inconnu : {name}")
            exchange = getattr(ccxt, name)({'enableRateLimit': True})
            try:
                if not exchange.has.get('fetchOHLCV'):
                    raise MarketFeedError(f"{name} ne prend pas en charge fetch_ohlcv.")
                await exchange.load_markets()
                timeframes = getattr(exchange, 'timeframes', None) or {}
                if settings['timeframe'] not in timeframes:
                    raise MarketFeedError(f"{name} ne prend pas en charge l'intervalle {settings['timeframe']}.")
            except Exception:
                await exchange.close()
                raise
            self._exchange = exchange
            logger.info("[Market] Source %s ouverte (%s, %s)", name, settings['timeframe'],
                        ', '.join(settings['symbols']))

    async def close(self) -> None:
        """Ferme proprement la session HTTP de l'exchange."""
        exchange, self._exchange = self._exchange, None
        if exchange is not None:
            await exchange.close()

    async def fetch_closes(self) -> dict | None:
        """Récupère les deux dernières clôtures consécutives des trois actifs, ou None."""
        settings = MathConfig.market_settings()
        await self.open()
        symbols = settings['symbols']
        results = await asyncio.gather(
            *(self._exchange.fetch_ohlcv(sym, settings['timeframe'], limit=int(settings['fetch_limit']))
              for sym in symbols),
            return_exceptions=True,
        )
        ohlcv = {}
        for sym, res in zip(symbols, results):
            if isinstance(res, Exception):
                raise MarketFeedError(f"Lecture impossible pour {sym} : {type(res).__name__}")
            ohlcv[sym] = res

        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        selected = select_closed_pair(
            ohlcv, now_ms, int(settings['interval_seconds']) * 1000,
            int(settings['max_staleness_seconds']),
        )
        if selected:
            selected['source'] = f"{settings['exchange']}:{settings['quote_currency']}"
        return selected

