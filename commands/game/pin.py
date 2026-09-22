"""Commande /pin et !pin (alias !p) — Mini-jeu communautaire Code PIN.

Ce module implémente le défi de déchiffrement de code PIN individuel de Root :
- Défi global partagé entre tous les serveurs connectés (même cible secrète).
- Progression INDIVIDUELLE : chaque joueur réduit sa propre zone de recherche personnelle.
- Le premier joueur qui valide le code PIN remporte la récompense en USD pour tout le réseau.
- Les résultats de victoire sont automatiquement journalisés dans le salon public.
"""

import discord
from discord.ext import commands

import data
from commands.game.game_config import GAMES
from commands.game.minigame_cog import MiniGameCog
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR


class Pin(MiniGameCog):
    """Cog gérant le mini-jeu Code PIN."""

    config = GAMES["pin"]

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="pin",
        description=EN["pin"],
        description_localizations={"fr": FR["pin"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def pin(
        self,
        ctx,
        guess: discord.Option(
            int,
            description="Your PIN code guess / Ton code PIN proposé",
            required=False,
            default=None,
        ) = None,
    ):
        """Participer à la course au code PIN ou consulter sa zone personnelle."""
        await self._run_slash(ctx, guess)

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="pin", aliases=["p"], help=FR["pin"])
    async def prefix_pin(self, ctx, guess: str = None):
        """Commande préfixe !pin [valeur]."""
        await self._run_prefix(ctx, guess)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Pin(bot))
