"""
Persistance des correctifs PvP V2 (table `pvp_v2_patches`).

Un patch est d'abord compilé (installed=0), puis installé (installed=1).
Une fois installé, il protège tous les modules du tier ciblé (présents et futurs).
Le champ reserved=1 indique qu'une annonce de marché est en cours.
Un patch installé ne peut pas être réservé ni revendu.
"""

import logging

logger = logging.getLogger(__name__)


class PvpV2PatchDB:
    """Accès aux données pour la table pvp_v2_patches."""

    @staticmethod
    def get_by_owner(tx, owner_id: int) -> list:
        """Retourne tous les patches d'un joueur (installés ou non)."""
        return tx.all(
            'SELECT * FROM pvp_v2_patches WHERE owner_id = %s ORDER BY created_at DESC',
            (int(owner_id),),
        )

    @staticmethod
    def get_by_id(tx, patch_id: int) -> dict | None:
        """Retourne un patch par son ID."""
        return tx.one(
            'SELECT * FROM pvp_v2_patches WHERE id = %s',
            (int(patch_id),),
        )

    @staticmethod
    def is_installed(tx, owner_id: int, fingerprint: str) -> bool:
        """Vérifie si un joueur a déjà installé le patch pour cette empreinte."""
        row = tx.one(
            'SELECT 1 FROM pvp_v2_patches WHERE owner_id = %s AND fingerprint = %s AND installed = 1',
            (int(owner_id), str(fingerprint)),
        )
        return row is not None

    @staticmethod
    def get_installed_fingerprints(tx, owner_id: int) -> set:
        """Retourne l'ensemble des empreintes patchées (installées) d'un joueur.

        Utilisé lors du calcul des effets actifs pour déterminer les immunités.
        """
        rows = tx.all(
            'SELECT fingerprint FROM pvp_v2_patches WHERE owner_id = %s AND installed = 1',
            (int(owner_id),),
        )
        return {r['fingerprint'] for r in rows}

    @staticmethod
    def create(tx, owner_id: int, family: str, fingerprint: str) -> dict:
        """Insère un nouveau patch compilé (non encore installé)."""
        patch_id = tx.execute(
            """
            INSERT INTO pvp_v2_patches (owner_id, family, fingerprint, installed, reserved, created_at)
            VALUES (%s, %s, %s, 0, 0, %s)
            """,
            (int(owner_id), str(family), str(fingerprint), tx.now),
        )
        return {
            'id': patch_id,
            'owner_id': int(owner_id),
            'family': str(family),
            'fingerprint': str(fingerprint),
            'installed': 0,
            'installed_at': None,
            'reserved': 0,
            'created_at': tx.now,
        }

    @staticmethod
    def install(tx, patch_id: int, owner_id: int) -> bool:
        """Marque un patch comme installé sur le réseau du joueur.

        Opération irréversible : installed=1 ne peut pas redevenir 0.
        Un patch installé ne peut pas être revendu (reserved=0 forcé par le dépôt marché).
        """
        affected = tx.execute(
            """
            UPDATE pvp_v2_patches
            SET installed = 1, installed_at = %s
            WHERE id = %s AND owner_id = %s AND installed = 0
            """,
            (tx.now, int(patch_id), int(owner_id)),
        )
        return bool(affected)

    @staticmethod
    def set_reserved(tx, patch_id: int, reserved: bool) -> bool:
        """Marque un patch comme réservé (annonce en cours) ou libéré.

        N'opère que sur des patches non encore installés.
        """
        affected = tx.execute(
            'UPDATE pvp_v2_patches SET reserved = %s WHERE id = %s AND installed = 0',
            (int(reserved), int(patch_id)),
        )
        return bool(affected)

    @staticmethod
    def transfer_ownership(tx, patch_id: int, new_owner_id: int) -> bool:
        """Transfère la propriété d'un patch non installé (achat sur le marché)."""
        affected = tx.execute(
            """
            UPDATE pvp_v2_patches
            SET owner_id = %s, reserved = 0
            WHERE id = %s AND installed = 0
            """,
            (int(new_owner_id), int(patch_id)),
        )
        return bool(affected)

    @staticmethod
    def delete(tx, patch_id: int, owner_id: int) -> bool:
        """Supprime un patch non installé appartenant au joueur."""
        affected = tx.execute(
            'DELETE FROM pvp_v2_patches WHERE id = %s AND owner_id = %s AND installed = 0',
            (int(patch_id), int(owner_id)),
        )
        return bool(affected)

