"""Module de commande /prefix et !prefix.

Ce module permet aux administrateurs de serveur de configurer un préfixe textuel
personnalisé pour les commandes classiques (ex: '!', '?', 'root!').

Règles de sécurité et architecture :
- Permissions strictes : réservé exclusivement aux membres ayant la permission 'administrator'.
- Persistance : déléguée à `utils.prefix_manager.set_prefix()`, qui enregistre en base via
  la couche `game/db/prefix_db.py` (UPSERT MySQL idempotent).
- Zéro SQL dans ce module : la commande reste un simple contrôleur d'interface.
- Les textes de confirmation et d'erreur proviennent entièrement de `lang/`.
"""

import discord
from discord.ext import commands
from data import GUILD_WHITELIST
from lang.descslash import desc, desc_loc
from utils import text
from utils.prefix_manager import set_prefix, set_user_prefix


class Prefix(commands.Cog):
    """Cog gérant la personnalisation du préfixe textuel par serveur et en MP.

    Attributes:
        bot (commands.Bot): L'instance principale du bot.
    """

    def __init__(self, bot):
        self.bot = bot

    async def _prefix_logic(self, ctx, new_prefix):
        """Valide et applique le nouveau préfixe pour le serveur ou en MP.

        Étapes :
        1. Vérifie si le préfixe fourni n'est pas vide ou constitué d'espaces blancs.
        2. Appelle `set_prefix(guild_id, new_prefix)` en serveur ou `set_user_prefix(user_id, new_prefix)` en MP :
           - Vérifie la contrainte de taille (1 à 32 caractères non vides).
           - Met à jour le cache mémoire synchrone.
           - Sauvegarde en base de données MariaDB / MySQL de façon asynchrone.
        3. Envoie un message de succès localisé au demandeur.
        """
        # Vérification si un argument a bien été passé
        if not new_prefix or not new_prefix.strip():
            msg = text.get(ctx, "prefix_usage")
            if hasattr(ctx, 'respond'):
                await ctx.respond(msg)
            else:
                await ctx.send(msg)
            return

        # Nettoyage des espaces résiduels
        new_prefix = new_prefix.strip()
        is_dm = (getattr(ctx, "guild", None) is None)
        author_id = getattr(getattr(ctx, "author", None) or getattr(ctx, "user", None), "id", None)

        try:
            if is_dm:
                if not author_id:
                    return
                await set_user_prefix(author_id, new_prefix)
            else:
                await set_prefix(ctx.guild.id, new_prefix)
        except ValueError:
            # Rejet si la longueur dépasse 32 caractères ou si invalide
            msg = text.get(ctx, "prefix_invalid")
            if hasattr(ctx, 'respond'):
                await ctx.respond(msg)
            else:
                await ctx.send(msg)
            return

        # Confirmation réussie
        key = "prefix_user_success" if is_dm else "prefix_success"
        success_msg = text.get(ctx, key, new_prefix=new_prefix)
        if hasattr(ctx, 'respond'):
            await ctx.respond(success_msg)
        else:
            await ctx.send(success_msg)

    # ── Version Commande Slash (/prefix) ────────────────────────────────────────
    @discord.slash_command(
        name="prefix",
        guild_ids=GUILD_WHITELIST or None,
        description=desc.get("prefix", "Manage server or DM prefix"),
        description_localizations=desc_loc.get("prefix", None),
        default_member_permissions=discord.Permissions(administrator=True)
    )
    async def slash_prefix(self, ctx, new_prefix: discord.Option(str, desc["new_prefix"])):
        """Définit le préfixe textuel du serveur ou en MP."""
        if ctx.guild is not None:
            author = getattr(ctx, "author", None)
            guild_perms = getattr(author, "guild_permissions", None)
            if not guild_perms or not guild_perms.administrator:
                raise commands.MissingPermissions(["administrator"])
        await self._prefix_logic(ctx, new_prefix)

    # ── Version Commande avec Préfixe ────────────────────────────────────────────
    @commands.command(name="prefix")
    async def prefix_command(self, ctx, new_prefix: str = None):
        """Définit le préfixe textuel du serveur ou en MP."""
        if ctx.guild is not None:
            author = getattr(ctx, "author", None)
            guild_perms = getattr(author, "guild_permissions", None)
            if not guild_perms or not guild_perms.administrator:
                raise commands.MissingPermissions(["administrator"])
        await self._prefix_logic(ctx, new_prefix)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Prefix(bot))

