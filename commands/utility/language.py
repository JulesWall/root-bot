"""Module de commande /language et !language.

Ce module permet aux utilisateurs de choisir leur langue préférée pour toutes
les interactions avec le bot (textes d'interface, erreurs, embeds, boutons).

Fonctionnalités :
1. Consultation : sans argument, affiche la langue actuellement active et son statut
   (par défaut selon le serveur/client ou personnalisée par le joueur).
2. Changement : sélection d'une langue supportée ('fr' ou 'en') avec prise en charge
   d'alias courants (fr, fra, francais, english, etc.).
3. Réinitialisation : 'reset' / 'auto' / 'default' pour effacer la préférence et revenir
   au comportement automatique de Discord.
4. Télémétrie : si un utilisateur saisit une langue non supportée (ex: 'es', 'de'),
   un log automatique est envoyé aux développeurs via `Logger.log_new_language()`.

Architecture :
- Découplage strict : la persistance passe par `utils.language_manager`, qui synchronise
  le cache en mémoire et la base MariaDB/MySQL sans injecter de SQL ici.
- Textes 100% gérés par `lang/`.
"""

import discord
from discord.ext import commands

from data import GUILD_WHITELIST, SUPPORTED_LANGS, DEFAULT_PREFIX
from lang.descslash import desc, desc_loc
from utils import text
from utils.language_manager import (
    fetch_user_language,
    get_user_language,
    set_user_language,
    reset_user_language,
)
from utils.logger import Logger
from utils.prefix_manager import get_prefix_async

# Table de correspondance des alias de langues saisis par les utilisateurs
LANG_ALIASES = {
    "fr": "fr",
    "fra": "fr",
    "francais": "fr",
    "français": "fr",
    "french": "fr",
    "en": "en",
    "eng": "en",
    "english": "en",
    "anglais": "en",
}


class Language(commands.Cog):
    """Cog de gestion de la langue des utilisateurs.

    Attributes:
        bot (commands.Bot): L'instance principale du bot.
    """

    def __init__(self, bot):
        self.bot = bot

    async def _language_logic(self, ctx, choice: str = None):
        """Logique centrale de gestion du changement de langue.

        Args:
            ctx: Contexte d'exécution (ApplicationContext ou Context classique).
            choice (str, optional): Code de langue, alias, ou commande de reset.
        """
        guild = getattr(ctx, "guild", None)
        prefix = await get_prefix_async(guild.id) if guild else DEFAULT_PREFIX
        user = getattr(ctx, "author", None) or getattr(ctx, "user", None)
        user_id = getattr(user, "id", None)
        if user_id:
            try:
                await fetch_user_language(user_id)
            except Exception:
                pass

        # ── 1. Aucun choix fourni : consultation de la langue actuelle ─────────────
        if not choice or not choice.strip():
            # Résolution de la locale active selon la cascade (User DB > Interaction > Fallback)
            current_lang = text.get_locale(ctx)
            saved = get_user_language(user_id) if user_id else None
            # Indique si la langue est personnalisée ou héritée
            display = f"{current_lang} (personnalisée / custom)" if saved else f"{current_lang} (par défaut / default)"
            msg = text.get(ctx, "language_current", lang=display, prefix=prefix)
            if hasattr(ctx, "respond"):
                await ctx.respond(msg)
            else:
                await ctx.send(msg)
            return

        choice = choice.strip().lower()

        # ── 2. Réinitialisation vers le mode automatique ───────────────────────────
        if choice in ("reset", "auto", "default", "supprimer", "clear"):
            if user_id:
                await reset_user_language(user_id)
            msg = text.get(ctx, "language_reset")
            if hasattr(ctx, "respond"):
                await ctx.respond(msg)
            else:
                await ctx.send(msg)
            return

        # ── 3. Validation de la langue choisie et notification en cas de demande inconnue
        target_lang = LANG_ALIASES.get(choice)
        if not target_lang or target_lang not in SUPPORTED_LANGS:
            # Langue inconnue : journalisation d'une demande de localisation dans le salon logs
            if user:
                await Logger(self.bot).log_new_language(user, choice)
            supported_str = ", ".join(SUPPORTED_LANGS)
            msg = text.get(ctx, "language_invalid", supported=supported_str)
            if hasattr(ctx, "respond"):
                await ctx.respond(msg)
            else:
                await ctx.send(msg)
            return

        # ── 4. Enregistrement du choix utilisateur ────────────────────────────────
        if user_id:
            await set_user_language(user_id, target_lang)

        # ── 5. Confirmation (immédiatement dans la nouvelle langue choisie) ────────
        msg = text.get(ctx, "language_success", lang=target_lang)
        if hasattr(ctx, "respond"):
            await ctx.respond(msg)
        else:
            await ctx.send(msg)

    # ── Version Commande Slash (/lang) ───────────────────────────────────────────
    @discord.slash_command(
        name="lang",
        guild_ids=GUILD_WHITELIST or None,
        description=desc.get("lang", desc.get("language", "Change your preferred language for the bot")),
        description_localizations=desc_loc.get("lang", desc_loc.get("language", None)),
    )
    async def slash_language(
        self,
        ctx,
        choice: discord.Option(
            str,
            desc.get("language_choice", "Choose language (fr or en, or reset)"),
            choices=[
                discord.OptionChoice("Français (fr)", "fr"),
                discord.OptionChoice("English (en)", "en"),
                discord.OptionChoice("Réinitialiser / Reset (auto)", "reset"),
            ],
            required=False,
            default=None,
        ) = None,
    ):
        """Permet de changer la langue des messages du bot."""
        await self._language_logic(ctx, choice)

    # ── Version Commande avec Préfixe (!lang ou !language) ──────────────────────
    @commands.command(name="lang", aliases=["language"])
    async def prefix_language(self, ctx, choice: str = None):
        """Permet de changer la langue des messages du bot (commande préfixe)."""
        await self._language_logic(ctx, choice)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Language(bot))
