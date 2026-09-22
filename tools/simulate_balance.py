"""Simulation locale de l'économie Root, sans Discord ni base de données.

Usage : python tools/simulate_balance.py --days 30 --runs 20 --seed 42
Voir tools/SIMULATION.md pour les hypothèses et les limites.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import random
import statistics
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.math_config import MathConfig

D = Decimal
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
DAY = 86400


@dataclass(frozen=True)
class Profile:
    name: str
    visit_minutes: tuple[int, ...]
    wins_per_day: float


PROFILES = (
    Profile('occasionnel', (9 * 60, 21 * 60), 1),
    Profile('regulier', (9 * 60, 12 * 60, 15 * 60, 18 * 60, 21 * 60, 23 * 60), 4),
    Profile('tres_actif', tuple(range(9 * 60, 23 * 60 + 1, 15)), 10),
)
STRATEGIES = {'pare_feu_prioritaire': 1, 'minage_prioritaire': 10}
STRESS_PROFILE = Profile('intensif_24h', tuple(range(0, 24 * 60, 8)), 100)
STRATEGIES['reinvestissement_t1'] = 0
SAVE_FROM_DAY = {
    'reinvestissement_t1_epargne_j5': 5, 'reinvestissement_t1_epargne_j8': 8,
    'minage_epargne_j5': 5, 'minage_epargne_j8': 8,
}
STRATEGIES.update({key: (0 if key.startswith('reinvestissement_t1') else 10)
                   for key in SAVE_FROM_DAY})


def price(kind: str, tier: int, rules: dict) -> Decimal:
    """Même formule que _calculate_module_price, sans importer la couche SQL."""
    cfg = rules['firewall' if kind == 'firewall' else 'mining']
    base = cfg['first_upgrade_usd' if kind == 'firewall' else 'cost_t1_usd']
    factor = cfg['upgrade_multiplier' if kind == 'firewall' else 'cost_multiplier']
    return D(str(base)) * D(str(factor)) ** (tier - 1)


def poisson(rng: random.Random, mean: float) -> int:
    """Nombre de victoires à une visite, selon une loi de Poisson."""
    total, count = 0.0, 0
    if mean <= 0:
        return 0
    while True:
        total += rng.expovariate(mean)
        if total > 1:
            return count
        count += 1


class Simulation:
    def __init__(self, profile: Profile, strategy: str, days: int, seed: int,
                 reputation: int = 0, event_scale: float = 1):
        if days < 1 or reputation < 0 or not math.isfinite(event_scale) or event_scale < 0:
            raise ValueError('Durée positive, réputation et événements non négatifs requis.')
        self.rules = MathConfig.load()
        self.profile, self.strategy, self.days, self.seed = profile, strategy, days, seed
        self.event_scale = event_scale
        self.rng = random.Random(seed)
        self.player = {
            'firewall_level': 0, 'reputation': reputation,
            'mining_buffer': D(0), 'mining_last_update_at': START,
        }
        self.cash = D(str(self.rules['initial_grant_usd']))
        self.mining_income = self.event_income = self.spent = D(0)
        self.claimed_rtm = self.lost_rtm = self.theoretical_rtm = D(0)
        self.rounding_rtm = D(0)
        self.wins = self.claims = 0
        self.last_claim = None
        self.pending = None
        self.peak_cash = self.cash
        self.income_100k_day = None
        self.cash_100k_day = None
        self.milestones = {}
        self.actions, self.daily = [], []
        self.queue = []
        self.stats = self.calculate_stats()
        self.challenges = [v for k, v in self.rules.items() if k.endswith('_challenge')]

    def log(self, second, action, **detail):
        self.actions.append({'day': round(second / DAY, 6), 'action': action, **detail})

    def calculate_stats(self):
        return MathConfig.calculate_player_stats(self.player)

    def mining_state(self, second):
        return MathConfig.compute_mining_progress(
            self.player, self.stats, START + timedelta(seconds=second))

    def after_upgrade(self, second, level):
        """Point d'extension des experiences, sans modifier les regles du bot."""

    def handle_scheduled_event(self, second, kind):
        raise ValueError(f'Evenement de simulation inconnu : {kind}')

    def settle(self, second: int) -> dict:
        now = START + timedelta(seconds=second)
        state = self.mining_state(second)
        elapsed = D(str((now - self.player['mining_last_update_at']).total_seconds()))
        produced = state['rate_per_min'] * elapsed / 60
        raw = self.player['mining_buffer'] + produced
        capped = min(raw, state['capacity_rtm'])
        self.theoretical_rtm += produced
        self.lost_rtm += max(D(0), raw - state['capacity_rtm'])
        # L'arrondi à 5 décimales du jeu est conservé et mesuré séparément.
        self.rounding_rtm += state['buffer'] - capped
        self.player['mining_buffer'] = state['buffer']
        self.player['mining_last_update_at'] = now
        return state

    def claim(self, second: int):
        cooldown = int(self.rules['mining'].get('claim_cooldown_seconds', 0))
        if self.last_claim is not None and second - self.last_claim < cooldown:
            return
        state = self.settle(second)
        amount = state['buffer']
        if amount > 0:
            revenue = MathConfig.convert_rtm_to_usd(amount)
            self.cash += revenue
            self.mining_income += revenue
            self.claimed_rtm += amount
            self.player['mining_buffer'] = D(0)
            self.claims += 1
            self.last_claim = second

    def events(self):
        expected = self.profile.wins_per_day * self.event_scale / len(self.profile.visit_minutes)
        count = poisson(self.rng, expected)
        for _ in range(count):
            cfg = self.rng.choice(self.challenges)
            # Distribution uniforme de récompenses en centimes, approximation explicite.
            cents = self.rng.randint(round(cfg['reward_min_usd'] * 100),
                                     round(cfg['reward_max_usd'] * 100))
            reward = D(cents) / 100 * MathConfig.get_event_firewall_multiplier(
                self.player['firewall_level'])
            self.cash += reward
            self.event_income += reward
        self.wins += count

    def invest(self, second: int):
        if second >= SAVE_FROM_DAY.get(self.strategy, math.inf) * DAY:
            return
        if self.pending is not None:
            return
        fw = self.player['firewall_level']
        tier = min(5, fw + int(self.rules['firewall'].get('max_tier_above', 1)))
        t1_only = self.strategy.startswith('reinvestissement_t1')
        if t1_only:
            tier = 1
        required = max(int(self.rules['beta']['required_firewall']['mining']),
                       tier - int(self.rules['firewall'].get('max_tier_above', 1)))
        if tier < 1 or fw < required:
            return
        column = f'mining_t{tier}'
        unit_price = price('mining', tier, self.rules)
        count = int(self.cash // unit_price)
        # À pare-feu maximal, tous les fonds sont réinvestis dans le dernier tier.
        max_fw = min(5, int(self.rules['firewall']['max_level']))
        if fw < max_fw and not t1_only:
            count = min(count, max(0, STRATEGIES[self.strategy] - self.player.get(column, 0)))
        if count > 0:
            self.settle(second)  # Cristalliser le minage AVANT le changement de matériel.
            cost = count * unit_price
            self.cash -= cost
            self.spent += cost
            self.player[column] = self.player.get(column, 0) + count
            self.stats = self.calculate_stats()
            self.milestones.setdefault(f'tier_{tier}_day', second / DAY)
            self.log(second, 'achat_minage', tier=tier, count=count, cost_usd=cost)
        quota_met = self.player.get(column, 0) >= STRATEGIES[self.strategy]
        if fw < max_fw and quota_met and not t1_only:
            cost = price('firewall', fw + 1, self.rules)
            if self.cash >= cost:
                self.cash -= cost
                self.spent += cost
                duration = int(self.rules['firewall']['upgrade_duration_seconds'])
                end = second + duration
                self.pending = (end, fw + 1)
                heapq.heappush(self.queue, (end, 0, 'upgrade'))
                self.log(second, 'debut_pare_feu', level=fw + 1, cost_usd=cost)

    def track_thresholds(self, second: int):
        self.peak_cash = max(self.peak_cash, self.cash)
        if self.income_100k_day is None and self.mining_income + self.event_income >= 100000:
            self.income_100k_day = second / DAY
        if self.cash_100k_day is None and self.cash >= 100000:
            self.cash_100k_day = second / DAY

    def snapshot(self, second: int) -> dict:
        # Lecture seule : un export ne doit pas ajouter d'arrondis au moteur.
        state = self.mining_state(second)
        return {
            'day': second / DAY, 'cash_usd': self.cash,
            'mining_income_usd': self.mining_income, 'event_income_usd': self.event_income,
            'spent_usd': self.spent, 'firewall': self.player['firewall_level'],
            'hashrate_hs': self.stats['total_hashrate_hs'], 'buffer_rtm': state['buffer'],
            'capacity_rtm': state['capacity_rtm'], 'wins': self.wins,
            'total_income_usd': self.mining_income + self.event_income,
            'peak_cash_usd': self.peak_cash, 'income_100k_day': self.income_100k_day,
            'cash_100k_day': self.cash_100k_day,
            **{f'mining_t{t}': self.player.get(f'mining_t{t}', 0) for t in range(1, 6)},
        }

    def result(self, second: int) -> dict:
        result = self.snapshot(second)
        result.update({
            'profile': self.profile.name, 'strategy': self.strategy, 'seed': self.seed,
            'total_income_usd': self.mining_income + self.event_income,
            'claims': self.claims, 'claimed_rtm': self.claimed_rtm,
            'theoretical_rtm': self.theoretical_rtm, 'saturation_loss_rtm': self.lost_rtm,
            'rounding_rtm': self.rounding_rtm,
            'saturation_loss_pct': (100 * self.lost_rtm / self.theoretical_rtm
                                    if self.theoretical_rtm else D(0)),
            **{f'{kind}_{level}_day': self.milestones.get(f'{kind}_{level}_day')
               for kind in ('tier', 'firewall') for level in range(1, 6)},
        })
        return result

    def run(self) -> dict:
        for day in range(self.days):
            for minute in self.profile.visit_minutes:
                heapq.heappush(self.queue, (day * DAY + minute * 60, 1, 'visit'))
            heapq.heappush(self.queue, ((day + 1) * DAY, 2, 'snapshot'))
        self.invest(0)
        self.daily.append(self.snapshot(0))
        checkpoint = self.result(0)
        horizon = self.days * DAY
        try:
            while self.queue:
                second, _, kind = heapq.heappop(self.queue)
                if second > horizon:
                    break
                if kind == 'upgrade':
                    _, level = self.pending
                    self.player['firewall_level'] = level
                    self.pending = None
                    self.milestones[f'firewall_{level}_day'] = second / DAY
                    self.log(second, 'fin_pare_feu', level=level)
                    self.after_upgrade(second, level)
                elif kind == 'visit':
                    self.claim(second)
                    self.events()
                    self.track_thresholds(second)
                    self.invest(second)
                    checkpoint = self.result(second)
                elif kind == 'snapshot':
                    self.daily.append(self.snapshot(second))
                else:
                    self.handle_scheduled_event(second, kind)
            second = horizon
            self.settle(horizon)
            return {**self.result(horizon), 'completed': True, 'stopped_day': None, 'error': ''}
        except InvalidOperation:
            # Conserver le dernier état valide, sans extrapoler ni changer les règles.
            self.actions = [a for a in self.actions if a['day'] <= round(checkpoint['day'], 6)]
            self.daily = [r for r in self.daily if r['day'] <= checkpoint['day']]
            return {**checkpoint, 'completed': False, 'stopped_day': second / DAY,
                    'error': 'decimal_precision_exceeded'}


def aggregate(results: list[dict]) -> list[dict]:
    rows = []
    for profile in dict.fromkeys(r['profile'] for r in results):
        for strategy in dict.fromkeys(r['strategy'] for r in results if r['profile'] == profile):
            group = [r for r in results if r['profile'] == profile and r['strategy'] == strategy]
            row = {'profile': profile, 'strategy': strategy, 'runs': len(group)}
            completed = [r for r in group if r['completed']]
            stopped = [r['stopped_day'] for r in group if not r['completed']]
            row['completed_pct'] = 100 * len(completed) / len(group)
            row['stopped_day_median'] = statistics.median(stopped) if stopped else None
            threshold_days = [r['income_100k_day'] for r in group if r['income_100k_day'] is not None]
            row['income_100k_day_earliest'] = min(threshold_days) if threshold_days else None
            row['income_100k_day_median_if_reached'] = statistics.median(threshold_days) if threshold_days else None
            row['income_100k_reached_pct'] = 100 * len(threshold_days) / len(group)
            row['income_100k_before_day10_pct'] = 100 * sum(d < 10 for d in threshold_days) / len(group)
            cash_days = [r['cash_100k_day'] for r in group if r['cash_100k_day'] is not None]
            row['cash_100k_day_earliest'] = min(cash_days) if cash_days else None
            row['cash_100k_day_median_if_reached'] = statistics.median(cash_days) if cash_days else None
            row['cash_100k_reached_pct'] = 100 * len(cash_days) / len(group)
            row['cash_100k_before_day10_pct'] = 100 * sum(d < 10 for d in cash_days) / len(group)
            for key in ('total_income_usd', 'mining_income_usd', 'event_income_usd',
                        'saturation_loss_pct', 'cash_usd', 'peak_cash_usd', 'firewall', 'mining_t5'):
                values = sorted(float(r[key]) for r in completed)
                row[f'{key}_median'] = statistics.median(values) if values else None
                row[f'{key}_p10'] = values[max(0, math.ceil(len(values) * .1) - 1)] if values else None
                row[f'{key}_p90'] = values[max(0, math.ceil(len(values) * .9) - 1)] if values else None
            for key in [f'{kind}_{level}_day' for kind in ('tier', 'firewall') for level in range(1, 6)]:
                reached = [r[key] for r in group if r[key] is not None]
                row[f'{key}_reached_pct'] = 100 * len(reached) / len(group)
                row[f'{key}_median_if_reached'] = statistics.median(reached) if reached else None
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict]):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--runs', type=int, default=20, help='Tirages par profil et stratégie')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--reputation', type=int, default=0, help='Réputation fixe')
    parser.add_argument('--stress', action='store_true', help='Ajouter un profil 24 h, 100 victoires/jour')
    parser.add_argument('--event-scale', type=float, default=1, help='0 désactive les événements')
    parser.add_argument('--config', type=Path, default=MathConfig.path)
    parser.add_argument('--output', type=Path, default=ROOT / 'simulation_results' / 'baseline')
    args = parser.parse_args()
    if (args.days < 1 or args.runs < 1 or args.reputation < 0
            or not math.isfinite(args.event_scale) or args.event_scale < 0):
        parser.error('days/runs doivent être positifs ; reputation/event-scale non négatifs et finis.')
    MathConfig.path = args.config.resolve()
    MathConfig.clear_cache()
    rules = MathConfig.load()
    results, daily, actions = [], [], []
    profiles = (*PROFILES, STRESS_PROFILE) if args.stress else PROFILES
    for profile in profiles:
        for strategy in STRATEGIES:
            for index in range(args.runs):
                sim = Simulation(profile, strategy, args.days, args.seed + index,
                                 args.reputation, args.event_scale)
                results.append(sim.run())
                if index == 0:
                    identity = {'profile': profile.name, 'strategy': strategy, 'seed': args.seed}
                    daily.extend({**identity, **row} for row in sim.daily)
                    actions.extend({**identity, **row} for row in sim.actions)
    summary = aggregate(results)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in [('summary', summary), ('runs', results), ('daily', daily), ('actions', actions)]:
        write_csv(args.output / f'{name}.csv', rows)
    metadata = {
        'days': args.days, 'runs_per_scenario': args.runs, 'seed': args.seed,
        'reputation': args.reputation, 'event_scale': args.event_scale,
        'profiles': [asdict(p) for p in profiles], 'strategy_miner_quotas': STRATEGIES,
        'save_from_day': SAVE_FROM_DAY,
        'rules_code': MathConfig.code(rules), 'rules': rules,
        'notes': [
            'Profils indépendants ; les victoires ne se partagent pas un serveur simulé.',
            'Victoires Poisson par visite ; récompenses uniformes en centimes.',
            'Aucun PvP, scan, compile, échange ou progression de réputation.',
            'Conversion de tout le RTM après chaque claim ; pas de claim forcé à la fin.',
            'Paliers séquentiels ; chantiers livrés exactement à échéance (sans latence de boucle).',
            'daily/actions décrivent seulement la première graine, pas une trajectoire médiane.',
            'Médianes des délais conditionnelles : uniquement les tirages ayant atteint le palier.',
            'P10/P90 empiriques au rang supérieur ; pas des intervalles de confiance.',
            'Revenus résumés uniquement sur les runs terminés ; consulter completed_pct.',
            'Un dépassement Decimal arrête le run ; runs.csv conserve son dernier état valide.',
        ],
    }
    (args.output / 'metadata.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    for row in summary:
        t5 = row['tier_5_day_median_if_reached']
        income = row['total_income_usd_median']
        income_text = f'{income:.2f}' if income is not None else 'indisponibles (arret numerique)'
        print(f"{row['profile']:12} {row['strategy']:22} "
              f"revenus medians={income_text} USD ; "
              f"T5={t5 if t5 is not None else 'non atteint'} jours ; "
              f"atteint={row['tier_5_day_reached_pct']:.0f}% ; "
              f"termines={row['completed_pct']:.0f}% ; "
              f"100k cash au plus tot J{row['cash_100k_day_earliest']}")
    print(f'Exports : {args.output.resolve()}')


if __name__ == '__main__':
    main()
