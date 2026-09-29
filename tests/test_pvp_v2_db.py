"""
Tests unitaires pour les dépôts SQL PvP V2 (Étape 2).

Valide :
- Les insertions et lectures pour chaque table (recherche, logiciels, patches, jobs, opérations, effets, rapports, marché).
- Les contraintes d'intégrité et de filtrage (ex: resellable=0 pour copies volées, reserved pour les annonces).
- Les transitions d'état (installing -> active -> ended, active -> sold/cancelled/expired).
- Le test de concurrence logique : deux confirmations simultanées sur la même ressource ou canal.
"""

import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from game.db.pvp_v2_research import PvpV2ResearchDB
from game.db.pvp_v2_software import PvpV2SoftwareDB
from game.db.pvp_v2_patches import PvpV2PatchDB
from game.db.pvp_v2_dev_jobs import PvpV2DevJobsDB
from game.db.pvp_v2_operations import PvpV2OperationsDB, PvpV2ActiveEffectsDB
from game.db.pvp_v2_reports import PvpV2ScanReportsDB, PvpV2EspionageReportsDB
from game.db.pvp_v2_market import PvpV2MarketDB


class MockPvpV2Transaction:
    """Simulateur en mémoire pour tester les dépôts PvP V2 avec sémantique MySQL."""

    def __init__(self, now=None):
        self.now = now or datetime(2026, 9, 29, 14, 0, 0)
        self.seq = 1
        self.research_folders = []
        self.software_copies = []
        self.patches = []
        self.dev_jobs = []
        self.operations = []
        self.active_effects = []
        self.scan_reports = []
        self.espionage_reports = []
        self.market_listings = []

    def _next_id(self):
        nid = self.seq
        self.seq += 1
        return nid

    def execute(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        # --- Research Folders ---
        if "INSERT INTO PVP_V2_RESEARCH_FOLDERS" in q:
            # owner_id, channel, family, tier, fingerprint, created_at
            owner_id, channel, family, tier, fingerprint, created_at = params
            # Check unique (family, fingerprint)
            for f in self.research_folders:
                if f['family'] == family and f['fingerprint'] == fingerprint:
                    raise Exception(f"Duplicate entry '{family}-{fingerprint}' for key 'uq_folder_family_fp'")
            row_id = self._next_id()
            self.research_folders.append({
                'id': row_id,
                'owner_id': int(owner_id),
                'channel': str(channel),
                'family': str(family),
                'tier': int(tier),
                'fingerprint': str(fingerprint),
                'created_at': created_at,
            })
            return row_id

        if "DELETE FROM PVP_V2_RESEARCH_FOLDERS WHERE ID =" in q:
            fid, oid = params
            before = len(self.research_folders)
            self.research_folders = [f for f in self.research_folders if not (f['id'] == int(fid) and f['owner_id'] == int(oid))]
            return before - len(self.research_folders)

        # --- Software Copies ---
        if "INSERT INTO PVP_V2_SOFTWARE_COPIES" in q:
            owner_id, family, tier, fingerprint, origin, resellable, created_at = params
            row_id = self._next_id()
            self.software_copies.append({
                'id': row_id,
                'owner_id': int(owner_id),
                'family': str(family),
                'tier': int(tier),
                'fingerprint': str(fingerprint),
                'origin': str(origin),
                'resellable': int(resellable),
                'reserved': 0,
                'created_at': created_at,
            })
            return row_id

        if "UPDATE PVP_V2_SOFTWARE_COPIES SET RESERVED =" in q:
            res, cid = params
            count = 0
            for c in self.software_copies:
                if c['id'] == int(cid):
                    c['reserved'] = int(res)
                    count += 1
            return count

        if "UPDATE PVP_V2_SOFTWARE_COPIES SET OWNER_ID =" in q:
            new_oid, cid = params
            count = 0
            for c in self.software_copies:
                if c['id'] == int(cid):
                    c['owner_id'] = int(new_oid)
                    c['origin'] = 'purchased'
                    c['reserved'] = 0
                    count += 1
            return count

        if "DELETE FROM PVP_V2_SOFTWARE_COPIES WHERE ID =" in q:
            cid, oid = params
            before = len(self.software_copies)
            self.software_copies = [c for c in self.software_copies if not (c['id'] == int(cid) and c['owner_id'] == int(oid))]
            return before - len(self.software_copies)

        # --- Patches ---
        if "INSERT INTO PVP_V2_PATCHES" in q:
            owner_id, family, fingerprint, created_at = params
            row_id = self._next_id()
            self.patches.append({
                'id': row_id,
                'owner_id': int(owner_id),
                'family': str(family),
                'fingerprint': str(fingerprint),
                'installed': 0,
                'installed_at': None,
                'reserved': 0,
                'created_at': created_at,
            })
            return row_id

        if "UPDATE PVP_V2_PATCHES SET INSTALLED = 1" in q:
            now_val, pid, oid = params
            count = 0
            for p in self.patches:
                if p['id'] == int(pid) and p['owner_id'] == int(oid) and p['installed'] == 0:
                    p['installed'] = 1
                    p['installed_at'] = now_val
                    count += 1
            return count

        if "UPDATE PVP_V2_PATCHES SET RESERVED =" in q:
            res, pid = params
            count = 0
            for p in self.patches:
                if p['id'] == int(pid) and p['installed'] == 0:
                    p['reserved'] = int(res)
                    count += 1
            return count

        if "UPDATE PVP_V2_PATCHES SET OWNER_ID =" in q:
            new_oid, pid = params
            count = 0
            for p in self.patches:
                if p['id'] == int(pid) and p['installed'] == 0:
                    p['owner_id'] = int(new_oid)
                    p['reserved'] = 0
                    count += 1
            return count

        if "DELETE FROM PVP_V2_PATCHES WHERE ID =" in q:
            pid, oid = params
            before = len(self.patches)
            self.patches = [p for p in self.patches if not (p['id'] == int(pid) and p['owner_id'] == int(oid) and p['installed'] == 0)]
            return before - len(self.patches)

        # --- Dev Jobs ---
        if "INSERT INTO PVP_V2_DEV_JOBS" in q:
            player_id, channel, job_type, family, tier, rtm_paid, bits_per_s, started_at, resolves_at = params
            for j in self.dev_jobs:
                if j['player_id'] == int(player_id) and j['channel'] == str(channel):
                    raise Exception(f"Duplicate entry for unique key 'uq_job_player_channel'")
            row_id = self._next_id()
            self.dev_jobs.append({
                'id': row_id,
                'player_id': int(player_id),
                'channel': str(channel),
                'job_type': str(job_type),
                'family': str(family),
                'tier': int(tier),
                'fingerprint': None,
                'rtm_paid': Decimal(str(rtm_paid)),
                'bits_per_s': int(bits_per_s),
                'started_at': started_at,
                'resolves_at': resolves_at,
            })
            return row_id

        if "DELETE FROM PVP_V2_DEV_JOBS WHERE ID =" in q:
            jid = params[0]
            before = len(self.dev_jobs)
            self.dev_jobs = [j for j in self.dev_jobs if j['id'] != int(jid)]
            return before - len(self.dev_jobs)

        # --- Operations ---
        if "INSERT INTO PVP_V2_OPERATIONS" in q:
            attacker_id, victim_id, family, tier, fingerprint, software_copy_id, rtm_cost, started_at = params
            row_id = self._next_id()
            self.operations.append({
                'id': row_id,
                'attacker_id': int(attacker_id),
                'victim_id': int(victim_id),
                'family': str(family),
                'tier': int(tier),
                'fingerprint': str(fingerprint),
                'software_copy_id': int(software_copy_id),
                'status': 'installing',
                'rtm_cost': Decimal(str(rtm_cost)),
                'started_at': started_at,
                'installed_at': None,
                'ended_at': None,
                'end_reason': None,
            })
            return row_id

        if "UPDATE PVP_V2_OPERATIONS SET STATUS = 'ACTIVE'" in q:
            inst_at, op_id = params
            count = 0
            for op in self.operations:
                if op['id'] == int(op_id) and op['status'] == 'installing':
                    op['status'] = 'active'
                    op['installed_at'] = inst_at
                    count += 1
            return count

        if "UPDATE PVP_V2_OPERATIONS SET STATUS =" in q:
            st, ended_at, reason, op_id = params
            count = 0
            for op in self.operations:
                if op['id'] == int(op_id) and op['status'] in ('installing', 'active'):
                    op['status'] = str(st)
                    op['ended_at'] = ended_at
                    op['end_reason'] = reason
                    count += 1
            return count

        # --- Active Effects ---
        if "INSERT INTO PVP_V2_ACTIVE_EFFECTS" in q:
            op_id, attacker_id, victim_id, family, tier, fingerprint, effect_data, started_at = params
            row_id = self._next_id()
            self.active_effects.append({
                'id': row_id,
                'operation_id': int(op_id),
                'attacker_id': int(attacker_id),
                'victim_id': int(victim_id),
                'family': str(family),
                'tier': int(tier),
                'fingerprint': str(fingerprint),
                'effect_data': effect_data,
                'started_at': started_at,
                'ended_at': None,
                'end_reason': None,
            })
            return row_id

        if "UPDATE PVP_V2_ACTIVE_EFFECTS SET ENDED_AT = %S, END_REASON = %S WHERE ID =" in q:
            now_val, reason, eid = params
            count = 0
            for ef in self.active_effects:
                if ef['id'] == int(eid) and ef['ended_at'] is None:
                    ef['ended_at'] = now_val
                    ef['end_reason'] = str(reason)
                    count += 1
            return count

        if "UPDATE PVP_V2_ACTIVE_EFFECTS SET ENDED_AT = %S, END_REASON = %S WHERE VICTIM_ID =" in q:
            now_val, reason, vid, fp = params
            count = 0
            for ef in self.active_effects:
                if ef['victim_id'] == int(vid) and ef['fingerprint'] == str(fp) and ef['ended_at'] is None:
                    ef['ended_at'] = now_val
                    ef['end_reason'] = str(reason)
                    count += 1
            return count

        # --- Reports ---
        if "INSERT INTO PVP_V2_SCAN_REPORTS" in q:
            aid, vid, scat, expat, rdata = params
            row_id = self._next_id()
            self.scan_reports.append({
                'id': row_id,
                'attacker_id': int(aid),
                'victim_id': int(vid),
                'scanned_at': scat,
                'expires_at': expat,
                'report_data': rdata,
            })
            return row_id

        if "DELETE FROM PVP_V2_SCAN_REPORTS WHERE EXPIRES_AT <=" in q:
            now_val = params[0]
            before = len(self.scan_reports)
            self.scan_reports = [r for r in self.scan_reports if r['expires_at'] > now_val]
            return before - len(self.scan_reports)

        if "INSERT INTO PVP_V2_ESPIONAGE_REPORTS" in q:
            aid, vid, scat, expat, rdata = params
            row_id = self._next_id()
            self.espionage_reports.append({
                'id': row_id,
                'attacker_id': int(aid),
                'victim_id': int(vid),
                'scanned_at': scat,
                'expires_at': expat,
                'report_data': rdata,
            })
            return row_id

        if "DELETE FROM PVP_V2_ESPIONAGE_REPORTS WHERE EXPIRES_AT <=" in q:
            now_val = params[0]
            before = len(self.espionage_reports)
            self.espionage_reports = [r for r in self.espionage_reports if r['expires_at'] > now_val]
            return before - len(self.espionage_reports)

        # --- Market Listings ---
        if "INSERT INTO PVP_V2_MARKET_LISTINGS" in q:
            seller_id, item_type, item_id, price_usd, listed_at = params
            row_id = self._next_id()
            self.market_listings.append({
                'id': row_id,
                'seller_id': int(seller_id),
                'item_type': str(item_type),
                'item_id': int(item_id),
                'price_usd': Decimal(str(price_usd)),
                'status': 'active',
                'listed_at': listed_at,
                'expires_at': None,
                'sold_to': None,
                'sold_at': None,
            })
            return row_id

        if "UPDATE PVP_V2_MARKET_LISTINGS SET STATUS = 'SOLD'" in q:
            buyer_id, now_val, lid = params
            count = 0
            for l in self.market_listings:
                if l['id'] == int(lid) and l['status'] == 'active':
                    l['status'] = 'sold'
                    l['sold_to'] = int(buyer_id)
                    l['sold_at'] = now_val
                    count += 1
            return count

        if "UPDATE PVP_V2_MARKET_LISTINGS SET STATUS = 'CANCELLED'" in q:
            lid = params[0]
            count = 0
            for l in self.market_listings:
                if l['id'] == int(lid):
                    l['status'] = 'cancelled'
                    count += 1
            return count

        if "UPDATE PVP_V2_MARKET_LISTINGS SET STATUS = 'EXPIRED'" in q:
            lid = params[0]
            count = 0
            for l in self.market_listings:
                if l['id'] == int(lid) and l['status'] == 'active':
                    l['status'] = 'expired'
                    count += 1
            return count

        raise NotImplementedError(f"Execute mock not implemented for: {query}")

    def one(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        # Research folders
        if "SELECT * FROM PVP_V2_RESEARCH_FOLDERS WHERE OWNER_ID = %S AND FAMILY = %S AND TIER = %S" in q:
            oid, fam, t = params
            for f in self.research_folders:
                if f['owner_id'] == int(oid) and f['family'] == str(fam) and f['tier'] == int(t):
                    return dict(f)
            return None

        if "SELECT * FROM PVP_V2_RESEARCH_FOLDERS WHERE FAMILY = %S AND FINGERPRINT = %S" in q:
            fam, fp = params
            for f in self.research_folders:
                if f['family'] == str(fam) and f['fingerprint'] == str(fp):
                    return dict(f)
            return None

        if "SELECT 1 FROM PVP_V2_RESEARCH_FOLDERS WHERE FAMILY = %S AND FINGERPRINT = %S" in q:
            fam, fp = params
            for f in self.research_folders:
                if f['family'] == str(fam) and f['fingerprint'] == str(fp):
                    return {'1': 1}
            return None

        # Software copies
        if "SELECT * FROM PVP_V2_SOFTWARE_COPIES WHERE ID = %S" in q:
            cid = params[0]
            for c in self.software_copies:
                if c['id'] == int(cid):
                    return dict(c)
            return None

        # Patches
        if "SELECT * FROM PVP_V2_PATCHES WHERE ID = %S" in q:
            pid = params[0]
            for p in self.patches:
                if p['id'] == int(pid):
                    return dict(p)
            return None

        if "SELECT 1 FROM PVP_V2_PATCHES WHERE OWNER_ID = %S AND FINGERPRINT = %S AND INSTALLED = 1" in q:
            oid, fp = params
            for p in self.patches:
                if p['owner_id'] == int(oid) and p['fingerprint'] == str(fp) and p['installed'] == 1:
                    return {'1': 1}
            return None

        # Dev jobs
        if "SELECT * FROM PVP_V2_DEV_JOBS WHERE PLAYER_ID = %S AND CHANNEL = %S" in q:
            pid, ch = params
            for j in self.dev_jobs:
                if j['player_id'] == int(pid) and j['channel'] == str(ch):
                    return dict(j)
            return None

        # Operations
        if "SELECT * FROM PVP_V2_OPERATIONS WHERE ID = %S" in q:
            opid = params[0]
            for op in self.operations:
                if op['id'] == int(opid):
                    return dict(op)
            return None

        if "SELECT COUNT(*) AS CNT FROM PVP_V2_OPERATIONS WHERE ATTACKER_ID = %S AND STATUS IN ('INSTALLING', 'ACTIVE')" in q:
            aid = params[0]
            cnt = sum(1 for op in self.operations if op['attacker_id'] == int(aid) and op['status'] in ('installing', 'active'))
            return {'cnt': cnt}

        if "SELECT COUNT(*) AS CNT FROM PVP_V2_OPERATIONS WHERE ATTACKER_ID = %S AND FAMILY = %S AND STATUS IN ('INSTALLING', 'ACTIVE')" in q:
            aid, fam = params
            cnt = sum(1 for op in self.operations if op['attacker_id'] == int(aid) and op['family'] == str(fam) and op['status'] in ('installing', 'active'))
            return {'cnt': cnt}

        # Active Effects
        if "SELECT 1 FROM PVP_V2_ACTIVE_EFFECTS WHERE VICTIM_ID = %S AND FINGERPRINT = %S AND ENDED_AT IS NULL" in q:
            vid, fp = params
            for ef in self.active_effects:
                if ef['victim_id'] == int(vid) and ef['fingerprint'] == str(fp) and ef['ended_at'] is None:
                    return {'1': 1}
            return None

        # Scan Reports
        if "SELECT * FROM PVP_V2_SCAN_REPORTS WHERE ATTACKER_ID = %S AND VICTIM_ID = %S AND EXPIRES_AT > %S" in q:
            aid, vid, now_val = params
            matches = [r for r in self.scan_reports if r['attacker_id'] == int(aid) and r['victim_id'] == int(vid) and r['expires_at'] > now_val]
            if matches:
                matches.sort(key=lambda x: x['scanned_at'], reverse=True)
                return dict(matches[0])
            return None

        # Espionage Reports
        if "SELECT * FROM PVP_V2_ESPIONAGE_REPORTS WHERE ATTACKER_ID = %S AND VICTIM_ID = %S AND EXPIRES_AT > %S" in q:
            aid, vid, now_val = params
            matches = [r for r in self.espionage_reports if r['attacker_id'] == int(aid) and r['victim_id'] == int(vid) and r['expires_at'] > now_val]
            if matches:
                matches.sort(key=lambda x: x['scanned_at'], reverse=True)
                return dict(matches[0])
            return None

        # Market Listings
        if "SELECT COUNT(*) AS CNT FROM PVP_V2_MARKET_LISTINGS WHERE SELLER_ID = %S AND STATUS = 'ACTIVE'" in q:
            sid = params[0]
            cnt = sum(1 for l in self.market_listings if l['seller_id'] == int(sid) and l['status'] == 'active')
            return {'cnt': cnt}

        if "SELECT * FROM PVP_V2_MARKET_LISTINGS WHERE ID = %S AND SELLER_ID = %S AND STATUS = 'ACTIVE'" in q:
            lid, sid = params
            for l in self.market_listings:
                if l['id'] == int(lid) and l['seller_id'] == int(sid) and l['status'] == 'active':
                    return dict(l)
            return None

        if "SELECT * FROM PVP_V2_MARKET_LISTINGS WHERE ID = %S" in q:
            lid = params[0]
            for l in self.market_listings:
                if l['id'] == int(lid):
                    return dict(l)
            return None

        raise NotImplementedError(f"One mock not implemented for: {query}")

    def all(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        if "SELECT * FROM PVP_V2_RESEARCH_FOLDERS WHERE OWNER_ID = %S ORDER BY CREATED_AT DESC" in q:
            oid = params[0]
            res = [dict(f) for f in self.research_folders if f['owner_id'] == int(oid)]
            res.sort(key=lambda x: x['created_at'], reverse=True)
            return res

        if "SELECT * FROM PVP_V2_SOFTWARE_COPIES WHERE OWNER_ID = %S ORDER BY CREATED_AT DESC" in q:
            oid = params[0]
            res = [dict(c) for c in self.software_copies if c['owner_id'] == int(oid)]
            res.sort(key=lambda x: x['created_at'], reverse=True)
            return res

        if "SELECT * FROM PVP_V2_SOFTWARE_COPIES WHERE OWNER_ID = %S AND FINGERPRINT = %S" in q:
            oid, fp = params
            return [dict(c) for c in self.software_copies if c['owner_id'] == int(oid) and c['fingerprint'] == str(fp)]

        if "SELECT * FROM PVP_V2_PATCHES WHERE OWNER_ID = %S ORDER BY CREATED_AT DESC" in q:
            oid = params[0]
            res = [dict(p) for p in self.patches if p['owner_id'] == int(oid)]
            res.sort(key=lambda x: x['created_at'], reverse=True)
            return res

        if "SELECT FINGERPRINT FROM PVP_V2_PATCHES WHERE OWNER_ID = %S AND INSTALLED = 1" in q:
            oid = params[0]
            return [{'fingerprint': p['fingerprint']} for p in self.patches if p['owner_id'] == int(oid) and p['installed'] == 1]

        if "SELECT * FROM PVP_V2_DEV_JOBS WHERE PLAYER_ID = %S ORDER BY RESOLVES_AT ASC" in q:
            pid = params[0]
            res = [dict(j) for j in self.dev_jobs if j['player_id'] == int(pid)]
            res.sort(key=lambda x: x['resolves_at'])
            return res

        if "SELECT * FROM PVP_V2_DEV_JOBS WHERE RESOLVES_AT <= %S ORDER BY RESOLVES_AT ASC" in q:
            now_val = params[0]
            res = [dict(j) for j in self.dev_jobs if j['resolves_at'] <= now_val]
            res.sort(key=lambda x: x['resolves_at'])
            return res

        if "SELECT * FROM PVP_V2_OPERATIONS WHERE ATTACKER_ID = %S AND STATUS IN ('INSTALLING', 'ACTIVE')" in q:
            aid = params[0]
            res = [dict(op) for op in self.operations if op['attacker_id'] == int(aid) and op['status'] in ('installing', 'active')]
            res.sort(key=lambda x: x['started_at'])
            return res

        if "SELECT * FROM PVP_V2_OPERATIONS WHERE VICTIM_ID = %S AND STATUS IN ('INSTALLING', 'ACTIVE')" in q:
            vid = params[0]
            res = [dict(op) for op in self.operations if op['victim_id'] == int(vid) and op['status'] in ('installing', 'active')]
            res.sort(key=lambda x: x['started_at'])
            return res

        if "SELECT * FROM PVP_V2_OPERATIONS WHERE STATUS = 'INSTALLING' ORDER BY STARTED_AT ASC" in q:
            res = [dict(op) for op in self.operations if op['status'] == 'installing']
            res.sort(key=lambda x: x['started_at'])
            return res

        if "SELECT * FROM PVP_V2_ACTIVE_EFFECTS WHERE VICTIM_ID = %S AND ENDED_AT IS NULL" in q:
            vid = params[0]
            res = [dict(ef) for ef in self.active_effects if ef['victim_id'] == int(vid) and ef['ended_at'] is None]
            res.sort(key=lambda x: x['started_at'])
            return res

        if "SELECT * FROM PVP_V2_ACTIVE_EFFECTS WHERE VICTIM_ID = %S AND FAMILY = %S AND ENDED_AT IS NULL" in q:
            vid, fam = params
            return [dict(ef) for ef in self.active_effects if ef['victim_id'] == int(vid) and ef['family'] == str(fam) and ef['ended_at'] is None]

        if "SELECT * FROM PVP_V2_SCAN_REPORTS WHERE ATTACKER_ID = %S ORDER BY SCANNED_AT DESC" in q:
            aid = params[0]
            res = [dict(r) for r in self.scan_reports if r['attacker_id'] == int(aid)]
            res.sort(key=lambda x: x['scanned_at'], reverse=True)
            return res

        if "SELECT * FROM PVP_V2_ESPIONAGE_REPORTS WHERE ATTACKER_ID = %S ORDER BY SCANNED_AT DESC" in q:
            aid = params[0]
            res = [dict(r) for r in self.espionage_reports if r['attacker_id'] == int(aid)]
            res.sort(key=lambda x: x['scanned_at'], reverse=True)
            return res

        if "SELECT * FROM PVP_V2_MARKET_LISTINGS WHERE STATUS = 'ACTIVE' AND ITEM_TYPE = %S" in q:
            itype = params[0]
            res = [dict(l) for l in self.market_listings if l['status'] == 'active' and l['item_type'] == str(itype)]
            res.sort(key=lambda x: x['listed_at'], reverse=True)
            return res

        if "SELECT * FROM PVP_V2_MARKET_LISTINGS WHERE STATUS = 'ACTIVE' ORDER BY LISTED_AT DESC" in q:
            res = [dict(l) for l in self.market_listings if l['status'] == 'active']
            res.sort(key=lambda x: x['listed_at'], reverse=True)
            return res

        if "SELECT * FROM PVP_V2_MARKET_LISTINGS WHERE SELLER_ID = %S ORDER BY LISTED_AT DESC" in q:
            sid = params[0]
            res = [dict(l) for l in self.market_listings if l['seller_id'] == int(sid)]
            res.sort(key=lambda x: x['listed_at'], reverse=True)
            return res

        if "SELECT * FROM PVP_V2_MARKET_LISTINGS WHERE STATUS = 'ACTIVE' AND EXPIRES_AT IS NOT NULL AND EXPIRES_AT <= %S" in q:
            now_val = params[0]
            return [dict(l) for l in self.market_listings if l['status'] == 'active' and l['expires_at'] is not None and l['expires_at'] <= now_val]

        raise NotImplementedError(f"All mock not implemented for: {query}")


class TestPvpV2DatabaseRepositories(unittest.TestCase):
    """Teste unitaire de tous les dépôts de base de données PvP V2."""

    def setUp(self):
        self.tx = MockPvpV2Transaction()
        self.player_a = 1001
        self.player_b = 2002

    # --- 1. Research Folders ---
    def test_research_folder_crud_and_uniqueness(self):
        folder = PvpV2ResearchDB.create(self.tx, self.player_a, 'offense', 'hostile_miner', 3, 'K7M2')
        self.assertEqual(folder['owner_id'], self.player_a)
        self.assertEqual(folder['fingerprint'], 'K7M2')

        self.assertTrue(PvpV2ResearchDB.fingerprint_exists(self.tx, 'hostile_miner', 'K7M2'))
        self.assertFalse(PvpV2ResearchDB.fingerprint_exists(self.tx, 'hostile_miner', 'ZZZZ'))

        found = PvpV2ResearchDB.get_by_owner_family_tier(self.tx, self.player_a, 'hostile_miner', 3)
        self.assertIsNotNone(found)
        self.assertEqual(found['fingerprint'], 'K7M2')

        # Test uniqueness constraint
        with self.assertRaises(Exception):
            PvpV2ResearchDB.create(self.tx, self.player_b, 'offense', 'hostile_miner', 3, 'K7M2')

        # Delete
        deleted = PvpV2ResearchDB.delete(self.tx, folder['id'], self.player_a)
        self.assertTrue(deleted)
        self.assertFalse(PvpV2ResearchDB.fingerprint_exists(self.tx, 'hostile_miner', 'K7M2'))

    # --- 2. Software Copies ---
    def test_software_copy_resellable_and_transfer(self):
        # Compiled copy is resellable
        c1 = PvpV2SoftwareDB.create(self.tx, self.player_a, 'hostile_miner', 3, 'K7M2', 'compiled')
        self.assertEqual(c1['resellable'], 1)
        self.assertEqual(c1['reserved'], 0)

        # Stolen copy is NOT resellable
        c2 = PvpV2SoftwareDB.create(self.tx, self.player_b, 'hostile_miner', 3, 'K7M2', 'stolen')
        self.assertEqual(c2['resellable'], 0)

        # Reserve
        self.assertTrue(PvpV2SoftwareDB.set_reserved(self.tx, c1['id'], True))
        c1_updated = PvpV2SoftwareDB.get_by_id(self.tx, c1['id'])
        self.assertEqual(c1_updated['reserved'], 1)

        # Transfer ownership
        self.assertTrue(PvpV2SoftwareDB.transfer_ownership(self.tx, c1['id'], self.player_b))
        c1_transferred = PvpV2SoftwareDB.get_by_id(self.tx, c1['id'])
        self.assertEqual(c1_transferred['owner_id'], self.player_b)
        self.assertEqual(c1_transferred['origin'], 'purchased')
        self.assertEqual(c1_transferred['reserved'], 0)

    # --- 3. Patches ---
    def test_patch_lifecycle_and_installed_lookup(self):
        patch = PvpV2PatchDB.create(self.tx, self.player_a, 'hostile_miner', 'K7M2')
        self.assertEqual(patch['installed'], 0)
        self.assertFalse(PvpV2PatchDB.is_installed(self.tx, self.player_a, 'K7M2'))

        # Install
        self.assertTrue(PvpV2PatchDB.install(self.tx, patch['id'], self.player_a))
        self.assertTrue(PvpV2PatchDB.is_installed(self.tx, self.player_a, 'K7M2'))
        self.assertIn('K7M2', PvpV2PatchDB.get_installed_fingerprints(self.tx, self.player_a))

        # Once installed, cannot be reserved or deleted
        self.assertFalse(PvpV2PatchDB.set_reserved(self.tx, patch['id'], True))
        self.assertFalse(PvpV2PatchDB.delete(self.tx, patch['id'], self.player_a))

    # --- 4. Dev Jobs ---
    def test_dev_jobs_channel_uniqueness_and_expiry(self):
        exp_time = self.tx.now + timedelta(minutes=45)
        job = PvpV2DevJobsDB.create(
            self.tx, self.player_a, 'offense', 'research', 'hostile_miner', 3,
            Decimal('0.005'), 500, exp_time
        )
        self.assertEqual(job['channel'], 'offense')

        # Cannot create second job on the same channel
        with self.assertRaises(Exception):
            PvpV2DevJobsDB.create(
                self.tx, self.player_a, 'offense', 'compile', 'hostile_miner', 3,
                Decimal('0.002'), 500, exp_time
            )

        # Defense channel is independent
        def_job = PvpV2DevJobsDB.create(
            self.tx, self.player_a, 'defense', 'patch_research', 'hostile_miner', 3,
            Decimal('0.005'), 200, exp_time
        )
        self.assertEqual(def_job['channel'], 'defense')
        self.assertEqual(len(PvpV2DevJobsDB.get_all_active_by_player(self.tx, self.player_a)), 2)

        # Expiry check
        self.tx.now = exp_time + timedelta(seconds=1)
        expired = PvpV2DevJobsDB.get_expired(self.tx)
        self.assertEqual(len(expired), 2)

        # Cancel channel
        cancelled = PvpV2DevJobsDB.cancel_by_player_channel(self.tx, self.player_a, 'offense')
        self.assertIsNotNone(cancelled)
        self.assertIsNone(PvpV2DevJobsDB.get_active_by_player_channel(self.tx, self.player_a, 'offense'))

    # --- 5. Operations & Active Effects ---
    def test_operations_lifecycle_and_active_effects(self):
        op = PvpV2OperationsDB.create(
            self.tx, self.player_a, self.player_b, 'hostile_miner', 3, 'K7M2', 42, Decimal('0.001')
        )
        self.assertEqual(op['status'], 'installing')
        self.assertEqual(PvpV2OperationsDB.count_active_by_attacker(self.tx, self.player_a), 1)
        self.assertEqual(PvpV2OperationsDB.count_active_by_attacker_family(self.tx, self.player_a, 'hostile_miner'), 1)

        # Transition to active
        self.assertTrue(PvpV2OperationsDB.mark_active(self.tx, op['id']))
        op_active = PvpV2OperationsDB.get_by_id(self.tx, op['id'])
        self.assertEqual(op_active['status'], 'active')

        # Create active effect
        effect = PvpV2ActiveEffectsDB.create(
            self.tx, op['id'], self.player_a, self.player_b, 'hostile_miner', 3, 'K7M2', {'siphon_rate': 0.15}
        )
        self.assertTrue(PvpV2ActiveEffectsDB.is_active_fingerprint_on_victim(self.tx, self.player_b, 'K7M2'))

        # End effect by patch
        ended_count = PvpV2ActiveEffectsDB.end_effects_by_fingerprint_victim(self.tx, self.player_b, 'K7M2', 'patch')
        self.assertEqual(ended_count, 1)
        self.assertFalse(PvpV2ActiveEffectsDB.is_active_fingerprint_on_victim(self.tx, self.player_b, 'K7M2'))

        # End operation
        self.assertTrue(PvpV2OperationsDB.mark_ended(self.tx, op['id'], 'completed', 'patch'))
        self.assertEqual(PvpV2OperationsDB.count_active_by_attacker(self.tx, self.player_a), 0)

    # --- 6. Reports ---
    def test_reports_snapshot_and_expiry(self):
        report_data = {'infrastructure_level': 2, 'hashrate': 2500}
        rep = PvpV2ScanReportsDB.create(self.tx, self.player_a, self.player_b, report_data, validity_hours=24)
        self.assertIsNotNone(PvpV2ScanReportsDB.get_latest_valid(self.tx, self.player_a, self.player_b))

        # After 25h, report is expired
        self.tx.now = self.tx.now + timedelta(hours=25)
        self.assertIsNone(PvpV2ScanReportsDB.get_latest_valid(self.tx, self.player_a, self.player_b))

        # Cleanup
        deleted = PvpV2ScanReportsDB.delete_expired(self.tx)
        self.assertEqual(deleted, 1)

    # --- 7. Market Listings ---
    def test_market_listing_lifecycle(self):
        listing = PvpV2MarketDB.create(self.tx, self.player_a, 'compiled_software', 10, Decimal('500.00'))
        self.assertEqual(listing['status'], 'active')
        self.assertEqual(PvpV2MarketDB.count_active_by_seller(self.tx, self.player_a), 1)

        active = PvpV2MarketDB.get_active_listings(self.tx, 'compiled_software')
        self.assertEqual(len(active), 1)

        # Mark sold
        self.assertTrue(PvpV2MarketDB.mark_sold(self.tx, listing['id'], self.player_b))
        sold = PvpV2MarketDB.get_by_id(self.tx, listing['id'])
        self.assertEqual(sold['status'], 'sold')
        self.assertEqual(sold['sold_to'], self.player_b)
        self.assertEqual(PvpV2MarketDB.count_active_by_seller(self.tx, self.player_a), 0)

    # --- 8. Logical Concurrency Test ---
    def test_logical_concurrency_double_confirmation(self):
        """Deux confirmations identiques ne créent qu'une seule ressource facturable."""
        # Confirmation 1 : lance la recherche sur 'offense'
        exp_time = self.tx.now + timedelta(minutes=45)
        PvpV2DevJobsDB.create(
            self.tx, self.player_a, 'offense', 'research', 'hostile_miner', 3,
            Decimal('0.005'), 500, exp_time
        )

        # Confirmation 2 (ex: double clic ou requête concurrente) :
        # Le verrou ou la vérification d'état détecte que le canal est déjà pris.
        active = PvpV2DevJobsDB.get_active_by_player_channel(self.tx, self.player_a, 'offense')
        self.assertIsNotNone(active)

        # Tentative d'insertion concurrente directe rejetée par la contrainte UNIQUE
        with self.assertRaises(Exception):
            PvpV2DevJobsDB.create(
                self.tx, self.player_a, 'offense', 'research', 'hostile_miner', 3,
                Decimal('0.005'), 500, exp_time
            )


if __name__ == '__main__':
    unittest.main()
