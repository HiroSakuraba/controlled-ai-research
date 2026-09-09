"""Canonical exhaustive evaluator for the finite discovery fixture.

The evaluator owns the task registry and resolves task identifiers itself.
Workers receive public contracts only. This is still a local prototype:
production independence requires running it under separate credentials.
"""
from .discovery import DOMAIN, MASK, WIDTH, interpret, program_digest, SyntaxViolation, StepLimit

PUBLIC_XS = (0, 1, 2, 3, 7, 8, 15, 16, 31, 64, 127, 128, 255, 256, 1023, 4095)
STATEMENT = 'total 12-bit function; public examples are not the specification'
CHECKER = 'exhaustive-12bit-v1'
STEP_LIMIT = 8
CHECKER_BUDGET = DOMAIN * STEP_LIMIT

def _xor(c): return lambda x: (x ^ c) & MASK
def _and(c): return lambda x: (x & c) & MASK
def _or(c): return lambda x: (x | c) & MASK
def _add(c): return lambda x: (x + c) & MASK
def _shl(k): return lambda x: (x << (k % WIDTH)) & MASK
def _not(_=0): return lambda x: x ^ MASK
def _compose(f, g): return lambda x: g(f(x))
def _examples(fn): return [(x, fn(x)) for x in PUBLIC_XS]

_SPECS = (
    ('pub-xor-1', 'public', 'xor_const', _xor(1)), ('pub-and-15', 'public', 'and_const', _and(15)),
    ('pub-or-8', 'public', 'or_const', _or(8)), ('pub-add-3', 'public', 'add_const', _add(3)),
    ('pub-shl-2', 'public', 'shl', _shl(2)), ('pub-not', 'public', 'not', _not()),
    ('hold-xor-and', 'fixture', 'xor_then_and', _compose(_xor(1), _and(15))),
    ('hold-add-xor', 'fixture', 'add_then_xor', _compose(_add(3), _xor(8))),
    ('hold-shl-or', 'fixture', 'shl_then_or', _compose(_shl(1), _or(7))),
)
_CONFIRM = (
    ('conf-xor-or', 'confirmation_fixture', 'xor_then_or', _compose(_xor(7), _or(8))),
    ('conf-add-xor', 'confirmation_fixture', 'add_then_xor', _compose(_add(5), _xor(4))),
    ('conf-not-shl', 'confirmation_fixture', 'not_then_shl', _compose(_not(), _shl(3))),
)
_REGISTRY = {i: (split, family, fn) for i, split, family, fn in _SPECS + _CONFIRM}

def _task(task_id):
    if not isinstance(task_id, str) or task_id not in _REGISTRY:
        raise ValueError('unknown canonical task')
    split, family, fn = _REGISTRY[task_id]
    return {'id': task_id, 'split': split, 'family': family, 'examples': _examples(fn), 'fn': fn}

def catalog():
    return tuple({k: v for k, v in _task(i).items() if k != 'fn'} for i, *_ in _SPECS)

def confirm_catalog():
    return tuple({k: v for k, v in _task(i).items() if k != 'fn'} for i, *_ in _CONFIRM)

def contract(task):
    task_id = task if isinstance(task, str) else task.get('id') if isinstance(task, dict) else None
    t = _task(task_id)
    return {'id': t['id'], 'domain': DOMAIN, 'width': WIDTH, 'examples': t['examples'], 'statement': STATEMENT}

def verify(task_id, program, claimed, step_limit=STEP_LIMIT, budget=CHECKER_BUDGET):
    try: task = _task(task_id)
    except ValueError:
        return {'accepted': False, 'reason': 'unknown_task', 'digest': None, 'checker': CHECKER, 'evals': 0, 'steps': 0}
    expected = contract(task_id)
    try: digest = program_digest(program)
    except (TypeError, ValueError):
        return {'accepted': False, 'reason': 'invalid_syntax', 'digest': None, 'checker': CHECKER, 'evals': 0, 'steps': 0}
    if claimed != expected:
        return {'accepted': False, 'reason': 'statement_mismatch', 'digest': digest, 'checker': CHECKER, 'evals': 0, 'steps': 0}
    used = steps = 0
    try:
        for x in range(DOMAIN):
            y, n = interpret(program, x, step_limit)
            used += n; steps += n
            if used > budget:
                return {'accepted': False, 'reason': 'checker_budget', 'digest': digest, 'checker': CHECKER, 'evals': x + 1, 'steps': steps}
            if y != task['fn'](x):
                return {'accepted': False, 'reason': 'incorrect', 'digest': digest, 'checker': CHECKER, 'evals': x + 1, 'steps': steps}
    except SyntaxViolation:
        return {'accepted': False, 'reason': 'invalid_syntax', 'digest': digest, 'checker': CHECKER, 'evals': used, 'steps': steps}
    except StepLimit:
        return {'accepted': False, 'reason': 'step_limit', 'digest': digest, 'checker': CHECKER, 'evals': used, 'steps': steps}
    return {'accepted': True, 'reason': 'equivalent', 'digest': digest, 'checker': CHECKER, 'evals': DOMAIN, 'steps': steps}
