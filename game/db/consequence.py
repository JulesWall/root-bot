"""
Gestion des droits de représailles PvP (table SQL `consequence`).

Une ligne est insérée après chaque scan livré (succès ou échec),
permettant à la victime de riposter pendant une fenêtre configurable.
La boucle de nettoyage du Cog Scan purge les lignes expirées.
"""


class ConsequenceDB:
    """Accès aux données pour la table consequence."""

    @staticmethod
    def insert(tx, victim_id: int, attacker_id: int, window_hours: int) -> None:
        """Insère un droit de représailles : victim_id peut riposter contre attacker_id."""
        tx.execute(
            """
            INSERT INTO consequence (victim_id, attacker_id, delete_at)
            VALUES (%s, %s, %s + INTERVAL %s HOUR)
            """,
            (int(victim_id), int(attacker_id), tx.now, int(window_hours)),
        )

    @staticmethod
    def check(tx, victim_id: int, attacker_id: int) -> bool:
        """Retourne True si victim_id a un droit de représailles actif contre attacker_id."""
        row = tx.one(
            """
            SELECT 1 FROM consequence
            WHERE victim_id = %s AND attacker_id = %s AND delete_at > %s
            LIMIT 1
            """,
            (int(victim_id), int(attacker_id), tx.now),
        )
        return row is not None

    @staticmethod
    def get_for_victim(tx, victim_id: int) -> list[dict]:
        """Retourne les droits de représailles actifs pour une victime donnée, triés par date d'expiration."""
        return tx.all(
            """
            SELECT attacker_id, delete_at FROM consequence
            WHERE victim_id = %s AND delete_at > %s
            ORDER BY delete_at ASC
            """,
            (int(victim_id), tx.now),
        )

    @staticmethod
    def purge_expired(tx) -> int:
        """Supprime toutes les lignes dont delete_at <= now. Retourne le nombre supprimé."""
        return tx.execute(
            'DELETE FROM consequence WHERE delete_at <= %s',
            (tx.now,),
        )


