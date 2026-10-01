"""
Commande /network et !network (alias !n) — Poste de commande central Root OS.

Ce module constitue l'interface principale et navigable du joueur :
- Poste de commande navigable en 4 vues unifiées dans le même message :
  1. Accueil : Identité, état du minage, portefeuille, protection, identifiant et progression d'infrastructure.
  2. Ferme : Débits de hachage, production horaire, mémoire vive, détail des mineurs et automatisation.
  3. Matériel : Inventaire complet (Minage, Attaque, Défense) regroupé par tier et accès à la boutique.
  4. Opérations : Stock ATK consommable, détail des modules ATK/DEF par tier, préparatifs, attaques et représailles.
- Chaque vue inclut obligatoirement la scène panoramique du niveau d'infrastructure courant.
- Deux actions rapides permanentes : Récolter et Actualiser.
- Actions contextuelles intégrées : Améliorer, Ouvrir la boutique, raccourcis d'opérations.
- Création automatique du compte joueur à l'initialisation et onboarding linguistique.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Any

import discord
from discord.ext import commands, tasks

import data
from commands.game.claim import log_claim_events
from commands.game.commandgame import BaseGameCog
from game.game_error import GameError
from game.math_config import MathConfig
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.check import Check
from utils.confirmation import Confirmation
from utils.infrastructure_display import (
    get_infrastructure_file,
    sanitize_level,
)
from utils.language_manager import set_user_language
from utils.logger import Logger
from utils.network_display import (
    build_farm_embed,
    build_hardware_embed,
    build_operations_embed,
    build_overview_embed,
)
from utils.root_emojis import get_button_emoji
from utils.root_theme import build_footer_text

logger = logging.getLogger(__name__)


def _secret_id_check_interval() -> int:
    """Intervalle de la boucle de rotation, lu depuis data/math.json."""
    return int(MathConfig.load().get('secret_id', {}).get('check_interval_seconds', 30))


def _build_compact_total_lines(ctx, stats, firewall_level, mining_state, bay_details, is_fr, rep_val, rep_pct) -> str:
    """Helper de compatibilité pour le formatage du temps de remplissage."""
    fill_sec = mining_state.get('seconds_to_full')
    if fill_sec is not None:
        m = int(fill_sec) // 60
        s = int(fill_sec) % 60
        dur = f"{m}min" if s == 0 else f"{m}min {s}s"
        return f"**Plein dans** : **{dur}**"
    return ""


_LANG_BUTTONS = {
    'en': ('🇬🇧', 'English'),
    'fr': ('🇫🇷', 'Français'),
}


def _slash_or_english(ctx) -> str:
    """Langue du client slash si supportée, sinon anglais."""
    interaction = getattr(ctx, 'interaction', None)
    locale = getattr(interaction, 'locale', None) if interaction else None
    if locale:
        code = str(locale)[:2].lower()
        if code in data.SUPPORTED_LANGS:
            return code
    return 'en'


def _command_prefix(ctx) -> str:
    """Préfixe à afficher dans l'intro : `/` en slash, sinon le préfixe du serveur."""
    if getattr(ctx, 'interaction', None):
        return '/'
    return getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')


class WelcomeLanguageView(discord.ui.View):
    """Sélecteur de langue au premier réseau."""

    def __init__(self, author_id: int, prompt_lang: str, prefix: str):
        super().__init__(timeout=300)
        self.author_id = int(author_id)
        self.prompt_lang = prompt_lang
        self.prefix = prefix
        self.done = False
        self.message = None

        codes = []
        if prompt_lang in data.SUPPORTED_LANGS:
            codes.append(prompt_lang)
        if 'en' not in codes:
            codes.append('en')
        for extra in data.SUPPORTED_LANGS:
            if extra not in codes:
                codes.append(extra)

        for code in codes:
            emoji, label = _LANG_BUTTONS.get(code, ('🌐', code.upper()))
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary)
            button.callback = self._callback_for(code)
            self.add_item(button)

    def _callback_for(self, lang: str):
        async def _on_click(interaction: discord.Interaction):
            await self._choose(interaction, lang)
        return _on_click

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                text.get_for_lang(self.prompt_lang, 'no_permission'),
                ephemeral=True,
            )
            return False
        return True

    async def _choose(self, interaction: discord.Interaction, lang: str):
        if self.done:
            await interaction.response.send_message(
                text.get_for_lang(lang, 'g_already_handled'),
                ephemeral=True,
            )
            return
        self.done = True
        self.stop()
        await set_user_language(self.author_id, lang)
        tip = text.get_for_lang(lang, 'g_welcome_onboarding', prefix=self.prefix)
        await interaction.response.edit_message(content=tip, view=None)

    async def on_timeout(self):
        if self.done:
            return
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class NetworkActionView(discord.ui.View):
    """Poste de commande interactif : navigation en 4 vues, récolte, actualisation et actions contextuelles."""

    def __init__(self, cog, ctx, result):
        timeout = 180
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            timeout = None
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
        self.author_id = author.id if author else int(result.get('discord_id', 0))
        self.display_name = getattr(author, 'display_name', str(self.author_id))
        self.avatar_url = author.display_avatar.url if author and hasattr(author, 'display_avatar') else None

        self.last_result = result
        self.current_view = 'overview'  # 'overview', 'farm', 'hardware', 'operations'
        self.current_page = 1
        self.total_pages = 1
        self.current_level = sanitize_level(result.get('firewall_level', 0))
        self.current_embed = None
        self.lock = asyncio.Lock()
        self.message = None

        self._rebuild_components()

    def _rebuild_components(self):
        """Reconstruit dynamiquement le menu de navigation et les boutons selon la vue active."""
        self.clear_items()
        is_fr = (text.get_locale(self.ctx) == 'fr')

        # ── Row 0 : Sélecteur des 4 vues ─────────────────────────────────────
        view_select = discord.ui.Select(
            placeholder="Naviguer dans le poste de commande" if is_fr else "Navigate command center",
            min_values=1,
            max_values=1,
            row=0,
            options=[
                discord.SelectOption(
                    label="Accueil" if is_fr else "Overview",
                    value="overview",
                    description="Tableau de bord et infrastructure" if is_fr else "Dashboard and infrastructure",
                    emoji=get_button_emoji("root_terminal") or "🖥️",
                    default=(self.current_view == 'overview'),
                ),
                discord.SelectOption(
                    label="Ferme" if is_fr else "Farm",
                    value="farm",
                    description="Minage, mémoire et automatisation" if is_fr else "Mining, memory and automation",
                    emoji=get_button_emoji("root_ferme") or "⛏️",
                    default=(self.current_view == 'farm'),
                ),
                discord.SelectOption(
                    label="Matériel" if is_fr else "Hardware",
                    value="hardware",
                    description="Équipements et accès boutique" if is_fr else "Hardware and shop access",
                    emoji=get_button_emoji("root_materiel") or "⚙️",
                    default=(self.current_view == 'hardware'),
                ),
                discord.SelectOption(
                    label="Opérations" if is_fr else "Operations",
                    value="operations",
                    description="ATK, PvP, préparatifs et attaques" if is_fr else "ATK, PvP, preparations and attacks",
                    emoji=get_button_emoji("root_operations") or "⚔️",
                    default=(self.current_view == 'operations'),
                ),
            ],
        )
        view_select.callback = self._on_select_view
        self.add_item(view_select)

        # ── Row 1 : Actions rapides permanentes (Récolter & Actualiser) ───────
        mining_state = self.last_result.get('mining_state') or {}
        buffer_val = Decimal(str(mining_state.get('buffer', 0)))
        has_buffer = (buffer_val > 0)

        if has_buffer:
            from utils.text import format_rtm
            base_label = "Récolter" if is_fr else "Claim"
            claim_label = f"{base_label} ({format_rtm(buffer_val)} RTM)"
        else:
            claim_label = "Récolter" if is_fr else "Claim"

        claim_btn = discord.ui.Button(
            label=claim_label,
            emoji=get_button_emoji("root_recolter") or "🪙",
            style=discord.ButtonStyle.success if has_buffer else discord.ButtonStyle.secondary,
            disabled=not has_buffer,
            row=1,
        )
        claim_btn.callback = self._on_claim
        self.add_item(claim_btn)

        refresh_btn = discord.ui.Button(
            label="Actualiser" if is_fr else "Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.primary,
            row=1,
        )
        refresh_btn.callback = self._on_refresh
        self.add_item(refresh_btn)

        # ── Row 2 : Actions contextuelles selon la vue ────────────────────────
        if self.current_view == 'overview':
            pending_up = self.last_result.get('pending_upgrade')
            can_upgrade = (pending_up is None and self.current_level < 5)
            upgrade_btn = discord.ui.Button(
                label="Améliorer" if is_fr else "Upgrade",
                emoji=get_button_emoji("root_connexions") or "🚀",
                style=discord.ButtonStyle.primary if can_upgrade else discord.ButtonStyle.secondary,
                disabled=not can_upgrade,
                row=2,
            )
            upgrade_btn.callback = self._on_upgrade_click
            self.add_item(upgrade_btn)

        elif self.current_view == 'hardware':
            shop_btn = discord.ui.Button(
                label="Ouvrir la boutique" if is_fr else "Open Shop",
                emoji="🛒",
                style=discord.ButtonStyle.secondary,
                row=2,
            )
            shop_btn.callback = self._on_shop_click
            self.add_item(shop_btn)

        elif self.current_view == 'operations':
            compile_btn = discord.ui.Button(
                label="Compiler" if is_fr else "Compile",
                emoji="🔨",
                style=discord.ButtonStyle.secondary,
                row=2,
            )
            compile_btn.callback = self._on_compile_click
            self.add_item(compile_btn)

            scan_btn = discord.ui.Button(
                label="Scanner" if is_fr else "Scan",
                emoji=get_button_emoji("root_scan") or "📡",
                style=discord.ButtonStyle.secondary,
                row=2,
            )
            scan_btn.callback = self._on_scan_click
            self.add_item(scan_btn)

            hack_btn = discord.ui.Button(
                label="Attaquer" if is_fr else "Attack",
                emoji="⚔️",
                style=discord.ButtonStyle.danger,
                row=2,
            )
            hack_btn.callback = self._on_hack_click
            self.add_item(hack_btn)

            # Pagination pour Opérations si nécessaire
            if self.total_pages > 1:
                prev_btn = discord.ui.Button(
                    label="◀",
                    style=discord.ButtonStyle.secondary,
                    disabled=(self.current_page <= 1),
                    row=2,
                )
                prev_btn.callback = self._on_prev_page
                self.add_item(prev_btn)

                next_btn = discord.ui.Button(
                    label="▶",
                    style=discord.ButtonStyle.secondary,
                    disabled=(self.current_page >= self.total_pages),
                    row=2,
                )
                next_btn.callback = self._on_next_page
                self.add_item(next_btn)

    def _render_current_view(self) -> tuple[discord.Embed, discord.File | None]:
        """Construit l'embed et l'éventuel fichier d'illustration correspondant à la vue active."""
        locale = text.get_locale(self.ctx)
        lvl = sanitize_level(self.last_result.get('firewall_level', 0))

        if self.current_view == 'farm':
            embed, file = build_farm_embed(
                self.last_result,
                locale=locale,
                display_name=self.display_name,
                avatar_url=self.avatar_url,
            )
        elif self.current_view == 'hardware':
            embed, file = build_hardware_embed(
                self.last_result,
                locale=locale,
                display_name=self.display_name,
                avatar_url=self.avatar_url,
            )
        elif self.current_view == 'operations':
            embed, file, tot_pages = build_operations_embed(
                self.last_result,
                locale=locale,
                display_name=self.display_name,
                page=self.current_page,
                avatar_url=self.avatar_url,
            )
            self.total_pages = tot_pages
        else:
            embed, file = build_overview_embed(
                self.last_result,
                locale=locale,
                display_name=self.display_name,
                avatar_url=self.avatar_url,
            )

        self.current_embed = embed
        return embed, file

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return False
        return True

    async def _on_select_view(self, interaction: discord.Interaction):
        """Bascule entre les 4 vues dans le même message."""
        async with self.lock:
            await interaction.response.defer()
            selected = interaction.data['values'][0]
            self.current_view = selected
            if selected == 'operations':
                self.current_page = 1

            embed, file = self._render_current_view()
            self._rebuild_components()

            new_lvl = sanitize_level(self.last_result.get('firewall_level', 0))
            edit_kwargs: dict[str, Any] = {'embed': embed, 'view': self}
            if new_lvl != self.current_level and file:
                edit_kwargs['file'] = file
                self.current_level = new_lvl

            try:
                await interaction.message.edit(**edit_kwargs)
            except Exception:
                logger.exception("Erreur lors du changement de vue network")

    async def _on_claim(self, interaction: discord.Interaction):
        """Exécute la récolte du Rootium en mémoire et actualise le panneau."""
        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.cog.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(text.get(self.ctx, err_key), ephemeral=True)
            return
        async with self.lock:
            await interaction.response.defer()
            try:
                claim_res = await self.cog.service.execute(
                    self.author_id,
                    interaction.guild.id if interaction.guild else None,
                    'claim',
                )
                if claim_res.get('claimed'):
                    amount = Decimal(str(claim_res.get('amount', 0)))
                    toast = text.get(self.ctx, 'g_net_claim_toast', amount=text.format_rtm(amount))
                    await interaction.followup.send(toast, ephemeral=True)
                    log_ctx = interaction if getattr(interaction, 'guild', None) else self.ctx
                    await log_claim_events(self.cog.bot, log_ctx, amount, claim_res)
            except Exception as err:
                if hasattr(err, 'key'):
                    err_msg = text.get(self.ctx, 'g_error_' + err.key, **getattr(err, 'values', {}))
                else:
                    err_msg = str(err)
                await interaction.followup.send(err_msg, ephemeral=True)
                return

            # Recharger network et rafraîchir
            self.last_result = await self.cog.service.execute(
                self.author_id,
                interaction.guild.id if interaction.guild else None,
                'network',
            )
            embed, file = self._render_current_view()
            self._rebuild_components()

            new_lvl = sanitize_level(self.last_result.get('firewall_level', 0))
            edit_kwargs: dict[str, Any] = {'embed': embed, 'view': self}
            if new_lvl != self.current_level and file:
                edit_kwargs['file'] = file
                self.current_level = new_lvl

            try:
                await interaction.message.edit(**edit_kwargs)
            except Exception:
                logger.exception("Erreur lors de l'actualisation après claim")

    async def _on_refresh(self, interaction: discord.Interaction):
        """Actualise les données de la vue active."""
        async with self.lock:
            await interaction.response.defer()
            self.last_result = await self.cog.service.execute(
                self.author_id,
                interaction.guild.id if interaction.guild else None,
                'network',
            )
            embed, file = self._render_current_view()
            self._rebuild_components()

            new_lvl = sanitize_level(self.last_result.get('firewall_level', 0))
            edit_kwargs: dict[str, Any] = {'embed': embed, 'view': self}
            if new_lvl != self.current_level and file:
                edit_kwargs['file'] = file
                self.current_level = new_lvl

            try:
                await interaction.message.edit(**edit_kwargs)
            except Exception:
                logger.exception("Erreur lors du rafraîchissement network")

    async def _on_upgrade_click(self, interaction: discord.Interaction):
        """Ouvre le devis d'amélioration d'infrastructure dans une confirmation séparée."""
        await interaction.response.defer(ephemeral=True)
        try:
            upgrade_cog = self.cog.bot.get_cog('Upgrade')
            if upgrade_cog:
                quote_res = await self.cog.service.execute(
                    self.author_id,
                    interaction.guild.id if interaction.guild else None,
                    'upgrade',
                    confirm=False,
                )
                await upgrade_cog._send(interaction, 'upgrade', quote_res)
            else:
                await interaction.followup.send(
                    "Utilise `/upgrade` pour consulter le devis d'amélioration.",
                    ephemeral=True,
                )
        except GameError as err:
            err_msg = text.get(self.ctx, 'g_error_' + err.key, **err.values)
            await interaction.followup.send(err_msg, ephemeral=True)
        except Exception:
            logger.exception("Erreur lors de l'accès au devis upgrade")
            await interaction.followup.send("Impossible d'ouvrir le devis.", ephemeral=True)

    async def _on_shop_click(self, interaction: discord.Interaction):
        """Ouvre le catalogue de la boutique dans un panneau séparé."""
        await interaction.response.defer(ephemeral=True)
        try:
            buy_cog = self.cog.bot.get_cog('Buy')
            if buy_cog:
                player_data = await self.cog.service.execute(
                    self.author_id,
                    interaction.guild.id if interaction.guild else None,
                    'network',
                )
                from commands.game.buy import ShopCatalogView
                view = ShopCatalogView(buy_cog, self.ctx, player_data=player_data, current_category='mining')
                embed = buy_cog._build_category_shop_embed(self.ctx, 'mining', player_data)
                msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                view.message = getattr(msg, 'message', None) or msg
            else:
                await interaction.followup.send("Utilise `/buy` pour consulter la boutique.", ephemeral=True)
        except Exception:
            logger.exception("Erreur lors de l'ouverture de la boutique")
            await interaction.followup.send("Impossible d'ouvrir la boutique.", ephemeral=True)

    async def _on_compile_click(self, interaction: discord.Interaction):
        """Aide ou lanceur rapide pour la compilation ATK."""
        is_fr = (text.get_locale(self.ctx) == 'fr')
        hint = (
            "⚙️ **Compilation ATK**\n"
            "Pour lancer une compilation, utilise :\n"
            "• `/compile method:unskilled atk:<nombre|all>`\n"
            "• `/compile method:skilled atk:<nombre|all>`\n"
            "• `/compile method:ai atk:<nombre|all>`"
        ) if is_fr else (
            "⚙️ **ATK Compilation**\n"
            "To start compilation, use:\n"
            "• `/compile method:unskilled atk:<amount|all>`\n"
            "• `/compile method:skilled atk:<amount|all>`\n"
            "• `/compile method:ai atk:<amount|all>`"
        )
        await interaction.response.send_message(hint, ephemeral=True)

    async def _on_scan_click(self, interaction: discord.Interaction):
        """Aide ou lanceur rapide pour le scan PvP."""
        is_fr = (text.get_locale(self.ctx) == 'fr')
        hint = (
            "📡 **Scan Réseau PvP**\n"
            "Pour scanner un joueur adverse et tenter d'obtenir son Secret ID :\n"
            "• `/scan target:<@joueur>`"
        ) if is_fr else (
            "📡 **PvP Network Scan**\n"
            "To scan an opponent and attempt to breach their Secret ID:\n"
            "• `/scan target:<@player>`"
        )
        await interaction.response.send_message(hint, ephemeral=True)

    async def _on_hack_click(self, interaction: discord.Interaction):
        """Aide ou lanceur rapide pour l'attaque PvP."""
        is_fr = (text.get_locale(self.ctx) == 'fr')
        hint = (
            "⚔️ **Attaque PvP (/hack)**\n"
            "Pour déployer une attaque contre un système adverse :\n"
            "• `/hack secret_id:<code_secret> attack_points:<points> target:<mining|attack>`"
        ) if is_fr else (
            "⚔️ **PvP Attack (/hack)**\n"
            "To deploy an offensive intrusion against an opponent:\n"
            "• `/hack secret_id:<secret_code> attack_points:<points> target:<mining|attack>`"
        )
        await interaction.response.send_message(hint, ephemeral=True)

    async def _on_prev_page(self, interaction: discord.Interaction):
        """Page précédente dans Opérations."""
        if self.current_page > 1:
            self.current_page -= 1
            await self._on_select_view(interaction)

    async def _on_next_page(self, interaction: discord.Interaction):
        """Page suivante dans Opérations."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            await self._on_select_view(interaction)

    async def on_timeout(self):
        """Désactive les contrôles et affiche la mention d'expiration propre."""
        for item in self.children:
            item.disabled = True
        if self.message and self.current_embed:
            is_fr = (text.get_locale(self.ctx) == 'fr')
            expired_footer = "Session expirée · Rouvre /network" if is_fr else "Session expired · Reopen /network"
            self.current_embed.set_footer(text=build_footer_text(expired_footer))
            try:
                await self.message.edit(embed=self.current_embed, view=self)
            except Exception:
                pass


class Network(BaseGameCog):
    """Cog gérant la commande centrale /network et le poste de commande du joueur."""

    def __init__(self, bot):
        self.bot = bot
        self.check_secret_rotation_loop.change_interval(seconds=_secret_id_check_interval())
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self.check_secret_rotation_loop.start()

    def cog_unload(self):
        """Arrête proprement la tâche périodique de rotation au déchargement du Cog."""
        self.check_secret_rotation_loop.cancel()

    @tasks.loop(seconds=_secret_id_check_interval())
    async def check_secret_rotation_loop(self):
        """Vérifie périodiquement si la rotation globale des secret ID est due."""
        try:
            result = await self.service.rotate_secret_ids_if_due()
            if result and result.get('rotated'):
                logger.info(
                    "%d identifiant(s) secret(s) régénéré(s), prochaine rotation %s",
                    result.get('count', 0),
                    result.get('next_at'),
                )
        except Exception:
            logger.exception("Erreur lors de la rotation des identifiants secrets")

    @check_secret_rotation_loop.before_loop
    async def before_check_secret_rotation_loop(self):
        """Attend que le bot soit prêt, puis rattrape immédiatement une rotation échue."""
        await self.bot.wait_until_ready()
        try:
            await self.service.rotate_secret_ids_if_due()
        except Exception:
            logger.exception("Erreur lors du rattrapage de rotation des identifiants secrets")

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='network',
        description=EN['network'],
        description_localizations={"fr": FR['network']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def network(self, ctx):
        """Commande Slash /network."""
        await self._invoke(ctx, 'network')

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='network', aliases=['n'], help=FR['network'])
    async def prefix_network(self, ctx):
        """Commande préfixe !network ou !n."""
        await self._invoke(ctx, 'network')

    # ── Rendu de l'Embed (utilisé aussi pour les tests et appels externes) ────
    def _build_network_embed(self, ctx, result, view_name: str = 'overview', page: int = 1):
        """Génère l'embed correspondant à la vue demandée (Accueil par défaut)."""
        author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
        author_name = getattr(author, 'display_name', str(result.get('discord_id', '')))
        avatar_url = author.display_avatar.url if author and hasattr(author, 'display_avatar') else None
        locale = text.get_locale(ctx)

        if view_name == 'farm':
            embed, _ = build_farm_embed(result, locale=locale, display_name=author_name, avatar_url=avatar_url)
        elif view_name == 'hardware':
            embed, _ = build_hardware_embed(result, locale=locale, display_name=author_name, avatar_url=avatar_url)
        elif view_name == 'operations':
            embed, _, _ = build_operations_embed(result, locale=locale, display_name=author_name, page=page, avatar_url=avatar_url)
        else:
            embed, _ = build_overview_embed(result, locale=locale, display_name=author_name, avatar_url=avatar_url)
        return embed

    async def _send(self, ctx, method, result):
        """Envoie l'Accueil initial avec l'illustration du niveau et la vue de navigation."""
        author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
        author_name = getattr(author, 'display_name', str(result.get('discord_id', '')))
        avatar_url = author.display_avatar.url if author and hasattr(author, 'display_avatar') else None
        locale = text.get_locale(ctx)

        embed, file = build_overview_embed(result, locale=locale, display_name=author_name, avatar_url=avatar_url)
        view = NetworkActionView(self, ctx, result)
        view.current_embed = embed

        kwargs: dict[str, Any] = {
            'embed': embed,
            'view': view,
            'allowed_mentions': discord.AllowedMentions.none(),
        }
        if file:
            kwargs['file'] = file

        if getattr(ctx, 'interaction', None):
            msg = await ctx.respond(**kwargs)
        else:
            msg = await ctx.send(**kwargs)
        view.message = getattr(msg, 'message', None) or msg

        if result.get('is_new'):
            await Logger(self.bot).log_new_player(ctx, result)
            await self._send_welcome_language(ctx)

    async def _send_welcome_language(self, ctx):
        """Propose le choix de langue au tout premier réseau, puis l'intro onboarding."""
        prompt_lang = _slash_or_english(ctx)
        prefix = _command_prefix(ctx)
        author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
        view = WelcomeLanguageView(author.id, prompt_lang, prefix)
        content = text.get_for_lang(prompt_lang, 'g_welcome_lang_pick')
        send_kwargs = {
            'content': content,
            'view': view,
            'allowed_mentions': discord.AllowedMentions.none(),
        }
        if getattr(ctx, 'interaction', None):
            msg = await ctx.followup.send(**send_kwargs)
        else:
            msg = await ctx.send(**send_kwargs)
        view.message = getattr(msg, 'message', None) or msg


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Network(bot))
