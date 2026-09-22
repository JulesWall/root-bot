"""
Tests unitaires pour la commande /scan et les mécaniques associées :
- ConsequenceDB (représailles PvP)
- HackDB (jobs de type scan)
- Player.scan (devis, validation, règles PvP, invulnérabilité, écart de niveau)
- Intégration RootService (_locks_for, ACTIONS, dispatch)
- Internationalisation des chaînes scan (FR et EN)
"""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from game.db.consequence import ConsequenceDB
from game.db.hack import HackDB
from game.db.players import Player, NewPlayer, UpdatePlayer
from game.game_error import GameError
from game.math_config import MathConfig
from game.root_service import RootService
from lang import game_en, game_fr, descslash


class MockTransaction:
    """Mock léger de transaction pour les tests de scan."""

    def __init__(self, now=None):
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        self.players = {}
        self.hacks = []
        self.consequences = []
        self.acquired_locks = []

    def acquire_lock(self, name: str, timeout: int = 10) -> None:
        if name and name not in self.acquired_locks:
            self.acquired_locks.append(name)

    def one(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        if "SELECT * FROM PLAYERS WHERE DISCORD_ID = %S" in q:
            uid = int(params[0])
            p = self.players.get(uid)
            return dict(p) if p else None

        if "SELECT * FROM HACK WHERE DISCORD_ID = %S AND TYPE = %S" in q:
            uid, htype = int(params[0]), str(params[1])
            for h in self.hacks:
                if h["discord_id"] == uid and h.get("type", "compile") == htype:
                    return dict(h)
            return None

        if "SELECT 1 FROM CONSEQUENCE WHERE VICTIM_ID = %S AND ATTACKER_ID = %S AND DELETE_AT > %S" in q:
            vid, aid, now = int(params[0]), int(params[1]), params[2]
            for c in self.consequences:
                if c["victim_id"] == vid and c["attacker_id"] == aid and c["delete_at"] > now:
                    return {"1": 1}
            return None

        return None

    def all(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        if "SELECT * FROM HACK WHERE EXPIRES_AT <= %S AND TYPE = 'SCAN'" in q:
            cutoff = params[0]
            return [dict(h) for h in self.hacks if h.get("type") == "scan" and h["expires_at"] <= cutoff]

        if "SELECT * FROM HACK WHERE EXPIRES_AT <= %S AND TYPE = 'COMPILE'" in q:
            cutoff = params[0]
            return [dict(h) for h in self.hacks if h.get("type", "compile") == "compile" and h["expires_at"] <= cutoff]

        return []

    def execute(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        if "INSERT INTO CONSEQUENCE" in q:
            vid, aid = int(params[0]), int(params[1])
            now_val, hours = params[2], int(params[3])
            del_at = now_val + timedelta(hours=hours)
            self.consequences.append({
                "id": len(self.consequences) + 1,
                "victim_id": vid,
                "attacker_id": aid,
                "delete_at": del_at,
            })
            return len(self.consequences)

        if "DELETE FROM CONSEQUENCE WHERE DELETE_AT <= %S" in q:
            cutoff = params[0]
            before = len(self.consequences)
            self.consequences = [c for c in self.consequences if c["delete_at"] > cutoff]
            return before - len(self.consequences)

        if "INSERT INTO HACK" in q:
            if "'SCAN'" in q:
                scanner_id = int(params[0])
                target_id = int(params[1])
                rtm_paid = Decimal(str(params[2]))
                boost_rtm = Decimal(str(params[3]))
                started_at = params[4]
                expires_at = params[5]
                row = {
                    "id": len(self.hacks) + 1,
                    "discord_id": scanner_id,
                    "target_id": target_id,
                    "type": "scan",
                    "method": "scan",
                    "bits_per_s": 0,
                    "atk_yield": 0,
                    "rtm_paid": rtm_paid,
                    "boost_rtm": boost_rtm,
                    "started_at": started_at,
                    "expires_at": expires_at,
                }
                self.hacks.append(row)
                return row["id"]

        if "DELETE FROM HACK WHERE ID = %S" in q:
            hid = int(params[0])
            self.hacks = [h for h in self.hacks if h["id"] != hid]
            return 1

        if "UPDATE PLAYERS SET" in q:
            uid = int(params[-1])
            if uid in self.players:
                pass
            return 1

        return 1


class TestScanFeature(unittest.TestCase):
    """Tests unitaires pour toutes les composantes de /scan."""

    def setUp(self):
        self.tx = MockTransaction()
        self.scanner_id = 1001
        self.target_id = 2002

        # Création scanner (Firewall 2, ATK 100, RTM 1.0)
        self.tx.players[self.scanner_id] = {
            "discord_id": self.scanner_id,
            "firewall_level": 2,
            "attack_points": 100,
            "rootium": Decimal("1.00000"),
            "dollars": Decimal("1000.00"),
            "mining_t1": 1,
            "attack_t1": 1,
            "attack_t2": 0,
            "defense_t1": 0,
            "secret_id": "111111",
        }

        # Création cible (Firewall 2, Defense 50)
        self.tx.players[self.target_id] = {
            "discord_id": self.target_id,
            "firewall_level": 2,
            "attack_points": 0,
            "rootium": Decimal("0.50000"),
            "dollars": Decimal("500.00"),
            "mining_t1": 0,
            "attack_t1": 0,
            "defense_t1": 1,
            "secret_id": "222222",
        }

    def test_consequence_db_flow(self):
        """Test insert, check et purge dans ConsequenceDB."""
        # Aucune conséquence au départ
        self.assertFalse(ConsequenceDB.check(self.tx, victim_id=self.target_id, attacker_id=self.scanner_id))

        # Insertion de représailles (72h)
        ConsequenceDB.insert(self.tx, victim_id=self.target_id, attacker_id=self.scanner_id, window_hours=72)
        self.assertTrue(ConsequenceDB.check(self.tx, victim_id=self.target_id, attacker_id=self.scanner_id))

        # Vérification qu'un tiers n'a pas de représailles
        self.assertFalse(ConsequenceDB.check(self.tx, victim_id=9999, attacker_id=self.scanner_id))

        # Purge avant expiration -> 0 supprimé
        purged = ConsequenceDB.purge_expired(self.tx)
        self.assertEqual(purged, 0)
        self.assertTrue(ConsequenceDB.check(self.tx, victim_id=self.target_id, attacker_id=self.scanner_id))

        # Avance dans le temps après 73h -> purge
        self.tx.now = self.tx.now + timedelta(hours=73)
        purged = ConsequenceDB.purge_expired(self.tx)
        self.assertEqual(purged, 1)
        self.assertFalse(ConsequenceDB.check(self.tx, victim_id=self.target_id, attacker_id=self.scanner_id))

    def test_scan_pvp_rules(self):
        """Vérifie toutes les contraintes PvP de Player.scan."""
        # 1. Auto-scan interdit
        with self.assertRaises(GameError) as cm:
            Player.scan(self.tx, self.scanner_id, target=self.scanner_id)
        self.assertEqual(cm.exception.key, "self_target")

        # 2. Cible non inscrite
        with self.assertRaises(GameError) as cm:
            Player.scan(self.tx, self.scanner_id, target=9999)
        self.assertEqual(cm.exception.key, "target_not_registered")

        # 3. Scanner invulnérable (firewall 0)
        self.tx.players[self.scanner_id]["firewall_level"] = 0
        with self.assertRaises(GameError) as cm:
            Player.scan(self.tx, self.scanner_id, target=self.target_id)
        self.assertEqual(cm.exception.key, "scan_self_invulnerable")
        self.tx.players[self.scanner_id]["firewall_level"] = 2

        # 4. Cible invulnérable (firewall 0)
        self.tx.players[self.target_id]["firewall_level"] = 0
        with self.assertRaises(GameError) as cm:
            Player.scan(self.tx, self.scanner_id, target=self.target_id)
        self.assertEqual(cm.exception.key, "scan_target_invulnerable")
        self.tx.players[self.target_id]["firewall_level"] = 1

        # 5. Protection écart de niveau (target_fw < scanner_fw)
        with self.assertRaises(GameError) as cm:
            Player.scan(self.tx, self.scanner_id, target=self.target_id)
        self.assertEqual(cm.exception.key, "scan_target_protected")

        # Avec droit de représailles actif : déblocage de la protection
        ConsequenceDB.insert(self.tx, victim_id=self.scanner_id, attacker_id=self.target_id, window_hours=72)
        quote = Player.scan(self.tx, self.scanner_id, target=self.target_id)
        self.assertTrue(quote.get("scan_quote"))

        # Remise à niveau égal
        self.tx.players[self.target_id]["firewall_level"] = 2

        # 6. Scanner sans stock ATK
        self.tx.players[self.scanner_id]["attack_points"] = 0
        with self.assertRaises(GameError) as cm:
            Player.scan(self.tx, self.scanner_id, target=self.target_id)
        self.assertEqual(cm.exception.key, "scan_no_atk")
        self.tx.players[self.scanner_id]["attack_points"] = 100

        # 7. Solde RTM insuffisant à la confirmation
        self.tx.players[self.scanner_id]["rootium"] = Decimal("0.00001")
        with self.assertRaises(GameError) as cm:
            Player.scan(self.tx, self.scanner_id, target=self.target_id, confirm=True)
        self.assertEqual(cm.exception.key, "insufficient_funds_rtm")

    def test_scan_quote_and_launch(self):
        """Vérifie le devis puis le lancement avec débit RTM et création du job."""
        # Devis (confirm=False)
        quote = Player.scan(self.tx, self.scanner_id, target=self.target_id)
        self.assertTrue(quote.get("scan_quote"))
        self.assertEqual(quote["prob_base_pct"], 33.3)
        self.assertEqual(len(quote["boost_options"]), 3)
        self.assertEqual(quote["boost_options"][0]["prob_pct"], 33.3)
        self.assertEqual(quote["boost_options"][1]["prob_pct"], 36.7)
        self.assertEqual(quote["boost_options"][2]["prob_pct"], 46.7)

        # Lancement avec boost multiplier 2
        res = Player.scan(self.tx, self.scanner_id, target=self.target_id, boost_multiplier=2, confirm=True)
        self.assertTrue(res.get("scan_started"))
        self.assertEqual(res["boost_multiplier"], 2)
        self.assertEqual(len(self.tx.hacks), 1)

        job = self.tx.hacks[0]
        self.assertEqual(job["type"], "scan")
        self.assertEqual(job["discord_id"], self.scanner_id)
        self.assertEqual(job["target_id"], self.target_id)

        # Scan déjà actif
        with self.assertRaises(GameError) as cm:
            Player.scan(self.tx, self.scanner_id, target=self.target_id)
        self.assertEqual(cm.exception.key, "scan_in_progress")

        # Livraison du job
        self.tx.hacks[0]["expires_at"] = self.tx.now
        delivered = HackDB.complete_and_delete_expired_scans(self.tx)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0]["scanner_id"], self.scanner_id)
        self.assertEqual(delivered[0]["target_id"], self.target_id)
        self.assertEqual(self.tx.hacks, [])

    def test_rootservice_scan_dispatch(self):
        """Vérifie que RootService intègre scan dans ACTIONS et _locks_for."""
        service = RootService(database=MagicMock())
        self.assertIn("scan", service.ACTIONS)

        # _locks_for pour scan prend les verrous des deux joueurs triés
        locks = service._locks_for("scan", 2002, {"target": 1001})
        self.assertEqual(locks, ["player:1001", "player:2002"])

    def test_scan_i18n_keys(self):
        """Vérifie la présence et symétrie de toutes les clés de langue pour scan."""
        required_keys = (
            "g_scan_quote", "g_scan_btn_launch", "g_scan_btn_boost2", "g_scan_btn_boost5",
            "g_scan_started", "g_scan_success_dm", "g_scan_failure_dm",
            "g_scan_alert_anon", "g_scan_alert_identified",
            "g_scan_expose_confirm", "g_scan_exposed_public",
            "g_scan_expose_btn", "g_scan_keep_secret_btn",
            "g_scan_expose_confirm_btn", "g_scan_expose_cancel_btn",
            "g_error_scan_in_progress", "g_error_scan_no_atk",
            "g_error_scan_target_invulnerable", "g_error_scan_self_invulnerable",
            "g_error_scan_target_protected", "g_error_scan_usage",
            "g_upgrade_quote_scan_alert_3", "g_upgrade_quote_scan_alert_4",
        )
        for k in required_keys:
            self.assertIn(k, game_fr.text, f"Clé manquante dans game_fr: {k}")
            self.assertIn(k, game_en.text, f"Clé manquante dans game_en: {k}")

        self.assertIn("scan", game_fr.descriptions)
        self.assertIn("scan", game_en.descriptions)
        self.assertIn("act_scan", game_fr.labels)
        self.assertIn("act_scan", game_en.labels)
        self.assertIn("scan_target", descslash.desc)
        self.assertIn("scan_target", descslash.desc_loc)


if __name__ == "__main__":
    unittest.main()

