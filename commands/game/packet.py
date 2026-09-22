"""Commande /packet et !packet (alias !pa) — Mini-jeu communautaire Packet.

Ce module implémente le défi d'intégrité de transmission de paquets de Root :
- Un numéro manquant parmi 1 à 10.
- Les 9 autres numéros transmis dans le désordre dans un bloc monospacé.
- Le joueur identifie le paquet manquant et répond avec /packet <1-10>.
- Le premier joueur qui soumet le bon numéro remporte la prime en USD.
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


class Packet(MiniGameCog):
    """Cog gérant le mini-jeu Packet."""

    config = GAMES["packet"]

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="packet",
        description=EN["packet"],
        description_localizations={"fr": FR["packet"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def packet(
        self,
        ctx,
        guess: discord.Option(
            int,
            description="Missing packet number (1-10) / Numéro du paquet manquant (1-10)",
            required=False,
            default=None,
            min_value=1,
            max_value=10,
        ) = None,
    ):
        """Participer au défi de transmission Packet ou consulter les paquets reçus."""
        await self._run_slash(ctx, guess)

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="packet", aliases=["pa"], help=FR["packet"])
    async def prefix_packet(self, ctx, guess: str = None):
        """Commande préfixe !packet [numéro] (alias !pa)."""
        await self._run_prefix(ctx, guess)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Packet(bot))
