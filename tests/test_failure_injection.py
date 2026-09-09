import concurrent.futures, tempfile, threading, unittest
from controlled_ai.effects import EffectReceiver
from controlled_ai.executor import Executor, PermitError
from controlled_ai.issuer import PermitIssuer
from controlled_ai.permits import PermitStore
from controlled_ai.providers import OpenAIActor, ProviderActor, ProviderConfig, ProviderDisabled
class BadReceiver:
    def deliver(self,*_): return '{"wrong":"receipt"}'
class FailureInjectionTests(unittest.TestCase):
    def test_failed_extra_rolls_back_nonce_consumption(self):
        with tempfile.TemporaryDirectory() as d:
            s=PermitStore(d+'/p.db',b'k'*32); token=s.issue('p','state')
            def fail(_db,_body): raise RuntimeError('injected')
            with self.assertRaises(RuntimeError): s.consume(token,'p','state',extra=fail)
            self.assertIsInstance(s.consume(token,'p','state'),str); s.close()
    def test_receiver_disagreement_leaves_dispatch_for_reconciliation(self):
        with tempfile.TemporaryDirectory() as d:
            key=b'k'*32; ex=Executor(d+'/e.db',key,effect_receiver=BadReceiver()); ex.step('approve')
            with self.assertRaises(PermitError): ex.step('release',token=PermitIssuer(key).issue(ex,'release'))
            self.assertEqual(ex.db.execute("SELECT status FROM log").fetchone()[0],'dispatched'); ex.close()
    def test_same_permit_can_be_consumed_once_under_race(self):
        with tempfile.TemporaryDirectory() as d:
            key=b'k'*32; path=d+'/e.db'; initial=Executor(path,key); initial.step('approve')
            token=PermitIssuer(key).issue(initial,'release'); initial.close()
            barrier=threading.Barrier(2)
            def run(_):
                ex=Executor(path,key)
                try:
                    barrier.wait()
                    ex.step('release',token=token)
                    return 'returned'
                except Exception as error: return type(error).__name__
                finally: ex.close()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(run,range(2)))
            check=Executor(path,key)
            try:
                self.assertEqual(len(check.effects()),1)
                self.assertEqual(check.db.execute('SELECT COUNT(*) FROM used').fetchone()[0],1)
            finally: check.close()
    def test_provider_adapter_is_disabled_without_explicit_switch(self):
        actor=OpenAIActor(ProviderConfig('openai','gpt-5.6-luna','OPENAI_API_KEY','https://api.openai.com/v1/responses','actor-v1'),'x')
        with self.assertRaises(ProviderDisabled): actor.decide({'permitted_actions':['approve']})
