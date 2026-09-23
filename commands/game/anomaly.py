"""Commande /anomaly et !anomaly (alias !a) — Mini-jeu communautaire Anomaly.

Ce module implémente le défi de détection d'anomalie de Root :
- Un bloc de données de 10 lignes de 16 lettres majuscules (sans ligne vide).
- Exactement un seul chiffre parasite (1-9) dissimulé sur une seule ligne.
- Les joueurs comptent les lignes de haut en bas (de 1 à 10) et soumettent le numéro.
- Le premier joueur qui trouve la bonne ligne remporte la récompense en USD.
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


class Anomaly(MiniGameCog):
    """Cog gérant le mini-jeu Anomaly."""

    config = GAMES["anomaly"]

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="anomaly",
        description=EN["anomaly"],
        description_localizations={"fr": FR["anomaly"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def anomaly(
        self,
        ctx,
        line: discord.Option(
            int,
            description="Line number containing the anomaly (1-10) / Numéro de ligne de l'anomalie (1-10)",
            required=False,
            default=None,
            min_value=1,
            max_value=10,
        ) = None,
    ):
        """Participer à l'épreuve d'Anomalie ou consulter le flux de données actif."""
        await self._run_slash(ctx, line)

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="anomaly", aliases=["a"], help=FR["anomaly"])
    async def prefix_anomaly(self, ctx, line: str = None):
        """Commande préfixe !anomaly [ligne] (alias !a)."""
        await self._run_prefix(ctx, line)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Anomaly(bot))
