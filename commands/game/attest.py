"""Commande /attest et !attest — Certification publique de solde de ressources (Preuve de fonds).

Permet à un joueur de prouver publiquement à ses pairs ou lors de négociations
qu'il détient au minimum un certain montant de USD ou de Rootium, sans avoir à
exécuter /network (!n) qui dévoilerait l'ensemble de son profil, ses baies et ses défenses.
"""

from decimal import Decimal, InvalidOperation
import re

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from utils import text
from utils.check import Check


class Attest(BaseGameCog):
    """Cog gérant les attestations publiques de preuve de solde."""

    def __init__(self, bot):
        self.bot = bot

    def _parse_currency_amount(self, currency_raw: str, amount_raw: str | float) -> tuple[str, Decimal]:
        """Valide et parse la devise et le montant certifié."""
        curr = str(currency_raw).lower().strip()
        if curr in ("$", "dollar", "dollars", "usd"):
            curr_code = "USD"
        elif curr in ("rtm", "rootium"):
            curr_code = "RTM"
        else:
            raise ValueError("invalid_currency")

        amt_str = str(amount_raw).replace(",", ".").strip()
        try:
            val = Decimal(amt_str)
        except InvalidOperation:
            raise ValueError("invalid_amount")

        if val <= Decimal("0"):
            raise ValueError("invalid_amount")

        if curr_code == "USD":
            if val.as_tuple().exponent < -2:
                raise ValueError("too_many_decimals_usd")
        else:
            if val.as_tuple().exponent < -5:
                raise ValueError("too_many_decimals_rtm")

        return curr_code, val

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name="attest",
        description="Certify you hold at least a certain amount of USD or RTM / Attester un solde minimum de ressources",
        description_localizations={
            "fr": "Certifier que vous possédez au moins un montant de ressources sans exposer votre profil"
        },
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def attest(
        self,
        ctx,
        currency: discord.Option(str, choices=["USD", "RTM"], description="Devise à attester"),
        amount: discord.Option(str, description="Montant minimum à certifier (ex: 500 ou 1.25)"),
    ):
        """Commande Slash /attest."""
        await self._prefetch_lang(ctx.author.id)
        await self._process_attest(ctx, currency, amount)

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name="attest", aliases=["certify", "proof"])
    async def prefix_attest(self, ctx, arg1: str = None, arg2: str = None):
        """Commande préfixe !attest <usd|rtm> <montant> ou !attest <montant><usd|rtm>."""
        await self._prefetch_lang(ctx.author.id)
        prefix = getattr(ctx, "clean_prefix", None) or getattr(ctx, "prefix", "!")

        if not arg1:
            return await ctx.send(text.get(ctx, "g_attest_usage", prefix=prefix))

        # Support de la syntaxe combinée !attest 500usd ou !attest 1.5rtm
        if arg2 is None:
            match = re.match(r"^([0-9]+(?:[\.,][0-9]+)?)\s*([a-zA-Z$]+)$", arg1.strip())
            if match:
                amount_raw, currency_raw = match.groups()
            else:
                match2 = re.match(r"^([a-zA-Z$]+)\s*([0-9]+(?:[\.,][0-9]+)?)$", arg1.strip())
                if match2:
                    currency_raw, amount_raw = match2.groups()
                else:
                    return await ctx.send(text.get(ctx, "g_attest_usage", prefix=prefix))
        else:
            # Ordre devise montant ou montant devise
            if re.match(r"^[0-9]+(?:[\.,][0-9]+)?$", arg1.strip()):
                amount_raw, currency_raw = arg1, arg2
            else:
                currency_raw, amount_raw = arg1, arg2

        await self._process_attest(ctx, currency_raw, amount_raw)

    async def _process_attest(self, ctx, currency_raw: str, amount_raw: str | float):
        """Vérifie le solde en base de données et délivre l'attestation ou le refus."""
        prefix = "/" if getattr(ctx, "interaction", None) else (getattr(ctx, "clean_prefix", None) or getattr(ctx, "prefix", "!"))

        # Vérification joueur inscrit
        checks = Check()
        if not await checks.is_player(ctx.author.id):
            msg = text.get(ctx, "g_error_no_network")
            if getattr(ctx, "interaction", None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        try:
            curr_code, val = self._parse_currency_amount(currency_raw, amount_raw)
        except ValueError:
            msg = text.get(ctx, "g_attest_usage", prefix=prefix)
            if getattr(ctx, "interaction", None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        # Lecture du solde du joueur
        player = await self.service.database.run(
            lambda tx: tx.one("SELECT dollars, rootium FROM players WHERE discord_id = %s", (ctx.author.id,)),
            readonly=True,
        )
        if not player:
            msg = text.get(ctx, "g_error_no_network")
            if getattr(ctx, "interaction", None):
                return await ctx.respond(msg, ephemeral=True)
            return await ctx.send(msg)

        cur_usd = Decimal(str(player.get("dollars", 0)))
        cur_rtm = Decimal(str(player.get("rootium", 0)))

        has_funds = (cur_usd >= val) if curr_code == "USD" else (cur_rtm >= val)

        formatted_val = f"{val:,.2f}" if curr_code == "USD" else f"{val:,.5f}"

        if has_funds:
            content = text.get(
                ctx,
                "g_attest_success",
                user=ctx.author.id,
                amount=formatted_val,
                currency=curr_code,
            )
        else:
            content = text.get(
                ctx,
                "g_attest_failed",
                user=ctx.author.id,
                amount=formatted_val,
                currency=curr_code,
            )

        if getattr(ctx, "interaction", None):
            await ctx.respond(content, allowed_mentions=discord.AllowedMentions.none())
        else:
            await ctx.send(content, allowed_mentions=discord.AllowedMentions.none())


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Attest(bot))

