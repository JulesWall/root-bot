"""
Gestionnaire métier du mini-jeu communautaire Décryptage (/decode).

Architecture des données (Zéro fichier JSON) :
1. Base de données MySQL (table 'events' avec event='decode') :
   - Source de vérité persistante pour le cooldown (next_at), le dernier gagnant (last_found_by),
     le serveur d'origine (last_found_on) et la récompense en USD (last_reward).
2. Mémoire vive (_active_challenge) :
   - Grille 4x4 de 16 lettres distinctes aléatoires (lignes A-D, colonnes 1-4).
   - Séquence ordonnée de 4 coordonnées distinctes à décoder.
   - Mot cible résultant des 4 lettres relevées.
   - Validation atomique (un seul gagnant garanti, même en cas de réponses concurrentes).
   - Aucun cooldown entre les tentatives erronées.
"""

from decimal import Decimal
import random
import string
from typing import Any

from game.base_challenge_manager import SingleTargetChallengeManager
from game.math_config import MathConfig


# 16 coordonnées de la grille 4x4 (A1 à D4)
COORDINATES = tuple(f"{r}{c}" for r in ("A", "B", "C", "D") for c in (1, 2, 3, 4))


def _build_grid_display(grid: dict) -> str:
    """Formate la grille 4x4 pour un affichage monospacé compact et lisible sur mobile."""
    rows = ["    1   2   3   4"]
    for r in ("A", "B", "C", "D"):
        cells = "   ".join(grid[f"{r}{c}"] for c in (1, 2, 3, 4))
        rows.append(f"{r}   {cells}")
    return "\n".join(rows)


def _create_new_challenge() -> dict:
    """Génère un nouveau défi actif de décryptage."""
    settings = MathConfig.load().get("decode_challenge", {})

    # 16 lettres distinctes tirées aléatoirement
    letters = random.sample(string.ascii_uppercase, 16)
    grid = dict(zip(COORDINATES, letters))

    # Séquence de 4 coordonnées distinctes
    sequence = random.sample(COORDINATES, 4)
    target = "".join(grid[coord] for coord in sequence)

    # Récompense en USD
    min_usd = float(settings.get("reward_min_usd", 1.50))
    max_usd = float(settings.get("reward_max_usd", 5.00))
    reward = round(random.uniform(min_usd, max_usd), 2)

    return {
        "grid": grid,
        "grid_display": _build_grid_display(grid),
        "sequence": sequence,
        "sequence_str": " · ".join(sequence),
        "target": target,
        "reward": Decimal(str(reward)),
    }


class DecodeManager(SingleTargetChallengeManager):
    """Gestionnaire du mini-jeu Décryptage en mémoire vive et BDD MySQL."""

    event_name = "decode"
    config_key = "decode_challenge"
    target_key = "target"

    @classmethod
    def _create_new_challenge(cls) -> dict:
        return _create_new_challenge()

    @classmethod
    def _normalize_guess(cls, raw_guess: Any) -> str | None:
        if raw_guess is None:
            return None
        return str(raw_guess).replace(" ", "").upper().strip()
