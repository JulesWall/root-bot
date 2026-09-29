"""
Persistance des copies de logiciels compilés PvP V2 (table `pvp_v2_software_copies`).

Chaque copie a une origine (compiled, purchased, stolen).
Les copies volées ont resellable=0 — contrainte applicative vérifiée à la création.
Le champ reserved=1 indique qu'une annonce de marché est en cours sur cette copie.
"""

import logging

logger = logging.getLogger(__name__)


class PvpV2SoftwareDB:
    """Accès aux données pour la table pvp_v2_software_copies."""

    @staticmethod
    def get_by_owner(tx, owner_id: int) -> list:
        """Retourne toutes les copies détenues par un joueur."""
        return tx.all(
            'SELECT * FROM pvp_v2_software_copies WHERE owner_id = %s ORDER BY created_at DESC',
            (int(owner_id),),
        )

    @staticmethod
    def get_by_id(tx, copy_id: int) -> dict | None:
        """Retourne une copie par son ID."""
        return tx.one(
            'SELECT * FROM pvp_v2_software_copies WHERE id = %s',
            (int(copy_id),),
        )

    @staticmethod
    def get_by_owner_fingerprint(tx, owner_id: int, fingerprint: str) -> list:
        """Retourne les copies d'un joueur pour une empreinte donnée."""
        return tx.all(
            'SELECT * FROM pvp_v2_software_copies WHERE owner_id = %s AND fingerprint = %s',
            (int(owner_id), str(fingerprint)),
        )

    @staticmethod
    def create(
        tx,
        owner_id: int,
        family: str,
        tier: int,
        fingerprint: str,
        origin: str,
    ) -> dict:
        """Insère une nouvelle copie de logiciel.

        Applique automatiquement resellable=0 si origin='stolen'.
        """
        resellable = 0 if origin == 'stolen' else 1
        copy_id = tx.execute(
            """
            INSERT INTO pvp_v2_software_copies
                (owner_id, family, tier, fingerprint, origin, resellable, reserved, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 0, %s)
            """,
            (
                int(owner_id),
                str(family),
                int(tier),
                str(fingerprint),
                str(origin),
                int(resellable),
                tx.now,
            ),
        )
        return {
            'id': copy_id,
            'owner_id': int(owner_id),
            'family': str(family),
            'tier': int(tier),
            'fingerprint': str(fingerprint),
            'origin': str(origin),
            'resellable': resellable,
            'reserved': 0,
            'created_at': tx.now,
        }

    @staticmethod
    def set_reserved(tx, copy_id: int, reserved: bool) -> bool:
        """Marque une copie comme réservée (annonce en cours) ou libérée."""
        affected = tx.execute(
            'UPDATE pvp_v2_software_copies SET reserved = %s WHERE id = %s',
            (int(reserved), int(copy_id)),
        )
        return bool(affected)

    @staticmethod
    def transfer_ownership(tx, copy_id: int, new_owner_id: int) -> bool:
        """Transfère la propriété d'une copie (achat sur le marché).

        Réinitialise reserved=0 et met à jour origin='purchased'.
        """
        affected = tx.execute(
            """
            UPDATE pvp_v2_software_copies
            SET owner_id = %s, origin = 'purchased', reserved = 0
            WHERE id = %s
            """,
            (int(new_owner_id), int(copy_id)),
        )
        return bool(affected)

    @staticmethod
    def delete(tx, copy_id: int, owner_id: int) -> bool:
        """Supprime une copie appartenant au joueur. Retourne True si supprimée."""
        affected = tx.execute(
            'DELETE FROM pvp_v2_software_copies WHERE id = %s AND owner_id = %s',
            (int(copy_id), int(owner_id)),
        )
        return bool(affected)

