"""Commande /market et !market — Marché souterrain de logiciels, patches et dossiers (PvP V2).

Mécanique conforme à design/PVP_V2_DECISIONS.md (Décisions 5, 16, 20) :
- Vente d'actifs : logiciels compilés (origin != 'stolen'), patches non installés, dossiers de recherche offensifs.
- Achat : transfert atomique des USD, taxe marché de 5%, transfert de propriété de l'actif.
- Réservation automatique de l'actif à la création d'annonce pour empêcher l'usage concurrent.
- Annulation : retrait de l'annonce et déverrouillage de l'actif par son propriétaire.
- Plafond : maximum 5 annonces simultanées par vendeur.
"""

import logging
from decimal import Decimal

import discord
from discord.ext import commands

import data
from commands.game.commandgame import BaseGameCog
from game.game_error import GameError
from game.math_config import MathConfig
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.confirmation import Confirmation
from utils.emojis import get_root_emojis
from utils.root_embed import RootEmbed

logger = logging.getLogger(__name__)


def _is_confirm(val) -> bool:
    """Détermine si un argument représente une confirmation explicite."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('confirm', 'true', 'yes', 'valider')
    return False


class Market(BaseGameCog):
    """Cog orchestrant le marché souterrain (/market et !market — alias !mkt)."""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash Command /market ─────────────────────────────────────────────────
    market_group = discord.SlashCommandGroup(
        name='market',
        description="Underground Software & Patch Marketplace",
        description_localizations={"fr": "Marché Souterrain de logiciels et correctifs"},
        guild_ids=data.GUILD_WHITELIST or None,
    )

    @market_group.command(
        name='list',
        description="Browse available marketplace listings",
        description_localizations={"fr": "Parcourir les annonces disponibles sur le marché"},
    )
    async def slash_market_list(
        self,
        ctx,
        item_type: discord.Option(
            str,
            choices=['compiled_software', 'patch', 'research_folder'],
            description="Filter by item type",
            description_localizations={"fr": "Filtrer par type d'article"},
            required=False,
            default=None,
        ) = None,
    ):
        """Affiche les annonces actives du marché."""
        await self._invoke(ctx, 'pvp_v2_market_list', item_type=item_type)

    @market_group.command(
        name='mine',
        description="View your own active marketplace listings",
        description_localizations={"fr": "Consulter vos annonces actives en cours"},
    )
    async def slash_market_mine(self, ctx):
        """Affiche les annonces du joueur."""
        await self._invoke(ctx, 'pvp_v2_market_mine')

    @market_group.command(
        name='sell',
        description="List software or patch for sale",
        description_localizations={"fr": "Mettre en vente un logiciel ou correctif"},
    )
    async def slash_market_sell(
        self,
        ctx,
        item_type: discord.Option(
            str,
            choices=['compiled_software', 'patch', 'research_folder'],
            description="Type of item to sell",
            description_localizations={"fr": "Type d'article à vendre"},
            required=True,
        ),
        item_id: discord.Option(
            int,
            description="ID of the item in your library",
            description_localizations={"fr": "ID de l'article dans votre bibliothèque"},
            required=True,
        ),
        price: discord.Option(
            str,
            description="Selling price in USD (e.g. 500)",
            description_localizations={"fr": "Prix de vente en USD (ex: 500)"},
            required=True,
        ),
        confirm: discord.Option(
            str,
            choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False,
            default=None,
        ) = None,
    ):
        """Met en vente un article sur le marché."""
        try:
            price_val = Decimal(str(price).replace('$', '').replace('usd', '').strip())
        except Exception:
            raise GameError('invalid_amount')

        action = 'pvp_v2_market_sell_start' if _is_confirm(confirm) else 'pvp_v2_market_sell_quote'
        await self._invoke(
            ctx,
            action,
            item_type=item_type,
            item_id=item_id,
            price_usd=price_val,
        )

    @market_group.command(
        name='buy',
        description="Purchase an item from the marketplace",
        description_localizations={"fr": "Acheter un article mis en vente sur le marché"},
    )
    async def slash_market_buy(
        self,
        ctx,
        listing_id: discord.Option(
            int,
            description="ID of the listing to purchase",
            description_localizations={"fr": "ID de l'annonce à acheter"},
            required=True,
        ),
        confirm: discord.Option(
            str,
            choices=['confirm'],
            description=desc['confirm'],
            description_localizations=desc_loc['confirm'],
            required=False,
            default=None,
        ) = None,
    ):
        """Achète une annonce active sur le marché."""
        action = 'pvp_v2_market_buy_start' if _is_confirm(confirm) else 'pvp_v2_market_buy_quote'
        await self._invoke(ctx, action, listing_id=listing_id)

    @market_group.command(
        name='cancel',
        description="Cancel one of your active marketplace listings",
        description_localizations={"fr": "Annuler l'une de vos annonces et déverrouiller l'article"},
    )
    async def slash_market_cancel(
        self,
        ctx,
        listing_id: discord.Option(
            int,
            description="ID of the listing to cancel",
            description_localizations={"fr": "ID de l'annonce à annuler"},
            required=True,
        ),
    ):
        """Annule une annonce du vendeur."""
        await self._invoke(ctx, 'pvp_v2_market_cancel', listing_id=listing_id)

    # ── Commande Préfixe !market ──────────────────────────────────────────────
    @commands.command(name='market', aliases=['mkt'], help="Accéder au Marché Souterrain")
    async def prefix_market(self, ctx, *args):
        """Commande préfixe !market [list|mine|sell|buy|cancel] ..."""
        await self._prefetch_lang(ctx.author.id)

        if not args or args[0].lower() in ('list', 'ls'):
            itype = args[1] if len(args) > 1 else None
            return await self._invoke(ctx, 'pvp_v2_market_list', item_type=itype)

        subcmd = args[0].lower()

        if subcmd in ('mine', 'mes-annonces'):
            return await self._invoke(ctx, 'pvp_v2_market_mine')

        if subcmd == 'buy':
            if len(args) < 2:
                prefix = getattr(ctx, 'prefix', None) or '!'
                return await ctx.send(f"> ⚠️ **Syntaxe** : `{prefix}market buy <id> [confirm]`")
            lid = int(args[1])
            is_confirm = any(_is_confirm(a) for a in args[2:])
            action = 'pvp_v2_market_buy_start' if is_confirm else 'pvp_v2_market_buy_quote'
            return await self._invoke(ctx, action, listing_id=lid)

        if subcmd == 'cancel':
            if len(args) < 2:
                prefix = getattr(ctx, 'prefix', None) or '!'
                return await ctx.send(f"> ⚠️ **Syntaxe** : `{prefix}market cancel <id>`")
            lid = int(args[1])
            return await self._invoke(ctx, 'pvp_v2_market_cancel', listing_id=lid)

        if subcmd == 'sell':
            # Syntaxe : !market sell <type> <id> <prix> [confirm]
            if len(args) < 4:
                prefix = getattr(ctx, 'prefix', None) or '!'
                return await ctx.send(f"> ⚠️ **Syntaxe** : `{prefix}market sell <software|patch|folder> <item_id> <prix> [confirm]`")

            raw_type = args[1].lower()
            type_map = {
                'software': 'compiled_software',
                'soft': 'compiled_software',
                'compiled_software': 'compiled_software',
                'patch': 'patch',
                'folder': 'research_folder',
                'research_folder': 'research_folder',
            }
            item_type = type_map.get(raw_type)
            if not item_type:
                raise GameError('invalid_selection')

            item_id = int(args[2])
            try:
                price_val = Decimal(str(args[3]).replace('$', '').replace('usd', '').strip())
            except Exception:
                raise GameError('invalid_amount')

            is_confirm = any(_is_confirm(a) for a in args[4:])
            action = 'pvp_v2_market_sell_start' if is_confirm else 'pvp_v2_market_sell_quote'
            return await self._invoke(
                ctx,
                action,
                item_type=item_type,
                item_id=item_id,
                price_usd=price_val,
            )

        prefix = getattr(ctx, 'prefix', None) or '!'
        return await ctx.send(text.get(ctx, 'g_error_market_usage', prefix=prefix))

    # ── Rendu Visuel ──────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Rendu visuel stylisé pour les opérations du marché."""
        e = get_root_emojis(ctx)

        family_display_names = {
            'hostile_miner': 'Hostile Miner',
            'ransomware': 'Ransomware',
            'currency_theft': 'Vol de Devises',
            'saturation': 'Saturation RAM',
            'espionage': 'Espionnage',
            'software_theft': 'Vol de Logiciel',
        }

        # 1. Liste des annonces du marché
        if method in ('pvp_v2_market_list', 'pvp_v2_market_mine'):
            is_mine = (method == 'pvp_v2_market_mine')
            header = text.get(ctx, 'g_pvp_v2_market_my_listings_header' if is_mine else 'g_pvp_v2_market_list_header')

            listings = result if isinstance(result, list) else []
            if not listings:
                embed_content = f"{header}\n\n{text.get(ctx, 'g_pvp_v2_market_empty')}"
                return await self._send_embed(ctx, 'market', embed_content)

            lines = []
            for l in listings:
                lid = l.get('id')
                fam_raw = l.get('family', '')
                fam_lbl = family_display_names.get(fam_raw, fam_raw.replace('_', ' ').title())
                tier = l.get('tier', 1)
                fp = l.get('fingerprint', '????')
                price = Decimal(str(l.get('price_usd', 0)))
                seller = l.get('seller_id')
                itype = l.get('item_type')

                type_icon = "💻" if itype == 'compiled_software' else ("🛡️" if itype == 'patch' else "📁")
                tier_str = f" T{tier}" if tier > 0 else ""
                lines.append(
                    f"> • `#{lid}` {type_icon} **{fam_lbl}**{tier_str} `[{fp}]` — **{price:,.2f} USD** · <@{seller}>"
                )

            body = "\n".join(lines)
            market_intro = text.get(ctx, 'g_pvp_v2_market_header')
            embed_content = f"{market_intro}\n\n{header}\n{body}\n\n💡 *Achetez un article avec `/market buy <id>` ou `!market buy <id>`*"
            await self._send_embed(ctx, 'market', embed_content)

        # 2. Devis de mise en vente
        elif method == 'pvp_v2_market_sell_quote':
            fam_raw = result.get('family', '')
            fam_lbl = family_display_names.get(fam_raw, fam_raw.replace('_', ' ').title())
            tier = result.get('tier', 1)
            fp = result.get('fingerprint', '????')
            price = result.get('price_usd', Decimal('0'))
            fee = result.get('fee_usd', Decimal('0'))
            net = result.get('net_usd', Decimal('0'))

            body = text.get(
                ctx,
                'g_pvp_v2_market_sell_quote_body',
                family_label=fam_lbl,
                tier=tier,
                fingerprint=fp,
                price=f"{price:,.2f}",
                fee=f"{fee:,.2f}",
                net=f"{net:,.2f}",
            )
            header = text.get(ctx, 'g_pvp_v2_market_sell_quote_header')
            embed_content = f"{header}\n\n{body}"

            confirmation_args = {
                'item_type': result.get('item_type'),
                'item_id': result.get('item_id'),
                'price_usd': str(price),
            }
            view = Confirmation(self._send, self.service, ctx, 'pvp_v2_market_sell_start', confirmation_args)
            await self._send_embed(ctx, 'market', embed_content, view=view)

        # 3. Création réussie d'une annonce
        elif method == 'pvp_v2_market_sell_start':
            fam_raw = result.get('family', '')
            fam_lbl = family_display_names.get(fam_raw, fam_raw.replace('_', ' ').title())
            tier = result.get('tier', 1)
            fp = result.get('fingerprint', '????')
            price = result.get('price_usd', Decimal('0'))
            lid = result.get('listing_id')

            content = text.get(
                ctx,
                'g_pvp_v2_market_sell_started',
                family_label=fam_lbl,
                tier=tier,
                fingerprint=fp,
                price=f"{price:,.2f}",
                listing_id=lid,
            )
            await self._send_embed(ctx, 'market', content)

        # 4. Devis d'achat
        elif method == 'pvp_v2_market_buy_quote':
            fam_raw = result.get('family', '')
            fam_lbl = family_display_names.get(fam_raw, fam_raw.replace('_', ' ').title())
            tier = result.get('tier', 1)
            fp = result.get('fingerprint', '????')
            price = result.get('price_usd', Decimal('0'))
            seller_id = result.get('seller_id')
            after = result.get('balance_after', Decimal('0'))

            body = text.get(
                ctx,
                'g_pvp_v2_market_buy_quote_body',
                family_label=fam_lbl,
                tier=tier,
                fingerprint=fp,
                seller_id=seller_id,
                price=f"{price:,.2f}",
                balance_after=f"{after:,.2f}",
            )
            header = text.get(ctx, 'g_pvp_v2_market_buy_quote_header')
            embed_content = f"{header}\n\n{body}"

            confirmation_args = {'listing_id': result.get('listing_id')}
            view = Confirmation(self._send, self.service, ctx, 'pvp_v2_market_buy_start', confirmation_args)
            await self._send_embed(ctx, 'market', embed_content, view=view)

        # 5. Achat réussi
        elif method == 'pvp_v2_market_buy_start':
            fam_raw = result.get('family', '')
            fam_lbl = family_display_names.get(fam_raw, fam_raw.replace('_', ' ').title())
            tier = result.get('tier', 1)
            fp = result.get('fingerprint', '????')
            price = result.get('price_usd', Decimal('0'))
            new_bal = result.get('new_buyer_balance', Decimal('0'))
            seller_id = result.get('seller_id')
            net = result.get('net_usd', Decimal('0'))

            content = text.get(
                ctx,
                'g_pvp_v2_market_buy_success',
                family_label=fam_lbl,
                tier=tier,
                fingerprint=fp,
                price=f"{price:,.2f}",
                new_balance=f"{new_bal:,.2f}",
            )
            await self._send_embed(ctx, 'market', content)

            # Notifier le vendeur en DM
            try:
                seller_user = self.bot.get_user(seller_id) or await self.bot.fetch_user(seller_id)
                if seller_user:
                    seller_row = await self.service.database.run(
                        lambda tx: tx.one('SELECT lang FROM players WHERE discord_id = %s', (seller_id,)),
                        readonly=True,
                    )
                    slang = (seller_row and seller_row.get('lang')) or 'fr'
                    dm_msg = text.get_for_lang(
                        slang,
                        'g_pvp_v2_market_sold_dm',
                        family_label=fam_lbl,
                        tier=tier,
                        fingerprint=fp,
                        listing_id=result.get('listing_id'),
                        net=f"{net:,.2f}",
                        new_balance=f"{result.get('new_seller_balance', Decimal('0')):,.2f}",
                    )
                    await seller_user.send(dm_msg)
            except Exception:
                logger.warning("Impossible d'envoyer la notification de vente au joueur %s", seller_id)

        # 6. Annulation réussie
        elif method == 'pvp_v2_market_cancel':
            lid = result.get('listing_id')
            content = text.get(ctx, 'g_pvp_v2_market_cancel_success', listing_id=lid)
            await self._send_embed(ctx, 'market', content)


def setup(bot):
    """Point d'entrée standard de chargement du Cog Market."""
    bot.add_cog(Market(bot))
