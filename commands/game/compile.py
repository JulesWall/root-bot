"""Commande /dev, /library et gestion du cycle logiciel PvP V2.

Remplace l'ancienne production d'ATK par le cycle de développement (recherche, compilation,
correctifs). Maintient le worker d'échéance persistant et fournit les interfaces utilisateur.
L'ancienne commande /compile est dépréciée et redirige vers /dev.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

import discord
from discord.ext import commands, tasks

import data
from commands.game.commandgame import BaseGameCog
from game.db.players import Player
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


def _dev_check_interval() -> int:
    """Intervalle de vérification des jobs de développement depuis math.json."""
    return int(MathConfig.load().get('pvp_v2', {}).get('development', {}).get('check_interval_seconds', 30))


def _is_confirm(val) -> bool:
    """Détermine si un argument représente une confirmation explicite."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('confirm', 'true', 'yes', 'valider')
    return False


def _format_seconds(seconds: int) -> str:
    """Formate une durée en secondes sous forme lisible (ex: 45 min, 2h 15m)."""
    sec = max(0, int(seconds))
    if sec < 60:
        return f"{sec}s"
    minutes = sec // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    rem_min = minutes % 60
    if rem_min == 0:
        return f"{hours}h"
    return f"{hours}h {rem_min}m"


class Compile(BaseGameCog):
    """Cog gérant le cycle de développement logiciel PvP V2 et les livraisons d'échéance."""

    def __init__(self, bot):
        self.bot = bot
        self.check_dev_loop.change_interval(seconds=_dev_check_interval())
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self.check_dev_loop.start()

    def cog_unload(self):
        """Arrête la boucle périodique au déchargement."""
        self.check_dev_loop.cancel()

    # ── Boucle de livraison ──────────────────────────────────────────────────
    @tasks.loop(seconds=_dev_check_interval())
    async def check_dev_loop(self):
        """Livre les jobs de développement PvP V2 échus."""
        try:
            delivered_v2 = await self.service.deliver_expired_pvp_v2_jobs()
            if delivered_v2:
                logger.info("%d job(s) PvP V2 livré(s)", len(delivered_v2))
                for item in delivered_v2:
                    await self._notify_delivered_v2(item)

            # Traite également d'éventuels jobs legacy résiduels
            delivered_v1 = await self.service.deliver_expired_hacks()
            if delivered_v1:
                logger.info("%d job(s) legacy ATK livré(s)", len(delivered_v1))
        except Exception:
            logger.exception("Erreur lors de la livraison des jobs de développement PvP V2")

    @check_dev_loop.before_loop
    async def before_check_dev_loop(self):
        """Attend que le bot soit prêt puis rattrape immédiatement les jobs échus."""
        await self.bot.wait_until_ready()
        try:
            delivered_v2 = await self.service.deliver_expired_pvp_v2_jobs()
            for item in delivered_v2 or []:
                await self._notify_delivered_v2(item)
            await self.service.deliver_expired_hacks()
        except Exception:
            logger.exception("Erreur lors du rattrapage initial des jobs PvP V2")

    async def _notify_delivered(self, item: dict):
        """Notifie le joueur en message privé de la livraison de son job (PvP V2 ou legacy)."""
        player_id = item.get('player_id') or item.get('discord_id')
        if not player_id:
            return

        try:
            user = self.bot.get_user(player_id) or await self.bot.fetch_user(player_id)
            if not user:
                return
        except discord.HTTPException:
            return
        except Exception:
            return

        if 'job_type' in item:
            job_type = item['job_type']
            family = item.get('family', '')
            tier = item.get('tier', 1)
            fp = item.get('fingerprint', '????')
            try:
                lang = await self.service.database.run(
                    lambda tx: Player.get_language(tx, player_id),
                    readonly=True,
                ) or 'fr'
            except Exception:
                lang = 'fr'
            e = get_root_emojis(self.bot)
            content = text.get_for_lang(
                lang,
                'g_pvp_v2_delivered_dm',
                e_mem=e['memoire'],
                job_type_label=job_type,
                family=family,
                tier=tier,
                fingerprint=fp,
            )
        else:
            atk = item.get('atk_yield', 0)
            content = f"Production terminée : +{atk} points d'attaque."

        max_retries = 3
        for attempt in range(max_retries):
            try:
                await user.send(content)
                break
            except discord.Forbidden:
                logger.debug("MP fermés pour le joueur %s", player_id)
                break
            except discord.HTTPException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    logger.warning("Échec HTTP lors de l'envoi du MP à %s", player_id)
            except Exception:
                logger.warning("Erreur inattendue envoi MP à %s", player_id)
                break

    _notify_delivered_v2 = _notify_delivered

    # ── Commande /compile dépréciée ──────────────────────────────────────────
    @discord.slash_command(
        name='compile',
        description=EN['compile'],
        description_localizations={"fr": FR['compile']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def compile(self, ctx):
        """Avertit de la désactivation de l'ancienne commande /compile."""
        await self._prefetch_lang(ctx.author.id)
        msg = text.get(ctx, 'g_pvp_v2_compile_deprecated')
        kwargs = {'content': msg, 'allowed_mentions': discord.AllowedMentions.none()}
        if getattr(ctx, 'interaction', None):
            await ctx.respond(**kwargs)
        else:
            await ctx.send(**kwargs)

    @commands.command(name='compile', aliases=['cp'], help=FR['compile'])
    async def prefix_compile(self, ctx, *args):
        """Commande préfixe !compile dépréciée."""
        await self._prefetch_lang(ctx.author.id)
        msg = text.get(ctx, 'g_pvp_v2_compile_deprecated')
        await ctx.send(msg)

    # ── Groupe Slash /dev ────────────────────────────────────────────────────
    dev_group = discord.SlashCommandGroup(
        name='dev',
        description=EN['dev'],
        description_localizations={"fr": FR['dev']},
        guild_ids=data.GUILD_WHITELIST or None,
    )

    @dev_group.command(
        name='start',
        description=desc['dev_start'],
        description_localizations=desc_loc['dev_start'],
    )
    async def dev_start(
        self,
        ctx,
        job_type: discord.Option(
            str,
            choices=['research', 'compile', 'patch_research', 'patch_compile'],
            description=desc['dev_job_type'],
            description_localizations=desc_loc['dev_job_type'],
        ),
        family: discord.Option(
            str,
            choices=['hostile_miner', 'ransomware', 'currency_theft', 'saturation', 'network_scan', 'software_theft', 'espionage'],
            description=desc['dev_family'],
            description_localizations=desc_loc['dev_family'],
        ),
        tier: discord.Option(
            int,
            min_value=1,
            max_value=6,
            description=desc['dev_tier'],
            description_localizations=desc_loc['dev_tier'],
        ),
        fingerprint: discord.Option(
            str,
            description=desc['dev_fingerprint'],
            description_localizations=desc_loc['dev_fingerprint'],
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
        """Lance ou demande le devis d'un job de développement."""
        action = 'pvp_v2_start_job' if _is_confirm(confirm) else 'pvp_v2_dev_quote'
        await self._invoke(
            ctx,
            action,
            job_type=job_type,
            family=family,
            tier=tier,
            fingerprint=fingerprint,
        )

    @dev_group.command(
        name='status',
        description=desc['dev_status'],
        description_localizations=desc_loc['dev_status'],
    )
    async def dev_status(self, ctx):
        """Affiche les jobs de développement en cours."""
        await self._invoke(ctx, 'pvp_v2_library')

    @dev_group.command(
        name='cancel',
        description=desc['dev_cancel'],
        description_localizations=desc_loc['dev_cancel'],
    )
    async def dev_cancel(
        self,
        ctx,
        channel: discord.Option(
            str,
            choices=['offense', 'defense'],
            description=desc['dev_channel'],
            description_localizations=desc_loc['dev_channel'],
        ),
    ):
        """Annule le job en cours sur un canal."""
        await self._invoke(ctx, 'pvp_v2_cancel_job', channel=channel)

    @dev_group.command(
        name='help',
        description=desc.get('dev_help', "Guide et syntaxe du développement logiciel"),
        description_localizations=desc_loc.get('dev_help'),
    )
    async def dev_help(self, ctx):
        """Affiche le lexique et guide complet du développement."""
        await self._send_dev_help(ctx)

    # ── Slash /library ───────────────────────────────────────────────────────
    @discord.slash_command(
        name='library',
        description=EN['library'],
        description_localizations={"fr": FR['library']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def library(self, ctx):
        """Affiche la bibliothèque de logiciels et correctifs."""
        await self._invoke(ctx, 'pvp_v2_library')

    # ── Préfixe !dev et !library ─────────────────────────────────────────────
    @commands.group(name='dev', help=FR['dev'], invoke_without_command=True)
    async def prefix_dev(self, ctx):
        """Commande préfixe !dev : affiche le lexique et guide complet."""
        await self._send_dev_help(ctx)

    @prefix_dev.command(name='help')
    async def prefix_dev_help(self, ctx):
        """Commande préfixe !dev help : affiche le lexique et guide complet."""
        await self._send_dev_help(ctx)

    @prefix_dev.command(name='start')
    async def prefix_dev_start(self, ctx, job_type: str = None, family: str = None, tier: int = None, *args):
        """Commande préfixe !dev start <type> <family> <tier> [fingerprint] [confirm]."""
        await self._prefetch_lang(ctx.author.id)
        if not job_type or not family or tier is None:
            prefix = getattr(ctx, 'prefix', None) or '!'
            return await ctx.send(text.get(ctx, 'g_error_dev_start_usage', prefix=prefix))

        confirm = any(_is_confirm(a) for a in args)
        fp = None
        for a in args:
            if not _is_confirm(a):
                fp = str(a).upper()
                break

        action = 'pvp_v2_start_job' if confirm else 'pvp_v2_dev_quote'
        await self._invoke(ctx, action, job_type=job_type, family=family, tier=int(tier), fingerprint=fp)

    @prefix_dev.command(name='status')
    async def prefix_dev_status(self, ctx):
        """Commande préfixe !dev status."""
        await self._invoke(ctx, 'pvp_v2_library')

    @prefix_dev.command(name='cancel')
    async def prefix_dev_cancel(self, ctx, channel: str = None):
        """Commande préfixe !dev cancel <offense|defense>."""
        if not channel or channel not in ('offense', 'defense'):
            prefix = getattr(ctx, 'prefix', None) or '!'
            return await ctx.send(text.get(ctx, 'g_error_dev_cancel_usage', prefix=prefix))
        await self._invoke(ctx, 'pvp_v2_cancel_job', channel=channel)

    @commands.command(name='library', aliases=['lib'], help=FR['library'])
    async def prefix_library(self, ctx):
        """Commande préfixe !library."""
        await self._invoke(ctx, 'pvp_v2_library')

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send_dev_help(self, ctx):
        """Affiche le lexique et la syntaxe complète de la commande dev."""
        await self._prefetch_lang(ctx.author.id)
        e = get_root_emojis(ctx)
        prefix = getattr(ctx, 'prefix', None) or '!'
        if getattr(ctx, 'interaction', None):
            prefix = '/'
        content = text.get(
            ctx,
            'g_dev_syntax',
            e_ops=e['operations'],
            e_log=e['logiciels'],
            e_fw=e['firewall'],
            e_mem=e['memoire'],
            e_pui=e['puissance'],
            e_con=e['connexions'],
            e_tmp=e['temps'],
            e_alt=e['alerte'],
            prefix=prefix,
        )
        await self._send_embed(ctx, 'dev', content)

    async def _send(self, ctx, method, result):
        """Formate et envoie la réponse selon l'action exécutée."""
        e = get_root_emojis(ctx)

        if method == 'pvp_v2_dev_quote':
            fp_str = f" · Empreinte : `{result.get('fingerprint')}`" if result.get('fingerprint') else ""
            power_unit = "Bit/s" if result.get('channel') == 'offense' else "DEF"
            body = text.get(
                ctx,
                'g_pvp_v2_quote_body',
                e_ops=e['operations'],
                e_log=e['logiciels'],
                e_con=e['connexions'],
                e_pui=e['puissance'],
                e_mem=e['memoire'],
                e_tmp=e['temps'],
                job_type_label=result.get('job_type'),
                family=result.get('family'),
                tier=result.get('tier'),
                fp_str=fp_str,
                channel_label=result.get('channel'),
                power=f"{result.get('power')} {power_unit}",
                rtm_cost=f"{Decimal(str(result.get('rtm_cost', 0))):,.5f}",
                duration=_format_seconds(result.get('duration_seconds', 0)),
            )
            embed_content = f"{text.get(ctx, 'g_pvp_v2_quote_header', e_ops=e['operations'])}\n\n{body}"
            confirmation_args = {
                'job_type': result.get('job_type'),
                'family': result.get('family'),
                'tier': result.get('tier'),
                'fingerprint': result.get('fingerprint'),
                'quoted_rtm': str(result.get('rtm_cost')),
                'confirm': True,
            }
            view = Confirmation(self._send, self.service, ctx, 'pvp_v2_start_job', confirmation_args)
            await self._send_embed(ctx, 'dev', embed_content, view=view)

        elif method == 'pvp_v2_start_job':
            resolves_at = result.get('resolves_at')
            ts = int(resolves_at.replace(tzinfo=timezone.utc).timestamp()) if isinstance(resolves_at, datetime) else 0
            quote = result.get('quote', {})
            fp_str = f" · Empreinte : `{quote.get('fingerprint')}`" if quote.get('fingerprint') else ""
            content = text.get(
                ctx,
                'g_pvp_v2_job_started',
                e_log=e['logiciels'],
                e_con=e['connexions'],
                e_mem=e['memoire'],
                e_tmp=e['temps'],
                job_type_label=quote.get('job_type'),
                family=quote.get('family'),
                tier=quote.get('tier'),
                fp_str=fp_str,
                channel_label=quote.get('channel'),
                rtm_cost=f"{Decimal(str(quote.get('rtm_cost', 0))):,.5f}",
                timestamp=ts,
            )
            kwargs = {'content': content, 'allowed_mentions': discord.AllowedMentions.none()}
            if getattr(ctx, 'interaction', None):
                await ctx.respond(**kwargs)
            else:
                await ctx.send(**kwargs)

        elif method == 'pvp_v2_cancel_job':
            content = text.get(
                ctx,
                'g_pvp_v2_job_cancelled',
                e_alt=e['alerte'],
                channel_label=result.get('channel'),
            )
            kwargs = {'content': content, 'allowed_mentions': discord.AllowedMentions.none()}
            if getattr(ctx, 'interaction', None):
                await ctx.respond(**kwargs)
            else:
                await ctx.send(**kwargs)

        elif method == 'pvp_v2_install_patch':
            content = text.get(
                ctx,
                'g_pvp_v2_patch_installed',
                e_fw=e['firewall'],
                family=result.get('family', 'patch'),
                fingerprint=result.get('fingerprint', '????'),
            )
            kwargs = {'content': content, 'allowed_mentions': discord.AllowedMentions.none()}
            if getattr(ctx, 'interaction', None):
                await ctx.respond(**kwargs)
            else:
                await ctx.send(**kwargs)

        elif method == 'pvp_v2_library':
            lines = [f"{text.get(ctx, 'g_pvp_v2_library_title', e_mem=e['memoire'])}\n"]

            # 1. Jobs actifs
            active_jobs = result.get('active_jobs', [])
            lines.append(text.get(ctx, 'g_pvp_v2_library_active_jobs', e_tmp=e['temps']))
            if not active_jobs:
                lines.append(text.get(ctx, 'g_pvp_v2_library_no_active_jobs'))
            else:
                for j in active_jobs:
                    res_at = j.get('resolves_at')
                    ts = int(res_at.replace(tzinfo=timezone.utc).timestamp()) if isinstance(res_at, datetime) else 0
                    fp_part = f" (`{j.get('fingerprint')}`)" if j.get('fingerprint') else ""
                    lines.append(f"> • **[{j['channel'].upper()}]** `{j['job_type']}` · {j['family']} T{j['tier']}{fp_part} — {e['temps']} fin <t:{ts}:R>")

            # 2. Dossiers de recherche
            folders = result.get('research_folders', [])
            lines.append(f"\n{text.get(ctx, 'g_pvp_v2_library_folders', e_ops=e['operations'])}")
            if not folders:
                lines.append(text.get(ctx, 'g_pvp_v2_library_no_folders'))
            else:
                for f in folders:
                    lines.append(f"> • {e['operations']} **{f['family']}** T{f['tier']} · Empreinte : `{f['fingerprint']}` ({f['channel']})")

            # 3. Logiciels compilés
            copies = result.get('software_copies', [])
            lines.append(f"\n{text.get(ctx, 'g_pvp_v2_library_copies', e_log=e['logiciels'])}")
            if not copies:
                lines.append(text.get(ctx, 'g_pvp_v2_library_no_copies'))
            else:
                for c in copies:
                    resell = "✅ Revente" if c.get('resellable') else "❌ Non revendable"
                    lines.append(f"> • {e['logiciels']} **{c['family']}** T{c['tier']} · Empreinte : `{c['fingerprint']}` [{c.get('origin', 'compiled')}] ({resell})")

            # 4. Patches
            patches = result.get('patches', [])
            lines.append(f"\n{text.get(ctx, 'g_pvp_v2_library_patches', e_fw=e['firewall'])}")
            if not patches:
                lines.append(text.get(ctx, 'g_pvp_v2_library_no_patches'))
            else:
                for p in patches:
                    st = f"{e['firewall']} **Installé**" if p.get('installed') else "📦 *Non installé*"
                    lines.append(f"> • {e['firewall']} **{p['family']}** · Empreinte : `{p['fingerprint']}` — {st}")

            content = "\n".join(lines)
            await self._send_embed(ctx, 'library', content)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Compile(bot))
