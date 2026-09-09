"""Append-only, HMAC-authenticated episode ledger for local experiments."""
import hashlib, hmac, json, sqlite3
from dataclasses import asdict, is_dataclass

class LedgerError(ValueError): pass

def _json(value):
    if is_dataclass(value): value = asdict(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)

class EpisodeLedger:
    def __init__(self, path, key):
        if not isinstance(key, bytes) or len(key) < 16: raise LedgerError('ledger key must be at least 16 bytes')
        self.key, self.db = key, sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS ledger (n INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, previous TEXT NOT NULL, mac TEXT NOT NULL)')
        self.db.commit()
    def close(self): self.db.close()
    def append(self, kind, payload):
        row = self.db.execute('SELECT n, mac FROM ledger ORDER BY n DESC LIMIT 1').fetchone()
        n, previous = (0, '0' * 64) if row is None else (row[0] + 1, row[1])
        body = _json({'n': n, 'kind': kind, 'payload': payload, 'previous': previous})
        mac = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
        with self.db: self.db.execute('INSERT INTO ledger VALUES (?,?,?,?,?)', (n, kind, _json(payload), previous, mac))
        return mac
    def verify(self):
        previous = '0' * 64
        for n, kind, payload, stored_previous, mac in self.db.execute('SELECT n,kind,payload,previous,mac FROM ledger ORDER BY n'):
            if stored_previous != previous: raise LedgerError('broken chain')
            body = _json({'n': n, 'kind': kind, 'payload': json.loads(payload), 'previous': previous})
            expected = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, mac): raise LedgerError('tampered event')
            previous = mac
        return True
    def events(self): return [(n, kind, json.loads(payload)) for n, kind, payload in self.db.execute('SELECT n,kind,payload FROM ledger ORDER BY n')]
