"""
Commande /contract et !contract — Contrats de travail garantis pour Root CyberSec.

Ce module permet à chaque joueur d'accepter des missions pour une agence fictive :
- Trois durées disponibles : court (30 min), moyen (2 h), long (6 h).
- Réussite garantie, récupération manuelle sans expiration ni pénalité de retard.
- Jauge de fidélité : après un certain nombre de missions terminées, la mission
  suivante bénéficie d'une « Mission spéciale : +50 % ».
- Interface interactive avec boutons dynamiques pour lancer ou récolter.
"""

import asyncio
from decimal import Decimal
import logging

import discord
from discord.ext import commands, tasks

import data
from commands.game.commandgame import BaseGameCog
from game.db.players import Player
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.check import Check
from utils.root_embed import RootEmbed
from utils.text import format_usd

logger = logging.getLogger(__name__)


def _format_fidelity_bar(fidelity: int, threshold: int = 5) -> str:
    """Génère la jauge ASCII de fidélité inspirée du style Root OS (ex: ▰▰▰▱▱)."""
    t = max(1, threshold)
    filled = max(0, min(t, fidelity))
    return "▰" * filled + "▱" * (t - filled)


def _build_contract_content(ctx, result: dict) -> str:
    """Construit le corps textuel de l'embed pour la commande /contract."""
    is_en = (text.get_locale(ctx) == "en")

    # Cas 1 : Résultat de collecte réussi
    if result.get("collected"):
        reward_usd = format_usd(result.get("reward_usd", 0))
        new_dollars = format_usd(result.get("new_dollars", 0))
        agency = result.get("offers_data", {}).get("agency", "Root CyberSec")
        title = result.get("title", "Mission")
        fidelity = result.get("contract_fidelity", 0)
        threshold = result.get("offers_data", {}).get("fidelity_threshold", 5)
        bar = _format_fidelity_bar(fidelity, threshold)

        is_special_next = result.get("offers_data", {}).get("is_special", False)
        grace_ts = result.get("grace_ts") or result.get("offers_data", {}).get("grace_ts")
        if is_special_next:
            if grace_ts:
                fidelity_hint = (
                    f" · ⭐ **Special mission active!** (Relaunch before <t:{grace_ts}:R>)"
                    if is_en else
                    f" · ⭐ **Mission spéciale active !** (Relancez avant <t:{grace_ts}:R>)"
                )
            else:
                fidelity_hint = (" · ⭐ **Special mission unlocked!**" if is_en else " · ⭐ **Mission spéciale débloquée !**")
        else:
            fidelity_hint = (f" *(Tier {threshold}: +40% bonus)*" if is_en else f" *(Palier {threshold} : bonus +40%)*")

        collected_msg = text.get(
            ctx,
            "g_contract_collected",
            reward_usd=reward_usd,
            new_dollars=new_dollars,
            agency=agency,
            title=title,
            fidelity=fidelity,
            threshold=threshold,
            fidelity_hint=fidelity_hint,
        )

        # Ajoute les nouvelles offres en dessous
        offers = result.get("offers_data", {}).get("offers", {})
        special_badge = text.get(ctx, "g_contract_special_badge") if is_special_next else ""
        offers_msg = text.get(
            ctx,
            "g_contract_offers",
            agency=agency,
            special_badge=special_badge,
            short_usd=format_usd(offers.get("short", {}).get("reward_usd", 75)),
            medium_usd=format_usd(offers.get("medium", {}).get("reward_usd", 250)),
            long_usd=format_usd(offers.get("long", {}).get("reward_usd", 600)),
            fidelity_bar=bar,
            fidelity=fidelity,
            threshold=threshold,
            fidelity_hint=fidelity_hint,
        )
        return f"{collected_msg}\n\n{offers_msg}"

    # Cas 2 : Contrat actif en cours ou terminé
    contract = result.get("contract") if result.get("has_active") else None
    if not contract and result.get("duration_type") and result.get("expires_ts"):
        # Résultat direct d'une action 'start'
        contract = result

    if contract:
        agency = result.get("offers_data", {}).get("agency", "Root CyberSec")
        title = contract.get("title", "Mission")
        reward_usd = format_usd(contract.get("reward_usd", 0))
        expires_ts = contract.get("expires_ts", 0)
        is_ready = contract.get("is_ready", False)
        is_special = contract.get("is_special", False)
        special_badge = text.get(ctx, "g_contract_special_badge") if is_special else ""

        if is_ready:
            return text.get(
                ctx,
                "g_contract_ready",
                agency=agency,
                special_badge=special_badge,
                title=title,
                reward_usd=reward_usd,
            )
        else:
            return text.get(
                ctx,
                "g_contract_active",
                agency=agency,
                special_badge=special_badge,
                title=title,
                reward_usd=reward_usd,
                expires_ts=expires_ts,
            )

    # Cas 3 : Aucune mission active — Présentation des offres
    offers_data = result.get("offers_data", {})
    agency = offers_data.get("agency", "Root CyberSec")
    fidelity = result.get("fidelity", 0)
    threshold = result.get("fidelity_threshold", 5)
    bar = _format_fidelity_bar(fidelity, threshold)
    is_special = offers_data.get("is_special", False)
    special_badge = text.get(ctx, "g_contract_special_badge") if is_special else ""
    grace_ts = result.get("grace_ts") or offers_data.get("grace_ts")
    if is_special:
        if grace_ts:
            fidelity_hint = (
                f" · ⭐ **Special mission active!** (Relaunch before <t:{grace_ts}:R>)"
                if is_en else
                f" · ⭐ **Mission spéciale active !** (Relancez avant <t:{grace_ts}:R>)"
            )
        else:
            fidelity_hint = (" · ⭐ **Special mission unlocked!**" if is_en else " · ⭐ **Mission spéciale débloquée !**")
    else:
        fidelity_hint = (f" *(Tier {threshold}: +40% bonus)*" if is_en else f" *(Palier {threshold} : bonus +40%)*")

    offers = offers_data.get("offers", {})
    short_usd = format_usd(offers.get("short", {}).get("reward_usd", 75))
    medium_usd = format_usd(offers.get("medium", {}).get("reward_usd", 250))
    long_usd = format_usd(offers.get("long", {}).get("reward_usd", 600))

    return text.get(
        ctx,
        "g_contract_offers",
        agency=agency,
        special_badge=special_badge,
        short_usd=short_usd,
        medium_usd=medium_usd,
        long_usd=long_usd,
        fidelity_bar=bar,
        fidelity=fidelity,
        threshold=threshold,
        fidelity_hint=fidelity_hint,
    )


class ContractView(discord.ui.View):
    """Composant d'interface interactif avec boutons pour gérer ses contrats."""

    def __init__(self, cog, ctx, result: dict):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.author_id = ctx.author.id
        self.lock = asyncio.Lock()
        self.message = None
        self._update_buttons(result)

    def _update_buttons(self, result: dict):
        self.clear_items()

        # Si le résultat est un 'start', on le traite comme un contrat actif
        contract = result.get("contract") if result.get("has_active") else None
        if not contract and result.get("duration_type") and result.get("expires_ts"):
            contract = result

        if contract:
            is_ready = contract.get("is_ready", False)
            reward_usd = format_usd(contract.get("reward_usd", 0))

            if is_ready:
                btn_collect = discord.ui.Button(
                    label=text.get(self.ctx, "g_contract_btn_collect", usd=reward_usd)[:80],
                    emoji="💵",
                    style=discord.ButtonStyle.success,
                )
                btn_collect.callback = self._on_collect
                self.add_item(btn_collect)
            else:
                btn_running = discord.ui.Button(
                    label=text.get(self.ctx, "g_contract_btn_short" if contract.get("duration_type") == "short" else ("g_contract_btn_medium" if contract.get("duration_type") == "medium" else "g_contract_btn_long"))[:80],
                    emoji="⏳",
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                )
                self.add_item(btn_running)

            btn_refresh = discord.ui.Button(
                label=text.get(self.ctx, "g_net_btn_refresh", fallback="Actualiser")[:80],
                emoji="🔄",
                style=discord.ButtonStyle.primary,
            )
            btn_refresh.callback = self._on_refresh
            self.add_item(btn_refresh)
        else:
            async def _start_short(i: discord.Interaction):
                await self._on_start(i, "short")

            async def _start_med(i: discord.Interaction):
                await self._on_start(i, "medium")

            async def _start_long(i: discord.Interaction):
                await self._on_start(i, "long")

            btn_short = discord.ui.Button(
                label=text.get(self.ctx, "g_contract_btn_short")[:80],
                emoji="⚡",
                style=discord.ButtonStyle.primary,
            )
            btn_short.callback = _start_short
            self.add_item(btn_short)

            btn_med = discord.ui.Button(
                label=text.get(self.ctx, "g_contract_btn_medium")[:80],
                emoji="💼",
                style=discord.ButtonStyle.primary,
            )
            btn_med.callback = _start_med
            self.add_item(btn_med)

            btn_long = discord.ui.Button(
                label=text.get(self.ctx, "g_contract_btn_long")[:80],
                emoji="🛡️",
                style=discord.ButtonStyle.primary,
            )
            btn_long.callback = _start_long
            self.add_item(btn_long)

            btn_refresh = discord.ui.Button(
                label=text.get(self.ctx, "g_net_btn_refresh", fallback="Actualiser")[:80],
                emoji="🔄",
                style=discord.ButtonStyle.secondary,
            )
            btn_refresh.callback = self._on_refresh
            self.add_item(btn_refresh)

    async def _check_interaction(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                text.get(self.ctx, "no_permission"), ephemeral=True
            )
            return False

        checks = Check()
        allowed, err_key = await checks.check_interaction_access(
            self.cog.bot, interaction, allow_network=False
        )
        if not allowed:
            await interaction.response.send_message(
                text.get(self.ctx, err_key), ephemeral=True
            )
            return False

        if not await checks.is_player(interaction.user.id):
            await interaction.response.send_message(
                text.get(self.ctx, "g_error_no_network"), ephemeral=True
            )
            return False

        return True

    async def _on_start(self, interaction: discord.Interaction, duration: str):
        if not await self._check_interaction(interaction):
            return

        async with self.lock:
            await interaction.response.defer()
            try:
                await self.cog.service.execute(
                    self.author_id,
                    interaction.guild.id if interaction.guild else None,
                    "contract",
                    action="start",
                    duration=duration,
                )
            except Exception as err:
                msg = (
                    text.get(self.ctx, "g_error_" + err.key, **getattr(err, "values", {}))
                    if hasattr(err, "key")
                    else str(err)
                )
                await interaction.followup.send(msg, ephemeral=True)
                return

            new_status = await self.cog.service.execute(
                self.author_id,
                interaction.guild.id if interaction.guild else None,
                "contract",
                action="view",
            )
            content = _build_contract_content(self.ctx, new_status)
            self._update_buttons(new_status)
            embed = RootEmbed(self.ctx, "contract", content)
            try:
                if self.message:
                    await self.message.edit(embed=embed, view=self)
                elif interaction.message:
                    await interaction.message.edit(embed=embed, view=self)
            except Exception:
                logger.exception("Erreur lors de la mise à jour du contrat après start")

    async def _on_collect(self, interaction: discord.Interaction):
        if not await self._check_interaction(interaction):
            return

        async with self.lock:
            await interaction.response.defer()
            try:
                res = await self.cog.service.execute(
                    self.author_id,
                    interaction.guild.id if interaction.guild else None,
                    "contract",
                    action="collect",
                )
            except Exception as err:
                msg = (
                    text.get(self.ctx, "g_error_" + err.key, **getattr(err, "values", {}))
                    if hasattr(err, "key")
                    else str(err)
                )
                await interaction.followup.send(msg, ephemeral=True)
                return

            content = _build_contract_content(self.ctx, res)
            self._update_buttons(res)
            embed = RootEmbed(self.ctx, "contract", content)
            try:
                if self.message:
                    await self.message.edit(embed=embed, view=self)
                elif interaction.message:
                    await interaction.message.edit(embed=embed, view=self)
            except Exception:
                logger.exception("Erreur lors de la mise à jour du contrat après collect")

    async def _on_refresh(self, interaction: discord.Interaction):
        if not await self._check_interaction(interaction):
            return

        async with self.lock:
            await interaction.response.defer()
            status = await self.cog.service.execute(
                self.author_id,
                interaction.guild.id if interaction.guild else None,
                "contract",
                action="view",
            )
            content = _build_contract_content(self.ctx, status)
            self._update_buttons(status)
            embed = RootEmbed(self.ctx, "contract", content)
            try:
                if self.message:
                    await self.message.edit(embed=embed, view=self)
                elif interaction.message:
                    await interaction.message.edit(embed=embed, view=self)
            except Exception:
                logger.exception("Erreur lors du rafraîchissement du contrat")


class Contract(BaseGameCog):
    """Cog gérant les contrats de travail de Root CyberSec."""

    def __init__(self, bot):
        self.bot = bot
        self.check_contracts_loop.start()

    def cog_unload(self):
        """Arrête la tâche d'arrière-plan au déchargement du Cog."""
        self.check_contracts_loop.cancel()

    @tasks.loop(seconds=30)
    async def check_contracts_loop(self):
        """Boucle de notification automatique en MP lors de l'échéance d'un contrat."""
        try:
            delivered = await self.service.deliver_due_contract_notifications()
            if delivered:
                for item in delivered:
                    await self._notify_contract_expired(item)
        except Exception:
            logger.exception("Erreur lors de la vérification des contrats expirés")

    @check_contracts_loop.before_loop
    async def before_check_contracts_loop(self):
        """Attend la synchronisation complète du bot avant de démarrer la boucle."""
        if hasattr(self.bot, "wait_until_ready") and callable(self.bot.wait_until_ready):
            res = self.bot.wait_until_ready()
            if asyncio.iscoroutine(res):
                await res

    async def _notify_contract_expired(self, item: dict):
        """Envoie un MP au joueur l'informant que son contrat est prêt à être récupéré."""
        discord_id = item.get("discord_id")
        if not discord_id:
            return
        try:
            user = self.bot.get_user(discord_id)
            if not user:
                user = await self.bot.fetch_user(discord_id)
            if user:
                lang = await self.service.database.run(
                    lambda tx: Player.get_language(tx, discord_id),
                    readonly=True,
                ) or "fr"
                agency = item.get("agency") or "Root CyberSec"
                title = item.get("title") or "Mission"
                reward_usd = format_usd(item.get("reward_usd", 0))
                msg = text.get_for_lang(
                    lang,
                    "g_contract_expired_dm",
                    agency=agency,
                    title=title,
                    reward_usd=reward_usd,
                )
                dm_title = "Contrat terminé" if lang == "fr" else "Contract Completed"
                embed = RootEmbed.notification(lang, dm_title, msg)
                await embed.send_to(user)
        except discord.Forbidden:
            logger.debug("Impossible d'envoyer le MP de fin de contrat à %s (MP bloqués)", discord_id)
        except Exception:
            logger.exception("Erreur lors de l'envoi du MP de fin de contrat à %s", discord_id)

    # ── Slash Command ────────────────────────────────────────────────────────
    @discord.slash_command(
        name="contract",
        description=EN["contract"],
        description_localizations={"fr": FR["contract"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def contract(
        self,
        ctx,
        action: discord.Option(
            str,
            description=desc["contract_action"],
            description_localizations=desc_loc["contract_action"],
            choices=["view", "start", "collect"],
            required=False,
            default="view",
        ) = "view",
        duration: discord.Option(
            str,
            description=desc["contract_duration"],
            description_localizations=desc_loc["contract_duration"],
            choices=["short", "medium", "long"],
            required=False,
            default=None,
        ) = None,
    ):
        """Consulter, accepter ou récupérer un contrat de travail garanti."""
        await self._invoke(ctx, "contract", action=action, duration=duration)

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="contract", aliases=["co"], help=FR["contract"])
    async def prefix_contract(self, ctx, *args):
        """Commande préfixe !contract (alias !co) [action] [duration]."""
        action = "view"
        duration = None

        if args:
            first = args[0].strip().lower()
            if first in ("start", "lancer"):
                action = "start"
                if len(args) > 1:
                    duration = args[1].strip().lower()
            elif first in ("collect", "claim", "recup", "recuperer"):
                action = "collect"
            elif first in ("short", "medium", "long", "court", "moyen"):
                action = "start"
                mapping = {"court": "short", "moyen": "medium"}
                duration = mapping.get(first, first)
            elif first in ("view", "voir", "status"):
                action = "view"
            else:
                action = first

        await self._invoke(ctx, "contract", action=action, duration=duration)

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Génère l'affichage stylisé du contrat avec la vue interactive."""
        content = _build_contract_content(ctx, result)
        view = ContractView(self, ctx, result)
        msg = await self._send_embed(ctx, "contract", content, view=view)
        if msg:
            view.message = msg


def setup(bot):
    """Point d'entrée standard pour le chargement du Cog."""
    bot.add_cog(Contract(bot))

