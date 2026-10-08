"""
Root OS - Charte graphique, thèmes et constantes de présentation.

Définit la palette unifiée par état, les budgets de contenu et les conventions de footer.
"""

from enum import Enum
import discord


class VisualState(str, Enum):
    CONSULTATION = 'consultation'
    QUOTE = 'quote'
    IN_PROGRESS = 'in_progress'
    SUCCESS = 'success'
    ATTENTION = 'attention'
    CRITICAL_FAILURE = 'critical_failure'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'


# Palette officielle Root OS
COLOR_TURQUOISE = discord.Color.from_rgb(84, 226, 209)   # #54E2D1
COLOR_AMBER     = discord.Color.from_rgb(255, 193, 90)   # #FFC15A
COLOR_RED       = discord.Color.from_rgb(240, 106, 106)  # #F06A6A
COLOR_WHITE     = discord.Color.from_rgb(238, 241, 245)  # #EEF1F5
COLOR_PURPLE    = discord.Color.from_rgb(182, 109, 255)  # #B66DFF

# Couleurs thématiques unifiées pour les flux de logs publics
COLOR_LOG_EVENT    = COLOR_TURQUOISE  # #54E2D1 - Événements réseau & mini-jeux résolus
COLOR_LOG_ATTACK   = COLOR_RED        # #F06A6A - Alertes offensives PvP (/hack)
COLOR_LOG_SCAN     = COLOR_AMBER      # #FFC15A - Cyber-renseignement & expositions (/scan)
COLOR_LOG_CRITICAL = COLOR_PURPLE     # #B66DFF - Procédure de sauvegarde PvP (dégâts critiques)

# Association état visuel -> couleur
STATE_COLORS = {
    VisualState.CONSULTATION: COLOR_TURQUOISE,
    VisualState.QUOTE: COLOR_TURQUOISE,
    VisualState.IN_PROGRESS: COLOR_TURQUOISE,
    VisualState.SUCCESS: COLOR_TURQUOISE,
    VisualState.ATTENTION: COLOR_AMBER,
    VisualState.CRITICAL_FAILURE: COLOR_RED,
    VisualState.CANCELLED: COLOR_TURQUOISE,
    VisualState.EXPIRED: COLOR_AMBER,
}

# Budgets de contenu recommandés
BUDGET_TITLE = 80
BUDGET_SHORT_DESC = 600
BUDGET_PONCTUAL = 800
BUDGET_FIELD_OVERVIEW = 500
BUDGET_FIELD_DETAIL = 800
BUDGET_BUTTON_LABEL = 80

# Identité globale
BRAND_PREFIX = "ROOT OS"


def get_color_for_state(state: VisualState | str) -> discord.Color:
    """Retourne la couleur Discord associée à un état visuel."""
    if isinstance(state, str):
        try:
            state = VisualState(state)
        except ValueError:
            return COLOR_TURQUOISE
    return STATE_COLORS.get(state, COLOR_TURQUOISE)


def build_footer_text(section: str | None = None) -> str:
    """Formate le texte de pied de page 'ROOT OS · {section}'."""
    if section:
        return f"{BRAND_PREFIX} · {section}"
    return BRAND_PREFIX
