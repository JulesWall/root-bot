"""
Tests unitaires pour le mode Bêta et le bonus de minage lié à la réputation :
- Activation et détection du mode Bêta (variable d'environnement).
- Chargement, tolérance aux pannes et sauvegarde atomique de « beta access.json ».
- Contrôle d'accès : OP et membres autorisés, blocage des utilisateurs ordinaires.
- Priorité stricte de la maintenance (OP et rôle dédié ont accès, l'accès bêta ne contourne pas).
- Exception /network : création de profil et consultation autorisées sans accès bêta.
- Invitation par réputation : ajout automatique dans beta access.json et confirmation.
- Bypass du cooldown de 24h de réputation pour les OP.
- Bonus de minage par réputation : multiplicateur 1 + (rep * 0.005), additif, actif même hors bêta.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from game.db.players import Player
from game.game_error import GameError
from game.math_config import MathConfig
from utils.check import Check
import utils.check


class MockTransaction:
    """Mock léger de transaction de base de données pour tester la réputation et le minage."""

    def __init__(self, now=None):
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        self.players = {}
        self.queries = []

    def one(self, query: str, params=()):
        q = " ".join(query.split()).upper()
        if "SELECT * FROM PLAYERS WHERE DISCORD_ID" in q:
            uid = int(params[0])
            p = self.players.get(uid)
            return dict(p) if p else None
        return None

    def all(self, query: str, params=()):
        return []

    def execute(self, query: str, params=()):
        self.queries.append((query, params))
        q = " ".join(query.split()).upper()
        if q.startswith("UPDATE PLAYERS SET"):
            uid = int(params[-1])
            if uid in self.players:
                # Analyse basique des colonnes
                set_part = query.split("SET", 1)[1].split("WHERE", 1)[0]
                cols = [c.strip().split("=")[0] for c in set_part.split(",")]
                for col, val in zip(cols, params[:-1]):
                    self.players[uid][col] = val


class TestBetaAccessCheck(unittest.IsolatedAsyncioTestCase):
    """Teste les vérifications d'habilitation et la gestion de beta access.json."""

    def setUp(self):
        Check._beta_access_cache = None
        self.orig_beta_mode = os.environ.get("BETA_MODE")
        self.orig_beta = os.environ.get("BETA")
        self.orig_maint = os.environ.get("MAINTENANCE")

    def tearDown(self):
        Check._beta_access_cache = None
        if self.orig_beta_mode is not None:
            os.environ["BETA_MODE"] = self.orig_beta_mode
        else:
            os.environ.pop("BETA_MODE", None)
        if self.orig_beta is not None:
            os.environ["BETA"] = self.orig_beta
        else:
            os.environ.pop("BETA", None)
        if self.orig_maint is not None:
            os.environ["MAINTENANCE"] = self.orig_maint
        else:
            os.environ.pop("MAINTENANCE", None)

    def test_beta_enabled_detection(self):
        """Vérifie l'activation/désactivation du mode bêta via variable d'environnement."""
        check = Check()
        for true_val in ["1", "true", "yes", "TRUE", "Yes "]:
            os.environ["BETA_MODE"] = true_val
            self.assertTrue(check.beta_enabled(), f"Devrait être True pour '{true_val}'")
        for false_val in ["0", "false", "no", "", "other"]:
            os.environ["BETA_MODE"] = false_val
            self.assertFalse(check.beta_enabled(), f"Devrait être False pour '{false_val}'")

    def test_load_beta_access_missing_or_corrupt_file(self):
        """Vérifie qu'un fichier absent ou corrompu ne fait pas crasher et verrouille l'accès."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dummy_file = Path(tmpdir) / "beta access.json"
            with patch.object(utils.check, "_get_beta_access_file", return_value=dummy_file):
                check = Check()
                # 1. Fichier absent
                self.assertEqual(check.load_beta_access(), set())

                # 2. Fichier avec JSON corrompu
                Check._beta_access_cache = None
                dummy_file.write_text("{ ce n'est pas du json valide !!!", encoding="utf-8")
                self.assertEqual(check.load_beta_access(), set())

                # 3. Fichier avec contenu non-liste
                Check._beta_access_cache = None
                dummy_file.write_text(json.dumps({"test": 123}), encoding="utf-8")
                self.assertEqual(check.load_beta_access(), set())

    def test_grant_beta_access_atomic_and_no_duplicates(self):
        """Vérifie que l'ajout au fichier est atomique, sans doublon et permanent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "beta access.json"
            test_file.write_text(json.dumps([11111, 22222]) + "\n", encoding="utf-8")

            with patch.object(utils.check, "_get_beta_access_file", return_value=test_file):
                check = Check()
                # 1. Vérification chargement initial
                self.assertEqual(check.load_beta_access(), {11111, 22222})

                # 2. Ajout d'un joueur existant -> retourne False, pas de doublon
                self.assertFalse(check.grant_beta_access(11111))
                self.assertEqual(check.load_beta_access(), {11111, 22222})

                # 3. Ajout d'un nouveau joueur -> retourne True, persisté sur disque
                self.assertTrue(check.grant_beta_access(33333))
                self.assertIn(33333, check.load_beta_access())

                # Relecture brute du fichier pour vérifier la persistance
                saved = json.loads(test_file.read_text(encoding="utf-8"))
                self.assertEqual(saved, [11111, 22222, 33333])

    async def test_can_bypass_maintenance_includes_op(self):
        """Vérifie que les OP ont également accès en mode maintenance."""
        check = Check()
        bot = MagicMock()

        # Utilisateur OP -> bypass maintenance accordé
        check.is_op = AsyncMock(return_value=True)
        self.assertTrue(await check.can_bypass_maintenance(bot, 9999))

        # Utilisateur non OP mais rôle MAINTENANCE_BYPASS -> accordé
        check.is_op = AsyncMock(return_value=False)
        check._has_role = AsyncMock(return_value=True)
        self.assertTrue(await check.can_bypass_maintenance(bot, 8888))

        # Utilisateur quelconque -> refusé
        check.is_op = AsyncMock(return_value=False)
        check._has_role = AsyncMock(return_value=False)
        self.assertFalse(await check.can_bypass_maintenance(bot, 7777))

    async def test_has_beta_access_roles_and_file(self):
        """Vérifie que la liste bêta ET les OP disposent de l'accès bêta."""
        check = Check()
        bot = MagicMock()
        check.load_beta_access = MagicMock(return_value={1001, 1002})

        # Présent dans le fichier
        check.is_op = AsyncMock(return_value=False)
        self.assertTrue(await check.has_beta_access(bot, 1001))

        # Non présent dans le fichier mais rôle OP
        check.is_op = AsyncMock(return_value=True)
        self.assertTrue(await check.has_beta_access(bot, 9999))

        # Ni dans le fichier ni OP
        check.is_op = AsyncMock(return_value=False)
        self.assertFalse(await check.has_beta_access(bot, 5555))

    async def test_check_interaction_access_priorities(self):
        """Vérifie l'ordre de priorité : Banni > Maintenance > Bêta > OK."""
        check = Check()
        bot = MagicMock()
        interaction = MagicMock()
        interaction.user.id = 12345

        # 1. Banni
        check.is_banned = MagicMock(return_value=True)
        allowed, err = await check.check_interaction_access(bot, interaction)
        self.assertFalse(allowed)
        self.assertEqual(err, "no_permission")
        check.is_banned = MagicMock(return_value=False)

        # 2. Maintenance active sans bypass
        check.maintenance_enabled = MagicMock(return_value=True)
        check.can_bypass_maintenance = AsyncMock(return_value=False)
        allowed, err = await check.check_interaction_access(bot, interaction)
        self.assertFalse(allowed)
        self.assertEqual(err, "no_permission")

        # 3. Maintenance active avec bypass
        check.can_bypass_maintenance = AsyncMock(return_value=True)
        check.beta_enabled = MagicMock(return_value=False)
        allowed, err = await check.check_interaction_access(bot, interaction)
        self.assertTrue(allowed)

        # 4. Bêta active, joueur non autorisé, action ordinaire
        check.maintenance_enabled = MagicMock(return_value=False)
        check.beta_enabled = MagicMock(return_value=True)
        check.has_beta_access = AsyncMock(return_value=False)
        allowed, err = await check.check_interaction_access(bot, interaction, allow_network=False)
        self.assertFalse(allowed)
        self.assertEqual(err, "g_error_beta_access_required")

        # 5. Bêta active, joueur non autorisé, action autorisée (/network)
        allowed, err = await check.check_interaction_access(bot, interaction, allow_network=True)
        self.assertTrue(allowed)


class TestReputationMiningBonus(unittest.TestCase):
    """Teste le calcul additif et précis du bonus de minage lié à la réputation."""

    def test_reputation_mining_progression(self):
        """Vérifie la formule multiplicateur = 1 + (réputation * 0.005)."""
        now = datetime.now(timezone.utc)
        stats = {
            "total_hashrate_hs": 1000000,
            "total_ram_bytes": 100000000,
            "total_hashrate_formatted": "1.00 MH/s",
            "total_ram_formatted": "100 Mo",
        }

        # 0 point -> x1.0 (+0.0%)
        row_0 = {"reputation": 0, "mining_buffer": Decimal("0"), "mining_last_update_at": now}
        res_0 = MathConfig.compute_mining_progress(row_0, stats, now)
        self.assertEqual(res_0["reputation_points"], 0)
        self.assertEqual(res_0["reputation_multiplier"], Decimal("1.0"))
        self.assertEqual(res_0["reputation_bonus_pct"], Decimal("0.0"))

        # 1 point -> x1.005 (+0.5%)
        row_1 = {"reputation": 1, "mining_buffer": Decimal("0"), "mining_last_update_at": now}
        res_1 = MathConfig.compute_mining_progress(row_1, stats, now)
        self.assertEqual(res_1["reputation_multiplier"], Decimal("1.005"))
        self.assertEqual(res_1["rate_per_min"], res_0["base_rate_per_min"] * Decimal("1.005"))

        # 100 points -> x1.5 (+50.0%)
        row_100 = {"reputation": 100, "mining_buffer": Decimal("0"), "mining_last_update_at": now}
        res_100 = MathConfig.compute_mining_progress(row_100, stats, now)
        self.assertEqual(res_100["reputation_multiplier"], Decimal("1.500"))
        self.assertEqual(res_100["reputation_bonus_pct"], Decimal("50.0"))
        self.assertEqual(res_100["rate_per_min"], res_0["base_rate_per_min"] * Decimal("1.5"))

        # 200 points -> x2.0 (+100.0%)
        row_200 = {"reputation": 200, "mining_buffer": Decimal("0"), "mining_last_update_at": now}
        res_200 = MathConfig.compute_mining_progress(row_200, stats, now)
        self.assertEqual(res_200["reputation_multiplier"], Decimal("2.000"))
        self.assertEqual(res_200["reputation_bonus_pct"], Decimal("100.0"))
        self.assertEqual(res_200["rate_per_min"], res_0["base_rate_per_min"] * Decimal("2.0"))

    def test_claim_includes_reputation_bonus_and_credits_correctly(self):
        """Vérifie que Player.claim intègre le bonus de réputation et crédite le montant effectif."""
        tx = MockTransaction()
        # Tampon valide à mi-capacité, quelle que soit la RAM configurée.
        capacity = (Decimal(MathConfig.get_module_ram(5)) * 10
                    / Decimal(str(MathConfig.load()['mining']['bytes_per_rtm'])))
        stored = (capacity / 2).quantize(Decimal('0.00001'))
        tx.players[1234] = {
            "discord_id": 1234,
            "rootium": Decimal("10.00000"),
            "reputation": 100,  # +50% de bonus
            "mining_t5": 10,
            "mining_buffer": stored,
            "mining_last_update_at": tx.now,
            "mining_last_claim_at": tx.now - timedelta(minutes=10),
        }

        result = Player.claim(tx, 1234)
        self.assertTrue(result["claimed"])
        self.assertEqual(result["amount"], stored)
        self.assertEqual(result["reputation_points"], 100)
        self.assertEqual(result["reputation_bonus_pct"], Decimal("50.0"))
        self.assertEqual(result["new_rootium"], Decimal("10.00000") + stored)


class TestReputationInviteAndOpBypass(unittest.IsolatedAsyncioTestCase):
    """Teste l'attribution de réputation, le contournement OP et l'invitation bêta."""

    def test_op_bypasses_reputation_cooldown(self):
        """Vérifie qu'un OP avec bypass_cooldown=True peut donner une réputation malgré le cooldown."""
        tx = MockTransaction()
        giver_id = 9999
        target_id = 1111

        tx.players[giver_id] = {
            "discord_id": giver_id,
            "reputation": 5,
            "next_reputation_at": tx.now + timedelta(hours=12),  # En cooldown !
        }
        tx.players[target_id] = {
            "discord_id": target_id,
            "reputation": 0,
        }

        # Sans bypass -> GameError('cooldown')
        with self.assertRaises(GameError) as cm:
            Player.give_reputation(tx, giver_id, target_id, bypass_cooldown=False)
        self.assertEqual(cm.exception.key, "cooldown")

        # Avec bypass (OP bot) -> Réussite et pas de cooldown imposé à l'OP
        res = Player.give_reputation(tx, giver_id, target_id, bypass_cooldown=True)
        self.assertTrue(res["reputation_given"])
        self.assertTrue(res["bypassed_cooldown"])
        self.assertEqual(tx.players[target_id]["reputation"], 1)

    async def test_rep_cog_invites_recipient_during_beta(self):
        """Vérifie que la commande /rep inscrit le destinataire dans beta access.json pendant la bêta."""
        from commands.game.rep import Rep

        bot = MagicMock()
        cog = Rep(bot)

        ctx = MagicMock()
        ctx.author.id = 9999
        ctx.guild.name = "Test Guild"
        ctx.interaction = None
        ctx.send = AsyncMock()

        result = {"reputation_given": True, "giver": 9999, "recipient": 1234, "points": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "beta access.json"
            test_file.write_text("[]\n", encoding="utf-8")

            with patch.object(utils.check, "_get_beta_access_file", return_value=test_file):
                Check._beta_access_cache = None
                with patch.object(Check, "beta_enabled", return_value=True):
                    with patch.object(Check, "has_beta_access", new=AsyncMock(return_value=True)):
                        await cog._send(ctx, "reputation", result)

                        # Le destinataire 1234 doit désormais figurer dans beta access.json
                        check = Check()
                        self.assertIn(1234, check.load_beta_access())

                        # Le message de réponse doit contenir l'annonce d'accès accordé
                        ctx.send.assert_awaited_once()
                        sent_content = ctx.send.call_args[0][0]
                        self.assertIn("1234", sent_content)


if __name__ == "__main__":
    unittest.main()
