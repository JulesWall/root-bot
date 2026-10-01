"""Commande /upgrade et !upgrade — Amélioration du niveau de pare-feu (Firewall).

Ce module permet d'accroître le niveau de protection général du réseau d'un joueur :
- Mécanique du Firewall :
  - Le Firewall constitue la première ligne de défense contre les cyber-attaques (`/hack`)
    et les sondes d'espionnage (`/scan`).
  - Chaque amélioration de niveau coûte un montant croissant en dollars (calculé par `game/rules.py`).
- Two-Phase Commit UI :
  1. Sans le paramètre `confirm` : le système présente un devis détaillé affichant
     le niveau actuel, le niveau suivant et le coût en USD, avec les boutons [Confirmer] et [Annuler].
  2. Avec confirmation explicite : le débit est prélevé et le niveau de pare-feu est incrémenté.
"""

import logging

import discord
from discord.ext import commands, tasks

import data
from commands.game.commandgame import BaseGameCog
from game.db.players import Player
from game.math_config import MathConfig
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.confirmation import Confirmation

logger = logging.getLogger(__name__)


def _is_confirm(val):
    """Vérifie si la valeur passée correspond à un accord explicite."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('confirm', 'true', 'yes', 'valider')
    return False


class Upgrade(BaseGameCog):
    """Cog gérant la montée en niveau du Firewall de défense."""

    def __init__(self, bot):
        self.bot = bot
        self.check_upgrades_loop.start()

    def cog_unload(self):
        """Arrête proprement la tâche périodique au déchargement du Cog."""
        self.check_upgrades_loop.cancel()

    @tasks.loop(seconds=30)
    async def check_upgrades_loop(self):
        """Boucle de vérification et livraison automatique des améliorations expirées."""
        try:
            delivered = await self.service.deliver_expired_upgrades()
            if delivered:
                logger.info("%d amélioration(s) de pare-feu livrée(s)", len(delivered))
                for item in delivered:
                    await self._notify_delivered(item)
        except Exception:
            logger.exception("Erreur lors de la vérification des améliorations expirées")

    @check_upgrades_loop.before_loop
    async def before_check_upgrades_loop(self):
        """Attend la synchronisation complète du bot avec Discord avant de démarrer la boucle."""
        await self.bot.wait_until_ready()

    async def _notify_delivered(self, item: dict):
        """Envoie un message privé à l'utilisateur pour l'informer de la fin de l'amélioration."""
        discord_id = item['discord_id']
        level = item['target_level']
        try:
            user = self.bot.get_user(discord_id)
            if not user:
                user = await self.bot.fetch_user(discord_id)
            if user:
                lang = await self.service.database.run(
                    lambda tx: Player.get_language(tx, discord_id),
                    readonly=True,
                ) or 'fr'
                content = text.get_for_lang(lang, 'g_upgrade_delivered_dm', level=level)
                from utils.root_embed import RootEmbed
                embed = RootEmbed.notification(lang, "Infrastructure", content)
                await user.send(embed=embed)
                logger.info("Notification MP envoyée à %s pour l'infrastructure niveau %s", discord_id, level)
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("Impossible d'envoyer le MP de livraison à %s (MP désactivés ou bloqués) : %s", discord_id, exc)
        except Exception:
            logger.exception("Erreur inattendue lors de la notification MP à %s", discord_id)

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='upgrade',
        description=EN['upgrade'],
        description_localizations={"fr": FR['upgrade']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def upgrade(
        self,
        ctx,
        confirm: discord.Option(
            str, choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False, default=None,
        ) = None,
    ):
        """Commande Slash /upgrade pour monter le pare-feu de niveau.

        Args:
            ctx: Contexte d'interaction.
            confirm (str, optional): Si renseigné à 'confirm', valide immédiatement l'achat.
        """
        await self._invoke(ctx, 'upgrade', confirm=_is_confirm(confirm))

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='upgrade', help=FR['upgrade'])
    async def prefix_upgrade(self, ctx, *args):
        """Commande préfixe !upgrade [confirm]."""
        confirm = any(_is_confirm(a) for a in args)
        await self._invoke(ctx, 'upgrade', confirm=confirm)

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Affiche le devis interactif ou la confirmation d'amélioration réussie."""
        usd = text.format_usd(result.get('usd_price', 0))

        if result.get('upgrade_quote'):
            # ── 1. Phase devis préliminaire avec boutons Confirmation ───────────
            next_lvl = result.get('next_level', 1)
            event_multiplier = MathConfig.get_event_firewall_multiplier(next_lvl)
            cur_lvl = result.get('current_level', 0)
            def_gain = result.get('defense_gain')
            if def_gain is None:
                def_gain = MathConfig.get_firewall_network_defense(next_lvl) - MathConfig.get_firewall_network_defense(cur_lvl)
            def_next = result.get('defense_next')
            if def_next is None:
                def_next = MathConfig.get_firewall_network_defense(next_lvl)

            def_gain_fmt = f"+{def_gain:,} DEF".replace(',', ' ')
            def_next_fmt = f"{def_next:,} DEF".replace(',', ' ')

            cur_usd = text.format_usd(result.get('current_usd', 0))
            rem_usd_val = result.get('remaining_usd', 0)
            is_fr = text.get_locale(ctx) == 'fr'

            if rem_usd_val < 0:
                missing = text.format_usd(abs(rem_usd_val))
                rem_usd = f"**{text.format_usd(rem_usd_val)} USD** ⚠️ *(Manque {missing} USD)*" if is_fr else f"**{text.format_usd(rem_usd_val)} USD** ⚠️ *(Missing {missing} USD)*"
            else:
                rem_usd = f"**{text.format_usd(rem_usd_val)} USD**"

            income_mult = next_lvl + 1
            cur_income_mult = cur_lvl + 1
            cur_multiplier = MathConfig.get_event_firewall_multiplier(cur_lvl)

            unlocked_modules = text.get(ctx, f'g_upgrade_modules_{next_lvl}')

            perks_list = []
            if next_lvl == 1:
                perks_list.append(text.get(ctx, 'g_upgrade_quote_perk_1'))
            elif next_lvl == 3:
                perks_list.append(text.get(ctx, 'g_upgrade_quote_scan_alert_3'))
            elif next_lvl == 4:
                perks_list.append(text.get(ctx, 'g_upgrade_quote_scan_alert_4'))
            elif next_lvl == 5:
                perks_list.append(text.get(ctx, 'g_upgrade_quote_perk_5'))

            perks_str = ""
            if perks_list:
                perks_str = "\n" + "\n".join(f"• {p}" for p in perks_list)

            content = text.get(
                ctx, 'g_upgrade_quote',
                current=cur_lvl,
                next=next_lvl,
                usd=usd,
                cur_usd=cur_usd,
                rem_usd=rem_usd,
                duration=result.get('duration', '5h'),
                multiplier=event_multiplier,
                cur_multiplier=cur_multiplier,
                defense_gain=def_gain_fmt,
                defense_next=def_next_fmt,
                income_mult=income_mult,
                cur_income_mult=cur_income_mult,
                unlocked_modules=unlocked_modules,
                perks=perks_str,
            )

            view = Confirmation(self._send, self.service, ctx, 'upgrade', {'confirm': True})
            await self._send_embed(ctx, 'upgrade', content, view=view)
        elif result.get('upgrade_started'):
            # ── 2. Amélioration en cours (différée) ─────────────────────────────
            content = text.get(
                ctx, 'g_upgrade_started',
                level=result.get('level', 1),
                usd=usd,
                timestamp=result.get('timestamp', 0),
            )
            await self._send_embed(ctx, 'upgrade', content)
        else:
            # ── 3. Amélioration immédiate (fallback legacy) ─────────────────────
            content = text.get(ctx, 'g_upgrade_success', level=result.get('level', 1), usd=usd)
            await self._send_embed(ctx, 'upgrade', content)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Upgrade(bot))
