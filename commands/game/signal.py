"""Commande /signal et !signal (alias !s) — Mini-jeu communautaire Signal.

Ce module implémente le défi d'interception de fréquence dominante de Root :
- Une ligne courte de 15 lettres majuscules espacées contenant 3 lettres distinctes.
- Une seule lettre nettement majoritaire apparaît 8 fois, face à 2 distracteurs (4 et 3 fois).
- Le joueur repère la lettre majoritaire et répond avec /signal <lettre> ou clique directement sur le bouton.
- Le premier joueur qui soumet la bonne lettre remporte la prime en USD.
- Aucun délai d'attente entre les mauvaises propositions.
- Les résultats de victoire sont automatiquement journalisés dans le salon public.
"""

from types import SimpleNamespace

import discord
from discord.ext import commands

import data
from commands.game.game_config import GAMES
from commands.game.minigame_cog import MiniGameCog
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR


class SignalButtonsView(discord.ui.View):
    """Boutons interactifs permettant de répondre instantanément au signal avec l'une des 3 lettres."""

    def __init__(self, cog, letters: list[str]):
        super().__init__(timeout=120)
        self.cog = cog
        for letter in letters:
            btn = discord.ui.Button(
                label=letter,
                style=discord.ButtonStyle.primary,
                custom_id=f"signal_btn_{letter}",
            )
            btn.callback = self._make_callback(letter)
            self.add_item(btn)

    def _make_callback(self, letter: str):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            sub_ctx = SimpleNamespace(
                interaction=interaction,
                author=interaction.user,
                guild=interaction.guild,
                bot=interaction.client,
                command=None,
                respond=interaction.followup.send,
                send=interaction.followup.send,
            )
            guild_name = interaction.guild.name if interaction.guild else None
            await self.cog._invoke(sub_ctx, "signal", guess=letter, guild_name=guild_name)
        return callback


class Signal(MiniGameCog):
    """Cog gérant le mini-jeu Signal."""

    config = GAMES["signal"]

    def _build_active_view(self, ctx, result: dict) -> discord.ui.View | None:
        """Génère la vue avec 3 boutons pour les 3 lettres concurrentes."""
        letters = result.get("letters")
        if letters and isinstance(letters, (list, tuple)) and len(letters) == 3:
            return SignalButtonsView(self, list(letters))
        return None

    async def _send(self, ctx, method: str, result: dict):
        """Dispatch des résultats de Signal.

        Si le joueur se trompe via un bouton, supprime le message du défi pour
        l'empêcher de cliquer successivement sur les autres boutons.
        """
        status = result.get("status")
        try:
            await super()._send(ctx, method, result)
        finally:
            if status == "wrong":
                interaction = getattr(ctx, "interaction", None)
                msg = getattr(interaction, "message", None) if interaction else None
                if msg:
                    try:
                        await msg.delete()
                    except Exception:
                        try:
                            await msg.edit(view=None)
                        except Exception:
                            pass


    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="signal",
        description=EN["signal"],
        description_localizations={"fr": FR["signal"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def signal(
        self,
        ctx,
        letter: discord.Option(
            str,
            description="Dominant letter in the signal (A-Z) / Lettre dominante du signal (A-Z)",
            required=False,
            default=None,
        ) = None,
    ):
        """Participer à l'interception de Signal ou consulter le flux actif."""
        await self._run_slash(ctx, letter)

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="signal", aliases=["s"], help=FR["signal"])
    async def prefix_signal(self, ctx, letter: str = None):
        """Commande préfixe !signal [lettre] (alias !s)."""
        await self._run_prefix(ctx, letter)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Signal(bot))
