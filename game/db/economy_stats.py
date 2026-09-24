"""
Module de suivi économique agrégé par heure.

Stocke des totaux par couple (heure UTC, joueur) dans economy_hourly.
Gère le calendrier des publications dans economy_reports (3 lignes : 1h, 24h, 72h).

Aucune logique Discord ici. Aucun recalcul de prix ou de règles de jeu.
Les montants utilisent Decimal, jamais float.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Liste fixe des colonnes numériques de economy_hourly.
# Toutes les lectures et écritures passent par cette liste.
# Les valeurs sont des Decimal pour les montants, int pour les compteurs.
# ------------------------------------------------------------------

# Colonnes de type BIGINT UNSIGNED (compteurs entiers)
_INT_COLUMNS = {
    'new_players', 'returning_players',
    'claims', 'full_claims',
    'miners_t1', 'miners_t2', 'miners_t3', 'miners_t4', 'miners_t5',
    'attack_bought', 'defense_bought',
    'upgrades_started',
    'conversions',
    'trades',
    'hourly_claims',
    'contracts_collected',
}

# Colonnes de type DECIMAL (montants)
_DECIMAL_COLUMNS = {
    'mining_rtm',
    'event_hash_usd', 'event_pin_usd', 'event_decode_usd',
    'event_anomaly_usd', 'event_buffer_usd', 'event_signal_usd', 'event_packet_usd',
    'grant_usd',
    'hourly_usd',
    'contracts_usd',
    'miners_usd', 'miners_rtm',
    'combat_usd', 'combat_rtm',
    'upgrades_usd',
    'compile_rtm', 'scan_rtm',
    'converted_rtm', 'converted_usd',
}

_ALL_COLUMNS = _INT_COLUMNS | _DECIMAL_COLUMNS

# Mini-jeux reconnus et leur colonne USD associée
_EVENT_COLUMNS = {
    'hash':    'event_hash_usd',
    'pin':     'event_pin_usd',
    'decode':  'event_decode_usd',
    'anomaly': 'event_anomaly_usd',
    'buffer':  'event_buffer_usd',
    'signal':  'event_signal_usd',
    'packet':  'event_packet_usd',
}

# Périodes gérées
_PERIODS = (1, 24, 72)


def _to_decimal(value) -> Decimal:
    """Convertit une valeur en Decimal proprement."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class EconomyStatsDB:
    """
    Accès aux données du suivi économique.
    Toutes les méthodes SQL reçoivent un objet Transaction existant (tx).
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    @staticmethod
    def initialize(tx) -> datetime:
        """
        Vérifie que les deux tables existent, crée les 3 lignes de calendrier
        si elles n'existent pas encore, et retourne tracking_start.

        Lève une RuntimeError si une table est absente (migration non appliquée).
        """
        # Vérification de l'existence des tables obligatoires
        for table in ('economy_hourly', 'economy_reports'):
            row = tx.one(
                "SELECT COUNT(*) AS cnt FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = %s",
                (table,),
            )
            if not row or int(row['cnt']) == 0:
                raise RuntimeError(
                    f"Table '{table}' absente. Appliquer migrations/001_economy_reports.sql avant d'activer le suivi."
                )

        # Création automatique de event_availability_logs si permissions accordées
        try:
            tx.execute(
                """
                CREATE TABLE IF NOT EXISTS event_availability_logs (
                    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    event               VARCHAR(32)     NOT NULL,
                    opened_at           DATETIME(6)     NOT NULL,
                    solved_at           DATETIME(6)     NOT NULL,
                    duration_seconds    INT UNSIGNED    NOT NULL,
                    winner_id           BIGINT UNSIGNED NULL,
                    reward              DECIMAL(30, 2)  NOT NULL DEFAULT 0.00,
                    INDEX idx_event_solved (event, solved_at),
                    INDEX idx_solved_at (solved_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )
        except Exception:
            pass

        # Lecture de l'état existant
        rows = tx.all('SELECT * FROM economy_reports ORDER BY period_hours')

        if rows:
            # Vérification de la cohérence : toutes les lignes doivent avoir le même tracking_start
            starts = {r['tracking_start'] for r in rows}
            if len(starts) > 1:
                raise RuntimeError(
                    "État economy_reports incohérent : plusieurs tracking_start distincts. "
                    "Correction manuelle requise."
                )
            if len(rows) != 3 or {r['period_hours'] for r in rows} != {1, 24, 72}:
                raise RuntimeError(
                    "État economy_reports incomplet (lignes manquantes). "
                    "Correction manuelle requise."
                )
            tracking_start = rows[0]['tracking_start']
            logger.info(
                "[EconomyStats] Suivi repris depuis tracking_start=%s", tracking_start
            )
            return tracking_start

        # Première initialisation : ancrage à la prochaine heure pleine UTC
        now = tx.now
        if isinstance(now, datetime) and now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        tracking_start = (now.replace(minute=0, second=0, microsecond=0, tzinfo=None)
                          + timedelta(hours=1))

        for period_hours in _PERIODS:
            tx.execute(
                """
                INSERT INTO economy_reports
                    (period_hours, tracking_start, next_start)
                VALUES (%s, %s, %s)
                """,
                (period_hours, tracking_start, tracking_start),
            )

        logger.info(
            "[EconomyStats] Première initialisation : tracking_start=%s", tracking_start
        )
        return tracking_start

    # ------------------------------------------------------------------
    # Construction des incréments (fonction pure, aucun SQL)
    # ------------------------------------------------------------------

    @staticmethod
    def build_increments(method: str, actor: int, result: dict) -> dict[int, dict]:
        """
        Traduit le résultat d'une action de jeu en dict d'incréments par joueur.

        Retourne {} si l'action n'est pas suivie ou n'a pas abouti.
        Lève ValueError si un champ indispensable est absent d'un résultat déclaré réussi.
        """
        actor = int(actor)

        if method == 'network':
            if result.get('is_new') is not True:
                return {}
            dollars = result.get('dollars')
            if dollars is None:
                raise ValueError("network réussi mais 'dollars' absent du résultat")
            return {actor: {'new_players': 1, 'grant_usd': _to_decimal(dollars)}}

        if method == 'claim':
            if result.get('claimed') is not True:
                return {}
            amount = result.get('amount')
            if amount is None:
                raise ValueError("claim réussi mais 'amount' absent du résultat")
            inc = {'claims': 1, 'mining_rtm': _to_decimal(amount)}
            if result.get('ram_was_full') is True:
                inc['full_claims'] = 1
            return {actor: inc}

        if method in _EVENT_COLUMNS:
            if result.get('status') != 'won':
                return {}
            reward = result.get('reward')
            if reward is None:
                raise ValueError(f"{method} gagné mais 'reward' absent du résultat")
            winner = result.get('winner')
            if winner is None:
                raise ValueError(f"{method} gagné mais 'winner' absent du résultat")
            col = _EVENT_COLUMNS[method]
            return {int(winner): {col: _to_decimal(reward)}}

        if method == 'buy':
            if result.get('bought') is not True:
                return {}
            kind = result.get('kind', '')
            usd_price = _to_decimal(result.get('usd_price') or 0)
            rtm_price = _to_decimal(result.get('rtm_price') or 0)
            tier = result.get('tier', 1)
            inc: dict = {}

            if kind == 'mining':
                inc['miners_usd'] = usd_price
                inc['miners_rtm'] = rtm_price
                col = f'miners_t{tier}'
                if col in _INT_COLUMNS:
                    inc[col] = 1
            elif kind == 'attack':
                inc['combat_usd'] = usd_price
                inc['combat_rtm'] = rtm_price
                inc['attack_bought'] = 1
            elif kind in ('bay_defense', 'defense'):
                inc['combat_usd'] = usd_price
                inc['combat_rtm'] = rtm_price
                inc['defense_bought'] = 1

            return {actor: inc} if inc else {}

        if method == 'upgrade':
            if result.get('upgrade_started') is not True:
                return {}
            usd_price = result.get('usd_price')
            if usd_price is None:
                raise ValueError("upgrade démarré mais 'usd_price' absent du résultat")
            return {actor: {'upgrades_started': 1, 'upgrades_usd': _to_decimal(usd_price)}}

        if method == 'compile':
            if result.get('compile_started') is not True:
                return {}
            rtm_paid = result.get('rtm_paid')
            if rtm_paid is None:
                raise ValueError("compile démarré mais 'rtm_paid' absent du résultat")
            return {actor: {'compile_rtm': _to_decimal(rtm_paid)}}

        if method == 'scan':
            if result.get('scan_started') is not True:
                return {}
            rtm_total = result.get('rtm_total')
            if rtm_total is None:
                raise ValueError("scan démarré mais 'rtm_total' absent du résultat")
            return {actor: {'scan_rtm': _to_decimal(rtm_total)}}

        if method == 'convert':
            if result.get('converted') is not True:
                return {}
            rtm_amount = result.get('rtm_amount')
            usd_amount = result.get('usd_amount')
            if rtm_amount is None or usd_amount is None:
                raise ValueError("conversion réussie mais montants absents du résultat")
            return {actor: {
                'conversions': 1,
                'converted_rtm': _to_decimal(rtm_amount),
                'converted_usd': _to_decimal(usd_amount),
            }}

        if method == 'trade':
            if result.get('trade_completed') is not True:
                return {}
            initiator = int(result.get('initiator', actor))
            target = result.get('target')
            if target is None:
                raise ValueError("trade complété mais 'target' absent du résultat")
            target = int(target)
            return {initiator: {'trades': 1}, target: {}}

        if method == 'hourly':
            if result.get('claimed') is not True:
                return {}
            total_usd = result.get('total_usd')
            if total_usd is None:
                raise ValueError("hourly réussi mais 'total_usd' absent du résultat")
            return {actor: {
                'hourly_claims': 1,
                'hourly_usd': _to_decimal(total_usd),
            }}

        if method == 'contract':
            if result.get('collected') is not True:
                return {}
            reward_usd = result.get('reward_usd')
            if reward_usd is None:
                raise ValueError("contract collecté mais 'reward_usd' absent du résultat")
            return {actor: {
                'contracts_collected': 1,
                'contracts_usd': _to_decimal(reward_usd),
            }}

        return {}

    # ------------------------------------------------------------------
    # Écriture atomique des incréments
    # ------------------------------------------------------------------

    @staticmethod
    def add(tx, bucket_start: datetime, increments: dict[int, dict]) -> None:
        """
        Applique les incréments dans la transaction, par joueur dans l'ordre croissant des IDs.

        Pour chaque joueur :
        1. Vérifie si c'est sa première apparition dans economy_hourly (returning_players).
        2. INSERT … ON DUPLICATE KEY UPDATE avec les colonnes de l'incrément.
        """
        if not increments:
            return

        # Cache local pour éviter plusieurs EXISTS par joueur dans la même transaction
        _returning_cache: dict[int, bool] = {}

        for player_id in sorted(increments.keys()):
            inc = increments[player_id]
            if not isinstance(inc, dict):
                continue

            # Filtre et validation des colonnes
            filtered = {k: v for k, v in inc.items() if k in _ALL_COLUMNS}

            # Calcul du flag returning_players (une seule fois par joueur par bucket)
            if player_id not in _returning_cache:
                row = tx.one(
                    """
                    SELECT 1 FROM economy_hourly
                    WHERE player_id = %s AND bucket_start < %s
                    LIMIT 1
                    """,
                    (player_id, bucket_start),
                )
                _returning_cache[player_id] = (row is not None)

            is_returning = _returning_cache[player_id]

            # Préparation de l'INSERT
            # On insère toujours au moins la ligne (même vide pour assurer la présence du joueur)
            insert_cols = ['bucket_start', 'player_id']
            insert_vals = [bucket_start, player_id]

            if is_returning:
                insert_cols.append('returning_players')
                insert_vals.append(1)

            for col, val in filtered.items():
                insert_cols.append(col)
                if col in _DECIMAL_COLUMNS:
                    insert_vals.append(_to_decimal(val))
                else:
                    insert_vals.append(int(val))

            # Partie ON DUPLICATE KEY UPDATE
            # returning_players n'est PAS mis à jour si la ligne existe déjà
            update_parts = []
            update_vals = []
            for col, val in filtered.items():
                update_parts.append(f'{col} = {col} + %s')
                if col in _DECIMAL_COLUMNS:
                    update_vals.append(_to_decimal(val))
                else:
                    update_vals.append(int(val))

            cols_sql = ', '.join(insert_cols)
            placeholders = ', '.join(['%s'] * len(insert_vals))

            if update_parts:
                update_sql = ', '.join(update_parts)
                sql = (
                    f"INSERT INTO economy_hourly ({cols_sql}) VALUES ({placeholders}) "
                    f"ON DUPLICATE KEY UPDATE {update_sql}"
                )
                tx.execute(sql, (*insert_vals, *update_vals))
            else:
                # Ligne vide (ex: cible d'un trade) : INSERT IGNORE suffit
                sql = (
                    f"INSERT IGNORE INTO economy_hourly ({cols_sql}) VALUES ({placeholders})"
                )
                tx.execute(sql, tuple(insert_vals))

    # ------------------------------------------------------------------
    # Agrégation pour un bilan
    # ------------------------------------------------------------------

    @staticmethod
    def aggregate(tx, start: datetime, end: datetime) -> dict:
        """
        Lit et agrège les compteurs de economy_hourly pour la période [start, end).

        Retourne un dict avec tous les totaux et le nombre de joueurs distincts et de retour.
        """
        decimal_sums = ', '.join(
            f'COALESCE(SUM({col}), 0) AS {col}' for col in sorted(_DECIMAL_COLUMNS)
        )
        int_sums_excl_returning = ', '.join(
            f'COALESCE(SUM({col}), 0) AS {col}'
            for col in sorted(_INT_COLUMNS - {'new_players', 'returning_players'})
        )

        sql = f"""
            SELECT
                COUNT(DISTINCT player_id) AS active_players,
                COALESCE(SUM(new_players), 0) AS new_players,
                COALESCE(SUM(returning_players), 0) AS returning_players,
                {int_sums_excl_returning},
                {decimal_sums}
            FROM economy_hourly
            WHERE bucket_start >= %s AND bucket_start < %s
        """
        row = tx.one(sql, (start, end))
        if not row:
            result = EconomyStatsDB._empty_aggregate()
        else:
            result = {}
            for key, val in row.items():
                if key == 'active_players':
                    result[key] = int(val or 0)
                elif key in _INT_COLUMNS or key == 'new_players':
                    result[key] = int(val or 0)
                else:
                    result[key] = _to_decimal(val or 0)

        # Calcul du taux de rejoueurs de la période précédente
        prev_start = start - (end - start)
        retention_sql = """
            SELECT
                COUNT(DISTINCT p.player_id) AS prev_active_players,
                COUNT(DISTINCT r.player_id) AS retained_players
            FROM (
                SELECT DISTINCT player_id
                FROM economy_hourly
                WHERE bucket_start >= %s AND bucket_start < %s
            ) p
            LEFT JOIN (
                SELECT DISTINCT player_id
                FROM economy_hourly
                WHERE bucket_start >= %s AND bucket_start < %s
            ) r ON p.player_id = r.player_id
        """
        try:
            row_ret = tx.one(retention_sql, (prev_start, start, start, end))
            result['prev_active_players'] = int(row_ret['prev_active_players'] or 0) if row_ret else 0
            result['retained_players'] = int(row_ret['retained_players'] or 0) if row_ret else 0
        except Exception:
            result['prev_active_players'] = 0
            result['retained_players'] = 0

        # Suivi de la disponibilité des mini-jeux / événements
        event_avail = {}
        try:
            avail_sql = """
                SELECT
                    event,
                    COUNT(*) AS wins,
                    COALESCE(SUM(duration_seconds), 0) AS total_seconds,
                    COALESCE(AVG(duration_seconds), 0) AS avg_seconds
                FROM event_availability_logs
                WHERE solved_at >= %s AND solved_at < %s
                GROUP BY event
            """
            event_rows = tx.all(avail_sql, (start, end))
            for erow in (event_rows or []):
                ev = erow['event']
                event_avail[ev] = {
                    'wins': int(erow.get('wins') or 0),
                    'total_seconds': int(erow.get('total_seconds') or 0),
                    'avg_seconds': int(round(float(erow.get('avg_seconds') or 0))),
                    'ongoing': False,
                }
        except Exception:
            pass

        # Vérification des événements actuellement disponibles (non résolus dans la période)
        for ev in _EVENT_COLUMNS.keys():
            if ev not in event_avail:
                try:
                    db_ev = tx.one("SELECT * FROM events WHERE event = %s", (ev,))
                    if db_ev and db_ev.get('next_at'):
                        nxt = db_ev['next_at']
                        nxt_clean = nxt.replace(tzinfo=None) if getattr(nxt, 'tzinfo', None) else nxt
                        end_clean = end.replace(tzinfo=None) if getattr(end, 'tzinfo', None) else end
                        start_clean = start.replace(tzinfo=None) if getattr(start, 'tzinfo', None) else start
                        if nxt_clean < end_clean:
                            open_from = max(start_clean, nxt_clean)
                            dur = max(0, int((end_clean - open_from).total_seconds()))
                            if dur > 0:
                                event_avail[ev] = {
                                    'wins': 0,
                                    'total_seconds': dur,
                                    'avg_seconds': dur,
                                    'ongoing': True,
                                }
                except Exception:
                    pass

        result['event_availability'] = event_avail
        return result

    @staticmethod
    def _empty_aggregate() -> dict:
        result = {
            'active_players': 0,
            'prev_active_players': 0,
            'retained_players': 0,
            'event_availability': {},
        }
        for col in _INT_COLUMNS:
            result[col] = 0
        for col in _DECIMAL_COLUMNS:
            result[col] = Decimal('0')
        return result

    # ------------------------------------------------------------------
    # Gestion du calendrier des bilans
    # ------------------------------------------------------------------

    @staticmethod
    def prepare_report(tx, period_hours: int, channel_id: int | None) -> dict | None:
        """
        Retourne le bilan déjà en attente, ou prépare celui qui vient d'arriver à échéance.
        Retourne None si rien n'est dû.

        Le payload sauvegardé contient les données agrégées brutes (montants en str).
        L'embed est construit par le Cog, pas ici.
        """
        row = tx.one(
            'SELECT * FROM economy_reports WHERE period_hours = %s FOR UPDATE',
            (period_hours,),
        )
        if not row:
            return None

        # Bilan déjà en attente : le retourner tel quel
        if row['pending_payload'] is not None:
            payload = row['pending_payload']
            if isinstance(payload, str):
                payload = json.loads(payload)
            return {
                'period_hours': period_hours,
                'pending_end': row['pending_end'],
                'pending_channel_id': row['pending_channel_id'],
                'data': payload,
            }

        # Vérification de l'échéance : next_start + period_hours + 2 min
        next_start = row['next_start']
        period_end = next_start + timedelta(hours=period_hours)

        now = tx.now
        if isinstance(now, datetime) and now.tzinfo is not None:
            now_naive = now.replace(tzinfo=None)
        else:
            now_naive = now

        if isinstance(period_end, datetime) and period_end.tzinfo is not None:
            period_end_naive = period_end.replace(tzinfo=None)
        else:
            period_end_naive = period_end

        deadline = period_end_naive + timedelta(minutes=2)
        if now_naive < deadline:
            return None

        # Agrégation des données
        data = EconomyStatsDB.aggregate(tx, next_start, period_end)

        # Sérialisation : les Decimal → str pour JSON
        serializable = {
            k: str(v) if isinstance(v, Decimal) else v
            for k, v in data.items()
        }
        serializable['period_start'] = next_start.isoformat()
        serializable['period_end'] = period_end.isoformat()

        payload_json = json.dumps(serializable, default=str)

        tx.execute(
            """
            UPDATE economy_reports
            SET pending_end = %s, pending_payload = %s, pending_channel_id = %s
            WHERE period_hours = %s
            """,
            (period_end, payload_json, channel_id, period_hours),
        )

        return {
            'period_hours': period_hours,
            'pending_end': period_end,
            'pending_channel_id': channel_id,
            'data': serializable,
        }

    @staticmethod
    def ack_report(
        tx,
        period_hours: int,
        expected_start: datetime,
        expected_end: datetime,
        message_id: int,
    ) -> None:
        """
        Avance le calendrier après un envoi Discord confirmé.

        Idempotent : un second appel pour la même période ne fait rien.
        """
        row = tx.one(
            'SELECT * FROM economy_reports WHERE period_hours = %s FOR UPDATE',
            (period_hours,),
        )
        if not row:
            return

        # Vérification que la période correspond bien à ce qu'on confirme
        pending_end = row['pending_end']
        next_start = row['next_start']

        def _strip_tz(dt):
            if isinstance(dt, datetime) and dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
            return dt

        if _strip_tz(next_start) != _strip_tz(expected_start):
            logger.warning(
                "[EconomyStats] ack_report ignoré : next_start=%s != expected_start=%s",
                next_start, expected_start,
            )
            return
        if pending_end is None or _strip_tz(pending_end) != _strip_tz(expected_end):
            logger.warning(
                "[EconomyStats] ack_report ignoré : pending_end=%s != expected_end=%s",
                pending_end, expected_end,
            )
            return

        tx.execute(
            """
            UPDATE economy_reports
            SET next_start = %s,
                pending_end = NULL,
                pending_payload = NULL,
                pending_channel_id = NULL,
                last_message_id = %s,
                last_sent_at = UTC_TIMESTAMP(6)
            WHERE period_hours = %s
            """,
            (expected_end, message_id, period_hours),
        )
        logger.info(
            "[EconomyStats] Bilan %dh confirmé. next_start avancé à %s.",
            period_hours, expected_end,
        )

