"""Commande /hack et !hack — Déploiement offensif, diagnostic, analyse de trace et rançons (PvP V2).

Mécanique conforme à design/PVP_V2_DECISIONS.md (Décisions 6, 7, 8, 9, 10, 12, 13, 14, 15) :
- Déploiement offensif multi-familles (Hostile Miner, Ransomware, Vol de devises, Saturation, Espionnage, Vol de logiciel).
- Ralentissement défensif passif : durée_effective = durée_base × (1 + défense / 500) plafonnée à ×10.
- Diagnostic réseau (/hack diag ou /diag) : analyse de trafic révélant famille et empreinte pour permettre le patch.
- Analyse de trace réseau (/hack trace ou /trace) : identification de l'attaquant si non protégé par un patch, ouverture du droit de représailles 72h.
- Paiement de rançon (/hack pay ou /pay) : déblocage des commandes économiques d'une victime sous Ransomware.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

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
from utils.confirmation import Confirmation
from utils.emojis import get_root_emojis
from utils.root_embed import RootEmbed


logger = logging.getLogger(__name__)


def _op_check_interval() -> int:
    """Intervalle de vérification des opérations offensives depuis math.json."""
    try:
        cfg = MathConfig.load().get('pvp_v2', {}).get('operations', {})
        return int(cfg.get('check_interval_seconds', 15))
    except Exception:
        return 15


def _is_confirm(val) -> bool:
    """Détermine si un argument représente une confirmation explicite."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('confirm', 'true', 'yes', 'valider')
    return False


class Hack(BaseGameCog):
    """Cog orchestrant les opérations offensives, diagnostics, traces et rançons."""

    def __init__(self, bot):
        self.bot = bot
        self.check_operations_loop.change_interval(seconds=_op_check_interval())
        self.check_pvp_loop = self.check_operations_loop
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self.check_operations_loop.start()

    def cog_unload(self):
        """Arrête la boucle périodique de résolution des opérations."""
        self.check_operations_loop.cancel()

    @tasks.loop(seconds=_op_check_interval())
    async def check_operations_loop(self):
        """Boucle de résolution et activation des opérations offensives arrivées à échéance."""
        try:
            delivered = await self.service.deliver_ready_pvp_v2_operations()
            if delivered:
                logger.info("%d opération(s) PvP V2 résolue(s)", len(delivered))
                for item in delivered:
                    await self._notify_delivered_op(item)
        except Exception:
            logger.exception("Erreur lors de la livraison des opérations PvP V2")

    @check_operations_loop.before_loop
    async def before_check_operations_loop(self):
        """Rattrapage initial des opérations échues dès que le bot est prêt."""
        await self.bot.wait_until_ready()
        try:
            delivered = await self.service.deliver_ready_pvp_v2_operations()
            for item in delivered or []:
                await self._notify_delivered_op(item)
        except Exception:
            logger.exception("Erreur lors du rattrapage des opérations PvP V2")

    async def _notify_delivered_op(self, item: dict):
        """Notifie l'attaquant et/ou la victime en MP lors de la résolution de l'opération."""
        attacker_id = item.get('attacker_id')
        victim_id = item.get('victim_id')
        status = item.get('status')
        tier = item.get('tier', 1)
        fingerprint = item.get('fingerprint', '????')
        family = item.get('family', 'hostile_miner')

        if not attacker_id:
            return

        try:
            attacker_user = self.bot.get_user(attacker_id) or await self.bot.fetch_user(attacker_id)
            if not attacker_user:
                return

            attacker_row = await self.service.database.run(
                lambda tx: tx.one('SELECT lang FROM players WHERE discord_id = %s', (attacker_id,)),
                readonly=True,
            )
            lang = (attacker_row and attacker_row.get('lang')) or 'fr'

            if status == 'active':
                if family == 'hostile_miner':
                    msg = text.get_for_lang(
                        lang,
                        'g_pvp_v2_op_dm_active',
                        victim_id=victim_id,
                        tier=tier,
                        fingerprint=fingerprint,
                    )
                    await attacker_user.send(msg)
                elif family == 'ransomware':
                    ransom_rtm = item.get('ransom_rtm', Decimal('0.005'))
                    msg = f"🔒 **RANSOMWARE DÉPLOYÉ AVEC SUCCÈS**\n> Votre ransomware `[{fingerprint}]` est actif sur le réseau de <@{victim_id}> !\n> • 💰 **Rançon exigée** : **{ransom_rtm} RTM**\n> • ⛔ Les commandes économiques de la cible sont désormais bloquées."
                    await attacker_user.send(msg)
                elif family == 'saturation':
                    msg = f"⚡ **SATURATION OFFENSIVE ACTIVE**\n> Le canal de recherche de <@{victim_id}> est saturé (-30% de débit offensif) pendant 6 heures `[{fingerprint}]`."
                    await attacker_user.send(msg)
            elif status == 'completed':
                if family == 'currency_theft':
                    stolen = item.get('stolen_usd', Decimal('0.00'))
                    net = item.get('net_usd', Decimal('0.00'))
                    msg = f"💸 **VOL DE DEVISES RÉUSSI**\n> Vous avez dérobé **{stolen} USD** sur le réseau de <@{victim_id}> (Net reçu : **{net} USD** après 5% de frais)."
                    await attacker_user.send(msg)
                elif family == 'espionage':
                    msg = f"🕵️ **RAPPORT D'ESPIONNAGE DISCRET**\n> L'inventaire logiciel de <@{victim_id}> a été cartographié avec succès."
                    await attacker_user.send(msg)
                elif family == 'software_theft':
                    msg = f"💾 **VOL DE LOGICIEL RÉUSSI**\n> Vous avez copié avec succès un logiciel depuis le réseau de <@{victim_id}> `[{fingerprint}]`."
                    await attacker_user.send(msg)
            elif status == 'failed':
                reason = item.get('reason', 'unknown')
                reason_label = (
                    "la cible a installé un correctif"
                    if reason == 'patched_during_install'
                    else "système cible inaccessible"
                )
                msg = text.get_for_lang(
                    lang,
                    'g_pvp_v2_op_dm_failed',
                    victim_id=victim_id,
                    reason_label=reason_label,
                )
                await attacker_user.send(msg)
        except Exception:
            logger.warning("Impossible d'envoyer la notification d'opération à %s", attacker_id)

    # ── Slash Command /hack ───────────────────────────────────────────────────
    @discord.slash_command(
        name='hack',
        description=EN['hack'],
        description_localizations={"fr": FR['hack']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def hack(
        self,
        ctx,
        target: discord.Option(
            discord.Member,
            description=desc['hack_target_player'],
            description_localizations=desc_loc['hack_target_player'],
            required=False,
            default=None,
        ) = None,
        family: discord.Option(
            str,
            choices=['hostile_miner', 'ransomware', 'currency_theft', 'saturation', 'espionage', 'software_theft'],
            description="Software family to deploy",
            description_localizations={"fr": "Famille de logiciel à déployer"},
            required=False,
            default='hostile_miner',
        ) = 'hostile_miner',
        tier: discord.Option(
            int,
            choices=[1, 2, 3, 4, 5, 6],
            description=desc['hack_tier'],
            description_localizations=desc_loc['hack_tier'],
            required=False,
            default=None,
        ) = None,
        confirm: discord.Option(
            str,
            choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False,
            default=None,
        ) = None,
    ):
        """Commande Slash /hack : déploie un malware offensif ou lance un diagnostic."""
        is_confirm = _is_confirm(confirm)
        if target is not None:
            action = 'pvp_v2_op_start' if is_confirm else 'pvp_v2_op_quote'
            await self._invoke(
                ctx,
                action,
                target=target.id,
                tier=tier,
                family=family,
            )
        else:
            action = 'pvp_v2_diag_start' if is_confirm else 'pvp_v2_diag_quote'
            await self._invoke(ctx, action)

    # ── Slash Command /diag ───────────────────────────────────────────────────
    @discord.slash_command(
        name='diag',
        description=desc['diag'],
        description_localizations=desc_loc['diag'],
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def diag(
        self,
        ctx,
        confirm: discord.Option(
            str,
            choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False,
            default=None,
        ) = None,
    ):
        """Commande Slash /diag : analyse l'intégrité réseau pour détecter les malwares actifs."""
        action = 'pvp_v2_diag_start' if _is_confirm(confirm) else 'pvp_v2_diag_quote'
        await self._invoke(ctx, action)

    # ── Slash Command /trace ──────────────────────────────────────────────────
    @discord.slash_command(
        name='trace',
        description="Analyze network traces to identify hostile attackers",
        description_localizations={"fr": "Analyser les traces réseau pour identifier les attaquants"},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def trace(
        self,
        ctx,
        confirm: discord.Option(
            str,
            choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False,
            default=None,
        ) = None,
    ):
        """Commande Slash /trace : identifie les attaquants des malwares actifs."""
        action = 'pvp_v2_trace_start' if _is_confirm(confirm) else 'pvp_v2_trace_quote'
        await self._invoke(ctx, action)

    # ── Slash Command /pay ────────────────────────────────────────────────────
    @discord.slash_command(
        name='pay',
        description="Pay ransomware ransom to unlock network operations",
        description_localizations={"fr": "Payer la rançon pour débloquer les commandes du réseau"},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def pay(
        self,
        ctx,
    ):
        """Commande Slash /pay : paye la rançon du ransomware actif."""
        await self._invoke(ctx, 'pvp_v2_pay_ransom')

    # ── Commande Préfixe !hack ────────────────────────────────────────────────
    @commands.command(name='hack', aliases=['hk'], help=FR['hack'])
    async def prefix_hack(self, ctx, *args):
        """Commande préfixe !hack <@cible> [famille] [tier] [confirm] ou sous-commandes diag/trace/pay."""
        await self._prefetch_lang(ctx.author.id)

        if not args:
            prefix = getattr(ctx, 'prefix', None) or '!'
            return await ctx.send(text.get(ctx, 'g_error_hack_usage_v2', prefix=prefix))

        all_args = list(args)
        is_confirm = any(_is_confirm(a) for a in all_args)
        first_arg = all_args[0].lower()

        # Sous-action diagnostic : !hack diag
        if first_arg in ('diag', 'diagnostic'):
            action = 'pvp_v2_diag_start' if is_confirm else 'pvp_v2_diag_quote'
            return await self._invoke(ctx, action)

        # Sous-action trace : !hack trace
        if first_arg in ('trace', 'traces'):
            action = 'pvp_v2_trace_start' if is_confirm else 'pvp_v2_trace_quote'
            return await self._invoke(ctx, action)

        # Sous-action pay : !hack pay / !hack rmd
        if first_arg in ('pay', 'rancon', 'ransom'):
            return await self._invoke(ctx, 'pvp_v2_pay_ransom')

        # Extraction de la cible, famille et tier
        target_arg = None
        tier_val = None
        family_val = 'hostile_miner'

        valid_families = ('hostile_miner', 'ransomware', 'currency_theft', 'saturation', 'espionage', 'software_theft')

        for a in all_args:
            if _is_confirm(a):
                continue
            if a.lower() in valid_families:
                family_val = a.lower()
                continue
            if a.isdigit() and int(a) in range(1, 7) and target_arg is not None and tier_val is None:
                tier_val = int(a)
                continue
            if target_arg is None:
                target_arg = a

        if not target_arg:
            prefix = getattr(ctx, 'prefix', None) or '!'
            return await ctx.send(text.get(ctx, 'g_error_hack_usage_v2', prefix=prefix))

        # Résolution du membre ou utilisateur Discord
        try:
            resolved_target = await commands.MemberConverter().convert(ctx, target_arg)
        except commands.BadArgument:
            try:
                resolved_target = await commands.UserConverter().convert(ctx, target_arg)
            except commands.BadArgument:
                return await ctx.send(text.get(ctx, 'g_error_target_not_registered'))

        action = 'pvp_v2_op_start' if is_confirm else 'pvp_v2_op_quote'
        await self._invoke(
            ctx,
            action,
            target=resolved_target.id,
            tier=tier_val,
            family=family_val,
        )

    # ── Commande Préfixe !diag ────────────────────────────────────────────────
    @commands.command(name='diag', help="Effectuer un diagnostic d'intégrité réseau")
    async def prefix_diag(self, ctx, *args):
        """Commande préfixe !diag [confirm]."""
        await self._prefetch_lang(ctx.author.id)
        is_confirm = any(_is_confirm(a) for a in args)
        action = 'pvp_v2_diag_start' if is_confirm else 'pvp_v2_diag_quote'
        await self._invoke(ctx, action)

    # ── Commande Préfixe !trace ───────────────────────────────────────────────
    @commands.command(name='trace', help="Analyser les traces réseau pour identifier les attaquants")
    async def prefix_trace(self, ctx, *args):
        """Commande préfixe !trace [confirm]."""
        await self._prefetch_lang(ctx.author.id)
        is_confirm = any(_is_confirm(a) for a in args)
        action = 'pvp_v2_trace_start' if is_confirm else 'pvp_v2_trace_quote'
        await self._invoke(ctx, action)

    # ── Commande Préfixe !pay ─────────────────────────────────────────────────
    @commands.command(name='pay', help="Payer la rançon d'un ransomware actif")
    async def prefix_pay(self, ctx):
        """Commande préfixe !pay."""
        await self._prefetch_lang(ctx.author.id)
        await self._invoke(ctx, 'pvp_v2_pay_ransom')

    # ── Rendu Visuel ──────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Rendu visuel stylisé pour les opérations offensives, diagnostics, traces et rançons."""
        e = get_root_emojis(ctx)

        family_display_names = {
            'hostile_miner': 'Hostile Miner',
            'ransomware': 'Ransomware',
            'currency_theft': 'Vol de Devises',
            'saturation': 'Saturation RAM',
            'espionage': 'Espionnage',
            'software_theft': 'Vol de Logiciel',
        }

        # 1. Devis de déploiement offensif
        if method == 'pvp_v2_op_quote':
            target_id = result.get('victim_id')
            family = result.get('family', 'hostile_miner')
            tier = result.get('tier', 1)
            fingerprint = result.get('fingerprint', '????')
            victim_def = result.get('victim_defense_power', 0)
            slowdown_mult = result.get('slowdown_multiplier', 1.0)
            base_dur = result.get('base_duration_seconds', 180)
            effective_dur = result.get('duration_formatted', f"{base_dur}s")

            status_note = ""
            if result.get('is_retaliation'):
                status_note = text.get(ctx, 'g_pvp_v2_op_quote_retaliation')

            fam_label = family_display_names.get(family, family.replace('_', ' ').title())

            body = text.get(
                ctx,
                'g_pvp_v2_op_quote_body',
                e_ops=e.get('operations', '📋'),
                e_fw=e.get('firewall', '🛡️'),
                e_tmp=e.get('temps', '⏱️'),
                e_pui=e.get('puissance', '⚙️'),
                family_label=fam_label,
                tier=tier,
                fingerprint=fingerprint,
                victim_defense=victim_def,
                slowdown_mult=slowdown_mult,
                effective_duration=effective_dur,
                base_duration=base_dur,
                status_note=status_note,
            )
            header = text.get(ctx, 'g_pvp_v2_op_quote_header', e_hack=e.get('hack', '⚔️'), target_id=target_id)
            embed_content = f"{header}\n\n{body}"

            confirmation_args = {
                'target': target_id,
                'copy_id': result.get('copy_id'),
                'family': family,
                'tier': tier,
            }
            view = Confirmation(self._send, self.service, ctx, 'pvp_v2_op_start', confirmation_args)
            await self._send_embed(ctx, 'hack', embed_content, view=view)

        # 2. Lancement effectif de l'opération
        elif method == 'pvp_v2_op_start':
            target_id = result.get('victim_id')
            family = result.get('family', 'hostile_miner')
            tier = result.get('tier', 1)
            fingerprint = result.get('fingerprint', '????')
            resolves_at = result.get('resolves_at') or result.get('installed_at')
            ts = int(resolves_at.replace(tzinfo=timezone.utc).timestamp()) if isinstance(resolves_at, datetime) else 0

            fam_label = family_display_names.get(family, family.replace('_', ' ').title())
            content = text.get(
                ctx,
                'g_pvp_v2_op_started',
                e_hack=e.get('hack', '⚔️'),
                e_tmp=e.get('temps', '⏱️'),
                family_label=fam_label,
                tier=tier,
                fingerprint=fingerprint,
                target_id=target_id,
                timestamp=ts,
            )
            embed = RootEmbed(ctx, 'hack', content)
            await embed.send(ctx)

        # 3. Devis de diagnostic réseau
        elif method == 'pvp_v2_diag_quote':
            cost_rtm = Decimal(str(result.get('cost_rtm', '0.001')))
            body = text.get(
                ctx,
                'g_pvp_v2_diag_quote_body',
                e_ops=e.get('operations', '📋'),
                cost_rtm=f"{cost_rtm:,.5f}",
            )
            header = text.get(ctx, 'g_pvp_v2_diag_quote_header', e_scan=e.get('scan', '🔍'))
            embed_content = f"{header}\n\n{body}"

            confirmation_args = {'quoted_rtm': str(cost_rtm)}
            view = Confirmation(self._send, self.service, ctx, 'pvp_v2_diag_start', confirmation_args)
            await self._send_embed(ctx, 'scan', embed_content, view=view)

        # 4. Résultat du diagnostic réseau
        elif method == 'pvp_v2_diag_start':
            count = result.get('detected_count', 0)
            header = text.get(ctx, 'g_pvp_v2_diag_quote_header', e_scan=e.get('scan', '🔍'))
            if count == 0:
                body = text.get(ctx, 'g_pvp_v2_diag_clean')
            else:
                lines = []
                for m in result.get('malwares', []):
                    started_at = m.get('started_at')
                    sts = int(started_at.replace(tzinfo=timezone.utc).timestamp()) if isinstance(started_at, datetime) else 0
                    fam_lbl = family_display_names.get(m.get('family'), m.get('family'))
                    lines.append(
                        text.get(
                            ctx,
                            'g_pvp_v2_diag_malware_item',
                            family_label=fam_lbl,
                            tier=m.get('tier'),
                            fingerprint=m.get('fingerprint'),
                            started_ts=sts,
                        )
                    )
                body = text.get(ctx, 'g_pvp_v2_diag_detected', count=count, malware_list="\n".join(lines))

            embed_content = f"{header}\n\n{body}"
            await self._send_embed(ctx, 'scan', embed_content)

        # 5. Devis d'analyse de trace
        elif method == 'pvp_v2_trace_quote':
            cost_rtm = Decimal(str(result.get('cost_rtm', '0.002')))
            count = result.get('active_malware_count', 0)
            if count == 0:
                embed_content = text.get(ctx, 'g_pvp_v2_trace_no_malware')
                return await self._send_embed(ctx, 'scan', embed_content)

            body = text.get(
                ctx,
                'g_pvp_v2_trace_quote_body',
                cost_rtm=f"{cost_rtm:,.5f}",
                count=count,
            )
            header = text.get(ctx, 'g_pvp_v2_trace_quote_header')
            embed_content = f"{header}\n\n{body}"

            confirmation_args = {'quoted_rtm': str(cost_rtm)}
            view = Confirmation(self._send, self.service, ctx, 'pvp_v2_trace_start', confirmation_args)
            await self._send_embed(ctx, 'scan', embed_content, view=view)

        # 6. Résultat d'analyse de trace
        elif method == 'pvp_v2_trace_start':
            total = result.get('total_analyzed', 0)
            found = result.get('identified_count', 0)
            header = text.get(ctx, 'g_pvp_v2_trace_result_header')

            lines = []
            for r in result.get('results', []):
                fp = r.get('fingerprint')
                if r.get('identified'):
                    lines.append(text.get(ctx, 'g_pvp_v2_trace_attacker_found', fingerprint=fp, attacker_id=r.get('attacker_id')))
                else:
                    lines.append(text.get(ctx, 'g_pvp_v2_trace_attacker_unknown', fingerprint=fp))

            summary = text.get(ctx, 'g_pvp_v2_trace_summary', found=found, total=total)
            embed_content = f"{header}\n\n" + "\n".join(lines) + f"\n\n{summary}"
            await self._send_embed(ctx, 'scan', embed_content)

        # 7. Paiement de rançon
        elif method == 'pvp_v2_pay_ransom':
            attacker_id = result.get('attacker_id')
            ransom_rtm = result.get('ransom_rtm', Decimal('0.005'))
            fp = result.get('fingerprint', '????')

            content = (
                f"🔓 **RANÇON VERSÉE & SYSTÈME DÉBLOQUÉ**\n"
                f"> Vous avez transféré **{ransom_rtm:,.5f} RTM** à <@{attacker_id}> pour neutraliser le ransomware `[{fp}]`.\n"
                f"> • 🟢 Vos commandes économiques et de développement sont maintenant déverrouillées !\n"
                f"> • 🛡️ *Immunité de 48h accordée contre cette signature.*"
            )
            await self._send_embed(ctx, 'hack', content)


def setup(bot):
    """Point d'entrée standard de chargement du Cog Hack."""
    bot.add_cog(Hack(bot))
