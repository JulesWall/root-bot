"""
Composant d'affichage standardisé des embeds Discord pour toutes les commandes Root OS.

Garantit l'homogénéité visuelle de l'ensemble du bot :
- Charte chromatique unifiée par état visuel (Turquoise, Ambre, Rouge, Blanc).
- Maintien de la compatibilité avec l'ancienne signature RootEmbed(ctx, action, content).
- Templates dédiés pour consultation, devis, action lancée, résultat, erreur, notification et rapport.
- Gestion autonome de la langue (ctx ou locale explicite pour les MP).
- Méthode send() universelle pour Slash, texte et MP.
"""

from typing import Any
import discord

from lang import game_en, game_fr
from utils import text
from utils.root_emojis import get_emoji, replace_vanilla_emojis
from utils.root_theme import (
    COLOR_TURQUOISE,
    VisualState,
    build_footer_text,
    get_color_for_state,
)

ACTION_EMOJIS = {
    'buy': 'root_materiel',
    'upgrade': 'root_firewall',
    'claim': 'root_recolter',
    'hourly': 'root_bilan',
    'reputation': 'root_puissance',
    'top': 'root_puissance',
    'hash': 'root_terminal',
    'pin': 'root_terminal',
    'event': 'root_connexions',
    'decode': 'root_logiciels',
    'anomaly': 'root_alerte',
    'buffer': 'root_memoire',
    'signal': 'root_connexions',
    'packet': 'root_connexions',
    'trade': 'root_bilan',
    'convert': 'root_bilan',
    'compile': 'root_materiel',
    'scan': 'root_scan',
    'hack': 'root_operations',
    'contract': 'root_operations',
    'rmd': 'root_temps',
    'macro': 'root_logiciels',
}


class RootEmbed(discord.Embed):
    """Embed Discord standardisé Root OS avec footer, couleur par état et horodatage unifiés."""

    # Charte chromatique historique conservée pour rétrocompatibilité avec les tests
    COLORS = {
        'buy':         discord.Color.from_rgb(46, 204, 113),   # Vert émeraude (Commerce)
        'upgrade':     discord.Color.from_rgb(46, 204, 113),   # Vert émeraude (Développement)
        'claim':       discord.Color.from_rgb(241, 196, 15),   # Or minier (Récolte de Rootium)
        'reputation':  discord.Color.gold(),                   # Or (Prestige)
        'top':         discord.Color.gold(),                   # Or (Classement)
        'hash':        discord.Color.from_rgb(0, 200, 255),    # Cyan électrique (Cryptographie)
        'pin':         discord.Color.from_rgb(255, 170, 0),    # Or/Ambre (Code PIN)
        'event':       discord.Color.from_rgb(0, 180, 240),    # Bleu réseau (Événements)
        'decode':      discord.Color.from_rgb(155, 89, 182),   # Violet/Améthyste (Décryptage)
        'anomaly':     discord.Color.from_rgb(231, 76, 60),    # Rouge alerte (Anomalie)
        'buffer':      discord.Color.from_rgb(41, 128, 185),   # Bleu cobalt (Buffer)
        'signal':      discord.Color.from_rgb(26, 188, 156),   # Turquoise (Signal)
        'packet':      discord.Color.from_rgb(230, 126, 34),   # Orange carotte (Packet)
        'trade':       discord.Color.from_rgb(46, 204, 113),   # Vert émeraude (Échange)
        'convert':     discord.Color.from_rgb(46, 204, 113),   # Vert émeraude (Vente de tokens)
        'compile':     discord.Color.from_rgb(231, 76, 60),    # Rouge offensif (Production d'ATK)
        'scan':        discord.Color.from_rgb(220, 50, 50),    # Rouge offensif (Scan PvP)
        'hourly':      discord.Color.from_rgb(52, 152, 219),   # Bleu azur (Récompense horaire)
        'contract':    discord.Color.from_rgb(0, 168, 204),    # Bleu canard (Root CyberSec)
        'rmd':         discord.Color.from_rgb(155, 89, 182),   # Violet / Améthyste (Rappels)
        'macro':       discord.Color.from_rgb(84, 226, 209),   # Turquoise Root OS (Macros)
    }

    def __init__(
        self,
        ctx=None,
        action: str = 'custom',
        content: str = '',
        state: VisualState | str | None = None,
        title: str | None = None,
        footer: str | None = None,
        locale: str | None = None,
        color: discord.Color | None = None,
    ):
        """
        Construit l'embed avec titre dynamique, palette par état ou action et footer harmonisé.
        """
        # Détermination de la locale
        resolved_locale = 'fr'
        if locale:
            resolved_locale = str(locale).lower()[:2]
        elif ctx is not None:
            resolved_locale = text.get_locale(ctx)

        lang_module = game_fr if resolved_locale == 'fr' else game_en
        action_key = 'act_' + action
        action_title = lang_module.labels.get(action_key, action.replace('_', ' ').title())

        # Nettoyage des emojis vanilla résiduels dans le libellé de l'action
        clean_action_title = action_title
        for vanilla in ('🌐', '🛒', '🧱', '🪙', '⏱️', '⭐', '🏆', '🧩', '🔐', '🔍', '⚠️', '📦', '📡', '🛰️', '🤝', '💱', '⚔️', '💼', '🔔'):
            clean_action_title = clean_action_title.replace(vanilla, '').strip()

        # Titre dynamique avec emoji personnalisé Root OS
        emoji_name = ACTION_EMOJIS.get(action, 'root_terminal')
        action_icon = get_emoji(emoji_name, True)

        if title is None:
            if ctx is not None:
                raw_title = text.get(ctx, 'g_title', action=clean_action_title)
                for vanilla in ('🌐', '🛒', '🧱', '🪙', '⏱️', '⭐', '🏆', '🧩', '🔐', '🔍', '⚠️', '📦', '📡', '🛰️', '🤝', '💱', '⚔️', '💼', '🔔'):
                    raw_title = raw_title.replace(vanilla, '').strip()
                title = f"{action_icon}{raw_title}"
            else:
                title = f"{action_icon}{clean_action_title}"
        elif not (title.startswith('<:') or title.startswith('<a:') or title.startswith('>')):
            title = f"{action_icon}{title}"

        # Couleur : priorité explicite > state > action historique > turquoise par défaut
        if color is not None:
            embed_color = color
        elif state is not None:
            embed_color = get_color_for_state(state)
        elif action in self.COLORS:
            embed_color = self.COLORS[action]
        else:
            embed_color = COLOR_TURQUOISE

        clean_content = replace_vanilla_emojis(content) if content else ''

        super().__init__(
            title=title,
            description=clean_content,
            color=embed_color,
            timestamp=discord.utils.utcnow(),
        )

        # En-tête d'auteur stylisé à l'image de /network (ROOT OS // USERNAME)
        author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
        if author and hasattr(author, 'display_name'):
            author_header = f"ROOT OS // {author.display_name.upper()}"
            avatar_url = author.display_avatar.url if hasattr(author, 'display_avatar') and author.display_avatar else None
            self.set_author(name=author_header, icon_url=avatar_url)
        else:
            bot_user = getattr(ctx, 'bot', None) and getattr(ctx.bot, 'user', None)
            bot_avatar = bot_user.display_avatar.url if bot_user and hasattr(bot_user, 'display_avatar') else None
            self.set_author(name=f"ROOT OS // {clean_action_title.upper()}", icon_url=bot_avatar)

        # Footer
        bot_user = getattr(ctx, 'bot', None) and getattr(ctx.bot, 'user', None)
        icon_url = bot_user.display_avatar.url if bot_user and hasattr(bot_user, 'display_avatar') else None

        footer_text = footer if footer is not None else build_footer_text(clean_action_title)
        self.set_footer(text=footer_text, icon_url=icon_url)

    @classmethod
    def panel(
        cls,
        ctx_or_locale: Any,
        rubrique: str,
        description: str = "",
        state: VisualState | str = VisualState.CONSULTATION,
        bot_user: Any = None,
    ) -> 'RootEmbed':
        """Gabarit : Panneau de consultation."""
        locale = ctx_or_locale if isinstance(ctx_or_locale, str) else None
        ctx = ctx_or_locale if not isinstance(ctx_or_locale, str) else None
        embed = cls(
            ctx=ctx,
            locale=locale,
            state=state,
            title=rubrique,
            content=description,
            footer=build_footer_text(rubrique),
        )
        if bot_user and hasattr(bot_user, 'display_avatar'):
            embed.set_footer(text=embed.footer.text, icon_url=bot_user.display_avatar.url)
        return embed

    @classmethod
    def quote(
        cls,
        ctx_or_locale: Any,
        action_title: str,
        intro_sentence: str = "",
        bot_user: Any = None,
    ) -> 'RootEmbed':
        """Gabarit : Devis interactif."""
        locale = ctx_or_locale if isinstance(ctx_or_locale, str) else None
        ctx = ctx_or_locale if not isinstance(ctx_or_locale, str) else None
        intro = intro_sentence or ("Vérifie le coût et l'effet avant de confirmer" if (locale == 'fr' or (ctx and text.get_locale(ctx) == 'fr')) else "Verify cost and effect before confirming")
        embed = cls(
            ctx=ctx,
            locale=locale,
            state=VisualState.QUOTE,
            title=action_title,
            content=intro,
            footer=build_footer_text(action_title),
        )
        if bot_user and hasattr(bot_user, 'display_avatar'):
            embed.set_footer(text=embed.footer.text, icon_url=bot_user.display_avatar.url)
        return embed

    @classmethod
    def action_launched(
        cls,
        ctx_or_locale: Any,
        action_title: str,
        phrase: str,
        bot_user: Any = None,
    ) -> 'RootEmbed':
        """Gabarit : Action lancée en cours."""
        locale = ctx_or_locale if isinstance(ctx_or_locale, str) else None
        ctx = ctx_or_locale if not isinstance(ctx_or_locale, str) else None
        embed = cls(
            ctx=ctx,
            locale=locale,
            state=VisualState.IN_PROGRESS,
            title=action_title,
            content=phrase,
            footer=build_footer_text(action_title),
        )
        if bot_user and hasattr(bot_user, 'display_avatar'):
            embed.set_footer(text=embed.footer.text, icon_url=bot_user.display_avatar.url)
        return embed

    @classmethod
    def result(
        cls,
        ctx_or_locale: Any,
        rubrique: str,
        result_phrase: str,
        state: VisualState | str = VisualState.SUCCESS,
        bot_user: Any = None,
    ) -> 'RootEmbed':
        """Gabarit : Résultat ponctuel d'action."""
        locale = ctx_or_locale if isinstance(ctx_or_locale, str) else None
        ctx = ctx_or_locale if not isinstance(ctx_or_locale, str) else None
        embed = cls(
            ctx=ctx,
            locale=locale,
            state=state,
            title=rubrique,
            content=result_phrase,
            footer=build_footer_text(rubrique),
        )
        if bot_user and hasattr(bot_user, 'display_avatar'):
            embed.set_footer(text=embed.footer.text, icon_url=bot_user.display_avatar.url)
        return embed

    @classmethod
    def error(
        cls,
        ctx_or_locale: Any,
        cause: str,
        rubrique: str | None = None,
        bot_user: Any = None,
    ) -> 'RootEmbed':
        """Gabarit : Erreur métier / action indisponible (Ambre)."""
        locale = ctx_or_locale if isinstance(ctx_or_locale, str) else None
        ctx = ctx_or_locale if not isinstance(ctx_or_locale, str) else None
        is_fr = (locale == 'fr' or (ctx and text.get_locale(ctx) == 'fr'))
        title = 'Action indisponible' if is_fr else 'Action unavailable'
        footer_sub = rubrique or ('Erreur' if is_fr else 'Error')
        embed = cls(
            ctx=ctx,
            locale=locale,
            state=VisualState.ATTENTION,
            title=title,
            content=cause,
            footer=build_footer_text(footer_sub),
        )
        if bot_user and hasattr(bot_user, 'display_avatar'):
            embed.set_footer(text=embed.footer.text, icon_url=bot_user.display_avatar.url)
        return embed

    @classmethod
    def notification(
        cls,
        ctx_or_locale: Any,
        event_title: str,
        content: str,
        state: VisualState | str = VisualState.CONSULTATION,
        bot_user: Any = None,
    ) -> 'RootEmbed':
        """Gabarit : Notification différée ou MP."""
        locale = ctx_or_locale if isinstance(ctx_or_locale, str) else None
        ctx = ctx_or_locale if not isinstance(ctx_or_locale, str) else None
        embed = cls(
            ctx=ctx,
            locale=locale,
            state=state,
            title=event_title,
            content=content,
            footer=build_footer_text(event_title),
        )
        if bot_user and hasattr(bot_user, 'display_avatar'):
            embed.set_footer(text=embed.footer.text, icon_url=bot_user.display_avatar.url)
        return embed

    @classmethod
    def report(
        cls,
        ctx_or_locale: Any,
        title: str,
        summary: str,
        is_loss: bool = False,
        bot_user: Any = None,
    ) -> 'RootEmbed':
        """Gabarit : Rapport PVP (Attaquant / Victime). Rouge si perte réelle, sinon Turquoise."""
        locale = ctx_or_locale if isinstance(ctx_or_locale, str) else None
        ctx = ctx_or_locale if not isinstance(ctx_or_locale, str) else None
        state = VisualState.CRITICAL_FAILURE if is_loss else VisualState.CONSULTATION
        embed = cls(
            ctx=ctx,
            locale=locale,
            state=state,
            title=title,
            content=summary,
            footer=build_footer_text(title),
        )
        if bot_user and hasattr(bot_user, 'display_avatar'):
            embed.set_footer(text=embed.footer.text, icon_url=bot_user.display_avatar.url)
        return embed

    async def send(
        self,
        ctx,
        view: discord.ui.View | None = None,
        file: discord.File | None = None,
        files: list[discord.File] | None = None,
    ) -> discord.Message:
        """
        Expédie l'embed en détectant s'il s'agit d'une Slash Command ou d'une commande à préfixe.
        Attache également la vue interactive (boutons) et fichiers si fournis.
        """
        kwargs: dict[str, Any] = {'embed': self, 'allowed_mentions': discord.AllowedMentions.none()}
        if view:
            kwargs['view'] = view
        if file:
            kwargs['file'] = file
        elif files:
            kwargs['files'] = files

        if getattr(ctx, 'interaction', None):
            msg = await ctx.respond(**kwargs)
            if view and hasattr(msg, 'message') and msg.message:
                view.message = msg.message
            elif view and isinstance(msg, discord.Message):
                view.message = msg
        else:
            msg = await ctx.send(**kwargs)
            if view:
                view.message = msg
        return msg

    async def send_to(
        self,
        target: Any,
        view: discord.ui.View | None = None,
        file: discord.File | None = None,
        files: list[discord.File] | None = None,
    ) -> discord.Message:
        """Envoie l'embed directement à un destinataire (Utilisateur Discord ou Salon)."""
        kwargs: dict[str, Any] = {'embed': self, 'allowed_mentions': discord.AllowedMentions.none()}
        if view:
            kwargs['view'] = view
        if file:
            kwargs['file'] = file
        elif files:
            kwargs['files'] = files

        msg = await target.send(**kwargs)
        if view:
            view.message = msg
        return msg

