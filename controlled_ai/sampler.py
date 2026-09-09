"""Finite-menu sampler with a shared remaining-amplification budget.

Menus are complete executable choices. The controller draws; the ranking model
cannot resample, refuse the draw, or extend the reference menu. Arithmetic is
exact rationals. A0 is the remaining amplification A, with B = ln A0.
"""
import json
import math
import random
import sqlite3
import tempfile
from fractions import Fraction as F
from .certificates import rational

class SamplerError(ValueError):
    pass

def masses(n):
    if n < 1:
        raise ValueError('empty menu')
    return tuple(F(1, n) for _ in range(n))

def filter_normalize(p, allowed):
    p = [rational(x) if on else F(0) for x, on in zip(p, allowed)]
    z = sum(p)
    if z == 0:
        return None
    return tuple(x / z for x in p)

def quantile(p, scores, q):
    q = rational(q)
    p = tuple(rational(x) for x in p)
    if not 0 < q <= 1 or any(x < 0 for x in p) or sum(p) != 1:
        raise SamplerError('invalid masses or q')
    if len(scores) != len(p):
        raise SamplerError('score length')
    order = sorted(range(len(p)), key=lambda i: (-scores[i], i))
    w = [F(0)] * len(p)
    retained = q
    for i in order:
        take = p[i] if p[i] < retained else retained
        w[i] = take
        retained -= take
        if retained == 0:
            break
    if retained != 0:
        raise SamplerError('could not allocate q')
    Q = tuple(x / q for x in w)
    if any(Q[i] > p[i] / q for i in range(len(p))):
        raise SamplerError('pointwise bound')
    return tuple(w), Q

def expect(dist, cost):
    return sum(rational(p) * cost[i] for i, p in enumerate(dist))

def spend(A, q):
    A, q = rational(A), rational(q)
    if q < 1 / A or q > 1:
        raise SamplerError('q outside remaining budget')
    nxt = A * q
    if nxt < 1:
        raise SamplerError('A would fall below 1')
    return nxt

def draw(Q, rng):
    den = 1
    for q in Q:
        den = den * q.denominator // math.gcd(den, q.denominator)
    weights = [int(q * den) for q in Q]
    r, acc = rng.randrange(sum(weights)), 0
    for i, w in enumerate(weights):
        acc += w
        if r < acc:
            return i
    raise SamplerError('draw')

def audit_n(p_upper=1e-4, alpha=0.05):
    return math.ceil(math.log(alpha) / math.log(1 - p_upper))

class Sampler:
    def __init__(self, path, A0=10, seed=0):
        self.A0 = rational(A0)
        self.A = self.A0
        self.rng = random.Random(seed)
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS event '
                        '(step INTEGER PRIMARY KEY, menu TEXT NOT NULL, q TEXT NOT NULL, '
                        'A TEXT NOT NULL, idx INTEGER NOT NULL, choice TEXT NOT NULL)')
        self.db.commit()
        self.step = 0
        row = self.db.execute('SELECT step, A FROM event ORDER BY step DESC LIMIT 1').fetchone()
        if row:
            self.step, self.A = row[0] + 1, rational(row[1])

    def close(self):
        self.db.close()

    def last(self):
        return self.db.execute('SELECT step, idx, choice, q, A FROM event ORDER BY step').fetchall()

    def decide(self, choices, p, scores, q, allowed=None, crash=False):
        if allowed is not None:
            p = filter_normalize(p, allowed)
            if p is None:
                raise SamplerError('stop')
        q = rational(q)
        if scores is None or len(scores) != len(choices):
            q, scores = F(1), tuple(range(len(choices)))
        _, Q = quantile(p, scores, q)
        self.A = spend(self.A, q)
        idx = draw(Q, self.rng)
        blob = json.dumps(list(choices), separators=(',', ':'))
        with self.db:
            self.db.execute('INSERT INTO event VALUES (?, ?, ?, ?, ?, ?)',
                            (self.step, blob, str(q), str(self.A), idx, json.dumps(choices[idx])))
        if crash:
            raise SamplerError('crash')
        choice = choices[idx]
        self.step += 1
        return choice, Q

    def replay(self, step):
        row = self.db.execute('SELECT idx, choice FROM event WHERE step=?', (step,)).fetchone()
        if not row:
            raise SamplerError('missing event')
        return row[0], json.loads(row[1])

    def retry(self):
        raise SamplerError('free retry forbidden')

    def refuse(self):
        raise SamplerError('refusal is not a free retry')

    def insert(self, _choice):
        raise SamplerError('model cannot extend the reference menu')

    def resample(self, _keep):
        raise SamplerError('post-selection filtering forbidden')

def experiment():
    n, q, K = 100, F(1, 10), 10
    p, cost = masses(n), (0,) * (n - 1) + (1,)
    _, Q = quantile(p, (0,) * (n - 1) + (1,), q)
    eq, ep = expect(Q, cost), expect(p, cost)
    unconstrained = F(1) / ep
    p10 = masses(10)
    _, Q10 = quantile(p10, tuple(range(10, 0, -1)), F(1, 10))
    first_ratio = Q10[0] / p10[0]
    useful, harm, p4 = (1, 1, 0, 0), (0, 0, 0, 1), masses(4)
    _, Qh = quantile(p4, (3, 2, 1, 0), F(1, 2))
    attacks = {}
    s = Sampler(':memory:', A0=10, seed=0)
    for name, call in (('retry', s.retry), ('refuse', s.refuse),
                       ('insert', lambda: s.insert('extra')),
                       ('resample', lambda: s.resample((1, 0)))):
        try:
            call()
            attacks[name] = 'allowed'
        except SamplerError as e:
            attacks[name] = str(e)
    s.close()
    with tempfile.TemporaryDirectory() as d:
        a = Sampler(d + '/s.db', A0=10, seed=1)
        try:
            a.decide(tuple(range(10)), p10, tuple(range(10, 0, -1)), F(1, 10), crash=True)
        except SamplerError:
            pass
        recorded = a.last()[0][1]
        a.close()
        b = Sampler(d + '/s.db', A0=10, seed=99)
        idx, _ = b.replay(0)
        recovered = {'same_index': idx == recorded, 'A': str(b.A), 'draws': len(b.last())}
        b.close()
    illegal = filter_normalize(masses(3), (True, True, False))
    return {
        'one_release': {'n': n, 'reference_harm': str(ep), 'quantile_harm': str(eq),
                        'quantile_bound': str(ep / q), 'unconstrained_ratio': str(unconstrained),
                        'claimed_K': K, 'claimed_K_covers_unconstrained': unconstrained <= K,
                        'quantile_respects_K': eq <= ep * K},
        'shared_budget': {'independent_two_step_ratio': str(first_ratio ** 2),
                          'shared_A0': '10', 'shared_two_step_ratio': str(first_ratio),
                          'independent_exceeds_A0': first_ratio ** 2 > 10},
        'usefulness': {'reference_useful': str(expect(p4, useful)),
                       'quantile_useful': str(expect(Qh, useful)),
                       'quantile_harm': str(expect(Qh, harm)),
                       'bound': str(expect(p4, harm) / F(1, 2))},
        'filtered_menu': [str(x) for x in illegal],
        'attacks': attacks,
        'recovery': recovered,
        'audit_zero_event_n_for_1e-4': audit_n(),
        'plan_n': 29956,
    }
