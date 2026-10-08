"""
Composant d'interface utilisateur Discord (View) pour les confirmations interactives.

Pattern Architectural : Two-Phase Commit UI
- Utilisé pour les actions financières ou irréversibles (/buy, /upgrade).
- Présente à l'utilisateur un devis chiffré accompagné de deux boutons : ✅ Confirmer et ❌ Annuler.
- Verrouillage anti-concurrence : un asyncio.Lock() garantit qu'un double-clic rapide ne peut
  pas valider l'action deux fois.
- Sécurité d'auteur : interaction_check vérifie que seul le joueur ayant initié la commande
  peut cliquer sur les boutons.
- Gestion du timeout (120 secondes) : désactive automatiquement les boutons après expiration.
"""

import asyncio
import logging

import discord

from game.game_error import GameError
from types import SimpleNamespace
from utils import text
from utils.check import Check


logger = logging.getLogger(__name__)


class Confirmation(discord.ui.View):
    """Vue interactive à deux boutons (Confirmer / Annuler) avec verrouillage anti-spam."""

    def __init__(self, send_fn, service, ctx, method: str, args: dict):
        """
        Initialise la vue de confirmation.
        
        Args:
            send_fn: Coroutine de rappel pour envoyer/éditer l'embed de résultat dans le Cog.
            service: Instance de RootService pour exécuter l'action confirmée.
            ctx: Contexte de la commande originale.
            method: Nom de la méthode de service à exécuter (ex: 'buy', 'upgrade').
            args: Arguments validés à transmettre au service lors de la confirmation.
        """
        super().__init__(timeout=120)
        self.send_fn = send_fn
        self.service = service
        self.ctx = ctx
        self.method = method
        self.args = args
        self.lock = asyncio.Lock()
        self.done = False
        self.message = None

        from utils.ui_components import create_cancel_button, create_confirm_button

        confirm = create_confirm_button(ctx, callback=self.confirm)
        cancel = create_cancel_button(ctx, style=discord.ButtonStyle.secondary, callback=self.cancel)
        self.add_item(confirm)
        self.add_item(cancel)

    async def acknowledge(self, interaction: discord.Interaction):
        """Accuse réception de l'interaction Discord pour éviter l'expiration du token (3s)."""
        if not interaction.response.is_done():
            await interaction.response.defer()

    def response_context(self, interaction: discord.Interaction):
        """Reconstitue un contexte léger compatible avec l'envoi de réponses de Cogs."""
        return SimpleNamespace(
            interaction=interaction,
            author=interaction.user,
            guild=self.ctx.guild,
            bot=self.ctx.bot,
            command=self.ctx.command,
            respond=interaction.followup.send,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Garde de sécurité sur les clics de boutons :
        - Vérifie que l'utilisateur qui clique est l'auteur de la commande originale.
        - Vérifie que l'utilisateur n'est pas banni.
        - Vérifie les autorisations en cas de mode maintenance actif.
        """
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return False
        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.ctx.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(text.get(self.ctx, err_key), ephemeral=True)
            return False
        await self.acknowledge(interaction)
        return True

    async def confirm(self, interaction):
        await self.acknowledge(interaction)
        async with self.lock:
            if self.done:
                await interaction.followup.send(text.get(self.ctx, 'g_already_handled'))
                return
            self.done = True
            try:
                if not await Check().is_player(interaction.user.id):
                    raise GameError('no_network')
                result = await self.service.execute(
                    interaction.user.id,
                    self.ctx.guild.id if self.ctx.guild else None,
                    self.method,
                    **self.args,
                )
                await self.send_fn(self.response_context(interaction), self.method, result)
            except GameError as error:
                if error.__cause__ is not None:
                    logger.exception(
                        "Erreur métier lors de la confirmation %s (%s)",
                        self.method, error.key,
                    )
                await interaction.followup.send(text.get(self.ctx, 'g_error_' + error.key, **error.values))
            except Exception:
                logger.exception("Erreur inattendue lors de la confirmation %s", self.method)
                try:
                    await interaction.followup.send(text.get(self.ctx, 'command_error'))
                except Exception:
                    logger.exception("Impossible d'envoyer la reponse d'erreur de confirmation")
            finally:
                self.stop()
                self._clear_original()

    async def cancel(self, interaction):
        await self.acknowledge(interaction)
        async with self.lock:
            if self.done:
                await interaction.followup.send(text.get(self.ctx, 'g_already_handled'), ephemeral=True)
                return
            self.done = True
            self.stop()
            cancelled_text = text.get(self.ctx, 'g_cancelled')
            edited = False
            if getattr(self.ctx, 'interaction', None):
                try:
                    await self.ctx.interaction.edit_original_response(content=cancelled_text, embed=None, view=None)
                    edited = True
                except Exception:
                    pass
            elif self.message:
                try:
                    await self.message.edit(content=cancelled_text, embed=None, view=None)
                    edited = True
                except Exception:
                    pass
            if not edited:
                await interaction.followup.send(cancelled_text, ephemeral=True)

    def _clear_original(self):
        try:
            if getattr(self.ctx, 'interaction', None):
                import asyncio as _asyncio
                _asyncio.ensure_future(self.ctx.interaction.edit_original_response(view=None))
            elif self.message:
                import asyncio as _asyncio
                _asyncio.ensure_future(self.message.edit(view=None))
        except Exception:
            pass

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if getattr(self.ctx, 'interaction', None):
                await self.ctx.interaction.edit_original_response(view=self)
            elif self.message:
                await self.message.edit(view=self)
        except Exception:
            pass

