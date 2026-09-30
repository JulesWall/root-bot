"""
Module de logique métier pour les opérations offensives PvP V2.

Conforme aux spécifications de design/PVP_V2_DECISIONS.md (Décisions 6, 7, 8, 9, 10, 12, 13, 14, 15) :
- Éligibilité : infrastructure >= 1, cible >= attaquant (sauf représailles < 72h).
- Déploiement : sélection d'une copie logicielle compilée détenue et non réservée.
- Ralentissement défensif passif : durée_effective = durée_base × (1 + défense / 500) plafonnée à ×10.
- Cycle de vie : installing (silencieux) -> active (infection persistante) -> completed / failed / cancelled.
- Contraintes de simultanéité : max 1 opération par famille et 3 opérations au total par attaquant.
- Familles gérées :
  • hostile_miner : siphonnage passif de 15% de la production du tier ciblé.
  • ransomware : blocage des commandes économiques jusqu'à paiement de la rançon (fixée par l'attaquant en RTM) ou patch.
  • currency_theft : vol direct de 25% du solde USD (plancher 50$ préservé, 5% de frais réseau).
  • saturation : réduction de 30% de la puissance offensive du canal offense pendant 6h.
  • espionage : cartographie complète des logiciels compilés, dossiers et jobs actifs (style directory).
  • software_theft : copie illicite d'un logiciel adverse identifié par scan.
- Diagnostic réseau (/hack diag) : détection des signatures hostiles actives.
- Analyse de trace (/hack trace) : identification de l'attaquant si non protégé par un patch, ouverture du droit de représailles 72h.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from game.db.consequence import ConsequenceDB
from game.db.players import PlayerData, UpdatePlayer
from game.db.pvp_v2_operations import PvpV2OperationsDB, PvpV2ActiveEffectsDB
from game.db.pvp_v2_patches import PvpV2PatchDB
from game.db.pvp_v2_research import PvpV2ResearchDB
from game.db.pvp_v2_software import PvpV2SoftwareDB
from game.game_error import GameError
from game.math_config import MathConfig

logger = logging.getLogger(__name__)


def _get_infra_level(row: dict | None) -> int:
    """Extrait le niveau d'infrastructure de manière sûre."""
    if not row:
        return 0
    return int(row.get('infrastructure_level') or row.get('firewall_level') or 0)


def compute_defensive_slowdown(victim_defense_power: int, base_duration_seconds: int) -> int:
    """Calcule la durée effective d'installation ralentie par la défense réseau (Décision 13).

    Formule pure : durée_effective = durée_base × (1 + victim_defense_power / defense_divisor)
    Plafonné à max_multiplier fois la durée de base.
    """
    cfg = MathConfig.get_pvp_v2_installation()
    divisor = int(cfg.get('defense_slowdown_divisor', 500))
    max_mult = int(cfg.get('defense_slowdown_max_multiplier', 10))

    defense_val = Decimal(str(max(0, victim_defense_power)))
    multiplier = Decimal('1') + (defense_val / Decimal(str(divisor)))
    if multiplier > Decimal(str(max_mult)):
        multiplier = Decimal(str(max_mult))

    return int((Decimal(str(base_duration_seconds)) * multiplier).to_integral_value())


def get_base_installation_duration(tier: int) -> int:
    """Retourne la durée de base en secondes pour l'installation d'un logiciel selon son tier."""
    cfg = MathConfig.get_pvp_v2_installation()
    durations = cfg.get('base_duration_seconds_by_tier', {})
    return int(durations.get(str(tier), 600))


class PvpV2OperationService:
    """Service centralisant les règles de déploiement, résolution, diagnostic et traces PvP V2."""

    @staticmethod
    def has_active_retaliation(tx, attacker_id: int, victim_id: int) -> bool:
        """Vérifie si l'attaquant possède un droit de représailles actif (< 72h) contre la cible."""
        return ConsequenceDB.check(tx, victim_id=int(attacker_id), attacker_id=int(victim_id))

    @classmethod
    def check_operation_eligibility(
        cls,
        tx,
        attacker_id: int,
        victim_id: int,
        copy_id: int | None = None,
        family: str = 'hostile_miner',
        tier: int | None = None,
    ) -> tuple[dict, dict, dict, bool]:
        """Vérifie l'ensemble des règles d'éligibilité pour lancer une opération offensive.

        Retourne :
            tuple: (attacker_row, victim_row, software_copy, is_retaliation)
        Lève :
            GameError avec code explicite en cas d'invalidation.
        """
        if int(attacker_id) == int(victim_id):
            raise GameError('op_self_target')

        attacker = PlayerData.get(tx, int(attacker_id))
        victim = PlayerData.get(tx, int(victim_id))

        attacker_infra = _get_infra_level(attacker)
        victim_infra = _get_infra_level(victim)

        if attacker_infra < 1:
            raise GameError('op_self_invulnerable')

        if victim_infra < 1:
            raise GameError('op_target_invulnerable')

        is_retaliation = cls.has_active_retaliation(tx, attacker_id, victim_id)
        if not is_retaliation and victim_infra < attacker_infra:
            raise GameError('op_target_protected')

        # Vérification et sélection de la copie logicielle
        if copy_id is not None:
            copy = PvpV2SoftwareDB.get_by_id(tx, int(copy_id))
            if not copy or int(copy.get('owner_id', 0)) != int(attacker_id):
                raise GameError('no_software_copy')
            if bool(copy.get('reserved')):
                raise GameError('copy_already_reserved')
        else:
            copies = PvpV2SoftwareDB.get_available_by_owner_family(tx, int(attacker_id), str(family))
            if tier is not None:
                copies = [c for c in copies if int(c['tier']) == int(tier)]
            if not copies:
                raise GameError('no_software_copy')
            copy = copies[0]

        fingerprint = copy['fingerprint']
        family_name = copy['family']

        # Vérification des défenses de la cible : patch déjà installé
        if PvpV2PatchDB.is_installed(tx, int(victim_id), fingerprint):
            raise GameError('victim_patched')

        # Vérification qu'un effet avec cette empreinte n'est pas déjà actif sur la cible
        if PvpV2ActiveEffectsDB.is_active_fingerprint_on_victim(tx, int(victim_id), fingerprint):
            raise GameError('fingerprint_already_active', fingerprint=fingerprint)

        # Plafonds de l'attaquant (Décision 14) :
        # - Max 1 opération active par famille
        if PvpV2OperationsDB.count_active_by_attacker_family(tx, int(attacker_id), family_name) >= 1:
            raise GameError('max_family_operations_reached', family=family_name)

        # - Max 3 opérations actives au total
        if PvpV2OperationsDB.count_active_by_attacker(tx, int(attacker_id)) >= 3:
            raise GameError('max_total_operations_reached')

        return attacker, victim, copy, is_retaliation

    @classmethod
    def calculate_operation_quote(
        cls,
        tx,
        attacker_id: int,
        victim_id: int,
        copy_id: int | None = None,
        family: str = 'hostile_miner',
        tier: int | None = None,
        ransom_rtm: str | None = None,
    ) -> dict:
        """Calcule le devis d'installation d'une opération offensive."""
        from utils.time_format import format_duration

        attacker, victim, copy, is_retaliation = cls.check_operation_eligibility(
            tx, attacker_id, victim_id, copy_id=copy_id, family=family, tier=tier
        )

        victim_stats = MathConfig.calculate_player_stats(victim)
        defense_power = int(victim_stats.get('total_bay_defense', 0) or 0) + int(victim_stats.get('network_defense', 0) or 0)

        base_duration = get_base_installation_duration(int(copy['tier']))
        effective_duration = compute_defensive_slowdown(defense_power, base_duration)

        cfg = MathConfig.get_pvp_v2_installation()
        divisor = cfg.get('defense_divisor', 500)
        multiplier = min(cfg.get('max_multiplier', 10.0), 1.0 + (defense_power / divisor))

        # Rançon par défaut pour les ransomwares (si non spécifiée)
        default_ransom = Decimal('0.005') * Decimal(str(copy['tier']))
        final_ransom_rtm = Decimal(str(ransom_rtm)) if ransom_rtm else default_ransom

        return {
            'attacker_id': int(attacker_id),
            'victim_id': int(victim_id),
            'copy_id': int(copy['id']),
            'family': copy['family'],
            'tier': int(copy['tier']),
            'fingerprint': copy['fingerprint'],
            'victim_infrastructure': _get_infra_level(victim),
            'victim_defense_power': defense_power,
            'slowdown_multiplier': multiplier,
            'base_duration_seconds': base_duration,
            'duration_seconds': effective_duration,
            'duration_formatted': format_duration(effective_duration),
            'cost_rtm': Decimal('0.00000'),
            'ransom_rtm': final_ransom_rtm,
            'is_retaliation': is_retaliation,
        }

    @classmethod
    def start_operation(
        cls,
        tx,
        attacker_id: int,
        victim_id: int,
        copy_id: int | None = None,
        family: str = 'hostile_miner',
        tier: int | None = None,
        ransom_rtm: str | None = None,
        quoted_rtm: str | None = None,
    ) -> dict:
        """Démarre atomiquement une opération offensive après validation complète."""
        p1, p2 = sorted([int(attacker_id), int(victim_id)])
        tx.acquire_lock(f"player_{p1}")
        if p1 != p2:
            tx.acquire_lock(f"player_{p2}")

        quote = cls.calculate_operation_quote(
            tx, attacker_id, victim_id, copy_id=copy_id, family=family, tier=tier, ransom_rtm=ransom_rtm
        )

        copy = PvpV2SoftwareDB.get_by_id(tx, quote['copy_id'])
        resolves_at = tx.now + timedelta(seconds=quote['duration_seconds'])

        # Réservation de la copie logicielle pour éviter son usage concurrent ou sa vente
        PvpV2SoftwareDB.set_reserved(tx, int(copy['id']), True)

        op = PvpV2OperationsDB.create(
            tx,
            attacker_id=int(attacker_id),
            victim_id=int(victim_id),
            family=copy['family'],
            tier=int(copy['tier']),
            fingerprint=copy['fingerprint'],
            software_copy_id=int(copy['id']),
            rtm_cost=Decimal('0.00000'),
            resolves_at=resolves_at,
        )

        # Si ransomware, mémoriser le montant de la rançon dans l'opération via champ JSON ou table
        # Pour rester compatible sans ALTER TABLE, l'effect_data sera créé à la livraison
        return {
            'status': 'started',
            'operation_id': op['id'],
            'attacker_id': int(attacker_id),
            'victim_id': int(victim_id),
            'copy_id': int(copy['id']),
            'family': copy['family'],
            'tier': int(copy['tier']),
            'fingerprint': copy['fingerprint'],
            'duration_seconds': quote['duration_seconds'],
            'resolves_at': resolves_at,
            'ransom_rtm': quote['ransom_rtm'],
            'is_retaliation': quote['is_retaliation'],
        }

    @classmethod
    def deliver_installed_operations(cls, tx) -> list[dict]:
        """Résout atomiquement toutes les opérations dont l'installation est arrivée à échéance."""
        ready_ops = PvpV2OperationsDB.get_installing_ready(tx)
        if not ready_ops:
            return []

        delivered = []
        for op in ready_ops:
            attacker_id = int(op['attacker_id'])
            victim_id = int(op['victim_id'])
            fingerprint = op['fingerprint']
            copy_id = int(op['software_copy_id'])
            family = op['family']
            tier = int(op['tier'])

            p1, p2 = sorted([attacker_id, victim_id])
            tx.acquire_lock(f"player_{p1}")
            if p1 != p2:
                tx.acquire_lock(f"player_{p2}")

            # 1. Vérification si la cible a installé le patch pendant l'installation
            if PvpV2PatchDB.is_installed(tx, victim_id, fingerprint):
                PvpV2OperationsDB.mark_ended(tx, op['id'], 'failed', 'patched_during_install')
                PvpV2SoftwareDB.set_reserved(tx, copy_id, False)
                delivered.append({
                    'status': 'failed',
                    'reason': 'patched_during_install',
                    'operation_id': op['id'],
                    'attacker_id': attacker_id,
                    'victim_id': victim_id,
                    'family': family,
                    'fingerprint': fingerprint,
                    'tier': tier,
                })
                continue

            # 2. Vérification si la cible existe toujours
            try:
                victim = PlayerData.get(tx, victim_id)
            except GameError:
                victim = None

            if not victim:
                PvpV2OperationsDB.mark_ended(tx, op['id'], 'failed', 'victim_deleted')
                PvpV2SoftwareDB.set_reserved(tx, copy_id, False)
                delivered.append({
                    'status': 'failed',
                    'reason': 'victim_deleted',
                    'operation_id': op['id'],
                    'attacker_id': attacker_id,
                    'victim_id': victim_id,
                    'family': family,
                    'fingerprint': fingerprint,
                    'tier': tier,
                })
                continue

            # 3. Résolution selon la famille
            if family == 'hostile_miner':
                PvpV2OperationsDB.mark_active(tx, op['id'])
                effect_data = {'siphon_rate': 0.15}
                effect = PvpV2ActiveEffectsDB.create(
                    tx,
                    operation_id=op['id'],
                    attacker_id=attacker_id,
                    victim_id=victim_id,
                    family=family,
                    tier=tier,
                    fingerprint=fingerprint,
                    effect_data=effect_data,
                )
                delivered.append({
                    'status': 'active',
                    'operation_id': op['id'],
                    'effect_id': effect['id'],
                    'attacker_id': attacker_id,
                    'victim_id': victim_id,
                    'family': family,
                    'fingerprint': fingerprint,
                    'tier': tier,
                })

            elif family == 'ransomware':
                PvpV2OperationsDB.mark_active(tx, op['id'])
                default_ransom = Decimal('0.005') * Decimal(str(tier))
                effect_data = {
                    'ransom_rtm': str(default_ransom),
                    'blocked_commands': ['buy', 'upgrade', 'compile', 'convert', 'trade', 'hourly', 'contract'],
                }
                effect = PvpV2ActiveEffectsDB.create(
                    tx,
                    operation_id=op['id'],
                    attacker_id=attacker_id,
                    victim_id=victim_id,
                    family=family,
                    tier=tier,
                    fingerprint=fingerprint,
                    effect_data=effect_data,
                )
                delivered.append({
                    'status': 'active',
                    'operation_id': op['id'],
                    'effect_id': effect['id'],
                    'attacker_id': attacker_id,
                    'victim_id': victim_id,
                    'family': family,
                    'fingerprint': fingerprint,
                    'tier': tier,
                    'ransom_rtm': default_ransom,
                })

            elif family == 'currency_theft':
                # Vol direct de 25% de la trésorerie USD (Décision 9)
                victim_usd = Decimal(str(victim.get('dollars', 0) or 0))
                theft_pct = Decimal('0.25')
                min_balance = Decimal('50.00')

                available_to_steal = max(Decimal('0.00'), victim_usd - min_balance)
                stolen_amount = (victim_usd * theft_pct).quantize(Decimal('0.01'))
                if stolen_amount > available_to_steal:
                    stolen_amount = available_to_steal.quantize(Decimal('0.01'))

                fee_pct = Decimal('0.05')
                fee_amount = (stolen_amount * fee_pct).quantize(Decimal('0.01'))
                net_stolen = stolen_amount - fee_amount

                if stolen_amount > Decimal('0.00'):
                    attacker = PlayerData.get(tx, attacker_id)
                    attacker_usd = Decimal(str(attacker.get('dollars', 0) or 0))
                    UpdatePlayer.set(tx, victim_id, dollars=victim_usd - stolen_amount)
                    UpdatePlayer.set(tx, attacker_id, dollars=attacker_usd + net_stolen)

                PvpV2OperationsDB.mark_ended(tx, op['id'], 'completed', 'theft_executed')
                PvpV2SoftwareDB.set_reserved(tx, copy_id, False)

                delivered.append({
                    'status': 'completed',
                    'operation_id': op['id'],
                    'attacker_id': attacker_id,
                    'victim_id': victim_id,
                    'family': family,
                    'fingerprint': fingerprint,
                    'tier': tier,
                    'stolen_usd': stolen_amount,
                    'net_usd': net_stolen,
                })

            elif family == 'saturation':
                # Saturation offensive de 30% pendant 6h (Décision 10)
                PvpV2OperationsDB.mark_active(tx, op['id'])
                effect_data = {'reduction_rate': 0.30, 'duration_hours': 6}
                effect = PvpV2ActiveEffectsDB.create(
                    tx,
                    operation_id=op['id'],
                    attacker_id=attacker_id,
                    victim_id=victim_id,
                    family=family,
                    tier=tier,
                    fingerprint=fingerprint,
                    effect_data=effect_data,
                )
                delivered.append({
                    'status': 'active',
                    'operation_id': op['id'],
                    'effect_id': effect['id'],
                    'attacker_id': attacker_id,
                    'victim_id': victim_id,
                    'family': family,
                    'fingerprint': fingerprint,
                    'tier': tier,
                })

            elif family == 'espionage':
                # Espionnage : inventaire complet des logiciels et jobs (Décision 7)
                software_copies = PvpV2SoftwareDB.get_by_owner(tx, victim_id)
                folders = PvpV2ResearchDB.get_by_owner(tx, victim_id)
                patches = PvpV2PatchDB.get_by_owner(tx, victim_id)

                PvpV2OperationsDB.mark_ended(tx, op['id'], 'completed', 'espionage_executed')
                PvpV2SoftwareDB.set_reserved(tx, copy_id, False)

                delivered.append({
                    'status': 'completed',
                    'operation_id': op['id'],
                    'attacker_id': attacker_id,
                    'victim_id': victim_id,
                    'family': family,
                    'fingerprint': fingerprint,
                    'tier': tier,
                    'report_data': {
                        'software': [{'family': s['family'], 'tier': s['tier'], 'fingerprint': s['fingerprint']} for s in software_copies],
                        'folders': [{'family': f['family'], 'tier': f['tier'], 'fingerprint': f['fingerprint'], 'channel': f.get('channel')} for f in folders],
                        'patches': [{'family': p['family'], 'fingerprint': p['fingerprint'], 'installed': bool(p.get('installed'))} for p in patches],
                    },
                })

            elif family == 'software_theft':
                # Vol de copie logicielle (Décision 12)
                victim_copies = PvpV2SoftwareDB.get_by_owner(tx, victim_id)
                stolen_copy = None
                if victim_copies:
                    # Copie le premier logiciel disponible
                    target_copy = victim_copies[0]
                    stolen_copy = PvpV2SoftwareDB.create(
                        tx,
                        owner_id=attacker_id,
                        family=target_copy['family'],
                        tier=int(target_copy['tier']),
                        fingerprint=target_copy['fingerprint'],
                        origin='stolen',
                    )

                PvpV2OperationsDB.mark_ended(tx, op['id'], 'completed', 'software_stolen')
                PvpV2SoftwareDB.set_reserved(tx, copy_id, False)

                delivered.append({
                    'status': 'completed',
                    'operation_id': op['id'],
                    'attacker_id': attacker_id,
                    'victim_id': victim_id,
                    'family': family,
                    'fingerprint': fingerprint,
                    'tier': tier,
                    'stolen_software': stolen_copy,
                })

            else:
                # Famille générique
                PvpV2OperationsDB.mark_active(tx, op['id'])
                effect = PvpV2ActiveEffectsDB.create(
                    tx,
                    operation_id=op['id'],
                    attacker_id=attacker_id,
                    victim_id=victim_id,
                    family=family,
                    tier=tier,
                    fingerprint=fingerprint,
                )
                delivered.append({
                    'status': 'active',
                    'operation_id': op['id'],
                    'effect_id': effect['id'],
                    'attacker_id': attacker_id,
                    'victim_id': victim_id,
                    'family': family,
                    'fingerprint': fingerprint,
                    'tier': tier,
                })

        return delivered

    @classmethod
    def calculate_diagnosis_quote(cls, tx, player_id: int) -> dict:
        """Calcule le devis pour un diagnostic réseau."""
        cfg = MathConfig.load().get('pvp_v2', {}).get('diagnosis', {})
        cost_rtm = Decimal(str(cfg.get('cost_rtm', '0.001')))
        player = PlayerData.get(tx, int(player_id))
        return {
            'player_id': int(player_id),
            'cost_rtm': cost_rtm,
            'duration_seconds': int(cfg.get('base_duration_seconds', 0)),
        }

    @classmethod
    def run_diagnosis(cls, tx, player_id: int, quoted_rtm: str | None = None) -> dict:
        """Effectue un diagnostic et retourne les malwares actifs détectés sur le réseau."""
        tx.acquire_lock(f"player_{int(player_id)}")
        player = PlayerData.get(tx, int(player_id))
        cfg = MathConfig.load().get('pvp_v2', {}).get('diagnosis', {})
        cost_rtm = Decimal(str(cfg.get('cost_rtm', '0.001')))

        if quoted_rtm is not None:
            if Decimal(str(quoted_rtm)) != cost_rtm:
                raise GameError('quote_changed')

        player_rtm = Decimal(str(player.get('rootium', 0) or 0))
        if player_rtm < cost_rtm:
            raise GameError('insufficient_rootium', rtm=f"{cost_rtm:,.5f}")

        if cost_rtm > 0:
            UpdatePlayer.set(tx, int(player_id), rootium=player_rtm - cost_rtm)

        active_effects = PvpV2ActiveEffectsDB.get_active_on_victim(tx, int(player_id))
        detected = [
            {
                'id': ef['id'],
                'family': ef['family'],
                'tier': int(ef['tier']),
                'fingerprint': ef['fingerprint'],
                'started_at': ef['started_at'],
            }
            for ef in active_effects
        ]
        return {
            'player_id': int(player_id),
            'cost_rtm': cost_rtm,
            'detected_count': len(detected),
            'malwares': detected,
        }

    @classmethod
    def calculate_trace_quote(cls, tx, player_id: int) -> dict:
        """Calcule le devis pour une analyse de trace réseau."""
        cfg = MathConfig.load().get('pvp_v2', {}).get('trace_analysis', {})
        cost_rtm = Decimal(str(cfg.get('cost_rtm', '0.002')))
        active_effects = PvpV2ActiveEffectsDB.get_active_on_victim(tx, int(player_id))
        return {
            'player_id': int(player_id),
            'cost_rtm': cost_rtm,
            'active_malware_count': len(active_effects),
        }

    @classmethod
    def run_trace_analysis(cls, tx, player_id: int, quoted_rtm: str | None = None) -> dict:
        """Exécute l'analyse de trace réseau pour identifier les attaquants des malwares actifs (Décision 15)."""
        tx.acquire_lock(f"player_{int(player_id)}")
        player = PlayerData.get(tx, int(player_id))
        cfg = MathConfig.load().get('pvp_v2', {}).get('trace_analysis', {})
        cost_rtm = Decimal(str(cfg.get('cost_rtm', '0.002')))

        if quoted_rtm is not None:
            if Decimal(str(quoted_rtm)) != cost_rtm:
                raise GameError('quote_changed')

        player_rtm = Decimal(str(player.get('rootium', 0) or 0))
        if player_rtm < cost_rtm:
            raise GameError('insufficient_rootium', rtm=f"{cost_rtm:,.5f}")

        active_effects = PvpV2ActiveEffectsDB.get_active_on_victim(tx, int(player_id))
        if not active_effects:
            raise GameError('trace_no_malware')

        if cost_rtm > 0:
            UpdatePlayer.set(tx, int(player_id), rootium=player_rtm - cost_rtm)

        traced_results = []
        identified_count = 0

        for ef in active_effects:
            attacker_id = int(ef['attacker_id'])
            fingerprint = ef['fingerprint']

            # Règle Décision 15 : Si l'attaquant a patché son propre réseau, la trace échoue
            is_attacker_patched = PvpV2PatchDB.is_installed(tx, attacker_id, fingerprint)
            if is_attacker_patched:
                traced_results.append({
                    'fingerprint': fingerprint,
                    'family': ef['family'],
                    'identified': False,
                    'attacker_id': None,
                })
            else:
                # Identification réussie : accorde 72h de représailles
                ConsequenceDB.insert(tx, victim_id=int(player_id), attacker_id=attacker_id, window_hours=72)
                identified_count += 1
                traced_results.append({
                    'fingerprint': fingerprint,
                    'family': ef['family'],
                    'identified': True,
                    'attacker_id': attacker_id,
                })

        return {
            'player_id': int(player_id),
            'cost_rtm': cost_rtm,
            'total_analyzed': len(active_effects),
            'identified_count': identified_count,
            'results': traced_results,
        }

    @classmethod
    def pay_ransom(cls, tx, victim_id: int, effect_id: int | None = None) -> dict:
        """Permet à la victime de payer la rançon d'un ransomware actif pour débloquer ses commandes (Décision 8)."""
        tx.acquire_lock(f"player_{int(victim_id)}")
        active_rw = PvpV2ActiveEffectsDB.get_active_on_victim_by_family(tx, int(victim_id), 'ransomware')
        if not active_rw:
            raise GameError('no_active_ransomware')

        effect = active_rw[0]
        if effect_id is not None:
            matching = [e for e in active_rw if int(e['id']) == int(effect_id)]
            if matching:
                effect = matching[0]

        attacker_id = int(effect['attacker_id'])
        effect_data = effect.get('effect_data') or {}
        if isinstance(effect_data, str):
            try:
                effect_data = json.loads(effect_data)
            except Exception:
                effect_data = {}

        ransom_rtm = Decimal(str(effect_data.get('ransom_rtm', '0.005')))
        victim = PlayerData.get(tx, int(victim_id))
        victim_rtm = Decimal(str(victim.get('rootium', 0) or 0))

        if victim_rtm < ransom_rtm:
            raise GameError('insufficient_rootium', rtm=f"{ransom_rtm:,.5f}")

        # Verrouillage et transfert
        tx.acquire_lock(f"player_{attacker_id}")
        attacker = PlayerData.get(tx, attacker_id)
        attacker_rtm = Decimal(str(attacker.get('rootium', 0) or 0))

        UpdatePlayer.set(tx, int(victim_id), rootium=victim_rtm - ransom_rtm)
        UpdatePlayer.set(tx, attacker_id, rootium=attacker_rtm + ransom_rtm)

        # Clôture de l'effet
        PvpV2ActiveEffectsDB.end_effect(tx, int(effect['id']), 'ransom_paid')
        if effect.get('operation_id'):
            PvpV2OperationsDB.mark_ended(tx, int(effect['operation_id']), 'completed', 'ransom_paid')

        return {
            'status': 'ransom_paid',
            'victim_id': int(victim_id),
            'attacker_id': attacker_id,
            'ransom_rtm': ransom_rtm,
            'fingerprint': effect['fingerprint'],
            'new_victim_rtm': victim_rtm - ransom_rtm,
        }

    @classmethod
    def get_active_effects(cls, tx, player_id: int) -> dict:
        """Retourne les effets actifs où le joueur est attaquant ou victime."""
        as_victim = PvpV2ActiveEffectsDB.get_active_on_victim(tx, int(player_id))
        as_attacker = PvpV2ActiveEffectsDB.get_active_by_attacker(tx, int(player_id))
        return {
            'as_victim': as_victim,
            'as_attacker': as_attacker,
        }
