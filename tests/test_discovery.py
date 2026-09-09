import tempfile
import unittest
from controlled_ai.discovery import interpret, enumerate_bounded, symbolic_fit, experiment, Gateway
from controlled_ai.evaluator import catalog, contract, verify, DOMAIN
from controlled_ai.permits import PermitError

class DiscoveryTests(unittest.TestCase):
    def test_interpreter_matches_held_out_functions(self):
        programs = {
            'pub-xor-1': (('xor', 1),),
            'pub-and-15': (('and', 15),),
            'pub-or-8': (('or', 8),),
            'pub-add-3': (('add', 3),),
            'pub-shl-2': (('shl', 2),),
            'pub-not': (('not', 0),),
            'hold-xor-and': (('xor', 1), ('and', 15)),
            'hold-add-xor': (('add', 3), ('xor', 8)),
            'hold-shl-or': (('shl', 1), ('or', 7)),
        }
        by_id = {t['id']: t for t in catalog()}
        for task_id, prog in programs.items():
            rec = verify(task_id, prog, contract(task_id))
            self.assertTrue(rec['accepted'], task_id)

    def test_checker_rejects_example_only_fit(self):
        task = next(t for t in catalog() if t['id'] == 'pub-xor-1')
        claimed = contract(task)
        rec = verify(task['id'], (('and', 15),), claimed)
        self.assertFalse(rec['accepted'])
        self.assertEqual(rec['reason'], 'incorrect')
        rec = verify(task['id'], (('xor', 1),), claimed)
        self.assertTrue(rec['accepted'])
        self.assertEqual(rec['evals'], DOMAIN)

    def test_weaker_misses_held_out_two_op_families(self):
        held = next(t for t in catalog() if t['split'] == 'fixture')
        prog, _ = enumerate_bounded(held['examples'], 1)
        self.assertIsNone(prog)
        prog, _ = enumerate_bounded(held['examples'], 2)
        self.assertIsNotNone(prog)
        rec = verify(held['id'], prog, contract(held['id']))
        self.assertTrue(rec['accepted'])

    def test_symbolic_fits_single_op_only(self):
        pub = next(t for t in catalog() if t['id'] == 'pub-xor-1')
        prog, _ = symbolic_fit(pub['examples'])
        self.assertTrue(verify(pub['id'], prog, contract(pub['id']))['accepted'])
        held = next(t for t in catalog() if t['id'] == 'hold-xor-and')
        prog, _ = symbolic_fit(held['examples'])
        self.assertIsNone(prog)

    def test_gateway_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as d:
            report = experiment(d + '/disc', b'k' * 32)
        weaker = report['generators']['weaker']
        stronger = report['generators']['stronger']
        self.assertEqual(weaker['verified_public'], weaker['public_tasks'])
        self.assertEqual(weaker['verified_fixture'], 0)
        self.assertEqual(stronger['verified_public'], stronger['public_tasks'])
        self.assertEqual(stronger['verified_fixture'], stronger['fixture_tasks'])
        self.assertGreater(stronger['verified_fixture'], weaker['verified_fixture'])
        neg = report['negative_controls']
        self.assertEqual(neg['invalid_syntax'], 'invalid_syntax')
        self.assertEqual(neg['weakened_statement'], 'statement_mismatch')
        self.assertEqual(neg['incorrect'], 'incorrect')
        self.assertEqual(neg['mismatched_release'], 'denied')
        self.assertTrue(neg['accepted_equivalent'])
        self.assertTrue(neg['checked_release'])
        self.assertEqual(neg['step_limit'], 'step_limit')

    def test_canonical_registry_rejects_forged_task(self):
        forged = {'id': 'forged', 'examples': [(0, 0)]}
        self.assertEqual(verify(forged['id'], (('xor', 0),), contract('pub-xor-1'))['reason'], 'unknown_task')

    def test_accepted_digest_survives_gateway_restart(self):
        task = next(t for t in catalog() if t['id'] == 'pub-xor-1')
        with tempfile.TemporaryDirectory() as d:
            path = d + '/g.db'
            gate = Gateway(path, b'k' * 32)
            rec = gate.submit(task['id'], (('xor', 1),), contract(task['id']))
            gate.close()
            reopened = Gateway(path, b'k' * 32)
            self.assertEqual(reopened.release(task['id'], rec['digest']), rec['digest'])
            reopened.close()

    def test_unchecked_digest_has_no_release_path(self):
        task = next(t for t in catalog() if t['id'] == 'pub-xor-1')
        with tempfile.TemporaryDirectory() as d:
            gate = Gateway(d + '/g.db', b'k' * 32)
            with self.assertRaises(PermitError):
                gate.release(task['id'], 'abc')
            rec = gate.submit(task['id'], [('bad',)], contract(task['id']))
            self.assertFalse(rec['accepted'])
            with self.assertRaises(PermitError):
                gate.release(task['id'], 'abc')
            gate.close()

if __name__ == '__main__':
    unittest.main()
