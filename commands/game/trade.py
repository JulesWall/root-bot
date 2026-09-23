"""
Commande /trade et !trade — Échange de ressources entre joueurs (trade.md).

Ressources échangeables : Dollars (USD) et Rootium (RTM).
Syntaxe extensible (+ / -) :
- `+<montant><ressource>` : ce que l'initiateur donne / envoie.
- `-<montant><ressource>` : ce que l'initiateur demande / reçoit.

Exemples :
  !trade @Joueur +50usd -1rtm
  !trade @Joueur +100usd
  !trade @Joueur -2.5rtm
  /trade target:@Joueur offer:+50usd request:-1rtm
"""

import re
from decimal import Decimal, InvalidOperation

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.check import Check
from utils.trade_view import TradeView

# Regex pour parser les jetons signés (+/-), avec espaces éventuels entre le signe, le montant et l'unité
# Ex: '+50usd', '+ 50 usd', '-1.25rtm', '+100$', '-2' (par défaut USD si non précisé)
TOKEN_REGEX = re.compile(
    r'([+\-])\s*([0-9]+(?:[\.,][0-9]+)?)\s*([a-zA-Z$]*)',
    re.IGNORECASE
)


def parse_trade_tokens(raw_tokens: list[str] | str) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    Parse les jetons de ressources avec préfixes + et -.
    
    Retourne :
        tuple[Decimal, Decimal, Decimal, Decimal]:
            (send_usd, send_rtm, receive_usd, receive_rtm)
    """
    if isinstance(raw_tokens, list):
        text_str = " ".join(raw_tokens)
    else:
        text_str = str(raw_tokens or "")

    text_str = text_str.strip()
    if not text_str:
        return Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0')

    matches = TOKEN_REGEX.findall(text_str)
    if not matches:
        raise ValueError("No valid tokens found")

    send_usd = Decimal('0')
    send_rtm = Decimal('0')
    receive_usd = Decimal('0')
    receive_rtm = Decimal('0')

    # Vérifie également qu'aucun déchet non analysé ne traîne
    # Reconstitue une chaîne sans les matches pour vérifier s'il reste des caractères suspects
    cleaned = TOKEN_REGEX.sub('', text_str).strip()
    # On tolère les virgules ou points-virgules de séparation
    cleaned = re.sub(r'[,;\s]+', '', cleaned)
    if cleaned:
        raise ValueError(f"Unexpected trailing text: {cleaned}")

    for sign, num_str, currency in matches:
        num_str = num_str.replace(',', '.')
        try:
            val = Decimal(num_str)
        except InvalidOperation:
            raise ValueError(f"Invalid number: {num_str}")

        if val < 0:
            raise ValueError("Negative numbers not allowed in amount")

        curr = currency.lower().strip()
        if curr in ('usd', 'dollar', 'dollars', '$', ''):
            # Limite 2 décimales pour l'USD
            if val.as_tuple().exponent < -2:
                raise ValueError("Too many decimals for USD (max 2)")
            if sign == '-':
                send_usd += val
            else:
                receive_usd += val
        elif curr in ('rtm', 'rootium'):
            # Limite 5 décimales pour le Rootium
            if val.as_tuple().exponent < -5:
                raise ValueError("Too many decimals for RTM (max 5)")
            if sign == '-':
                send_rtm += val
            else:
                receive_rtm += val
        else:
            raise ValueError(f"Unknown currency: {currency}")

    return send_usd, send_rtm, receive_usd, receive_rtm


class Trade(BaseGameCog):
    """Cog gérant le système d'échange de ressources entre joueurs."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='trade',
        description=EN['trade'],
        description_localizations={"fr": FR['trade']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def trade(
        self,
        ctx,
        target: discord.Option(
            discord.Member,
            description=desc['trade_target'],
            description_localizations=desc_loc['trade_target'],
            required=True,
        ),
        offer: discord.Option(
            str,
            description=desc['trade_offer'],
            description_localizations=desc_loc['trade_offer'],
            required=False,
            default="",
        ) = "",
        request: discord.Option(
            str,
            description=desc['trade_request'],
            description_localizations=desc_loc['trade_request'],
            required=False,
            default="",
        ) = "",
    ):
        """Commande Slash /trade."""
        await self._prefetch_lang(ctx.author.id)

        # Concatène offer (- envoyé) et request (+ reçu) pour le parsing par jetons
        tokens = []
        if offer:
            for part in offer.split():
                if not part.startswith(('+', '-')):
                    part = '-' + part
                tokens.append(part)
        if request:
            for part in request.split():
                if not part.startswith(('+', '-')):
                    part = '+' + part
                tokens.append(part)

        raw_input = " ".join(tokens)
        await self._start_trade(ctx, target=target, raw_input=raw_input)

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='trade', help=FR['trade'])
    async def prefix_trade(self, ctx, target_arg: str = None, *resource_args):
        """Commande préfixe !trade <@cible> <+ressources> <-ressources>."""
        await self._prefetch_lang(ctx.author.id)

        if not target_arg or not resource_args:
            prefix = getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')
            return await ctx.send(text.get(ctx, 'g_error_trade_usage', prefix=prefix))

        try:
            resolved_target = await commands.MemberConverter().convert(ctx, target_arg)
        except commands.BadArgument:
            try:
                resolved_user = await commands.UserConverter().convert(ctx, target_arg)
                resolved_target = resolved_user
            except commands.BadArgument:
                return await ctx.send(text.get(ctx, 'g_error_target_not_registered'))

        raw_input = " ".join(resource_args)
        await self._start_trade(ctx, target=resolved_target, raw_input=raw_input)

    async def _start_trade(
        self,
        ctx,
        target: discord.User | discord.Member,
        raw_input: str,
    ):
        """Validation préliminaire et lancement de l'interface TradeView."""
        # 1. Validation de la cible
        if target.id == ctx.author.id:
            msg = text.get(ctx, 'g_error_self_target')
            if getattr(ctx, 'interaction', None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        if getattr(target, 'bot', False):
            msg = text.get(ctx, 'g_error_forbidden')
            if getattr(ctx, 'interaction', None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        # 2. Vérification que la cible est bien un joueur enregistré
        checks = Check()
        if not await checks.is_player(target.id):
            msg = text.get(ctx, 'g_error_target_not_registered')
            if getattr(ctx, 'interaction', None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        # 3. Parsing des jetons signés (+/-)
        try:
            send_usd, send_rtm, receive_usd, receive_rtm = parse_trade_tokens(raw_input)
        except ValueError:
            msg = text.get(ctx, 'g_error_invalid_amount')
            if getattr(ctx, 'interaction', None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        if send_usd == 0 and send_rtm == 0 and receive_usd == 0 and receive_rtm == 0:
            msg = text.get(ctx, 'g_error_invalid_amount')
            if getattr(ctx, 'interaction', None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        # 4. Vérification préliminaire non bloquante des fonds de l'initiateur
        author_profile = await self.service.database.run(
            lambda tx: tx.one('SELECT dollars, rootium FROM players WHERE discord_id=%s', (ctx.author.id,)),
            readonly=True,
        )
        if not author_profile:
            msg = text.get(ctx, 'g_error_no_network')
            if getattr(ctx, 'interaction', None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        auth_usd = Decimal(str(author_profile.get('dollars', 0)))
        auth_rtm = Decimal(str(author_profile.get('rootium', 0)))
        if send_usd > 0 and auth_usd < send_usd:
            msg = text.get(ctx, 'g_error_insufficient_funds')
            if getattr(ctx, 'interaction', None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)
        if send_rtm > 0 and auth_rtm < send_rtm:
            msg = text.get(ctx, 'g_error_insufficient_funds')
            if getattr(ctx, 'interaction', None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        # 5. Création et affichage de la vue interactive
        view = TradeView(
            bot=self.bot,
            initiator=ctx.author,
            target=target,
            send_usd=send_usd,
            send_rtm=send_rtm,
            receive_usd=receive_usd,
            receive_rtm=receive_rtm,
            ctx=ctx,
        )

        embed = view.build_embed()
        if getattr(ctx, 'interaction', None):
            res = await ctx.respond(embed=embed, view=view)
            view.message = await ctx.interaction.original_response()
        else:
            view.message = await ctx.send(embed=embed, view=view)


def setup(bot):
    bot.add_cog(Trade(bot))
