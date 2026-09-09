"""Signed monotonic handoff records.

HmacSigner is a fixture implementation. The Signer interface is deliberately
small so a deployment can use an external public-key signer/verifier instead.
"""
import hashlib,hmac,json,sqlite3
class HandoffError(ValueError): pass
class HmacSigner:
    def __init__(self,key): self.key=key
    def sign(self,body): return hmac.new(self.key,body.encode(),hashlib.sha256).hexdigest()
    def verify(self,body,signature): return hmac.compare_digest(self.sign(body),signature)
def canonical(data): return json.dumps(data,sort_keys=True,separators=(',',':'))
class HandoffAuthority:
    def __init__(self,path,signer):
        self.signer,self.db=signer,sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS imports (source TEXT PRIMARY KEY, epoch INTEGER NOT NULL, body TEXT NOT NULL)'); self.db.commit()
    def issue(self,source,epoch,export):
        body=canonical({'source':source,'epoch':epoch,'export':export})
        return {'body':body,'signature':self.signer.sign(body)}
    def accept(self,record):
        if set(record)!={'body','signature'} or not self.signer.verify(record['body'],record['signature']): raise HandoffError('invalid signature')
        data=json.loads(record['body']); source,epoch=data['source'],data['epoch']
        row=self.db.execute('SELECT epoch FROM imports WHERE source=?',(source,)).fetchone()
        if row and epoch<=row[0]: raise HandoffError('stale or replayed epoch')
        with self.db:self.db.execute('INSERT OR REPLACE INTO imports VALUES (?,?,?)',(source,epoch,record['body']))
        return data['export']
    def close(self): self.db.close()
