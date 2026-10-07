"""
Module Discord pour les macros de joueurs (commands/game/macro.py).

Prend en charge :
- La commande préfixe :
  • !macro <nom> : lance la macro.
  • !macro create [nom] : ouvre l'assistant interactif de création (avec option d'écoute rapide des messages !).
  • !macro listen [nom] : lance directement l'écoute active des messages pour enregistrer une macro à la volée.
  • !macro delete <nom> : supprime la macro.
  • !macro (ou !macro list) : liste les macros du joueur.
- Les Slash Commands :
  • /macro nom:<nom> (avec autocomplétion des macros du joueur).
  • /macro-create [nom] : assistant interactif complet.
  • /macro-delete nom:<nom> (avec autocomplétion).
"""

import asyncio
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
    return "\n".join(lines)


def _parse_command_line_to_step(line: str) -> dict | None:
    """
    Parse une chaîne de commande textuelle (ex: '!buy mining 2 5 confirm' ou 'claim')
    en une étape de macro ({'method': '...', 'args': {...}}).
    """
    clean = line.strip()
    if not clean or clean.lower() in ("done", "fin", "save", "sauvegarder"):
        return None

    # Enlève un préfixe éventuel (!, /, etc.)
    if clean.startswith(("!", "/", ";", "$", "?")):
        clean = clean[1:].strip()

    try:
        parts = shlex.split(clean)
    except Exception:
        parts = clean.split()

    if not parts:
        return None

    cmd_name = parts[0].lower().strip()

    # Alias fréquents
    if cmd_name in ("co", "contrat"):
        cmd_name = "contract"
    elif cmd_name in ("n", "net"):
        cmd_name = "network"
    elif cmd_name in ("rep",):
        cmd_name = "reputation"
    elif cmd_name in ("cl",):
        cmd_name = "claim"

    if cmd_name not in MACRO_CATALOG:
        return None

    args = {}
    tokens = parts[1:]

    if cmd_name == "buy":
        # Parsing de buy : [kind] [tier] [count|all] ou [kind] [count|all]
        _ALL = ("all", "max", "tout")
        clean_tokens = [t.lower() for t in tokens if t.lower() not in ("confirm", "confirmer", "valider")]
        if clean_tokens:
            args["kind"] = clean_tokens[0]
        if len(clean_tokens) == 2:
            if clean_tokens[1].isdigit():
                args["tier"] = clean_tokens[1]
                args["count"] = "1"
            elif clean_tokens[1] in _ALL:
                args["tier"] = "1"
                args["count"] = "all"
            else:
                args["tier"] = "1"
                args["count"] = clean_tokens[1]
        elif len(clean_tokens) >= 3:
            if clean_tokens[1].isdigit():
                args["tier"] = clean_tokens[1]
                args["count"] = clean_tokens[2]
            elif clean_tokens[1] in _ALL:
                args["tier"] = clean_tokens[2] if clean_tokens[2].isdigit() else "1"
                args["count"] = "all"
            else:
                args["tier"] = "1"
                args["count"] = clean_tokens[1]
        elif len(clean_tokens) == 1:
            args["tier"] = "1"
            args["count"] = "1"

    elif cmd_name == "contract":
        # Parsing contract : [action] [duration]
        if tokens:
            first = tokens[0].lower()
            if first in ("start", "lancer"):
                args["action"] = "start"
                if len(tokens) > 1:
                    args["duration"] = tokens[1].lower()
            elif first in ("collect", "claim", "recup", "recuperer"):
                args["action"] = "collect"
            elif first in ("short", "medium", "long", "court", "moyen"):
                args["action"] = "start"
                args["duration"] = "short" if first == "court" else ("medium" if first == "moyen" else first)
            elif first in ("view", "voir", "status"):
                args["action"] = "view"
            else:
                args["action"] = first
        else:
            args["action"] = "collect"

    elif cmd_name == "convert":
        if tokens:
            args["amount"] = tokens[0]
        else:
            args["amount"] = "all"

    elif cmd_name == "compile":
        if tokens:
            args["atk"] = tokens[0]
            if len(tokens) > 1:
                args["method_name"] = tokens[1].lower()
        else:
            args["atk"] = "all"

    elif cmd_name == "claim_auto":
        if tokens:
            args["count"] = tokens[0]
        else:
            args["count"] = "all"

    elif cmd_name == "top":
        if tokens:
            args["category"] = tokens[0].lower()

    elif cmd_name == "rmd":
        if tokens:
            args["action"] = tokens[0].lower()
            if len(tokens) > 1:
                args["target"] = tokens[1].lower()

    elif cmd_name in ("scan", "reputation"):
        if tokens:
            # Nettoyer mention Discord <@12345> -> 12345
            raw_id = re.sub(r"[<@!>]", "", tokens[0])
            if raw_id.isdigit():
                args["target"] = int(raw_id)

    elif cmd_name == "hack":
        if tokens:
            args["secret_id"] = tokens[0]
        if len(tokens) > 1 and tokens[1].isdigit():
            args["attack_points"] = int(tokens[1])
        if len(tokens) > 2:
            args["target"] = tokens[2].lower()

    # Valide avec le catalogue
    try:
        clean_args = validate_step_args(cmd_name, args)
        return {"method": cmd_name, "args": clean_args}
    except Exception:
        return None


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
        self.listening_task = None
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

            # Bouton mode écoute rapide de messages
            btn_listen = discord.ui.Button(
                label="Écoute rapide (chat)",
                emoji=get_button_emoji("root_connexions") or "🎧",
                style=discord.ButtonStyle.secondary,
            )
            btn_listen.callback = self._on_start_listen
            self.add_item(btn_listen)

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
            lines.append("*(Choisis une commande dans le menu ou clique sur **Écoute rapide** pour taper directement vos actions)*")
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

    async def _on_start_listen(self, interaction: discord.Interaction):
        """Active l'écoute des messages du joueur dans le salon pour ajouter des commandes en temps réel."""
        if not await self._check_interaction(interaction):
            return

        if self.listening_task and not self.listening_task.done():
            await interaction.response.send_message("🎧 *L'écoute est déjà en cours dans ce salon.*", ephemeral=True)
            return

        await interaction.response.defer()
        listen_desc = text.get(
            self.ctx,
            "g_macro_listen_desc",
            name=self.macro_name or "Nouvelle",
            count=len(self.steps),
        )
        embed = RootEmbed(self.ctx, "macro", listen_desc)
        if self.message:
            await self.message.edit(embed=embed, view=self)

        self.listening_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self):
        """Boucle d'écoute des messages postés par le joueur dans le salon."""
        bot = self.cog.bot
        channel = getattr(self.ctx, "channel", None)
        if not channel:
            return

        def check(m: discord.Message):
            return m.author.id == self.author_id and m.channel.id == channel.id

        while len(self.steps) < 5:
            try:
                msg = await bot.wait_for("message", timeout=60.0, check=check)
            except asyncio.TimeoutError:
                # Timeout atteint : met à jour le message
                timeout_note = text.get(self.ctx, "g_macro_listen_timeout")
                embed = RootEmbed(self.ctx, "macro", f"{self._render_summary()}\n\n{timeout_note}")
                if self.message:
                    await self.message.edit(embed=embed, view=self)
                break

            content = msg.content.strip()
            if content.lower() in ("done", "fin", "save", "sauvegarder"):
                # Sauvegarde immédiate
                await self._save_macro_direct()
                break

            # Découpage par point-virgule si multi-commandes sur une même ligne
            sub_lines = [s.strip() for s in content.split(";") if s.strip()]
            added_any = False
            for line in sub_lines:
                if len(self.steps) >= 5:
                    break
                parsed = _parse_command_line_to_step(line)
                if parsed:
                    self.steps.append(parsed)
                    added_any = True

            if added_any:
                try:
                    await msg.add_reaction("✅")
                except Exception:
                    pass
                self._build_interface()
                embed = RootEmbed(self.ctx, "macro", self._render_summary())
                if self.message:
                    await self.message.edit(embed=embed, view=self)

    async def _save_macro_direct(self):
        """Sauvegarde directe de la macro sans passer par un bouton d'interaction."""
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
            if self.message:
                await self.message.edit(embed=embed, view=None)
        except GameError as ge:
            err_msg = text.get(self.ctx, "g_error_" + ge.key, **ge.values)
            if self.message:
                await self.message.edit(content=err_msg, view=self)

    async def _on_save(self, interaction: discord.Interaction):
        if not await self._check_interaction(interaction):
            return

        if self.listening_task and not self.listening_task.done():
            self.listening_task.cancel()

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
        if self.listening_task and not self.listening_task.done():
            self.listening_task.cancel()
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
            description="Afficher les réponses de chaque commande (mode verbeux / d)",
            description_localizations={"fr": "Afficher les réponses de chaque commande (mode verbeux / d)"},
            required=False,
            default=False,
        ) = False,
    ):
        """Lancer une macro enregistrée ou lister ses macros."""
        await self._prefetch_lang(ctx.author.id)
        if not nom:
            await self._show_macro_list(ctx)
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
        """Créer une macro interactivement avec l'assistant ou l'écoute rapide."""
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
        """Commande préfixe !macro [create [nom] | listen [nom] | delete <nom> | <nom> [d] | list]."""
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

        if not remaining_tokens or remaining_tokens[0].lower() in ("list", "liste"):
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

        if action in ("listen", "ecoute", "quick"):
            default_name = remaining_tokens[1].strip().lower() if len(remaining_tokens) > 1 else None
            view = MacroWizardView(self, ctx, default_name=default_name)
            listen_desc = text.get(
                ctx,
                "g_macro_listen_desc",
                name=view.macro_name or "Nouvelle",
                count=0,
            )
            embed = RootEmbed(ctx, "macro", listen_desc)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
            view.listening_task = asyncio.create_task(view._listen_loop())
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

    async def _show_macro_list(self, ctx):
        """Affiche la liste des macros possédées par le joueur avec style Root OS."""
        macros = await self.macro_service.list_macros(ctx.author.id)
        prefix = getattr(ctx, "prefix", "!")
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
        lines.append(f"> 💡 Lance une routine avec `{prefix}macro <nom>` ou `/macro <nom>`.")
        await self._send_embed(ctx, "macro", "\n".join(lines))

    async def _send(self, ctx, method, result):
        pass


def setup(bot):
    """Enregistre le Cog Macro auprès du bot."""
    bot.add_cog(Macro(bot))
