"""Commande /convert et !convert — Vente de Rootium contre des dollars au taux fixe.

Direction unique pour l'instant : RTM → USD.
Le joueur cède des tokens Rootium ; le DEX crédite des dollars.
Chaque vente confirmée est inscrite dans le journal #blockchain (TYPE SELL TOKEN).
"""

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.confirmation import Confirmation
from utils.logger import Logger


DEX_ADDRESS = "0xROOTIUM_DEX"


def _is_confirm(val):
    """Détermine si un argument représente une confirmation explicite."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('confirm', 'true', 'yes', 'valider')
    return False


def _is_all(token: str | None) -> bool:
    """Vrai si le joueur demande la vente de tout son solde RTM."""
    if token is None:
        return False
    return str(token).strip().lower().replace(',', '.') in ('all', 'tout', 'max')


class Convert(BaseGameCog):
    """Cog gérant la conversion RTM → USD (vente de tokens)."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='convert',
        description=EN['convert'],
        description_localizations={"fr": FR['convert']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def convert(
        self,
        ctx,
        amount: discord.Option(
            str,
            description=desc['convert_amount'],
            description_localizations=desc_loc['convert_amount'],
        ),
        confirm: discord.Option(
            str, choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False, default=None,
        ) = None,
    ):
        """Commande Slash /convert <amount>."""
        await self._invoke(
            ctx, 'convert',
            amount=amount,
            all=_is_all(amount),
            confirm=_is_confirm(confirm),
        )

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='convert', aliases=['cv'], help=FR['convert'])
    async def prefix_convert(self, ctx, amount: str = None, *args):
        """Commande préfixe !convert <montant|all> [confirm]."""
        await self._prefix_sell_or_convert(ctx, amount, *args)

    @commands.group(name='sell', invoke_without_command=True, help=FR['convert'])
    async def prefix_sell(self, ctx, amount: str = None, *args):
        """Commande préfixe !sell <montant> — vente RTM → USD."""
        await self._prefix_sell_or_convert(ctx, amount, *args)

    @prefix_sell.command(name='all')
    async def prefix_sell_all(self, ctx, *args):
        """Commande préfixe !sell all — vend tout le solde Rootium."""
        confirm = any(_is_confirm(a) for a in args)
        await self._invoke(ctx, 'convert', amount='all', all=True, confirm=confirm)

    async def _prefix_sell_or_convert(self, ctx, amount: str = None, *args):
        """Parse le montant (ou all) pour !convert / !sell."""
        if not amount:
            await self._prefetch_lang(ctx.author.id)
            prefix = getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')
            return await ctx.send(text.get(ctx, 'g_error_convert_usage', prefix=prefix))

        confirm = any(_is_confirm(a) for a in (amount, *args))
        await self._invoke(
            ctx, 'convert',
            amount=amount,
            all=_is_all(amount),
            confirm=confirm,
        )

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Affiche le devis interactif ou le reçu de vente, puis journalise la blockchain."""
        rtm = text.format_rtm(result.get('rtm_amount', 0))
        usd = text.format_usd(result.get('usd_amount', 0))
        rate = text.format_usd(result.get('rate', 0))

        if result.get('convert_quote'):
            cur_rtm = text.format_rtm(result.get('current_rootium', 0))
            rem_rtm = text.format_rtm(result.get('new_rootium', 0))
            cur_usd = text.format_usd(result.get('current_dollars', 0))
            rem_usd = text.format_usd(result.get('new_dollars', 0))
            content = text.get(
                ctx, 'g_convert_quote',
                rtm=rtm, usd=usd, rate=rate,
                cur_rtm=cur_rtm, rem_rtm=rem_rtm,
                cur_usd=cur_usd, rem_usd=rem_usd,
            )
            view = Confirmation(
                self._send, self.service, ctx, 'convert',
                {
                    'amount': str(result.get('rtm_amount')),
                    'all': False,
                    'rate': str(result.get('rate')),
                    'confirm': True,
                },
            )
            await self._send_embed(ctx, 'convert', content, view=view)
            return

        content = text.get(
            ctx, 'g_convert_success',
            rtm=rtm,
            usd=usd,
            rate=rate,
            usd_total=text.format_usd(result.get('new_dollars', 0)),
            rtm_total=text.format_rtm(result.get('new_rootium', 0)),
        )
        kwargs = {'content': content, 'allowed_mentions': discord.AllowedMentions.none()}
        if getattr(ctx, 'interaction', None):
            await ctx.respond(**kwargs)
        else:
            await ctx.send(**kwargs)

        await self._log_blockchain(ctx, result)

    async def _log_blockchain(self, ctx, result: dict):
        """Inscrit la vente de tokens dans #blockchain (best-effort)."""
        bot_logger = getattr(self.bot, 'discord_logger', None) or Logger(self.bot)
        try:
            await bot_logger.log_blockchain_transaction(
                from_id=ctx.author.id,
                to_address=DEX_ADDRESS,
                rtm_amount=result.get('rtm_amount', 0),
                tx_type='SELL TOKEN',
                usd_amount=result.get('usd_amount'),
            )
        except Exception:
            pass


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Convert(bot))
