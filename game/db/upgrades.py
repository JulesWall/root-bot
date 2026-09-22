"""
Gestion de la persistance et des opérations sur la table SQL 'upgrades'.

Permet le suivi des améliorations non instantanées (notamment le pare-feu) :
- Enregistrement des améliorations en cours avec durée d'expiration.
- Contrôle d'unicité (une seule amélioration en cours par joueur).
- Dépouillement des améliorations expirées, livraison sur le profil joueur
  et suppression immédiate de la ligne en base de données.
"""

from datetime import datetime

from game.db.database import player_lock_name


class UpgradesDB:
    """Accès aux données pour la table upgrades."""

    @staticmethod
    def get_active(tx, discord_id: int, item_type: str = 'firewall') -> dict | None:
        """
        Retourne l'amélioration active (non encore expirée ou en attente de livraison) pour un joueur.
        """
        return tx.one(
            "SELECT * FROM upgrades WHERE discord_id = %s AND item_type = %s",
            (discord_id, item_type),
        )

    @staticmethod
    def create(tx, discord_id: int, target_level: int, expires_at: datetime, item_type: str = 'firewall') -> dict:
        """
        Insère une nouvelle amélioration en cours pour un joueur.
        """
        upgrade_id = tx.execute(
            """
            INSERT INTO upgrades (discord_id, item_type, target_level, started_at, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (discord_id, item_type, target_level, tx.now, expires_at),
        )
        return {
            'id': upgrade_id,
            'discord_id': discord_id,
            'item_type': item_type,
            'target_level': target_level,
            'started_at': tx.now,
            'expires_at': expires_at,
        }

    @staticmethod
    def complete_and_delete_expired(tx) -> list[dict]:
        """
        Scanne les améliorations expirées, les applique sur les profils des joueurs
        dans la table players, supprime les lignes de la table upgrades et retourne
        la liste des livraisons effectuées.
        """
        # Verrouille les lignes expirées
        expired = tx.all(
            "SELECT * FROM upgrades WHERE expires_at <= %s FOR UPDATE",
            (tx.now,),
        )
        if not expired:
            return []

        # Verrouille chaque compte concerné (ordre croissant) pour ne pas
        # livrer un pare-feu en parallèle d'un /buy ou /upgrade du même joueur.
        player_ids = sorted({int(row['discord_id']) for row in expired})
        for pid in player_ids:
            tx.acquire_lock(player_lock_name(pid))

        delivered = []
        for row in expired:
            if row['item_type'] == 'firewall':
                # Livraison de l'amélioration de pare-feu (ne baisse jamais le niveau)
                tx.execute(
                    "UPDATE players SET firewall_level = GREATEST(firewall_level, %s) WHERE discord_id = %s",
                    (row['target_level'], row['discord_id']),
                )

            # Suppression immédiate de la ligne dans la table SQL
            tx.execute("DELETE FROM upgrades WHERE id = %s", (row['id'],))
            delivered.append({
                'id': row['id'],
                'discord_id': row['discord_id'],
                'item_type': row['item_type'],
                'target_level': row['target_level'],
                'expires_at': row['expires_at'],
            })

        return delivered

