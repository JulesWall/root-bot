"""Module de commande /botinfo et !botinfo.

Ce module fournit des statistiques globales sur le bot :
- Nombre total de serveurs (guilds) connectés.
- Nombre total d'utilisateurs atteints (somme des member_count).
- Latence actuelle de la connexion Gateway.
- Titre et champs traduits dynamiquement selon la langue de l'utilisateur.
"""

import discord
from discord.ext import commands

from data import BOT_NAME, GUILD_WHITELIST, INVITE_URL
from lang.descslash import desc, desc_loc
from utils import text



class BotInfo(commands.Cog):
    """Cog d'affichage des statistiques techniques et globales du bot.

    Attributes:
        bot (commands.Bot): L'instance principale du bot.
    """

    def __init__(self, bot):
        self.bot = bot

    async def _botinfo_logic(self, ctx):
        """Construit et expédie l'Embed récapitulatif des informations du bot.

        Architecture et Localisation :
        - Les textes des champs ('botinfo_servers', 'botinfo_members', 'botinfo_ping')
          sont dynamiquement obtenus via `utils.text.get(ctx, ...)`.
        - L'avatar du bot est récupéré via `self.bot.user.display_avatar.url`.
        - Le total des membres est calculé avec `sum(guild.member_count or 0)` pour
          éviter tout plantage sur les guilds dont le cache n'a pas encore résolu le décompte.
        """
        # Création de l'Embed Discord violet aux couleurs du bot
        embed = discord.Embed(
            title=text.get(ctx, "botinfo_title", bot_name=BOT_NAME),
            color=discord.Color.purple(),
        )

        # Affichage de l'avatar du bot en miniature
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Nombre de serveurs où le bot est présent
        embed.add_field(
            name=text.get(ctx, "botinfo_servers"),
            value=str(len(self.bot.guilds)),
        )

        # Somme des membres de tous les serveurs
        embed.add_field(
            name=text.get(ctx, "botinfo_members"),
            value=str(sum(guild.member_count or 0 for guild in self.bot.guilds)),
        )

        # Nombre de réseaux / joueurs enregistrés en base
        player_count = 0
        try:
            if hasattr(self.bot, "root_service") and self.bot.root_service.database:
                row = await self.bot.root_service.database.run(
                    lambda tx: tx.one("SELECT COUNT(*) as total FROM players"),
                    readonly=True,
                )
                if row:
                    player_count = row.get("total", 0)
        except Exception:
            player_count = 0

        embed.add_field(
            name=text.get(ctx, "botinfo_players"),
            value=f"{player_count:,}",
        )

        # Uptime du bot
        uptime_str = "En ligne"
        if hasattr(self.bot, "start_time") and self.bot.start_time:
            uptime_str = f"<t:{int(self.bot.start_time.timestamp())}:R>"

        embed.add_field(
            name=text.get(ctx, "botinfo_uptime"),
            value=uptime_str,
        )

        # Latence Gateway WebSocket
        embed.add_field(
            name=text.get(ctx, "botinfo_ping"),
            value=f"{round(self.bot.latency * 1000)}ms",
        )

        # Lien d'invitation officiel du bot
        embed.add_field(
            name=text.get(ctx, "botinfo_invite"),
            value=text.get(ctx, "botinfo_invite_link", bot_name=BOT_NAME, invite_url=INVITE_URL),
            inline=False,
        )

        # Bouton d'invitation directe
        btn_label = text.get(ctx, "invite_button_label", bot_name=BOT_NAME)
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label=btn_label,
                url=INVITE_URL,
                style=discord.ButtonStyle.link,
                emoji="🔗",
            )
        )

        # Envoi unifié de l'Embed
        if hasattr(ctx, "respond"):
            await ctx.respond(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    # ── Version Commande Slash ───────────────────────────────────────────────────
    @discord.slash_command(
        guild_ids=GUILD_WHITELIST or None,
        description=desc["botinfo"],
        description_localizations=desc_loc["botinfo"],
    )
    async def botinfo(self, ctx):
        """Commande Slash /botinfo."""
        await self._botinfo_logic(ctx)

    # ── Version Commande avec Préfixe ────────────────────────────────────────────
    @commands.command(name="botinfo")
    async def botinfo_prefix(self, ctx):
        """Commande avec préfixe !botinfo."""
        await self._botinfo_logic(ctx)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(BotInfo(bot))
