"""Held-out evaluator for finite program synthesis.

Generators receive only the public contract. This module compares a candidate
against the total function on every input in the declared domain.
"""
from .discovery import DOMAIN, MASK, WIDTH, interpret, program_digest, SyntaxViolation, StepLimit

PUBLIC_XS = (0, 1, 2, 3, 7, 8, 15, 16, 31, 64, 127, 128, 255, 256, 1023, 4095)
STATEMENT = 'total 12-bit function; public examples are not the specification'
CHECKER = 'exhaustive-12bit-v1'
STEP_LIMIT = 8
CHECKER_BUDGET = DOMAIN * STEP_LIMIT

def _xor(c):
    return lambda x: (x ^ c) & MASK

def _and(c):
    return lambda x: (x & c) & MASK

def _or(c):
    return lambda x: (x | c) & MASK

def _add(c):
    return lambda x: (x + c) & MASK

def _shl(k):
    return lambda x: (x << (k % WIDTH)) & MASK

def _not(_=0):
    return lambda x: x ^ MASK

def _compose(f, g):
    return lambda x: g(f(x))

# Frozen task generator. Public split is one opcode; held-out split needs two.
_SPECS = (
    ('pub-xor-1', 'public', 'xor_const', _xor(1)),
    ('pub-and-15', 'public', 'and_const', _and(15)),
    ('pub-or-8', 'public', 'or_const', _or(8)),
    ('pub-add-3', 'public', 'add_const', _add(3)),
    ('pub-shl-2', 'public', 'shl', _shl(2)),
    ('pub-not', 'public', 'not', _not()),
    ('hold-xor-and', 'heldout', 'xor_then_and', _compose(_xor(1), _and(15))),
    ('hold-add-xor', 'heldout', 'add_then_xor', _compose(_add(3), _xor(8))),
    ('hold-shl-or', 'heldout', 'shl_then_or', _compose(_shl(1), _or(7))),
)

def _examples(fn):
    return [(x, fn(x)) for x in PUBLIC_XS]

def catalog():
    return tuple({'id': i, 'split': split, 'family': family, 'fn': fn,
                  'examples': _examples(fn)} for i, split, family, fn in _SPECS)

def contract(task):
    return {'id': task['id'], 'domain': DOMAIN, 'width': WIDTH,
            'examples': task['examples'], 'statement': STATEMENT}

def verify(task, program, claimed, step_limit=STEP_LIMIT, budget=CHECKER_BUDGET):
    expected = contract(task)
    digest = None
    try:
        digest = program_digest(program)
    except (TypeError, ValueError):
        return {'accepted': False, 'reason': 'invalid_syntax', 'digest': None,
                'checker': CHECKER, 'evals': 0, 'steps': 0}
    if claimed != expected:
        return {'accepted': False, 'reason': 'statement_mismatch', 'digest': digest,
                'checker': CHECKER, 'evals': 0, 'steps': 0}
    used = 0
    steps = 0
    fn = task['fn']
    try:
        for x in range(DOMAIN):
            y, n = interpret(program, x, step_limit)
            used += n
            steps += n
            if used > budget:
                return {'accepted': False, 'reason': 'checker_budget', 'digest': digest,
                        'checker': CHECKER, 'evals': x + 1, 'steps': steps}
            if y != fn(x):
                return {'accepted': False, 'reason': 'incorrect', 'digest': digest,
                        'checker': CHECKER, 'evals': x + 1, 'steps': steps}
    except SyntaxViolation:
        return {'accepted': False, 'reason': 'invalid_syntax', 'digest': digest,
                'checker': CHECKER, 'evals': used, 'steps': steps}
    except StepLimit:
        return {'accepted': False, 'reason': 'step_limit', 'digest': digest,
                'checker': CHECKER, 'evals': used, 'steps': steps}
    return {'accepted': True, 'reason': 'equivalent', 'digest': digest,
            'checker': CHECKER, 'evals': DOMAIN, 'steps': steps}
