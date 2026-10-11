"""Couche d'accès aux données pour les alertes de cours du Rootium (RTM).

Permet aux joueurs de surveiller le cours du RTM (seuil à la hausse ou à la baisse).
Évalué de façon idempotente et transactionnelle à chaque cycle de marché (15 min).
"""

from datetime import datetime
from decimal import Decimal
import logging
from typing import Optional

from game.game_error import GameError
from game.math_config import MathConfig

logger = logging.getLogger(__name__)


class MarketAlerts:
    """Gestion des alertes de cours personnelles dans la table rtm_price_alerts."""

    @staticmethod
    def list_for(tx, discord_id: int) -> list[dict]:
        """Retourne toutes les alertes du joueur, triées par sens et seuil."""
        return tx.all(
            "SELECT id, discord_id, direction, threshold_usd, enabled, created_at "
            "FROM rtm_price_alerts WHERE discord_id = %s "
            "ORDER BY direction ASC, threshold_usd ASC",
            (int(discord_id),),
        )

    @staticmethod
    def count_for(tx, discord_id: int) -> int:
        """Nombre total d'alertes configurées par le joueur."""
        row = tx.one(
            "SELECT COUNT(*) AS cnt FROM rtm_price_alerts WHERE discord_id = %s",
            (int(discord_id),),
        )
        return int(row['cnt']) if row else 0

    @staticmethod
    def create(
        tx,
        discord_id: int,
        direction: str,
        threshold_usd: Decimal | float | int | str,
        cooldown_minutes: Optional[int] = None,
        current_price: Optional[Decimal] = None,
    ) -> dict:
        """Crée une nouvelle alerte personnelle (à usage unique)."""
        tx.acquire_lock(f"player:{int(discord_id)}")

        dir_clean = str(direction).lower().strip()
        if dir_clean not in ('above', 'below'):
            raise GameError('invalid_selection')

        try:
            threshold = Decimal(str(threshold_usd))
        except Exception:
            raise GameError('invalid_amount')

        if threshold <= 0:
            raise GameError('invalid_amount')

        # Plafond de garde : seuil maximum à 10x le cours si fourni
        if current_price and current_price > 0 and threshold > (current_price * Decimal('10')):
            raise GameError('market_alert_threshold_too_high')

        market_cfg = MathConfig.market_settings()
        max_alerts = int(market_cfg.get('alerts_max_per_player', 5))

        current_count = MarketAlerts.count_for(tx, discord_id)
        if current_count >= max_alerts:
            raise GameError('market_alert_limit_reached')

        existing = tx.one(
            "SELECT id FROM rtm_price_alerts WHERE discord_id = %s AND direction = %s AND threshold_usd = %s",
            (int(discord_id), dir_clean, threshold),
        )
        if existing:
            raise GameError('market_alert_duplicate')

        alert_id = tx.execute(
            "INSERT INTO rtm_price_alerts "
            "(discord_id, direction, threshold_usd, enabled, created_at) "
            "VALUES (%s, %s, %s, 1, UTC_TIMESTAMP(6))",
            (int(discord_id), dir_clean, threshold),
        )

        return {
            'id': alert_id,
            'discord_id': int(discord_id),
            'direction': dir_clean,
            'threshold_usd': threshold,
            'enabled': 1,
        }

    @staticmethod
    def delete(tx, discord_id: int, alert_id: int) -> bool:
        """Supprime une alerte appartenant au joueur."""
        tx.acquire_lock(f"player:{int(discord_id)}")
        row = tx.one(
            "SELECT id FROM rtm_price_alerts WHERE id = %s AND discord_id = %s",
            (int(alert_id), int(discord_id)),
        )
        if not row:
            return False
        tx.execute(
            "DELETE FROM rtm_price_alerts WHERE id = %s AND discord_id = %s",
            (int(alert_id), int(discord_id)),
        )
        return True

    @staticmethod
    def toggle(tx, discord_id: int, alert_id: int, enabled: Optional[bool] = None) -> dict:
        """Active ou désactive une alerte."""
        tx.acquire_lock(f"player:{int(discord_id)}")
        row = tx.one(
            "SELECT * FROM rtm_price_alerts WHERE id = %s AND discord_id = %s",
            (int(alert_id), int(discord_id)),
        )
        if not row:
            raise GameError('not_found')

        new_enabled = int(enabled) if enabled is not None else (0 if row['enabled'] else 1)

        tx.execute(
            "UPDATE rtm_price_alerts SET enabled = %s WHERE id = %s AND discord_id = %s",
            (new_enabled, int(alert_id), int(discord_id)),
        )
        row['enabled'] = new_enabled
        return row

    @staticmethod
    def evaluate_and_trigger(tx, current_price: Decimal, now: Optional[datetime] = None) -> list[dict]:
        """Évalue l'ensemble des alertes actives et supprime immédiatement celles déclenchées."""
        price = Decimal(str(current_price))

        # Déclenchement des alertes dont le seuil est franchi
        triggered = tx.all(
            "SELECT id, discord_id, direction, threshold_usd "
            "FROM rtm_price_alerts "
            "WHERE enabled = 1 "
            "AND ("
            "  (direction = 'above' AND %s >= threshold_usd) "
            "  OR (direction = 'below' AND %s <= threshold_usd)"
            ")",
            (price, price),
        )

        if not triggered:
            return []

        # Suppression immédiate de la BDD (usage unique) pour éviter tout spam
        for alert in triggered:
            tx.execute(
                "DELETE FROM rtm_price_alerts WHERE id = %s",
                (int(alert['id']),),
            )

        return triggered

