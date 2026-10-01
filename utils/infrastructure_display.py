"""
Root OS - Catalogue des infrastructures et association des illustrations.

Associe les 6 niveaux d'infrastructure (0 à 5) à leurs dénominations FR/EN
et aux scènes panoramiques officielles en pixel art.
"""

from pathlib import Path
import logging
import discord

logger = logging.getLogger(__name__)

# Racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Définition des niveaux d'infrastructure
INFRASTRUCTURE_CATALOG = {
    0: {
        'name_fr': "Smartphone bricolé",
        'name_en': "Improvised smartphone",
        'rel_path': "design/infrastructures-controle/niveau-0-smartphone.png",
        'filename': "niveau-0-smartphone.png",
    },
    1: {
        'name_fr': "PC assemblé",
        'name_en': "Assembled PC",
        'rel_path': "design/infrastructures-controle/niveau-1-pc-assemble.png",
        'filename': "niveau-1-pc-assemble.png",
    },
    2: {
        'name_fr': "Station de travail",
        'name_en': "Workstation",
        'rel_path': "design/infrastructures-controle/niveau-2-station-de-travail.png",
        'filename': "niveau-2-station-de-travail.png",
    },
    3: {
        'name_fr': "Serveur dédié",
        'name_en': "Dedicated server",
        'rel_path': "design/infrastructures-controle/niveau-3-serveur-dedie.png",
        'filename': "niveau-3-serveur-dedie.png",
    },
    4: {
        'name_fr': "Salle des serveurs",
        'name_en': "Server room",
        'rel_path': "design/infrastructures-controle/niveau-4-salle-des-serveurs.png",
        'filename': "niveau-4-salle-des-serveurs.png",
    },
    5: {
        'name_fr': "Datacenter",
        'name_en': "Data center",
        'rel_path': "design/infrastructures-controle/niveau-5-datacenter.png",
        'filename': "niveau-5-datacenter.png",
    },
}


def sanitize_level(level: int | None) -> int:
    """Valide et borne le niveau d'infrastructure entre 0 et 5."""
    try:
        lvl = int(level or 0)
    except (ValueError, TypeError):
        lvl = 0
    return max(0, min(5, lvl))


def get_infrastructure_name(level: int, locale: str = 'fr') -> str:
    """Retourne l'intitulé officiel de l'infrastructure selon la langue."""
    lvl = sanitize_level(level)
    data = INFRASTRUCTURE_CATALOG[lvl]
    loc = str(locale).lower()[:2]
    return data['name_fr'] if loc == 'fr' else data['name_en']


def get_infrastructure_image_path(level: int) -> Path:
    """Retourne le chemin absolu du fichier image pour ce niveau."""
    lvl = sanitize_level(level)
    return PROJECT_ROOT / INFRASTRUCTURE_CATALOG[lvl]['rel_path']


def get_infrastructure_filename(level: int) -> str:
    """Retourne le nom de fichier de l'illustration (utilisé pour les attachements Discord)."""
    lvl = sanitize_level(level)
    return INFRASTRUCTURE_CATALOG[lvl]['filename']


def get_infrastructure_attachment_url(level: int) -> str:
    """Retourne l'URL d'attachement Discord pour l'embed ('attachment://nom.png')."""
    return f"attachment://{get_infrastructure_filename(level)}"


def get_infrastructure_file(level: int) -> discord.File | None:
    """
    Crée une instance discord.File prête à être envoyée dans un message.
    Si le fichier est absent ou illisible, journalise l'anomalie et retourne None
    sans faire crasher le bot.
    """
    path = get_infrastructure_image_path(level)
    if not path.is_file():
        logger.error("Illustration d'infrastructure introuvable au chemin : %s", path)
        return None
    try:
        return discord.File(str(path), filename=get_infrastructure_filename(level))
    except Exception:
        logger.exception("Impossible d'ouvrir l'illustration d'infrastructure : %s", path)
        return None
