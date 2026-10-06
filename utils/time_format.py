"""
Utilitaires de calcul et de formatage de durées temporelles pour Root Bot.

Fournit des fonctions réutilisables dans tout le bot pour afficher
des comptes à rebours et durées restantes sous forme claire et compacte (ex: '23h 46min 33s').
"""

from datetime import datetime, timezone
import re

_DURATION_TOKEN_REGEX = re.compile(
    r"(\d+)\s*(jours?|days?|j|d|heures?|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)",
    re.IGNORECASE,
)


def parse_duration(duration_str: str) -> int | None:
    """
    Parse une chaîne de durée en nombre total de secondes.

    Exemples supportés :
    - '30s', '45sec' -> 30, 45
    - '15m', '15min', '30 minutes' -> 900, 900, 1800
    - '2h', '1h30m', '1h 30min' -> 7200, 5400, 5400
    - '1j', '2d', '1d12h' -> 86400, 172800, 129600

    Renvoie None si la chaîne ne correspond pas à un format de durée valide.
    """
    if not duration_str or not isinstance(duration_str, str):
        return None

    s = duration_str.strip().lower()
    matches = list(_DURATION_TOKEN_REGEX.finditer(s))
    if not matches:
        return None

    # Vérifie qu'aucun caractère parasite hors espaces ne subsiste
    remaining = _DURATION_TOKEN_REGEX.sub("", s).strip()
    if remaining:
        return None

    total_seconds = 0
    for match in matches:
        val = int(match.group(1))
        unit = match.group(2)
        if unit.startswith(('j', 'd')):
            total_seconds += val * 86400
        elif unit.startswith('h'):
            total_seconds += val * 3600
        elif unit.startswith('m'):
            total_seconds += val * 60
        elif unit.startswith('s'):
            total_seconds += val

    return total_seconds


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


def to_utc_timestamp(dt) -> int:
    """
    Convertit un datetime (naïf supposé UTC ou timezone-aware) ou une chaîne ISO en timestamp Unix UTC (secondes).

    Indispensable pour l'affichage Discord <t:{ts}:R> / <t:{ts}:t> car Python traite
    les datetimes naïfs comme de l'heure locale lors de l'appel à .timestamp(), causant
    un décalage d'affichage dans Discord.
    """
    if dt is None:
        return 0
    if isinstance(dt, (int, float)):
        return int(dt)
    if isinstance(dt, str) and (dt.isdigit() or (dt.startswith('-') and dt[1:].isdigit())):
        return int(dt)
    if not hasattr(dt, "timestamp"):
        try:
            dt = datetime.fromisoformat(str(dt))
        except Exception:
            return 0
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

