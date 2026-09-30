"""
Tests unitaires pour le cycle de développement, correctifs et bibliothèque PvP V2 (Étape 4).

Valide :
- La génération d'empreintes uniques avec gestion de collision.
- La formule pure de ralentissement défensif avec plafond.
- Le calcul des devis (coûts RTM, durées, puissance consommée).
- La concurrence des canaux (offense et defense simultanés, 1 max par canal).
- L'héritage d'empreinte lors de la compilation depuis un dossier source.
- L'installation idempotente des correctifs (patches).
- La livraison persistante et unique des jobs échus par le worker.
- L'enregistrement des nouvelles actions dans RootService.
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock

from game.game_error import GameError
from game.math_config import MathConfig
from game.pvp_v2_dev import (
    generate_unique_fingerprint,
    compute_defensive_slowdown,
    calculate_dev_quote,
    PvpV2DevService,
)
from tests.test_pvp_v2_db import MockPvpV2Transaction


class MockDevTransaction(MockPvpV2Transaction):
    """Extension de MockPvpV2Transaction avec table players pour tester PvpV2DevService."""

    def __init__(self, now=None):
        super().__init__(now=now)
        self.players = {}

    def add_player(self, discord_id: int, **fields):
        base = {
            'discord_id': int(discord_id),
            'dollars': Decimal('1000.00'),
            'rootium': Decimal('1.00000'),
            'firewall_level': 1,
            'infrastructure_level': 1,
            'mining_t1': 1,
            'attack_t1': 2,       # 2 * 10 = 20 bits/s
            'attack_t2': 0,
            'attack_t3': 0,
            'attack_t4': 0,
            'attack_t5': 0,
            'bay_defense_t1': 2,  # 2 * 10 = 20 DEF
            'bay_defense_t2': 0,
            'bay_defense_t3': 0,
            'bay_defense_t4': 0,
            'bay_defense_t5': 0,
            'lang': 'fr',
        }
        base.update(fields)
        self.players[int(discord_id)] = base
        return base

    def one(self, query: str, params=()):
        q = " ".join(query.split()).upper()
        if "FROM PLAYERS WHERE DISCORD_ID" in q or "FROM PLAYERS WHERE DISCORD_ID = %S" in q:
            pid = int(params[0])
            return self.players.get(pid)
        return super().one(query, params)

    def execute(self, query: str, params=()):
        q = " ".join(query.split()).upper()
        if "UPDATE PLAYERS SET ROOTIUM" in q:
            # UPDATE players SET rootium = rootium - %s WHERE discord_id = %s ...
            amount = Decimal(str(params[0]))
            pid = int(params[1])
            if pid in self.players:
                self.players[pid]['rootium'] = amount
            return 1
        return super().execute(query, params)


class TestFingerprintGeneration(unittest.TestCase):
    """Test de la génération d'empreinte courte unique."""

    def setUp(self):
        self.tx = MockDevTransaction()

    def test_fingerprint_format_and_alphabet(self):
        """L'empreinte fait 4 caractères issus de l'alphabet autorisé."""
        fp_cfg = MathConfig.get_pvp_v2_fingerprint()
        alphabet = set(fp_cfg['alphabet'])
        fp = generate_unique_fingerprint(self.tx, 'hostile_miner')
        self.assertEqual(len(fp), 4)
        for char in fp:
            self.assertIn(char, alphabet)

    def test_fingerprint_retries_on_collision(self):
        """Si une collision est détectée, le générateur réessaie et trouve une empreinte libre."""
        # Pré-remplir un dossier avec 'K7M2'
        self.tx.research_folders.append({
            'id': 1, 'owner_id': 100, 'channel': 'offense',
            'family': 'hostile_miner', 'tier': 1, 'fingerprint': 'K7M2',
            'created_at': self.tx.now,
        })
        with patch('secrets.choice', side_effect=['K', '7', 'M', '2', 'P', '3', 'R', 'X']):
            fp = generate_unique_fingerprint(self.tx, 'hostile_miner')
            self.assertEqual(fp, 'P3RX')

    def test_fingerprint_collision_exhaustion_raises(self):
        """Si toutes les tentatives échouent (10 collisions), GameError('fingerprint_collision') est levée."""
        self.tx.research_folders.append({
            'id': 1, 'owner_id': 100, 'channel': 'offense',
            'family': 'hostile_miner', 'tier': 1, 'fingerprint': 'AAAA',
            'created_at': self.tx.now,
        })
        with patch('secrets.choice', return_value='A'):
            with self.assertRaises(GameError) as cm:
                generate_unique_fingerprint(self.tx, 'hostile_miner')
            self.assertEqual(cm.exception.key, 'fingerprint_collision')


class TestDefensiveSlowdown(unittest.TestCase):
    """Test du calcul pur du ralentissement défensif (Décision 13)."""

    def test_slowdown_no_defense(self):
        """0 défense -> durée inchangée (1.0x)."""
        dur = compute_defensive_slowdown(0, 1000)
        self.assertEqual(dur, 1000)

    def test_slowdown_decision_13_example(self):
        """Exemple du game design : 250 défense avec diviseur 500 -> 1.5x."""
        # 45 min = 2700s. 2700 * 1.5 = 4050s = 67.5 min
        dur = compute_defensive_slowdown(250, 2700)
        self.assertEqual(dur, 4050)

    def test_slowdown_capped_at_max_multiplier(self):
        """Une défense massive (10 000 DEF) est plafonnée à 10x."""
        dur = compute_defensive_slowdown(10000, 2700)
        self.assertEqual(dur, 27000)


class TestDevQuotes(unittest.TestCase):
    """Test du calcul des devis de développement."""

    def setUp(self):
        self.tx = MockDevTransaction()
        self.player = self.tx.add_player(1001, attack_t1=2, bay_defense_t1=2)
        self.stats = MathConfig.calculate_player_stats(self.player)

    def test_offensive_quote_research(self):
        """Devis de recherche offensive T1."""
        quote = calculate_dev_quote(self.player, self.stats, 'research', 'hostile_miner', 1)
        self.assertEqual(quote['channel'], 'offense')
        self.assertEqual(quote['power'], 10)  # 2 * 5 = 10 bits/s
        self.assertEqual(quote['rtm_cost'], Decimal('0.001'))
        self.assertGreater(quote['duration_seconds'], 0)

    def test_offensive_quote_requires_attack_modules(self):
        """Impossible de lancer une recherche offensive sans modules d'attaque."""
        p_no_atk = self.tx.add_player(1002, attack_t1=0)
        stats = MathConfig.calculate_player_stats(p_no_atk)
        with self.assertRaises(GameError) as cm:
            calculate_dev_quote(p_no_atk, stats, 'research', 'hostile_miner', 1)
        self.assertEqual(cm.exception.key, 'no_attack_module')

    def test_defensive_quote_requires_defense_modules(self):
        """Impossible de lancer un correctif défensif sans modules de défense de baie."""
        p_no_def = self.tx.add_player(1003, bay_defense_t1=0)
        stats = MathConfig.calculate_player_stats(p_no_def)
        with self.assertRaises(GameError) as cm:
            calculate_dev_quote(p_no_def, stats, 'patch_research', 'hostile_miner', 1)
        self.assertEqual(cm.exception.key, 'no_defense_module')


class TestDevJobWorkflowAndConcurrency(unittest.TestCase):
    """Test du cycle de vie des jobs et de la concurrence entre canaux."""

    def setUp(self):
        self.tx = MockDevTransaction()
        self.pid = 2001
        self.player = self.tx.add_player(self.pid, rootium=Decimal('0.10000'), attack_t1=2, bay_defense_t1=2)

    def test_start_offensive_job_debits_rtm(self):
        """Lancer une recherche offensive débite le RTM et enregistre le job."""
        initial_rtm = self.player['rootium']
        res = PvpV2DevService.start_job(self.tx, self.pid, 'research', 'hostile_miner', 1)
        self.assertEqual(res['status'], 'started')
        self.assertEqual(self.player['rootium'], initial_rtm - Decimal('0.001'))
        self.assertEqual(len(self.tx.dev_jobs), 1)
        self.assertEqual(self.tx.dev_jobs[0]['channel'], 'offense')

    def test_simultaneous_offense_and_defense_jobs_allowed(self):
        """Un joueur peut avoir simultanément 1 job offensif et 1 job défensif."""
        PvpV2DevService.start_job(self.tx, self.pid, 'research', 'hostile_miner', 1)
        PvpV2DevService.start_job(self.tx, self.pid, 'patch_research', 'hostile_miner', 1)
        self.assertEqual(len(self.tx.dev_jobs), 2)
        channels = {j['channel'] for j in self.tx.dev_jobs}
        self.assertEqual(channels, {'offense', 'defense'})

    def test_two_jobs_on_same_channel_forbidden(self):
        """Deux jobs sur le même canal sont interdits (channel_busy)."""
        PvpV2DevService.start_job(self.tx, self.pid, 'research', 'hostile_miner', 1)
        with self.assertRaises(GameError) as cm:
            PvpV2DevService.start_job(self.tx, self.pid, 'research', 'ransomware', 1)
        self.assertEqual(cm.exception.key, 'channel_busy')

    def test_cannot_research_already_owned_folder(self):
        """Impossible de relancer une recherche si le dossier est déjà détenu."""
        # Créer dossier existant
        self.tx.research_folders.append({
            'id': 1, 'owner_id': self.pid, 'channel': 'offense',
            'family': 'hostile_miner', 'tier': 1, 'fingerprint': 'K7M2',
            'created_at': self.tx.now,
        })
        with self.assertRaises(GameError) as cm:
            PvpV2DevService.start_job(self.tx, self.pid, 'research', 'hostile_miner', 1)
        self.assertEqual(cm.exception.key, 'research_already_completed')

    def test_cannot_compile_without_source_folder(self):
        """Impossible de compiler une copie sans détenir le dossier de recherche source."""
        with self.assertRaises(GameError) as cm:
            PvpV2DevService.start_job(self.tx, self.pid, 'compile', 'hostile_miner', 1)
        self.assertEqual(cm.exception.key, 'research_folder_required')

    def test_compile_inherits_fingerprint_from_folder(self):
        """Compiler une copie hérite exactement de l'empreinte du dossier source."""
        self.tx.research_folders.append({
            'id': 1, 'owner_id': self.pid, 'channel': 'offense',
            'family': 'hostile_miner', 'tier': 1, 'fingerprint': 'K7M2',
            'created_at': self.tx.now,
        })
        res = PvpV2DevService.start_job(self.tx, self.pid, 'compile', 'hostile_miner', 1)
        self.assertEqual(res['job']['fingerprint'], 'K7M2')

    def test_insufficient_rootium_rejected(self):
        """Solde RTM insuffisant bloque le lancement du job."""
        self.player['rootium'] = Decimal('0.00000')
        with self.assertRaises(GameError) as cm:
            PvpV2DevService.start_job(self.tx, self.pid, 'research', 'hostile_miner', 1)
        self.assertEqual(cm.exception.key, 'insufficient_rootium')

    def test_cancel_job_frees_channel(self):
        """Annuler un job supprime la ligne et libère le canal."""
        PvpV2DevService.start_job(self.tx, self.pid, 'research', 'hostile_miner', 1)
        self.assertEqual(len(self.tx.dev_jobs), 1)
        PvpV2DevService.cancel_job(self.tx, self.pid, 'offense')
        self.assertEqual(len(self.tx.dev_jobs), 0)
        # Peut maintenant relancer
        res = PvpV2DevService.start_job(self.tx, self.pid, 'research', 'hostile_miner', 1)
        self.assertEqual(res['status'], 'started')


class TestDevDelivery(unittest.TestCase):
    """Test de la livraison persistante des jobs par le worker."""

    def setUp(self):
        self.tx = MockDevTransaction()
        self.pid = 3001
        self.tx.add_player(self.pid)

    def test_deliver_research_creates_folder_and_deletes_job(self):
        """La livraison d'une recherche crée le dossier et supprime le job."""
        job = {
            'id': 10,
            'player_id': self.pid,
            'channel': 'offense',
            'job_type': 'research',
            'family': 'hostile_miner',
            'tier': 2,
            'fingerprint': None,
        }
        self.tx.dev_jobs.append(dict(job))
        res = PvpV2DevService.deliver_job(self.tx, job)
        self.assertTrue(res['delivered'])
        self.assertEqual(len(res['fingerprint']), 4)
        self.assertEqual(len(self.tx.dev_jobs), 0)
        self.assertEqual(len(self.tx.research_folders), 1)
        self.assertEqual(self.tx.research_folders[0]['fingerprint'], res['fingerprint'])

    def test_deliver_compile_creates_software_copy(self):
        """La livraison d'une compilation crée la copie de logiciel avec la même empreinte."""
        job = {
            'id': 11,
            'player_id': self.pid,
            'channel': 'offense',
            'job_type': 'compile',
            'family': 'hostile_miner',
            'tier': 1,
            'fingerprint': 'K7M2',
        }
        self.tx.dev_jobs.append(dict(job))
        res = PvpV2DevService.deliver_job(self.tx, job)
        self.assertTrue(res['delivered'])
        self.assertEqual(res['fingerprint'], 'K7M2')
        self.assertEqual(len(self.tx.dev_jobs), 0)
        self.assertEqual(len(self.tx.software_copies), 1)
        self.assertEqual(self.tx.software_copies[0]['fingerprint'], 'K7M2')
        self.assertEqual(self.tx.software_copies[0]['origin'], 'compiled')


class TestPatchInstallation(unittest.TestCase):
    """Test de l'installation idempotente des patchs."""

    def setUp(self):
        self.tx = MockDevTransaction()
        self.pid = 4001
        self.tx.add_player(self.pid)

    def test_install_patch_success(self):
        """Installer un patch non installé le marque comme installed=1."""
        self.tx.patches.append({
            'id': 50,
            'owner_id': self.pid,
            'family': 'hostile_miner',
            'fingerprint': 'K7M2',
            'installed': 0,
            'reserved': 0,
            'created_at': self.tx.now,
        })
        res = PvpV2DevService.install_patch(self.tx, self.pid, patch_id=50)
        self.assertEqual(res['status'], 'installed')
        self.assertEqual(self.tx.patches[0]['installed'], 1)

    def test_install_patch_idempotent(self):
        """Installer deux fois le même patch retourne already_installed sans erreur."""
        self.tx.patches.append({
            'id': 51,
            'owner_id': self.pid,
            'family': 'hostile_miner',
            'fingerprint': 'K7M2',
            'installed': 1,
            'reserved': 0,
            'created_at': self.tx.now,
        })
        res = PvpV2DevService.install_patch(self.tx, self.pid, patch_id=51)
        self.assertEqual(res['status'], 'already_installed')
        self.assertTrue(res.get('idempotent'))


class TestRootServiceActions(unittest.TestCase):
    """Vérifie l'enregistrement des actions V2 sur RootService."""

    def test_actions_registered_in_root_service(self):
        """Toutes les actions requises de l'étape 4 figurent dans RootService.ACTIONS."""
        from game.root_service import RootService
        required_actions = {
            'pvp_v2_dev_quote',
            'pvp_v2_start_job',
            'pvp_v2_cancel_job',
            'pvp_v2_install_patch',
            'pvp_v2_library',
        }
        for act in required_actions:
            self.assertIn(act, RootService.ACTIONS, f"Action {act} absente de RootService.ACTIONS")


class TestCompilePrefixCommands(unittest.IsolatedAsyncioTestCase):
    """Vérifie le comportement de la commande préfixe !dev et de son lexique."""

    def _make_cog(self):
        from commands.game.compile import Compile
        bot = MagicMock()
        bot.wait_until_ready = AsyncMock()
        cog = object.__new__(Compile)
        cog.bot = bot
        cog._prefetch_lang = AsyncMock()
        cog._send_embed = AsyncMock()
        cog._invoke = AsyncMock()
        return cog, bot

    async def test_prefix_dev_invokes_help_not_library(self):
        """!dev sans sous-commande affiche le lexique d'aide et n'appelle pas la bibliothèque."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.author.id = 1234
        ctx.prefix = '!'

        cog._send_dev_help = AsyncMock()
        await cog.prefix_dev.callback(cog, ctx)

        cog._send_dev_help.assert_awaited_once_with(ctx)
        cog._invoke.assert_not_called()

    async def test_prefix_dev_help_command(self):
        """!dev help affiche également le lexique complet."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.author.id = 1234
        ctx.prefix = '!'

        cog._send_dev_help = AsyncMock()
        await cog.prefix_dev_help.callback(cog, ctx)

        cog._send_dev_help.assert_awaited_once_with(ctx)
        cog._invoke.assert_not_called()

    async def test_send_dev_help_renders_embed_with_syntax(self):
        """_send_dev_help génère un embed 'dev' contenant le guide, les types de jobs et les canaux."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.author.id = 1234
        ctx.prefix = '!'
        ctx.guild = None

        await cog._send_dev_help(ctx)

        cog._send_embed.assert_awaited_once()
        call_args = cog._send_embed.await_args[0]
        action = call_args[1]
        content = call_args[2]

        self.assertEqual(action, 'dev')
        self.assertIn('research', content)
        self.assertIn('compile', content)
        self.assertIn('patch_research', content)
        self.assertIn('patch_compile', content)
        self.assertIn('offense', content)
        self.assertIn('defense', content)


if __name__ == '__main__':
    unittest.main()
