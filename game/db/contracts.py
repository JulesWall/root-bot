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
    def get_offers(fidelity: int, firewall_level: int = 0, grace_ts: int | None = None) -> dict:
        """Construit les propositions de missions pour les 3 durées selon la fidélité et le pare-feu."""
        cfg = MathConfig.get_contracts_config()
        threshold = int(cfg.get('fidelity_threshold', 5))
        is_special = (fidelity >= threshold)
        mult = Decimal(str(cfg.get('special_bonus_multiplier', 1.4))) if is_special else Decimal('1')
        agency = cfg.get('agency_name', "Agence Root CyberSec")

        fw_mult = Decimal(str(max(0, int(firewall_level or 0)) + 1))

        offers = {}
        for tier in ('short', 'medium', 'long'):
            tier_cfg = MathConfig.get_contract_tier(tier) or {}
            raw_base = Decimal(str(tier_cfg.get('reward_usd', 0)))
            base_reward = (raw_base * fw_mult).quantize(Decimal('0.01'))
            reward = (base_reward * mult).quantize(Decimal('0.01'))
            hourly_rate = float((Decimal(str(tier_cfg.get('hourly_rate', 0))) * fw_mult).quantize(Decimal('0.01')))
            offers[tier] = {
                'duration_seconds': int(tier_cfg.get('duration_seconds', 0)),
                'reward_usd': reward,
                'base_reward_usd': base_reward,
                'hourly_rate': hourly_rate,
                'is_special': is_special,
            }

        return {
            'agency': agency,
            'fidelity': fidelity,
            'fidelity_threshold': threshold,
            'is_special': is_special,
            'offers': offers,
            'firewall_level': int(firewall_level or 0),
            'firewall_multiplier': int(fw_mult),
            'grace_ts': grace_ts,
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
        firewall_level = int((player.get('firewall_level') if player else 0) or 0)
        grace_until = player.get('contract_grace_until') if player else None

        cfg = MathConfig.get_contracts_config()
        threshold = int(cfg.get('fidelity_threshold', 5))

        # Vérification expiration de la fenêtre de grâce (si fidélité >= 5 et aucun contrat actif)
        if fidelity >= threshold and not active and grace_until:
            if tx.now > grace_until:
                fidelity = 0
                grace_until = None
                UpdatePlayer.set(tx, discord_id, contract_fidelity=0, contract_grace_until=None)

        grace_ts = to_utc_timestamp(grace_until) if (grace_until and not active) else None
        grace_remaining = max(0, int((grace_until - tx.now).total_seconds())) if (grace_until and not active) else None

        offers_data = ContractsDB.get_offers(fidelity, firewall_level=firewall_level, grace_ts=grace_ts)

        if active:
            return {
                'has_active': True,
                'contract': active,
                'fidelity': fidelity,
                'fidelity_threshold': offers_data['fidelity_threshold'],
                'contracts_completed': completed,
                'offers_data': offers_data,
                'grace_ts': None,
                'grace_remaining_seconds': None,
            }

        return {
            'has_active': False,
            'contract': None,
            'fidelity': fidelity,
            'fidelity_threshold': offers_data['fidelity_threshold'],
            'contracts_completed': completed,
            'offers_data': offers_data,
            'grace_ts': grace_ts,
            'grace_remaining_seconds': grace_remaining,
        }

    @staticmethod
    def start(tx, discord_id: int, duration_type: str) -> dict:
        """Accepte et démarre un nouveau contrat de travail."""
        duration_type = (duration_type or '').strip().lower()
        if duration_type not in ('short', 'medium', 'long'):
            raise GameError('invalid_contract_duration')

        existing = ContractsDB.get_active(tx, discord_id)
        if existing:
            remaining = format_duration(existing.get('remaining_seconds', 0))
            expires_ts = existing.get('expires_ts', 0)
            raise GameError('contract_in_progress', timestamp=expires_ts, ts=expires_ts, remaining=remaining, duration=remaining)

        player = tx.one(
            "SELECT * FROM players WHERE discord_id = %s",
            (discord_id,),
        )
        if not player:
            raise GameError('no_network')
        fidelity = int(player.get('contract_fidelity') or 0)
        firewall_level = int(player.get('firewall_level') or 0)
        grace_until = player.get('contract_grace_until')

        cfg = MathConfig.get_contracts_config()
        threshold = int(cfg.get('fidelity_threshold', 5))

        # Vérification expiration de la grâce avant le démarrage
        if fidelity >= threshold and grace_until:
            if tx.now > grace_until:
                fidelity = 0
                grace_until = None
                UpdatePlayer.set(tx, discord_id, contract_fidelity=0, contract_grace_until=None)

        fw_mult = Decimal(str(max(0, firewall_level) + 1))
        is_special = (fidelity >= threshold)
        mult = Decimal(str(cfg.get('special_bonus_multiplier', 1.4))) if is_special else Decimal('1')

        tier_cfg = MathConfig.get_contract_tier(duration_type)
        if not tier_cfg:
            raise GameError('invalid_contract_duration')

        duration_sec = int(tier_cfg['duration_seconds'])
        raw_base = Decimal(str(tier_cfg['reward_usd']))
        base_reward = (raw_base * fw_mult).quantize(Decimal('0.01'))
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

        # Dès qu'un contrat démarre, la grâce en attente est consommée
        if grace_until is not None:
            UpdatePlayer.set(tx, discord_id, contract_grace_until=None)

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
            expires_ts = active.get('expires_ts', 0)
            raise GameError('contract_not_ready', remaining=remaining_fmt, duration=remaining_fmt, timestamp=expires_ts, ts=expires_ts)

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
        firewall_level = int(player.get('firewall_level') or 0)

        new_dollars = cur_dollars + reward
        new_completed = cur_completed + 1

        cfg = MathConfig.get_contracts_config()
        threshold = int(cfg.get('fidelity_threshold', 5))
        grace_sec = int(cfg.get('grace_period_seconds', 2700))

        # La fenêtre de grâce de 45 minutes pour relancer le contrat et conserver le combo
        # doit être calculée impérativement à compter de l'EXPIRATION du contrat (active['expires_at']),
        # et non pas à partir du moment de la collecte manuelle (tx.now).
        expires_at = active['expires_at']
        grace_deadline = expires_at + timedelta(seconds=grace_sec)
        is_within_grace = (tx.now <= grace_deadline)

        if active.get('is_special'):
            if is_within_grace:
                new_fidelity = max(threshold, cur_fidelity)
                new_grace_until = grace_deadline
            else:
                new_fidelity = 0
                new_grace_until = None
        else:
            new_fidelity = cur_fidelity + 1
            if new_fidelity >= threshold:
                if is_within_grace:
                    new_grace_until = grace_deadline
                else:
                    # Collecté plus de 45 min après l'échéance : le combo pour lancer la mission spéciale a expiré
                    new_fidelity = 0
                    new_grace_until = None
            else:
                new_grace_until = None

        UpdatePlayer.set(
            tx, discord_id,
            dollars=new_dollars,
            contract_fidelity=new_fidelity,
            contracts_completed=new_completed,
            contract_grace_until=new_grace_until,
        )

        tx.execute("DELETE FROM contracts WHERE discord_id = %s", (discord_id,))

        grace_ts = to_utc_timestamp(new_grace_until) if new_grace_until else None
        grace_remaining = max(0, int((new_grace_until - tx.now).total_seconds())) if new_grace_until else None

        offers_data = ContractsDB.get_offers(new_fidelity, firewall_level=firewall_level, grace_ts=grace_ts)

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
            'grace_until': new_grace_until,
            'grace_ts': grace_ts,
            'grace_remaining_seconds': grace_remaining,
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
