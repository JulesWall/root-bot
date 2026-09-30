"""
Commande /scan et !scan — Analyse du réseau d'un joueur pour découvrir son secret_id.

Mécanique :
- Déclenchement : /scan <@cible> ou !scan <@cible>
- Phase 1 : Devis estimatif avec probabilités de base et options de boost (×1, ×2, ×5).
- Phase 2 : Validation avec prélèvement RTM, journalisation #blockchain et différé 90s.
- Livraison : Calcul du succès selon ratio ATK/DEF réels et tirage aléatoire.
  - Succès : Envoi en MP du secret_id + bouton pour exposer publiquement.
  - Échec : Envoi en MP d'un message d'échec.
  - Alerte cible : Si firewall >= 3 (anonyme), >= 4 (avec identité de l'attaquant).
  - Représailles : Insertion dans la table `consequence` (72h).
"""

import asyncio
import datetime
import logging
import secrets
from decimal import Decimal
from types import SimpleNamespace

import discord
from discord.ext import commands, tasks

import data
from commands.game.commandgame import BaseGameCog
from game.game_error import GameError
from game.math_config import MathConfig
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.check import Check
from utils.logger import Logger
from utils.root_embed import RootEmbed


logger = logging.getLogger(__name__)


def _scan_check_interval() -> int:
    """Intervalle de vérification de la livraison des scans depuis math.json."""
    return int(MathConfig.load().get('scan', {}).get('check_interval_seconds', 15))


class ConfirmExposeView(discord.ui.View):
    """Vue de confirmation pour l'exposition publique du Secret ID."""

    def __init__(self, bot, scanner_id: int, target_id: int, target_name: str, secret_id: str, lang: str, parent_view=None):
        super().__init__(timeout=120)
        self.bot = bot
        self.scanner_id = scanner_id
        self.target_id = target_id
        self.target_name = target_name
        self.secret_id = secret_id
        self.lang = lang
        self.parent_view = parent_view

        confirm_btn = discord.ui.Button(
            label=text.get_for_lang(lang, 'g_scan_expose_confirm_btn'),
            style=discord.ButtonStyle.danger,
        )
        confirm_btn.callback = self.confirm_callback
        self.add_item(confirm_btn)

        cancel_btn = discord.ui.Button(
            label=text.get_for_lang(lang, 'g_scan_expose_cancel_btn'),
            style=discord.ButtonStyle.secondary,
        )
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def confirm_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.scanner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        await interaction.response.defer()
        for child in self.children:
            child.disabled = True
        try:
            await interaction.edit_original_response(view=self)
        except Exception:
            pass

        if self.parent_view:
            for child in self.parent_view.children:
                child.disabled = True
            try:
                if hasattr(self.parent_view, 'message') and self.parent_view.message:
                    await self.parent_view.message.edit(view=self.parent_view)
            except Exception:
                pass

        bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)
        await bot_logger.log_scan_exposed(
            scanner_id=self.scanner_id,
            target_name=self.target_name,
            secret_id=self.secret_id,
        )

        exposed_msg = text.get_for_lang(
            self.lang, 'g_scan_exposed_public',
            scanner=self.scanner_id,
            target_name=self.target_name,
            secret_id=self.secret_id,
        )
        await interaction.followup.send(exposed_msg)
        self.stop()

    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.scanner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        await interaction.response.defer()
        for child in self.children:
            child.disabled = True
        try:
            await interaction.edit_original_response(content=text.get_for_lang(self.lang, 'g_cancelled'), view=self)
        except Exception:
            pass
        self.stop()


class ExposeView(discord.ui.View):
    """Vue affichée en MP au scanner avec boutons Exposer / Garder secret."""

    def __init__(self, bot, scanner_id: int, target_id: int, target_name: str, secret_id: str, lang: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.scanner_id = scanner_id
        self.target_id = target_id
        self.target_name = target_name
        self.secret_id = secret_id
        self.lang = lang
        self.message = None

        btn_expose = discord.ui.Button(
            label=text.get_for_lang(lang, 'g_scan_expose_btn'),
            style=discord.ButtonStyle.danger,
        )
        btn_expose.callback = self.expose_callback
        self.add_item(btn_expose)

        btn_keep = discord.ui.Button(
            label=text.get_for_lang(lang, 'g_scan_keep_secret_btn'),
            style=discord.ButtonStyle.secondary,
        )
        btn_keep.callback = self.keep_callback
        self.add_item(btn_keep)

    async def expose_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.scanner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        confirm_text = text.get_for_lang(
            self.lang, 'g_scan_expose_confirm',
            secret_id=self.secret_id,
            target=self.target_id,
        )
        view = ConfirmExposeView(
            bot=self.bot,
            scanner_id=self.scanner_id,
            target_id=self.target_id,
            target_name=self.target_name,
            secret_id=self.secret_id,
            lang=self.lang,
            parent_view=self,
        )
        await interaction.response.send_message(confirm_text, view=view, ephemeral=True)

    async def keep_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.scanner_id:
            await interaction.response.send_message("Action non autorisée.", ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class ScanBoostView(discord.ui.View):
    """Vue interactive avec options de boost pour confirmer le scan."""

    def __init__(self, send_fn, service, ctx, target_id: int, boost_options: list[dict]):
        super().__init__(timeout=60)
        self.send_fn = send_fn
        self.service = service
        self.ctx = ctx
        self.target_id = target_id
        self.boost_options = boost_options
        self.lock = asyncio.Lock()
        self.done = False
        self.message = None

        for opt in boost_options:
            mult = opt['multiplier']
            prob = opt['prob_pct']
            cost = text.format_rtm(opt['rtm_cost'])
            if mult == 1:
                label = text.get(ctx, 'g_scan_btn_launch', prob=prob, rtm=cost)
                style = discord.ButtonStyle.primary
            elif mult == 2:
                label = text.get(ctx, 'g_scan_btn_boost2', prob=prob, rtm=cost)
                style = discord.ButtonStyle.success
            elif mult == 5:
                label = text.get(ctx, 'g_scan_btn_boost5', prob=prob, rtm=cost)
                style = discord.ButtonStyle.danger
            else:
                label = f"Boost ×{mult} ({prob}%) — {cost} RTM"
                style = discord.ButtonStyle.secondary

            btn = discord.ui.Button(label=label, style=style)
            btn.callback = self._make_callback(mult)
            self.add_item(btn)

        cancel_btn = discord.ui.Button(label=text.get(ctx, 'g_cancel'), style=discord.ButtonStyle.secondary)
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)

    def _make_callback(self, multiplier: int):
        async def callback(interaction: discord.Interaction):
            await self._handle_click(interaction, multiplier)
        return callback

    def response_context(self, interaction: discord.Interaction):
        return SimpleNamespace(
            interaction=interaction,
            author=interaction.user,
            guild=self.ctx.guild,
            bot=self.ctx.bot,
            command=self.ctx.command,
            respond=interaction.followup.send,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return False
        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.ctx.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(text.get(self.ctx, err_key), ephemeral=True)
            return False
        if not interaction.response.is_done():
            await interaction.response.defer()
        return True

    async def _handle_click(self, interaction: discord.Interaction, multiplier: int):
        async with self.lock:
            if self.done:
                await interaction.followup.send(text.get(self.ctx, 'g_already_handled'))
                return
            self.done = True
            try:
                result = await self.service.execute(
                    interaction.user.id,
                    self.ctx.guild.id if self.ctx.guild else None,
                    'scan',
                    target=self.target_id,
                    boost_multiplier=multiplier,
                    confirm=True,
                )
                await self.send_fn(self.response_context(interaction), 'scan', result)
            except GameError as error:
                await interaction.followup.send(text.get(self.ctx, 'g_error_' + error.key, **error.values))
            except Exception:
                logger.exception("Erreur inattendue lors de la confirmation du scan")
                await interaction.followup.send(text.get(self.ctx, 'command_error'))
            finally:
                self.stop()
                self._clear_view()

    async def cancel(self, interaction: discord.Interaction):
        async with self.lock:
            if self.done:
                await interaction.followup.send(text.get(self.ctx, 'g_already_handled'))
                return
            self.done = True
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

    def _clear_view(self):
        try:
            if getattr(self.ctx, 'interaction', None):
                asyncio.ensure_future(self.ctx.interaction.edit_original_response(view=None))
            elif self.message:
                asyncio.ensure_future(self.message.edit(view=None))
        except Exception:
            pass

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if getattr(self.ctx, 'interaction', None):
                await self.ctx.interaction.edit_original_response(view=self)
            elif self.message:
                await self.message.edit(view=self)
        except discord.HTTPException:
            pass


class Scan(BaseGameCog):
    """Cog gérant le scan de réseau adverse (/scan et !scan)."""

    def __init__(self, bot):
        self.bot = bot
        self.check_scans_loop.change_interval(seconds=_scan_check_interval())
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self.check_scans_loop.start()

    def cog_unload(self):
        self.check_scans_loop.cancel()

    @tasks.loop(seconds=_scan_check_interval())
    async def check_scans_loop(self):
        """Boucle de livraison des scans arrivés à échéance et purge des conséquences."""
        try:
            delivered = await self.service.deliver_expired_scans()
            if delivered:
                logger.info("%d scan(s) à livrer", len(delivered))
                for item in delivered:
                    await self._notify_delivered(item)
            await self.service.purge_expired_consequences()
        except Exception:
            logger.exception("Erreur lors de la livraison des scans expirés")

    @check_scans_loop.before_loop
    async def before_check_scans_loop(self):
        await self.bot.wait_until_ready()
        try:
            delivered = await self.service.deliver_expired_scans()
            for item in delivered or []:
                await self._notify_delivered(item)
            await self.service.purge_expired_consequences()
        except Exception:
            logger.exception("Erreur lors du rattrapage des scans")

    async def _notify_delivered(self, item: dict):
        """Calcule le résultat du scan et notifie scanner et cible."""
        scanner_id = item['scanner_id']
        target_id = item['target_id']
        boost_rtm = item.get('boost_rtm') or Decimal('0')

        scanner = await self.service.database.run(
            lambda tx: tx.one('SELECT * FROM players WHERE discord_id = %s', (scanner_id,)),
            readonly=True,
        )
        target = await self.service.database.run(
            lambda tx: tx.one('SELECT * FROM players WHERE discord_id = %s', (target_id,)),
            readonly=True,
        )
        if not scanner or not target:
            return

        cfg = MathConfig.load().get('scan', {})
        min_prob = float(cfg.get('min_success_prob', 0.05))
        boost_per_point = Decimal(str(cfg.get('boost_rtm_per_point', '0.001')))
        window_hours = int(cfg.get('retaliation_window_hours', 72))

        atk = int(scanner.get('attack_points') or 0)
        target_stats = MathConfig.calculate_player_stats(target)
        total_defense = max(1, target_stats['total_defense'])

        base_prob = min(1.0, max(min_prob, atk / total_defense))
        if boost_per_point > 0 and boost_rtm > 0:
            bonus = float(boost_rtm / boost_per_point) * 0.01 * (1.0 - base_prob)
            final_prob = min(1.0, base_prob + bonus)
        else:
            final_prob = base_prob

        roll = secrets.randbelow(10000)
        success = roll < int(final_prob * 10000)

        # Enregistrement du droit de représailles (consequence)
        from game.db.consequence import ConsequenceDB
        await self.service.database.run(
            lambda tx: ConsequenceDB.insert(tx, victim_id=target_id, attacker_id=scanner_id, window_hours=window_hours)
        )

        # Alerte à la cible selon son niveau de firewall
        target_fw = int(target.get('firewall_level') or 0)
        alert_threshold = int(cfg.get('alert_firewall_threshold', 3))
        identity_threshold = int(cfg.get('alert_identity_threshold', 4))

        target_user = None
        try:
            target_user = self.bot.get_user(target_id) or await self.bot.fetch_user(target_id)
        except Exception:
            pass

        if target_fw >= alert_threshold and target_user:
            try:
                target_lang = target.get('lang') or 'fr'
                if target_fw >= identity_threshold:
                    alert_msg = text.get_for_lang(target_lang, 'g_scan_alert_identified', scanner=scanner_id)
                else:
                    alert_msg = text.get_for_lang(target_lang, 'g_scan_alert_anon', level=target_fw)
                await target_user.send(alert_msg)
            except Exception:
                logger.warning("Impossible d'envoyer l'alerte de scan à la cible %s", target_id)

        # Notification au scanner
        try:
            scanner_user = self.bot.get_user(scanner_id) or await self.bot.fetch_user(scanner_id)
            if scanner_user:
                scanner_lang = scanner.get('lang') or 'fr'
                if success:
                    target_secret = target.get('secret_id')
                    if not target_secret:
                        from game.db.secret_ids import ensure_player_secret
                        updated_target = await self.service.database.run(
                            lambda tx: ensure_player_secret(tx, target)
                        )
                        target_secret = updated_target.get('secret_id')

                    from game.db.secret_ids import next_rotation_at, unix_ts
                    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                    rot_ts = unix_ts(next_rotation_at(now_utc))

                    msg = text.get_for_lang(
                        scanner_lang, 'g_scan_success_dm',
                        target=target_id,
                        secret_id=target_secret,
                        rotation_ts=rot_ts,
                    )
                    target_name = getattr(target_user, 'name', str(target_id)) if target_user else str(target_id)

                    view = ExposeView(
                        bot=self.bot,
                        scanner_id=scanner_id,
                        target_id=target_id,
                        target_name=target_name,
                        secret_id=target_secret,
                        lang=scanner_lang,
                    )
                    dm_msg = await scanner_user.send(msg, view=view)
                    view.message = dm_msg
                else:
                    msg = text.get_for_lang(scanner_lang, 'g_scan_failure_dm', target=target_id)
                    await scanner_user.send(msg)
        except Exception:
            logger.exception("Erreur lors de la notification DM au scanner %s", scanner_id)

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='scan',
        description=EN['scan'],
        description_localizations={"fr": FR['scan']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def scan(
        self,
        ctx,
        target: discord.Option(
            discord.Member,
            description=desc['scan_target'],
            description_localizations=desc_loc['scan_target'],
        ),
    ):
        """Commande Slash /scan pour lancer un scan de réseau adverse."""
        await self._prefetch_lang(ctx.author.id)
        msg = text.get(ctx, 'g_pvp_v2_maintenance')
        kwargs = {'content': msg, 'allowed_mentions': discord.AllowedMentions.none()}
        if getattr(ctx, 'interaction', None):
            await ctx.respond(**kwargs)
        else:
            await ctx.send(**kwargs)

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='scan', help=FR['scan'])
    async def prefix_scan(self, ctx, target: str = None):
        """Commande préfixe !scan <@cible>."""
        await self._prefetch_lang(ctx.author.id)
        msg = text.get(ctx, 'g_pvp_v2_maintenance')
        await ctx.send(msg)

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        if result.get('scan_quote'):
            content = text.get(
                ctx, 'g_scan_quote',
                target=result.get('target_id'),
                prob_base=result.get('prob_base_pct'),
                rtm=text.format_rtm(result.get('rtm_base')),
                cur_rtm=text.format_rtm(result.get('current_rtm', 0)),
                rem_rtm=text.format_rtm(result.get('remaining_rtm', 0)),
            )
            view = ScanBoostView(
                self._send,
                self.service,
                ctx,
                target_id=result.get('target_id'),
                boost_options=result.get('boost_options', []),
            )
            embed = RootEmbed(ctx, 'scan', content)
            await embed.send(ctx, view=view)
        elif result.get('scan_started'):
            content = text.get(
                ctx, 'g_scan_started',
                target=result.get('target_id'),
                rtm=text.format_rtm(result.get('rtm_total')),
                timestamp=result.get('timestamp', 0),
            )
            kwargs = {'content': content, 'allowed_mentions': discord.AllowedMentions.none()}
            if getattr(ctx, 'interaction', None):
                await ctx.respond(**kwargs)
            else:
                await ctx.send(**kwargs)

            # Log blockchain
            bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)
            try:
                await bot_logger.log_blockchain_transaction(
                    from_id=ctx.author.id,
                    to_address="0xROOT_SCAN_NODE",
                    rtm_amount=result.get('rtm_total'),
                    tx_type="SCAN",
                )
            except Exception:
                logger.exception("Erreur lors de la journalisation blockchain pour le scan")


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Scan(bot))

