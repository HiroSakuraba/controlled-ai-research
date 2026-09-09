"""Evidence ancestry, circular support, and structured review.

Unverified origin remains unknown. Creating another node does not create a
verified independent source. Repeated descendants of one root count once.
"""
import json
from dataclasses import asdict
from .model import State
from .outcomes import harms

TESTS = {
    'artifact_corrupt': lambda s: s.artifact != 0,
    'reserve_spent': lambda s: s.reserve < 1,
    'released_wrong': lambda s: s.released not in (-1, 0),
}

class EvidenceStore:
    def __init__(self, trusted_sources=()):
        self.nodes = {}
        self.trusted_sources = frozenset(trusted_sources)

    def put(self, name, source, controller, parents=(), body=''):
        if name in self.nodes:
            raise ValueError('duplicate')
        if any(p not in self.nodes for p in parents):
            raise ValueError('unknown parent')
        circular = any(name in self.ancestry(p) for p in parents)
        self.nodes[name] = {'source': source, 'controller': controller,
                            'parents': tuple(parents), 'body': body, 'circular': circular}
        return self.nodes[name]

    def cite(self, name, parent):
        if name not in self.nodes or parent not in self.nodes:
            raise ValueError('unknown')
        circular = name == parent or name in self.ancestry(parent)
        node = self.nodes[name]
        node['parents'] = node['parents'] + (parent,)
        node['circular'] = node['circular'] or circular
        return circular

    def ancestry(self, name):
        seen = set()
        stack = [name]
        while stack:
            n = stack.pop()
            if n in seen or n not in self.nodes:
                continue
            seen.add(n)
            stack.extend(self.nodes[n]['parents'])
        return seen

    def roots(self, name):
        return {n for n in self.ancestry(name) if not self.nodes[n]['parents']}

    def verified_roots(self, name):
        return {n for n in self.roots(name)
                if self.nodes[n]['source'] in self.trusted_sources}

    def control_roots(self, name):
        return {self.nodes[n]['controller'] for n in self.roots(name)}

class Review:
    def __init__(self, store, budget=2):
        self.store = store
        self.budget = budget
        self.used = 0
        self.proposal = None
        self.evidence = ()
        self.state_digest = None
        self.objections = []
        self.dissent = []

    def freeze(self, proposal, evidence, state):
        self.proposal = proposal
        self.evidence = tuple(evidence)
        self.state_digest = json.dumps(asdict(state), sort_keys=True)
        self.objections = []
        self.dissent = []
        self.used = 0

    def object(self, claim, evidence, consequence, test):
        if self.used >= self.budget:
            return None
        self.used += 1
        rec = {'claim': claim, 'evidence': evidence, 'consequence': consequence,
               'test': test, 'disposition': None}
        self.objections.append(rec)
        return rec

    def dispose(self, index, disposition, reason=''):
        if disposition == 'overruled' and not reason:
            raise ValueError('overruling requires a recorded reason')
        self.objections[index]['disposition'] = disposition
        self.objections[index]['reason'] = reason

    def decide(self, state):
        if self.proposal is None:
            return 'not_frozen'
        if json.dumps(asdict(state), sort_keys=True) != self.state_digest:
            return 'material_change'
        blocked = []
        for rec in self.objections:
            if rec['disposition'] == 'overruled':
                self.dissent.append(rec)
                continue
            if TESTS[rec['test']](state):
                rec['disposition'] = 'sustained'
                blocked.append(rec)
            elif rec['disposition'] is None:
                rec['disposition'] = 'unresolved'
                blocked.append(rec)
        if blocked:
            return 'blocked'
        if harms(state):
            return 'independent_harm'
        return 'authorize'

def experiment():
    store = EvidenceStore(('heldout-evaluator',))
    store.put('eval', 'heldout-evaluator', 'trusted', body='12-bit total function')
    store.put('cite-a', 'heldout-evaluator', 'trusted', parents=('eval',))
    store.put('cite-b', 'heldout-evaluator', 'trusted', parents=('eval',))
    store.put('claim', 'derived', 'actor', parents=('cite-a', 'cite-b'))
    store.put('rumor', 'unverified', 'actor')
    store.put('launder', 'derived', 'actor', parents=('rumor',))
    store.put('loop-a', 'paper', 'actor')
    store.put('loop-b', 'paper', 'actor', parents=('loop-a',))
    circular = store.cite('loop-a', 'loop-b')
    shared = {'verified_roots': sorted(store.verified_roots('claim')),
              'root_count': len(store.verified_roots('claim')),
              'laundered_verified': sorted(store.verified_roots('launder')),
              'circular': circular,
              'control_roots': sorted(store.control_roots('claim'))}
    review = Review(store, budget=2)
    honest = State(artifact=0, approved=0)
    review.freeze('release artifact 0', ('claim',), honest)
    review.object('looks unusual', 'claim', 'false block', 'artifact_corrupt')
    review.dispose(0, 'dismissed', 'state is independently checked')
    honest_decision = review.decide(honest)
    mutated = State(artifact=1, approved=0)
    review.freeze('release artifact 1', ('claim',), mutated)
    review.object('corrupt payload', 'eval', 'incorrect_release', 'artifact_corrupt')
    minority = review.decide(mutated)
    review.dispose(0, 'overruled', 'independent test is inapplicable to this proposal')
    overruled = review.decide(mutated)
    dissent_kept = len(review.dissent) > 0
    review.freeze('release', ('claim',), honest)
    changed = review.decide(State(artifact=1, approved=0))
    review.freeze('release', ('claim',), mutated)
    review.object('first', 'eval', 'incorrect_release', 'artifact_corrupt')
    exhausted = review.object('second', 'eval', 'incorrect_release', 'artifact_corrupt')
    third = review.object('third', 'eval', 'incorrect_release', 'artifact_corrupt')
    return {'shared_source': shared, 'honest_authorize': honest_decision,
            'minority_blocks': minority, 'overruled_with_dissent': overruled,
            'dissent_kept': dissent_kept,
            'material_change': changed, 'budget_rejects_third': third is None,
            'second_recorded': exhausted is not None}
