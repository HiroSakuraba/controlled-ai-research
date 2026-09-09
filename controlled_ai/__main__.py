import json
import platform
import tempfile
import time
from datetime import datetime, timezone
from .model import State, Rules
from .solver import solve
from .certificates import check
from .executor import Executor, Crash
from .discovery import experiment as discovery_experiment
from .monitor import comparison as monitor_comparison, exhaustion as exhaustion_experiment
from .provenance import experiment as provenance_experiment
from .takeover import experiment as takeover_experiment
from .sampler import experiment as sampler_experiment
from .compare import experiment as compare_experiment
from .expand import experiment as expand_experiment

def executor_recovery():
    with tempfile.TemporaryDirectory() as d:
        path, key = d + '/exec.db', b'k' * 32
        ex = Executor(path, key)
        ex.step('approve')
        try:
            ex.step('release', token=ex.authorize('release'), crash_after='dispatch')
        except Crash:
            pass
        before = len(ex.effects())
        released_after_crash = ex.state.released
        ex.close()
        ex = Executor(path, key)
        recovered = {'released': ex.state.released, 'effects_before_recover_close': before,
                     'effects': len(ex.effects()), 'released_after_crash': released_after_crash}
        ex.step('release')
        recovered['effects_after_replay'] = len(ex.effects())
        recovered['consumed'] = ex.state.consumed
        ex.close()
        return recovered

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
    results['executor_recovery'] = executor_recovery()
    with tempfile.TemporaryDirectory() as d:
        results['discovery'] = discovery_experiment(d + '/disc', b'k' * 32)
    results['monitor'] = monitor_comparison()
    results['exhaustion'] = exhaustion_experiment()
    results['provenance'] = provenance_experiment()
    results['takeover'] = takeover_experiment()
    results['sampler'] = sampler_experiment()
    results['comparison'] = compare_experiment()
    results['expansion'] = expand_experiment()
    print(json.dumps({'generated_utc': datetime.now(timezone.utc).isoformat(),
                      'scope': 'deterministic finite model; no empirical model evaluation',
                      'results': results, 'usage': {
                          'experiment_wall_seconds': round(time.perf_counter() - started, 6),
                          'python': platform.python_version(), 'model_api_calls': 0,
                          'chatgpt_tokens': None, 'chatgpt_allowance_remaining': None,
                          'note': 'ChatGPT account usage is not exposed; runtime covers this command only.'}}, indent=2))

if __name__ == '__main__':
    main()
