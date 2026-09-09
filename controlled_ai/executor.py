"""Trusted executor: state-bound permits, dispatch journal, crash recovery.

Consume, the local snapshot, and the dispatch record share one transaction.
A later transaction records the simulated remote effect. A crash between them
resumes the same nonce. The database cannot atomically commit a remote effect.
"""
import hashlib
import hmac
import json
from dataclasses import asdict
from .model import State, Rules, transition
from .permits import PermitStore, PermitError

CONSEQUENTIAL = frozenset(('release', 'queue'))

class Crash(RuntimeError):
    pass

def state_id(state, rules):
    return json.dumps({'state': asdict(state), 'rules': asdict(rules)},
                      sort_keys=True, separators=(',', ':'))

def payload_id(action, artifact, destination='default'):
    return json.dumps({'action': action, 'artifact': artifact, 'destination': destination},
                      sort_keys=True, separators=(',', ':'))

class Executor:
    def __init__(self, path, key, state=None, rules=None, effect_receiver=None):
        self.store = PermitStore(path, key)
        self.effect_receiver = effect_receiver
        self.db = self.store.db
        self.db.execute('CREATE TABLE IF NOT EXISTS snapshot '
                        '(id INTEGER PRIMARY KEY CHECK (id=1), state TEXT NOT NULL, clock INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK (id=1), rules TEXT NOT NULL, digest TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS log '
                        '(nonce TEXT PRIMARY KEY, action TEXT NOT NULL, payload TEXT NOT NULL, '
                        'pre TEXT NOT NULL, status TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS effects '
                        '(nonce TEXT PRIMARY KEY, action TEXT NOT NULL, artifact INTEGER NOT NULL)')
        self.db.commit()
        configured_rules = Rules() if rules is None else rules
        policy = self.db.execute('SELECT rules, digest FROM policy WHERE id=1').fetchone()
        if policy:
            stored = Rules(**json.loads(policy[0]))
            if stored != configured_rules:
                raise PermitError('policy mismatch on restart')
            self.rules, self.policy_digest = stored, policy[1]
        else:
            self.rules = configured_rules
            self.policy_digest = hashlib.sha256(json.dumps(asdict(self.rules), sort_keys=True).encode()).hexdigest()
            self.db.execute('INSERT INTO policy VALUES (1, ?, ?)', (json.dumps(asdict(self.rules), sort_keys=True), self.policy_digest))
            self.db.commit()
        row = self.db.execute('SELECT state, clock FROM snapshot WHERE id=1').fetchone()
        if row:
            self.state = State(**json.loads(row[0]))
            self.clock = row[1]
        else:
            self.state = State() if state is None else state
            self.clock = 0
            self._save()
        self.recover()

    def close(self):
        self.store.close()

    def effects(self):
        return list(self.db.execute('SELECT nonce, action, artifact FROM effects ORDER BY rowid'))

    def _save(self):
        blob = json.dumps(asdict(self.state), sort_keys=True)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO snapshot VALUES (1, ?, ?)', (blob, self.clock))

    def export(self):
        """Return a signed state export for a replacement controller."""
        data = {'state': asdict(self.state), 'clock': self.clock, 'rules': asdict(self.rules),
                'policy_digest': self.policy_digest, 'effects': self.effects(),
                'pending_dispatches': list(self.db.execute("SELECT nonce,action,payload,pre FROM log WHERE status='dispatched'"))}
        body = json.dumps(data, sort_keys=True, separators=(',', ':'))
        mac = hmac.new(self.store.key, body.encode(), hashlib.sha256).hexdigest()
        return {'body': body, 'mac': mac}

    @staticmethod
    def verify_export(record, key):
        if set(record) != {'body', 'mac'}: raise PermitError('malformed export')
        expected = hmac.new(key, record['body'].encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, record['mac']): raise PermitError('invalid export signature')
        data = json.loads(record['body'])
        if hashlib.sha256(json.dumps(data['rules'], sort_keys=True).encode()).hexdigest() != data['policy_digest']:
            raise PermitError('export policy digest')
        return data

    def step(self, action, token=None, destination='default', crash_after=None):
        nxt = transition(self.state, action, self.rules)
        if action not in CONSEQUENTIAL or nxt == self.state:
            self.state = nxt
            self.clock += 1
            self._save()
            return self.state
        payload = payload_id(action, self.state.artifact, destination)
        pre = state_id(self.state, self.rules)
        if token is None:
            raise PermitError('consequential action requires a permit')
        nonce = self._dispatch(token, payload, pre, action)
        if crash_after == 'dispatch':
            raise Crash(nonce)
        self._effect(nonce, action, self.state)
        return self.state

    def recover(self):
        rows = list(self.db.execute("SELECT nonce, action FROM log WHERE status='dispatched'"))
        for nonce, action in rows:
            self._effect(nonce, action, self.state)

    def _dispatch(self, token, payload, pre, action):
        holder = []
        def extra(db, body):
            row = db.execute('SELECT state, clock FROM snapshot WHERE id=1').fetchone()
            live = State(**json.loads(row[0]))
            if state_id(live, self.rules) != pre:
                raise PermitError('state changed before dispatch')
            recomputed = transition(live, action, self.rules)
            if recomputed == live:
                raise PermitError('no longer applicable')
            db.execute('INSERT INTO log VALUES (?, ?, ?, ?, ?)',
                       (body['nonce'], action, payload, pre, 'dispatched'))
            db.execute('INSERT OR REPLACE INTO snapshot VALUES (1, ?, ?)',
                       (json.dumps(asdict(recomputed), sort_keys=True), row[1] + 1))
            holder.append((recomputed, row[1] + 1))
        nonce = self.store.consume(token, payload, pre, clock=self.clock, extra=extra)
        self.state, self.clock = holder[0]
        return nonce

    def _effect(self, nonce, action, state):
        artifact = state.released if action == 'release' else -1
        if self.effect_receiver is not None:
            self.effect_receiver.deliver(nonce, action, artifact)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO effects VALUES (?, ?, ?)',
                            (nonce, action, artifact))
            self.db.execute("UPDATE log SET status='completed' WHERE nonce=?", (nonce,))
