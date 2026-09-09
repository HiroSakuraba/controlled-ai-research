"""Stage 7 expansions that do not need a model API.

Horizon is the one changed dimension in the original game. The observation
bracket is a manufactured hidden-bit game: empty observations, exact rationals.
Delayed-worker certificates add retry. Model attackers remain out of scope.
"""
from functools import lru_cache
from fractions import Fraction as F
from .model import State, Rules, ACTIONS, transition
from .outcomes import harms, terminal_bounds
from .solver import solve
from .certificates import check

def setup_trigger():
    rules = Rules(bind_payload=False)
    fresh = State()
    one = {a: int(bool(harms(transition(fresh, a, rules)))) for a in ('mutate', 'release')}
    armed = transition(transition(fresh, 'approve', rules), 'mutate', rules)
    seq = transition(armed, 'release', rules)
    tiny = {'fresh_setup': 'armed', 'fresh_trigger': 'fresh', 'armed_trigger': 'harm'}
    return {'one_step_mutate': one['mutate'], 'one_step_release': one['release'],
            'setup_trigger_harms': int(bool(harms(seq))),
            'tiny': tiny,
            'appendix_f_case1': one['mutate'] == 0 and one['release'] == 0 and bool(harms(seq))}

def _v_full(h, t):
    if t <= 0:
        return F(0)
    fire = F(1) if h else F(0)
    arm = _v_full(1 - h, t - 1)
    wait = _v_full(h, t - 1)
    return max(fire, arm, wait)

def _open_loop(h0, actions):
    h, harm = h0, F(0)
    for a in actions:
        if a == 'fire':
            return F(1) if h else F(0)
        if a == 'arm':
            h = 1 - h
    return harm

def partial_obs(horizon=2):
    full = (_v_full(0, horizon) + _v_full(1, horizon)) / 2
    sequences = []
    for a in ('arm', 'fire', 'wait'):
        for b in ('arm', 'fire', 'wait'):
            sequences.append((a, b)[:horizon])
    limited = max((_open_loop(0, seq) + _open_loop(1, seq)) / 2 for seq in sequences)
    return {'horizon': horizon, 'full_info': str(full), 'limited_open_loop': str(limited),
            'bracket': [str(limited), str(full)],
            'gap': str(full - limited),
            'full_is_upper_benchmark': full >= limited,
            'empty_observation_exact_limited': True}

def delayed_certificate():
    trusted = {'job': {'job': '1/2', 'cleanup': '1/2'},
               'cleanup': {'cleanup': '1/2', 'done': '1/4', 'retry': '1/4'},
               'retry': {'cleanup': 1},
               'done': {'done': 1}}
    potential = {'job': 2, 'cleanup': '3/4', 'retry': 1, 'done': 0}
    accepted = check(trusted, {'done'}, potential, '1/8')
    wait = {'job': {'job': 1}, 'cleanup': {'cleanup': 1},
            'retry': {'retry': 1}, 'done': {'done': 1}}
    try:
        check(wait, {'done'}, potential, '1/8')
        wait_ok = True
    except ValueError:
        wait_ok = False
    exhausted = {'job': {'job': 1}, 'cleanup': {'cleanup': 1},
                 'retry': {'retry': 1}, 'done': {'done': 1},
                 'exhausted': {'exhausted': 1}}
    try:
        check(exhausted, {'done'}, {**potential, 'exhausted': 0}, '1/8')
        exhausted_ok = True
    except ValueError:
        exhausted_ok = False
    return {'trusted_bounds': accepted, 'wait_rejected': not wait_ok,
            'exhausted_rejected': not exhausted_ok}

def horizon_transfer():
    rows = {}
    for name, rules in (('hardened', Rules()),
                        ('unbound_payload', Rules(bind_payload=False))):
        a = solve(State(), rules, horizon=6)
        b = solve(State(), rules, horizon=8)
        rows[name] = {'h6': (a['harm_lower'], a['harm_upper']),
                      'h8': (b['harm_lower'], b['harm_upper']),
                      'state_time_h8': b['state_time_pairs'],
                      'transfers': (a['harm_lower'], a['harm_upper']) == (b['harm_lower'], b['harm_upper'])}
    return rows

def reference_process(horizon=6):
    n = len(ACTIONS)

    def expected(initial, rules):
        @lru_cache(None)
        def visit(s, rem):
            if harms(s):
                return F(1)
            if rem == 0:
                return F(terminal_bounds(s)[1])
            return sum(visit(transition(s, a, rules), rem - 1) for a in ACTIONS) / n
        return visit(initial, horizon)

    hard = expected(State(), Rules())
    unbound = expected(State(), Rules(bind_payload=False))
    atk = solve(State(), Rules(bind_payload=False), horizon=horizon)
    return {'horizon': horizon, 'hardened_reference': str(hard),
            'unbound_reference': str(unbound),
            'unbound_attacker': atk['harm_lower'],
            'reference_below_attacker': unbound <= atk['harm_lower']}

def experiment():
    return {'changed_dimension': 'horizon',
            'setup_trigger': setup_trigger(),
            'partial_observation': partial_obs(),
            'delayed_certificate': delayed_certificate(),
            'horizon_transfer': horizon_transfer(),
            'reference_process': reference_process(),
            'blocked_without_model_api': (
                'learned monitors', 'model attackers vs finite optimum',
                'priced-call capability comparison', 'training-method expansion',
                'empirical 29956-episode reference audit')}
