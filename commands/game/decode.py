"""Commande /decode et !decode (alias !d) — Mini-jeu communautaire Décryptage.

Ce module implémente le défi de déchiffrement de grille 4x4 de Root :
- Défi global partagé entre tous les serveurs connectés (même grille et même séquence).
- Une grille 4x4 contenant 16 lettres distinctes aléatoires (A-D, 1-4).
- Une séquence de 4 coordonnées distinctes à décoder dans l'ordre (ex: B3 · D1 · A4 · C2).
- Le premier joueur qui soumet le code valide remporte la récompense en USD.
- Aucun cooldown entre les mauvaises propositions.
- Les résultats de victoire sont automatiquement journalisés dans le salon public.
"""

import discord
from discord.ext import commands

import data
from commands.game.game_config import GAMES
from commands.game.minigame_cog import MiniGameCog
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR


class Decode(MiniGameCog):
    """Cog gérant le mini-jeu Décryptage."""

    config = GAMES["decode"]

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="decode",
        description=EN["decode"],
        description_localizations={"fr": FR["decode"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def decode(
        self,
        ctx,
        code: discord.Option(
            str,
            description="Your decoded 4-letter word / Ton mot de 4 lettres décodé",
            required=False,
            default=None,
        ) = None,
    ):
        """Participer au Décryptage ou consulter la grille active."""
        await self._run_slash(ctx, code)

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="decode", aliases=["d"], help=FR["decode"])
    async def prefix_decode(self, ctx, *, code: str = None):
        """Commande préfixe !decode [code] (alias !d)."""
        await self._run_prefix(ctx, code)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Decode(bot))
