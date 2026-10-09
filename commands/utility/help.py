"""
Module de la commande /help (Root Help System).
Conforme aux spécifications de CONCEPTION_HELP.md :
- 8 pages principales (Accueil, Bien démarrer, 5 rubriques de jeu, Syntaxe).
- 24 fiches de commandes publiques avec bascule dynamique Slash / Texte.
- Accès direct via `/help command:...` ou `{prefix}help <nom|alias>`.
- Menus déroulants et boutons interactifs verrouillés à l'auteur.
- Réponse éphémère en Slash, publique en préfixe.
- Timeout de 5 minutes avec désactivation propre des composants.
"""

import logging
from typing import Optional

import discord
from discord.commands import Option, slash_command
from discord.ext import commands

import data
from lang import help_en, help_fr
from utils.check import Check
from utils.prefix_manager import get_prefix_async, get_user_prefix_async
from utils.text import get_locale

logger = logging.getLogger(__name__)

# Liste canonique des 29 commandes publiques autorisées
PUBLIC_COMMANDS = [
    "network", "buy", "claim", "hourly", "contract", "convert", "market", "upgrade",
    "macro",
    "compile", "scan", "hack",
    "event", "hash", "pin", "decode", "anomaly", "buffer", "signal", "packet",
    "rep", "trade", "attest", "top",
    "lang", "rmd", "ping", "botinfo", "invite", "maths",
]


def _get_help_module(locale: str):
    """Retourne le module de langue approprié (help_fr ou help_en)."""
    return help_fr if locale == "fr" else help_en


async def help_command_autocomplete(ctx: discord.AutocompleteContext):
    """Autocomplétion slash proposant uniquement les 24 commandes publiques."""
    user_input = (ctx.value or "").strip().lower().lstrip("/")
    return [cmd for cmd in PUBLIC_COMMANDS if user_input in cmd][:25]


def render_help_embed(
    locale: str,
    prefix: str,
    mode: str,
    category: str,
    command_name: Optional[str] = None,
    beta_note: bool = False,
    unknown_query: Optional[str] = None,
) -> discord.Embed:
    """Génère l'embed Discord correspondant à la vue demandée."""
    lang = _get_help_module(locale)
    ui = lang.UI

    from utils.root_theme import COLOR_TURQUOISE
    embed = discord.Embed(
        color=COLOR_TURQUOISE,
        timestamp=discord.utils.utcnow(),
    )
    author_title = "ROOT OS // MANUEL DU SYSTÈME" if locale == 'fr' else "ROOT OS // SYSTEM MANUAL"
    embed.set_author(name=author_title)

    if unknown_query is not None:
        embed.title = f"❓ {ui['unknown_command_title']}"
        embed.description = ui["unknown_command_body"]
    elif command_name and command_name in lang.COMMANDS:
        cmd = lang.COMMANDS[command_name]
        embed.title = cmd["title"]
        description_lines = [cmd["description"], ""]

        # Syntaxe
        syntax = cmd["slash_syntax"] if mode == "slash" else cmd["text_syntax"].format(prefix=prefix)
        description_lines.append(f"**{ui['sec_syntax']}**\n`{syntax}`\n")

        # Paramètres
        if cmd.get("parameters"):
            description_lines.append(f"**{ui['sec_parameters']}**\n{cmd['parameters']}\n")

        # Exemple
        example = cmd["slash_example"] if mode == "slash" else cmd["text_example"].format(prefix=prefix)
        description_lines.append(f"**{ui['sec_example']}**\n`{example}`")
        if cmd.get("example_note"):
            description_lines.append(f"*{cmd['example_note'].format(prefix=prefix)}*")
        description_lines.append("")

        # Prérequis
        if cmd.get("prerequisites"):
            description_lines.append(f"**{ui['sec_prerequisites']}**\n{cmd['prerequisites']}\n")

        # Conseil
        if cmd.get("advice"):
            description_lines.append(f"**{ui['sec_advice']}**\n{cmd['advice']}\n")

        # Alias texte
        aliases = cmd.get("aliases")
        if aliases:
            formatted_aliases = ", ".join(a.format(prefix=prefix) for a in aliases)
            description_lines.append(f"**{ui['sec_aliases']}** : {formatted_aliases}\n")

        # Commandes liées
        linked = cmd.get("linked_commands")
        if linked:
            if mode == "slash":
                formatted_linked = ", ".join(f"`/{c}`" for c in linked)
            else:
                formatted_linked = ", ".join(f"`{prefix}{c}`" for c in linked)
            description_lines.append(f"**{ui['sec_linked']}** : {formatted_linked}")

        embed.description = "\n".join(description_lines)
    else:
        # Page de rubrique (0 à 7)
        page = lang.PAGES.get(category, lang.PAGES["home"])
        embed.title = page["title"]
        body = page["body_slash"] if mode == "slash" else page["body_text"].format(prefix=prefix)
        if category == "home" and beta_note:
            body += ui["beta_note"]
        embed.description = body

    # Pied de page
    if mode == "slash":
        footer_text = ui["footer_slash"]
    else:
        footer_text = ui["footer_text"].format(prefix=prefix)
    embed.set_footer(text=footer_text)

    return embed


class HelpCategorySelect(discord.ui.Select):
    """Menu déroulant pour naviguer entre les rubriques (Accueil, Bien démarrer, Catégories, Syntaxe)."""

    def __init__(self, view: "HelpView"):
        self.help_view = view
        lang = _get_help_module(view.locale)
        options = []
        for cat in lang.CATEGORIES:
            options.append(
                discord.SelectOption(
                    label=cat["label"],
                    value=cat["id"],
                    description=cat["description"],
                    emoji=cat["emoji"],
                    default=(cat["id"] == view.current_category and view.current_command is None),
                )
            )
        super().__init__(
            placeholder=lang.UI["select_category_placeholder"],
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        vals = self.values or getattr(self, "_selected_values", [])
        if not vals:
            return
        selected_cat = vals[0]
        self.help_view.current_category = selected_cat
        self.help_view.current_command = None
        self.help_view.unknown_query = None
        await self.help_view.refresh_and_update(interaction)


class HelpCommandSelect(discord.ui.Select):
    """Menu déroulant pour afficher en détail une commande de la rubrique courante."""

    def __init__(
        self,
        view: "HelpView",
        commands_in_category: list[dict],
        row: int = 1,
        placeholder: Optional[str] = None,
    ):
        self.help_view = view
        lang = _get_help_module(view.locale)
        options = []
        for cmd in commands_in_category:
            # Récupération d'un résumé court pour la description du menu
            short_desc = cmd["description"].split(".")[0]
            if len(short_desc) > 80:
                short_desc = short_desc[:77] + "..."
            options.append(
                discord.SelectOption(
                    label=f"/{cmd['name']}",
                    value=cmd["name"],
                    description=short_desc,
                    default=(cmd["name"] == view.current_command),
                )
            )
        super().__init__(
            placeholder=placeholder or lang.UI["select_command_placeholder"],
            min_values=1,
            max_values=1,
            options=options,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        vals = self.values or getattr(self, "_selected_values", [])
        if not vals:
            return
        selected_cmd = vals[0]
        self.help_view.current_command = selected_cmd
        self.help_view.unknown_query = None
        await self.help_view.refresh_and_update(interaction)


class HelpHomeButton(discord.ui.Button):
    """Bouton pour revenir à la page d'accueil (Page 0)."""

    def __init__(self, view: "HelpView", row: int = 2):
        self.help_view = view
        lang = _get_help_module(view.locale)
        is_home = (view.current_category == "home" and view.current_command is None and view.unknown_query is None)
        super().__init__(
            label=lang.UI["btn_home"],
            emoji="🏠",
            style=discord.ButtonStyle.secondary,
            disabled=is_home,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        self.help_view.current_category = "home"
        self.help_view.current_command = None
        self.help_view.unknown_query = None
        await self.help_view.refresh_and_update(interaction)


class HelpBackCategoryButton(discord.ui.Button):
    """Bouton pour revenir à l'index de la rubrique depuis une fiche de commande."""

    def __init__(self, view: "HelpView", row: int = 2):
        self.help_view = view
        lang = _get_help_module(view.locale)
        super().__init__(
            label=lang.UI["btn_back_category"],
            emoji="↩️",
            style=discord.ButtonStyle.secondary,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        self.help_view.current_command = None
        self.help_view.unknown_query = None
        await self.help_view.refresh_and_update(interaction)


class HelpSyntaxToggleButton(discord.ui.Button):
    """Bouton pour basculer entre l'affichage Slash et Texte."""

    def __init__(self, view: "HelpView", row: int = 2):
        self.help_view = view
        lang = _get_help_module(view.locale)
        next_label = lang.UI["btn_view_text"] if view.mode == "slash" else lang.UI["btn_view_slash"]
        super().__init__(
            label=next_label,
            emoji="🔄",
            style=discord.ButtonStyle.primary,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        self.help_view.mode = "text" if self.help_view.mode == "slash" else "slash"
        await self.help_view.refresh_and_update(interaction)


class HelpView(discord.ui.View):
    """Vue interactive pour la navigation dans l'aide."""

    def __init__(
        self,
        author_id: int,
        locale: str,
        prefix: str,
        mode: str = "slash",
        initial_category: str = "home",
        initial_command: Optional[str] = None,
        beta_note: bool = False,
        unknown_query: Optional[str] = None,
    ):
        super().__init__(timeout=300.0)
        self.author_id = author_id
        self.locale = locale
        self.prefix = prefix
        self.mode = mode
        self.current_category = initial_category
        self.current_command = initial_command
        self.beta_note = beta_note
        self.unknown_query = unknown_query
        self.message: Optional[discord.Message] = None

        self._build_components()

    def _build_components(self):
        """Reconstruit dynamiquement la liste des composants selon l'état actuel."""
        self.clear_items()
        lang = _get_help_module(self.locale)

        # 1. Sélecteur de catégorie (toujours présent)
        self.add_item(HelpCategorySelect(self))

        # 2. Sélecteur(s) de commande
        button_row = 2
        if self.current_category == "all":
            all_cmds = list(lang.COMMANDS.values())
            # Discord restreint les menus déroulants à 25 options maximum.
            # Avec 27 commandes, nous séparons en 2 menus cohérents :
            # Partie 1 : Réseau, Combat, Événements (18 commandes)
            # Partie 2 : Échange, Utilitaires & Infos (9 commandes)
            p1_cmds = [c for c in all_cmds if c["category"] in ("network", "combat", "events")]
            p2_cmds = [c for c in all_cmds if c["category"] in ("trade", "info")]

            p1_placeholder = lang.UI.get("select_cmd_part1_placeholder", lang.UI["select_command_placeholder"])
            p2_placeholder = lang.UI.get("select_cmd_part2_placeholder", lang.UI["select_command_placeholder"])

            self.add_item(HelpCommandSelect(self, p1_cmds, row=1, placeholder=p1_placeholder))
            self.add_item(HelpCommandSelect(self, p2_cmds, row=2, placeholder=p2_placeholder))
            button_row = 3
        else:
            commands_in_cat = [
                cmd for cmd in lang.COMMANDS.values()
                if cmd["category"] == self.current_category
            ]
            if commands_in_cat:
                self.add_item(HelpCommandSelect(self, commands_in_cat, row=1))
                button_row = 2
            else:
                button_row = 1

        # 3. Ligne de boutons
        self.add_item(HelpHomeButton(self, row=button_row))
        if self.current_command is not None or self.unknown_query is not None:
            self.add_item(HelpBackCategoryButton(self, row=button_row))
        self.add_item(HelpSyntaxToggleButton(self, row=button_row))
        self.add_item(
            discord.ui.Button(
                label=lang.UI["btn_server"],
                url=data.OFFICIAL_SERVER_URL,
                style=discord.ButtonStyle.link,
                emoji="💬",
                row=button_row,
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Vérifie que seul l'auteur de la commande peut interagir."""
        if interaction.user.id != self.author_id:
            lang = _get_help_module(self.locale)
            await interaction.response.send_message(
                lang.UI["not_author_error"],
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        """À expiration des contrôles (5 min), désactive tous les composants sans effacer le contenu."""
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                lang = _get_help_module(self.locale)
                embed = self.message.embeds[0] if self.message.embeds else None
                if embed:
                    embed_dict = embed.to_dict()
                    current_desc = embed_dict.get("description", "")
                    embed_dict["description"] = f"{current_desc}\n\n⚠️ *{lang.UI['navigation_expired']}*"
                    new_embed = discord.Embed.from_dict(embed_dict)
                    await self.message.edit(embed=new_embed, view=self)
                else:
                    await self.message.edit(view=self)
            except Exception:
                pass

    async def refresh_and_update(self, interaction: discord.Interaction):
        """Met à jour les composants et édite le message avec le nouvel embed."""
        self._build_components()
        embed = render_help_embed(
            locale=self.locale,
            prefix=self.prefix,
            mode=self.mode,
            category=self.current_category,
            command_name=self.current_command,
            beta_note=self.beta_note,
            unknown_query=self.unknown_query,
        )
        await interaction.response.edit_message(embed=embed, view=self)


class HelpCog(commands.Cog, name="Help"):
    """Cog d'aide publique fournissant l'index interactif /help et {prefix}help."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check = Check()

    def _resolve_command_query(self, query: Optional[str], locale: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Résout une recherche de commande :
        Retourne (canonical_name, category, error_query).
        """
        if not query:
            return None, "home", None

        q = query.strip().lower().lstrip("/").strip()
        lang = _get_help_module(locale)

        # 1. Alias de commande
        if q in lang.COMMAND_ALIASES:
            q = lang.COMMAND_ALIASES[q]

        # 2. Nom canonique dans les 24 commandes
        if q in lang.COMMANDS:
            cmd = lang.COMMANDS[q]
            return q, cmd["category"], None

        # 3. Commande inconnue ou commande d'administration exclue
        return None, "home", query

    async def _should_show_beta_note(self, user_id: int) -> bool:
        """Détermine si la mention bêta doit être affichée."""
        if not self.check.beta_enabled():
            return False
        has_access = await self.check.has_beta_access(self.bot, user_id)
        return not has_access

    async def _resolve_prefix(self, guild_id: Optional[int], user_id: Optional[int] = None) -> str:
        """Résout le préfixe avec repli sur le préfixe utilisateur en MP ou DEFAULT_PREFIX."""
        if guild_id:
            return await get_prefix_async(guild_id)
        if user_id:
            return await get_user_prefix_async(user_id)
        return data.DEFAULT_PREFIX

    @slash_command(
        name="help",
        description="Retrouve les commandes, leur syntaxe et les conseils pour progresser.",
    )
    async def slash_help(
        self,
        ctx: discord.ApplicationContext,
        command: Option(
            str,
            description="Choisis une commande pour afficher son utilisation détaillée.",
            required=False,
            autocomplete=help_command_autocomplete,
        ) = None,
    ):
        """Commande Slash d'accès au centre d'aide (réponse éphémère)."""
        locale = get_locale(ctx) or "fr"
        guild_id = ctx.guild.id if ctx.guild else None
        prefix = await self._resolve_prefix(guild_id, ctx.author.id)

        canonical_cmd, category, unknown_q = self._resolve_command_query(command, locale)
        show_beta = await self._should_show_beta_note(ctx.author.id)

        embed = render_help_embed(
            locale=locale,
            prefix=prefix,
            mode="slash",
            category=category,
            command_name=canonical_cmd,
            beta_note=show_beta,
            unknown_query=unknown_q,
        )

        view = HelpView(
            author_id=ctx.author.id,
            locale=locale,
            prefix=prefix,
            mode="slash",
            initial_category=category,
            initial_command=canonical_cmd,
            beta_note=show_beta,
            unknown_query=unknown_q,
        )

        # L'interaction a déjà été différée en mode éphémère par global_check
        msg = await ctx.respond(embed=embed, view=view, ephemeral=True)
        if hasattr(msg, "message") and msg.message:
            view.message = msg.message
        elif isinstance(msg, discord.Message):
            view.message = msg

    @commands.command(name="help")
    async def prefix_help(self, ctx: commands.Context, *, command_name: Optional[str] = None):
        """Commande textuelle avec préfixe ({prefix}help)."""
        locale = get_locale(ctx) or "fr"
        guild_id = ctx.guild.id if ctx.guild else None
        prefix = await self._resolve_prefix(guild_id, ctx.author.id)

        canonical_cmd, category, unknown_q = self._resolve_command_query(command_name, locale)
        show_beta = await self._should_show_beta_note(ctx.author.id)

        embed = render_help_embed(
            locale=locale,
            prefix=prefix,
            mode="text",
            category=category,
            command_name=canonical_cmd,
            beta_note=show_beta,
            unknown_query=unknown_q,
        )

        view = HelpView(
            author_id=ctx.author.id,
            locale=locale,
            prefix=prefix,
            mode="text",
            initial_category=category,
            initial_command=canonical_cmd,
            beta_note=show_beta,
            unknown_query=unknown_q,
        )

        msg = await ctx.send(embed=embed, view=view)
        view.message = msg


def setup(bot: commands.Bot):
    """Enregistre le cog Help dans le bot."""
    bot.add_cog(HelpCog(bot))
