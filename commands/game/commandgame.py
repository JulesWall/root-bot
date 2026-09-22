"""Classe de base commune à tous les Cogs de jeu (BaseGameCog).

Ce module implémente le pattern architectural fondamental pour toutes les commandes de jeu :
- Aucun accès direct à la base de données : tout passe par la façade de service (`self.service`).
- Aucun texte codé en dur : centralisation des erreurs et des messages dans `lang/`.
- Gestion automatisée du préchargement de langue (`_prefetch_lang`) : garantit que la
  langue stockée en base de données pour le joueur est présente en cache avant de formater
  le moindre message ou Embed.
- Capture unifiée des exceptions métier (`GameError`) et restitution propre via `_send_error`.
"""

import discord
from discord.ext import commands

from game.game_error import GameError
from utils import text
from utils.root_embed import RootEmbed
from utils.language_manager import fetch_user_language


class BaseGameCog(commands.Cog):
    """Classe parente de tous les Cogs liés aux mécaniques de jeu de Root.

    Elle fournit :
    1. L'accès direct à l'instance singleton de `RootService` via la propriété `service`.
    2. Le préchargement asynchrone de la langue de l'utilisateur (`_prefetch_lang`).
    3. Un wrapper d'invocation standardisé (`_invoke`) capturant les `GameError`.
    4. Des méthodes utilitaires pour l'envoi d'Embeds cohérents (`_send_embed`, `_send_error`).
    """

    @property
    def service(self):
        """Fournit un accès pratique à l'instance de `RootService` attachée au bot."""
        return self.bot.root_service

    async def _prefetch_lang(self, user_id):
        """Charge la langue personnalisée du joueur en cache mémoire avant toute résolution de texte.

        Cette étape garantit que si le joueur a défini sa langue avec `/language`,
        toutes les réponses et tous les messages d'erreur subséquents respecteront son choix,
        sans devoir interroger la base de données de manière synchrone lors du rendu.
        """
        await fetch_user_language(user_id)

    async def _invoke(self, ctx, method, **args):
        """Exécute une méthode de jeu de manière standardisée et sécurisée.

        Flux d'exécution :
        1. Précharge la langue du joueur via `_prefetch_lang`.
        2. Appelle `service.execute(user_id, guild_id, method, **args)`.
        3. Transmet le résultat métier à la méthode d'affichage `_send()` du Cog enfant.
        4. Intercepte toute `GameError` pour afficher l'erreur localisée correspondante.
        """
        await self._prefetch_lang(ctx.author.id)
        try:
            result = await self.service.execute(
                ctx.author.id,
                ctx.guild.id if ctx.guild else None,
                method,
                **args,
            )
            await self._send(ctx, method, result)
        except GameError as error:
            # Traitement unifié des erreurs de règles de jeu
            await self._send_error(ctx, error)

    async def _send(self, ctx, method, result):
        """Méthode abstraite d'affichage à surcharger dans chaque Cog de commande de jeu.

        Args:
            ctx: Contexte d'exécution de la commande.
            method (str): Nom de l'action exécutée (ex: 'network', 'buy', 'upgrade').
            result (dict): Données retournées par la logique métier.
        """
        raise NotImplementedError

    async def _send_error(self, ctx, error: GameError):
        """Formate et expédie un message d'erreur de jeu localisé.

        Résolution :
        - La clé de localisation est construite sous la forme 'g_error_' + error.key.
        - Les paramètres dynamiques de l'erreur (`error.values`) sont injectés dans le modèle de texte.
        - Les mentions sont désactivées (`AllowedMentions.none()`) par mesure de sécurité.
        """
        msg = text.get(ctx, 'g_error_' + error.key, **error.values)
        if getattr(ctx, 'interaction', None):
            await ctx.respond(msg, allowed_mentions=discord.AllowedMentions.none())
        else:
            await ctx.send(msg, allowed_mentions=discord.AllowedMentions.none())

    async def _send_embed(self, ctx, action, content, view=None):
        """Construit et envoie un Embed stylisé via le composant `RootEmbed`.

        Args:
            ctx: Contexte d'exécution.
            action (str): Nom de l'action pour déterminer la couleur de la barre latérale.
            content (str): Corps du message textuel.
            view (discord.ui.View, optional): Composants interactifs (boutons, confirmations).
        """
        embed = RootEmbed(ctx, action, content)
        return await embed.send(ctx, view=view)


# Rétrocompatibilité interne
GameCog = BaseGameCog


def setup(bot):
    """Pas de Cog concret à enregistrer directement pour cette classe abstraite."""
    pass

