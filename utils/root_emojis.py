"""
Root OS - Registre centralisé et résolution des emojis.

Prend en charge la résolution des emojis importés dans Discord (IDs réels et flags animés).
En cas d'asset non résolu, un repli silencieux propre (chaîne vide / pas d'icône) est appliqué.
"""

import logging
from typing import Any
import discord

logger = logging.getLogger(__name__)

# Noms des emojis dont l'utilisation de la version animée est obligatoire
ANIMATED_EMOJI_NAMES = {
    'root_terminal',
    'root_recolter',
    'root_scan',
    'root_retour',
    'root_alerte',
}

# Noms de tous les emojis officiels Root OS
ALL_EMOJI_NAMES = {
    'root_terminal',
    'root_ferme',
    'root_puissance',
    'root_production',
    'root_memoire',
    'root_temps',
    'root_recolter',
    'root_materiel',
    'root_logiciels',
    'root_operations',
    'root_journal',
    'root_alerte',
    'root_scan',
    'root_connexions',
    'root_retour',
    'root_bilan',
    'root_firewall',  # Ressource historique
}

DEFAULT_EMOJI_IDS: dict[str, tuple[int, bool]] = {
    'root_terminal': (1554180832938434651, True),
    'root_alerte': (1554180834662031510, True),
    'root_recolter': (1554180835958063226, True),
    'root_retour': (1554180838231375984, True),
    'root_scan': (1554180839665832028, True),
    'root_bilan': (1554180904329420893, False),
    'root_connexions': (1554180905763872878, False),
    'root_ferme': (1554180916161683458, False),
    'root_firewall': (1554180918154104984, False),
    'root_journal': (1554180919990952098, False),
    'root_logiciels': (1554180921656352839, False),
    'root_materiel': (1554180923690586153, False),
    'root_memoire': (1554180926999887983, False),
    'root_operations': (1554180929272942765, False),
    'root_production': (1554180930904522863, False),
    'root_puissance': (1554180932821454918, False),
    'root_temps': (1554181059011416205, False),
}

# Registre interne pré-rempli avec les identifiants Discord réels
_REGISTRY: dict[str, dict[str, Any]] = {
    name: {'id': eid, 'animated': anim}
    for name, (eid, anim) in DEFAULT_EMOJI_IDS.items()
}


def register_emoji(name: str, emoji_id: int, animated: bool | None = None) -> None:
    """Enregistre manuellement un emoji avec son ID Discord."""
    is_anim = animated if animated is not None else (name in ANIMATED_EMOJI_NAMES)
    _REGISTRY[name] = {
        'id': int(emoji_id),
        'animated': bool(is_anim),
    }


def init_emojis(bot_or_iterable: Any) -> None:
    """
    Détecte et synchronise automatiquement les emojis accessibles au bot.
    Privilégie la version animée pour les 5 noms obligatoires.
    """
    emojis = getattr(bot_or_iterable, 'emojis', None)
    if emojis is None and hasattr(bot_or_iterable, '__iter__'):
        emojis = bot_or_iterable
    if not emojis:
        return

    # Organise par nom
    by_name: dict[str, list[Any]] = {}
    for emo in emojis:
        name = getattr(emo, 'name', None)
        if name and name in ALL_EMOJI_NAMES:
            by_name.setdefault(name, []).append(emo)

    for name, list_emo in by_name.items():
        prefer_animated = (name in ANIMATED_EMOJI_NAMES)
        chosen = None
        # Recherche la variante correspondant au flag souhaité
        for emo in list_emo:
            if bool(getattr(emo, 'animated', False)) == prefer_animated:
                chosen = emo
                break
        if not chosen and list_emo:
            chosen = list_emo[0]

        if chosen:
            _REGISTRY[name] = {
                'id': int(chosen.id),
                'animated': bool(getattr(chosen, 'animated', False)),
            }
            logger.debug(
                "Emoji Root OS résolu : %s (id=%s, anim=%s)",
                name,
                chosen.id,
                _REGISTRY[name]['animated'],
            )


FALLBACK_EMOJIS = {
    'root_terminal': '>_',
    'root_ferme': '🖧',
    'root_puissance': '🔲',
    'root_firewall': '🛡️',
    'root_production': '📊',
    'root_memoire': '🖴',
    'root_temps': '⏱️',
    'root_recolter': '📥',
    'root_materiel': '⚙️',
    'root_logiciels': '💻',
    'root_operations': '⚔️',
    'root_journal': '📜',
    'root_alerte': '⚠️',
    'root_scan': '📡',
    'root_connexions': '🌐',
    'root_retour': '↩️',
    'root_bilan': '💵',
}


def get_emoji(name: str, space_after: bool = False) -> str:
    """
    Retourne la représentation textuelle Discord de l'emoji (<:name:id> ou <a:name:id>).
    Si l'emoji n'est pas encore résolu dans le cache du bot, utilise le repli stylisé correspondant.
    """
    info = _REGISTRY.get(name)
    if info:
        prefix = "a" if info['animated'] else ""
        formatted = f"<{prefix}:{name}:{info['id']}>"
        return f"{formatted} " if space_after else formatted
    fb = FALLBACK_EMOJIS.get(name, "")
    return f"{fb} " if (space_after and fb) else fb


def get_button_emoji(name: str) -> discord.PartialEmoji | str | None:
    """
    Retourne un objet discord.PartialEmoji pour les boutons interactifs,
    ou l'emoji unicode stylisé de repli.
    """
    info = _REGISTRY.get(name)
    if info:
        return discord.PartialEmoji(
            name=name,
            id=info['id'],
            animated=info['animated'],
        )
    return FALLBACK_EMOJIS.get(name)


def is_resolved(name: str) -> bool:
    """Vérifie si un emoji a été résolu."""
    return name in _REGISTRY


VANILLA_TO_ROOT_MAP: dict[str, str] = {
    '⚠️': 'root_alerte',
    '🚨': 'root_alerte',
    '🖧': 'root_ferme',
    '⛏️': 'root_ferme',
    '🔲': 'root_puissance',
    '🛡️': 'root_firewall',
    '📊': 'root_production',
    '📈': 'root_production',
    '🖴': 'root_memoire',
    '🧠': 'root_memoire',
    '⏱️': 'root_temps',
    '⏳': 'root_temps',
    '🕒': 'root_temps',
    '📥': 'root_recolter',
    '⚙️': 'root_materiel',
    '🛠️': 'root_materiel',
    '🔧': 'root_materiel',
    '🔨': 'root_materiel',
    '💻': 'root_logiciels',
    '🖥️': 'root_terminal',
    '⚔️': 'root_operations',
    '📜': 'root_journal',
    '📄': 'root_journal',
    '📡': 'root_scan',
    '🔍': 'root_scan',
    '🌐': 'root_connexions',
    '🚀': 'root_connexions',
    '↩️': 'root_retour',
    '⬅️': 'root_retour',
    '💵': 'root_bilan',
    '💰': 'root_bilan',
    '🪙': 'root_memoire',
    '🔥': 'root_puissance',
    '🤖': 'root_logiciels',
    '🎫': 'root_journal',
    '🛑': 'root_alerte',
    '🚫': 'root_alerte',
    '⛔': 'root_alerte',
    '❌': 'root_alerte',
    'ℹ️': 'root_terminal',
    '👋': 'root_terminal',
    '💳': 'root_bilan',
    '💎': 'root_memoire',
    '⭐': 'root_puissance',
    '🎯': 'root_operations',
    '⚡': 'root_puissance',
    '📦': 'root_materiel',
    '📬': 'root_journal',
    '💡': 'root_terminal',
    '🔹': 'root_terminal',
    '✅': 'root_recolter',
}


def replace_vanilla_emojis(content: str) -> str:
    """Remplace les emojis unicode vanilla par les emojis Discord personnalisés Root OS."""
    if not content:
        return content
    res = content
    for vanilla, root_name in VANILLA_TO_ROOT_MAP.items():
        if vanilla in res:
            res = res.replace(vanilla, get_emoji(root_name))
    return res

