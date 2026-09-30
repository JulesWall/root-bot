"""
Service métier du Marché Souterrain PvP V2 (table `pvp_v2_market_listings`).

Conforme aux spécifications de design/PVP_V2_DECISIONS.md (Décisions 5, 16, 20) :
- Vente d'actifs : logiciels compilés (origin != 'stolen'), patches non installés, dossiers de recherche offensifs.
- Réservation automatique de l'actif mis en vente pour empêcher l'usage concurrent.
- Achat : transfert atomique des fonds (USD), prélèvement d'une taxe marché de 5%, transfert de propriété.
- Retrait / Annulation : déverrouillage de l'actif par son vendeur.
- Plafond : 5 annonces actives simultanées par vendeur.
- Pas de revente pour les copies volées (resellable=0) ni les patches déjà installés.
"""

import logging
from decimal import Decimal

from game.db.players import PlayerData, UpdatePlayer
from game.db.pvp_v2_market import PvpV2MarketDB
from game.db.pvp_v2_patches import PvpV2PatchDB
from game.db.pvp_v2_research import PvpV2ResearchDB
from game.db.pvp_v2_software import PvpV2SoftwareDB
from game.game_error import GameError
from game.math_config import MathConfig

logger = logging.getLogger(__name__)


class PvpV2MarketService:
    """Service centralisant les règles de publication, achat et gestion du Marché PvP V2."""

    @classmethod
    def get_listings(cls, tx, item_type: str | None = None) -> list[dict]:
        """Retourne la liste des annonces actives enrichies des métadonnées des articles."""
        listings = PvpV2MarketDB.get_active_listings(tx, item_type=item_type)
        results = []
        for l in listings:
            enriched = cls._enrich_listing(tx, l)
            if enriched:
                results.append(enriched)
        return results

    @classmethod
    def get_my_listings(cls, tx, player_id: int) -> list[dict]:
        """Retourne les annonces d'un joueur."""
        listings = PvpV2MarketDB.get_by_seller(tx, int(player_id))
        results = []
        for l in listings:
            enriched = cls._enrich_listing(tx, l)
            if enriched:
                results.append(enriched)
        return results

    @classmethod
    def _enrich_listing(cls, tx, listing: dict) -> dict | None:
        """Enrichit une annonce avec les détails de l'item (famille, tier, fingerprint...)."""
        item_type = listing.get('item_type')
        item_id = int(listing.get('item_id', 0))

        item_info = {}
        if item_type == 'compiled_software':
            soft = PvpV2SoftwareDB.get_by_id(tx, item_id)
            if not soft:
                return None
            item_info = {
                'family': soft['family'],
                'tier': int(soft['tier']),
                'fingerprint': soft['fingerprint'],
                'origin': soft.get('origin', 'compiled'),
            }
        elif item_type == 'patch':
            patch = PvpV2PatchDB.get_by_id(tx, item_id)
            if not patch:
                return None
            item_info = {
                'family': patch['family'],
                'tier': 0,
                'fingerprint': patch['fingerprint'],
                'installed': bool(patch.get('installed', 0)),
            }
        elif item_type in ('research_folder', 'folder'):
            folder = PvpV2ResearchDB.get_by_id(tx, item_id)
            if not folder:
                return None
            item_info = {
                'family': folder['family'],
                'tier': int(folder['tier']),
                'fingerprint': folder['fingerprint'],
                'channel': folder.get('channel', 'offense'),
            }
        else:
            return None

        result = dict(listing)
        result.update(item_info)
        return result

    @classmethod
    def calculate_sell_quote(cls, tx, seller_id: int, item_type: str, item_id: int, price_usd: Decimal | float | int | str) -> dict:
        """Vérifie l'éligibilité et calcule le devis de mise en vente."""
        price_d = Decimal(str(price_usd)).quantize(Decimal('0.01'))
        mkt_cfg = MathConfig.get_pvp_v2_market()
        min_price = Decimal(str(mkt_cfg.get('min_price_usd', 1)))
        max_price_raw = mkt_cfg.get('max_price_usd')
        max_price = Decimal(str(max_price_raw)) if max_price_raw is not None else None
        fee_rate = Decimal(str(mkt_cfg.get('fee_rate', 0.05)))
        max_listings = int(mkt_cfg.get('max_active_listings_per_player', 5))

        if price_d < min_price:
            raise GameError('invalid_amount')
        if max_price is not None and price_d > max_price:
            raise GameError('invalid_amount')

        active_count = PvpV2MarketDB.count_active_by_seller(tx, int(seller_id))
        if active_count >= max_listings:
            raise GameError('market_max_listings', max=max_listings)

        # Vérification de propriété et d'état
        item = cls._verify_item_for_sale(tx, seller_id, item_type, item_id)

        fee_d = (price_d * fee_rate).quantize(Decimal('0.01'))
        net_d = price_d - fee_d

        return {
            'seller_id': int(seller_id),
            'item_type': item_type,
            'item_id': int(item_id),
            'family': item['family'],
            'tier': item.get('tier', 1),
            'fingerprint': item['fingerprint'],
            'price_usd': price_d,
            'fee_usd': fee_d,
            'net_usd': net_d,
        }

    @classmethod
    def create_listing(cls, tx, seller_id: int, item_type: str, item_id: int, price_usd: Decimal | float | int | str) -> dict:
        """Crée une annonce de vente sur le marché et verrouille l'item."""
        tx.acquire_lock(f"player_{int(seller_id)}")
        quote = cls.calculate_sell_quote(tx, seller_id, item_type, item_id, price_usd)

        # Réservation de l'item selon son type
        if item_type == 'compiled_software':
            PvpV2SoftwareDB.set_reserved(tx, int(item_id), True)
        elif item_type == 'patch':
            PvpV2PatchDB.set_reserved(tx, int(item_id), True)
        elif item_type in ('research_folder', 'folder'):
            # Les dossiers peuvent être marqués si champ présent
            pass

        listing = PvpV2MarketDB.create(
            tx,
            seller_id=int(seller_id),
            item_type=item_type,
            item_id=int(item_id),
            price_usd=quote['price_usd'],
        )

        return {
            'status': 'listed',
            'listing_id': listing['id'],
            'seller_id': int(seller_id),
            'item_type': item_type,
            'item_id': int(item_id),
            'family': quote['family'],
            'tier': quote['tier'],
            'fingerprint': quote['fingerprint'],
            'price_usd': quote['price_usd'],
            'fee_usd': quote['fee_usd'],
            'net_usd': quote['net_usd'],
        }

    @classmethod
    def calculate_buy_quote(cls, tx, buyer_id: int, listing_id: int) -> dict:
        """Calcule le devis d'achat d'une annonce."""
        listing = PvpV2MarketDB.get_by_id(tx, int(listing_id))
        if not listing or listing.get('status') != 'active':
            raise GameError('market_listing_not_found')

        seller_id = int(listing['seller_id'])
        if seller_id == int(buyer_id):
            raise GameError('market_self_buy')

        enriched = cls._enrich_listing(tx, listing)
        if not enriched:
            raise GameError('market_listing_not_found')

        buyer = PlayerData.get(tx, int(buyer_id))
        buyer_usd = Decimal(str(buyer.get('dollars', 0) or 0))
        price_usd = Decimal(str(listing.get('price_usd', 0) or 0))

        if buyer_usd < price_usd:
            raise GameError('insufficient_funds_usd', usd=f"{price_usd:,.2f}")

        return {
            'listing_id': int(listing_id),
            'buyer_id': int(buyer_id),
            'seller_id': seller_id,
            'item_type': listing['item_type'],
            'item_id': int(listing['item_id']),
            'family': enriched['family'],
            'tier': enriched.get('tier', 1),
            'fingerprint': enriched['fingerprint'],
            'price_usd': price_usd,
            'buyer_balance': buyer_usd,
            'balance_after': buyer_usd - price_usd,
        }

    @classmethod
    def buy_listing(cls, tx, buyer_id: int, listing_id: int) -> dict:
        """Exécute atomiquement l'achat d'une annonce."""
        listing = PvpV2MarketDB.get_by_id(tx, int(listing_id))
        if not listing or listing.get('status') != 'active':
            raise GameError('market_listing_not_found')

        seller_id = int(listing['seller_id'])
        if seller_id == int(buyer_id):
            raise GameError('market_self_buy')

        # Verrouillage ordonné des deux comptes
        p1, p2 = sorted([int(buyer_id), seller_id])
        tx.acquire_lock(f"player_{p1}")
        if p1 != p2:
            tx.acquire_lock(f"player_{p2}")

        # Re-vérification après verrouillage
        listing = PvpV2MarketDB.get_by_id(tx, int(listing_id))
        if not listing or listing.get('status') != 'active':
            raise GameError('market_listing_not_found')

        enriched = cls._enrich_listing(tx, listing)
        if not enriched:
            raise GameError('market_listing_not_found')

        buyer = PlayerData.get(tx, int(buyer_id))
        seller = PlayerData.get(tx, seller_id)

        buyer_usd = Decimal(str(buyer.get('dollars', 0) or 0))
        seller_usd = Decimal(str(seller.get('dollars', 0) or 0))
        price_usd = Decimal(str(listing.get('price_usd', 0) or 0))

        if buyer_usd < price_usd:
            raise GameError('insufficient_funds_usd', usd=f"{price_usd:,.2f}")

        mkt_cfg = MathConfig.get_pvp_v2_market()
        fee_rate = Decimal(str(mkt_cfg.get('fee_rate', 0.05)))
        fee_usd = (price_usd * fee_rate).quantize(Decimal('0.01'))
        net_usd = price_usd - fee_usd

        # Transferts financiers
        UpdatePlayer.set(tx, int(buyer_id), dollars=buyer_usd - price_usd)
        UpdatePlayer.set(tx, seller_id, dollars=seller_usd + net_usd)

        # Transfert de l'item
        item_type = listing['item_type']
        item_id = int(listing['item_id'])

        if item_type == 'compiled_software':
            PvpV2SoftwareDB.transfer_ownership(tx, item_id, int(buyer_id))
        elif item_type == 'patch':
            # Crée une copie patch pour l'acheteur et supprime la ligne du vendeur
            PvpV2PatchDB.create(tx, int(buyer_id), enriched['family'], enriched['fingerprint'])
            PvpV2PatchDB.delete(tx, item_id, seller_id)
        elif item_type in ('research_folder', 'folder'):
            # Transfert de propriété du dossier
            tx.execute(
                'UPDATE pvp_v2_research_folders SET owner_id = %s WHERE id = %s',
                (int(buyer_id), item_id),
            )

        # Clôture de l'annonce
        PvpV2MarketDB.mark_sold(tx, int(listing_id), int(buyer_id))

        return {
            'status': 'sold',
            'listing_id': int(listing_id),
            'buyer_id': int(buyer_id),
            'seller_id': seller_id,
            'item_type': item_type,
            'item_id': item_id,
            'family': enriched['family'],
            'tier': enriched.get('tier', 1),
            'fingerprint': enriched['fingerprint'],
            'price_usd': price_usd,
            'fee_usd': fee_usd,
            'net_usd': net_usd,
            'new_buyer_balance': buyer_usd - price_usd,
            'new_seller_balance': seller_usd + net_usd,
        }

    @classmethod
    def cancel_listing(cls, tx, seller_id: int, listing_id: int) -> dict:
        """Annule une annonce active et libère l'item réservé."""
        tx.acquire_lock(f"player_{int(seller_id)}")
        listing = PvpV2MarketDB.get_by_id(tx, int(listing_id))
        if not listing or listing.get('status') != 'active':
            raise GameError('market_listing_not_found')

        if int(listing['seller_id']) != int(seller_id):
            raise GameError('market_not_owner')

        item_type = listing['item_type']
        item_id = int(listing['item_id'])

        if item_type == 'compiled_software':
            PvpV2SoftwareDB.set_reserved(tx, item_id, False)
        elif item_type == 'patch':
            PvpV2PatchDB.set_reserved(tx, item_id, False)

        PvpV2MarketDB.cancel(tx, int(listing_id), int(seller_id))

        return {
            'status': 'cancelled',
            'listing_id': int(listing_id),
            'seller_id': int(seller_id),
            'item_type': item_type,
            'item_id': item_id,
        }

    @classmethod
    def _verify_item_for_sale(cls, tx, seller_id: int, item_type: str, item_id: int) -> dict:
        """Vérifie que l'item existe, appartient au vendeur et n'est pas réservé ni exclu de la revente."""
        if item_type == 'compiled_software':
            soft = PvpV2SoftwareDB.get_by_id(tx, int(item_id))
            if not soft or int(soft.get('owner_id', 0)) != int(seller_id):
                raise GameError('market_listing_not_found')
            if bool(soft.get('reserved')):
                raise GameError('market_item_reserved')
            if not bool(soft.get('resellable', 1)) or soft.get('origin') == 'stolen':
                raise GameError('market_not_resellable')
            return soft
        elif item_type == 'patch':
            patch = PvpV2PatchDB.get_by_id(tx, int(item_id))
            if not patch or int(patch.get('owner_id', 0)) != int(seller_id):
                raise GameError('market_listing_not_found')
            if bool(patch.get('reserved')):
                raise GameError('market_item_reserved')
            if bool(patch.get('installed')):
                raise GameError('market_not_resellable')
            return patch
        elif item_type in ('research_folder', 'folder'):
            folder = PvpV2ResearchDB.get_by_id(tx, int(item_id))
            if not folder or int(folder.get('owner_id', 0)) != int(seller_id):
                raise GameError('market_listing_not_found')
            if folder.get('channel') == 'defense':
                raise GameError('market_not_resellable')
            return folder
        else:
            raise GameError('invalid_selection')
