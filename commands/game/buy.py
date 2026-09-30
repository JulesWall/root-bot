"""Commande /buy et !buy — Achat de modules matériels et défensifs.

Ce module gère le processus d'achat des composants de Root :
- Types de modules disponibles :
  - `mining` : modules de minage de Rootium (tiers 1 à 6).
  - `attack` : modules offensifs fournissant du Bit/s (tiers 1 à 5). Les points ATK se produisent via `/compile`.
  - `bay_defense` : modules de protection locale par baie (tiers 1 à 6).
  - `network_defense` : défense globale du réseau joueur.
- Mécanisme de validation à deux phases (Two-Phase Commit UI) :
  1. Phase Devis (Quote) : si la commande est lancée sans confirmation explicite,
     le moteur calcule le prix exact en dollars et en Rootium, et présente un devis
     avec les boutons [Confirmer] et [Annuler] via `utils.confirmation.Confirmation`.
  2. Phase Validation : si l'utilisateur clique sur Confirmer ou ajoute le paramètre 'confirm',
     la transaction financière est verrouillée et exécutée de façon atomique.
"""

import asyncio
from decimal import Decimal

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from game.db.players import _calculate_module_price
from game.game_error import GameError
from game.math_config import MathConfig
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.check import Check
from utils.confirmation import Confirmation
from utils.root_embed import RootEmbed


def _is_confirm(val):
    """Détermine si un argument textuel ou booléen représente une volonté explicite de confirmation.

    Supporte les valeurs booléennes True ainsi que les variantes textuelles
    courantes ('confirm', 'true', 'yes', 'valider').
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('confirm', 'true', 'yes', 'valider')
    return False


def _get_purchasable_options(ctx, kind: str, player_data: dict) -> list[discord.SelectOption]:
    """Construit la liste des modules achetables pour la catégorie donnée selon le solde et le pare-feu du joueur."""
    settings = MathConfig.load()
    options = []

    kinds_meta = {
        'mining': ('🪙', 'Minage' if text.get_locale(ctx) == 'fr' else 'Mining', 'mining_', 'USD'),
        'attack': ('⚔️', 'Attaque' if text.get_locale(ctx) == 'fr' else 'Attack', 'attack_', 'RTM'),
        'defense': ('🛡️', 'Défense' if text.get_locale(ctx) == 'fr' else 'Defense', 'bay_defense_', 'USD'),
    }
    meta = kinds_meta.get(kind)
    if not meta:
        return options

    emoji, kind_label, col_prefix, currency = meta
    internal_kind = 'bay_defense' if kind == 'defense' else kind

    player_fw = int(player_data.get('firewall_level') or 0)
    player_usd = Decimal(str(player_data.get('dollars') or 0))
    player_rtm = Decimal(str(player_data.get('rootium') or 0))
    max_tier_above = int(settings.get('firewall', {}).get('max_tier_above', 1))

    for tier in range(1, 6):
        col = f"{col_prefix}t{tier}"
        usd_p, rtm_p = _calculate_module_price(col, tier)
        required_firewall = max(
            int(settings.get('beta', {}).get('required_firewall', {}).get(internal_kind, 0)),
            tier - max_tier_above,
        )

        can_buy = (player_fw >= required_firewall) and (player_usd >= usd_p) and (player_rtm >= rtm_p)
        if not can_buy:
            continue

        price_str = f"{text.format_usd(usd_p)} $" if currency == 'USD' else f"{rtm_p:,.5f} RTM"
        if kind == 'mining':
            hs = settings.get('module_stats', {}).get('mining_hashrate_hs', {}).get(str(tier), 0)
            ram = settings.get('module_stats', {}).get('mining_ram_bytes', {}).get(str(tier), 0)
            hs_fmt = MathConfig.format_hashrate(hs)
            ram_fmt = MathConfig.format_memory(ram)
            bonus = f"+{hs_fmt} · +{ram_fmt}"
        elif kind == 'attack':
            bits = settings.get('module_stats', {}).get('attack_bits_per_s', {}).get(str(tier), 0)
            bonus = f"+{MathConfig.format_bits_per_s(bits)}"
        else:
            pw = settings.get('module_stats', {}).get('bay_defense_power', {}).get(str(tier), 0)
            bonus = f"+{pw} DEF"

        is_fr = text.get_locale(ctx) == 'fr'
        desc_text = f"Coût : {price_str} │ {bonus} (FW {required_firewall}+)" if is_fr else f"Cost: {price_str} │ {bonus} (FW {required_firewall}+)"
        options.append(
            discord.SelectOption(
                label=f"{kind_label} T{tier} — {price_str}",
                value=f"{kind}:{tier}",
                description=desc_text[:100],
                emoji=emoji,
            )
        )
    return options


def _get_shop_options(ctx) -> list[discord.SelectOption]:
    """Rétro-compatibilité : liste générale des 15 options T1 à T5."""
    settings = MathConfig.load()
    options = []
    kinds = [
        ('mining', '🪙', 'Minage' if text.get_locale(ctx) == 'fr' else 'Mining', 'mining_', 'USD'),
        ('attack', '⚔️', 'Attaque' if text.get_locale(ctx) == 'fr' else 'Attack', 'attack_', 'RTM'),
        ('defense', '🛡️', 'Défense' if text.get_locale(ctx) == 'fr' else 'Defense', 'bay_defense_', 'USD'),
    ]
    for kind_key, emoji, kind_label, col_prefix, currency in kinds:
        for tier in range(1, 6):
            col = f"{col_prefix}t{tier}"
            usd_p, rtm_p = _calculate_module_price(col, tier)
            price_str = f"{text.format_usd(usd_p)} $" if currency == 'USD' else f"{rtm_p:,.5f} RTM"
            if kind_key == 'mining':
                hs = settings.get('module_stats', {}).get('mining_hashrate_hs', {}).get(str(tier), 0)
                ram = settings.get('module_stats', {}).get('mining_ram_bytes', {}).get(str(tier), 0)
                hs_fmt = MathConfig.format_hashrate(hs)
                ram_fmt = MathConfig.format_memory(ram)
                bonus = f"+{hs_fmt} · +{ram_fmt}"
            elif kind_key == 'attack':
                bits = settings.get('module_stats', {}).get('attack_bits_per_s', {}).get(str(tier), 0)
                bonus = f"+{MathConfig.format_bits_per_s(bits)}"
            else:
                pw = settings.get('module_stats', {}).get('bay_defense_power', {}).get(str(tier), 0)
                bonus = f"+{pw} DEF"

            req_fw = max(int(settings.get('beta', {}).get('required_firewall', {}).get(kind_key if kind_key != 'defense' else 'bay_defense', 0)), tier - 1)
            is_fr = text.get_locale(ctx) == 'fr'
            desc_text = f"Coût : {price_str} │ {bonus} (FW {req_fw}+)" if is_fr else f"Cost: {price_str} │ {bonus} (FW {req_fw}+)"

            options.append(
                discord.SelectOption(
                    label=f"{kind_label} T{tier} — {price_str}",
                    value=f"{kind_key}:{tier}",
                    description=desc_text[:100],
                    emoji=emoji,
                )
            )
    return options


class ShopCatalogView(discord.ui.View):
    """Vue interactive du catalogue avec 3 boutons de catégorie, menu déroulant filtré et annulation."""

    def __init__(self, cog, ctx, player_data=None, current_category=None):
        timeout = 120
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            timeout = None
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.player_data = player_data or {}
        self.current_category = current_category
        self.author_id = getattr(ctx, 'author', None) and ctx.author.id or (getattr(ctx, 'user', None) and ctx.user.id)
        self.message = None
        self._rebuild_items()

    def _rebuild_items(self):
        self.clear_items()

        # Row 0 : 3 Boutons de catégories + Annuler
        btn_mining = discord.ui.Button(
            label=text.get(self.ctx, 'g_shop_btn_mining'),
            emoji="🪙",
            style=discord.ButtonStyle.primary if self.current_category == 'mining' else discord.ButtonStyle.secondary,
            row=0,
        )
        btn_mining.callback = self._on_click_mining
        self.add_item(btn_mining)

        btn_attack = discord.ui.Button(
            label=text.get(self.ctx, 'g_shop_btn_attack'),
            emoji="⚔️",
            style=discord.ButtonStyle.primary if self.current_category == 'attack' else discord.ButtonStyle.secondary,
            row=0,
        )
        btn_attack.callback = self._on_click_attack
        self.add_item(btn_attack)

        btn_defense = discord.ui.Button(
            label=text.get(self.ctx, 'g_shop_btn_defense'),
            emoji="🛡️",
            style=discord.ButtonStyle.primary if self.current_category == 'defense' else discord.ButtonStyle.secondary,
            row=0,
        )
        btn_defense.callback = self._on_click_defense
        self.add_item(btn_defense)

        cancel_btn = discord.ui.Button(
            label=text.get(self.ctx, 'g_shop_btn_close'),
            emoji="❌",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        cancel_btn.callback = self._on_cancel
        self.add_item(cancel_btn)

        # Row 1 : Menu déroulant pour la catégorie active (contenant UNIQUEMENT les modules achetables)
        if self.current_category:
            options = _get_purchasable_options(self.ctx, self.current_category, self.player_data)
            if options:
                select = discord.ui.Select(
                    placeholder=text.get(self.ctx, 'g_shop_select_placeholder'),
                    min_values=1,
                    max_values=1,
                    options=options,
                    row=1,
                )
                select.callback = self._on_select_module
                self.add_item(select)
            else:
                disabled_select = discord.ui.Select(
                    placeholder=text.get(self.ctx, 'g_shop_select_empty'),
                    min_values=1,
                    max_values=1,
                    disabled=True,
                    options=[discord.SelectOption(label="---", value="none")],
                    row=1,
                )
                self.add_item(disabled_select)

    async def _on_click_mining(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return
        self.current_category = 'mining'
        self._rebuild_items()
        embed = self.cog._build_category_shop_embed(self.ctx, 'mining', self.player_data)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_click_attack(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return
        self.current_category = 'attack'
        self._rebuild_items()
        embed = self.cog._build_category_shop_embed(self.ctx, 'attack', self.player_data)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_click_defense(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return
        self.current_category = 'defense'
        self._rebuild_items()
        embed = self.cog._build_category_shop_embed(self.ctx, 'defense', self.player_data)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_select_module(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return
        await interaction.response.defer()
        selected = interaction.data['values'][0]
        kind, tier_str = selected.split(':')
        tier = int(tier_str)
        try:
            result = await self.cog.service.execute(
                interaction.user.id,
                self.ctx.guild.id if self.ctx.guild else None,
                'buy',
                kind=kind,
                tier=tier,
                confirm=False,
            )
            await self.cog._send_quote_from_interaction(self.ctx, interaction, result)
        except GameError as error:
            err_msg = text.get(self.ctx, 'g_error_' + error.key, **error.values)
            await interaction.followup.send(err_msg, ephemeral=True)

    async def _on_cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return
        self.stop()
        cancelled_text = text.get(self.ctx, 'g_cancelled')
        if getattr(self.ctx, 'interaction', None):
            try:
                await self.ctx.interaction.edit_original_response(content=cancelled_text, embed=None, view=None)
            except Exception:
                pass
        elif self.message:
            try:
                await self.message.edit(content=cancelled_text, embed=None, view=None)
            except Exception:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return False
        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.ctx.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(text.get(self.ctx, err_key), ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if getattr(self.ctx, 'interaction', None):
            try:
                await self.ctx.interaction.edit_original_response(view=self)
            except Exception:
                pass
        elif self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


# Rétro-compatibilité pour les imports existants
ShopSelectView = ShopCatalogView


class Buy(BaseGameCog):
    """Cog gérant l'achat de modules d'infrastructure et de défense."""

    def __init__(self, bot):
        self.bot = bot

    def _build_shop_embed(self, ctx, player_data: dict = None) -> discord.Embed:
        """Rétro-compatibilité : délègue à _build_main_shop_embed."""
        return self._build_main_shop_embed(ctx, player_data or {})

    def _build_main_shop_embed(self, ctx, player_data: dict) -> discord.Embed:
        """Construit l'Embed d'accueil du catalogue détaillant les 3 filières."""
        prefix = '/' if getattr(ctx, 'interaction', None) else (getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!'))
        embed = discord.Embed(
            title=text.get(ctx, 'g_shop_title'),
            description=text.get(ctx, 'g_shop_description'),
            color=discord.Color.from_rgb(0, 220, 200),
        )
        embed.add_field(
            name=text.get(ctx, 'g_shop_field_mining'),
            value=text.get(ctx, 'g_shop_field_mining_desc', prefix=prefix),
            inline=False,
        )
        embed.add_field(
            name=text.get(ctx, 'g_shop_field_attack'),
            value=text.get(ctx, 'g_shop_field_attack_desc', prefix=prefix),
            inline=False,
        )
        embed.add_field(
            name=text.get(ctx, 'g_shop_field_defense'),
            value=text.get(ctx, 'g_shop_field_defense_desc', prefix=prefix),
            inline=False,
        )
        return embed

    def _build_category_shop_embed(self, ctx, kind: str, player_data: dict) -> discord.Embed:
        """Construit l'Embed détaillé d'une filière avec explications, syntaxe classique et ressources."""
        prefix = '/' if getattr(ctx, 'interaction', None) else (getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!'))
        title = text.get(ctx, f'g_shop_cat_{kind}_title')
        desc = text.get(ctx, f'g_shop_cat_{kind}_desc')
        syntax = text.get(ctx, f'g_shop_syntax_{kind}', prefix=prefix)

        embed = discord.Embed(
            title=title,
            description=desc,
            color=discord.Color.from_rgb(0, 220, 200),
        )
        embed.add_field(
            name=text.get(ctx, 'g_shop_syntax_field'),
            value=syntax,
            inline=False,
        )

        currency = 'RTM' if kind == 'attack' else 'USD'
        if currency == 'RTM':
            bal_str = f"{Decimal(str(player_data.get('rootium') or 0)):,.5f} RTM"
        else:
            bal_str = f"{text.format_usd(player_data.get('dollars') or 0)} USD"
        fw_lvl = player_data.get('firewall_level', 0)
        wallet_info = text.get(ctx, 'g_shop_wallet_info', balance=bal_str, fw=fw_lvl)
        embed.add_field(
            name=text.get(ctx, 'g_shop_wallet_field'),
            value=wallet_info,
            inline=False,
        )

        options = _get_purchasable_options(ctx, kind, player_data)
        if not options:
            embed.add_field(
                name="ℹ️",
                value=text.get(ctx, 'g_shop_no_affordable_hint'),
                inline=False,
            )
        return embed

    async def _send_catalog(self, ctx):
        """Affiche le catalogue interactif avec les 3 boutons de filières et menu déroulant filtré."""
        author_id = getattr(ctx, 'author', None) and ctx.author.id or (getattr(ctx, 'user', None) and ctx.user.id)
        guild_id = ctx.guild.id if ctx.guild else None
        player_data = await self.service.execute(author_id, guild_id, 'network')
        embed = self._build_main_shop_embed(ctx, player_data)
        view = ShopCatalogView(self, ctx, player_data)
        if getattr(ctx, 'interaction', None):
            msg = await ctx.respond(embed=embed, view=view)
        else:
            msg = await ctx.send(embed=embed, view=view)
        view.message = getattr(msg, 'message', None) or msg

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='buy',
        description=EN['buy'],
        description_localizations={"fr": FR['buy']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def buy(
        self,
        ctx,
        kind: discord.Option(
            str,
            choices=['mining', 'attack', 'defense'],
            required=False,
            default=None,
        ) = None,
        tier: discord.Option(
            int,
            description="Tier (1-5)",
            choices=[1, 2, 3, 4, 5],
            required=False,
            default=1,
        ) = 1,
        confirm: discord.Option(
            str, choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False, default=None,
        ) = None,
        count: discord.Option(
            str,
            description="Quantity to buy — integer or 'all' for max affordable (défaut: 1)",
            description_localizations={"fr": "Quantité à acheter — entier ou 'all' pour le maximum (défaut : 1)"},
            required=False,
            default='1',
        ) = '1',
    ):
        """Commande Slash /buy."""
        if not kind:
            await self._prefetch_lang(ctx.author.id)
            return await self._send_catalog(ctx)
        _ALL_TOKENS = {'all', 'max', 'tout'}
        raw = str(count).strip().lower()
        if raw in _ALL_TOKENS:
            await self._invoke(ctx, 'buy', kind=kind, tier=tier, all=True, confirm=_is_confirm(confirm))
        else:
            try:
                cnt = int(raw)
            except (ValueError, TypeError):
                cnt = 1
            await self._invoke(ctx, 'buy', kind=kind, tier=tier, count=cnt, confirm=_is_confirm(confirm))


    @commands.command(name='buy', help=FR['buy'])
    async def prefix_buy(self, ctx, kind: str = None, *args):
        """Commande préfixe !buy [kind] [tier] [count|all] [confirm].

        Exemples :
        - `!buy` -> affiche le catalogue interactif.
        - `!buy mining` -> devis pour un module de minage T1.
        - `!buy attack 3` -> devis pour un module d'attaque T3.
        - `!buy defense 3 20` -> devis pour 20 modules de défense T3.
        - `!buy defense 3 all` -> devis pour le maximum de modules de défense T3 achetables.
        - `!buy defense 3 20 confirm` -> validation immédiate pour 20 modules de défense T3.
        - `!buy defense 3 all confirm` -> achat immédiat du maximum de modules de défense T3.
        """
        if not kind:
            await self._prefetch_lang(ctx.author.id)
            return await self._send_catalog(ctx)

        valid_kinds = {'mining', 'attack', 'defense', 'bay_defense'}
        cleaned_kind = kind.lower().strip()

        if cleaned_kind not in valid_kinds:
            await self._prefetch_lang(ctx.author.id)
            prefix = getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')
            return await ctx.send(text.get(ctx, 'g_error_buy_usage', prefix=prefix))

        # Détecter "all" / "max" / "tout" comme token de quantité
        _ALL_TOKENS = {'all', 'max', 'tout'}
        want_all = any(str(a).strip().lower() in _ALL_TOKENS for a in args)

        # Extraire les chiffres (tier en premier, count éventuel en second)
        digits = [int(a) for a in args if str(a).isdigit()]
        tier = 1
        count = 1
        if len(digits) >= 2:
            tier = digits[0]
            count = digits[1]
        elif len(digits) == 1:
            tier = digits[0]
            # Si "all" est présent, le second chiffre est ignoré et want_all prévaut.

        if tier < 1 or tier > 5 or (not want_all and count < 1):
            await self._prefetch_lang(ctx.author.id)
            prefix = getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')
            return await ctx.send(text.get(ctx, 'g_error_buy_usage', prefix=prefix))

        confirm = any(_is_confirm(a) for a in args)
        invoke_kwargs = dict(kind=cleaned_kind, tier=tier, confirm=confirm)
        if want_all:
            invoke_kwargs['all'] = True
        else:
            invoke_kwargs['count'] = count
        await self._invoke(ctx, 'buy', **invoke_kwargs)

    # ── Rendu ────────────────────────────────────────────────────────────────
    def _label(self, ctx, kind, tier, count: int = 1):
        """Construit le libellé localisé de l'équipement (ex: 'Module de minage T2' ou '20x Module de minage T2')."""
        from lang import game_en, game_fr
        lang = game_fr if text.get_locale(ctx) == 'fr' else game_en
        base = f"{lang.labels.get(kind, kind)} T{tier}"
        if count and count > 1:
            return f"{count}x {base}"
        return base

    def _build_quote_content_and_view(self, ctx, result):
        """Construit le texte et la vue Confirmation du devis d'achat avec bilans avant/après."""
        usd_val = Decimal(str(result.get('usd_price', 0)))
        rtm_val = Decimal(str(result.get('rtm_price', 0)))
        kind, tier, count = result.get('kind'), result.get('tier'), result.get('count', 1)
        item = self._label(ctx, kind, tier, count)
        usd = text.format_usd(usd_val)
        rtm = f"{rtm_val:,.5f}"
        cur_usd = text.format_usd(result.get('current_usd', 0))
        rem_usd = text.format_usd(result.get('remaining_usd', 0))
        cur_rtm = f"{Decimal(str(result.get('current_rtm', 0))):,.5f}"
        rem_rtm = f"{Decimal(str(result.get('remaining_rtm', 0))):,.5f}"
        stat_gain_fmt = result.get('stat_gain_formatted', '')
        stat_cur_fmt = result.get('stat_current_formatted', '')
        stat_new_fmt = result.get('stat_new_formatted', '')
        ram_gain_fmt = result.get('ram_gain_formatted', '0 o')
        ram_new_fmt = result.get('ram_new_formatted', '0 o')

        if kind == 'mining':
            content = text.get(
                ctx, 'g_buy_quote_mining',
                item=item, usd=usd,
                cur_usd=cur_usd, rem_usd=rem_usd,
                stat_gain_formatted=stat_gain_fmt,
                stat_new_formatted=stat_new_fmt,
                ram_gain_formatted=ram_gain_fmt,
                ram_new_formatted=ram_new_fmt,
            )
        else:
            if usd_val > 0 and rtm_val > 0:
                quote_key = 'g_buy_quote'
            elif rtm_val > 0:
                quote_key = 'g_buy_quote_rtm'
            else:
                quote_key = 'g_buy_quote_usd'
            content = text.get(
                ctx, quote_key,
                item=item, usd=usd, rtm=rtm,
                cur_usd=cur_usd, rem_usd=rem_usd,
                cur_rtm=cur_rtm, rem_rtm=rem_rtm,
                stat_gain_formatted=stat_gain_fmt,
                stat_current_formatted=stat_cur_fmt,
                stat_new_formatted=stat_new_fmt,
            )

        confirmation_args = {'kind': kind, 'tier': tier, 'count': count, 'confirm': True}
        view = Confirmation(self._send, self.service, ctx, 'buy', confirmation_args)
        return content, view

    async def _send_quote_from_interaction(self, ctx, interaction, result):
        """Met à jour le message du catalogue pour afficher le devis suite à une sélection dans le menu."""
        content, view = self._build_quote_content_and_view(ctx, result)
        embed = RootEmbed(ctx, 'buy', content)
        if getattr(ctx, 'interaction', None):
            await ctx.interaction.edit_original_response(content=None, embed=embed, view=view)
        elif interaction.message:
            await interaction.message.edit(content=None, embed=embed, view=view)
        view.message = interaction.message

    async def _send(self, ctx, method, result):
        """Affiche le devis interactif ou la confirmation finale de l'achat."""
        usd_val = Decimal(str(result.get('usd_price', 0)))
        rtm_val = Decimal(str(result.get('rtm_price', 0)))
        kind, tier, count = result.get('kind'), result.get('tier'), result.get('count', 1)
        item = self._label(ctx, kind, tier, count)
        usd = text.format_usd(usd_val)
        rtm = f"{rtm_val:,.5f}"
        stat_gain_fmt = result.get('stat_gain_formatted', '')
        stat_cur_fmt = result.get('stat_current_formatted', '')
        stat_new_fmt = result.get('stat_new_formatted', '')
        ram_gain_fmt = result.get('ram_gain_formatted', '0 o')
        ram_new_fmt = result.get('ram_new_formatted', '0 o')

        if result.get('buy_quote'):
            content, view = self._build_quote_content_and_view(ctx, result)
            await self._send_embed(ctx, 'buy', content, view=view)
        else:
            # ── 2. Confirmation finale suite à l'achat effectif ─────────────────
            if kind == 'mining':
                content = text.get(
                    ctx, 'g_buy_success_mining',
                    item=item, usd=usd,
                    stat_gain_formatted=stat_gain_fmt,
                    stat_new_formatted=stat_new_fmt,
                    ram_gain_formatted=ram_gain_fmt,
                    ram_new_formatted=ram_new_fmt,
                )
            else:
                if usd_val > 0 and rtm_val > 0:
                    success_key = 'g_buy_success'
                elif rtm_val > 0:
                    success_key = 'g_buy_success_rtm'
                else:
                    success_key = 'g_buy_success_usd'
                content = text.get(
                    ctx, success_key,
                    item=item, usd=usd, rtm=rtm,
                    stat_gain_formatted=stat_gain_fmt,
                    stat_current_formatted=stat_cur_fmt,
                    stat_new_formatted=stat_new_fmt,
                )
            kwargs = {'content': content, 'allowed_mentions': discord.AllowedMentions.none()}
            if getattr(ctx, 'interaction', None):
                await ctx.respond(**kwargs)
            else:
                await ctx.send(**kwargs)

            # Log blockchain lore-friendly pour l'achat de module d'attaque (RTM)
            if kind == 'attack' and rtm_val > 0:
                bot_logger = getattr(self.bot, 'discord_logger', None)
                if not bot_logger:
                    from utils.logger import Logger
                    bot_logger = Logger(self.bot)
                try:
                    await bot_logger.log_blockchain_transaction(
                        from_id=ctx.author.id,
                        to_address="0xROOT_BLACK_MARKET",
                        rtm_amount=rtm_val,
                    )
                except Exception:
                    pass


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Buy(bot))
