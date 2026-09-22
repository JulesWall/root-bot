"""
Gestionnaire métier du mini-jeu communautaire Buffer (/buffer).

Architecture des données (Zéro fichier JSON) :
1. Base de données MySQL (table 'events' avec event='buffer') :
   - Source de vérité persistante pour le cooldown (next_at), le dernier gagnant (last_found_by),
     le serveur d'origine (last_found_on) et la récompense en USD (last_reward).
2. Mémoire vive (_active_challenge) :
   - 6 fragments numérotés de 1 à 6 contenant chacun une lettre majuscule distincte.
   - Les fragments sont affichés dans le désordre (garanti jamais pré-trié).
   - Code cible : Reconstitution du mot de 6 lettres selon l'ordre des index 1 à 6.
   - Validation atomique (un seul gagnant garanti même en cas de réponses simultanées).
   - Aucun délai entre les propositions erronées.
"""

from decimal import Decimal
import random
import string
from typing import Any

from game.base_challenge_manager import SingleTargetChallengeManager
from game.math_config import MathConfig

FRAGMENT_COUNT = 6


def _create_new_challenge() -> dict:
    """
    Génère un nouveau défi actif de buffer :
    - 6 fragments numérotés de 1 à 6 avec 6 lettres majuscules distinctes.
    - Ordre d'affichage mélangé et garanti non pré-trié.
    - Code cible : mot de 6 lettres reconstitué dans l'ordre 1 à 6.
    """
    settings = MathConfig.load().get("buffer_challenge", {})

    # 6 lettres majuscules distinctes
    letters = random.sample(string.ascii_uppercase, FRAGMENT_COUNT)
    fragment_map = {i + 1: letters[i] for i in range(FRAGMENT_COUNT)}

    # Code cible ordonné selon 1..6
    target = "".join(fragment_map[i] for i in range(1, FRAGMENT_COUNT + 1))

    # Ordre d'affichage aléatoire garanti jamais trié
    displayed_order = list(range(1, FRAGMENT_COUNT + 1))
    while displayed_order == list(range(1, FRAGMENT_COUNT + 1)):
        random.shuffle(displayed_order)

    displayed_fragments = [f"{num}:{fragment_map[num]}" for num in displayed_order]
    buffer_display = "  ".join(displayed_fragments)

    min_usd = float(settings.get("reward_min_usd", 1.50))
    max_usd = float(settings.get("reward_max_usd", 5.00))
    reward = round(random.uniform(min_usd, max_usd), 2)

    return {
        "fragment_map": fragment_map,
        "displayed_order": displayed_order,
        "buffer_display": buffer_display,
        "target": target,
        "reward": Decimal(str(reward)),
    }


class BufferManager(SingleTargetChallengeManager):
    """Gestionnaire du mini-jeu Buffer en mémoire vive et BDD MySQL."""

    event_name = "buffer"
    config_key = "buffer_challenge"
    target_key = "target"

    @classmethod
    def _create_new_challenge(cls) -> dict:
        return _create_new_challenge()

    @classmethod
    def _normalize_guess(cls, raw_guess: Any) -> str | None:
        if raw_guess is None:
            return None
        return str(raw_guess).replace(" ", "").upper().strip()
