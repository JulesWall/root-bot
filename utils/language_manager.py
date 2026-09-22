"""
Gestionnaire des préférences de langue des joueurs avec synchronisation cache/BDD.

Architecture de résolution linguistique :
1. Cache en mémoire (_cache) :
   Permet une lecture synchrone ultra-rapide O(1) lors de la génération de chaque texte
   dans utils.text sans bloquer sur une requête SQL.
2. Préchargement (Prefetch) :
   La classe de base GameCog appelle fetch_user_language() dès la réception d'une commande
   pour alimenter le cache avant la génération des messages.
3. Persistance SQL :
   La colonne 'lang' de la table 'players' conserve le choix définitif du joueur.
"""

import logging
import time

from data import SUPPORTED_LANGS
from game.db.database import Database

logger = logging.getLogger(__name__)

_db = Database()
# Cache mémoire {discord_id: (lang, expires_at)}
_cache: dict[int, tuple[str | None, float]] = {}
LANG_CACHE_TTL = 600.0  # 10 minutes


def invalidate_language_cache(user_id: int | None = None):
    """Purge le cache linguistique pour un joueur ou pour l'ensemble des joueurs."""
    if user_id is None:
        _cache.clear()
    else:
        _cache.pop(int(user_id), None)


def get_user_language(user_id: int | None) -> str | None:
    """Lecture synchrone non bloquante depuis le cache mémoire vérifiant le TTL."""
    if not user_id:
        return None
    entry = _cache.get(int(user_id))
    if entry is not None:
        lang, expires_at = entry
        if time.monotonic() < expires_at:
            return lang
    return None


async def fetch_user_language(user_id: int | None) -> str | None:
    """
    Interroge la base de données de manière asynchrone pour charger la langue du joueur si non en cache ou expirée.
    Alimente immédiatement le cache mémoire pour les lectures synchrones ultérieures.
    """
    if not user_id:
        return None
    uid = int(user_id)
    now = time.monotonic()
    entry = _cache.get(uid)
    if entry is not None:
        lang, expires_at = entry
        if now < expires_at:
            return lang

    try:
        from game.db.players import Player
        lang = await _db.run(lambda tx: Player.get_language(tx, uid), readonly=True)
        _cache[uid] = (lang, now + LANG_CACHE_TTL)
        return lang
    except Exception:
        return None


async def set_user_language(user_id: int, lang: str) -> str:
    """
    Définit la langue préférée d'un joueur en base et met à jour immédiatement le cache mémoire avec un nouveau TTL.
    Valide que la langue appartient à SUPPORTED_LANGS.
    """
    lang = (lang or "").strip().lower()
    if lang not in SUPPORTED_LANGS:
        raise ValueError(f"Langue non supportee: {lang}")
    from game.db.players import Player
    uid = int(user_id)
    await _db.run(lambda tx: Player.set_language(tx, uid, lang), locks=[f'player:{uid}'])
    _cache[uid] = (lang, time.monotonic() + LANG_CACHE_TTL)
    return lang


async def reset_user_language(user_id: int) -> bool:
    """Réinitialise la préférence linguistique à NULL en base et actualise immédiatement le cache."""
    try:
        from game.db.players import Player
        uid = int(user_id)
        await _db.run(lambda tx: Player.set_language(tx, uid, None), locks=[f'player:{uid}'])
        _cache[uid] = (None, time.monotonic() + LANG_CACHE_TTL)
        return True
    except Exception:
        return False

