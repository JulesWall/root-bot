"""
Accès exclusif et persistance des préfixes personnalisés par serveur (guild_prefixes).

Permet à chaque serveur Discord de définir un préfixe textuel sur-mesure (ex: '!' ou 'r!').
Utilise la syntaxe MySQL ON DUPLICATE KEY UPDATE (UPSERT) pour insérer ou mettre à jour
l'enregistrement en une seule requête atomique.
"""

import data
from game.db.database import Database


class PrefixDB:
    """Gestionnaire de persistance des préfixes de serveurs dans MySQL."""

    def __init__(self, database=None):
        self.database = database or Database()

    @staticmethod
    def get(tx, guild_id: int) -> str:
        """Retourne le préfixe configuré du serveur ou data.DEFAULT_PREFIX ('+r')."""
        row = tx.one(
            'SELECT prefix FROM guild_prefixes WHERE guild_id = %s',
            (guild_id,)
        )
        return row['prefix'] if row else data.DEFAULT_PREFIX

    @staticmethod
    def set(tx, guild_id: int, prefix: str):
        """
        Insère ou met à jour le préfixe d'un serveur (UPSERT atomique).
        ON DUPLICATE KEY UPDATE évite le besoin d'un SELECT préalable.
        """
        tx.execute(
            """
            INSERT INTO guild_prefixes (guild_id, prefix)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE prefix = VALUES(prefix)
            """,
            (guild_id, prefix)
        )

    @staticmethod
    def delete(tx, guild_id: int):
        """Supprime la configuration personnalisée (retour immédiat au préfixe par défaut)."""
        tx.execute(
            'DELETE FROM guild_prefixes WHERE guild_id = %s',
            (guild_id,)
        )

    async def fetch(self, guild_id: int) -> str:
        """Lecture asynchrone concurrente du préfixe (utilisée dans main.py get_prefix_for_bot)."""
        return await self.database.run(lambda tx: self.get(tx, guild_id), readonly=True)

    async def save(self, guild_id: int, prefix: str):
        """Écriture asynchrone du préfixe validé."""
        await self.database.run(
            lambda tx: self.set(tx, guild_id, prefix),
            locks=[f'guild:{int(guild_id)}'],
        )

    # ── Préfixes Utilisateurs (MP) ───────────────────────────────────────────
    @staticmethod
    def get_user(tx, user_id: int) -> str:
        """Retourne le préfixe configuré de l'utilisateur en MP ou data.DEFAULT_PREFIX ('+r')."""
        row = tx.one(
            'SELECT prefix FROM user_prefixes WHERE user_id = %s',
            (user_id,)
        )
        return row['prefix'] if row else data.DEFAULT_PREFIX

    @staticmethod
    def set_user(tx, user_id: int, prefix: str):
        """Insère ou met à jour le préfixe personnel d'un utilisateur (UPSERT atomique)."""
        tx.execute(
            """
            INSERT INTO user_prefixes (user_id, prefix)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE prefix = VALUES(prefix)
            """,
            (user_id, prefix)
        )

    @staticmethod
    def delete_user(tx, user_id: int):
        """Supprime la configuration personnalisée en MP (retour à DEFAULT_PREFIX)."""
        tx.execute(
            'DELETE FROM user_prefixes WHERE user_id = %s',
            (user_id,)
        )

    async def fetch_user(self, user_id: int) -> str:
        """Lecture asynchrone concurrente du préfixe utilisateur."""
        return await self.database.run(lambda tx: self.get_user(tx, user_id), readonly=True)

    async def save_user(self, user_id: int, prefix: str):
        """Écriture asynchrone du préfixe utilisateur validé."""
        await self.database.run(
            lambda tx: self.set_user(tx, user_id, prefix),
            locks=[f'user:{int(user_id)}'],
        )

