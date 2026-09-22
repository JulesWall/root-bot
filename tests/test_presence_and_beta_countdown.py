"""
Tests unitaires complets pour le gestionnaire de présence et le compte à rebours de lancement de la bêta.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord

import data
from commands.admin.beta_launch import BetaLaunch
from utils.presence_manager import (
    calculate_remaining_hours,
    clear_beta_launch_target,
    get_beta_launch_target,
    get_presence_activity,
    get_presence_text,
    parse_target_datetime,
    set_beta_launch_target,
    update_bot_presence,
)


class TestBetaCountdownAndPresence(unittest.IsolatedAsyncioTestCase):
    """Vérifie tous les aspects du compte à rebours de la bêta et de la présence Discord."""

    def setUp(self):
        clear_beta_launch_target()

    def tearDown(self):
        clear_beta_launch_target()

    def test_parse_target_datetime_relative(self):
        """Vérifie le parsing des formats relatifs (+24h, 12h, 5 heures)."""
        now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
        target24 = parse_target_datetime("24h", now=now)
        self.assertEqual(target24, now + timedelta(hours=24))

        target12 = parse_target_datetime("+12h", now=now)
        self.assertEqual(target12, now + timedelta(hours=12))

        target5 = parse_target_datetime("5 heures", now=now)
        self.assertEqual(target5, now + timedelta(hours=5))

    def test_parse_target_datetime_time_of_day(self):
        """Vérifie le parsing d'une heure de la journée (ex: 18:00 ou 18h30)."""
        now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
        target = parse_target_datetime("18:00", now=now)
        self.assertEqual(target, datetime(2026, 9, 22, 18, 0, 0, tzinfo=timezone.utc))

        # Si l'heure est déjà passée aujourd'hui, elle bascule sur le lendemain
        target_past = parse_target_datetime("10:00", now=now)
        self.assertEqual(target_past, datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc))

    def test_parse_target_datetime_iso_and_dates(self):
        """Vérifie le parsing des formats ISO et dates classiques."""
        now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
        target = parse_target_datetime("2026-09-25T15:30:00", now=now)
        self.assertEqual(target.year, 2026)
        self.assertEqual(target.month, 9)
        self.assertEqual(target.day, 25)
        self.assertEqual(target.hour, 15)
        self.assertEqual(target.minute, 30)

        # Invalide
        self.assertIsNone(parse_target_datetime("invalide_date"))
        self.assertIsNone(parse_target_datetime(None))

    def test_calculate_remaining_hours(self):
        """Vérifie le calcul des heures restantes avec arrondi supérieur."""
        now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)

        # 5h 30min d'attente -> 6 heures
        t1 = now + timedelta(hours=5, minutes=30)
        self.assertEqual(calculate_remaining_hours(target=t1, now=now), 6)

        # Exactement 5 heures -> 5 heures
        t2 = now + timedelta(hours=5)
        self.assertEqual(calculate_remaining_hours(target=t2, now=now), 5)

        # 45 minutes restantes -> 1 heure
        t3 = now + timedelta(minutes=45)
        self.assertEqual(calculate_remaining_hours(target=t3, now=now), 1)

        # Date dépassée (0s ou négatif) -> 0
        t4 = now - timedelta(minutes=5)
        self.assertEqual(calculate_remaining_hours(target=t4, now=now), 0)

    def test_get_presence_text_formatting(self):
        """Vérifie le texte exact selon la spécification heure par heure."""
        now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)

        with patch("utils.check.Check.beta_enabled", return_value=True):
            # Plus de 1 heure
            t_multi = now + timedelta(hours=4, minutes=10)
            self.assertEqual(get_presence_text(target=t_multi, now=now), "Ouverture de la beta dans 5 heures")

            # Exactement 1 heure
            t_single = now + timedelta(minutes=50)
            self.assertEqual(get_presence_text(target=t_single, now=now), "Ouverture de la beta dans 1 heure")

            # Déjà ouvert
            t_past = now - timedelta(seconds=10)
            self.assertEqual(get_presence_text(target=t_past, now=now), "Beta ouverte !")

        with patch("utils.check.Check.beta_enabled", return_value=False):
            self.assertEqual(get_presence_text(target=t_multi, now=now), data.BOT_NAME)

    def test_get_presence_activity_type(self):
        """Vérifie que get_presence_activity retourne un CustomActivity avec le bon texte."""
        now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
        with patch("utils.check.Check.beta_enabled", return_value=True):
            t = now + timedelta(hours=3)
            act = get_presence_activity(target=t, now=now)
            self.assertIsInstance(act, discord.CustomActivity)
            self.assertEqual(act.name, "Ouverture de la beta dans 3 heures")

        with patch("utils.check.Check.beta_enabled", return_value=False):
            act_default = get_presence_activity(target=t, now=now)
            self.assertIsInstance(act_default, discord.Game)
            self.assertEqual(act_default.name, data.BOT_NAME)

    def test_target_persistence_in_file(self):
        """Vérifie la persistance de la date cible via set_beta_launch_target."""
        import os
        with patch.dict(os.environ, {"BETA_LAUNCH_AT": "", "BETA_LAUNCH_TIME": "", "BETA_LAUNCH_HOURS": ""}):
            now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
            target = now + timedelta(hours=48)

            set_beta_launch_target(target)
            loaded = get_beta_launch_target()
            self.assertIsNotNone(loaded)
            self.assertEqual(int(loaded.timestamp()), int(target.timestamp()))

            clear_beta_launch_target()
            self.assertIsNone(get_beta_launch_target())

    async def test_update_bot_presence_status_and_activity(self):
        """Vérifie que update_bot_presence respecte le mode maintenance et applique l'activité."""
        mock_bot = MagicMock()
        mock_bot.change_presence = AsyncMock()
        now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
        set_beta_launch_target(now + timedelta(hours=10))

        with patch("utils.check.Check.beta_enabled", return_value=True):
            # 1. Hors maintenance -> Status.online
            with patch("utils.check.Check.maintenance_enabled", return_value=False):
                await update_bot_presence(mock_bot)
                mock_bot.change_presence.assert_called_once()
                call_kwargs = mock_bot.change_presence.call_args[1]
                self.assertEqual(call_kwargs["status"], discord.Status.online)
                self.assertIn("Ouverture de la beta", call_kwargs["activity"].name)

            # 2. Même appel sans changement -> pas de flood gateway
            mock_bot.change_presence.reset_mock()
            with patch("utils.check.Check.maintenance_enabled", return_value=False):
                await update_bot_presence(mock_bot)
                mock_bot.change_presence.assert_not_called()

            # 3. En maintenance -> Status.dnd
            with patch("utils.check.Check.maintenance_enabled", return_value=True):
                await update_bot_presence(mock_bot)
                mock_bot.change_presence.assert_called_once()
                call_kwargs = mock_bot.change_presence.call_args[1]
                self.assertEqual(call_kwargs["status"], discord.Status.dnd)

    async def test_admin_beta_launch_commands(self):
        """Vérifie la commande d'administration /beta_launch (status, set, clear)."""
        import os
        with patch.dict(os.environ, {"BETA_LAUNCH_AT": "", "BETA_LAUNCH_TIME": "", "BETA_LAUNCH_HOURS": ""}):
            mock_bot = MagicMock()
            mock_bot.change_presence = AsyncMock()
            cog = BetaLaunch(mock_bot)

            mock_ctx = MagicMock()
            mock_ctx.author.id = 12345
            mock_ctx.respond = AsyncMock()
            mock_ctx.send = AsyncMock()

            # 1. Non-OP refusé
            with patch("utils.check.Check.is_op", new=AsyncMock(return_value=False)):
                await cog.slash_beta_launch.callback(cog, mock_ctx, action="status")
                mock_ctx.respond.assert_called_once()
                self.assertIn("Accès refusé", mock_ctx.respond.call_args[0][0])

            # 2. OP autorisé : set
            mock_ctx.respond.reset_mock()
            with patch("utils.check.Check.is_op", new=AsyncMock(return_value=True)):
                await cog.slash_beta_launch.callback(cog, mock_ctx, action="set", cible="24h")
                mock_ctx.respond.assert_called_once()
                self.assertIn("Lancement de la Bêta programmé", mock_ctx.respond.call_args[0][0])
                self.assertIsNotNone(get_beta_launch_target())

                # 3. OP autorisé : status
                mock_ctx.respond.reset_mock()
                await cog.slash_beta_launch.callback(cog, mock_ctx, action="status")
                mock_ctx.respond.assert_called_once()
                self.assertIn("Compte à rebours Bêta actif", mock_ctx.respond.call_args[0][0])

                # 4. OP autorisé : clear
                mock_ctx.respond.reset_mock()
                await cog.slash_beta_launch.callback(cog, mock_ctx, action="clear")
                mock_ctx.respond.assert_called_once()
                self.assertIn("réinitialisé", mock_ctx.respond.call_args[0][0])
                self.assertIsNone(get_beta_launch_target())
