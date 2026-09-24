"""Commande /hourly et !hourly (alias !hr) — Récompense horaire et combo minuté.

Ce module permet aux joueurs d'obtenir une prime en dollars toutes les heures :
- Gain de base aléatoire entre 30 et 90 USD (tirage uniforme).
- Délai de rechargement (cooldown) strict de 60 minutes.
- Fenêtre de combo de 20 minutes (entre 1h00 et 1h20 après la précédente récolte) :
  Un bonus de pourcentage (20 - temps - 60)% s'accumule sans limite de plafond.
- Au-delà de 1h20 : le combo est perdu (réinitialisé à 0%, série ramenée à 1).
- Système de Combo Saver : possibilité de restaurer le combo brisé contre 1 crédit.
- Traçabilité complète via le système de logs de modération.
"""

from decimal import Decimal
import logging

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from game.game_error import GameError
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils.text import format_usd, get as text_get

logger = logging.getLogger(__name__)


def _pct(value) -> str:
    """Affiche un pourcentage sans décimale inutile."""
    amount = Decimal(str(value or 0))
    if amount == amount.to_integral_value():
        return str(int(amount))
    return f"{amount:.1f}"


class HourlyComboSaverView(discord.ui.View):
    """Composant interactif permettant de sauver un combo brisé contre 1 crédit."""

    def __init__(self, cog, ctx, result: dict):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.author_id = getattr(ctx, "author", None) and ctx.author.id or ctx.user.id
        self.result = result
        self._setup_button()

    def _setup_button(self):
        credits = int(self.result.get("combo_saver_credits", 0) or 0)
        if credits > 0:
            btn = discord.ui.Button(
                label=text_get(self.ctx, "g_hourly_btn_save")[:80],
                emoji="🛡️",
                style=discord.ButtonStyle.success,
            )
            btn.callback = self._on_save
        else:
            btn = discord.ui.Button(
                label=text_get(self.ctx, "g_hourly_btn_no_credits")[:80],
                emoji="🛡️",
                style=discord.ButtonStyle.secondary,
                disabled=True,
            )
        self.add_item(btn)

    async def _on_save(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                text_get(self.ctx, "g_error_forbidden"),
                ephemeral=True,
            )
            return

        try:
            save_res = await self.cog.service.execute(
                self.author_id,
                self.ctx.guild.id if self.ctx.guild else None,
                "hourly_save_combo",
            )
            self.clear_items()
            success_msg = text_get(
                self.ctx,
                "g_hourly_saved_success",
                streak=save_res["restored_streak"],
                bonus=_pct(save_res["restored_bonus"]),
                credits=save_res["remaining_credits"],
            )
            if interaction.message:
                await interaction.response.edit_message(
                    content=f"{interaction.message.content}\n\n{success_msg}",
                    view=None,
                )
            else:
                await interaction.response.send_message(success_msg)
        except GameError as err:
            err_msg = text_get(self.ctx, f"g_error_{err.key}", **err.values)
            await interaction.response.send_message(err_msg, ephemeral=True)
        except Exception:
            logger.exception("Erreur lors de la sauvegarde du combo")
            await interaction.response.send_message("Une erreur est survenue.", ephemeral=True)


class Hourly(BaseGameCog):
    """Cog gérant la commande /hourly et le système de combo."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="hourly",
        description=EN["hourly"],
        description_localizations={"fr": FR["hourly"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def hourly(
        self,
        ctx,
        action: discord.Option(
            str,
            description="Action optionnelle (ex: 'save' pour restaurer un combo brisé)",
            choices=["save"],
            required=False,
            default=None,
        ) = None,
    ):
        """Réclamer sa récompense horaire en USD avec bonus de combo."""
        if action == "save":
            await self._invoke(ctx, "hourly_save_combo")
        else:
            await self._invoke(ctx, "hourly")

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="hourly", aliases=["hr"], help=FR["hourly"])
    async def prefix_hourly(self, ctx, action: str = None):
        """Commande préfixe !hourly (alias !hr)."""
        if action and action.lower() in ("save", "sauve", "sauver"):
            await self._invoke(ctx, "hourly_save_combo")
        else:
            await self._invoke(ctx, "hourly")

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Affiche le rapport de récompense horaire et déclenche la journalisation."""
        mentions = discord.AllowedMentions.none()

        if method == "hourly_save_combo":
            success_msg = text_get(
                ctx,
                "g_hourly_saved_success",
                streak=result["restored_streak"],
                bonus=_pct(result["restored_bonus"]),
                credits=result["remaining_credits"],
            )
            if getattr(ctx, "interaction", None):
                await ctx.respond(success_msg, allowed_mentions=mentions)
            else:
                await ctx.send(success_msg, allowed_mentions=mentions)
            return

        base_usd = result["base_usd"]
        bonus_pct = result["bonus_pct"]
        step_bonus_pct = result["step_bonus_pct"]
        total_usd = result["total_usd"]
        new_dollars = result["new_dollars"]
        streak = result["streak"]
        combo_lost = result["combo_lost"]
        is_first = result["is_first"]
        next_ts = result["next_available_ts"]
        interval_seconds = result.get("interval_seconds")
        can_save = result.get("can_save_combo", False)

        values = {
            "total": format_usd(total_usd),
            "bonus": _pct(bonus_pct),
            "streak": streak,
            "next_ts": next_ts,
        }
        if is_first:
            key = "g_hourly_first"
        elif combo_lost:
            key = "g_hourly_broken"
        else:
            key = "g_hourly_combo"
        content = text_get(ctx, key, **values)

        view = None
        if can_save:
            saver_prompt = text_get(
                ctx,
                "g_hourly_broken_saver_prompt",
                lost_streak=result.get("lost_streak", 0),
                lost_bonus=_pct(result.get("lost_bonus", 0)),
                credits=result.get("combo_saver_credits", 0),
            )
            content = f"{content}\n{saver_prompt}"
            view = HourlyComboSaverView(self, ctx, result)

        kwargs = {"allowed_mentions": mentions}
        if view is not None:
            kwargs["view"] = view

        if getattr(ctx, "interaction", None):
            await ctx.respond(content, **kwargs)
        else:
            await ctx.send(content, **kwargs)

        # Journalisation Discord asynchrone
        try:
            author = getattr(ctx, "author", None) or getattr(ctx, "user", None)
            if author:
                await self.bot.discord_logger.log_hourly(
                    ctx=ctx,
                    user=author,
                    base_usd=base_usd,
                    bonus_pct=bonus_pct,
                    total_usd=total_usd,
                    streak=streak,
                    interval_seconds=interval_seconds,
                    combo_lost=combo_lost,
                    is_first=is_first,
                    step_bonus_pct=step_bonus_pct,
                    new_dollars=new_dollars,
                )
        except Exception:
            pass


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Hourly(bot))
