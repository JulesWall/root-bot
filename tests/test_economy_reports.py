"""
Tests du module de suivi économique (economy_stats).

Couvre les cas du §10 de SUIVI_ECONOMIE_DISCORD.md :
- Incréments par action (claim, network, mini-jeux, buy, upgrade, compile, scan, convert, trade)
- Rétention (returning_players)
- Joueurs distincts sur plusieurs heures
- Rollback / retry (atomicité)
- Périodes (bucket)
- Envoi / reprise de bilan
- Bilan à zéro
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from game.db.economy_stats import EconomyStatsDB, _PERIODS


# ---------------------------------------------------------------------------
# MockTransaction minimaliste orienté economy_stats
# ---------------------------------------------------------------------------

class MockTx:
    """
    Simule une Transaction MySQL en mémoire pour les tests economy_stats.
    Stocke economy_hourly en dict{(bucket, player_id): row}.
    Stocke economy_reports en dict{period_hours: row}.
    """

    def __init__(self, now=None):
        self.now = now or datetime(2026, 9, 21, 14, 30, 0)
        self.economy_hourly: dict[tuple, dict] = {}
        self.economy_reports: dict[int, dict] = {}
        self.tables_exist = True  # simule information_schema
        self.acquired_locks = []
        self._queries = []

    def acquire_lock(self, name: str, timeout: int = 10) -> None:
        if name not in self.acquired_locks:
            self.acquired_locks.append(name)

    def one(self, sql: str, args=()):
        self._queries.append((sql, args))
        q = ' '.join(sql.split()).upper()

        # information_schema check
        if 'INFORMATION_SCHEMA' in q and 'COUNT(*)' in q:
            table_name = args[0] if args else ''
            if self.tables_exist:
                return {'cnt': 1}
            return {'cnt': 0}

        # economy_reports SELECT * ... WHERE period_hours
        if 'FROM ECONOMY_REPORTS WHERE PERIOD_HOURS' in q:
            period = args[0]
            row = self.economy_reports.get(period)
            return dict(row) if row else None

        # economy_hourly EXISTS (returning check)
        if 'FROM ECONOMY_HOURLY' in q and 'WHERE PLAYER_ID' in q and 'BUCKET_START <' in q:
            player_id = args[0]
            bucket_limit = args[1]
            for (b, pid), row in self.economy_hourly.items():
                if pid == player_id and b < bucket_limit:
                    return {'1': 1}
            return None

        # economy_hourly aggregate
        if 'FROM ECONOMY_HOURLY' in q and 'COUNT(DISTINCT' in q:
            start, end = args
            matching = {
                (b, pid): row
                for (b, pid), row in self.economy_hourly.items()
                if start <= b < end
            }
            if not matching:
                return None
            result = {'active_players': len({pid for (_, pid) in matching})}
            # Agréger toutes les colonnes numériques
            all_cols = set()
            for row in matching.values():
                all_cols.update(row.keys())
            for col in all_cols:
                if col in ('bucket_start', 'player_id'):
                    continue
                total = sum(
                    (row.get(col) or 0) for row in matching.values()
                )
                result[col] = total
            return result

        return None

    def all(self, sql: str, args=()):
        self._queries.append((sql, args))
        q = ' '.join(sql.split()).upper()

        if 'FROM ECONOMY_REPORTS ORDER BY PERIOD_HOURS' in q:
            return sorted(self.economy_reports.values(), key=lambda r: r['period_hours'])

        return []

    def execute(self, sql: str, args=()):
        self._queries.append((sql, args))
        q = ' '.join(sql.split()).upper()

        # INSERT INTO economy_reports
        if 'INSERT INTO ECONOMY_REPORTS' in q:
            period_hours = args[0]
            self.economy_reports[period_hours] = {
                'period_hours': period_hours,
                'tracking_start': args[1],
                'next_start': args[2],
                'pending_end': None,
                'pending_payload': None,
                'pending_channel_id': None,
                'last_message_id': None,
                'last_sent_at': None,
            }
            return 1

        # INSERT INTO economy_hourly
        if 'INSERT INTO ECONOMY_HOURLY' in q and 'ON DUPLICATE KEY UPDATE' in q:
            self._apply_hourly_upsert(sql, args)
            return 1

        if 'INSERT IGNORE INTO ECONOMY_HOURLY' in q:
            self._apply_hourly_ignore(sql, args)
            return 1

        # UPDATE economy_reports SET next_start (ack)
        if 'UPDATE ECONOMY_REPORTS' in q and 'SET NEXT_START' in q:
            period = args[-1]
            row = self.economy_reports.get(period)
            if row:
                row['next_start'] = args[0]
                row['pending_end'] = None
                row['pending_payload'] = None
                row['pending_channel_id'] = None
                row['last_message_id'] = args[1]
            return 1

        # UPDATE economy_reports SET pending_end (prepare)
        if 'UPDATE ECONOMY_REPORTS' in q and 'SET PENDING_END' in q:
            period = args[-1]
            row = self.economy_reports.get(period)
            if row:
                row['pending_end'] = args[0]
                row['pending_payload'] = args[1]
                row['pending_channel_id'] = args[2]
            return 1

        return 0

    def _parse_insert_cols_vals(self, sql: str, args) -> tuple[list[str], list]:
        """Extrait les colonnes et valeurs d'un INSERT INTO economy_hourly."""
        import re
        m = re.search(r'INSERT\s+(?:IGNORE\s+)?INTO\s+economy_hourly\s*\(([^)]+)\)', sql, re.IGNORECASE)
        if not m:
            return [], []
        cols = [c.strip() for c in m.group(1).split(',')]
        n_insert = cols.count('bucket_start') and len(cols)
        vals = list(args[:len(cols)])
        return cols, vals

    def _apply_hourly_upsert(self, sql: str, args):
        import re
        # Colonnes insert
        m_cols = re.search(r'INSERT INTO economy_hourly\s*\(([^)]+)\)', sql, re.IGNORECASE)
        if not m_cols:
            return
        cols = [c.strip() for c in m_cols.group(1).split(',')]
        n = len(cols)
        insert_vals = list(args[:n])
        update_vals = list(args[n:])

        bucket = insert_vals[cols.index('bucket_start')]
        pid = insert_vals[cols.index('player_id')]
        key = (bucket, pid)

        if key not in self.economy_hourly:
            row = {'bucket_start': bucket, 'player_id': pid}
            for col, val in zip(cols, insert_vals):
                if col not in ('bucket_start', 'player_id'):
                    row[col] = val
            self.economy_hourly[key] = row
        else:
            row = self.economy_hourly[key]
            # Extraire les colonnes de update
            m_upd = re.findall(r'(\w+)\s*=\s*\w+\s*\+\s*%s', sql, re.IGNORECASE)
            for col, val in zip(m_upd, update_vals):
                col_lower = col.lower()
                current = row.get(col_lower, 0) or 0
                row[col_lower] = (Decimal(str(current)) + Decimal(str(val or 0)))

    def _apply_hourly_ignore(self, sql: str, args):
        import re
        m_cols = re.search(r'INSERT IGNORE INTO economy_hourly\s*\(([^)]+)\)', sql, re.IGNORECASE)
        if not m_cols:
            return
        cols = [c.strip() for c in m_cols.group(1).split(',')]
        insert_vals = list(args[:len(cols)])
        bucket = insert_vals[cols.index('bucket_start')]
        pid = insert_vals[cols.index('player_id')]
        key = (bucket, pid)
        if key not in self.economy_hourly:
            row = {'bucket_start': bucket, 'player_id': pid}
            for col, val in zip(cols, insert_vals):
                if col not in ('bucket_start', 'player_id'):
                    row[col] = val
            self.economy_hourly[key] = row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _d(val) -> Decimal:
    return Decimal(str(val))

BUCKET_14H = datetime(2026, 9, 21, 14, 0, 0)
BUCKET_15H = datetime(2026, 9, 21, 15, 0, 0)
BUCKET_16H = datetime(2026, 9, 21, 16, 0, 0)


# ---------------------------------------------------------------------------
# Tests build_increments (aucun SQL)
# ---------------------------------------------------------------------------

class TestBuildIncrements(unittest.TestCase):

    def test_claim_normal(self):
        result = {'claimed': True, 'amount': _d('0.00250'), 'ram_was_full': False}
        inc = EconomyStatsDB.build_increments('claim', 123, result)
        self.assertEqual(inc, {123: {'claims': 1, 'mining_rtm': _d('0.00250')}})

    def test_claim_full(self):
        result = {'claimed': True, 'amount': _d('0.00100'), 'ram_was_full': True}
        inc = EconomyStatsDB.build_increments('claim', 123, result)
        self.assertIn('full_claims', inc[123])
        self.assertEqual(inc[123]['full_claims'], 1)
        self.assertEqual(inc[123]['claims'], 1)

    def test_two_claims_aggregation(self):
        """Deux claims successifs : 2 claims, somme des RTM, 50% full."""
        tx = MockTx()
        r1 = {'claimed': True, 'amount': _d('0.00250'), 'ram_was_full': True}
        r2 = {'claimed': True, 'amount': _d('0.00100'), 'ram_was_full': False}
        inc1 = EconomyStatsDB.build_increments('claim', 123, r1)
        inc2 = EconomyStatsDB.build_increments('claim', 123, r2)
        EconomyStatsDB.add(tx, BUCKET_14H, inc1)
        EconomyStatsDB.add(tx, BUCKET_14H, inc2)
        row = tx.economy_hourly.get((BUCKET_14H, 123))
        self.assertEqual(int(row['claims']), 2)
        self.assertEqual(_d(row['full_claims']), _d(1))
        self.assertEqual(_d(row['mining_rtm']), _d('0.00350'))

    def test_claim_refused(self):
        result = {'claimed': False, 'reason': 'empty', 'amount': _d('0')}
        inc = EconomyStatsDB.build_increments('claim', 123, result)
        self.assertEqual(inc, {})

    def test_network_new(self):
        result = {'is_new': True, 'dollars': _d('5000')}
        inc = EconomyStatsDB.build_increments('network', 456, result)
        self.assertEqual(inc, {456: {'new_players': 1, 'grant_usd': _d('5000')}})

    def test_network_existing(self):
        result = {'is_new': False, 'dollars': _d('5000')}
        inc = EconomyStatsDB.build_increments('network', 456, result)
        self.assertEqual(inc, {})

    def test_event_hash_win(self):
        result = {'status': 'won', 'reward': _d('1200'), 'winner': 789}
        inc = EconomyStatsDB.build_increments('hash', 789, result)
        self.assertEqual(inc, {789: {'event_hash_usd': _d('1200')}})

    def test_event_packet_win(self):
        result = {'status': 'won', 'reward': _d('800'), 'winner': 789}
        inc = EconomyStatsDB.build_increments('packet', 789, result)
        self.assertIn('event_packet_usd', inc[789])
        self.assertNotIn('event_hash_usd', inc[789])

    def test_event_loss(self):
        result = {'status': 'lost', 'reward': _d('0'), 'winner': None}
        inc = EconomyStatsDB.build_increments('hash', 123, result)
        self.assertEqual(inc, {})

    def test_buy_mining_t2(self):
        result = {'bought': True, 'kind': 'mining', 'tier': 2, 'usd_price': _d('200'), 'rtm_price': _d('0')}
        inc = EconomyStatsDB.build_increments('buy', 123, result)
        self.assertIn('miners_t2', inc[123])
        self.assertEqual(inc[123]['miners_t2'], 1)
        self.assertEqual(inc[123]['miners_usd'], _d('200'))

    def test_buy_attack(self):
        result = {'bought': True, 'kind': 'attack', 'tier': 1, 'usd_price': _d('0'), 'rtm_price': _d('0.01')}
        inc = EconomyStatsDB.build_increments('buy', 123, result)
        self.assertEqual(inc[123]['attack_bought'], 1)

    def test_buy_quote_not_counted(self):
        result = {'quote': True, 'buy_quote': True, 'bought': False}
        inc = EconomyStatsDB.build_increments('buy', 123, result)
        self.assertEqual(inc, {})

    def test_upgrade_started(self):
        result = {'upgrade_started': True, 'usd_price': _d('500')}
        inc = EconomyStatsDB.build_increments('upgrade', 123, result)
        self.assertEqual(inc[123]['upgrades_started'], 1)
        self.assertEqual(inc[123]['upgrades_usd'], _d('500'))

    def test_compile_started(self):
        result = {'compile_started': True, 'rtm_paid': _d('0.02')}
        inc = EconomyStatsDB.build_increments('compile', 123, result)
        self.assertEqual(inc[123]['compile_rtm'], _d('0.02'))

    def test_scan_started_with_boost(self):
        result = {'scan_started': True, 'rtm_total': _d('0.015')}
        inc = EconomyStatsDB.build_increments('scan', 123, result)
        self.assertEqual(inc[123]['scan_rtm'], _d('0.015'))

    def test_convert(self):
        result = {'converted': True, 'rtm_amount': _d('0.05'), 'usd_amount': _d('2178.35')}
        inc = EconomyStatsDB.build_increments('convert', 123, result)
        self.assertEqual(inc[123]['conversions'], 1)
        self.assertEqual(inc[123]['converted_rtm'], _d('0.05'))
        self.assertEqual(inc[123]['converted_usd'], _d('2178.35'))

    def test_trade(self):
        result = {'trade_completed': True, 'initiator': 123, 'target': 456}
        inc = EconomyStatsDB.build_increments('trade', 123, result)
        self.assertEqual(inc[123]['trades'], 1)
        self.assertIn(456, inc)
        self.assertEqual(inc[456], {})

    def test_unknown_method(self):
        inc = EconomyStatsDB.build_increments('top', 123, {'ranking': []})
        self.assertEqual(inc, {})


# ---------------------------------------------------------------------------
# Tests add() — SQL atomique et returning_players
# ---------------------------------------------------------------------------

class TestAdd(unittest.TestCase):

    def test_first_time_player_not_returning(self):
        tx = MockTx()
        inc = {123: {'claims': 1, 'mining_rtm': _d('0.00250')}}
        EconomyStatsDB.add(tx, BUCKET_14H, inc)
        row = tx.economy_hourly.get((BUCKET_14H, 123))
        self.assertIsNotNone(row)
        # Pas de returning_players car aucune ligne antérieure
        self.assertEqual(int(row.get('returning_players', 0)), 0)

    def test_returning_player_flag(self):
        tx = MockTx()
        # Ligne dans une heure précédente
        tx.economy_hourly[(BUCKET_14H, 123)] = {'bucket_start': BUCKET_14H, 'player_id': 123}
        # Nouvelle heure → doit être marqué returning
        inc = {123: {'claims': 1}}
        EconomyStatsDB.add(tx, BUCKET_15H, inc)
        row = tx.economy_hourly.get((BUCKET_15H, 123))
        self.assertIsNotNone(row)
        self.assertEqual(int(row.get('returning_players', 0)), 1)

    def test_returning_not_updated_on_duplicate(self):
        """Si la ligne existe déjà dans le même bucket, returning_players ne change pas."""
        tx = MockTx()
        # Ligne antérieure → marque returning
        tx.economy_hourly[(BUCKET_14H, 123)] = {'bucket_start': BUCKET_14H, 'player_id': 123}
        inc = {123: {'claims': 1}}
        EconomyStatsDB.add(tx, BUCKET_15H, inc)
        # Deuxième add dans le même bucket → ON DUPLICATE KEY UPDATE, returning ne doit pas changer
        inc2 = {123: {'claims': 1}}
        EconomyStatsDB.add(tx, BUCKET_15H, inc2)
        row = tx.economy_hourly.get((BUCKET_15H, 123))
        # returning_players reste à 1, pas 2
        self.assertEqual(int(row.get('returning_players', 0)), 1)

    def test_trade_target_empty_dict_creates_row(self):
        tx = MockTx()
        inc = {123: {'trades': 1}, 456: {}}
        EconomyStatsDB.add(tx, BUCKET_14H, inc)
        self.assertIn((BUCKET_14H, 456), tx.economy_hourly)

    def test_ordered_by_player_id(self):
        """Les joueurs sont traités par ID croissant (anti-deadlock)."""
        tx = MockTx()
        processed_order = []
        original_add = EconomyStatsDB.add.__func__ if hasattr(EconomyStatsDB.add, '__func__') else None

        inc = {999: {'trades': 1}, 111: {}}
        EconomyStatsDB.add(tx, BUCKET_14H, inc)
        keys = list(tx.economy_hourly.keys())
        pids = [k[1] for k in keys]
        # 111 doit être créé avant 999
        self.assertLess(pids.index(111), pids.index(999))


# ---------------------------------------------------------------------------
# Tests aggregate()
# ---------------------------------------------------------------------------

class TestAggregate(unittest.TestCase):

    def test_empty_period(self):
        tx = MockTx()
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        self.assertEqual(result['active_players'], 0)
        self.assertEqual(result['claims'], 0)

    def test_distinct_players(self):
        """Un même joueur sur 3 heures compte une fois dans active_players."""
        tx = MockTx()
        for bucket in (BUCKET_14H, BUCKET_15H, BUCKET_16H):
            tx.economy_hourly[(bucket, 123)] = {
                'bucket_start': bucket, 'player_id': 123,
                'claims': 1, 'mining_rtm': _d('0.001'),
            }
        # Active player sur 3 heures
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_16H + timedelta(hours=1))
        self.assertEqual(result['active_players'], 1)

    def test_returning_players_sum(self):
        """returning_players est une somme directe des flags, pas COUNT DISTINCT."""
        tx = MockTx()
        tx.economy_hourly[(BUCKET_14H, 123)] = {
            'bucket_start': BUCKET_14H, 'player_id': 123,
            'returning_players': 0, 'claims': 1,
        }
        tx.economy_hourly[(BUCKET_15H, 123)] = {
            'bucket_start': BUCKET_15H, 'player_id': 123,
            'returning_players': 1, 'claims': 2,
        }
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_16H)
        self.assertEqual(result['active_players'], 1)
        self.assertEqual(int(result.get('returning_players', 0)), 1)

    def test_period_boundaries(self):
        """Action à 14h59 → bucket 14h ; action à 15h → bucket 15h."""
        tx = MockTx()
        tx.economy_hourly[(BUCKET_14H, 123)] = {
            'bucket_start': BUCKET_14H, 'player_id': 123, 'claims': 5,
        }
        tx.economy_hourly[(BUCKET_15H, 123)] = {
            'bucket_start': BUCKET_15H, 'player_id': 123, 'claims': 3,
        }
        # Période [14h, 15h) → inclut 14h, exclut 15h
        result_14 = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        self.assertEqual(int(result_14.get('claims', 0)), 5)
        # Période [15h, 16h)
        result_15 = EconomyStatsDB.aggregate(tx, BUCKET_15H, BUCKET_16H)
        self.assertEqual(int(result_15.get('claims', 0)), 3)

    def test_mini_games_separate_columns(self):
        """hash et packet ont des colonnes distinctes."""
        tx = MockTx()
        tx.economy_hourly[(BUCKET_14H, 123)] = {
            'bucket_start': BUCKET_14H, 'player_id': 123,
            'event_hash_usd': _d('1200'), 'event_packet_usd': _d('800'),
        }
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        self.assertEqual(_d(result.get('event_hash_usd', 0)), _d('1200'))
        self.assertEqual(_d(result.get('event_packet_usd', 0)), _d('800'))

    def test_retention_rate(self):
        """Deux joueurs dont un seul de retour → 50%."""
        tx = MockTx()
        tx.economy_hourly[(BUCKET_14H, 100)] = {
            'bucket_start': BUCKET_14H, 'player_id': 100,
            'returning_players': 0, 'claims': 1,
        }
        tx.economy_hourly[(BUCKET_14H, 200)] = {
            'bucket_start': BUCKET_14H, 'player_id': 200,
            'returning_players': 1, 'claims': 1,
        }
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        active = result['active_players']
        returning = int(result.get('returning_players', 0))
        self.assertEqual(active, 2)
        self.assertEqual(returning, 1)
        rate = returning / active
        self.assertAlmostEqual(rate, 0.5)


# ---------------------------------------------------------------------------
# Tests initialize()
# ---------------------------------------------------------------------------

class TestInitialize(unittest.TestCase):

    def test_first_init_creates_three_rows(self):
        tx = MockTx(now=datetime(2026, 9, 21, 10, 17, 0))
        tracking_start = EconomyStatsDB.initialize(tx)
        # Doit ancrer à 11h00
        self.assertEqual(tracking_start, datetime(2026, 9, 21, 11, 0, 0))
        self.assertEqual(set(tx.economy_reports.keys()), {1, 24, 72})

    def test_resume_existing(self):
        tx = MockTx()
        # Pré-peupler les 3 lignes
        ts = datetime(2026, 9, 21, 11, 0, 0)
        for p in (1, 24, 72):
            tx.economy_reports[p] = {
                'period_hours': p, 'tracking_start': ts, 'next_start': ts,
                'pending_end': None, 'pending_payload': None, 'pending_channel_id': None,
                'last_message_id': None, 'last_sent_at': None,
            }
        result = EconomyStatsDB.initialize(tx)
        self.assertEqual(result, ts)

    def test_missing_table_raises(self):
        tx = MockTx()
        tx.tables_exist = False
        with self.assertRaises(RuntimeError):
            EconomyStatsDB.initialize(tx)


# ---------------------------------------------------------------------------
# Tests prepare_report() et ack_report()
# ---------------------------------------------------------------------------

class TestReportLifecycle(unittest.TestCase):

    def _setup_economy_reports(self, tx: MockTx, tracking_start: datetime):
        for p in _PERIODS:
            tx.economy_reports[p] = {
                'period_hours': p,
                'tracking_start': tracking_start,
                'next_start': tracking_start,
                'pending_end': None,
                'pending_payload': None,
                'pending_channel_id': None,
                'last_message_id': None,
                'last_sent_at': None,
            }

    def test_nothing_due_yet(self):
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        # now = 11h30, pas encore 12h02 pour le bilan 1h
        tx = MockTx(now=datetime(2026, 9, 21, 11, 30, 0))
        self._setup_economy_reports(tx, tracking_start)
        result = EconomyStatsDB.prepare_report(tx, 1, 12345)
        self.assertIsNone(result)

    def test_report_due_after_period_plus_2min(self):
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        # now = 12h03, le bilan 1h (11h→12h) est dû
        tx = MockTx(now=datetime(2026, 9, 21, 12, 3, 0))
        self._setup_economy_reports(tx, tracking_start)
        result = EconomyStatsDB.prepare_report(tx, 1, 99999)
        self.assertIsNotNone(result)
        self.assertEqual(result['period_hours'], 1)

    def test_pending_payload_returned_as_is(self):
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        tx = MockTx(now=datetime(2026, 9, 21, 12, 3, 0))
        self._setup_economy_reports(tx, tracking_start)
        import json
        payload = {'active_players': 5, 'period_start': '2026-09-21T11:00:00', 'period_end': '2026-09-21T12:00:00'}
        tx.economy_reports[1]['pending_payload'] = json.dumps(payload)
        tx.economy_reports[1]['pending_end'] = datetime(2026, 9, 21, 12, 0, 0)
        tx.economy_reports[1]['pending_channel_id'] = 99999
        result = EconomyStatsDB.prepare_report(tx, 1, 88888)
        # Doit retourner le payload existant, pas en préparer un nouveau
        self.assertEqual(result['data']['active_players'], 5)
        self.assertEqual(result['pending_channel_id'], 99999)  # salon original conservé

    def test_ack_advances_calendar(self):
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        period_end = datetime(2026, 9, 21, 12, 0, 0)
        tx = MockTx(now=datetime(2026, 9, 21, 12, 3, 0))
        self._setup_economy_reports(tx, tracking_start)
        import json
        tx.economy_reports[1]['pending_end'] = period_end
        tx.economy_reports[1]['pending_payload'] = json.dumps({'period_start': tracking_start.isoformat(), 'period_end': period_end.isoformat()})

        EconomyStatsDB.ack_report(tx, 1, tracking_start, period_end, message_id=777)
        row = tx.economy_reports[1]
        self.assertEqual(row['next_start'], period_end)
        self.assertIsNone(row['pending_end'])
        self.assertEqual(row['last_message_id'], 777)

    def test_ack_idempotent(self):
        """Répéter l'ack ne fait rien (next_start ne change pas à nouveau)."""
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        period_end = datetime(2026, 9, 21, 12, 0, 0)
        tx = MockTx()
        self._setup_economy_reports(tx, tracking_start)
        tx.economy_reports[1]['pending_end'] = period_end
        import json
        tx.economy_reports[1]['pending_payload'] = json.dumps({})

        EconomyStatsDB.ack_report(tx, 1, tracking_start, period_end, message_id=111)
        # next_start est maintenant period_end, pending_end est None

        # Deuxième ack avec les mêmes paramètres → ignoré car next_start != expected_start
        EconomyStatsDB.ack_report(tx, 1, tracking_start, period_end, message_id=222)
        # Le message_id ne doit pas avoir changé
        self.assertEqual(tx.economy_reports[1]['last_message_id'], 111)

    def test_zero_activity_report_no_crash(self):
        """Un bilan à zéro doit être généré sans plantage."""
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        tx = MockTx(now=datetime(2026, 9, 21, 12, 3, 0))
        self._setup_economy_reports(tx, tracking_start)
        # Aucune donnée dans economy_hourly
        result = EconomyStatsDB.prepare_report(tx, 1, 12345)
        self.assertIsNotNone(result)
        data = result['data']
        self.assertEqual(int(data.get('active_players', 0)), 0)


# ---------------------------------------------------------------------------
# Tests du patch players.py (ram_was_full)
# ---------------------------------------------------------------------------

class TestRamWasFull(unittest.TestCase):

    def test_ram_was_full_in_claim_result(self):
        """Player.claim doit inclure ram_was_full dans son résultat en cas de succès."""
        from game.db.players import Player
        import inspect
        source = inspect.getsource(Player.claim)
        self.assertIn('ram_was_full', source,
                      "Player.claim doit inclure 'ram_was_full' dans le résultat")

    def test_ram_was_full_before_update(self):
        """ram_was_full doit être capturé AVANT le UpdatePlayer.set du chemin principal."""
        from game.db.players import Player
        import inspect
        source = inspect.getsource(Player.claim)
        # Chercher la section du chemin principal : après 'new_rootium'
        idx_new_rootium = source.find('new_rootium')
        self.assertGreater(idx_new_rootium, 0, "new_rootium doit exister dans claim")
        # Dans la section après new_rootium, ram_was_full doit précéder le UpdatePlayer.set final
        section = source[idx_new_rootium:]
        idx_ram = section.find('ram_was_full')
        idx_update = section.find('UpdatePlayer.set')
        self.assertGreater(idx_update, idx_ram,
                           "ram_was_full doit être calculé avant UpdatePlayer.set dans le chemin principal")


if __name__ == '__main__':
    unittest.main(verbosity=2)
