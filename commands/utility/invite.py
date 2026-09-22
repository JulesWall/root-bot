"""Module de commande /invite et !invite.

Ce module fournit le lien d'invitation officiel du bot Root avec les permissions requises.
- Zéro SQL (commande utilitaire).
- Supporte à la fois la commande Slash (/invite) et la commande préfixe (!invite).
- Fournit le lien au format texte et un bouton de redirection directe Discord (ButtonStyle.link).
"""

import discord
from discord.ext import commands

from data import BOT_NAME, GUILD_WHITELIST, INVITE_URL
from lang.descslash import desc, desc_loc
from utils import text


class InviteButtonView(discord.ui.View):
    """Vue contenant un bouton de lien externe pour inviter le bot en un clic."""

    def __init__(self, label: str):
        super().__init__()
        self.add_item(
            discord.ui.Button(
                label=label,
                url=INVITE_URL,
                style=discord.ButtonStyle.link,
                emoji="🔗",
            )
        )


class Invite(commands.Cog):
    """Cog fournissant la commande d'invitation du bot."""

    def __init__(self, bot):
        self.bot = bot

    async def _invite_logic(self, ctx):
        """Logique d'exécution partagée pour /invite et !invite."""
        resp = text.get(ctx, "invite_response", bot_name=BOT_NAME, invite_url=INVITE_URL)
        btn_label = text.get(ctx, "invite_button_label", bot_name=BOT_NAME)
        view = InviteButtonView(label=btn_label)

        if hasattr(ctx, "respond"):
            await ctx.respond(resp, view=view)
        else:
            await ctx.send(resp, view=view)

    # ── Version Commande Slash ───────────────────────────────────────────────────
    @discord.slash_command(
        guild_ids=GUILD_WHITELIST or None,
        description=desc["invite"],
        description_localizations=desc_loc["invite"],
    )
    async def invite(self, ctx):
        """Commande Slash /invite."""
        await self._invite_logic(ctx)

    # ── Version Commande avec Préfixe ────────────────────────────────────────────
    @commands.command(name="invite")
    async def prefix_invite(self, ctx):
        """Commande avec préfixe !invite."""
        await self._invite_logic(ctx)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Invite(bot))
