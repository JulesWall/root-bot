"""Commande /hash et !hash (alias !h) — Mini-jeu communautaire Hash Challenge.

Ce module implémente le défi cryptographique périodique de Root :
- Défi global partagé entre tous les serveurs connectés.
- Les joueurs proposent des nombres pour réduire la zone de recherche jusqu'à trouver la cible.
- Le premier joueur qui valide le hash remporte une récompense en USD.
- Les résultats de victoire sont automatiquement journalisés dans le salon public.
"""

import discord
from discord.ext import commands

import data
from commands.game.game_config import GAMES
from commands.game.minigame_cog import MiniGameCog
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR


class Hash(MiniGameCog):
    """Cog gérant le mini-jeu Hash Challenge."""

    config = GAMES["hash"]

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="hash",
        description=EN["hash"],
        description_localizations={"fr": FR["hash"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def hash(
        self,
        ctx,
        guess: discord.Option(
            int,
            description="Your guess for the corrupted hash / Ta proposition pour le hash",
            required=False,
            default=None,
        ) = None,
    ):
        """Participer au Hash Challenge ou consulter l'état actuel du défi."""
        await self._run_slash(ctx, guess)

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="hash", aliases=["h"], help=FR["hash"])
    async def prefix_hash(self, ctx, guess: str = None):
        """Commande préfixe !hash [valeur]."""
        await self._run_prefix(ctx, guess)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Hash(bot))
