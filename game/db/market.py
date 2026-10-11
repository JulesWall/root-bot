"""
Persistance du cours dynamique du RTM (état courant + historique à 15 minutes).

Le cours est la composition des variations moyennes de BTC, ETH et SOL :
    asset_change_pct = (close_now / close_prev - 1) * 100
    average_change_pct = (btc + eth + sol) / 3
    price_next = price * (1 + average_change_pct / 100)

Toutes les valeurs monétaires sont des `Decimal`. Les formules sont évaluées par
`MathConfig` (AST sécurisé), jamais par `eval()`.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from game.math_config import MathConfig

logger = logging.getLogger(__name__)

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

    raw_avg = MathConfig.market_formula(
        'market_average_change_pct', btc_pct=btc, eth_pct=eth, sol_pct=sol,
    )
    multiplier_val = (
        settings.get('volatility_multiplier')
        if settings and 'volatility_multiplier' in settings
        else MathConfig.market_volatility_multiplier()
    )
    volatility_mult = Decimal(str(multiplier_val if multiplier_val is not None else 2.5))
    avg = raw_avg * volatility_mult

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


def build_catchup_cycles(
    all_slots: list[datetime],
    existing_entries: dict[datetime, dict],
    candles_by_symbol: dict[str, dict[int, list]],
    initial_price: Decimal,
    settings: dict | None = None,
    row_before: dict | None = None,
) -> list[dict]:
    """Calcule tous les cycles manquants sur la séquence all_slots.

    Garantit une continuité temporelle et mathématique complète.
    Si les premiers créneaux sont manquants sans historique antérieur connu,
    ils sont calculés à rebours depuis le premier enregistrement existant.
    """
    settings = settings or MathConfig.market_settings()
    interval_ms = int(settings['interval_seconds']) * 1000
    places = int(settings.get('price_decimal_places', 8))
    quantum = Decimal('1').scaleb(-places)

    missing_slots = [s for s in all_slots if s not in existing_entries]
    if not missing_slots:
        return []

    first_existing_slot = min(existing_entries.keys()) if existing_entries else None
    missing_prefix = [s for s in all_slots if s < first_existing_slot] if first_existing_slot else []

    # Cas A : préfixe manquant sans antécédent -> calcul à rebours
    backward_cycles = []
    if missing_prefix and not row_before:
        p_after = Decimal(str(existing_entries[first_existing_slot]['price_before']))
        for slot_dt in reversed(missing_prefix):
            slot_ms = int(slot_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
            prev_ms = slot_ms - interval_ms
            closes = {}
            for sym in settings['symbols']:
                sym_candles = candles_by_symbol.get(sym, {})
                c_prev = sym_candles.get(prev_ms)
                c_now = sym_candles.get(slot_ms)
                if c_prev and c_now:
                    closes[sym] = (Decimal(str(c_prev[4])), Decimal(str(c_now[4])))
                else:
                    closes[sym] = (Decimal('1'), Decimal('1'))

            cycle_res = compute_cycle(p_after, closes, settings)
            avg_pct = cycle_res['avg_pct']
            factor = Decimal('1') + (avg_pct / Decimal('100'))
            if factor <= Decimal('0'):
                factor = Decimal('1')
            p_before = (p_after / factor).quantize(quantum)
            backward_cycles.append({
                'market_ts': slot_dt,
                'price_before': p_before,
                'price_after': p_after,
                'btc_pct': cycle_res['btc_pct'],
                'eth_pct': cycle_res['eth_pct'],
                'sol_pct': cycle_res['sol_pct'],
                'avg_pct': cycle_res['avg_pct'],
                'capped': cycle_res['capped'],
            })
            p_after = p_before
        backward_cycles.reverse()

    # Cas B : calcul vers l'avant
    if first_existing_slot and missing_prefix and not row_before:
        remaining_slots = [s for s in all_slots if s > first_existing_slot]
        current_price = Decimal(str(existing_entries[first_existing_slot]['price_after']))
    else:
        remaining_slots = all_slots
        current_price = initial_price

    forward_cycles = []
    for slot_dt in remaining_slots:
        if slot_dt in existing_entries:
            current_price = Decimal(str(existing_entries[slot_dt]['price_after']))
            continue

        slot_ms = int(slot_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        prev_ms = slot_ms - interval_ms
        closes = {}
        for sym in settings['symbols']:
            sym_candles = candles_by_symbol.get(sym, {})
            c_prev = sym_candles.get(prev_ms)
            c_now = sym_candles.get(slot_ms)
            if c_prev and c_now:
                closes[sym] = (Decimal(str(c_prev[4])), Decimal(str(c_now[4])))
            else:
                closes[sym] = (Decimal('1'), Decimal('1'))

        cycle_res = compute_cycle(current_price, closes, settings)
        forward_cycles.append({
            'market_ts': slot_dt,
            'price_before': current_price,
            'price_after': cycle_res['price_after'],
            'btc_pct': cycle_res['btc_pct'],
            'eth_pct': cycle_res['eth_pct'],
            'sol_pct': cycle_res['sol_pct'],
            'avg_pct': cycle_res['avg_pct'],
            'capped': cycle_res['capped'],
        })
        current_price = cycle_res['price_after']

    return backward_cycles + forward_cycles


class MarketState:
    """Accès SQL à l'état courant du cours et à son historique."""

    @staticmethod
    def get(tx, for_update: bool = False) -> dict | None:
        """Retourne la ligne singleton de l'état courant (ou None si absente)."""
        suffix = ' FOR UPDATE' if for_update else ''
        return tx.one(f'SELECT * FROM rtm_market_state WHERE id = 1{suffix}')

    @staticmethod
    def ensure(tx) -> dict:
        """Garantit l'existence de l'état courant (synchronisé sur l'historique si présent, sinon amorçage `market.start_price`)."""
        state = MarketState.get(tx)
        latest_history = None
        try:
            latest_history = tx.one(
                'SELECT market_ts, price_after, source FROM rtm_market_history ORDER BY market_ts DESC LIMIT 1'
            )
        except Exception:
            pass

        if not state:
            settings = MathConfig.market_settings()
            start = Decimal(str(settings.get('start_price') or 0))
            if start <= 0:
                raise ValueError('market.start_price doit être strictement positif.')
            init_price = latest_history['price_after'] if latest_history else start
            init_ts = latest_history['market_ts'] if latest_history else None
            init_src = latest_history['source'] if latest_history else 'seed'
            tx.execute(
                'INSERT IGNORE INTO rtm_market_state '
                '(id, price_usd, market_ts, observed_at, status, source) '
                "VALUES (1, %s, %s, UTC_TIMESTAMP(6), 'live', %s)",
                (init_price, init_ts, init_src),
            )
            return MarketState.get(tx)

        # Si l'historique contient un point et que l'état courant est un seed, en retard ou désynchronisé
        if latest_history and Decimal(str(latest_history.get('price_after') or 0)) > 0:
            state_ts = state.get('market_ts')
            state_price = Decimal(str(state.get('price_usd') or 0))
            hist_price = Decimal(str(latest_history['price_after']))
            if state.get('source') == 'seed' or state_ts is None or state_ts != latest_history['market_ts'] or state_price != hist_price:
                tx.execute(
                    "UPDATE rtm_market_state SET price_usd = %s, market_ts = %s, "
                    "observed_at = UTC_TIMESTAMP(6), status = 'live', source = %s WHERE id = 1",
                    (hist_price, latest_history['market_ts'], latest_history['source']),
                )
                state = MarketState.get(tx)
        return state

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
            state = MarketState.ensure(tx)
        except Exception:
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

        # On cherche la dernière bougie enregistrée dans l'historique
        latest_history = tx.one(
            'SELECT market_ts, price_after FROM rtm_market_history ORDER BY market_ts DESC LIMIT 1'
        )
        if not latest_history or 'price_after' not in latest_history:
            newest = tx.one('SELECT MAX(market_ts) AS ts FROM rtm_market_history')
            newest_ts = newest.get('ts') if newest else None
            if newest_ts is not None and market_ts <= newest_ts:
                return {
                    'status': 'already_applied',
                    'price': Decimal(str(state['price_usd'])),
                    'market_ts': newest_ts,
                }
            previous_price = Decimal(str(state['price_usd']))
        else:
            latest_ts = latest_history['market_ts']
            if latest_ts is not None and market_ts <= latest_ts:
                return {
                    'status': 'already_applied',
                    'price': Decimal(str(latest_history['price_after'])),
                    'market_ts': latest_ts,
                }
            previous_price = Decimal(str(latest_history['price_after']))

        result = compute_cycle(previous_price, closes)
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

    @staticmethod
    def get_history_in_range(tx, start_dt: datetime, end_dt: datetime | None = None) -> list[dict]:
        """Retourne l'historique chronologique dans l'intervalle [start_dt, end_dt]."""
        if end_dt:
            return tx.all(
                'SELECT market_ts, price_before, price_after, btc_pct, eth_pct, sol_pct, avg_pct '
                'FROM rtm_market_history WHERE market_ts >= %s AND market_ts <= %s ORDER BY market_ts ASC',
                (start_dt, end_dt),
            )
        return tx.all(
            'SELECT market_ts, price_before, price_after, btc_pct, eth_pct, sol_pct, avg_pct '
            'FROM rtm_market_history WHERE market_ts >= %s ORDER BY market_ts ASC',
            (start_dt,),
        )

    @staticmethod
    def get_last_before(tx, dt: datetime) -> dict | None:
        """Retourne la dernière entrée d'historique strictement antérieure à dt."""
        return tx.one(
            'SELECT market_ts, price_before, price_after '
            'FROM rtm_market_history WHERE market_ts < %s ORDER BY market_ts DESC LIMIT 1',
            (dt,),
        )

    @staticmethod
    def save_catchup_cycles(tx, cycles: list[dict], source: str) -> dict:
        """Insère un lot de cycles rattrapés et met à jour l'état si le plus récent est postérieur."""
        if not cycles:
            return {'status': 'noop', 'inserted': 0}

        tx.acquire_lock(MARKET_LOCK)
        state = MarketState.get(tx, for_update=True) or MarketState.ensure(tx)

        params = [
            (
                c['market_ts'], c['price_before'], c['price_after'],
                c['btc_pct'], c['eth_pct'], c['sol_pct'],
                c['avg_pct'], 1 if c.get('capped') else 0, source,
            )
            for c in cycles
        ]
        if hasattr(tx, 'executemany'):
            tx.executemany(
                'INSERT IGNORE INTO rtm_market_history '
                '(market_ts, price_before, price_after, btc_pct, eth_pct, sol_pct, avg_pct, capped, source) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                params,
            )
        else:
            tx.cursor.executemany(
                'INSERT IGNORE INTO rtm_market_history '
                '(market_ts, price_before, price_after, btc_pct, eth_pct, sol_pct, avg_pct, capped, source) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                params,
            )

        latest_cycle = max(cycles, key=lambda c: c['market_ts'])
        latest_ts = latest_cycle['market_ts']

        # Synchronisation systématique de rtm_market_state sur la dernière bougie absolue
        latest_row = tx.one(
            'SELECT price_after, market_ts, source FROM rtm_market_history ORDER BY market_ts DESC LIMIT 1'
        )
        if latest_row and isinstance(latest_row, dict) and 'price_after' in latest_row:
            final_price = latest_row['price_after']
            final_ts = latest_row.get('market_ts') or latest_ts
            final_source = latest_row.get('source') or source
        else:
            final_price = latest_cycle['price_after']
            final_ts = latest_ts
            final_source = source

        tx.execute(
            "UPDATE rtm_market_state SET price_usd = %s, market_ts = %s, "
            "observed_at = UTC_TIMESTAMP(6), status = 'live', source = %s WHERE id = 1",
            (final_price, final_ts, final_source),
        )

        triggered_alerts = []
        try:
            from game.db.market_alerts import MarketAlerts
            now_dt = getattr(tx, 'now', None) or datetime.utcnow()
            triggered_alerts = MarketAlerts.evaluate_and_trigger(
                tx, final_price, now_dt
            )
        except Exception:
            logger.exception("[Market] Erreur lors de l'évaluation des alertes post-rattrapage")

        return {
            'status': 'applied',
            'inserted': len(cycles),
            'latest_price': final_price,
            'latest_ts': final_ts,
            'triggered_alerts': triggered_alerts,
        }
