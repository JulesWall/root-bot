"""
Module de gestion et résolution des emojis et emotes Root OS.

Centralise les noms d'emojis personnalisés (root_*), leurs équivalents Unicode de repli,
et la logique d'extraction priorisant les versions animées utilisables par le bot Discord.
Conforme aux spécifications visuelles de design/ROOT_OS_GAME_DESIGN.md et embed.md.
"""

from typing import Any
import discord

# Replis textuels Unicode garantissant la lisibilité lorsque les emojis personnalisés
# ne sont pas disponibles sur le serveur ou dans le contexte d'exécution.
FALLBACKS: dict[str, str] = {
    "terminal": "🖥️",
    "firewall": "🛡️",
    "ferme": "🗄️",
    "puissance": "⚙️",
    "production": "📊",
    "memoire": "💾",
    "temps": "⏱️",
    "recolter": "📥",
    "materiel": "⚙️",
    "logiciels": "💻",
    "operations": "📋",
    "journal": "📄",
    "alerte": "⚠️",
    "scan": "🔍",
    "hack": "⚔️",
    "connexions": "🌐",
    "retour": "↩️",
    "bilan": "📊",
    "dollars": "💵",
}


class EmojiDict(dict):
    """Dictionnaire d'emojis avec repli par défaut pour éviter tout KeyError."""

    def __missing__(self, key: str) -> str:
        return FALLBACKS.get(key, "⚙️")


def select_emojis(emojis) -> dict[str, Any]:
    """Résout les emojis personnalisés root_* en priorisant les versions animées utilisables."""
    selected = {}
    if not emojis:
        return selected
    for emoji in sorted(emojis, key=lambda item: (getattr(item, 'animated', False), getattr(item, 'id', 0))):
        name = getattr(emoji, 'name', '')
        if name.startswith("root_"):
            clean_name = name.removeprefix("root_")
            if clean_name in FALLBACKS:
                is_usable = getattr(emoji, 'is_usable', None)
                if is_usable is None or is_usable():
                    selected[clean_name] = emoji
    return selected


def get_emoji_map(ctx_or_guild) -> dict[str, Any]:
    """Extrait et résout les emojis root personnalisés à partir d'un contexte, guild ou bot."""
    guild = getattr(ctx_or_guild, 'guild', None) if not isinstance(ctx_or_guild, discord.Guild) else ctx_or_guild
    if guild and hasattr(guild, 'emojis'):
        try:
            mapped = select_emojis(guild.emojis)
            if mapped:
                return mapped
        except Exception:
            pass

    bot = getattr(ctx_or_guild, 'bot', None)
    if bot and hasattr(bot, 'emojis'):
        try:
            mapped = select_emojis(bot.emojis)
            if mapped:
                return mapped
        except Exception:
            pass

    return {}


def root_emoji(ctx_or_guild, name: str) -> str:
    """Retourne la représentation textuelle Discord d'un emoji root ou son repli Unicode."""
    emap = get_emoji_map(ctx_or_guild)
    if name in emap:
        return str(emap[name])
    return FALLBACKS.get(name, "⚙️")


def get_root_emojis(ctx_or_guild) -> dict[str, str]:
    """Retourne un dictionnaire associant chaque nom d'emoji root à sa chaîne Discord (<...:id>) ou son repli Unicode."""
    emap = get_emoji_map(ctx_or_guild)
    result = {}
    for name, fallback in FALLBACKS.items():
        if name in emap:
            result[name] = str(emap[name])
        else:
            result[name] = fallback
    return EmojiDict(result)

