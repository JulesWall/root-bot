"""Commande /scan et !scan — Sondage et reconnaissance de réseau adverse (PvP V2).

Mécanique conforme à design/PVP_V2_DECISIONS.md (Décision 11, 14, 15) :
- Sondage déterministe (coût 0.005 RTM, durée 90s).
- Phase 1 : Devis estimatif avec boutons de validation ✅ et annulation ❌ (Two-Phase Commit).
- Phase 2 : Prélèvement RTM, journalisation #blockchain et création du job différé dans `hack`.
- Livraison : Worker persistant capturant la photographie directe (snapshot) à t=résolution.
  - Envoi en MP au scanner du rapport complet (RootEmbed turquoise).
  - Alerte au défenseur si pare-feu/infrastructure >= 3 (anonyme), >= 4 (identifié).
"""

import asyncio
import json
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
from utils.logger import Logger
from utils.root_embed import RootEmbed


logger = logging.getLogger(__name__)


def _scan_check_interval() -> int:
    """Intervalle de vérification de la livraison des scans depuis math.json."""
    try:
        cfg = MathConfig.get_pvp_v2_network_scan()
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


def format_scan_report(ctx_or_lang, report_row: dict, bot=None) -> str:
    """Formate les données d'un rapport de reconnaissance réseau direct sous forme de texte markdown pour RootEmbed."""
    e = get_root_emojis(ctx_or_lang)
    lang = getattr(ctx_or_lang, 'guild', None) and text.get_locale(ctx_or_lang) or 'fr'
    if isinstance(ctx_or_lang, str):
        lang = ctx_or_lang
    is_fr = (lang == 'fr')

    victim_id = int(report_row.get('victim_id') or 0)
    raw_data = report_row.get('report_data') or {}
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except Exception:
            raw_data = {}

    created_at = report_row.get('created_at')
    created_ts = int(created_at.replace(tzinfo=timezone.utc).timestamp()) if isinstance(created_at, datetime) else int(datetime.now(timezone.utc).timestamp())

    # Libellés des familles de logiciels
    family_labels = {
        'hostile_miner': 'Hostile Miner',
        'ransomware': 'Ransomware',
        'currency_theft': 'Vol de Devises' if is_fr else 'Currency Theft',
        'saturation': 'Saturation RAM' if is_fr else 'RAM Saturation',
        'network_scan': 'Scan Réseau' if is_fr else 'Network Scan',
        'software_theft': 'Vol de Logiciel' if is_fr else 'Software Theft',
    }

    # 1. En-tête & Métadonnées
    header_title = f"{e['scan']} **Rapport de Reconnaissance Réseau** · <@{victim_id}>" if is_fr else f"{e['scan']} **Network Reconnaissance Report** · <@{victim_id}>"
    capture_lbl = f"> • 📅 **Capture directe** : <t:{created_ts}:f> (<t:{created_ts}:R>)" if is_fr else f"> • 📅 **Direct snapshot**: <t:{created_ts}:f> (<t:{created_ts}:R>)"
    meta_lines = [
        header_title,
        capture_lbl,
    ]

    # 2. Infrastructure, Puissance & Mémoire
    infra_lvl = int(raw_data.get('infrastructure_level', 0) or 0)
    filled_lvl = max(0, min(5, infra_lvl))
    lvl_bar = '▰' * filled_lvl + '▱' * (5 - filled_lvl)

    hashrate = int(raw_data.get('total_hashrate_hs', 0) or 0)
    est_rtm_h = raw_data.get('estimated_production_rtm_h', '0.00000')
    used_ratio = float(raw_data.get('memory_used_ratio', 0.0) or 0.0)
    used_pct = round(used_ratio * 100, 1)
    buffer_rtm = raw_data.get('memory_buffer_rtm', '0.00000')
    capacity_rtm = raw_data.get('memory_capacity_rtm', '0.00000')

    bar_blocks = max(0, min(10, int(round(used_ratio * 10.0))))
    ram_bar = '▰' * bar_blocks + '▱' * (10 - bar_blocks)

    if is_fr:
        infra_title = f"\n{e['firewall']} **Infrastructure & Sécurité**"
        infra_desc = f"> • **Pare-feu système** : Niveau `{infra_lvl}` `{lvl_bar}` ({infra_lvl}/5)"
        pui_title = f"\n{e['puissance']} **Capacité de Calcul & Mémoire Vive**"
        pui_desc = f"> • {e['puissance']} **Hashrate minage** : **{hashrate:,} H/s** (~`{est_rtm_h}` RTM/h)"
        mem_desc = f"> • {e['memoire']} **Tampon RAM** : `{buffer_rtm}` / `{capacity_rtm}` RTM ({used_pct}%)\n>   └ `{ram_bar}`"
    else:
        infra_title = f"\n{e['firewall']} **Infrastructure & Security**"
        infra_desc = f"> • **System Firewall**: Level `{infra_lvl}` `{lvl_bar}` ({infra_lvl}/5)"
        pui_title = f"\n{e['puissance']} **Computing Capacity & Memory**"
        pui_desc = f"> • {e['puissance']} **Mining hashrate**: **{hashrate:,} H/s** (~`{est_rtm_h}` RTM/h)"
        mem_desc = f"> • {e['memoire']} **RAM Buffer**: `{buffer_rtm}` / `{capacity_rtm}` RTM ({used_pct}%)\n>   └ `{ram_bar}`"

    core_lines = [infra_title, infra_desc, pui_title, pui_desc, mem_desc]

    # 3. Modules matériels installés par baie (Tier)
    modules_by_tier = raw_data.get('modules_by_tier', {})
    mod_lines = [f"\n{e['materiel']} **Modules Matériels Détectés**" if is_fr else f"\n{e['materiel']} **Hardware Modules Detected**"]
    has_any_module = False
    for tier_key in sorted(modules_by_tier.keys(), key=lambda x: int(x)):
        m = modules_by_tier[tier_key]
        mining = int(m.get('mining', 0) or 0)
        attack = int(m.get('attack', 0) or 0)
        defense = int(m.get('bay_defense', 0) or 0)
        if mining > 0 or attack > 0 or defense > 0:
            has_any_module = True
            parts = []
            if mining > 0:
                parts.append(f"{mining} mineur(s)" if is_fr else f"{mining} miner(s)")
            if attack > 0:
                parts.append(f"{attack} attaque" if is_fr else f"{attack} attack")
            if defense > 0:
                parts.append(f"{defense} défense" if is_fr else f"{defense} defense")
            mod_lines.append(f"> • **Baie Tier {tier_key}** : {' · '.join(parts)}")

    if not has_any_module:
        mod_lines.append(f"> • *Aucun module matériel installé dans les baies.*" if is_fr else f"> • *No hardware modules installed in bays.*")

    # 4. Logiciels & Correctifs
    soft_lines = [f"\n{e['logiciels']} **Logiciels Compilés & Correctifs Déployés**" if is_fr else f"\n{e['logiciels']} **Compiled Software & Deployed Patches**"]
    software_list = raw_data.get('installed_software', [])
    if software_list:
        for s in software_list:
            raw_fam = s.get('family', '')
            fam = family_labels.get(raw_fam, raw_fam.replace('_', ' ').title())
            t = s.get('tier', 1)
            fp = s.get('fingerprint', '????')
            soft_lines.append(f"> • 💻 **{fam}** (T{t}) — Empreinte `[{fp}]`")
    else:
        soft_lines.append(f"> • *Aucun logiciel offensif ou utilitaire compilé.*" if is_fr else f"> • *No offensive or utility software compiled.*")

    patches_list = raw_data.get('installed_patches', [])
    if patches_list:
        for p in patches_list:
            raw_fam = p.get('family', '')
            fam = family_labels.get(raw_fam, raw_fam.replace('_', ' ').title())
            fp = p.get('fingerprint', '????')
            soft_lines.append(f"> • 🛡️ Correctif **{fam}** — Empreinte `[{fp}]`")
    else:
        soft_lines.append(f"> • *Aucun correctif actif déployé sur le réseau.*" if is_fr else f"> • *No active defensive patch deployed on the network.*")

    # 5. Activité de Recherche & Développement
    active_jobs = int(raw_data.get('active_dev_jobs_count', 0) or 0)
    jobs_title = f"\n{e['operations']} **Activités de Développement Détectées**" if is_fr else f"\n{e['operations']} **Development Activities Detected**"
    if active_jobs > 0:
        jobs_desc = f"> • 📋 **Recherche active** : **{active_jobs}** job(s) en cours d'exécution" if is_fr else f"> • 📋 **Active research**: **{active_jobs}** job(s) currently in progress"
    else:
        jobs_desc = f"> • *Aucun processus de développement actif détecté.*" if is_fr else f"> • *No active development process detected.*"
    jobs_lines = [jobs_title, jobs_desc]

    all_blocks = meta_lines + core_lines + mod_lines + soft_lines + jobs_lines
    return "\n".join(all_blocks)


class Scan(BaseGameCog):
    """Cog gérant le scan de réseau adverse PvP V2 (/scan et !scan)."""

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
        """Arrête la boucle de vérification périodique."""
        self.check_scans_loop.cancel()

    @tasks.loop(seconds=_scan_check_interval())
    async def check_scans_loop(self):
        """Boucle de livraison des scans arrivés à échéance et purge des conséquences."""
        try:
            delivered = await self.service.deliver_expired_scans()
            if delivered:
                logger.info("%d scan(s) PvP V2 à livrer", len(delivered))
                for item in delivered:
                    await self._notify_delivered_v2(item)
            await self.service.purge_expired_consequences()
        except Exception:
            logger.exception("Erreur lors de la livraison des scans expirés")

    @check_scans_loop.before_loop
    async def before_check_scans_loop(self):
        """Rattrapage initial des scans échus dès que le bot est prêt."""
        await self.bot.wait_until_ready()
        try:
            delivered = await self.service.deliver_expired_scans()
            for item in delivered or []:
                await self._notify_delivered_v2(item)
            await self.service.purge_expired_consequences()
        except Exception:
            logger.exception("Erreur lors du rattrapage initial des scans")

    async def _notify_delivered_v2(self, item: dict):
        """Notifie le scanner par MP avec le rapport figé, et alerte la cible si son pare-feu le permet."""
        scanner_id = item.get('attacker_id')
        victim_id = item.get('victim_id')
        status = item.get('status')

        if not scanner_id or not victim_id:
            return

        # 1. Cas d'échec : la cible a été supprimée pendant le sondage
        if status == 'victim_deleted':
            try:
                scanner_user = self.bot.get_user(scanner_id) or await self.bot.fetch_user(scanner_id)
                if scanner_user:
                    scanner_row = await self.service.database.run(
                        lambda tx: tx.one('SELECT lang FROM players WHERE discord_id = %s', (scanner_id,)),
                        readonly=True,
                    )
                    slang = (scanner_row and scanner_row.get('lang')) or 'fr'
                    msg = text.get_for_lang(slang, 'g_pvp_v2_scan_dm_victim_deleted', target_id=victim_id)
                    await scanner_user.send(msg)
            except Exception:
                logger.warning("Impossible d'envoyer la notification de scan annulé au joueur %s", scanner_id)
            return

        # 2. Cas de succès : livraison du rapport de sondage complet au scanner
        try:
            scanner_user = self.bot.get_user(scanner_id) or await self.bot.fetch_user(scanner_id)
            if scanner_user:
                scanner_row = await self.service.database.run(
                    lambda tx: tx.one('SELECT lang FROM players WHERE discord_id = %s', (scanner_id,)),
                    readonly=True,
                )
                slang = (scanner_row and scanner_row.get('lang')) or 'fr'

                report_embed_content = format_scan_report(slang, {
                    'victim_id': victim_id,
                    'created_at': datetime.now(timezone.utc),
                    'report_data': item.get('report_data'),
                }, bot=self.bot)

                title = "Root OS • Rapport de Reconnaissance Réseau" if slang == 'fr' else "Root OS • Network Reconnaissance Report"
                footer = "Root OS • Système de Reconnaissance V2" if slang == 'fr' else "Root OS • Reconnaissance System V2"
                bot_user = getattr(self.bot, 'user', None)
                icon_url = bot_user.display_avatar.url if bot_user and hasattr(bot_user, 'display_avatar') else None

                embed = discord.Embed(
                    title=title,
                    description=report_embed_content,
                    color=discord.Color.from_rgb(84, 226, 209),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.set_footer(text=footer, icon_url=icon_url)
                dm_header = text.get_for_lang(slang, 'g_pvp_v2_scan_dm_delivered', target_id=victim_id)
                await scanner_user.send(content=dm_header, embed=embed)
        except Exception:
            logger.exception("Erreur lors de la notification DM du rapport de scan au scanner %s", scanner_id)

        # 3. Alerte au pare-feu de la cible (Niv. 3 anonyme, Niv. 4 identifié)
        try:
            victim_row = await self.service.database.run(
                lambda tx: tx.one('SELECT infrastructure_level, firewall_level, lang FROM players WHERE discord_id = %s', (victim_id,)),
                readonly=True,
            )
            if victim_row:
                fw_lvl = int(victim_row.get('infrastructure_level') or victim_row.get('firewall_level') or 0)
                cfg = MathConfig.load().get('scan', {})
                alert_threshold = int(cfg.get('alert_firewall_threshold', 3))
                identity_threshold = int(cfg.get('alert_identity_threshold', 4))

                victim_user = self.bot.get_user(victim_id) or await self.bot.fetch_user(victim_id)
                if victim_user and fw_lvl >= alert_threshold:
                    vlang = victim_row.get('lang') or 'fr'
                    if fw_lvl >= identity_threshold:
                        alert_msg = text.get_for_lang(vlang, 'g_scan_alert_identified', scanner=scanner_id)
                    else:
                        alert_msg = text.get_for_lang(vlang, 'g_scan_alert_anon', level=fw_lvl)
                    await victim_user.send(alert_msg)
        except Exception:
            logger.warning("Impossible d'envoyer l'alerte de sécurité de scan à la victime %s", victim_id)

    # ── Slash Command /scan ──────────────────────────────────────────────────
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
        confirm: discord.Option(
            str,
            choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False,
            default=None,
        ) = None,
    ):
        """Commande Slash /scan : sonde le réseau adverse."""
        await self._invoke_scan(ctx, target=target, is_confirm=_is_confirm(confirm))

    # ── Préfixe !scan ────────────────────────────────────────────────────────
    @commands.command(name='scan', help=FR['scan'])
    async def prefix_scan(self, ctx, arg1: str = None, *args):
        """Commande préfixe !scan <@cible> [confirm]."""
        await self._prefetch_lang(ctx.author.id)

        if not arg1:
            prefix = getattr(ctx, 'prefix', None) or '!'
            return await ctx.send(text.get(ctx, 'g_error_scan_usage', prefix=prefix))

        all_args = [arg1] + list(args)
        is_confirm = any(_is_confirm(a) for a in all_args)

        # Extraction de la cible parmi les arguments (le premier argument qui n'est pas confirm)
        target_arg = None
        for a in all_args:
            if not _is_confirm(a):
                target_arg = a
                break

        if not target_arg:
            prefix = getattr(ctx, 'prefix', None) or '!'
            return await ctx.send(text.get(ctx, 'g_error_scan_usage', prefix=prefix))

        # Résolution du membre ou utilisateur Discord
        try:
            resolved_target = await commands.MemberConverter().convert(ctx, target_arg)
        except commands.BadArgument:
            try:
                resolved_target = await commands.UserConverter().convert(ctx, target_arg)
            except commands.BadArgument:
                return await ctx.send(text.get(ctx, 'g_error_target_not_registered'))

        await self._invoke_scan(ctx, target=resolved_target, is_confirm=is_confirm)

    async def _invoke_scan(self, ctx, target, is_confirm: bool = False):
        """Logique d'exécution unifiée pour slash et préfixe."""
        await self._prefetch_lang(ctx.author.id)
        target_id = getattr(target, 'id', target)
        action = 'pvp_v2_scan_start' if is_confirm else 'pvp_v2_scan_quote'
        await self._invoke(ctx, action, target=target_id)

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Formate et restitue la réponse visuelle de l'opération demandée."""
        e = get_root_emojis(ctx)

        # 1. Devis de reconnaissance (pvp_v2_scan_quote)
        if method == 'pvp_v2_scan_quote':
            target_id = result.get('victim_id')
            rtm_cost = Decimal(str(result.get('cost_rtm', '0.005')))
            duration = result.get('duration_seconds', 90)
            victim_infra = result.get('victim_infrastructure', 0)

            status_note = ""
            if result.get('is_retaliation'):
                status_note += text.get(ctx, 'g_pvp_v2_scan_quote_retaliation')

            body = text.get(
                ctx,
                'g_pvp_v2_scan_quote_body',
                e_fw=e['firewall'],
                e_tmp=e['temps'],
                e_pui=e['puissance'],
                target_id=target_id,
                victim_infra=victim_infra,
                duration=duration,
                rtm_cost=f"{rtm_cost:,.5f}",
                status_note=status_note,
            )
            embed_content = f"{text.get(ctx, 'g_pvp_v2_scan_quote_header', e_scan=e['scan'])}\n\n{body}"

            confirmation_args = {
                'target': target_id,
                'quoted_rtm': str(rtm_cost),
            }
            view = Confirmation(self._send, self.service, ctx, 'pvp_v2_scan_start', confirmation_args)
            await self._send_embed(ctx, 'scan', embed_content, view=view)

        # 2. Lancement du scan réseau (pvp_v2_scan_start)
        elif method == 'pvp_v2_scan_start':
            target_id = result.get('victim_id')
            rtm_cost = Decimal(str(result.get('cost_rtm', '0.005')))
            expires_at = result.get('expires_at')
            ts = int(expires_at.replace(tzinfo=timezone.utc).timestamp()) if isinstance(expires_at, datetime) else 0

            content = text.get(
                ctx,
                'g_pvp_v2_scan_started',
                e_scan=e['scan'],
                e_tmp=e['temps'],
                target_id=target_id,
                rtm_cost=f"{rtm_cost:,.5f}",
                timestamp=ts,
            )

            kwargs = {'content': content, 'allowed_mentions': discord.AllowedMentions.none()}
            if getattr(ctx, 'interaction', None):
                await ctx.respond(**kwargs)
            else:
                await ctx.send(**kwargs)

            # Journalisation blockchain
            bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)
            try:
                await bot_logger.log_blockchain_transaction(
                    from_id=ctx.author.id,
                    to_address="0xROOT_SCAN_NODE",
                    rtm_amount=rtm_cost,
                    tx_type="SCAN",
                )
            except Exception:
                logger.exception("Erreur lors de la journalisation blockchain pour le scan V2")


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Scan(bot))
