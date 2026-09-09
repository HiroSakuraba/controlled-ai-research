import tempfile, unittest
from controlled_ai.custody import CHECKER_DIGEST, CustodyService, claim
from controlled_ai.discovery import enumerate_bounded
class CustodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.service=CustodyService('private-suite-seed',b'k'*32,self.tmp.name+'/a.db')
    def tearDown(self): self.service.close(); self.tmp.cleanup()
    def test_canonical_manifest_and_durable_certificate(self):
        e=next(self.service.publish(i) for i in range(24) if self.service.publish(i)['manifest']['family'] != 'composition-3'); m=e['manifest']; program,_=enumerate_bounded(m['examples'],2)
        result=self.service.submit(e,program,claim(m))
        self.assertTrue(result['accepted']); self.assertEqual(m['checker_digest'],CHECKER_DIGEST)
        self.assertTrue(self.service.release(m['task_id'],result['digest'])['released'])
        self.service.close()
        self.service=CustodyService('private-suite-seed',b'k'*32,self.tmp.name+'/a.db')
        self.assertTrue(self.service.release(m['task_id'],result['digest'])['released'])
    def test_modified_task_or_version_is_rejected(self):
        e=self.service.publish(1); forged={'manifest':dict(e['manifest']),'signature':e['signature']}; forged['manifest']['checker_version']='forged'
        self.assertEqual(self.service.submit(forged,(('xor',0),),claim(e['manifest']))['reason'],'invalid_manifest')
    def test_worker_cannot_claim_another_task_with_a_valid_signature(self):
        a,b=self.service.publish(0),self.service.publish(1)
        mixed={'manifest':b['manifest'],'signature':a['signature']}
        self.assertEqual(self.service.submit(mixed,(('xor',0),),claim(b['manifest']))['reason'],'invalid_manifest')
