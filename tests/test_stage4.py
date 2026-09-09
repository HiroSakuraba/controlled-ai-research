import unittest
from controlled_ai.model import State, Rules
from controlled_ai.monitor import ALL, comparison, exhaustion, _run
from controlled_ai.provenance import EvidenceStore, experiment as provenance_experiment
from controlled_ai.takeover import experiment as takeover_experiment

class MonitorTests(unittest.TestCase):
    def test_honest_release_survives_full_monitor(self):
        rec = _run(ALL, 'deny', State(), Rules(), ('approve', 'release'))
        self.assertEqual((rec['harm'], rec['useful']), (0, 1))
        self.assertFalse(any(e[0] == 'flag' for e in rec['events']))

    def test_each_channel_is_complementary(self):
        rows = comparison()['attacks']
        for name, row in rows.items():
            self.assertEqual(row['full_monitor_harm'], 0, name)
            self.assertEqual(row['drop_channel_harm'], 1, name)
            self.assertEqual(row['no_monitor_harm'], 1, name)
            self.assertTrue(row['complementary'], name)

    def test_edit_recovers_useful_release(self):
        rec = comparison()['edit_unbound']
        self.assertEqual((rec['harm'], rec['useful']), (0, 1))

    def test_audit_denies_corrupt_release(self):
        rec = comparison()['audit_unbound']
        self.assertEqual((rec['harm'], rec['useful']), (0, 0))

    def test_overbroad_blocks_honest_work(self):
        rec = comparison()['overbroad_blocks_honest']
        self.assertEqual(rec['useful'], 0)

    def test_monitor_timeout_does_not_authorize(self):
        rec = comparison()['monitor_timeout']
        self.assertEqual(rec['harm'], 0)
        self.assertTrue(any(e[0] == 'monitor_timeout' for e in rec['events']))

class ExhaustionTests(unittest.TestCase):
    def test_cap_holds_and_uncapped_attack_succeeds(self):
        rec = exhaustion()
        self.assertTrue(rec['actor_flood_capped']['enforcement'])
        self.assertEqual(rec['actor_flood_capped']['harm'], 0)
        self.assertEqual(rec['actor_flood_uncapped']['harm'], 1)
        self.assertEqual(rec['padded_honest']['useful'], 1)

    def test_checker_budget_caps_expensive_work(self):
        rec = exhaustion()
        self.assertEqual(rec['checker_honest'], 'ok')
        self.assertEqual(rec['checker_attack'], 'capped')
        self.assertIn('checker', rec['checker_attack_capped'])
        self.assertLess(rec['checker_honest_steps'], rec['checker_attack_steps'])

class ProvenanceTests(unittest.TestCase):
    def test_shared_root_counted_once_and_unverified_stays_unknown(self):
        rec = provenance_experiment()['shared_source']
        self.assertEqual(rec['root_count'], 1)
        self.assertEqual(rec['verified_roots'], ['eval'])
        self.assertEqual(rec['laundered_verified'], [])
        self.assertTrue(rec['circular'])

    def test_review_objections_and_material_change(self):
        rec = provenance_experiment()
        self.assertEqual(rec['honest_authorize'], 'authorize')
        self.assertEqual(rec['minority_blocks'], 'blocked')
        self.assertEqual(rec['overruled_with_dissent'], 'authorize')
        self.assertTrue(rec['dissent_kept'])
        self.assertEqual(rec['material_change'], 'material_change')
        self.assertTrue(rec['budget_rejects_third'])

    def test_store_rejects_unknown_parent(self):
        store = EvidenceStore()
        with self.assertRaises(ValueError):
            store.put('x', 's', 'c', parents=('missing',))

class TakeoverTests(unittest.TestCase):
    def test_independent_replacement_completes_and_rejects_actor_token(self):
        rec = takeover_experiment()
        self.assertEqual(rec['ordinary']['useful'], 1)
        self.assertTrue(rec['ordinary']['primary_revoked'])
        self.assertTrue(rec['credentials']['independent_rejects_actor_token'])
        self.assertTrue(rec['credentials']['shared_key_accepts_actor_token'])

    def test_stale_export_and_pending_and_shared_db(self):
        rec = takeover_experiment()
        self.assertEqual(rec['stale_export']['trust_export_useful'], 0)
        self.assertEqual(rec['stale_export']['live_copy_useful'], 1)
        self.assertTrue(rec['pending']['primary_pending_after_revoke'])
        self.assertTrue(rec['pending']['stale_copy_misses_pending'])
        self.assertTrue(rec['pending']['live_copy_cancelled'])
        self.assertTrue(rec['shared_db']['approved_lost'])
        self.assertFalse(rec['unavailable']['can_take_over'])
        self.assertEqual(rec['cleanup_certificate']['pending'], '4')

if __name__ == '__main__':
    unittest.main()
