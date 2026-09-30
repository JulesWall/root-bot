"""
Façade de service du jeu Root pour les commandes Discord, sans SQL direct.

Pattern Architectural : Façade & Dispatcher
- Isole complètement la couche Discord (Cogs) des détails d'accès à la base de données.
- Toute action de jeu passe impérativement par RootService.execute().
- Exécute chaque action au sein d'une transaction MySQL unifiée, sérialisée
  par un verrou applicatif **par joueur** (GET_LOCK player:<id>).
  Les actions à deux comptes (trade, réputation) prennent les deux verrous
  dans l'ordre croissant des identifiants pour éviter les deadlocks.
- Vérifie l'existence préalable du joueur pour toutes les commandes autres que l'initialisation 'network'.
"""

from game.db.database import Database, player_lock_name
from game.db.economy_stats import EconomyStatsDB
from game.db.hack import HackDB
from game.db.players import Player, PlayerData
from game.db.pvp import PvpDB
from game.db.secret_ids import rotate_all_if_due
from game.db.upgrades import UpgradesDB
from game.game_error import GameError
from game.hash_manager import HashManager
from game.pin_manager import PinManager
from game.decode_manager import DecodeManager
from game.anomaly_manager import AnomalyManager
from game.buffer_manager import BufferManager
from game.signal_manager import SignalManager
from game.packet_manager import PacketManager
from game.events_manager import EventsManager
from game.math_config import MathConfig


EVENT_REMINDER_ADVANCE_SECONDS = 30


class RootService:
    """Façade centrale orchestrant toutes les opérations de jeu côté serveur."""

    ACTIONS = {
        'network', 'buy', 'upgrade', 'reputation', 'top', 'set_language',
        'hash', 'pin', 'event', 'decode', 'anomaly', 'buffer', 'signal',
        'packet', 'trade', 'claim', 'claim_auto', 'claim_cancel', 'convert', 'compile', 'scan', 'hack',
        'hourly', 'hourly_save_combo', 'contract', 'rmd',
        'pvp_v2_dev_quote', 'pvp_v2_start_job', 'pvp_v2_cancel_job', 'pvp_v2_install_patch', 'pvp_v2_library',
        'pvp_v2_scan_quote', 'pvp_v2_scan_start', 'pvp_v2_scan_view',
    }

    def __init__(self, database=None):
        import os
        self.database = database or Database()
        # Activation du suivi économique (lire explicitement, bool("false") vaut True)
        raw = os.getenv('ECONOMY_REPORTS_ENABLED', 'false').strip().lower()
        self.economy_enabled: bool = raw == 'true'
        self.economy_tracking_start = None

    async def init_economy(self) -> None:
        """
        Initialise les tables de suivi économique et mémorise tracking_start.
        À appeler une fois au démarrage si ECONOMY_REPORTS_ENABLED=true.
        Lève RuntimeError si les tables sont absentes (migration non appliquée).
        """
        if not self.economy_enabled:
            return
        tracking_start = await self.database.run(
            EconomyStatsDB.initialize,
            locks=['economy-init'],
        )
        self.economy_tracking_start = tracking_start
        import logging
        logging.getLogger(__name__).info(
            "[EconomyStats] Suivi actif. tracking_start=%s", tracking_start
        )


    async def deliver_expired_upgrades(self) -> list[dict]:
        """
        Scanne et livre les améliorations arrivées à échéance,
        met à jour le niveau de pare-feu et supprime les lignes de la table SQL.
        """
        return await self.database.run(
            UpgradesDB.complete_and_delete_expired,
            locks=['upgrades'],
        )

    async def rotate_secret_ids_if_due(self) -> dict:
        """Régénère tous les identifiants secrets si la frontière UTC de 12 h est échue."""
        return await self.database.run(
            rotate_all_if_due,
            locks=['secret_rotation'],
        )

    async def deliver_expired_hacks(self) -> list[dict]:
        """Livre les productions d'ATK arrivées à échéance et supprime les lignes `hack`."""
        return await self.database.run(
            HackDB.complete_and_delete_expired,
            locks=['hack'],
        )

    async def deliver_expired_scans(self) -> list[dict]:
        """Récupère et résout les jobs de scan arrivés à échéance pour livraison V2."""
        from game.pvp_v2_scan import PvpV2ScanService
        return await self.database.run(
            PvpV2ScanService.deliver_expired_scans,
            locks=['hack'],
        )

    async def purge_expired_consequences(self) -> int:
        """Supprime les droits de représailles expirés."""
        from game.db.consequence import ConsequenceDB
        return await self.database.run(
            ConsequenceDB.purge_expired,
            locks=['consequence'],
        )

    async def deliver_expired_pvp_attacks(self) -> list[dict]:
        """Résout les attaques PvP arrivées à échéance et supprime les lignes `pvp_attacks`."""
        return await self.database.run(
            PvpDB.complete_and_delete_expired,
            locks=['pvp'],
        )

    async def deliver_expired_pvp_v2_jobs(self) -> list[dict]:
        """Résout les jobs de développement PvP V2 arrivés à échéance et supprime les lignes `pvp_v2_dev_jobs`."""
        from game.pvp_v2_dev import PvpV2DevService
        from game.db.pvp_v2_dev_jobs import PvpV2DevJobsDB

        def _deliver_tx(tx):
            expired = PvpV2DevJobsDB.get_expired(tx)
            results = []
            for job in expired:
                delivered = PvpV2DevService.deliver_job(tx, job)
                results.append(delivered)
            return results

        return await self.database.run(
            _deliver_tx,
            locks=['pvp_v2_dev'],
        )

    async def process_due_autoclaims(self) -> list[dict]:
        """Scanne les joueurs ayant des claims automatiques programmés et exécute ceux dont la RAM est >= 99.9%."""
        return await self.database.run(
            self._process_due_autoclaims_tx,
            locks=['autoclaim'],
        )

    @staticmethod
    def _process_due_autoclaims_tx(tx) -> list[dict]:
        from decimal import Decimal
        from game.math_config import MathConfig

        candidates = Player.get_active_autoclaim_players(tx)
        results = []
        now = tx.now
        for p in candidates:
            actor = p['discord_id']
            stats = MathConfig.calculate_player_stats(p)
            state = MathConfig.compute_mining_progress(p, stats, now)
            capacity = state.get('capacity_rtm', Decimal('0'))
            buffer_rtm = state.get('buffer', Decimal('0'))
            # Seuil : 99.9% de la capacité totale de RAM ou mémoire pleine
            if capacity > 0 and (buffer_rtm >= capacity * Decimal('0.999') or state.get('is_full')):
                res = Player.process_autoclaim_tick(tx, actor)
                if res.get('claimed'):
                    results.append(res)
        return results

    async def grant_autoclaim_credits(self, actor: int, amount: int) -> dict:
        """Crédite des autoclaims au joueur, sous le verrou de son compte."""
        return await self.database.run(
            lambda tx: Player.add_autoclaim_credits(tx, actor, amount),
            locks=[player_lock_name(int(actor))],
        )

    async def grant_combo_saver_credits(self, actor: int, amount: int) -> dict:
        """Crédite des Combo Saver au joueur, sous le verrou de son compte."""
        return await self.database.run(
            lambda tx: Player.add_combo_saver_credits(tx, actor, amount),
            locks=[player_lock_name(int(actor))],
        )

    async def deliver_due_reminders(self) -> list[dict]:
        """Récupère et supprime de la base les rappels arrivés à échéance pour notification."""
        from game.db.reminders import RemindersDB
        return await self.database.run(
            RemindersDB.deliver_expired_reminders,
            locks=['reminders'],
        )

    async def deliver_due_contract_notifications(self) -> list[dict]:
        """Récupère et marque comme notifiés les contrats terminés pour notification MP."""
        from game.db.contracts import ContractsDB
        return await self.database.run(
            ContractsDB.get_unnotified_expired,
            locks=['contracts'],
        )

    async def execute(self, actor: int, guild: int | None, method: str, **args):
        """
        Point d'entrée asynchrone universel pour l'exécution d'une action de jeu.
        
        Args:
            actor (int): Identifiant Discord de l'auteur de l'action.
            guild (int | None): Identifiant du serveur Discord d'origine.
            method (str): Nom de l'action demandée (doit figurer dans ACTIONS).
            **args: Paramètres spécifiques à l'action.
        """
        if method not in self.ACTIONS:
            raise GameError('invalid_selection')
        # 'top' et 'event' (ainsi que 'rmd list') sont des lectures pures : exécution concurrente sans verrou applicatif
        readonly = (method in ('top', 'event') or (method == 'rmd' and args.get('action') == 'list'))
        manager = self._get_challenge_manager(method)
        resource = None
        if manager:
            from game.challenge_utils import ChallengeResource
            resource = ChallengeResource(manager)

        # Construit la closure avec les valeurs actuelles de economy_enabled et tracking_start
        economy_enabled = self.economy_enabled
        economy_tracking_start = self.economy_tracking_start

        def dispatch_and_track(tx):
            result = self._dispatch(tx, actor, method, args, resource=resource)
            if (
                economy_enabled
                and not readonly
                and economy_tracking_start is not None
                and tx.now >= economy_tracking_start
            ):
                try:
                    increments = EconomyStatsDB.build_increments(method, actor, result)
                    if increments:
                        bucket = tx.now.replace(minute=0, second=0, microsecond=0)
                        EconomyStatsDB.add(tx, bucket, increments)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "[EconomyStats] Erreur lors de l'enregistrement des compteurs "
                        "(method=%s, actor=%s). La transaction sera annulée.", method, actor
                    )
                    raise
            return result

        return await self.database.run(
            dispatch_and_track,
            resource=resource,
            readonly=readonly,
            locks=self._locks_for(method, actor, args),
        )


    @staticmethod
    def _locks_for(method: str, actor: int, args: dict) -> list[str]:
        """Calcule les verrous applicatifs requis par l'action.

        Une action mono-joueur (network, buy, claim, mini-jeux…) verrouille
        uniquement le compte de l'acteur. Trade et réputation verrouillent
        les deux comptes, triés, pour rester sans deadlock.
        """
        if method in ('top', 'event'):
            return []
        ids = {int(actor)}
        if method in ('reputation', 'trade', 'scan', 'pvp_v2_scan_quote', 'pvp_v2_scan_start', 'pvp_v2_scan_view'):
            try:
                target = int(args.get('target') or 0)
            except (TypeError, ValueError):
                target = 0
            if target:
                ids.add(target)
        elif method == 'hack':
            try:
                target_id = int(args.get('target_id') or 0)
            except (TypeError, ValueError):
                target_id = 0
            if target_id:
                ids.add(target_id)
        return [player_lock_name(uid) for uid in sorted(ids)]

    # Table de dispatch : méthode → gestionnaire de défi en mémoire vive.
    # Les managers sont déjà importés au niveau module ; pas besoin de les réimporter ici.
    _CHALLENGE_MANAGERS = {
        'hash':    HashManager,
        'pin':     PinManager,
        'decode':  DecodeManager,
        'anomaly': AnomalyManager,
        'buffer':  BufferManager,
        'signal':  SignalManager,
        'packet':  PacketManager,
    }

    @staticmethod
    def _get_challenge_manager(method: str):
        """Retourne la classe du gestionnaire de défi en mémoire pour la méthode demandée."""
        return RootService._CHALLENGE_MANAGERS.get(method)

    def _dispatch(self, tx, actor: int, method: str, args: dict, resource=None):
        """
        Aiguillage interne des actions au sein de la transaction SQL active.
        """
        # Seule l'action 'network' permet à un nouvel utilisateur de s'inscrire
        if method == 'network':
            return Player.network(tx, actor)

        # Vérification d'existence préalable du joueur en base pour toute autre action
        PlayerData.get(tx, actor)

        # 1. Opérations Joueur & Économie
        if method == 'buy':
            return Player.buy(tx, actor, **args)
        elif method == 'upgrade':
            return Player.upgrade(tx, actor, **args)
        elif method == 'claim':
            return Player.claim(tx, actor)
        elif method == 'hourly':
            return Player.hourly(tx, actor)
        elif method == 'hourly_save_combo':
            return Player.save_hourly_combo(tx, actor)
        elif method == 'contract':
            return Player.contract(tx, actor, **args)
        elif method == 'claim_auto':
            return Player.start_autoclaim(tx, actor, count=args.get('count', 'all'))
        elif method == 'claim_cancel':
            return Player.cancel_autoclaim(tx, actor)
        elif method == 'convert':
            return Player.convert(tx, actor, **args)
        elif method == 'compile':
            return Player.compile(tx, actor, **args)
        elif method == 'scan':
            from game.pvp_v2_scan import PvpV2ScanService
            target_id = int(args.get('target', 0))
            if args.get('confirm'):
                return PvpV2ScanService.start_scan(tx, actor, target_id, quoted_rtm=args.get('quoted_rtm'))
            return PvpV2ScanService.calculate_scan_quote(tx, actor, target_id)
        elif method == 'pvp_v2_scan_quote':
            from game.pvp_v2_scan import PvpV2ScanService
            return PvpV2ScanService.calculate_scan_quote(tx, actor, int(args.get('target', 0)))
        elif method == 'pvp_v2_scan_start':
            from game.pvp_v2_scan import PvpV2ScanService
            return PvpV2ScanService.start_scan(tx, actor, int(args.get('target', 0)), quoted_rtm=args.get('quoted_rtm'))
        elif method == 'pvp_v2_scan_view':
            from game.pvp_v2_scan import PvpV2ScanService
            return PvpV2ScanService.get_latest_scan_report(tx, actor, int(args.get('target', 0)))
        elif method == 'hack':
            return Player.hack(tx, actor, **args)
        elif method == 'reputation':
            return Player.give_reputation(
                tx,
                actor,
                args.get('target', 0),
                bypass_cooldown=bool(args.get('bypass_cooldown', False)),
            )
        elif method == 'trade':
            return Player.trade(
                tx,
                actor,
                args.get('target', 0),
                send_usd=args.get('send_usd', 0),
                send_rtm=args.get('send_rtm', 0),
                receive_usd=args.get('receive_usd', 0),
                receive_rtm=args.get('receive_rtm', 0),
            )
        elif method == 'top':
            return Player.top(tx, args.get('category', 'reputation'))

        # 2. Préférences de langue du joueur
        elif method == 'set_language':
            return Player.set_language(tx, actor, lang=args.get('lang'))

        # 3. Mini-jeux Réseau (avec gestionnaire de ressource 2-phase)
        elif method == 'event':
            status = EventsManager.get_all_events_status(tx)
            player = PlayerData.get(tx, actor)
            fw_lvl = int(player.get('firewall_level', 0) or 0)
            status['firewall_level'] = fw_lvl
            status['firewall_multiplier'] = MathConfig.get_event_firewall_multiplier(fw_lvl)
            return status
        elif manager := self._CHALLENGE_MANAGERS.get(method):
            return manager.process(tx, actor, args.get('guild_name'), args.get('guess'), resource=resource)

        # 4. Rappels et Alertes Temporelles (/rmd)
        elif method == 'rmd':
            return self._dispatch_rmd(tx, actor, args)

        # 5. PvP V2 — Développement et correctifs
        elif method == 'pvp_v2_dev_quote':
            from game.pvp_v2_dev import PvpV2DevService
            return PvpV2DevService.get_quote(
                tx,
                actor,
                job_type=args.get('job_type'),
                family=args.get('family'),
                tier=int(args.get('tier', 1)),
                fingerprint=args.get('fingerprint'),
            )
        elif method == 'pvp_v2_start_job':
            from game.pvp_v2_dev import PvpV2DevService
            return PvpV2DevService.start_job(
                tx,
                actor,
                job_type=args.get('job_type'),
                family=args.get('family'),
                tier=int(args.get('tier', 1)),
                fingerprint=args.get('fingerprint'),
                quoted_rtm=args.get('quoted_rtm'),
            )
        elif method == 'pvp_v2_cancel_job':
            from game.pvp_v2_dev import PvpV2DevService
            return PvpV2DevService.cancel_job(
                tx,
                actor,
                channel=args.get('channel'),
            )
        elif method == 'pvp_v2_install_patch':
            from game.pvp_v2_dev import PvpV2DevService
            return PvpV2DevService.install_patch(
                tx,
                actor,
                patch_id=args.get('patch_id'),
                fingerprint=args.get('fingerprint'),
            )
        elif method == 'pvp_v2_library':
            from game.pvp_v2_dev import PvpV2DevService
            return PvpV2DevService.get_library(tx, actor)

        # Ne devrait jamais être atteint si ACTIONS et _dispatch sont synchronisés
        raise GameError('invalid_selection')

    def _dispatch_rmd(self, tx, actor: int, args: dict) -> dict:
        """Gère les opérations de création, consultation et annulation de rappels."""
        from datetime import timedelta
        from game.db.reminders import RemindersDB
        from game.events_manager import EventsManager
        from game.math_config import MathConfig

        action = args.get('action', 'list')
        channel_id = args.get('channel_id')
        guild_id = args.get('guild_id')

        if action == 'help':
            return {'status': 'help'}

        if action == 'list':
            reminders = RemindersDB.get_user_reminders(tx, actor)
            return {'status': 'list', 'reminders': reminders}

        if action == 'cancel':
            target = args.get('reminder_id')
            if str(target).lower() == 'all':
                count = RemindersDB.clear_user_reminders(tx, actor)
                return {'status': 'cancelled_all', 'count': count}
            try:
                rid = int(target)
            except (ValueError, TypeError):
                raise GameError('invalid_selection')
            deleted = RemindersDB.delete_reminder(tx, rid, actor)
            if not deleted:
                raise GameError('reminder_not_found')
            return {'status': 'cancelled', 'reminder_id': rid}

        if action == 'create_custom':
            dur_sec = args.get('duration_sec')
            try:
                dur_sec = int(dur_sec)
            except (ValueError, TypeError):
                raise GameError('invalid_duration')
            if dur_sec < 10 or dur_sec > 30 * 86400:
                raise GameError('duration_out_of_range')
            message = str(args.get('message') or 'Rappel')[:200]
            remind_at = tx.now + timedelta(seconds=dur_sec)
            created = RemindersDB.create_reminder(
                tx, actor, remind_at=remind_at, message=message,
                channel_id=channel_id, guild_id=guild_id, reminder_type='custom',
            )
            return {'status': 'created', 'reminder': created, 'remind_at': remind_at, 'duration_seconds': dur_sec}

        if action == 'create_smart':
            target = str(args.get('target', '')).lower()
            p = PlayerData.get(tx, actor)

            if target == 'all':
                existing_reminders = RemindersDB.get_user_reminders(tx, actor)
                existing_map = {r.get('reminder_type'): r for r in existing_reminders}
                results = []

                # 1. Hourly
                if 'hourly' in existing_map:
                    results.append({
                        'target': 'hourly',
                        'status': 'already_scheduled',
                        'remind_at': existing_map['hourly'].get('remind_at'),
                    })
                else:
                    last_hourly = p.get('hourly_last_at')
                    cooldown_sec = 3600
                    elapsed = (tx.now - last_hourly).total_seconds() if last_hourly else 999999
                    if last_hourly is None or elapsed >= cooldown_sec:
                        results.append({'target': 'hourly', 'status': 'already_available'})
                    else:
                        remind_at = last_hourly + timedelta(seconds=cooldown_sec)
                        rem_sec = int(cooldown_sec - elapsed)
                        created = RemindersDB.create_reminder(
                            tx, actor, remind_at=remind_at, message="Prime horaire (/hourly) disponible !",
                            channel_id=channel_id, guild_id=guild_id, reminder_type='hourly',
                        )
                        results.append({
                            'target': 'hourly',
                            'status': 'created',
                            'remind_at': remind_at,
                            'remaining_seconds': rem_sec,
                            'reminder': created,
                        })

                # 2. Claim (RAM)
                if 'claim' in existing_map:
                    stats = MathConfig.calculate_player_stats(p)
                    if stats.get('total_hashrate_hs', 0) > 0:
                        state = MathConfig.compute_mining_progress(p, stats, tx.now)
                        sec_to_full = state.get('seconds_to_full', 0)
                        if not state.get('is_full') and sec_to_full > 0:
                            new_at = tx.now + timedelta(seconds=sec_to_full)
                            RemindersDB.reschedule_claim_reminder(tx, actor, new_at)
                            existing_map['claim']['remind_at'] = new_at
                    results.append({
                        'target': 'claim',
                        'status': 'already_scheduled',
                        'remind_at': existing_map['claim'].get('remind_at'),
                    })
                else:
                    stats = MathConfig.calculate_player_stats(p)
                    if stats.get('total_hashrate_hs', 0) <= 0:
                        results.append({'target': 'claim', 'status': 'no_miner'})
                    else:
                        state = MathConfig.compute_mining_progress(p, stats, tx.now)
                        sec_to_full = state.get('seconds_to_full', 0)
                        if state.get('is_full') or sec_to_full <= 0:
                            results.append({'target': 'claim', 'status': 'already_available'})
                        else:
                            remind_at = tx.now + timedelta(seconds=sec_to_full)
                            created = RemindersDB.create_reminder(
                                tx, actor, remind_at=remind_at, message="Mémoire vive pleine ! Récolte /claim prête.",
                                channel_id=channel_id, guild_id=guild_id, reminder_type='claim',
                            )
                            results.append({
                                'target': 'claim',
                                'status': 'created',
                                'remind_at': remind_at,
                                'remaining_seconds': sec_to_full,
                                'reminder': created,
                            })

                # 3. Events
                existing_event_reminders = {
                    r.get('target_event'): r
                    for r in existing_reminders
                    if r.get('reminder_type') == 'events' and r.get('target_event')
                }
                generic_event_reminder = next(
                    (r for r in existing_reminders if r.get('reminder_type') == 'events' and not r.get('target_event')),
                    None
                )

                events_status = EventsManager.get_all_events_status(tx)
                events_map = events_status.get('events', {})

                from game.hash_manager import HashManager
                hash_info = events_map.get('hash')
                if hash_info and hash_info.get('status') == 'active':
                    p_rem_sec, p_next_at = HashManager.get_player_cooldown(actor, tx.now)
                    if p_rem_sec > 0 and p_next_at:
                        events_map['hash'] = {
                            **hash_info,
                            'status': 'cooldown',
                            'next_at': p_next_at,
                            'remaining_seconds': p_rem_sec,
                            'player_cooldown': True,
                        }

                unavailable_events = [
                    (ev_name, info) for ev_name, info in events_map.items()
                    if info.get('status') != 'active' and info.get('remaining_seconds', 0) > EVENT_REMINDER_ADVANCE_SECONDS
                ]
                unavailable_events.sort(key=lambda item: item[1].get('remaining_seconds', 999999))

                if not unavailable_events:
                    results.append({'target': 'events', 'status': 'already_available'})
                else:
                    for ev_name, info in unavailable_events:
                        existing = existing_event_reminders.get(ev_name) or (generic_event_reminder if not existing_event_reminders else None)
                        if existing:
                            results.append({
                                'target': 'events',
                                'target_event': ev_name,
                                'status': 'already_scheduled',
                                'remind_at': existing.get('remind_at'),
                            })
                        else:
                            remind_at = info.get('next_at') - timedelta(seconds=EVENT_REMINDER_ADVANCE_SECONDS)
                            rem_sec = info.get('remaining_seconds', 0) - EVENT_REMINDER_ADVANCE_SECONDS
                            try:
                                created = RemindersDB.create_reminder(
                                    tx, actor, remind_at=remind_at, message=f"Événement {ev_name} dans 30 secondes !",
                                    channel_id=channel_id, guild_id=guild_id, reminder_type='events', target_event=ev_name,
                                )
                                results.append({
                                    'target': 'events',
                                    'target_event': ev_name,
                                    'status': 'created',
                                    'remind_at': remind_at,
                                    'remaining_seconds': rem_sec,
                                    'reminder': created,
                                })
                            except GameError as ge:
                                if ge.key == 'reminder_limit_reached':
                                    break
                                raise

                return {'status': 'created_all', 'results': results}

            if target == 'hourly':
                last_hourly = p.get('hourly_last_at')
                cooldown_sec = 3600
                if last_hourly is None:
                    return {'status': 'already_available', 'target': 'hourly'}
                elapsed = (tx.now - last_hourly).total_seconds()
                if elapsed >= cooldown_sec:
                    return {'status': 'already_available', 'target': 'hourly'}
                remind_at = last_hourly + timedelta(seconds=cooldown_sec)
                rem_sec = int(cooldown_sec - elapsed)
                created = RemindersDB.create_reminder(
                    tx, actor, remind_at=remind_at, message="Prime horaire (/hourly) disponible !",
                    channel_id=channel_id, guild_id=guild_id, reminder_type='hourly',
                )
                return {'status': 'created', 'reminder': created, 'remind_at': remind_at, 'target': 'hourly', 'remaining_seconds': rem_sec}

            if target in ('events', 'event') or target in EventsManager.SUPPORTED_EVENTS:
                events_status = EventsManager.get_all_events_status(tx)
                events_map = events_status.get('events', {})

                from game.hash_manager import HashManager
                hash_info = events_map.get('hash')
                if hash_info and hash_info.get('status') == 'active':
                    p_rem_sec, p_next_at = HashManager.get_player_cooldown(actor, tx.now)
                    if p_rem_sec > 0 and p_next_at:
                        events_map['hash'] = {
                            **hash_info,
                            'status': 'cooldown',
                            'next_at': p_next_at,
                            'remaining_seconds': p_rem_sec,
                            'player_cooldown': True,
                        }

                if target in EventsManager.SUPPORTED_EVENTS:
                    info = events_map.get(target)
                    if not info or info.get('status') == 'active' or info.get('remaining_seconds', 0) <= EVENT_REMINDER_ADVANCE_SECONDS:
                        return {'status': 'already_available', 'target': target}
                    remind_at = info.get('next_at') - timedelta(seconds=EVENT_REMINDER_ADVANCE_SECONDS)
                    rem_sec = info.get('remaining_seconds', 0) - EVENT_REMINDER_ADVANCE_SECONDS
                    chosen_event = target
                else:
                    active_any = [
                        k for k, v in events_map.items()
                        if v.get('status') == 'active' or v.get('remaining_seconds', 0) <= EVENT_REMINDER_ADVANCE_SECONDS
                    ]
                    if active_any:
                        return {'status': 'already_available', 'target': 'events', 'active_event': active_any[0]}
                    sorted_events = sorted(
                        events_map.items(),
                        key=lambda item: item[1].get('remaining_seconds', 999999),
                    )
                    chosen_event, info = sorted_events[0]
                    if info.get('remaining_seconds', 0) <= EVENT_REMINDER_ADVANCE_SECONDS:
                        return {'status': 'already_available', 'target': 'events', 'active_event': chosen_event}
                    remind_at = info.get('next_at') - timedelta(seconds=EVENT_REMINDER_ADVANCE_SECONDS)
                    rem_sec = info.get('remaining_seconds', 0) - EVENT_REMINDER_ADVANCE_SECONDS

                created = RemindersDB.create_reminder(
                    tx, actor, remind_at=remind_at, message=f"Événement {chosen_event} dans 30 secondes !",
                    channel_id=channel_id, guild_id=guild_id, reminder_type='events', target_event=chosen_event,
                )
                return {'status': 'created', 'reminder': created, 'remind_at': remind_at, 'target': 'events', 'target_event': chosen_event, 'remaining_seconds': rem_sec}

            if target == 'claim':
                stats = MathConfig.calculate_player_stats(p)
                if stats.get('total_hashrate_hs', 0) <= 0:
                    raise GameError('no_miner')
                state = MathConfig.compute_mining_progress(p, stats, tx.now)
                sec_to_full = state.get('seconds_to_full', 0)
                if state.get('is_full') or sec_to_full <= 0:
                    return {'status': 'already_available', 'target': 'claim'}
                remind_at = tx.now + timedelta(seconds=sec_to_full)
                existing_reminders = RemindersDB.get_user_reminders(tx, actor)
                existing_claim = next((r for r in existing_reminders if r.get('reminder_type') == 'claim'), None)
                if existing_claim:
                    RemindersDB.reschedule_claim_reminder(tx, actor, remind_at)
                    created = dict(existing_claim)
                    created['remind_at'] = remind_at
                else:
                    created = RemindersDB.create_reminder(
                        tx, actor, remind_at=remind_at, message="Mémoire vive pleine ! Récolte /claim prête.",
                        channel_id=channel_id, guild_id=guild_id, reminder_type='claim',
                    )
                return {'status': 'created', 'reminder': created, 'remind_at': remind_at, 'target': 'claim', 'remaining_seconds': sec_to_full}

            raise GameError('invalid_selection')

        raise GameError('invalid_selection')

