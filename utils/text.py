"""
Moteur de résolution de langue et d'interpolation de chaînes localisées.

Architecture de l'internationalisation (i18n) :
1. get_locale(ctx) applique une priorité stricte à 3 niveaux :
   - Niveau 1 : Préférence personnalisée persistée du joueur (en cache mémoire, synchronisée avec MySQL).
   - Niveau 2 : Pour les Slash Commands, détection automatique de la langue du client Discord (interaction.locale).
   - Niveau 3 : Repli universel sur l'anglais ('en') pour les commandes textuelles préfixées ou langues inconnues.
2. get(ctx, key, **kwargs) :
   - Extrait le texte localisé depuis le dictionnaire correspondant dans data.LANGUAGES.
   - Injecte les variables dynamiques (**kwargs) via str.format().
   - Fournit un fallback robuste sur l'anglais ou un message de clé manquante sans faire crasher le bot.
"""

from decimal import Decimal, ROUND_HALF_UP

from data import LANGUAGES, SUPPORTED_LANGS
from utils.language_manager import get_user_language


def format_usd(val) -> str:
    """Formate un montant en USD : sans centimes si rond, 2 décimales sinon."""
    d = Decimal(str(val or 0))
    if d % 1 == 0:
        return f"{int(d):,}"
    return f"{d:,.2f}"


def format_rtm(val) -> str:
    """Formate un montant en Rootium avec 5 décimales maximum (précision monétaire RTM).

    Cas particulier : si la valeur est strictement positive mais s'arrondit à `0.00000`
    sur 5 décimales, affiche `>0.00001` pour signaler un montant infime non nul plutôt
    qu'un zéro trompeur.
    """
    d = Decimal(str(val or 0))
    if d <= 0:
        return "0.00000"
    rounded = d.quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)
    if rounded == 0:
        return ">0.00001"
    return f"{rounded:,.5f}"


def format_seconds(seconds: int | float) -> str:
    """Formate une durée en secondes en format lisible (alias de time_format.format_duration)."""
    from utils.time_format import format_duration
    return format_duration(seconds)


def get_locale(ctx) -> str:
    """
    Détermine la langue applicable au contexte donné selon les règles hiérarchiques :
    1. Si le joueur a une langue enregistrée en cache (depuis BDD) -> prioritaire.
    2. Si Slash Command -> langue du client Discord de l'utilisateur (si supportée, sinon 'en').
    3. Pour les commandes textuelles à préfixe -> 'en' par défaut.
    """
    # 1. Vérification de la préférence personnalisée du joueur (cache mémoire synchronisé)
    user = getattr(ctx, "author", None) or getattr(ctx, "user", None)
    if user:
        user_id = getattr(user, "id", None)
        if user_id:
            user_lang = get_user_language(user_id)
            if user_lang and user_lang in SUPPORTED_LANGS:
                return user_lang

    # 2. Pour les Slash Commands et interactions UI : langue du client Discord de l'utilisateur
    interaction = getattr(ctx, "interaction", None) or ctx
    if interaction and getattr(interaction, "locale", None):
        locale_code = str(interaction.locale)[:2].lower()
        if locale_code in SUPPORTED_LANGS:
            return locale_code
        return "en"

    # 3. Pour les Prefix Commands : 'en' par défaut
    return "en"


def get(ctx, key: str, **kwargs) -> str:
    """
    Résout et formate une chaîne de texte dans la langue de l'utilisateur.
    
    Args:
        ctx: Contexte de la commande ou de l'interaction.
        key: Identifiant de la chaîne de texte (ex: 'ping_response', 'g_buy_success').
        **kwargs: Variables dynamiques injectées dans le template.
    """
    user_locale = get_locale(ctx)
    # Sélection du dictionnaire localisé avec repli systématique sur l'anglais
    selected_lang = LANGUAGES.get(user_locale, LANGUAGES.get("en", {}))
    text_content = selected_lang.get(key, f"MISSING_KEY: {key}")
    try:
        return text_content.format(**kwargs)
    except Exception:
        # En cas d'erreur de formatage, retourne le template brut sans lever d'exception fatale
        return text_content


def get_for_lang(lang: str | None, key: str, **kwargs) -> str:
    """
    Résout et formate une chaîne de texte directement selon le code de langue spécifié ('fr', 'en'...).
    Idéal pour les notifications d'arrière-plan sans contexte Discord d'origine (ex: DM automatique).
    """
    code = (lang or 'en')[:2].lower()
    selected_lang = LANGUAGES.get(code, LANGUAGES.get("en", {}))
    text_content = selected_lang.get(key, f"MISSING_KEY: {key}")
    try:
        return text_content.format(**kwargs)
    except Exception:
        return text_content


