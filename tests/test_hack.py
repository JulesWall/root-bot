"""
Tests unitaires pour la commande PvP /hack et les mécaniques associées :
- PvpDB (création, sélection, résolution de combat atomique)
- Destruction déterministe des modules de défense (T1 -> T6)
- Test strict d'intrusion (attack_points > total_defense)
- Effet intrusion : destruction module ATK (tier le plus haut) ou transfert module minage (tier le plus haut)
- Pare-feu indestructible
- Player.hack (devis, validation des règles PvP, invulnérabilités, stock ATK, réservation)
- Intégration RootService (ACTIONS, _locks_for, dispatch)
- Internationalisation complète (FR et EN)
"""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from game.db.consequence import ConsequenceDB
from game.db.players import Player, UpdatePlayer
from game.db.pvp import PvpDB
from game.game_error import GameError
from game.math_config import MathConfig
from game.root_service import RootService
from lang import game_en, game_fr, descslash


class MockTransaction:
    """Mock léger de transaction pour tester la logique PvP."""

    def __init__(self, now=None):
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        self.players = {}
        self.pvp_attacks = []
        self.consequences = []
        self.acquired_locks = []

    def acquire_lock(self, name: str, timeout: int = 10) -> None:
        if name and name not in self.acquired_locks:
            self.acquired_locks.append(name)

    def one(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        if "SELECT * FROM PLAYERS WHERE DISCORD_ID = %S" in q or "SELECT SECRET_ID FROM PLAYERS WHERE DISCORD_ID = %S" in q:
            uid = int(params[0])
            p = self.players.get(uid)
            return dict(p) if p else None

        if "SELECT * FROM PLAYERS WHERE SECRET_ID=%S" in q or "SELECT * FROM PLAYERS WHERE SECRET_ID = %S" in q:
            sec = str(params[0]).strip()
            for p in self.players.values():
                if p.get("secret_id") == sec:
                    return dict(p)
            return None

        if "SELECT * FROM PVP_ATTACKS WHERE ID = %S" in q:
            aid = int(params[0])
            for a in self.pvp_attacks:
                if a["id"] == aid:
                    return dict(a)
            return None

        if "SELECT * FROM PVP_ATTACKS WHERE VICTIM_ID = %S" in q:
            vid = int(params[0])
            for a in self.pvp_attacks:
                if a["victim_id"] == vid:
                    return dict(a)
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

        if "SELECT * FROM PVP_ATTACKS WHERE ATTACKER_ID = %S" in q:
            aid = int(params[0])
            return [dict(a) for a in self.pvp_attacks if a["attacker_id"] == aid]

        if "SELECT ID FROM PVP_ATTACKS WHERE RESOLVES_AT <= %S" in q:
            cutoff = params[0]
            return [{"id": a["id"]} for a in self.pvp_attacks if a["resolves_at"] <= cutoff]

        if "SELECT SECRET_ID FROM PLAYERS WHERE SECRET_ID IS NOT NULL" in q:
            return [{"secret_id": p.get("secret_id")} for p in self.players.values() if p.get("secret_id")]

        return []

    def execute(self, query: str, params=()):
        q = " ".join(query.split()).upper()

        if "INSERT INTO PVP_ATTACKS" in q:
            attacker_id = int(params[0])
            victim_id = int(params[1])
            attack_points = int(params[2])
            target = str(params[3])
            started_at = params[4]
            resolves_at = params[5]
            row = {
                "id": len(self.pvp_attacks) + 1,
                "attacker_id": attacker_id,
                "victim_id": victim_id,
                "attack_points": attack_points,
                "target": target,
                "started_at": started_at,
                "resolves_at": resolves_at,
            }
            self.pvp_attacks.append(row)
            return row["id"]

        if "DELETE FROM PVP_ATTACKS WHERE ID = %S" in q:
            aid = int(params[0])
            self.pvp_attacks = [a for a in self.pvp_attacks if a["id"] != aid]
            return 1

        if "INSERT INTO CONSEQUENCE" in q:
            vid, aid = int(params[0]), int(params[1])
            now_val, hours = params[2], int(params[3])
            self.consequences.append({
                "id": len(self.consequences) + 1,
                "victim_id": vid,
                "attacker_id": aid,
                "delete_at": now_val + timedelta(hours=hours),
            })
            return len(self.consequences)

        if "UPDATE PLAYERS SET SECRET_ID = NULL WHERE DISCORD_ID = %S" in q:
            uid = int(params[0])
            p = self.players.get(uid)
            if p:
                p["secret_id"] = None
            return 1

        if "UPDATE PLAYERS SET" in q:
            uid = int(params[-1])
            p = self.players.get(uid)
            if p:
                parts = query.split("SET")[1].split("WHERE")[0].split(",")
                for idx, part in enumerate(parts):
                    col = part.strip().split("=")[0].strip()
                    p[col] = params[idx]
            return 1

        return 1


class TestPvPFeature(unittest.TestCase):
    """Tests unitaires exhaustifs pour la commande /hack."""

    def setUp(self):
        self.tx = MockTransaction()
        self.attacker_id = 1111
        self.victim_id = 2222

        # Attaquant : Firewall 2, 600 ATK, 2 mineurs T1, 1 mineur T3
        self.tx.players[self.attacker_id] = {
            "discord_id": self.attacker_id,
            "firewall_level": 2,
            "attack_points": 600,
            "rootium": Decimal("10.00000"),
            "dollars": Decimal("1000.00"),
            "mining_t1": 2,
            "mining_t2": 0,
            "mining_t3": 1,
            "mining_t4": 0,
            "mining_t5": 0,
            "mining_t6": 0,
            "attack_t1": 1,
            "attack_t2": 1,
            "attack_t3": 0,
            "attack_t4": 0,
            "attack_t5": 0,
            "attack_t6": 0,
            "bay_defense_t1": 0,
            "bay_defense_t2": 0,
            "bay_defense_t3": 0,
            "bay_defense_t4": 0,
            "bay_defense_t5": 0,
            "bay_defense_t6": 0,
            "secret_id": "123456",
            "mining_buffer": Decimal("0"),
            "mining_last_update_at": self.tx.now,
        }

        # Victime : Firewall 2 (300 DEF firewall)
        # Modules défense : 3x T1 (3x 10 = 30 DEF), 2x T2 (2x 50 = 100 DEF), 1x T3 (1x 200 = 200 DEF)
        # Total modules DEF = 30 + 100 + 200 = 330 DEF. Total defense initiale = 330 + 300 = 630 DEF.
        # Modules attaque : 2x T1, 1x T4 (le plus haut est T4)
        # Modules minage : 1x T2, 1x T5 (le plus haut est T5)
        self.tx.players[self.victim_id] = {
            "discord_id": self.victim_id,
            "firewall_level": 2,
            "attack_points": 50,
            "rootium": Decimal("5.00000"),
            "dollars": Decimal("500.00"),
            "mining_t1": 0,
            "mining_t2": 1,
            "mining_t3": 0,
            "mining_t4": 0,
            "mining_t5": 1,
            "mining_t6": 0,
            "attack_t1": 2,
            "attack_t2": 0,
            "attack_t3": 0,
            "attack_t4": 1,
            "attack_t5": 0,
            "attack_t6": 0,
            "bay_defense_t1": 3,
            "bay_defense_t2": 2,
            "bay_defense_t3": 1,
            "bay_defense_t4": 0,
            "bay_defense_t5": 0,
            "bay_defense_t6": 0,
            "secret_id": "654321",
            "mining_buffer": Decimal("0"),
            "mining_last_update_at": self.tx.now,
        }

    def test_pvp_rules_and_validations(self):
        """Vérifie toutes les contraintes d'accès PvP pour Player.hack."""
        # 1. Secret ID inconnu
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id="000000", atk=100, zone="mining")
        self.assertEqual(cm.exception.key, "invalid_secret_id")

        # 2. Auto-ciblage interdit
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id="123456", atk=100, zone="mining")
        self.assertEqual(cm.exception.key, "self_target")

        # 3. Attaquant invulnérable (firewall 0)
        self.tx.players[self.attacker_id]["firewall_level"] = 0
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=100, zone="mining")
        self.assertEqual(cm.exception.key, "hack_self_invulnerable")
        self.tx.players[self.attacker_id]["firewall_level"] = 2

        # 4. Cible invulnérable (firewall 0)
        self.tx.players[self.victim_id]["firewall_level"] = 0
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=100, zone="mining")
        self.assertEqual(cm.exception.key, "hack_target_invulnerable")
        self.tx.players[self.victim_id]["firewall_level"] = 1

        # 5. Protection écart de niveau (target_fw < attacker_fw)
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=100, zone="mining")
        self.assertEqual(cm.exception.key, "hack_target_protected")

        # Déblocage par droit de représailles actif
        ConsequenceDB.insert(self.tx, victim_id=self.attacker_id, attacker_id=self.victim_id, window_hours=72)
        quote = Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=100, zone="mining")
        self.assertTrue(quote.get("hack_quote"))
        self.tx.players[self.victim_id]["firewall_level"] = 2

        # 6. Zone invalide
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=100, zone="invalid_zone")
        self.assertEqual(cm.exception.key, "invalid_selection")

        # 7. Points ATK négatifs ou nuls
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=0, zone="mining")
        self.assertEqual(cm.exception.key, "invalid_selection")

        # 8. Points ATK supérieurs au stock disponible
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=9999, zone="mining")
        self.assertEqual(cm.exception.key, "hack_insufficient_atk")

    def test_hack_quote_and_launch(self):
        """Vérifie le devis puis le lancement avec réservation des ATK et création dans pvp_attacks."""
        # Devis
        quote = Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=250, zone="mining", confirm=False)
        self.assertTrue(quote.get("hack_quote"))
        self.assertEqual(quote["attack_points"], 250)
        self.assertEqual(quote["target_zone"], "mining")
        self.assertEqual(quote["current_atk"], 600)
        self.assertEqual(quote["remaining_atk"], 350)
        self.assertEqual(len(self.tx.pvp_attacks), 0)
        self.assertEqual(self.tx.players[self.attacker_id]["attack_points"], 600)

        # Lancement (confirm=True)
        res = Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=250, zone="mining", confirm=True)
        self.assertTrue(res.get("hack_started"))
        self.assertEqual(res["remaining_atk"], 350)
        self.assertEqual(self.tx.players[self.attacker_id]["attack_points"], 350)
        self.assertEqual(len(self.tx.pvp_attacks), 1)

        attack = self.tx.pvp_attacks[0]
        self.assertEqual(attack["attacker_id"], self.attacker_id)
        self.assertEqual(attack["victim_id"], self.victim_id)
        self.assertEqual(attack["attack_points"], 250)
        self.assertEqual(attack["target"], "mining")

        # Vérification qu'une 2ème attaque contre la même victime est bloquée
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id="654321", atk=50, zone="attack")
        self.assertEqual(cm.exception.key, "hack_target_in_progress")

    def test_pvp_resolution_no_intrusion(self):
        """
        Cas sans intrusion : attack_points <= total_defense (630 DEF).
        Engageons 150 ATK :
        - T1 : 3x 10 DEF = 30 DEF absorbée (reste 120 budget, 3 T1 détruits)
        - T2 : 2x 50 DEF = 100 DEF absorbée (reste 20 budget, 2 T2 détruits)
        - T3 : 1x 200 DEF > 20 budget restant -> T3 intact, budget restant (20) perdu !
        Total détruit = 130 DEF.
        attack_points (150) <= total_defense (630) -> intrusion_success = False.
        Pare-feu intact.
        Aucun module adverse attaqué/minier touché.
        """
        attack_id = PvpDB.create(
            self.tx,
            attacker_id=self.attacker_id,
            victim_id=self.victim_id,
            attack_points=150,
            target="attack",
            resolves_at=self.tx.now,
        )["id"]

        result = PvpDB.resolve_single_attack(self.tx, attack_id)
        self.assertIsNotNone(result)
        self.assertFalse(result["intrusion_success"])
        self.assertEqual(result["destroyed_defense_points"], 130)
        self.assertEqual(result["initial_total_defense"], 630)
        self.assertEqual(result["firewall_def_points"], 300)
        self.assertIsNone(result["destroyed_attack_tier"])

        # Vérification sur les modules réels de la victime
        self.assertEqual(self.tx.players[self.victim_id]["bay_defense_t1"], 0)
        self.assertEqual(self.tx.players[self.victim_id]["bay_defense_t2"], 0)
        self.assertEqual(self.tx.players[self.victim_id]["bay_defense_t3"], 1)  # Resté intact !
        self.assertEqual(self.tx.players[self.victim_id]["firewall_level"], 2)  # Pare-feu intact !
        self.assertEqual(self.tx.players[self.victim_id]["attack_t4"], 1)       # Module ATK intact !

        # Vérification suppression de l'attaque temporaire
        self.assertEqual(self.tx.pvp_attacks, [])

        # Droit de représailles inséré
        self.assertTrue(ConsequenceDB.check(self.tx, victim_id=self.victim_id, attacker_id=self.attacker_id))

    def test_pvp_resolution_intrusion_attack_target(self):
        """
        Cas avec intrusion réussie sur cible 'attack' :
        Total defense victime = 630 DEF.
        Attaque avec 631 ATK (> 630 strictly !).
        Tous les modules DEF détruits :
        3x T1 (30), 2x T2 (100), 1x T3 (200) = 330 DEF détruits.
        Intrusion réussie !
        Target 'attack' -> destruction de 1 module d'attaque du tier le plus haut possédé (T4).
        Victime passe de attack_t4: 1 à 0.
        Attaquant ne reçoit rien.
        """
        attack_id = PvpDB.create(
            self.tx,
            attacker_id=self.attacker_id,
            victim_id=self.victim_id,
            attack_points=631,
            target="attack",
            resolves_at=self.tx.now,
        )["id"]

        result = PvpDB.resolve_single_attack(self.tx, attack_id)
        self.assertIsNotNone(result)
        self.assertTrue(result["intrusion_success"])
        self.assertEqual(result["destroyed_attack_tier"], 4)
        self.assertEqual(result["destroyed_defense_points"], 330)

        # Vérification victime
        self.assertEqual(self.tx.players[self.victim_id]["bay_defense_t1"], 0)
        self.assertEqual(self.tx.players[self.victim_id]["bay_defense_t2"], 0)
        self.assertEqual(self.tx.players[self.victim_id]["bay_defense_t3"], 0)
        self.assertEqual(self.tx.players[self.victim_id]["attack_t4"], 0)  # Détruit !
        self.assertEqual(self.tx.players[self.victim_id]["attack_t1"], 2)  # Non touché

        # Attaquant n'a pas reçu le module
        self.assertEqual(self.tx.players[self.attacker_id]["attack_t4"], 0)

    def test_pvp_resolution_intrusion_mining_target(self):
        """
        Cas avec intrusion réussie sur cible 'mining' :
        Total defense = 630 DEF.
        Attaque avec 700 ATK (> 630).
        Target 'mining' -> transfert de 1 module de minage du tier le plus haut possédé (T5).
        Victime mining_t5 : 1 -> 0
        Attaquant mining_t5 : 0 -> 1
        """
        attack_id = PvpDB.create(
            self.tx,
            attacker_id=self.attacker_id,
            victim_id=self.victim_id,
            attack_points=700,
            target="mining",
            resolves_at=self.tx.now,
        )["id"]

        result = PvpDB.resolve_single_attack(self.tx, attack_id)
        self.assertIsNotNone(result)
        self.assertTrue(result["intrusion_success"])
        self.assertEqual(result["captured_mining_tier"], 5)

        # Vérification transfert
        self.assertEqual(self.tx.players[self.victim_id]["mining_t5"], 0)
        self.assertEqual(self.tx.players[self.attacker_id]["mining_t5"], 1)

    def test_pvp_resolution_strict_equality_no_intrusion(self):
        """
        Cas d'égalité stricte : attack_points == total_defense (630 ATK contre 630 DEF).
        Règle : l'intrusion exige un '>' strict.
        Résultat attendu :
        - Tous les modules DEF sont détruits (330 DEF).
        - attack_points (630) n'est PAS > total_defense (630).
        - intrusion_success = False !
        - Aucun module d'attaque de la victime n'est détruit.
        """
        attack_id = PvpDB.create(
            self.tx,
            attacker_id=self.attacker_id,
            victim_id=self.victim_id,
            attack_points=630,
            target="attack",
            resolves_at=self.tx.now,
        )["id"]

        result = PvpDB.resolve_single_attack(self.tx, attack_id)
        self.assertIsNotNone(result)
        self.assertFalse(result["intrusion_success"])
        self.assertEqual(result["destroyed_defense_points"], 330)
        self.assertIsNone(result["destroyed_attack_tier"])
        self.assertEqual(self.tx.players[self.victim_id]["attack_t4"], 1)

    def test_pvp_resolution_empty_target_modules(self):
        """
        Cas d'intrusion réussie mais la victime ne possède aucun module dans la zone ciblée.
        Ex: cible 'mining', mais la victime a 0 modules de minage.
        Résultat : intrusion_success = True, captured_mining_tier = None, aucune erreur.
        """
        self.tx.players[self.victim_id]["mining_t1"] = 0
        self.tx.players[self.victim_id]["mining_t2"] = 0
        self.tx.players[self.victim_id]["mining_t3"] = 0
        self.tx.players[self.victim_id]["mining_t4"] = 0
        self.tx.players[self.victim_id]["mining_t5"] = 0
        self.tx.players[self.victim_id]["mining_t6"] = 0

        attack_id = PvpDB.create(
            self.tx,
            attacker_id=self.attacker_id,
            victim_id=self.victim_id,
            attack_points=700,
            target="mining",
            resolves_at=self.tx.now,
        )["id"]

        result = PvpDB.resolve_single_attack(self.tx, attack_id)
        self.assertIsNotNone(result)
        self.assertTrue(result["intrusion_success"])
        self.assertIsNone(result["captured_mining_tier"])

    def test_rootservice_hack_dispatch(self):
        """Vérifie l'intégration dans RootService."""
        service = RootService(database=MagicMock())
        self.assertIn("hack", service.ACTIONS)

        locks = service._locks_for("hack", 1111, {"target_id": 2222})
        self.assertEqual(locks, ["player:1111", "player:2222"])

    def test_pvp_i18n_keys(self):
        """Vérifie la cohérence et la présence de toutes les clés de localisation pour hack."""
        required_keys = (
            "g_hack_quote", "g_hack_btn_launch", "g_hack_started",
            "g_hack_attacker_no_intrusion", "g_hack_attacker_intrusion_attack",
            "g_hack_attacker_intrusion_mining", "g_hack_attacker_intrusion_empty",
            "g_hack_victim_no_intrusion", "g_hack_victim_intrusion_attack",
            "g_hack_victim_intrusion_mining", "g_hack_victim_intrusion_empty",
            "g_error_hack_self_invulnerable", "g_error_hack_target_invulnerable",
            "g_error_hack_target_protected", "g_error_hack_target_in_progress",
            "g_error_hack_insufficient_atk", "g_error_hack_usage",
        )
        for k in required_keys:
            self.assertIn(k, game_fr.text, f"Clé manquante dans game_fr: {k}")
            self.assertIn(k, game_en.text, f"Clé manquante dans game_en: {k}")

        self.assertIn("hack", game_fr.descriptions)
        self.assertIn("hack", game_en.descriptions)
        self.assertIn("act_hack", game_fr.labels)
        self.assertIn("act_hack", game_en.labels)

    def test_pvp_resolution_rotates_victim_secret_id(self):
        """Vérifie que la résolution d'une attaque renouvelle le Secret ID de la victime et invalide l'ancien."""
        old_secret = self.tx.players[self.victim_id]["secret_id"]
        self.assertEqual(old_secret, "654321")

        attack_id = PvpDB.create(
            self.tx,
            attacker_id=self.attacker_id,
            victim_id=self.victim_id,
            attack_points=100,
            target="mining",
            resolves_at=self.tx.now,
        )["id"]

        result = PvpDB.resolve_single_attack(self.tx, attack_id)
        new_secret = result.get("new_victim_secret")
        self.assertIsNotNone(new_secret)
        self.assertNotEqual(new_secret, old_secret)
        self.assertEqual(self.tx.players[self.victim_id]["secret_id"], new_secret)

        # Vérifier que l'ancien secret_id est désormais invalide pour une nouvelle attaque
        with self.assertRaises(GameError) as cm:
            Player.hack(self.tx, self.attacker_id, secret_id=old_secret, atk=100, zone="mining")
        self.assertEqual(cm.exception.key, "invalid_secret_id")

        # Vérifier que le nouveau secret_id permet de cibler la victime
        quote = Player.hack(self.tx, self.attacker_id, secret_id=new_secret, atk=100, zone="mining", confirm=False)
        self.assertTrue(quote.get("hack_quote"))
        self.assertEqual(quote["target_id"], self.victim_id)

    def test_victim_notification_formatting(self):
        """Vérifie que les chaînes de notification victime s'affichent correctement avec new_secret_id."""
        from utils import text
        for l in ("fr", "en"):
            msg1 = text.get_for_lang(
                l, "g_hack_victim_no_intrusion",
                attacker_id=1111,
                attack_points=100,
                total_defense=500,
                destroyed_defense=50,
                new_secret_id="999888",
            )
            self.assertIn("999888", msg1)

            msg2 = text.get_for_lang(
                l, "g_hack_victim_intrusion_attack",
                attacker_id=1111,
                attack_points=600,
                total_defense=500,
                destroyed_defense=200,
                tier=3,
                new_secret_id="999888",
            )
            self.assertIn("999888", msg2)

    def test_hack_confirm_helper(self):
        """Vérifie le comportement de la fonction helper _is_confirm pour !hack."""
        from commands.game.hack import _is_confirm
        self.assertTrue(_is_confirm(True))
        self.assertTrue(_is_confirm("confirm"))
        self.assertTrue(_is_confirm("CONFIRM"))
        self.assertTrue(_is_confirm("valider"))
        self.assertTrue(_is_confirm("yes"))
        self.assertTrue(_is_confirm("true"))
        self.assertFalse(_is_confirm(False))
        self.assertFalse(_is_confirm(None))
        self.assertFalse(_is_confirm("other"))

    def test_hack_has_slash_and_prefix(self):
        """Vérifie que /hack est une slash command ET que !hack/!hk existe en préfixe."""
        import discord
        from discord.ext import commands as ext_commands
        from commands.game.hack import Hack
        bot = MagicMock()
        cog = Hack(bot)

        # /hack doit être une slash command
        slash_commands = [cmd for cmd in getattr(cog, '__cog_commands__', []) if isinstance(cmd, discord.SlashCommand)]
        slash_names = [cmd.name for cmd in slash_commands]
        self.assertIn('hack', slash_names)

        # !hack (et alias !hk) doivent être présents en préfixe (pas des SlashCommands)
        prefix_cmds = [cmd for cmd in cog.get_commands() if cmd.name == 'hack' and isinstance(cmd, ext_commands.Command)]
        self.assertEqual(len(prefix_cmds), 1)
        self.assertIn('hk', prefix_cmds[0].aliases)

        # La fonction slash s'appelle 'hack', la fonction préfixe s'appelle 'prefix_hack'
        self.assertTrue(isinstance(cog.hack, discord.SlashCommand))


class TestPvPPrefixCommand(unittest.IsolatedAsyncioTestCase):
    """Vérifie l'exécution de la commande préfixe !hack."""

    async def test_prefix_hack_invoke_with_confirm(self):
        """Vérifie que la commande hack propage confirm=True lors de l'appel avec le mot-clé confirm."""
        from unittest.mock import AsyncMock
        from commands.game.hack import Hack
        bot = MagicMock()
        bot.wait_until_ready = AsyncMock()
        cog = Hack(bot)
        cog.check_pvp_loop.cancel()
        cog._invoke = AsyncMock()

        ctx = MagicMock()
        ctx.author.id = 1111

        # Appel avec 'confirm' dans les arguments
        await cog.prefix_hack.callback(cog, ctx, "654321", "200", "mining", "confirm")
        cog._invoke.assert_awaited_once_with(
            ctx, "hack",
            secret_id="654321",
            attack_points=200,
            zone="mining",
            confirm=True,
        )

        # Appel sans 'confirm'
        cog._invoke.reset_mock()
        await cog.prefix_hack.callback(cog, ctx, "654321", "200", "attack")
        cog._invoke.assert_awaited_once_with(
            ctx, "hack",
            secret_id="654321",
            attack_points=200,
            zone="attack",
            confirm=False,
        )


class TestPvPLogger(unittest.IsolatedAsyncioTestCase):
    """Vérifie la mise en forme du log public de PvP."""

    async def test_logger_pvp_attack(self):
        """Vérifie que log_pvp_attack formate correctement le message avec l'attaquant et les points d'attaque."""
        from unittest.mock import AsyncMock
        from utils.logger import Logger
        bot = MagicMock()
        logger = Logger(bot)
        logger._send_embed = AsyncMock()

        await logger.log_pvp_attack(attacker=1111, attack_points=500, attacker_name="ShadowHacker")
        logger._send_embed.assert_awaited_once()
        args = logger._send_embed.call_args[0]
        self.assertEqual(args[0], "public")
        embed = args[1]
        self.assertIn("500 ATK", embed.description)
        self.assertIn("ShadowHacker", embed.description)
        self.assertIn("1111", embed.description)

    async def test_hack_started_logs_public_attack(self):
        """Vérifie que _send publie le log public de PvP immédiatement lors du hack_started."""
        from unittest.mock import AsyncMock
        from commands.game.hack import Hack
        bot = MagicMock()
        bot.wait_until_ready = AsyncMock()
        mock_logger = MagicMock()
        mock_logger.log_pvp_attack = AsyncMock()
        bot.discord_logger = mock_logger

        cog = Hack(bot)
        cog.check_pvp_loop.cancel()

        ctx = MagicMock()
        ctx.author.id = 12345
        ctx.send = AsyncMock()
        ctx.interaction = None

        started_result = {
            'hack_started': True,
            'target_id': 67890,
            'attack_points': 1500,
            'target_zone': 'mining',
            'timestamp': 1700000000,
        }

        await cog._send(ctx, 'hack', started_result)
        mock_logger.log_pvp_attack.assert_awaited_once_with(ctx.author, 1500)


if __name__ == "__main__":
    unittest.main()


