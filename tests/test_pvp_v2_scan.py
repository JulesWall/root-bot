"""
Tests unitaires pour le scan complet du réseau PvP V2 (Étape 5 simplifiée).

Conforme à design/PVP_V2_DECISIONS.md (Décisions 11, 14, 15) et aux simplifications de l'Étape 5 :
- Éligibilité : infrastructure >= 1 pour l'attaquant, cible > 0, cible >= attaquant sauf si représailles actives (< 72h).
- Devis déterministe (0.005 RTM, 90s).
- Lancement atomique avec prélèvement RTM et enregistrement dans la table `hack` (type='scan').
- Photographie directe (snapshot) capturée à t=résolution :
  - Infrastructure, modules par tier, hashrate H/s, RTM/h estimé, ratio RAM, logiciels & correctifs installés, jobs de dev actifs.
  - Aucune fuite de solde en cash/RTM, ni de secret_id.
- Résolution et livraison directe par worker persistant (pas de stockage de rapport figé ni de table dédiée).
- Rendu visuel soigné du rapport Root OS turquoise avec jauges ASCII et métadonnées complètes.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from game.game_error import GameError
from game.math_config import MathConfig
from game.pvp_v2_scan import PvpV2ScanService, _get_infra_level
from commands.game.scan import format_scan_report
from tests.test_pvp_v2_db import MockPvpV2Transaction


class MockScanTransaction(MockPvpV2Transaction):
    """Simulateur transactionnel complet pour le scan réseau PvP V2."""

    def __init__(self, now=None):
        super().__init__(now=now)
        self.players = {}
        self.hacks = []
        self.consequences = []
        self.locks_acquired = []

    def acquire_lock(self, name: str):
        self.locks_acquired.append(name)

    def add_player(self, discord_id: int, **fields):
        base = {
            'discord_id': int(discord_id),
            'dollars': Decimal('1000.00'),
            'rootium': Decimal('1.00000'),
            'firewall_level': 1,
            'infrastructure_level': 1,
            'mining_t1': 2,
            'mining_t2': 0,
            'mining_t3': 0,
            'mining_t4': 0,
            'mining_t5': 0,
            'attack_t1': 1,
            'attack_t2': 0,
            'attack_t3': 0,
            'attack_t4': 0,
            'attack_t5': 0,
            'bay_defense_t1': 1,
            'bay_defense_t2': 0,
            'bay_defense_t3': 0,
            'bay_defense_t4': 0,
            'bay_defense_t5': 0,
            'last_claim_at': self.now,
            'buffer': Decimal('0.00000'),
            'lang': 'fr',
        }
        base.update(fields)
        self.players[int(discord_id)] = base
        return base

    def add_consequence(self, victim_id: int, attacker_id: int, expires_at: datetime):
        self.consequences.append({
            'id': self._next_id(),
            'victim_id': int(victim_id),
            'attacker_id': int(attacker_id),
            'expires_at': expires_at,
        })

    def one(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        if "FROM PLAYERS WHERE DISCORD_ID" in q:
            pid = int(params[0])
            row = self.players.get(pid)
            if row and 'infrastructure_level' not in row:
                row['infrastructure_level'] = int(row.get('firewall_level') or 0)
            return row

        if "FROM HACK WHERE" in q and "TYPE =" in q:
            pid = int(params[0])
            htype = str(params[1])
            cutoff = params[2] if len(params) > 2 else None
            for h in self.hacks:
                if h['discord_id'] == pid and h['type'] == htype:
                    if cutoff is None or h['expires_at'] > cutoff:
                        return h
            return None

        if "FROM CONSEQUENCE WHERE" in q:
            vid = int(params[0])
            aid = int(params[1])
            cutoff = params[2]
            for c in self.consequences:
                if c['victim_id'] == vid and c['attacker_id'] == aid and c['expires_at'] > cutoff:
                    return c
            return None

        return super().one(query, params)

    def all(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        if "FROM HACK WHERE TYPE = 'SCAN' AND EXPIRES_AT <=" in q:
            cutoff = params[0]
            matched = [h for h in self.hacks if h['type'] == 'scan' and h['expires_at'] <= cutoff]
            matched.sort(key=lambda x: x['expires_at'])
            return matched

        return super().all(query, params)

    def execute(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        if "INSERT INTO HACK" in q:
            pid = int(params[0])
            tid = int(params[1]) if len(params) > 1 and "TARGET_ID" in q else 0
            htype = 'scan' if "'SCAN'" in q else ('compile' if "'COMPILE'" in q else str(params[2]))
            exp = params[-1]
            hid = self._next_id()
            self.hacks.append({
                'id': hid,
                'discord_id': pid,
                'target_id': tid,
                'type': htype,
                'expires_at': exp,
                'created_at': self.now,
            })
            return 1

        if "DELETE FROM HACK WHERE ID =" in q:
            hid = int(params[0])
            before = len(self.hacks)
            self.hacks = [h for h in self.hacks if h['id'] != hid]
            return before - len(self.hacks)

        if "UPDATE PLAYERS SET" in q:
            for pid, p in self.players.items():
                if f"WHERE DISCORD_ID = {pid}" in q or (params and params[-1] == pid):
                    if "ROOTIUM=%S" in q or "ROOTIUM = %S" in q or "ROOTIUM = ROOTIUM -" in q:
                        if len(params) >= 2:
                            p['rootium'] = Decimal(str(params[0]))
                        else:
                            p['rootium'] = p['rootium'] - Decimal('0.005')
                    return 1

        return super().execute(query, params)


class TestPvpV2ScanEligibility(unittest.TestCase):
    """Vérifie les règles d'éligibilité pour lancer un scan réseau."""

    def setUp(self):
        self.tx = MockScanTransaction()
        self.attacker = self.tx.add_player(1001, firewall_level=1, infrastructure_level=1)
        self.victim = self.tx.add_player(2002, firewall_level=2, infrastructure_level=2)

    def test_attacker_level_zero_forbidden(self):
        self.attacker['firewall_level'] = 0
        self.attacker['infrastructure_level'] = 0
        with self.assertRaises(GameError) as cm:
            PvpV2ScanService.check_scan_eligibility(self.tx, 1001, 2002)
        self.assertEqual(cm.exception.key, 'scan_self_invulnerable')

    def test_victim_level_zero_forbidden(self):
        self.victim['firewall_level'] = 0
        self.victim['infrastructure_level'] = 0
        with self.assertRaises(GameError) as cm:
            PvpV2ScanService.check_scan_eligibility(self.tx, 1001, 2002)
        self.assertEqual(cm.exception.key, 'scan_target_invulnerable')

    def test_cannot_target_self(self):
        with self.assertRaises(GameError) as cm:
            PvpV2ScanService.check_scan_eligibility(self.tx, 1001, 1001)
        self.assertEqual(cm.exception.key, 'self_target')

    def test_attacker_cannot_target_lower_level_without_retaliation(self):
        self.attacker['firewall_level'] = 3
        self.attacker['infrastructure_level'] = 3
        self.victim['firewall_level'] = 1
        self.victim['infrastructure_level'] = 1
        with self.assertRaises(GameError) as cm:
            PvpV2ScanService.check_scan_eligibility(self.tx, 1001, 2002)
        self.assertEqual(cm.exception.key, 'scan_target_protected')

    def test_retaliation_allows_targeting_lower_level(self):
        self.attacker['firewall_level'] = 3
        self.attacker['infrastructure_level'] = 3
        self.victim['firewall_level'] = 1
        self.victim['infrastructure_level'] = 1
        self.tx.add_consequence(
            victim_id=1001,
            attacker_id=2002,
            expires_at=self.tx.now + timedelta(hours=24),
        )
        _, _, is_retaliation = PvpV2ScanService.check_scan_eligibility(self.tx, 1001, 2002)
        self.assertTrue(is_retaliation)

    def test_attacker_level_4_recognized_from_firewall_level(self):
        self.attacker.pop('infrastructure_level', None)
        self.attacker['firewall_level'] = 4
        self.victim['firewall_level'] = 4
        self.victim['infrastructure_level'] = 4
        _, _, is_retaliation = PvpV2ScanService.check_scan_eligibility(self.tx, 1001, 2002)
        self.assertFalse(is_retaliation)


class TestPvpV2ScanQuote(unittest.TestCase):
    """Vérifie le calcul et le contenu du devis de scan réseau."""

    def setUp(self):
        self.tx = MockScanTransaction()
        self.tx.add_player(1001, firewall_level=2, infrastructure_level=2)
        self.tx.add_player(2002, firewall_level=2, infrastructure_level=2)

    def test_quote_deterministic_values(self):
        quote = PvpV2ScanService.calculate_scan_quote(self.tx, 1001, 2002)
        self.assertEqual(quote['cost_rtm'], Decimal('0.005'))
        self.assertEqual(quote['duration_seconds'], 90)
        self.assertEqual(quote['victim_id'], 2002)
        self.assertEqual(quote['victim_infrastructure'], 2)
        self.assertFalse(quote['is_retaliation'])


class TestPvpV2ScanExecution(unittest.TestCase):
    """Vérifie le démarrage atomique d'un scan réseau."""

    def setUp(self):
        self.tx = MockScanTransaction()
        self.tx.add_player(1001, firewall_level=1, infrastructure_level=1, rootium=Decimal('1.00000'))
        self.tx.add_player(2002, firewall_level=2, infrastructure_level=2)

    def test_start_scan_insufficient_rtm(self):
        self.tx.players[1001]['rootium'] = Decimal('0.00100')
        with self.assertRaises(GameError) as cm:
            PvpV2ScanService.start_scan(self.tx, 1001, 2002)
        self.assertEqual(cm.exception.key, 'insufficient_rootium')

    def test_start_scan_already_in_progress(self):
        self.tx.hacks.append({
            'id': 1,
            'discord_id': 1001,
            'target_id': 2002,
            'type': 'scan',
            'expires_at': self.tx.now + timedelta(seconds=60),
            'created_at': self.tx.now,
        })
        with self.assertRaises(GameError) as cm:
            PvpV2ScanService.start_scan(self.tx, 1001, 2002)
        self.assertEqual(cm.exception.key, 'scan_in_progress')

    def test_start_scan_success(self):
        res = PvpV2ScanService.start_scan(self.tx, 1001, 2002)
        self.assertEqual(res['victim_id'], 2002)
        self.assertEqual(res['cost_rtm'], Decimal('0.005'))
        self.assertEqual(self.tx.players[1001]['rootium'], Decimal('0.99500'))
        self.assertEqual(len(self.tx.hacks), 1)
        hack_job = self.tx.hacks[0]
        self.assertEqual(hack_job['discord_id'], 1001)
        self.assertEqual(hack_job['target_id'], 2002)
        self.assertEqual(hack_job['type'], 'scan')
        self.assertEqual(hack_job['expires_at'], self.tx.now + timedelta(seconds=90))


class TestPvpV2ScanSnapshotAndResolve(unittest.TestCase):
    """Vérifie la capture du snapshot direct et la résolution du scan sans persistance de rapport."""

    def setUp(self):
        self.tx = MockScanTransaction()
        self.tx.add_player(
            1001,
            firewall_level=2,
            infrastructure_level=2,
        )
        self.victim = self.tx.add_player(
            2002,
            firewall_level=3,
            infrastructure_level=3,
            mining_t1=5,
            attack_t2=2,
            bay_defense_t1=3,
            buffer=Decimal('0.15000'),
        )

    def test_build_scan_snapshot_contents(self):
        snapshot = PvpV2ScanService.build_scan_snapshot(self.tx, self.victim)
        self.assertEqual(snapshot['victim_id'], 2002)
        self.assertEqual(snapshot['infrastructure_level'], 3)
        self.assertIn('modules_by_tier', snapshot)
        self.assertIn('total_hashrate_hs', snapshot)
        self.assertIn('estimated_production_rtm_h', snapshot)
        self.assertIn('memory_used_ratio', snapshot)
        self.assertIn('memory_buffer_rtm', snapshot)
        self.assertIn('memory_capacity_rtm', snapshot)
        self.assertIn('installed_software', snapshot)
        self.assertIn('installed_patches', snapshot)
        self.assertIn('active_dev_jobs_count', snapshot)
        # Vérification qu'aucune donnée sensible ne fuite
        self.assertNotIn('dollars', snapshot)
        self.assertNotIn('rootium', snapshot)
        self.assertNotIn('secret_id', snapshot)

    def test_resolve_scan_delivers_directly_and_deletes_hack_job(self):
        self.tx.hacks.append({
            'id': 77,
            'discord_id': 1001,
            'target_id': 2002,
            'type': 'scan',
            'expires_at': self.tx.now - timedelta(seconds=1),
            'created_at': self.tx.now - timedelta(seconds=91),
        })
        scan_row = self.tx.hacks[0]
        res = PvpV2ScanService.resolve_scan(self.tx, scan_row)

        self.assertEqual(res['status'], 'delivered')
        self.assertEqual(res['scan_id'], 77)
        self.assertEqual(res['attacker_id'], 1001)
        self.assertEqual(res['victim_id'], 2002)
        self.assertIn('report_data', res)
        self.assertEqual(res['report_data']['victim_id'], 2002)
        # Le job a bien été supprimé de la table hack
        self.assertEqual(len(self.tx.hacks), 0)

    def test_resolve_scan_victim_deleted(self):
        self.tx.hacks.append({
            'id': 88,
            'discord_id': 1001,
            'target_id': 9999,
            'type': 'scan',
            'expires_at': self.tx.now - timedelta(seconds=1),
            'created_at': self.tx.now - timedelta(seconds=91),
        })
        scan_row = self.tx.hacks[0]
        res = PvpV2ScanService.resolve_scan(self.tx, scan_row)
        self.assertEqual(res['status'], 'victim_deleted')
        self.assertEqual(len(self.tx.hacks), 0)

    def test_deliver_expired_scans(self):
        self.tx.hacks.append({
            'id': 10,
            'discord_id': 1001,
            'target_id': 2002,
            'type': 'scan',
            'expires_at': self.tx.now - timedelta(seconds=5),
            'created_at': self.tx.now - timedelta(seconds=95),
        })
        delivered = PvpV2ScanService.deliver_expired_scans(self.tx)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0]['status'], 'delivered')
        self.assertEqual(len(self.tx.hacks), 0)


class TestPvpV2ScanReportFormatting(unittest.TestCase):
    """Vérifie le formatage visuel du rapport de scan réseau."""

    def test_format_scan_report_fr(self):
        report_row = {
            'victim_id': 2002,
            'created_at': datetime(2026, 9, 30, 14, 0, 0, tzinfo=timezone.utc),
            'report_data': {
                'victim_id': 2002,
                'infrastructure_level': 3,
                'modules_by_tier': {
                    '1': {'mining': 2, 'attack': 0, 'bay_defense': 1},
                    '2': {'mining': 0, 'attack': 1, 'bay_defense': 0},
                },
                'total_hashrate_hs': 50000,
                'estimated_production_rtm_h': '0.01250',
                'memory_used_ratio': 0.45,
                'memory_buffer_rtm': '0.04500',
                'memory_capacity_rtm': '0.10000',
                'installed_software': [
                    {'family': 'hostile_miner', 'tier': 1, 'fingerprint': 'K7M2'},
                ],
                'installed_patches': [
                    {'family': 'ransomware', 'fingerprint': 'P3RX'},
                ],
                'active_dev_jobs_count': 1,
            },
        }

        text_out = format_scan_report('fr', report_row)
        self.assertIn('<@2002>', text_out)
        self.assertIn('Infrastructure & Sécurité', text_out)
        self.assertIn('Niveau `3`', text_out)
        self.assertIn('▰▰▰▱▱', text_out)
        self.assertIn('50,000 H/s', text_out)
        self.assertIn('`0.04500` / `0.10000` RTM', text_out)
        self.assertIn('Baie Tier 1', text_out)
        self.assertIn('Hostile Miner', text_out)
        self.assertIn('K7M2', text_out)
        self.assertIn('Ransomware', text_out)
        self.assertIn('P3RX', text_out)
        self.assertIn('Recherche active', text_out)

    def test_format_scan_report_en(self):
        report_row = {
            'victim_id': 2002,
            'created_at': datetime(2026, 9, 30, 14, 0, 0, tzinfo=timezone.utc),
            'report_data': {
                'victim_id': 2002,
                'infrastructure_level': 4,
                'modules_by_tier': {},
                'total_hashrate_hs': 0,
                'estimated_production_rtm_h': '0.00000',
                'memory_used_ratio': 0.0,
                'memory_buffer_rtm': '0.00000',
                'memory_capacity_rtm': '0.20000',
                'installed_software': [],
                'installed_patches': [],
                'active_dev_jobs_count': 0,
            },
        }

        text_out = format_scan_report('en', report_row)
        self.assertIn('Network Reconnaissance Report', text_out)
        self.assertIn('Infrastructure & Security', text_out)
        self.assertIn('Level `4`', text_out)
        self.assertIn('No hardware modules installed', text_out)
        self.assertIn('No offensive or utility software compiled', text_out)
        self.assertIn('No active defensive patch deployed', text_out)


if __name__ == '__main__':
    unittest.main()
