"""Commande /compile et !compile (alias !cp) — production d'ATK via les modules d'attaque.

Les modules d'attaque fournissent du Bit/s. /compile produit un nombre d'ATK choisi
(humains non qualifiés, qualifiés ou IA) ; le coût RTM et la durée en découlent.
Le paiement est journalisé dans #blockchain.
"""

import asyncio
import logging
from decimal import Decimal

import discord
from discord.ext import commands, tasks

import data
from commands.game.commandgame import BaseGameCog
from game.db.players import Player
from game.math_config import MathConfig
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.confirmation import Confirmation
from utils.logger import Logger
from utils.root_embed import RootEmbed


logger = logging.getLogger(__name__)

COMPILE_ADDRESSES = {
    'unskilled': '0xROOT_UNSKILLED_LABOR',
    'skilled': '0xROOT_SKILLED_OPERATORS',
    'ai': '0xROOT_AI_CLUSTER',
}


def _compile_check_interval() -> int:
    """Intervalle de la boucle de livraison, lu depuis data/math.json."""
    return int(MathConfig.load().get('compile', {}).get('check_interval_seconds', 30))


def _is_confirm(val):
    """Détermine si un argument représente une confirmation explicite."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('confirm', 'true', 'yes', 'valider')
    return False


def _is_all(token) -> bool:
    """Vrai si le joueur produit autant d'ATK que son débit Bit/s."""
    if token is None:
        return False
    return str(token).strip().lower().replace(',', '.') in ('all', 'tout', 'max')


class Compile(BaseGameCog):
    """Cog gérant la production d'ATK (/compile) et la livraison différée des jobs `hack`."""

    def __init__(self, bot):
        self.bot = bot
        self.check_hacks_loop.change_interval(seconds=_compile_check_interval())
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self.check_hacks_loop.start()

    def cog_unload(self):
        """Arrête proprement la tâche périodique au déchargement du Cog."""
        self.check_hacks_loop.cancel()

    @tasks.loop(seconds=_compile_check_interval())
    async def check_hacks_loop(self):
        """Livre les productions d'ATK arrivées à échéance."""
        try:
            delivered = await self.service.deliver_expired_hacks()
            if delivered:
                logger.info("%d production(s) d'ATK livrée(s)", len(delivered))
                for item in delivered:
                    await self._notify_delivered(item)
        except Exception:
            logger.exception("Erreur lors de la livraison des productions d'ATK")

    @check_hacks_loop.before_loop
    async def before_check_hacks_loop(self):
        """Attend que le bot soit prêt, puis rattrape immédiatement les jobs échus."""
        await self.bot.wait_until_ready()
        try:
            delivered = await self.service.deliver_expired_hacks()
            for item in delivered or []:
                await self._notify_delivered(item)
        except Exception:
            logger.exception("Erreur lors du rattrapage des productions d'ATK")

    async def _notify_delivered(self, item: dict):
        """Envoie un MP au joueur lorsque ses ATK sont crédités.

        L'ATK est déjà crédité en base à ce stade : la ligne `hack` a été
        supprimée dans la transaction de livraison. On réessaie donc les échecs
        transitoires (rate-limit / cache froid juste après le démarrage) afin de
        ne pas perdre définitivement la notification. Un `Forbidden` (MP fermés
        côté joueur) est en revanche irrécupérable et n'est pas rejoué.
        """
        discord_id = item['discord_id']
        atk = int(item.get('atk_yield') or 0)
        attempts = int(MathConfig.load().get('compile', {}).get('dm_retry_attempts', 3))
        for attempt in range(1, max(1, attempts) + 1):
            try:
                user = self.bot.get_user(discord_id)
                if not user:
                    user = await self.bot.fetch_user(discord_id)
                if not user:
                    logger.warning("MP de compile ignoré : joueur %s introuvable", discord_id)
                    return
                lang = await self.service.database.run(
                    lambda tx: Player.get_language(tx, discord_id),
                    readonly=True,
                ) or 'fr'
                content = text.get_for_lang(lang, 'g_compile_delivered_dm', atk=atk)
                dm_title = "Compilation terminée" if lang == 'fr' else "Compilation Complete"
                embed = RootEmbed.notification(lang, dm_title, content)
                await embed.send_to(user)
                return
            except discord.Forbidden as exc:
                # MP fermés / bot bloqué : inutile de réessayer.
                logger.warning("MP de compile refusé par %s (MP fermés) : %s", discord_id, exc)
                return
            except discord.HTTPException as exc:
                if attempt >= max(1, attempts):
                    logger.error(
                        "Échec définitif du MP de compile à %s après %d tentative(s) : %s",
                        discord_id, attempt, exc,
                    )
                    return
                delay = 2 ** (attempt - 1)
                logger.warning(
                    "MP de compile à %s en échec (tentative %d/%d), nouvel essai dans %ds : %s",
                    discord_id, attempt, attempts, delay, exc,
                )
                await asyncio.sleep(delay)
            except Exception:
                logger.exception("Erreur inattendue lors de la notification compile à %s", discord_id)
                return

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='compile',
        description=EN['compile'],
        description_localizations={"fr": FR['compile']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def compile(
        self,
        ctx,
        method: discord.Option(
            str,
            choices=['unskilled', 'skilled', 'ai'],
            description=desc['compile_method'],
            description_localizations=desc_loc['compile_method'],
        ),
        atk: discord.Option(
            str,
            description=desc['compile_atk'],
            description_localizations=desc_loc['compile_atk'],
            required=False,
            default='all',
        ) = 'all',
        confirm: discord.Option(
            str, choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False, default=None,
        ) = None,
    ):
        """Commande Slash /compile <method> [atk|all]."""
        await self._invoke(
            ctx, 'compile',
            mode=method,
            atk=atk,
            all=_is_all(atk),
            confirm=_is_confirm(confirm),
        )

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='compile', aliases=['cp'], help=FR['compile'])
    async def prefix_compile(self, ctx, method: str = None, atk: str = None, *args):
        """Commande préfixe !compile <method> [atk|all] [confirm]."""
        await self._prefetch_lang(ctx.author.id)
        prefix = getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')
        resolved = MathConfig.normalize_compile_method(method)
        if resolved is None:
            return await ctx.send(text.get(ctx, 'g_error_compile_usage', prefix=prefix))

        tokens = list(args)
        if atk is not None and _is_confirm(atk):
            tokens.append(atk)
            atk = 'all'
        confirm = any(_is_confirm(a) for a in tokens)
        if atk is None:
            atk = 'all'
        await self._invoke(
            ctx, 'compile',
            mode=resolved,
            atk=atk,
            all=_is_all(atk),
            confirm=confirm,
        )

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Affiche le devis interactif ou le lancement de la production d'ATK."""
        rtm = f"{Decimal(str(result.get('rtm_paid', 0))):,.5f}"
        method_key = result.get('method', 'unskilled')
        method_label = text.get(ctx, f'g_compile_method_{method_key}')
        atk = int(result.get('atk_yield') or 0)
        bits = result.get('bits_formatted') or ''

        if result.get('compile_quote'):
            content = text.get(
                ctx, 'g_compile_quote',
                method=method_label,
                bits=bits,
                atk=atk,
                rtm=rtm,
                duration=result.get('duration', ''),
            )
            confirmation_args = {
                'mode': method_key,
                'atk': atk,
                'all': False,
                'confirm': True,
                'quoted_rtm': str(result.get('rtm_paid')),
                'quoted_atk': atk,
                'quoted_duration': int(result.get('duration_seconds') or 0),
            }
            view = Confirmation(self._send, self.service, ctx, 'compile', confirmation_args)
            await self._send_embed(ctx, 'compile', content, view=view)
            return

        content = text.get(
            ctx, 'g_compile_started',
            method=method_label,
            atk=atk,
            rtm=rtm,
            timestamp=result.get('timestamp', 0),
        )
        await self._send_embed(ctx, 'compile', content)
        await self._log_blockchain(ctx, method_key, result.get('rtm_paid'))

    async def _log_blockchain(self, ctx, method_key: str, rtm_paid):
        """Journalise le paiement RTM vers le cluster (IA / opérateurs)."""
        rtm_val = Decimal(str(rtm_paid or 0))
        if rtm_val <= 0:
            return
        to_address = COMPILE_ADDRESSES.get(method_key)
        if not to_address:
            return
        bot_logger = getattr(self.bot, 'discord_logger', None)
        if not bot_logger:
            bot_logger = Logger(self.bot)
        try:
            await bot_logger.log_blockchain_transaction(
                from_id=ctx.author.id,
                to_address=to_address,
                rtm_amount=rtm_val,
            )
        except Exception:
            pass


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Compile(bot))
