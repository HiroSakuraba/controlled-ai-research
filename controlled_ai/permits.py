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
        self.db.execute('CREATE TABLE IF NOT EXISTS used (nonce TEXT PRIMARY KEY)')
        self.db.commit()

    def close(self):
        self.db.close()

    def issue(self, payload, state):
        body = json.dumps({'nonce': uuid.uuid4().hex, 'payload': payload, 'state': state},
                          sort_keys=True, separators=(',', ':'))
        return {'body': body, 'mac': hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()}

    def consume(self, token, payload, state):
        try:
            if set(token) != {'body', 'mac'}:
                raise PermitError('unexpected token fields')
            expected = hmac.new(self.key, token['body'].encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, token['mac']):
                raise PermitError('invalid signature')
            body = json.loads(token['body'])
            if set(body) != {'nonce', 'payload', 'state'} or body['payload'] != payload or body['state'] != state:
                raise PermitError('binding mismatch')
            with self.db:
                self.db.execute('INSERT INTO used VALUES (?)', (body['nonce'],))
        except sqlite3.IntegrityError as exc:
            raise PermitError('already consumed') from exc
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise PermitError('malformed token') from exc
        return body['nonce']
