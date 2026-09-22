"""Vérification des invariants économiques et de la reproductibilité."""

import sys
import unittest
import copy
from unittest.mock import patch
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.math_config import MathConfig
from tools.simulate_balance import DAY, PROFILES, STRESS_PROFILE, Profile, Simulation, aggregate, price


def test_prices_match_game():
    from game.db.players import _calculate_module_price
    for tier in range(1, 6):
        for kind in ('firewall', 'mining'):
            column = kind if kind == 'firewall' else f'mining_t{tier}'
            assert price(kind, tier, MathConfig.load()) == _calculate_module_price(column, tier)[0]


def test_t1_saturation_and_conversion():
    # Petit scénario contrôlé, indépendant des réglages d'équilibrage en production.
    rules = copy.deepcopy(MathConfig.load())
    rules['module_stats']['mining_hashrate_hs']['1'] = 25
    rules['module_stats']['mining_ram_bytes']['1'] = 200
    rules['mining']['rootium_per_hs_per_minute'] = 0.0000001
    rules['mining']['bytes_per_rtm'] = 10000000
    with patch.object(MathConfig, 'load', return_value=rules):
        sim = Simulation(PROFILES[0], 'pare_feu_prioritaire', 1, 42, event_scale=0)
        result = sim.run()
        assert result['claimed_rtm'] == D('0.00004')
        assert result['mining_income_usd'] == MathConfig.convert_rtm_to_usd(D('0.00002')) * 2
        assert result['buffer_rtm'] == D('0.00002')
    assert result['firewall'] == 0
    assert result['tier_2_day'] is None
    assert result['completed']


def test_cash_and_production_conservation():
    sim = Simulation(PROFILES[1], 'minage_prioritaire', 10, 8)
    result = sim.run()
    grant = D(str(MathConfig.load()['initial_grant_usd']))
    assert abs(grant + result['total_income_usd'] - result['spent_usd'] - result['cash_usd']) < D('0.00001')
    balance = (result['theoretical_rtm'] - result['saturation_loss_rtm']
               + result['rounding_rtm'] - result['claimed_rtm'] - result['buffer_rtm'])
    assert abs(balance) < D('0.0000001')


def test_reproducible_randomness_and_daily_snapshots_are_read_only():
    first = Simulation(PROFILES[1], 'pare_feu_prioritaire', 5, 42)
    second = Simulation(PROFILES[1], 'pare_feu_prioritaire', 5, 42)
    assert first.run() == second.run()
    assert first.actions == second.actions
    probe = Simulation(PROFILES[0], 'pare_feu_prioritaire', 1, 42)
    probe.invest(0)
    before = probe.player.copy()
    probe.snapshot(100)
    probe.snapshot(200)
    assert probe.player == before


def test_upgrade_delay_and_tier_requirements():
    sim = Simulation(PROFILES[2], 'pare_feu_prioritaire', 12, 42)
    sim.cash = D(50000)  # Isoler les délais du rythme d'accumulation des revenus.
    sim.run()
    level, started = 0, {}
    for action in sim.actions:
        if action['action'] == 'debut_pare_feu':
            started[action['level']] = action['day']
        elif action['action'] == 'fin_pare_feu':
            level = action['level']
            duration = (action['day'] - started[level]) * DAY
            assert abs(duration - sim.rules['firewall']['upgrade_duration_seconds']) < 1
        elif action['action'] == 'achat_minage':
            assert action['tier'] <= level + sim.rules['firewall']['max_tier_above']
    assert level >= 1


def test_numeric_overflow_is_reported_as_partial_not_day_30():
    # Conserver la régression de l'ancien emballement, même après rééquilibrage.
    rules = copy.deepcopy(MathConfig.load())
    rules['initial_grant_usd'] = 100
    rules['mining']['cost_t1_usd'] = 100
    rules['mining']['cost_multiplier'] = 1.5
    rules['firewall']['first_upgrade_usd'] = 1000
    rules['firewall']['upgrade_multiplier'] = 2.5
    rules['conversion']['rtm_to_usd'] = 43567
    rules['module_stats']['mining_hashrate_hs'] = {
        '1': 25, '2': 250, '3': 1250, '4': 7500, '5': 50000,
    }
    rules['module_stats']['mining_ram_bytes'] = {
        '1': 200, '2': 3000, '3': 43750, '4': 375000, '5': 3750000,
    }
    rules['event_firewall_multipliers'] = {str(i): 2 ** i for i in range(6)}
    with patch.object(MathConfig, 'load', return_value=rules):
        sim = Simulation(PROFILES[2], 'minage_prioritaire', 30, 42)
        result = sim.run()
    assert not result['completed']
    assert result['error'] == 'decimal_precision_exceeded'
    assert result['day'] <= result['stopped_day'] < 30
    assert result['tier_5_day'] < result['stopped_day']


def test_unreached_milestones_are_not_zero_days():
    results = [Simulation(profile, strategy, 1, 42, event_scale=0).run()
               for profile in PROFILES
               for strategy in ('pare_feu_prioritaire', 'minage_prioritaire')]
    for row in aggregate(results):
        assert row['tier_5_day_reached_pct'] == 0
        assert row['tier_5_day_median_if_reached'] is None


def test_cash_threshold_is_measured_before_reinvestment():
    sim = Simulation(PROFILES[0], 'reinvestissement_t1', 1, 42)
    sim.cash = D('100001')
    sim.track_thresholds(5 * DAY)
    sim.invest(5 * DAY)
    assert sim.cash < 100
    assert sim.cash_100k_day == 5
    assert sim.income_100k_day is None  # Le cash n'est pas assimilé aux revenus cumulés.


def test_saving_strategy_stops_purchases():
    sim = Simulation(PROFILES[0], 'reinvestissement_t1_epargne_j5', 1, 42)
    sim.cash = D(500)
    sim.invest(5 * DAY)
    assert sim.cash == 500
    assert sim.player.get('mining_t1', 0) == 0


def test_all_mining_tiers_take_at_least_twelve_days_to_pay_back_without_reputation():
    rules = MathConfig.load()
    for tier in range(1, 6):
        per_day = (D(MathConfig.get_module_stat('mining', tier))
                   * D(str(rules['mining']['rootium_per_hs_per_minute']))
                   * 1440 * MathConfig.rtm_to_usd_rate())
        assert price('mining', tier, rules) / per_day >= 12


def test_combat_prices_are_independent_of_mining_increase_and_keep_legacy_fallback():
    from game.db.players import _calculate_module_price
    assert _calculate_module_price('attack_t5', 5)[1] == D('.005') * D('1.5') ** 4
    assert _calculate_module_price('bay_defense_t5', 5)[0] == D(75) * D('1.5') ** 4
    rules = copy.deepcopy(MathConfig.load())
    del rules['beta']['cost_multiplier']
    rules['mining']['cost_multiplier'] = 2
    with patch.object(MathConfig, 'load', return_value=rules):
        assert _calculate_module_price('attack_t2', 2)[1] == D('.010')


def test_extreme_saving_profile_does_not_reach_100k_before_day10():
    rules = MathConfig.load()
    profile = Profile('extreme', STRESS_PROFILE.visit_minutes, 600)
    with patch.object(MathConfig, 'load', classmethod(lambda cls: rules)):
        for seed in (42, 43, 44):
            for strategy in ('reinvestissement_t1_epargne_j5', 'minage_epargne_j5'):
                result = Simulation(profile, strategy, 15, seed, reputation=100).run()
                assert result['completed']
                assert result['cash_100k_day'] is None or result['cash_100k_day'] >= 10


def test_calibration_preserves_claim_cadence_when_hashrate_changes():
    from tools.calibrate_balance import candidate
    base = copy.deepcopy(MathConfig.load())
    modified = candidate(base, 2780, 3)
    for tier, minutes in {1: 8, 2: 12, 3: 35, 4: 50, 5: 75}.items():
        stats = modified['module_stats']
        rate = D(stats['mining_hashrate_hs'][str(tier)]) * D(str(modified['mining']['rootium_per_hs_per_minute']))
        capacity = D(stats['mining_ram_bytes'][str(tier)]) / D(modified['mining']['bytes_per_rtm'])
        assert capacity / rate == minutes


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith('test_') and callable(fn))
