import itertools
import tempfile
import unittest
from dataclasses import replace
from controlled_ai.model import State, Rules, ACTIONS, transition
from controlled_ai.outcomes import harms, terminal_bounds, witness
from controlled_ai.solver import solve
from controlled_ai.permits import PermitStore, PermitError
from controlled_ai.certificates import check

class FiniteTests(unittest.TestCase):
    def test_hardened(self):
        r = solve()
        self.assertEqual((r['harm_lower'], r['harm_upper']), (0, 0))
    def test_ablations_and_witnesses(self):
        for flag in ('bind_payload', 'prevent_replay', 'protect_reserve'):
            rules = replace(Rules(), **{flag: False})
            result = solve(rules=rules)
            self.assertEqual(result['harm_lower'], 1)
            state = State()
            for action in result['witness']:
                state = transition(state, action, rules)
            self.assertTrue(harms(state))
    def test_exhaustive_sequence_crosscheck(self):
        rules = Rules(bind_payload=False)
        for horizon in range(4):
            outcomes = []
            for actions in itertools.product(ACTIONS, repeat=horizon):
                state = State()
                hit = False
                for action in actions:
                    state = transition(state, action, rules)
                    hit |= bool(harms(state))
                outcomes.append(1 if hit else terminal_bounds(state)[0])
            self.assertEqual(solve(rules=rules, horizon=horizon)['harm_lower'], max(outcomes))
    def test_delayed_effect_and_truncation(self):
        state = State(revoked=True, pending=True)
        self.assertEqual(terminal_bounds(state), (0, 1))
        self.assertTrue(harms(transition(state, 'tick', Rules())))
        self.assertEqual(solve(state, horizon=0)['harm_upper'], 1)
    def test_revocation_cancels(self):
        s = transition(State(pending=True), 'revoke', Rules())
        self.assertFalse(transition(s, 'tick', Rules()).pending)
        self.assertFalse(harms(s))
    def test_honest_release(self):
        s = transition(transition(State(), 'approve', Rules()), 'release', Rules())
        self.assertEqual(s.released, 0)
        self.assertFalse(harms(s))
    def test_ground_truth_witness(self):
        self.assertEqual(witness(1), 2)
        self.assertIsNone(witness(0))
    def test_ceiling(self):
        with self.assertRaises(RuntimeError):
            solve(ceiling=1)

class PermitTests(unittest.TestCase):
    def test_bindings_tampering_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path, key = d + '/permits.db', b'k' * 32
            store = PermitStore(path, key)
            token = store.issue('artifact-sha:abc', 'state:1')
            for payload, state in [('artifact-sha:evil', 'state:1'), ('artifact-sha:abc', 'state:2')]:
                with self.assertRaises(PermitError):
                    store.consume(token, payload, state)
            with self.assertRaises(PermitError):
                store.consume({**token, 'credential_id': 'replacement'}, 'artifact-sha:abc', 'state:1')
            with self.assertRaises(PermitError):
                store.consume({**token, 'body': token['body'].replace('abc', 'bad')}, 'artifact-sha:bad', 'state:1')
            store.consume(token, 'artifact-sha:abc', 'state:1')
            store.close()
            store = PermitStore(path, key)
            with self.assertRaises(PermitError):
                store.consume(token, 'artifact-sha:abc', 'state:1')
            store.close()

class CertificateTests(unittest.TestCase):
    def test_exact_bound(self):
        self.assertEqual(check({'a': {'a': '3/4', 'b': '1/4'}, 'b': {'b': 1}},
                               {'b'}, {'a': 1, 'b': 0}, '1/4')['a'], '4')
    def test_reject_stalling(self):
        with self.assertRaises(ValueError):
            check({'a': {'a': 1}, 'b': {'b': 1}}, {'b'}, {'a': 1, 'b': 0}, '1/4')
    def test_reject_invalid_kernels(self):
        for row in ({'z': 1}, {'a': '1/2'}, {'a': 2, 'b': -1}, {'a': 1.0}):
            with self.assertRaises(ValueError):
                check({'a': row, 'b': {'b': 1}}, {'b'}, {'a': 1, 'b': 0}, 1)

if __name__ == '__main__':
    unittest.main()
