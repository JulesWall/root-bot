"""Specification des bonus temporaires, sans activation dans le bot."""

import sys
import unittest
from pathlib import Path
from decimal import Decimal as D
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.simulate_balance import DAY, PROFILES, MathConfig
from tools.simulate_ram_rewards import RewardSimulation


class TestRamRewardsSimulation(unittest.TestCase):
    def setUp(self):
        rules = MathConfig.load()
        self.patch = patch.object(MathConfig, 'load', classmethod(lambda cls: rules))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def simulation(self, **kwargs):
        sim = RewardSimulation(PROFILES[0], 'pare_feu_prioritaire', 15, 42, **kwargs)
        sim.invest(0)
        return sim

    def event(self, sim, second, action, identity=None):
        sim.reward_events['test_event'] = (action, identity)
        sim.handle_scheduled_event(second, 'test_event')

    def test_vote_duration_and_refresh_without_stacking(self):
        sim = self.simulation(variant='vote')
        self.event(sim, 0, 'vote')
        self.assertEqual(sim.bonus_percent, 20)
        self.assertEqual(sim.stats['total_ram_bytes'], 240)
        self.event(sim, 3600, 'vote')
        self.assertEqual(sim.bonus_percent, 20)
        self.assertEqual(sim.vote_until, 7 * 3600)
        self.event(sim, 6 * 3600, 'expire')
        self.assertEqual(sim.bonus_percent, 20)
        self.event(sim, 7 * 3600, 'expire')
        self.assertEqual(sim.bonus_percent, 0)

    def test_referee_bonus_waits_for_firewall_one_and_lasts_seven_days(self):
        sim = self.simulation(variant='combined')
        sim.after_upgrade(0, 0)
        self.assertEqual(sim.bonus_percent, 0)
        sim.after_upgrade(DAY, 1)
        self.assertEqual(sim.bonus_percent, 10)
        self.assertEqual(sim.received_until, 8 * DAY)
        sim.after_upgrade(2 * DAY, 2)
        self.assertEqual(sim.received_until, 8 * DAY)
        self.event(sim, 8 * DAY, 'expire')
        self.assertEqual(sim.bonus_percent, 0)

    def test_sponsor_three_distinct_referees_independent_expirations(self):
        sim = self.simulation(variant='referral')
        for index in range(3):
            self.event(sim, index * DAY, 'qualify', index)
        self.event(sim, 3 * DAY, 'qualify', 3)
        self.assertEqual(sim.bonus_percent, 30)
        self.assertEqual(len(sim.sponsored), 3)
        self.event(sim, 7 * DAY, 'expire')
        self.assertEqual(sim.bonus_percent, 20)
        self.event(sim, 7 * DAY, 'qualify', 0)
        self.assertEqual(sim.bonus_percent, 20)
        self.event(sim, 9 * DAY, 'expire')
        self.assertEqual(sim.bonus_percent, 0)

    def test_bonus_changes_capacity_not_mining_rate(self):
        base = self.simulation()
        boosted = self.simulation(variant='maximum_60')
        self.assertEqual(boosted.stats['total_ram_bytes'], 300)
        self.assertEqual(boosted.bonus_percent, 50)
        self.assertEqual(boosted.mining_state(0)['rate_per_min'], base.mining_state(0)['rate_per_min'])

    def test_fractional_storage_retains_a_small_bonus(self):
        sim = self.simulation(variant='maximum_20', precision='exact_storage')
        sim.claim(20 * 60)
        self.assertEqual(sim.claimed_rtm, D('.000024'))
        self.assertEqual(sim.player['mining_buffer'], D(0))
        self.assertEqual(sim.wallet_remainder_rtm, D('.000004'))
        for index in range(2, 6):
            sim.claim(index * 20 * 60)
        self.assertEqual(sim.claimed_rtm, D('.00012'))
        self.assertEqual(sim.wallet_remainder_rtm, D(0))

    def test_expiration_settles_old_capacity_before_reducing_it(self):
        sim = self.simulation(variant='vote', precision='exact_storage')
        self.event(sim, 0, 'vote')
        self.event(sim, 6 * 3600, 'expire')
        self.assertEqual(sim.player['mining_buffer'], D('.00002'))
        self.assertEqual(sim.expiry_loss_rtm, D('.000004'))

    def test_both_roles_count_then_global_cap_applies(self):
        sim = self.simulation(variant='combined')
        for index in range(3):
            self.event(sim, 0, 'qualify', index)
        sim.after_upgrade(0, 1)
        self.assertEqual(sim.bonus_percent, 40)
        self.event(sim, 0, 'vote')
        self.assertEqual(sim.bonus_percent, 50)
        self.event(sim, 6 * 3600, 'expire')
        self.assertEqual(sim.bonus_percent, 40)


if __name__ == '__main__':
    unittest.main()
