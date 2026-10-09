"""Tests du cours dynamique du RTM (calcul, sélection des bougies, idempotence)."""

import sys
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.db.market import MarketState, compute_cycle
from game.market_feed import select_closed_pair
from game.math_config import MathConfig

SYMS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
SETTINGS = {
    'symbols': SYMS, 'price_decimal_places': 8, 'max_change_pct': None,
}
IV = 900_000


def candle(ts, close):
    return [ts, close, close, close, close, 1]


class ComputeCycleTests(unittest.TestCase):
    def test_zero_average_keeps_price(self):
        closes = {
            'BTC/USDT': (Decimal(100), Decimal(101)),
            'ETH/USDT': (Decimal(100), Decimal(99)),
            'SOL/USDT': (Decimal(100), Decimal(100)),
        }
        res = compute_cycle(Decimal('43567'), closes, SETTINGS)
        self.assertEqual(res['avg_pct'], Decimal('0'))
        self.assertEqual(res['price_after'], Decimal('43567').quantize(Decimal('1e-8')))

    def test_compounding_two_cycles(self):
        up = {s: (Decimal(100), Decimal(110)) for s in SYMS}
        first = compute_cycle(Decimal(1000), up, SETTINGS)['price_after']
        second = compute_cycle(first, up, SETTINGS)['price_after']
        self.assertEqual(first, Decimal('1100'))
        self.assertEqual(second, Decimal('1210'))

    def test_missing_asset_rejected(self):
        with self.assertRaises(ValueError):
            compute_cycle(Decimal(1000), {'BTC/USDT': (Decimal(1), Decimal(2))}, SETTINGS)

    def test_zero_quote_rejected(self):
        closes = {s: (Decimal(0), Decimal(1)) for s in SYMS}
        with self.assertRaises(ValueError):
            compute_cycle(Decimal(1000), closes, SETTINGS)

    def test_cap_applied_when_configured(self):
        up = {s: (Decimal(100), Decimal(150)) for s in SYMS}
        res = compute_cycle(Decimal(1000), up, {**SETTINGS, 'max_change_pct': 5})
        self.assertTrue(res['capped'])
        self.assertEqual(res['price_after'], Decimal('1050'))
        self.assertEqual(res['avg_pct'], Decimal('50'))

    def test_formulas_stay_ast_only(self):
        with self.assertRaises(ValueError):
            MathConfig.validate(__import__('ast').parse('__import__("os")', mode='eval'))


class SelectClosedPairTests(unittest.TestCase):
    def _data(self, last_open, offset=0):
        return {
            s: [candle(last_open - IV + offset, 100), candle(last_open + offset, 101)]
            for s in SYMS
        }

    def test_ignores_open_candle(self):
        base = 10 * IV
        data = self._data(base - IV)
        for s in SYMS:
            data[s].append(candle(base, 999))  # bougie en cours
        res = select_closed_pair(data, base + 30_000, IV, 1500)
        self.assertEqual(res['closes'][SYMS[0]], (Decimal(100), Decimal(101)))

    def test_missing_asset_returns_none(self):
        base = 10 * IV
        data = self._data(base - IV)
        data['SOL/USDT'] = []
        self.assertIsNone(select_closed_pair(data, base + 30_000, IV, 1500))

    def test_mismatched_timestamps(self):
        base = 10 * IV
        data = self._data(base - IV)
        data['ETH/USDT'] = [candle(base - 3 * IV, 100), candle(base - 2 * IV, 101)]
        self.assertIsNone(select_closed_pair(data, base + 30_000, IV, 1500))

    def test_non_consecutive_returns_none(self):
        base = 10 * IV
        data = {s: [candle(base - 3 * IV, 100), candle(base - IV, 101)] for s in SYMS}
        self.assertIsNone(select_closed_pair(data, base + 30_000, IV, 1500))

    def test_stale_data_rejected(self):
        base = 10 * IV
        data = self._data(base - IV)
        self.assertIsNone(select_closed_pair(data, base + 5_000_000, IV, 1500))

    def test_market_ts_is_naive_utc_open(self):
        base = 10 * IV
        res = select_closed_pair(self._data(base - IV), base + 30_000, IV, 1500)
        self.assertEqual(res['market_ts'], datetime.utcfromtimestamp((base - IV) / 1000))


class ApplyCycleTests(unittest.TestCase):
    CLOSES = {s: (Decimal(100), Decimal(110)) for s in SYMS}

    def _tx(self, newest_ts):
        tx = MagicMock()
        state = {'price_usd': Decimal(1000), 'status': 'live'}
        tx.one.side_effect = lambda sql, args=(): (
            {'ts': newest_ts} if 'MAX(market_ts)' in sql else state
        )
        tx.all.return_value = []
        return tx

    def setUp(self):
        MathConfig.clear_cache()

    def test_apply_cycle_applies_new_timestamp(self):
        tx = self._tx(None)
        res = MarketState.apply_cycle(tx, datetime(2026, 1, 1, 12, 0), self.CLOSES, 'test')
        self.assertEqual(res['status'], 'applied')
        self.assertEqual(res['price'], Decimal('1100.00000000'))
        tx.acquire_lock.assert_called_once_with('rtm_market')

    def test_apply_cycle_idempotent_same_timestamp(self):
        ts = datetime(2026, 1, 1, 12, 0)
        tx = self._tx(ts)
        res = MarketState.apply_cycle(tx, ts, self.CLOSES, 'test')
        self.assertEqual(res['status'], 'already_applied')
        tx.execute.assert_not_called()

    def test_apply_cycle_older_timestamp_ignored(self):
        tx = self._tx(datetime(2026, 1, 1, 12, 0))
        res = MarketState.apply_cycle(tx, datetime(2026, 1, 1, 11, 45), self.CLOSES, 'test')
        self.assertEqual(res['status'], 'already_applied')

    def test_apply_cycle_returns_triggered_alerts(self):
        tx = self._tx(None)
        res = MarketState.apply_cycle(tx, datetime(2026, 1, 1, 12, 0), self.CLOSES, 'test')
        self.assertIn('triggered_alerts', res)
        self.assertIsInstance(res['triggered_alerts'], list)


class ConvertMarketRateTests(unittest.TestCase):
    """La vente RTM → USD utilise le cours persistant lu dans la transaction."""

    def _tx(self, price='50000', status='live'):
        tx = MagicMock()
        tx.one.return_value = {
            'price_usd': Decimal(price), 'status': status,
            'observed_at': datetime(2026, 1, 1, 12, 0, 10),
        }
        return tx

    def _convert(self, tx, **args):
        from unittest.mock import patch
        from game.db.players import Player
        player = {'rootium': Decimal('1.00000'), 'dollars': Decimal('0.00')}
        with patch('game.db.players.PlayerData.get', return_value=player), \
                patch('game.db.players.UpdatePlayer.set') as upd:
            return Player.convert(tx, 1, **args), upd

    def test_current_rate_reads_state_and_freshness(self):
        rate, info = MarketState.current_rate(self._tx('50000', 'delayed'))
        self.assertEqual(rate, Decimal('50000'))
        self.assertEqual(info['status'], 'delayed')
        self.assertEqual(info['updated_ts'], 1767268810)

    def test_current_rate_falls_back_without_state(self):
        tx = MagicMock()
        tx.one.return_value = None
        rate, info = MarketState.current_rate(tx)
        self.assertEqual(rate, MathConfig.rtm_to_usd_rate())
        self.assertIsNone(info)

    def test_current_rate_falls_back_on_error(self):
        tx = MagicMock()
        tx.one.side_effect = RuntimeError('db down')
        rate, info = MarketState.current_rate(tx)
        self.assertEqual(rate, MathConfig.rtm_to_usd_rate())
        self.assertIsNone(info)

    def test_quote_uses_persisted_rate_and_exposes_freshness(self):
        quote, upd = self._convert(self._tx('50000', 'delayed'), amount='0.5', confirm=False)
        self.assertEqual(quote['rate'], Decimal('50000'))
        self.assertEqual(quote['gross_usd'], Decimal('25000.00'))
        self.assertEqual(quote['fee_usd'], Decimal('250.00'))
        self.assertEqual(quote['usd_amount'], Decimal('24750.00'))
        self.assertEqual(quote['market_status'], 'delayed')
        self.assertEqual(quote['market_updated_ts'], 1767268810)
        upd.assert_not_called()

    def test_confirm_refused_when_rate_changed_since_quote(self):
        from game.game_error import GameError
        with self.assertRaises(GameError) as cm:
            self._convert(self._tx('50100'), amount='0.5', confirm=True, rate='50000')
        self.assertEqual(cm.exception.key, 'quote_changed')

    def test_confirm_accepted_when_rate_unchanged(self):
        sold, upd = self._convert(self._tx('50000.00000000'), amount='0.5', confirm=True, rate='50000')
        self.assertTrue(sold['converted'])
        upd.assert_called_once()

    def test_pvp_threshold_does_not_follow_market(self):
        MathConfig.set_market_rate('10')
        low = MathConfig.calculate_pvp_overrun_threshold(2)
        MathConfig.set_market_rate('999999')
        high = MathConfig.calculate_pvp_overrun_threshold(2)
        MathConfig.set_market_rate(None)
        self.assertEqual(low, high)


class MathConfigMarketTests(unittest.TestCase):
    def tearDown(self):
        MathConfig.set_market_rate(None)

    def test_rate_falls_back_to_start_price(self):
        MathConfig.set_market_rate(None)
        expected = Decimal(str(MathConfig.market_settings().get('start_price') or 43567))
        self.assertEqual(MathConfig.rtm_to_usd_rate(), expected)

    def test_rate_uses_cached_market_price(self):
        MathConfig.set_market_rate('50000.12345678')
        self.assertEqual(MathConfig.rtm_to_usd_rate(), Decimal('50000.12345678'))
        self.assertEqual(MathConfig.convert_rtm_to_usd(2), Decimal('100000.25'))

    def test_pvp_reference_rate_independent_of_market(self):
        MathConfig.set_market_rate('99999')
        self.assertEqual(MathConfig.pvp_reference_rate(), Decimal('43567'))

    def test_market_settings_have_three_symbols(self):
        self.assertEqual(len(MathConfig.market_settings()['symbols']), 3)


class MarketChartsTests(unittest.TestCase):
    """Tests des fonctions de sparkline, calculs de période, downsampling LTTB et rendu PNG."""

    def test_sparkline_empty_and_flat(self):
        from game.market_charts import sparkline
        empty = sparkline([])
        self.assertEqual(len(empty), 30)
        flat = sparkline([100, 100, 100], width=10)
        self.assertEqual(len(flat), 10)
        self.assertTrue(all(c == flat[0] for c in flat))

    def test_sparkline_variation(self):
        from game.market_charts import sparkline
        up = sparkline([10, 20, 30, 40, 50], width=5)
        self.assertEqual(len(up), 5)
        # La première barre doit être la plus basse et la dernière la plus haute
        self.assertLess(up[0], up[-1])

    def test_period_change_pct(self):
        from game.market_charts import period_change_pct
        pct = period_change_pct(Decimal('100'), Decimal('105'))
        self.assertEqual(pct, Decimal('5.00'))
        pct_down = period_change_pct(Decimal('100'), Decimal('95'))
        self.assertEqual(pct_down, Decimal('-5.00'))

    def test_downsample_lttb(self):
        from datetime import timedelta
        from game.market_charts import downsample_lttb
        base = datetime(2026, 1, 1, 0, 0)
        pts = [
            {'market_ts': base + timedelta(minutes=i), 'price_after': Decimal(str(100 + (i % 5)))}
            for i in range(100)
        ]
        sampled = downsample_lttb(pts, threshold=20)
        self.assertEqual(len(sampled), 20)
        self.assertEqual(sampled[0], pts[0])
        self.assertEqual(sampled[-1], pts[-1])

    def test_detect_gaps(self):
        from game.market_charts import detect_gaps
        pts = [
            {'market_ts': datetime(2026, 1, 1, 10, 0), 'price_after': Decimal('100')},
            {'market_ts': datetime(2026, 1, 1, 10, 15), 'price_after': Decimal('101')},
            {'market_ts': datetime(2026, 1, 1, 12, 0), 'price_after': Decimal('102')},  # trou > 30m
        ]
        gaps = detect_gaps(pts, max_gap_seconds=1800)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0], (1, 2))

    def test_render_chart_sync_creates_valid_png(self):
        from game.market_charts import _render_chart_sync
        pts = [
            {'market_ts': datetime(2026, 1, 1, 10, 0), 'price_after': Decimal('100')},
            {'market_ts': datetime(2026, 1, 1, 10, 15), 'price_after': Decimal('102')},
            {'market_ts': datetime(2026, 1, 1, 10, 30), 'price_after': Decimal('101')},
        ]
        png_bytes = _render_chart_sync(pts, '24h', '20260101_103000', 'binance:USDT')
        # Signature magic bytes PNG
        self.assertTrue(png_bytes.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertGreater(len(png_bytes), 1000)


class FakeAlertTx:
    """Mock léger de transaction pour tester MarketAlerts de manière déterministe."""

    def __init__(self, now=None):
        self.alerts = []
        self._next_id = 1
        self.now = now or datetime(2026, 1, 1, 12, 0)
        self.acquired_locks = []

    def acquire_lock(self, name, timeout=10):
        self.acquired_locks.append(name)

    def execute(self, sql, args=()):
        sql_u = sql.upper().strip()
        if "INSERT INTO RTM_PRICE_ALERTS" in sql_u:
            aid = self._next_id
            self._next_id += 1
            self.alerts.append({
                'id': aid,
                'discord_id': int(args[0]),
                'direction': str(args[1]),
                'threshold_usd': Decimal(str(args[2])),
                'cooldown_minutes': int(args[3]),
                'enabled': 1,
                'armed': 1,
                'last_notified_at': None,
            })
            return aid
        elif "DELETE FROM RTM_PRICE_ALERTS" in sql_u:
            aid = int(args[0])
            self.alerts = [a for a in self.alerts if a['id'] != aid]
            return 1
        elif "UPDATE RTM_PRICE_ALERTS SET ARMED = 1" in sql_u:
            price = Decimal(str(args[0]))
            now_val = args[2] if len(args) > 2 else self.now
            for a in self.alerts:
                if a['enabled'] == 1 and a['armed'] == 0:
                    if (a['direction'] == 'above' and price < a['threshold_usd']) or \
                       (a['direction'] == 'below' and price > a['threshold_usd']):
                        a['armed'] = 1
                    elif a.get('last_notified_at'):
                        diff = (now_val - a['last_notified_at']).total_seconds() / 60
                        if diff >= a['cooldown_minutes']:
                            a['armed'] = 1
            return 1
        elif "UPDATE RTM_PRICE_ALERTS SET ARMED = 0" in sql_u:
            now_val = args[0]
            aid = int(args[1])
            for a in self.alerts:
                if a['id'] == aid:
                    a['armed'] = 0
                    a['last_notified_at'] = now_val
            return 1
        elif "UPDATE RTM_PRICE_ALERTS SET ENABLED =" in sql_u:
            new_en = int(args[0])
            new_ar = int(args[1])
            aid = int(args[2])
            for a in self.alerts:
                if a['id'] == aid:
                    a['enabled'] = new_en
                    a['armed'] = new_ar
            return 1
        return 0

    def one(self, sql, args=()):
        sql_u = sql.upper().strip()
        if "COUNT(*)" in sql_u:
            uid = int(args[0])
            return {'cnt': sum(1 for a in self.alerts if a['discord_id'] == uid)}
        elif "WHERE DISCORD_ID = %S AND DIRECTION = %S AND THRESHOLD_USD = %S" in sql_u:
            uid, direction, thresh = int(args[0]), str(args[1]), Decimal(str(args[2]))
            for a in self.alerts:
                if a['discord_id'] == uid and a['direction'] == direction and a['threshold_usd'] == thresh:
                    return {'id': a['id']}
            return None
        elif "WHERE ID = %S AND DISCORD_ID = %S" in sql_u:
            aid, uid = int(args[0]), int(args[1])
            for a in self.alerts:
                if a['id'] == aid and a['discord_id'] == uid:
                    return dict(a)
            return None
        return None

    def all(self, sql, args=()):
        sql_u = sql.upper().strip()
        if "WHERE DISCORD_ID = %S" in sql_u:
            uid = int(args[0])
            return [dict(a) for a in self.alerts if a['discord_id'] == uid]
        elif "WHERE ENABLED = 1 AND ARMED = 1" in sql_u:
            price = Decimal(str(args[0]))
            res = []
            for a in self.alerts:
                if a['enabled'] == 1 and a['armed'] == 1:
                    if a['direction'] == 'above' and price >= a['threshold_usd']:
                        res.append(dict(a))
                    elif a['direction'] == 'below' and price <= a['threshold_usd']:
                        res.append(dict(a))
            return res
        return []


class MarketAlertsTests(unittest.TestCase):
    """Tests unitaires de la gestion et du déclenchement des alertes de marché."""

    def setUp(self):
        self.tx = FakeAlertTx(now=datetime(2026, 1, 1, 12, 0))
        from game.math_config import MathConfig
        MathConfig.clear_cache()

    def test_create_alert_valid(self):
        from game.db.market_alerts import MarketAlerts
        alert = MarketAlerts.create(
            self.tx,
            discord_id=123,
            direction='above',
            threshold_usd=Decimal('50000'),
            cooldown_minutes=60,
            current_price=Decimal('40000'),
        )
        self.assertEqual(alert['id'], 1)
        self.assertEqual(alert['direction'], 'above')
        self.assertEqual(alert['threshold_usd'], Decimal('50000'))
        self.assertEqual(alert['cooldown_minutes'], 60)
        self.assertEqual(alert['enabled'], 1)
        self.assertEqual(alert['armed'], 1)

    def test_create_alert_limit_reached(self):
        from game.db.market_alerts import MarketAlerts
        from game.game_error import GameError
        for i in range(5):
            MarketAlerts.create(self.tx, discord_id=123, direction='above', threshold_usd=Decimal(f'{50000 + i * 100}'))
        with self.assertRaises(GameError) as ctx:
            MarketAlerts.create(self.tx, discord_id=123, direction='above', threshold_usd=Decimal('60000'))
        self.assertEqual(str(ctx.exception), 'market_alert_limit_reached')

    def test_create_alert_duplicate(self):
        from game.db.market_alerts import MarketAlerts
        from game.game_error import GameError
        MarketAlerts.create(self.tx, discord_id=123, direction='above', threshold_usd=Decimal('50000'))
        with self.assertRaises(GameError) as ctx:
            MarketAlerts.create(self.tx, discord_id=123, direction='above', threshold_usd=Decimal('50000'))
        self.assertEqual(str(ctx.exception), 'market_alert_duplicate')

    def test_create_alert_threshold_too_high(self):
        from game.db.market_alerts import MarketAlerts
        from game.game_error import GameError
        with self.assertRaises(GameError) as ctx:
            MarketAlerts.create(
                self.tx,
                discord_id=123,
                direction='above',
                threshold_usd=Decimal('500000'),
                current_price=Decimal('40000'),  # 10x = 400000
            )
        self.assertEqual(str(ctx.exception), 'market_alert_threshold_too_high')

    def test_create_alert_invalid_direction(self):
        from game.db.market_alerts import MarketAlerts
        from game.game_error import GameError
        with self.assertRaises(GameError):
            MarketAlerts.create(self.tx, discord_id=123, direction='sideways', threshold_usd=Decimal('50000'))

    def test_delete_alert(self):
        from game.db.market_alerts import MarketAlerts
        alert = MarketAlerts.create(self.tx, discord_id=123, direction='above', threshold_usd=Decimal('50000'))
        self.assertTrue(MarketAlerts.delete(self.tx, discord_id=123, alert_id=alert['id']))
        self.assertEqual(len(MarketAlerts.list_for(self.tx, 123)), 0)
        # Supprimer une alerte inexistante
        self.assertFalse(MarketAlerts.delete(self.tx, discord_id=123, alert_id=999))

    def test_toggle_alert(self):
        from game.db.market_alerts import MarketAlerts
        alert = MarketAlerts.create(self.tx, discord_id=123, direction='above', threshold_usd=Decimal('50000'))
        toggled = MarketAlerts.toggle(self.tx, discord_id=123, alert_id=alert['id'])
        self.assertEqual(toggled['enabled'], 0)
        toggled2 = MarketAlerts.toggle(self.tx, discord_id=123, alert_id=alert['id'])
        self.assertEqual(toggled2['enabled'], 1)
        self.assertEqual(toggled2['armed'], 1)

    def test_trigger_above_and_rearm(self):
        from datetime import timedelta
        from game.db.market_alerts import MarketAlerts
        MarketAlerts.create(self.tx, discord_id=123, direction='above', threshold_usd=Decimal('50000'), cooldown_minutes=60)

        # Prix à 45000 -> pas de déclenchement
        trig = MarketAlerts.evaluate_and_trigger(self.tx, Decimal('45000'), self.tx.now)
        self.assertEqual(len(trig), 0)

        # Prix monte à 51000 -> déclenchement !
        trig = MarketAlerts.evaluate_and_trigger(self.tx, Decimal('51000'), self.tx.now)
        self.assertEqual(len(trig), 1)
        self.assertEqual(trig[0]['discord_id'], 123)

        # Cycle suivant à 52000 -> l'alerte est désarmée, pas de re-déclenchement intempestif
        trig2 = MarketAlerts.evaluate_and_trigger(self.tx, Decimal('52000'), self.tx.now + timedelta(minutes=15))
        self.assertEqual(len(trig2), 0)

        # Le cours redescend à 48000 -> réarmement automatique !
        MarketAlerts.evaluate_and_trigger(self.tx, Decimal('48000'), self.tx.now + timedelta(minutes=30))
        alerts = MarketAlerts.list_for(self.tx, 123)
        self.assertEqual(alerts[0]['armed'], 1)

        # Le cours remonte à 53000 -> nouveau déclenchement !
        trig3 = MarketAlerts.evaluate_and_trigger(self.tx, Decimal('53000'), self.tx.now + timedelta(minutes=45))
        self.assertEqual(len(trig3), 1)

    def test_trigger_below(self):
        from game.db.market_alerts import MarketAlerts
        MarketAlerts.create(self.tx, discord_id=123, direction='below', threshold_usd=Decimal('30000'))

        # Prix à 35000 -> pas de déclenchement
        trig = MarketAlerts.evaluate_and_trigger(self.tx, Decimal('35000'), self.tx.now)
        self.assertEqual(len(trig), 0)

        # Prix chute à 29000 -> déclenchement !
        trig = MarketAlerts.evaluate_and_trigger(self.tx, Decimal('29000'), self.tx.now)
        self.assertEqual(len(trig), 1)
        self.assertEqual(trig[0]['threshold_usd'], Decimal('30000'))


class FakeAutoSellTx:
    """Mock de transaction MySQL dédié aux tests des ventes automatiques."""

    def __init__(self, now=None):
        self.now = now or datetime(2026, 1, 1, 12, 0)
        self.rules = []
        self.runs = []
        self.next_rule_id = 1
        self.next_run_id = 1
        self.player = {
            'discord_id': 123,
            'dollars': Decimal('1000.00'),
            'rootium': Decimal('100.00000'),
        }

    def acquire_lock(self, name):
        pass

    def execute(self, sql, args=()):
        sql_u = sql.upper().strip()
        if "INSERT INTO RTM_AUTO_SELL_RULES" in sql_u:
            rid = self.next_rule_id
            self.next_rule_id += 1
            self.rules.append({
                'id': rid,
                'discord_id': int(args[0]),
                'direction': str(args[1]),
                'threshold_usd': Decimal(str(args[2])),
                'mode': str(args[3]),
                'amount_rtm': Decimal(str(args[4])) if args[4] is not None else None,
                'percent': Decimal(str(args[5])) if args[5] is not None else None,
                'max_rtm_per_run': Decimal(str(args[6])) if args[6] is not None else None,
                'cooldown_minutes': int(args[7]),
                'repeat_mode': str(args[8]),
                'enabled': 1,
                'last_run_at': None,
                'created_at': self.now,
            })
            return rid
        elif "INSERT INTO RTM_AUTO_SELL_RUNS" in sql_u:
            run_id = self.next_run_id
            self.next_run_id += 1
            self.runs.append({
                'id': run_id,
                'rule_id': int(args[0]),
                'discord_id': int(args[1]),
                'market_ts': args[2],
                'rate_usd': Decimal(str(args[3])),
                'rtm_amount': Decimal(str(args[4])),
                'usd_amount': Decimal(str(args[5])),
                'created_at': args[6],
            })
            return run_id
        elif "DELETE FROM RTM_AUTO_SELL_RULES" in sql_u:
            rid, uid = int(args[0]), int(args[1])
            self.rules = [r for r in self.rules if not (r['id'] == rid and r['discord_id'] == uid)]
            return 1
        elif "UPDATE RTM_AUTO_SELL_RULES SET ENABLED =" in sql_u:
            new_en, rid = int(args[0]), int(args[1])
            for r in self.rules:
                if r['id'] == rid:
                    r['enabled'] = new_en
            return 1
        elif "UPDATE RTM_AUTO_SELL_RULES SET LAST_RUN_AT = %S, ENABLED = 0" in sql_u:
            last_run, rid = args[0], int(args[1])
            for r in self.rules:
                if r['id'] == rid:
                    r['last_run_at'] = last_run
                    r['enabled'] = 0
            return 1
        elif "UPDATE RTM_AUTO_SELL_RULES SET LAST_RUN_AT = %S WHERE ID = %S" in sql_u:
            last_run, rid = args[0], int(args[1])
            for r in self.rules:
                if r['id'] == rid:
                    r['last_run_at'] = last_run
            return 1
        elif "UPDATE PLAYERS SET" in sql_u:
            cols = [part.split('=')[0].strip().lower() for part in sql_u.split('SET')[1].split('WHERE')[0].split(',')]
            for i, col in enumerate(cols):
                if col in self.player:
                    self.player[col] = args[i]
            return 1
        return 0

    def one(self, sql, args=()):
        sql_u = sql.upper().strip()
        if "COUNT(*)" in sql_u:
            uid = int(args[0])
            return {'cnt': sum(1 for r in self.rules if r['discord_id'] == uid)}
        elif "SELECT ID FROM RTM_AUTO_SELL_RULES WHERE DISCORD_ID = %S AND DIRECTION = %S AND THRESHOLD_USD = %S AND MODE = %S" in sql_u:
            uid, direction, thresh, mode = int(args[0]), str(args[1]), Decimal(str(args[2])), str(args[3])
            for r in self.rules:
                if (r['discord_id'] == uid and r['direction'] == direction
                        and r['threshold_usd'] == thresh and r['mode'] == mode):
                    return {'id': r['id']}
            return None
        elif "FROM RTM_AUTO_SELL_RULES WHERE ID = %S AND DISCORD_ID = %S" in sql_u:
            rid, uid = int(args[0]), int(args[1])
            for r in self.rules:
                if r['id'] == rid and r['discord_id'] == uid:
                    return dict(r)
            return None
        elif "FROM RTM_AUTO_SELL_RULES WHERE ID = %S" in sql_u:
            rid = int(args[0])
            for r in self.rules:
                if r['id'] == rid:
                    return dict(r)
            return None
        elif "SELECT ID FROM RTM_AUTO_SELL_RUNS WHERE RULE_ID = %S AND MARKET_TS = %S" in sql_u:
            rid, mts = int(args[0]), args[1]
            for run in self.runs:
                if run['rule_id'] == rid and run['market_ts'] == mts:
                    return {'id': run['id']}
            return None
        elif "FROM PLAYERS WHERE DISCORD_ID" in sql_u:
            uid = int(args[0])
            if uid == self.player['discord_id']:
                return dict(self.player)
            return None
        elif "SELECT * FROM RTM_MARKET_STATE" in sql_u:
            return {
                'id': 1,
                'price_usd': Decimal('50000.00000000'),
                'observed_at': self.now,
                'status': 'live',
                'source': 'binance',
            }
        return None

    def all(self, sql, args=()):
        sql_u = sql.upper().strip()
        if "WHERE DISCORD_ID = %S" in sql_u:
            uid = int(args[0])
            return [dict(r) for r in self.rules if r['discord_id'] == uid]
        elif "WHERE ENABLED = 1" in sql_u:
            price = Decimal(str(args[0]))
            res = []
            for r in self.rules:
                if r['enabled'] == 1:
                    if r['direction'] == 'above' and price >= r['threshold_usd']:
                        res.append(dict(r))
                    elif r['direction'] == 'below' and price <= r['threshold_usd']:
                        res.append(dict(r))
            return res
        return []


class AutoSellTests(unittest.TestCase):
    """Tests unitaires de la vente automatique de Rootium (règles et exécution)."""

    def setUp(self):
        self.tx = FakeAutoSellTx(now=datetime(2026, 1, 1, 12, 0))
        from game.math_config import MathConfig
        MathConfig.clear_cache()

    def test_create_rule_fixed_valid(self):
        from game.db.auto_sell import AutoSellDB
        rule = AutoSellDB.create(
            self.tx,
            discord_id=123,
            direction='above',
            threshold_usd=Decimal('50000'),
            mode='fixed',
            amount_rtm=Decimal('10.5'),
            repeat_mode='once',
            current_price=Decimal('40000'),
        )
        self.assertEqual(rule['id'], 1)
        self.assertEqual(rule['direction'], 'above')
        self.assertEqual(rule['threshold_usd'], Decimal('50000'))
        self.assertEqual(rule['mode'], 'fixed')
        self.assertEqual(rule['amount_rtm'], Decimal('10.5'))
        self.assertEqual(rule['repeat_mode'], 'once')
        self.assertEqual(rule['enabled'], 1)

    def test_create_rule_percent_valid(self):
        from game.db.auto_sell import AutoSellDB
        rule = AutoSellDB.create(
            self.tx,
            discord_id=123,
            direction='above',
            threshold_usd=Decimal('50000'),
            mode='percent',
            percent=Decimal('50'),
            repeat_mode='repeat',
            cooldown_minutes=30,
        )
        self.assertEqual(rule['mode'], 'percent')
        self.assertEqual(rule['percent'], Decimal('50.00'))
        self.assertEqual(rule['repeat_mode'], 'repeat')
        self.assertEqual(rule['cooldown_minutes'], 30)

    def test_create_rule_limit_reached(self):
        from game.db.auto_sell import AutoSellDB
        from game.game_error import GameError
        for i in range(3):
            AutoSellDB.create(
                self.tx, discord_id=123, direction='above',
                threshold_usd=Decimal(f'{50000 + i * 100}'),
                mode='fixed', amount_rtm=Decimal('1'),
            )
        with self.assertRaises(GameError) as ctx:
            AutoSellDB.create(
                self.tx, discord_id=123, direction='above',
                threshold_usd=Decimal('60000'),
                mode='fixed', amount_rtm=Decimal('1'),
            )
        self.assertEqual(str(ctx.exception), 'market_auto_sell_limit_reached')

    def test_create_rule_duplicate(self):
        from game.db.auto_sell import AutoSellDB
        from game.game_error import GameError
        AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='fixed', amount_rtm=Decimal('1'),
        )
        with self.assertRaises(GameError) as ctx:
            AutoSellDB.create(
                self.tx, discord_id=123, direction='above',
                threshold_usd=Decimal('50000'), mode='fixed', amount_rtm=Decimal('2'),
            )
        self.assertEqual(str(ctx.exception), 'market_auto_sell_duplicate')

    def test_create_rule_threshold_too_high(self):
        from game.db.auto_sell import AutoSellDB
        from game.game_error import GameError
        with self.assertRaises(GameError) as ctx:
            AutoSellDB.create(
                self.tx, discord_id=123, direction='above',
                threshold_usd=Decimal('500000'), mode='fixed', amount_rtm=Decimal('1'),
                current_price=Decimal('40000'),
            )
        self.assertEqual(str(ctx.exception), 'market_auto_sell_threshold_too_high')

    def test_delete_rule(self):
        from game.db.auto_sell import AutoSellDB
        rule = AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='fixed', amount_rtm=Decimal('1'),
        )
        self.assertTrue(AutoSellDB.delete(self.tx, discord_id=123, rule_id=rule['id']))
        self.assertEqual(len(AutoSellDB.list_for(self.tx, 123)), 0)

    def test_toggle_rule(self):
        from game.db.auto_sell import AutoSellDB
        rule = AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='fixed', amount_rtm=Decimal('1'),
        )
        toggled = AutoSellDB.toggle(self.tx, discord_id=123, rule_id=rule['id'])
        self.assertEqual(toggled['enabled'], 0)
        toggled2 = AutoSellDB.toggle(self.tx, discord_id=123, rule_id=rule['id'])
        self.assertEqual(toggled2['enabled'], 1)

    def test_get_due_rules_cooldown_filter(self):
        from datetime import timedelta
        from game.db.auto_sell import AutoSellDB
        AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='fixed', amount_rtm=Decimal('1'),
            repeat_mode='repeat', cooldown_minutes=60,
        )
        # Règle jamais exécutée -> due
        due = AutoSellDB.get_due_rules(self.tx, Decimal('51000'), self.tx.now)
        self.assertEqual(len(due), 1)

        # Règle exécutée il y a 30 minutes -> cooldown non expiré -> non due
        self.tx.rules[0]['last_run_at'] = self.tx.now - timedelta(minutes=30)
        due2 = AutoSellDB.get_due_rules(self.tx, Decimal('51000'), self.tx.now)
        self.assertEqual(len(due2), 0)

        # Règle exécutée il y a 65 minutes -> cooldown expiré -> due
        self.tx.rules[0]['last_run_at'] = self.tx.now - timedelta(minutes=65)
        due3 = AutoSellDB.get_due_rules(self.tx, Decimal('51000'), self.tx.now)
        self.assertEqual(len(due3), 1)

    def test_execute_rule_fixed_success(self):
        from game.db.auto_sell import AutoSellDB
        rule = AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='fixed', amount_rtm=Decimal('20'),
            repeat_mode='once',
        )
        market_ts = datetime(2026, 1, 1, 12, 0)
        res = AutoSellDB.execute_rule(
            self.tx, rule, Decimal('50000'), market_ts, self.tx.now,
        )
        self.assertIsNotNone(res)
        self.assertEqual(res['rtm_amount'], Decimal('20.00000'))
        self.assertEqual(res['rate'], Decimal('50000'))
        # Vérification débit/crédit
        self.assertEqual(res['new_rootium'], Decimal('80.00000'))
        # 20 RTM * 50,000 USD = 1,000,000 gross - 10,000 fee (1%) = 990,000 net USD
        self.assertEqual(res['new_dollars'], Decimal('1000.00') + Decimal('990000.00'))
        # Règle 'once' désactivée
        self.assertEqual(self.tx.rules[0]['enabled'], 0)
        # Run enregistré
        self.assertEqual(len(self.tx.runs), 1)

    def test_execute_rule_partial_balance(self):
        from game.db.auto_sell import AutoSellDB
        # Joueur a 100 RTM, demande 150 RTM -> vend la totalité (100 RTM)
        rule = AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='fixed', amount_rtm=Decimal('150'),
            repeat_mode='once',
        )
        res = AutoSellDB.execute_rule(
            self.tx, rule, Decimal('50000'), datetime(2026, 1, 1, 12, 0), self.tx.now,
        )
        self.assertIsNotNone(res)
        self.assertEqual(res['rtm_amount'], Decimal('100.00000'))
        self.assertEqual(res['new_rootium'], Decimal('0.00000'))

    def test_execute_rule_percent_success(self):
        from game.db.auto_sell import AutoSellDB
        # Joueur a 100 RTM, demande 25% -> vend 25 RTM
        rule = AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='percent', percent=Decimal('25'),
            repeat_mode='repeat',
        )
        res = AutoSellDB.execute_rule(
            self.tx, rule, Decimal('50000'), datetime(2026, 1, 1, 12, 0), self.tx.now,
        )
        self.assertIsNotNone(res)
        self.assertEqual(res['rtm_amount'], Decimal('25.00000'))
        self.assertEqual(res['new_rootium'], Decimal('75.00000'))
        # Règle 'repeat' reste active
        self.assertEqual(self.tx.rules[0]['enabled'], 1)

    def test_execute_rule_max_cap(self):
        from game.db.auto_sell import AutoSellDB
        # Joueur a 100 RTM, demande 50% (50 RTM), plafonné à 15 RTM -> vend 15 RTM
        rule = AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='percent', percent=Decimal('50'),
            max_rtm_per_run=Decimal('15'),
            repeat_mode='once',
        )
        res = AutoSellDB.execute_rule(
            self.tx, rule, Decimal('50000'), datetime(2026, 1, 1, 12, 0), self.tx.now,
        )
        self.assertIsNotNone(res)
        self.assertEqual(res['rtm_amount'], Decimal('15.00000'))
        self.assertEqual(res['new_rootium'], Decimal('85.00000'))

    def test_execute_rule_zero_balance_skipped(self):
        from game.db.auto_sell import AutoSellDB
        self.tx.player['rootium'] = Decimal('0.00000')
        rule = AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='fixed', amount_rtm=Decimal('10'),
        )
        res = AutoSellDB.execute_rule(
            self.tx, rule, Decimal('50000'), datetime(2026, 1, 1, 12, 0), self.tx.now,
        )
        self.assertIsNone(res)
        self.assertEqual(len(self.tx.runs), 0)

    def test_execute_rule_idempotence_same_cycle(self):
        from game.db.auto_sell import AutoSellDB
        rule = AutoSellDB.create(
            self.tx, discord_id=123, direction='above',
            threshold_usd=Decimal('50000'), mode='fixed', amount_rtm=Decimal('10'),
            repeat_mode='repeat',
        )
        mts = datetime(2026, 1, 1, 12, 0)
        # Première exécution
        res1 = AutoSellDB.execute_rule(self.tx, rule, Decimal('50000'), mts, self.tx.now)
        self.assertIsNotNone(res1)
        # Seconde exécution pour le MÊME cycle -> bloqué par idempotence !
        res2 = AutoSellDB.execute_rule(self.tx, rule, Decimal('50000'), mts, self.tx.now)
        self.assertIsNone(res2)
        self.assertEqual(len(self.tx.runs), 1)


class MarketTradeAndBlockchainTests(unittest.TestCase):
    """Tests pour l'achat et la vente de RTM sur le marché, les frais de 1% et les logs."""

    def _setup_tx(self, rate_str='40000'):
        from datetime import timezone
        tx = MagicMock()
        tx.one.return_value = {
            'price_usd': Decimal(rate_str),
            'status': 'live',
            'observed_at': datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            'market_ts': datetime(2026, 1, 1, 12, 0),
        }
        return tx

    def test_buy_quote_and_confirm_with_one_percent_fee(self):
        from unittest.mock import patch
        from game.db.players import Player
        tx = self._setup_tx('50000')
        player = {'rootium': Decimal('0.00000'), 'dollars': Decimal('1000.00')}
        with patch('game.db.players.PlayerData.get', return_value=player), \
             patch('game.db.players.UpdatePlayer.set') as upd:
            # 1. Devis d'achat de 0.01 RTM
            # 0.01 * 50,000 = 500.00 USD brut.
            # Frais 1% = 5.00 USD. Total débité = 505.00 USD.
            quote = Player.convert(tx, 123, action='buy', amount='0.01', confirm=False)
            self.assertTrue(quote['quote'])
            self.assertEqual(quote['action'], 'buy')
            self.assertEqual(quote['rtm_amount'], Decimal('0.01000'))
            self.assertEqual(quote['gross_usd'], Decimal('500.00'))
            self.assertEqual(quote['fee_usd'], Decimal('5.00'))
            self.assertEqual(quote['fee_pct'], Decimal('1.0'))
            self.assertEqual(quote['usd_amount'], Decimal('505.00'))
            self.assertEqual(quote['new_dollars'], Decimal('495.00'))
            self.assertEqual(quote['new_rootium'], Decimal('0.01000'))
            upd.assert_not_called()

            # 2. Confirmation de l'achat
            bought = Player.convert(tx, 123, action='buy', amount='0.01', confirm=True, rate='50000')
            self.assertTrue(bought['converted'])
            self.assertEqual(bought['usd_amount'], Decimal('505.00'))
            upd.assert_called_once_with(tx, 123, dollars=Decimal('495.00'), rootium=Decimal('0.01000'))

    def test_buy_all_calculates_max_rtm_with_fees(self):
        from game.db.players import Player
        tx = self._setup_tx('50000')
        # Solde de 1010.00 USD -> Avec frais 1%, montant brut max = 1000.00 USD, frais = 10.00 USD.
        # À 50,000 USD/RTM, 1000 USD / 50000 = 0.02000 RTM.
        player = {'rootium': Decimal('0.00000'), 'dollars': Decimal('1010.00')}
        with patch('game.db.players.PlayerData.get', return_value=player), \
             patch('game.db.players.UpdatePlayer.set') as upd:
            bought = Player.convert(tx, 123, action='buy', amount='all', all=True, confirm=True)
            self.assertTrue(bought['converted'])
            self.assertEqual(bought['rtm_amount'], Decimal('0.02000'))
            self.assertEqual(bought['gross_usd'], Decimal('1000.00'))
            self.assertEqual(bought['fee_usd'], Decimal('10.00'))
            self.assertEqual(bought['usd_amount'], Decimal('1010.00'))
            self.assertEqual(bought['new_dollars'], Decimal('0.00'))
            self.assertEqual(bought['new_rootium'], Decimal('0.02000'))
            upd.assert_called_once()

    def test_buy_insufficient_funds_raises_error(self):
        from game.db.players import Player
        from game.game_error import GameError
        tx = self._setup_tx('50000')
        player = {'rootium': Decimal('0.00000'), 'dollars': Decimal('100.00')}
        with patch('game.db.players.PlayerData.get', return_value=player):
            with self.assertRaises(GameError) as cm:
                Player.convert(tx, 123, action='buy', amount='1', confirm=True)
            self.assertEqual(cm.exception.key, 'insufficient_funds_usd')

    def test_economy_stats_increments_for_buy_and_sell(self):
        from game.db.economy_stats import EconomyStatsDB
        # 1. Achat
        buy_res = {
            'converted': True,
            'action': 'buy',
            'rtm_amount': Decimal('0.05'),
            'usd_amount': Decimal('2525.00'),
            'fee_usd': Decimal('25.00'),
        }
        inc_buy = EconomyStatsDB.build_increments('convert', 123, buy_res)
        self.assertIn(123, inc_buy)
        self.assertEqual(inc_buy[123]['market_buys'], 1)
        self.assertEqual(inc_buy[123]['market_bought_rtm'], Decimal('0.05'))
        self.assertEqual(inc_buy[123]['market_spent_usd'], Decimal('2525.00'))
        self.assertEqual(inc_buy[123]['market_fees_usd'], Decimal('25.00'))

        # 2. Vente
        sell_res = {
            'converted': True,
            'action': 'sell',
            'rtm_amount': Decimal('0.05'),
            'usd_amount': Decimal('2475.00'),
            'fee_usd': Decimal('25.00'),
        }
        inc_sell = EconomyStatsDB.build_increments('convert', 123, sell_res)
        self.assertIn(123, inc_sell)
        self.assertEqual(inc_sell[123]['conversions'], 1)
        self.assertEqual(inc_sell[123]['converted_rtm'], Decimal('0.05'))
        self.assertEqual(inc_sell[123]['converted_usd'], Decimal('2475.00'))
        self.assertEqual(inc_sell[123]['market_fees_usd'], Decimal('25.00'))

    def test_blockchain_log_formats_fee(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from utils.logger import Logger
        bot = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        bot.get_channel.return_value = mock_channel
        with patch.object(Logger, 'channel_id', return_value=123456789):
            logger_inst = Logger(bot)
            asyncio.run(logger_inst.log_blockchain_transaction(
                from_id=123,
                to_address="0xROOTIUM_DEX",
                rtm_amount=Decimal('0.05000'),
                tx_type="SELL TOKEN",
                usd_amount=Decimal('2500.00'),
                fee_usd=Decimal('25.00'),
                from_name="Alice",
            ))
            mock_channel.send.assert_awaited_once()
            call_content = mock_channel.send.call_args[0][0]
            self.assertIn("TYPE   SELL TOKEN", call_content)
            self.assertIn("RTM    0.05000", call_content)
            self.assertIn("USD    2,500", call_content)
            self.assertIn("FEE    25", call_content)


if __name__ == '__main__':
    unittest.main()


