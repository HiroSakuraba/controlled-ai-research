"""Exact deterministic finite-horizon search, with explicit truncation bounds."""
from functools import lru_cache
from .model import ACTIONS, State, Rules, transition
from .outcomes import harms, terminal_bounds

def solve(initial=State(), rules=Rules(), horizon=6, ceiling=100_000):
    if horizon < 0:
        raise ValueError('negative horizon')
    count = 0
    @lru_cache(None)
    def visit(s, remaining):
        nonlocal count
        count += 1
        if count > ceiling:
            raise RuntimeError('state-time ceiling exceeded')
        if harms(s) or remaining == 0:
            lo, hi = terminal_bounds(s)
            return lo, hi, ()
        choices = []
        for action in ACTIONS:
            lo, hi, path = visit(transition(s, action, rules), remaining - 1)
            choices.append((lo, hi, (action,) + path))
        best = max(choices, key=lambda x: (x[0], x[1]))
        return max(x[0] for x in choices), max(x[1] for x in choices), best[2]
    lo, hi, path = visit(initial, horizon)
    return {'harm_lower': lo, 'harm_upper': hi, 'witness': list(path),
            'state_time_pairs': count, 'horizon': horizon}
