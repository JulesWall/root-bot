"""
Gestionnaire métier du mini-jeu communautaire Signal (/signal).

Architecture des données (Zéro fichier JSON) :
1. Base de données MySQL (table 'events' avec event='signal') :
   - Source de vérité persistante pour le cooldown (next_at), le dernier gagnant (last_found_by),
     le serveur d'origine (last_found_on) et la récompense en USD (last_reward).
2. Mémoire vive (_active_challenge) :
   - Une seule ligne courte de 15 lettres majuscules espacées.
   - 3 lettres distinctes : 1 lettre très majoritaire (8 occurrences),
     et 2 distracteurs (4 et 3 occurrences).
   - Victoire stricte sans égalité possible (8 vs 4 et 3).
   - Validation atomique (un seul gagnant garanti même en cas de réponses simultanées).
   - Aucun délai entre les propositions erronées.
"""

from decimal import Decimal
import random
import string
from typing import Any

from game.base_challenge_manager import SingleTargetChallengeManager
from game.math_config import MathConfig

SIGNAL_LENGTH = 15
TARGET_COUNT = 8
DISTRACTOR_1_COUNT = 4
DISTRACTOR_2_COUNT = 3  # 8 + 4 + 3 = 15


def _create_new_challenge() -> dict:
    """
    Génère un nouveau défi actif de signal :
    - Une seule ligne courte de 15 lettres majuscules espacées.
    - 3 lettres majuscules distinctes sélectionnées.
    - 1 lettre nettement majoritaire (8 occurrences).
    - 2 lettres distractrices (4 et 3 occurrences).
    - Mélange aléatoire des 15 lettres.
    """
    settings = MathConfig.load().get("signal_challenge", {})

    chosen_letters = random.sample(string.ascii_uppercase, 3)
    winning_letter = chosen_letters[0]
    d1, d2 = chosen_letters[1], chosen_letters[2]

    pool = [winning_letter] * TARGET_COUNT + [d1] * DISTRACTOR_1_COUNT + [d2] * DISTRACTOR_2_COUNT
    random.shuffle(pool)

    block_display = " ".join(pool)

    min_usd = float(settings.get("reward_min_usd", 1.50))
    max_usd = float(settings.get("reward_max_usd", 5.00))
    reward = round(random.uniform(min_usd, max_usd), 2)

    return {
        "winning_letter": winning_letter,
        "distractors": [d1, d2],
        "letters": sorted([winning_letter, d1, d2]),
        "block_display": block_display,
        "reward": Decimal(str(reward)),
    }


class SignalManager(SingleTargetChallengeManager):
    """Gestionnaire du mini-jeu Signal en mémoire vive et BDD MySQL."""

    event_name = "signal"
    config_key = "signal_challenge"
    target_key = "winning_letter"

    @classmethod
    def _create_new_challenge(cls) -> dict:
        return _create_new_challenge()

    @classmethod
    def _normalize_guess(cls, raw_guess: Any) -> str | None:
        if raw_guess is None:
            return None
        return str(raw_guess).strip().upper()
