"""
Persistance des annonces de marché PvP V2 (table `pvp_v2_market_listings`).

Cycle de vie d'une annonce :
  active -> sold (achat réussi)
  active -> cancelled (retrait par le vendeur)
  active -> expired (si expires_at est défini et passé)

L'item vendu est marqué reserved=1 dans sa table source à la création de l'annonce.
Il est libéré (reserved=0) ou transféré lors de la résolution.
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class PvpV2MarketDB:
    """Accès aux données pour la table pvp_v2_market_listings."""

    @staticmethod
    def get_active_listings(tx, item_type: str | None = None) -> list:
        """Retourne les annonces actives, optionnellement filtrées par type."""
        if item_type:
            return tx.all(
                """
                SELECT * FROM pvp_v2_market_listings
                WHERE status = 'active' AND item_type = %s
                ORDER BY listed_at DESC
                """,
                (str(item_type),),
            )
        return tx.all(
            "SELECT * FROM pvp_v2_market_listings WHERE status = 'active' ORDER BY listed_at DESC",
        )

    @staticmethod
    def get_by_seller(tx, seller_id: int) -> list:
        """Retourne toutes les annonces d'un vendeur (actives et clôturées)."""
        return tx.all(
            'SELECT * FROM pvp_v2_market_listings WHERE seller_id = %s ORDER BY listed_at DESC',
            (int(seller_id),),
        )

    @staticmethod
    def count_active_by_seller(tx, seller_id: int) -> int:
        """Compte les annonces actives d'un vendeur.

        Permet de vérifier le plafond de 5 annonces simultanées (décision 20).
        """
        row = tx.one(
            "SELECT COUNT(*) AS cnt FROM pvp_v2_market_listings WHERE seller_id = %s AND status = 'active'",
            (int(seller_id),),
        )
        return int(row['cnt']) if row else 0

    @staticmethod
    def get_by_id(tx, listing_id: int) -> dict | None:
        """Retourne une annonce par son ID."""
        return tx.one(
            'SELECT * FROM pvp_v2_market_listings WHERE id = %s',
            (int(listing_id),),
        )

    @staticmethod
    def create(
        tx,
        seller_id: int,
        item_type: str,
        item_id: int,
        price_usd,
    ) -> dict:
        """Crée une annonce de marché.

        Ne marque PAS l'item comme reserved= : c'est la responsabilité de l'appelant
        d'appeler set_reserved() sur le dépôt correspondant dans la même transaction.
        """
        price_d = Decimal(str(price_usd))
        listing_id = tx.execute(
            """
            INSERT INTO pvp_v2_market_listings
                (seller_id, item_type, item_id, price_usd, status, listed_at)
            VALUES (%s, %s, %s, %s, 'active', %s)
            """,
            (
                int(seller_id),
                str(item_type),
                int(item_id),
                price_d,
                tx.now,
            ),
        )
        return {
            'id': listing_id,
            'seller_id': int(seller_id),
            'item_type': str(item_type),
            'item_id': int(item_id),
            'price_usd': price_d,
            'status': 'active',
            'listed_at': tx.now,
            'expires_at': None,
            'sold_to': None,
            'sold_at': None,
        }

    @staticmethod
    def mark_sold(tx, listing_id: int, buyer_id: int) -> bool:
        """Marque une annonce comme vendue.

        Ne transfère pas l'item : l'appelant doit faire le transfert dans la même transaction.
        """
        affected = tx.execute(
            """
            UPDATE pvp_v2_market_listings
            SET status = 'sold', sold_to = %s, sold_at = %s
            WHERE id = %s AND status = 'active'
            """,
            (int(buyer_id), tx.now, int(listing_id)),
        )
        return bool(affected)

    @staticmethod
    def cancel(tx, listing_id: int, seller_id: int) -> dict | None:
        """Annule une annonce active par son vendeur.

        Retourne la ligne annulée (pour libérer l'item reserved) ou None si absent.
        """
        listing = tx.one(
            "SELECT * FROM pvp_v2_market_listings WHERE id = %s AND seller_id = %s AND status = 'active'",
            (int(listing_id), int(seller_id)),
        )
        if listing is None:
            return None
        tx.execute(
            "UPDATE pvp_v2_market_listings SET status = 'cancelled' WHERE id = %s",
            (int(listing_id),),
        )
        return listing

    @staticmethod
    def mark_expired(tx, listing_id: int) -> bool:
        """Marque une annonce comme expirée (tâche de nettoyage)."""
        affected = tx.execute(
            "UPDATE pvp_v2_market_listings SET status = 'expired' WHERE id = %s AND status = 'active'",
            (int(listing_id),),
        )
        return bool(affected)

    @staticmethod
    def get_expired_active(tx) -> list:
        """Retourne les annonces actives dont expires_at est passé.

        Utilisé par le worker de nettoyage.
        """
        return tx.all(
            "SELECT * FROM pvp_v2_market_listings WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at <= %s",
            (tx.now,),
        )

