"""
Gestionnaire de connexions et transactions MySQL hautement résilientes.

Conception architecturale :
1. Connexions éphémères et transactions courtes :
   Chaque opération ouvre une connexion dédiée, exécute la transaction, effectue le COMMIT et se ferme.
2. Verrous consultatifs applicatifs (GET_LOCK) :
   Sérialise les écritures d'un même compte via GET_LOCK(CONCAT(DATABASE(), ':player:<id>'), 10).
   Les actions multi-joueurs (trade, réputation) acquièrent les verrous dans un ordre
   déterministe (identifiants croissants) pour éviter tout interblocage.
   Le verrou global historique ':root-game' reste le repli des appelants non convertis.
3. Résilience aux interblocages (Deadlock Retry) :
   Intercepte les erreurs MySQL 1205 (Lock wait timeout) et 1213 (Deadlock found) et retente
   jusqu'à 3 fois avec un backoff progressif.
4. Non-blocage asynchrone (asyncio.to_thread) :
   Toutes les opérations synchrones du connecteur MySQL sont exécutées dans un thread séparé
   pour ne jamais figer la boucle événementielle Discord.
5. Chemin de lecture concurrente (readonly=True) :
   Les opérations en lecture seule (préfixe, langue, profil, classement) peuvent passer
   readonly=True pour contourner le verrou applicatif et s'exécuter simultanément.
   Ce chemin utilise autocommit=True et n'acquiert ni verrou ni transaction.
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from decimal import Decimal

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

from game.game_error import GameError


logger = logging.getLogger(__name__)

# Coupures / saturation du serveur — pas les erreurs de schéma ou de contrainte
_MYSQL_UNAVAILABLE_ERRNOS = {
    1040,  # Too many connections
    1129,  # Host blocked
    1205,  # Lock wait timeout (rejoué avant, relancé ici si épuisé)
    1213,  # Deadlock (idem)
    1290,  # Server running with --read-only
    2003,  # Can't connect
    2006,  # Server has gone away
    2013,  # Lost connection during query
    2055,  # Lost connection to MySQL server
    4031,  # Client connection idle timeout
}


# Nom du verrou global historique (repli pour les écritures hors compte joueur)
GLOBAL_LOCK_NAME = 'root-game'


def player_lock_name(discord_id: int) -> str:
    """Nom de verrou applicatif d'un compte joueur (sans préfixe de base)."""
    return f'player:{int(discord_id)}'


def encode(value):
    """Sérialise en JSON avec prise en charge native des objets datetime et Decimal."""
    return json.dumps(
        value,
        default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item),
        ensure_ascii=False
    )


def decode(value):
    """Désérialise un JSON en convertissant automatiquement les nombres flottants en Decimal."""
    return json.loads(value, parse_float=Decimal) if isinstance(value, (str, bytes)) else value


class Transaction:
    """
    Encapsule un curseur MySQL en mode dictionnaire et bufferisé.
    Fournit l'horodatage serveur de référence (now en microsecondes UTC).
    """

    def __init__(self, connection, clock=None):
        self.cursor = connection.cursor(dictionary=True, buffered=True)
        # Verrous GET_LOCK acquis sur cette session, dans l'ordre d'acquisition
        self.acquired_locks: list[str] = []
        # Horodatage serveur UTC haute précision (DATETIME(6))
        self.now = clock() if clock else self.one('SELECT UTC_TIMESTAMP(6) AS now')['now']

    def acquire_lock(self, name: str, timeout: int = 10) -> None:
        """Acquiert un verrou consultatif nommé sur la session courante.

        Les noms sont portés au niveau session MySQL (GET_LOCK), indépendamment
        du COMMIT/ROLLBACK. Un nom déjà détenu par cette transaction est ignoré
        (GET_LOCK est réentrant : un second RELEASE_LOCK le laisserait coincé).
        """
        key = str(name)
        if not key or key in self.acquired_locks:
            return
        row = self.one(
            "SELECT GET_LOCK(CONCAT(DATABASE(), %s), %s) AS acquired",
            (f':{key}', int(timeout)),
        )
        if not row or row.get('acquired') != 1:
            raise GameError('busy')
        self.acquired_locks.append(key)

    def execute(self, sql: str, args=()) -> int:
        """Exécute une requête d'écriture (INSERT/UPDATE/DELETE) et retourne lastrowid."""
        self.cursor.execute(sql, args)
        return self.cursor.lastrowid

    def one(self, sql: str, args=()) -> dict | None:
        """Exécute une requête et retourne la première ligne trouvée ou None."""
        self.cursor.execute(sql, args)
        return self.cursor.fetchone()

    def all(self, sql: str, args=()) -> list[dict]:
        """Exécute une requête et retourne toutes les lignes correspondantes."""
        self.cursor.execute(sql, args)
        return self.cursor.fetchall()


class Database:
    """Gestionnaire de persistance MySQL pour le bot Root avec pool partagé et transactions résilientes."""

    # Registre partagé des pools de connexions indexé par configuration normalisée
    _pools: dict[tuple, MySQLConnectionPool] = {}
    _pool_lock = threading.Lock()

    def __init__(self, config=None, clock=None):
        self.config = config
        self.clock = clock

    def options(self) -> dict:
        """Résout les paramètres de connexion depuis l'environnement .env."""
        if self.config is not None:
            return dict(self.config)
        if not os.getenv('DB_USER'):
            raise GameError('database_unconfigured')
        return dict(
            host=os.getenv('DB_HOST', '127.0.0.1'),
            user=os.environ['DB_USER'],
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'root')
        )

    def _get_pool(self) -> MySQLConnectionPool:
        """
        Retourne le pool partagé pour la configuration courante (lazy-initialization thread-safe).
        Exécuté hors de la boucle événementielle Discord (au sein d'un thread worker).
        """
        opts = self.options()
        pool_key = tuple(sorted(opts.items()))
        with Database._pool_lock:
            if pool_key not in Database._pools:
                pool_size = min(32, max(1, int(os.getenv('DB_POOL_SIZE', '20'))))
                pool_name = f"root_pool_{len(Database._pools)}_{opts.get('database', 'root')}"
                Database._pools[pool_key] = MySQLConnectionPool(
                    pool_name=pool_name,
                    pool_size=pool_size,
                    pool_reset_session=True,
                    connection_timeout=5,
                    charset='utf8mb4',
                    sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION',
                    **opts,
                )
            return Database._pools[pool_key]

    @staticmethod
    def _acquire_connection(pool: MySQLConnectionPool, timeout: float = 5.0):
        """Acquiert une connexion du pool en attendant si le pool est temporairement saturé."""
        deadline = time.time() + timeout
        while True:
            try:
                return pool.get_connection()
            except mysql.connector.errors.PoolError as err:
                if "pool exhausted" in str(err).lower() and time.time() < deadline:
                    time.sleep(0.05)
                    continue
                raise

    @staticmethod
    def _cleanup(call):
        """Exécute une fonction de nettoyage (rollback, close) en masquant les erreurs secondaires."""
        try:
            call()
        except mysql.connector.Error:
            pass

    @staticmethod
    def _raise_mysql(error: mysql.connector.Error):
        """Journalise l'erreur MySQL réelle. 'database_unavailable' uniquement si la connexion est morte."""
        logger.exception("Erreur MySQL errno=%s: %s", getattr(error, 'errno', None), error)
        if getattr(error, 'errno', None) in _MYSQL_UNAVAILABLE_ERRNOS:
            raise GameError('database_unavailable') from error
        raise

    @staticmethod
    def normalize_locks(locks) -> list[str]:
        """Normalise la liste des verrous applicatifs à acquérir.

        - None  → verrou global historique (repli des appelants non convertis).
        - []    → aucun GET_LOCK initial (la fonction métier peut en poser ensuite).
        - liste → noms uniques triés (ordre déterministe anti-deadlock).
        """
        if locks is None:
            return [GLOBAL_LOCK_NAME]
        names = []
        seen = set()
        for item in locks:
            key = str(item)
            if key and key not in seen:
                seen.add(key)
                names.append(key)
        names.sort()
        return names

    @staticmethod
    def _release_session_locks(connection, names: list[str]) -> None:
        """Libère les GET_LOCK de session dans l'ordre inverse d'acquisition."""
        if not connection or not names:
            return
        cursor = None
        try:
            cursor = connection.cursor()
            for name in reversed(names):
                try:
                    cursor.execute(
                        "SELECT RELEASE_LOCK(CONCAT(DATABASE(), %s))",
                        (f':{name}',),
                    )
                    cursor.fetchall()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def run_sync(self, function, resource=None, readonly: bool = False, locks=None):
        """
        Exécute une fonction dans une transaction MySQL sécurisée par verrou applicatif et pool partagé.

        Si readonly=True : chemin de lecture concurrente.
          - Obtient une connexion du pool avec autocommit=True.
          - Aucun verrou applicatif GET_LOCK acquis.
          - Restitue la connexion au pool via connection.close().

        Si readonly=False (défaut) : chemin d'écriture.
          - Obtient une connexion du pool avec autocommit=False.
          - Acquiert les GET_LOCK demandés (par joueur, ou global si locks=None).
          - Exécute le code métier (qui peut poser des verrous supplémentaires via tx.acquire_lock).
          - Valide avec COMMIT.
          - Finalise la ressource mémoire (resource.finish()).
          - Libère explicitement tous les RELEASE_LOCK avant restitution au pool.
        """
        pool = None
        try:
            pool = self._get_pool()
        except mysql.connector.Error as error:
            self._raise_mysql(error)

        if readonly:
            connection = None
            tx = None
            try:
                connection = self._acquire_connection(pool)
                connection.autocommit = True
                tx = Transaction(connection, self.clock)
                return function(tx)
            except mysql.connector.Error as error:
                self._raise_mysql(error)
            finally:
                if tx:
                    self._cleanup(tx.cursor.close)
                if connection:
                    self._cleanup(connection.close)

        lock_names = self.normalize_locks(locks)

        for attempt in range(3):
            connection = None
            tx = None
            committed = False
            commit_started = False
            try:
                connection = self._acquire_connection(pool)
                connection.autocommit = False
                tx = Transaction(connection, self.clock)

                # Acquisition déterministe (noms déjà triés) — timeout 10 s par verrou
                for name in lock_names:
                    tx.acquire_lock(name)

                tx.now = self.clock() if self.clock else tx.one('SELECT UTC_TIMESTAMP(6) AS now')['now']
                if resource:
                    resource.begin(tx)

                result = function(tx)

                if resource:
                    resource.prepare(tx)

                commit_started = True
                connection.commit()
                committed = True

                if resource:
                    resource.finish()
                return result

            except mysql.connector.Error as error:
                if connection:
                    self._cleanup(connection.rollback)
                if resource and not committed:
                    if commit_started:
                        resource.uncertain()
                    else:
                        resource.rollback()
                # Tentative de rejeu automatique uniquement si le commit n'a pas été amorcé
                if not commit_started and error.errno in (1205, 1213) and attempt < 2:
                    time.sleep(0.05 * (attempt + 1))
                    continue
                self._raise_mysql(error)

            except BaseException:
                if connection:
                    self._cleanup(connection.rollback)
                if resource and not committed:
                    if commit_started:
                        resource.uncertain()
                    else:
                        resource.rollback()
                raise

            finally:
                held = list(tx.acquired_locks) if tx is not None else []
                self._release_session_locks(connection, held)
                if tx:
                    self._cleanup(tx.cursor.close)
                if connection:
                    self._cleanup(connection.close)

    async def run(self, function, resource=None, readonly: bool = False, locks=None):
        """
        Encapsule l'exécution synchrone run_sync dans asyncio.to_thread()
        afin de libérer la boucle événementielle du bot Discord.

        Passe readonly au chemin synchrone pour activer la lecture concurrente.
        locks : noms de verrous applicatifs (voir normalize_locks).
        """
        return await asyncio.to_thread(self.run_sync, function, resource, readonly, locks)

