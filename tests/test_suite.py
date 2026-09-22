"""
Suite de tests complète et automatisée pour le bot Root.

Exécute une série exhaustive de tests unitaires et d'intégration :
1. Test de syntaxe AST sur tous les fichiers Python du projet.
2. Validation de l'internationalisation (symétrie FR/EN et variables de template).
3. Sécurité arithmétique et configuration mathématique (MathConfig).
4. Utilitaires de formatage (temps, devises, langues).
5. Logique métier des 7 mini-jeux (Hash, PIN, Decode, Anomaly, Buffer, Signal, Packet).
6. Économie et calcul des prix de modules.
7. Logique de persistance et de transactions (avec MockTransaction).
8. Contrôles de sécurité (bannissements, cache).
"""

import ast
import inspect
import json
import os
import re
import string
import sys
import time
import copy
import threading
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Configuration du PYTHONPATH vers la racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import data
from lang import en, fr, game_en, game_fr, descslash
from utils.time_format import format_duration, format_remaining_time
from utils import text
from game.math_config import MathConfig
from game.game_error import GameError
from game.db.players import _calculate_module_price, Player, PlayerData, UpdatePlayer, NewPlayer
from game.decode_manager import DecodeManager, COORDINATES, _create_new_challenge as create_decode_challenge
from game.anomaly_manager import AnomalyManager, _create_new_challenge as create_anomaly_challenge
from game.buffer_manager import BufferManager, _create_new_challenge as create_buffer_challenge
from game.signal_manager import SignalManager, _create_new_challenge as create_signal_challenge
from game.packet_manager import PacketManager, _create_new_challenge as create_packet_challenge
from game.hash_manager import HashManager, _create_new_challenge as create_hash_challenge
from game.pin_manager import PinManager, _create_new_challenge as create_pin_challenge
from game.events_manager import EventsManager
from game.challenge_utils import ChallengeResource
from game.db.daily_event_stats import DailyEventStatsDB
from game.db.events import EventsDB
from game.db.upgrades import UpgradesDB
from game.db.hack import HackDB
from game.db.prefix_db import PrefixDB
from utils.check import Check


class MockTransaction:
    """Simulateur en mémoire d'une transaction MySQL pour tester les DAO sans serveur BDD actif."""

    def __init__(self, now=None):
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        self.players = {}
        self.events = {}
        self.upgrades = []
        self.hacks = []
        self.daily_stats = {}
        self.daily_claim_logs = []
        self.prefixes = {}
        self.executed_queries = []
        self.acquired_locks = []

    def acquire_lock(self, name: str, timeout: int = 10) -> None:
        """No-op du GET_LOCK applicatif : enregistre le nom pour les assertions de test."""
        key = str(name)
        if key and key not in self.acquired_locks:
            self.acquired_locks.append(key)

    def one(self, query: str, params=()):
        self.executed_queries.append((query, params))
        q = " ".join(query.split()).upper()

        if "SELECT UTC_TIMESTAMP(6)" in q:
            return {"now": self.now}

        if "SELECT * FROM PLAYERS WHERE DISCORD_ID" in q:
            uid = params[0]
            row = self.players.get(uid)
            return dict(row) if row else None

        if "SELECT * FROM PLAYERS WHERE SECRET_ID" in q:
            code = params[0] if params else None
            if not code:
                return None
            for row in self.players.values():
                if row.get("secret_id") == code:
                    return dict(row)
            return None

        if "SELECT LANG FROM PLAYERS WHERE DISCORD_ID" in q:
            uid = params[0]
            row = self.players.get(uid)
            return {"lang": row.get("lang")} if row else None

        if "SELECT * FROM EVENTS WHERE EVENT" in q:
            ev = params[0]
            row = self.events.get(ev)
            return dict(row) if row else None

        if "SELECT * FROM UPGRADES WHERE DISCORD_ID" in q:
            uid = params[0]
            itype = params[1] if len(params) > 1 else "firewall"
            for up in self.upgrades:
                if up["discord_id"] == uid and up["item_type"] == itype:
                    return dict(up)
            return None

        if "SELECT * FROM HACK WHERE DISCORD_ID" in q:
            uid = params[0]
            for row in self.hacks:
                if row["discord_id"] == uid:
                    return dict(row)
            return None

        if "SELECT PREFIX FROM GUILD_PREFIXES WHERE GUILD_ID" in q:
            gid = params[0]
            p = self.prefixes.get(gid)
            return {"prefix": p} if p else None

        if "SELECT LAST_FOUND_ON FROM EVENTS WHERE EVENT = 'DAILY_MODERATION_REPORT'" in q:
            row = self.events.get("daily_moderation_report")
            return {"last_found_on": row.get("last_found_on")} if row else None

        if "SELECT LAST_FOUND_ON FROM EVENTS WHERE EVENT = 'DAILY_CLAIM_REPORT'" in q:
            row = self.events.get("daily_claim_report")
            return {"last_found_on": row.get("last_found_on")} if row else None

        return None

    def all(self, query: str, params=()):
        self.executed_queries.append((query, params))
        q = " ".join(query.split()).upper()

        if "SELECT DISCORD_ID, SECRET_ID FROM PLAYERS" in q:
            return [
                {"discord_id": uid, "secret_id": p.get("secret_id")}
                for uid, p in self.players.items()
            ]

        if "SELECT SECRET_ID FROM PLAYERS" in q:
            rows = []
            for p in self.players.values():
                code = p.get("secret_id")
                if "IS NOT NULL" in q and not code:
                    continue
                rows.append({"secret_id": code})
            return rows

        if "SELECT DISCORD_ID" in q and "FROM PLAYERS ORDER BY" in q:
            rows = []
            for uid, p in self.players.items():
                if "DOLLARS AS SCORE" in q:
                    score = p.get("dollars", Decimal("0"))
                elif "ROOTIUM AS SCORE" in q:
                    score = p.get("rootium", Decimal("0"))
                elif "EVENTS_WON AS SCORE" in q:
                    score = p.get("events_won", 0)
                else:
                    score = p.get("reputation", 0)
                rows.append({"discord_id": uid, "score": score})
            rows.sort(key=lambda r: r["score"], reverse=True)
            return rows[:10]

        if "SELECT DISCORD_ID, EVENTS_WON, EVENTS_PARTICIPATED FROM DAILY_EVENT_STATS" in q:
            rows = [dict(v) for v in self.daily_stats.values() if v["events_won"] > 0 or v["events_participated"] > 0]
            rows.sort(key=lambda r: (r["events_won"], r["events_participated"]), reverse=True)
            limit = params[0] if params else 50
            return rows[:limit]

        if "SELECT * FROM UPGRADES WHERE EXPIRES_AT <=" in q:
            cutoff = params[0]
            return [dict(u) for u in self.upgrades if u["expires_at"] <= cutoff]

        if "SELECT * FROM HACK WHERE EXPIRES_AT <=" in q:
            cutoff = params[0]
            return [dict(h) for h in self.hacks if h["expires_at"] <= cutoff]

        if "GROUP BY DISCORD_ID" in q and "DAILY_CLAIM_LOGS" in q:
            from collections import defaultdict
            user_counts = defaultdict(lambda: {"claim_count": 0, "total_amount": Decimal("0")})
            for c in self.daily_claim_logs:
                uid = c["discord_id"]
                user_counts[uid]["claim_count"] += 1
                user_counts[uid]["total_amount"] += c.get("amount", Decimal("0"))
            rows = [
                {"discord_id": uid, "claim_count": data["claim_count"], "total_amount": data["total_amount"]}
                for uid, data in user_counts.items()
            ]
            rows.sort(key=lambda r: r["claim_count"], reverse=True)
            limit = params[0] if params else 50
            return rows[:limit]

        if "FROM DAILY_CLAIM_LOGS WHERE DISCORD_ID =" in q:
            uid = params[0]
            matched = [dict(c) for c in self.daily_claim_logs if c["discord_id"] == uid]
            matched.sort(key=lambda r: r["claimed_at"])
            return matched

        if "FROM DAILY_CLAIM_LOGS WHERE DISCORD_ID IN" in q:
            uids = set(params)
            matched = [dict(c) for c in self.daily_claim_logs if c["discord_id"] in uids]
            matched.sort(key=lambda r: r["claimed_at"])
            return matched

        return []

    def execute(self, query: str, params=()):
        self.executed_queries.append((query, params))
        q = " ".join(query.split()).upper()

        if "INSERT INTO PLAYERS" in q:
            uid, dollars, created_at = params[0], params[1], params[2]
            secret_id = params[3] if len(params) > 3 else None
            if secret_id:
                for other in self.players.values():
                    if other.get("secret_id") == secret_id:
                        raise GameError("secret_id_exhausted")
            self.players[uid] = {
                "discord_id": uid,
                "dollars": Decimal(str(dollars)),
                "rootium": Decimal("0.00000"),
                "firewall_level": 0,
                "reputation": 0,
                "next_reputation_at": None,
                "created_at": created_at,
                "network_defense": 0,
                "events_won": 0,
                "lang": None,
                "secret_id": secret_id,
                "attack_points": 0,
                "mining_t1": 0, "mining_t2": 0, "mining_t3": 0, "mining_t4": 0, "mining_t5": 0, "mining_t6": 0,
                "attack_t1": 0, "attack_t2": 0, "attack_t3": 0, "attack_t4": 0, "attack_t5": 0, "attack_t6": 0,
                "bay_defense_t1": 0, "bay_defense_t2": 0, "bay_defense_t3": 0, "bay_defense_t4": 0, "bay_defense_t5": 0, "bay_defense_t6": 0,
                "mining_buffer": Decimal("0.00000"),
                "mining_last_update_at": None,
                "mining_last_claim_at": None,
            }
            return 1

        if "UPDATE PLAYERS SET" in q:
            compacted = q.replace(" ", "")
            if compacted.startswith("UPDATEPLAYERSSETSECRET_ID=NULL") and "WHERE" not in q:
                for player in self.players.values():
                    player["secret_id"] = None
                return 1
            if "ATTACK_POINTS = ATTACK_POINTS +" in q:
                uid = params[-1]
                delta = int(params[0])
                if uid in self.players:
                    self.players[uid]["attack_points"] = int(self.players[uid].get("attack_points") or 0) + delta
                return 1
            if not params:
                return 1
            uid = params[-1]
            if uid in self.players:
                if "GREATEST" in q and "FIREWALL_LEVEL" in q:
                    target = int(params[0])
                    current = int(self.players[uid].get("firewall_level", 0) or 0)
                    self.players[uid]["firewall_level"] = max(current, target)
                    return 1
                clause = query.split("SET")[1].split("WHERE")[0]
                cols = [c.split("=")[0].strip() for c in clause.split(",")]
                for col, val in zip(cols, params[:-1]):
                    if col == "secret_id" and val:
                        for other_id, other in self.players.items():
                            if other_id != uid and other.get("secret_id") == val:
                                raise GameError("secret_id_exhausted")
                    self.players[uid][col] = val
            return 1

        if "INSERT INTO EVENTS" in q:
            if "DAILY_MODERATION_REPORT" in q:
                self.events["daily_moderation_report"] = {
                    "event": "daily_moderation_report",
                    "next_at": params[0],
                    "last_found_by": None,
                    "last_found_on": params[1] if len(params) > 1 else None,
                    "last_reward": Decimal("0.00"),
                }
                return 1
            if "DAILY_CLAIM_REPORT" in q:
                self.events["daily_claim_report"] = {
                    "event": "daily_claim_report",
                    "next_at": params[0],
                    "last_found_by": None,
                    "last_found_on": params[1] if len(params) > 1 else None,
                    "last_reward": Decimal("0.00"),
                }
                return 1
            ev_name = params[0]
            next_at = params[1]
            last_found_by = params[2] if len(params) > 2 else None
            last_found_on = params[3] if len(params) > 3 else None
            last_reward = params[4] if len(params) > 4 else Decimal("0.00")
            self.events[ev_name] = {
                "event": ev_name,
                "next_at": next_at,
                "last_found_by": last_found_by,
                "last_found_on": last_found_on,
                "last_reward": last_reward,
            }
            return 1

        if "INSERT INTO DAILY_EVENT_STATS" in q:
            uid = params[0]
            if uid not in self.daily_stats:
                self.daily_stats[uid] = {"discord_id": uid, "events_won": 0, "events_participated": 0}
            if "EVENTS_PARTICIPATED = EVENTS_PARTICIPATED + 1" in q:
                self.daily_stats[uid]["events_participated"] += 1
            if "EVENTS_WON = EVENTS_WON + 1" in q:
                self.daily_stats[uid]["events_won"] += 1
            return 1

        if "DELETE FROM DAILY_EVENT_STATS" in q:
            self.daily_stats.clear()
            return 1

        if "INSERT INTO DAILY_CLAIM_LOGS" in q:
            self.daily_claim_logs.append({
                "discord_id": params[0],
                "claimed_at": params[1],
                "interval_seconds": params[2],
                "amount": params[3],
            })
            return 1

        if "DELETE FROM DAILY_CLAIM_LOGS" in q:
            self.daily_claim_logs.clear()
            return 1

        if "INSERT INTO UPGRADES" in q:
            up_id = len(self.upgrades) + 1
            self.upgrades.append({
                "id": up_id,
                "discord_id": params[0],
                "item_type": params[1],
                "target_level": params[2],
                "started_at": params[3],
                "expires_at": params[4],
            })
            return up_id

        if "DELETE FROM UPGRADES WHERE ID" in q:
            up_id = params[0]
            self.upgrades = [u for u in self.upgrades if u["id"] != up_id]
            return 1

        if "INSERT INTO HACK" in q:
            if any(h["discord_id"] == params[0] for h in self.hacks):
                return 0
            hack_id = len(self.hacks) + 1
            # discord_id, method, bits_per_s, atk_yield, rtm_paid, started_at, expires_at
            self.hacks.append({
                "id": hack_id,
                "discord_id": params[0],
                "method": params[1],
                "bits_per_s": params[2],
                "atk_yield": params[3],
                "rtm_paid": params[4],
                "started_at": params[5],
                "expires_at": params[6],
            })
            return hack_id

        if "DELETE FROM HACK WHERE ID" in q:
            hack_id = params[0]
            self.hacks = [h for h in self.hacks if h["id"] != hack_id]
            return 1

        if "INSERT INTO GUILD_PREFIXES" in q:
            gid, prefix = params[0], params[1]
            self.prefixes[gid] = prefix
            return 1

        if "DELETE FROM GUILD_PREFIXES" in q:
            self.prefixes.pop(params[0], None)
            return 1

        return 0


class TestSyntaxAndCompilation(unittest.TestCase):
    """Vérifie la validité syntaxique de chaque fichier Python du projet."""

    def test_all_python_files_syntax(self):
        py_files = [p for p in PROJECT_ROOT.rglob("*.py") if ".venv" not in p.parts and "__pycache__" not in p.parts]
        self.assertGreater(len(py_files), 20, "Le projet doit contenir des fichiers Python.")
        for path in py_files:
            with self.subTest(file=str(path.relative_to(PROJECT_ROOT))):
                try:
                    content = path.read_text(encoding="utf-8")
                    ast.parse(content, filename=str(path))
                except SyntaxError as e:
                    self.fail(f"Erreur de syntaxe dans {path}: {e}")


class TestInternationalization(unittest.TestCase):
    """Valide l'exhaustivité et la symétrie des dictionnaires de langues."""

    def test_general_translation_keys_symmetry(self):
        fr_keys = set(fr.text.keys())
        en_keys = set(en.text.keys())
        diff_fr = fr_keys - en_keys
        diff_en = en_keys - fr_keys
        self.assertEqual(diff_fr, set(), f"Clés présentes dans fr.py mais absentes de en.py: {diff_fr}")
        self.assertEqual(diff_en, set(), f"Clés présentes dans en.py mais absentes de fr.py: {diff_en}")

    def test_game_translation_keys_symmetry(self):
        fr_keys = set(game_fr.text.keys())
        en_keys = set(game_en.text.keys())
        diff_fr = fr_keys - en_keys
        diff_en = en_keys - fr_keys
        self.assertEqual(diff_fr, set(), f"Clés de jeu dans game_fr mais absentes de game_en: {diff_fr}")
        self.assertEqual(diff_en, set(), f"Clés de jeu dans game_en mais absentes de game_fr: {diff_en}")

    def test_descriptions_symmetry(self):
        self.assertEqual(set(game_fr.descriptions.keys()), set(game_en.descriptions.keys()))

    def test_labels_symmetry(self):
        self.assertEqual(set(game_fr.labels.keys()), set(game_en.labels.keys()))

    def test_descslash_symmetry(self):
        self.assertEqual(set(descslash.desc.keys()), set(descslash.desc_loc.keys()))
        self.assertIn("compile_method", descslash.desc)
        self.assertIn("compile_atk", descslash.desc)
        self.assertIn("convert_amount", descslash.desc)
        self.assertIn("confirm", descslash.desc)

    def test_template_variables_parity(self):
        """Vérifie que les chaînes françaises et anglaises attendent exactement les mêmes placeholders."""
        all_fr = {**fr.text, **game_fr.text}
        all_en = {**en.text, **game_en.text}
        placeholder_regex = re.compile(r"\{([a-zA-Z0-9_]+)\}")

        for key in all_fr:
            if key in all_en:
                fr_vars = set(placeholder_regex.findall(all_fr[key]))
                en_vars = set(placeholder_regex.findall(all_en[key]))
                self.assertEqual(
                    fr_vars, en_vars,
                    f"Incohérence des variables pour la clé '{key}': FR a {fr_vars}, EN a {en_vars}"
                )


class TestMathConfig(unittest.TestCase):
    """Teste le chargement sécurisé, la validation AST et l'évaluation mathématique."""

    def setUp(self):
        MathConfig.clear_cache()

    def test_load_config(self):
        cfg = MathConfig.load()
        self.assertIn("version", cfg)
        self.assertIn("initial_grant_usd", cfg)
        self.assertIn("firewall", cfg)
        self.assertIn("hash_challenge", cfg)
        self.assertIn("conversion", cfg)
        self.assertIn("mining_ram_bytes", cfg.get("module_stats", {}))
        self.assertIn("claim_cooldown_seconds", cfg.get("mining", {}))
        self.assertIn("compile", cfg)
        self.assertIn("attack_bits_per_s", cfg.get("module_stats", {}))

    def test_ast_security_validation(self):
        safe_tree = ast.parse("cost_t1 * (multiplier ** (tier - 1))", mode="eval")
        MathConfig.validate(safe_tree)

        unsafe_cases = [
            "__import__('os').system('ls')",
            "open('/etc/passwd').read()",
            "eval('2 + 2')",
            "(lambda x: x)(5)",
            "[x for x in range(10)]",
        ]
        for expr in unsafe_cases:
            with self.subTest(expression=expr):
                tree = ast.parse(expr, mode="eval")
                with self.assertRaises(ValueError):
                    MathConfig.validate(tree)

    def test_event_firewall_multipliers(self):
        self.assertEqual(MathConfig.get_event_firewall_multiplier(0), 1)
        self.assertEqual(MathConfig.get_event_firewall_multiplier(1), 1)
        self.assertEqual(MathConfig.get_event_firewall_multiplier(2), 2)
        self.assertEqual(MathConfig.get_event_firewall_multiplier(3), 2)
        self.assertEqual(MathConfig.get_event_firewall_multiplier(4), 3)
        self.assertEqual(MathConfig.get_event_firewall_multiplier(5), 3)

    def test_convert_rtm_to_usd_rate(self):
        """Conversion RTM → USD au taux configuré, arrondi à 2 décimales."""
        cfg = MathConfig.load()
        rate = Decimal(str(cfg["conversion"]["rtm_to_usd"]))
        self.assertEqual(MathConfig.rtm_to_usd_rate(), rate)
        self.assertEqual(MathConfig.convert_rtm_to_usd(Decimal("1")), rate.quantize(Decimal("0.01")))
        self.assertEqual(
            MathConfig.convert_rtm_to_usd(Decimal("0.00002")),
            (Decimal("0.00002") * rate).quantize(Decimal("0.01")),
        )

    def test_mining_ram_and_fill_time(self):
        """La cadence des claims reste de 8 à 75 minutes sans réputation."""
        cfg = MathConfig.load()
        rate_per_hs = Decimal(str(cfg["mining"]["rootium_per_hs_per_minute"]))
        bytes_per_rtm = Decimal(str(cfg["mining"]["bytes_per_rtm"]))
        expected_minutes = {1: 8, 2: 12, 3: 35, 4: 50, 5: 75}
        for tier, minutes in expected_minutes.items():
            hs = Decimal(str(MathConfig.get_module_stat("mining", tier)))
            ram = Decimal(str(MathConfig.get_module_ram(tier)))
            fill_min = (ram / bytes_per_rtm) / (hs * rate_per_hs)
            self.assertEqual(int(fill_min.to_integral_value()), minutes, f"T{tier} doit se remplir en {minutes} min")

    def test_format_memory(self):
        self.assertEqual(MathConfig.format_memory(200), "200 o")
        self.assertEqual(MathConfig.format_memory(3000), "3.00 Ko")
        self.assertEqual(MathConfig.format_memory(0), "0 o")


class TestFormatters(unittest.TestCase):
    """Teste les modules de formatage de temps et devises."""

    def test_format_duration(self):
        self.assertEqual(format_duration(0), "0s")
        self.assertEqual(format_duration(42), "42s")
        self.assertEqual(format_duration(60), "1min")
        self.assertEqual(format_duration(905), "15min 5s")
        self.assertEqual(format_duration(3600), "1h")
        self.assertEqual(format_duration(85593), "23h 46min 33s")
        self.assertEqual(format_duration(184204), "2j 3h 10min 4s")

    def test_format_remaining_time(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        until = datetime(2026, 1, 1, 12, 10, 30)
        self.assertEqual(format_remaining_time(until, now), "10min 30s")

    def test_format_usd(self):
        self.assertEqual(text.format_usd(1000), "1,000")
        self.assertEqual(text.format_usd(12.5), "12.50")
        self.assertEqual(text.format_usd(Decimal("3.15")), "3.15")
        self.assertEqual(text.format_usd(0), "0")
        self.assertEqual(text.format_usd(None), "0")

    def test_format_rtm(self):
        self.assertEqual(text.format_rtm(0), "0.00000")
        self.assertEqual(text.format_rtm(Decimal("0.00002")), "0.00002")
        self.assertEqual(text.format_rtm(Decimal("1.234567")), "1.23457")
        self.assertEqual(text.format_rtm(Decimal("0.0000001")), ">0.00001")
        self.assertEqual(text.format_rtm(-1), "0.00000")

    def test_get_for_lang(self):
        fr_ping = text.get_for_lang("fr", "ping_response", latency=50)
        en_ping = text.get_for_lang("en", "ping_response", latency=50)
        self.assertIn("50ms", fr_ping)
        self.assertIn("50ms", en_ping)
        self.assertIn("Pong", fr_ping)
        self.assertIn("Pong", en_ping)


class TestPricingAndEconomics(unittest.TestCase):
    """Teste le calcul des prix de modules et les vérifications de tiers."""

    def test_module_prices(self):
        cfg = MathConfig.load()
        mining_t1 = Decimal(str(cfg["mining"]["cost_t1_usd"]))
        combat_mult = Decimal(str(cfg["beta"].get("cost_multiplier", cfg["mining"]["cost_multiplier"])))
        attack_t1 = Decimal(str(cfg["beta"]["attack_price_t1_rtm"]))
        bay_t1 = Decimal(str(cfg["beta"]["bay_defense_usd"]))

        usd_m1, rtm_m1 = _calculate_module_price("mining_t1", 1)
        self.assertEqual(usd_m1, mining_t1)
        self.assertEqual(rtm_m1, Decimal("0"))

        usd_a1, rtm_a1 = _calculate_module_price("attack_t1", 1)
        self.assertEqual(usd_a1, Decimal("0"))
        self.assertEqual(rtm_a1, attack_t1)

        usd_bd, _ = _calculate_module_price("bay_defense_t1", 1)
        self.assertEqual(usd_bd, bay_t1)

        usd_bd2, _ = _calculate_module_price("bay_defense_t2", 2)
        self.assertEqual(usd_bd2, bay_t1 * combat_mult)

        with self.assertRaises(GameError):
            _calculate_module_price("network_defense", 1)

        with self.assertRaises(GameError):
            _calculate_module_price("invalid_module", 1)

    def test_module_stats_and_firewall_defense(self):
        cfg = MathConfig.load()
        hs = cfg["module_stats"]["mining_hashrate_hs"]
        ram = cfg["module_stats"]["mining_ram_bytes"]
        atk = cfg["module_stats"]["attack_bits_per_s"]
        bdef = cfg["module_stats"]["bay_defense_power"]

        self.assertEqual(MathConfig.get_module_stat("mining", 1), int(hs["1"]))
        self.assertEqual(MathConfig.get_module_stat("mining", 5), int(hs["5"]))
        self.assertEqual(MathConfig.get_module_ram(1), int(ram["1"]))
        self.assertEqual(MathConfig.get_module_ram(5), int(ram["5"]))
        self.assertEqual(MathConfig.get_module_stat("attack", 1), int(atk["1"]))
        self.assertEqual(MathConfig.get_module_stat("bay_defense", 1), int(bdef["1"]))
        self.assertEqual(MathConfig.get_module_stat("unknown", 1), 0)

        self.assertEqual(MathConfig.get_firewall_network_defense(0), 0)
        self.assertEqual(MathConfig.get_firewall_network_defense(1), 100)
        self.assertEqual(MathConfig.get_firewall_network_defense(2), 300)
        self.assertEqual(MathConfig.get_firewall_network_defense(5), 5000)

        self.assertEqual(MathConfig.format_hashrate(50), "50 H/s")
        self.assertEqual(MathConfig.format_hashrate(1500), "1.50 KH/s")
        self.assertEqual(MathConfig.format_hashrate(2500000), "2.50 MH/s")
        self.assertEqual(MathConfig.format_bits_per_s(5), "5 Bit/s")
        self.assertEqual(MathConfig.format_bits_per_s(1500), "1.50 KBit/s")
        self.assertEqual(MathConfig.format_bits_per_s(2_500_000), "2.50 MBit/s")


class TestChallengeManagers(unittest.TestCase):
    """Teste la logique des 7 mini-jeux d'événements."""

    def setUp(self):
        self.tx = MockTransaction()
        self.actor = 123456789
        self.tx.players[self.actor] = {
            "discord_id": self.actor,
            "dollars": Decimal("1000.00"),
            "rootium": Decimal("0.00000"),
            "firewall_level": 0,
            "events_won": 0,
        }

    def test_decode_challenge_generation(self):
        self.assertEqual(len(COORDINATES), 16, "COORDINATES doit contenir exactement 16 cellules.")
        challenge = create_decode_challenge()
        self.assertIn("grid", challenge)
        self.assertIn("sequence", challenge)
        self.assertIn("target", challenge)
        self.assertEqual(len(challenge["grid"]), 16)
        self.assertEqual(len(challenge["sequence"]), 4)
        self.assertEqual(len(challenge["target"]), 4)

    def test_decode_process(self):
        DecodeManager._active_challenge = None
        info = DecodeManager.process(self.tx, self.actor, "TestGuild", None)
        self.assertEqual(info["status"], "active_info")

        wrong = DecodeManager.process(self.tx, self.actor, "TestGuild", "ZZZZ")
        self.assertEqual(wrong["status"], "wrong")

        target = DecodeManager._active_challenge["target"]
        win = DecodeManager.process(self.tx, self.actor, "TestGuild", target.lower())
        self.assertEqual(win["status"], "won")
        self.assertEqual(win["winner"], self.actor)
        self.assertGreater(self.tx.players[self.actor]["dollars"], Decimal("1000"))
        self.assertEqual(self.tx.players[self.actor]["events_won"], 1)

    def test_anomaly_challenge_generation(self):
        challenge = create_anomaly_challenge()
        lines = challenge["block_display"].split("\n")
        self.assertEqual(len(lines), 10, "Le bloc d'anomalie doit contenir 10 lignes.")
        for line in lines:
            self.assertEqual(len(line), 16, "Chaque ligne doit avoir 16 caractères.")
        total_digits = sum(1 for c in challenge["block_display"] if c.isdigit())
        self.assertEqual(total_digits, 1, "Il doit y avoir exactement un seul chiffre parasite.")

    def test_anomaly_process(self):
        AnomalyManager._active_challenge = None
        info = AnomalyManager.process(self.tx, self.actor, "TestGuild", None)
        self.assertEqual(info["status"], "active_info")

        target_line = AnomalyManager._active_challenge["target_line"]
        wrong_line = (target_line % 10) + 1
        wrong = AnomalyManager.process(self.tx, self.actor, "TestGuild", wrong_line)
        self.assertEqual(wrong["status"], "wrong")

        win = AnomalyManager.process(self.tx, self.actor, "TestGuild", target_line)
        self.assertEqual(win["status"], "won")
        self.assertEqual(win["line"], target_line)

    def test_buffer_challenge_generation(self):
        challenge = create_buffer_challenge()
        self.assertEqual(len(challenge["fragment_map"]), 6)
        self.assertEqual(len(challenge["target"]), 6)
        self.assertNotEqual(challenge["displayed_order"], [1, 2, 3, 4, 5, 6], "L'ordre ne doit pas être pré-trié.")

    def test_buffer_process(self):
        BufferManager._active_challenge = None
        info = BufferManager.process(self.tx, self.actor, "TestGuild", None)
        self.assertEqual(info["status"], "active_info")

        target = BufferManager._active_challenge["target"]
        wrong = BufferManager.process(self.tx, self.actor, "TestGuild", "WRONGX")
        self.assertEqual(wrong["status"], "wrong")

        win = BufferManager.process(self.tx, self.actor, "TestGuild", target.lower())
        self.assertEqual(win["status"], "won")

    def test_signal_challenge_generation(self):
        challenge = create_signal_challenge()
        letters = challenge["block_display"].split(" ")
        self.assertEqual(len(letters), 15)
        winning_letter = challenge["winning_letter"]
        count_win = sum(1 for letter in letters if letter == winning_letter)
        self.assertEqual(count_win, 8, "La lettre dominante doit apparaître 8 fois.")

    def test_signal_process(self):
        SignalManager._active_challenge = None
        info = SignalManager.process(self.tx, self.actor, "TestGuild", None)
        self.assertEqual(info["status"], "active_info")

        winning_letter = SignalManager._active_challenge["winning_letter"]
        wrong_letter = [l for l in string.ascii_uppercase if l != winning_letter][0]
        wrong = SignalManager.process(self.tx, self.actor, "TestGuild", wrong_letter)
        self.assertEqual(wrong["status"], "wrong")

        win = SignalManager.process(self.tx, self.actor, "TestGuild", winning_letter.lower())
        self.assertEqual(win["status"], "won")

    def test_packet_challenge_generation(self):
        challenge = create_packet_challenge()
        missing = challenge["missing_packet"]
        remaining = challenge["remaining"]
        self.assertEqual(len(remaining), 9)
        self.assertNotIn(missing, remaining)
        self.assertIn(missing, range(1, 11))

    def test_packet_process(self):
        PacketManager._active_challenge = None
        info = PacketManager.process(self.tx, self.actor, "TestGuild", None)
        self.assertEqual(info["status"], "active_info")

        missing = PacketManager._active_challenge["missing_packet"]
        wrong_packet = [p for p in range(1, 11) if p != missing][0]
        wrong = PacketManager.process(self.tx, self.actor, "TestGuild", wrong_packet)
        self.assertEqual(wrong["status"], "wrong")

        win = PacketManager.process(self.tx, self.actor, "TestGuild", missing)
        self.assertEqual(win["status"], "won")

    def test_hash_process(self):
        HashManager._active_challenge = None
        info = HashManager.process(self.tx, self.actor, "TestGuild", None)
        self.assertEqual(info["status"], "active_info")

        target = HashManager._active_challenge["target"]
        if target > HashManager._active_challenge["current_min"]:
            res = HashManager.process(self.tx, self.actor, "TestGuild", target - 1)
            self.assertEqual(res["status"], "too_low")
            self.assertEqual(res["current_min"], target)

        if target < HashManager._active_challenge["current_max"]:
            res = HashManager.process(self.tx, self.actor, "TestGuild", target + 1)
            self.assertEqual(res["status"], "too_high")
            self.assertEqual(res["current_max"], target)

        win = HashManager.process(self.tx, self.actor, "TestGuild", target)
        self.assertEqual(win["status"], "won")

    def test_pin_process(self):
        PinManager._active_challenge = None
        info = PinManager.process(self.tx, self.actor, "TestGuild", None)
        self.assertEqual(info["status"], "active_info")

        target = PinManager._active_challenge["target"]
        win = PinManager.process(self.tx, self.actor, "TestGuild", target)
        self.assertEqual(win["status"], "won")
        self.assertEqual(win["winner"], self.actor)

    def test_pin_too_low_and_too_high(self):
        PinManager._active_challenge = None
        PinManager.process(self.tx, self.actor, "TestGuild", None)
        target = PinManager._active_challenge["target"]
        if target > PinManager._active_challenge["min_bound"]:
            low = PinManager.process(self.tx, self.actor, "TestGuild", target - 1)
            self.assertEqual(low["status"], "too_low")
            self.assertEqual(low["current_min"], target)
        if target < PinManager._active_challenge["max_bound"]:
            high = PinManager.process(self.tx, self.actor, "TestGuild", target + 1)
            self.assertEqual(high["status"], "too_high")
            self.assertEqual(high["current_max"], target)

    def test_hash_and_pin_range_from_math(self):
        cfg = MathConfig.load()
        hash_ch = create_hash_challenge()
        pin_ch = create_pin_challenge()
        self.assertEqual(
            hash_ch["max_bound"] - hash_ch["min_bound"],
            int(cfg["hash_challenge"]["range_size"]),
        )
        self.assertEqual(
            pin_ch["max_bound"] - pin_ch["min_bound"],
            int(cfg["pin_challenge"]["range_size"]),
        )
        hash_min = Decimal(str(cfg["hash_challenge"]["reward_min_usd"]))
        hash_max = Decimal(str(cfg["hash_challenge"]["reward_max_usd"]))
        reward = Decimal(str(hash_ch["reward"]))
        self.assertGreaterEqual(reward, hash_min)
        self.assertLessEqual(reward, hash_max)

    def test_challenge_win_records_daily_stats_and_events(self):
        DecodeManager._active_challenge = None
        DecodeManager.process(self.tx, self.actor, "TestGuild", None)
        DecodeManager.process(self.tx, self.actor, "TestGuild", "ZZZZ")
        self.assertEqual(self.tx.daily_stats[self.actor]["events_participated"], 1)

        self.tx.players[self.actor]["firewall_level"] = 2
        before = Decimal(str(self.tx.players[self.actor]["dollars"]))
        target = DecodeManager._active_challenge["target"]
        win = DecodeManager.process(self.tx, self.actor, "TestGuild", target)
        self.assertEqual(win["status"], "won")
        self.assertEqual(win["multiplier"], MathConfig.get_event_firewall_multiplier(2))
        self.assertEqual(self.tx.players[self.actor]["events_won"], 1)
        self.assertEqual(self.tx.daily_stats[self.actor]["events_won"], 1)
        self.assertEqual(self.tx.events["decode"]["last_found_by"], self.actor)
        self.assertGreater(self.tx.events["decode"]["next_at"], self.tx.now)
        self.assertEqual(
            self.tx.players[self.actor]["dollars"],
            before + win["reward"],
        )

    def test_events_manager_status(self):
        status = EventsManager.get_all_events_status(self.tx)
        self.assertIn("events", status)
        for ev in ["hash", "pin", "decode", "anomaly", "buffer", "signal", "packet"]:
            self.assertIn(ev, status["events"])
            self.assertEqual(status["events"][ev]["status"], "active")


class TestPlayerAndGameOperations(unittest.TestCase):
    """Teste les opérations métier Player (network, buy, upgrade, rep, top)."""

    def setUp(self):
        self.tx = MockTransaction()
        self.actor = 999
        Player.network(self.tx, self.actor)

    def test_network_creation(self):
        p = self.tx.players.get(self.actor)
        self.assertIsNotNone(p)
        grant = Decimal(str(MathConfig.load()["initial_grant_usd"]))
        self.assertEqual(p["dollars"], grant)

    def test_buy_quote_and_execution(self):
        cfg = MathConfig.load()
        price = Decimal(str(cfg["mining"]["cost_t1_usd"]))
        hs = MathConfig.get_module_stat("mining", 1)
        ram = MathConfig.get_module_ram(1)
        grant = Decimal(str(cfg["initial_grant_usd"]))

        quote = Player.buy(self.tx, self.actor, kind="mining", tier=1, confirm=False)
        self.assertTrue(quote.get("buy_quote"))
        self.assertEqual(quote.get("usd_price"), price)
        self.assertEqual(quote.get("stat_gain"), hs)
        self.assertEqual(quote.get("stat_unit"), "H/s")
        self.assertEqual(quote.get("stat_current_formatted"), "0 H/s")
        self.assertEqual(quote.get("stat_new_formatted"), MathConfig.format_hashrate(hs))
        self.assertEqual(quote.get("ram_gain"), ram)

        bought = Player.buy(self.tx, self.actor, kind="mining", tier=1, confirm=True)
        self.assertTrue(bought.get("bought"))
        self.assertEqual(self.tx.players[self.actor]["dollars"], grant - price)
        self.assertEqual(self.tx.players[self.actor]["mining_t1"], 1)
        self.assertEqual(bought.get("stat_new_formatted"), MathConfig.format_hashrate(hs))

    def test_buy_attack_and_bay_defense(self):
        # Crédit de Rootium pour tester l'achat d'attaque (T1 requiert Pare-feu Niv 1)
        self.tx.players[self.actor]["firewall_level"] = 1
        self.tx.players[self.actor]["rootium"] = Decimal("10.00000")

        # Achat Attaque T1
        atk_quote = Player.buy(self.tx, self.actor, kind="attack", tier=1, confirm=False)
        self.assertEqual(atk_quote.get("stat_gain"), 5)
        self.assertEqual(atk_quote.get("stat_unit"), "Bit/s")
        self.assertEqual(atk_quote.get("stat_current_formatted"), "0 Bit/s")
        self.assertEqual(atk_quote.get("stat_new_formatted"), "5 Bit/s")

        # Achat Défense de Baie T1 (avec alias 'defense' et 'bay_defense')
        def_quote = Player.buy(self.tx, self.actor, kind="bay_defense", tier=1, confirm=False)
        self.assertEqual(def_quote.get("stat_gain"), 10)
        self.assertEqual(def_quote.get("stat_unit"), "DEF")
        self.assertEqual(def_quote.get("stat_current_formatted"), "0 DEF")
        self.assertEqual(def_quote.get("stat_new_formatted"), "10 DEF")

        def_alias_quote = Player.buy(self.tx, self.actor, kind="defense", tier=1, confirm=False)
        self.assertEqual(def_alias_quote.get("stat_gain"), 10)
        self.assertEqual(def_alias_quote.get("stat_unit"), "DEF")
        self.assertEqual(def_alias_quote.get("kind"), "defense")

        # Rejet de network_defense à l'achat direct
        with self.assertRaises(GameError) as cm:
            Player.buy(self.tx, self.actor, kind="network_defense", tier=1, confirm=False)
        self.assertEqual(cm.exception.key, "invalid_selection")

    def test_network_stats_and_firewall_defense_sync(self):
        self.tx.players[self.actor]["firewall_level"] = 2
        net = Player.network(self.tx, self.actor)
        self.assertIn("stats", net)
        self.assertEqual(net["network_defense"], 300)
        self.assertEqual(net["stats"]["network_defense"], 300)

    def test_buy_invalid_tier(self):
        with self.assertRaises(GameError) as cm:
            Player.buy(self.tx, self.actor, kind="mining", tier=99, confirm=False)
        self.assertEqual(cm.exception.key, "invalid_selection")

    def test_upgrade_quote_and_execution(self):
        upgrade_cost, _ = _calculate_module_price("firewall", 1)
        self.tx.players[self.actor]["dollars"] = upgrade_cost

        quote = Player.upgrade(self.tx, self.actor, confirm=False)
        self.assertTrue(quote.get("upgrade_quote"))
        self.assertEqual(quote.get("current_level"), 0)
        self.assertEqual(quote.get("next_level"), 1)
        self.assertEqual(quote.get("defense_gain"), 100)
        self.assertEqual(quote.get("defense_next"), 100)
        self.assertEqual(quote.get("defense_current"), 0)
        self.assertEqual(quote.get("usd_price"), upgrade_cost)

        started = Player.upgrade(self.tx, self.actor, confirm=True)
        self.assertTrue(started.get("upgrade_started"))
        self.assertEqual(started.get("defense_gain"), 100)
        self.assertEqual(started.get("defense_next"), 100)
        self.assertEqual(self.tx.players[self.actor]["dollars"], Decimal("0.00"))
        self.assertEqual(len(self.tx.upgrades), 1)

        with self.assertRaises(GameError) as cm:
            Player.upgrade(self.tx, self.actor, confirm=False)
        self.assertEqual(cm.exception.key, "upgrade_in_progress")

    def test_complete_expired_upgrades(self):
        upgrade_cost, _ = _calculate_module_price("firewall", 1)
        self.tx.players[self.actor]["dollars"] = upgrade_cost
        Player.upgrade(self.tx, self.actor, confirm=True)
        self.tx.now += timedelta(hours=6)
        delivered = UpgradesDB.complete_and_delete_expired(self.tx)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(self.tx.players[self.actor]["firewall_level"], 1)
        self.assertEqual(len(self.tx.upgrades), 0)
        self.assertIn(f"player:{self.actor}", self.tx.acquired_locks)

    def test_reputation_system(self):
        target_id = 888
        Player.network(self.tx, target_id)

        with self.assertRaises(GameError) as cm:
            Player.give_reputation(self.tx, self.actor, self.actor)
        self.assertEqual(cm.exception.key, "self_target")

        rep = Player.give_reputation(self.tx, self.actor, target_id)
        self.assertTrue(rep.get("reputation_given"))
        self.assertEqual(self.tx.players[target_id]["reputation"], 1)

        with self.assertRaises(GameError) as cm:
            Player.give_reputation(self.tx, self.actor, target_id)
        self.assertEqual(cm.exception.key, "cooldown")

    def test_convert_rtm_to_usd(self):
        """Vérifie le devis et la vente RTM → USD au taux fixe."""
        self.tx.players[self.actor]["rootium"] = Decimal("0.00010")
        self.tx.players[self.actor]["dollars"] = Decimal("10.00")

        quote = Player.convert(self.tx, self.actor, amount="0.00002", confirm=False)
        self.assertTrue(quote.get("convert_quote"))
        self.assertEqual(quote.get("rtm_amount"), Decimal("0.00002"))
        self.assertEqual(quote.get("usd_amount"), MathConfig.convert_rtm_to_usd("0.00002"))
        self.assertEqual(self.tx.players[self.actor]["rootium"], Decimal("0.00010"))

        sold = Player.convert(self.tx, self.actor, amount="0.00002", confirm=True)
        self.assertTrue(sold.get("converted"))
        self.assertEqual(self.tx.players[self.actor]["rootium"], Decimal("0.00008"))
        self.assertEqual(self.tx.players[self.actor]["dollars"], Decimal("10.00") + MathConfig.convert_rtm_to_usd("0.00002"))

        with self.assertRaises(GameError) as cm:
            Player.convert(self.tx, self.actor, amount="1", confirm=True)
        self.assertEqual(cm.exception.key, "insufficient_funds_rtm")

    def test_convert_sell_all_and_quote_changed(self):
        self.tx.players[self.actor]["rootium"] = Decimal("0.00010")
        self.tx.players[self.actor]["dollars"] = Decimal("0.00")

        quote = Player.convert(self.tx, self.actor, amount="all", all=True, confirm=False)
        self.assertTrue(quote.get("convert_quote"))
        self.assertEqual(quote.get("rtm_amount"), Decimal("0.00010"))
        sold = Player.convert(self.tx, self.actor, amount="all", all=True, confirm=True)
        self.assertTrue(sold.get("converted"))
        self.assertEqual(self.tx.players[self.actor]["rootium"], Decimal("0.00000"))
        self.assertGreater(self.tx.players[self.actor]["dollars"], Decimal("0"))

        with self.assertRaises(GameError) as cm:
            Player.convert(self.tx, self.actor, amount="0.00002", confirm=True, rate="1")
        self.assertEqual(cm.exception.key, "quote_changed")

        with self.assertRaises(GameError) as cm:
            Player.convert(self.tx, self.actor, amount="0.0000001", confirm=False)
        self.assertEqual(cm.exception.key, "invalid_amount")

    def test_top_leaderboard(self):
        for i in range(1, 5):
            uid = 1000 + i
            Player.network(self.tx, uid)
            self.tx.players[uid]["reputation"] = i * 10
            self.tx.players[uid]["dollars"] = Decimal(str(i * 500))

        top_rep = Player.top(self.tx, "reputation")
        self.assertEqual(len(top_rep["ranking"]), 5)
        self.assertEqual(top_rep["ranking"][0]["score"], 40)

        top_usd = Player.top(self.tx, "usd")
        self.assertEqual(top_usd["ranking"][0]["score"], Decimal("2000.00"))

    def test_buy_insufficient_funds(self):
        # Solde de base : 1000 USD, 0 RTM
        # bay_defense_t1 coûte 50 USD, firewall niveau 1 requis
        # Si pare-feu est niveau 0 -> GameError('firewall_required')
        with self.assertRaises(GameError) as cm:
            Player.buy(self.tx, self.actor, kind="bay_defense", tier=1, confirm=False)
        self.assertEqual(cm.exception.key, "firewall_required")

        # Donner le niveau 1 de pare-feu au joueur
        self.tx.players[self.actor]["firewall_level"] = 1
        # attack_t1 coûte du RTM (1.5 RTM), le joueur a 0 RTM -> GameError('insufficient_funds_rtm')
        with self.assertRaises(GameError) as cm:
            Player.buy(self.tx, self.actor, kind="attack", tier=1, confirm=False)
        self.assertEqual(cm.exception.key, "insufficient_funds_rtm")

        # Réduire le solde USD à 0 et tenter d'acheter du minage
        self.tx.players[self.actor]["dollars"] = Decimal("0.00")
        with self.assertRaises(GameError) as cm:
            Player.buy(self.tx, self.actor, kind="mining", tier=1, confirm=False)
        self.assertEqual(cm.exception.key, "insufficient_funds_usd")

    def test_upgrade_max_level(self):
        self.tx.players[self.actor]["firewall_level"] = 5
        with self.assertRaises(GameError) as cm:
            Player.upgrade(self.tx, self.actor, confirm=False)
        self.assertEqual(cm.exception.key, "maximum_level")


class TestChallengesCooldownState(unittest.TestCase):
    """Teste le comportement de tous les mini-jeux lorsqu'ils sont en période de cooldown."""

    def setUp(self):
        self.tx = MockTransaction()
        self.actor = 55555
        self.tx.players[self.actor] = {
            "discord_id": self.actor,
            "dollars": Decimal("1000.00"),
            "rootium": Decimal("0.00000"),
            "firewall_level": 0,
            "events_won": 0,
        }
        # Définir un cooldown futur pour tous les événements
        future_time = self.tx.now + timedelta(minutes=20)
        for ev in ["hash", "pin", "decode", "anomaly", "buffer", "signal", "packet"]:
            self.tx.events[ev] = {
                "event": ev,
                "next_at": future_time,
                "last_found_by": 99999,
                "last_found_on": "CooldownServer",
                "last_reward": Decimal("12.50"),
            }

    def test_all_challenges_return_cooldown(self):
        managers = [
            (HashManager, "hash"),
            (PinManager, "pin"),
            (DecodeManager, "decode"),
            (AnomalyManager, "anomaly"),
            (BufferManager, "buffer"),
            (SignalManager, "signal"),
            (PacketManager, "packet"),
        ]
        for mgr, name in managers:
            with self.subTest(challenge=name):
                res = mgr.process(self.tx, self.actor, "TestGuild", None)
                self.assertEqual(res["status"], "cooldown")
                self.assertEqual(res["last_found_by"], 99999)
                self.assertEqual(res["last_found_on"], "CooldownServer")
                self.assertEqual(res["last_reward"], Decimal("12.50"))
                self.assertGreater(res["remaining_seconds"], 0)


class TestDatabaseSerializersAndPrefix(unittest.TestCase):
    """Teste la sérialisation JSON et la validation des préfixes."""

    def test_database_encode_decode(self):
        from game.db.database import encode, decode
        data_obj = {
            "amount": 123.45678,
            "date": datetime(2026, 9, 13, 22, 0, 0),
            "text": "Root System",
            "number": 42,
        }
        encoded = encode(data_obj)
        self.assertIsInstance(encoded, str)
        decoded = decode(encoded)
        self.assertEqual(decoded["number"], 42)
        self.assertEqual(decoded["text"], "Root System")
        self.assertEqual(decoded["amount"], Decimal("123.45678"))

    def test_mysql_schema_error_is_not_database_unavailable(self):
        """Une erreur de schéma/contrainte ne doit plus être vendue comme une panne de connexion."""
        import mysql.connector
        from game.db.database import Database

        schema_err = mysql.connector.Error("Field 'bits_per_s' doesn't have a default value")
        schema_err.errno = 1364
        with self.assertRaises(mysql.connector.Error) as cm:
            try:
                raise schema_err
            except mysql.connector.Error as error:
                Database._raise_mysql(error)
        self.assertEqual(cm.exception.errno, 1364)

        gone = mysql.connector.Error("MySQL server has gone away")
        gone.errno = 2006
        with self.assertRaises(GameError) as cm:
            try:
                raise gone
            except mysql.connector.Error as error:
                Database._raise_mysql(error)
        self.assertEqual(cm.exception.key, "database_unavailable")
        self.assertIs(cm.exception.__cause__, gone)

    def test_prefix_validation(self):
        from utils.prefix_manager import set_prefix
        import asyncio

        # Préfixe avec espace interdit
        with self.assertRaises(ValueError):
            asyncio.run(set_prefix(1234, "r oot"))

        # Préfixe vide interdit
        with self.assertRaises(ValueError):
            asyncio.run(set_prefix(1234, "   "))

        # Préfixe trop long (>32 caractères) interdit
        with self.assertRaises(ValueError):
            asyncio.run(set_prefix(1234, "a" * 33))


class TestRootEmbedDesign(unittest.TestCase):
    """Teste la cohérence visuelle et chromatique des RootEmbed."""

    def test_embed_colors_and_labels(self):
        from utils.root_embed import RootEmbed
        mock_ctx = MagicMock()
        mock_ctx.interaction = None
        mock_ctx.author.id = 12345
        mock_ctx.bot.user = None

        expected_actions = [
            'buy', 'upgrade', 'reputation', 'top', 'hash', 'pin',
            'event', 'decode', 'anomaly', 'buffer', 'signal', 'packet',
            'convert', 'claim', 'trade', 'compile',
        ]
        for action in expected_actions:
            with self.subTest(action=action):
                self.assertIn(action, RootEmbed.COLORS)
                embed = RootEmbed(mock_ctx, action, "Content test")
                self.assertEqual(embed.color, RootEmbed.COLORS[action])
                self.assertTrue(embed.title.startswith("> 🌐") or len(embed.title) > 0)

    def test_network_embed_ascii_box_structure(self):
        from commands.game.network import Network
        cog = Network(MagicMock())
        mock_ctx = MagicMock()
        mock_ctx.author.id = 12345
        mock_ctx.author.display_name = "Juels"
        mock_ctx.interaction = None

        result = {
            "discord_id": 12345,
            "dollars": Decimal("1250.00"),
            "rootium": Decimal("14.50000"),
            "firewall_level": 2,
            "reputation": 12,
            "mining_t1": 4,
            "mining_t2": 2,
            "attack_t1": 2,
            "bay_defense_t1": 1,
            "bay_defense_t2": 1,
            "secret_id": "000042",
            "secret_next_ts": 1760000000,
        }
        embed = cog._build_network_embed(mock_ctx, result)
        self.assertIsNotNone(embed)
        # Économie, Sécurité, Secret ID, ATK, baies, total
        self.assertEqual(len(embed.fields), 6)

        sec_field = embed.fields[1]
        self.assertIn("360 pts", sec_field.value)

        secret_field = embed.fields[2]
        self.assertFalse(secret_field.inline)
        self.assertIn("000042", secret_field.value)
        self.assertIn("<t:1760000000:R>", secret_field.value)

        atk_field = embed.fields[3]
        self.assertFalse(atk_field.inline)
        self.assertIn("`0`", atk_field.value)

        bays_field = embed.fields[4]
        self.assertFalse(bays_field.inline)
        self.assertIn("01", bays_field.value)
        self.assertIn("02", bays_field.value)
        self.assertIn("03", bays_field.value)

        total_hs = (
            4 * MathConfig.get_module_stat("mining", 1)
            + 2 * MathConfig.get_module_stat("mining", 2)
        )
        total_bits = 2 * MathConfig.get_module_stat("attack", 1)
        total_field = embed.fields[5]
        self.assertFalse(total_field.inline)
        self.assertIn("TOTAL INFRASTRUCTURE", total_field.name)
        self.assertIn(MathConfig.format_hashrate(total_hs), total_field.value)
        self.assertIn(MathConfig.format_bits_per_s(total_bits), total_field.value)
        self.assertIn("60 DEF", total_field.value)
        self.assertIn("300 DEF", total_field.value)
        self.assertIn(MathConfig.format_memory(
            4 * MathConfig.get_module_ram(1) + 2 * MathConfig.get_module_ram(2)
        ), total_field.value)
        footer_text = embed.footer.text or ""
        self.assertNotIn("000042", footer_text)
        cog.cog_unload()

    def test_network_embed_atk_and_hack_progress(self):
        from commands.game.network import Network
        cog = Network(MagicMock())
        mock_ctx = MagicMock()
        mock_ctx.author.id = 12345
        mock_ctx.author.display_name = "Juels"
        mock_ctx.interaction = None
        expires = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
        result = {
            "discord_id": 12345,
            "dollars": Decimal("100.00"),
            "rootium": Decimal("1.00000"),
            "firewall_level": 1,
            "reputation": 0,
            "attack_points": 42,
            "secret_id": "000042",
            "secret_next_ts": 1760000000,
            "pending_hack": {
                "method": "skilled",
                "atk_yield": 25,
                "expires_at": expires,
            },
        }
        embed = cog._build_network_embed(mock_ctx, result)
        self.assertEqual(len(embed.fields), 6)
        secret_field = embed.fields[2]
        self.assertIn("000042", secret_field.value)
        atk_field = embed.fields[3]
        self.assertIn("`42`", atk_field.value)
        self.assertIn("25 ATK", atk_field.value)
        self.assertIn(f"<t:{int(expires.timestamp())}:R>", atk_field.value)
        cog.cog_unload()


class TestSecurityAndChecks(unittest.TestCase):
    """Teste les vérifications de rôles, bannissements et mode maintenance."""

    def test_banned_cache_and_atomicity(self):
        import tempfile
        from unittest.mock import patch
        import utils.check

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_banned = Path(tmpdir) / "banned.json"
            tmp_banned.write_text(json.dumps([111, 222]) + "\n", encoding="utf-8")
            
            orig_cache = Check._banned_cache
            try:
                Check._banned_cache = None
                with patch.object(utils.check, "BANNED_FILE", tmp_banned):
                    checks = Check()
                    test_id = 999999999
                    self.assertFalse(checks.is_banned(test_id))
                    
                    # Vérifie le bannissement
                    self.assertTrue(checks.set_banned(test_id, True))
                    self.assertTrue(checks.is_banned(test_id))
                    
                    # Vérification de l'écriture sur fichier temporaire
                    content = json.loads(tmp_banned.read_text(encoding="utf-8"))
                    self.assertIn(test_id, content)
                    
                    # Vérifie le débannissement
                    self.assertTrue(checks.set_banned(test_id, False))
                    self.assertFalse(checks.is_banned(test_id))
            finally:
                Check._banned_cache = orig_cache

    def test_maintenance_modes(self):
        checks = Check()
        for true_val in ["1", "true", "yes", "TRUE", "Yes "]:
            os.environ["MAINTENANCE"] = true_val
            self.assertTrue(checks.maintenance_enabled(), f"Devrait être True pour '{true_val}'")
        for false_val in ["0", "false", "no", "", "other"]:
            os.environ["MAINTENANCE"] = false_val
            self.assertFalse(checks.maintenance_enabled(), f"Devrait être False pour '{false_val}'")


class TestGuildInfoCommand(unittest.IsolatedAsyncioTestCase):
    """Teste la commande d'administration guildinfo et sa vue associée."""

    async def test_guildinfo_cog_structure(self):
        import discord
        from commands.admin.guildinfo import GuildInfo
        mock_bot = MagicMock()
        cog = GuildInfo(mock_bot)

        # Vérifie qu'il s'agit bien d'une commande à préfixe
        command = cog.guildinfo
        self.assertIsInstance(command, discord.ext.commands.Command)
        self.assertEqual(command.name, "guildinfo")

        # Vérifie qu'aucune commande Slash n'est enregistrée sur ce Cog
        slash_commands = [
            attr for attr in dir(cog)
            if isinstance(getattr(cog, attr), discord.commands.ApplicationCommand)
        ]
        self.assertEqual(len(slash_commands), 0, "guildinfo ne doit pas être une commande slash.")

    async def test_guildinfo_view_components(self):
        import discord
        from commands.admin.guildinfo import GuildInfoView
        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_guild.id = 123456789
        mock_guild.name = "Test Server"

        view = GuildInfoView(mock_bot, mock_guild, 99999)
        # La vue doit comporter les 2 boutons : Liste des membres et Liste des salons
        self.assertEqual(len(view.children), 2)
        button_members = view.children[0]
        self.assertIsInstance(button_members, discord.ui.Button)
        self.assertEqual(button_members.label, "Liste des membres")

        button_channels = view.children[1]
        self.assertIsInstance(button_channels, discord.ui.Button)
        self.assertEqual(button_channels.label, "Liste des salons")

    async def test_guildinfo_execution_and_embed(self):
        import discord
        from unittest.mock import AsyncMock
        from commands.admin.guildinfo import GuildInfo

        mock_bot = MagicMock()
        mock_bot.user.id = 777777777
        mock_guild = MagicMock()
        mock_guild.id = 987654321
        mock_guild.name = "Mock Guild"
        mock_guild.created_at = datetime(2022, 1, 1, tzinfo=timezone.utc)
        mock_guild.owner = None
        mock_guild.owner_id = 111111111
        mock_guild.description = "A mock guild for testing"
        mock_guild.preferred_locale = "fr"
        mock_guild.shard_id = 0
        mock_guild.vanity_url_code = None
        mock_guild.member_count = 100
        mock_guild.members = []
        mock_guild.approximate_presence_count = 42
        mock_guild.max_members = 250000
        mock_guild.roles = [MagicMock(name="@everyone", id=1), MagicMock(name="Admin", id=2)]
        mock_guild.channels = []
        mock_guild.text_channels = []
        mock_guild.voice_channels = []
        mock_guild.categories = []
        mock_guild.stage_channels = []
        mock_guild.forum_channels = []
        mock_guild.threads = []
        mock_guild.system_channel = None
        mock_guild.rules_channel = None
        mock_guild.public_updates_channel = None
        mock_guild.afk_channel = None
        mock_guild.premium_subscriber_role = None
        mock_guild.icon = None
        mock_guild.banner = None
        mock_guild.splash = None
        mock_guild.me = MagicMock()
        mock_guild.me.joined_at = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock_guild.me.guild_permissions.view_audit_log = False

        mock_bot.get_guild.return_value = mock_guild
        mock_bot.fetch_user = AsyncMock(return_value=None)

        cog = GuildInfo(mock_bot)
        cog.check.is_op = AsyncMock(return_value=True)

        mock_ctx = MagicMock()
        mock_ctx.author.id = 55555
        mock_ctx.guild.id = 987654321
        mock_ctx.send = AsyncMock()

        await cog.guildinfo.callback(cog, mock_ctx, 987654321)

        mock_ctx.send.assert_called_once()
        _, kwargs = mock_ctx.send.call_args
        embed = kwargs.get("embed")
        view = kwargs.get("view")
        self.assertIsNotNone(embed)
        self.assertIsNotNone(view)
        self.assertIn("Mock Guild", embed.title)

        field_names = [f.name for f in embed.fields]
        self.assertIn("📌 Général", field_names)
        self.assertIn("👥 Membres & Présences", field_names)
        self.assertIn("🎭 Rôles", field_names)
        self.assertIn("💬 Salons & Organisation", field_names)

        # Vérification de la suppression des sections demandées
        self.assertNotIn("🛡️ Sécurité & Modération", field_names)
        self.assertNotIn("🚀 Boosts Discord Nitro", field_names)
        self.assertNotIn("📦 Médias & Quotas", field_names)
        self.assertNotIn("✨ Fonctionnalités (Features)", field_names)

        # Vérification qu'aucune mention cliquable n'est présente dans les champs
        general_field = next(f for f in embed.fields if f.name == "📌 Général")
        self.assertIn("Arrivée du bot", general_field.value)
        self.assertIn("Bot ajouté par", general_field.value)
        self.assertNotIn("<@", general_field.value)
        self.assertNotIn("<#", general_field.value)

    async def test_guildmembers_button_interaction(self):
        import discord
        from unittest.mock import AsyncMock, patch
        from commands.admin.guildinfo import GuildInfoView

        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_guild.name = "Button Guild"

        # Mock member
        m1 = MagicMock()
        m1.id = 101
        m1.name = "Alice"
        m1.display_name = "AliceD"
        m1.bot = False
        m1.joined_at = datetime(2023, 1, 1, tzinfo=timezone.utc)
        m1.created_at = datetime(2021, 1, 1, tzinfo=timezone.utc)
        m1.top_role.name = "Admin"
        r1 = MagicMock(); r1.name = "@everyone"
        r2 = MagicMock(); r2.name = "Admin"
        m1.roles = [r1, r2]

        mock_guild.members = [m1]

        view = GuildInfoView(mock_bot, mock_guild, 55555)

        # 1. Non-authorized user
        unauthorized_interaction = MagicMock()
        unauthorized_interaction.user.id = 99999
        unauthorized_interaction.response.send_message = AsyncMock()

        button = view.children[0]
        with patch("commands.admin.guildinfo.Check.is_op", new=AsyncMock(return_value=False)):
            await button.callback(unauthorized_interaction)
        unauthorized_interaction.response.send_message.assert_called_once()
        _, unauth_kwargs = unauthorized_interaction.response.send_message.call_args
        self.assertTrue(unauth_kwargs.get("ephemeral"))

        # 2. Authorized user (author)
        authorized_interaction = MagicMock()
        authorized_interaction.user.id = 55555
        authorized_interaction.response.defer = AsyncMock()
        authorized_interaction.followup.send = AsyncMock()

        await button.callback(authorized_interaction)
        authorized_interaction.response.defer.assert_called_once_with(ephemeral=True)
        authorized_interaction.followup.send.assert_called_once()
        _, auth_kwargs = authorized_interaction.followup.send.call_args
        self.assertTrue(auth_kwargs.get("ephemeral"))
        self.assertIn("file", auth_kwargs)
        self.assertEqual(auth_kwargs["file"].filename, "membres-12345.txt")

    async def test_guildchannels_button_interaction(self):
        import discord
        from unittest.mock import AsyncMock, patch
        from commands.admin.guildinfo import GuildInfoView

        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_guild.name = "Channels Guild"

        ch1 = MagicMock()
        ch1.id = 201
        ch1.name = "general"
        ch1.type = discord.ChannelType.text
        ch1.category = None
        ch1.position = 1
        ch1.topic = "Bienvenue"

        mock_guild.channels = [ch1]
        mock_guild.text_channels = [ch1]
        mock_guild.voice_channels = []
        mock_guild.categories = []
        mock_guild.stage_channels = []
        mock_guild.forum_channels = []
        mock_guild.threads = []

        view = GuildInfoView(mock_bot, mock_guild, 55555)
        button_channels = view.children[1]

        # 1. Non-authorized user
        unauth = MagicMock()
        unauth.user.id = 88888
        unauth.response.send_message = AsyncMock()

        with patch("commands.admin.guildinfo.Check.is_op", new=AsyncMock(return_value=False)):
            await button_channels.callback(unauth)
        unauth.response.send_message.assert_called_once()
        _, unauth_kwargs = unauth.response.send_message.call_args
        self.assertTrue(unauth_kwargs.get("ephemeral"))

        # 2. Authorized user (author)
        auth = MagicMock()
        auth.user.id = 55555
        auth.response.defer = AsyncMock()
        auth.followup.send = AsyncMock()

        await button_channels.callback(auth)
        auth.response.defer.assert_called_once_with(ephemeral=True)
        auth.followup.send.assert_called_once()
        _, auth_kwargs = auth.followup.send.call_args
        self.assertTrue(auth_kwargs.get("ephemeral"))
        self.assertIn("file", auth_kwargs)
        self.assertEqual(auth_kwargs["file"].filename, "salons-12345.txt")
        embed = auth_kwargs.get("embed")
        self.assertIsNotNone(embed)
        self.assertIn("Channels Guild", embed.title)


class TestMiniGameSharedLayer(unittest.IsolatedAsyncioTestCase):
    """Validation exhaustive de la couche mutualisée des mini-jeux (GameConfig, MiniGameCog)."""

    def test_games_configuration(self):
        from commands.game.game_config import GAMES, GameConfig
        from utils.logger import Logger

        expected_games = ["hash", "pin", "decode", "anomaly", "buffer", "signal", "packet"]
        for key in expected_games:
            self.assertIn(key, GAMES)
            cfg = GAMES[key]
            self.assertIsInstance(cfg, GameConfig)
            self.assertEqual(cfg.key, key)
            self.assertTrue(len(cfg.aliases) > 0)
            self.assertIn(cfg.shape, ("narrowing", "binary"))
            self.assertIn(cfg.active_info_mode, ("text", "embed"))
            self.assertIn(cfg.guess_kind, ("int", "int_bounded", "raw_str", "letter"))
            self.assertTrue(hasattr(Logger, cfg.log_method), f"Logger must have {cfg.log_method}")
            self.assertTrue(callable(cfg.log_kwargs))

    def test_parse_guess(self):
        from commands.game.minigame_cog import MiniGameCog
        from commands.game.game_config import GameConfig

        # 1. int
        cog_int = MiniGameCog(MagicMock())
        cog_int.config = GameConfig("test", [], "g", "int")
        self.assertEqual(cog_int._parse_guess(42), 42)
        self.assertEqual(cog_int._parse_guess(" 1337 "), 1337)
        self.assertIsNone(cog_int._parse_guess(None))
        with self.assertRaises(ValueError):
            cog_int._parse_guess("abc")

        # 2. int_bounded
        cog_bounded = MiniGameCog(MagicMock())
        cog_bounded.config = GameConfig("test", [], "g", "int_bounded", bounds=(1, 10))
        self.assertEqual(cog_bounded._parse_guess(1), 1)
        self.assertEqual(cog_bounded._parse_guess(10), 10)
        self.assertEqual(cog_bounded._parse_guess(" 5 "), 5)
        with self.assertRaises(ValueError):
            cog_bounded._parse_guess(0)
        with self.assertRaises(ValueError):
            cog_bounded._parse_guess(11)
        with self.assertRaises(ValueError):
            cog_bounded._parse_guess("xyz")

        # 3. raw_str
        cog_str = MiniGameCog(MagicMock())
        cog_str.config = GameConfig("test", [], "g", "raw_str")
        self.assertEqual(cog_str._parse_guess(" ABCD "), "ABCD")
        self.assertIsNone(cog_str._parse_guess(None))
        self.assertIsNone(cog_str._parse_guess("   "))

        # 4. letter
        cog_letter = MiniGameCog(MagicMock())
        cog_letter.config = GameConfig("test", [], "g", "letter")
        self.assertEqual(cog_letter._parse_guess("a"), "A")
        self.assertEqual(cog_letter._parse_guess(" Z "), "Z")
        with self.assertRaises(ValueError):
            cog_letter._parse_guess("AB")
        with self.assertRaises(ValueError):
            cog_letter._parse_guess("1")
        with self.assertRaises(ValueError):
            cog_letter._parse_guess("?")
        with self.assertRaises(ValueError):
            cog_letter._parse_guess(123)

    async def test_resolve_winner_display(self):
        from unittest.mock import AsyncMock
        from commands.game.minigame_cog import MiniGameCog

        mock_bot = MagicMock()
        cog = MiniGameCog(mock_bot)

        # 1. get_user cached
        mock_user = MagicMock()
        mock_user.name = "Alice"
        mock_bot.get_user.return_value = mock_user
        display = await cog._resolve_winner_display(12345)
        self.assertEqual(display, "<@12345> (`Alice`)")

        # 2. get_user None -> fetch_user success
        mock_bot.get_user.return_value = None
        mock_fetched = MagicMock()
        mock_fetched.name = "Bob"
        mock_bot.fetch_user = AsyncMock(return_value=mock_fetched)
        display = await cog._resolve_winner_display(67890)
        self.assertEqual(display, "<@67890> (`Bob`)")

        # 3. get_user None -> fetch_user fails
        mock_bot.fetch_user = AsyncMock(side_effect=Exception("User not found"))
        display = await cog._resolve_winner_display(99999)
        self.assertEqual(display, "<@99999>")

    async def test_send_cooldown(self):
        from unittest.mock import AsyncMock
        from commands.game.minigame_cog import MiniGameCog
        from commands.game.game_config import GAMES

        mock_bot = MagicMock()
        cog = MiniGameCog(mock_bot)
        cog.config = GAMES["hash"]
        cog._reply_text = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.author.id = 111
        mock_ctx.prefix = "!"

        # Cooldown without winner
        res_no_win = {"status": "cooldown", "remaining_seconds": 120}
        await cog._send(mock_ctx, "hash", res_no_win)
        cog._reply_text.assert_called_once()

        # Cooldown with winner
        cog._reply_text.reset_mock()
        cog._resolve_winner_display = AsyncMock(return_value="<@222> (`Winner`)")
        res_win = {
            "status": "cooldown",
            "remaining_seconds": 60,
            "last_found_by": 222,
            "last_found_on": "RootServer",
        }
        await cog._send(mock_ctx, "hash", res_win)
        cog._reply_text.assert_called_once()

    async def test_send_active_info_text_and_embed(self):
        from unittest.mock import AsyncMock
        from commands.game.minigame_cog import MiniGameCog
        from commands.game.game_config import GAMES

        mock_bot = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.author.id = 111
        mock_ctx.prefix = "!"

        # Hash (text)
        cog_hash = MiniGameCog(mock_bot)
        cog_hash.config = GAMES["hash"]
        cog_hash._reply_text = AsyncMock()
        cog_hash._send_embed = AsyncMock()
        await cog_hash._send(mock_ctx, "hash", {"status": "active_info", "current_min": 1, "current_max": 100, "players_count": 5})
        cog_hash._reply_text.assert_called_once()
        cog_hash._send_embed.assert_not_called()

        # Decode (embed)
        cog_decode = MiniGameCog(mock_bot)
        cog_decode.config = GAMES["decode"]
        cog_decode._reply_text = AsyncMock()
        cog_decode._send_embed = AsyncMock()
        await cog_decode._send(mock_ctx, "decode", {"status": "active_info", "sequence": "A1 B2", "grid_display": "..."})
        cog_decode._send_embed.assert_called_once()
        cog_decode._reply_text.assert_not_called()

    async def test_send_intermediate_and_won(self):
        from unittest.mock import AsyncMock, patch
        from commands.game.minigame_cog import MiniGameCog
        from commands.game.game_config import GAMES

        mock_bot = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.author.id = 111
        mock_ctx.guild.name = "TestGuild"
        mock_ctx.prefix = "!"

        cog_hash = MiniGameCog(mock_bot)
        cog_hash.config = GAMES["hash"]
        cog_hash._reply_text = AsyncMock()

        # too_low
        await cog_hash._send(mock_ctx, "hash", {"status": "too_low", "current_min": 10, "current_max": 50, "players_count": 2})
        cog_hash._reply_text.assert_called_once()

        # won with logger
        cog_hash._reply_text.reset_mock()
        mock_logger = MagicMock()
        mock_logger.log_hash_won = AsyncMock()
        with patch("commands.game.minigame_cog.Logger", return_value=mock_logger):
            await cog_hash._send(mock_ctx, "hash", {
                "status": "won",
                "winner": 111,
                "reward": Decimal("5.00"),
                "target": 42,
                "players_count": 3,
                "last_found_on": "TestGuild",
            })
            cog_hash._reply_text.assert_called_once()
            mock_logger.log_hash_won.assert_called_once()

    async def test_run_slash_and_prefix_error(self):
        from unittest.mock import AsyncMock
        from commands.game.minigame_cog import MiniGameCog
        from commands.game.game_config import GAMES

        mock_bot = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.author.id = 111
        mock_ctx.guild = None
        mock_ctx.prefix = "!"

        cog = MiniGameCog(mock_bot)
        cog.config = GAMES["anomaly"]  # bounds (1, 10)
        cog._reply_text = AsyncMock()
        cog._invoke = AsyncMock()

        # Invalid bounds for prefix -> error replied, _invoke not called
        await cog._run_prefix(mock_ctx, "99")
        cog._reply_text.assert_called_once()
        cog._invoke.assert_not_called()

        # Valid input -> _invoke called
        cog._reply_text.reset_mock()
        await cog._run_prefix(mock_ctx, "5")
        cog._reply_text.assert_not_called()
        cog._invoke.assert_called_once_with(mock_ctx, "anomaly", guess=5, guild_name=None)

    async def test_all_game_cogs_instantiation(self):
        from commands.game.hash import Hash
        from commands.game.pin import Pin
        from commands.game.decode import Decode
        from commands.game.anomaly import Anomaly
        from commands.game.buffer import Buffer
        from commands.game.signal import Signal
        from commands.game.packet import Packet

        mock_bot = MagicMock()
        cogs = [
            Hash(mock_bot),
            Pin(mock_bot),
            Decode(mock_bot),
            Anomaly(mock_bot),
            Buffer(mock_bot),
            Signal(mock_bot),
            Packet(mock_bot),
        ]
        for cog in cogs:
            self.assertIsNotNone(cog.config)
            self.assertEqual(cog.bot, mock_bot)


class MockDatabase:
    """Simulateur de base de données thread-safe avec gestion des transactions, verrous et snapshots."""

    def __init__(self):
        self.lock = threading.RLock()
        self.players = {}
        self.events = {}
        self.daily_stats = {}
        self.daily_claim_logs = []
        self.prefixes = {}
        self.upgrades = []
        self.hacks = []
        self.released_locks = []
        self.acquired_locks = []
        self.committed_count = 0
        self.rollback_count = 0

    def run_sync(self, function, resource=None, readonly: bool = False, locks=None):
        import copy
        from game.db.database import Database
        if readonly:
            tx = MockTransaction()
            tx.players = self.players
            tx.events = self.events
            tx.daily_stats = self.daily_stats
            tx.daily_claim_logs = self.daily_claim_logs
            tx.prefixes = self.prefixes
            tx.upgrades = self.upgrades
            tx.hacks = self.hacks
            return function(tx)

        with self.lock:
            tx = MockTransaction()
            tx.players = copy.deepcopy(self.players)
            tx.events = copy.deepcopy(self.events)
            tx.daily_stats = copy.deepcopy(self.daily_stats)
            tx.daily_claim_logs = copy.deepcopy(self.daily_claim_logs)
            tx.prefixes = copy.deepcopy(self.prefixes)
            tx.upgrades = copy.deepcopy(self.upgrades)
            tx.hacks = copy.deepcopy(self.hacks)

            commit_started = False
            committed = False
            for name in Database.normalize_locks(locks):
                tx.acquire_lock(name)
            if resource:
                resource.begin(tx)
            try:
                result = function(tx)
                if resource:
                    resource.prepare(tx)
                commit_started = True
                # Commit effectif
                self.players = tx.players
                self.events = tx.events
                self.daily_stats = tx.daily_stats
                self.daily_claim_logs = tx.daily_claim_logs
                self.prefixes = tx.prefixes
                self.upgrades = tx.upgrades
                self.hacks = tx.hacks
                committed = True
                self.committed_count += 1
                if resource:
                    resource.finish()
                return result
            except Exception:
                self.rollback_count += 1
                if resource and not committed:
                    if commit_started:
                        resource.uncertain()
                    else:
                        resource.rollback()
                raise
            finally:
                self.acquired_locks = list(tx.acquired_locks)
                for name in Database.normalize_locks(locks):
                    self.released_locks.append(name)
                for name in tx.acquired_locks:
                    if name not in self.released_locks:
                        self.released_locks.append(name)

    async def run(self, function, resource=None, readonly: bool = False, locks=None):
        import asyncio
        return await asyncio.to_thread(self.run_sync, function, resource, readonly, locks)


class TestConcurrentPurchasesAndConfirmations(unittest.IsolatedAsyncioTestCase):
    """Couvre les achats simultanés et les doubles confirmations UI."""

    async def test_concurrent_purchases_balance_protection(self):
        """Vérifie que deux achats simultanés avec solde suffisant pour un seul n'autorisent qu'un seul achat."""
        import asyncio
        from game.root_service import RootService

        mock_db = MockDatabase()
        actor = 777
        cost, _ = _calculate_module_price("mining_t1", 1)
        mock_db.players[actor] = {
            "discord_id": actor,
            "dollars": cost + Decimal("15.00"),
            "rootium": Decimal("0.00000"),
            "firewall_level": 0,
            "mining_t1": 0,
            "events_won": 0,
            "reputation": 0,
        }

        service = RootService(database=mock_db)

        task1 = service.execute(actor, None, 'buy', kind='mining', tier=1, confirm=True)
        task2 = service.execute(actor, None, 'buy', kind='mining', tier=1, confirm=True)

        results = await asyncio.gather(task1, task2, return_exceptions=True)

        successes = [r for r in results if isinstance(r, dict) and r.get("bought")]
        errors = [r for r in results if isinstance(r, GameError) and r.key == "insufficient_funds_usd"]

        self.assertEqual(len(successes), 1, "Exactement un achat doit réussir.")
        self.assertEqual(len(errors), 1, "L'autre achat doit échouer pour fonds insuffisants.")
        self.assertEqual(mock_db.players[actor]["dollars"], Decimal("15.00"))
        self.assertEqual(mock_db.players[actor]["mining_t1"], 1, "Seul 1 module doit avoir été acquis.")

    async def test_double_confirmation_click_prevention(self):
        """Vérifie qu'un double clic sur le bouton de confirmation ne traite l'action qu'une seule fois."""
        import asyncio
        from unittest.mock import AsyncMock
        from utils.confirmation import Confirmation

        mock_service = MagicMock()
        mock_service.execute = AsyncMock(return_value={"bought": True})

        mock_send_fn = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.author.id = 12345
        mock_ctx.guild = None
        mock_ctx.bot = MagicMock()

        view = Confirmation(
            send_fn=mock_send_fn,
            service=mock_service,
            ctx=mock_ctx,
            method='buy',
            args={'kind': 'mining', 'tier': 1}
        )

        interaction1 = MagicMock()
        interaction1.user.id = 12345
        interaction1.response.is_done.return_value = True
        interaction1.followup.send = AsyncMock()

        interaction2 = MagicMock()
        interaction2.user.id = 12345
        interaction2.response.is_done.return_value = True
        interaction2.followup.send = AsyncMock()

        with patch("utils.confirmation.Check.is_player", new=AsyncMock(return_value=True)):
            # Simule deux clics simultanés sur ✅ Confirmer
            await asyncio.gather(view.confirm(interaction1), view.confirm(interaction2))

        # Vérifie que service.execute n'a été appelé qu'une seule fois
        self.assertEqual(mock_service.execute.call_count, 1)
        self.assertTrue(view.done)

        # L'une des deux interactions a reçu le message 'g_already_handled'
        all_followup_calls = interaction1.followup.send.call_args_list + interaction2.followup.send.call_args_list
        already_handled_sent = any(
            "already" in str(call).lower() or "déjà" in str(call).lower() or "handled" in str(call).lower()
            for call in all_followup_calls
        )
        self.assertTrue(already_handled_sent, "Le second clic doit recevoir l'information que l'action est déjà traitée.")


class TestSQLTransactionsAndLocking(unittest.IsolatedAsyncioTestCase):
    """Couvre les transactions, rollbacks, libération de verrous et commits incertains."""

    async def test_transaction_rollback_on_sql_error(self):
        """Vérifie qu'en cas d'erreur pendant une transaction, les modifications sont annulées."""
        mock_db = MockDatabase()
        actor = 888
        mock_db.players[actor] = {
            "discord_id": actor,
            "dollars": Decimal("50.00"),
            "rootium": Decimal("0.00000"),
            "firewall_level": 0,
            "events_won": 0,
            "reputation": 0,
        }

        def failing_tx(tx):
            tx.players[actor]["dollars"] = Decimal("0.00")
            raise RuntimeError("Erreur SQL inattendue")

        with self.assertRaises(RuntimeError):
            await mock_db.run(failing_tx)

        # Les modifications doivent avoir été annulées par le rollback
        self.assertEqual(mock_db.players[actor]["dollars"], Decimal("50.00"))
        self.assertGreater(mock_db.rollback_count, 0)
        self.assertIn("root-game", mock_db.released_locks)

    async def test_explicit_release_lock_called(self):
        """Vérifie que RELEASE_LOCK est systématiquement consigné à la fin d'une transaction."""
        mock_db = MockDatabase()
        await mock_db.run(lambda tx: tx.now)
        self.assertIn("root-game", mock_db.released_locks)

    async def test_player_lock_released_for_game_action(self):
        """Vérifie qu'une action de jeu libère le verrou par joueur plutôt que le verrou global."""
        from game.root_service import RootService

        mock_db = MockDatabase()
        actor = 4242
        mock_db.players[actor] = {
            "discord_id": actor,
            "dollars": Decimal("100.00"),
            "rootium": Decimal("0.00000"),
            "firewall_level": 0,
            "events_won": 0,
            "reputation": 0,
        }
        service = RootService(database=mock_db)
        await service.execute(actor, None, 'top', category='usd')
        # 'top' est en lecture seule : aucun verrou d'écriture
        self.assertEqual(mock_db.released_locks, [])

        mock_db.released_locks.clear()
        await service.execute(actor, None, 'set_language', lang='en')
        self.assertIn("player:4242", mock_db.released_locks)
        self.assertNotIn("root-game", mock_db.released_locks)

    async def test_trade_locks_both_players_sorted(self):
        """Vérifie que trade pose les deux verrous joueur dans l'ordre croissant."""
        from game.root_service import RootService

        self.assertEqual(
            RootService._locks_for('trade', 99, {'target': 12}),
            ['player:12', 'player:99'],
        )
        self.assertEqual(
            RootService._locks_for('reputation', 5, {'target': 8}),
            ['player:5', 'player:8'],
        )
        self.assertEqual(
            RootService._locks_for('claim', 42, {}),
            ['player:42'],
        )

    async def test_normalize_locks(self):
        """Vérifie le repli global, la liste vide, et le tri unique anti-deadlock."""
        from game.db.database import Database
        self.assertEqual(Database.normalize_locks(None), ['root-game'])
        self.assertEqual(Database.normalize_locks([]), [])
        self.assertEqual(
            Database.normalize_locks(['player:9', 'player:1', 'player:9']),
            ['player:1', 'player:9'],
        )

    async def test_uncertain_commit_invalidates_memory_challenge(self):
        """Vérifie qu'en cas d'échec incertain de validation MySQL, le défi mémoire est réinitialisé."""
        initial_challenge = {"type": "hash", "target": "abc", "status": "active"}
        HashManager._active_challenge = copy.deepcopy(initial_challenge)
        resource = ChallengeResource(HashManager)

        # Prépare une mutation en mémoire
        resource.begin(None)
        resource.stage({"type": "hash", "target": "abc", "status": "solved"})

        # Simule un commit incertain (déconnexion pendant le commit)
        resource.uncertain()

        # L'état actif en mémoire doit être vidé pour forcer une regénération propre
        self.assertIsNone(HashManager._active_challenge, "En cas de commit incertain, le défi en mémoire doit être invalidé.")

    async def test_staged_memory_changes_discarded_on_rollback(self):
        """Vérifie qu'en cas de rollback, les changements préparés ne sont pas appliqués à l'état actif."""
        initial_challenge = {"type": "hash", "target": "xyz", "status": "active"}
        HashManager._active_challenge = copy.deepcopy(initial_challenge)
        resource = ChallengeResource(HashManager)

        resource.begin(None)
        resource.stage({"type": "hash", "target": "xyz", "status": "solved"})

        # Rollback suite à une annulation SQL
        resource.rollback()

        # Le défi actif en mémoire doit être inchangé
        self.assertEqual(HashManager._active_challenge["status"], "active")

    def test_mysql_pool_shared_by_config(self):
        """Vérifie que deux instances de Database partageant la même config utilisent le même pool."""
        from game.db.database import Database
        cfg = {"host": "127.0.0.1", "user": "test_bot", "password": "pwd", "database": "root_test"}
        db1 = Database(config=cfg)
        db2 = Database(config=cfg)

        with patch("game.db.database.MySQLConnectionPool") as mock_pool_cls:
            mock_pool_instance = MagicMock()
            mock_pool_cls.return_value = mock_pool_instance
            Database._pools.clear()

            p1 = db1._get_pool()
            p2 = db2._get_pool()
            self.assertIs(p1, p2, "Les deux instances Database doivent réutiliser le même pool de connexions.")
            self.assertEqual(mock_pool_cls.call_count, 1)


class TestDailyReportSendingAndReset(unittest.IsolatedAsyncioTestCase):
    """Couvre les scénarios de réussite, échec total, échec partiel et concurrence du rapport quotidien."""

    def setUp(self):
        from commands.admin.event_moderation import EventModeration
        self._loop_patch = patch.object(EventModeration, "daily_report_loop")
        self._mock_loop = self._loop_patch.start()

    def tearDown(self):
        self._loop_patch.stop()

    async def test_report_total_failure_preserves_stats(self):
        """Vérifie qu'en cas d'échec d'envoi du rapport préserve intégralement les compteurs en base."""
        from commands.admin.event_moderation import EventModeration

        mock_bot = MagicMock()
        mock_db = MockDatabase()
        mock_db.daily_stats[100] = {"discord_id": 100, "events_won": 2, "events_participated": 5}

        mock_bot.root_service.database = mock_db
        mock_bot.discord_logger.log_daily_event_report = AsyncMock(side_effect=RuntimeError("Erreur Discord API"))

        cog = EventModeration(mock_bot)

        # L'envoi doit échouer en levant l'exception
        with self.assertRaises(RuntimeError):
            await cog._run_daily_report()

        # Les compteurs n'ont PAS été remis à zéro
        self.assertIn(100, mock_db.daily_stats)
        self.assertEqual(mock_db.daily_stats[100]["events_won"], 2)

    async def test_report_second_message_failure_preserves_stats(self):
        """
        Vérifie spécifiquement que si le premier message est envoyé mais le deuxième échoue,
        les compteurs NE sont PAS remis à zéro.
        """
        from utils.logger import Logger
        from commands.admin.event_moderation import EventModeration

        mock_bot = MagicMock()
        mock_db = MockDatabase()
        mock_db.daily_stats[101] = {"discord_id": 101, "events_won": 1, "events_participated": 2}
        mock_db.daily_stats[102] = {"discord_id": 102, "events_won": 3, "events_participated": 4}

        mock_bot.root_service.database = mock_db

        # Configure un mock de salon où le 1er send() réussit et le 2e send() échoue
        mock_channel = MagicMock()
        send_count = 0

        async def conditional_send(*args, **kwargs):
            nonlocal send_count
            send_count += 1
            if send_count >= 2:
                raise RuntimeError("Échec d'envoi du message #2")
            return MagicMock()

        mock_channel.send = AsyncMock(side_effect=conditional_send)
        mock_bot.get_channel.return_value = mock_channel

        logger_inst = Logger(mock_bot)
        logger_inst.channel_id = MagicMock(return_value=123456)
        mock_bot.discord_logger = logger_inst

        # Génère une liste de 40 entrées volumineuses provoquant un découpage en au moins 2 messages
        big_summary = [
            {"discord_id": 1000 + i, "events_won": i, "events_participated": i * 2}
            for i in range(40)
        ]
        mock_db.daily_stats.update({row["discord_id"]: row for row in big_summary})

        cog = EventModeration(mock_bot)

        # L'exécution doit échouer au message #2
        with self.assertRaises(RuntimeError):
            await cog._run_daily_report()

        # Les compteurs doivent être conservés
        self.assertGreater(len(mock_db.daily_stats), 0, "Les compteurs doivent être conservés en base.")
        self.assertIn(101, mock_db.daily_stats)

    async def test_report_success_resets_stats(self):
        """Vérifie qu'un envoi réussi purge les statistiques journalières."""
        from commands.admin.event_moderation import EventModeration

        mock_bot = MagicMock()
        mock_db = MockDatabase()
        mock_db.daily_stats[200] = {"discord_id": 200, "events_won": 5, "events_participated": 10}

        mock_bot.root_service.database = mock_db
        mock_bot.discord_logger.log_daily_event_report = AsyncMock(return_value=None)

        cog = EventModeration(mock_bot)
        status = await cog._run_daily_report()

        self.assertEqual(status, 'success')
        self.assertEqual(len(mock_db.daily_stats), 0, "La table daily_event_stats doit être vidée après succès.")

    async def test_concurrent_daily_reports_prevented(self):
        """Vérifie que deux rapports simultanés ne peuvent pas s'exécuter en parallèle."""
        import asyncio
        from commands.admin.event_moderation import EventModeration

        mock_bot = MagicMock()
        mock_db = MockDatabase()
        mock_bot.root_service.database = mock_db

        async def slow_send(summary):
            await asyncio.sleep(0.05)

        mock_bot.discord_logger.log_daily_event_report = AsyncMock(side_effect=slow_send)

        cog = EventModeration(mock_bot)

        task1 = cog._run_daily_report()
        task2 = cog._run_daily_report()

        res1, res2 = await asyncio.gather(task1, task2)
        results = {res1, res2}
        self.assertIn('success', results)
        self.assertIn('busy', results, "Le second rapport simultané doit retourner 'busy'.")

    async def test_manual_daily_report_distinguishes_outcomes(self):
        """Vérifie les annonces de manual_daily_report pour succès, échec et busy."""
        from commands.admin.event_moderation import EventModeration

        mock_bot = MagicMock()
        mock_db = MockDatabase()
        mock_bot.root_service.database = mock_db

        cog = EventModeration(mock_bot)
        cog.check.is_op = AsyncMock(return_value=True)

        mock_ctx = MagicMock()
        mock_ctx.author.id = 999
        mock_ctx.send = AsyncMock()

        # 1. Succès
        cog._run_daily_report = AsyncMock(return_value='success')
        await cog.manual_daily_report.callback(cog, mock_ctx)
        last_msg = mock_ctx.send.call_args[0][0]
        self.assertIn("✅", last_msg)

        # 2. Échec
        mock_ctx.send.reset_mock()
        cog._run_daily_report = AsyncMock(side_effect=RuntimeError("Erreur d'envoi"))
        await cog.manual_daily_report.callback(cog, mock_ctx)
        last_msg = mock_ctx.send.call_args[0][0]
        self.assertIn("❌", last_msg)
        self.assertIn("n'ont pas été réinitialisés", last_msg)

        # 3. Déjà en cours
        mock_ctx.send.reset_mock()
        cog._run_daily_report = AsyncMock(return_value='busy')
        await cog.manual_daily_report.callback(cog, mock_ctx)
        last_msg = mock_ctx.send.call_args[0][0]
        self.assertIn("⚠️", last_msg)


class TestPrefixAndLanguageCacheTTL(unittest.IsolatedAsyncioTestCase):
    """Couvre les caches de préfixes et de langues avec expiration TTL et actualisation."""

    async def test_prefix_cache_and_expiration(self):
        """Vérifie le cache de préfixe, son expiration TTL et son actualisation immédiate."""
        from utils.prefix_manager import get_prefix_async, set_prefix, invalidate_prefix_cache, _prefix_cache
        import utils.prefix_manager as pm

        invalidate_prefix_cache()
        guild_id = 123456789

        with patch.object(pm._prefix_db, "fetch", new=AsyncMock(return_value="!custom")) as mock_fetch:
            # 1. Premier appel : interroge la BDD et alimente le cache
            p1 = await get_prefix_async(guild_id)
            self.assertEqual(p1, "!custom")
            self.assertEqual(mock_fetch.call_count, 1)

            # 2. Deuxième appel immédiat : retourne la valeur du cache sans requête BDD
            p2 = await get_prefix_async(guild_id)
            self.assertEqual(p2, "!custom")
            self.assertEqual(mock_fetch.call_count, 1)

            # 3. Expiration simulée du TTL
            _prefix_cache[guild_id] = ("!custom", time.monotonic() - 1.0)
            mock_fetch.return_value = "!new_db_prefix"
            p3 = await get_prefix_async(guild_id)
            self.assertEqual(p3, "!new_db_prefix")
            self.assertEqual(mock_fetch.call_count, 2)

        # 4. Modification immédiate via set_prefix
        with patch.object(pm._prefix_db, "save", new=AsyncMock()) as mock_save:
            await set_prefix(guild_id, "!instant")
            mock_save.assert_called_once_with(guild_id, "!instant")
            # Le cache doit refléter immédiatement le nouveau préfixe
            cached = await get_prefix_async(guild_id)
            self.assertEqual(cached, "!instant")

        invalidate_prefix_cache()

    async def test_language_cache_and_expiration(self):
        """Vérifie le cache de langue, son expiration TTL et son actualisation immédiate."""
        from utils.language_manager import fetch_user_language, set_user_language, reset_user_language, get_user_language, invalidate_language_cache, _cache
        import utils.language_manager as lm

        invalidate_language_cache()
        user_id = 987654321

        with patch.object(lm._db, "run", new=AsyncMock(return_value="fr")) as mock_db_run:
            # 1. Premier chargement : interroge la BDD et alimente le cache
            l1 = await fetch_user_language(user_id)
            self.assertEqual(l1, "fr")
            self.assertEqual(get_user_language(user_id), "fr")
            self.assertEqual(mock_db_run.call_count, 1)

            # 2. Deuxième lecture : renvoie depuis le cache sans requête BDD
            l2 = await fetch_user_language(user_id)
            self.assertEqual(l2, "fr")
            self.assertEqual(mock_db_run.call_count, 1)

            # 3. Expiration simulée du TTL
            _cache[user_id] = ("fr", time.monotonic() - 1.0)
            self.assertIsNone(get_user_language(user_id), "Une entrée expirée ne doit pas être retournée par get_user_language.")

            mock_db_run.return_value = "en"
            l3 = await fetch_user_language(user_id)
            self.assertEqual(l3, "en")
            self.assertEqual(mock_db_run.call_count, 2)

        # 4. Modification via set_user_language
        with patch.object(lm._db, "run", new=AsyncMock()) as mock_save:
            await set_user_language(user_id, "fr")
            self.assertEqual(get_user_language(user_id), "fr")

            # 5. Réinitialisation via reset_user_language
            await reset_user_language(user_id)
            self.assertIsNone(get_user_language(user_id))

        invalidate_language_cache()

    async def test_language_restart_persistence_in_logic(self):
        """Vérifie que /lang sans argument recharge la langue depuis la BDD après un redémarrage (cache vide)."""
        from utils.language_manager import invalidate_language_cache, get_user_language
        import utils.language_manager as lm
        from commands.utility.language import Language

        invalidate_language_cache()
        user_id = 123456789
        mock_ctx = MagicMock()
        mock_ctx.author.id = user_id
        mock_ctx.guild = None
        mock_ctx.respond = AsyncMock()
        mock_bot = MagicMock()

        cog = Language(mock_bot)

        # Simulation du redémarrage : cache vide, BDD contient 'fr'
        with patch.object(lm._db, "run", new=AsyncMock(return_value="fr")) as mock_db_run:
            await cog._language_logic(mock_ctx, choice=None)
            self.assertEqual(mock_db_run.call_count, 1)
            self.assertEqual(get_user_language(user_id), "fr")
            mock_ctx.respond.assert_called_once()
            sent_msg = mock_ctx.respond.call_args[0][0]
            self.assertIn("fr (personnalisée / custom)", sent_msg)
            # Vérifie que le texte du template est en français
            self.assertIn("Langue actuelle", sent_msg)

        invalidate_language_cache()

    async def test_language_restart_persistence_in_global_check(self):
        """Vérifie que global_check charge immédiatement la langue en cache pour toute commande."""
        from utils.language_manager import invalidate_language_cache, get_user_language
        import utils.language_manager as lm
        from main import create_bot

        invalidate_language_cache()
        user_id = 998877665
        mock_bot = create_bot()
        check_fn = mock_bot._checks[0]

        mock_ctx = MagicMock()
        mock_ctx.guild = MagicMock()
        mock_ctx.guild.id = 111
        mock_ctx.author.id = user_id
        mock_ctx.interaction = None
        mock_ctx.command.module = "commands.utility.ping"
        mock_ctx.command.name = "ping"

        with patch.object(lm._db, "run", new=AsyncMock(return_value="fr")) as mock_db_run:
            with patch("utils.check.Check.is_banned", return_value=False):
                with patch("utils.check.Check.maintenance_enabled", return_value=False):
                    with patch("utils.check.Check.beta_enabled", return_value=False):
                        res = await check_fn(mock_ctx)
                        self.assertTrue(res)
                        self.assertEqual(mock_db_run.call_count, 1)
                        self.assertEqual(get_user_language(user_id), "fr")

        invalidate_language_cache()

    async def test_language_restart_persistence_in_error_reporting(self):
        """Vérifie que report_command_error répond dans la langue de l'utilisateur même si le cache est vide."""
        from utils.language_manager import invalidate_language_cache, get_user_language
        import utils.language_manager as lm
        from main import create_bot
        from game.game_error import GameError

        invalidate_language_cache()
        user_id = 554433221
        mock_bot = create_bot()

        mock_ctx = MagicMock()
        mock_ctx.guild = MagicMock()
        mock_ctx.author.id = user_id
        mock_ctx.interaction = None
        mock_ctx.send = AsyncMock()

        with patch.object(lm._db, "run", new=AsyncMock(return_value="fr")) as mock_db_run:
            await mock_bot.on_command_error(mock_ctx, GameError("beta_access_required"))
            self.assertEqual(get_user_language(user_id), "fr")
            mock_ctx.send.assert_called_once()
            sent_text = mock_ctx.send.call_args[0][0]
            # Le message doit être en français
            self.assertIn("Accès Bêta restreint", sent_text)

        invalidate_language_cache()


class TestBlockchainLogs(unittest.IsolatedAsyncioTestCase):
    """Teste les logs lore-friendly dans le salon #blockchain."""

    async def test_log_blockchain_ready(self):
        from utils.logger import Logger
        bot = MagicMock()
        mock_channel = AsyncMock()
        bot.get_channel.return_value = mock_channel
        
        logger = Logger(bot)
        with patch.dict(os.environ, {"LOG_BLOCKCHAIN_CHANNEL_ID": "999888777"}):
            await logger.log_blockchain_ready()
            mock_channel.send.assert_called_once()
            sent_text = mock_channel.send.call_args[0][0]
            self.assertIn("Connexion au réseau Rootium…", sent_text)
            self.assertIn("Connecté.", sent_text)
            self.assertIn("Transactions Rootium en direct :", sent_text)

    async def test_log_blockchain_transaction(self):
        from utils.logger import Logger
        bot = MagicMock()
        mock_channel = AsyncMock()
        bot.get_channel.return_value = mock_channel

        logger = Logger(bot)
        fixed_dt = datetime(2026, 9, 16, 8, 42, 17, 446000, tzinfo=timezone.utc)
        with patch.dict(os.environ, {"LOG_BLOCKCHAIN_CHANNEL_ID": "999888777"}):
            await logger.log_blockchain_transaction(
                from_id=123456789,
                to_address="0xROOT_BLACK_MARKET",
                rtm_amount=Decimal("0.06"),
                dt=fixed_dt,
            )
            mock_channel.send.assert_called_once()
            sent_text = mock_channel.send.call_args[0][0]
            self.assertTrue(sent_text.startswith("```text\n"))
            self.assertTrue(sent_text.endswith("\n```"))
            self.assertIn("⏱  2026-09-16 08:42:17.446", sent_text)
            self.assertIn("FROM   123456789", sent_text)
            self.assertIn("TO     0xROOT_BLACK_MARKET", sent_text)
            self.assertIn("RTM    0.06000", sent_text)

    async def test_log_blockchain_sell_token(self):
        from utils.logger import Logger
        bot = MagicMock()
        mock_channel = AsyncMock()
        bot.get_channel.return_value = mock_channel

        logger = Logger(bot)
        fixed_dt = datetime(2026, 9, 16, 8, 42, 17, 446000, tzinfo=timezone.utc)
        with patch.dict(os.environ, {"LOG_BLOCKCHAIN_CHANNEL_ID": "999888777"}):
            await logger.log_blockchain_transaction(
                from_id=123456789,
                to_address="0xROOTIUM_DEX",
                rtm_amount=Decimal("0.00002"),
                dt=fixed_dt,
                tx_type="SELL TOKEN",
                usd_amount=Decimal("0.87"),
            )
            sent_text = mock_channel.send.call_args[0][0]
            self.assertIn("FROM   123456789", sent_text)
            self.assertIn("TO     0xROOTIUM_DEX", sent_text)
            self.assertIn("TYPE   SELL TOKEN", sent_text)
            self.assertIn("RTM    0.00002", sent_text)
            self.assertIn("USD    0.87", sent_text)



class TestTradeSystem(unittest.IsolatedAsyncioTestCase):
    """Teste le système de trade : SQL atomique, validation asymétrique, logs et DMs."""

    def setUp(self):
        self.tx = MockTransaction()
        self.tx.players[101] = {
            "discord_id": 101,
            "dollars": Decimal("100.00"),
            "rootium": Decimal("5.00000"),
            "firewall_level": 1,
            "lang": "fr",
        }
        self.tx.players[202] = {
            "discord_id": 202,
            "dollars": Decimal("50.00"),
            "rootium": Decimal("1.00000"),
            "firewall_level": 1,
            "lang": "en",
        }

    def test_trade_sql_bilateral_success(self):
        """Vérifie un échange bilatéral USD <-> RTM réussi."""
        res = Player.trade(
            self.tx,
            initiator=101,
            target=202,
            send_usd=Decimal("30.00"),
            send_rtm=Decimal("0.00000"),
            receive_usd=Decimal("0.00"),
            receive_rtm=Decimal("0.50000"),
        )
        self.assertTrue(res["trade_completed"])
        self.assertEqual(self.tx.players[101]["dollars"], Decimal("70.00"))
        self.assertEqual(self.tx.players[101]["rootium"], Decimal("5.50000"))
        self.assertEqual(self.tx.players[202]["dollars"], Decimal("80.00"))
        self.assertEqual(self.tx.players[202]["rootium"], Decimal("0.50000"))

    def test_trade_sql_unilateral_gift(self):
        """Vérifie un don unilatéral d'USD."""
        res = Player.trade(
            self.tx,
            initiator=101,
            target=202,
            send_usd=Decimal("25.00"),
            send_rtm=Decimal("0"),
            receive_usd=Decimal("0"),
            receive_rtm=Decimal("0"),
        )
        self.assertTrue(res["trade_completed"])
        self.assertEqual(self.tx.players[101]["dollars"], Decimal("75.00"))
        self.assertEqual(self.tx.players[202]["dollars"], Decimal("75.00"))

    def test_trade_sql_self_target(self):
        """Vérifie le rejet d'un échange avec soi-même."""
        with self.assertRaises(GameError) as ctx:
            Player.trade(self.tx, initiator=101, target=101, send_usd=10)
        self.assertEqual(ctx.exception.key, "self_target")

    def test_trade_sql_empty_trade(self):
        """Vérifie le rejet d'un échange sans aucun montant (> 0)."""
        with self.assertRaises(GameError) as ctx:
            Player.trade(self.tx, initiator=101, target=202, send_usd=0, send_rtm=0, receive_usd=0, receive_rtm=0)
        self.assertEqual(ctx.exception.key, "invalid_amount")

    def test_trade_sql_negative_amount(self):
        """Vérifie le rejet de montants négatifs."""
        with self.assertRaises(GameError) as ctx:
            Player.trade(self.tx, initiator=101, target=202, send_usd=-10)
        self.assertEqual(ctx.exception.key, "invalid_amount")

    def test_trade_sql_insufficient_funds_initiator(self):
        """Vérifie le rejet si l'initiateur manque de fonds."""
        with self.assertRaises(GameError) as ctx:
            Player.trade(self.tx, initiator=101, target=202, send_usd=500)
        self.assertEqual(ctx.exception.key, "insufficient_funds")

    def test_trade_sql_insufficient_funds_target(self):
        """Vérifie le rejet si la cible manque de fonds pour honorer la demande."""
        with self.assertRaises(GameError) as ctx:
            Player.trade(self.tx, initiator=101, target=202, send_usd=10, receive_rtm=10)
        self.assertEqual(ctx.exception.key, "insufficient_funds")

    async def test_trade_view_asymmetric_validation_rules(self):
        """Vérifie que la vue détermine correctement qui doit valider."""
        from utils.trade_view import TradeView
        bot = MagicMock()
        user_a = MagicMock(); user_a.id = 101
        user_b = MagicMock(); user_b.id = 202
        ctx = MagicMock(); ctx.author = user_a; ctx.guild = None

        # 1. Bilatéral : les deux doivent valider
        v1 = TradeView(bot, user_a, user_b, Decimal("10"), Decimal("0"), Decimal("5"), Decimal("0"), ctx)
        self.assertTrue(v1.needs_initiator)
        self.assertTrue(v1.needs_target)

        # 2. Don de A vers B : seul A doit valider
        v2 = TradeView(bot, user_a, user_b, Decimal("10"), Decimal("0"), Decimal("0"), Decimal("0"), ctx)
        self.assertTrue(v2.needs_initiator)
        self.assertFalse(v2.needs_target)

        # 3. Demande de A envers B : seul B doit valider
        v3 = TradeView(bot, user_a, user_b, Decimal("0"), Decimal("0"), Decimal("5"), Decimal("0"), ctx)
        self.assertFalse(v3.needs_initiator)
        self.assertTrue(v3.needs_target)

    async def test_trade_moderation_and_blockchain_logging(self):
        """Vérifie l'expédition des logs dans les bons salons Discord."""
        from utils.logger import Logger
        bot = MagicMock()
        mock_chan_bc = AsyncMock()
        mock_chan_mod = AsyncMock()

        def get_channel_side_effect(cid):
            if cid == 1111:
                return mock_chan_bc
            if cid == 2222:
                return mock_chan_mod
            return None

        bot.get_channel.side_effect = get_channel_side_effect
        logger = Logger(bot)

        with patch.dict(os.environ, {
            "LOG_BLOCKCHAIN_CHANNEL_ID": "1111",
            "LOG_MODERATION_TRADE_CHANNEL_ID": "2222",
        }):
            user_a = MagicMock(); user_a.id = 101; user_a.name = "Alice"; user_a.mention = "<@101>"
            user_b = MagicMock(); user_b.id = 202; user_b.name = "Bob"; user_b.mention = "<@202>"

            # Log modération trade
            await logger.log_trade(
                initiator=user_a,
                target=user_b,
                send_usd=Decimal("50.00"),
                send_rtm=Decimal("1.50000"),
                rec_usd=Decimal("0.00"),
                rec_rtm=Decimal("0.00000"),
            )
            mock_chan_mod.send.assert_called_once()
            embed = mock_chan_mod.send.call_args[1]["embed"]
            self.assertIn("Échange de ressources validé", embed.title)
            self.assertIn("Envoyeur", embed.description)
            self.assertIn("Récepteur", embed.description)
            self.assertIn("50.00 USD", embed.description)
            self.assertIn("1.50000 RTM", embed.description)

            # Log blockchain pour le transfert de Rootium
            await logger.log_blockchain_transaction(
                from_id=101,
                to_address="202",
                rtm_amount=Decimal("1.50000"),
            )
            mock_chan_bc.send.assert_called_once()
            bc_text = mock_chan_bc.send.call_args[0][0]
            self.assertIn("FROM   101", bc_text)
            self.assertIn("TO     202", bc_text)
            self.assertIn("RTM    1.50000", bc_text)

    def test_parse_trade_tokens(self):
        """Vérifie le parsing des montants et devises avec préfixes + (reçu) et - (envoyé)."""
        from commands.game.trade import parse_trade_tokens

        # 1. Bilatéral classique (- donne, + demande)
        s_usd, s_rtm, r_usd, r_rtm = parse_trade_tokens("-50usd +1rtm")
        self.assertEqual(s_usd, Decimal("50"))
        self.assertEqual(s_rtm, Decimal("0"))
        self.assertEqual(r_usd, Decimal("0"))
        self.assertEqual(r_rtm, Decimal("1"))

        # 2. Multiples ressources et tolérance des espaces
        s_usd, s_rtm, r_usd, r_rtm = parse_trade_tokens("-100$ -2.5rtm +10usd +0.05rtm")
        self.assertEqual(s_usd, Decimal("100"))
        self.assertEqual(s_rtm, Decimal("2.5"))
        self.assertEqual(r_usd, Decimal("10"))
        self.assertEqual(r_rtm, Decimal("0.05"))

        # 3. Don unilatéral (- envoyé)
        s_usd, s_rtm, r_usd, r_rtm = parse_trade_tokens("-20usd")
        self.assertEqual(s_usd, Decimal("20"))
        self.assertEqual(r_usd, Decimal("0"))

        # 4. Demande unilatérale (+ reçu)
        s_usd, s_rtm, r_usd, r_rtm = parse_trade_tokens("+5rtm")
        self.assertEqual(s_rtm, Decimal("0"))
        self.assertEqual(r_rtm, Decimal("5"))

        # 5. Erreurs : trop de décimales
        with self.assertRaises(ValueError):
            parse_trade_tokens("-10.123usd")  # Max 2 décimales pour USD
        with self.assertRaises(ValueError):
            parse_trade_tokens("-1.123456rtm")  # Max 5 décimales pour RTM

        # 6. Erreurs : ressource inconnue ou syntaxe invalide
        with self.assertRaises(ValueError):
            parse_trade_tokens("-10gold")
        with self.assertRaises(ValueError):
            parse_trade_tokens("n'importe quoi")



class TestNewUpdateFeatures(unittest.IsolatedAsyncioTestCase):
    """Tests pour les nouvelles fonctionnalités et le refactoring de la mise à jour."""

    def test_bay_title_no_rack_tier(self):
        """Vérifie que la mention Rack Tier a bien été retirée des titres de baies."""
        from lang.game_fr import text as fr_text
        from lang.game_en import text as en_text

        self.assertNotIn("Rack Tier", fr_text["g_net_rack_bay_title"])
        self.assertNotIn("Rack Tier", en_text["g_net_rack_bay_title"])
        self.assertIn("Baie", fr_text["g_net_rack_bay_title"])
        self.assertIn("Bay", en_text["g_net_rack_bay_title"])

    def test_attest_parsing(self):
        """Vérifie la validation des devises et des montants dans la commande Attest."""
        from commands.game.attest import Attest

        mock_bot = MagicMock()
        attest_cog = Attest(mock_bot)

        # Parsing valide
        code, val = attest_cog._parse_currency_amount("usd", "500")
        self.assertEqual(code, "USD")
        self.assertEqual(val, Decimal("500"))

        code, val = attest_cog._parse_currency_amount("rtm", "1.23456")
        self.assertEqual(code, "RTM")
        self.assertEqual(val, Decimal("1.23456"))

        code, val = attest_cog._parse_currency_amount("$", "10.50")
        self.assertEqual(code, "USD")
        self.assertEqual(val, Decimal("10.50"))

        # Erreurs
        with self.assertRaises(ValueError):
            attest_cog._parse_currency_amount("gold", "100")
        with self.assertRaises(ValueError):
            attest_cog._parse_currency_amount("usd", "-50")
        with self.assertRaises(ValueError):
            attest_cog._parse_currency_amount("usd", "10.555")  # > 2 décimales pour USD
        with self.assertRaises(ValueError):
            attest_cog._parse_currency_amount("rtm", "1.1234567")  # > 5 décimales pour RTM

    async def test_top_rtm_hidden(self):
        """Vérifie que RTM est masqué dans /top et que la phrase d'intro est retirée."""
        import discord
        from commands.game.top import Top, TopView

        mock_bot = MagicMock()
        top_cog = Top(mock_bot)
        mock_ctx = MagicMock()
        mock_ctx.author.id = 123456
        mock_ctx.guild = None

        view = TopView(top_cog, mock_ctx)
        cat_ids = [item.custom_id for item in view.children]
        self.assertNotIn("top_cat_rtm", cat_ids)
        self.assertIn("top_cat_reputation", cat_ids)
        self.assertIn("top_cat_usd", cat_ids)
        self.assertIn("top_cat_events", cat_ids)

        embed = top_cog._build_top_embed(mock_ctx, {
            "category": "usd",
            "ranking": [{"discord_id": 123456, "score": Decimal("100")}]
        })
        self.assertNotIn("Voici les meilleurs joueurs", embed.description)
        self.assertIn("`100.00` USD", embed.description)

    async def test_challenge_tracker(self):
        """Vérifie l'enregistrement et la notification automatique de victoire dans ChallengeTracker."""
        import discord
        from game.challenge_tracker import ChallengeTracker
        from datetime import datetime, timezone, timedelta

        mock_msg = AsyncMock(spec=discord.Message)
        mock_msg.id = 999
        mock_msg.edit = AsyncMock()

        await ChallengeTracker.register_message("test_game", mock_msg)
        next_dt = datetime.now(timezone.utc) + timedelta(minutes=5)
        await ChallengeTracker.notify_win("test_game", winner_id=111, next_at=next_dt)

        mock_msg.edit.assert_called_once()
        call_kwargs = mock_msg.edit.call_args[1]
        self.assertIn("<@111>", call_kwargs["content"])
        self.assertIn("résolu le défi", call_kwargs["content"])

    async def test_ui_components_buttons(self):
        """Vérifie la création unifiée des boutons."""
        import discord
        from utils.ui_components import create_confirm_button, create_cancel_button, create_trade_buttons

        mock_ctx = MagicMock()
        mock_ctx.author.id = 1
        btn_c = create_confirm_button(mock_ctx)
        btn_x = create_cancel_button(mock_ctx)
        self.assertEqual(btn_c.style, discord.ButtonStyle.success)
        self.assertEqual(btn_x.style, discord.ButtonStyle.danger)

        v_btn, r_btn = create_trade_buttons(mock_ctx, AsyncMock(), AsyncMock())
        self.assertEqual(v_btn.style, discord.ButtonStyle.success)
        self.assertEqual(r_btn.style, discord.ButtonStyle.danger)

    async def test_attest_flow(self):
        """Vérifie que /attest et !attest envoient le succès et le refus directement dans le salon."""
        from commands.game.attest import Attest
        bot = MagicMock()
        bot.root_service = MagicMock()
        cog = Attest(bot)

        # Mock database return
        cog.service.database.run = AsyncMock(return_value={"dollars": 1000, "rootium": 50})

        # Mock player check
        with patch("commands.game.attest.Check.is_player", new=AsyncMock(return_value=True)):
            # Cas 1: Fonds suffisants (USD)
            ctx = MagicMock()
            ctx.author.id = 12345
            ctx.respond = AsyncMock()
            ctx.interaction = MagicMock()
            await cog._process_attest(ctx, "USD", "500")
            ctx.respond.assert_called_once()
            args, kwargs = ctx.respond.call_args
            self.assertTrue("<@12345> a bien au moins **500.00 USD**" in args[0] or "<@12345> holds at least **500.00 USD**" in args[0])
            self.assertFalse(kwargs.get("ephemeral", False))

            # Cas 2: Refus envoyé sur le salon (pas en MP ni ephemeral)
            ctx2 = MagicMock()
            ctx2.author.id = 12345
            ctx2.respond = AsyncMock()
            ctx2.interaction = MagicMock()
            await cog._process_attest(ctx2, "USD", "2000")
            ctx2.respond.assert_called_once()
            args2, kwargs2 = ctx2.respond.call_args
            self.assertTrue("<@12345> n'a pas au moins **2,000.00 USD**" in args2[0] or "<@12345> does not hold at least **2,000.00 USD**" in args2[0])
            self.assertFalse(kwargs2.get("ephemeral", False))

    async def test_trade_acceptance_deletes_message(self):
        """Vérifie que l'acceptation de l'échange supprime le message du salon au lieu d'afficher un résumé public."""
        from utils.trade_view import TradeView
        bot = MagicMock()
        bot.root_service = MagicMock()
        bot.root_service.execute = AsyncMock(return_value={"initiator_lang": "fr", "target_lang": "fr"})

        ctx = MagicMock()
        ctx.author.id = 111
        ctx.guild = MagicMock()
        ctx.guild.id = 999
        ctx.interaction = MagicMock()
        ctx.interaction.delete_original_response = AsyncMock()

        initiator = MagicMock()
        initiator.id = 111
        initiator.send = AsyncMock()
        target = MagicMock()
        target.id = 222
        target.send = AsyncMock()

        view = TradeView(
            bot=bot,
            ctx=ctx,
            initiator=initiator,
            target=target,
            send_usd=Decimal("100"),
            send_rtm=Decimal("0"),
            receive_usd=Decimal("0"),
            receive_rtm=Decimal("10"),
        )
        view.message = MagicMock()
        view.message.delete = AsyncMock()

        with patch("utils.trade_view.Logger") as mock_logger_cls:
            mock_logger = MagicMock()
            mock_logger.log_blockchain_transaction = AsyncMock()
            mock_logger.log_trade = AsyncMock()
            mock_logger_cls.return_value = mock_logger

            interaction = MagicMock()
            await view._execute_trade(interaction)

            # Doit avoir supprimé le message
            ctx.interaction.delete_original_response.assert_called_once()
            # DMs doivent avoir été envoyés
            initiator.send.assert_called_once()
            target.send.assert_called_once()


class TestMiningClaimAndWelcome(unittest.TestCase):
    """Couvre le minage (claim), RootService et l'accueil langue du premier réseau."""

    def setUp(self):
        self.tx = MockTransaction()
        self.actor = 4242
        Player.network(self.tx, self.actor)

    def test_compute_mining_progress_t1_fill_time(self):
        self.tx.players[self.actor]["mining_t1"] = 1
        self.tx.players[self.actor]["mining_buffer"] = Decimal("0")
        self.tx.players[self.actor]["mining_last_update_at"] = self.tx.now
        stats = MathConfig.calculate_player_stats(self.tx.players[self.actor])
        state = MathConfig.compute_mining_progress(self.tx.players[self.actor], stats, self.tx.now)
        self.assertAlmostEqual(state["seconds_to_fill_total"], 8 * 60, delta=2)
        self.assertEqual(state["total_ram_bytes"], MathConfig.get_module_ram(1))
        self.assertFalse(state["is_full"])

    def test_claim_no_miner_empty_success_cooldown(self):
        none = Player.claim(self.tx, self.actor)
        self.assertFalse(none.get("claimed"))
        self.assertEqual(none.get("reason"), "no_miner")

        self.tx.players[self.actor]["mining_t1"] = 1
        self.tx.players[self.actor]["mining_buffer"] = Decimal("0")
        self.tx.players[self.actor]["mining_last_update_at"] = self.tx.now
        empty = Player.claim(self.tx, self.actor)
        self.assertEqual(empty.get("reason"), "empty")

        self.tx.players[self.actor]["mining_buffer"] = Decimal("0.00001")
        self.tx.players[self.actor]["mining_last_update_at"] = self.tx.now
        before = Decimal(str(self.tx.players[self.actor]["rootium"]))
        ok = Player.claim(self.tx, self.actor)
        self.assertTrue(ok.get("claimed"))
        self.assertEqual(ok.get("amount"), Decimal("0.00001"))
        self.assertEqual(self.tx.players[self.actor]["rootium"], before + Decimal("0.00001"))
        self.assertEqual(self.tx.players[self.actor]["mining_buffer"], Decimal("0"))

        with self.assertRaises(GameError) as cm:
            Player.claim(self.tx, self.actor)
        self.assertEqual(cm.exception.key, "claim_cooldown")

    def test_root_service_actions_include_claim_and_convert(self):
        from game.root_service import RootService
        self.assertIn("claim", RootService.ACTIONS)
        self.assertIn("convert", RootService.ACTIONS)
        self.assertIn("compile", RootService.ACTIONS)
        self.assertIn("hack", RootService.ACTIONS)
        self.assertEqual(RootService._locks_for("claim", 42, {}), ["player:42"])
        self.assertEqual(RootService._locks_for("convert", 42, {}), ["player:42"])
        self.assertEqual(RootService._locks_for("compile", 42, {}), ["player:42"])

    def test_welcome_copy_exists(self):
        self.assertIn("{prefix}", game_fr.text["g_welcome_onboarding"])
        self.assertIn("{prefix}", game_en.text["g_welcome_onboarding"])
        self.assertIn("event", game_fr.text["g_welcome_onboarding"].lower())
        self.assertIn("buy", game_en.text["g_welcome_onboarding"].lower())
        self.assertIn("claim", game_fr.text["g_welcome_onboarding"].lower())
        self.assertIn("claim", game_en.text["g_welcome_onboarding"].lower())
        self.assertIn("mineur de tiers 1", game_fr.text["g_welcome_onboarding"].lower())
        self.assertIn("tier 1 miner", game_en.text["g_welcome_onboarding"].lower())


class TestWelcomeLanguageView(unittest.IsolatedAsyncioTestCase):
    """WelcomeLanguageView exige une boucle asyncio (Pycord)."""

    async def test_welcome_language_buttons(self):
        from commands.game.network import WelcomeLanguageView
        fr_view = WelcomeLanguageView(1, "fr", "/")
        fr_labels = [child.label for child in fr_view.children]
        self.assertEqual(fr_labels[0], "Français")
        self.assertIn("English", fr_labels)

        en_view = WelcomeLanguageView(1, "en", "!")
        en_labels = [child.label for child in en_view.children]
        self.assertEqual(en_labels[0], "English")
        self.assertIn("Français", en_labels)


class TestPreExistingGameCoverage(unittest.TestCase):
    """Couverture des mécaniques déjà présentes avant le minage/claim/convert du jour."""

    def setUp(self):
        self.tx = MockTransaction()
        self.actor = 424242
        Player.network(self.tx, self.actor)

    def test_player_data_requires_network(self):
        with self.assertRaises(GameError) as cm:
            PlayerData.get(self.tx, 1)
        self.assertEqual(cm.exception.key, "no_network")

    def test_new_player_is_new_then_idempotent(self):
        grant = Decimal(str(MathConfig.load()["initial_grant_usd"]))
        first = NewPlayer.create(self.tx, 77, self.tx.now, grant)
        self.assertTrue(first["is_new"])
        second = NewPlayer.create(self.tx, 77, self.tx.now, grant)
        self.assertFalse(second["is_new"])
        self.assertEqual(second["dollars"], grant)

    def test_update_player_whitelist(self):
        UpdatePlayer.set(self.tx, self.actor, lang="fr")
        self.assertEqual(self.tx.players[self.actor]["lang"], "fr")
        with self.assertRaises(GameError) as cm:
            UpdatePlayer.set(self.tx, self.actor, password="x")
        self.assertEqual(cm.exception.key, "invalid_selection")

    def test_set_and_get_language(self):
        self.assertIsNone(Player.get_language(self.tx, self.actor))
        Player.set_language(self.tx, self.actor, "en")
        self.assertEqual(Player.get_language(self.tx, self.actor), "en")
        Player.set_language(self.tx, self.actor, None)
        self.assertIsNone(Player.get_language(self.tx, self.actor))
        self.assertIsNone(Player.get_language(self.tx, 999999))

    def test_network_is_new_and_pending_upgrade(self):
        first = Player.network(self.tx, 88)
        self.assertTrue(first.get("is_new"))
        again = Player.network(self.tx, 88)
        self.assertFalse(again.get("is_new"))

        expires = self.tx.now + timedelta(hours=1)
        UpgradesDB.create(self.tx, 88, 1, expires)
        with_upgrade = Player.network(self.tx, 88)
        self.assertEqual(with_upgrade["pending_upgrade"]["target_level"], 1)

    def test_calculate_player_stats_mixed_modules(self):
        row = self.tx.players[self.actor]
        row["mining_t1"] = 2
        row["mining_t2"] = 1
        row["attack_t1"] = 3
        row["bay_defense_t1"] = 1
        row["firewall_level"] = 1
        stats = MathConfig.calculate_player_stats(row)
        self.assertEqual(
            stats["total_hashrate_hs"],
            2 * MathConfig.get_module_stat("mining", 1) + MathConfig.get_module_stat("mining", 2),
        )
        self.assertEqual(
            stats["total_ram_bytes"],
            2 * MathConfig.get_module_ram(1) + MathConfig.get_module_ram(2),
        )
        self.assertEqual(stats["total_bits_per_s"], 3 * MathConfig.get_module_stat("attack", 1))
        self.assertEqual(stats["total_bay_defense"], MathConfig.get_module_stat("bay_defense", 1))
        self.assertEqual(stats["network_defense"], 100)
        self.assertEqual(stats["total_defense"], stats["total_bay_defense"] + 100)

    def test_mining_price_progression_and_firewall_gate(self):
        cfg = MathConfig.load()
        t1 = Decimal(str(cfg["mining"]["cost_t1_usd"]))
        mult = Decimal(str(cfg["mining"]["cost_multiplier"]))
        usd_t2, rtm_t2 = _calculate_module_price("mining_t2", 2)
        usd_t3, _ = _calculate_module_price("mining_t3", 3)
        self.assertEqual(usd_t2, t1 * mult)
        self.assertEqual(usd_t3, t1 * (mult ** 2))
        self.assertEqual(rtm_t2, Decimal("0"))

        with self.assertRaises(GameError) as cm:
            Player.buy(self.tx, self.actor, kind="mining", tier=2, confirm=False)
        self.assertEqual(cm.exception.key, "firewall_required")
        self.assertEqual(cm.exception.values["level"], 1)

        self.tx.players[self.actor]["firewall_level"] = 1
        with self.assertRaises(GameError) as cm:
            Player.buy(self.tx, self.actor, kind="mining", tier=3, confirm=False)
        self.assertEqual(cm.exception.key, "firewall_required")
        self.assertEqual(cm.exception.values["level"], 2)

        self.tx.players[self.actor]["dollars"] = usd_t2
        bought = Player.buy(self.tx, self.actor, kind="mining", tier=2, confirm=True)
        self.assertTrue(bought.get("bought"))
        self.assertEqual(self.tx.players[self.actor]["mining_t2"], 1)

    def test_buy_attack_and_bay_execution(self):
        cfg = MathConfig.load()
        attack_cost = Decimal(str(cfg["beta"]["attack_price_t1_rtm"]))
        bay_cost = Decimal(str(cfg["beta"]["bay_defense_usd"]))
        self.tx.players[self.actor]["firewall_level"] = 1
        self.tx.players[self.actor]["rootium"] = attack_cost
        self.tx.players[self.actor]["dollars"] = bay_cost

        atk = Player.buy(self.tx, self.actor, kind="attack", tier=1, confirm=True)
        self.assertTrue(atk.get("bought"))
        self.assertEqual(self.tx.players[self.actor]["attack_t1"], 1)
        self.assertEqual(self.tx.players[self.actor]["rootium"], Decimal("0"))

        bay = Player.buy(self.tx, self.actor, kind="defense", tier=1, confirm=True)
        self.assertTrue(bay.get("bought"))
        self.assertEqual(self.tx.players[self.actor]["bay_defense_t1"], 1)
        self.assertEqual(self.tx.players[self.actor]["dollars"], Decimal("0"))

        with self.assertRaises(GameError) as cm:
            Player.buy(self.tx, self.actor, kind="mining", tier="abc", confirm=False)
        self.assertEqual(cm.exception.key, "invalid_selection")

        with self.assertRaises(GameError) as cm:
            Player.buy(self.tx, self.actor, kind="gpu", tier=1, confirm=False)
        self.assertEqual(cm.exception.key, "invalid_selection")

    def test_firewall_upgrade_price_duration_and_funds(self):
        cfg = MathConfig.load()
        t1 = Decimal(str(cfg["firewall"]["first_upgrade_usd"]))
        mult = Decimal(str(cfg["firewall"]["upgrade_multiplier"]))
        duration = int(cfg["firewall"]["upgrade_duration_seconds"])
        usd_t2, _ = _calculate_module_price("firewall", 2)
        self.assertEqual(usd_t2, t1 * mult)

        with self.assertRaises(GameError) as cm:
            Player.upgrade(self.tx, self.actor, confirm=False)
        self.assertEqual(cm.exception.key, "upgrade_insufficient_funds")
        self.assertEqual(cm.exception.values["level"], 1)

        self.tx.players[self.actor]["dollars"] = t1
        quote = Player.upgrade(self.tx, self.actor, confirm=False)
        self.assertEqual(quote["duration_seconds"], duration)
        self.assertEqual(quote["usd_price"], t1)

    def test_upgrade_greatest_does_not_lower_firewall(self):
        self.tx.players[self.actor]["firewall_level"] = 3
        UpgradesDB.create(self.tx, self.actor, 1, self.tx.now)
        delivered = UpgradesDB.complete_and_delete_expired(self.tx)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(self.tx.players[self.actor]["firewall_level"], 3)

    def test_reputation_target_not_registered(self):
        with self.assertRaises(GameError) as cm:
            Player.give_reputation(self.tx, self.actor, 123456)
        self.assertEqual(cm.exception.key, "target_not_registered")

    def test_top_category_aliases(self):
        other = 1001
        Player.network(self.tx, other)
        self.tx.players[other]["rootium"] = Decimal("9.00000")
        self.tx.players[other]["events_won"] = 7
        self.tx.players[self.actor]["reputation"] = 3

        top_rep = Player.top(self.tx, "rep")
        self.assertEqual(top_rep["category"], "reputation")
        self.assertEqual(top_rep["ranking"][0]["discord_id"], self.actor)

        top_rtm = Player.top(self.tx, "rtm")
        self.assertEqual(top_rtm["category"], "rtm")
        self.assertEqual(top_rtm["ranking"][0]["score"], Decimal("9.00000"))

        top_ev = Player.top(self.tx, "e")
        self.assertEqual(top_ev["category"], "events")
        self.assertEqual(top_ev["ranking"][0]["score"], 7)

        unknown = Player.top(self.tx, "gold")
        self.assertEqual(unknown["category"], "reputation")

    def test_events_db_and_manager_cooldown(self):
        future = self.tx.now + timedelta(minutes=12)
        EventsDB.save(self.tx, "hash", future, last_found_by=7, last_found_on="Alpha", last_reward=Decimal("8.50"))
        row = EventsDB.get(self.tx, "hash")
        self.assertEqual(row["last_found_by"], 7)
        self.assertEqual(row["last_found_on"], "Alpha")

        status = EventsManager.get_all_events_status(self.tx)
        self.assertEqual(status["events"]["hash"]["status"], "cooldown")
        self.assertEqual(status["events"]["hash"]["last_found_by"], 7)
        self.assertEqual(status["events"]["pin"]["status"], "active")
        self.assertGreater(status["events"]["hash"]["remaining_seconds"], 0)

    def test_daily_event_stats_cycle(self):
        DailyEventStatsDB.record_participation(self.tx, self.actor)
        DailyEventStatsDB.record_participation(self.tx, self.actor)
        DailyEventStatsDB.record_win(self.tx, self.actor)
        other = 55
        DailyEventStatsDB.record_participation(self.tx, other)

        summary = DailyEventStatsDB.get_summary(self.tx)
        self.assertEqual(summary[0]["discord_id"], self.actor)
        self.assertEqual(summary[0]["events_won"], 1)
        self.assertEqual(summary[0]["events_participated"], 2)

        DailyEventStatsDB.set_last_report_date(self.tx, "2026-09-16", self.tx.now)
        self.assertEqual(DailyEventStatsDB.get_last_report_date(self.tx), "2026-09-16")

        DailyEventStatsDB.reset(self.tx)
        self.assertEqual(DailyEventStatsDB.get_summary(self.tx), [])

    def test_prefix_db_get_set_delete(self):
        import data as data_mod
        self.assertEqual(PrefixDB.get(self.tx, 1), data_mod.DEFAULT_PREFIX)
        PrefixDB.set(self.tx, 1, "!root")
        self.assertEqual(PrefixDB.get(self.tx, 1), "!root")
        PrefixDB.delete(self.tx, 1)
        self.assertEqual(PrefixDB.get(self.tx, 1), data_mod.DEFAULT_PREFIX)

    def test_game_error_and_error_i18n_keys(self):
        err = GameError("firewall_required", level=2)
        self.assertEqual(err.key, "firewall_required")
        self.assertEqual(err.values["level"], 2)
        for key in (
            "no_network", "invalid_selection", "insufficient_funds_usd",
            "insufficient_funds_rtm", "firewall_required", "maximum_level",
            "self_target", "cooldown", "target_not_registered",
            "upgrade_in_progress", "upgrade_insufficient_funds", "invalid_amount",
            "invalid_secret_id", "secret_id_exhausted",
            "compile_in_progress", "no_attack_modules",
        ):
            self.assertIn("g_error_" + key, game_fr.text)
            self.assertIn("g_error_" + key, game_en.text)

    def test_command_descriptions_cover_core_actions(self):
        from commands.game.game_config import GAMES
        for key in ("network", "buy", "upgrade", "rep", "top", "event", "trade", *GAMES):
            self.assertIn(key, game_fr.descriptions)
            self.assertIn(key, game_en.descriptions)
        for action in ("network", "buy", "upgrade", "reputation", "top", "hash", "trade", "compile"):
            self.assertIn("act_" + action, game_fr.labels)
            self.assertIn("act_" + action, game_en.labels)
        self.assertIn("compile", game_fr.descriptions)
        self.assertIn("compile", game_en.descriptions)

    def test_math_config_formula_code_and_numeric_constants(self):
        rules = {"formulas": {"mix": "min(a, b) + max(1, 2) * 3"}}
        self.assertEqual(MathConfig.formula(rules, "mix", a=4, b=9), Decimal("10"))
        cfg = MathConfig.load()
        fingerprint = MathConfig.code(cfg)
        self.assertTrue(fingerprint.startswith(cfg["version"] + "-"))
        self.assertEqual(len(fingerprint.split("-", 1)[1]), 12)
        with self.assertRaises(ValueError):
            MathConfig.validate(ast.parse("'nope'", mode="eval"))

    def test_challenge_intervals_day_and_night(self):
        from game.challenge_utils import calculate_next_interval_seconds, is_paris_day
        cfg = MathConfig.load()["hash_challenge"]
        day_dt = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        night_dt = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
        self.assertTrue(is_paris_day(day_dt))
        self.assertFalse(is_paris_day(night_dt))
        with patch("game.challenge_utils.random.randint", return_value=15):
            self.assertEqual(calculate_next_interval_seconds(day_dt, "hash_challenge"), 15 * 60)
        with patch("game.challenge_utils.random.randint", return_value=25):
            self.assertEqual(calculate_next_interval_seconds(night_dt, "hash_challenge"), 25 * 60)
        self.assertEqual(int(cfg["day_interval_min_minutes"]), 15)
        self.assertEqual(int(cfg["night_interval_min_minutes"]), 25)

    def test_formatters_and_locale_fallbacks(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        past = datetime(2026, 1, 1, 11, 0, 0)
        self.assertEqual(format_remaining_time(past, now), "0s")
        self.assertIn("MISSING_KEY", text.get_for_lang("en", "no_such_key_xyz"))
        self.assertEqual(data.env_ids("ROOT_TEST_EMPTY_IDS"), [])
        with patch.dict(os.environ, {"ROOT_TEST_IDS": "10, 20, 30"}):
            self.assertEqual(data.env_ids("ROOT_TEST_IDS"), [10, 20, 30])
        self.assertEqual(set(data.SUPPORTED_LANGS), {"fr", "en"})
        self.assertTrue(data.DEFAULT_PREFIX)

        from utils.language_manager import invalidate_language_cache, _cache
        invalidate_language_cache()
        ctx = MagicMock()
        ctx.author.id = 321
        ctx.interaction = None
        self.assertEqual(text.get_locale(ctx), "en")
        _cache[321] = ("fr", time.monotonic() + 60)
        self.assertEqual(text.get_locale(ctx), "fr")
        invalidate_language_cache()
        ctx.interaction = MagicMock()
        ctx.interaction.locale = "fr"
        self.assertEqual(text.get_locale(ctx), "fr")
        ctx.interaction.locale = "de"
        self.assertEqual(text.get_locale(ctx), "en")
        invalidate_language_cache()


class TestPreExistingServiceAndUi(unittest.IsolatedAsyncioTestCase):
    """RootService, Confirmation, BaseGameCog et ChallengeTracker — couverture antérieure."""

    async def test_root_service_invalid_no_network_and_event(self):
        from game.root_service import RootService

        mock_db = MockDatabase()
        service = RootService(database=mock_db)
        with self.assertRaises(GameError) as cm:
            await service.execute(1, None, "not_an_action")
        self.assertEqual(cm.exception.key, "invalid_selection")

        with self.assertRaises(GameError) as cm:
            await service.execute(99, None, "buy", kind="mining", tier=1)
        self.assertEqual(cm.exception.key, "no_network")

        grant = Decimal(str(MathConfig.load()["initial_grant_usd"]))
        await service.execute(11, None, "network")
        self.assertEqual(mock_db.players[11]["dollars"], grant)

        result = await service.execute(11, None, "event")
        self.assertIn("events", result)
        self.assertIn("hash", result["events"])
        self.assertEqual(RootService._locks_for("event", 11, {}), [])
        self.assertEqual(RootService._locks_for("top", 11, {}), [])
        self.assertEqual(RootService._get_challenge_manager("hash"), HashManager)
        self.assertIsNone(RootService._get_challenge_manager("buy"))

    async def test_base_game_cog_invoke_error(self):
        from commands.game.commandgame import BaseGameCog

        class DummyCog(BaseGameCog):
            def __init__(self, bot):
                self.bot = bot
                self.err = None

            async def _prefetch_lang(self, user_id):
                return None

            async def _send(self, ctx, method, result):
                pass

            async def _send_error(self, ctx, error):
                self.err = error

        bot = MagicMock()
        bot.root_service.execute = AsyncMock(side_effect=GameError("no_network"))
        cog = DummyCog(bot)
        ctx = MagicMock()
        ctx.author.id = 1
        ctx.guild = None
        await cog._invoke(ctx, "buy", kind="mining")
        self.assertEqual(cog.err.key, "no_network")

        bot.root_service.execute = AsyncMock(return_value={"bought": True})
        cog.sent = None

        async def capture(ctx, method, result):
            cog.sent = (method, result)

        cog._send = capture
        await cog._invoke(ctx, "buy", kind="mining", tier=1, confirm=True)
        self.assertEqual(cog.sent[0], "buy")

    async def test_confirmation_cancel(self):
        from utils.confirmation import Confirmation

        mock_service = MagicMock()
        mock_service.execute = AsyncMock()
        mock_ctx = MagicMock()
        mock_ctx.author.id = 123
        mock_ctx.guild = None
        mock_ctx.bot = MagicMock()
        mock_ctx.interaction = None
        view = Confirmation(
            send_fn=AsyncMock(),
            service=mock_service,
            ctx=mock_ctx,
            method="buy",
            args={"kind": "mining", "tier": 1},
        )
        view.message = MagicMock()
        view.message.edit = AsyncMock()
        interaction = MagicMock()
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()
        await view.cancel(interaction)
        self.assertTrue(view.done)
        mock_service.execute.assert_not_called()
        view.message.edit.assert_called_once()

    async def test_confirmation_unexpected_error_sends_command_error(self):
        """Un crash hors GameError sur confirm ne doit plus rester silencieux ni mentir sur la DB."""
        from utils.confirmation import Confirmation

        mock_service = MagicMock()
        mock_service.execute = AsyncMock(side_effect=RuntimeError("boom"))
        mock_ctx = MagicMock()
        mock_ctx.author.id = 123
        mock_ctx.guild = None
        mock_ctx.bot = MagicMock()
        mock_ctx.interaction = None
        view = Confirmation(
            send_fn=AsyncMock(),
            service=mock_service,
            ctx=mock_ctx,
            method="compile",
            args={"mode": "unskilled", "atk": 5, "confirm": True},
        )
        interaction = MagicMock()
        interaction.user.id = 123
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()
        with patch("utils.confirmation.Check.is_player", new=AsyncMock(return_value=True)):
            await view.confirm(interaction)
        interaction.followup.send.assert_called_once()
        sent = interaction.followup.send.call_args[0][0]
        self.assertIn(text.get(mock_ctx, "command_error"), sent)
        self.assertTrue(view.done)

    async def test_challenge_tracker_skips_solved_message(self):
        import discord
        from game.challenge_tracker import ChallengeTracker

        solved = AsyncMock(spec=discord.Message)
        solved.id = 1
        other = AsyncMock(spec=discord.Message)
        other.id = 2
        other.edit = AsyncMock()
        ChallengeTracker._active_messages.pop("skip_game", None)
        await ChallengeTracker.register_message("skip_game", solved)
        await ChallengeTracker.register_message("skip_game", other)
        await ChallengeTracker.notify_win("skip_game", winner_id=9, next_at=None, solved_message_id=1)
        other.edit.assert_called_once()
        solved.edit.assert_not_called()


class TestSecretIds(unittest.TestCase):
    """Identifiant secret 6 chiffres : attribution, unicité, rotation UTC, lookup."""

    def setUp(self):
        MathConfig.clear_cache()
        self.tx = MockTransaction()
        self.cfg = MathConfig.load()["secret_id"]
        self.digits = int(self.cfg["digits"])
        self.interval = int(self.cfg["rotation_interval_seconds"])

    def _assert_valid_code(self, code):
        self.assertIsNotNone(code)
        self.assertEqual(len(str(code)), self.digits)
        self.assertTrue(str(code).isdigit())
        self.assertNotEqual(str(code), "000000")

    def test_network_create_assigns_unique_persisted_secret(self):
        row = Player.network(self.tx, 101)
        code = row["secret_id"]
        self._assert_valid_code(code)
        self.assertEqual(row["secret_id_display"], code)
        self.assertEqual(self.tx.players[101]["secret_id"], code)
        self.assertIn("secret_next_ts", row)
        self.assertGreater(row["secret_next_ts"], 0)

    def test_secret_id_zero_padding(self):
        from game.db.secret_ids import generate_unique
        with patch("game.db.secret_ids.secrets.randbelow", return_value=42):
            row = Player.network(self.tx, 102)
        self.assertEqual(row["secret_id"], "000042")
        self.assertEqual(row["secret_id_display"], "000042")
        with patch("game.db.secret_ids.secrets.randbelow", return_value=7):
            padded = generate_unique(self.tx, set())
        self.assertEqual(padded, "000007")

    def test_n_players_have_unique_codes(self):
        codes = []
        for i in range(12):
            row = Player.network(self.tx, 2000 + i)
            self._assert_valid_code(row["secret_id"])
            codes.append(row["secret_id"])
        self.assertEqual(len(set(codes)), 12)

    def test_lazy_assign_null_then_stable_on_second_network(self):
        Player.network(self.tx, 303)
        self.tx.players[303]["secret_id"] = None
        first = Player.network(self.tx, 303)
        self._assert_valid_code(first["secret_id"])
        code = first["secret_id"]
        second = Player.network(self.tx, 303)
        self.assertEqual(second["secret_id"], code)
        self.assertEqual(self.tx.players[303]["secret_id"], code)

    def test_rotation_when_next_at_past(self):
        from game.db.secret_ids import rotate_all_if_due
        for i in range(3):
            Player.network(self.tx, 400 + i)
        old = {uid: p["secret_id"] for uid, p in self.tx.players.items()}
        self.tx.events["secret_rotation"]["next_at"] = self.tx.now - timedelta(seconds=1)
        result = rotate_all_if_due(self.tx)
        self.assertTrue(result["rotated"])
        self.assertEqual(result["count"], 3)
        new = {uid: p["secret_id"] for uid, p in self.tx.players.items()}
        for code in new.values():
            self._assert_valid_code(code)
        self.assertEqual(len(set(new.values())), 3)
        self.assertGreater(result["next_at"], self.tx.now)
        self.assertGreater(self.tx.events["secret_rotation"]["next_at"], self.tx.now)

    def test_rotation_noop_when_next_at_future(self):
        from game.db.secret_ids import rotate_all_if_due
        Player.network(self.tx, 501)
        Player.network(self.tx, 502)
        old = {uid: p["secret_id"] for uid, p in self.tx.players.items()}
        old_next = self.tx.events["secret_rotation"]["next_at"]
        result = rotate_all_if_due(self.tx)
        self.assertFalse(result["rotated"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["next_at"], old_next)
        now_codes = {uid: p["secret_id"] for uid, p in self.tx.players.items()}
        self.assertEqual(now_codes, old)

    def test_catchup_overdue_one_regen_next_at_future(self):
        from game.db.secret_ids import next_rotation_at, rotate_all_if_due
        Player.network(self.tx, 601)
        Player.network(self.tx, 602)
        overdue = timedelta(seconds=self.interval * 3)
        self.tx.events["secret_rotation"]["next_at"] = self.tx.now - overdue
        result = rotate_all_if_due(self.tx)
        self.assertTrue(result["rotated"])
        self.assertEqual(result["count"], 2)
        self.assertGreater(result["next_at"], self.tx.now)
        self.assertEqual(result["next_at"], next_rotation_at(self.tx.now))
        codes = [p["secret_id"] for p in self.tx.players.values()]
        self.assertEqual(len(set(codes)), 2)
        for code in codes:
            self._assert_valid_code(code)

    def test_find_by_secret_id_valid_invalid_short_alpha_zero(self):
        row = Player.network(self.tx, 701)
        code = row["secret_id"]
        found = Player.find_by_secret_id(self.tx, code)
        self.assertEqual(found["discord_id"], 701)

        for bad in ("999991", "12345", "abcdef", "000000", "12ab56", ""):
            with self.subTest(code=bad):
                with self.assertRaises(GameError) as cm:
                    Player.find_by_secret_id(self.tx, bad)
                self.assertEqual(cm.exception.key, "invalid_secret_id")

    def test_collision_retry_mock(self):
        from game.db.secret_ids import generate_unique
        taken = set()
        with patch("game.db.secret_ids.secrets.randbelow", side_effect=[1, 1, 2]):
            first = generate_unique(self.tx, taken)
            second = generate_unique(self.tx, taken)
        self.assertEqual(first, "000001")
        self.assertEqual(second, "000002")
        self.assertEqual(taken, {"000001", "000002"})

    def test_000000_never_assigned(self):
        from game.db.secret_ids import generate_unique
        with patch("game.db.secret_ids.secrets.randbelow", side_effect=[0, 8]):
            code = generate_unique(self.tx, set())
        self.assertEqual(code, "000008")
        self.assertNotEqual(code, "000000")
        with patch("game.db.secret_ids.secrets.randbelow", return_value=0):
            with self.assertRaises(GameError) as cm:
                generate_unique(self.tx, set())
        self.assertEqual(cm.exception.key, "secret_id_exhausted")

    def test_error_i18n_keys(self):
        for key in ("invalid_secret_id", "secret_id_exhausted"):
            self.assertIn("g_error_" + key, game_fr.text)
            self.assertIn("g_error_" + key, game_en.text)
        self.assertIn("{secret_id}", game_fr.text["g_net_secret_desc"])
        self.assertIn("{timestamp}", game_en.text["g_net_secret_desc"])
        self.assertNotIn("{secret_id}", game_fr.text["g_net_footer"])
        self.assertNotIn("{secret_id}", game_en.text["g_net_footer"])


class TestCompile(unittest.TestCase):
    """Production d'ATK via /compile : Bit/s matériel, coût RTM, table hack."""

    def setUp(self):
        self.tx = MockTransaction()
        self.actor = 8080
        Player.network(self.tx, self.actor)
        self.tx.players[self.actor]["attack_t1"] = 2
        self.tx.players[self.actor]["attack_t5"] = 1
        self.tx.players[self.actor]["rootium"] = Decimal("10.00000")

    def test_method_aliases(self):
        self.assertEqual(MathConfig.normalize_compile_method("IA"), "ai")
        self.assertEqual(MathConfig.normalize_compile_method("qualifie"), "skilled")
        self.assertEqual(MathConfig.normalize_compile_method("nq"), "unskilled")
        self.assertIsNone(MathConfig.normalize_compile_method("hack"))

    def test_quote_scales_with_atk_and_bits(self):
        t1 = MathConfig.get_module_stat("attack", 1)
        full = MathConfig.compile_quote(t1, t1, "unskilled")
        double_atk = MathConfig.compile_quote(t1, t1 * 2, "unskilled")
        double_bits = MathConfig.compile_quote(t1 * 2, t1, "unskilled")
        self.assertEqual(full["duration_seconds"], 4500)
        self.assertEqual(double_atk["duration_seconds"], 9000)
        self.assertEqual(double_bits["duration_seconds"], 2250)
        self.assertEqual(full["rtm_paid"], Decimal("0.00100"))
        self.assertEqual(double_atk["rtm_paid"], Decimal("0.00200"))
        self.assertEqual(MathConfig.compile_quote(t1, t1, "skilled")["duration_seconds"], 1200)
        self.assertEqual(MathConfig.compile_quote(t1, t1, "ai")["duration_seconds"], 10800)

    def test_compile_quote_and_execution(self):
        quote = Player.compile(self.tx, self.actor, method="unskilled", atk=5, confirm=False)
        self.assertTrue(quote.get("compile_quote"))
        self.assertEqual(quote["atk_yield"], 5)
        self.assertEqual(quote["rtm_paid"], Decimal("0.00100"))
        bits = 2 * MathConfig.get_module_stat("attack", 1) + MathConfig.get_module_stat("attack", 5)
        expected_duration = MathConfig.compile_quote(bits, 5, "unskilled")["duration_seconds"]
        self.assertEqual(quote["duration_seconds"], expected_duration)

        before_rtm = Decimal(str(self.tx.players[self.actor]["rootium"]))
        started = Player.compile(self.tx, self.actor, method="unskilled", atk=5, confirm=True)
        self.assertTrue(started.get("compile_started"))
        self.assertEqual(self.tx.players[self.actor]["rootium"], before_rtm - Decimal("0.00100"))
        self.assertEqual(self.tx.players[self.actor]["attack_t1"], 2)
        self.assertEqual(self.tx.players[self.actor]["attack_t5"], 1)
        self.assertEqual(self.tx.players[self.actor]["attack_points"], 0)
        self.assertEqual(len(self.tx.hacks), 1)
        self.assertEqual(self.tx.hacks[0]["atk_yield"], 5)
        self.assertEqual(self.tx.hacks[0]["method"], "unskilled")
        self.assertEqual(self.tx.hacks[0]["bits_per_s"], bits)

        net = Player.network(self.tx, self.actor)
        self.assertIn("pending_hack", net)
        self.assertEqual(net["pending_hack"]["atk_yield"], 5)

    def test_compile_in_progress_and_errors(self):
        with self.assertRaises(GameError) as cm:
            Player.compile(self.tx, 9090, method="unskilled", atk=1, confirm=False)
        self.assertEqual(cm.exception.key, "no_network")

        Player.network(self.tx, 9090)
        with self.assertRaises(GameError) as cm:
            Player.compile(self.tx, 9090, method="unskilled", atk=1, confirm=False)
        self.assertEqual(cm.exception.key, "no_attack_modules")

        with self.assertRaises(GameError) as cm:
            Player.compile(self.tx, self.actor, method="nope", atk=1, confirm=False)
        self.assertEqual(cm.exception.key, "invalid_selection")

        with self.assertRaises(GameError) as cm:
            Player.compile(self.tx, self.actor, method="skilled", atk=0, confirm=False)
        self.assertEqual(cm.exception.key, "invalid_selection")

        bits = 2 * MathConfig.get_module_stat("attack", 1) + MathConfig.get_module_stat("attack", 5)
        with self.assertRaises(GameError) as cm:
            Player.compile(self.tx, self.actor, method="skilled", atk=bits + 1, confirm=False)
        self.assertEqual(cm.exception.key, "compile_max_exceeded")
        self.assertEqual(cm.exception.values.get("max_atk"), bits)

        self.tx.players[self.actor]["rootium"] = Decimal("0.00000")
        with self.assertRaises(GameError) as cm:
            Player.compile(self.tx, self.actor, method="skilled", atk=5, confirm=True)
        self.assertEqual(cm.exception.key, "insufficient_funds_rtm")

        self.tx.players[self.actor]["rootium"] = Decimal("1.00000")
        Player.compile(self.tx, self.actor, method="ai", atk="all", confirm=True)
        with self.assertRaises(GameError) as cm:
            Player.compile(self.tx, self.actor, method="unskilled", atk=1, confirm=False)
        self.assertEqual(cm.exception.key, "compile_in_progress")

    def test_quote_changed_and_all_alias(self):
        bits = 2 * MathConfig.get_module_stat("attack", 1) + MathConfig.get_module_stat("attack", 5)
        quote = Player.compile(self.tx, self.actor, method="skilled", all=True, confirm=False)
        self.assertEqual(quote["atk_yield"], bits)
        with self.assertRaises(GameError) as cm:
            Player.compile(
                self.tx, self.actor, method="skilled", atk=bits, confirm=True,
                quoted_rtm="0.00100",
            )
        self.assertEqual(cm.exception.key, "quote_changed")
        with self.assertRaises(GameError) as cm:
            Player.compile(
                self.tx, self.actor, method="skilled", atk=bits, confirm=True,
                quoted_rtm=str(quote["rtm_paid"]), quoted_atk=1,
            )
        self.assertEqual(cm.exception.key, "quote_changed")
        started = Player.compile(
            self.tx, self.actor, method="skilled", atk="tout", confirm=True,
            quoted_rtm=str(quote["rtm_paid"]), quoted_atk=quote["atk_yield"],
        )
        self.assertTrue(started.get("compile_started"))
        self.assertEqual(started["atk_yield"], quote["atk_yield"])

    def test_delivery_credits_attack_points(self):
        Player.compile(self.tx, self.actor, method="unskilled", atk=5, confirm=True)
        self.assertEqual(len(self.tx.hacks), 1)
        self.tx.hacks[0]["expires_at"] = self.tx.now
        delivered = HackDB.complete_and_delete_expired(self.tx)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(self.tx.hacks, [])
        self.assertEqual(self.tx.players[self.actor]["attack_points"], 5)
        self.assertEqual(self.tx.players[self.actor]["attack_t5"], 1)
        self.assertIn("player:8080", self.tx.acquired_locks)
        self.assertEqual(HackDB.complete_and_delete_expired(self.tx), [])

    def test_compile_i18n_keys(self):
        for key in (
            "g_compile_quote", "g_compile_started", "g_compile_delivered_dm",
            "g_compile_method_unskilled", "g_compile_method_skilled", "g_compile_method_ai",
            "g_net_atk", "g_net_atk_stock", "g_net_hack_progress",
            "g_error_compile_usage", "g_error_compile_in_progress",
            "g_error_no_attack_modules",
        ):
            self.assertIn(key, game_fr.text)
            self.assertIn(key, game_en.text)


class TestCompileDeliveryLock(unittest.IsolatedAsyncioTestCase):
    """RootService.deliver_expired_hacks acquiert le verrou hack."""

    async def test_deliver_hacks_lock(self):
        from game.root_service import RootService
        mock_db = MockDatabase()
        service = RootService(database=mock_db)
        delivered = await service.deliver_expired_hacks()
        self.assertEqual(delivered, [])
        self.assertIn("hack", mock_db.acquired_locks)
        self.assertIn("hack", mock_db.released_locks)
        self.assertIn("compile", RootService.ACTIONS)
        self.assertIn("hack", RootService.ACTIONS)


class TestCompileDeliveryNotification(unittest.IsolatedAsyncioTestCase):
    """Résilience du MP de fin de compile (rattrapage au démarrage inclus)."""

    def _make_cog(self):
        import discord
        from commands.game.compile import Compile
        db = MockDatabase()
        db.players[8080] = {
            "discord_id": 8080, "dollars": Decimal("0"), "rootium": Decimal("0"),
            "attack_points": 0, "lang": None,
        }
        from game.root_service import RootService
        bot = MagicMock()
        bot.root_service = RootService(database=db)
        cog = object.__new__(Compile)
        cog.bot = bot
        return cog, bot

    async def test_dm_uses_fetch_user_when_cache_cold(self):
        """Au démarrage le cache est froid : get_user=None doit basculer sur fetch_user."""
        cog, bot = self._make_cog()
        user = MagicMock()
        user.send = AsyncMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(return_value=user)
        await cog._notify_delivered({"discord_id": 8080, "atk_yield": 5})
        bot.fetch_user.assert_awaited_once()
        user.send.assert_awaited_once()

    async def test_dm_retries_transient_http_error(self):
        """Une HTTPException transitoire est rejouée puis finit par réussir."""
        import discord
        cog, bot = self._make_cog()
        user = MagicMock()
        user.send = AsyncMock(side_effect=[discord.HTTPException(MagicMock(), "429"), None])
        bot.get_user = MagicMock(return_value=user)
        bot.fetch_user = AsyncMock(return_value=user)
        with patch("commands.game.compile.asyncio.sleep", new=AsyncMock()):
            await cog._notify_delivered({"discord_id": 8080, "atk_yield": 5})
        self.assertEqual(user.send.await_count, 2)

    async def test_dm_forbidden_is_not_retried(self):
        """Un Forbidden (MP fermés) ne doit pas être rejoué."""
        import discord
        cog, bot = self._make_cog()
        user = MagicMock()
        user.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "dm closed"))
        bot.get_user = MagicMock(return_value=user)
        bot.fetch_user = AsyncMock(return_value=user)
        with patch("commands.game.compile.asyncio.sleep", new=AsyncMock()) as slept:
            await cog._notify_delivered({"discord_id": 8080, "atk_yield": 5})
        self.assertEqual(user.send.await_count, 1)
        slept.assert_not_awaited()


class TestSecretIdRotationLock(unittest.IsolatedAsyncioTestCase):
    """RootService.rotate_secret_ids_if_due acquiert le verrou secret_rotation."""

    async def test_rotate_lock_secret_rotation(self):
        from game.root_service import RootService
        mock_db = MockDatabase()
        service = RootService(database=mock_db)
        result = await service.rotate_secret_ids_if_due()
        self.assertIn("rotated", result)
        self.assertIn("secret_rotation", mock_db.acquired_locks)
        self.assertIn("secret_rotation", mock_db.released_locks)
        self.assertIn("hack", RootService.ACTIONS)
        self.assertNotIn("secret", RootService.ACTIONS)


if __name__ == "__main__":
    unittest.main(verbosity=2)

