"""
Commande d'administration : Arrêt contrôlé du processus du bot Root.

Action :
- Réservée aux administrateurs détenant le rôle OP (OP_ROLE_ID).
- Envoie un message d'avertissement sur Discord.
- Ferme la session Discord WebSocket proprement avec bot.close().
- Termine le processus Python via os._exit(0).
"""

import os
from discord.ext import commands
from utils import text
from utils.check import Check


class Shutdown(commands.Cog):
    """Cog d'administration gérant l'arrêt propre du bot."""

    def __init__(self, bot):
        self.bot = bot
        self.check = Check()

    @commands.command(name="shutdown")
    async def shutdown(self, ctx):
        """Arrête le processus du bot Root (réservé OP)."""
        # Contrôle strict du rôle OP sur le serveur maître
        if not await self.check.is_op(self.bot, ctx.author.id):
            return
        await ctx.send(text.get(ctx, "shutdown_response"))
        await self.bot.close()
        os._exit(0)


def setup(bot):
    bot.add_cog(Shutdown(bot))
