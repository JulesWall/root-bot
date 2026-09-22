"""Commande /rep et !rep — Attribution de points de réputation à un autre joueur.

Ce module permet la reconnaissance sociale entre joueurs :
- Chaque joueur peut donner de la réputation à ses pairs.
- Un délai de rechargement (cooldown de 24h) est appliqué au niveau de la couche métier (`game/db/players.py`).
- Les points de réputation influencent directement le classement `/top` (catégorie réputation).
"""

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.check import Check
from utils.logger import Logger


class Rep(BaseGameCog):
    """Cog gérant le système d'honneur et de réputation inter-joueurs."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='rep',
        description=EN['rep'],
        description_localizations={"fr": FR['rep']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def rep(self, ctx, target: discord.User):
        """Commande Slash /rep pour accorder un point de réputation.

        Args:
            ctx: Contexte d'interaction.
            target (discord.User): Joueur receveur du point d'honneur.
        """
        ctx._rep_target = target
        is_op = await Check().is_op(self.bot, ctx.author.id)
        await self._invoke(ctx, 'reputation', target=target.id, bypass_cooldown=is_op)

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='rep', aliases=['reputation'], help=FR['rep'])
    async def prefix_rep(self, ctx, target: str = None):
        """Commande préfixe !rep <@cible>.

        Args:
            ctx: Contexte de commande.
            target: Mention ou identifiant du joueur receveur du point d'honneur.
        """
        if not target:
            await self._prefetch_lang(ctx.author.id)
            prefix = getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')
            return await ctx.send(text.get(ctx, 'g_error_rep_usage', prefix=prefix))

        try:
            resolved_user = await commands.UserConverter().convert(ctx, target)
        except commands.BadArgument:
            await self._prefetch_lang(ctx.author.id)
            prefix = getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')
            return await ctx.send(text.get(ctx, 'g_error_rep_usage', prefix=prefix))

        ctx._rep_target = resolved_user
        is_op = await Check().is_op(self.bot, ctx.author.id)
        await self._invoke(ctx, 'reputation', target=resolved_user.id, bypass_cooldown=is_op)

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Formate et envoie le message de succès d'attribution de réputation."""
        from utils.language_manager import fetch_user_language

        points = result.get('points', 1)
        recipient_id = result.get('recipient')
        content = text.get(
            ctx, 'g_reputation_success',
            points=points,
            recipient=recipient_id,
        )

        checks = Check()
        granted_beta = False
        if checks.beta_enabled() and recipient_id:
            if await checks.has_beta_access(self.bot, ctx.author.id):
                granted_beta = checks.grant_beta_access(recipient_id)

        if granted_beta:
            content += text.get(ctx, 'g_reputation_beta_granted', recipient=recipient_id)

        kwargs = {'allowed_mentions': discord.AllowedMentions.none()}
        if getattr(ctx, 'interaction', None):
            await ctx.respond(content, **kwargs)
        else:
            await ctx.send(content, **kwargs)

        # Résolution du destinataire
        target = getattr(ctx, '_rep_target', None)
        if not target and recipient_id:
            target = self.bot.get_user(recipient_id)
            if not target:
                try:
                    target = await self.bot.fetch_user(recipient_id)
                except Exception:
                    target = None

        if target:
            # Envoi du message privé au bénéficiaire
            try:
                target_lang = await fetch_user_language(target.id) or "en"
                server_str = ctx.guild.name if ctx.guild else "Serveur"
                dm_content = text.get_for_lang(
                    target_lang,
                    'g_reputation_dm_received',
                    giver=ctx.author.display_name,
                    points=points,
                    server=server_str,
                )
                if granted_beta:
                    dm_content += "\n" + text.get_for_lang(target_lang, 'g_reputation_dm_beta_granted')
                await target.send(dm_content)
            except Exception:
                pass

            await Logger(self.bot).log_reputation(
                ctx,
                giver=ctx.author,
                recipient=target,
                points=points,
            )


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Rep(bot))
