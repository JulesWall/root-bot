"""
Commande /hack et !hack — Cyberattaque PvP d'un réseau adverse via son identifiant secret.

Mécanique :
- Déclenchement : /hack <secret_id> <attack_points> <mining|attack> [confirm]
                  !hack <secret_id> <attack_points> <mining|attack> [confirm]
- Phase 1 : Devis estimatif récapitulant les points engagés, la zone ciblée et l'heure de résolution.
- Phase 2 : Prélèvement/réservation immédiat des points ATK et enregistrement dans `pvp_attacks`.
- Différé : 45 minutes avant résolution.
- Résolution atomique à échéance :
  - Défense adverse calculée à cet instant précis (Modules DEF + Pare-feu).
  - Destruction des modules de défense du tier le plus bas au plus haut sans dépasser le budget ATK.
  - Test d'intrusion : attack_points > total_defense (strict).
  - Si intrusion :
    - Target 'attack' : Destruction d'un module d'attaque adverse (tier le plus haut possédé).
    - Target 'mining' : Transfert de propriété d'un module de minage adverse (tier le plus haut possédé).
  - Pare-feu indestructible.
  - Enregistrement des droits de représailles (72h).
  - Notifications privées (DM) à l'attaquant et à la victime.
  - Log public affichant l'attaquant et la puissance ATK engagée.
"""

import asyncio
import logging
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
import time
from utils import text
from utils.check import Check
from utils.logger import Logger
from utils.root_embed import RootEmbed
from utils.root_theme import VisualState
from utils.time_format import format_duration, to_utc_timestamp


logger = logging.getLogger(__name__)


def _pvp_check_interval() -> int:
    """Intervalle de vérification des attaques PvP depuis math.json."""
    return int(MathConfig.load().get('pvp', {}).get('check_interval_seconds', 15))


def _is_confirm(val):
    """Vérifie si la valeur passée correspond à un accord explicite."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('confirm', 'true', 'yes', 'valider')
    return False


def _format_modules_summary(modules_dict: dict, single_fallback: int | None = None) -> str:
    """Formate proprement la liste des modules capturés ou détruits."""
    if not modules_dict:
        return str(single_fallback) if single_fallback is not None else ""
    if len(modules_dict) == 1:
        tier, count = next(iter(modules_dict.items()))
        return f"{tier}" if count == 1 else f"{tier} (×{count})"
    parts = []
    for tier, count in sorted(modules_dict.items(), key=lambda x: x[0], reverse=True):
        parts.append(f"{tier} (×{count})" if count > 1 else f"{tier}")
    return " + Tier ".join(parts)


class HackConfirmView(discord.ui.View):
    """Vue interactive avec bouton de confirmation pour lancer le /hack."""

    def __init__(self, send_fn, service, ctx, secret_id: str, attack_points: int, target_zone: str, target_id: int = 0):
        super().__init__(timeout=60)
        self.send_fn = send_fn
        self.service = service
        self.ctx = ctx
        self.secret_id = secret_id
        self.attack_points = attack_points
        self.target_zone = target_zone
        self.target_id = int(target_id or 0)
        self.lock = asyncio.Lock()
        self.done = False
        self.message = None

        launch_btn = discord.ui.Button(
            label=text.get(ctx, 'g_hack_btn_launch', attack_points=attack_points),
            style=discord.ButtonStyle.danger,
        )
        launch_btn.callback = self.confirm_callback
        self.add_item(launch_btn)

        cancel_btn = discord.ui.Button(
            label=text.get(ctx, 'g_hack_btn_cancel'),
            style=discord.ButtonStyle.secondary,
        )
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

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

    async def confirm_callback(self, interaction: discord.Interaction):
        async with self.lock:
            if self.done:
                await interaction.followup.send(text.get(self.ctx, 'g_already_handled'))
                return
            self.done = True
            try:
                result = await self.service.execute(
                    interaction.user.id,
                    self.ctx.guild.id if self.ctx.guild else None,
                    'hack',
                    secret_id=self.secret_id,
                    attack_points=self.attack_points,
                    zone=self.target_zone,
                    target_id=self.target_id,
                    confirm=True,
                )
                await self.send_fn(self.response_context(interaction), 'hack', result)
            except GameError as error:
                await interaction.followup.send(text.get(self.ctx, 'g_error_' + error.key, **error.values))
            except Exception:
                logger.exception("Erreur inattendue lors de la confirmation du hack")
                await interaction.followup.send(text.get(self.ctx, 'command_error'))
            finally:
                self.stop()
                self._clear_view()

    async def cancel_callback(self, interaction: discord.Interaction):
        async with self.lock:
            if self.done:
                await interaction.followup.send(text.get(self.ctx, 'g_already_handled'))
                return
            self.done = True
            self.stop()
            cancelled_text = text.get(self.ctx, 'g_cancelled')
            embed = RootEmbed(self.ctx, 'hack', cancelled_text, state=VisualState.CANCELLED)
            if getattr(self.ctx, 'interaction', None):
                try:
                    await self.ctx.interaction.edit_original_response(embed=embed, view=None)
                except Exception:
                    pass
            elif self.message:
                try:
                    await self.message.edit(embed=embed, view=None)
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


class Hack(BaseGameCog):
    """Cog orchestrant les cyberattaques PvP (/hack et !hack — alias !hk)."""

    def __init__(self, bot):
        self.bot = bot
        self.check_pvp_loop.change_interval(seconds=_pvp_check_interval())
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self.check_pvp_loop.start()

    def cog_unload(self):
        self.check_pvp_loop.cancel()

    @tasks.loop(seconds=_pvp_check_interval())
    async def check_pvp_loop(self):
        """Boucle d'évaluation et de résolution des attaques arrivées à échéance."""
        try:
            resolved = await self.service.deliver_expired_pvp_attacks()
            if resolved:
                logger.info("%d attaque(s) PvP résolue(s)", len(resolved))
                for item in resolved:
                    await self._notify_and_log_resolved(item)
        except Exception:
            logger.exception("Erreur lors de la résolution des attaques PvP expirées")

    @check_pvp_loop.before_loop
    async def before_check_pvp_loop(self):
        await self.bot.wait_until_ready()
        try:
            resolved = await self.service.deliver_expired_pvp_attacks()
            for item in resolved or []:
                await self._notify_and_log_resolved(item)
        except Exception:
            logger.exception("Erreur lors du rattrapage des attaques PvP")


    async def _notify_and_log_resolved(self, item: dict):
        """Notifie l'attaquant et la victime en DM lors de la résolution de l'attaque."""
        attacker_id = item['attacker_id']
        victim_id = item['victim_id']
        attacker_lang = item.get('attacker_lang') or 'fr'
        victim_lang = item.get('victim_lang') or 'fr'

        # 0. Cas où l'attaque en vol a été annulée car la cible est déjà sous verrouillage critique
        if item.get('aborted_victim_locked'):
            try:
                attacker_user = self.bot.get_user(attacker_id) or await self.bot.fetch_user(attacker_id)
                if attacker_user:
                    title = "Opération interrompue" if attacker_lang == 'fr' else "Operation Aborted"
                    msg = text.get_for_lang(attacker_lang, 'g_hack_attacker_aborted_target_locked', target_id=victim_id)
                    embed = RootEmbed.report(attacker_lang, title, msg, is_loss=False)
                    await embed.send_to(attacker_user)
            except Exception:
                logger.warning("Impossible d'envoyer l'alerte d'annulation à l'attaquant %s", attacker_id)
            return

        attack_points = item['attack_points']
        target_zone = item['target']
        intrusion_success = item['intrusion_success']
        total_defense = item['initial_total_defense']
        firewall_def = item['firewall_def_points']
        module_def = item['module_def_points']
        destroyed_defense = item['destroyed_defense_points']
        destroyed_atk_tier = item.get('destroyed_attack_tier')
        captured_mining_tier = item.get('captured_mining_tier')

        destroyed_atk_summary = _format_modules_summary(
            item.get('destroyed_attack_modules') or {},
            destroyed_atk_tier,
        )
        captured_mining_summary = _format_modules_summary(
            item.get('captured_mining_modules') or {},
            captured_mining_tier,
        )

        # Émission unique du log public en cas de procédure de sauvegarde déclenchée
        if item.get('critical_triggered'):
            try:
                bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)
                await bot_logger.log_pvp_critical_lock(
                    victim=victim_id,
                    duration_hours=item.get('critical_lock_duration_hours', 48),
                    lock_until=item.get('critical_lock_until'),
                )
            except Exception:
                logger.exception("Erreur lors de l'émission du log public de verrouillage critique")

        # 1. Notification DM à l'attaquant
        attacker_user = None
        try:
            attacker_user = self.bot.get_user(attacker_id) or await self.bot.fetch_user(attacker_id)
            if attacker_user:
                if not intrusion_success:
                    attacker_msg = text.get_for_lang(
                        attacker_lang, 'g_hack_attacker_no_intrusion',
                        target_id=victim_id,
                        attack_points=attack_points,
                        total_defense=total_defense,
                        firewall_def=firewall_def,
                        module_def=module_def,
                        destroyed_defense=destroyed_defense,
                    )
                else:
                    if target_zone == 'attack':
                        if destroyed_atk_summary:
                            attacker_msg = text.get_for_lang(
                                attacker_lang, 'g_hack_attacker_intrusion_attack',
                                target_id=victim_id,
                                attack_points=attack_points,
                                total_defense=total_defense,
                                destroyed_defense=destroyed_defense,
                                tier=destroyed_atk_summary,
                            )
                        else:
                            attacker_msg = text.get_for_lang(
                                attacker_lang, 'g_hack_attacker_intrusion_empty',
                                target_id=victim_id,
                                attack_points=attack_points,
                                total_defense=total_defense,
                                destroyed_defense=destroyed_defense,
                            )
                    else:  # mining
                        if captured_mining_summary:
                            attacker_msg = text.get_for_lang(
                                attacker_lang, 'g_hack_attacker_intrusion_mining',
                                target_id=victim_id,
                                attack_points=attack_points,
                                total_defense=total_defense,
                                destroyed_defense=destroyed_defense,
                                tier=captured_mining_summary,
                            )
                        else:
                            attacker_msg = text.get_for_lang(
                                attacker_lang, 'g_hack_attacker_intrusion_empty',
                                target_id=victim_id,
                                attack_points=attack_points,
                                total_defense=total_defense,
                                destroyed_defense=destroyed_defense,
                            )

                    if item.get('critical_triggered'):
                        attacker_msg += "\n\n" + text.get_for_lang(
                            attacker_lang, 'g_hack_attacker_critical_capped',
                            effective=item.get('effective_count_to_take', 0),
                        )

                if intrusion_success:
                    title_atk = "Rapport d'opération — Accès obtenu" if attacker_lang == 'fr' else "Operation Report — Access Granted"
                else:
                    title_atk = "Rapport d'opération — Accès refusé" if attacker_lang == 'fr' else "Operation Report — Access Denied"
                embed_atk = RootEmbed.report(attacker_lang, title_atk, attacker_msg, is_loss=False)
                await embed_atk.send_to(attacker_user)

                # ── Debug : détail du calcul overrun (visible uniquement par l'attaquant) ──
                try:
                    overrun_threshold = item.get('overrun_threshold', 'N/A')
                    target_count = item.get('target_count_to_take', 0)
                    delta = max(0, attack_points - total_defense)
                    extra = max(0, target_count - 1) if intrusion_success else 0
                    overrun_threshold_fmt = f"{float(overrun_threshold):.2f}" if overrun_threshold != 'N/A' else 'N/A'
                    fw_atk = item.get('attacker_fw', '?')
                    fw_vic = item.get('victim_fw', '?')
                    effective_count = item.get('effective_count_to_take', target_count)
                    lines_debug = [
                        "```",
                        "🔬 ROOT DEBUG — Calcul Overrun PvP",
                        "─" * 35,
                        f"⚔️  ATK engagés          : {attack_points}",
                        f"🛡️  DEF totale victime   : {total_defense}",
                        f"   ├─ Pare-feu          : {firewall_def} pts  (FW Lv.{fw_vic})",
                        f"   └─ Modules baie      : {module_def} pts",
                        f"📉  Modules DEF détruits : {destroyed_defense} pts",
                        "─" * 35,
                        f"✅  Intrusion           : {'OUI' if intrusion_success else 'NON'}",
                        f"🔢  delta (ATK - DEF)   : {delta}",
                        f"📐  Seuil Overrun V(T{fw_atk}): {overrun_threshold_fmt}",
                        f"   formule : V = (cost_mining_USD / (cost_atk_RTM * rtm_usd)) * mult * sqrt(bits*time)",
                        f"🎯  Modules pris (base) : 1" if intrusion_success else "🎯  Modules pris       : 0",
                        f"➕  Bonus overrun       : +{extra}  (delta // V = {delta} // {overrun_threshold_fmt})" if intrusion_success else "",
                    ]
                    if item.get('critical_triggered'):
                        lines_debug.append(f"🛡️  Plafond critique     : {effective_count} (procédure active)")
                        lines_debug.append(f"📦  Total modules pris  : {effective_count} (brut calculé : {target_count})")
                    else:
                        lines_debug.append(f"📦  Total modules pris  : {target_count}")
                    lines_debug.append("```")
                    debug_msg = "\n".join(l for l in lines_debug if l != "")
                    await attacker_user.send(debug_msg)
                except Exception as exc:
                    logger.debug("Envoi debug overrun échoué pour attaquant %s : %s", attacker_id, exc)

        except Exception:
            logger.warning("Impossible d'envoyer le compte-rendu PvP à l'attaquant %s", attacker_id)

        new_victim_secret = item.get('new_victim_secret') or ''

        # 2. Notification DM à la victime
        try:
            victim_user = self.bot.get_user(victim_id) or await self.bot.fetch_user(victim_id)
            if victim_user:
                if not intrusion_success:
                    victim_msg = text.get_for_lang(
                        victim_lang, 'g_hack_victim_no_intrusion',
                        attacker_id=attacker_id,
                        attack_points=attack_points,
                        total_defense=total_defense,
                        destroyed_defense=destroyed_defense,
                        new_secret_id=new_victim_secret,
                    )
                else:
                    if target_zone == 'attack':
                        if destroyed_atk_summary:
                            victim_msg = text.get_for_lang(
                                victim_lang, 'g_hack_victim_intrusion_attack',
                                attacker_id=attacker_id,
                                attack_points=attack_points,
                                total_defense=total_defense,
                                destroyed_defense=destroyed_defense,
                                tier=destroyed_atk_summary,
                                new_secret_id=new_victim_secret,
                            )
                        else:
                            victim_msg = text.get_for_lang(
                                victim_lang, 'g_hack_victim_intrusion_empty',
                                attacker_id=attacker_id,
                                attack_points=attack_points,
                                total_defense=total_defense,
                                destroyed_defense=destroyed_defense,
                                new_secret_id=new_victim_secret,
                            )
                    else:  # mining
                        if captured_mining_summary:
                            victim_msg = text.get_for_lang(
                                victim_lang, 'g_hack_victim_intrusion_mining',
                                attacker_id=attacker_id,
                                attack_points=attack_points,
                                total_defense=total_defense,
                                destroyed_defense=destroyed_defense,
                                tier=captured_mining_summary,
                                new_secret_id=new_victim_secret,
                            )
                        else:
                            victim_msg = text.get_for_lang(
                                victim_lang, 'g_hack_victim_intrusion_empty',
                                attacker_id=attacker_id,
                                attack_points=attack_points,
                                total_defense=total_defense,
                                destroyed_defense=destroyed_defense,
                                new_secret_id=new_victim_secret,
                            )

                    if item.get('critical_triggered'):
                        lock_until = item.get('critical_lock_until')
                        ts_lock = to_utc_timestamp(lock_until) if lock_until else 0
                        duration_hours = item.get('critical_lock_duration_hours', 48)
                        victim_msg += "\n\n" + text.get_for_lang(
                            victim_lang, 'g_hack_victim_critical_saved',
                            duration=duration_hours,
                            timestamp=ts_lock,
                        )

                if intrusion_success:
                    title_vic = "Alerte intrusion — Brèche confirmée" if victim_lang == 'fr' else "Intrusion Alert — Breach Confirmed"
                else:
                    title_vic = "Alerte réseau — Intrusion repoussée" if victim_lang == 'fr' else "Network Alert — Intrusion Repelled"
                embed_vic = RootEmbed.report(victim_lang, title_vic, victim_msg, is_loss=intrusion_success)
                await embed_vic.send_to(victim_user)
        except Exception:
            logger.warning("Impossible d'envoyer l'alerte PvP à la victime %s", victim_id)

    # ── Slash Command ─────────────────────────────────────────────────────────
    @discord.slash_command(
        name='hack',
        description=EN['hack'],
        description_localizations={"fr": FR['hack']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def hack(
        self,
        ctx,
        secret_id: discord.Option(
            str,
            description=desc['hack_secret_id'],
            description_localizations=desc_loc['hack_secret_id'],
        ),
        attack_points: discord.Option(
            int,
            description=desc['hack_attack_points'],
            description_localizations=desc_loc['hack_attack_points'],
            min_value=1,
        ),
        zone: discord.Option(
            str,
            choices=['mining', 'attack'],
            description=desc['hack_target'],
            description_localizations=desc_loc['hack_target'],
        ),
        confirm: discord.Option(
            str, choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False, default=None,
        ) = None,
    ):
        """Commande Slash /hack <secret_id> <attack_points> <mining|attack> [confirm]."""
        await self._invoke(
            ctx, 'hack',
            secret_id=secret_id,
            attack_points=attack_points,
            zone=zone,
            confirm=_is_confirm(confirm),
        )

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name='hack', aliases=['hk'], help=FR['hack'])
    async def prefix_hack(self, ctx, secret_id: str = None, attack_points: str = None, zone: str = None, *args):
        """Commande préfixe !hack <secret_id> <points_atk> <mining|attack> [confirm]."""
        if not secret_id or not attack_points or not zone:
            await self._prefetch_lang(ctx.author.id)
            prefix = getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')
            return await ctx.send(text.get(ctx, 'g_error_hack_usage', prefix=prefix))

        try:
            atk_val = int(attack_points.strip())
        except (ValueError, TypeError):
            await self._prefetch_lang(ctx.author.id)
            prefix = getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')
            return await ctx.send(text.get(ctx, 'g_error_hack_usage', prefix=prefix))

        confirm = any(_is_confirm(a) for a in args)
        await self._invoke(
            ctx, 'hack',
            secret_id=secret_id,
            attack_points=atk_val,
            zone=zone,
            confirm=confirm,
        )

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        if result.get('hack_quote'):
            target_zone = result.get('target_zone')
            zone_display = text.get(ctx, 'mining') if target_zone == 'mining' else text.get(ctx, 'attack')
            ts = result.get('timestamp') or 0
            dur = format_duration(max(0, ts - int(time.time()))) if ts else "45m"

            content = text.get(
                ctx, 'g_hack_quote',
                target_id=result.get('target_id'),
                secret_id=result.get('secret_id'),
                attack_points=result.get('attack_points'),
                zone_display=zone_display,
                timestamp=ts,
                ts=ts,
                duration=dur,
                remaining=dur,
                remaining_atk=result.get('remaining_atk'),
            )
            view = HackConfirmView(
                self._send,
                self.service,
                ctx,
                secret_id=result.get('secret_id'),
                attack_points=result.get('attack_points'),
                target_zone=target_zone,
                target_id=result.get('target_id', 0),
            )
            embed = RootEmbed(ctx, 'hack', content)
            await embed.send(ctx, view=view)

        elif result.get('hack_started'):
            target_zone = result.get('target_zone')
            zone_display = text.get(ctx, 'mining') if target_zone == 'mining' else text.get(ctx, 'attack')
            ts = result.get('timestamp') or 0
            dur = format_duration(max(0, ts - int(time.time()))) if ts else "45m"

            content = text.get(
                ctx, 'g_hack_started',
                target_id=result.get('target_id'),
                attack_points=result.get('attack_points'),
                zone_display=zone_display,
                timestamp=ts,
                ts=ts,
                duration=dur,
                remaining=dur,
            )
            embed = RootEmbed.action_launched(ctx, text.get(ctx, 'act_hack', fallback='Attaque'), content)
            await embed.send(ctx)

            # Log public (points ATK engagés et attaquant publiés immédiatement au lancement)
            bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)
            author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
            try:
                await bot_logger.log_pvp_attack(author or ctx.author.id, result.get('attack_points'))
            except Exception:
                logger.exception("Erreur lors de l'émission du log public PvP")


def setup(bot):
    """Point d'entrée standard de chargement du Cog Hack."""
    bot.add_cog(Hack(bot))

