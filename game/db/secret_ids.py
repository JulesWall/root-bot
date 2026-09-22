"""
Identifiants secrets des joueurs (code à 6 chiffres, rotation globale UTC).

Chaque joueur possède un secret_id unique, visible uniquement sur son propre /network.
Tous les codes tournent ensemble à chaque frontière UTC de 12 h (00:00 et 12:00).
La future commande /hack ciblera ce code via Player.find_by_secret_id.
"""

import secrets
from datetime import datetime, timezone

from game.db.events import EventsDB
from game.game_error import GameError
from game.math_config import MathConfig

EVENT_NAME = 'secret_rotation'


def _config() -> dict:
    """Retourne le bloc de configuration secret_id de math.json."""
    return MathConfig.load()['secret_id']


def _as_utc_naive(value) -> datetime | None:
    """Normalise un datetime en UTC naïf (stockage DATETIME MySQL)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    return value


def unix_ts(value) -> int:
    """Convertit un datetime (UTC naïf ou aware) en timestamp Unix entier."""
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    return int(value)


def format_code(value) -> str:
    """Formate un entier en code à N chiffres, zéro-paddé."""
    digits = int(_config()['digits'])
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise GameError('invalid_secret_id')
    if number < 0 or number >= 10 ** digits:
        raise GameError('invalid_secret_id')
    return f'{number:0{digits}d}'


def normalize_code(code) -> str:
    """Valide un code saisi : exactement N chiffres, sinon invalid_secret_id."""
    digits = int(_config()['digits'])
    if code is None:
        raise GameError('invalid_secret_id')
    text = str(code).strip()
    if not text.isdigit() or len(text) != digits:
        raise GameError('invalid_secret_id')
    return text


def _taken_codes(tx) -> set:
    """Ensemble des secret_id actuellement attribués."""
    rows = tx.all('SELECT secret_id FROM players WHERE secret_id IS NOT NULL')
    return {str(row['secret_id']) for row in rows if row.get('secret_id')}


def generate_unique(tx, taken: set) -> str:
    """Tire un code unique (hors exclus et hors `taken`) via secrets.randbelow."""
    cfg = _config()
    digits = int(cfg['digits'])
    max_attempts = int(cfg['max_generate_attempts'])
    excluded = {str(item) for item in (cfg.get('excluded_codes') or [])}
    modulus = 10 ** digits
    for _ in range(max_attempts):
        code = format_code(secrets.randbelow(modulus))
        if code in excluded or code in taken:
            continue
        taken.add(code)
        return code
    raise GameError('secret_id_exhausted')


def ensure_player_secret(tx, row: dict) -> dict:
    """Assigne paresseusement un secret_id si la colonne est encore NULL."""
    existing = row.get('secret_id')
    if existing:
        row['secret_id'] = format_code(existing) if str(existing).isdigit() else existing
        return row
    from game.db.players import UpdatePlayer
    code = generate_unique(tx, _taken_codes(tx))
    updated = UpdatePlayer.set(tx, int(row['discord_id']), secret_id=code)
    if updated:
        row.update(updated)
    row['secret_id'] = code
    return row


def next_rotation_at(now) -> datetime:
    """Prochaine frontière UTC : ((unix_now // interval) + 1) * interval."""
    interval = int(_config()['rotation_interval_seconds'])
    next_ts = ((unix_ts(now) // interval) + 1) * interval
    return datetime.fromtimestamp(next_ts, tz=timezone.utc).replace(tzinfo=None)


def get_epoch(tx) -> dict | None:
    """Lit la ligne events event='secret_rotation'."""
    return EventsDB.get(tx, EVENT_NAME)


def save_epoch(tx, next_at: datetime) -> dict:
    """Persiste le prochain horodatage de rotation globale."""
    return EventsDB.save(tx, EVENT_NAME, next_at)


def rotate_all_if_due(tx) -> dict:
    """Régénère tous les secret_id si next_at est échu (un seul cycle même en retard)."""
    now = _as_utc_naive(tx.now) or tx.now
    epoch = get_epoch(tx)
    stored_next = _as_utc_naive(epoch['next_at']) if epoch else None
    if stored_next is not None and stored_next > now:
        return {'rotated': False, 'count': 0, 'next_at': stored_next}

    rows = tx.all('SELECT discord_id, secret_id FROM players FOR UPDATE')
    taken: set = set()
    assignments = []
    for row in rows:
        code = generate_unique(tx, taken)
        assignments.append((int(row['discord_id']), code))

    tx.execute('UPDATE players SET secret_id = NULL')
    from game.db.players import UpdatePlayer
    for discord_id, code in assignments:
        UpdatePlayer.set(tx, discord_id, secret_id=code)

    future = next_rotation_at(now)
    save_epoch(tx, future)
    return {'rotated': True, 'count': len(assignments), 'next_at': future}


def rotate_player_secret(tx, discord_id: int) -> str:
    """Régénère immédiatement le secret_id d'un joueur unique (ex: après avoir subi une attaque)."""
    current_row = tx.one('SELECT secret_id FROM players WHERE discord_id = %s', (int(discord_id),))
    old_code = current_row.get('secret_id') if current_row else None

    # Mettre à NULL temporairement pour éviter tout conflit d'unicité SQL
    tx.execute('UPDATE players SET secret_id = NULL WHERE discord_id = %s', (int(discord_id),))
    taken = _taken_codes(tx)
    if old_code:
        taken.add(str(old_code))  # Évite de réattribuer le même code immédiatement

    code = generate_unique(tx, taken)
    from game.db.players import UpdatePlayer
    UpdatePlayer.set(tx, int(discord_id), secret_id=code)
    return code

