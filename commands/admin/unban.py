"""
Commande d'administration : Débannissement d'un utilisateur du réseau Root.

Action :
- Réservée aux administrateurs possédant le rôle OP (OP_ROLE_ID).
- Retire l'identifiant de data/banned.json.
- Consigne la décision dans le salon de logs de modération.
"""

import discord
from discord.ext import commands

from utils.logger import Logger
from utils import text
from utils.check import Check


class Unban(commands.Cog):
    """Cog d'administration gérant la réintégration des utilisateurs bannis."""

    def __init__(self, bot):
        self.bot = bot
        self.check = Check()

    @commands.command(name="unban")
    async def unban(self, ctx, user: discord.User):
        """Réintègre un utilisateur sur le réseau Root (réservé OP)."""
        # Contrôle strict du rôle OP sur le serveur maître
        if not await self.check.is_op(self.bot, ctx.author.id):
            return
        # Retrait de data/banned.json (retourne False si l'utilisateur n'était pas banni)
        if not self.check.set_banned(user.id, False):
            await ctx.send(text.get(ctx, "unban_not_banned", user=user.mention))
            return
        # Traçabilité dans le salon Discord de modération
        await Logger(self.bot).log_ban_unban(user, "unban", ctx.author)
        await ctx.send(text.get(ctx, "unban_success", user=user.mention))


def setup(bot):
    bot.add_cog(Unban(bot))

