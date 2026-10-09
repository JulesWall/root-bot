"""
Persistance du cours dynamique du RTM (état courant + historique à 15 minutes).

Le cours est la composition des variations moyennes de BTC, ETH et SOL :
    asset_change_pct = (close_now / close_prev - 1) * 100
    average_change_pct = (btc + eth + sol) / 3
    price_next = price * (1 + average_change_pct / 100)

Toutes les valeurs monétaires sont des `Decimal`. Les formules sont évaluées par
`MathConfig` (AST sécurisé), jamais par `eval()`.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from game.math_config import MathConfig

MARKET_LOCK = 'rtm_market'
PCT_QUANTUM = Decimal('0.000001')


def compute_cycle(price, closes: dict, settings: dict | None = None) -> dict:
    """Calcule le prochain cours à partir des clôtures (prev, now) des trois actifs.

    `closes` associe chaque symbole configuré à un tuple `(close_prev, close_now)`.
    Retourne les trois variations, la moyenne brute, le cours suivant et le drapeau `capped`.
    """
    settings = settings or MathConfig.market_settings()
    symbols = settings['symbols']
    if len(symbols) != 3 or any(sym not in closes for sym in symbols):
        raise ValueError('Les trois cotations (BTC, ETH, SOL) sont requises.')

    changes = []
    for sym in symbols:
        prev, now = closes[sym]
        prev, now = Decimal(str(prev)), Decimal(str(now))
        if prev <= 0 or now <= 0:
            raise ValueError(f'Cotation invalide pour {sym}.')
        changes.append(MathConfig.market_formula(
            'market_asset_change_pct', close_now=now, close_prev=prev,
        ))
    btc, eth, sol = changes

    avg = MathConfig.market_formula(
        'market_average_change_pct', btc_pct=btc, eth_pct=eth, sol_pct=sol,
    )
    effective = avg
    capped = False
    cap = settings.get('max_change_pct')
    if cap is not None:
        cap = abs(Decimal(str(cap)))
        if effective > cap:
            effective, capped = cap, True
        elif effective < -cap:
            effective, capped = -cap, True

    price = Decimal(str(price))
    places = int(settings.get('price_decimal_places', 8))
    quantum = Decimal('1').scaleb(-places)
    price_next = MathConfig.market_formula(
        'market_price_next', price=price, avg_pct=effective,
    ).quantize(quantum)
    if price_next <= 0:
        raise ValueError('Cours calculé invalide.')

    return {
        'btc_pct': btc.quantize(PCT_QUANTUM),
        'eth_pct': eth.quantize(PCT_QUANTUM),
        'sol_pct': sol.quantize(PCT_QUANTUM),
        'avg_pct': avg.quantize(PCT_QUANTUM),
        'price_before': price,
        'price_after': price_next,
        'capped': capped,
    }


class MarketState:
    """Accès SQL à l'état courant du cours et à son historique."""

    @staticmethod
    def get(tx, for_update: bool = False) -> dict | None:
        """Retourne la ligne singleton de l'état courant (ou None si absente)."""
        suffix = ' FOR UPDATE' if for_update else ''
        return tx.one(f'SELECT * FROM rtm_market_state WHERE id = 1{suffix}')

    @staticmethod
    def ensure(tx) -> dict:
        """Garantit l'existence de l'état courant (amorçage `market.start_price`)."""
        state = MarketState.get(tx)
        if state:
            return state
        settings = MathConfig.market_settings()
        start = Decimal(str(settings.get('start_price') or 0))
        if start <= 0:
            raise ValueError('market.start_price doit être strictement positif.')
        tx.execute(
            'INSERT IGNORE INTO rtm_market_state '
            '(id, price_usd, market_ts, observed_at, status, source) '
            "VALUES (1, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP(6), 'seed', 'seed')",
            (start,),
        )
        return MarketState.get(tx)

    @staticmethod
    def get_rate(tx) -> Decimal:
        """Cours RTM → USD courant lu en base (amorçage si la table est vide)."""
        return Decimal(str(MarketState.ensure(tx)['price_usd']))

    @staticmethod
    def current_rate(tx) -> tuple[Decimal, dict | None]:
        """Cours courant lu dans la transaction de l'appelant, avec son état de fraîcheur.

        Retourne `(taux, info)` où `info` contient `status` et `updated_ts` (epoch UTC en
        secondes). Si l'état n'est pas lisible (table absente, base indisponible), retombe
        sur le cours en mémoire/d'amorçage de `MathConfig` et `info` vaut None.
        """
        try:
            state = MarketState.get(tx)
        except Exception:
            state = None
        if state and Decimal(str(state.get('price_usd') or 0)) > 0:
            observed = state.get('observed_at')
            updated_ts = None
            if isinstance(observed, datetime):
                updated_ts = int(observed.replace(tzinfo=timezone.utc).timestamp())
            return Decimal(str(state['price_usd'])), {
                'status': str(state.get('status') or 'live'),
                'updated_ts': updated_ts,
            }
        return MathConfig.rtm_to_usd_rate(), None

    @staticmethod
    def apply_cycle(tx, market_ts: datetime, closes: dict, source: str) -> dict:
        """Applique un cycle de marché, une seule fois par `market_ts` (idempotent).

        Sérialisé par verrou MySQL ; la clé primaire de `rtm_market_history`
        garantit l'unicité même en cas de processus concurrents.
        """
        tx.acquire_lock(MARKET_LOCK)
        state = MarketState.get(tx, for_update=True) or MarketState.ensure(tx)

        newest = tx.one('SELECT MAX(market_ts) AS ts FROM rtm_market_history')
        newest_ts = newest['ts'] if newest else None
        if newest_ts is not None and market_ts <= newest_ts:
            return {
                'status': 'already_applied',
                'price': Decimal(str(state['price_usd'])),
                'market_ts': newest_ts,
            }

        result = compute_cycle(state['price_usd'], closes)
        tx.execute(
            'INSERT INTO rtm_market_history '
            '(market_ts, price_before, price_after, btc_pct, eth_pct, sol_pct, avg_pct, capped, source) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (
                market_ts, result['price_before'], result['price_after'],
                result['btc_pct'], result['eth_pct'], result['sol_pct'],
                result['avg_pct'], 1 if result['capped'] else 0, source,
            ),
        )
        tx.execute(
            "UPDATE rtm_market_state SET price_usd = %s, market_ts = %s, "
            "observed_at = UTC_TIMESTAMP(6), status = 'live', source = %s WHERE id = 1",
            (result['price_after'], market_ts, source),
        )

        triggered_alerts = []
        try:
            from game.db.market_alerts import MarketAlerts
            now_dt = getattr(tx, 'now', None) or datetime.utcnow()
            triggered_alerts = MarketAlerts.evaluate_and_trigger(tx, result['price_after'], now_dt)
        except Exception:
            logger.exception("[Market] Erreur lors de l'évaluation des alertes")

        result.update(
            status='applied',
            market_ts=market_ts,
            price=result['price_after'],
            triggered_alerts=triggered_alerts,
        )
        return result

    @staticmethod
    def mark_delayed(tx) -> dict:
        """Marque le flux comme retardé sans modifier le cours."""
        tx.acquire_lock(MARKET_LOCK)
        state = MarketState.ensure(tx)
        tx.execute("UPDATE rtm_market_state SET status = 'delayed' WHERE id = 1")
        return {'status': 'delayed', 'price': Decimal(str(state['price_usd']))}

    @staticmethod
    def series(tx, since: datetime) -> list[dict]:
        """Historique chronologique depuis `since` (UTC)."""
        return tx.all(
            'SELECT market_ts, price_after, btc_pct, eth_pct, sol_pct, avg_pct '
            'FROM rtm_market_history WHERE market_ts >= %s ORDER BY market_ts ASC',
            (since,),
        )

    @staticmethod
    def purge(tx, retention_days: int | None = None) -> int:
        """Supprime l'historique plus ancien que la rétention configurée."""
        days = int(retention_days or MathConfig.market_settings()['history_retention_days'])
        cutoff = tx.now - timedelta(days=days)
        tx.execute('DELETE FROM rtm_market_history WHERE market_ts < %s', (cutoff,))
        return int(tx.cursor.rowcount or 0)
