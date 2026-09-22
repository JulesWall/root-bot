"""
Gestionnaire métier du mini-jeu communautaire Anomaly (/anomaly).

Architecture des données (Zéro fichier JSON) :
1. Base de données MySQL (table 'events' avec event='anomaly') :
   - Source de vérité persistante pour le cooldown (next_at), le dernier gagnant (last_found_by),
     le serveur d'origine (last_found_on) et la récompense en USD (last_reward).
2. Mémoire vive (_active_challenge) :
   - Bloc de 10 lignes de 16 lettres majuscules sans ligne vide.
   - Exactement un seul chiffre parasite (0-9) dissimulé sur une seule ligne.
   - Cible : numéro de ligne compris entre 1 et 10 (comptage de haut en bas).
   - Validation atomique (un seul gagnant garanti même en cas de réponses simultanées).
   - Aucun délai entre les propositions erronées.
"""

from decimal import Decimal
import random
import string
from typing import Any

from game.base_challenge_manager import SingleTargetChallengeManager
from game.math_config import MathConfig


# Paramètres géométriques du bloc d'anomalie
LINE_COUNT = 10
LINE_LENGTH = 16


def _create_new_challenge() -> dict:
    """
    Génère un nouveau défi actif d'anomalie :
    - Exactement 10 lignes de 16 lettres majuscules.
    - Sur une seule ligne (1 à 10), une seule lettre est remplacée par un chiffre (0-9).
    - Exactement 1 chiffre dans tout le bloc.
    """
    settings = MathConfig.load().get("anomaly_challenge", {})

    target_line = random.randint(1, LINE_COUNT)  # Ligne 1 à 10 (1-indexée)
    target_digit = str(random.randint(0, 9))
    col_idx = random.randint(0, LINE_LENGTH - 1)  # Colonne 0 à 15

    lines = []
    for line_num in range(1, LINE_COUNT + 1):
        letters = [random.choice(string.ascii_uppercase) for _ in range(LINE_LENGTH)]
        if line_num == target_line:
            letters[col_idx] = target_digit
        lines.append("".join(letters))

    block_display = "\n".join(lines)

    min_usd = float(settings.get("reward_min_usd", 1.50))
    max_usd = float(settings.get("reward_max_usd", 5.00))
    reward = round(random.uniform(min_usd, max_usd), 2)

    return {
        "target_line": target_line,
        "target_digit": target_digit,
        "line": target_line,
        "digit": target_digit,
        "block_display": block_display,
        "reward": Decimal(str(reward)),
    }


class AnomalyManager(SingleTargetChallengeManager):
    """Gestionnaire du mini-jeu Anomaly en mémoire vive et BDD MySQL."""

    event_name = "anomaly"
    config_key = "anomaly_challenge"
    target_key = "target_line"

    @classmethod
    def _create_new_challenge(cls) -> dict:
        return _create_new_challenge()

    @classmethod
    def _normalize_guess(cls, raw_guess: Any) -> int | None:
        return int(raw_guess) if raw_guess is not None else None
