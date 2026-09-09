"""Finite program synthesis and a durable submit-check-release ledger.

Generators see public examples. Gateway resolves task identifiers through the
canonical evaluator; callers cannot supply either the evaluator or its target
function. Separate-process custody remains required outside this fixture.
"""
import hashlib
import json
import sqlite3
from itertools import product
from .permits import PermitStore, PermitError

WIDTH = 12
MASK = (1 << WIDTH) - 1
DOMAIN = 1 << WIDTH
OPS = ('and', 'or', 'xor', 'add', 'shl', 'not')
IMMS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 15, 16, 32, 63, 64, 128, 255, 256, 512, 1023, 2048, 4095)
class SyntaxViolation(ValueError): pass
class StepLimit(RuntimeError): pass

def program_digest(program):
    return hashlib.sha256(json.dumps(list(program), separators=(',', ':')).encode()).hexdigest()

def interpret(program, x, step_limit=8):
    if not isinstance(program, (list, tuple)) or not program: raise SyntaxViolation('empty or malformed program')
    acc, steps = x & MASK, 0
    for item in program:
        steps += 1
        if steps > step_limit: raise StepLimit
        if not isinstance(item, (list, tuple)) or len(item) != 2: raise SyntaxViolation('malformed instruction')
        op, k = item
        if op not in OPS or type(k) is not int: raise SyntaxViolation('unknown operation')
        if op == 'and': acc &= k & MASK
        elif op == 'or': acc |= k & MASK
        elif op == 'xor': acc ^= k & MASK
        elif op == 'add': acc = (acc + (k & MASK)) & MASK
        elif op == 'shl': acc = (acc << (k % WIDTH)) & MASK
        else: acc ^= MASK
    return acc, steps

def _matches(program, examples):
    try: return all(interpret(program, x)[0] == y for x, y in examples)
    except (SyntaxViolation, StepLimit): return False

def enumerate_bounded(examples, bound):
    tried = 0; instructions = tuple((op, k) for op in OPS for k in IMMS)
    for length in range(1, bound + 1):
        for prog in product(instructions, repeat=length):
            tried += 1
            if _matches(prog, examples): return prog, tried
    return None, tried

def symbolic_fit(examples):
    tried = 0; x0, y0 = examples[0]
    proposals = [('xor', (x0 ^ y0) & MASK), ('and', y0), ('or', y0), ('add', (y0 - x0) & MASK), ('not', 0)]
    proposals.extend(('shl', k) for k in range(WIDTH))
    for op, k in proposals:
        tried += 1; prog = ((op, k),)
        if _matches(prog, examples): return prog, tried
    return None, tried

GENERATORS = (('weaker', lambda ex: enumerate_bounded(ex, 1)), ('symbolic', symbolic_fit), ('stronger', lambda ex: enumerate_bounded(ex, 2)))

class Gateway:
    """Durable acceptance ledger keyed by canonical task identifier and digest."""
    def __init__(self, path, key):
        self.store = PermitStore(path, key); self.db = self.store.db
        self.db.execute('CREATE TABLE IF NOT EXISTS accepted (task TEXT NOT NULL, digest TEXT NOT NULL, checker TEXT NOT NULL, program TEXT NOT NULL, PRIMARY KEY(task, digest))')
        self.db.execute('CREATE TABLE IF NOT EXISTS ledger (n INTEGER PRIMARY KEY, task TEXT NOT NULL, digest TEXT, accepted INTEGER NOT NULL, record TEXT NOT NULL)')
        self.db.commit(); self.released = None
    def close(self): self.store.close()
    def submit(self, task_id, program, claimed):
        from .evaluator import verify
        rec = verify(task_id, program, claimed)
        record = {'task': task_id, **rec, 'program': None if not rec['accepted'] else [list(s) for s in program]}
        with self.db:
            self.db.execute('INSERT INTO ledger(task,digest,accepted,record) VALUES (?,?,?,?)', (task_id, rec['digest'], int(rec['accepted']), json.dumps(record, sort_keys=True)))
            if rec['accepted']:
                self.db.execute('INSERT OR REPLACE INTO accepted VALUES (?,?,?,?)', (task_id, rec['digest'], rec['checker'], json.dumps(record['program'])))
        return record
    def release(self, task_id, digest, destination='default'):
        row = self.db.execute('SELECT checker FROM accepted WHERE task=? AND digest=?', (task_id, digest)).fetchone()
        if row is None: raise PermitError('unchecked artifact')
        payload = json.dumps({'task': task_id, 'digest': digest, 'destination': destination}, sort_keys=True, separators=(',', ':'))
        token = self.store.issue(payload, 'checked:' + task_id + ':' + digest)
        self.store.consume(token, payload, 'checked:' + task_id + ':' + digest)
        self.released = digest
        return digest

def experiment(path, key):
    from .evaluator import catalog, contract
    tasks = catalog(); summary = {'width': WIDTH, 'domain': DOMAIN, 'checker': 'exhaustive-12bit-v1', 'generators': {}, 'negative_controls': {}}
    for name, gen in GENERATORS:
        rows = []
        for task in tasks:
            prog, tried = gen(task['examples']); gate = Gateway(path + '.' + name + '.' + task['id'], key)
            if prog is None: rec = {'task': task['id'], 'split': task['split'], 'family': task['family'], 'accepted': False, 'reason': 'no_candidate', 'digest': None, 'checker': None, 'evals': 0, 'steps': 0, 'tried': tried, 'released': False}
            else:
                rec = gate.submit(task['id'], prog, contract(task['id'])); rec.update({'split': task['split'], 'family': task['family'], 'tried': tried, 'released': False})
                if rec['accepted']: gate.release(task['id'], rec['digest']); rec['released'] = True
            gate.close(); rows.append(rec)
        accepted = [r for r in rows if r['accepted']]
        summary['generators'][name] = {'tried_total': sum(r['tried'] for r in rows), 'checker_evals': sum(r['evals'] for r in rows), 'verified_public': sum(r['split'] == 'public' for r in accepted), 'verified_fixture': sum(r['split'] == 'fixture' for r in accepted), 'public_tasks': sum(r['split'] == 'public' for r in rows), 'fixture_tasks': sum(r['split'] == 'fixture' for r in rows), 'released': sum(r['released'] for r in rows), 'rows': rows}
    task = next(t for t in tasks if t['id'] == 'pub-xor-1'); claimed = contract(task['id']); gate = Gateway(path + '.negatives', key); controls = {}
    controls['invalid_syntax'] = gate.submit(task['id'], [('nope', 0)], claimed)['reason']
    controls['weakened_statement'] = gate.submit(task['id'], (('xor', 1),), {**claimed, 'statement': 'examples only'})['reason']
    controls['incorrect'] = gate.submit(task['id'], (('and', 15),), claimed)['reason']
    ok = gate.submit(task['id'], (('xor', 1),), claimed); controls['accepted_equivalent'] = ok['accepted']
    try: gate.release(task['id'], '0' * 64); controls['mismatched_release'] = 'allowed'
    except PermitError: controls['mismatched_release'] = 'denied'
    gate.release(task['id'], ok['digest']); controls['checked_release'] = gate.released == ok['digest']
    controls['step_limit'] = gate.submit(task['id'], tuple(('xor', 0) for _ in range(9)), claimed)['reason']; gate.close(); summary['negative_controls'] = controls
    return summary
