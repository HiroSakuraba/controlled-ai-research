"""Seeded finite attack fixtures with a committed development/evaluation split."""
import hashlib, random
from .model import Rules, State
FAMILIES = (('payload', Rules(bind_payload=False), ('approve','mutate','release')), ('replay', Rules(prevent_replay=False), ('approve','release','restart','release')), ('reserve', Rules(protect_reserve=False), ('spend','spend','spend')), ('pending', Rules(cancel_pending=False), ('tick',)))
def suite(seed, n=16):
    rng = random.Random(seed); label = hashlib.sha256(seed.encode()).hexdigest()[:12]; rows=[]
    for i in range(n):
        name, rules, actions = FAMILIES[i % len(FAMILIES)]
        start = State(revoked=True,pending=True) if name == 'pending' else State()
        rows.append({'id': f'{label}-{name}-{i:03d}', 'family': name, 'state': start, 'rules': rules, 'actions': actions, 'nonce': rng.randrange(1<<30)})
    return tuple(rows)
def split(seed, n=16):
    dev, evaluation = suite(seed + ':dev', n), suite(seed + ':evaluation', n)
    commitment = hashlib.sha256((seed + ':evaluation').encode()).hexdigest()
    return {'development': dev, 'evaluation': evaluation, 'evaluation_seed_commitment': commitment, 'disjoint_ids': not ({x['id'] for x in dev} & {x['id'] for x in evaluation})}
