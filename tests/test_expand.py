import unittest
from fractions import Fraction as F
from controlled_ai.expand import (setup_trigger, partial_obs, delayed_certificate,
                                  horizon_transfer, reference_process, experiment)
from controlled_ai.certificates import check

class SetupTriggerTests(unittest.TestCase):
    def test_appendix_f_case1(self):
        rec = setup_trigger()
        self.assertEqual(rec['one_step_mutate'], 0)
        self.assertEqual(rec['one_step_release'], 0)
        self.assertEqual(rec['setup_trigger_harms'], 1)
        self.assertTrue(rec['appendix_f_case1'])

class PartialObsTests(unittest.TestCase):
    def test_bracket_and_gap(self):
        rec = partial_obs()
        self.assertEqual(F(rec['full_info']), 1)
        self.assertEqual(F(rec['limited_open_loop']), F(1, 2))
        self.assertEqual(rec['bracket'], ['1/2', '1'])
        self.assertTrue(rec['full_is_upper_benchmark'])

class CertificateExpandTests(unittest.TestCase):
    def test_delayed_worker_retry_accepted_wait_rejected(self):
        rec = delayed_certificate()
        self.assertEqual(rec['trusted_bounds']['done'], '0')
        self.assertEqual(rec['trusted_bounds']['job'], '16')
        self.assertTrue(rec['wait_rejected'])
        self.assertTrue(rec['exhausted_rejected'])

    def test_two_state_still_accepted(self):
        self.assertEqual(check({'pending': {'pending': '3/4', 'done': '1/4'},
                                'done': {'done': 1}}, {'done'},
                               {'pending': 1, 'done': 0}, '1/4')['pending'], '4')

class HorizonTests(unittest.TestCase):
    def test_hardened_and_unbound_transfer(self):
        rec = horizon_transfer()
        self.assertEqual(rec['hardened']['h6'], (0, 0))
        self.assertEqual(rec['hardened']['h8'], (0, 0))
        self.assertTrue(rec['hardened']['transfers'])
        self.assertEqual(rec['unbound_payload']['h8'][0], 1)
        self.assertTrue(rec['unbound_payload']['transfers'])
        self.assertLess(rec['hardened']['state_time_h8'], 100_000)

class ReferenceTests(unittest.TestCase):
    def test_reference_is_below_attacker_and_hardened_is_zero(self):
        rec = reference_process()
        self.assertEqual(F(rec['hardened_reference']), 0)
        self.assertGreater(F(rec['unbound_reference']), 0)
        self.assertLess(F(rec['unbound_reference']), rec['unbound_attacker'])
        self.assertTrue(rec['reference_below_attacker'])

    def test_experiment_lists_model_blockers(self):
        rec = experiment()
        self.assertEqual(rec['changed_dimension'], 'horizon')
        self.assertIn('model attackers vs finite optimum', rec['blocked_without_model_api'])

if __name__ == '__main__':
    unittest.main()
