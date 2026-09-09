import unittest
from fractions import Fraction as F
from controlled_ai.compare import experiment, frozen_id, FROZEN, DEV, HELD, play, SYSTEMS
from controlled_ai.model import State, Rules

class FreezeTests(unittest.TestCase):
    def test_digest_is_stable_and_sensitive(self):
        a = frozen_id()
        self.assertEqual(len(a), 16)
        self.assertEqual(a, frozen_id(FROZEN))
        other = dict(FROZEN)
        other['A0'] = 11
        self.assertNotEqual(a, frozen_id(other))

class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = experiment()

    def test_untrusted_fails_dev_and_heldout(self):
        m = self.rec['systems']['untrusted']
        self.assertGreater(m['dev']['attack_harm'], 0)
        self.assertGreater(m['heldout']['attack_harm'], 0)
        self.assertFalse(m['heldout']['survives'])

    def test_composition_survives_where_each_alone_misses(self):
        for name in ('combined', 'executor_monitor', 'reference'):
            row = self.rec['systems'][name]
            self.assertTrue(row['dev']['survives'], name)
            self.assertTrue(row['heldout']['survives'], name)
        self.assertFalse(self.rec['systems']['executor']['dev']['survives'])
        self.assertTrue(self.rec['systems']['executor']['heldout']['survives'])
        self.assertTrue(self.rec['systems']['monitor']['dev']['survives'])
        self.assertFalse(self.rec['systems']['monitor']['heldout']['survives'])

    def test_honest_completes_under_frozen_executor(self):
        rec = play({'name': 'executor', 'channels': (), 'harden': True},
                   State(), Rules(), ('approve', 'release'))
        self.assertEqual((rec['harm'], rec['useful']), (0, 1))

    def test_leave_one_out(self):
        loo = self.rec['leave_one_out']
        self.assertFalse(loo['drop_executor']['heldout_survives'])
        self.assertTrue(loo['drop_monitor']['heldout_survives'])
        self.assertTrue(loo['drop_neither']['dev_survives'])
        self.assertTrue(loo['drop_neither']['heldout_survives'])
        self.assertFalse(loo['drop_both']['heldout_survives'])

    def test_heldout_attacks_were_not_the_dev_set(self):
        self.assertEqual({e[0] for e in DEV} & {e[0] for e in HELD}, set())
        self.assertEqual(len(SYSTEMS), 9)

    def test_payload_sampler_bound_and_checker_filter(self):
        rec = self.rec['payload_sampler']
        self.assertTrue(rec['bound_holds_quantile'])
        self.assertTrue(rec['bound_fails_argmax'])
        self.assertEqual(F(rec['checker_filter_harm']), 0)

    def test_discovery_confirm_transfers(self):
        rec = self.rec['discovery_confirm']
        self.assertEqual(rec['stronger'], 3)
        self.assertEqual(rec['weaker'], 0)
        self.assertLess(rec['symbolic'], rec['stronger'])

    def test_findings_record_complementary_misses(self):
        f = self.rec['findings']
        self.assertTrue(f['combined_survives'])
        self.assertTrue(f['executor_misses_preexisting_pending'])
        self.assertTrue(f['monitor_misses_restart_replay'])
        self.assertTrue(f['executor_blocks_restart_replay'])
        self.assertTrue(f['monitor_blocks_preexisting_pending'])
        self.assertTrue(f['composition_improves_on_each_alone'])
        self.assertTrue(f['untrusted_fails'])
        self.assertTrue(f['reference_survives'])

if __name__ == '__main__':
    unittest.main()
