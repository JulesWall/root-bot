"""
Gestionnaire métier du mini-jeu communautaire Packet (/packet).

Architecture des données (Zéro fichier JSON) :
1. Base de données MySQL (table 'events' avec event='packet') :
   - Source de vérité persistante pour le cooldown (next_at), le dernier gagnant (last_found_by),
     le serveur d'origine (last_found_on) et la récompense en USD (last_reward).
2. Mémoire vive (_active_challenge) :
   - Un numéro manquant parmi 1 à 10.
   - Les 9 autres numéros affichés une seule fois chacun, dans le désordre (garanti non pré-trié).
   - Validation atomique (un seul gagnant garanti même en cas de réponses simultanées).
   - Aucun délai entre les propositions erronées.
"""

from decimal import Decimal
import random
from typing import Any

from game.base_challenge_manager import SingleTargetChallengeManager
from game.math_config import MathConfig

PACKET_MIN = 1
PACKET_MAX = 10


def _create_new_challenge() -> dict:
    """
    Génère un nouveau défi actif de paquet :
    - 1 numéro manquant aléatoire parmi 1 à 10.
    - 9 autres numéros ordonnés aléatoirement sans tri préalable.
    """
    settings = MathConfig.load().get("packet_challenge", {})
    missing_packet = random.randint(PACKET_MIN, PACKET_MAX)
    available_packets = [i for i in range(PACKET_MIN, PACKET_MAX + 1) if i != missing_packet]

    sorted_packets = list(available_packets)
    while True:
        random.shuffle(available_packets)
        if available_packets != sorted_packets:
            break

    block_display = " ".join(f"`[{p:02d}]`" for p in available_packets)

    min_usd = float(settings.get("reward_min_usd", 1.50))
    max_usd = float(settings.get("reward_max_usd", 5.00))
    reward = round(random.uniform(min_usd, max_usd), 2)

    return {
        "missing_packet": missing_packet,
        "remaining": available_packets,
        "block_display": block_display,
        "reward": Decimal(str(reward)),
    }


class PacketManager(SingleTargetChallengeManager):
    """Gestionnaire du mini-jeu Packet en mémoire vive et BDD MySQL."""

    event_name = "packet"
    config_key = "packet_challenge"
    target_key = "missing_packet"

    @classmethod
    def _create_new_challenge(cls) -> dict:
        return _create_new_challenge()

    @classmethod
    def _normalize_guess(cls, raw_guess: Any) -> int | None:
        return int(raw_guess) if raw_guess is not None else None
