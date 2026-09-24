"""
Gestionnaire métier du mini-jeu communautaire Hash Challenge (/hash).

Architecture des données :
1. Base de données MySQL (table 'events') :
   - Source de vérité persistante pour le cooldown (next_at), le dernier gagnant (last_found_by),
     le serveur d'origine (last_found_on) et la récompense (last_reward).
2. Mémoire vive (_active_challenge) :
   - Maintient l'état du défi en cours et l'affinement en direct des bornes (current_min / current_max).
   - Réinitialisé à None dès la résolution du hash ou lors d'un cooldown.
"""

from datetime import timedelta
from decimal import Decimal
import random
from typing import Any

from game.base_challenge_manager import BaseChallengeManager
from game.challenge_utils import ChallengeResource, check_challenge_cooldown, settle_challenge_win
from game.db.daily_event_stats import DailyEventStatsDB
from game.math_config import MathConfig


def _create_new_challenge() -> dict:
    """Génère un nouveau défi actif avec une plage de valeurs configurée."""
    settings = MathConfig.load().get("hash_challenge", {})
    range_size = int(settings.get("range_size", 1000))
    min_bound = random.randint(1, 900)
    max_bound = min_bound + range_size
    target = random.randint(min_bound, max_bound)

    min_usd = float(settings.get("reward_min_usd", 75.00))
    max_usd = float(settings.get("reward_max_usd", 200.00))
    reward = round(random.uniform(min_usd, max_usd), 2)

    return {
        "min_bound": min_bound,
        "max_bound": max_bound,
        "current_min": min_bound,
        "current_max": max_bound,
        "target": target,
        "reward": reward,
        "participants": set(),
        "player_cooldowns": {},
    }


class HashManager(BaseChallengeManager):
    """Gestionnaire du Hash Challenge en mémoire vive et BDD MySQL."""

    event_name = "hash"
    config_key = "hash_challenge"

    @classmethod
    def _create_new_challenge(cls) -> dict:
        return _create_new_challenge()

    @classmethod
    def _process_staged(cls, tx, actor: int, guild_name: str | None, guess: Any, resource: ChallengeResource) -> dict:
        now = tx.now

        # 1. Vérification du cooldown réseau
        cooldown = check_challenge_cooldown(tx, cls.event_name, now)
        if cooldown:
            resource.stage(None)
            return cooldown

        # 2. Le hash est actif
        challenge = resource.staged_challenge
        if challenge is None:
            challenge = cls._create_new_challenge()
            resource.stage(challenge)

        challenge.setdefault("participants", set())
        challenge.setdefault("player_cooldowns", {})

        min_bound = challenge["min_bound"]
        max_bound = challenge["max_bound"]
        current_min = challenge.get("current_min", min_bound)
        current_max = challenge.get("current_max", max_bound)
        target = challenge["target"]
        reward = Decimal(str(challenge.get("reward", "100.00")))
        player_cooldowns = challenge["player_cooldowns"]

        # Consultation sans proposition
        if guess is None:
            return {
                "status": "active_info",
                "min_bound": min_bound,
                "max_bound": max_bound,
                "current_min": current_min,
                "current_max": current_max,
                "players_count": len(challenge["participants"]),
            }

        guess = int(guess)

        # Vérification du cooldown individuel joueur (8 minutes par défaut)
        settings = MathConfig.load().get("hash_challenge", {})
        player_cooldown_sec = int(settings.get("player_cooldown_seconds", 480))
        last_guess_at = player_cooldowns.get(actor)
        if last_guess_at is not None:
            elapsed = (now - last_guess_at).total_seconds()
            if elapsed < player_cooldown_sec:
                remaining_sec = max(1, int(player_cooldown_sec - elapsed))
                next_guess_at = last_guess_at + timedelta(seconds=player_cooldown_sec)
                return {
                    "status": "player_cooldown",
                    "guess": guess,
                    "min_bound": min_bound,
                    "max_bound": max_bound,
                    "current_min": current_min,
                    "current_max": current_max,
                    "remaining_seconds": remaining_sec,
                    "next_guess_at": next_guess_at,
                    "players_count": len(challenge["participants"]),
                }

        # Enregistrement de la tentative
        player_cooldowns[actor] = now
        DailyEventStatsDB.record_participation(tx, actor)
        challenge["participants"].add(actor)
        players_count = len(challenge["participants"])

        if guess < target:
            new_min = max(current_min, guess + 1)
            challenge["current_min"] = new_min
            resource.stage(challenge)
            return {
                "status": "too_low",
                "guess": guess,
                "min_bound": min_bound,
                "max_bound": max_bound,
                "current_min": new_min,
                "current_max": current_max,
                "players_count": players_count,
            }

        if guess > target:
            new_max = min(current_max, guess - 1)
            challenge["current_max"] = new_max
            resource.stage(challenge)
            return {
                "status": "too_high",
                "guess": guess,
                "min_bound": min_bound,
                "max_bound": max_bound,
                "current_min": current_min,
                "current_max": new_max,
                "players_count": players_count,
            }

        # 3. VICTOIRE (guess == target)
        settlement = settle_challenge_win(tx, cls.event_name, cls.config_key, actor, reward, now, guild_name)
        final_players_count = players_count
        resource.stage(None)

        return {
            "status": "won",
            "winner": actor,
            "reward": settlement["final_reward"],
            "base_reward": settlement["base_reward"],
            "multiplier": settlement["multiplier"],
            "target": target,
            "next_at": settlement["next_at"],
            "last_found_on": settlement["server_name"],
            "players_count": final_players_count,
        }
