"""
Gestionnaire métier du mini-jeu communautaire Code PIN (/pin).

Architecture des données (Zéro fichier JSON) :
1. Base de données MySQL (table 'events' avec event='pin') :
   - Source de vérité persistante pour le cooldown (next_at), le dernier gagnant (last_found_by),
     le serveur d'origine (last_found_on) et la récompense (last_reward).
2. Mémoire vive (_active_challenge) :
   - Fourchette courte (150 valeurs) avec cible globale secrète commune à tous les serveurs.
   - Suivi INDIVIDUEL de la zone de recherche (player_states[actor]) et du compteur d'essais.
   - Dès qu'un joueur trouve le code PIN, le gain est attribué en BDD et la manche est clôturée pour tout le monde.
"""

from decimal import Decimal
import random
from typing import Any

from game.base_challenge_manager import BaseChallengeManager
from game.challenge_utils import ChallengeResource, check_challenge_cooldown, settle_challenge_win
from game.db.daily_event_stats import DailyEventStatsDB
from game.math_config import MathConfig


def _create_new_challenge() -> dict:
    """Génère un nouveau défi actif avec une plage de 100 valeurs."""
    settings = MathConfig.load().get("pin_challenge", {})
    range_size = int(settings.get("range_size", 100))
    min_bound = random.randint(1, 900)
    max_bound = min_bound + range_size
    target = random.randint(min_bound, max_bound)

    min_usd = float(settings.get("reward_min_usd", 1.50))
    max_usd = float(settings.get("reward_max_usd", 5.00))
    reward = round(random.uniform(min_usd, max_usd), 2)

    return {
        "min_bound": min_bound,
        "max_bound": max_bound,
        "target": target,
        "reward": reward,
        "player_states": {},
    }


class PinManager(BaseChallengeManager):
    """Gestionnaire du PIN Challenge en mémoire vive et BDD MySQL."""

    event_name = "pin"
    config_key = "pin_challenge"

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

        # 2. Le défi est actif
        challenge = resource.staged_challenge
        if challenge is None:
            challenge = cls._create_new_challenge()
            resource.stage(challenge)

        challenge.setdefault("player_states", {})

        if actor not in challenge["player_states"]:
            challenge["player_states"][actor] = {
                "current_min": challenge["min_bound"],
                "current_max": challenge["max_bound"],
                "tries": 0,
            }
            resource.stage(challenge)

        player_state = challenge["player_states"][actor]
        target = challenge["target"]
        reward = Decimal(str(challenge.get("reward", "3.15")))
        players_count = len(challenge["player_states"])

        # Consultation sans proposition
        if guess is None:
            return {
                "status": "active_info",
                "min_bound": challenge["min_bound"],
                "max_bound": challenge["max_bound"],
                "current_min": player_state["current_min"],
                "current_max": player_state["current_max"],
                "players_count": players_count,
                "tries": player_state["tries"],
            }

        guess = int(guess)
        DailyEventStatsDB.record_participation(tx, actor)
        player_state["tries"] += 1

        if guess < target:
            player_state["current_min"] = max(player_state["current_min"], guess + 1)
            resource.stage(challenge)
            return {
                "status": "too_low",
                "guess": guess,
                "min_bound": challenge["min_bound"],
                "max_bound": challenge["max_bound"],
                "current_min": player_state["current_min"],
                "current_max": player_state["current_max"],
                "players_count": players_count,
                "tries": player_state["tries"],
            }

        if guess > target:
            player_state["current_max"] = min(player_state["current_max"], guess - 1)
            resource.stage(challenge)
            return {
                "status": "too_high",
                "guess": guess,
                "min_bound": challenge["min_bound"],
                "max_bound": challenge["max_bound"],
                "current_min": player_state["current_min"],
                "current_max": player_state["current_max"],
                "players_count": players_count,
                "tries": player_state["tries"],
            }

        # 3. VICTOIRE (guess == target)
        settlement = settle_challenge_win(tx, cls.event_name, cls.config_key, actor, reward, now, guild_name)
        final_players_count = players_count
        final_tries = player_state["tries"]
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
            "tries": final_tries,
        }
