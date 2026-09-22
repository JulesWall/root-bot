"""
Module d'administration pour la gestion du compte à rebours de lancement de la bêta.

Commandes :
- /beta_launch status (ou !beta_launch) : Consulte l'état du compte à rebours et la présence actuelle.
- /beta_launch set <cible> (ou !beta_launch set <cible>) : Définit la date/heure ou durée du lancement.
- /beta_launch clear (ou !beta_launch clear) : Supprime la date cible et rétablit l'activité par défaut.
"""

import discord
from discord.ext import commands

from data import GUILD_WHITELIST
from utils.check import Check
from utils.presence_manager import (
    calculate_remaining_hours,
    clear_beta_launch_target,
    get_beta_launch_target,
    get_presence_text,
    set_beta_launch_target,
    update_bot_presence,
)


class BetaLaunch(commands.Cog):
    """Cog d'administration pour le compte à rebours de lancement de la bêta."""

    def __init__(self, bot):
        self.bot = bot
        self.check = Check()

    async def _handle_status(self, ctx):
        target = get_beta_launch_target()
        text = get_presence_text()
        hours = calculate_remaining_hours()

        if target is None:
            msg = (
                "ℹ️ **Compte à rebours Bêta** : Aucun lancement planifié.\n"
                "• Présence actuelle : `" + text + "`\n"
                "• Utilisez `/beta_launch set <date_ou_heures>` (ex: `24h` ou `2026-09-23 18:00`) pour en définir un."
            )
        else:
            iso_str = target.strftime("%Y-%m-%d %H:%M:%S %Z")
            ts = int(target.timestamp())
            msg = (
                f"⏱️ **Compte à rebours Bêta actif** :\n"
                f"• Cible : **{iso_str}** (<t:{ts}:R>)\n"
                f"• Heures restantes : **{hours}**\n"
                f"• Présence Discord actuelle : `{text}`"
            )

        if hasattr(ctx, "respond"):
            await ctx.respond(msg)
        else:
            await ctx.send(msg)

    async def _handle_set(self, ctx, target_input: str):
        if not target_input or not target_input.strip():
            msg = "⚠️ Veuillez spécifier une date ou durée (ex: `24h`, `18:00`, `2026-09-23 18:00`)."
            if hasattr(ctx, "respond"):
                await ctx.respond(msg)
            else:
                await ctx.send(msg)
            return

        try:
            target = set_beta_launch_target(target_input.strip())
            await update_bot_presence(self.bot)
            hours = calculate_remaining_hours(target)
            text = get_presence_text(target)
            ts = int(target.timestamp())
            msg = (
                f"✅ **Lancement de la Bêta programmé avec succès !**\n"
                f"• Cible : **{target.strftime('%Y-%m-%d %H:%M:%S')}** (<t:{ts}:R>)\n"
                f"• Heures restantes calculées : **{hours}**\n"
                f"• Présence Discord mise à jour : `{text}`"
            )
        except Exception as e:
            msg = f"❌ Format de date/heure invalide : `{target_input}` ({e})"

        if hasattr(ctx, "respond"):
            await ctx.respond(msg)
        else:
            await ctx.send(msg)

    async def _handle_clear(self, ctx):
        clear_beta_launch_target()
        await update_bot_presence(self.bot)
        msg = "🗑️ Compte à rebours de bêta réinitialisé. La présence du bot a été remise par défaut."
        if hasattr(ctx, "respond"):
            await ctx.respond(msg)
        else:
            await ctx.send(msg)

    # ── Commande Slash /beta_launch ──────────────────────────────────────────
    @discord.slash_command(
        name="beta_launch",
        guild_ids=GUILD_WHITELIST or None,
        description="Gère le compte à rebours de lancement de la bêta dans la présence du bot",
    )
    async def slash_beta_launch(
        self,
        ctx,
        action: discord.Option(
            str,
            "Action à effectuer",
            choices=["status", "set", "clear"],
            default="status",
            required=False,
        ) = "status",
        cible: discord.Option(
            str,
            "Date, heure ou durée cible (ex: 24h, 18:00, 2026-09-23 18:00)",
            default=None,
            required=False,
        ) = None,
    ):
        if not await self.check.is_op(self.bot, ctx.author.id):
            await ctx.respond("⛔ Accès refusé : rôle OP requis.", ephemeral=True)
            return

        if action == "set":
            await self._handle_set(ctx, cible)
        elif action == "clear":
            await self._handle_clear(ctx)
        else:
            await self._handle_status(ctx)

    # ── Commande Préfixe !beta_launch ────────────────────────────────────────
    @commands.command(name="beta_launch")
    async def prefix_beta_launch(self, ctx, action: str = "status", *, cible: str = None):
        if not await self.check.is_op(self.bot, ctx.author.id):
            return

        action = action.lower().strip()
        if action == "set":
            await self._handle_set(ctx, cible)
        elif action == "clear":
            await self._handle_clear(ctx)
        elif action == "status":
            await self._handle_status(ctx)
        else:
            # Si l'utilisateur a tapé !beta_launch 24h directement
            await self._handle_set(ctx, f"{action} {cible or ''}".strip())


def setup(bot):
    bot.add_cog(BetaLaunch(bot))

