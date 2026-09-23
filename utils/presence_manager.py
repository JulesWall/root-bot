"""
Gestionnaire dynamique de présence Discord et compte à rebours de lancement de la bêta.

Architecture :
1. Calcul horaire dynamique :
   - Détermine le nombre d'heures restantes jusqu'à l'ouverture de la bêta.
   - Formate le texte selon la spécification :
     • x > 1 : "Ouverture de la beta dans {x} heures"
     • x == 1 : "Ouverture de la beta dans 1 heure"
     • x <= 0 : "Beta ouverte !"
     • Mode bêta inactif ou non configuré : repli sur data.BOT_NAME ("Root").
2. Multi-sources de configuration de la cible :
   - Variable en mémoire (mise à jour instantanée par commande admin).
   - Fichier persistant data/beta_launch.json (survit aux redémarrages).
   - Variable d'environnement BETA_LAUNCH_AT (dans .env).
   - Section "beta.launch_at" dans data/math.json.
3. Actualisation continue (@tasks.loop) :
   - Met à jour la présence Discord chaque minute.
   - Préserve le statut de maintenance (DND si maintenance active, Online sinon).
   - Évite les appels Gateway redondants si l'état n'a pas changé.
"""

import json
import logging
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import tasks

import data
from utils.check import Check

logger = logging.getLogger(__name__)

BETA_LAUNCH_FILE = data.DATA_DIR / "beta_launch.json"

_target_datetime: datetime | None = None
_last_activity_text: str | None = None
_last_status: discord.Status | None = None
_presence_task: tasks.Loop | None = None


def parse_target_datetime(value: str | int | float | None, now: datetime | None = None) -> datetime | None:
    """
    Convertit une entrée utilisateur, variable .env ou configuration en datetime localisé.

    Formats supportés :
    - Relatif : "+24h", "24h", "12 heures", "+5h" (calcule now + heures)
    - Heure de la journée : "18:00", "18h", "18h30" (aujourd'hui ou demain si dépassée)
    - Timestamp Unix : "1790186400"
    - Format ISO 8601 : "2026-09-23T18:00:00", "2026-09-23 18:00:00"
    - Formats de date standards : "23/09/2026 18:00"
    """
    if value is None:
        return None
    val = str(value).strip()
    if not val:
        return None

    now = now or datetime.now().astimezone()

    # 1. Format relatif "+24h" / "24h"
    m_rel = re.match(r"^\+?(\d+)\s*h(?:eures?)?$", val, re.IGNORECASE)
    if m_rel:
        hours = int(m_rel.group(1))
        return now + timedelta(hours=hours)

    # 2. Heure de la journée ("18:00", "18h30")
    m_tod = re.match(r"^(\d{1,2})[:h](\d{2})?(?::(\d{2}))?$", val, re.IGNORECASE)
    if m_tod:
        h = int(m_tod.group(1))
        mn = int(m_tod.group(2) or 0)
        sec = int(m_tod.group(3) or 0)
        if 0 <= h < 24 and 0 <= mn < 60 and 0 <= sec < 60:
            target = now.replace(hour=h, minute=mn, second=sec, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target

    # 3. Timestamp Unix
    if val.isdigit() and len(val) >= 9:
        try:
            return datetime.fromtimestamp(int(val), tz=now.tzinfo)
        except (ValueError, OverflowError):
            pass

    # 4. Format ISO 8601
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=now.tzinfo)
        return dt
    except Exception:
        pass

    # 5. Formats de date/heure classiques
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            dt = datetime.strptime(val, fmt)
            return dt.replace(tzinfo=now.tzinfo)
        except Exception:
            pass

    return None


def _save_target_to_file(target: datetime, raw_input: str) -> None:
    """Enregistre de manière atomique la cible de lancement dans data/beta_launch.json."""
    try:
        data.DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "target_iso": target.isoformat(),
            "raw_input": raw_input,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        temp_file = BETA_LAUNCH_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.replace(BETA_LAUNCH_FILE)
    except Exception:
        logger.exception("Échec d'enregistrement de %s", BETA_LAUNCH_FILE)


def get_beta_launch_target() -> datetime | None:
    """
    Résout la date/heure cible de lancement de la bêta par ordre de priorité :
    1. Variable en mémoire (_target_datetime définie via commande à chaud).
    2. Variable d'environnement BETA_LAUNCH_AT / BETA_LAUNCH_TIME / BETA_LAUNCH_HOURS (rechargée dynamiquement depuis .env).
    3. Fichier data/beta_launch.json.
    4. Configuration math.json ("beta.launch_at").
    """
    global _target_datetime
    if _target_datetime is not None:
        return _target_datetime

    # Rechargement dynamique de .env en production pour prendre en compte les modifications à chaud
    is_testing = (
        "PYTEST_CURRENT_TEST" in os.environ
        or "unittest" in sys.modules
        or any("test" in arg.lower() for arg in sys.argv)
    )
    if not is_testing:
        try:
            from dotenv import load_dotenv
            load_dotenv(data.BASE_DIR / ".env", override=True)
        except Exception:
            pass

    # 2. Variable d'environnement (.env)
    env_val = os.getenv("BETA_LAUNCH_AT") or os.getenv("BETA_LAUNCH_TIME") or os.getenv("BETA_LAUNCH_HOURS")
    if env_val:
        env_val = env_val.strip()
        # Si beta_launch.json correspond déjà à la valeur exacte configurée dans .env (pour ancrer les formats relatifs ex: 24h)
        if BETA_LAUNCH_FILE.exists():
            try:
                with open(BETA_LAUNCH_FILE, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if content.get("raw_input") == env_val:
                        iso_str = content.get("target_iso")
                        if iso_str:
                            dt = datetime.fromisoformat(iso_str)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                            return dt
            except Exception:
                pass

        # Nouvelle valeur dans .env ou pas encore ancrée : on parse et on synchronise
        dt = parse_target_datetime(env_val)
        if dt:
            _save_target_to_file(dt, env_val)
            return dt

    # 3. Lecture depuis data/beta_launch.json (si aucune valeur dans .env mais défini par commande)
    if BETA_LAUNCH_FILE.exists():
        try:
            with open(BETA_LAUNCH_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                iso_str = content.get("target_iso")
                if iso_str:
                    dt = datetime.fromisoformat(iso_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                    return dt
        except Exception:
            logger.warning("Échec de lecture de %s", BETA_LAUNCH_FILE, exc_info=True)

    # 4. Configuration math.json
    try:
        from game.math_config import MathConfig
        cfg = MathConfig.load()
        math_val = cfg.get("beta", {}).get("launch_at")
        if math_val:
            dt = parse_target_datetime(math_val)
            if dt:
                return dt
    except Exception:
        pass

    return None


def set_beta_launch_target(value: str | int | float | datetime) -> datetime:
    """Définit une nouvelle date cible pour le lancement de la bêta et la persiste."""
    global _target_datetime
    if isinstance(value, datetime):
        target = value
        if target.tzinfo is None:
            target = target.replace(tzinfo=datetime.now().astimezone().tzinfo)
    else:
        target = parse_target_datetime(value)
        if not target:
            raise ValueError(f"Format de date/heure invalide : {value}")

    _target_datetime = target
    _save_target_to_file(target, str(value))
    return target


def clear_beta_launch_target() -> None:
    """Supprime la configuration du compte à rebours de bêta."""
    global _target_datetime, _last_activity_text, _last_status
    _target_datetime = None
    _last_activity_text = None
    _last_status = None
    if BETA_LAUNCH_FILE.exists():
        try:
            BETA_LAUNCH_FILE.unlink()
        except OSError:
            pass


def calculate_remaining_hours(target: datetime | None = None, now: datetime | None = None) -> int | None:
    """
    Calcule le nombre d'heures restantes (arrondi supérieur) jusqu'à l'ouverture de la bêta.
    Retourne 0 si la date est échue, ou None si aucune cible n'est configurée.
    """
    target = target or get_beta_launch_target()
    if target is None:
        return None

    now = now or datetime.now().astimezone()
    if target.tzinfo is not None and now.tzinfo is None:
        target = target.replace(tzinfo=None)
    elif target.tzinfo is None and now.tzinfo is not None:
        target = target.replace(tzinfo=now.tzinfo)

    diff_seconds = (target - now).total_seconds()
    if diff_seconds <= 0:
        return 0

    hours = math.ceil(diff_seconds / 3600)
    return max(1, hours)


def get_presence_text(target: datetime | None = None, now: datetime | None = None) -> str:
    """
    Formate le message de présence pour le bot Root :
    - Si BOT_PRESENCE est défini dans l'environnement, utilise cette valeur.
    - Si le mode bêta est désactivé : data.BOT_NAME ('Root')
    - x > 1 : 'Ouverture de la beta dans {x} heures'
    - x == 1 : 'Ouverture de la beta dans 1 heure'
    - x <= 0 : 'Beta ouverte !'
    - Si aucune date n'est configurée : data.BOT_NAME ('Root')
    """
    env_presence = os.getenv("BOT_PRESENCE")
    if env_presence and env_presence.strip():
        return env_presence.strip()

    checks = Check()
    if not checks.beta_enabled():
        return data.BOT_NAME

    hours = calculate_remaining_hours(target, now)
    if hours is None:
        return data.BOT_NAME

    if hours <= 0:
        return "Beta ouverte !"
    if hours == 1:
        return "Ouverture de la beta dans 1 heure"
    return f"Ouverture de la beta dans {hours} heures"



def get_presence_activity(target: datetime | None = None, now: datetime | None = None) -> discord.BaseActivity:
    """Crée l'objet d'activité Discord adapté au message de statut."""
    activity_text = get_presence_text(target, now)
    if activity_text == data.BOT_NAME:
        return discord.Game(name=data.BOT_NAME)
    return discord.CustomActivity(name=activity_text)


async def update_bot_presence(bot: discord.Bot) -> None:
    """
    Actualise la présence du bot sur Discord en tenant compte :
    - Du mode maintenance (Statut DND ou Online)
    - De l'activité calculée (compte à rebours de bêta ou défaut)
    """
    global _last_activity_text, _last_status
    try:
        checks = Check()
        status = discord.Status.dnd if checks.maintenance_enabled() else discord.Status.online
        activity = get_presence_activity()
        current_text = getattr(activity, "name", None) or getattr(activity, "state", None)

        if current_text != _last_activity_text or status != _last_status:
            await bot.change_presence(status=status, activity=activity)
            _last_activity_text = current_text
            _last_status = status
            logger.info("Présence mise à jour : status=%s | activity=%s", status, current_text)
    except Exception:
        logger.exception("Échec de l'actualisation de présence Discord")


def start_presence_loop(bot: discord.Bot) -> None:
    """Démarre la boucle d'arrière-plan de rafraîchissement minute par minute."""
    global _presence_task
    if _presence_task is not None and _presence_task.is_running():
        return

    @tasks.loop(minutes=1)
    async def _presence_ticker():
        await update_bot_presence(bot)

    _presence_task = _presence_ticker
    _presence_ticker.start()


def stop_presence_loop() -> None:
    """Arrête la tâche de fond de présence."""
    global _presence_task
    if _presence_task is not None and _presence_task.is_running():
        _presence_task.cancel()
        _presence_task = None

