import tempfile, unittest
from controlled_ai.custody import CustodyService
from controlled_ai.effects import EffectReceiver
from controlled_ai.executor import Crash, Executor
from controlled_ai.handoff import HandoffAuthority, HandoffError, HmacSigner
from controlled_ai.issuer import PermitIssuer
from controlled_ai.model import Rules
class SeparationTests(unittest.TestCase):
    def test_receiver_deduplicates_crash_recovery_by_nonce(self):
        with tempfile.TemporaryDirectory() as d:
            key=b'k'*32; receiver=EffectReceiver(d+'/receiver.db'); ex=Executor(d+'/executor.db',key,effect_receiver=receiver)
            ex.step('approve')
            with self.assertRaises(Crash): ex.step('release',token=PermitIssuer(key).issue(ex,'release'),crash_after='dispatch')
            ex.close(); ex=Executor(d+'/executor.db',key,effect_receiver=receiver)
            self.assertEqual(receiver.count(),1); ex.recover(); self.assertEqual(receiver.count(),1)
            ex.close(); receiver.close()
    def test_handoff_epoch_rejects_replay_and_bad_signature(self):
        with tempfile.TemporaryDirectory() as d:
            a=HandoffAuthority(d+'/imports.db',HmacSigner(b'k'*32)); r=a.issue('primary',1,{'state':'s'})
            self.assertEqual(a.accept(r),{'state':'s'})
            with self.assertRaises(HandoffError): a.accept(r)
            bad=dict(r); bad['signature']='0'*64
            with self.assertRaises(HandoffError): a.accept(bad)
            a.close()
    def test_seeded_custody_suite_has_multiple_families(self):
        with tempfile.TemporaryDirectory() as d:
            s=CustodyService('private-seed',b'k'*32,d+'/x.db')
            try: self.assertGreater(len({s.publish(i)['manifest']['family'] for i in range(24)}),1)
            finally: s.close()
