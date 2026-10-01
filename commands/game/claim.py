"""Commande /claim et !claim — Récolte du Rootium miné, autoclaim et vidage de la mémoire vive.

Ce module matérialise le cœur de la boucle de minage passif de Root :
- Les modules de minage produisent en continu du Rootium selon leur puissance de hachage (H/s).
- Chaque Rootium produit occupe de la mémoire vive (RAM) ; la capacité totale de RAM installée
  détermine combien de temps le réseau peut miner avant saturation.
- `/claim` extrait le Rootium accumulé, le crédite sur le solde du joueur, puis vide la mémoire
  (retour à 100 % de mémoire disponible) afin de relancer le cycle de minage.
- Mode Autoclaim : le joueur peut utiliser des crédits d'autoclaim (!claim auto <nb|all>) pour
  déclencher automatiquement les récoltes dès que la mémoire vive atteint 99,9 %.
"""

from decimal import Decimal
import logging

import discord
from discord.ext import commands, tasks

import data
from commands.game.commandgame import BaseGameCog
from game.db.players import Player
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.logger import Logger
from utils.time_format import format_duration

logger = logging.getLogger(__name__)

# Adresse lore-friendly du pool de minage source des récompenses de Rootium
MINING_POOL_ADDRESS = "0xROOTIUM_MINING_POOL"


class Claim(BaseGameCog):
    """Cog gérant la récolte du Rootium miné, l'autoclaim et la libération de la mémoire vive."""

    def __init__(self, bot):
        self.bot = bot
        self.check_autoclaims_loop.start()

    def cog_unload(self):
        """Arrête la tâche d'arrière-plan au déchargement du Cog."""
        self.check_autoclaims_loop.cancel()

    @tasks.loop(seconds=20)
    async def check_autoclaims_loop(self):
        """Boucle de détection et exécution des claims automatiques programmés (seuil 99,9 % de RAM)."""
        try:
            delivered = await self.bot.root_service.process_due_autoclaims()
            if delivered:
                logger.info("%d autoclaim(s) déclenché(s)", len(delivered))
                for item in delivered:
                    await self._notify_and_log_autoclaim(item)
        except Exception:
            logger.exception("Erreur lors de la vérification des autoclaims")

    @check_autoclaims_loop.before_loop
    async def before_check_autoclaims_loop(self):
        """Attend la synchronisation complète du bot avant de démarrer la boucle."""
        await self.bot.wait_until_ready()

    async def _notify_and_log_autoclaim(self, item: dict):
        """Envoie un MP au joueur et consigne les logs blockchain et modération."""
        actor_id = item.get('actor')
        amount = Decimal(str(item.get('amount', 0)))
        bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)

        # 1. Notification MP au joueur
        try:
            user = self.bot.get_user(actor_id)
            if not user:
                user = await self.bot.fetch_user(actor_id)
            if user:
                lang = await self.bot.root_service.database.run(
                    lambda tx: Player.get_language(tx, actor_id),
                    readonly=True,
                ) or 'fr'

                rate_str = text.format_rtm(item.get('rate_per_min', 0))
                ram_total = item.get('total_ram_formatted', '0 o')
                rep_pts = int(item.get('reputation_points', 0) or 0)
                rep_bonus_pct = Decimal(str(rep_pts)) * Decimal('0.5')
                rep_label = "réputation" if lang == 'fr' else "reputation"
                rep_bonus_note = f" *(+{rep_bonus_pct:.1f}% {rep_label})*" if rep_pts > 0 else ""

                content = text.get_for_lang(
                    lang,
                    'g_claim_auto_dm',
                    amount=text.format_rtm(amount),
                    rtm_total=text.format_rtm(item.get('new_rootium', 0)),
                    ram_total=ram_total,
                    rate=rate_str,
                    rep_bonus_note=rep_bonus_note,
                    remaining_active=item.get('autoclaim_active_remaining', 0),
                    remaining_credits=item.get('autoclaim_credits_remaining', 0),
                )
                from utils.root_embed import RootEmbed
                embed = RootEmbed.notification(lang, "Autoclaim", content)
                await user.send(embed=embed)
                logger.info("Notification MP d'autoclaim envoyée à %s", actor_id)
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("Impossible d'envoyer le MP d'autoclaim à %s (MP bloqués/fermés) : %s", actor_id, exc)
        except Exception:
            logger.exception("Erreur inattendue lors de l'envoi du MP d'autoclaim à %s", actor_id)

        # 2. Log Blockchain
        try:
            await bot_logger.log_blockchain_transaction(
                from_id=MINING_POOL_ADDRESS,
                to_address=str(actor_id),
                rtm_amount=amount,
            )
        except Exception:
            pass

        # 3. Log Modération (embed spécifique)
        try:
            user_obj = self.bot.get_user(actor_id)
            if not user_obj:
                try:
                    user_obj = await self.bot.fetch_user(actor_id)
                except Exception:
                    user_obj = None

            await bot_logger.log_claim(
                user_obj or actor_id,
                amount,
                new_rootium=item.get('new_rootium'),
                rate=item.get('rate_per_min'),
                ram_total=item.get('total_ram_formatted'),
                seconds_since_last_claim=item.get('seconds_since_last_claim'),
                is_auto=True,
                remaining_active=item.get('autoclaim_active_remaining'),
            )
        except Exception:
            pass

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='claim',
        description=EN['claim'],
        description_localizations={"fr": FR['claim']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def claim(
        self,
        ctx,
        auto: discord.Option(
            str,
            description="Activer l'autoclaim (ex: 'all' ou nombre) ou 'cancel'",
            required=False,
            default=None,
        ) = None,
    ):
        """Commande Slash /claim."""
        if auto:
            val = auto.strip().lower()
            if val in ('cancel', 'stop', 'off', 'annuler'):
                await self._invoke(ctx, 'claim_cancel')
            else:
                await self._invoke(ctx, 'claim_auto', count=auto.strip())
        else:
            await self._invoke(ctx, 'claim')

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='claim', aliases=['c', 'cl'], help=FR['claim'])
    async def prefix_claim(self, ctx, *args):
        """Commande préfixe !claim (aliases !c, !cl)."""
        if args:
            sub = args[0].strip().lower()
            if sub in ('cancel', 'stop', 'off', 'annuler'):
                await self._invoke(ctx, 'claim_cancel')
                return
            elif sub in ('auto', 'a'):
                count = args[1].strip() if len(args) > 1 else 'all'
                if count.lower() in ('cancel', 'stop', 'off', 'annuler'):
                    await self._invoke(ctx, 'claim_cancel')
                else:
                    await self._invoke(ctx, 'claim_auto', count=count)
                return
        await self._invoke(ctx, 'claim')

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Affiche le résultat de la récolte et journalise la transaction blockchain si crédit effectif."""
        prefix = '/' if getattr(ctx, 'interaction', None) else (getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!'))

        if method == 'claim_cancel':
            refunded = result.get('refunded_count', 0)
            credits_total = result.get('autoclaim_credits', 0)
            content = text.get(ctx, 'g_claim_auto_cancelled', refunded_count=refunded, autoclaim_credits=credits_total)
            await self._reply(ctx, content)
            return

        if method == 'claim_auto':
            claim_res = result.get('claim_result', {})
            amount = Decimal(str(claim_res.get('amount', 0)))
            new_rtm = text.format_rtm(claim_res.get('new_rootium', 0))
            ram_total = claim_res.get('total_ram_formatted', '0 o')
            activated = result.get('activated_count', 0)
            rem_credits = result.get('autoclaim_credits_remaining', 0)
            active_queue = result.get('autoclaim_active', 0)

            content = text.get(
                ctx, 'g_claim_auto_started',
                activated_count=activated,
                amount=text.format_rtm(amount),
                rtm_total=new_rtm,
                ram_total=ram_total,
                credits_remaining=rem_credits,
                active_count=active_queue,
            )
            await self._reply(ctx, content)
            if claim_res.get('claimed'):
                await self._log_blockchain(ctx, amount)
                await self._log_moderation(ctx, amount, claim_res)
            return

        # Méthode claim standard
        rate_str = text.format_rtm(result.get('rate_per_min', 0))
        ram_total = result.get('total_ram_formatted', '0 o')

        rep_pts = int(result.get('reputation_points', 0) or 0)
        rep_bonus_pct = Decimal(str(rep_pts)) * Decimal('0.5')
        is_fr = (text.get_locale(ctx) == 'fr')
        rep_label = "réputation" if is_fr else "reputation"
        rep_bonus_note = f" *(+{rep_bonus_pct:.1f}% {rep_label})*" if rep_pts > 0 else ""

        autoclaim_credits = int(result.get('autoclaim_credits', 0) or 0)
        if autoclaim_credits > 0:
            credits_hint = text.get(ctx, 'g_claim_credits_hint', autoclaim_credits=autoclaim_credits, prefix=prefix)
        else:
            credits_hint = ""

        if result.get('claimed'):
            amount = Decimal(str(result.get('amount', 0)))
            rmd_hint = ""
            if result.get('reminder_rescheduled'):
                sec_to_fill = result.get('seconds_to_fill_total') or result.get('seconds_to_full', 0)
                time_to_full = format_duration(sec_to_fill)
                rmd_hint = text.get(ctx, 'g_claim_rmd_rescheduled_hint', time_to_full=time_to_full)

            content = text.get(
                ctx, 'g_claim_success',
                amount=text.format_rtm(amount),
                rtm_total=text.format_rtm(result.get('new_rootium', 0)),
                ram_total=ram_total,
                rate=rate_str,
                rep_bonus_note=rep_bonus_note,
                credits_hint=credits_hint,
                rmd_hint=rmd_hint,
            )
            await self._reply(ctx, content)
            await self._log_blockchain(ctx, amount)
            await self._log_moderation(ctx, amount, result)
            return

        reason = result.get('reason')
        if reason == 'no_miner':
            content = text.get(ctx, 'g_claim_no_miner', prefix=prefix)
        else:
            time_to_full = format_duration(result.get('seconds_to_full', 0))
            content = text.get(
                ctx, 'g_claim_empty',
                rate=rate_str,
                ram_total=ram_total,
                time_to_full=time_to_full,
                rep_bonus_note=rep_bonus_note,
                credits_hint=credits_hint,
            )
        await self._reply(ctx, content)

    async def _reply(self, ctx, content: str):
        """Envoie une réponse simple sous forme de message direct sans embed."""
        interaction = getattr(ctx, 'interaction', None)
        if interaction:
            if interaction.response.is_done():
                await interaction.followup.send(content, allowed_mentions=discord.AllowedMentions.none())
            else:
                await interaction.response.send_message(content, allowed_mentions=discord.AllowedMentions.none())
        else:
            await ctx.send(content, allowed_mentions=discord.AllowedMentions.none())


    async def _log_blockchain(self, ctx, amount: Decimal):
        """Publie la récolte de minage dans le salon #blockchain (best-effort, sans casser la commande)."""
        bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)
        author = getattr(ctx, 'user', None) or getattr(ctx, 'author', None)
        author_id = str(author.id) if author else ""
        try:
            await bot_logger.log_blockchain_transaction(
                from_id=MINING_POOL_ADDRESS,
                to_address=author_id,
                rtm_amount=amount,
            )
        except Exception:
            pass

    async def _log_moderation(self, ctx, amount: Decimal, result: dict):
        """Consigne la récolte dans le salon de modération dédié (best-effort, sans casser la commande)."""
        bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)
        try:
            log_kwargs = {
                'new_rootium': result.get('new_rootium'),
                'rate': result.get('rate_per_min'),
                'ram_total': result.get('total_ram_formatted'),
                'seconds_since_last_claim': result.get('seconds_since_last_claim'),
            }
            if result.get('is_auto'):
                log_kwargs['is_auto'] = True
            await bot_logger.log_claim(ctx, amount, **log_kwargs)
        except Exception:
            pass


async def log_claim_events(bot, ctx, amount: Decimal, result: dict):
    """Publie la récolte de minage dans #blockchain et dans le salon de modération (best-effort)."""
    bot_logger = getattr(bot, 'discord_logger', None) or Logger(bot)
    author = getattr(ctx, 'user', None) or getattr(ctx, 'author', None)
    author_id = str(author.id) if author else ""
    try:
        await bot_logger.log_blockchain_transaction(
            from_id=MINING_POOL_ADDRESS,
            to_address=author_id,
            rtm_amount=amount,
        )
    except Exception:
        pass

    try:
        log_kwargs = {
            'new_rootium': result.get('new_rootium'),
            'rate': result.get('rate_per_min'),
            'ram_total': result.get('total_ram_formatted'),
            'seconds_since_last_claim': result.get('seconds_since_last_claim'),
        }
        if result.get('is_auto'):
            log_kwargs['is_auto'] = True
        await bot_logger.log_claim(ctx, amount, **log_kwargs)
    except Exception:
        pass


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Claim(bot))
