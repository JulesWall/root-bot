"""Commande /top et !top (alias !leaderboard) — Classement général des joueurs.

Ce module présente les classements de Root à travers 3 axes :
- `reputation` : Classement de prestige basé sur les votes d'honneur reçus des pairs.
- `usd` : Classement de fortune financière classique (dollars accumulés).
- `rtm` : Classement des plus grands détenteurs de la cryptomonnaie Rootium.

Fonctionnalités et Interface :
- Boutons interactifs (`TopView`) permettant de basculer instantanément d'une catégorie à une autre
  sans renvoyer de message. Le bouton de la catégorie active est visuellement désactivé.
- Médailles visuelles pour le podium (🥇 1er, 🥈 2e, 🥉 3e) et badges numérotés pour les suivants.
- Détection automatique et mise en évidence de la position du demandeur dans le footer de l'Embed.
"""

from decimal import Decimal

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from game.math_config import MathConfig
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.check import Check
from utils.root_embed import RootEmbed


class TopView(discord.ui.View):
    """Vue à onglets pour naviguer entre les différentes catégories du classement.

    Attributes:
        cog (Top): Référence vers le Cog pour réutiliser la construction de l'Embed.
        ctx: Contexte d'origine de la commande.
        message (discord.Message): Message hébergeant la vue pour la désactivation au timeout.
    """

    def __init__(self, cog, ctx, current_category='reputation'):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.message = None

        if current_category in ('hs', 'h/s', 'mining', 'h'):
            current_category = 'hashrate'
        elif current_category in ('rep',):
            current_category = 'reputation'
        elif current_category in ('event', 'e'):
            current_category = 'events'

        # Configuration des 4 catégories publiques avec leurs icônes respectives
        categories = [
            ('reputation', '🌟 ' + text.get(ctx, 'g_top_btn_rep')),
            ('usd',        '💵 ' + text.get(ctx, 'g_top_btn_usd')),
            ('events',     '🏆 ' + text.get(ctx, 'g_top_btn_events')),
            ('hashrate',   '⛏️ ' + text.get(ctx, 'g_top_btn_hs')),
        ]

        # Génération dynamique des boutons d'onglets
        for cat_id, label in categories:
            is_active = (cat_id == current_category)
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary,
                custom_id=f'top_cat_{cat_id}',
                disabled=is_active,  # Le bouton actif est grisé/désactivé
            )
            btn.callback = self._make_callback(cat_id)
            self.add_item(btn)

    def _make_callback(self, cat_id):
        """Fabrique un gestionnaire d'événement asynchrone pour l'onglet sélectionné."""
        async def callback(interaction):
            await interaction.response.defer()
            # Récupération des données du leaderboard pour la nouvelle catégorie
            result = await self.cog.service.execute(
                interaction.user.id,
                interaction.guild.id if interaction.guild else None,
                'top',
                category=cat_id,
            )
            # Reconstitution de l'Embed et rafraîchissement des boutons
            embed = self.cog._build_top_embed(self.ctx, result)
            new_view = TopView(self.cog, self.ctx, current_category=cat_id)
            await interaction.message.edit(embed=embed, view=new_view)
        return callback

    async def interaction_check(self, interaction):
        """Sécurité : restreint le changement d'onglet à l'auteur de la commande."""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return False
        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.ctx.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(text.get(self.ctx, err_key), ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        """Désactive les boutons après 3 minutes sans interaction."""
        for item in self.children:
            item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


class Top(BaseGameCog):
    """Cog gérant la commande /top et les tableaux des scores."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='top',
        description=EN['top'],
        description_localizations={"fr": FR['top']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def top(
        self,
        ctx,
        category: discord.Option(str, choices=['reputation', 'usd', 'events', 'hashrate']) = 'reputation',
    ):
        """Affiche le classement des meilleurs joueurs selon la catégorie choisie."""
        await self._invoke(ctx, 'top', category=category)

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='top', aliases=['leaderboard'], help=FR['top'])
    async def prefix_top(self, ctx, category: str = 'reputation'):
        """Commande préfixe !top [catégorie]."""
        raw_cat = category.lower().strip()
        if raw_cat in ('rep', 'reputation'):
            cat = 'reputation'
        elif raw_cat in ('event', 'events', 'e'):
            cat = 'events'
        elif raw_cat in ('usd', 'dollar', 'dollars', '$'):
            cat = 'usd'
        elif raw_cat in ('hashrate', 'hs', 'h/s', 'mining', 'h'):
            cat = 'hashrate'
        else:
            cat = 'reputation'
        await self._invoke(ctx, 'top', category=cat)

    # ── Rendu ────────────────────────────────────────────────────────────────
    def _build_top_embed(self, ctx, result):
        """Construit l'Embed Discord du classement avec mise en forme personnalisée par catégorie.

        Palette de couleurs :
        - Réputation : Or (Gold)
        - USD : Vert dollar (#2ECC71)
        - Événements : Cyan (#00B4F0)
        - Hashrate : Ambre (#FFAA00)
        """
        category = result.get('category', 'reputation')
        if category in ('rep', 'reputation'):
            category = 'reputation'
        elif category in ('event', 'events', 'e'):
            category = 'events'
        elif category in ('hashrate', 'hs', 'h/s', 'mining', 'h'):
            category = 'hashrate'
        ranking = result.get('ranking', [])

        cat_name = text.get(ctx, f'g_top_cat_{category}')
        title = text.get(ctx, 'g_top_title', category_name=cat_name)

        colors = {
            'reputation': discord.Color.gold(),
            'usd':        discord.Color.from_rgb(46, 204, 113),
            'events':     discord.Color.from_rgb(0, 180, 240),
            'hashrate':   discord.Color.from_rgb(255, 170, 0),
        }
        medals = {1: '🥇 **1er**', 2: '🥈 **2e** ', 3: '🥉 **3e** '}

        lines = []
        user_rank = None
        for i, row in enumerate(ranking, 1):
            discord_id = row['discord_id']
            score = row['score']

            # Détection de la position de l'auteur dans le tableau
            if getattr(ctx, 'author', None) and int(discord_id) == ctx.author.id:
                user_rank = i

            # Formatage spécifique au type de métrique
            if category == 'reputation':
                score_str = f"`{int(score):,}` pts"
            elif category == 'usd':
                score_str = f"`{Decimal(str(score)):,.2f}` USD"
            elif category == 'events':
                vic_count = int(score)
                is_fr = text.get_locale(ctx) == 'fr'
                vic_label = ("victoire" if vic_count <= 1 else "victoires") if is_fr else ("win" if vic_count <= 1 else "wins")
                score_str = f"`{vic_count:,}` {vic_label}"
            elif category == 'hashrate':
                score_str = f"`{MathConfig.format_hashrate(score)}`"
            else:
                score_str = f"`{score}`"

            rank_badge = medals.get(i, f"▫️ **`{i:02d}`**")
            lines.append(f"> {rank_badge} · <@{discord_id}> ➔ **{score_str}**")

        description = '\n'.join(lines) if lines else text.get(ctx, 'g_top_empty')
        footer_text = text.get(ctx, 'g_top_footer_user', rank=user_rank) if user_rank else text.get(ctx, 'g_top_footer')
        embed = RootEmbed(
            ctx,
            'top',
            content=description,
            title=title,
            footer=footer_text,
            color=colors.get(category, discord.Color.dark_teal()),
        )
        return embed

    async def _send(self, ctx, method, result):
        """Envoie l'Embed initial du leaderboard accompagné des boutons d'onglets `TopView`."""
        embed = self._build_top_embed(ctx, result)
        view = TopView(self, ctx, current_category=result.get('category', 'reputation'))
        kwargs = {'embed': embed, 'view': view, 'allowed_mentions': discord.AllowedMentions.none()}
        if getattr(ctx, 'interaction', None):
            msg = await ctx.respond(**kwargs)
            if hasattr(msg, 'message') and msg.message:
                view.message = msg.message
            elif isinstance(msg, discord.Message):
                view.message = msg
        else:
            msg = await ctx.send(**kwargs)
            view.message = msg


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Top(bot))
