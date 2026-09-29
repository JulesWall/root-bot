"""
Persistance des dossiers de recherche PvP V2 (table `pvp_v2_research_folders`).

Un dossier est créé à la résolution d'un job de recherche réussi.
Il permet au joueur de compiler des copies (canal offense) ou des patches (canal defense).
La contrainte UNIQUE (family, fingerprint) en base garantit l'unicité par famille.
"""

import logging

logger = logging.getLogger(__name__)


class PvpV2ResearchDB:
    """Accès aux données pour la table pvp_v2_research_folders."""

    @staticmethod
    def get_by_owner(tx, owner_id: int) -> list:
        """Retourne tous les dossiers de recherche d'un joueur."""
        return tx.all(
            'SELECT * FROM pvp_v2_research_folders WHERE owner_id = %s ORDER BY created_at DESC',
            (int(owner_id),),
        )

    @staticmethod
    def get_by_owner_family_tier(tx, owner_id: int, family: str, tier: int) -> dict | None:
        """Retourne le dossier correspondant à (owner, family, tier) s'il existe."""
        return tx.one(
            'SELECT * FROM pvp_v2_research_folders WHERE owner_id = %s AND family = %s AND tier = %s',
            (int(owner_id), str(family), int(tier)),
        )

    @staticmethod
    def get_by_family_fingerprint(tx, family: str, fingerprint: str) -> dict | None:
        """Retourne le dossier ayant cette empreinte dans cette famille (contrainte UNIQUE)."""
        return tx.one(
            'SELECT * FROM pvp_v2_research_folders WHERE family = %s AND fingerprint = %s',
            (str(family), str(fingerprint)),
        )

    @staticmethod
    def fingerprint_exists(tx, family: str, fingerprint: str) -> bool:
        """Vérifie si une empreinte est déjà utilisée pour cette famille.

        Utilisé lors de la génération pour détecter les collisions avant insertion.
        """
        row = tx.one(
            'SELECT 1 FROM pvp_v2_research_folders WHERE family = %s AND fingerprint = %s',
            (str(family), str(fingerprint)),
        )
        return row is not None

    @staticmethod
    def create(tx, owner_id: int, channel: str, family: str, tier: int, fingerprint: str) -> dict:
        """Insère un nouveau dossier de recherche.

        Lève une erreur SQL (IntegrityError) si l'empreinte est déjà prise dans cette famille.
        L'appelant doit vérifier fingerprint_exists() avant d'appeler cette méthode
        ou intercepter l'IntegrityError.
        """
        folder_id = tx.execute(
            """
            INSERT INTO pvp_v2_research_folders (owner_id, channel, family, tier, fingerprint, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (int(owner_id), str(channel), str(family), int(tier), str(fingerprint), tx.now),
        )
        return {
            'id': folder_id,
            'owner_id': int(owner_id),
            'channel': str(channel),
            'family': str(family),
            'tier': int(tier),
            'fingerprint': str(fingerprint),
            'created_at': tx.now,
        }

    @staticmethod
    def delete(tx, folder_id: int, owner_id: int) -> bool:
        """Supprime un dossier appartenant au joueur. Retourne True si supprimé."""
        affected = tx.execute(
            'DELETE FROM pvp_v2_research_folders WHERE id = %s AND owner_id = %s',
            (int(folder_id), int(owner_id)),
        )
        return bool(affected)

