"""A separate, durable idempotent effect receiver for the finite prototype."""
import json, sqlite3
class EffectError(ValueError): pass
class EffectReceiver:
    def __init__(self,path):
        self.db=sqlite3.connect(path); self.db.execute('CREATE TABLE IF NOT EXISTS delivered (nonce TEXT PRIMARY KEY, action TEXT NOT NULL, artifact INTEGER NOT NULL, destination TEXT NOT NULL, receipt TEXT NOT NULL)'); self.db.commit()
    def deliver(self,nonce,action,artifact,destination='default'):
        receipt=json.dumps({'nonce':nonce,'action':action,'artifact':artifact,'destination':destination},sort_keys=True,separators=(',',':'))
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO delivered VALUES (?,?,?,?,?)',(nonce,action,artifact,destination,receipt))
        return receipt
    def count(self): return self.db.execute('SELECT COUNT(*) FROM delivered').fetchone()[0]
    def close(self): self.db.close()
