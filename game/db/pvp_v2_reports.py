"""
Persistance des rapports de scan et d'espionnage PvP V2
(tables `pvp_v2_scan_reports` et `pvp_v2_espionage_reports`).

Les rapports sont des snapshots figés. Jamais mis à jour après création.
expires_at détermine la validité du rapport (24h par défaut, configurable dans math.json).
"""

import logging
import json
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class PvpV2ScanReportsDB:
    """Accès aux données pour la table pvp_v2_scan_reports."""

    @staticmethod
    def get_latest_valid(tx, attacker_id: int, victim_id: int) -> dict | None:
        """Retourne le rapport de scan le plus récent et encore valide pour cette paire.

        Utilisé pour valider un vol de logiciel (décision 12).
        """
        return tx.one(
            """
            SELECT * FROM pvp_v2_scan_reports
            WHERE attacker_id = %s AND victim_id = %s AND expires_at > %s
            ORDER BY scanned_at DESC
            LIMIT 1
            """,
            (int(attacker_id), int(victim_id), tx.now),
        )

    @staticmethod
    def get_by_attacker(tx, attacker_id: int) -> list:
        """Retourne tous les rapports de scan d'un attaquant, valides et périmés."""
        return tx.all(
            'SELECT * FROM pvp_v2_scan_reports WHERE attacker_id = %s ORDER BY scanned_at DESC',
            (int(attacker_id),),
        )

    @staticmethod
    def create(tx, attacker_id: int, victim_id: int, report_data: dict, validity_hours: int) -> dict:
        """Insère un rapport de scan horodaté figé.

        validity_hours doit venir de MathConfig (pvp_v2.network_scan.report_validity_hours).
        """
        expires_at = tx.now + timedelta(hours=int(validity_hours))
        report_json = json.dumps(report_data)
        report_id = tx.execute(
            """
            INSERT INTO pvp_v2_scan_reports
                (attacker_id, victim_id, scanned_at, expires_at, report_data)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (int(attacker_id), int(victim_id), tx.now, expires_at, report_json),
        )
        return {
            'id': report_id,
            'attacker_id': int(attacker_id),
            'victim_id': int(victim_id),
            'scanned_at': tx.now,
            'expires_at': expires_at,
            'report_data': report_data,
        }

    @staticmethod
    def delete_expired(tx) -> int:
        """Supprime les rapports périmés. Retourne le nombre supprimé.

        Appelé par une tâche de nettoyage périodique.
        """
        affected = tx.execute(
            'DELETE FROM pvp_v2_scan_reports WHERE expires_at <= %s',
            (tx.now,),
        )
        return int(affected) if affected else 0


class PvpV2EspionageReportsDB:
    """Accès aux données pour la table pvp_v2_espionage_reports."""

    @staticmethod
    def get_latest_valid(tx, attacker_id: int, victim_id: int) -> dict | None:
        """Retourne le rapport d'espionnage le plus récent et encore valide pour cette paire."""
        return tx.one(
            """
            SELECT * FROM pvp_v2_espionage_reports
            WHERE attacker_id = %s AND victim_id = %s AND expires_at > %s
            ORDER BY scanned_at DESC
            LIMIT 1
            """,
            (int(attacker_id), int(victim_id), tx.now),
        )

    @staticmethod
    def get_by_attacker(tx, attacker_id: int) -> list:
        """Retourne tous les rapports d'espionnage d'un attaquant."""
        return tx.all(
            'SELECT * FROM pvp_v2_espionage_reports WHERE attacker_id = %s ORDER BY scanned_at DESC',
            (int(attacker_id),),
        )

    @staticmethod
    def create(tx, attacker_id: int, victim_id: int, report_data: dict, validity_hours: int) -> dict:
        """Insère un rapport d'espionnage horodaté figé.

        validity_hours doit venir de MathConfig (pvp_v2.espionage.report_validity_hours).
        """
        expires_at = tx.now + timedelta(hours=int(validity_hours))
        report_json = json.dumps(report_data)
        report_id = tx.execute(
            """
            INSERT INTO pvp_v2_espionage_reports
                (attacker_id, victim_id, scanned_at, expires_at, report_data)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (int(attacker_id), int(victim_id), tx.now, expires_at, report_json),
        )
        return {
            'id': report_id,
            'attacker_id': int(attacker_id),
            'victim_id': int(victim_id),
            'scanned_at': tx.now,
            'expires_at': expires_at,
            'report_data': report_data,
        }

    @staticmethod
    def delete_expired(tx) -> int:
        """Supprime les rapports périmés. Retourne le nombre supprimé."""
        affected = tx.execute(
            'DELETE FROM pvp_v2_espionage_reports WHERE expires_at <= %s',
            (tx.now,),
        )
        return int(affected) if affected else 0

