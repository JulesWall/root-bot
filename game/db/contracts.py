"""
Gestion de la persistance et logique métier pour les contrats de travail (/contract).

Ce module implémente l'accès aux données (DAO) pour la table SQL `contracts` :
- Un joueur ne peut avoir qu'un seul contrat actif (clé primaire discord_id).
- Trois durées disponibles : court (30 min), moyen (2 h), long (6 h).
- Réussite garantie, récupération manuelle sans expiration ni pénalité de retard.
- Système de fidélité : après un certain nombre de contrats validés, le prochain
  contrat bénéficie d'une mission spéciale (+50 % de récompense USD).
"""

from datetime import datetime, timedelta
from decimal import Decimal
import random

from game.db.players import UpdatePlayer
from game.game_error import GameError
from game.math_config import MathConfig
from utils.time_format import format_duration, to_utc_timestamp


# Pool de titres immersifs par type de durée
MISSION_TITLES = {
    'short': [
        "Diagnostic de sous-réseau",
        "Analyse de flux de paquets",
        "Patch de micro-service",
        "Vérification des tables de routage",
        "Optimisation du cache DNS",
    ],
    'medium': [
        "Restauration de sauvegarde chiffrée",
        "Déploiement de cluster sécurisé",
        "Nettoyage de base corrompue",
        "Audit de redondance de baie",
        "Isolation de passerelle compromise",
    ],
    'long': [
        "Audit de sécurité périmétrique",
        "Reconnaissance d'infrastructure critique",
        "Migration complète d'hyperviseur",
        "Durcissement d'architecture réseau",
        "Analyse forensique approfondie",
    ],
}


class ContractsDB:
    """Accès aux données et opérations métier pour la table contracts."""

    @staticmethod
    def get_active(tx, discord_id: int) -> dict | None:
        """Retourne le contrat en cours du joueur, s'il existe."""
        row = tx.one(
            "SELECT * FROM contracts WHERE discord_id = %s",
            (discord_id,),
        )
        if not row:
            return None
        expires_at = row['expires_at']
        is_ready = (tx.now >= expires_at)
        remaining = max(0, int((expires_at - tx.now).total_seconds()))
        return {
            **row,
            'is_ready': is_ready,
            'remaining_seconds': remaining,
            'expires_ts': to_utc_timestamp(expires_at),
        }

    @staticmethod
    def get_offers(fidelity: int) -> dict:
        """Construit les propositions de missions pour les 3 durées selon la fidélité."""
        cfg = MathConfig.get_contracts_config()
        threshold = int(cfg.get('fidelity_threshold', 5))
        is_special = (fidelity >= threshold)
        mult = Decimal(str(cfg.get('special_bonus_multiplier', 1.5))) if is_special else Decimal('1')
        agency = cfg.get('agency_name', "Agence Root CyberSec")

        offers = {}
        for tier in ('short', 'medium', 'long'):
            tier_cfg = MathConfig.get_contract_tier(tier) or {}
            base_reward = Decimal(str(tier_cfg.get('reward_usd', 0)))
            reward = (base_reward * mult).quantize(Decimal('0.01'))
            offers[tier] = {
                'duration_seconds': int(tier_cfg.get('duration_seconds', 0)),
                'reward_usd': reward,
                'base_reward_usd': base_reward,
                'hourly_rate': tier_cfg.get('hourly_rate', 0),
                'is_special': is_special,
            }

        return {
            'agency': agency,
            'fidelity': fidelity,
            'fidelity_threshold': threshold,
            'is_special': is_special,
            'offers': offers,
        }

    @staticmethod
    def get_status(tx, discord_id: int) -> dict:
        """Retourne l'état complet du joueur pour la commande /contract."""
        active = ContractsDB.get_active(tx, discord_id)
        player = tx.one(
            "SELECT * FROM players WHERE discord_id = %s",
            (discord_id,),
        )
        fidelity = int((player.get('contract_fidelity') if player else 0) or 0)
        completed = int((player.get('contracts_completed') if player else 0) or 0)

        offers_data = ContractsDB.get_offers(fidelity)

        if active:
            return {
                'has_active': True,
                'contract': active,
                'fidelity': fidelity,
                'fidelity_threshold': offers_data['fidelity_threshold'],
                'contracts_completed': completed,
                'offers_data': offers_data,
            }

        return {
            'has_active': False,
            'contract': None,
            'fidelity': fidelity,
            'fidelity_threshold': offers_data['fidelity_threshold'],
            'contracts_completed': completed,
            'offers_data': offers_data,
        }

    @staticmethod
    def start(tx, discord_id: int, duration_type: str) -> dict:
        """Accepte et démarre un nouveau contrat de travail."""
        duration_type = (duration_type or '').strip().lower()
        if duration_type not in ('short', 'medium', 'long'):
            raise GameError('invalid_contract_duration')

        existing = ContractsDB.get_active(tx, discord_id)
        if existing:
            raise GameError('contract_in_progress', timestamp=existing['expires_ts'])

        player = tx.one(
            "SELECT * FROM players WHERE discord_id = %s",
            (discord_id,),
        )
        if not player:
            raise GameError('no_network')
        fidelity = int(player.get('contract_fidelity') or 0)

        cfg = MathConfig.get_contracts_config()
        threshold = int(cfg.get('fidelity_threshold', 5))
        is_special = (fidelity >= threshold)
        mult = Decimal(str(cfg.get('special_bonus_multiplier', 1.5))) if is_special else Decimal('1')

        tier_cfg = MathConfig.get_contract_tier(duration_type)
        if not tier_cfg:
            raise GameError('invalid_contract_duration')

        duration_sec = int(tier_cfg['duration_seconds'])
        base_reward = Decimal(str(tier_cfg['reward_usd']))
        reward_usd = (base_reward * mult).quantize(Decimal('0.01'))

        # Choix du titre
        titles = MISSION_TITLES.get(duration_type, ["Mission réseau"])
        title = random.choice(titles)

        expires_at = tx.now + timedelta(seconds=duration_sec)

        tx.execute(
            """
            INSERT INTO contracts (
                discord_id, duration_type, title, reward_usd, is_special, started_at, expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                discord_id, duration_type, title, reward_usd,
                1 if is_special else 0, tx.now, expires_at,
            ),
        )

        expires_ts = to_utc_timestamp(expires_at)
        return {
            'discord_id': discord_id,
            'duration_type': duration_type,
            'title': title,
            'reward_usd': reward_usd,
            'is_special': is_special,
            'started_at': tx.now,
            'expires_at': expires_at,
            'expires_ts': expires_ts,
            'duration_seconds': duration_sec,
        }

    @staticmethod
    def collect(tx, discord_id: int) -> dict:
        """Récupère la rémunération d'un contrat arrivé à échéance."""
        active = ContractsDB.get_active(tx, discord_id)
        if not active:
            raise GameError('no_active_contract')

        if not active['is_ready']:
            remaining_fmt = format_duration(active['remaining_seconds'])
            raise GameError('contract_not_ready', remaining=remaining_fmt)

        reward = Decimal(str(active['reward_usd']))
        player = tx.one(
            "SELECT * FROM players WHERE discord_id = %s",
            (discord_id,),
        )
        if not player:
            raise GameError('no_network')

        cur_dollars = Decimal(str(player.get('dollars') or 0))
        cur_fidelity = int(player.get('contract_fidelity') or 0)
        cur_completed = int(player.get('contracts_completed') or 0)

        new_dollars = cur_dollars + reward
        new_completed = cur_completed + 1
        # Si c'était une mission spéciale, la jauge de fidélité se réinitialise à 0
        new_fidelity = 0 if active.get('is_special') else (cur_fidelity + 1)

        UpdatePlayer.set(
            tx, discord_id,
            dollars=new_dollars,
            contract_fidelity=new_fidelity,
            contracts_completed=new_completed,
        )

        tx.execute("DELETE FROM contracts WHERE discord_id = %s", (discord_id,))

        offers_data = ContractsDB.get_offers(new_fidelity)

        return {
            'collected': True,
            'reward_usd': reward,
            'new_dollars': new_dollars,
            'contract_fidelity': new_fidelity,
            'contracts_completed': new_completed,
            'was_special': bool(active.get('is_special')),
            'title': active.get('title'),
            'duration_type': active.get('duration_type'),
            'offers_data': offers_data,
        }

    @staticmethod
    def get_unnotified_expired(tx) -> list[dict]:
        """Retourne les contrats arrivés à échéance qui n'ont pas encore été notifiés en MP."""
        rows = tx.all(
            """
            SELECT * FROM contracts
            WHERE expires_at <= %s AND (notified IS NULL OR notified = 0)
            """,
            (tx.now,),
        )
        if not rows:
            return []
        uids = [r["discord_id"] for r in rows]
        format_strings = ",".join(["%s"] * len(uids))
        tx.execute(
            f"UPDATE contracts SET notified = 1 WHERE discord_id IN ({format_strings})",
            tuple(uids),
        )
        return rows
