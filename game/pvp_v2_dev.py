"""
Module de logique métier pour le cycle de développement logiciel et correctifs PvP V2.

Responsabilités :
- Génération d'empreintes courtes uniques par famille avec gestion des collisions.
- Calcul pur du ralentissement passif d'installation selon la défense réseau.
- Devis et validation des jobs de développement (offensifs et défensifs).
- Gestion des canaux concurrents (offense / defense).
- Installation idempotente des correctifs (patches).
- Consultation de la bibliothèque de logiciels et correctifs.
- Livraison atomique des jobs échus par le worker périodique.
"""

import logging
import secrets
from datetime import timedelta
from decimal import Decimal

from game.db.players import PlayerData, UpdatePlayer
from game.db.pvp_v2_dev_jobs import PvpV2DevJobsDB
from game.db.pvp_v2_patches import PvpV2PatchDB
from game.db.pvp_v2_research import PvpV2ResearchDB
from game.db.pvp_v2_software import PvpV2SoftwareDB
from game.game_error import GameError
from game.math_config import MathConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fonctions pures & utilitaires
# ---------------------------------------------------------------------------

def generate_unique_fingerprint(tx, family: str) -> str:
    """Génère une empreinte courte unique pour une famille donnée.

    Utilise l'alphabet et la longueur définis dans math.json (Décision 2).
    Effectue jusqu'à max_generation_attempts tentatives en cas de collision.
    Lève GameError('fingerprint_collision') si toutes les tentatives échouent.
    """
    fp_cfg = MathConfig.get_pvp_v2_fingerprint()
    alphabet = fp_cfg.get('alphabet', 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
    length = int(fp_cfg.get('length', 4))
    max_attempts = int(fp_cfg.get('max_generation_attempts', 10))

    for _ in range(max_attempts):
        candidate = ''.join(secrets.choice(alphabet) for _ in range(length))
        if not PvpV2ResearchDB.fingerprint_exists(tx, family, candidate):
            return candidate

    logger.error("Échec de génération d'empreinte unique pour la famille %s après %d tentatives", family, max_attempts)
    raise GameError('fingerprint_collision')


def compute_defensive_slowdown(victim_defense_power: int, base_duration_seconds: int) -> int:
    """Calcule la durée effective d'installation hostile ralentie par la défense réseau (Décision 13).

    Formule : durée_effective = durée_base × (1 + victim_defense_power / defense_divisor)
    Plafonné à max_multiplier fois la durée de base.
    Fonction pure, sans effet de bord ni dépendance externe.
    """
    divisor, max_mult = MathConfig.get_pvp_v2_defense_slowdown()
    power = max(0, int(victim_defense_power or 0))
    base = max(1, int(base_duration_seconds or 1))

    multiplier = 1.0 + (power / divisor)
    capped_multiplier = min(multiplier, float(max_mult))
    return int(base * capped_multiplier)


def get_dev_channel_for_job(job_type: str) -> str:
    """Détermine le canal ('offense' ou 'defense') selon le type de job."""
    if job_type in ('research', 'compile'):
        return 'offense'
    if job_type in ('patch_research', 'patch_compile'):
        return 'defense'
    raise GameError('invalid_selection')


def calculate_dev_quote(player_row: dict, stats: dict, job_type: str, family: str, tier: int, fingerprint: str | None = None) -> dict:
    """Calcule le devis (coût RTM, durée, puissance requise) pour un job de développement."""
    valid_families = MathConfig.get_pvp_v2_families()
    if family not in valid_families:
        raise GameError('invalid_selection')

    valid_tiers = MathConfig.get_pvp_v2_tiers()
    if tier not in valid_tiers:
        raise GameError('invalid_selection')

    channel = get_dev_channel_for_job(job_type)

    if channel == 'offense':
        power = int(stats.get('total_bits_per_s', 0) or 0)
        if power <= 0:
            raise GameError('no_attack_module')
    else:
        power = int(stats.get('total_bay_defense', 0) or 0)
        if power <= 0:
            raise GameError('no_defense_module')

    costs = MathConfig.get_pvp_v2_dev_costs(tier)
    cost_key_map = {
        'research': 'research_rtm',
        'compile': 'compile_rtm',
        'patch_research': 'patch_research_rtm',
        'patch_compile': 'patch_compile_rtm',
    }
    cost_key = cost_key_map.get(job_type)
    if not cost_key or cost_key not in costs:
        raise GameError('invalid_selection')

    rtm_cost = costs[cost_key]

    work_units = MathConfig.get_pvp_v2_dev_work_units(tier)
    bits_per_unit = MathConfig.get_pvp_v2_dev_bits_per_unit(job_type)
    total_bits_needed = work_units * bits_per_unit
    min_duration = MathConfig.get_pvp_v2_dev_min_duration()

    duration_seconds = max(min_duration, int(total_bits_needed / power))

    return {
        'job_type': job_type,
        'family': family,
        'tier': tier,
        'fingerprint': fingerprint,
        'channel': channel,
        'power': power,
        'rtm_cost': rtm_cost,
        'duration_seconds': duration_seconds,
    }


# ---------------------------------------------------------------------------
# Service Métier
# ---------------------------------------------------------------------------

class PvpV2DevService:
    """Service orchestrant le cycle de développement PvP V2."""

    @staticmethod
    def get_quote(tx, player_id: int, job_type: str, family: str, tier: int, fingerprint: str | None = None) -> dict:
        """Fournit un devis sans engagement pour un job de développement."""
        player = PlayerData.get(tx, player_id)
        if not player:
            raise GameError('player_not_found')

        stats = MathConfig.calculate_player_stats(player)
        quote = calculate_dev_quote(player, stats, job_type, family, tier, fingerprint=fingerprint)
        quote['status'] = 'quote'
        quote['player_rtm'] = player.get('rootium', Decimal('0'))
        return quote

    @staticmethod
    def start_job(
        tx,
        player_id: int,
        job_type: str,
        family: str,
        tier: int,
        fingerprint: str | None = None,
        quoted_rtm=None,
    ) -> dict:
        """Lance un job de développement après vérification des prérequis et débit du coût RTM."""
        player = PlayerData.get(tx, player_id)
        if not player:
            raise GameError('player_not_found')

        stats = MathConfig.calculate_player_stats(player)
        channel = get_dev_channel_for_job(job_type)

        # 1. Vérification du canal (1 job actif max par canal)
        active_job = PvpV2DevJobsDB.get_active_by_player_channel(tx, player_id, channel)
        if active_job is not None:
            raise GameError('channel_busy', channel=channel)

        # 2. Règles métier spécifiques par type de job
        resolved_fp = fingerprint
        if job_type == 'research':
            # Impossible de relancer une recherche si on possède déjà le dossier pour (family, tier)
            existing_folder = PvpV2ResearchDB.get_by_owner_family_tier(tx, player_id, family, tier)
            if existing_folder is not None:
                raise GameError('research_already_completed', family=family, tier=tier)
            resolved_fp = None

        elif job_type == 'compile':
            # Exige de détenir le dossier de recherche source
            folder = PvpV2ResearchDB.get_by_owner_family_tier(tx, player_id, family, tier)
            if folder is None:
                raise GameError('research_folder_required', family=family, tier=tier)
            # Hérite impérativement de l'empreinte du dossier source
            resolved_fp = folder['fingerprint']

        elif job_type in ('patch_research', 'patch_compile'):
            if resolved_fp and PvpV2PatchDB.is_installed(tx, player_id, resolved_fp):
                raise GameError('patch_already_installed', fingerprint=resolved_fp)

        # 3. Calcul du devis exact
        quote = calculate_dev_quote(player, stats, job_type, family, tier, fingerprint=resolved_fp)
        rtm_cost = quote['rtm_cost']

        # 4. Protection contre le glissement de devis
        if quoted_rtm is not None:
            quoted_d = Decimal(str(quoted_rtm))
            if quoted_d != rtm_cost:
                raise GameError('quote_changed')

        # 5. Vérification du solde RTM
        player_rtm = player.get('rootium', Decimal('0'))
        if player_rtm < rtm_cost:
            raise GameError('insufficient_rootium', rtm=f"{rtm_cost:,.5f}")

        # 6. Débit du coût RTM (consommé irréversiblement)
        UpdatePlayer.set(tx, player_id, rootium=player_rtm - rtm_cost)

        # 7. Création du job persistant
        resolves_at = tx.now + timedelta(seconds=quote['duration_seconds'])
        created_job = PvpV2DevJobsDB.create(
            tx,
            player_id=player_id,
            channel=channel,
            job_type=job_type,
            family=family,
            tier=tier,
            rtm_paid=rtm_cost,
            bits_per_s=quote['power'],
            resolves_at=resolves_at,
            fingerprint=resolved_fp,
        )

        return {
            'status': 'started',
            'job': created_job,
            'quote': quote,
            'resolves_at': resolves_at,
            'duration_seconds': quote['duration_seconds'],
        }

    @staticmethod
    def cancel_job(tx, player_id: int, channel: str) -> dict:
        """Annule le job en cours sur un canal. Les RTM engagés ne sont pas remboursés (Décision 3)."""
        if channel not in ('offense', 'defense'):
            raise GameError('invalid_selection')

        cancelled = PvpV2DevJobsDB.cancel_by_player_channel(tx, player_id, channel)
        if cancelled is None:
            raise GameError('no_active_job', channel=channel)

        return {
            'status': 'cancelled',
            'channel': channel,
            'cancelled_job': cancelled,
        }

    @staticmethod
    def install_patch(tx, player_id: int, patch_id: int | None = None, fingerprint: str | None = None) -> dict:
        """Installe un correctif (patch) de manière idempotente sur le réseau du joueur.

        Protège de façon permanente tous les modules actuels et futurs du tier concerné.
        """
        player = PlayerData.get(tx, player_id)
        if not player:
            raise GameError('player_not_found')

        target_patch = None
        if patch_id is not None:
            target_patch = PvpV2PatchDB.get_by_id(tx, int(patch_id))
            if not target_patch or int(target_patch['owner_id']) != int(player_id):
                raise GameError('patch_not_found')
        elif fingerprint:
            # Vérifier si déjà installé (idempotence)
            if PvpV2PatchDB.is_installed(tx, player_id, fingerprint):
                return {
                    'status': 'already_installed',
                    'fingerprint': str(fingerprint),
                    'idempotent': True,
                }
            all_patches = PvpV2PatchDB.get_by_owner(tx, player_id)
            target_patch = next((p for p in all_patches if p['fingerprint'] == fingerprint and not p['installed']), None)
            if not target_patch:
                raise GameError('patch_not_found')
        else:
            raise GameError('invalid_selection')

        # Idempotence : si déjà installé
        if target_patch['installed']:
            return {
                'status': 'already_installed',
                'patch_id': target_patch['id'],
                'fingerprint': target_patch['fingerprint'],
                'idempotent': True,
            }

        # Marque le patch comme installé
        PvpV2PatchDB.install(tx, int(target_patch['id']), player_id)

        # Neutralise les opérations hostiles actives correspondantes si la table pvp_v2_operations existe
        fp = target_patch['fingerprint']
        try:
            tx.execute(
                """
                UPDATE pvp_v2_operations
                SET status = 'completed'
                WHERE victim_id = %s AND fingerprint = %s AND status = 'active'
                """,
                (int(player_id), str(fp)),
            )
        except Exception:
            pass

        return {
            'status': 'installed',
            'patch_id': target_patch['id'],
            'family': target_patch['family'],
            'fingerprint': fp,
        }

    @staticmethod
    def get_library(tx, player_id: int) -> dict:
        """Retourne la bibliothèque logicielle complète du joueur."""
        player = PlayerData.get(tx, player_id)
        if not player:
            raise GameError('player_not_found')

        folders = PvpV2ResearchDB.get_by_owner(tx, player_id)
        copies = PvpV2SoftwareDB.get_by_owner(tx, player_id)
        patches = PvpV2PatchDB.get_by_owner(tx, player_id)
        active_jobs = PvpV2DevJobsDB.get_all_active_by_player(tx, player_id)

        return {
            'player_id': int(player_id),
            'research_folders': folders,
            'software_copies': copies,
            'patches': patches,
            'active_jobs': active_jobs,
        }

    @staticmethod
    def deliver_job(tx, job: dict) -> dict:
        """Résout un job de développement échu et crée l'actif correspondant atomiquement."""
        job_id = int(job['id'])
        player_id = int(job['player_id'])
        job_type = str(job['job_type'])
        family = str(job['family'])
        tier = int(job['tier'])
        fp = job.get('fingerprint')

        result = {
            'delivered': True,
            'job_id': job_id,
            'player_id': player_id,
            'job_type': job_type,
            'family': family,
            'tier': tier,
        }

        if job_type == 'research':
            # Génère l'empreinte courte unique et crée le dossier de recherche offensif
            assigned_fp = generate_unique_fingerprint(tx, family)
            folder = PvpV2ResearchDB.create(tx, player_id, 'offense', family, tier, assigned_fp)
            result['fingerprint'] = assigned_fp
            result['folder_id'] = folder['id']

        elif job_type == 'compile':
            # Crée une nouvelle copie utilisable portant l'empreinte du dossier source
            copy = PvpV2SoftwareDB.create(tx, player_id, family, tier, fp, origin='compiled')
            result['fingerprint'] = fp
            result['copy_id'] = copy['id']

        elif job_type == 'patch_research':
            assigned_fp = fp or generate_unique_fingerprint(tx, family)
            folder = PvpV2ResearchDB.create(tx, player_id, 'defense', family, tier, assigned_fp)
            result['fingerprint'] = assigned_fp
            result['folder_id'] = folder['id']

        elif job_type == 'patch_compile':
            patch = PvpV2PatchDB.create(tx, player_id, family, fp)
            result['fingerprint'] = fp
            result['patch_id'] = patch['id']

        else:
            raise GameError('invalid_selection')

        # Supprime le job traité (garantit une livraison unique)
        PvpV2DevJobsDB.delete(tx, job_id)
        return result
