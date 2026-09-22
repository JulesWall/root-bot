"""
Commande d'administration : Bannissement d'un utilisateur du réseau Root.

Action :
- Réservée aux administrateurs possédant le rôle OP (OP_ROLE_ID).
- Bloque l'accès aux commandes ordinaires du bot via data/banned.json.
- N'exclut pas le membre du serveur Discord (sanction interne au bot).
- Consigne la décision dans le salon de logs de modération.
"""

import discord
from discord.ext import commands

from utils.logger import Logger
from utils import text
from utils.check import Check


class Ban(commands.Cog):
    """Cog d'administration gérant l'exclusion des utilisateurs."""

    def __init__(self, bot):
        self.bot = bot
        self.check = Check()

    @commands.command(name="ban")
    async def ban(self, ctx, user: discord.User):
        """Bannit un utilisateur de l'utilisation du bot Root (réservé OP)."""
        # Contrôle strict du rôle OP sur le serveur maître
        if not await self.check.is_op(self.bot, ctx.author.id):
            return
        # Enregistrement dans data/banned.json (retourne False si déjà banni)
        if not self.check.set_banned(user.id, True):
            await ctx.send(text.get(ctx, "ban_already_banned", user=user.mention))
            return
        # Traçabilité dans le salon Discord de modération
        await Logger(self.bot).log_ban_unban(user, "ban", ctx.author)
        await ctx.send(text.get(ctx, "ban_success", user=user.mention))


def setup(bot):
    bot.add_cog(Ban(bot))

