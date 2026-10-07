"""
Module Discord pour les macros de joueurs (commands/game/macro.py).

Prend en charge :
- La commande préfixe :
  • !macro <nom> [d] : lance la macro (mode compact ou verbeux/display avec 'd').
  • !macro create [nom] : ouvre l'assistant interactif de création.
  • !macro delete <nom> : supprime la macro.
  • !macro (ou !macro list) : liste les macros du joueur.
- Les Slash Commands :
  • /macro nom:<nom> [display:True/False] (avec autocomplétion des macros du joueur).
  • /macro-create [nom] : assistant interactif complet.
  • /macro-delete nom:<nom> (avec autocomplétion).
"""

import asyncio
from decimal import Decimal
import logging
import re
import shlex

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from game.game_error import GameError
from game.macro_catalog import MACRO_CATALOG, validate_step_args
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.root_embed import RootEmbed
from utils.root_emojis import get_button_emoji, get_emoji

logger = logging.getLogger(__name__)


def _format_step_bar(current: int, total: int = 5) -> str:
    """Génère la jauge Unicode pour le nombre d'étapes (ex: ■■■□□ 3/5)."""
    t = max(1, total)
    filled = max(0, min(t, current))
    return f"{'■' * filled}{'□' * (t - filled)} {current}/{t}"


async def macro_name_autocomplete(ctx: discord.AutocompleteContext):
    """Fournit l'autocomplétion des macros appartenant au joueur appelant."""
    try:
        user_id = ctx.interaction.user.id
        service = ctx.bot.root_service.macro_service
        macros = await service.list_macros(user_id)
        current = (ctx.value or "").lower()
        return [m["name"] for m in macros if current in m["name"].lower()][:25]
    except Exception:
        return []


def _format_macro_run_content(ctx, result: dict) -> str:
    """Formate le rapport d'exécution compact d'une macro selon l'identité graphique Root OS."""
    name = result.get("macro_name", "macro")
    total = result.get("total_steps", 0)
    steps = result.get("steps", [])

    lines = [
        f"**Macro `{name}`** · Progression : {_format_step_bar(len(steps), total)}",
        "",
    ]
    success_count = 0
    skipped_count = 0

    for s in steps:
        pos = s.get("position", 1)
        cmd = s.get("method", "command")
        if s.get("success"):
            success_count += 1
            lines.append(f"> 🟢 **Étape {pos}/{total}** (`{cmd}`) · Réussie")
        elif s.get("skipped"):
            skipped_count += 1
            err = s.get("error", {})
            err_key = err.get("key", "error")
            err_vals = err.get("values", {})
            reason_msg = text.get(ctx, "g_error_" + err_key, **err_vals)
            clean_reason = reason_msg.lstrip("> ").replace("\n> ", " · ").replace("\n", " ").strip()
            lines.append(f"> ⏳ **Étape {pos}/{total}** (`{cmd}`) · Ignorée ({clean_reason})")
        else:
            err = s.get("error", {})
            err_key = err.get("key", "error")
            err_vals = err.get("values", {})
            reason_msg = text.get(ctx, "g_error_" + err_key, **err_vals)
            clean_reason = reason_msg.lstrip("> ").replace("\n> ", " · ").replace("\n", " ").strip()
            lines.append(f"> 🔴 **Étape {pos}/{total}** (`{cmd}`) · Échec : {clean_reason}")

    lines.append("")
    summary = f"📊 **Bilan :** `{success_count}/{total}` étape(s) menée(s) à bien."
    if skipped_count > 0:
        summary += f" *({skipped_count} ignorée(s) car en attente)*"
    lines.append(summary)

    prefix = getattr(ctx, "prefix", "!")
    if getattr(ctx, "interaction", None):
        prefix = "/"
    tip = text.get(ctx, "g_macro_run_tip", prefix=prefix, name=name)
    lines.append("")
    lines.append(tip)
    return "\n".join(lines)


class StepArgsModal(discord.ui.Modal):
    """Modal dynamique pour saisir les arguments d'une étape."""

    def __init__(self, spec, on_submit_callback):
        super().__init__(title=f"Configuration : {spec.method}"[:45])
        self.spec = spec
        self.on_submit_callback = on_submit_callback
        self.inputs = {}

        for p in self.spec.params[:5]:
            placeholder = p.label_fr
            default_val = str(p.default) if p.default is not None else ""
            field = discord.ui.InputText(
                label=f"{p.name} ({p.type})"[:45],
                placeholder=placeholder[:100],
                value=default_val,
                required=p.required,
            )
            self.inputs[p.name] = field
            self.add_item(field)

    async def callback(self, interaction: discord.Interaction):
        args = {}
        for name, field in self.inputs.items():
            val = field.value
            if val != "":
                args[name] = val
        await self.on_submit_callback(interaction, self.spec.method, args)


class MacroWizardView(discord.ui.View):
    """Assistant interactif par boutons et menus pour créer et enregistrer une macro."""

    def __init__(self, cog, ctx, default_name: str | None = None):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.author_id = ctx.author.id
        self.macro_name = default_name.strip().lower() if default_name else None
        self.steps = []
        self.message = None
        self._build_interface()

    def _build_interface(self):
        self.clear_items()

        # Si le nom n'est pas encore défini
        if not self.macro_name:
            btn_name = discord.ui.Button(
                label="Nommer la macro",
                emoji=get_button_emoji("root_logiciels") or "📝",
                style=discord.ButtonStyle.primary,
            )
            btn_name.callback = self._prompt_name
            self.add_item(btn_name)
            return

        # Menu déroulant des commandes (si moins de 5 étapes)
        if len(self.steps) < 5:
            options = []
            is_en = (text.get_locale(self.ctx) == "en")
            for method, spec in MACRO_CATALOG.items():
                label = spec.label_en if is_en else spec.label_fr
                options.append(discord.SelectOption(label=f"{method}", description=label[:50], value=method))

            select_cmd = discord.ui.Select(
                placeholder=f"Ajouter étape #{len(self.steps) + 1}...",
                options=options[:25],
            )
            select_cmd.callback = self._on_select_command
            self.add_item(select_cmd)

        # Bouton d'enregistrement si au moins 1 étape
        if self.steps:
            btn_save = discord.ui.Button(
                label=f"Sauvegarder ({len(self.steps)}/5)",
                emoji=get_button_emoji("root_recolter") or "💾",
                style=discord.ButtonStyle.success,
            )
            btn_save.callback = self._on_save
            self.add_item(btn_save)

        btn_cancel = discord.ui.Button(
            label="Annuler",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
        )
        btn_cancel.callback = self._on_cancel
        self.add_item(btn_cancel)

    def _render_summary(self) -> str:
        lines = [
            f"**Configuration de la Macro** · Progression : {_format_step_bar(len(self.steps), 5)}",
            "",
            f"• **Nom assigné :** `{self.macro_name or 'En attente...'}`",
            "",
        ]
        if self.steps:
            lines.append("**Séquence programmée :**")
            for idx, s in enumerate(self.steps, start=1):
                m = s["method"]
                args_repr = ", ".join(f"{k}={v}" for k, v in s.get("args", {}).items() if k != "confirm")
                lines.append(f"> `{idx}.` **{m}** {f'({args_repr})' if args_repr else ''}")
        else:
            lines.append("*(Choisis une commande dans le menu déroulant ci-dessous pour ajouter une étape)*")
        return "\n".join(lines)

    async def _check_interaction(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                text.get(self.ctx, "no_permission"),
                ephemeral=True,
            )
            return False
        return True

    async def _prompt_name(self, interaction: discord.Interaction):
        if not await self._check_interaction(interaction):
            return

        class NameModal(discord.ui.Modal):
            def __init__(self, parent):
                super().__init__(title="Nom de la macro")
                self.parent = parent
                self.input_name = discord.ui.InputText(
                    label="Nom (1-32 caractères minuscules)",
                    placeholder="ex: farm_matin",
                    max_length=32,
                    required=True,
                )
                self.add_item(self.input_name)

            async def callback(self, modal_interaction: discord.Interaction):
                clean_name = self.input_name.value.strip().lower()
                self.parent.macro_name = clean_name
                self.parent._build_interface()
                embed = RootEmbed(self.parent.ctx, "macro", self.parent._render_summary())
                await modal_interaction.response.edit_message(
                    embed=embed,
                    view=self.parent,
                )

        await interaction.response.send_modal(NameModal(self))

    async def _on_select_command(self, interaction: discord.Interaction):
        if not await self._check_interaction(interaction):
            return

        method = interaction.data["values"][0]
        spec = MACRO_CATALOG.get(method)
        if not spec:
            return

        if spec.params:
            async def _modal_submit(modal_inter: discord.Interaction, m_method: str, m_args: dict):
                try:
                    clean_args = validate_step_args(m_method, m_args)
                    self.steps.append({"method": m_method, "args": clean_args})
                    self._build_interface()
                    embed = RootEmbed(self.ctx, "macro", self._render_summary())
                    await modal_inter.response.edit_message(embed=embed, view=self)
                except GameError as ge:
                    msg = text.get(self.ctx, "g_error_" + ge.key, **ge.values)
                    await modal_inter.followup.send(msg, ephemeral=True)

            await interaction.response.send_modal(StepArgsModal(spec, _modal_submit))
        else:
            clean_args = validate_step_args(method, {})
            self.steps.append({"method": method, "args": clean_args})
            self._build_interface()
            embed = RootEmbed(self.ctx, "macro", self._render_summary())
            await interaction.response.edit_message(embed=embed, view=self)

    async def _on_save(self, interaction: discord.Interaction):
        if not await self._check_interaction(interaction):
            return

        service = self.cog.macro_service
        try:
            res = await service.create_macro(self.author_id, self.macro_name, self.steps)
            msg = text.get(
                self.ctx,
                "g_macro_created",
                name=res["name"],
                steps_count=len(res.get("steps", [])),
            )
            embed = RootEmbed(self.ctx, "macro", msg)
            self.stop()
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=None)
            else:
                await interaction.response.edit_message(embed=embed, view=None)
        except GameError as ge:
            err_msg = text.get(self.ctx, "g_error_" + ge.key, **ge.values)
            if not interaction.response.is_done():
                await interaction.response.send_message(err_msg, ephemeral=True)
            else:
                await interaction.followup.send(err_msg, ephemeral=True)

    async def _on_cancel(self, interaction: discord.Interaction):
        if not await self._check_interaction(interaction):
            return
        self.stop()
        embed = RootEmbed(self.ctx, "macro", "❌ *Création de macro annulée.*")
        await interaction.response.edit_message(embed=embed, view=None)


class Macro(BaseGameCog):
    """Cog des commandes de macros d'automatisation."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def macro_service(self):
        return self.service.macro_service

    # ── Slash Commands ───────────────────────────────────────────────────────
    @discord.slash_command(
        name="macro",
        description=EN["macro"],
        description_localizations={"fr": FR["macro"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def macro(
        self,
        ctx,
        nom: discord.Option(
            str,
            description=desc["macro_name"],
            description_localizations=desc_loc["macro_name"],
            autocomplete=macro_name_autocomplete,
            required=False,
            default=None,
        ) = None,
        display: discord.Option(
            bool,
            description="Afficher les réponses de chaque commande (mode verbeux / option d)",
            description_localizations={"fr": "Afficher les réponses de chaque commande (mode verbeux / option d)"},
            required=False,
            default=False,
        ) = False,
    ):
        """Lancer une macro enregistrée ou lister ses macros."""
        await self._prefetch_lang(ctx.author.id)
        if not nom or nom.strip().lower() in ("help", "aide", "?"):
            await self._show_macro_help(ctx)
            return

        try:
            result = await self.macro_service.run_macro(
                ctx.author.id,
                ctx.guild.id if ctx.guild else None,
                nom,
            )
            if display:
                await self._display_macro_steps(ctx, nom, result)
            else:
                await self._dispatch_macro_logs(ctx, result)
                content = _format_macro_run_content(ctx, result)
                await self._send_embed(ctx, "macro", content)
        except GameError as error:
            await self._send_error(ctx, error)

    @discord.slash_command(
        name="macro-create",
        description=desc["macro_create"],
        description_localizations=desc_loc["macro_create"],
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def macro_create(
        self,
        ctx,
        nom: discord.Option(
            str,
            description=desc["macro_name"],
            description_localizations=desc_loc["macro_name"],
            required=False,
            default=None,
        ) = None,
    ):
        """Créer une macro interactivement avec l'assistant."""
        await self._prefetch_lang(ctx.author.id)
        view = MacroWizardView(self, ctx, default_name=nom)
        embed = RootEmbed(ctx, "macro", view._render_summary())
        if getattr(ctx, "interaction", None):
            msg = await ctx.respond(embed=embed, view=view)
        else:
            msg = await ctx.send(embed=embed, view=view)
        view.message = getattr(msg, "message", None) or msg

    @discord.slash_command(
        name="macro-delete",
        description=desc["macro_delete"],
        description_localizations=desc_loc["macro_delete"],
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def macro_delete(
        self,
        ctx,
        nom: discord.Option(
            str,
            description=desc["macro_delete_name"],
            description_localizations=desc_loc["macro_delete_name"],
            autocomplete=macro_name_autocomplete,
            required=True,
        ),
    ):
        """Supprimer l'une de ses macros."""
        await self._prefetch_lang(ctx.author.id)
        try:
            await self.macro_service.delete_macro(ctx.author.id, nom)
            msg = text.get(ctx, "g_macro_deleted", name=nom)
            await self._send_embed(ctx, "macro", msg)
        except GameError as error:
            await self._send_error(ctx, error)

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="macro", aliases=["mac"], help=FR["macro"])
    async def prefix_macro(self, ctx, *args):
        """Commande préfixe !macro [create [nom] | delete <nom> | <nom> [d] | list]."""
        await self._prefetch_lang(ctx.author.id)
        tokens = list(args)
        display_flags = {"d", "display", "-d", "--display", "v", "verbose"}
        display_steps = False
        remaining_tokens = []
        for t in tokens:
            if t.lower().strip() in display_flags:
                display_steps = True
            else:
                remaining_tokens.append(t)

        if not remaining_tokens or remaining_tokens[0].lower() in ("help", "aide", "?"):
            await self._show_macro_help(ctx)
            return

        if remaining_tokens[0].lower() in ("list", "liste"):
            await self._show_macro_list(ctx)
            return

        action = remaining_tokens[0].strip().lower()

        if action in ("create", "creer", "new"):
            default_name = remaining_tokens[1].strip().lower() if len(remaining_tokens) > 1 else None
            view = MacroWizardView(self, ctx, default_name=default_name)
            embed = RootEmbed(ctx, "macro", view._render_summary())
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
            return

        if action in ("delete", "suppr", "remove", "del"):
            if len(remaining_tokens) < 2:
                await ctx.send(f"⚠️ Syntaxe : `{ctx.prefix}macro delete <nom>`")
                return
            target_name = remaining_tokens[1].strip().lower()
            try:
                await self.macro_service.delete_macro(ctx.author.id, target_name)
                msg = text.get(ctx, "g_macro_deleted", name=target_name)
                await self._send_embed(ctx, "macro", msg)
            except GameError as error:
                await self._send_error(ctx, error)
            return

        if action in ("run", "exec"):
            if len(remaining_tokens) < 2:
                await ctx.send(f"⚠️ Syntaxe : `{ctx.prefix}macro run <nom> [d]`")
                return
            macro_name = remaining_tokens[1].strip().lower()
        else:
            macro_name = action

        # Par défaut : exécution de la macro spécifiée par son nom
        try:
            result = await self.macro_service.run_macro(
                ctx.author.id,
                ctx.guild.id if ctx.guild else None,
                macro_name,
            )
            if display_steps:
                await self._display_macro_steps(ctx, macro_name, result)
            else:
                await self._dispatch_macro_logs(ctx, result)
                content = _format_macro_run_content(ctx, result)
                await self._send_embed(ctx, "macro", content)
        except GameError as error:
            await self._send_error(ctx, error)

    async def _display_macro_steps(self, ctx, macro_name: str, result: dict):
        """Affiche les réponses individuelles de chaque commande comme si le joueur les avait tapées."""
        steps = result.get("steps", [])
        total = result.get("total_steps", len(steps))
        success_count = 0
        skipped_count = 0

        method_cog_map = {
            "claim": "Claim",
            "claim_auto": "Claim",
            "claim_cancel": "Claim",
            "hourly": "Hourly",
            "hourly_save_combo": "Hourly",
            "buy": "Buy",
            "upgrade": "Upgrade",
            "convert": "Convert",
            "compile": "Compile",
            "contract": "Contract",
            "network": "Network",
            "reputation": "Rep",
            "scan": "Scan",
            "hack": "Hack",
            "trade": "Trade",
            "rmd": "Reminder",
        }

        for idx, s in enumerate(steps, start=1):
            method = s.get("method", "command")
            if s.get("success"):
                success_count += 1
                res = s.get("result", {})
                cog_name = method_cog_map.get(method)
                cog = self.bot.get_cog(cog_name) if (self.bot and cog_name) else None
                displayed = False
                if cog and hasattr(cog, "_send"):
                    try:
                        await cog._send(ctx, method, res)
                        displayed = True
                    except Exception:
                        logger.exception("Erreur lors de l'affichage de l'étape %s via %s", method, cog_name)
                if not displayed:
                    await self._log_step(ctx, method, res)
                    await self._send_embed(ctx, method or "macro", f"> 🟢 **Étape {idx}/{total}** (`{method}`) · Exécutée avec succès.")
            elif s.get("skipped"):
                skipped_count += 1
                err = s.get("error", {})
                err_key = err.get("key", "error")
                err_vals = err.get("values", {})
                reason_msg = text.get(ctx, "g_error_" + err_key, **err_vals)
                if getattr(ctx, "interaction", None):
                    await ctx.respond(reason_msg, allowed_mentions=discord.AllowedMentions.none())
                else:
                    await ctx.send(reason_msg, allowed_mentions=discord.AllowedMentions.none())
            else:
                err = s.get("error", {})
                err_key = err.get("key", "error")
                err_vals = err.get("values", {})
                reason_msg = text.get(ctx, "g_error_" + err_key, **err_vals)
                if getattr(ctx, "interaction", None):
                    await ctx.respond(reason_msg, allowed_mentions=discord.AllowedMentions.none())
                else:
                    await ctx.send(reason_msg, allowed_mentions=discord.AllowedMentions.none())

        # Bilan final
        summary = f"📊 **Macro `{macro_name}`** · `{success_count}/{total}` étape(s) complétée(s)"
        if skipped_count > 0:
            summary += f" *({skipped_count} ignorée(s) car en attente)*"
        summary += "."
        if getattr(ctx, "interaction", None):
            await ctx.respond(summary, allowed_mentions=discord.AllowedMentions.none())
        else:
            await ctx.send(summary, allowed_mentions=discord.AllowedMentions.none())

    async def _dispatch_macro_logs(self, ctx, result: dict):
        """Déclenche les logs de modération et transactions blockchain pour chaque étape réussie."""
        steps = result.get("steps", [])
        for s in steps:
            if s.get("success"):
                method = s.get("method")
                res = s.get("result", {})
                await self._log_step(ctx, method, res)

    async def _log_step(self, ctx, method: str, result: dict):
        """Déclenche la journalisation modération et blockchain spécifique à la méthode exécutée."""
        if not result or not isinstance(result, dict):
            return

        from utils.logger import Logger
        bot_logger = getattr(self.bot, "discord_logger", None) or Logger(self.bot)
        author = getattr(ctx, "author", None) or getattr(ctx, "user", None)
        if isinstance(author, (int, str)):
            author_id = int(author)
            author = None
            author_name = str(author_id)
        elif author:
            author_id = getattr(author, "id", None)
            author_name = getattr(author, "display_name", None) or getattr(author, "name", None)
        else:
            author_id = None
            author_name = None

        try:
            if method in ("claim", "claim_auto"):
                claim_res = result.get("claim_result", {}) if method == "claim_auto" else result
                if claim_res.get("claimed"):
                    amount = Decimal(str(claim_res.get("amount", 0)))
                    from commands.game.claim import log_claim_events
                    await log_claim_events(self.bot, ctx, amount, claim_res)

            elif method == "hourly":
                if author:
                    await bot_logger.log_hourly(
                        ctx=ctx,
                        user=author,
                        base_usd=result.get("base_usd"),
                        bonus_pct=result.get("bonus_pct"),
                        total_usd=result.get("total_usd"),
                        streak=result.get("streak"),
                        interval_seconds=result.get("interval_seconds"),
                        combo_lost=result.get("combo_lost", False),
                        is_first=result.get("is_first", False),
                        step_bonus_pct=result.get("step_bonus_pct", 0),
                        new_dollars=result.get("new_dollars"),
                    )

            elif method == "buy":
                kind = result.get("kind")
                rtm_val = Decimal(str(result.get("rtm_price", 0)))
                if kind == "attack" and rtm_val > 0 and author_id:
                    await bot_logger.log_blockchain_transaction(
                        from_id=author_id,
                        to_address="0xROOT_BLACK_MARKET",
                        rtm_amount=rtm_val,
                        from_name=author_name,
                    )

            elif method == "convert":
                from commands.game.convert import DEX_ADDRESS
                rtm_val = Decimal(str(result.get("rtm_amount", 0)))
                if rtm_val > 0 and author_id:
                    await bot_logger.log_blockchain_transaction(
                        from_id=author_id,
                        to_address=DEX_ADDRESS,
                        rtm_amount=rtm_val,
                        tx_type="SELL TOKEN",
                        usd_amount=result.get("usd_amount"),
                        from_name=author_name,
                    )

            elif method == "compile":
                from commands.game.compile import COMPILE_ADDRESSES
                rtm_val = Decimal(str(result.get("rtm_paid") or 0))
                method_key = result.get("method", "skilled")
                to_address = COMPILE_ADDRESSES.get(method_key)
                if rtm_val > 0 and to_address and author_id:
                    await bot_logger.log_blockchain_transaction(
                        from_id=author_id,
                        to_address=to_address,
                        rtm_amount=rtm_val,
                        from_name=author_name,
                    )

            elif method == "scan":
                if result.get("scan_started") and author_id:
                    await bot_logger.log_blockchain_transaction(
                        from_id=author_id,
                        to_address="0xROOT_SCAN_NODE",
                        rtm_amount=result.get("rtm_total"),
                        tx_type="SCAN",
                        from_name=author_name,
                    )

            elif method == "hack":
                if result.get("hack_started"):
                    await bot_logger.log_pvp_attack(
                        author or author_id,
                        result.get("attack_points"),
                    )

            elif method == "reputation":
                target_id = result.get("target_id")
                if target_id and author:
                    target = self.bot.get_user(target_id)
                    if not target and hasattr(self.bot, "fetch_user"):
                        target = await self.bot.fetch_user(target_id)
                    if target:
                        await bot_logger.log_reputation(
                            ctx,
                            giver=author,
                            recipient=target,
                            points=result.get("points", 1),
                        )
        except Exception:
            logger.exception("Erreur lors de la journalisation de l'étape macro %s", method)

    async def _show_macro_help(self, ctx):
        """Affiche le guide complet d'utilisation des macros et l'état des macros du joueur."""
        macros = await self.macro_service.list_macros(ctx.author.id)
        prefix = getattr(ctx, "prefix", "!")
        if getattr(ctx, "interaction", None):
            prefix = "/"

        lines = [
            text.get(ctx, "g_macro_help_title"),
            text.get(ctx, "g_macro_help_desc"),
            "",
            "**Commandes & Syntaxe :**",
            text.get(ctx, "g_macro_help_run", prefix=prefix),
            text.get(ctx, "g_macro_help_manage", prefix=prefix),
            "",
            f"**Tes Macros Enregistrées ({len(macros)}/3) :**",
        ]
        if macros:
            for m in macros:
                lines.append(f"> • **`{m['name']}`** · `{m.get('steps_count', 0)}/5` étapes")
        else:
            lines.append(f"> *(Aucune macro configurée. Tape `{prefix}macro create` pour commencer !)*")

        lines.append("")
        lines.append(f"ℹ️ {text.get(ctx, 'g_macro_help_rules')}")
        await self._send_embed(ctx, "macro", "\n".join(lines))

    async def _show_macro_list(self, ctx):
        """Affiche la liste des macros possédées par le joueur avec style Root OS."""
        macros = await self.macro_service.list_macros(ctx.author.id)
        prefix = getattr(ctx, "prefix", "!")
        if getattr(ctx, "interaction", None):
            prefix = "/"
        if not macros:
            msg = text.get(ctx, "g_macro_list_empty", prefix=prefix)
            await self._send_embed(ctx, "macro", msg)
            return

        lines = [
            f"**Macros Enregistrées** · Capacités : {_format_step_bar(len(macros), 3)}",
            "",
        ]
        for m in macros:
            lines.append(f"> 🤖 **`{m['name']}`** · `{m.get('steps_count', 0)}/5` étapes")
        lines.append("")
        lines.append(f"> 💡 Lance avec `{prefix}macro <nom>` (ou `{prefix}macro <nom> d` pour afficher le détail de chaque commande).")
        await self._send_embed(ctx, "macro", "\n".join(lines))

    async def _send(self, ctx, method, result):
        pass


def setup(bot):
    """Enregistre le Cog Macro auprès du bot."""
    bot.add_cog(Macro(bot))
