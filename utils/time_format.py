"""
Utilitaires de calcul et de formatage de durées temporelles pour Root Bot.

Fournit des fonctions réutilisables dans tout le bot pour afficher
des comptes à rebours et durées restantes sous forme claire et compacte (ex: '23h 46min 33s').
"""

from datetime import datetime, timezone


def format_duration(seconds: int | float) -> str:
    """
    Formate un nombre de secondes en une chaîne lisible et compacte.

    Exemples :
    - 85593 -> '23h 46min 33s'
    - 905   -> '15min 5s'
    - 42    -> '42s'
    - 183604 -> '2j 3h 10min 4s'
    """
    total_seconds = max(0, int(seconds))
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}j")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}min")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def format_remaining_time(until, now=None) -> str:
    """
    Calcule et formate la durée restante entre maintenant (now) et une échéance future (until).

    Supporte les objets datetime (naïfs ou timezone-aware) ainsi que les chaînes ISO formatées.
    Si now n'est pas fourni, utilise l'horodatage UTC courant.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not hasattr(until, 'tzinfo'):
        until = datetime.fromisoformat(str(until))

    if until.tzinfo is not None and getattr(now, 'tzinfo', None) is None:
        until = until.replace(tzinfo=None)
    elif until.tzinfo is None and getattr(now, 'tzinfo', None) is not None:
        until = until.replace(tzinfo=now.tzinfo)

    seconds = (until - now).total_seconds()
    return format_duration(seconds)

