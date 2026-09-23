"""
Accès exclusif et opérations métier sur la table SQL 'players'.

Ce module implémente les classes d'accès aux données (DAO / Repository) et la logique économique :
- ExistPlayer : Lecture et verrouillage d'un joueur en base (SELECT ... FOR UPDATE).
- NewPlayer : Création et dotation initiale d'un nouveau compte joueur.
- PlayerData : Vérification de l'existence préalable d'un profil de jeu.
- UpdatePlayer : Mise à jour sécurisée par liste blanche des colonnes autorisées.
- Player : Opérations de jeu conservées (network, buy, upgrade, reputation, top, set_language, get_language).
"""

from datetime import timedelta, timezone
from decimal import Decimal, InvalidOperation
import random

from game.db.consequence import ConsequenceDB
from game.db.daily_claim_stats import DailyClaimStatsDB
from game.db.database import Database, player_lock_name
from game.db.hack import HackDB
from game.db.hourly_stats import HourlyStatsDB
from game.db.pvp import PvpDB
from game.db.secret_ids import (
    ensure_player_secret,
    generate_unique,
    get_epoch,
    next_rotation_at,
    normalize_code,
    save_epoch,
    unix_ts,
)
from game.db.upgrades import UpgradesDB
from game.game_error import GameError
from game.math_config import MathConfig
from utils.text import format_usd
from utils.time_format import format_duration, format_remaining_time


def _calculate_module_price(column: str, tier: int = 1) -> tuple[Decimal, Decimal]:
    """
    Calcule le prix d'un module ou d'une amélioration en (USD, RTM) selon le type et le tier.
    
    Retourne :
        tuple[Decimal, Decimal]: (prix_usd, prix_rtm)
    """
    settings = MathConfig.load()
    if column == 'firewall':
        base_usd = Decimal(str(settings.get('firewall', {}).get('first_upgrade_usd', 0)))
        multiplier = Decimal(str(settings.get('firewall', {}).get('upgrade_multiplier', 1)))
        return base_usd * (multiplier ** max(0, tier - 1)), Decimal('0')

    if tier < 1 or tier > 5:
        raise GameError('invalid_selection')

    if column.startswith('mining_'):
        base = settings.get('mining', {}).get('cost_t1_usd', 0)
        mult = settings.get('mining', {}).get('cost_multiplier', 1)
        return Decimal(str(base)) * (Decimal(str(mult)) ** max(0, tier - 1)), Decimal('0')

    beta = settings.get('beta', {})
    if column.startswith('attack_'):
        factor = Decimal(str(beta.get('cost_multiplier', settings.get('mining', {}).get('cost_multiplier', 1)))) ** max(0, tier - 1)
        rtm = Decimal(str(beta.get('attack_price_t1_rtm', 0))) * factor
        return Decimal('0'), rtm

    if column.startswith('bay_defense_'):
        factor = Decimal(str(beta.get('cost_multiplier', settings.get('mining', {}).get('cost_multiplier', 1)))) ** max(0, tier - 1)
        usd = Decimal(str(beta.get('bay_defense_usd', 0))) * factor
        return usd, Decimal('0')

    raise GameError('invalid_selection')


def _settle_mining(tx, player_row: dict, now, stats: dict | None = None) -> dict:
    """Met à jour et persiste le tampon de minage du joueur jusqu'à l'instant présent.

    Calcule le Rootium accumulé depuis la dernière mise à jour (plafonné par la mémoire vive
    disponible), persiste le nouveau tampon et l'horodatage, puis renvoie l'état de minage.

    Cette « matérialisation » du tampon est indispensable avant tout changement de débit de
    minage (achat de module) afin de figer la production au taux réellement en vigueur.
    """
    if stats is None:
        stats = MathConfig.calculate_player_stats(player_row)
    state = MathConfig.compute_mining_progress(player_row, stats, now)
    UpdatePlayer.set(
        tx, int(player_row['discord_id']),
        mining_buffer=state['buffer'],
        mining_last_update_at=now,
    )
    player_row['mining_buffer'] = state['buffer']
    player_row['mining_last_update_at'] = now
    return state


class ExistPlayer:
    """Vérifie l'existence d'un joueur et charge son profil."""

    def __init__(self, database=None):
        self.database = database or Database()

    def get(self, tx, user_id: int) -> dict | None:
        """Charge le joueur au sein d'une transaction avec verrouillage de ligne (FOR UPDATE)."""
        return tx.one('SELECT * FROM players WHERE discord_id=%s FOR UPDATE', (user_id,))

    async def fetch(self, user_id: int) -> dict | None:
        """Lecture concurrente asynchrone pour vérifier l'existence hors transaction explicite."""
        return await self.database.run(
            lambda tx: tx.one('SELECT * FROM players WHERE discord_id=%s', (user_id,)),
            readonly=True,
        )


class NewPlayer:
    """Gestionnaire de création d'un profil joueur lors de son premier /network."""

    @staticmethod
    def create(tx, user_id: int, now, grant: Decimal) -> dict:
        """
        Crée le joueur en base s'il n'existe pas déjà, avec sa dotation initiale en USD.
        Idempotent : si le joueur existe déjà, retourne simplement ses données actuelles.
        """
        row = tx.one('SELECT * FROM players WHERE discord_id=%s FOR UPDATE', (user_id,))
        if row:
            row['is_new'] = False
            return row
        occupied = tx.all('SELECT secret_id FROM players WHERE secret_id IS NOT NULL')
        taken = {str(item['secret_id']) for item in occupied if item.get('secret_id')}
        secret_id = generate_unique(tx, taken)
        tx.execute(
            'INSERT INTO players (discord_id, dollars, created_at, secret_id) VALUES (%s, %s, %s, %s)',
            (user_id, grant, now, secret_id)
        )
        new_row = tx.one('SELECT * FROM players WHERE discord_id=%s', (user_id,))
        if new_row:
            new_row['is_new'] = True
        return new_row


class PlayerData:
    """Vérification stricte de l'inscription du joueur."""

    @staticmethod
    def get(tx, user_id: int) -> dict:
        """
        Retourne les données du joueur ou lève une GameError('no_network')
        si le joueur n'est pas encore inscrit sur Root.
        """
        row = tx.one('SELECT * FROM players WHERE discord_id=%s', (user_id,))
        if not row:
            raise GameError('no_network')
        return row


class UpdatePlayer:
    """Gestionnaire de mise à jour sécurisé des champs de la table players."""

    @staticmethod
    def set(tx, user_id: int, **values) -> dict:
        """
        Met à jour un sous-ensemble de colonnes pour un utilisateur donné.
        Sécurité : seules les colonnes déclarées dans 'allowed' peuvent être modifiées.
        """
        allowed = {
            'dollars', 'rootium', 'firewall_level',
            'reputation', 'next_reputation_at', 'network_defense', 'lang', 'events_won',
            'mining_buffer', 'mining_last_update_at', 'mining_last_claim_at',
            'secret_id', 'attack_points',
            'autoclaim_credits', 'autoclaim_active',
            'hourly_last_at', 'hourly_combo_bonus', 'hourly_streak',
        } | {f'{kind}_t{tier}' for kind in ('mining', 'attack', 'bay_defense') for tier in range(1, 7)}

        if not values or any(key not in allowed for key in values):
            raise GameError('invalid_selection')

        set_clause = ', '.join(f'{key}=%s' for key in values)
        tx.execute(f'UPDATE players SET {set_clause} WHERE discord_id=%s', (*values.values(), user_id))
        return tx.one('SELECT * FROM players WHERE discord_id=%s', (user_id,))


class Player:
    """Opérations et règles métier interactives liées au joueur."""

    @staticmethod
    def network(tx, actor: int) -> dict:
        """Crée ou consulte le profil réseau du joueur avec dotation de départ si nouveau."""
        settings = MathConfig.load()
        row = NewPlayer.create(tx, actor, tx.now, Decimal(str(settings['initial_grant_usd'])))
        active_upgrade = UpgradesDB.get_active(tx, actor)
        if active_upgrade:
            row['pending_upgrade'] = active_upgrade
        active_hack = HackDB.get_active(tx, actor)
        if active_hack:
            row['pending_hack'] = active_hack
        active_scan = HackDB.get_active(tx, actor, type='scan')
        if active_scan:
            row['pending_scan'] = active_scan
        retaliations = ConsequenceDB.get_for_victim(tx, actor)
        if retaliations:
            row['retaliations'] = retaliations

        stats = MathConfig.calculate_player_stats(row)
        if int(row.get('network_defense') or 0) != stats['network_defense']:
            UpdatePlayer.set(tx, actor, network_defense=stats['network_defense'])
            row['network_defense'] = stats['network_defense']
        row['stats'] = stats
        # Matérialisation du minage : accumule le Rootium miné et rafraîchit l'état mémoire
        row['mining_state'] = _settle_mining(tx, row, tx.now, stats)
        row = ensure_player_secret(tx, row)
        row['secret_id_display'] = row.get('secret_id')
        epoch = get_epoch(tx)
        if epoch is None:
            next_at = next_rotation_at(tx.now)
            save_epoch(tx, next_at)
        else:
            next_at = epoch['next_at']
        row['secret_next_at'] = next_at
        row['secret_next_ts'] = unix_ts(next_at)
        return row

    @staticmethod
    def find_by_secret_id(tx, code) -> dict:
        """Retrouve un joueur par secret_id. Inconnu, expiré ou mal formé → invalid_secret_id."""
        normalized = normalize_code(code)
        row = tx.one('SELECT * FROM players WHERE secret_id=%s', (normalized,))
        if not row:
            raise GameError('invalid_secret_id')
        return row

    @staticmethod
    def buy(tx, actor: int, **args) -> dict:
        """
        Achat de modules (mining, attack, bay_defense) avec devis et confirmation.
        
        Contrôles préalables :
        - Niveau de pare-feu minimal exigé selon beta.required_firewall et max_tier_above.
        - Vérification des soldes USD et RTM disponibles.
        - Calcul de l'impact statistique immédiat et projeté.
        - Crédit du module dans la colonne dédiée (ex: mining_t2).
        """
        settings = MathConfig.load()
        kind = args.get('kind', 'mining')
        try:
            tier = int(args.get('tier', 1))
        except (ValueError, TypeError):
            raise GameError('invalid_selection')

        if kind not in ('mining', 'attack', 'bay_defense', 'defense') or tier < 1 or tier > 5:
            raise GameError('invalid_selection')

        internal_kind = 'bay_defense' if kind == 'defense' else kind
        column = f'{internal_kind}_t{tier}'
        usd_price, rtm_price = _calculate_module_price(column, tier)

        if 'price' in args:
            usd_price, rtm_price = Decimal(str(args['price'])), Decimal('0')

        p = PlayerData.get(tx, actor)
        max_tier_above = int(settings.get('firewall', {}).get('max_tier_above', 1))
        required_firewall = int(settings.get('beta', {}).get('required_firewall', {}).get(internal_kind, 0))
        required_firewall = max(required_firewall, tier - max_tier_above)

        if int(p['firewall_level']) < required_firewall:
            raise GameError('firewall_required', level=required_firewall)

        if Decimal(p['dollars']) < usd_price or Decimal(p['rootium']) < rtm_price:
            usd_fmt = format_usd(usd_price)
            rtm_fmt = f"{rtm_price:,.5f}"
            if usd_price > 0 and rtm_price > 0:
                raise GameError('insufficient_funds_both', usd=usd_fmt, rtm=rtm_fmt)
            elif rtm_price > 0:
                raise GameError('insufficient_funds_rtm', rtm=rtm_fmt)
            else:
                raise GameError('insufficient_funds_usd', usd=usd_fmt)

        # Calcul de l'impact statistique
        stats_before = MathConfig.calculate_player_stats(p)
        stat_unit_val = MathConfig.get_module_stat(internal_kind, tier)

        # Informations mémoire vive (uniquement pertinentes pour le minage)
        ram_gain = MathConfig.get_module_ram(tier) if kind == 'mining' else 0
        ram_gain_fmt = MathConfig.format_memory(ram_gain)
        ram_cur_fmt = MathConfig.format_memory(stats_before['total_ram_bytes'])
        ram_new_fmt = MathConfig.format_memory(stats_before['total_ram_bytes'] + ram_gain)

        if kind == 'mining':
            stat_type = 'mining'
            stat_unit = 'H/s'
            stat_gain_fmt = MathConfig.format_hashrate(stat_unit_val)
            cur_fmt = MathConfig.format_hashrate(stats_before['total_hashrate_hs'])
            new_fmt = MathConfig.format_hashrate(stats_before['total_hashrate_hs'] + stat_unit_val)
        elif kind == 'attack':
            stat_type = 'attack'
            stat_unit = 'Bit/s'
            bits_cur = stats_before.get('total_bits_per_s', 0)
            stat_gain_fmt = MathConfig.format_bits_per_s(stat_unit_val)
            cur_fmt = MathConfig.format_bits_per_s(bits_cur)
            new_fmt = MathConfig.format_bits_per_s(bits_cur + stat_unit_val)
        else:  # bay_defense / defense
            stat_type = 'defense' if kind == 'defense' else 'bay_defense'
            stat_unit = 'DEF'
            stat_gain_fmt = f"+{stat_unit_val} DEF"
            cur_fmt = f"{stats_before['total_bay_defense']} DEF"
            new_fmt = f"{stats_before['total_bay_defense'] + stat_unit_val} DEF"

        # Phase 1 : Devis préalable sans prélèvement
        if not args.get('confirm'):
            return {
                'quote': True,
                'buy_quote': True,
                'kind': kind,
                'tier': tier,
                'usd_price': usd_price,
                'rtm_price': rtm_price,
                'current_usd': Decimal(str(p['dollars'])),
                'remaining_usd': Decimal(str(p['dollars'])) - usd_price,
                'current_rtm': Decimal(str(p['rootium'])),
                'remaining_rtm': Decimal(str(p['rootium'])) - rtm_price,
                'stat_type': stat_type,
                'stat_unit': stat_unit,
                'stat_gain': stat_unit_val,
                'stat_gain_formatted': stat_gain_fmt,
                'stat_current_formatted': cur_fmt,
                'stat_new_formatted': new_fmt,
                'ram_gain': ram_gain,
                'ram_gain_formatted': ram_gain_fmt,
                'ram_current_formatted': ram_cur_fmt,
                'ram_new_formatted': ram_new_fmt,
            }

        # Phase 2 : Exécution de l'achat
        # Matérialise le minage AVANT de modifier l'infrastructure : un nouveau module de minage
        # change le débit et la capacité mémoire, il faut donc figer la production au taux actuel.
        _settle_mining(tx, p, tx.now, stats_before)
        UpdatePlayer.set(
            tx, actor,
            dollars=Decimal(p['dollars']) - usd_price,
            rootium=Decimal(p['rootium']) - rtm_price,
            **{column: int(p.get(column, 0)) + 1}
        )
        return {
            'bought': True,
            'kind': kind,
            'tier': tier,
            'usd_price': usd_price,
            'rtm_price': rtm_price,
            'stat_type': stat_type,
            'stat_unit': stat_unit,
            'stat_gain': stat_unit_val,
            'stat_gain_formatted': stat_gain_fmt,
            'stat_current_formatted': cur_fmt,
            'stat_new_formatted': new_fmt,
            'ram_gain': ram_gain,
            'ram_gain_formatted': ram_gain_fmt,
            'ram_current_formatted': ram_cur_fmt,
            'ram_new_formatted': ram_new_fmt,
        }

    @staticmethod
    def claim(tx, actor: int, is_auto: bool = False, bypass_cooldown: bool = False) -> dict:
        """Réclame le Rootium miné accumulé et vide la mémoire vive du réseau.

        Mécanique :
        - Matérialise la production depuis le dernier /claim (plafonnée par la mémoire vive).
        - Crédite le Rootium extrait sur le solde du joueur.
        - Réinitialise le tampon de minage à zéro (mémoire disponible à 100 %).

        Cas particuliers :
        - Aucun module de minage installé (capacité nulle) -> 'no_miner'.
        - Rien à réclamer pour le moment (tampon vide) -> 'empty'.
        """
        p = PlayerData.get(tx, actor)

        # Délai d'attente minimal entre deux réclamations réussies (anti-spam)
        if not is_auto and not bypass_cooldown:
            cooldown = int(MathConfig.load().get('mining', {}).get('claim_cooldown_seconds', 0))
            last_claim = p.get('mining_last_claim_at')
            if cooldown > 0 and last_claim is not None and hasattr(last_claim, 'timestamp'):
                ref, now_ref = last_claim, tx.now
                if getattr(ref, 'tzinfo', None) is not None and getattr(now_ref, 'tzinfo', None) is None:
                    now_ref = now_ref.replace(tzinfo=timezone.utc)
                elif getattr(ref, 'tzinfo', None) is None and getattr(now_ref, 'tzinfo', None) is not None:
                    ref = ref.replace(tzinfo=now_ref.tzinfo)
                elapsed = (now_ref - ref).total_seconds()
                if elapsed < cooldown:
                    remaining = format_duration(cooldown - elapsed)
                    raise GameError('claim_cooldown', remaining=remaining, time=remaining)

        stats = MathConfig.calculate_player_stats(p)
        state = MathConfig.compute_mining_progress(p, stats, tx.now)

        claimed = state['buffer']

        # Temps écoulé depuis le dernier claim réussi (repli sur la création du réseau si jamais réclamé)
        last_claim_ref = p.get('mining_last_claim_at') or p.get('created_at')
        seconds_since_last_claim = None
        if last_claim_ref is not None and hasattr(last_claim_ref, 'timestamp'):
            ref, now_ref = last_claim_ref, tx.now
            if getattr(ref, 'tzinfo', None) is not None and getattr(now_ref, 'tzinfo', None) is None:
                from datetime import timezone as _tz
                now_ref = now_ref.replace(tzinfo=_tz.utc)
            elif getattr(ref, 'tzinfo', None) is None and getattr(now_ref, 'tzinfo', None) is not None:
                ref = ref.replace(tzinfo=now_ref.tzinfo)
            seconds_since_last_claim = max(0, int((now_ref - ref).total_seconds()))

        autoclaim_credits = int(p.get('autoclaim_credits', 0) or 0)
        autoclaim_active = int(p.get('autoclaim_active', 0) or 0)

        result = {
            'rate_per_min': state['rate_per_min'],
            'base_rate_per_min': state.get('base_rate_per_min', state['rate_per_min']),
            'reputation_points': state.get('reputation_points', 0),
            'reputation_multiplier': state.get('reputation_multiplier', Decimal('1')),
            'reputation_bonus_pct': state.get('reputation_bonus_pct', Decimal('0')),
            'capacity_rtm': state['capacity_rtm'],
            'total_ram_bytes': state['total_ram_bytes'],
            'total_ram_formatted': state['total_ram_formatted'],
            'total_hashrate_formatted': stats['total_hashrate_formatted'],
            'seconds_to_full': state['seconds_to_full'],
            'seconds_since_last_claim': seconds_since_last_claim,
            'is_auto': is_auto,
            'autoclaim_credits': autoclaim_credits,
            'autoclaim_active': autoclaim_active,
        }

        if state['capacity_rtm'] <= 0:
            result.update({'claimed': False, 'reason': 'no_miner', 'amount': Decimal('0')})
            return result

        if claimed <= 0:
            # Rien à créditer : on rafraîchit tout de même la base de référence temporelle
            UpdatePlayer.set(tx, actor, mining_buffer=Decimal('0'), mining_last_update_at=tx.now)
            result.update({'claimed': False, 'reason': 'empty', 'amount': Decimal('0')})
            return result

        new_rootium = Decimal(str(p['rootium'])) + claimed
        # ram_was_full : calculé à partir de l'état AVANT la vidange (is_full indique si le tampon
        # était au plafond). Doit être capturé ici, avant UpdatePlayer.set qui réinitialise le buffer.
        ram_was_full: bool = bool(state.get('is_full', False))
        UpdatePlayer.set(
            tx, actor,
            rootium=new_rootium,
            mining_buffer=Decimal('0'),
            mining_last_update_at=tx.now,
            mining_last_claim_at=tx.now,
        )
        DailyClaimStatsDB.record_claim(
            tx,
            discord_id=actor,
            claimed_at=tx.now,
            interval_seconds=seconds_since_last_claim,
            amount=claimed,
            is_auto=is_auto,
        )
        result.update({'claimed': True, 'amount': claimed, 'new_rootium': new_rootium, 'ram_was_full': ram_was_full})
        return result

    @staticmethod
    def start_autoclaim(tx, actor: int, count: int | str = 'all') -> dict:
        """Active l'autoclaim en consommant N crédits et en exécutant un premier claim immédiat."""
        p = PlayerData.get(tx, actor)
        stats = MathConfig.calculate_player_stats(p)
        state = MathConfig.compute_mining_progress(p, stats, tx.now)

        if state['capacity_rtm'] <= 0 or state['rate_per_min'] <= 0:
            raise GameError('no_miner_autoclaim')

        available = int(p.get('autoclaim_credits', 0) or 0)
        if available <= 0:
            raise GameError('insufficient_autoclaim_credits', available=0, requested=1)

        if isinstance(count, str) and count.lower() in ('all', 'tout'):
            amount = available
        else:
            try:
                amount = int(count)
            except (ValueError, TypeError):
                raise GameError('invalid_autoclaim_count')

        if amount <= 0 or amount > available:
            raise GameError('insufficient_autoclaim_credits', available=available, requested=amount)

        new_credits = available - amount
        new_active = int(p.get('autoclaim_active', 0) or 0) + amount

        UpdatePlayer.set(tx, actor, autoclaim_credits=new_credits, autoclaim_active=new_active)

        # Claim immédiat pour vider la RAM et lancer le cycle propre
        claim_res = Player.claim(tx, actor, is_auto=False, bypass_cooldown=True)
        claim_res['autoclaim_credits'] = new_credits
        claim_res['autoclaim_active'] = new_active

        return {
            'claim_result': claim_res,
            'activated_count': amount,
            'autoclaim_credits_remaining': new_credits,
            'autoclaim_active': new_active,
        }

    @staticmethod
    def cancel_autoclaim(tx, actor: int) -> dict:
        """Annule les autoclaims programmés en cours et restitue les crédits."""
        p = PlayerData.get(tx, actor)
        active = int(p.get('autoclaim_active', 0) or 0)
        if active <= 0:
            raise GameError('no_active_autoclaim')

        available = int(p.get('autoclaim_credits', 0) or 0) + active
        UpdatePlayer.set(tx, actor, autoclaim_credits=available, autoclaim_active=0)

        return {
            'refunded_count': active,
            'autoclaim_credits': available,
        }

    @staticmethod
    def process_autoclaim_tick(tx, actor: int) -> dict:
        """Exécute un claim automatique pour un joueur dont la RAM a atteint 99,9 %."""
        p = PlayerData.get(tx, actor)
        active = int(p.get('autoclaim_active', 0) or 0)
        if active <= 0:
            return {'claimed': False, 'reason': 'no_active'}

        claim_res = Player.claim(tx, actor, is_auto=True, bypass_cooldown=True)
        new_active = active - 1
        UpdatePlayer.set(tx, actor, autoclaim_active=new_active)

        claim_res['autoclaim_active_remaining'] = new_active
        claim_res['autoclaim_credits_remaining'] = int(p.get('autoclaim_credits', 0) or 0)
        claim_res['actor'] = actor
        return claim_res

    @staticmethod
    def get_active_autoclaim_players(tx) -> list[dict]:
        """Retourne la liste des joueurs ayant au moins un claim automatique programmé."""
        return tx.all("SELECT * FROM players WHERE autoclaim_active > 0")


    @staticmethod
    def compile(tx, actor: int, **args) -> dict:
        """Lance une production d'ATK à partir du débit des modules d'attaque.

        Le joueur choisit le nombre de points ATK ; le coût RTM et la durée
        en découlent. Le Bit/s matériel accélère la production.
        """
        method = MathConfig.normalize_compile_method(args.get('mode') or args.get('method'))
        if method is None:
            raise GameError('invalid_selection')

        p = PlayerData.get(tx, actor)
        active = HackDB.get_active(tx, actor)
        if active:
            exp = active.get('expires_at')
            ts = 0
            if exp is not None and hasattr(exp, 'timestamp'):
                aware = exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp
                ts = int(aware.timestamp())
            raise GameError(
                'compile_in_progress',
                method=active.get('method') or method,
                atk=int(active.get('atk_yield') or 0),
                timestamp=ts,
            )

        stats = MathConfig.calculate_player_stats(p)
        bits_per_s = int(stats.get('total_bits_per_s') or 0)
        if bits_per_s <= 0:
            raise GameError('no_attack_modules')

        raw_atk = args.get('atk', args.get('count', 'all'))
        want_all = bool(args.get('all'))
        if not want_all and isinstance(raw_atk, str):
            token = raw_atk.strip().lower().replace(',', '.')
            if token in ('all', 'tout', 'max', ''):
                want_all = True

        if want_all:
            atk = bits_per_s
        else:
            try:
                atk = int(str(raw_atk).strip())
            except (TypeError, ValueError):
                raise GameError('invalid_selection')
        if atk <= 0:
            raise GameError('invalid_selection')
        if atk > bits_per_s:
            raise GameError('compile_max_exceeded', max_atk=bits_per_s, bits_per_s=bits_per_s)

        quote = MathConfig.compile_quote(bits_per_s, atk, method)
        if quote['atk_yield'] <= 0:
            raise GameError('no_attack_modules')

        rtm_paid = quote['rtm_paid']
        quoted_rtm = args.get('quoted_rtm')
        quoted_atk = args.get('quoted_atk')
        quoted_duration = args.get('quoted_duration')
        if args.get('confirm'):
            if quoted_rtm is not None and Decimal(str(quoted_rtm)) != rtm_paid:
                raise GameError('quote_changed')
            if quoted_atk is not None and int(quoted_atk) != int(quote['atk_yield']):
                raise GameError('quote_changed')
            if quoted_duration is not None and int(quoted_duration) != int(quote['duration_seconds']):
                raise GameError('quote_changed')

        balance = Decimal(str(p.get('rootium') or 0))
        duration_seconds = int(quote['duration_seconds'])
        duration_str = format_duration(duration_seconds)
        expires_at = tx.now + timedelta(seconds=duration_seconds)
        ts = int(expires_at.replace(tzinfo=timezone.utc).timestamp()) if getattr(expires_at, 'tzinfo', None) is None else int(expires_at.timestamp())

        payload = {
            'method': method,
            'bits_formatted': MathConfig.format_bits_per_s(quote['bits_per_s']),
            'atk_yield': quote['atk_yield'],
            'rtm_paid': rtm_paid,
            'duration': duration_str,
            'duration_seconds': duration_seconds,
            'timestamp': ts,
        }
        if not args.get('confirm'):
            payload['compile_quote'] = True
            return payload

        if balance < rtm_paid:
            rtm_places = int(MathConfig.load().get('rtm_decimal_places', 5))
            raise GameError('insufficient_funds_rtm', rtm=f"{rtm_paid:,.{rtm_places}f}")

        UpdatePlayer.set(tx, actor, rootium=balance - rtm_paid)
        HackDB.create(
            tx, actor, method, quote['atk_yield'], rtm_paid, expires_at,
            bits_per_s=bits_per_s,
        )
        payload['compile_started'] = True
        payload['new_rootium'] = balance - rtm_paid
        return payload

    @staticmethod
    def scan(tx, actor: int, **args) -> dict:
        """Lance ou présente un devis pour scanner le réseau d'un autre joueur.

        Phase 1 (confirm=False) : vérifie toutes les règles PvP, calcule les probabilités
        estimées pour chaque niveau de boost et retourne un devis interactif.
        Phase 2 (confirm=True)  : re-vérifie, débite le RTM et insère le job de scan différé.
        """
        from game.db.consequence import ConsequenceDB

        cfg = MathConfig.load().get('scan', {})
        rtm_cost = Decimal(str(cfg.get('rtm_cost', '0.005')))
        duration = int(cfg.get('duration_seconds', 90))
        min_prob = float(cfg.get('min_success_prob', 0.05))
        boost_per_point = Decimal(str(cfg.get('boost_rtm_per_point', '0.001')))
        boost_levels = cfg.get('boost_levels', [1, 2, 5])

        target_id = int(args.get('target') or 0)
        if not target_id:
            raise GameError('invalid_selection')

        if int(actor) == target_id:
            raise GameError('self_target')

        # Lecture du scanner (avec verrou)
        scanner = tx.one('SELECT * FROM players WHERE discord_id = %s FOR UPDATE', (actor,))
        if not scanner:
            raise GameError('no_network')

        # Lecture de la cible (lecture simple)
        target = tx.one('SELECT * FROM players WHERE discord_id = %s', (target_id,))
        if not target:
            raise GameError('target_not_registered')

        # Règles PvP firewall
        scanner_fw = int(scanner.get('firewall_level') or 0)
        target_fw = int(target.get('firewall_level') or 0)

        if scanner_fw == 0:
            raise GameError('scan_self_invulnerable')
        if target_fw == 0:
            raise GameError('scan_target_invulnerable')

        # Protection écart de niveau (sauf représailles actives)
        if target_fw < scanner_fw:
            if not ConsequenceDB.check(tx, victim_id=actor, attacker_id=target_id):
                raise GameError('scan_target_protected')

        # Stock ATK requis
        if int(scanner.get('attack_points') or 0) == 0:
            raise GameError('scan_no_atk')

        # Scan déjà actif
        active_scan = HackDB.get_active(tx, actor, type='scan')
        if active_scan:
            exp = active_scan.get('expires_at')
            ts = 0
            if exp is not None and hasattr(exp, 'timestamp'):
                aware = exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp
                ts = int(aware.timestamp())
            raise GameError('scan_in_progress', timestamp=ts)

        # Calcul probabilités estimées pour le devis
        atk = int(scanner.get('attack_points') or 0)
        target_stats = MathConfig.calculate_player_stats(target)
        total_defense = max(1, target_stats['total_defense'])

        def _estimate_prob(multiplier: int) -> float:
            boost_rtm = rtm_cost * (Decimal(str(multiplier)) - 1)
            base = min(1.0, max(min_prob, atk / total_defense))
            if boost_per_point > 0 and boost_rtm > 0:
                bonus = float(boost_rtm / boost_per_point) * 0.01 * (1.0 - base)
                return min(1.0, base + bonus)
            return base

        boost_multiplier = int(args.get('boost_multiplier') or 1)
        if boost_multiplier not in boost_levels:
            boost_multiplier = 1

        total_rtm = rtm_cost * Decimal(str(boost_multiplier))
        boost_rtm_paid = rtm_cost * Decimal(str(boost_multiplier - 1))

        # Phase 1 : devis
        if not args.get('confirm'):
            boost_options = []
            for lvl in boost_levels:
                prob_pct = round(_estimate_prob(lvl) * 100, 1)
                cost = rtm_cost * Decimal(str(lvl))
                boost_options.append({
                    'multiplier': lvl,
                    'prob_pct': prob_pct,
                    'rtm_cost': cost,
                })
            return {
                'quote': True,
                'scan_quote': True,
                'target_id': target_id,
                'target_name': str(target.get('discord_id', target_id)),
                'prob_base_pct': round(_estimate_prob(1) * 100, 1),
                'boost_options': boost_options,
                'rtm_base': rtm_cost,
                'current_rtm': Decimal(str(scanner.get('rootium') or 0)),
                'remaining_rtm': Decimal(str(scanner.get('rootium') or 0)) - rtm_cost,
            }

        # Phase 2 : lancement (confirm=True)
        # Re-vérification solde
        scanner_rtm = Decimal(str(scanner.get('rootium') or 0))
        if scanner_rtm < total_rtm:
            raise GameError('insufficient_funds_rtm', rtm=f'{total_rtm:,.5f}')

        # Débit RTM
        UpdatePlayer.set(tx, actor, rootium=scanner_rtm - total_rtm)

        # Création du job
        expires_at = tx.now + timedelta(seconds=duration)
        HackDB.create_scan(
            tx,
            scanner_id=actor,
            target_id=target_id,
            rtm_paid=rtm_cost,
            boost_rtm=boost_rtm_paid,
            expires_at=expires_at,
        )

        ts_exp = int(expires_at.replace(tzinfo=timezone.utc).timestamp()) if getattr(expires_at, 'tzinfo', None) is None else int(expires_at.timestamp())
        return {
            'scan_started': True,
            'target_id': target_id,
            'rtm_total': total_rtm,
            'boost_multiplier': boost_multiplier,
            'timestamp': ts_exp,
        }

    @staticmethod
    def hack(tx, actor: int, **args) -> dict:
        """Lance ou présente un devis pour une attaque PvP (/hack) contre le réseau d'un joueur.

        Phase 1 (confirm=False) : valide l'existence de la cible via son secret_id,
        vérifie les règles de pare-feu et les points d'attaque disponibles, puis retourne un devis.
        Phase 2 (confirm=True) : déduit les points d'attaque engagés et insère l'entrée dans pvp_attacks (45 min).
        """
        code = args.get('secret_id') or args.get('target_secret') or args.get('code')
        if not code:
            raise GameError('invalid_secret_id')

        # Recherche de la victime par secret_id
        target = Player.find_by_secret_id(tx, code)
        target_id = int(target['discord_id'])

        if int(actor) == target_id:
            raise GameError('self_target')

        tx.acquire_lock(player_lock_name(target_id))

        # Lecture de l'attaquant et de la cible (avec verrous)
        attacker = tx.one('SELECT * FROM players WHERE discord_id = %s FOR UPDATE', (actor,))
        target = tx.one('SELECT * FROM players WHERE discord_id = %s FOR UPDATE', (target_id,)) or target
        if not attacker:
            raise GameError('no_network')

        # Règles PvP firewall (identiques au scan)
        attacker_fw = int(attacker.get('firewall_level') or 0)
        target_fw = int(target.get('firewall_level') or 0)

        if attacker_fw == 0:
            raise GameError('hack_self_invulnerable')
        if target_fw == 0:
            raise GameError('hack_target_invulnerable')

        # Protection écart de niveau (sauf représailles actives)
        if target_fw < attacker_fw:
            if not ConsequenceDB.check(tx, victim_id=actor, attacker_id=target_id):
                raise GameError('hack_target_protected')

        # Vérifier si la victime subit déjà une attaque en cours
        if PvpDB.get_active_for_victim(tx, target_id):
            raise GameError('hack_target_in_progress')

        # Normalisation de la zone ciblée
        raw_zone = str(args.get('zone') or args.get('target_zone') or args.get('target') or '').strip().lower()
        if raw_zone in ('mining', 'minage', 'mine', 'm'):
            target_zone = 'mining'
        elif raw_zone in ('attack', 'attaque', 'atk', 'a'):
            target_zone = 'attack'
        else:
            raise GameError('invalid_selection')

        # Validation des points d'attaque
        raw_atk = args.get('attack_points') or args.get('atk')
        try:
            attack_points = int(str(raw_atk).strip())
        except (TypeError, ValueError):
            raise GameError('invalid_selection')

        if attack_points <= 0:
            raise GameError('invalid_selection')

        attacker_atk = int(attacker.get('attack_points') or 0)
        if attack_points > attacker_atk:
            raise GameError('hack_insufficient_atk', available=attacker_atk, requested=attack_points)

        cfg = MathConfig.load().get('pvp', {})
        duration_seconds = int(cfg.get('delay_seconds', 2700))
        expires_at = tx.now + timedelta(seconds=duration_seconds)
        ts_exp = int(expires_at.replace(tzinfo=timezone.utc).timestamp()) if getattr(expires_at, 'tzinfo', None) is None else int(expires_at.timestamp())

        # Phase 1 : devis
        if not args.get('confirm'):
            return {
                'quote': True,
                'hack_quote': True,
                'target_id': target_id,
                'secret_id': str(target.get('secret_id')),
                'attack_points': attack_points,
                'target_zone': target_zone,
                'duration_seconds': duration_seconds,
                'timestamp': ts_exp,
                'current_atk': attacker_atk,
                'remaining_atk': attacker_atk - attack_points,
            }

        # Phase 2 : lancement (confirm=True)
        UpdatePlayer.set(tx, actor, attack_points=attacker_atk - attack_points)
        PvpDB.create(
            tx,
            attacker_id=actor,
            victim_id=target_id,
            attack_points=attack_points,
            target=target_zone,
            resolves_at=expires_at,
        )

        return {
            'hack_started': True,
            'target_id': target_id,
            'secret_id': str(target.get('secret_id')),
            'attack_points': attack_points,
            'target_zone': target_zone,
            'timestamp': ts_exp,
            'remaining_atk': attacker_atk - attack_points,
        }

    @staticmethod
    def convert(tx, actor: int, **args) -> dict:
        """Vend du Rootium contre des dollars au taux fixe RTM → USD.

        Direction unique pour l'instant : le joueur cède du RTM et reçoit des USD.
        Un devis est renvoyé tant que confirm=False ; le débit/crédit n'a lieu qu'à la confirmation.
        """
        p = PlayerData.get(tx, actor)
        rate = MathConfig.rtm_to_usd_rate()
        if rate <= 0:
            raise GameError('invalid_selection')

        quoted_rate = args.get('rate')
        if args.get('confirm') and quoted_rate is not None and Decimal(str(quoted_rate)) != rate:
            raise GameError('quote_changed')

        settings = MathConfig.load()
        rtm_places = int(settings.get('rtm_decimal_places', 5))
        rtm_quantum = Decimal('1').scaleb(-rtm_places)
        balance = Decimal(str(p.get('rootium') or 0))

        raw_amount = args.get('amount')
        sell_all = bool(args.get('all'))
        if not sell_all and isinstance(raw_amount, str):
            token = raw_amount.strip().lower().replace(',', '.')
            if token in ('all', 'tout', 'max'):
                sell_all = True

        if sell_all:
            amount = balance
        else:
            try:
                amount = Decimal(str(raw_amount).replace(',', '.').strip())
            except (InvalidOperation, TypeError, AttributeError, ValueError):
                raise GameError('invalid_amount')

        if amount <= 0:
            raise GameError('invalid_amount')

        quantized = amount.quantize(rtm_quantum)
        if quantized != amount:
            raise GameError('invalid_amount')
        amount = quantized
        if amount <= 0:
            raise GameError('invalid_amount')
        if amount > balance:
            raise GameError('insufficient_funds_rtm', rtm=f"{amount:,.{rtm_places}f}")

        usd = MathConfig.convert_rtm_to_usd(amount)
        if usd <= 0:
            raise GameError('invalid_amount')

        new_rtm = balance - amount
        new_usd = Decimal(str(p.get('dollars') or 0)) + usd
        payload = {
            'rtm_amount': amount,
            'usd_amount': usd,
            'rate': rate,
            'current_rootium': balance,
            'current_dollars': Decimal(str(p.get('dollars') or 0)),
            'new_rootium': new_rtm,
            'new_dollars': new_usd,
            'sold_all': sell_all,
        }
        if not args.get('confirm'):
            payload['quote'] = True
            payload['convert_quote'] = True
            return payload

        UpdatePlayer.set(tx, actor, dollars=new_usd, rootium=new_rtm)
        payload['converted'] = True
        return payload

    @staticmethod
    def upgrade(tx, actor: int, **args) -> dict:
        """
        Amélioration du pare-feu (firewall_level de 0 à 5).
        
        Vérifications :
        - Vérifie si une amélioration est déjà en cours (bloque les chantiers simultanés).
        - Plafond absolu au niveau 5.
        - Devis initial si confirm=False avec durée estimée.
        - Si confirm=True : prélèvement des USD et enregistrement dans la table upgrades.
        """
        active = UpgradesDB.get_active(tx, actor)
        if active:
            remaining = format_remaining_time(active['expires_at'], tx.now)
            ts = int(active['expires_at'].replace(tzinfo=timezone.utc).timestamp())
            raise GameError('upgrade_in_progress', level=active['target_level'], remaining=remaining, timestamp=ts)

        p = PlayerData.get(tx, actor)
        current_level = int(p.get('firewall_level', 0))
        if current_level >= 5:
            raise GameError('maximum_level')

        target_level = int(args.get('level', current_level + 1))
        if target_level <= current_level:
            target_level = current_level + 1
        if target_level > 5:
            raise GameError('maximum_level')

        usd_price, _ = _calculate_module_price('firewall', target_level)

        if Decimal(p['dollars']) < usd_price:
            raise GameError('upgrade_insufficient_funds', usd=format_usd(usd_price), level=target_level)

        settings = MathConfig.load()
        duration_seconds = int(settings.get('firewall', {}).get('upgrade_duration_seconds', 18000))
        duration_str = format_duration(duration_seconds)

        current_def = MathConfig.get_firewall_network_defense(current_level)
        next_def = MathConfig.get_firewall_network_defense(target_level)
        def_gain = next_def - current_def

        if not args.get('confirm'):
            return {
                'quote': True,
                'upgrade_quote': True,
                'current_level': current_level,
                'next_level': target_level,
                'usd_price': usd_price,
                'current_usd': Decimal(str(p['dollars'])),
                'remaining_usd': Decimal(str(p['dollars'])) - usd_price,
                'duration': duration_str,
                'duration_seconds': duration_seconds,
                'defense_current': current_def,
                'defense_next': next_def,
                'defense_gain': def_gain,
            }

        expires_at = tx.now + timedelta(seconds=duration_seconds)
        UpdatePlayer.set(tx, actor, dollars=Decimal(p['dollars']) - usd_price)
        UpgradesDB.create(tx, actor, target_level, expires_at)
        return {
            'upgrade_started': True,
            'level': target_level,
            'usd_price': usd_price,
            'expires_at': expires_at,
            'timestamp': int(expires_at.replace(tzinfo=timezone.utc).timestamp()),
            'duration': duration_str,
            'defense_current': current_def,
            'defense_next': next_def,
            'defense_gain': def_gain,
        }

    @staticmethod
    def give_reputation(tx, actor: int, target: int, bypass_cooldown: bool = False) -> dict:
        """
        Donne un point de réputation à un autre joueur inscrit.
        
        Contraintes :
        - Auto-ciblage interdit.
        - Cooldown de 24 heures (next_reputation_at), sauf si bypass_cooldown=True (OP bot).
        - La cible doit impérativement avoir un profil de jeu actif.
        """
        target = int(target)
        if target == actor:
            raise GameError('self_target')

        recipient = tx.one('SELECT * FROM players WHERE discord_id=%s', (target,))
        if not recipient:
            raise GameError('target_not_registered')

        giver = PlayerData.get(tx, actor)

        if not bypass_cooldown and giver.get('next_reputation_at') and giver['next_reputation_at'] > tx.now:
            remaining = format_remaining_time(giver['next_reputation_at'], tx.now)
            raise GameError('cooldown', time=remaining, remaining=remaining, until=remaining)

        UpdatePlayer.set(tx, target, reputation=int(recipient['reputation']) + 1)
        if not bypass_cooldown:
            UpdatePlayer.set(tx, actor, next_reputation_at=tx.now + timedelta(hours=24))
        return {'reputation_given': True, 'giver': actor, 'recipient': target, 'points': 1, 'bypassed_cooldown': bypass_cooldown}

    @staticmethod
    def top(tx, category: str = 'reputation') -> dict:
        """Retourne le Top 10 des joueurs classés par réputation, USD, RTM ou victoires d'événements."""
        raw_cat = (category or 'reputation').lower().strip()
        if raw_cat == 'rep':
            normalized = 'reputation'
        elif raw_cat in ('event', 'events', 'e'):
            normalized = 'events'
        else:
            normalized = raw_cat

        column = {'reputation': 'reputation', 'usd': 'dollars', 'rtm': 'rootium', 'events': 'events_won'}.get(normalized, 'reputation')
        canonical = 'reputation' if column == 'reputation' else normalized
        rows = tx.all(f'SELECT discord_id, {column} AS score FROM players ORDER BY {column} DESC LIMIT 10')
        return {'ranking': rows, 'category': canonical}

    @staticmethod
    def set_language(tx, actor: int, lang: str | None) -> dict:
        """Met à jour la préférence de langue du joueur (colonne lang de players)."""
        PlayerData.get(tx, actor)
        UpdatePlayer.set(tx, actor, lang=lang if lang else None)
        return {'language_set': True, 'lang': lang}

    @staticmethod
    def get_language(tx, actor: int) -> str | None:
        """Retourne la préférence linguistique persistée du joueur, ou None si auto-détection."""
        row = tx.one('SELECT lang FROM players WHERE discord_id = %s', (actor,))
        return row['lang'] if row else None

    @staticmethod
    def trade(
        tx,
        initiator: int,
        target: int,
        send_usd: Decimal | float = 0,
        send_rtm: Decimal | float = 0,
        receive_usd: Decimal | float = 0,
        receive_rtm: Decimal | float = 0,
    ) -> dict:
        """
        Exécute un échange atomique de ressources entre deux joueurs.

        Règles métier :
        - Impossible d'échanger avec soi-même.
        - Les deux comptes doivent exister en base.
        - Verrouillage SELECT ... FOR UPDATE ordonné par identifiant croissant (anti-deadlock).
        - Les montants doivent être >= 0 et au moins une ressource doit être transférée.
        - Vérification stricte des soldes au moment de la transaction.
        - Débit/crédit atomique sous transaction SQL.
        """
        initiator = int(initiator)
        target = int(target)
        if initiator == target:
            raise GameError('self_target')

        s_usd = Decimal(str(send_usd or 0))
        s_rtm = Decimal(str(send_rtm or 0))
        r_usd = Decimal(str(receive_usd or 0))
        r_rtm = Decimal(str(receive_rtm or 0))

        if s_usd < 0 or s_rtm < 0 or r_usd < 0 or r_rtm < 0:
            raise GameError('invalid_amount')

        if s_usd == 0 and s_rtm == 0 and r_usd == 0 and r_rtm == 0:
            raise GameError('invalid_amount')

        # Verrouillage ordonné par ID croissant pour prévenir tout interblocage (deadlock)
        first_id, second_id = (initiator, target) if initiator < target else (target, initiator)
        first_p = tx.one('SELECT * FROM players WHERE discord_id=%s FOR UPDATE', (first_id,))
        second_p = tx.one('SELECT * FROM players WHERE discord_id=%s FOR UPDATE', (second_id,))

        init_p = first_p if first_id == initiator else second_p
        target_p = second_p if first_id == initiator else first_p

        if not init_p or not target_p:
            raise GameError('target_not_registered')

        # Vérification des soldes de l'initiateur
        init_dollars = Decimal(str(init_p.get('dollars', 0)))
        init_rootium = Decimal(str(init_p.get('rootium', 0)))
        if s_usd > 0 and init_dollars < s_usd:
            raise GameError('insufficient_funds')
        if s_rtm > 0 and init_rootium < s_rtm:
            raise GameError('insufficient_funds')

        # Vérification des soldes de la cible
        target_dollars = Decimal(str(target_p.get('dollars', 0)))
        target_rootium = Decimal(str(target_p.get('rootium', 0)))
        if r_usd > 0 and target_dollars < r_usd:
            raise GameError('insufficient_funds')
        if r_rtm > 0 and target_rootium < r_rtm:
            raise GameError('insufficient_funds')

        # Calcul des nouveaux soldes
        new_init_dollars = init_dollars - s_usd + r_usd
        new_init_rootium = init_rootium - s_rtm + r_rtm

        new_target_dollars = target_dollars + s_usd - r_usd
        new_target_rootium = target_rootium + s_rtm - r_rtm

        UpdatePlayer.set(tx, initiator, dollars=new_init_dollars, rootium=new_init_rootium)
        UpdatePlayer.set(tx, target, dollars=new_target_dollars, rootium=new_target_rootium)

        return {
            'trade_completed': True,
            'initiator': initiator,
            'target': target,
            'send_usd': s_usd,
            'send_rtm': s_rtm,
            'receive_usd': r_usd,
            'receive_rtm': r_rtm,
            'initiator_lang': init_p.get('lang'),
            'target_lang': target_p.get('lang'),
        }

    @staticmethod
    def hourly(tx, actor: int) -> dict:
        """Réclame la récompense horaire (30 à 90 USD) avec bonus de combo incitatif.

        Règles :
        - Cooldown de 60 minutes : lève GameError('hourly_cooldown') si appelé trop tôt.
        - Fenêtre de combo de 20 minutes (entre 60m et 80m après le précédent claim) :
          Bonus étape = (20 - (temps_en_minutes - 60))%.
          Ce bonus s'ajoute au bonus cumulé existant (sans limite de plafond).
          Série incrémentée de 1.
        - Si > 80 minutes : combo brisé, bonus réinitialisé à 0%, série revient à 1, gain de base seul.
        - Si première exécution : gain de base, bonus 0%, série 1.
        - Enregistre l'événement dans hourly_logs pour audit et surveillance.
        """
        p = PlayerData.get(tx, actor)

        config = MathConfig.load().get('hourly', {})
        reward_min = int(config.get('reward_min_usd', 30))
        reward_max = int(config.get('reward_max_usd', 90))
        cooldown_sec = int(config.get('cooldown_minutes', 60)) * 60
        combo_window_sec = int(config.get('combo_window_minutes', 20)) * 60
        max_combo_sec = cooldown_sec + combo_window_sec  # 80 min = 4800 s

        last_hourly = p.get('hourly_last_at')
        current_combo_bonus = Decimal(str(p.get('hourly_combo_bonus', 0) or 0))
        current_streak = int(p.get('hourly_streak', 0) or 0)

        interval_seconds = None
        step_bonus = Decimal('0.00')
        combo_lost = False
        is_first = (last_hourly is None)

        if not is_first:
            ref, now_ref = last_hourly, tx.now
            if getattr(ref, 'tzinfo', None) is not None and getattr(now_ref, 'tzinfo', None) is None:
                now_ref = now_ref.replace(tzinfo=timezone.utc)
            elif getattr(ref, 'tzinfo', None) is None and getattr(now_ref, 'tzinfo', None) is not None:
                ref = ref.replace(tzinfo=now_ref.tzinfo)
            elapsed = (now_ref - ref).total_seconds()
            interval_seconds = max(0, int(elapsed))

            # 1. Vérification du cooldown (60 minutes)
            if interval_seconds < cooldown_sec:
                remaining_sec = cooldown_sec - interval_seconds
                remaining_str = format_duration(remaining_sec)
                raise GameError('hourly_cooldown', remaining=remaining_str, time=remaining_str, remaining_seconds=remaining_sec)

            # 2. Vérification de la fenêtre de combo (60m à 80m)
            if interval_seconds <= max_combo_sec:
                # t = minutes entières écoulées. À 60 min : +20 %, à 80 min : +0 %.
                t_min = interval_seconds // 60
                step_pct = max(0, 20 - (t_min - 60))
                step_bonus = Decimal(step_pct).quantize(Decimal('0.01'))
                new_combo_bonus = (current_combo_bonus + step_bonus).quantize(Decimal('0.01'))
                new_streak = current_streak + 1
            else:
                combo_lost = True
                step_bonus = Decimal('0.00')
                new_combo_bonus = Decimal('0.00')
                new_streak = 1
        else:
            new_combo_bonus = Decimal('0.00')
            new_streak = 1

        # Tirage aléatoire uniforme du gain de base
        base_gain = Decimal(str(random.randint(reward_min, reward_max)))

        # Calcul du gain total avec le bonus cumulé (sans plafond)
        multiplier = Decimal('1') + (new_combo_bonus / Decimal('100'))
        total_gain = (base_gain * multiplier).quantize(Decimal('0.01'))
        bonus_usd = total_gain - base_gain

        # Mise à jour du compte joueur
        new_dollars = Decimal(str(p['dollars'])) + total_gain
        UpdatePlayer.set(
            tx, actor,
            dollars=new_dollars,
            hourly_last_at=tx.now,
            hourly_combo_bonus=new_combo_bonus,
            hourly_streak=new_streak,
        )

        # Enregistrement dans hourly_logs
        HourlyStatsDB.record_hourly(
            tx,
            discord_id=actor,
            claimed_at=tx.now,
            interval_seconds=interval_seconds,
            base_usd=base_gain,
            bonus_pct=new_combo_bonus,
            total_usd=total_gain,
            streak=new_streak,
            combo_lost=combo_lost,
        )

        next_avail_dt = tx.now + timedelta(seconds=cooldown_sec)
        combo_dead_dt = tx.now + timedelta(seconds=max_combo_sec)
        next_ts = int(next_avail_dt.replace(tzinfo=timezone.utc).timestamp()) if getattr(next_avail_dt, 'tzinfo', None) is None else int(next_avail_dt.timestamp())
        combo_ts = int(combo_dead_dt.replace(tzinfo=timezone.utc).timestamp()) if getattr(combo_dead_dt, 'tzinfo', None) is None else int(combo_dead_dt.timestamp())

        return {
            'claimed': True,
            'base_usd': base_gain,
            'bonus_pct': new_combo_bonus,
            'step_bonus_pct': step_bonus,
            'bonus_usd': bonus_usd,
            'total_usd': total_gain,
            'new_dollars': new_dollars,
            'streak': new_streak,
            'combo_lost': combo_lost,
            'is_first': is_first,
            'interval_seconds': interval_seconds,
            'next_available_ts': next_ts,
            'combo_deadline_ts': combo_ts,
        }
