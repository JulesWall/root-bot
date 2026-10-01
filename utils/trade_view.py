"""
Composant d'interface utilisateur Discord (View) pour les échanges de ressources entre joueurs.

Règles de validation asymétrique (trade.md) :
- Échange bilatéral (les deux envoient > 0) : les deux joueurs doivent valider.
- Don / Envoi unilatéral (initiateur donne, cible rien) : seul l'initiateur valide.
- Demande unilatérale (initiateur demande, donne rien) : seule la cible valide.
- L'un ou l'autre joueur peut refuser / annuler à tout moment.
- Un délai d'expiration (timeout de 3 minutes) désactive les boutons.
- Exécution atomique via RootService.execute('trade').
- Journalisation #blockchain pour chaque transfert de Rootium.
- Journalisation modération dans LOG_MODERATION_TRADE_CHANNEL_ID.
- Confirmations MP privées envoyées aux deux joueurs dans leur langue respective.
"""

import asyncio
from decimal import Decimal

import discord

from game.game_error import GameError
from utils import text
from utils.check import Check
from utils.logger import Logger
from utils.root_embed import RootEmbed
from utils.root_theme import VisualState
from utils.ui_components import create_trade_buttons


def _format_resource_lines(
    usd: Decimal,
    rtm: Decimal,
    sign: str = "",
    no_res_text: str = "• *Aucune ressource (0)*",
) -> str:
    """Formate une liste de ressources sous forme de puces markdown signées."""
    lines = []
    prefix = f"{sign} " if sign else "• "
    if usd > 0:
        lines.append(f"{prefix}💵 **{usd:,.2f} USD**")
    if rtm > 0:
        lines.append(f"{prefix}◈ **{rtm:,.5f} RTM**")
    return "\n".join(lines) if lines else no_res_text


class TradeView(discord.ui.View):
    """Vue interactive pour la négociation et la validation d'un échange."""

    def __init__(
        self,
        bot,
        initiator: discord.User | discord.Member,
        target: discord.User | discord.Member,
        send_usd: Decimal,
        send_rtm: Decimal,
        receive_usd: Decimal,
        receive_rtm: Decimal,
        ctx,
    ):
        super().__init__(timeout=180)  # 3 minutes de délai
        self.bot = bot
        self.initiator = initiator
        self.target = target
        self.send_usd = send_usd
        self.send_rtm = send_rtm
        self.receive_usd = receive_usd
        self.receive_rtm = receive_rtm
        self.ctx = ctx
        self.lock = asyncio.Lock()
        self.done = False
        self.message: discord.Message | None = None

        # Règles de validation requise
        self.initiator_sends = (self.send_usd > 0 or self.send_rtm > 0)
        self.target_sends = (self.receive_usd > 0 or self.receive_rtm > 0)

        # Qui doit valider ?
        self.needs_initiator = self.initiator_sends
        self.needs_target = self.target_sends

        # Suivi des validations
        self.initiator_validated = False
        self.target_validated = False

        # Boutons unifiés
        self.btn_validate, self.btn_refuse = create_trade_buttons(
            ctx, on_validate=self.on_validate, on_refuse=self.on_refuse
        )
        self.add_item(self.btn_validate)
        self.add_item(self.btn_refuse)

    def _build_status_text(self) -> str:
        """Construit la chaîne de statut d'attente / validation."""
        if self.needs_initiator and self.needs_target:
            if self.initiator_validated and not self.target_validated:
                return text.get(self.ctx, 'g_trade_status_initiator_ok', initiator=self.initiator.id, target=self.target.id)
            if self.target_validated and not self.initiator_validated:
                return text.get(self.ctx, 'g_trade_status_target_ok', initiator=self.initiator.id, target=self.target.id)
            return text.get(self.ctx, 'g_trade_status_waiting_both')
        elif self.needs_initiator:
            return text.get(self.ctx, 'g_trade_status_waiting_initiator', initiator=self.initiator.id)
        elif self.needs_target:
            return text.get(self.ctx, 'g_trade_status_waiting_target', target=self.target.id)
        return ""

    def build_embed(self) -> RootEmbed:
        """Construit l'embed de la proposition d'échange."""
        no_res = text.get(self.ctx, 'g_trade_no_resources')
        send_lines = _format_resource_lines(self.send_usd, self.send_rtm, sign="-", no_res_text=no_res)
        receive_lines = _format_resource_lines(self.receive_usd, self.receive_rtm, sign="+", no_res_text=no_res)
        status_line = self._build_status_text()

        desc_content = text.get(
            self.ctx,
            'g_trade_proposal_desc',
            initiator=self.initiator.id,
            target=self.target.id,
            send_lines=send_lines,
            receive_lines=receive_lines,
            validation_status=status_line,
        )
        return RootEmbed(self.ctx, 'trade', desc_content)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Seuls l'initiateur et la cible peuvent interagir avec les boutons."""
        uid = interaction.user.id
        if uid not in (self.initiator.id, self.target.id):
            await interaction.response.send_message(
                text.get(self.ctx, 'g_trade_forbidden'),
                ephemeral=True,
            )
            return False

        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(
                text.get(self.ctx, err_key),
                ephemeral=True,
            )
            return False

        return True

    async def on_validate(self, interaction: discord.Interaction):
        """Gestion du clic sur Valider."""
        if not interaction.response.is_done():
            await interaction.response.defer()

        async with self.lock:
            if self.done:
                await interaction.followup.send(text.get(self.ctx, 'g_already_handled'), ephemeral=True)
                return

            uid = interaction.user.id
            if uid == self.initiator.id:
                if not self.needs_initiator:
                    # L'initiateur ne donne rien, sa validation n'est pas requise
                    await interaction.followup.send(text.get(self.ctx, 'g_trade_not_allowed'), ephemeral=True)
                    return
                self.initiator_validated = True
            elif uid == self.target.id:
                if not self.needs_target:
                    # La cible ne donne rien, sa validation n'est pas requise
                    await interaction.followup.send(text.get(self.ctx, 'g_trade_not_allowed'), ephemeral=True)
                    return
                self.target_validated = True

            # Vérifier si toutes les validations requises sont réunies
            initiator_ok = (not self.needs_initiator) or self.initiator_validated
            target_ok = (not self.needs_target) or self.target_validated

            if initiator_ok and target_ok:
                self.done = True
                self.stop()
                await self._execute_trade(interaction)
            else:
                # Mise à jour du message avec le statut intermédiaire
                new_embed = self.build_embed()
                await self._edit_message(embed=new_embed, view=self)

    async def on_refuse(self, interaction: discord.Interaction):
        """Gestion du clic sur Refuser / Annuler."""
        if not interaction.response.is_done():
            await interaction.response.defer()

        async with self.lock:
            if self.done:
                await interaction.followup.send(text.get(self.ctx, 'g_already_handled'), ephemeral=True)
                return
            self.done = True
            self.stop()

            cancel_msg = text.get(self.ctx, 'g_trade_cancelled')
            embed = RootEmbed(self.ctx, 'trade', cancel_msg, state=VisualState.CANCELLED)
            await self._edit_message(embed=embed, view=None)

    async def on_timeout(self):
        """Délai de validation expiré."""
        async with self.lock:
            if self.done:
                return
            self.done = True
            self.stop()

            timeout_msg = text.get(self.ctx, 'g_trade_timeout')
            embed = RootEmbed(self.ctx, 'trade', timeout_msg, state=VisualState.ATTENTION)
            await self._edit_message(embed=embed, view=None)

    async def _edit_message(self, embed: discord.Embed, view: discord.ui.View | None):
        """Met à jour le message d'origine de manière sûre."""
        if getattr(self.ctx, 'interaction', None):
            try:
                await self.ctx.interaction.edit_original_response(embed=embed, view=view)
                return
            except Exception:
                pass
        if self.message:
            try:
                await self.message.edit(embed=embed, view=view)
            except Exception:
                pass

    async def _delete_message(self):
        """Supprime le message d'échange du salon de manière sûre."""
        if getattr(self.ctx, 'interaction', None):
            try:
                await self.ctx.interaction.delete_original_response()
                return
            except Exception:
                pass
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass

    async def _execute_trade(self, interaction: discord.Interaction):
        """Exécute la transaction SQL, consigne les logs et envoie les MP."""
        try:
            # 1. Exécution atomique en base de données
            trade_res = await self.bot.root_service.execute(
                self.initiator.id,
                self.ctx.guild.id if self.ctx.guild else None,
                'trade',
                target=self.target.id,
                send_usd=self.send_usd,
                send_rtm=self.send_rtm,
                receive_usd=self.receive_usd,
                receive_rtm=self.receive_rtm,
            )

            # 2. Suppression de l'affichage dans le salon (la validation n'a pas lieu d'être publique)
            await self._delete_message()

            # 3. Blockchain log si Rootium transféré
            logger = Logger(self.bot)
            if self.send_rtm > 0:
                await logger.log_blockchain_transaction(
                    from_id=self.initiator.id,
                    to_address=str(self.target.id),
                    rtm_amount=self.send_rtm,
                )
            if self.receive_rtm > 0:
                await logger.log_blockchain_transaction(
                    from_id=self.target.id,
                    to_address=str(self.initiator.id),
                    rtm_amount=self.receive_rtm,
                )

            # 4. Modération log
            await logger.log_trade(
                initiator=self.initiator,
                target=self.target,
                send_usd=self.send_usd,
                send_rtm=self.send_rtm,
                rec_usd=self.receive_usd,
                rec_rtm=self.receive_rtm,
                guild=self.ctx.guild,
            )

            # 5. Envoi des MP bilingues
            init_lang = trade_res.get('initiator_lang') or 'en'
            target_lang = trade_res.get('target_lang') or 'en'

            no_res_init = text.get_for_lang(init_lang, 'g_trade_no_resources')
            no_res_target = text.get_for_lang(target_lang, 'g_trade_no_resources')

            # Message privé pour l'initiateur (a envoyé send_*, a reçu receive_*)
            init_received = _format_resource_lines(self.receive_usd, self.receive_rtm, sign="+", no_res_text=no_res_init)
            init_sent = _format_resource_lines(self.send_usd, self.send_rtm, sign="-", no_res_text=no_res_init)
            init_dm_text = text.get_for_lang(
                init_lang,
                'g_trade_dm_received',
                partner=self.target.display_name,
                received_lines=init_received,
                sent_lines=init_sent,
            )

            # Message privé pour la cible (a reçu send_*, a envoyé receive_*)
            target_received = _format_resource_lines(self.send_usd, self.send_rtm, sign="+", no_res_text=no_res_target)
            target_sent = _format_resource_lines(self.receive_usd, self.receive_rtm, sign="-", no_res_text=no_res_target)
            target_dm_text = text.get_for_lang(
                target_lang,
                'g_trade_dm_received',
                partner=self.initiator.display_name,
                received_lines=target_received,
                sent_lines=target_sent,
            )

            try:
                dm_title = "Échange" if init_lang == "fr" else "Trade"
                embed_init = RootEmbed.notification(init_lang, dm_title, init_dm_text)
                await embed_init.send_to(self.initiator)
            except Exception:
                pass

            try:
                dm_title = "Échange" if target_lang == "fr" else "Trade"
                embed_target = RootEmbed.notification(target_lang, dm_title, target_dm_text)
                await embed_target.send_to(self.target)
            except Exception:
                pass

        except GameError as err:
            err_text = text.get(self.ctx, 'g_error_' + err.key, **err.values)
            err_embed = RootEmbed.error(self.ctx, err_text, rubrique='trade')
            await self._edit_message(embed=err_embed, view=None)
        except Exception:
            err_text = text.get(self.ctx, 'command_error')
            err_embed = RootEmbed.error(self.ctx, err_text, rubrique='trade')
            await self._edit_message(embed=err_embed, view=None)
