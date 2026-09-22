"""Compare les bonus RAM temporaires et une borne maximale permanente, hors bot."""

import argparse
import heapq
import json
import statistics
from decimal import Decimal as D, ROUND_DOWN
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.simulate_balance import (
    DAY, START, MathConfig, PROFILES, STRESS_PROFILE, Profile,
    SAVE_FROM_DAY, STRATEGIES, Simulation, write_csv,
)


class RewardSimulation(Simulation):
    def __init__(self, *args, variant='none', precision='engine', child_unlocks=(), **kwargs):
        self.variant = variant
        self.precision = precision
        self.spec = MathConfig.load()['ram_rewards']
        self.vote_until = self.received_until = 0
        self.sponsored = {}
        self.qualified_once = set()
        self.received_once = False
        self.reward_events = {}
        self.reward_event_index = 0
        self.expiry_loss_rtm = D(0)
        self.wallet_remainder_rtm = D(0)
        requested = D(variant.split('_')[1]) if variant.startswith('maximum_') else D(0)
        self.bonus_percent = min(requested, D(self.spec['max_total_ram_bonus_percent']))
        super().__init__(*args, **kwargs)
        if variant in ('vote', 'combined'):
            # Hypothèse déclarée : un vote par jour à la première visite.
            for day in range(self.days):
                self.schedule(day * DAY + self.profile.visit_minutes[0] * 60, 'vote')
        if variant in ('referral', 'combined'):
            for index, second in enumerate(child_unlocks):
                self.schedule(second, 'qualify', index)

    def schedule(self, second, action, identity=None):
        key = f'reward_{self.reward_event_index}'
        self.reward_event_index += 1
        self.reward_events[key] = (action, identity)
        heapq.heappush(self.queue, (int(second), 0, key))

    def calculate_stats(self):
        stats = super().calculate_stats()
        stats['total_ram_bytes'] = int(D(stats['total_ram_bytes']) * (1 + self.bonus_percent / 100))
        return stats

    def mining_state(self, second):
        state = super().mining_state(second)
        if self.precision == 'exact_storage':
            elapsed = D(str(second - (self.player['mining_last_update_at'] - START).total_seconds()))
            state['buffer'] = min(state['capacity_rtm'], self.player['mining_buffer']
                                  + state['rate_per_min'] * max(D(0), elapsed) / 60)
        return state

    def claim(self, second):
        if self.precision == 'engine':
            return super().claim(second)
        cooldown = int(self.rules['mining'].get('claim_cooldown_seconds', 0))
        if self.last_claim is not None and second - self.last_claim < cooldown:
            return
        state = self.settle(second)
        quantum = D(1).scaleb(-self.rules['rtm_decimal_places'])
        collected = state['buffer']
        if collected > 0:
            # Le reliquat doit sortir de la RAM pour rendre le petit bonus réel :
            # sinon il occupe toujours la fraction de capacité ajoutée et ne se paie jamais.
            self.wallet_remainder_rtm += collected
            amount = self.wallet_remainder_rtm.quantize(quantum, rounding=ROUND_DOWN)
            revenue = MathConfig.convert_rtm_to_usd(amount)
            self.cash += revenue
            self.mining_income += revenue
            self.claimed_rtm += collected
            self.wallet_remainder_rtm -= amount
            self.player['mining_buffer'] = D(0)
            self.claims += 1
            self.last_claim = second

    def refresh_bonus(self, second):
        vote = self.spec['vote']['ram_bonus_percent'] if second < self.vote_until else 0
        referral = self.spec['referral']
        self.sponsored = {key: expiry for key, expiry in self.sponsored.items() if second < expiry}
        count = min(len(self.sponsored), referral['max_active_referees'])
        received = int(second < self.received_until)
        percent = D(min(self.spec['max_total_ram_bonus_percent'],
                        vote + (count + received) * referral['ram_bonus_percent_per_referral']))
        if percent == self.bonus_percent:
            return
        self.settle(second)  # Appliquer l'ancien plafond jusqu'à l'instant du changement.
        self.bonus_percent = percent
        self.stats = self.calculate_stats()
        new_capacity = D(self.stats['total_ram_bytes']) / D(self.rules['mining']['bytes_per_rtm'])
        loss = max(D(0), self.player['mining_buffer'] - new_capacity)
        self.player['mining_buffer'] -= loss
        self.expiry_loss_rtm += loss
        self.log(second, 'bonus_ram', percent=int(percent))

    def after_upgrade(self, second, level):
        if self.variant not in ('referral', 'combined') or self.received_once:
            return
        if level >= self.spec['referral']['required_referee_firewall_level']:
            self.received_once = True
            self.received_until = second + self.spec['referral']['duration_seconds']
            self.schedule(self.received_until, 'expire')
            self.refresh_bonus(second)

    def handle_scheduled_event(self, second, kind):
        action, identity = self.reward_events[kind]
        if action == 'vote':
            self.vote_until = second + self.spec['vote']['duration_seconds']
            self.schedule(self.vote_until, 'expire')
        elif action == 'qualify':
            self.sponsored = {key: expiry for key, expiry in self.sponsored.items() if second < expiry}
            if identity not in self.qualified_once and len(self.sponsored) < self.spec['referral']['max_active_referees']:
                expiry = second + self.spec['referral']['duration_seconds']
                self.sponsored[identity] = expiry
                self.qualified_once.add(identity)
                self.schedule(expiry, 'expire')
        self.refresh_bonus(second)

    def result(self, second):
        return {**super().result(second), 'variant': self.variant, 'precision': self.precision,
                'bonus_percent_at_end': self.bonus_percent, 'expiry_loss_rtm': self.expiry_loss_rtm,
                'wallet_remainder_rtm': self.wallet_remainder_rtm}


def add_savings_strategies():
    for day in range(1, 10):
        for prefix, quota in (('reinvestissement_t1', 0), ('minage', 10), ('pare_feu', 1)):
            name = f'{prefix}_epargne_j{day}'
            STRATEGIES[name] = quota
            SAVE_FROM_DAY[name] = day


def run_experiment(output, runs, cohort='full'):
    rules = MathConfig.load()
    results, timelines = [], []
    spec = rules['ram_rewards']
    max_percent = min(spec['max_total_ram_bonus_percent'], spec['vote']['ram_bonus_percent']
                   + spec['referral']['ram_bonus_percent_per_referral']
                   * (spec['referral']['max_active_referees'] + 1))
    max_variant = f'maximum_{max_percent}'
    normal_profiles = PROFILES if cohort == 'full' else (
        Profile('parrain_actif', STRESS_PROFILE.visit_minutes, 100),)
    with patch.object(MathConfig, 'load', classmethod(lambda cls: rules)):
        for profile in normal_profiles:
            for seed in range(42, 42 + runs):
                unlocks = []
                for child in range(3):
                    result = Simulation(profile, 'pare_feu_prioritaire', 30, seed + 1000 + child).run()
                    if result['firewall_1_day'] is not None:
                        unlocks.append(round(result['firewall_1_day'] * DAY))
                for strategy in ('pare_feu_prioritaire', 'minage_prioritaire', 'reinvestissement_t1'):
                    for precision in ('engine', 'exact_storage'):
                        for variant in ('none', 'vote', 'referral', 'combined', max_variant):
                            sim = RewardSimulation(profile, strategy, 30, seed, variant=variant,
                                                   precision=precision, child_unlocks=unlocks)
                            results.append({**sim.run(), 'experiment': 'profiles_30days'})
                            if seed == 42:
                                timelines.extend({'profile': profile.name, 'strategy': strategy,
                                                  'precision': precision, 'variant': variant, **row}
                                                 for row in sim.actions if row['action'] == 'bonus_ram')
        add_savings_strategies()
        stress = Profile('intensif_24h', STRESS_PROFILE.visit_minutes, 600)
        for strategy in STRATEGIES if cohort == 'full' else ():
            for seed in range(42, 42 + runs):
                for precision in ('engine', 'exact_storage'):
                    for variant in ('none', max_variant):
                        sim = RewardSimulation(stress, strategy, 15, seed, reputation=100,
                                               variant=variant, precision=precision)
                        results.append({**sim.run(), 'experiment': 'stress_15days'})
    grouped = {}
    for row in results:
        key = (row['experiment'], row['profile'], row['strategy'], row['precision'], row['variant'])
        grouped.setdefault(key, []).append(row)
    summary = []
    for key, group in grouped.items():
        baseline = grouped[(*key[:-1], 'none')]
        baseline_by_seed = {row['seed']: row for row in baseline}
        changes = [(row['mining_income_usd'] / baseline_by_seed[row['seed']]['mining_income_usd'] - 1) * 100
                   for row in group if baseline_by_seed[row['seed']]['mining_income_usd'] > 0]
        crossing = [row['cash_100k_day'] for row in group if row['cash_100k_day'] is not None]
        summary.append(dict(zip(('experiment', 'profile', 'strategy', 'precision', 'variant'), key)) | {
            'runs': len(group), 'completed': sum(row['completed'] for row in group),
            'mining_income_median_usd': statistics.median(row['mining_income_usd'] for row in group),
            'mining_income_change_pct_median': statistics.median(changes) if changes else None,
            'earliest_cash_100k_day': min(crossing) if crossing else None,
            'before_day10_count': sum(day < 10 for day in crossing),
        })
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / 'runs.csv', results)
    write_csv(output / 'summary.csv', summary)
    write_csv(output / 'bonus_timeline.csv', timelines)
    violations = [r for r in results if r['cash_100k_day'] is not None and r['cash_100k_day'] < 10]
    metadata = {
        'rules': rules, 'rules_code': MathConfig.code(rules), 'runs_per_scenario': runs,
        'cohort': cohort,
        'all_roles_counted_before_cap': True, 'maximum_ram_bonus_percent': max_percent,
        'stress_reputation': 100, 'stress_wins_per_day': 600, 'normal_reputation': 0,
        'total_runs': len(results), 'completed_runs': sum(r['completed'] for r in results),
        'cash_before_day10_count': len(violations),
        'earliest_cash_100k_day': min((r['cash_100k_day'] for r in results if r['cash_100k_day'] is not None), default=None),
        'notes': [
            'Un vote par jour a la premiere visite dans les scenarios temporaires.',
            'Les trois filleuls sont des simulations independantes de meme profil, priorite pare-feu, sans bonus.',
            'Leur premier FW1 declenche chaque bonus du parrain pour exactement 7 jours.',
            'Le bonus recu comme filleul se declenche au propre FW1 du joueur simule.',
            'Aucune boucle de parrainage ni transfert de monnaie simules.',
            'maximum est une borne volontairement excessive : bonus permanent des J0, sans conditions.',
            'A expiration, capacite reduite immediatement et surplus tronque ; hypothese de simulation.',
            'exact_storage transfere tout le tampon vers un portefeuille precis ; la conversion utilise 5 decimales et conserve le reliquat hors RAM.',
            'Les ecarts de revenus incluent le reinvestissement ; ils ne mesurent pas un bonus de hashrate.',
        ],
    }
    (output / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: metadata[key] for key in ('total_runs', 'completed_runs', 'maximum_ram_bonus_percent',
                                                   'cash_before_day10_count', 'earliest_cash_100k_day')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--cohort', choices=('full', 'active-referrals'), default='full')
    parser.add_argument('--output', type=Path, default=ROOT / 'simulation_results/ram_rewards')
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('--runs doit etre positif')
    run_experiment(args.output, args.runs, args.cohort)
