"""
Persistance des opérations PvP V2 et des effets persistants actifs
(tables `pvp_v2_operations` et `pvp_v2_active_effects`).

Cycle de vie d'une opération :
  installing -> active -> completed / failed / cancelled

Le passage installing -> active se fait quand le job d'installation est livré.
Les effets persistants (siphon, ransomware, saturation…) sont des lignes dans
pvp_v2_active_effects avec ended_at=NULL tant qu'actifs.
"""

import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class PvpV2OperationsDB:
    """Accès aux données pour la table pvp_v2_operations."""

    @staticmethod
    def get_by_id(tx, op_id: int) -> dict | None:
        """Retourne une opération par son ID."""
        return tx.one(
            'SELECT * FROM pvp_v2_operations WHERE id = %s',
            (int(op_id),),
        )

    @staticmethod
    def get_active_by_attacker(tx, attacker_id: int) -> list:
        """Retourne les opérations en cours (installing ou active) d'un attaquant."""
        return tx.all(
            """
            SELECT * FROM pvp_v2_operations
            WHERE attacker_id = %s AND status IN ('installing', 'active')
            ORDER BY started_at ASC
            """,
            (int(attacker_id),),
        )

    @staticmethod
    def get_active_by_victim(tx, victim_id: int) -> list:
        """Retourne les opérations actives subies par un joueur."""
        return tx.all(
            """
            SELECT * FROM pvp_v2_operations
            WHERE victim_id = %s AND status IN ('installing', 'active')
            ORDER BY started_at ASC
            """,
            (int(victim_id),),
        )

    @staticmethod
    def get_installing(tx) -> list:
        """Retourne les opérations en cours d'installation.

        Utilisé par le worker d'installation pour calculer les fins de job.
        """
        return tx.all(
            "SELECT * FROM pvp_v2_operations WHERE status = 'installing' ORDER BY started_at ASC",
        )

    @staticmethod
    def get_installing_ready(tx, cutoff=None) -> list:
        """Retourne les opérations en cours d'installation arrivées à échéance (FOR UPDATE)."""
        cutoff_dt = cutoff or tx.now
        rows = tx.all(
            """
            SELECT * FROM pvp_v2_operations
            WHERE status = 'installing' AND installed_at IS NOT NULL AND installed_at <= %s
            ORDER BY installed_at ASC FOR UPDATE
            """,
            (cutoff_dt,),
        )
        for r in rows:
            if 'resolves_at' not in r or r['resolves_at'] is None:
                r['resolves_at'] = r.get('installed_at')
        return rows

    @staticmethod
    def count_active_by_attacker(tx, attacker_id: int) -> int:
        """Compte les opérations actives (installing+active) d'un attaquant.

        Permet de vérifier le plafond de 3 opérations simultanées (décision 14).
        """
        row = tx.one(
            """
            SELECT COUNT(*) AS cnt FROM pvp_v2_operations
            WHERE attacker_id = %s AND status IN ('installing', 'active')
            """,
            (int(attacker_id),),
        )
        return int(row['cnt']) if row else 0

    @staticmethod
    def count_active_by_attacker_family(tx, attacker_id: int, family: str) -> int:
        """Compte les opérations actives d'un attaquant pour une famille donnée.

        Permet de vérifier le plafond de 1 opération par famille (décision 14).
        """
        row = tx.one(
            """
            SELECT COUNT(*) AS cnt FROM pvp_v2_operations
            WHERE attacker_id = %s AND family = %s AND status IN ('installing', 'active')
            """,
            (int(attacker_id), str(family)),
        )
        return int(row['cnt']) if row else 0

    @staticmethod
    def create(
        tx,
        attacker_id: int,
        victim_id: int,
        family: str,
        tier: int,
        fingerprint: str,
        software_copy_id: int,
        rtm_cost,
        resolves_at=None,
    ) -> dict:
        """Crée une opération en statut 'installing'."""
        from decimal import Decimal
        rtm_cost_d = Decimal(str(rtm_cost))
        op_id = tx.execute(
            """
            INSERT INTO pvp_v2_operations
                (attacker_id, victim_id, family, tier, fingerprint,
                 software_copy_id, status, rtm_cost, started_at, installed_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'installing', %s, %s, %s)
            """,
            (
                int(attacker_id),
                int(victim_id),
                str(family),
                int(tier),
                str(fingerprint),
                int(software_copy_id),
                rtm_cost_d,
                tx.now,
                resolves_at,
            ),
        )
        return {
            'id': op_id,
            'attacker_id': int(attacker_id),
            'victim_id': int(victim_id),
            'family': str(family),
            'tier': int(tier),
            'fingerprint': str(fingerprint),
            'software_copy_id': int(software_copy_id),
            'status': 'installing',
            'rtm_cost': rtm_cost_d,
            'started_at': tx.now,
            'installed_at': resolves_at,
            'resolves_at': resolves_at,
            'ended_at': None,
            'end_reason': None,
        }

    @staticmethod
    def mark_active(tx, op_id: int) -> bool:
        """Fait passer une opération de 'installing' à 'active' (effet démarré)."""
        affected = tx.execute(
            """
            UPDATE pvp_v2_operations
            SET status = 'active'
            WHERE id = %s AND status = 'installing'
            """,
            (int(op_id),),
        )
        return bool(affected)

    @staticmethod
    def mark_ended(tx, op_id: int, status: str, end_reason: str | None = None) -> bool:
        """Termine une opération avec un statut final et une raison optionnelle.

        status doit être 'completed', 'failed' ou 'cancelled'.
        """
        affected = tx.execute(
            """
            UPDATE pvp_v2_operations
            SET status = %s, ended_at = %s, end_reason = %s
            WHERE id = %s AND status IN ('installing', 'active')
            """,
            (str(status), tx.now, end_reason, int(op_id)),
        )
        return bool(affected)


class PvpV2ActiveEffectsDB:
    """Accès aux données pour la table pvp_v2_active_effects."""

    @staticmethod
    def get_active_on_victim(tx, victim_id: int) -> list:
        """Retourne tous les effets actifs (ended_at IS NULL) ciblant un joueur."""
        return tx.all(
            """
            SELECT * FROM pvp_v2_active_effects
            WHERE victim_id = %s AND ended_at IS NULL
            ORDER BY started_at ASC
            """,
            (int(victim_id),),
        )

    @staticmethod
    def get_active_by_attacker(tx, attacker_id: int) -> list:
        """Retourne tous les effets actifs initiés par un attaquant."""
        return tx.all(
            """
            SELECT * FROM pvp_v2_active_effects
            WHERE attacker_id = %s AND ended_at IS NULL
            """,
            (int(attacker_id),),
        )

    @staticmethod
    def get_active_on_victim_by_family(tx, victim_id: int, family: str) -> list:
        """Retourne les effets actifs d'une famille donnée sur un joueur."""
        return tx.all(
            """
            SELECT * FROM pvp_v2_active_effects
            WHERE victim_id = %s AND family = %s AND ended_at IS NULL
            """,
            (int(victim_id), str(family)),
        )

    @staticmethod
    def is_active_fingerprint_on_victim(tx, victim_id: int, fingerprint: str) -> bool:
        """Vérifie si un effet avec cette empreinte est déjà actif sur la victime."""
        row = tx.one(
            """
            SELECT 1 FROM pvp_v2_active_effects
            WHERE victim_id = %s AND fingerprint = %s AND ended_at IS NULL
            """,
            (int(victim_id), str(fingerprint)),
        )
        return row is not None

    @staticmethod
    def create(
        tx,
        operation_id: int,
        attacker_id: int,
        victim_id: int,
        family: str,
        tier: int,
        fingerprint: str,
        effect_data: dict | None = None,
    ) -> dict:
        """Crée un effet persistant actif associé à une opération."""
        effect_data_json = json.dumps(effect_data) if effect_data is not None else None
        effect_id = tx.execute(
            """
            INSERT INTO pvp_v2_active_effects
                (operation_id, attacker_id, victim_id, family, tier,
                 fingerprint, effect_data, started_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(operation_id),
                int(attacker_id),
                int(victim_id),
                str(family),
                int(tier),
                str(fingerprint),
                effect_data_json,
                tx.now,
            ),
        )
        return {
            'id': effect_id,
            'operation_id': int(operation_id),
            'attacker_id': int(attacker_id),
            'victim_id': int(victim_id),
            'family': str(family),
            'tier': int(tier),
            'fingerprint': str(fingerprint),
            'effect_data': effect_data,
            'started_at': tx.now,
            'ended_at': None,
            'end_reason': None,
        }

    @staticmethod
    def end_effect(tx, effect_id: int, end_reason: str) -> bool:
        """Clôture un effet actif en renseignant ended_at et end_reason."""
        affected = tx.execute(
            """
            UPDATE pvp_v2_active_effects
            SET ended_at = %s, end_reason = %s
            WHERE id = %s AND ended_at IS NULL
            """,
            (tx.now, str(end_reason), int(effect_id)),
        )
        return bool(affected)

    @staticmethod
    def end_effects_by_fingerprint_victim(tx, victim_id: int, fingerprint: str, end_reason: str) -> int:
        """Clôture tous les effets actifs d'une empreinte donnée sur un joueur.

        Utilisé lors de l'installation d'un patch. Retourne le nombre d'effets clos.
        """
        affected = tx.execute(
            """
            UPDATE pvp_v2_active_effects
            SET ended_at = %s, end_reason = %s
            WHERE victim_id = %s AND fingerprint = %s AND ended_at IS NULL
            """,
            (tx.now, str(end_reason), int(victim_id), str(fingerprint)),
        )
        return int(affected) if affected else 0

