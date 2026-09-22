"""
Persistance des jobs asynchrones (table SQL `hack`).

La table `hack` gère deux types de jobs différés :
- `compile` : production d'ATK via les modules d'attaque.
- `scan`    : scan réseau d'un joueur adverse pour découvrir son secret_id.

Un joueur ne peut avoir qu'un seul job actif par type (UNIQUE discord_id, type).
"""

from datetime import datetime
from decimal import Decimal

from game.db.database import player_lock_name


class HackDB:
    """Accès aux données pour la table hack (compile + scan)."""

    @staticmethod
    def get_active(tx, discord_id: int, type: str = 'compile') -> dict | None:
        """Retourne le job actif du joueur pour le type donné, s'il existe."""
        return tx.one(
            'SELECT * FROM hack WHERE discord_id = %s AND type = %s',
            (discord_id, type),
        )

    @staticmethod
    def create(
        tx,
        discord_id: int,
        method: str,
        atk_yield: int,
        rtm_paid: Decimal,
        expires_at: datetime,
        bits_per_s: int = 0,
    ) -> dict:
        """Insère un lot de production d'ATK (type='compile') et renvoie la ligne créée."""
        bits = int(bits_per_s or atk_yield)
        hack_id = tx.execute(
            """
            INSERT INTO hack (
                discord_id, type, method, bits_per_s, atk_yield, rtm_paid, boost_rtm, started_at, expires_at
            )
            VALUES (%s, 'compile', %s, %s, %s, %s, 0.00000, %s, %s)
            """,
            (
                discord_id, method, bits, int(atk_yield), rtm_paid,
                tx.now, expires_at,
            ),
        )
        return {
            'id': hack_id,
            'discord_id': discord_id,
            'type': 'compile',
            'method': method,
            'bits_per_s': bits,
            'atk_yield': int(atk_yield),
            'rtm_paid': rtm_paid,
            'boost_rtm': Decimal('0'),
            'started_at': tx.now,
            'expires_at': expires_at,
        }

    @staticmethod
    def create_scan(
        tx,
        scanner_id: int,
        target_id: int,
        rtm_paid: Decimal,
        boost_rtm: Decimal,
        expires_at: datetime,
    ) -> dict:
        """Insère un job de scan réseau (type='scan') et renvoie la ligne créée."""
        scan_id = tx.execute(
            """
            INSERT INTO hack (
                discord_id, type, target_id, method, bits_per_s, atk_yield,
                rtm_paid, boost_rtm, started_at, expires_at
            )
            VALUES (%s, 'scan', %s, 'scan', 0, 0, %s, %s, %s, %s)
            """,
            (
                int(scanner_id), int(target_id),
                rtm_paid, boost_rtm,
                tx.now, expires_at,
            ),
        )
        return {
            'id': scan_id,
            'discord_id': int(scanner_id),
            'type': 'scan',
            'target_id': int(target_id),
            'method': 'scan',
            'bits_per_s': 0,
            'atk_yield': 0,
            'rtm_paid': rtm_paid,
            'boost_rtm': boost_rtm,
            'started_at': tx.now,
            'expires_at': expires_at,
        }

    @staticmethod
    def complete_and_delete_expired(tx) -> list[dict]:
        """Crédite attack_points pour les jobs compile arrivés à échéance et les supprime."""
        expired = tx.all(
            "SELECT * FROM hack WHERE expires_at <= %s AND type = 'compile' FOR UPDATE",
            (tx.now,),
        )
        if not expired:
            return []

        player_ids = sorted({int(row['discord_id']) for row in expired})
        for pid in player_ids:
            tx.acquire_lock(player_lock_name(pid))

        delivered = []
        for row in expired:
            yield_atk = int(row.get('atk_yield') or 0)
            discord_id = int(row['discord_id'])
            if yield_atk > 0:
                tx.execute(
                    'UPDATE players SET attack_points = attack_points + %s WHERE discord_id = %s',
                    (yield_atk, discord_id),
                )
            tx.execute('DELETE FROM hack WHERE id = %s', (row['id'],))
            delivered.append({
                'discord_id': discord_id,
                'atk_yield': yield_atk,
            })
        return delivered

    @staticmethod
    def complete_and_delete_expired_scans(tx) -> list[dict]:
        """Récupère et supprime les jobs de scan arrivés à échéance pour livraison."""
        expired = tx.all(
            "SELECT * FROM hack WHERE expires_at <= %s AND type = 'scan' FOR UPDATE",
            (tx.now,),
        )
        if not expired:
            return []

        delivered = []
        for row in expired:
            tx.execute('DELETE FROM hack WHERE id = %s', (row['id'],))
            delivered.append({
                'scanner_id': int(row['discord_id']),
                'target_id': int(row['target_id']),
                'boost_rtm': row.get('boost_rtm') or Decimal('0'),
            })
        return delivered

