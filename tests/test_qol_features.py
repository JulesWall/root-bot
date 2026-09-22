"""
Tests unitaires pour les améliorations QOL :
- Chantier A : Boutons d'action rapide & alerte RAM saturée sur /network
- Chantier B : Riposte autorisée sur /network avec règles strictes d'anonymat
- Chantier C : Catalogue interactif intégré à !buy / /buy (15 options T1 à T5 avec stats et utilités)
- Chantier D : Soldes restants affichés dans les devis (/buy, /upgrade, /scan, /convert)
"""

import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

import discord

from commands.game.buy import Buy, _get_shop_options, _get_purchasable_options, ShopCatalogView, ShopSelectView
from commands.game.network import Network, NetworkActionView
from game.db.consequence import ConsequenceDB
from game.db.players import Player, _calculate_module_price
from utils.text import format_usd
from game.math_config import MathConfig
from lang import game_en, game_fr
import time
from utils.language_manager import _cache


class MockTransaction:
    """Mock léger de transaction SQL pour tester les méthodes métier."""

    def __init__(self, now=None):
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        self.players = {}
        self.consequences = []
        self.hacks = []
        self.upgrades = []

    def one(self, query: str, params=()):
        q = " ".join(query.split()).upper()
        if "SELECT * FROM PLAYERS WHERE DISCORD_ID" in q:
            uid = int(params[0])
            p = self.players.get(uid)
            return dict(p) if p else None
        if "SELECT 1 FROM CONSEQUENCE WHERE VICTIM_ID = %S AND ATTACKER_ID = %S AND DELETE_AT > %S" in q:
            vid, aid, now = int(params[0]), int(params[1]), params[2]
            for c in self.consequences:
                if c["victim_id"] == vid and c["attacker_id"] == aid and c["delete_at"] > now:
                    return {"1": 1}
            return None
        if "SELECT * FROM UPGRADES WHERE DISCORD_ID" in q:
            return None
        if "SELECT * FROM HACK WHERE DISCORD_ID" in q:
            return None
        return None

    def all(self, query: str, params=()):
        q = " ".join(query.split()).upper()
        if "SELECT ATTACKER_ID, DELETE_AT FROM CONSEQUENCE" in q:
            vid, now = int(params[0]), params[1]
            return [
                {"attacker_id": c["attacker_id"], "delete_at": c["delete_at"]}
                for c in self.consequences
                if c["victim_id"] == vid and c["delete_at"] > now
            ]
        return []

    def execute(self, query: str, params=()):
        return 1


class TestNetworkQOL(unittest.IsolatedAsyncioTestCase):
    """Tests des fonctionnalités de /network (Chantiers A et B)."""

    def setUp(self):
        _cache[10001] = ('fr', time.monotonic() + 3600)
        self.bot = MagicMock()
        self.cog = Network(self.bot)
        self.mock_ctx = MagicMock()
        self.mock_ctx.author.id = 10001
        self.mock_ctx.author.display_name = "PlayerOne"
        self.mock_ctx.interaction = None

    def tearDown(self):
        self.cog.cog_unload()
        _cache.pop(10001, None)

    def test_ram_saturation_alert(self):
        """Si la RAM est saturée (>=100%), la couleur passe à l'orange et la bannière apparaît."""
        base_result = {
            "discord_id": 10001,
            "dollars": Decimal("200.00"),
            "rootium": Decimal("5.00000"),
            "firewall_level": 1,
            "reputation": 0,
            "secret_id": "999001",
            "secret_next_ts": 1700000000,
        }

        # 1. Non saturé (50%)
        result_normal = dict(base_result)
        result_normal["mining_state"] = {
            "buffer": Decimal("0.00050"),
            "memory_pct": 50.0,
            "rate_per_min": Decimal("0.00010"),
            "memory_used_formatted": "100 o",
            "total_ram_formatted": "200 o",
            "is_full": False,
            "seconds_to_fill_total": 60,
        }
        embed_normal = self.cog._build_network_embed(self.mock_ctx, result_normal)
        self.assertEqual(embed_normal.color.value, discord.Color.from_rgb(0, 220, 200).value)
        total_field_normal = embed_normal.fields[5].value
        self.assertNotIn("MÉMOIRE PLEINE", total_field_normal)

        # 2. Saturé (100%)
        result_full = dict(base_result)
        result_full["mining_state"] = {
            "buffer": Decimal("0.00100"),
            "memory_pct": 100.0,
            "rate_per_min": Decimal("0.00010"),
            "memory_used_formatted": "200 o",
            "total_ram_formatted": "200 o",
            "is_full": True,
            "seconds_to_fill_total": 0,
        }
        embed_full = self.cog._build_network_embed(self.mock_ctx, result_full)
        self.assertEqual(embed_full.color.value, discord.Color.from_rgb(255, 170, 0).value)
        total_field_full = embed_full.fields[5].value
        self.assertIn("MÉMOIRE PLEINE (100%)", total_field_full)

    async def test_network_action_view_button_states(self):
        """Vérifie l'état des boutons de Récolte et d'Actualisation selon le buffer."""
        # Buffer vide -> bouton Récolter désactivé
        res_empty = {"mining_state": {"buffer": Decimal("0.00000")}}
        view_empty = NetworkActionView(self.cog, self.mock_ctx, res_empty)
        claim_btn_empty = view_empty.children[0]
        self.assertTrue(claim_btn_empty.disabled)
        self.assertEqual(claim_btn_empty.style, discord.ButtonStyle.secondary)

        # Buffer positif -> bouton Récolter activé avec le montant
        res_full = {"mining_state": {"buffer": Decimal("0.00420")}}
        view_full = NetworkActionView(self.cog, self.mock_ctx, res_full)
        claim_btn_full = view_full.children[0]
        self.assertFalse(claim_btn_full.disabled)
        self.assertEqual(claim_btn_full.style, discord.ButtonStyle.success)
        self.assertIn("0.00420 RTM", claim_btn_full.label)

        # Bouton Actualiser toujours présent et primaire
        refresh_btn = view_full.children[1]
        self.assertFalse(refresh_btn.disabled)
        self.assertEqual(refresh_btn.style, discord.ButtonStyle.primary)

    async def test_network_claim_button_logs_blockchain_and_moderation(self):
        """Vérifie que cliquer sur le bouton de Récolte sous le profil déclenche les logs blockchain et modération."""
        res_full = {"mining_state": {"buffer": Decimal("0.00500")}}
        view = NetworkActionView(self.cog, self.mock_ctx, res_full)

        mock_interaction = AsyncMock()
        mock_interaction.user.id = 10001
        mock_interaction.author = None
        mock_interaction.guild = MagicMock()
        mock_interaction.guild.id = 9999
        mock_interaction.guild.name = "Root City"
        mock_interaction.message = AsyncMock()

        claim_payload = {
            "claimed": True,
            "amount": Decimal("0.00500"),
            "new_rootium": Decimal("15.00500"),
            "rate_per_min": Decimal("0.00010"),
            "total_ram_formatted": "100 Ko",
            "seconds_since_last_claim": 1200,
        }
        net_payload = {
            "discord_id": 10001,
            "dollars": Decimal("100"),
            "rootium": Decimal("15.00500"),
            "firewall_level": 1,
            "secret_id": "000001",
            "secret_next_ts": 1700000000,
            "mining_state": {"buffer": Decimal("0")},
        }

        self.cog.service.execute = AsyncMock(side_effect=[claim_payload, net_payload])

        mock_logger = AsyncMock()
        self.cog.bot.discord_logger = mock_logger

        with patch("commands.game.network.Check.check_interaction_access", new=AsyncMock(return_value=(True, ""))):
            await view._on_claim(mock_interaction)

        # Vérifie l'envoi du toast de récolte
        mock_interaction.followup.send.assert_awaited()

        # Vérifie le log blockchain
        mock_logger.log_blockchain_transaction.assert_awaited_once_with(
            from_id="0xROOTIUM_MINING_POOL",
            to_address="10001",
            rtm_amount=Decimal("0.00500"),
        )

        # Vérifie le log de modération
        mock_logger.log_claim.assert_awaited_once_with(
            mock_interaction,
            Decimal("0.00500"),
            new_rootium=Decimal("15.00500"),
            rate=Decimal("0.00010"),
            ram_total="100 Ko",
            seconds_since_last_claim=1200,
        )

    def test_retaliation_displayed_in_all_firewall_levels(self):
        """Les représailles apparaissent dans tous les cas avec agresseur identifié."""
        expiry = datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc)
        retaliation = [{"attacker_id": 99999, "delete_at": expiry}]

        base_res = {
            "discord_id": 10001,
            "dollars": Decimal("100"),
            "rootium": Decimal("1"),
            "secret_id": "999001",
            "secret_next_ts": 1700000000,
            "retaliations": retaliation,
        }

        # Quel que soit le pare-feu (ex: niv 1, 2, 3, 4), l'agresseur est affiché
        for fw in (1, 2, 3, 4, 5):
            res_fw = dict(base_res, firewall_level=fw)
            embed_fw = self.cog._build_network_embed(self.mock_ctx, res_fw)
            atk_val = embed_fw.fields[3].value
            self.assertIn("Riposte autorisée", atk_val)
            self.assertIn("<@99999>", atk_val)
            self.assertIn("expire dans", atk_val)

    def test_pending_scan_display(self):
        """Un scan en cours est affiché dans le champ offensif."""
        exp = datetime(2026, 9, 18, 17, 30, tzinfo=timezone.utc)
        res = {
            "discord_id": 10001,
            "dollars": Decimal("100"),
            "rootium": Decimal("1"),
            "firewall_level": 1,
            "secret_id": "999001",
            "secret_next_ts": 1700000000,
            "pending_scan": {
                "target_id": 77777,
                "expires_at": exp,
            },
        }
        embed = self.cog._build_network_embed(self.mock_ctx, res)
        atk_val = embed.fields[3].value
        self.assertIn("Scan en cours", atk_val)
        self.assertIn("<@77777>", atk_val)

    def test_network_displays_higher_tier_bay_if_owned(self):
        """Si un joueur possède un module de tier supérieur non encore achetable (ex: via /hack), la baie s'affiche."""
        player_data = {
            "discord_id": 10001,
            "dollars": Decimal("100"),
            "rootium": Decimal("1"),
            "firewall_level": 0,  # FW 0 : normalement seule la baie 1 est débloquée
            "secret_id": "999001",
            "secret_next_ts": 1700000000,
            "mining_t1": 1,
            "mining_t4": 1,       # Module T4 capturé en PvP !
        }
        stats = MathConfig.calculate_player_stats(player_data)
        mining_state = MathConfig.compute_mining_progress(player_data, stats, datetime.now(timezone.utc))
        res = dict(player_data, stats=stats, mining_state=mining_state)

        embed = self.cog._build_network_embed(self.mock_ctx, res)
        bays_field = next(f for f in embed.fields if "Baie" in f.value)
        self.assertIn("Baie 01", bays_field.value)
        self.assertIn("Baie 04", bays_field.value)


class TestBuyCatalogAndShop(unittest.IsolatedAsyncioTestCase):
    """Tests du catalogue interactif et de la boutique (Chantier C)."""

    def setUp(self):
        _cache[10001] = ('fr', time.monotonic() + 3600)
        self.bot = MagicMock()
        self.cog = Buy(self.bot)
        self.mock_ctx = MagicMock()
        self.mock_ctx.author.id = 10001
        self.mock_ctx.author = MagicMock()
        self.mock_ctx.author.id = 10001
        self.mock_ctx.interaction = None
        self.mock_ctx.clean_prefix = "!"
        self.mock_ctx.prefix = "!"

    def tearDown(self):
        _cache.pop(10001, None)

    def test_shop_options_generation(self):
        """Le sélecteur génère exactement 15 options (5 minage, 5 attaque, 5 défense)."""
        options = _get_shop_options(self.mock_ctx)
        self.assertEqual(len(options), 15)

        mining_opts = [o for o in options if o.value.startswith("mining:")]
        attack_opts = [o for o in options if o.value.startswith("attack:")]
        defense_opts = [o for o in options if o.value.startswith("defense:")]

        self.assertEqual(len(mining_opts), 5)
        self.assertEqual(len(attack_opts), 5)
        self.assertEqual(len(defense_opts), 5)

        # Vérifier la présence des emojis et labels
        self.assertIn("Minage T1", mining_opts[0].label)
        self.assertIn("Attaque T1", attack_opts[0].label)
        self.assertIn("Défense T1", defense_opts[0].label)

    def test_purchasable_options_filtering(self):
        """Le sélecteur filtre strictement selon les fonds et le pare-feu du joueur."""
        # Joueur sans le sou et sans pare-feu
        poor_player = {"dollars": Decimal("0"), "rootium": Decimal("0"), "firewall_level": 0}
        poor_opts = _get_purchasable_options(self.mock_ctx, "mining", poor_player)
        self.assertEqual(len(poor_opts), 0)

        # Budget exactement égal au prix d'un T1, avec FW 0.
        t1_price, _ = _calculate_module_price('mining_t1', 1)
        t1_player = {"dollars": t1_price, "rootium": Decimal("0"), "firewall_level": 0}
        t1_opts = _get_purchasable_options(self.mock_ctx, "mining", t1_player)
        self.assertEqual(len(t1_opts), 1)
        self.assertEqual(t1_opts[0].value, "mining:1")

        # Attaque requiert du RTM et FW 1+ (beta.required_firewall.attack = 1)
        poor_atk = _get_purchasable_options(self.mock_ctx, "attack", t1_player)
        self.assertEqual(len(poor_atk), 0)

        # Joueur riche FW 5 : accès complet aux 5 tiers
        t5_price, _ = _calculate_module_price('mining_t5', 5)
        rich_player = {"dollars": t5_price, "rootium": Decimal("50"), "firewall_level": 5}
        rich_mining = _get_purchasable_options(self.mock_ctx, "mining", rich_player)
        rich_attack = _get_purchasable_options(self.mock_ctx, "attack", rich_player)
        rich_defense = _get_purchasable_options(self.mock_ctx, "defense", rich_player)
        self.assertEqual(len(rich_mining), 5)
        self.assertEqual(len(rich_attack), 5)
        self.assertEqual(len(rich_defense), 5)

    def test_shop_embed_fields(self):
        """L'embed catalogue expose fidèlement les textes français et anglais des captures."""
        # FR
        embed_fr = self.cog._build_main_shop_embed(self.mock_ctx, {})
        self.assertEqual(embed_fr.title, "🛒 Marché des Composants Réseau")
        self.assertIn("Améliorez vos baies de serveurs", embed_fr.description)
        self.assertEqual(len(embed_fr.fields), 3)

        mining_field = embed_fr.fields[0]
        self.assertEqual(mining_field.name, "🪙 Filière Minage — USD")
        self.assertIn("production de Rootium (**RTM**)", mining_field.value)
        self.assertIn("`/claim`", mining_field.value)

        attack_field = embed_fr.fields[1]
        self.assertEqual(attack_field.name, "⚔️ Filière Attaque — RTM")
        self.assertIn("`/compile`", attack_field.value)
        self.assertIn("`/scan`", attack_field.value)
        self.assertIn("`/hack`", attack_field.value)

        defense_field = embed_fr.fields[2]
        self.assertEqual(defense_field.name, "🛡️ Filière Défense — USD")
        self.assertIn("Défense locale (DEF)", defense_field.value)

        # EN
        _cache[10001] = ('en', time.monotonic() + 3600)
        embed_en = self.cog._build_main_shop_embed(self.mock_ctx, {})
        self.assertEqual(embed_en.title, "🛒 Network Components Market")
        self.assertIn("Upgrade your server racks", embed_en.description)
        self.assertEqual(embed_en.fields[0].name, "🪙 Mining Branch — USD")
        self.assertEqual(embed_en.fields[1].name, "⚔️ Attack Branch — RTM")
        self.assertEqual(embed_en.fields[2].name, "🛡️ Defense Branch — USD")
        _cache[10001] = ('fr', time.monotonic() + 3600)

    def test_category_shop_embeds_with_syntax(self):
        """Chaque embed de catégorie affiche la syntaxe classique et les ressources du joueur."""
        p_data = {"dollars": Decimal("500"), "rootium": Decimal("0.05"), "firewall_level": 2}
        embed = self.cog._build_category_shop_embed(self.mock_ctx, "mining", p_data)
        field_names = [f.name for f in embed.fields]
        self.assertIn("⌨️ Commande directe (au clavier)", field_names)
        self.assertIn("💰 Vos ressources actuelles", field_names)
        syntax_value = next(f.value for f in embed.fields if f.name == "⌨️ Commande directe (au clavier)")
        self.assertIn("!buy mining <tier>", syntax_value)
        self.assertIn("/buy kind:mining", syntax_value)

    async def test_shop_catalog_view_buttons_and_navigation(self):
        """Vérifie les 4 boutons initiaux et l'apparition du menu déroulant filtré sur clic de catégorie."""
        t1_price, _ = _calculate_module_price('mining_t1', 1)
        p_data = {"dollars": t1_price, "rootium": Decimal("0"), "firewall_level": 0}
        view = ShopCatalogView(self.cog, self.mock_ctx, p_data)
        self.assertEqual(len(view.children), 4)

        labels = [getattr(c, "label", None) for c in view.children]
        emojis = [str(getattr(c, "emoji", "")) for c in view.children]
        self.assertEqual(labels[0], "Minage")
        self.assertEqual(emojis[0], "🪙")
        self.assertEqual(labels[1], "Attaque")
        self.assertEqual(emojis[1], "⚔️")
        self.assertEqual(labels[2], "Défense")
        self.assertEqual(emojis[2], "🛡️")
        self.assertEqual(labels[3], "Fermer")
        self.assertEqual(emojis[3], "❌")

        # Vérification en anglais
        _cache[10001] = ('en', time.monotonic() + 3600)
        view_en = ShopCatalogView(self.cog, self.mock_ctx, p_data)
        en_labels = [getattr(c, "label", None) for c in view_en.children]
        self.assertEqual(en_labels, ["Mining", "Attack", "Defense", "Close"])
        _cache[10001] = ('fr', time.monotonic() + 3600)

        # Avec une catégorie sélectionnée (Minage) : 4 boutons + 1 menu déroulant filtré (T1 seul)
        view_mining = ShopCatalogView(self.cog, self.mock_ctx, p_data, current_category="mining")
        self.assertEqual(len(view_mining.children), 5)
        select_item = view_mining.children[4]
        self.assertFalse(select_item.disabled)
        self.assertEqual(len(select_item.options), 1)
        opt = select_item.options[0]
        self.assertEqual(opt.value, "mining:1")
        self.assertEqual(str(opt.emoji), "🪙")
        # Le label ne contient pas l'emoji (évite le double emote) et rend le prix très visible
        self.assertEqual(opt.label, f"Minage T1 — {format_usd(t1_price)} $")
        self.assertIn(f"Coût : {format_usd(t1_price)} $", opt.description)


class TestRemainingBalancesInQuotes(unittest.TestCase):
    """Tests de l'affichage du solde restant dans tous les devis (Chantier D)."""

    def setUp(self):
        self.tx = MockTransaction()
        self.tx.players[10001] = {
            "discord_id": 10001,
            "dollars": Decimal("5000.00"),
            "rootium": Decimal("2.50000"),
            "firewall_level": 1,
            "attack_points": 100,
            "mining_t1": 1,
            "attack_t1": 1,
            "bay_defense_t1": 1,
            "mining_buffer": Decimal("0"),
            "mining_last_update_at": self.tx.now,
            "network_defense": 100,
            "reputation": 0,
            "secret_id": "000001",
        }
        self.tx.players[20002] = {
            "discord_id": 20002,
            "dollars": Decimal("5000.00"),
            "rootium": Decimal("2.50000"),
            "firewall_level": 1,
            "attack_points": 50,
            "network_defense": 100,
            "bay_defense_t1": 1,
            "secret_id": "000002",
        }

    def test_buy_quote_balances(self):
        """Le devis /buy retourne current_usd/rtm et remaining_usd/rtm."""
        quote = Player.buy(self.tx, 10001, kind="mining", tier=1, confirm=False)
        self.assertTrue(quote.get("buy_quote"))
        self.assertEqual(quote.get("current_usd"), Decimal("5000.00"))
        t1_price, _ = _calculate_module_price('mining_t1', 1)
        self.assertEqual(quote.get("remaining_usd"), Decimal("5000.00") - t1_price)

    def test_upgrade_quote_balances(self):
        """Le devis /upgrade retourne current_usd et remaining_usd."""
        fw_price, _ = _calculate_module_price('firewall', 2)
        self.tx.players[10001]['dollars'] = fw_price + Decimal('2500.00')
        quote = Player.upgrade(self.tx, 10001, confirm=False)
        self.assertTrue(quote.get("upgrade_quote"))
        self.assertEqual(quote.get("current_usd"), fw_price + Decimal('2500.00'))
        self.assertEqual(quote.get("remaining_usd"), Decimal("2500.00"))

    def test_scan_quote_balances(self):
        """Le devis /scan retourne current_rtm et remaining_rtm."""
        quote = Player.scan(self.tx, 10001, target=20002, confirm=False)
        self.assertTrue(quote.get("scan_quote"))
        self.assertEqual(quote.get("current_rtm"), Decimal("2.50000"))
        self.assertLess(quote.get("remaining_rtm"), Decimal("2.50000"))

    def test_convert_quote_balances(self):
        """Le devis /convert retourne current_rootium/dollars et new_rootium/dollars."""
        quote = Player.convert(self.tx, 10001, amount="1.00000", confirm=False)
        self.assertTrue(quote.get("convert_quote"))
        self.assertEqual(quote.get("current_rootium"), Decimal("2.50000"))
        self.assertEqual(quote.get("new_rootium"), Decimal("1.50000"))
        self.assertEqual(quote.get("current_dollars"), Decimal("5000.00"))
        self.assertGreater(quote.get("new_dollars"), Decimal("5000.00"))


class TestSignalButtonDeleteOnWrong(unittest.IsolatedAsyncioTestCase):
    """Vérifie que le message avec boutons est supprimé quand le joueur se trompe."""

    async def test_signal_wrong_button_deletes_message(self):
        from commands.game.signal import Signal
        bot = MagicMock()
        cog = Signal(bot)
        cog._reply_text = AsyncMock()

        mock_msg = MagicMock()
        mock_msg.delete = AsyncMock()

        mock_interaction = MagicMock()
        mock_interaction.message = mock_msg

        ctx = MagicMock()
        ctx.interaction = mock_interaction

        await cog._send(ctx, "signal", {"status": "wrong", "guess": "X"})
        mock_msg.delete.assert_awaited_once()

    async def test_signal_won_button_does_not_delete_message(self):
        from commands.game.signal import Signal
        bot = MagicMock()
        cog = Signal(bot)
        cog._reply_text = AsyncMock()
        with patch("game.challenge_tracker.ChallengeTracker.notify_win", new_callable=AsyncMock):
            mock_msg = MagicMock()
            mock_msg.delete = AsyncMock()

            mock_interaction = MagicMock()
            mock_interaction.message = mock_msg

            ctx = MagicMock()
            ctx.interaction = mock_interaction

            await cog._send(ctx, "signal", {"status": "won", "reward": Decimal("2.50"), "winning_letter": "A"})
            mock_msg.delete.assert_not_awaited()


class TestMaintenanceSilence(unittest.IsolatedAsyncioTestCase):
    """Vérifie que le bot reste silencieux lors des échecs de check en mode maintenance."""

    async def test_maintenance_check_failure_is_silent(self):
        from discord.ext import commands
        import main
        bot = main.create_bot()

        # Simuler un contexte avec interaction
        ctx = MagicMock()
        ctx.guild = MagicMock()
        ctx.interaction = MagicMock()
        ctx.respond = AsyncMock()
        ctx.send = AsyncMock()

        error = commands.CheckFailure("Check failed")

        with patch.object(main.Check, "maintenance_enabled", return_value=True):
            # Le handler doit retourner sans rien envoyer
            # On récupère report_command_error défini dans create_bot
            # En appelant le dispatch on_command_error
            await bot.on_command_error(ctx, error)
            ctx.respond.assert_not_awaited()
            ctx.send.assert_not_awaited()


class TestInviteAndBotinfo(unittest.IsolatedAsyncioTestCase):
    """Vérifie la commande !invite et la présence du lien d'invitation dans !botinfo."""

    async def test_invite_command_gives_invite_url(self):
        from commands.utility.invite import Invite
        from data import INVITE_URL
        bot = MagicMock()
        cog = Invite(bot)

        ctx = MagicMock()
        ctx.respond = AsyncMock()
        ctx.author = MagicMock()
        ctx.author.id = 123456

        await cog._invite_logic(ctx)
        ctx.respond.assert_awaited_once()
        args, kwargs = ctx.respond.call_args
        message_text = args[0] if args else kwargs.get("content", "")
        self.assertIn(INVITE_URL, message_text)

        view = kwargs.get("view")
        self.assertIsNotNone(view)
        button = view.children[0]
        self.assertEqual(button.url, INVITE_URL)

    async def test_botinfo_embed_contains_invite_url(self):
        from commands.utility.botinfo import BotInfo
        from data import INVITE_URL
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.display_avatar.url = "https://example.com/avatar.png"
        bot.guilds = []
        bot.latency = 0.042
        bot.start_time = None
        cog = BotInfo(bot)

        ctx = MagicMock()
        ctx.respond = AsyncMock()
        ctx.author = MagicMock()
        ctx.author.id = 123456

        await cog._botinfo_logic(ctx)
        ctx.respond.assert_awaited_once()
        _, kwargs = ctx.respond.call_args
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        field_values = [f.value for f in embed.fields]
        has_invite = any(INVITE_URL in val for val in field_values)
        self.assertTrue(has_invite, f"L'URL d'invitation {INVITE_URL} doit être présente dans les champs de l'embed")


if __name__ == "__main__":
    unittest.main()


