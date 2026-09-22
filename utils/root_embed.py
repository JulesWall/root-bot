"""
Composant d'affichage standardisé des embeds Discord pour toutes les commandes Root.

Garantit l'homogénéité visuelle de l'ensemble du bot :
- Palette de couleurs dédiée par type d'action (vert pour achat/upgrade, or pour réputation/top).
- Titres localisés résolus automatiquement selon la langue de l'utilisateur.
- Horodatage UTC et pied de page officiel 'Root OS • Système sécurisé' avec l'avatar du bot.
- Méthode send() universelle gérant indifféremment les contextes Slash (ctx.respond) et textuels (ctx.send).
"""

import discord

from lang import game_en, game_fr
from utils import text


class RootEmbed(discord.Embed):
    """Embed Discord standardisé avec footer, couleur thématique et horodatage unifiés."""

    # Charte chromatique thématique par type d'opération de jeu conservée
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
    }

    def __init__(self, ctx, action: str, content: str):
        """
        Construit l'embed avec titre dynamique et couleur appropriée.
        
        Args:
            ctx: Contexte de la commande (pour la résolution de la langue).
            action: Identifiant de l'action pour la couleur et le titre (ex: 'buy', 'upgrade').
            content: Corps du message / description formatée en markdown.
        """
        action_key = 'act_' + action
        lang_module = game_fr if text.get_locale(ctx) == 'fr' else game_en
        action_title = lang_module.labels.get(action_key, action.replace('_', ' ').title())
        title = text.get(ctx, 'g_title', action=action_title)

        super().__init__(
            title=title,
            description=content,
            color=self.COLORS.get(action, discord.Color.from_rgb(0, 220, 200)),
            timestamp=discord.utils.utcnow(),
        )
        bot_user = getattr(ctx, 'bot', None) and getattr(ctx.bot, 'user', None)
        icon_url = bot_user.display_avatar.url if bot_user and hasattr(bot_user, 'display_avatar') else None
        self.set_footer(text='Root OS • Système sécurisé', icon_url=icon_url)

    async def send(self, ctx, view: discord.ui.View | None = None) -> discord.Message:
        """
        Expédie l'embed en détectant s'il s'agit d'une Slash Command ou d'une commande à préfixe.
        Attache également la vue interactive (boutons) si fournie et enregistre la référence du message.
        """
        kwargs = {'embed': self, 'allowed_mentions': discord.AllowedMentions.none()}
        if view:
            kwargs['view'] = view
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

