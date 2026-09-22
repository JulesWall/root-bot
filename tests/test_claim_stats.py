"""
Tests unitaires pour le suivi des récoltes /claim et la détection d'automatisation (Anti-Triche).

Couvre :
1. L'extraction des intervalles temporels (extract_claim_intervals).
2. L'analyse statistique (moyenne, écart-type, régularité, scores de risque).
3. La détection par fenêtre glissante des baisses localisées de variation (Streak / Burst Bot).
4. La détection d'activité continue 24/24 sans sommeil.
5. Le cycle de persistance en base (DailyClaimStatsDB).
6. Le cycle d'exécution du rapport quotidien et la résilience aux pannes (ClaimModeration).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.admin.claim_moderation import ClaimModeration
from game.db.daily_claim_stats import DailyClaimStatsDB
from tests.test_suite import MockDatabase, MockTransaction
from utils.claim_analysis import (
    calculate_player_claim_metrics,
    extract_claim_intervals,
)


class TestClaimAnalysis(unittest.TestCase):
    """Vérifie la robustesse mathématique et la sensibilité de détection d'automatisation."""

    def test_extract_claim_intervals_edge_cases(self):
        """0 ou 1 claim ne doit produire aucun intervalle."""
        self.assertEqual(extract_claim_intervals([]), [])
        self.assertEqual(extract_claim_intervals([{"claimed_at": datetime.now(), "interval_seconds": 100}]), [])

    def test_extract_claim_intervals_from_datetimes(self):
        """Les intervalles doivent être déduits précisément de l'écart entre datetimes."""
        base = datetime(2026, 9, 22, 12, 0, 0)
        claims = [
            {"claimed_at": base, "interval_seconds": None, "amount": Decimal("1")},
            {"claimed_at": base + timedelta(seconds=900), "interval_seconds": None, "amount": Decimal("1")},
            {"claimed_at": base + timedelta(seconds=1850), "interval_seconds": None, "amount": Decimal("1")},
        ]
        intervals = extract_claim_intervals(claims)
        self.assertEqual(intervals, [900.0, 950.0])

    def test_calculate_player_claim_metrics_insufficient_data(self):
        """Moins de 2 claims doit renvoyer INSUFFICIENT_DATA et risque LOW."""
        res = calculate_player_claim_metrics([
            {"claimed_at": datetime.now(), "interval_seconds": None, "amount": Decimal("5")},
        ])
        self.assertEqual(res["status"], "INSUFFICIENT_DATA")
        self.assertEqual(res["risk_level"], "LOW")
        self.assertIsNone(res["mean_interval_sec"])

    def test_calculate_player_claim_metrics_human_behavior(self):
        """Un joueur humain aux horaires variables doit avoir un score naturel sans alerte."""
        base = datetime(2026, 9, 22, 8, 0, 0)
        # Intervalles humains : 15m, 1h15, 3h, 45m, 2h, 10m
        deltas = [900, 4500, 10800, 2700, 7200, 600]
        claims = [{"claimed_at": base, "interval_seconds": 0, "amount": Decimal("2")}]
        cur = base
        for d in deltas:
            cur += timedelta(seconds=d)
            claims.append({"claimed_at": cur, "interval_seconds": d, "amount": Decimal("2")})

        res = calculate_player_claim_metrics(claims)
        self.assertEqual(res["risk_level"], "LOW")
        self.assertEqual(res["risk_badge"], "🟢")
        self.assertGreater(res["cv"], 0.35, "Un comportement humain doit présenter un CV significatif.")
        self.assertEqual(res["alerts"], [])

    def test_calculate_player_claim_metrics_full_bot(self):
        """Un bot actif 24h avec un timer de 15 minutes strict doit déclencher une ALERTE ROUGE critique."""
        base = datetime(2026, 9, 22, 0, 0, 0)
        # 12 claims espacés de 900s à +/- 2 secondes
        claims = [{"claimed_at": base, "interval_seconds": 0, "amount": Decimal("1")}]
        cur = base
        bot_intervals = [900, 901, 899, 900, 902, 900, 899, 900, 901, 900, 900]
        for iv in bot_intervals:
            cur += timedelta(seconds=iv)
            claims.append({"claimed_at": cur, "interval_seconds": iv, "amount": Decimal("1")})

        res = calculate_player_claim_metrics(claims)
        self.assertEqual(res["risk_level"], "HIGH")
        self.assertEqual(res["risk_badge"], "🔴")
        self.assertLess(res["std_dev_sec"], 5.0, "L'écart-type d'un script strict doit être infime.")
        self.assertGreater(res["regularity_pct"], 95.0, "La régularité doit être supérieure à 95%.")
        self.assertIn("CRITICAL_MACRO_STREAK", res["alerts"])

    def test_calculate_player_claim_metrics_burst_bot_detection(self):
        """Détection clé : un joueur manuel le jour qui lance un bot la nuit doit être détecté.

        Bien que le CV global de la journée soit dilué par le jeu manuel, la fenêtre glissante
        (Rolling Streak) doit identifier les 6 claims de nuit à variance quasi nulle.
        """
        base = datetime(2026, 9, 22, 10, 0, 0)
        # Phase 1 : Jeu manuel le jour (forte variance)
        day_intervals = [1200, 5400, 10800, 2400, 7200]
        claims = [{"claimed_at": base, "interval_seconds": 0, "amount": Decimal("2")}]
        cur = base
        for iv in day_intervals:
            cur += timedelta(seconds=iv)
            claims.append({"claimed_at": cur, "interval_seconds": iv, "amount": Decimal("2")})

        # Phase 2 : Macro lancée la nuit (7 claims consécutifs à 900s +/- 1s)
        night_intervals = [900, 901, 900, 899, 900, 900]
        for iv in night_intervals:
            cur += timedelta(seconds=iv)
            claims.append({"claimed_at": cur, "interval_seconds": iv, "amount": Decimal("2")})

        res = calculate_player_claim_metrics(claims)
        # Grâce à la détection de baisse de variation (streak), le risque doit passer à HIGH !
        self.assertEqual(res["risk_level"], "HIGH", "Le botting nocturne partiel doit être détecté.")
        self.assertEqual(res["risk_badge"], "🔴")
        self.assertIsNotNone(res["suspicious_streak"])
        self.assertLess(res["suspicious_streak"]["std_dev_sec"], 5.0)
        self.assertIn("CRITICAL_MACRO_STREAK", res["alerts"])

    def test_calculate_player_claim_metrics_no_sleep_alert(self):
        """Un compte avec 16 claims réguliers sans aucune coupure de plus de 3.5h déclenche NO_SLEEP_24H."""
        base = datetime(2026, 9, 22, 0, 0, 0)
        claims = [{"claimed_at": base, "interval_seconds": 0, "amount": Decimal("1")}]
        cur = base
        # 16 claims espacés d'1h30 (5400s), variance modérée mais pas de pause sommeil
        for i in range(16):
            iv = 5400 + (i % 3) * 600  # 1h30, 1h40, 1h50 (max 1h50 < 3h30)
            cur += timedelta(seconds=iv)
            claims.append({"claimed_at": cur, "interval_seconds": iv, "amount": Decimal("1")})

        res = calculate_player_claim_metrics(claims)
        self.assertTrue(res["active_24h"])
        self.assertIn("NO_SLEEP_24H", res["alerts"])


class TestDailyClaimStatsDB(unittest.TestCase):
    """Vérifie le fonctionnement de la persistance SQL des claims journaliers."""

    def setUp(self):
        self.tx = MockTransaction()
        self.actor1 = 1001
        self.actor2 = 1002

    def test_record_summary_and_reset_cycle(self):
        """Vérifie l'enregistrement, l'extraction triée par nombre de claims et la purge."""
        now = datetime(2026, 9, 22, 14, 0, 0)

        # Actor 1 effectue 3 claims
        DailyClaimStatsDB.record_claim(self.tx, self.actor1, now, 900, Decimal("1.5"))
        DailyClaimStatsDB.record_claim(self.tx, self.actor1, now + timedelta(minutes=15), 900, Decimal("1.5"))
        DailyClaimStatsDB.record_claim(self.tx, self.actor1, now + timedelta(minutes=30), 900, Decimal("1.5"))

        # Actor 2 effectue 1 claim
        DailyClaimStatsDB.record_claim(self.tx, self.actor2, now, 1800, Decimal("5.0"))

        # Résumé général
        summary = DailyClaimStatsDB.get_summary(self.tx)
        self.assertEqual(len(summary), 2)
        # Actor 1 doit être premier (3 claims > 1 claim)
        self.assertEqual(summary[0]["discord_id"], self.actor1)
        self.assertEqual(summary[0]["claim_count"], 3)
        self.assertEqual(len(summary[0]["claims"]), 3)

        self.assertEqual(summary[1]["discord_id"], self.actor2)
        self.assertEqual(summary[1]["claim_count"], 1)

        # Audit ciblé d'un joueur
        actor1_claims = DailyClaimStatsDB.get_user_claims(self.tx, self.actor1)
        self.assertEqual(len(actor1_claims), 3)

        # Date de rapport
        self.assertIsNone(DailyClaimStatsDB.get_last_report_date(self.tx))
        DailyClaimStatsDB.set_last_report_date(self.tx, "2026-09-22", now)
        self.assertEqual(DailyClaimStatsDB.get_last_report_date(self.tx), "2026-09-22")

        # Purge
        DailyClaimStatsDB.reset(self.tx)
        self.assertEqual(DailyClaimStatsDB.get_summary(self.tx), [])

    def test_player_claim_integration_records_to_daily_claim_logs(self):
        """Vérifie que Player.claim insère automatiquement une ligne dans daily_claim_logs quand claimed=True."""
        from game.db.players import Player
        # Enregistrer l'acteur
        Player.network(self.tx, self.actor1)
        self.tx.players[self.actor1]["mining_t1"] = 1
        self.tx.players[self.actor1]["mining_buffer"] = Decimal("0.05000")
        self.tx.players[self.actor1]["mining_last_update_at"] = self.tx.now

        self.assertEqual(len(self.tx.daily_claim_logs), 0)
        res = Player.claim(self.tx, self.actor1)
        self.assertTrue(res.get("claimed"))
        self.assertEqual(len(self.tx.daily_claim_logs), 1)
        logged = self.tx.daily_claim_logs[0]
        self.assertEqual(logged["discord_id"], self.actor1)
        self.assertEqual(logged["amount"], res["amount"])
        self.assertEqual(res["amount"], Decimal("0.00002"))


class TestClaimModerationCog(unittest.IsolatedAsyncioTestCase):
    """Teste le cycle de vie, la résilience aux pannes et le rattrapage du Cog ClaimModeration."""

    def setUp(self):
        self._loop_patch = patch.object(ClaimModeration, "daily_claim_report_loop")
        self._mock_loop = self._loop_patch.start()

    def tearDown(self):
        self._loop_patch.stop()

    async def test_run_report_success_resets_database(self):
        """Un envoi réussi doit vider la table et enregistrer la date."""
        mock_bot = MagicMock()
        mock_db = MockDatabase()
        now = datetime(2026, 9, 22, 12, 0, 0)

        # Insérer 2 claims
        mock_db.daily_claim_logs.append({
            "discord_id": 999,
            "claimed_at": now,
            "interval_seconds": 900,
            "amount": Decimal("2"),
        })
        mock_db.daily_claim_logs.append({
            "discord_id": 999,
            "claimed_at": now + timedelta(minutes=15),
            "interval_seconds": 900,
            "amount": Decimal("2"),
        })

        mock_bot.root_service.database = mock_db
        mock_bot.discord_logger.log_daily_claim_report = AsyncMock(return_value=None)

        cog = ClaimModeration(mock_bot)
        status = await cog._run_daily_report()
        self.assertEqual(status, "success")
        mock_bot.discord_logger.log_daily_claim_report.assert_called_once()
        self.assertEqual(len(mock_db.daily_claim_logs), 0, "La table doit être vidée après succès d'envoi.")

    async def test_run_report_failure_preserves_database(self):
        """Si l'envoi Discord échoue, les logs NE doivent PAS être purgés."""
        mock_bot = MagicMock()
        mock_db = MockDatabase()
        now = datetime(2026, 9, 22, 12, 0, 0)
        mock_db.daily_claim_logs.append({
            "discord_id": 999,
            "claimed_at": now,
            "interval_seconds": 900,
            "amount": Decimal("2"),
        })

        mock_bot.root_service.database = mock_db
        mock_bot.discord_logger.log_daily_claim_report = AsyncMock(side_effect=RuntimeError("Discord API Error"))

        cog = ClaimModeration(mock_bot)
        with self.assertRaises(RuntimeError):
            await cog._run_daily_report()

        self.assertEqual(len(mock_db.daily_claim_logs), 1, "Les logs doivent être préservés en cas d'erreur API.")


if __name__ == "__main__":
    unittest.main()
