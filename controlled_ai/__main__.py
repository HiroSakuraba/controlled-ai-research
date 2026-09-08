import json
import platform
import time
from dataclasses import replace
from datetime import datetime, timezone
from .model import State, Rules
from .solver import solve
from .certificates import check

def main():
    started = time.perf_counter()
    cases = {'hardened': (State(), Rules()),
             'unbound_payload': (State(), Rules(bind_payload=False)),
             'replay_allowed': (State(), Rules(prevent_replay=False)),
             'reserve_unprotected': (State(), Rules(protect_reserve=False)),
             'delayed_effect_after_revocation': (State(revoked=True, pending=True), Rules(cancel_pending=False))}
    results = {name: solve(state, rules) for name, (state, rules) in cases.items()}
    results['progress_certificate'] = check({'pending': {'pending': '3/4', 'done': '1/4'},
                                            'done': {'done': 1}}, {'done'},
                                           {'pending': 1, 'done': 0}, '1/4')
    print(json.dumps({'generated_utc': datetime.now(timezone.utc).isoformat(),
                      'scope': 'deterministic finite model; no empirical model evaluation',
                      'results': results, 'usage': {
                          'experiment_wall_seconds': round(time.perf_counter() - started, 6),
                          'python': platform.python_version(), 'model_api_calls': 0,
                          'chatgpt_tokens': None, 'chatgpt_allowance_remaining': None,
                          'note': 'ChatGPT account usage is not exposed; runtime covers this command only.'}}, indent=2))

if __name__ == '__main__':
    main()
