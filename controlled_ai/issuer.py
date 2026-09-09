"""Trusted permit issuer interface, separate from the executor action API.

The fixture uses HMAC, so issuer and executor still share a verification secret.
A deployment should replace this with a remote signer or public-key verifier.
"""
from .permits import PermitStore
class PermitIssuer:
    def __init__(self, key): self.key = key
    def issue(self, executor, action, destination='default', ttl=8):
        from .executor import payload_id, state_id
        payload = payload_id(action, executor.state.artifact, destination)
        store = PermitStore(':memory:', self.key)
        try: return store.issue(payload, state_id(executor.state, executor.rules), executor.clock + ttl)
        finally: store.close()
