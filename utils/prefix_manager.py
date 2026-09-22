"""
Gestionnaire et validateur des préfixes textuels par serveur (guild_prefixes).

Fournit deux fonctions asynchrones de haut niveau :
1. get_prefix_async(guild_id) : Lit le préfixe configuré en base avec repli robuste sur data.DEFAULT_PREFIX.
2. set_prefix(guild_id, new_prefix) : Valide la syntaxe (1 à 32 caractères non blancs) et persiste le nouveau préfixe.
"""

import logging
import time

import data
from game.db.prefix_db import PrefixDB

MAX_PREFIX_LENGTH = 32
PREFIX_CACHE_TTL = 600.0  # 10 minutes
logger = logging.getLogger(__name__)

_prefix_db = PrefixDB()
# Cache mémoire {guild_id: (prefix, expires_at)}
_prefix_cache: dict[int, tuple[str, float]] = {}


def invalidate_prefix_cache(guild_id: int | None = None):
    """Purge le cache de préfixe pour un serveur donné ou pour tous les serveurs."""
    if guild_id is None:
        _prefix_cache.clear()
    else:
        _prefix_cache.pop(int(guild_id), None)


async def get_prefix_async(guild_id: int) -> str:
    """
    Récupère de façon asynchrone le préfixe propre à un serveur avec cache TTL.
    En cas de problème d'accès à la BDD, retourne data.DEFAULT_PREFIX sans planter.
    """
    gid = int(guild_id)
    now = time.monotonic()
    if gid in _prefix_cache:
        cached_prefix, expires_at = _prefix_cache[gid]
        if now < expires_at:
            return cached_prefix

    try:
        prefix = await _prefix_db.fetch(gid)
        _prefix_cache[gid] = (prefix, now + PREFIX_CACHE_TTL)
        return prefix
    except Exception:
        logger.warning("Impossible de lire le préfixe pour le serveur %s, utilisation du défaut.", gid)
        return data.DEFAULT_PREFIX


async def set_prefix(guild_id: int, new_prefix: str):
    """
    Valide et enregistre un nouveau préfixe de serveur, et actualise immédiatement le cache.
    
    Règles de validation :
    - Longueur comprise entre 1 et 32 caractères.
    - Aucun caractère d'espacement (espace, tabulation, saut de ligne).
    Lève ValueError si la chaîne n'est pas conforme.
    """
    new_prefix = new_prefix.strip()
    if not new_prefix or len(new_prefix) > MAX_PREFIX_LENGTH or any(char.isspace() for char in new_prefix):
        raise ValueError("Le prefixe doit contenir de 1 a 32 caracteres sans espace.")
    gid = int(guild_id)
    await _prefix_db.save(gid, new_prefix)
    # Actualisation immédiate du cache avec un nouveau TTL
    _prefix_cache[gid] = (new_prefix, time.monotonic() + PREFIX_CACHE_TTL)

