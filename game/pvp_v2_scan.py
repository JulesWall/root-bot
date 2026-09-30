"""
Service métier du Scan réseau PvP V2 (Étape 5).

Conforme à design/PVP_V2_DECISIONS.md (Décision 11, 14, 15) et PVP_IMPLEMENTATION_PLAN.md.
Fournit :
- L'éligibilité stricte (Infrastructure >= 1, cible >= attaquant sauf représailles 72h).
- Le devis déterministe (coût 0.005 RTM, durée 90s, validité 24h depuis math.json).
- Le lancement du job différé sans jet de dés aléatoire ni secret_id obsolète.
- La capture de la photographie (snapshot) figée lors de la résolution (t = résolution).
- L'enregistrement du rapport dans pvp_v2_scan_reports et du droit de représailles dans consequence.
- La livraison par worker persistant et la consultation des rapports existants.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from game.db.consequence import ConsequenceDB
from game.db.hack import HackDB
from game.db.players import PlayerData, UpdatePlayer
from game.db.pvp_v2_dev_jobs import PvpV2DevJobsDB
from game.db.pvp_v2_patches import PvpV2PatchDB
from game.db.pvp_v2_software import PvpV2SoftwareDB
from game.game_error import GameError
from game.math_config import MathConfig

logger = logging.getLogger(__name__)


def _get_infra_level(row: dict | None) -> int:
    """Retourne le niveau d'infrastructure du joueur (alias de firewall_level en BDD)."""
    if not row:
        return 0
    val = row.get('infrastructure_level')
    if val is not None:
        return int(val or 0)
    return int(row.get('firewall_level', 0) or 0)


class PvpV2ScanService:
    """Logique métier et transactionnelle du scan réseau PvP V2."""

    @staticmethod
    def check_scan_eligibility(tx, attacker_id: int, victim_id: int) -> tuple[dict, dict, bool]:
        """Vérifie l'ensemble des règles d'éligibilité pour un scan réseau V2.

        Retourne (attacker_row, victim_row, is_retaliation).
        Lève GameError si une condition n'est pas remplie.
        """
        if int(attacker_id) == int(victim_id):
            raise GameError('self_target')

        try:
            attacker = PlayerData.get(tx, int(attacker_id))
        except GameError:
            attacker = None
        if not attacker:
            raise GameError('player_not_found')

        try:
            victim = PlayerData.get(tx, int(victim_id))
        except GameError:
            victim = None
        if not victim:
            raise GameError('target_not_registered')

        elig = MathConfig.get_pvp_v2_eligibility()
        min_lvl = int(elig.get('min_infrastructure_level_attacker', 1))
        attacker_infra = _get_infra_level(attacker)
        victim_infra = _get_infra_level(victim)

        # Attaquant doit posséder au moins le niveau minimum d'infrastructure
        if attacker_infra < min_lvl:
            raise GameError('scan_self_invulnerable')

        # Cible au niveau 0 est invulnérable
        if victim_infra == 0:
            raise GameError('scan_target_invulnerable')

        # Droit de représailles actif (< 72h)
        is_retaliation = ConsequenceDB.check(tx, victim_id=int(attacker_id), attacker_id=int(victim_id))

        # Règle d'écart de niveau : cible >= attaquant sauf si représailles
        if elig.get('target_must_be_equal_or_higher_level', True):
            if victim_infra < attacker_infra and not is_retaliation:
                raise GameError('scan_target_protected')

        # Vérification qu'un scan n'est pas déjà en cours pour cet attaquant
        active_scan = HackDB.get_active(tx, int(attacker_id), type='scan')
        if active_scan:
            exp = active_scan.get('expires_at')
            ts = int(exp.replace(tzinfo=timezone.utc).timestamp()) if isinstance(exp, datetime) else 0
            raise GameError('scan_in_progress', timestamp=ts)

        return attacker, victim, is_retaliation

    @classmethod
    def calculate_scan_quote(cls, tx, attacker_id: int, victim_id: int) -> dict:
        """Calcule le devis du scan réseau V2 après vérification d'éligibilité."""
        attacker, victim, is_retaliation = cls.check_scan_eligibility(tx, attacker_id, victim_id)
        scan_cfg = MathConfig.get_pvp_v2_network_scan()

        cost_rtm = Decimal(str(scan_cfg.get('cost_rtm', '0.005')))
        duration_seconds = int(scan_cfg.get('base_duration_seconds', 90))

        return {
            'attacker_id': int(attacker_id),
            'victim_id': int(victim_id),
            'cost_rtm': cost_rtm,
            'duration_seconds': duration_seconds,
            'attacker_infrastructure': _get_infra_level(attacker),
            'victim_infrastructure': _get_infra_level(victim),
            'is_retaliation': is_retaliation,
        }

    @classmethod
    def start_scan(cls, tx, attacker_id: int, victim_id: int, quoted_rtm: str | None = None) -> dict:
        """Débite le coût RTM et crée le job différé de scan réseau."""
        # Verrouillage atomique des deux joueurs par ID croissant
        p1, p2 = sorted([int(attacker_id), int(victim_id)])
        tx.acquire_lock(f"player_{p1}")
        if p1 != p2:
            tx.acquire_lock(f"player_{p2}")

        attacker, victim, is_retaliation = cls.check_scan_eligibility(tx, attacker_id, victim_id)
        scan_cfg = MathConfig.get_pvp_v2_network_scan()

        cost_rtm = Decimal(str(scan_cfg.get('cost_rtm', '0.005')))
        duration_seconds = int(scan_cfg.get('base_duration_seconds', 90))

        if quoted_rtm is not None:
            if Decimal(str(quoted_rtm)) != cost_rtm:
                raise GameError('quote_changed')

        attacker_rtm = attacker.get('rootium', Decimal('0'))
        if attacker_rtm < cost_rtm:
            raise GameError('insufficient_rootium', rtm=f"{cost_rtm:,.5f}")

        # Débit RTM immédiat
        UpdatePlayer.set(tx, int(attacker_id), rootium=attacker_rtm - cost_rtm)

        # Création du job différé
        expires_at = tx.now + timedelta(seconds=duration_seconds)
        job = HackDB.create_scan(
            tx,
            scanner_id=int(attacker_id),
            target_id=int(victim_id),
            rtm_paid=cost_rtm,
            boost_rtm=Decimal('0'),
            expires_at=expires_at,
        )

        return {
            'status': 'started',
            'scan_id': job['id'],
            'attacker_id': int(attacker_id),
            'victim_id': int(victim_id),
            'cost_rtm': cost_rtm,
            'duration_seconds': duration_seconds,
            'expires_at': expires_at,
            'is_retaliation': is_retaliation,
        }

    @staticmethod
    def build_scan_snapshot(tx, victim_row: dict) -> dict:
        """Capture la photographie figée (snapshot) de la victime au moment de la résolution.

        Champs approuvés dans math.json et décision 11 :
        - infrastructure_level
        - modules_by_tier (mining, attack, bay_defense)
        - total_hashrate_hs
        - estimated_production_rtm_h
        - memory_used_ratio
        - memory_buffer_rtm
        - memory_capacity_rtm
        - installed_software (famille, tier, empreinte)
        - installed_patches (famille, empreinte)
        - active_dev_jobs_count
        """
        victim_id = int(victim_row['discord_id'])
        victim_stats = MathConfig.calculate_player_stats(victim_row)
        accrual = MathConfig.compute_mining_progress(victim_row, victim_stats, tx.now)

        tiers = MathConfig.get_pvp_v2_tiers()
        modules_by_tier = {}
        for t in tiers:
            modules_by_tier[str(t)] = {
                'mining': int(victim_row.get(f'mining_t{t}', 0) or 0),
                'attack': int(victim_row.get(f'attack_t{t}', 0) or 0),
                'bay_defense': int(victim_row.get(f'bay_defense_t{t}', 0) or 0),
            }

        # Estimation production RTM horaire
        rate_per_min = Decimal(str(accrual.get('rate_per_min', 0) or 0))
        est_rtm_h = rate_per_min * Decimal('60')

        # Ratio mémoire vive utilisée
        buffer_rtm = Decimal(str(accrual.get('buffer', 0) or 0))
        capacity_rtm = Decimal(str(accrual.get('capacity_rtm', 0) or 0))
        ratio = float(buffer_rtm / capacity_rtm) if capacity_rtm > 0 else 0.0
        used_ratio = max(0.0, min(1.0, ratio))

        # Logiciels compilés / détenus
        software_copies = PvpV2SoftwareDB.get_by_owner(tx, victim_id)
        installed_software = [
            {
                'family': s['family'],
                'tier': int(s['tier']),
                'fingerprint': s['fingerprint'],
            }
            for s in software_copies
        ]

        # Correctifs (patches) installés
        patches = PvpV2PatchDB.get_by_owner(tx, victim_id)
        installed_patches = [
            {
                'family': p['family'],
                'fingerprint': p['fingerprint'],
            }
            for p in patches if p.get('installed')
        ]

        # Nombre de jobs de développement en cours
        active_dev_jobs = PvpV2DevJobsDB.get_all_active_by_player(tx, victim_id)

        return {
            'victim_id': victim_id,
            'infrastructure_level': _get_infra_level(victim_row),
            'modules_by_tier': modules_by_tier,
            'total_hashrate_hs': int(victim_stats.get('total_hashrate_hs', 0) or 0),
            'estimated_production_rtm_h': f"{est_rtm_h:,.5f}",
            'memory_used_ratio': round(used_ratio, 4),
            'memory_buffer_rtm': f"{buffer_rtm:,.5f}",
            'memory_capacity_rtm': f"{capacity_rtm:,.5f}",
            'installed_software': installed_software,
            'installed_patches': installed_patches,
            'active_dev_jobs_count': len(active_dev_jobs),
        }

    @classmethod
    def resolve_scan(cls, tx, scan_row: dict) -> dict:
        """Résout un job de scan arrivé à échéance et génère le rapport figé."""
        attacker_id = int(scan_row['discord_id'])
        victim_id = int(scan_row['target_id'])
        scan_id = int(scan_row['id'])

        p1, p2 = sorted([attacker_id, victim_id])
        tx.acquire_lock(f"player_{p1}")
        if p1 != p2:
            tx.acquire_lock(f"player_{p2}")

        try:
            victim = PlayerData.get(tx, victim_id)
        except GameError:
            victim = None
        if not victim:
            # Cas limite : la cible a été supprimée pendant le scan
            tx.execute('DELETE FROM hack WHERE id = %s', (scan_id,))
            return {
                'status': 'victim_deleted',
                'scan_id': scan_id,
                'attacker_id': attacker_id,
                'victim_id': victim_id,
            }

        # 1. Capture directe des données au moment de la résolution
        report_data = cls.build_scan_snapshot(tx, victim)

        # 2. Suppression du job hack
        tx.execute('DELETE FROM hack WHERE id = %s', (scan_id,))

        return {
            'status': 'delivered',
            'scan_id': scan_id,
            'attacker_id': attacker_id,
            'victim_id': victim_id,
            'report_data': report_data,
        }

    @classmethod
    def deliver_expired_scans(cls, tx) -> list[dict]:
        """Récupère et résout atomiquement tous les jobs de scan arrivés à échéance."""
        expired = tx.all(
            "SELECT * FROM hack WHERE type = 'scan' AND expires_at <= %s ORDER BY expires_at ASC FOR UPDATE",
            (tx.now,),
        )
        if not expired:
            return []

        delivered = []
        for row in expired:
            res = cls.resolve_scan(tx, row)
            delivered.append(res)

        return delivered
