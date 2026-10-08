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
    build_farm_container,
    build_farm_embed,
    build_hardware_container,
    build_hardware_embed,
    build_operations_container,
    build_operations_embed,
    build_overview_container,
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


class NetworkActionView(discord.ui.DesignerView):
    """Poste de commande interactif Root OS basé sur Discord Components V2.
    
    Structure visuelle (identique au mockup) :
    - Image panoramique au sommet (MediaGallery)
    - Titre >_ ROOT OS / USERNAME et séparateur
    - Statistiques avec emojis stylisés et barre latérale turquoise/ambrée
    - Rangée de boutons intégrée dans le conteneur :
      * [ 📥 Récolter ({montant} RTM) ] (Vert si buffer > 0, Gris désactivé si 0)
      * [ ⚙️ Matériel ] (Gris / Secondaire, bascule vers la vue matériel)
      * [ 🔄 Actualiser ] (Bleu / Primaire, actualise les données)
    """

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
        self.current_view = 'overview'  # 'overview', 'hardware', 'operations'
        self.current_file = None
        self.current_embed = None
        self._top_items = []
        self._container = None
        self.lock = asyncio.Lock()
        self.message = None

        self._rebuild_components()

    def add_item(self, item):
        self._top_items.append(item)
        return super().add_item(item)

    def clear_items(self):
        self._top_items.clear()
        super().clear_items()

    def to_components(self):
        return [item.to_component_dict() for item in self._top_items]

    def is_components_v2(self) -> bool:
        return True

    def walk_children(self):
        for item in self._top_items:
            if hasattr(item, 'walk_items'):
                yield from item.walk_items()
            else:
                yield item

    @property
    def children(self):
        return list(self.walk_children())

    @children.setter
    def children(self, val):
        pass

    def _rebuild_components(self):
        """Reconstruit le conteneur Discord V2 et ses boutons intégrés selon la vue active."""
        self.clear_items()
        is_fr = (text.get_locale(self.ctx) == 'fr')

        mining_state = self.last_result.get('mining_state') or {}
        buffer_val = Decimal(str(mining_state.get('buffer', 0)))
        has_buffer = (buffer_val > 0)

        # Label dynamique du bouton Récolter
        if has_buffer:
            base_label = "Récolter" if is_fr else "Claim"
            claim_label = f"{base_label} ({text.format_rtm(buffer_val)} RTM)"
        else:
            claim_label = "Récolter" if is_fr else "Claim"

        claim_btn = discord.ui.Button(
            label=claim_label,
            emoji=get_button_emoji("root_recolter") or "📥",
            style=discord.ButtonStyle.success if has_buffer else discord.ButtonStyle.secondary,
            disabled=not has_buffer,
        )
        claim_btn.callback = self._on_claim

        refresh_btn = discord.ui.Button(
            label="Actualiser" if is_fr else "Refresh",
            emoji=get_button_emoji("root_temps") or "🔄",
            style=discord.ButtonStyle.primary,
        )
        refresh_btn.callback = self._on_refresh

        locale = text.get_locale(self.ctx)

        home_btn = discord.ui.Button(
            label="Accueil" if is_fr else "Home",
            emoji=get_button_emoji("root_terminal") or "🖥️",
            style=discord.ButtonStyle.secondary,
        )
        home_btn.callback = self._on_switch_overview

        farm_btn = discord.ui.Button(
            label="Ferme" if is_fr else "Farm",
            emoji=get_button_emoji("root_ferme") or "🖧",
            style=discord.ButtonStyle.secondary,
        )
        farm_btn.callback = self._on_switch_farm

        mat_btn = discord.ui.Button(
            label="Matériel" if is_fr else "Hardware",
            emoji=get_button_emoji("root_materiel") or "⚙️",
            style=discord.ButtonStyle.secondary,
        )
        mat_btn.callback = self._on_switch_hardware

        ops_btn = discord.ui.Button(
            label="Opérations" if is_fr else "Operations",
            emoji=get_button_emoji("root_operations") or "⚔️",
            style=discord.ButtonStyle.secondary,
        )
        ops_btn.callback = self._on_switch_operations

        if self.current_view == 'farm':
            container, file = build_farm_container(
                self.last_result,
                locale=locale,
                display_name=self.display_name,
            )
            container.add_row(home_btn, mat_btn, ops_btn)
            container.add_row(claim_btn, refresh_btn)

        elif self.current_view == 'hardware':
            container, file = build_hardware_container(
                self.last_result,
                locale=locale,
                display_name=self.display_name,
            )
            container.add_row(home_btn, farm_btn, ops_btn)
            container.add_row(claim_btn, refresh_btn)

        elif self.current_view == 'operations':
            container, file = build_operations_container(
                self.last_result,
                locale=locale,
                display_name=self.display_name,
            )
            container.add_row(home_btn, farm_btn, mat_btn)
            container.add_row(claim_btn, refresh_btn)

        else:
            # Vue standard : Accueil (Overview)
            container, file = build_overview_container(
                self.last_result,
                locale=locale,
                display_name=self.display_name,
            )
            container.add_row(farm_btn, mat_btn, ops_btn)
            container.add_row(claim_btn, refresh_btn)

        self._container = container
        self.current_file = file
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return False
        return True

    async def _on_switch_overview(self, interaction: discord.Interaction):
        """Bascule vers la vue Accueil."""
        async with self.lock:
            await interaction.response.defer()
            self.current_view = 'overview'
            self._rebuild_components()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                logger.exception("Erreur lors du retour à l'accueil network")

    async def _on_switch_farm(self, interaction: discord.Interaction):
        """Bascule vers la vue Ferme."""
        async with self.lock:
            await interaction.response.defer()
            self.current_view = 'farm'
            self._rebuild_components()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                logger.exception("Erreur lors du passage à la vue ferme network")

    async def _on_switch_hardware(self, interaction: discord.Interaction):
        """Bascule vers la vue Matériel."""
        async with self.lock:
            await interaction.response.defer()
            self.current_view = 'hardware'
            self._rebuild_components()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                logger.exception("Erreur lors du passage à la vue matériel network")

    async def _on_switch_operations(self, interaction: discord.Interaction):
        """Bascule vers la vue Opérations."""
        async with self.lock:
            await interaction.response.defer()
            self.current_view = 'operations'
            self._rebuild_components()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                logger.exception("Erreur lors du passage à la vue opérations network")

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
            self._rebuild_components()
            try:
                await interaction.message.edit(view=self)
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
            self._rebuild_components()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                logger.exception("Erreur lors du rafraîchissement network")

    async def on_timeout(self):
        """Désactive les contrôles lors de l'expiration du timeout."""
        if self._container:
            self._container.disable_all_items()
        if self.message:
            try:
                await self.message.edit(view=self)
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
        """Envoie l'Accueil initial avec le conteneur Discord V2 et ses boutons intégrés."""
        author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
        author_name = getattr(author, 'display_name', str(result.get('discord_id', '')))
        avatar_url = author.display_avatar.url if author and hasattr(author, 'display_avatar') else None
        locale = text.get_locale(ctx)

        view = NetworkActionView(self, ctx, result)
        kwargs: dict[str, Any] = {
            'view': view,
            'allowed_mentions': discord.AllowedMentions.none(),
        }
        if view.current_file:
            kwargs['file'] = view.current_file

        try:
            if getattr(ctx, 'interaction', None):
                msg = await ctx.respond(**kwargs)
            else:
                msg = await ctx.send(**kwargs)
            view.message = getattr(msg, 'message', None) or msg
        except Exception as e:
            logger.exception("Échec envoi V2 components network, repli sur embed V1: %s", e)
            embed, file = build_overview_embed(result, locale=locale, display_name=author_name, avatar_url=avatar_url)
            fb_view = discord.ui.View()
            fb_kwargs: dict[str, Any] = {
                'embed': embed,
                'view': fb_view,
                'allowed_mentions': discord.AllowedMentions.none(),
            }
            if file:
                fb_kwargs['file'] = file
            if getattr(ctx, 'interaction', None):
                msg = await ctx.respond(**fb_kwargs)
            else:
                msg = await ctx.send(**fb_kwargs)
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
