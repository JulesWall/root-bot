"""
Persistance des jobs de développement PvP V2 (table `pvp_v2_dev_jobs`).

Un seul job actif par canal (offense / defense) par joueur (contrainte UNIQUE SQL).
Le worker de livraison poll les jobs dont resolves_at <= now et les traite atomiquement.
Les jobs sont persistants : un redémarrage du bot reprend depuis la base sans double livraison.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PvpV2DevJobsDB:
    """Accès aux données pour la table pvp_v2_dev_jobs."""

    @staticmethod
    def get_active_by_player_channel(tx, player_id: int, channel: str) -> dict | None:
        """Retourne le job actif d'un joueur sur un canal donné ('offense' ou 'defense')."""
        return tx.one(
            'SELECT * FROM pvp_v2_dev_jobs WHERE player_id = %s AND channel = %s',
            (int(player_id), str(channel)),
        )

    @staticmethod
    def get_all_active_by_player(tx, player_id: int) -> list:
        """Retourne les deux jobs actifs d'un joueur (un par canal au maximum)."""
        return tx.all(
            'SELECT * FROM pvp_v2_dev_jobs WHERE player_id = %s ORDER BY resolves_at ASC',
            (int(player_id),),
        )

    @staticmethod
    def get_expired(tx) -> list:
        """Retourne les jobs dont l'échéance est passée, triés par resolves_at croissant.

        Utilisé par le worker de livraison. Le tri garantit un traitement FIFO par canal.
        """
        return tx.all(
            'SELECT * FROM pvp_v2_dev_jobs WHERE resolves_at <= %s ORDER BY resolves_at ASC',
            (tx.now,),
        )

    @staticmethod
    def create(
        tx,
        player_id: int,
        channel: str,
        job_type: str,
        family: str,
        tier: int,
        rtm_paid,
        bits_per_s: int,
        resolves_at: datetime,
    ) -> dict:
        """Insère un nouveau job de développement.

        Lève IntegrityError si le canal est déjà occupé (contrainte UNIQUE player_id, channel).
        L'appelant doit vérifier get_active_by_player_channel() avant ou intercepter l'erreur.
        fingerprint est NULL à la création ; il sera assigné à la résolution pour 'research'.
        """
        from decimal import Decimal
        rtm_paid_d = Decimal(str(rtm_paid))
        job_id = tx.execute(
            """
            INSERT INTO pvp_v2_dev_jobs
                (player_id, channel, job_type, family, tier, fingerprint,
                 rtm_paid, bits_per_s, started_at, resolves_at)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s)
            """,
            (
                int(player_id),
                str(channel),
                str(job_type),
                str(family),
                int(tier),
                rtm_paid_d,
                int(bits_per_s),
                tx.now,
                resolves_at,
            ),
        )
        return {
            'id': job_id,
            'player_id': int(player_id),
            'channel': str(channel),
            'job_type': str(job_type),
            'family': str(family),
            'tier': int(tier),
            'fingerprint': None,
            'rtm_paid': rtm_paid_d,
            'bits_per_s': int(bits_per_s),
            'started_at': tx.now,
            'resolves_at': resolves_at,
        }

    @staticmethod
    def delete(tx, job_id: int) -> bool:
        """Supprime un job par son ID (appelé après résolution ou annulation).

        Retourne True si une ligne a été supprimée.
        """
        affected = tx.execute(
            'DELETE FROM pvp_v2_dev_jobs WHERE id = %s',
            (int(job_id),),
        )
        return bool(affected)

    @staticmethod
    def cancel_by_player_channel(tx, player_id: int, channel: str) -> dict | None:
        """Annule et supprime le job actif d'un joueur sur un canal.

        Retourne la ligne supprimée (pour remboursement RTM éventuel), ou None si absent.
        """
        job = PvpV2DevJobsDB.get_active_by_player_channel(tx, player_id, channel)
        if job is None:
            return None
        PvpV2DevJobsDB.delete(tx, int(job['id']))
        return job

