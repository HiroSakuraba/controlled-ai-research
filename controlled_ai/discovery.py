"""Finite program synthesis: public contracts, enumerative generators, ledger.

Generators see examples and the frozen statement. They do not import the
held-out evaluator. Release is allowed only for a digest the checker accepted.
"""
import hashlib
import json
from itertools import product
from .permits import PermitStore, PermitError

WIDTH = 12
MASK = (1 << WIDTH) - 1
DOMAIN = 1 << WIDTH
OPS = ('and', 'or', 'xor', 'add', 'shl', 'not')
IMMS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 15, 16, 32, 63, 64, 128, 255, 256, 512, 1023, 2048, 4095)

class SyntaxViolation(ValueError):
    pass

class StepLimit(RuntimeError):
    pass

def program_digest(program):
    body = json.dumps(list(program), separators=(',', ':'))
    return hashlib.sha256(body.encode()).hexdigest()

def interpret(program, x, step_limit=8):
    if not isinstance(program, (list, tuple)) or not program:
        raise SyntaxViolation('empty or malformed program')
    acc = x & MASK
    steps = 0
    for item in program:
        steps += 1
        if steps > step_limit:
            raise StepLimit
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise SyntaxViolation('malformed instruction')
        op, k = item
        if op not in OPS or type(k) is not int:
            raise SyntaxViolation('unknown operation')
        if op == 'and':
            acc = acc & (k & MASK)
        elif op == 'or':
            acc = acc | (k & MASK)
        elif op == 'xor':
            acc = acc ^ (k & MASK)
        elif op == 'add':
            acc = (acc + (k & MASK)) & MASK
        elif op == 'shl':
            acc = (acc << (k % WIDTH)) & MASK
        else:
            acc = acc ^ MASK
    return acc, steps

def _matches(program, examples):
    try:
        return all(interpret(program, x)[0] == y for x, y in examples)
    except (SyntaxViolation, StepLimit):
        return False

def enumerate_bounded(examples, bound):
    tried = 0
    for length in range(1, bound + 1):
        for prog in product(*((tuple((op, k) for op in OPS for k in IMMS),) * length)):
            tried += 1
            if _matches(prog, examples):
                return prog, tried
    return None, tried

def symbolic_fit(examples):
    tried = 0
    x0, y0 = examples[0]
    proposals = [('xor', (x0 ^ y0) & MASK), ('and', y0), ('or', y0),
                 ('add', (y0 - x0) & MASK), ('not', 0)]
    for k in range(WIDTH):
        proposals.append(('shl', k))
    for op, k in proposals:
        tried += 1
        prog = ((op, k),)
        if _matches(prog, examples):
            return prog, tried
    return None, tried

GENERATORS = (
    ('weaker', lambda ex: enumerate_bounded(ex, 1)),
    ('symbolic', symbolic_fit),
    ('stronger', lambda ex: enumerate_bounded(ex, 2)),
)

class Gateway:
    """Submit-check-release: only the exact accepted digest can be released."""

    def __init__(self, path, key):
        self.store = PermitStore(path, key)
        self.checked = None
        self.released = None
        self.ledger = []

    def close(self):
        self.store.close()

    def submit(self, task, program, claimed, verify):
        result = verify(task, program, claimed)
        rec = {'task': task['id'], 'split': task['split'], 'family': task['family'],
               **result, 'program': None if not result['accepted'] else [list(s) for s in program]}
        self.ledger.append(rec)
        if result['accepted']:
            self.checked = result['digest']
        return rec

    def release(self, digest, destination='default'):
        if self.checked is None or digest != self.checked:
            raise PermitError('unchecked artifact')
        payload = json.dumps({'digest': digest, 'destination': destination},
                             sort_keys=True, separators=(',', ':'))
        token = self.store.issue(payload, 'checked:' + digest)
        self.store.consume(token, payload, 'checked:' + digest)
        self.released = digest
        return digest

def experiment(path, key):
    from .evaluator import catalog, contract, verify
    tasks = catalog()
    summary = {'width': WIDTH, 'domain': DOMAIN, 'checker': 'exhaustive-12bit-v1',
               'generators': {}, 'negative_controls': {}}
    for name, gen in GENERATORS:
        rows = []
        for task in tasks:
            prog, tried = gen(task['examples'])
            claimed = contract(task)
            gate = Gateway(path + '.' + name + '.' + task['id'], key)
            if prog is None:
                rec = {'task': task['id'], 'split': task['split'], 'family': task['family'],
                       'accepted': False, 'reason': 'no_candidate', 'digest': None,
                       'checker': None, 'evals': 0, 'steps': 0, 'tried': tried, 'released': False}
            else:
                rec = gate.submit(task, prog, claimed, verify)
                rec['tried'] = tried
                rec['released'] = False
                if rec['accepted']:
                    gate.release(rec['digest'])
                    rec['released'] = True
            gate.close()
            rows.append(rec)
        accepted = [r for r in rows if r['accepted']]
        summary['generators'][name] = {
            'tried_total': sum(r['tried'] for r in rows),
            'checker_evals': sum(r['evals'] for r in rows),
            'verified_public': sum(1 for r in accepted if r['split'] == 'public'),
            'verified_heldout': sum(1 for r in accepted if r['split'] == 'heldout'),
            'public_tasks': sum(1 for r in rows if r['split'] == 'public'),
            'heldout_tasks': sum(1 for r in rows if r['split'] == 'heldout'),
            'released': sum(1 for r in rows if r['released']),
            'rows': rows,
        }
    # Negative controls use a public xor task and the stronger generator's checker.
    task = next(t for t in tasks if t['id'] == 'pub-xor-1')
    claimed = contract(task)
    gate = Gateway(path + '.negatives', key)
    controls = {}
    controls['invalid_syntax'] = gate.submit(task, [('nope', 0)], claimed, verify)['reason']
    controls['weakened_statement'] = gate.submit(
        task, (('xor', 1),), {**claimed, 'statement': 'examples only'}, verify)['reason']
    controls['incorrect'] = gate.submit(task, (('and', 15),), claimed, verify)['reason']
    ok = gate.submit(task, (('xor', 1),), claimed, verify)
    controls['accepted_equivalent'] = ok['accepted']
    try:
        gate.release('0' * 64)
        controls['mismatched_release'] = 'allowed'
    except PermitError:
        controls['mismatched_release'] = 'denied'
    gate.release(ok['digest'])
    controls['checked_release'] = gate.released == ok['digest']
    long_prog = tuple(('xor', 0) for _ in range(9))
    controls['step_limit'] = gate.submit(task, long_prog, claimed, verify)['reason']
    gate.close()
    summary['negative_controls'] = controls
    return summary
