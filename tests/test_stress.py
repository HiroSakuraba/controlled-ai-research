import random, tempfile, unittest
from dataclasses import asdict
from controlled_ai.executor import Executor, PermitError
from controlled_ai.issuer import PermitIssuer
from controlled_ai.model import ACTIONS, Rules, State, transition

class ExecutorStressTests(unittest.TestCase):
    def test_executor_matches_transition_model_on_random_sequences(self):
        rng=random.Random(20260910)
        for case in range(40):
            rules=Rules(bind_payload=rng.choice((True,False)), prevent_replay=rng.choice((True,False)), cancel_pending=rng.choice((True,False)), protect_reserve=rng.choice((True,False)))
            with tempfile.TemporaryDirectory() as d:
                key=b'k'*32; ex=Executor(d+'/e.db',key,rules=rules); expected=State()
                for _ in range(12):
                    action=rng.choice(ACTIONS); expected=transition(expected,action,rules)
                    if action in ('release','queue') and transition(ex.state,action,rules) != ex.state:
                        ex.step(action,token=PermitIssuer(key).issue(ex,action))
                    else: ex.step(action)
                    self.assertEqual(asdict(ex.state),asdict(expected),(case,action,rules))
                ex.close()
    def test_policy_is_durable_and_signed_export_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            key=b'k'*32; p=d+'/e.db'; ex=Executor(p,key,rules=Rules(bind_payload=False)); ex.step('approve')
            record=ex.export(); self.assertEqual(Executor.verify_export(record,key)['state']['approved'],0)
            with self.assertRaises(PermitError): Executor(p,key,rules=Rules())
            forged=dict(record); forged['body']=forged['body'].replace('"approved":0','"approved":1')
            with self.assertRaises(PermitError): Executor.verify_export(forged,key)
            ex.close()
