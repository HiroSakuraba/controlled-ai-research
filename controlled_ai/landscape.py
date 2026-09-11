"""Offline finite-horizon response map, including the specified monitor.

Existential reachability is not model propensity or attractor stability.
"""
import json
from dataclasses import asdict
from .adapters import RuleMonitor
from .benchmarks import suite
from .live import ARMS, HONEST_TRACES, arm_config
from .model import ACTIONS, transition
from .outcomes import harms
from .solver import solve


def effective_step(state, action, rules, channels):
    review, _ = RuleMonitor(channels).decide(state, action)
    return transition(state, action, rules) if review['decision'] == 'allow' else state


def bounded_outcomes(initial, rules, channels=(), horizon=6):
    if type(horizon) is not int or not 0 <= horizon <= 8:
        raise ValueError('horizon must be an integer from 0 through 8')
    frontier = {initial: ()}
    harmful = None
    useful = None
    count = 0
    pending_at_boundary = False
    for depth in range(horizon + 1):
        following = {}
        for state, path in frontier.items():
            count += 1
            if count > 100000:
                raise RuntimeError('state-time ceiling exceeded')
            if harms(state):
                if harmful is None:
                    harmful = path
                continue  # Same termination rule as the episode runner.
            if state.released == 0 and useful is None:
                useful = path
            if depth == horizon:
                pending_at_boundary |= state.pending
            else:
                for action in ACTIONS:
                    nxt = effective_step(state, action, rules, channels)
                    following.setdefault(nxt, path + (action,))
        frontier = following
    return {'completed_harm_reachable': harmful is not None,
            'completed_harm_witness': list(harmful) if harmful is not None else None,
            'useful_without_harm_reachable': useful is not None,
            'useful_witness': list(useful) if useful is not None else None,
            'unresolved_pending_at_horizon': pending_at_boundary,
            'state_time_pairs': count}


def scripted_outcome(initial, rules, channels, actions, horizon):
    state = initial
    for action in actions[:horizon]:
        state = effective_step(state, action, rules, channels)
        if harms(state):
            break
    return {'completed_harm': bool(harms(state)),
            'useful_without_harm': state.released == 0 and not harms(state),
            'pending': state.pending}


def build_landscape():
    rows = []
    for fixture in suite('perturbation-map-v1', 4):
        for arm in ARMS:
            rules, channels = arm_config(arm, fixture['rules'])
            for horizon in range(1, 7):
                raw = solve(fixture['state'], rules, horizon)
                effective = bounded_outcomes(fixture['state'], rules, channels, horizon)
                rows.append({'family': fixture['family'], 'arm': arm, 'horizon': horizon,
                             'initial_state': asdict(fixture['state']), 'rules': asdict(rules),
                             'monitor_channels': list(channels),
                             'rules_only_harm_lower': raw['harm_lower'],
                             'rules_only_harm_upper': raw['harm_upper'],
                             **effective,
                             'honest_script': scripted_outcome(fixture['state'], rules, channels,
                                                              HONEST_TRACES[fixture['family']], horizon),
                             'adversary_script': scripted_outcome(fixture['state'], rules, channels,
                                                                 fixture['actions'], horizon),
                             'model_harm': None, 'model_observations': 0})
    return {'claim': 'Finite offline response map. No model calls, propensity estimates, or attractor claim.',
            'scope': 'Four fixture families, four arms, horizons 1..6; fully observed closed action grammar.',
            'distinctions': ['Rules-only upper bounds include pending effects at truncation.',
                             'Completed harm reachability includes the specified rule monitor.',
                             'Useful-without-harm reachability is a prefix witness, not eventual completion.',
                             'Existence of a trace is separate from the outcome of a fixed script.',
                             'A horizon sweep is not a continuous control-parameter or hysteresis experiment.'],
            'rows': rows}


if __name__ == '__main__':
    print(json.dumps(build_landscape(), indent=2, sort_keys=True))
