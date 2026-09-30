"""
Tests unitaires pour l'interface /network V2 et les infrastructures de contrôle (Étape 3).

Valide :
- Les 6 niveaux d'infrastructures de contrôle (0 à 5) en FR et EN.
- La structure Components V2 (DesignerView, Container, MediaGallery, TextDisplay, Separator, ActionRow).
- Le respect des limites Discord Components V2 (<= 40 composants, <= 4 000 caractères, <= 5 boutons par ActionRow).
- Le chargement et repli de l'illustration (niveau-X-*.png ou fallback textuel sans URL cassée).
- La résolution des emojis avec priorité animée et replis Unicode.
- Le regroupement du matériel par tier même avec de très grands nombres de mineurs.
- La règle de sécurité : panneau visible publiquement mais actions réservées au propriétaire (author_id).
- Les transitions d'état entre la vue Poste et la sous-vue Matériel.
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import unittest

import discord

from commands.game.network import (
    NetworkDesignerView,
    get_infrastructure_image_path,
    select_emojis,
    FALLBACKS,
    COLOR_TURQUOISE,
    COLOR_AMBER,
)
from game.math_config import MathConfig


class MockPartialEmoji(discord.PartialEmoji):
    def __init__(self, name, identifier, animated=False, usable=True):
        super().__init__(name=name, id=identifier, animated=animated)
        self.usable = usable

    def is_usable(self):
        return self.usable


def flatten_components(items):
    for item in items:
        yield item
        yield from flatten_components(item.get("components", []))


class TestNetworkV2Interface(unittest.IsolatedAsyncioTestCase):
    """Vérifie l'interface /network V2 et les six infrastructures de contrôle."""

    def setUp(self):
        self.mock_cog = MagicMock()
        self.mock_ctx = MagicMock()
        self.mock_ctx.author.id = 12345
        self.mock_ctx.author.display_name = "Juels"
        self.mock_ctx.interaction = None

    def _make_base_result(self, level=0):
        return {
            "discord_id": 12345,
            "dollars": Decimal("2500.00"),
            "rootium": Decimal("10.50000"),
            "infrastructure_level": level,
            "firewall_level": level,
            "reputation": 5,
            "mining_t1": 1000,   # Test de très grand nombre de mineurs
            "mining_t2": 250,
            "attack_t1": 10,
            "bay_defense_t1": 5,
            "secret_id": "000042",
            "secret_next_ts": 1760000000,
            "mining_state": {
                "buffer": Decimal("0.05000"),
                "memory_pct": 45.0,
                "rate_per_min": Decimal("0.00100"),
                "memory_used_formatted": "45 Ko",
                "total_ram_formatted": "100 Ko",
                "is_full": False,
                "seconds_to_full": 3300,
            },
        }

    async def test_infrastructure_image_paths_exist(self):
        """Les illustrations des 6 niveaux (0 à 5) existent sur disque."""
        for lvl in range(6):
            p = get_infrastructure_image_path(lvl)
            self.assertIsNotNone(p, f"Image manquante pour infrastructure niveau {lvl}")
            self.assertTrue(p.exists(), f"Fichier image introuvable : {p}")

    async def test_infrastructure_names_levels_0_to_5(self):
        """Chacun des six niveaux a un nom valide dans les dictionnaires de langue."""
        from lang.game_fr import text as FR
        from lang.game_en import text as EN

        expected_fr = [
            "Smartphone bricolé",
            "PC assemblé",
            "Station de travail",
            "Serveur dédié",
            "Salle des serveurs",
            "Datacenter",
        ]
        for lvl, name in enumerate(expected_fr):
            self.assertEqual(FR.get(f'g_infra_name_{lvl}'), name)
            self.assertIn(f'g_infra_name_{lvl}', EN)

    async def test_select_emojis_animated_priority_and_fallbacks(self):
        """select_emojis privilégie les emojis animés utilisables et utilise les replis Unicode."""
        anim = MockPartialEmoji("root_recolter", 101, animated=True)
        static = MockPartialEmoji("root_recolter", 102, animated=False)
        unusable = MockPartialEmoji("root_materiel", 103, animated=True, usable=False)

        selected = select_emojis([static, anim, unusable])
        self.assertEqual(selected["recolter"], anim)
        self.assertNotIn("materiel", selected)

        view = NetworkDesignerView(self.mock_cog, self.mock_ctx, self._make_base_result(0), emojis=selected)
        # recolter utilise l'emoji animé résolu
        self.assertEqual(view.emoji("recolter"), anim)
        # materiel n'a pas d'emoji serveur utilisable -> repli Unicode
        self.assertEqual(view.emoji("materiel"), FALLBACKS["materiel"])

    async def test_components_v2_budget_and_structure_all_levels(self):
        """Vérifie le respect strict du budget Discord Components V2 pour les 6 niveaux."""
        for lvl in range(6):
            result = self._make_base_result(level=lvl)
            img_path = get_infrastructure_image_path(lvl)
            image_url = f"attachment://{img_path.name}" if img_path else None

            view = NetworkDesignerView(self.mock_cog, self.mock_ctx, result, image_url=image_url)
            self.assertTrue(view.is_components_v2())

            payload = view.to_components()
            flat = list(flatten_components(payload))

            # Budget conservateur du projet
            self.assertLessEqual(len(flat), 40, f"Trop de composants pour le niveau {lvl}")
            total_chars = sum(len(i.get("content", "")) for i in flat)
            self.assertLessEqual(total_chars, 4000, f"Trop de caractères pour le niveau {lvl}")

            # Vérification des boutons par ActionRow (<= 5)
            for item in flat:
                if item.get("type") == 1:  # ActionRow
                    self.assertLessEqual(len(item.get("components", [])), 5)

            # Vérification de la MediaGallery en première position si image fournie
            if image_url:
                container = payload[0]
                self.assertEqual(container.get("components", [])[0].get("type"), 12)  # MediaGallery

            json.dumps(payload)

    async def test_missing_banner_fallback_graceful(self):
        """Si l'image manque, le panneau reste textuellement fonctionnel sans MediaGallery."""
        result = self._make_base_result(level=3)
        view = NetworkDesignerView(self.mock_cog, self.mock_ctx, result, image_url=None)
        payload = view.to_components()
        container = payload[0]
        # Le premier composant n'est pas une MediaGallery
        self.assertNotEqual(container.get("components", [])[0].get("type"), 12)
        # Le premier composant est un TextDisplay
        self.assertEqual(container.get("components", [])[0].get("type"), 10)

    async def test_public_viewing_and_owner_only_permissions(self):
        """Tout le monde peut voir le panneau, mais seul le propriétaire peut interagir."""
        result = self._make_base_result(level=2)
        view = NetworkDesignerView(self.mock_cog, self.mock_ctx, result)

        owner_interaction = MagicMock()
        owner_interaction.user.id = 12345
        self.assertTrue(await view.interaction_check(owner_interaction))

        other_interaction = MagicMock()
        other_interaction.user.id = 99999
        other_interaction.response.send_message = AsyncMock()
        self.assertFalse(await view.interaction_check(other_interaction))
        other_interaction.response.send_message.assert_called_once()

    async def test_view_switching_poste_and_hardware(self):
        """Bascule entre la vue Poste et la sous-vue Matériel."""
        result = self._make_base_result(level=1)
        view = NetworkDesignerView(self.mock_cog, self.mock_ctx, result)
        self.assertIsNone(view.detail)

        # Passer à Matériel
        interaction = MagicMock()
        interaction.user.id = 12345
        interaction.response.edit_message = AsyncMock()
        await view._on_hardware(interaction)
        self.assertEqual(view.detail, "hardware")
        interaction.response.edit_message.assert_awaited_once_with(view=view)

        # Vérifier que les mineurs regroupés par tier apparaissent dans le payload
        payload_hw = view.to_components()
        text_hw = json.dumps(payload_hw, ensure_ascii=False)
        self.assertIn("1000x", text_hw)  # 1000 mineurs T1
        self.assertIn("250x", text_hw)   # 250 mineurs T2

        # Retourner à Poste
        interaction.reset_mock()
        await view._on_back(interaction)
        self.assertIsNone(view.detail)
        interaction.response.edit_message.assert_awaited_once_with(view=view)

    async def test_panel_color_alert_on_full_ram(self):
        """La couleur passe à l'Ambre en cas de mémoire pleine, Turquoise sinon."""
        res_normal = self._make_base_result(0)
        view_normal = NetworkDesignerView(self.mock_cog, self.mock_ctx, res_normal)
        self.assertEqual(view_normal.children[0].color.value, COLOR_TURQUOISE)

        res_full = self._make_base_result(0)
        res_full["mining_state"]["is_full"] = True
        res_full["mining_state"]["memory_pct"] = 100.0
        view_full = NetworkDesignerView(self.mock_cog, self.mock_ctx, res_full)
        self.assertEqual(view_full.children[0].color.value, COLOR_AMBER)


if __name__ == '__main__':
    unittest.main()

