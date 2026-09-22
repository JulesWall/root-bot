"""
Module de configuration globale et de chargement des constantes du bot Root.

Ce module est l'un des deux seuls fichiers autorisés à la racine du projet
(avec main.py), selon les règles d'architecture strictes.
Il a pour rôles :
1. Charger les variables d'environnement depuis le fichier .env.
2. Définir les constantes fondamentales (nom du bot, préfixe par défaut, whitelist de serveurs).
3. Compiler et fusionner les dictionnaires de localisation (FR et EN) pour l'ensemble du bot et du jeu.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from lang import en, fr, game_en, game_fr

# Chemins de base du projet
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Chargement du fichier d'environnement .env (override=False préserve les variables d'environnement système existantes)
load_dotenv(BASE_DIR / ".env", override=False)


def env_ids(name: str) -> list[int]:
    """
    Parse une variable d'environnement contenant une liste d'identifiants séparés par des virgules.
    
    Exemple : "123456789, 987654321" -> [123456789, 987654321]
    Ignore les entrées vides ou composées uniquement d'espaces.
    """
    return [int(value.strip()) for value in os.getenv(name, "").split(",") if value.strip()]


# Nom affiché pour l'activité Discord et les embeds
BOT_NAME = "Root"

# Jeton d'authentification du bot Discord (obligatoire)
TOKEN = os.getenv("DISCORD_TOKEN")

# Préfixe par défaut pour les commandes textuelles (ex: +rping, +rnetwork)
DEFAULT_PREFIX = os.getenv("DEFAULT_PREFIX", "+r").strip() or "+r"

# Lien d'invitation officiel du bot Discord
INVITE_URL = "https://discord.com/oauth2/authorize?client_id=659013189136285708&permissions=139586825280&scope=bot+applications.commands"

# Lien du serveur Discord officiel de Root
OFFICIAL_SERVER_URL = "https://discord.gg/FtfGuyb6mv"

# Whitelist optionnelle de serveurs (Guild IDs) pour la publication instantanée des Slash Commands.
# Si la liste est vide, les commandes sont publiées globalement sur Discord (délai de propagation possible).
GUILD_WHITELIST = env_ids("GUILD_WHITELIST")

# Fusion des dictionnaires de langue généraux (système/admin/utilitaire) et spécifiques au jeu (Root OS)
LANGUAGES = {
    "fr": {**fr.text, **game_fr.text, **game_fr.labels},
    "en": {**en.text, **game_en.text, **game_en.labels}
}

# Tuple des codes de langues supportées pour les vérifications d'appartenance rapides (O(1))
SUPPORTED_LANGS = tuple(LANGUAGES)

