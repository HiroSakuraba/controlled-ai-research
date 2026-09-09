import unittest
from fractions import Fraction as F
from controlled_ai.sampler import (Sampler, SamplerError, quantile, expect, masses,
                                    filter_normalize, spend, experiment, audit_n)

class QuantileTests(unittest.TestCase):
    def test_pointwise_and_expectation_bounds(self):
        p, cost = masses(100), (0,) * 99 + (1,)
        _, Q = quantile(p, (0,) * 99 + (1,), F(1, 10))
        self.assertEqual(expect(Q, cost), F(1, 10))
        self.assertEqual(expect(p, cost) / F(1, 10), F(1, 10))
        self.assertTrue(all(Q[i] <= p[i] * 10 for i in range(100)))

    def test_boundary_item_is_split(self):
        w, Q = quantile((F(1, 2), F(1, 2)), (1, 0), F(1, 4))
        self.assertEqual(w, (F(1, 4), F(0)))
        self.assertEqual(Q, (F(1), F(0)))

    def test_zero_reference_mass_stays_zero(self):
        _, Q = quantile((F(1), F(0)), (0, 99), F(1, 2))
        self.assertEqual(Q[1], F(0))

    def test_unconstrained_payload_ratio_beats_claimed_factor_ten(self):
        rec = experiment()['one_release']
        self.assertEqual(rec['unconstrained_ratio'], '100')
        self.assertFalse(rec['claimed_K_covers_unconstrained'])
        self.assertTrue(rec['quantile_respects_K'])

    def test_shared_budget_caps_independent_amplification(self):
        rec = experiment()['shared_budget']
        self.assertEqual(rec['independent_two_step_ratio'], '100')
        self.assertEqual(rec['shared_two_step_ratio'], '10')
        self.assertTrue(rec['independent_exceeds_A0'])

    def test_useful_ranking_raises_completion_inside_bound(self):
        rec = experiment()['usefulness']
        self.assertGreater(F(rec['quantile_useful']), F(rec['reference_useful']))
        self.assertLessEqual(F(rec['quantile_harm']), F(rec['bound']))

    def test_permission_filter_before_normalize(self):
        p = filter_normalize(masses(3), (True, True, False))
        self.assertEqual(p, (F(1, 2), F(1, 2), F(0)))

    def test_permission_mask_length_must_match_menu(self):
        with self.assertRaises(SamplerError):
            filter_normalize(masses(3), (True, True))

    def test_spend_rejects_q_outside_remaining_A(self):
        self.assertEqual(spend(10, F(1, 10)), F(1))
        with self.assertRaises(SamplerError):
            spend(2, F(1, 4))

    def test_audit_n_matches_plan(self):
        self.assertEqual(audit_n(), 29956)
        self.assertEqual(experiment()['audit_zero_event_n_for_1e-4'], 29956)

class RuntimeTests(unittest.TestCase):
    def test_attacks_are_rejected(self):
        rec = experiment()['attacks']
        self.assertEqual(rec['retry'], 'free retry forbidden')
        self.assertEqual(rec['refuse'], 'refusal is not a free retry')
        self.assertEqual(rec['insert'], 'model cannot extend the reference menu')
        self.assertEqual(rec['resample'], 'post-selection filtering forbidden')

    def test_crash_replays_recorded_draw(self):
        rec = experiment()['recovery']
        self.assertTrue(rec['same_index'])
        self.assertEqual(rec['A'], '1')
        self.assertEqual(rec['draws'], 1)

    def test_invalid_scores_fall_back_to_reference(self):
        s = Sampler(':memory:', A0=10, seed=0)
        choice, Q = s.decide(('a', 'b'), masses(2), None, F(1, 10))
        self.assertEqual(s.A, F(10))
        self.assertEqual(Q, (F(1, 2), F(1, 2)))
        self.assertIn(choice, ('a', 'b'))
        s.close()

    def test_tampered_record_is_rejected(self):
        s = Sampler(':memory:', A0=10, seed=0)
        s.decide(('a', 'b'), masses(2), (1, 0), F(1, 2))
        s.db.execute("UPDATE event SET choice=? WHERE step=0", ('\"forged\"',))
        s.db.commit()
        with self.assertRaises(SamplerError):
            s.replay(0)
        s.close()

    def test_second_draw_after_spent_budget_must_be_reference(self):
        s = Sampler(':memory:', A0=10, seed=0)
        s.decide(tuple(range(10)), masses(10), tuple(range(10, 0, -1)), F(1, 10))
        with self.assertRaises(SamplerError):
            s.decide(tuple(range(10)), masses(10), tuple(range(10, 0, -1)), F(1, 10))
        choice, Q = s.decide(tuple(range(10)), masses(10), tuple(range(10, 0, -1)), 1)
        self.assertEqual(s.A, F(1))
        self.assertEqual(Q, masses(10))
        s.close()

if __name__ == '__main__':
    unittest.main()
