"""Expériences reproductibles de réglage ; conserve les règles et résultats testés.

Écrit data/math.json uniquement avec --apply ; aucune connexion au bot/SQL.
"""

import argparse
import copy
import json
import math
from dataclasses import asdict
from pathlib import Path
import sys
from decimal import Decimal
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.simulate_balance import MathConfig, PROFILES, STRESS_PROFILE, STRATEGIES, SAVE_FROM_DAY, Profile, Simulation, aggregate, write_csv


def preserve_claim_cadence(rules, base):
    """La fréquence des claims est une mécanique à conserver pendant le réglage."""
    for tier, old_ram in base['module_stats']['mining_ram_bytes'].items():
        old_rate = (Decimal(base['module_stats']['mining_hashrate_hs'][tier])
                    * Decimal(str(base['mining']['rootium_per_hs_per_minute'])))
        minutes = Decimal(old_ram) / Decimal(base['mining']['bytes_per_rtm']) / old_rate
        new_rate = (Decimal(rules['module_stats']['mining_hashrate_hs'][tier])
                    * Decimal(str(rules['mining']['rootium_per_hs_per_minute'])))
        rules['module_stats']['mining_ram_bytes'][tier] = int(
            minutes * new_rate * Decimal(rules['mining']['bytes_per_rtm']))


def candidate(base, rate, firewall_reward_max, reward_scale=1):
    rules = copy.deepcopy(base)
    rules['version'] = f'1.1.0-candidate-{rate}-{firewall_reward_max}'
    rules['conversion']['rtm_to_usd'] = rate
    rules['module_stats']['mining_hashrate_hs'] = {
        '1': 25, '2': 38, '3': 56, '4': 84, '5': 126,
    }
    preserve_claim_cadence(rules, base)
    rewards = (1, 1, 2, 2, 3, 3) if firewall_reward_max == 3 else (1, 1, 1, 2, 2, 2)
    rules['event_firewall_multipliers'] = {str(i): v for i, v in enumerate(rewards)}
    for key, cfg in rules.items():
        if key.endswith('_challenge'):
            cfg['reward_min_usd'] = round(cfg['reward_min_usd'] * reward_scale, 2)
            cfg['reward_max_usd'] = round(cfg['reward_max_usd'] * reward_scale, 2)
    return rules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rate', type=int, default=2780)
    parser.add_argument('--reward-max', type=int, choices=(2, 3), default=3)
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--reputation', type=int, default=0)
    parser.add_argument('--stress-wins', type=float, default=100)
    parser.add_argument('--reward-scale', type=float, default=1)
    parser.add_argument('--price-based', action='store_true')
    parser.add_argument('--config', type=Path, help='Tester exactement ce fichier, sans générer de candidat')
    parser.add_argument('--sweep-saving', action='store_true')
    parser.add_argument('--stress-only', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (args.days < 1 or args.runs < 1 or args.rate <= 0 or args.reputation < 0
            or not math.isfinite(args.stress_wins) or args.stress_wins < 0
            or not math.isfinite(args.reward_scale) or args.reward_scale <= 0):
        parser.error('Durées, tirages, taux et récompenses positifs ; réputation/victoires non négatives.')
    base = json.loads((ROOT / 'simulation_results/baseline/metadata.json').read_text(encoding='utf-8'))['rules']
    rules = base if args.baseline else candidate(base, args.rate, args.reward_max, args.reward_scale)
    if args.price_based:
        rules['version'] = '1.1.1'
        rules['initial_grant_usd'] = 2000
        rules['mining']['cost_t1_usd'] = 2000
        rules['mining']['cost_multiplier'] = 5
        rules['beta']['cost_multiplier'] = base['mining']['cost_multiplier']
        rules['conversion']['rtm_to_usd'] = base['conversion']['rtm_to_usd']
        rules['firewall']['first_upgrade_usd'] = 10000
        rules['firewall']['upgrade_multiplier'] = 3
        for key, cfg in rules.items():
            if key.endswith('_challenge'):
                cfg['reward_min_usd'] = 7.5
                cfg['reward_max_usd'] = 20.0
        rates = [25 * 5 ** i for i in range(5)]
        rules['module_stats']['mining_hashrate_hs'] = {str(i + 1): h for i, h in enumerate(rates)}
        preserve_claim_cadence(rules, base)
    if args.config:
        rules = json.loads(args.config.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=True)
    config = args.output.resolve() / 'math.json'
    serialized = json.dumps(rules, ensure_ascii=False, indent=2) + '\n'
    config.write_text(serialized, encoding='utf-8')
    if args.apply:
        config = ROOT / 'data/math.json'
        config.write_text(serialized, encoding='utf-8')
    MathConfig.path = config
    MathConfig.clear_cache()
    runs, daily = [], []
    stress = Profile(STRESS_PROFILE.name, STRESS_PROFILE.visit_minutes, args.stress_wins)
    profiles = (stress,) if args.stress_only else (*PROFILES, stress)
    if args.sweep_saving:
        for day in range(1, 10):
            for prefix, quota in (('reinvestissement_t1', 0), ('minage', 10), ('pare_feu', 1)):
                name = f'{prefix}_epargne_j{day}'
                STRATEGIES[name] = quota
                SAVE_FROM_DAY[name] = day
    # Une expérience emploie un instantané immuable : pas de stat/lecture du JSON
    # à chaque calcul. Toutes les formules du moteur restent inchangées.
    with patch.object(MathConfig, 'load', classmethod(lambda cls: rules)):
        for profile in profiles:
            for strategy in STRATEGIES:
                for index in range(args.runs):
                    sim = Simulation(profile, strategy, args.days, 42 + index, args.reputation)
                    runs.append(sim.run())
                    if index == 0:
                        daily.extend({'profile': profile.name, 'strategy': strategy, **row} for row in sim.daily)
    summary = aggregate(runs)
    write_csv(args.output / 'summary.csv', summary)
    write_csv(args.output / 'runs.csv', runs)
    write_csv(args.output / 'daily.csv', daily)
    violations = [r for r in runs if r['cash_100k_day'] is not None and r['cash_100k_day'] < 10]
    earliest = min((r['cash_100k_day'] for r in runs if r['cash_100k_day'] is not None), default=None)
    metadata = {'days': args.days, 'runs_per_scenario': args.runs, 'reputation': args.reputation,
                'stress_wins_per_day': args.stress_wins,
                'strategies': STRATEGIES, 'save_from_day': SAVE_FROM_DAY,
                'profiles': [asdict(profile) for profile in profiles],
                'stress_only': args.stress_only,
                'seed_start': 42, 'rules_code': MathConfig.code(rules),
                'total_runs': len(runs), 'cash_before_day10_violations': len(violations),
                'earliest_cash_100k_day': earliest, 'completed_runs': sum(r['completed'] for r in runs)}
    (args.output / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps(metadata))
    for row in summary:
        if row['profile'] in ('tres_actif', 'intensif_24h'):
            print(row['profile'], row['strategy'], 'cash100k=', row['cash_100k_day_earliest'],
                  'cash median=', row['cash_usd_median'])


if __name__ == '__main__':
    main()
