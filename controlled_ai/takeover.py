"""Trusted replacement: export, independent credentials, shared-dependency failures.

The replacement must acquire its own credentials, read an export, and continue
without the revoked actor. Shared keys or a shared database can disable both
paths. Stale exports are not authoritative.
"""
import os
import tempfile
from dataclasses import asdict
from .model import State, Rules
from .executor import Executor
from .permits import PermitError
from .certificates import check
from .outcomes import harms

def _dump(ex):
    return {'state': asdict(ex.state), 'clock': ex.clock,
            'effects': [list(row) for row in ex.effects()]}

def _load_state(blob):
    return State(**blob['state'])

def experiment():
    cleanup = check({'pending': {'pending': '3/4', 'done': '1/4'}, 'done': {'done': 1}},
                    {'done'}, {'pending': 1, 'done': 0}, '1/4')
    with tempfile.TemporaryDirectory() as d:
        key_a, key_b = b'a' * 32, b'b' * 32
        # Ordinary takeover with independent credentials.
        p = Executor(d + '/ord.db', key_a)
        p.step('approve')
        live = _dump(p)
        p.step('revoke')
        r = Executor(d + '/ord-r.db', key_b, state=_load_state(live))
        r.step('release', token=r.authorize('release'))
        ordinary = {'useful': int(r.state.released == 0), 'harm': int(bool(harms(r.state))),
                    'primary_revoked': p.state.revoked, 'independent_key': key_a != key_b}
        p.close(); r.close()

        # Independent key rejects an actor token; shared key accepts it.
        p = Executor(d + '/tok.db', key_a)
        p.step('approve')
        token = p.authorize('release')
        pre = _dump(p)
        p.step('revoke')
        indep = Executor(d + '/tok-b.db', key_b, state=_load_state(pre))
        shared = Executor(d + '/tok-s.db', key_a, state=_load_state(pre))
        try:
            indep.step('release', token=token)
            indep_result = 'accepted'
        except PermitError:
            indep_result = 'rejected'
        shared.step('release', token=token)
        keys = {'independent_rejects_actor_token': indep_result == 'rejected',
                'shared_key_accepts_actor_token': shared.state.released == 0,
                'shared_dependency': 'signing key'}
        p.close(); indep.close(); shared.close()

        # Stale export taken before approval; live copy can finish.
        p = Executor(d + '/stale.db', key_a)
        stale = _dump(p)
        p.step('approve')
        live = _dump(p)
        p.step('revoke')
        trust = Executor(d + '/stale-t.db', key_b, state=_load_state(stale))
        trust.step('release')
        fresh = Executor(d + '/stale-f.db', key_b, state=_load_state(live))
        fresh.step('release', token=fresh.authorize('release'))
        stale_case = {'trust_export_useful': int(trust.state.released == 0),
                      'live_copy_useful': int(fresh.state.released == 0),
                      'state_loss': stale['state'] != live['state']}
        p.close(); trust.close(); fresh.close()

        # Delayed pending on live; stale export misses it.
        p = Executor(d + '/pend.db', key_a, rules=Rules(bind_payload=False, cancel_pending=False))
        p.step('approve')
        early = _dump(p)
        p.step('queue', token=p.authorize('queue'))
        live = _dump(p)
        p.step('revoke')
        miss = Executor(d + '/pend-m.db', key_b, state=_load_state(early),
                        rules=Rules(bind_payload=False, cancel_pending=False))
        hit = Executor(d + '/pend-h.db', key_b, state=_load_state(live),
                       rules=Rules(cancel_pending=True))
        hit.step('revoke')
        pending_case = {'primary_pending_after_revoke': p.state.pending,
                        'stale_copy_misses_pending': not miss.state.pending,
                        'live_copy_cancelled': not hit.state.pending}
        p.close(); miss.close(); hit.close()

        # Shared database wipe disables primary and replacement together.
        path = d + '/wipe.db'
        p = Executor(path, key_a)
        p.step('approve')
        p.close()
        os.remove(path)
        wiped = Executor(path, key_b)
        shared_db = {'useful': int(wiped.state.released == 0),
                     'approved_lost': wiped.state.approved == -1,
                     'shared_dependency': 'database file'}
        wiped.close()

        # Missing export fields.
        missing = 'state' not in {}

        # Unavailable replacement capacity: reserve already spent.
        p = Executor(d + '/res.db', key_a, rules=Rules(protect_reserve=False))
        p.step('spend'); p.step('spend'); p.step('spend')
        unavailable = {'reserve': p.state.reserve, 'can_take_over': p.state.reserve >= 1}
        p.close()

        return {'ordinary': ordinary, 'credentials': keys, 'stale_export': stale_case,
                'pending': pending_case, 'shared_db': shared_db,
                'missing_dependencies': missing, 'unavailable': unavailable,
                'cleanup_certificate': cleanup}
