"""Exact checking of a supplied progress certificate against a trusted kernel."""
from fractions import Fraction as F

def rational(value):
    if isinstance(value, bool) or not isinstance(value, (int, str, F)):
        raise ValueError('use integers, fraction strings, or Fraction; no floats')
    return F(value)

def check(kernel, completed, potential, epsilon):
    states = set(kernel)
    completed = set(completed)
    if not states or not completed <= states or set(potential) != states:
        raise ValueError('incomplete state table')
    w = {s: rational(v) for s, v in potential.items()}
    eps = rational(epsilon)
    if eps <= 0 or any(v < 0 for v in w.values()):
        raise ValueError('invalid potential or epsilon')
    for s, row in kernel.items():
        p = {t: rational(v) for t, v in row.items()}
        if not set(p) <= states or any(v < 0 for v in p.values()) or sum(p.values()) != 1:
            raise ValueError('invalid transition distribution')
        if s not in completed and sum(prob * w[t] for t, prob in p.items()) > w[s] - eps:
            raise ValueError('insufficient progress')
    # Every unfinished state is pending; this bounds time to first completion.
    return {s: str(w[s] / eps) if s not in completed else '0' for s in states}
