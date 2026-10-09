"""Couche d'accès aux données pour les ventes automatiques de Rootium (RTM).

Permet aux joueurs de programmer des ordres de vente virtuelle de RTM
déclenchés lors de l'application d'un nouveau cours de marché (cycle de 15 min).
Chaque exécution utilise le cours réel validé et réutilise `Player.convert`
pour garantir l'intégrité comptable et l'idempotence exacte par cycle.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import logging
from typing import Optional

from game.game_error import GameError
from game.math_config import MathConfig
from game.db.players import Player, PlayerData

logger = logging.getLogger(__name__)


class AutoSellDB:
    """Gestion des règles et exécutions de vente automatique de RTM."""

    @staticmethod
    def list_for(tx, discord_id: int) -> list[dict]:
        """Retourne toutes les règles de vente automatique d'un joueur."""
        return tx.all(
            "SELECT id, discord_id, direction, threshold_usd, mode, amount_rtm, "
            "percent, max_rtm_per_run, cooldown_minutes, repeat_mode, enabled, "
            "last_run_at, created_at "
            "FROM rtm_auto_sell_rules WHERE discord_id = %s "
            "ORDER BY created_at ASC",
            (int(discord_id),),
        )

    @staticmethod
    def count_for(tx, discord_id: int) -> int:
        """Nombre total de règles configurées par un joueur."""
        row = tx.one(
            "SELECT COUNT(*) AS cnt FROM rtm_auto_sell_rules WHERE discord_id = %s",
            (int(discord_id),),
        )
        return int(row['cnt']) if row else 0

    @staticmethod
    def get(tx, rule_id: int, discord_id: Optional[int] = None) -> dict | None:
        """Récupère une règle par son identifiant (et vérifie optionnellement son propriétaire)."""
        if discord_id is not None:
            return tx.one(
                "SELECT * FROM rtm_auto_sell_rules WHERE id = %s AND discord_id = %s",
                (int(rule_id), int(discord_id)),
            )
        return tx.one("SELECT * FROM rtm_auto_sell_rules WHERE id = %s", (int(rule_id),))

    @staticmethod
    def create(
        tx,
        discord_id: int,
        direction: str,
        threshold_usd: Decimal | float | int | str,
        mode: str = 'fixed',
        amount_rtm: Decimal | float | int | str | None = None,
        percent: Decimal | float | int | str | None = None,
        max_rtm_per_run: Decimal | float | int | str | None = None,
        cooldown_minutes: int = 60,
        repeat_mode: str = 'once',
        current_price: Optional[Decimal] = None,
    ) -> dict:
        """Crée une nouvelle règle de vente automatique personnelle."""
        tx.acquire_lock(f"player:{int(discord_id)}")

        dir_clean = str(direction).lower().strip()
        if dir_clean not in ('above', 'below'):
            raise GameError('invalid_selection')

        mode_clean = str(mode).lower().strip()
        if mode_clean not in ('fixed', 'percent'):
            raise GameError('invalid_selection')

        repeat_clean = str(repeat_mode).lower().strip()
        if repeat_clean not in ('once', 'repeat'):
            raise GameError('invalid_selection')

        try:
            threshold = Decimal(str(threshold_usd).replace(',', '.'))
        except (InvalidOperation, TypeError, ValueError):
            raise GameError('invalid_amount')

        if threshold <= 0:
            raise GameError('invalid_amount')

        # Plafond de garde : seuil maximum à 10x le cours actuel
        if current_price and current_price > 0 and threshold > (current_price * Decimal('10')):
            raise GameError('market_auto_sell_threshold_too_high')

        market_cfg = MathConfig.market_settings()
        max_rules = int(market_cfg.get('auto_sell_max_per_player', 3))
        min_cooldown = int(market_cfg.get('auto_sell_min_cooldown_minutes', 15))

        cooldown = max(min_cooldown, int(cooldown_minutes or 60))

        current_count = AutoSellDB.count_for(tx, discord_id)
        if current_count >= max_rules:
            raise GameError('market_auto_sell_limit_reached')

        amount_rtm_val = None
        percent_val = None
        settings = MathConfig.load()
        rtm_places = int(settings.get('rtm_decimal_places', 5))
        rtm_quantum = Decimal('1').scaleb(-rtm_places)

        if mode_clean == 'fixed':
            if amount_rtm is None:
                raise GameError('invalid_amount')
            try:
                amt = Decimal(str(amount_rtm).replace(',', '.'))
            except (InvalidOperation, TypeError, ValueError):
                raise GameError('invalid_amount')
            if amt <= 0:
                raise GameError('invalid_amount')
            quantized = amt.quantize(rtm_quantum)
            if quantized != amt:
                raise GameError('invalid_amount')
            amount_rtm_val = amt
        elif mode_clean == 'percent':
            if percent is None:
                raise GameError('invalid_amount')
            try:
                pct = Decimal(str(percent).replace(',', '.').replace('%', ''))
            except (InvalidOperation, TypeError, ValueError):
                raise GameError('invalid_amount')
            if pct <= 0 or pct > 100:
                raise GameError('invalid_amount')
            percent_val = pct.quantize(Decimal('0.01'))

        max_cap_val = None
        if max_rtm_per_run is not None:
            try:
                cap = Decimal(str(max_rtm_per_run).replace(',', '.'))
                if cap > 0:
                    max_cap_val = cap.quantize(rtm_quantum)
            except (InvalidOperation, TypeError, ValueError):
                pass

        # Vérification des doublons stricts
        existing = tx.one(
            "SELECT id FROM rtm_auto_sell_rules "
            "WHERE discord_id = %s AND direction = %s AND threshold_usd = %s AND mode = %s",
            (int(discord_id), dir_clean, threshold, mode_clean),
        )
        if existing:
            raise GameError('market_auto_sell_duplicate')

        rule_id = tx.execute(
            "INSERT INTO rtm_auto_sell_rules "
            "(discord_id, direction, threshold_usd, mode, amount_rtm, percent, max_rtm_per_run, "
            "cooldown_minutes, repeat_mode, enabled, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, UTC_TIMESTAMP(6))",
            (
                int(discord_id), dir_clean, threshold, mode_clean, amount_rtm_val,
                percent_val, max_cap_val, cooldown, repeat_clean,
            ),
        )

        return {
            'id': rule_id,
            'discord_id': int(discord_id),
            'direction': dir_clean,
            'threshold_usd': threshold,
            'mode': mode_clean,
            'amount_rtm': amount_rtm_val,
            'percent': percent_val,
            'max_rtm_per_run': max_cap_val,
            'cooldown_minutes': cooldown,
            'repeat_mode': repeat_clean,
            'enabled': 1,
            'last_run_at': None,
        }

    @staticmethod
    def delete(tx, discord_id: int, rule_id: int) -> bool:
        """Supprime une règle de vente automatique appartenant au joueur."""
        tx.acquire_lock(f"player:{int(discord_id)}")
        rule = tx.one(
            "SELECT id FROM rtm_auto_sell_rules WHERE id = %s AND discord_id = %s",
            (int(rule_id), int(discord_id)),
        )
        if not rule:
            raise GameError('invalid_selection')

        tx.execute(
            "DELETE FROM rtm_auto_sell_rules WHERE id = %s AND discord_id = %s",
            (int(rule_id), int(discord_id)),
        )
        return True

    @staticmethod
    def toggle(tx, discord_id: int, rule_id: int, enabled: Optional[bool] = None) -> dict:
        """Active ou désactive une règle de vente automatique."""
        tx.acquire_lock(f"player:{int(discord_id)}")
        rule = tx.one(
            "SELECT * FROM rtm_auto_sell_rules WHERE id = %s AND discord_id = %s",
            (int(rule_id), int(discord_id)),
        )
        if not rule:
            raise GameError('invalid_selection')

        new_enabled = (0 if rule['enabled'] else 1) if enabled is None else (1 if enabled else 0)
        tx.execute(
            "UPDATE rtm_auto_sell_rules SET enabled = %s WHERE id = %s",
            (new_enabled, int(rule_id)),
        )
        rule['enabled'] = new_enabled
        return rule

    @staticmethod
    def get_due_rules(tx, current_price: Decimal, now_dt: datetime) -> list[dict]:
        """Retourne les règles éligibles à être exécutées compte tenu du cours et du cooldown."""
        rows = tx.all(
            "SELECT * FROM rtm_auto_sell_rules "
            "WHERE enabled = 1 "
            "  AND ("
            "    (direction = 'above' AND %s >= threshold_usd)"
            "    OR (direction = 'below' AND %s <= threshold_usd)"
            "  ) "
            "ORDER BY created_at ASC",
            (current_price, current_price),
        )

        due = []
        for r in rows:
            last_run = r.get('last_run_at')
            if last_run and r.get('repeat_mode') == 'repeat':
                cooldown_sec = int(r.get('cooldown_minutes') or 60) * 60
                if (now_dt - last_run).total_seconds() < cooldown_sec:
                    continue
            due.append(r)
        return due

    @staticmethod
    def execute_rule(
        tx,
        rule: dict,
        current_price: Decimal,
        market_ts: datetime,
        now_dt: datetime,
    ) -> dict | None:
        """Exécute une règle de vente automatique de façon atomique et idempotente.

        Retourne un dictionnaire de résultat si la vente a été effectuée,
        ou None si la règle n'a pas pu être exécutée (solde nul, déjà exécutée pour ce cycle).
        """
        rule_id = int(rule['id'])
        discord_id = int(rule['discord_id'])

        # 1. Vérification d'idempotence stricte pour ce cycle de marché
        existing_run = tx.one(
            "SELECT id FROM rtm_auto_sell_runs WHERE rule_id = %s AND market_ts = %s",
            (rule_id, market_ts),
        )
        if existing_run:
            return None

        # 2. Lecture du solde du joueur
        player = PlayerData.get(tx, discord_id)
        balance = Decimal(str(player.get('rootium') or 0))
        if balance <= Decimal('0'):
            return None

        # 3. Calcul du montant à vendre
        settings = MathConfig.load()
        rtm_places = int(settings.get('rtm_decimal_places', 5))
        rtm_quantum = Decimal('1').scaleb(-rtm_places)

        mode = rule.get('mode', 'fixed')
        if mode == 'percent':
            pct = Decimal(str(rule.get('percent') or 100))
            raw_amount = balance * (pct / Decimal('100'))
        else:
            raw_amount = Decimal(str(rule.get('amount_rtm') or 0))
            raw_amount = min(raw_amount, balance)

        max_cap = rule.get('max_rtm_per_run')
        if max_cap:
            cap = Decimal(str(max_cap))
            if cap > Decimal('0'):
                raw_amount = min(raw_amount, cap)

        amount = raw_amount.quantize(rtm_quantum)
        if amount <= Decimal('0') or amount > balance:
            return None

        # 4. Exécution de la conversion via le service métier standard Player.convert
        convert_result = Player.convert(
            tx,
            discord_id,
            amount=amount,
            confirm=True,
            rate=current_price,
        )

        # 5. Enregistrement immuable du run (idempotence garantie par la clé unique uq_rule_cycle)
        tx.execute(
            "INSERT INTO rtm_auto_sell_runs "
            "(rule_id, discord_id, market_ts, rate_usd, rtm_amount, usd_amount, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                rule_id,
                discord_id,
                market_ts,
                current_price,
                amount,
                convert_result['usd_amount'],
                now_dt,
            ),
        )

        # 6. Mise à jour de la règle (désactivation si repeat_mode == 'once', mise à jour de last_run_at)
        repeat_mode = rule.get('repeat_mode', 'once')
        if repeat_mode == 'once':
            tx.execute(
                "UPDATE rtm_auto_sell_rules SET last_run_at = %s, enabled = 0 WHERE id = %s",
                (now_dt, rule_id),
            )
        else:
            tx.execute(
                "UPDATE rtm_auto_sell_rules SET last_run_at = %s WHERE id = %s",
                (now_dt, rule_id),
            )

        return {
            'rule_id': rule_id,
            'discord_id': discord_id,
            'direction': rule['direction'],
            'threshold_usd': Decimal(str(rule['threshold_usd'])),
            'mode': mode,
            'repeat_mode': repeat_mode,
            'rate': current_price,
            'rtm_amount': amount,
            'usd_amount': convert_result['usd_amount'],
            'new_rootium': convert_result['new_rootium'],
            'new_dollars': convert_result['new_dollars'],
            'market_ts': market_ts,
        }

