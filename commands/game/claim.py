"""Commande /claim et !claim — Récolte du Rootium miné et vidage de la mémoire vive.

Ce module matérialise le cœur de la boucle de minage passif de Root :
- Les modules de minage produisent en continu du Rootium selon leur puissance de hachage (H/s).
- Chaque Rootium produit occupe de la mémoire vive (RAM) ; la capacité totale de RAM installée
  détermine combien de temps le réseau peut miner avant saturation.
- `/claim` extrait le Rootium accumulé, le crédite sur le solde du joueur, puis vide la mémoire
  (retour à 100 % de mémoire disponible) afin de relancer le cycle de minage.

Plus le réseau dispose de mémoire vive, moins il faut réclamer souvent ; plus la puissance de
minage est élevée, plus le rendement en Rootium par minute est important.

Chaque récolte réussie est publiée dans le journal #blockchain sous forme de transaction Rootium.
"""

from decimal import Decimal

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.logger import Logger
from utils.time_format import format_duration


# Adresse lore-friendly du pool de minage source des récompenses de Rootium
MINING_POOL_ADDRESS = "0xROOTIUM_MINING_POOL"


class Claim(BaseGameCog):
    """Cog gérant la récolte du Rootium miné et la libération de la mémoire vive."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='claim',
        description=EN['claim'],
        description_localizations={"fr": FR['claim']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def claim(self, ctx):
        """Commande Slash /claim."""
        await self._invoke(ctx, 'claim')

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='claim', aliases=['cl'], help=FR['claim'])
    async def prefix_claim(self, ctx):
        """Commande préfixe !claim (alias !cl)."""
        await self._invoke(ctx, 'claim')

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Affiche le résultat de la récolte et journalise la transaction blockchain si crédit effectif."""
        prefix = '/' if getattr(ctx, 'interaction', None) else (getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!'))
        rate_str = text.format_rtm(result.get('rate_per_min', 0))
        ram_total = result.get('total_ram_formatted', '0 o')

        rep_pts = int(result.get('reputation_points', 0) or 0)
        rep_bonus_pct = Decimal(str(rep_pts)) * Decimal('0.5')
        is_fr = (text.get_locale(ctx) == 'fr')
        rep_label = "réputation" if is_fr else "reputation"
        rep_bonus_note = f" *(+{rep_bonus_pct:.1f}% {rep_label})*" if rep_pts > 0 else ""

        if result.get('claimed'):
            amount = Decimal(str(result.get('amount', 0)))
            content = text.get(
                ctx, 'g_claim_success',
                amount=text.format_rtm(amount),
                rtm_total=text.format_rtm(result.get('new_rootium', 0)),
                ram_total=ram_total,
                rate=rate_str,
                rep_bonus_note=rep_bonus_note,
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
            )
        await self._reply(ctx, content)

    async def _reply(self, ctx, content: str):
        """Envoie une réponse en texte brut (hors Embed) selon le contexte Slash ou préfixe."""
        kwargs = {'content': content, 'allowed_mentions': discord.AllowedMentions.none()}
        if getattr(ctx, 'interaction', None):
            await ctx.respond(**kwargs)
        else:
            await ctx.send(**kwargs)

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
            await bot_logger.log_claim(
                ctx, amount,
                new_rootium=result.get('new_rootium'),
                rate=result.get('rate_per_min'),
                ram_total=result.get('total_ram_formatted'),
                seconds_since_last_claim=result.get('seconds_since_last_claim'),
            )
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
        await bot_logger.log_claim(
            ctx, amount,
            new_rootium=result.get('new_rootium'),
            rate=result.get('rate_per_min'),
            ram_total=result.get('total_ram_formatted'),
            seconds_since_last_claim=result.get('seconds_since_last_claim'),
        )
    except Exception:
        pass


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Claim(bot))
