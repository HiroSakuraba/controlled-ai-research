"""HMAC permits and durable single-use consumption for a local demonstration.

The database operation models dispatch. It cannot atomically commit a remote effect.
The signing key belongs to the trusted issuer and is supplied by the caller.
"""
import hashlib
import hmac
import json
import sqlite3
import uuid

class PermitError(ValueError):
    pass

class PermitStore:
    def __init__(self, path, key):
        if len(key) < 32:
            raise ValueError('use at least 32 key bytes')
        self.key = key
        self.db = sqlite3.connect(path)
        self.db.isolation_level = 'IMMEDIATE'
        self.db.execute('CREATE TABLE IF NOT EXISTS used (nonce TEXT PRIMARY KEY)')
        self.db.commit()
        self.db.execute('PRAGMA busy_timeout=5000')

    def close(self):
        self.db.close()

    def issue(self, payload, state, exp=None):
        body = json.dumps({'nonce': uuid.uuid4().hex, 'payload': payload, 'state': state,
                           'exp': exp}, sort_keys=True, separators=(',', ':'))
        return {'body': body, 'mac': hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()}

    def verify(self, token, payload, state, clock=None):
        try:
            if set(token) != {'body', 'mac'}:
                raise PermitError('unexpected token fields')
            expected = hmac.new(self.key, token['body'].encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, token['mac']):
                raise PermitError('invalid signature')
            body = json.loads(token['body'])
            required = {'nonce', 'payload', 'state', 'exp'}
            if set(body) != required or body['payload'] != payload or body['state'] != state:
                raise PermitError('binding mismatch')
            if body['exp'] is not None and clock is not None and clock >= body['exp']:
                raise PermitError('expired')
            return body
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise PermitError('malformed token') from exc

    def consume(self, token, payload, state, clock=None, extra=None):
        body = self.verify(token, payload, state, clock)
        try:
            with self.db:
                self.db.execute('INSERT INTO used VALUES (?)', (body['nonce'],))
                if extra is not None:
                    extra(self.db, body)
        except sqlite3.IntegrityError as exc:
            raise PermitError('already consumed') from exc
        return body['nonce']
