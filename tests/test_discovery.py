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
            fn = by_id[task_id]['fn']
            for x in (0, 1, 7, 31, 128, 4095):
                self.assertEqual(interpret(prog, x)[0], fn(x))

    def test_checker_rejects_example_only_fit(self):
        task = next(t for t in catalog() if t['id'] == 'pub-xor-1')
        claimed = contract(task)
        rec = verify(task, (('and', 15),), claimed)
        self.assertFalse(rec['accepted'])
        self.assertEqual(rec['reason'], 'incorrect')
        rec = verify(task, (('xor', 1),), claimed)
        self.assertTrue(rec['accepted'])
        self.assertEqual(rec['evals'], DOMAIN)

    def test_weaker_misses_held_out_two_op_families(self):
        held = next(t for t in catalog() if t['split'] == 'heldout')
        prog, _ = enumerate_bounded(held['examples'], 1)
        self.assertIsNone(prog)
        prog, _ = enumerate_bounded(held['examples'], 2)
        self.assertIsNotNone(prog)
        rec = verify(held, prog, contract(held))
        self.assertTrue(rec['accepted'])

    def test_symbolic_fits_single_op_only(self):
        pub = next(t for t in catalog() if t['id'] == 'pub-xor-1')
        prog, _ = symbolic_fit(pub['examples'])
        self.assertTrue(verify(pub, prog, contract(pub))['accepted'])
        held = next(t for t in catalog() if t['id'] == 'hold-xor-and')
        prog, _ = symbolic_fit(held['examples'])
        self.assertIsNone(prog)

    def test_gateway_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as d:
            report = experiment(d + '/disc', b'k' * 32)
        weaker = report['generators']['weaker']
        stronger = report['generators']['stronger']
        self.assertEqual(weaker['verified_public'], weaker['public_tasks'])
        self.assertEqual(weaker['verified_heldout'], 0)
        self.assertEqual(stronger['verified_public'], stronger['public_tasks'])
        self.assertEqual(stronger['verified_heldout'], stronger['heldout_tasks'])
        self.assertGreater(stronger['verified_heldout'], weaker['verified_heldout'])
        neg = report['negative_controls']
        self.assertEqual(neg['invalid_syntax'], 'invalid_syntax')
        self.assertEqual(neg['weakened_statement'], 'statement_mismatch')
        self.assertEqual(neg['incorrect'], 'incorrect')
        self.assertEqual(neg['mismatched_release'], 'denied')
        self.assertTrue(neg['accepted_equivalent'])
        self.assertTrue(neg['checked_release'])
        self.assertEqual(neg['step_limit'], 'step_limit')

    def test_unchecked_digest_has_no_release_path(self):
        task = next(t for t in catalog() if t['id'] == 'pub-xor-1')
        with tempfile.TemporaryDirectory() as d:
            gate = Gateway(d + '/g.db', b'k' * 32)
            with self.assertRaises(PermitError):
                gate.release('abc')
            rec = gate.submit(task, [('bad',)], contract(task), verify)
            self.assertFalse(rec['accepted'])
            with self.assertRaises(PermitError):
                gate.release('abc')
            gate.close()

if __name__ == '__main__':
    unittest.main()
