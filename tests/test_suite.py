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



# Imports additionnels pour les modules spécialisés
from decimal import Decimal as D
from utils.text import format_usd
import tempfile
import discord
from decimal import Decimal as D
import tempfile
import time
import utils.check
from utils.language_manager import _cache
from game.root_service import RootService
from game.db.consequence import ConsequenceDB
from game.db.pvp import PvpDB
from commands.game.hack import Hack
from commands.game.buy import Buy, _get_shop_options, _get_purchasable_options, ShopCatalogView
from commands.game.network import Network, NetworkActionView
from utils.presence_manager import (
    get_presence_activity,
    get_presence_text,
    update_bot_presence,
)
from commands.admin.claim_moderation import ClaimModeration
from game.db.daily_claim_stats import DailyClaimStatsDB
from utils.claim_analysis import calculate_player_claim_metrics, extract_claim_intervals
from game.db.economy_stats import EconomyStatsDB, _PERIODS
from tools.simulate_balance import DAY, PROFILES, STRESS_PROFILE, Profile, Simulation, aggregate, price



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
        self.pvp_attacks = []
        self.consequences = []
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

        if "FROM HACK WHERE DISCORD_ID" in q:
            uid = int(params[0])
            htype = str(params[1]) if len(params) > 1 else "compile"
            for row in self.hacks:
                if row["discord_id"] == uid and row.get("type", "compile") == htype:
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

        if "SELECT * FROM PVP_ATTACKS WHERE ID =" in q:
            aid = int(params[0])
            for a in self.pvp_attacks:
                if a["id"] == aid:
                    return dict(a)
            return None

        if "SELECT * FROM PVP_ATTACKS WHERE VICTIM_ID =" in q:
            vid = int(params[0])
            for a in self.pvp_attacks:
                if a["victim_id"] == vid:
                    return dict(a)
            return None

        if "FROM CONSEQUENCE WHERE VICTIM_ID =" in q or "SELECT 1 FROM CONSEQUENCE" in q:
            vid, aid, now_val = int(params[0]), int(params[1]), params[2]
            for c in self.consequences:
                if c["victim_id"] == vid and c["attacker_id"] == aid and c["delete_at"] > now_val:
                    return {"1": 1}
            return None

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

        if "SELECT * FROM PVP_ATTACKS WHERE ATTACKER_ID =" in q:
            aid = int(params[0])
            return [dict(a) for a in self.pvp_attacks if a["attacker_id"] == aid]

        if "SELECT ID FROM PVP_ATTACKS WHERE RESOLVES_AT <=" in q:
            cutoff = params[0]
            return [{"id": a["id"]} for a in self.pvp_attacks if a["resolves_at"] <= cutoff]

        if "FROM CONSEQUENCE WHERE DELETE_AT <=" in q or "SELECT ID FROM CONSEQUENCE" in q:
            cutoff = params[0]
            return [{"id": c["id"]} for c in self.consequences if c["delete_at"] <= cutoff]

        if "FROM PLAYERS WHERE AUTOCLAIM_ACTIVE > 0" in q:
            return [dict(p) for p in self.players.values() if int(p.get("autoclaim_active", 0) or 0) > 0]

        if "SELECT SECRET_ID FROM PLAYERS WHERE SECRET_ID IS NOT NULL" in q:
            return [{"secret_id": p.get("secret_id")} for p in self.players.values() if p.get("secret_id")]

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
                "is_auto": bool(params[4]) if len(params) > 4 else False,
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

        if "INSERT INTO PVP_ATTACKS" in q:
            attacker_id, victim_id, attack_points, target = int(params[0]), int(params[1]), int(params[2]), str(params[3])
            started_at, resolves_at = params[4], params[5]
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

        if "DELETE FROM PVP_ATTACKS WHERE ID =" in q:
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

        if "DELETE FROM CONSEQUENCE" in q:
            if "WHERE DELETE_AT <=" in q:
                cutoff = params[0]
                before = len(self.consequences)
                self.consequences = [c for c in self.consequences if c["delete_at"] > cutoff]
                return before - len(self.consequences)
            cid = int(params[0])
            self.consequences = [c for c in self.consequences if c["id"] != cid]
            return 1

        if "INSERT INTO HACK" in q:
            hack_id = len(self.hacks) + 1
            if "'SCAN'" in q:
                self.hacks.append({
                    "id": hack_id,
                    "discord_id": int(params[0]),
                    "type": "scan",
                    "target_id": int(params[1]),
                    "method": "scan",
                    "bits_per_s": 0,
                    "atk_yield": 0,
                    "rtm_paid": params[2],
                    "boost_rtm": params[3],
                    "started_at": params[4],
                    "expires_at": params[5],
                })
            else:
                self.hacks.append({
                    "id": hack_id,
                    "discord_id": int(params[0]),
                    "type": "compile",
                    "target_id": None,
                    "method": params[1],
                    "bits_per_s": int(params[2]),
                    "atk_yield": int(params[3]),
                    "rtm_paid": params[4],
                    "boost_rtm": Decimal("0.00000"),
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
        self.pvp_attacks = []
        self.consequences = []
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
            tx.pvp_attacks = self.pvp_attacks
            tx.consequences = self.consequences
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
            tx.pvp_attacks = copy.deepcopy(self.pvp_attacks)
            tx.consequences = copy.deepcopy(self.consequences)
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
                self.pvp_attacks = tx.pvp_attacks
                self.consequences = tx.consequences
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


# ============================================================================
# SECTIONS FUSIONNÉES : PvP (Scan, Hack), Bêta, QoL, Claims, Économie, Simulation
# ============================================================================

# ── 1. PvP : Scan & Hack ───────────────────────────────────────────────────

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

# ── 2. Bêta Launch & Réputation ────────────────────────────────────────────

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

class TestBotPresence(unittest.IsolatedAsyncioTestCase):
    """Vérifie la gestion de la présence Discord et du statut de maintenance."""

    def test_get_presence_text_from_env(self):
        """Vérifie que la présence est récupérée depuis BOT_PRESENCE dans l'environnement."""
        with patch.dict(os.environ, {"BOT_PRESENCE": "Root Bot Beta"}):
            self.assertEqual(get_presence_text(), "Root Bot Beta")

        with patch.dict(os.environ, {"BOT_PRESENCE": "Custom Presence"}):
            self.assertEqual(get_presence_text(), "Custom Presence")

        with patch.dict(os.environ, {"BOT_PRESENCE": ""}):
            with patch("utils.check.Check.beta_enabled", return_value=False):
                self.assertEqual(get_presence_text(), data.BOT_NAME)

    def test_get_presence_activity_type(self):
        """Vérifie que get_presence_activity configure correctement l'activité avec le texte de présence."""
        with patch.dict(os.environ, {"BOT_PRESENCE": "Root Bot Beta"}):
            act = get_presence_activity()
            self.assertIsInstance(act, discord.CustomActivity)
            self.assertEqual(act.name, "Root Bot Beta")

    async def test_update_bot_presence_status_and_activity(self):
        """Vérifie que update_bot_presence respecte le mode maintenance et applique l'activité."""
        mock_bot = MagicMock()
        mock_bot.change_presence = AsyncMock()

        with patch.dict(os.environ, {"BOT_PRESENCE": "Root Bot Beta"}):
            # 1. Hors maintenance -> Status.online
            with patch("utils.check.Check.maintenance_enabled", return_value=False):
                await update_bot_presence(mock_bot)
                mock_bot.change_presence.assert_called_once()
                call_kwargs = mock_bot.change_presence.call_args[1]
                self.assertEqual(call_kwargs["status"], discord.Status.online)
                self.assertEqual(call_kwargs["activity"].name, "Root Bot Beta")

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
                self.assertEqual(call_kwargs["activity"].name, "Root Bot Beta")


# ── 3. Améliorations QoL & Interface ───────────────────────────────────────

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

    async def test_botinfo_embed_contains_invite_and_server_url(self):
        from commands.utility.botinfo import BotInfo
        from data import INVITE_URL, OFFICIAL_SERVER_URL
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
        has_server = any(OFFICIAL_SERVER_URL in val for val in field_values)
        self.assertTrue(has_server, f"L'URL du serveur officiel {OFFICIAL_SERVER_URL} doit être présente dans les champs de l'embed")

        view = kwargs.get("view")
        self.assertIsNotNone(view)
        button_urls = [btn.url for btn in view.children if hasattr(btn, "url")]
        self.assertIn(INVITE_URL, button_urls)
        self.assertIn(OFFICIAL_SERVER_URL, button_urls)


class TestDecodeWinLogKwargs(unittest.IsolatedAsyncioTestCase):
    """Vérifie que la victoire au mini-jeu Decode contient la séquence et s'enregistre sans KeyError."""

    def test_decode_win_contains_sequence_and_resolves_log_kwargs(self):
        from commands.game.game_config import GAMES
        from game.base_challenge_manager import SingleTargetChallengeManager

        settlement = {
            "final_reward": Decimal("2.50"),
            "base_reward": Decimal("2.50"),
            "multiplier": Decimal("1.0"),
            "next_at": None,
            "server_name": "TestServer",
        }
        challenge = {
            "target": "TEST",
            "sequence": ["A1", "B2", "C3", "D4"],
            "sequence_str": "A1 · B2 · C3 · D4",
        }
        won_result = SingleTargetChallengeManager._format_won(settlement, challenge, actor=12345)
        self.assertIn("sequence", won_result)
        self.assertEqual(won_result["sequence"], "A1 · B2 · C3 · D4")

        # Vérifier que log_kwargs de GAMES["decode"] résout sans KeyError
        decode_config = GAMES["decode"]
        kwargs = decode_config.log_kwargs(won_result)
        self.assertEqual(kwargs["sequence"], "A1 · B2 · C3 · D4")
        self.assertEqual(kwargs["target"], "TEST")

# ── 4. Récoltes & Modération des Claims ────────────────────────────────────

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

# ── 5. Suivi Économique & Rapports ─────────────────────────────────────────

class MockTx:
    """
    Simule une Transaction MySQL en mémoire pour les tests economy_stats.
    Stocke economy_hourly en dict{(bucket, player_id): row}.
    Stocke economy_reports en dict{period_hours: row}.
    """

    def __init__(self, now=None):
        self.now = now or datetime(2026, 9, 21, 14, 30, 0)
        self.economy_hourly: dict[tuple, dict] = {}
        self.economy_reports: dict[int, dict] = {}
        self.event_availability_logs: list[dict] = []
        self.events: dict[str, dict] = {}
        self.tables_exist = True  # simule information_schema
        self.acquired_locks = []
        self._queries = []

    def acquire_lock(self, name: str, timeout: int = 10) -> None:
        if name not in self.acquired_locks:
            self.acquired_locks.append(name)

    def one(self, sql: str, args=()):
        self._queries.append((sql, args))
        q = ' '.join(sql.split()).upper()

        # information_schema check
        if 'INFORMATION_SCHEMA' in q and 'COUNT(*)' in q:
            table_name = args[0] if args else ''
            if self.tables_exist:
                return {'cnt': 1}
            return {'cnt': 0}

        # economy_reports SELECT * ... WHERE period_hours
        if 'FROM ECONOMY_REPORTS WHERE PERIOD_HOURS' in q:
            period = args[0]
            row = self.economy_reports.get(period)
            return dict(row) if row else None

        # events SELECT * ... WHERE event = %s
        if 'FROM EVENTS WHERE EVENT' in q:
            ev = args[0]
            row = self.events.get(ev)
            return dict(row) if row else None

        # economy_hourly EXISTS (returning check)
        if 'FROM ECONOMY_HOURLY' in q and 'WHERE PLAYER_ID' in q and 'BUCKET_START <' in q:
            player_id = args[0]
            bucket_limit = args[1]
            for (b, pid), row in self.economy_hourly.items():
                if pid == player_id and b < bucket_limit:
                    return {'1': 1}
            return None

        # Previous period retention query
        if 'PREV_ACTIVE_PLAYERS' in q:
            prev_start, p_end, curr_start, curr_end = args
            prev_pids = {pid for (b, pid) in self.economy_hourly if prev_start <= b < p_end}
            curr_pids = {pid for (b, pid) in self.economy_hourly if curr_start <= b < curr_end}
            retained = prev_pids & curr_pids
            return {
                'prev_active_players': len(prev_pids),
                'retained_players': len(retained),
            }

        # economy_hourly aggregate
        if 'FROM ECONOMY_HOURLY' in q and 'COUNT(DISTINCT' in q:
            start, end = args
            matching = {
                (b, pid): row
                for (b, pid), row in self.economy_hourly.items()
                if start <= b < end
            }
            if not matching:
                return None
            result = {'active_players': len({pid for (_, pid) in matching})}
            # Agréger toutes les colonnes numériques
            all_cols = set()
            for row in matching.values():
                all_cols.update(row.keys())
            for col in all_cols:
                if col in ('bucket_start', 'player_id'):
                    continue
                total = sum(
                    (row.get(col) or 0) for row in matching.values()
                )
                result[col] = total
            return result

        return None

    def all(self, sql: str, args=()):
        self._queries.append((sql, args))
        q = ' '.join(sql.split()).upper()

        if 'FROM ECONOMY_REPORTS ORDER BY PERIOD_HOURS' in q:
            return sorted(self.economy_reports.values(), key=lambda r: r['period_hours'])

        if 'FROM EVENT_AVAILABILITY_LOGS' in q:
            start, end = args
            matching = [
                log for log in self.event_availability_logs
                if start <= log['solved_at'] < end
            ]
            by_event = {}
            for m in matching:
                ev = m['event']
                if ev not in by_event:
                    by_event[ev] = {'event': ev, 'wins': 0, 'total_seconds': 0}
                by_event[ev]['wins'] += 1
                by_event[ev]['total_seconds'] += m['duration_seconds']
            rows = []
            for ev, edata in by_event.items():
                avg = edata['total_seconds'] / edata['wins'] if edata['wins'] else 0
                rows.append({
                    'event': ev,
                    'wins': edata['wins'],
                    'total_seconds': edata['total_seconds'],
                    'avg_seconds': avg,
                })
            return rows

        return []

    def execute(self, sql: str, args=()):
        self._queries.append((sql, args))
        q = ' '.join(sql.split()).upper()

        if 'CREATE TABLE IF NOT EXISTS' in q:
            return 0

        # INSERT INTO event_availability_logs
        if 'INSERT INTO EVENT_AVAILABILITY_LOGS' in q:
            self.event_availability_logs.append({
                'event': args[0],
                'opened_at': args[1],
                'solved_at': args[2],
                'duration_seconds': args[3],
                'winner_id': args[4],
                'reward': args[5],
            })
            return 1

        # INSERT INTO events ... ON DUPLICATE KEY UPDATE
        if 'INSERT INTO EVENTS' in q:
            ev = args[0]
            self.events[ev] = {
                'event': args[0],
                'next_at': args[1],
                'last_found_by': args[2],
                'last_found_on': args[3],
                'last_reward': args[4],
            }
            return 1

        # INSERT INTO economy_reports
        if 'INSERT INTO ECONOMY_REPORTS' in q:
            period_hours = args[0]
            self.economy_reports[period_hours] = {
                'period_hours': period_hours,
                'tracking_start': args[1],
                'next_start': args[2],
                'pending_end': None,
                'pending_payload': None,
                'pending_channel_id': None,
                'last_message_id': None,
                'last_sent_at': None,
            }
            return 1

        # INSERT INTO economy_hourly
        if 'INSERT INTO ECONOMY_HOURLY' in q and 'ON DUPLICATE KEY UPDATE' in q:
            self._apply_hourly_upsert(sql, args)
            return 1

        if 'INSERT IGNORE INTO ECONOMY_HOURLY' in q:
            self._apply_hourly_ignore(sql, args)
            return 1

        # UPDATE economy_reports SET next_start (ack)
        if 'UPDATE ECONOMY_REPORTS' in q and 'SET NEXT_START' in q:
            period = args[-1]
            row = self.economy_reports.get(period)
            if row:
                row['next_start'] = args[0]
                row['pending_end'] = None
                row['pending_payload'] = None
                row['pending_channel_id'] = None
                row['last_message_id'] = args[1]
            return 1

        # UPDATE economy_reports SET pending_end (prepare)
        if 'UPDATE ECONOMY_REPORTS' in q and 'SET PENDING_END' in q:
            period = args[-1]
            row = self.economy_reports.get(period)
            if row:
                row['pending_end'] = args[0]
                row['pending_payload'] = args[1]
                row['pending_channel_id'] = args[2]
            return 1

        return 0

    def _parse_insert_cols_vals(self, sql: str, args) -> tuple[list[str], list]:
        """Extrait les colonnes et valeurs d'un INSERT INTO economy_hourly."""
        import re
        m = re.search(r'INSERT\s+(?:IGNORE\s+)?INTO\s+economy_hourly\s*\(([^)]+)\)', sql, re.IGNORECASE)
        if not m:
            return [], []
        cols = [c.strip() for c in m.group(1).split(',')]
        n_insert = cols.count('bucket_start') and len(cols)
        vals = list(args[:len(cols)])
        return cols, vals

    def _apply_hourly_upsert(self, sql: str, args):
        import re
        # Colonnes insert
        m_cols = re.search(r'INSERT INTO economy_hourly\s*\(([^)]+)\)', sql, re.IGNORECASE)
        if not m_cols:
            return
        cols = [c.strip() for c in m_cols.group(1).split(',')]
        n = len(cols)
        insert_vals = list(args[:n])
        update_vals = list(args[n:])

        bucket = insert_vals[cols.index('bucket_start')]
        pid = insert_vals[cols.index('player_id')]
        key = (bucket, pid)

        if key not in self.economy_hourly:
            row = {'bucket_start': bucket, 'player_id': pid}
            for col, val in zip(cols, insert_vals):
                if col not in ('bucket_start', 'player_id'):
                    row[col] = val
            self.economy_hourly[key] = row
        else:
            row = self.economy_hourly[key]
            # Extraire les colonnes de update
            m_upd = re.findall(r'(\w+)\s*=\s*\w+\s*\+\s*%s', sql, re.IGNORECASE)
            for col, val in zip(m_upd, update_vals):
                col_lower = col.lower()
                current = row.get(col_lower, 0) or 0
                row[col_lower] = (Decimal(str(current)) + Decimal(str(val or 0)))

    def _apply_hourly_ignore(self, sql: str, args):
        import re
        m_cols = re.search(r'INSERT IGNORE INTO economy_hourly\s*\(([^)]+)\)', sql, re.IGNORECASE)
        if not m_cols:
            return
        cols = [c.strip() for c in m_cols.group(1).split(',')]
        insert_vals = list(args[:len(cols)])
        bucket = insert_vals[cols.index('bucket_start')]
        pid = insert_vals[cols.index('player_id')]
        key = (bucket, pid)
        if key not in self.economy_hourly:
            row = {'bucket_start': bucket, 'player_id': pid}
            for col, val in zip(cols, insert_vals):
                if col not in ('bucket_start', 'player_id'):
                    row[col] = val
            self.economy_hourly[key] = row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _d(val) -> Decimal:
    return Decimal(str(val))

BUCKET_14H = datetime(2026, 9, 21, 14, 0, 0)
BUCKET_15H = datetime(2026, 9, 21, 15, 0, 0)
BUCKET_16H = datetime(2026, 9, 21, 16, 0, 0)


# ---------------------------------------------------------------------------
# Tests build_increments (aucun SQL)
# ---------------------------------------------------------------------------

class TestBuildIncrements(unittest.TestCase):

    def test_claim_normal(self):
        result = {'claimed': True, 'amount': _d('0.00250'), 'ram_was_full': False}
        inc = EconomyStatsDB.build_increments('claim', 123, result)
        self.assertEqual(inc, {123: {'claims': 1, 'mining_rtm': _d('0.00250')}})

    def test_claim_full(self):
        result = {'claimed': True, 'amount': _d('0.00100'), 'ram_was_full': True}
        inc = EconomyStatsDB.build_increments('claim', 123, result)
        self.assertIn('full_claims', inc[123])
        self.assertEqual(inc[123]['full_claims'], 1)
        self.assertEqual(inc[123]['claims'], 1)

    def test_two_claims_aggregation(self):
        """Deux claims successifs : 2 claims, somme des RTM, 50% full."""
        tx = MockTx()
        r1 = {'claimed': True, 'amount': _d('0.00250'), 'ram_was_full': True}
        r2 = {'claimed': True, 'amount': _d('0.00100'), 'ram_was_full': False}
        inc1 = EconomyStatsDB.build_increments('claim', 123, r1)
        inc2 = EconomyStatsDB.build_increments('claim', 123, r2)
        EconomyStatsDB.add(tx, BUCKET_14H, inc1)
        EconomyStatsDB.add(tx, BUCKET_14H, inc2)
        row = tx.economy_hourly.get((BUCKET_14H, 123))
        self.assertEqual(int(row['claims']), 2)
        self.assertEqual(_d(row['full_claims']), _d(1))
        self.assertEqual(_d(row['mining_rtm']), _d('0.00350'))

    def test_claim_refused(self):
        result = {'claimed': False, 'reason': 'empty', 'amount': _d('0')}
        inc = EconomyStatsDB.build_increments('claim', 123, result)
        self.assertEqual(inc, {})

    def test_network_new(self):
        result = {'is_new': True, 'dollars': _d('5000')}
        inc = EconomyStatsDB.build_increments('network', 456, result)
        self.assertEqual(inc, {456: {'new_players': 1, 'grant_usd': _d('5000')}})

    def test_network_existing(self):
        result = {'is_new': False, 'dollars': _d('5000')}
        inc = EconomyStatsDB.build_increments('network', 456, result)
        self.assertEqual(inc, {})

    def test_event_hash_win(self):
        result = {'status': 'won', 'reward': _d('1200'), 'winner': 789}
        inc = EconomyStatsDB.build_increments('hash', 789, result)
        self.assertEqual(inc, {789: {'event_hash_usd': _d('1200')}})

    def test_event_packet_win(self):
        result = {'status': 'won', 'reward': _d('800'), 'winner': 789}
        inc = EconomyStatsDB.build_increments('packet', 789, result)
        self.assertIn('event_packet_usd', inc[789])
        self.assertNotIn('event_hash_usd', inc[789])

    def test_event_loss(self):
        result = {'status': 'lost', 'reward': _d('0'), 'winner': None}
        inc = EconomyStatsDB.build_increments('hash', 123, result)
        self.assertEqual(inc, {})

    def test_buy_mining_t2(self):
        result = {'bought': True, 'kind': 'mining', 'tier': 2, 'usd_price': _d('200'), 'rtm_price': _d('0')}
        inc = EconomyStatsDB.build_increments('buy', 123, result)
        self.assertIn('miners_t2', inc[123])
        self.assertEqual(inc[123]['miners_t2'], 1)
        self.assertEqual(inc[123]['miners_usd'], _d('200'))

    def test_buy_attack(self):
        result = {'bought': True, 'kind': 'attack', 'tier': 1, 'usd_price': _d('0'), 'rtm_price': _d('0.01')}
        inc = EconomyStatsDB.build_increments('buy', 123, result)
        self.assertEqual(inc[123]['attack_bought'], 1)

    def test_buy_quote_not_counted(self):
        result = {'quote': True, 'buy_quote': True, 'bought': False}
        inc = EconomyStatsDB.build_increments('buy', 123, result)
        self.assertEqual(inc, {})

    def test_upgrade_started(self):
        result = {'upgrade_started': True, 'usd_price': _d('500')}
        inc = EconomyStatsDB.build_increments('upgrade', 123, result)
        self.assertEqual(inc[123]['upgrades_started'], 1)
        self.assertEqual(inc[123]['upgrades_usd'], _d('500'))

    def test_compile_started(self):
        result = {'compile_started': True, 'rtm_paid': _d('0.02')}
        inc = EconomyStatsDB.build_increments('compile', 123, result)
        self.assertEqual(inc[123]['compile_rtm'], _d('0.02'))

    def test_scan_started_with_boost(self):
        result = {'scan_started': True, 'rtm_total': _d('0.015')}
        inc = EconomyStatsDB.build_increments('scan', 123, result)
        self.assertEqual(inc[123]['scan_rtm'], _d('0.015'))

    def test_convert(self):
        result = {'converted': True, 'rtm_amount': _d('0.05'), 'usd_amount': _d('2178.35')}
        inc = EconomyStatsDB.build_increments('convert', 123, result)
        self.assertEqual(inc[123]['conversions'], 1)
        self.assertEqual(inc[123]['converted_rtm'], _d('0.05'))
        self.assertEqual(inc[123]['converted_usd'], _d('2178.35'))

    def test_trade(self):
        result = {'trade_completed': True, 'initiator': 123, 'target': 456}
        inc = EconomyStatsDB.build_increments('trade', 123, result)
        self.assertEqual(inc[123]['trades'], 1)
        self.assertIn(456, inc)
        self.assertEqual(inc[456], {})

    def test_unknown_method(self):
        inc = EconomyStatsDB.build_increments('top', 123, {'ranking': []})
        self.assertEqual(inc, {})


# ---------------------------------------------------------------------------
# Tests add() — SQL atomique et returning_players
# ---------------------------------------------------------------------------

class TestAdd(unittest.TestCase):

    def test_first_time_player_not_returning(self):
        tx = MockTx()
        inc = {123: {'claims': 1, 'mining_rtm': _d('0.00250')}}
        EconomyStatsDB.add(tx, BUCKET_14H, inc)
        row = tx.economy_hourly.get((BUCKET_14H, 123))
        self.assertIsNotNone(row)
        # Pas de returning_players car aucune ligne antérieure
        self.assertEqual(int(row.get('returning_players', 0)), 0)

    def test_returning_player_flag(self):
        tx = MockTx()
        # Ligne dans une heure précédente
        tx.economy_hourly[(BUCKET_14H, 123)] = {'bucket_start': BUCKET_14H, 'player_id': 123}
        # Nouvelle heure → doit être marqué returning
        inc = {123: {'claims': 1}}
        EconomyStatsDB.add(tx, BUCKET_15H, inc)
        row = tx.economy_hourly.get((BUCKET_15H, 123))
        self.assertIsNotNone(row)
        self.assertEqual(int(row.get('returning_players', 0)), 1)

    def test_returning_not_updated_on_duplicate(self):
        """Si la ligne existe déjà dans le même bucket, returning_players ne change pas."""
        tx = MockTx()
        # Ligne antérieure → marque returning
        tx.economy_hourly[(BUCKET_14H, 123)] = {'bucket_start': BUCKET_14H, 'player_id': 123}
        inc = {123: {'claims': 1}}
        EconomyStatsDB.add(tx, BUCKET_15H, inc)
        # Deuxième add dans le même bucket → ON DUPLICATE KEY UPDATE, returning ne doit pas changer
        inc2 = {123: {'claims': 1}}
        EconomyStatsDB.add(tx, BUCKET_15H, inc2)
        row = tx.economy_hourly.get((BUCKET_15H, 123))
        # returning_players reste à 1, pas 2
        self.assertEqual(int(row.get('returning_players', 0)), 1)

    def test_trade_target_empty_dict_creates_row(self):
        tx = MockTx()
        inc = {123: {'trades': 1}, 456: {}}
        EconomyStatsDB.add(tx, BUCKET_14H, inc)
        self.assertIn((BUCKET_14H, 456), tx.economy_hourly)

    def test_ordered_by_player_id(self):
        """Les joueurs sont traités par ID croissant (anti-deadlock)."""
        tx = MockTx()
        processed_order = []
        original_add = EconomyStatsDB.add.__func__ if hasattr(EconomyStatsDB.add, '__func__') else None

        inc = {999: {'trades': 1}, 111: {}}
        EconomyStatsDB.add(tx, BUCKET_14H, inc)
        keys = list(tx.economy_hourly.keys())
        pids = [k[1] for k in keys]
        # 111 doit être créé avant 999
        self.assertLess(pids.index(111), pids.index(999))


# ---------------------------------------------------------------------------
# Tests aggregate()
# ---------------------------------------------------------------------------

class TestAggregate(unittest.TestCase):

    def test_empty_period(self):
        tx = MockTx()
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        self.assertEqual(result['active_players'], 0)
        self.assertEqual(result['claims'], 0)

    def test_distinct_players(self):
        """Un même joueur sur 3 heures compte une fois dans active_players."""
        tx = MockTx()
        for bucket in (BUCKET_14H, BUCKET_15H, BUCKET_16H):
            tx.economy_hourly[(bucket, 123)] = {
                'bucket_start': bucket, 'player_id': 123,
                'claims': 1, 'mining_rtm': _d('0.001'),
            }
        # Active player sur 3 heures
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_16H + timedelta(hours=1))
        self.assertEqual(result['active_players'], 1)

    def test_returning_players_sum(self):
        """returning_players est une somme directe des flags, pas COUNT DISTINCT."""
        tx = MockTx()
        tx.economy_hourly[(BUCKET_14H, 123)] = {
            'bucket_start': BUCKET_14H, 'player_id': 123,
            'returning_players': 0, 'claims': 1,
        }
        tx.economy_hourly[(BUCKET_15H, 123)] = {
            'bucket_start': BUCKET_15H, 'player_id': 123,
            'returning_players': 1, 'claims': 2,
        }
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_16H)
        self.assertEqual(result['active_players'], 1)
        self.assertEqual(int(result.get('returning_players', 0)), 1)

    def test_period_boundaries(self):
        """Action à 14h59 → bucket 14h ; action à 15h → bucket 15h."""
        tx = MockTx()
        tx.economy_hourly[(BUCKET_14H, 123)] = {
            'bucket_start': BUCKET_14H, 'player_id': 123, 'claims': 5,
        }
        tx.economy_hourly[(BUCKET_15H, 123)] = {
            'bucket_start': BUCKET_15H, 'player_id': 123, 'claims': 3,
        }
        # Période [14h, 15h) → inclut 14h, exclut 15h
        result_14 = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        self.assertEqual(int(result_14.get('claims', 0)), 5)
        # Période [15h, 16h)
        result_15 = EconomyStatsDB.aggregate(tx, BUCKET_15H, BUCKET_16H)
        self.assertEqual(int(result_15.get('claims', 0)), 3)

    def test_mini_games_separate_columns(self):
        """hash et packet ont des colonnes distinctes."""
        tx = MockTx()
        tx.economy_hourly[(BUCKET_14H, 123)] = {
            'bucket_start': BUCKET_14H, 'player_id': 123,
            'event_hash_usd': _d('1200'), 'event_packet_usd': _d('800'),
        }
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        self.assertEqual(_d(result.get('event_hash_usd', 0)), _d('1200'))
        self.assertEqual(_d(result.get('event_packet_usd', 0)), _d('800'))

    def test_retention_rate(self):
        """Deux joueurs dont un seul de retour → 50%."""
        tx = MockTx()
        tx.economy_hourly[(BUCKET_14H, 100)] = {
            'bucket_start': BUCKET_14H, 'player_id': 100,
            'returning_players': 0, 'claims': 1,
        }
        tx.economy_hourly[(BUCKET_14H, 200)] = {
            'bucket_start': BUCKET_14H, 'player_id': 200,
            'returning_players': 1, 'claims': 1,
        }
        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        active = result['active_players']
        returning = int(result.get('returning_players', 0))
        self.assertEqual(active, 2)
        self.assertEqual(returning, 1)
        rate = returning / active
        self.assertAlmostEqual(rate, 0.5)

    def test_prev_period_retention(self):
        """Calcul de la rétention des joueurs actifs de la période précédente."""
        tx = MockTx()
        bucket_13h = datetime(2026, 9, 21, 13, 0, 0)
        # Période précédente (13h-14h) : joueurs 100, 200, 300
        for pid in (100, 200, 300):
            tx.economy_hourly[(bucket_13h, pid)] = {
                'bucket_start': bucket_13h, 'player_id': pid, 'claims': 1,
            }
        # Période courante (14h-15h) : joueurs 200, 300, 400
        for pid in (200, 300, 400):
            tx.economy_hourly[(BUCKET_14H, pid)] = {
                'bucket_start': BUCKET_14H, 'player_id': pid, 'claims': 1,
            }

        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        self.assertEqual(result['active_players'], 3)
        self.assertEqual(result['prev_active_players'], 3)
        self.assertEqual(result['retained_players'], 2)  # 200 et 300 ont rejoué

    def test_event_availability_aggregation(self):
        """Agrégation des journaux de disponibilité d'événements résolus."""
        tx = MockTx()
        # Deux résolutions pour hash et une pour pin dans [14h, 15h)
        tx.event_availability_logs.append({
            'event': 'hash',
            'opened_at': datetime(2026, 9, 21, 14, 10, 0),
            'solved_at': datetime(2026, 9, 21, 14, 13, 0),
            'duration_seconds': 180,
            'winner_id': 123,
            'reward': Decimal('10.00'),
        })
        tx.event_availability_logs.append({
            'event': 'hash',
            'opened_at': datetime(2026, 9, 21, 14, 30, 0),
            'solved_at': datetime(2026, 9, 21, 14, 34, 0),
            'duration_seconds': 240,
            'winner_id': 456,
            'reward': Decimal('15.00'),
        })
        tx.event_availability_logs.append({
            'event': 'pin',
            'opened_at': datetime(2026, 9, 21, 14, 0, 0),
            'solved_at': datetime(2026, 9, 21, 14, 10, 0),
            'duration_seconds': 600,
            'winner_id': 789,
            'reward': Decimal('5.00'),
        })

        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        avail = result.get('event_availability', {})
        self.assertIn('hash', avail)
        self.assertEqual(avail['hash']['wins'], 2)
        self.assertEqual(avail['hash']['total_seconds'], 420)
        self.assertEqual(avail['hash']['avg_seconds'], 210)
        self.assertFalse(avail['hash']['ongoing'])

        self.assertIn('pin', avail)
        self.assertEqual(avail['pin']['wins'], 1)
        self.assertEqual(avail['pin']['total_seconds'], 600)

    def test_ongoing_event_availability(self):
        """Détection d'un événement ouvert avant la fin de la période et non résolu."""
        tx = MockTx()
        # 'signal' ouvert à 14h15, non résolu
        tx.events['signal'] = {
            'event': 'signal',
            'next_at': datetime(2026, 9, 21, 14, 15, 0),
            'last_found_by': None,
            'last_found_on': None,
            'last_reward': Decimal('0.00'),
        }

        result = EconomyStatsDB.aggregate(tx, BUCKET_14H, BUCKET_15H)
        avail = result.get('event_availability', {})
        self.assertIn('signal', avail)
        self.assertTrue(avail['signal']['ongoing'])
        # 14h15 à 15h00 = 45 min = 2700 secondes
        self.assertEqual(avail['signal']['total_seconds'], 2700)


# ---------------------------------------------------------------------------
# Tests rendu Embed (_build_embed)
# ---------------------------------------------------------------------------

class TestEconomyEmbed(unittest.IsolatedAsyncioTestCase):

    def test_period_colors(self):
        """Vérifie la différenciation en couleur des embeds selon la durée."""
        from commands.admin.economy_reports import _build_embed
        start = datetime(2026, 9, 21, 14, 0, 0)
        end_1h = datetime(2026, 9, 21, 15, 0, 0)
        end_24h = datetime(2026, 9, 22, 14, 0, 0)
        end_72h = datetime(2026, 9, 24, 14, 0, 0)
        dummy_data = {'active_players': 1}

        embed_1h = _build_embed(1, dummy_data, start, end_1h)
        embed_24h = _build_embed(24, dummy_data, start, end_24h)
        embed_72h = _build_embed(72, dummy_data, start, end_72h)

        self.assertEqual(embed_1h.color.value, 0x3498DB)
        self.assertEqual(embed_24h.color.value, 0x2ECC71)
        self.assertEqual(embed_72h.color.value, 0x9B59B6)

    def test_retention_rendering(self):
        """Vérifie le rendu du taux de rejoueurs de la période précédente."""
        from commands.admin.economy_reports import _build_embed
        start = datetime(2026, 9, 21, 14, 0, 0)
        end = datetime(2026, 9, 21, 15, 0, 0)

        # Cas 1 : avec rejoueurs (3 sur 4 = 75.0%)
        data = {
            'active_players': 5,
            'new_players': 2,
            'prev_active_players': 4,
            'retained_players': 3,
            'claims': 10,
        }
        embed = _build_embed(1, data, start, end)
        act_field = next(f for f in embed.fields if "Activité" in f.name)
        self.assertIn("Rétention : 75.0 % (3/4 rejoueurs)", act_field.value)

        # Cas 2 : aucun joueur précédent (premier bilan)
        data_first = {
            'active_players': 2,
            'new_players': 2,
            'prev_active_players': 0,
            'retained_players': 0,
        }
        embed_first = _build_embed(1, data_first, start, end)
        act_field_first = next(f for f in embed_first.fields if "Activité" in f.name)
        self.assertIn("Rétention : non applicable (0 joueur préc.)", act_field_first.value)

    def test_availability_rendering(self):
        """Vérifie le rendu du temps de disponibilité des événements."""
        from commands.admin.economy_reports import _build_embed
        start = datetime(2026, 9, 21, 14, 0, 0)
        end = datetime(2026, 9, 21, 15, 0, 0)

        data = {
            'active_players': 3,
            'event_availability': {
                'hash': {'wins': 1, 'total_seconds': 192, 'avg_seconds': 192, 'ongoing': False},
                'pin': {'wins': 2, 'total_seconds': 600, 'avg_seconds': 300, 'ongoing': False},
                'signal': {'wins': 0, 'total_seconds': 1200, 'avg_seconds': 1200, 'ongoing': True},
            }
        }
        embed = _build_embed(1, data, start, end)
        avail_field = next(f for f in embed.fields if "Disponibilité" in f.name)
        # 192s -> 3min 12s
        self.assertIn("[hash]     3min 12s", avail_field.value)
        # 600s total, moy 300s -> 10min (2 manches • moy. 5min)
        self.assertIn("[pin]      10min (2 manches • moy. 5min)", avail_field.value)
        # en cours
        self.assertIn("[signal]   20min (en cours)", avail_field.value)

    def test_settle_challenge_win_availability(self):
        """Vérifie que settle_challenge_win enregistre la durée disponible dans les logs."""
        from unittest.mock import patch
        from game.challenge_utils import settle_challenge_win
        tx = MockTx()
        # Événement 'decode' ouvert à 14h00
        tx.events['decode'] = {
            'event': 'decode',
            'next_at': datetime(2026, 9, 21, 14, 0, 0),
            'last_found_by': None,
            'last_found_on': None,
            'last_reward': Decimal('0.00'),
        }

        # Résolution à 14h12 (12 min = 720 secondes après ouverture)
        solve_time = datetime(2026, 9, 21, 14, 12, 0)
        with patch('game.challenge_utils.PlayerData.get', return_value={'firewall_level': 0, 'dollars': 100, 'events_won': 2}), \
             patch('game.challenge_utils.UpdatePlayer.set'), \
             patch('game.challenge_utils.DailyEventStatsDB.record_win'):
            res = settle_challenge_win(tx, 'decode', 'decode_challenge', 999, Decimal('25.00'), solve_time, guild_name='TestGuild')

        self.assertEqual(res['available_seconds'], 720)
        self.assertEqual(len(tx.event_availability_logs), 1)
        log = tx.event_availability_logs[0]
        self.assertEqual(log['event'], 'decode')
        self.assertEqual(log['duration_seconds'], 720)
        self.assertEqual(log['winner_id'], 999)


# ---------------------------------------------------------------------------
# Tests initialize()
# ---------------------------------------------------------------------------

class TestInitialize(unittest.TestCase):

    def test_first_init_creates_three_rows(self):
        tx = MockTx(now=datetime(2026, 9, 21, 10, 17, 0))
        tracking_start = EconomyStatsDB.initialize(tx)
        # Doit ancrer à 11h00
        self.assertEqual(tracking_start, datetime(2026, 9, 21, 11, 0, 0))
        self.assertEqual(set(tx.economy_reports.keys()), {1, 24, 72})

    def test_resume_existing(self):
        tx = MockTx()
        # Pré-peupler les 3 lignes
        ts = datetime(2026, 9, 21, 11, 0, 0)
        for p in (1, 24, 72):
            tx.economy_reports[p] = {
                'period_hours': p, 'tracking_start': ts, 'next_start': ts,
                'pending_end': None, 'pending_payload': None, 'pending_channel_id': None,
                'last_message_id': None, 'last_sent_at': None,
            }
        result = EconomyStatsDB.initialize(tx)
        self.assertEqual(result, ts)

    def test_missing_table_raises(self):
        tx = MockTx()
        tx.tables_exist = False
        with self.assertRaises(RuntimeError):
            EconomyStatsDB.initialize(tx)


# ---------------------------------------------------------------------------
# Tests prepare_report() et ack_report()
# ---------------------------------------------------------------------------

class TestReportLifecycle(unittest.TestCase):

    def _setup_economy_reports(self, tx: MockTx, tracking_start: datetime):
        for p in _PERIODS:
            tx.economy_reports[p] = {
                'period_hours': p,
                'tracking_start': tracking_start,
                'next_start': tracking_start,
                'pending_end': None,
                'pending_payload': None,
                'pending_channel_id': None,
                'last_message_id': None,
                'last_sent_at': None,
            }

    def test_nothing_due_yet(self):
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        # now = 11h30, pas encore 12h02 pour le bilan 1h
        tx = MockTx(now=datetime(2026, 9, 21, 11, 30, 0))
        self._setup_economy_reports(tx, tracking_start)
        result = EconomyStatsDB.prepare_report(tx, 1, 12345)
        self.assertIsNone(result)

    def test_report_due_after_period_plus_2min(self):
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        # now = 12h03, le bilan 1h (11h→12h) est dû
        tx = MockTx(now=datetime(2026, 9, 21, 12, 3, 0))
        self._setup_economy_reports(tx, tracking_start)
        result = EconomyStatsDB.prepare_report(tx, 1, 99999)
        self.assertIsNotNone(result)
        self.assertEqual(result['period_hours'], 1)

    def test_pending_payload_returned_as_is(self):
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        tx = MockTx(now=datetime(2026, 9, 21, 12, 3, 0))
        self._setup_economy_reports(tx, tracking_start)
        import json
        payload = {'active_players': 5, 'period_start': '2026-09-21T11:00:00', 'period_end': '2026-09-21T12:00:00'}
        tx.economy_reports[1]['pending_payload'] = json.dumps(payload)
        tx.economy_reports[1]['pending_end'] = datetime(2026, 9, 21, 12, 0, 0)
        tx.economy_reports[1]['pending_channel_id'] = 99999
        result = EconomyStatsDB.prepare_report(tx, 1, 88888)
        # Doit retourner le payload existant, pas en préparer un nouveau
        self.assertEqual(result['data']['active_players'], 5)
        self.assertEqual(result['pending_channel_id'], 99999)  # salon original conservé

    def test_ack_advances_calendar(self):
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        period_end = datetime(2026, 9, 21, 12, 0, 0)
        tx = MockTx(now=datetime(2026, 9, 21, 12, 3, 0))
        self._setup_economy_reports(tx, tracking_start)
        import json
        tx.economy_reports[1]['pending_end'] = period_end
        tx.economy_reports[1]['pending_payload'] = json.dumps({'period_start': tracking_start.isoformat(), 'period_end': period_end.isoformat()})

        EconomyStatsDB.ack_report(tx, 1, tracking_start, period_end, message_id=777)
        row = tx.economy_reports[1]
        self.assertEqual(row['next_start'], period_end)
        self.assertIsNone(row['pending_end'])
        self.assertEqual(row['last_message_id'], 777)

    def test_ack_idempotent(self):
        """Répéter l'ack ne fait rien (next_start ne change pas à nouveau)."""
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        period_end = datetime(2026, 9, 21, 12, 0, 0)
        tx = MockTx()
        self._setup_economy_reports(tx, tracking_start)
        tx.economy_reports[1]['pending_end'] = period_end
        import json
        tx.economy_reports[1]['pending_payload'] = json.dumps({})

        EconomyStatsDB.ack_report(tx, 1, tracking_start, period_end, message_id=111)
        # next_start est maintenant period_end, pending_end est None

        # Deuxième ack avec les mêmes paramètres → ignoré car next_start != expected_start
        EconomyStatsDB.ack_report(tx, 1, tracking_start, period_end, message_id=222)
        # Le message_id ne doit pas avoir changé
        self.assertEqual(tx.economy_reports[1]['last_message_id'], 111)

    def test_zero_activity_report_no_crash(self):
        """Un bilan à zéro doit être généré sans plantage."""
        tracking_start = datetime(2026, 9, 21, 11, 0, 0)
        tx = MockTx(now=datetime(2026, 9, 21, 12, 3, 0))
        self._setup_economy_reports(tx, tracking_start)
        # Aucune donnée dans economy_hourly
        result = EconomyStatsDB.prepare_report(tx, 1, 12345)
        self.assertIsNotNone(result)
        data = result['data']
        self.assertEqual(int(data.get('active_players', 0)), 0)


# ---------------------------------------------------------------------------
# Tests du patch players.py (ram_was_full)
# ---------------------------------------------------------------------------

class TestRamWasFull(unittest.TestCase):

    def test_ram_was_full_in_claim_result(self):
        """Player.claim doit inclure ram_was_full dans son résultat en cas de succès."""
        from game.db.players import Player
        import inspect
        source = inspect.getsource(Player.claim)
        self.assertIn('ram_was_full', source,
                      "Player.claim doit inclure 'ram_was_full' dans le résultat")

    def test_ram_was_full_before_update(self):
        """ram_was_full doit être capturé AVANT le UpdatePlayer.set du chemin principal."""
        from game.db.players import Player
        import inspect
        source = inspect.getsource(Player.claim)
        # Chercher la section du chemin principal : après 'new_rootium'
        idx_new_rootium = source.find('new_rootium')
        self.assertGreater(idx_new_rootium, 0, "new_rootium doit exister dans claim")
        # Dans la section après new_rootium, ram_was_full doit précéder le UpdatePlayer.set final
        section = source[idx_new_rootium:]
        idx_ram = section.find('ram_was_full')
        idx_update = section.find('UpdatePlayer.set')
        self.assertGreater(idx_update, idx_ram,
                           "ram_was_full doit être calculé avant UpdatePlayer.set dans le chemin principal")

# ── 6. Simulation d'Équilibrage Économique ──────────────────────────────────

class TestBalanceSimulation(unittest.TestCase):
    def test_prices_match_game(self):
        from game.db.players import _calculate_module_price
        for tier in range(1, 6):
            for kind in ('firewall', 'mining'):
                column = kind if kind == 'firewall' else f'mining_t{tier}'
                assert price(kind, tier, MathConfig.load()) == _calculate_module_price(column, tier)[0]


    def test_t1_saturation_and_conversion(self):
        # Petit scénario contrôlé, indépendant des réglages d'équilibrage en production.
        rules = copy.deepcopy(MathConfig.load())
        rules['module_stats']['mining_hashrate_hs']['1'] = 25
        rules['module_stats']['mining_ram_bytes']['1'] = 200
        rules['mining']['rootium_per_hs_per_minute'] = 0.0000001
        rules['mining']['bytes_per_rtm'] = 10000000
        with patch.object(MathConfig, 'load', return_value=rules):
            sim = Simulation(PROFILES[0], 'pare_feu_prioritaire', 1, 42, event_scale=0)
            result = sim.run()
            assert result['claimed_rtm'] == D('0.00004')
            assert result['mining_income_usd'] == MathConfig.convert_rtm_to_usd(D('0.00002')) * 2
            assert result['buffer_rtm'] == D('0.00002')
        assert result['firewall'] == 0
        assert result['tier_2_day'] is None
        assert result['completed']


    def test_cash_and_production_conservation(self):
        sim = Simulation(PROFILES[1], 'minage_prioritaire', 10, 8)
        result = sim.run()
        grant = D(str(MathConfig.load()['initial_grant_usd']))
        assert abs(grant + result['total_income_usd'] - result['spent_usd'] - result['cash_usd']) < D('0.00001')
        balance = (result['theoretical_rtm'] - result['saturation_loss_rtm']
                   + result['rounding_rtm'] - result['claimed_rtm'] - result['buffer_rtm'])
        assert abs(balance) < D('0.0000001')


    def test_reproducible_randomness_and_daily_snapshots_are_read_only(self):
        first = Simulation(PROFILES[1], 'pare_feu_prioritaire', 5, 42)
        second = Simulation(PROFILES[1], 'pare_feu_prioritaire', 5, 42)
        assert first.run() == second.run()
        assert first.actions == second.actions
        probe = Simulation(PROFILES[0], 'pare_feu_prioritaire', 1, 42)
        probe.invest(0)
        before = probe.player.copy()
        probe.snapshot(100)
        probe.snapshot(200)
        assert probe.player == before


    def test_upgrade_delay_and_tier_requirements(self):
        sim = Simulation(PROFILES[2], 'pare_feu_prioritaire', 12, 42)
        sim.cash = D(50000)  # Isoler les délais du rythme d'accumulation des revenus.
        sim.run()
        level, started = 0, {}
        for action in sim.actions:
            if action['action'] == 'debut_pare_feu':
                started[action['level']] = action['day']
            elif action['action'] == 'fin_pare_feu':
                level = action['level']
                duration = (action['day'] - started[level]) * DAY
                assert abs(duration - sim.rules['firewall']['upgrade_duration_seconds']) < 1
            elif action['action'] == 'achat_minage':
                assert action['tier'] <= level + sim.rules['firewall']['max_tier_above']
        assert level >= 1


    def test_numeric_overflow_is_reported_as_partial_not_day_30(self):
        # Conserver la régression de l'ancien emballement, même après rééquilibrage.
        rules = copy.deepcopy(MathConfig.load())
        rules['initial_grant_usd'] = 100
        rules['mining']['cost_t1_usd'] = 100
        rules['mining']['cost_multiplier'] = 1.5
        rules['firewall']['first_upgrade_usd'] = 1000
        rules['firewall']['upgrade_multiplier'] = 2.5
        rules['conversion']['rtm_to_usd'] = 43567
        rules['module_stats']['mining_hashrate_hs'] = {
            '1': 25, '2': 250, '3': 1250, '4': 7500, '5': 50000,
        }
        rules['module_stats']['mining_ram_bytes'] = {
            '1': 200, '2': 3000, '3': 43750, '4': 375000, '5': 3750000,
        }
        rules['event_firewall_multipliers'] = {str(i): 2 ** i for i in range(6)}
        with patch.object(MathConfig, 'load', return_value=rules):
            sim = Simulation(PROFILES[2], 'minage_prioritaire', 30, 42)
            result = sim.run()
        assert not result['completed']
        assert result['error'] == 'decimal_precision_exceeded'
        assert result['day'] <= result['stopped_day'] < 30
        assert result['tier_5_day'] < result['stopped_day']


    def test_unreached_milestones_are_not_zero_days(self):
        results = [Simulation(profile, strategy, 1, 42, event_scale=0).run()
                   for profile in PROFILES
                   for strategy in ('pare_feu_prioritaire', 'minage_prioritaire')]
        for row in aggregate(results):
            assert row['tier_5_day_reached_pct'] == 0
            assert row['tier_5_day_median_if_reached'] is None


    def test_cash_threshold_is_measured_before_reinvestment(self):
        sim = Simulation(PROFILES[0], 'reinvestissement_t1', 1, 42)
        sim.cash = D('100001')
        sim.track_thresholds(5 * DAY)
        sim.invest(5 * DAY)
        assert sim.cash < 100
        assert sim.cash_100k_day == 5
        assert sim.income_100k_day is None  # Le cash n'est pas assimilé aux revenus cumulés.


    def test_saving_strategy_stops_purchases(self):
        sim = Simulation(PROFILES[0], 'reinvestissement_t1_epargne_j5', 1, 42)
        sim.cash = D(500)
        sim.invest(5 * DAY)
        assert sim.cash == 500
        assert sim.player.get('mining_t1', 0) == 0


    def test_all_mining_tiers_take_at_least_twelve_days_to_pay_back_without_reputation(self):
        rules = MathConfig.load()
        for tier in range(1, 6):
            per_day = (D(MathConfig.get_module_stat('mining', tier))
                       * D(str(rules['mining']['rootium_per_hs_per_minute']))
                       * 1440 * MathConfig.rtm_to_usd_rate())
            assert price('mining', tier, rules) / per_day >= 12


    def test_combat_prices_are_independent_of_mining_increase_and_keep_legacy_fallback(self):
        from game.db.players import _calculate_module_price
        assert _calculate_module_price('attack_t5', 5)[1] == D('.005') * D('1.5') ** 4
        assert _calculate_module_price('bay_defense_t5', 5)[0] == D(75) * D('1.5') ** 4
        rules = copy.deepcopy(MathConfig.load())
        del rules['beta']['cost_multiplier']
        rules['mining']['cost_multiplier'] = 2
        with patch.object(MathConfig, 'load', return_value=rules):
            assert _calculate_module_price('attack_t2', 2)[1] == D('.010')


    def test_extreme_saving_profile_does_not_reach_100k_before_day10(self):
        rules = MathConfig.load()
        profile = Profile('extreme', STRESS_PROFILE.visit_minutes, 600)
        with patch.object(MathConfig, 'load', classmethod(lambda cls: rules)):
            for seed in (42, 43, 44):
                for strategy in ('reinvestissement_t1_epargne_j5', 'minage_epargne_j5'):
                    result = Simulation(profile, strategy, 15, seed, reputation=100).run()
                    assert result['completed']
                    assert result['cash_100k_day'] is None or result['cash_100k_day'] >= 10


    def test_calibration_preserves_claim_cadence_when_hashrate_changes(self):
        from tools.calibrate_balance import candidate
        base = copy.deepcopy(MathConfig.load())
        modified = candidate(base, 2780, 3)
        for tier, minutes in {1: 8, 2: 12, 3: 35, 4: 50, 5: 75}.items():
            stats = modified['module_stats']
            rate = D(stats['mining_hashrate_hs'][str(tier)]) * D(str(modified['mining']['rootium_per_hs_per_minute']))
            capacity = D(stats['mining_ram_bytes'][str(tier)]) / D(modified['mining']['bytes_per_rtm'])
            assert capacity / rate == minutes



# ============================================================================
# SECTION : Système d'aide (/help, {prefix}help, CONCEPTION_HELP.md)
# ============================================================================

class TestHelpSystem(unittest.IsolatedAsyncioTestCase):
    """Vérifie l'intégralité du système d'aide (/help, pages, fiches et navigation)."""

    def setUp(self):
        from commands.utility.help import HelpCog
        self.bot = MagicMock()
        self.cog = HelpCog(self.bot)

    def test_help_catalogs_consistency(self):
        """Vérifie que les catalogues FR et EN sont exhaustifs et cohérents avec CONCEPTION_HELP."""
        from lang import help_fr, help_en
        from commands.utility.help import PUBLIC_COMMANDS

        # 24 commandes publiques
        self.assertEqual(len(PUBLIC_COMMANDS), 24)
        self.assertEqual(len(help_fr.COMMANDS), 24)
        self.assertEqual(len(help_en.COMMANDS), 24)

        for cmd_name in PUBLIC_COMMANDS:
            self.assertIn(cmd_name, help_fr.COMMANDS)
            self.assertIn(cmd_name, help_en.COMMANDS)

            fr_cmd = help_fr.COMMANDS[cmd_name]
            en_cmd = help_en.COMMANDS[cmd_name]

            # Vérification des champs requis
            for field in ("name", "category", "title", "description", "slash_syntax", "text_syntax", "slash_example", "text_example"):
                self.assertIn(field, fr_cmd)
                self.assertIn(field, en_cmd)
                self.assertTrue(fr_cmd[field], f"Champ {field} vide pour {cmd_name} en FR")
                self.assertTrue(en_cmd[field], f"Champ {field} vide pour {cmd_name} en EN")

        # Vérification des 8 rubriques
        self.assertEqual(len(help_fr.CATEGORIES), 8)
        self.assertEqual(len(help_en.CATEGORIES), 8)
        expected_cat_ids = {"home", "all", "network", "combat", "events", "trade", "info", "syntax"}
        self.assertEqual({c["id"] for c in help_fr.CATEGORIES}, expected_cat_ids)
        self.assertEqual({c["id"] for c in help_en.CATEGORIES}, expected_cat_ids)

        # Vérification des 8 pages
        self.assertEqual(set(help_fr.PAGES.keys()), expected_cat_ids)
        self.assertEqual(set(help_en.PAGES.keys()), expected_cat_ids)

        # Vérification des alias
        self.assertEqual(help_fr.COMMAND_ALIASES, help_en.COMMAND_ALIASES)
        for alias, target in help_fr.COMMAND_ALIASES.items():
            self.assertIn(target, PUBLIC_COMMANDS, f"L'alias {alias} pointe vers {target} qui n'est pas dans PUBLIC_COMMANDS")

    async def test_all_commands_page(self):
        """Vérifie que la page 'Toutes les commandes' liste les 24 commandes et alimente le menu déroulant."""
        from commands.utility.help import HelpView, HelpCommandSelect, PUBLIC_COMMANDS, render_help_embed

        view = HelpView(author_id=12345, locale="fr", prefix="+r", initial_category="all")
        self.assertEqual(view.current_category, "all")

        # Vérifie que le sélecteur de commandes contient bien les 24 commandes
        cmd_select = next(item for item in view.children if isinstance(item, HelpCommandSelect))
        self.assertEqual(len(cmd_select.options), 24)
        option_values = {opt.value for opt in cmd_select.options}
        self.assertEqual(option_values, set(PUBLIC_COMMANDS))

        # Vérifie que l'embed de la page liste toutes les 24 commandes
        embed = render_help_embed(locale="fr", prefix="+r", mode="slash", category="all")
        self.assertIn("Toutes les commandes", embed.title)
        for cmd_name in PUBLIC_COMMANDS:
            self.assertIn(f"/{cmd_name}", embed.description)

    async def test_slash_help_home(self):
        """Vérifie l'affichage de l'accueil en slash command (éphémère)."""
        ctx = MagicMock()
        ctx.author.id = 12345
        ctx.guild = MagicMock()
        ctx.guild.id = 999
        ctx.interaction = MagicMock()
        ctx.respond = AsyncMock()

        with patch("commands.utility.help.get_locale", return_value="fr"):
            with patch("commands.utility.help.get_prefix_async", new=AsyncMock(return_value="+r")):
                with patch.object(self.cog.check, "beta_enabled", return_value=False):
                    await self.cog.slash_help.callback(self.cog, ctx, command=None)

        ctx.respond.assert_called_once()
        call_kwargs = ctx.respond.call_args[1]
        self.assertTrue(call_kwargs.get("ephemeral"))
        embed = call_kwargs["embed"]
        self.assertIn("Centre d'aide", embed.title)
        self.assertIn("Crée ton réseau", embed.description)
        self.assertIn("`/network`", embed.description)
        self.assertIn("Mode Slash", embed.footer.text)
        view = call_kwargs["view"]
        self.assertEqual(view.mode, "slash")
        self.assertEqual(view.current_category, "home")

    async def test_prefix_help_home(self):
        """Vérifie l'affichage de l'accueil avec préfixe (public)."""
        ctx = MagicMock()
        ctx.author.id = 12345
        ctx.guild = MagicMock()
        ctx.guild.id = 999
        ctx.interaction = None
        ctx.send = AsyncMock()

        with patch("commands.utility.help.get_locale", return_value="fr"):
            with patch("commands.utility.help.get_prefix_async", new=AsyncMock(return_value="!")):
                with patch.object(self.cog.check, "beta_enabled", return_value=False):
                    await self.cog.prefix_help(ctx, command_name=None)

        ctx.send.assert_called_once()
        call_kwargs = ctx.send.call_args[1]
        embed = call_kwargs["embed"]
        self.assertIn("!network", embed.description)
        self.assertIn("Préfixe : !", embed.footer.text)
        view = call_kwargs["view"]
        self.assertEqual(view.mode, "text")

    async def test_direct_command_access(self):
        """Vérifie l'accès direct via /help command:buy et {prefix}help buy."""
        ctx = MagicMock()
        ctx.author.id = 12345
        ctx.guild = MagicMock()
        ctx.guild.id = 999
        ctx.interaction = MagicMock()
        ctx.respond = AsyncMock()

        with patch("commands.utility.help.get_locale", return_value="fr"):
            with patch("commands.utility.help.get_prefix_async", new=AsyncMock(return_value="+r")):
                with patch.object(self.cog.check, "beta_enabled", return_value=False):
                    await self.cog.slash_help.callback(self.cog, ctx, command="buy")

        ctx.respond.assert_called_once()
        embed = ctx.respond.call_args[1]["embed"]
        self.assertIn("/buy", embed.title)
        self.assertIn("/buy [kind:<mining|attack|defense>]", embed.description)
        self.assertIn("Avant d'utiliser", embed.description)
        view = ctx.respond.call_args[1]["view"]
        self.assertEqual(view.current_category, "network")
        self.assertEqual(view.current_command, "buy")

    async def test_text_alias_resolution(self):
        """Vérifie la résolution des alias texte (ex: !help n -> network, !help sell -> convert)."""
        ctx = MagicMock()
        ctx.author.id = 12345
        ctx.guild = MagicMock()
        ctx.guild.id = 999
        ctx.interaction = None
        ctx.send = AsyncMock()

        # 1. Alias 'n' -> network
        with patch("commands.utility.help.get_locale", return_value="fr"):
            with patch("commands.utility.help.get_prefix_async", new=AsyncMock(return_value="+r")):
                with patch.object(self.cog.check, "beta_enabled", return_value=False):
                    await self.cog.prefix_help(ctx, command_name="n")
        embed1 = ctx.send.call_args[1]["embed"]
        self.assertIn("network", embed1.title.lower())

        # 2. Alias 'sell' -> convert
        ctx.send.reset_mock()
        with patch("commands.utility.help.get_locale", return_value="fr"):
            with patch("commands.utility.help.get_prefix_async", new=AsyncMock(return_value="+r")):
                with patch.object(self.cog.check, "beta_enabled", return_value=False):
                    await self.cog.prefix_help(ctx, command_name="sell")
        embed2 = ctx.send.call_args[1]["embed"]
        self.assertIn("convert", embed2.title.lower())

    async def test_unknown_or_admin_command_lookup(self):
        """Vérifie qu'une commande inconnue ou d'administration affiche l'embed générique sans rien révéler."""
        ctx = MagicMock()
        ctx.author.id = 12345
        ctx.guild = MagicMock()
        ctx.guild.id = 999
        ctx.interaction = MagicMock()
        ctx.respond = AsyncMock()

        for query in ("prefix", "op", "guildinfo", "inconnue123", "/ban"):
            ctx.respond.reset_mock()
            with patch("commands.utility.help.get_locale", return_value="fr"):
                with patch("commands.utility.help.get_prefix_async", new=AsyncMock(return_value="+r")):
                    with patch.object(self.cog.check, "beta_enabled", return_value=False):
                        await self.cog.slash_help.callback(self.cog, ctx, command=query)

            embed = ctx.respond.call_args[1]["embed"]
            self.assertIn("Commande non trouvée", embed.title)
            self.assertIn("Cette commande n’est pas disponible", embed.description)

    async def test_beta_access_and_note(self):
        """Vérifie que /help est accessible en mode bêta et affiche la note pour les non-bêta testeurs."""
        from main import create_bot
        mock_bot = create_bot()
        check_fn = mock_bot._checks[0]

        mock_ctx = MagicMock()
        mock_ctx.guild = MagicMock()
        mock_ctx.guild.id = 111
        mock_ctx.author.id = 777888
        mock_ctx.interaction = MagicMock()
        mock_ctx.interaction.response.is_done.return_value = False
        mock_ctx.defer = AsyncMock()
        mock_ctx.command.module = "commands.utility.help"
        mock_ctx.command.name = "help"

        # Le joueur n'a PAS d'accès bêta : global_check doit autoriser quand même /help
        with patch("utils.check.Check.is_banned", return_value=False):
            with patch("utils.check.Check.maintenance_enabled", return_value=False):
                with patch("utils.check.Check.beta_enabled", return_value=True):
                    with patch("utils.check.Check.has_beta_access", new=AsyncMock(return_value=False)):
                        allowed = await check_fn(mock_ctx)
                        self.assertTrue(allowed)
                        mock_ctx.defer.assert_awaited_once_with(ephemeral=True)

        # Vérifie la présence de la note bêta dans l'accueil
        mock_ctx.respond = AsyncMock()
        mock_ctx.interaction.locale = "fr"
        with patch("utils.text.get_locale", return_value="fr"):
            with patch("commands.utility.help.get_locale", return_value="fr"):
                with patch("commands.utility.help.get_prefix_async", new=AsyncMock(return_value="+r")):
                    with patch.object(self.cog.check, "beta_enabled", return_value=True):
                        with patch.object(self.cog.check, "has_beta_access", new=AsyncMock(return_value=False)):
                            await self.cog.slash_help.callback(self.cog, mock_ctx, command=None)
        embed = mock_ctx.respond.call_args[1]["embed"]
        self.assertIn("Le jeu est actuellement en bêta", embed.description)

    async def test_help_view_author_lock(self):
        """Vérifie que seul l'auteur de l'aide peut manipuler les composants."""
        from commands.utility.help import HelpView

        view = HelpView(author_id=12345, locale="fr", prefix="+r")

        # 1. Même utilisateur -> autorisé
        author_interaction = MagicMock()
        author_interaction.user.id = 12345
        self.assertTrue(await view.interaction_check(author_interaction))

        # 2. Utilisateur tiers -> rejeté avec message éphémère
        intruder_interaction = MagicMock()
        intruder_interaction.user.id = 99999
        intruder_interaction.response.send_message = AsyncMock()
        self.assertFalse(await view.interaction_check(intruder_interaction))
        intruder_interaction.response.send_message.assert_called_once()
        self.assertTrue(intruder_interaction.response.send_message.call_args[1].get("ephemeral"))
        self.assertIn("propre guide", intruder_interaction.response.send_message.call_args[0][0])

    async def test_help_view_syntax_toggle(self):
        """Vérifie la bascule entre mode Slash et mode Texte."""
        from commands.utility.help import HelpView

        view = HelpView(author_id=12345, locale="fr", prefix="+r", mode="slash")
        self.assertEqual(view.mode, "slash")

        # Recherche du bouton de bascule
        toggle_btn = next(item for item in view.children if isinstance(item, discord.ui.Button) and "texte" in item.label.lower())
        mock_interaction = MagicMock()
        mock_interaction.response.edit_message = AsyncMock()

        await toggle_btn.callback(mock_interaction)
        self.assertEqual(view.mode, "text")
        mock_interaction.response.edit_message.assert_called_once()
        embed = mock_interaction.response.edit_message.call_args[1]["embed"]
        self.assertIn("Mode Texte", embed.footer.text)

    async def test_help_view_category_navigation(self):
        """Vérifie la navigation vers une catégorie puis vers une commande."""
        from commands.utility.help import HelpView, HelpCategorySelect, HelpCommandSelect

        view = HelpView(author_id=12345, locale="fr", prefix="+r", mode="slash")
        cat_select = next(item for item in view.children if isinstance(item, HelpCategorySelect))

        mock_interaction = MagicMock()
        mock_interaction.response.edit_message = AsyncMock()

        # Sélection de la catégorie "combat"
        cat_select._selected_values = ["combat"]
        await cat_select.callback(mock_interaction)
        self.assertEqual(view.current_category, "combat")
        self.assertIsNone(view.current_command)

        # Sélection de la commande "hack"
        cmd_select = next(item for item in view.children if isinstance(item, HelpCommandSelect))
        cmd_select._selected_values = ["hack"]
        await cmd_select.callback(mock_interaction)
        self.assertEqual(view.current_command, "hack")
        embed = mock_interaction.response.edit_message.call_args[1]["embed"]
        self.assertIn("/hack", embed.title)

    async def test_help_view_timeout(self):
        """Vérifie la désactivation des composants à l'expiration du timeout."""
        from commands.utility.help import HelpView

        view = HelpView(author_id=12345, locale="fr", prefix="+r")
        mock_msg = MagicMock()
        mock_msg.embeds = [discord.Embed(title="Aide", description="Contenu")]
        mock_msg.edit = AsyncMock()
        view.message = mock_msg

        await view.on_timeout()
        for child in view.children:
            self.assertTrue(child.disabled)
        mock_msg.edit.assert_awaited_once()
        edited_embed = mock_msg.edit.call_args[1]["embed"]
        self.assertIn("Navigation expirée", edited_embed.description)

    async def test_help_autocomplete(self):
        """Vérifie que l'autocomplétion propose les 24 commandes et filtre la saisie."""
        from commands.utility.help import help_command_autocomplete

        ctx = MagicMock()
        ctx.value = ""
        results = await help_command_autocomplete(ctx)
        self.assertEqual(len(results), 24)

        ctx.value = "ha"
        results_ha = await help_command_autocomplete(ctx)
        self.assertIn("hack", results_ha)
        self.assertIn("hash", results_ha)
        self.assertNotIn("buy", results_ha)

    async def test_help_official_server_presence(self):
        """Vérifie la présence du lien et bouton du serveur officiel dans le système d'aide."""
        from commands.utility.help import HelpView, render_help_embed
        from data import OFFICIAL_SERVER_URL
        from lang import help_fr, help_en

        self.assertIn("btn_server", help_fr.UI)
        self.assertIn("btn_server", help_en.UI)

        # Vérifie le bouton dans HelpView
        view = HelpView(author_id=12345, locale="fr", prefix="+r")
        button_urls = [btn.url for btn in view.children if hasattr(btn, "url")]
        self.assertIn(OFFICIAL_SERVER_URL, button_urls)

        # Vérifie la présence du lien dans les embeds Home et Info (FR et EN)
        for loc in ("fr", "en"):
            home_embed = render_help_embed(locale=loc, prefix="+r", mode="slash", category="home")
            self.assertIn(OFFICIAL_SERVER_URL, home_embed.description)

            info_embed = render_help_embed(locale=loc, prefix="+r", mode="slash", category="info")
            self.assertIn(OFFICIAL_SERVER_URL, info_embed.description)



class TestOfficialServerAutoRole(unittest.IsolatedAsyncioTestCase):
    """Vérifie l'attribution automatique du rôle player lors de l'arrivée sur le serveur officiel."""

    async def test_assign_role_success(self):
        from main import assign_official_player_role
        from data import OFFICIAL_GUILD_ID, PLAYER_ROLE_ID

        member = MagicMock()
        member.id = 123456789
        member.bot = False
        member.roles = []
        member.guild = MagicMock()
        member.guild.id = OFFICIAL_GUILD_ID

        mock_role = MagicMock()
        mock_role.id = PLAYER_ROLE_ID
        member.guild.get_role.return_value = mock_role
        member.add_roles = AsyncMock()

        result = await assign_official_player_role(member)
        self.assertTrue(result)
        member.add_roles.assert_awaited_once_with(
            mock_role,
            reason="Attribution automatique du rôle player aux nouveaux membres du serveur officiel",
        )

    async def test_assign_role_fallback_object(self):
        from main import assign_official_player_role
        from data import OFFICIAL_GUILD_ID, PLAYER_ROLE_ID

        member = MagicMock()
        member.id = 123456789
        member.bot = False
        member.roles = []
        member.guild = MagicMock()
        member.guild.id = OFFICIAL_GUILD_ID
        member.guild.get_role.return_value = None
        member.add_roles = AsyncMock()

        result = await assign_official_player_role(member)
        self.assertTrue(result)
        member.add_roles.assert_awaited_once()
        added_role = member.add_roles.call_args[0][0]
        self.assertEqual(added_role.id, PLAYER_ROLE_ID)

    async def test_ignore_other_guild(self):
        from main import assign_official_player_role

        member = MagicMock()
        member.id = 123456789
        member.bot = False
        member.guild = MagicMock()
        member.guild.id = 999999999999  # Serveur tiers
        member.add_roles = AsyncMock()

        result = await assign_official_player_role(member)
        self.assertFalse(result)
        member.add_roles.assert_not_awaited()

    async def test_ignore_bot(self):
        from main import assign_official_player_role
        from data import OFFICIAL_GUILD_ID

        member = MagicMock()
        member.id = 123456789
        member.bot = True
        member.guild = MagicMock()
        member.guild.id = OFFICIAL_GUILD_ID
        member.add_roles = AsyncMock()

        result = await assign_official_player_role(member)
        self.assertFalse(result)
        member.add_roles.assert_not_awaited()

    async def test_already_has_role(self):
        from main import assign_official_player_role
        from data import OFFICIAL_GUILD_ID, PLAYER_ROLE_ID

        mock_role = MagicMock()
        mock_role.id = PLAYER_ROLE_ID

        member = MagicMock()
        member.id = 123456789
        member.bot = False
        member.roles = [mock_role]
        member.guild = MagicMock()
        member.guild.id = OFFICIAL_GUILD_ID
        member.add_roles = AsyncMock()

        result = await assign_official_player_role(member)
        self.assertTrue(result)
        member.add_roles.assert_not_awaited()

    async def test_forbidden_handled_gracefully(self):
        from main import assign_official_player_role
        from data import OFFICIAL_GUILD_ID

        member = MagicMock()
        member.id = 123456789
        member.bot = False
        member.roles = []
        member.guild = MagicMock()
        member.guild.id = OFFICIAL_GUILD_ID

        mock_resp = MagicMock()
        mock_resp.status = 403
        member.add_roles = AsyncMock(side_effect=discord.Forbidden(mock_resp, "Missing Permissions"))

        result = await assign_official_player_role(member)
        self.assertFalse(result)

    async def test_on_member_join_event_in_bot(self):
        from main import create_bot
        from data import OFFICIAL_GUILD_ID, PLAYER_ROLE_ID

        bot = create_bot()
        self.assertTrue(hasattr(bot, "on_member_join"))

        member = MagicMock()
        member.id = 123456789
        member.bot = False
        member.roles = []
        member.guild = MagicMock()
        member.guild.id = OFFICIAL_GUILD_ID
        mock_role = MagicMock()
        mock_role.id = PLAYER_ROLE_ID
        member.guild.get_role.return_value = mock_role
        member.add_roles = AsyncMock()

        await bot.on_member_join(member)
        member.add_roles.assert_awaited_once()


class TestAutoclaimFeature(unittest.IsolatedAsyncioTestCase):
    """Couvre l'ensemble du système d'autoclaim (crédits, seuil 99.9%, annulation, logs et anti-triche)."""

    def setUp(self):
        self.tx = MockTransaction()
        self.actor = 99901
        Player.network(self.tx, self.actor)
        self.tx.players[self.actor]["mining_t1"] = 1
        self.tx.players[self.actor]["mining_buffer"] = Decimal('0.05000')
        self.tx.players[self.actor]["mining_last_update_at"] = self.tx.now
        self.tx.players[self.actor]["autoclaim_credits"] = 3
        self.tx.players[self.actor]["autoclaim_active"] = 0

    def test_start_autoclaim_all_and_count(self):
        """Vérifie le démarrage de l'autoclaim avec 'all' et avec un montant explicite."""
        # Lancement avec count='all'
        res_all = Player.start_autoclaim(self.tx, self.actor, 'all')
        self.assertEqual(res_all['activated_count'], 3)
        self.assertEqual(self.tx.players[self.actor]['autoclaim_credits'], 0)
        self.assertEqual(self.tx.players[self.actor]['autoclaim_active'], 3)
        self.assertTrue(res_all['claim_result'].get('claimed'))

        # Restitution pour second test
        self.tx.players[self.actor]['autoclaim_credits'] = 5
        self.tx.players[self.actor]['autoclaim_active'] = 0
        res_nb = Player.start_autoclaim(self.tx, self.actor, 2)
        self.assertEqual(res_nb['activated_count'], 2)
        self.assertEqual(self.tx.players[self.actor]['autoclaim_credits'], 3)
        self.assertEqual(self.tx.players[self.actor]['autoclaim_active'], 2)

    def test_start_autoclaim_errors(self):
        """Vérifie le rejet pour crédits insuffisants, quantité invalide ou absence de mineurs."""
        # 1. Crédits insuffisants
        self.tx.players[self.actor]['autoclaim_credits'] = 0
        with self.assertRaises(GameError) as cm:
            Player.start_autoclaim(self.tx, self.actor, 1)
        self.assertEqual(cm.exception.key, 'insufficient_autoclaim_credits')

        self.tx.players[self.actor]['autoclaim_credits'] = 2
        with self.assertRaises(GameError) as cm:
            Player.start_autoclaim(self.tx, self.actor, 5)
        self.assertEqual(cm.exception.key, 'insufficient_autoclaim_credits')

        # 2. Quantité invalide
        with self.assertRaises(GameError) as cm:
            Player.start_autoclaim(self.tx, self.actor, 0)
        self.assertEqual(cm.exception.key, 'insufficient_autoclaim_credits')

        with self.assertRaises(GameError) as cm:
            Player.start_autoclaim(self.tx, self.actor, 'invalide')
        self.assertEqual(cm.exception.key, 'invalid_autoclaim_count')

        # 3. Aucun module de minage
        no_miner_actor = 99902
        Player.network(self.tx, no_miner_actor)
        self.tx.players[no_miner_actor]['autoclaim_credits'] = 5
        with self.assertRaises(GameError) as cm:
            Player.start_autoclaim(self.tx, no_miner_actor, 'all')
        self.assertEqual(cm.exception.key, 'no_miner_autoclaim')

    def test_cancel_autoclaim(self):
        """Vérifie l'annulation des autoclaims et la restitution exacte des crédits."""
        self.tx.players[self.actor]['autoclaim_credits'] = 1
        self.tx.players[self.actor]['autoclaim_active'] = 3

        res = Player.cancel_autoclaim(self.tx, self.actor)
        self.assertEqual(res['refunded_count'], 3)
        self.assertEqual(res['autoclaim_credits'], 4)
        self.assertEqual(self.tx.players[self.actor]['autoclaim_credits'], 4)
        self.assertEqual(self.tx.players[self.actor]['autoclaim_active'], 0)

        # Annulation quand aucun n'est actif -> erreur
        with self.assertRaises(GameError) as cm:
            Player.cancel_autoclaim(self.tx, self.actor)
        self.assertEqual(cm.exception.key, 'no_active_autoclaim')

    def test_process_autoclaim_tick_at_threshold(self):
        """Vérifie l'exécution d'un tick d'autoclaim et la décrémentation du compteur."""
        self.tx.players[self.actor]['autoclaim_active'] = 2
        self.tx.players[self.actor]['mining_buffer'] = Decimal('0.05000')

        res = Player.process_autoclaim_tick(self.tx, self.actor)
        self.assertTrue(res.get('claimed'))
        self.assertTrue(res.get('is_auto'))
        self.assertEqual(res.get('autoclaim_active_remaining'), 1)
        self.assertEqual(self.tx.players[self.actor]['autoclaim_active'], 1)

        # Vérifie l'enregistrement avec is_auto=True dans daily_claim_logs
        self.assertEqual(len(self.tx.daily_claim_logs), 1)
        self.assertTrue(self.tx.daily_claim_logs[0]['is_auto'])

    async def test_service_process_due_autoclaims_threshold_filter(self):
        """Vérifie que process_due_autoclaims ne récolte que si la RAM atteint >= 99.9%."""
        from game.root_service import RootService
        mock_db = MockDatabase()
        mock_db.players[self.actor] = dict(self.tx.players[self.actor])
        mock_db.players[self.actor]['autoclaim_active'] = 1

        service = RootService(database=mock_db)

        # Calcul de la capacité de RAM
        stats = MathConfig.calculate_player_stats(mock_db.players[self.actor])
        capacity = MathConfig.compute_mining_progress(mock_db.players[self.actor], stats, datetime.now())['capacity_rtm']

        # 1. Tampon à 50% de la capacité -> pas de récolte
        mock_db.players[self.actor]['mining_buffer'] = (capacity * Decimal('0.50')).quantize(Decimal('0.00001'))
        mock_db.players[self.actor]['mining_last_update_at'] = datetime.now()
        due = await service.process_due_autoclaims()
        self.assertEqual(len(due), 0)
        self.assertEqual(mock_db.players[self.actor]['autoclaim_active'], 1)

        # 2. Tampon à 99.95% de la capacité (>= 99.9%) -> déclenchement automatique
        mock_db.players[self.actor]['mining_buffer'] = (capacity * Decimal('0.9995')).quantize(Decimal('0.00001'))
        mock_db.players[self.actor]['mining_last_update_at'] = datetime.now()
        due = await service.process_due_autoclaims()
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]['actor'], self.actor)
        self.assertTrue(due[0]['is_auto'])
        self.assertEqual(mock_db.players[self.actor]['autoclaim_active'], 0)

    def test_daily_claim_stats_breakdown(self):
        """Vérifie que DailyClaimStatsDB ventile correctement manual_count et auto_count."""
        now = datetime(2026, 9, 23, 14, 0, 0)
        DailyClaimStatsDB.record_claim(self.tx, self.actor, now, 600, Decimal("1.0"), is_auto=False)
        DailyClaimStatsDB.record_claim(self.tx, self.actor, now + timedelta(minutes=10), 600, Decimal("1.0"), is_auto=True)
        DailyClaimStatsDB.record_claim(self.tx, self.actor, now + timedelta(minutes=20), 600, Decimal("1.0"), is_auto=True)

        summary = DailyClaimStatsDB.get_summary(self.tx)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["claim_count"], 3)
        self.assertEqual(summary[0]["manual_count"], 1)
        self.assertEqual(summary[0]["auto_count"], 2)

        user_claims = DailyClaimStatsDB.get_user_claims(self.tx, self.actor)
        self.assertEqual(len(user_claims), 3)
        self.assertFalse(user_claims[0]["is_auto"])
        self.assertTrue(user_claims[1]["is_auto"])
        self.assertTrue(user_claims[2]["is_auto"])

    def test_claim_analysis_autoclaim_anti_cheat(self):
        """Vérifie que les autoclaims n'induisent pas de faux positifs de macro."""
        now = datetime(2026, 9, 23, 10, 0, 0)
        # Séquence de claims avec plusieurs autoclaims
        claims = [
            {"claimed_at": now, "interval_seconds": 0, "amount": Decimal("1"), "is_auto": False},
            {"claimed_at": now + timedelta(hours=2), "interval_seconds": 7200, "amount": Decimal("1"), "is_auto": False},
            {"claimed_at": now + timedelta(hours=5), "interval_seconds": 10800, "amount": Decimal("1"), "is_auto": True},
            {"claimed_at": now + timedelta(hours=8), "interval_seconds": 10800, "amount": Decimal("1"), "is_auto": True},
        ]
        metrics = calculate_player_claim_metrics(claims)
        self.assertEqual(metrics["manual_claim_count"], 2)
        self.assertEqual(metrics["auto_claim_count"], 2)
        # Ne doit pas être HIGH risk
        self.assertNotEqual(metrics["risk_level"], "HIGH")

    async def test_claim_credits_hint_conditional_display(self):
        """Vérifie que la phrase de crédits ne s'affiche que si autoclaim_credits > 0."""
        from commands.game.claim import Claim

        mock_bot = MagicMock()
        mock_bot.wait_until_ready = AsyncMock()
        mock_bot.discord_logger = MagicMock()
        cog = Claim(mock_bot)
        try:
            mock_ctx = MagicMock()
            mock_ctx.interaction = None
            mock_ctx.clean_prefix = "!"
            mock_ctx.prefix = "!"
            mock_ctx.user = None
            mock_ctx.author.id = self.actor

            # 1. Avec 0 crédits
            res_zero = {
                'claimed': True,
                'amount': Decimal('0.05000'),
                'new_rootium': Decimal('10.05000'),
                'rate_per_min': Decimal('0.00010'),
                'total_ram_formatted': '100 Ko',
                'autoclaim_credits': 0,
            }
            cog._reply = AsyncMock()
            cog._log_blockchain = AsyncMock()
            cog._log_moderation = AsyncMock()
            await cog._send(mock_ctx, 'claim', res_zero)
            sent_content_zero = cog._reply.call_args[0][1]
            self.assertNotIn("Autoclaim credits", sent_content_zero)
            self.assertNotIn("Crédits d'autoclaim", sent_content_zero)

            # 2. Avec 3 crédits
            res_credits = {
                'claimed': True,
                'amount': Decimal('0.05000'),
                'new_rootium': Decimal('10.05000'),
                'rate_per_min': Decimal('0.00010'),
                'total_ram_formatted': '100 Ko',
                'autoclaim_credits': 3,
            }
            cog._reply.reset_mock()
            await cog._send(mock_ctx, 'claim', res_credits)
            sent_content_credits = cog._reply.call_args[0][1]
            self.assertTrue(
                "Autoclaim credits" in sent_content_credits or "Crédits d'autoclaim" in sent_content_credits
            )
            self.assertIn("`3`", sent_content_credits)
        finally:
            cog.cog_unload()

    async def test_prefix_and_slash_claim_dispatch(self):
        """Vérifie l'aiguillage des commandes préfixe !claim auto/cancel et slash /claim auto:x."""
        from commands.game.claim import Claim

        mock_bot = MagicMock()
        mock_bot.wait_until_ready = AsyncMock()
        cog = Claim(mock_bot)
        try:
            cog._invoke = AsyncMock()
            mock_ctx = MagicMock()

            # 1. !claim -> claim
            await cog.prefix_claim.callback(cog, mock_ctx)
            cog._invoke.assert_awaited_with(mock_ctx, 'claim')

            # 2. !claim auto 3 -> claim_auto count='3'
            cog._invoke.reset_mock()
            await cog.prefix_claim.callback(cog, mock_ctx, 'auto', '3')
            cog._invoke.assert_awaited_with(mock_ctx, 'claim_auto', count='3')

            # 3. !claim auto all -> claim_auto count='all'
            cog._invoke.reset_mock()
            await cog.prefix_claim.callback(cog, mock_ctx, 'auto', 'all')
            cog._invoke.assert_awaited_with(mock_ctx, 'claim_auto', count='all')

            # 4. !claim auto cancel -> claim_cancel
            cog._invoke.reset_mock()
            await cog.prefix_claim.callback(cog, mock_ctx, 'auto', 'cancel')
            cog._invoke.assert_awaited_with(mock_ctx, 'claim_cancel')

            # 5. !claim cancel -> claim_cancel
            cog._invoke.reset_mock()
            await cog.prefix_claim.callback(cog, mock_ctx, 'cancel')
            cog._invoke.assert_awaited_with(mock_ctx, 'claim_cancel')

            # 6. /claim -> claim
            cog._invoke.reset_mock()
            await cog.claim.callback(cog, mock_ctx, auto=None)
            cog._invoke.assert_awaited_with(mock_ctx, 'claim')

            # 7. /claim auto:'all' -> claim_auto
            cog._invoke.reset_mock()
            await cog.claim.callback(cog, mock_ctx, auto='all')
            cog._invoke.assert_awaited_with(mock_ctx, 'claim_auto', count='all')

            # 8. /claim auto:'cancel' -> claim_cancel
            cog._invoke.reset_mock()
            await cog.claim.callback(cog, mock_ctx, auto='cancel')
            cog._invoke.assert_awaited_with(mock_ctx, 'claim_cancel')
        finally:
            cog.cog_unload()


class TestPrefixCaseInsensitiveHandling(unittest.IsolatedAsyncioTestCase):
    """Vérifie la normalisation en minuscules des commandes commençant par un préfixe custom."""

    async def test_on_message_lowers_custom_prefix_command(self):
        from main import create_bot
        bot = create_bot()
        bot.process_commands = AsyncMock()

        msg = MagicMock(spec=discord.Message)
        msg.author.bot = False
        msg.guild = MagicMock(id=123)
        msg.content = "!NETWORK"

        with patch("main.get_prefix_async", new=AsyncMock(return_value="!")):
            await bot.on_message(msg)

        self.assertEqual(msg.content, "!network")
        bot.process_commands.assert_awaited_once_with(msg)

    async def test_on_message_lowers_mixed_case_arguments(self):
        from main import create_bot
        bot = create_bot()
        bot.process_commands = AsyncMock()

        msg = MagicMock(spec=discord.Message)
        msg.author.bot = False
        msg.guild = MagicMock(id=123)
        msg.content = "!BUY MINING 1"

        with patch("main.get_prefix_async", new=AsyncMock(return_value="!")):
            await bot.on_message(msg)

        self.assertEqual(msg.content, "!buy mining 1")
        bot.process_commands.assert_awaited_once_with(msg)

    async def test_on_message_handles_uppercase_prefix_itself(self):
        from main import create_bot
        bot = create_bot()
        bot.process_commands = AsyncMock()

        msg = MagicMock(spec=discord.Message)
        msg.author.bot = False
        msg.guild = MagicMock(id=123)
        msg.content = "+R NETWORK"

        with patch("main.get_prefix_async", new=AsyncMock(return_value="+r")):
            await bot.on_message(msg)

        self.assertEqual(msg.content, "+r network")
        bot.process_commands.assert_awaited_once_with(msg)

    async def test_on_message_ignores_non_prefix_messages(self):
        from main import create_bot
        bot = create_bot()
        bot.process_commands = AsyncMock()

        msg = MagicMock(spec=discord.Message)
        msg.author.bot = False
        msg.guild = MagicMock(id=123)
        msg.content = "HELLO WORLD"

        with patch("main.get_prefix_async", new=AsyncMock(return_value="!")):
            await bot.on_message(msg)

        self.assertEqual(msg.content, "HELLO WORLD")
        bot.process_commands.assert_awaited_once_with(msg)

    async def test_on_message_edit_lowers_custom_prefix_command(self):
        from main import create_bot
        bot = create_bot()
        bot.process_commands = AsyncMock()

        before = MagicMock(spec=discord.Message)
        before.author.bot = False
        before.guild = MagicMock(id=123)
        before.content = "hello"

        after = MagicMock(spec=discord.Message)
        after.author.bot = False
        after.guild = MagicMock(id=123)
        after.content = "!HELP"

        with patch("main.get_prefix_async", new=AsyncMock(return_value="!")):
            await bot.on_message_edit(before, after)

        self.assertEqual(after.content, "!help")
        bot.process_commands.assert_awaited_once_with(after)


if __name__ == '__main__':
    unittest.main()

