"""Commande /market et !market — Consultation du cours dynamique et graphiques.

Fournit :
1. Vue par défaut (Niveau 1) : Embed sobre Root OS, cours, sparkline Unicode, variation,
   contributions BTC/ETH/SOL et boutons d'interaction. Aucun fichier image n'est transféré par défaut.
2. Vue graphique (Niveau 2) : Sur demande explicite, rendu haute résolution aux couleurs Root OS
   généré hors event-loop, mis en cache sur disque et envoyé de façon éphémère.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
from typing import Optional

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from game.game_error import GameError
from game.market_charts import (
    PERIODS,
    get_or_render_chart,
    period_change_pct,
    sparkline,
)
from game.math_config import MathConfig
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.check import Check
from utils.root_embed import RootEmbed
from utils.root_emojis import get_button_emoji, get_emoji
from utils.root_theme import VisualState

logger = logging.getLogger(__name__)


class MarketView(discord.ui.View):
    """Vue interactive pour basculer de période ou afficher le graphique détaillé."""

    def __init__(self, cog: "Market", ctx, current_period: str = "24h"):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.current_period = current_period
        self.message = None

        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        for p in ('24h', '7d', '30d'):
            is_active = (p == self.current_period)
            btn = discord.ui.Button(
                label=text.get(self.ctx, f'g_market_btn_{p}'),
                style=discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary,
                custom_id=f"market_p_{p}",
                disabled=is_active,
            )
            btn.callback = self._make_period_callback(p)
            self.add_item(btn)

        # Bouton Graphique
        btn_chart = discord.ui.Button(
            label=text.get(self.ctx, 'g_market_btn_chart'),
            emoji=get_button_emoji('root_production') or '📊',
            style=discord.ButtonStyle.secondary,
            custom_id="market_btn_chart",
        )
        btn_chart.callback = self._on_chart_click
        self.add_item(btn_chart)

        # Bouton Alertes
        btn_alerts = discord.ui.Button(
            label=text.get(self.ctx, 'g_market_btn_alerts'),
            emoji=get_button_emoji('root_alerte') or '🔔',
            style=discord.ButtonStyle.secondary,
            custom_id="market_btn_alerts",
        )
        btn_alerts.callback = self._on_alerts_click
        self.add_item(btn_alerts)

    def _make_period_callback(self, period: str):
        async def callback(interaction: discord.Interaction):
            # Les modifications de période dans un message public sont éphémères pour les non-auteurs
            if interaction.user.id != self.ctx.author.id:
                await interaction.response.defer(ephemeral=True)
                embed, view = await self.cog._build_market_display(self.ctx, period)
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                return

            await interaction.response.defer()
            self.current_period = period
            self._build_buttons()
            embed, _ = await self.cog._build_market_display(self.ctx, period)
            await interaction.message.edit(embed=embed, view=self)

        return callback

    async def _on_chart_click(self, interaction: discord.Interaction):
        """Génère (ou récupère en cache) l'image PNG et l'envoie en réponse éphémère."""
        await interaction.response.defer(ephemeral=True)
        try:
            file, embed = await self.cog._generate_chart_file(self.ctx, self.current_period)
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        except Exception:
            logger.exception("[Market] Erreur lors de l'envoi du graphique")
            err_msg = text.get(self.ctx, 'g_error_busy')
            await interaction.followup.send(err_msg, ephemeral=True)

    async def _on_alerts_click(self, interaction: discord.Interaction):
        """Affiche l'interface de gestion des alertes personnelles."""
        await interaction.response.defer(ephemeral=True)
        try:
            embed, view = await self.cog._build_alerts_display(self.ctx, interaction.user.id)
            resp = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            if hasattr(resp, 'message') and resp.message:
                view.message = resp.message
            elif isinstance(resp, discord.Message):
                view.message = resp
        except Exception:
            logger.exception("[Market] Erreur ouverture vue alertes")
            await interaction.followup.send(text.get(self.ctx, 'g_error_busy'), ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.ctx.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(text.get(self.ctx, err_key), ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


class MarketAlertAddModal(discord.ui.Modal):
    """Modal de configuration d'une alerte de cours."""

    def __init__(self, cog: "Market", ctx, user_id: int, on_complete):
        super().__init__(title=text.get(ctx, 'g_market_modal_add_title')[:45])
        self.cog = cog
        self.ctx = ctx
        self.user_id = user_id
        self.on_complete = on_complete

        self.threshold_input = discord.ui.InputText(
            label=text.get(ctx, 'g_market_modal_threshold_label')[:45],
            placeholder=text.get(ctx, 'g_market_modal_threshold_hint')[:100],
            required=True,
        )
        self.add_item(self.threshold_input)

        self.dir_input = discord.ui.InputText(
            label=text.get(ctx, 'g_market_modal_dir_label')[:45],
            placeholder=text.get(ctx, 'g_market_modal_dir_hint')[:100],
            value="above",
            required=True,
        )
        self.add_item(self.dir_input)

        self.cooldown_input = discord.ui.InputText(
            label=text.get(ctx, 'g_market_modal_cooldown_label')[:45],
            placeholder=text.get(ctx, 'g_market_modal_cooldown_hint')[:100],
            value="60",
            required=False,
        )
        self.add_item(self.cooldown_input)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        raw_dir = self.dir_input.value.strip().lower()
        if raw_dir in ('above', 'up', 'hausse', '>=', '>', '+'):
            direction = 'above'
        elif raw_dir in ('below', 'down', 'baisse', '<=', '<', '-'):
            direction = 'below'
        else:
            return await interaction.followup.send(
                text.get(self.ctx, 'g_error_market_alert_invalid_direction'),
                ephemeral=True,
            )

        raw_thresh = self.threshold_input.value.strip().replace(' ', '').replace(',', '.')
        try:
            threshold = Decimal(raw_thresh)
            if threshold <= 0:
                raise ValueError()
        except Exception:
            return await interaction.followup.send(
                text.get(self.ctx, 'g_error_market_alert_invalid_threshold'),
                ephemeral=True,
            )

        raw_cd = self.cooldown_input.value.strip() if self.cooldown_input.value else "60"
        try:
            cooldown = max(15, int(raw_cd))
        except Exception:
            cooldown = 60

        try:
            state = await self.cog.service.get_market_state() or {}
            cur_price = Decimal(str(state.get('price_usd') or MathConfig.rtm_to_usd_rate()))
            await self.cog.service.create_market_alert(
                self.user_id,
                direction=direction,
                threshold_usd=threshold,
                cooldown_minutes=cooldown,
                current_price=cur_price,
            )
            dir_label = (
                text.get(self.ctx, 'g_market_alerts_dir_above')
                if direction == 'above'
                else text.get(self.ctx, 'g_market_alerts_dir_below')
            )
            success_msg = text.get(
                self.ctx,
                'g_market_alert_created',
                dir_label=dir_label,
                threshold=text.format_usd(threshold),
                cooldown=cooldown,
            )
            await interaction.followup.send(success_msg, ephemeral=True)
            await self.on_complete()
        except GameError as err:
            err_map = {
                'market_alert_limit_reached': 'g_error_market_alert_limit',
                'market_alert_duplicate': 'g_error_market_alert_duplicate',
                'market_alert_threshold_too_high': 'g_error_market_alert_invalid_threshold',
            }
            err_key = err_map.get(str(err), 'g_error_busy')
            max_alerts = MathConfig.market_settings().get('alerts_max_per_player', 5)
            await interaction.followup.send(
                text.get(self.ctx, err_key, max=max_alerts),
                ephemeral=True,
            )
        except Exception:
            logger.exception("[Market] Erreur création alerte")
            await interaction.followup.send(text.get(self.ctx, 'g_error_busy'), ephemeral=True)


class MarketAlertsView(discord.ui.View):
    """Vue interactive pour la gestion des alertes personnelles."""

    def __init__(self, cog: "Market", ctx, user_id: int, alerts: list[dict]):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.user_id = user_id
        self.alerts = alerts
        self.message = None

        self._build_interface()

    def _build_interface(self):
        self.clear_items()

        # Bouton Ajouter
        btn_add = discord.ui.Button(
            label=text.get(self.ctx, 'g_market_btn_add_alert'),
            emoji=get_button_emoji('root_materiel') or '➕',
            style=discord.ButtonStyle.primary,
            custom_id="market_alert_add",
        )
        btn_add.callback = self._on_add_click
        self.add_item(btn_add)

        # Select menu de suppression si alertes présentes
        if self.alerts:
            opts_del = []
            for a in self.alerts[:25]:
                direction_txt = "≥" if a['direction'] == 'above' else "≤"
                thresh_txt = text.format_usd(a['threshold_usd'])
                label = f"#{a['id']} · {direction_txt} {thresh_txt} USD"
                opts_del.append(discord.SelectOption(
                    label=label[:100],
                    value=str(a['id']),
                    description=f"Rappel : {a.get('cooldown_minutes', 60)} min",
                ))

            select_del = discord.ui.Select(
                placeholder=text.get(self.ctx, 'g_market_btn_del_alert'),
                options=opts_del,
                custom_id="market_alert_del_select",
            )
            select_del.callback = self._on_del_select
            self.add_item(select_del)

            # Select menu d'activation / désactivation
            opts_toggle = []
            for a in self.alerts[:25]:
                direction_txt = "≥" if a['direction'] == 'above' else "≤"
                thresh_txt = text.format_usd(a['threshold_usd'])
                state_txt = "Désactiver" if a.get('enabled') else "Activer"
                label = f"{state_txt} #{a['id']} ({direction_txt} {thresh_txt})"
                opts_toggle.append(discord.SelectOption(
                    label=label[:100],
                    value=str(a['id']),
                ))

            select_toggle = discord.ui.Select(
                placeholder=text.get(self.ctx, 'g_market_btn_toggle_alert'),
                options=opts_toggle,
                custom_id="market_alert_toggle_select",
            )
            select_toggle.callback = self._on_toggle_select
            self.add_item(select_toggle)

        # Bouton Retour au Marché
        btn_back = discord.ui.Button(
            label=text.get(self.ctx, 'g_market_btn_back'),
            emoji=get_button_emoji('root_retour') or '🔙',
            style=discord.ButtonStyle.secondary,
            custom_id="market_alert_back",
        )
        btn_back.callback = self._on_back_click
        self.add_item(btn_back)

    async def _on_add_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(text.get(self.ctx, 'g_error_access_denied'), ephemeral=True)

        async def on_complete():
            embed, view = await self.cog._build_alerts_display(self.ctx, self.user_id)
            if self.message:
                await self.message.edit(embed=embed, view=view)

        modal = MarketAlertAddModal(self.cog, self.ctx, self.user_id, on_complete)
        await interaction.response.send_modal(modal)

    async def _on_del_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(text.get(self.ctx, 'g_error_access_denied'), ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        alert_id = int(interaction.data['values'][0])
        await self.cog.service.delete_market_alert(self.user_id, alert_id)
        del_msg = text.get(self.ctx, 'g_market_alert_deleted', id=alert_id)
        await interaction.followup.send(del_msg, ephemeral=True)

        embed, view = await self.cog._build_alerts_display(self.ctx, self.user_id)
        if self.message:
            await self.message.edit(embed=embed, view=view)

    async def _on_toggle_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(text.get(self.ctx, 'g_error_access_denied'), ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        alert_id = int(interaction.data['values'][0])
        updated = await self.cog.service.toggle_market_alert(self.user_id, alert_id)
        st = text.get(self.ctx, 'g_market_alerts_status_armed' if updated.get('enabled') else 'g_market_alerts_status_disabled')
        upd_msg = text.get(self.ctx, 'g_market_alert_toggled', id=alert_id, status=st)
        await interaction.followup.send(upd_msg, ephemeral=True)

        embed, view = await self.cog._build_alerts_display(self.ctx, self.user_id)
        if self.message:
            await self.message.edit(embed=embed, view=view)

    async def _on_back_click(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed, view = await self.cog._build_market_display(self.ctx, '24h')
        if self.message:
            await self.message.edit(embed=embed, view=view)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.ctx.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(text.get(self.ctx, err_key), ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass



class Market(BaseGameCog):
    """Cog gérant la consultation du marché RTM et l'affichage des cours."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='market',
        description=EN['market'],
        description_localizations={"fr": FR['market']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def market(
        self,
        ctx,
        period: discord.Option(
            str,
            choices=['24h', '7d', '30d'],
            description=desc['market_period'],
            description_localizations=desc_loc['market_period'],
            required=False,
            default='24h',
        ) = '24h',
    ):
        """Affiche le terminal de marché RTM avec la période sélectionnée."""
        await self._prefetch_lang(ctx.author.id)
        embed, view = await self._build_market_display(ctx, period)
        msg = await ctx.respond(embed=embed, view=view)
        if hasattr(msg, 'message') and msg.message:
            view.message = msg.message
        elif isinstance(msg, discord.Message):
            view.message = msg

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='market', aliases=['mk'], help=FR['market'])
    async def prefix_market(self, ctx, period: str = '24h', *args):
        """Commande préfixe !market [24h|7d|30d|chart]."""
        await self._prefetch_lang(ctx.author.id)
        period_clean = period.lower().strip()
        if period_clean in ('alert', 'alerts', 'alerte', 'alertes'):
            embed, view = await self._build_alerts_display(ctx, ctx.author.id)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
            return

        if period_clean in ('chart', 'c', 'graph', 'graphique'):
            target_period = args[0].lower().strip() if args else '24h'
            if target_period not in PERIODS:
                target_period = '24h'
            try:
                file, embed = await self._generate_chart_file(ctx, target_period)
                return await ctx.send(embed=embed, file=file)
            except Exception:
                logger.exception("[Market] Erreur commande préfixe graphique")
                return await ctx.send(text.get(ctx, 'g_error_busy'))

        if period_clean not in PERIODS:
            period_clean = '24h'

        embed, view = await self._build_market_display(ctx, period_clean)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    async def _build_alerts_display(self, ctx, user_id: int):
        """Construit l'embed et la vue de gestion des alertes personnelles."""
        alerts = await self.service.list_market_alerts(user_id)
        max_alerts = MathConfig.market_settings().get('alerts_max_per_player', 5)

        lines = []
        if not alerts:
            lines.append(text.get(ctx, 'g_market_alerts_empty'))
        else:
            lines.append(text.get(ctx, 'g_market_alerts_header', count=len(alerts), max=max_alerts))
            for a in alerts:
                direction = a['direction']
                dir_label = (
                    text.get(ctx, 'g_market_alerts_dir_above')
                    if direction == 'above'
                    else text.get(ctx, 'g_market_alerts_dir_below')
                )
                if not a.get('enabled'):
                    st = text.get(ctx, 'g_market_alerts_status_disabled')
                elif a.get('armed'):
                    st = text.get(ctx, 'g_market_alerts_status_armed')
                else:
                    st = text.get(ctx, 'g_market_alerts_status_waiting')

                lines.append(text.get(
                    ctx,
                    'g_market_alerts_item',
                    id=a['id'],
                    dir_label=dir_label,
                    threshold=text.format_usd(a['threshold_usd']),
                    status=st,
                    cooldown=a.get('cooldown_minutes', 60),
                ))

        embed = RootEmbed(
            ctx=ctx,
            action='market',
            title=text.get(ctx, 'g_market_alerts_title'),
            content="\n".join(lines),
            state=VisualState.CONSULTATION,
            footer="ROOT OS · Marché",
        )
        view = MarketAlertsView(self, ctx, user_id, alerts)
        return embed, view

    # ── Rendu et Données ─────────────────────────────────────────────────────
    async def _build_market_display(self, ctx, period: str):
        """Construit l'embed de niveau 1 (sans image PNG) et la vue."""
        state = await self.service.get_market_state() or {}
        price = Decimal(str(state.get('price_usd') or MathConfig.rtm_to_usd_rate()))
        status = state.get('status', 'live')
        source = state.get('source', 'seed')
        market_ts = state.get('market_ts')

        # Calcul de la fenêtre temporelle
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        seconds_back = PERIODS.get(period, 24 * 3600)
        since = now_utc - timedelta(seconds=seconds_back)

        series = await self.service.get_market_series(since)
        prices = [p['price_after'] for p in series] if series else [price]

        # Calcul des variations
        first_price = prices[0]
        last_price = prices[-1] if len(prices) > 1 else price
        pct = period_change_pct(first_price, last_price)
        sign = "+" if pct >= 0 else ""
        change_str = f"{sign}{pct}%"
        direction = "↗ Hausse" if pct > 0 else ("↘ Baisse" if pct < 0 else "→ Stable")
        spark = sparkline(prices, width=28)

        # Dernières contributions crypto (issues du dernier point d'historique)
        if series:
            last_entry = series[-1]
            btc = f"{Decimal(str(last_entry.get('btc_pct', 0))):+.2f}%"
            eth = f"{Decimal(str(last_entry.get('eth_pct', 0))):+.2f}%"
            sol = f"{Decimal(str(last_entry.get('sol_pct', 0))):+.2f}%"
        else:
            btc = eth = sol = "+0.00%"

        # Horodatage Discord
        ts_val = int(state.get('observed_at').replace(tzinfo=timezone.utc).timestamp()) if state.get('observed_at') else int(datetime.now(timezone.utc).timestamp())

        # Assemblage des lignes de l'embed
        status_line = text.get(ctx, 'g_market_status_delayed') if status == 'delayed' else text.get(ctx, 'g_market_status_live')

        lines = [
            text.get(ctx, 'g_market_rate', rate=text.format_usd(price)),
            text.get(ctx, 'g_market_change', period=period.upper(), change_str=change_str),
            text.get(ctx, 'g_market_sparkline', sparkline=spark, direction=direction),
            text.get(ctx, 'g_market_contributions', btc=btc, eth=eth, sol=sol),
            f"> 📶 **Statut** : {status_line}",
            text.get(ctx, 'g_market_meta', ts=ts_val, source=source),
        ]

        embed_state = VisualState.ATTENTION if status == 'delayed' else VisualState.CONSULTATION
        embed = RootEmbed(
            ctx=ctx,
            action='market',
            title=text.get(ctx, 'g_market_title'),
            content="\n".join(lines),
            state=embed_state,
            footer=f"ROOT OS · Marché",
        )

        view = MarketView(self, ctx, current_period=period)
        return embed, view

    async def _generate_chart_file(self, ctx, period: str):
        """Génère l'objet discord.File avec l'image PNG et un embed résumé."""
        state = await self.service.get_market_state() or {}
        price = Decimal(str(state.get('price_usd') or MathConfig.rtm_to_usd_rate()))
        source = state.get('source', 'seed')

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        seconds_back = PERIODS.get(period, 24 * 3600)
        since = now_utc - timedelta(seconds=seconds_back)

        series = await self.service.get_market_series(since)
        if not series:
            series = [{'market_ts': now_utc, 'price_after': price}]

        chart_path = await get_or_render_chart(series, period, source)
        file = discord.File(chart_path, filename=f"rtm_chart_{period}.png")

        p_start = series[0]['price_after']
        p_end = series[-1]['price_after']
        pct = period_change_pct(p_start, p_end)
        sign = "+" if pct >= 0 else ""
        change_str = f"{sign}{pct}%"

        desc_content = text.get(
            ctx,
            'g_market_chart_desc',
            start_price=text.format_usd(p_start),
            end_price=text.format_usd(p_end),
            change_str=change_str,
            count=len(series),
        )

        embed = RootEmbed(
            ctx=ctx,
            action='market',
            title=text.get(ctx, 'g_market_chart_title', period=period.upper()),
            content=desc_content,
            footer="ROOT OS · Marché",
        )
        embed.set_image(url=f"attachment://rtm_chart_{period}.png")
        return file, embed


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Market(bot))
