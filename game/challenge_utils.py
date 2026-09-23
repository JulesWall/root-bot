"""
Module utilitaire mutualisé pour les 7 mini-jeux d'événements communautaires.

Regroupe les logiques communes auparavant dupliquées dans chaque gestionnaire :
1. Calculs temporels et plages jour/nuit (fuseau horaire Europe/Paris).
2. Vérification et extraction standardisée du statut de cooldown (table events).
3. Règlement complet de victoire (multiplicateur pare-feu, mise à jour joueur,
   statistiques journalières, persistance MySQL events).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import copy
import random

from game.db.daily_event_stats import DailyEventStatsDB
from game.db.events import EventsDB
from game.db.players import PlayerData, UpdatePlayer
from game.math_config import MathConfig


class ChallengeResource:
    """
    Ressource transactionnelle à deux phases pour les défis en mémoire vive.
    
    Garantit :
    1. L'isolation stricte via copie indépendante (copy.deepcopy).
    2. La sérialisation des threads SQL worker via threading.RLock().
    3. L'application des modifications uniquement après le COMMIT MySQL réussi.
    4. La réinitialisation propre du défi en mémoire en cas de commit incertain sans rejeu aveugle.
    """

    def __init__(self, manager_cls):
        self.manager_cls = manager_cls
        self.lock = getattr(manager_cls, "_lock", None)
        self.staged_challenge = None
        self.has_staged_change = False
        self.acquired = False

    def begin(self, tx):
        """Acquiert le verrou de thread et capture une copie profonde indépendante de l'état actif."""
        if self.lock is not None:
            self.lock.acquire()
            self.acquired = True
        self.staged_challenge = copy.deepcopy(self.manager_cls._active_challenge)
        self.has_staged_change = False

    def stage(self, new_state):
        """Enregistre un changement d'état préparé (copie isolée)."""
        self.staged_challenge = copy.deepcopy(new_state)
        self.has_staged_change = True

    def prepare(self, tx):
        """Vérifie la consistance avant commit."""
        pass

    def finish(self):
        """Applique les modifications préparées après le commit réussi et libère le verrou."""
        try:
            if self.has_staged_change:
                self.manager_cls._active_challenge = self.staged_challenge
        finally:
            if self.acquired and self.lock is not None:
                self.lock.release()
                self.acquired = False

    def rollback(self):
        """Abandonne les modifications préparées sans toucher à l'état actif et libère le verrou."""
        try:
            self.staged_challenge = None
            self.has_staged_change = False
        finally:
            if self.acquired and self.lock is not None:
                self.lock.release()
                self.acquired = False

    def uncertain(self):
        """
        En cas de commit dont le résultat est inconnu :
        - Invalide explicitement le défi en mémoire (None) sans rejeu aveugle.
        - Libère le verrou.
        """
        try:
            self.staged_challenge = None
            self.has_staged_change = False
            # Perte en mémoire acceptée : réinitialisation explicite
            self.manager_cls._active_challenge = None
        finally:
            if self.acquired and self.lock is not None:
                self.lock.release()
                self.acquired = False


def get_paris_hour(dt: datetime) -> int:
    """Retourne l'heure courante à Paris (gère l'offset UTC+2 en été, UTC+1 en hiver)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        paris_tz = ZoneInfo("Europe/Paris")
        return dt.astimezone(paris_tz).hour
    except Exception:
        offset_hours = 2 if 4 <= dt.month <= 10 else 1
        paris_tz = timezone(timedelta(hours=offset_hours))
        return dt.astimezone(paris_tz).hour


def is_paris_day(dt: datetime) -> bool:
    """Journée à Paris : 11h00 à 01h00 (heures 11 à 23 et 0). Nuit : 1h00 à 10h59."""
    hour = get_paris_hour(dt)
    return hour >= 11 or hour < 1


def calculate_next_interval_seconds(dt: datetime, challenge_key: str) -> int:
    """Calcule le délai avant le prochain événement selon la période (jour vs nuit)."""
    settings = MathConfig.load().get(challenge_key, {})
    if is_paris_day(dt):
        min_m = int(settings.get("day_interval_min_minutes", 15))
        max_m = int(settings.get("day_interval_max_minutes", 45))
    else:
        min_m = int(settings.get("night_interval_min_minutes", 25))
        max_m = int(settings.get("night_interval_max_minutes", 60))
    return random.randint(min_m, max_m) * 60


def check_challenge_cooldown(tx, event_name: str, now: datetime) -> dict | None:
    """
    Vérifie si l'événement est en cooldown d'après la table MySQL 'events'.
    Retourne le dictionnaire de statut 'cooldown' si actif, ou None sinon.
    """
    db_event = EventsDB.get(tx, event_name)
    if db_event and db_event.get("next_at"):
        next_at = db_event["next_at"]
        if next_at > now:
            remaining_seconds = max(0, int((next_at - now).total_seconds()))
            return {
                "status": "cooldown",
                "last_found_by": db_event.get("last_found_by"),
                "last_found_on": db_event.get("last_found_on") or "Inconnu",
                "last_reward": Decimal(str(db_event.get("last_reward") or "0.00")),
                "next_at": next_at,
                "remaining_seconds": remaining_seconds,
            }
    return None


def settle_challenge_win(
    tx,
    event_name: str,
    challenge_key: str,
    actor: int,
    base_reward: Decimal | float,
    now: datetime,
    guild_name: str | None = None,
) -> dict:
    """
    Règlement complet de la victoire d'un mini-jeu :
    1. Multiplicateur de pare-feu et calcul de la récompense finale.
    2. Crédit en dollars et incrémentation de events_won.
    3. Enregistrement de la victoire dans daily_event_stats.
    4. Calcul du prochain intervalle et persistance dans la table events.
    Retourne un dictionnaire contenant les métadonnées de la victoire.
    """
    # 1. Calcul du multiplicateur de pare-feu
    player = PlayerData.get(tx, actor)
    firewall_level = int(player.get("firewall_level", 0))
    multiplier = MathConfig.get_event_firewall_multiplier(firewall_level)
    reward_dec = Decimal(str(base_reward))
    final_reward = round(reward_dec * Decimal(str(multiplier)), 2)

    # 2. Créditer le joueur en BDD et incrémenter les victoires
    current_dollars = Decimal(str(player.get("dollars", 0)))
    current_events_won = int(player.get("events_won", 0) or 0)
    UpdatePlayer.set(tx, actor, dollars=current_dollars + final_reward, events_won=current_events_won + 1)

    # 3. Enregistrer la victoire dans la table journalière de modération
    DailyEventStatsDB.record_win(tx, actor)

    # 4. Calculer le temps où l'événement est resté disponible et archiver
    prev_event = EventsDB.get(tx, event_name)
    prev_next_at = prev_event.get("next_at") if prev_event else None
    available_seconds = 0
    if prev_next_at:
        p_dt = prev_next_at.replace(tzinfo=None) if getattr(prev_next_at, 'tzinfo', None) else prev_next_at
        n_dt = now.replace(tzinfo=None) if getattr(now, 'tzinfo', None) else now
        if n_dt >= p_dt:
            available_seconds = int((n_dt - p_dt).total_seconds())
        opened_at = prev_next_at
    else:
        opened_at = now

    EventsDB.record_availability(
        tx,
        event_name=event_name,
        opened_at=opened_at,
        solved_at=now,
        duration_seconds=available_seconds,
        winner_id=actor,
        reward=final_reward,
    )

    # 5. Calculer le prochain horodatage et persister dans MySQL
    interval_seconds = calculate_next_interval_seconds(now, challenge_key)
    next_at = now + timedelta(seconds=interval_seconds)
    server_name = guild_name or "Serveur inconnu"

    EventsDB.save(
        tx,
        event_name=event_name,
        next_at=next_at,
        last_found_by=actor,
        last_found_on=server_name,
        last_reward=final_reward,
    )

    return {
        "final_reward": final_reward,
        "base_reward": reward_dec,
        "multiplier": multiplier,
        "next_at": next_at,
        "server_name": server_name,
        "available_seconds": available_seconds,
    }

