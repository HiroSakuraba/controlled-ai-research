import tempfile
import unittest
from dataclasses import asdict
from controlled_ai.model import State, Rules, transition
from controlled_ai.outcomes import harms
from controlled_ai.permits import PermitError, PermitStore
from controlled_ai.executor import Executor, Crash, payload_id, state_id
from controlled_ai.issuer import PermitIssuer

class ExecutorTests(unittest.TestCase):
    def consequential(self, action, **kwargs):
        return self.ex.step(action, token=PermitIssuer(self.key).issue(self.ex, action, destination=kwargs.get('destination', 'default')), **kwargs)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path, self.key = self.tmp.name + '/exec.db', b'k' * 32
        self.ex = Executor(self.path, self.key)

    def tearDown(self):
        self.ex.close()
        self.tmp.cleanup()

    def test_honest_release_matches_model(self):
        model = State()
        for action in ('approve', 'release'):
            model = transition(model, action, Rules())
            self.consequential(action) if action in ('release', 'queue') else self.ex.step(action)
        self.assertEqual(asdict(model), asdict(self.ex.state))
        self.assertFalse(harms(self.ex.state))
        self.assertEqual(len(self.ex.effects()), 1)

    def test_consequential_action_requires_permit(self):
        self.ex.step('approve')
        with self.assertRaises(PermitError):
            self.ex.step('release')

    def test_payload_and_destination_and_state_bindings(self):
        self.ex.step('approve')
        token = PermitIssuer(self.key).issue(self.ex, 'release')
        with self.assertRaises(PermitError):
            self.ex.step('release', token=token, destination='other')
        self.ex.step('spend')
        with self.assertRaises(PermitError):
            self.ex.step('release', token=token)

    def test_expired_permit(self):
        self.ex.step('approve')
        token = PermitIssuer(self.key).issue(self.ex, 'release', ttl=1)
        self.ex.step('approve')
        with self.assertRaises(PermitError):
            self.ex.step('release', token=token)

    def test_policy_change_invalidates_permit(self):
        self.ex.step('approve')
        token = PermitIssuer(self.key).issue(self.ex, 'release')
        payload = payload_id('release', 0)
        pre = state_id(self.ex.state, self.ex.rules)
        other = state_id(self.ex.state, Rules(bind_payload=False))
        with self.assertRaises(PermitError):
            self.ex.store.consume(token, payload, other, clock=self.ex.clock)
        self.ex.store.consume(token, payload, pre, clock=self.ex.clock)

    def test_crash_then_recover_exactly_once(self):
        self.ex.step('approve')
        with self.assertRaises(Crash):
            self.consequential('release', crash_after='dispatch')
        self.assertEqual(self.ex.state.released, 0)
        self.assertEqual(self.ex.effects(), [])
        self.ex.close()
        self.ex = Executor(self.path, self.key)
        self.assertEqual(self.ex.state.released, 0)
        self.assertEqual(len(self.ex.effects()), 1)
        self.ex.recover()
        self.assertEqual(len(self.ex.effects()), 1)
        self.ex.step('release')
        self.assertEqual(len(self.ex.effects()), 1)

    def test_restart_cannot_replay_nonce(self):
        self.ex.step('approve')
        token = PermitIssuer(self.key).issue(self.ex, 'release')
        payload = payload_id('release', 0)
        pre = state_id(self.ex.state, self.ex.rules)
        clock = self.ex.clock
        self.ex.step('release', token=token)
        self.ex.close()
        store = PermitStore(self.path, self.key)
        with self.assertRaises(PermitError):
            store.consume(token, payload, pre, clock=clock)
        store.close()
        self.ex = Executor(self.path, self.key)

    def test_queue_permit_and_revocation(self):
        path = self.tmp.name + '/queue.db'
        ex = Executor(path, self.key, rules=Rules(bind_payload=False))
        ex.step('approve')
        ex.step('queue', token=PermitIssuer(self.key).issue(ex, 'queue'))
        self.assertTrue(ex.state.pending)
        self.assertEqual(len(ex.effects()), 1)
        ex.step('revoke')
        self.assertFalse(ex.state.pending)
        ex.step('tick')
        self.assertFalse(harms(ex.state))
        ex.close()

if __name__ == '__main__':
    unittest.main()
