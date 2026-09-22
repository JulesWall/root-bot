"""Commande /buffer et !buffer (alias !b) — Mini-jeu communautaire Buffer.

Ce module implémente le défi de réordonnancement de fragments de données de Root :
- 6 fragments numérotés de 1 à 6 affichés dans le désordre (garanti non pré-trié).
- Chaque fragment contient une lettre majuscule distincte (ex: 4:T  1:R  6:M  2:K  5:X  3:A).
- Le joueur remet les fragments dans l'ordre 1 à 6 pour reconstituer le mot (ex: RKATXM).
- Le premier joueur qui trouve le mot valide remporte la prime en USD.
- Aucun délai d'attente entre les mauvaises propositions.
- Les résultats de victoire sont automatiquement journalisés dans le salon public.
"""

import discord
from discord.ext import commands

import data
from commands.game.game_config import GAMES
from commands.game.minigame_cog import MiniGameCog
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR


class Buffer(MiniGameCog):
    """Cog gérant le mini-jeu Buffer."""

    config = GAMES["buffer"]

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="buffer",
        description=EN["buffer"],
        description_localizations={"fr": FR["buffer"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def buffer(
        self,
        ctx,
        code: discord.Option(
            str,
            description="Reconstructed 6-letter code / Code de 6 lettres reconstitué",
            required=False,
            default=None,
        ) = None,
    ):
        """Participer au défi Buffer ou consulter les fragments actifs."""
        await self._run_slash(ctx, code)

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="buffer", aliases=["b"], help=FR["buffer"])
    async def prefix_buffer(self, ctx, *, code: str = None):
        """Commande préfixe !buffer [code] (alias !b)."""
        await self._run_prefix(ctx, code)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Buffer(bot))
