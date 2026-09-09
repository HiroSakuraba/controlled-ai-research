"""Specified monitors, response policies, and resource ceilings.

Learned monitors and model attackers are out of scope. Channels are explicit
predicates on the fully observed finite state. A monitor timeout withholds;
it does not authorize the action.
"""
from dataclasses import dataclass, replace
from .model import State, Rules, transition
from .outcomes import harms
from .discovery import interpret, StepLimit

CHANNELS = {
    'artifact': lambda s, a: a in ('release', 'queue') and s.artifact != 0,
    'pending': lambda s, a: a == 'tick' and s.pending,
    'replay': lambda s, a: a in ('release', 'queue') and s.consumed,
    'reserve': lambda s, a: a == 'spend' and s.ordinary == 0,
    'overbroad': lambda s, a: a == 'release',
}
ALL = ('artifact', 'pending', 'replay', 'reserve')

@dataclass(frozen=True)
class Limits:
    actor: int = 32
    monitor: int = 32
    checker: int = 256
    review: int = 4
    cleanup: int = 4

class Controller:
    def __init__(self, state=None, rules=None, channels=(), response='deny', limits=None):
        self.state = State() if state is None else state
        self.rules = Rules() if rules is None else rules
        self.channels = tuple(channels)
        self.response = response
        self.limits = Limits() if limits is None else limits
        self.used = {'actor': 0, 'monitor': 0, 'checker': 0, 'review': 0, 'cleanup': 0}
        self.events = []

    def _cap(self, role):
        if self.used[role] >= getattr(self.limits, role):
            self.events.append(('cap', role))
            return True
        self.used[role] += 1
        return False

    def step(self, action):
        if self._cap('actor'):
            return 'capped_actor'
        if self.channels:
            if self._cap('monitor'):
                self.events.append(('monitor_timeout', action))
                return 'monitor_timeout'
            flag = next((name for name in self.channels if CHANNELS[name](self.state, action)), None)
            if flag:
                self.events.append(('flag', flag, action))
                return self._respond(action, flag)
        self.state = transition(self.state, action, self.rules)
        self.events.append(('exec', action))
        return 'executed'

    def _respond(self, action, flag):
        if self.response == 'defer':
            return 'deferred'
        if self.response == 'edit':
            if flag == 'artifact':
                self.state = replace(self.state, artifact=0)
                self.state = transition(self.state, action, self.rules)
                self.events.append(('edit', action))
                return 'edited'
            if flag == 'pending':
                self.state = replace(self.state, pending=False)
                self.events.append(('edit', 'cancel_pending'))
                return 'edited'
            return 'denied'
        if self.response == 'audit':
            if self._cap('review'):
                return 'review_exhausted'
            nxt = transition(self.state, action, self.rules)
            if harms(nxt):
                return 'denied'
            self.state = nxt
            self.events.append(('audit', action))
            return 'audited'
        return 'denied'

    def outcome(self):
        return {'harm': int(bool(harms(self.state))), 'useful': int(self.state.released == 0),
                'pending': self.state.pending, 'used': dict(self.used),
                'events': [list(e) for e in self.events]}

ATTACKS = (
    ('unbound_payload', State(), Rules(bind_payload=False), ('approve', 'mutate', 'release'), 'artifact'),
    ('replay_allowed', State(), Rules(prevent_replay=False), ('approve', 'release', 'release'), 'replay'),
    ('reserve_unprotected', State(), Rules(protect_reserve=False), ('spend', 'spend', 'spend'), 'reserve'),
    ('delayed_effect', State(revoked=True, pending=True), Rules(cancel_pending=False), ('tick',), 'pending'),
)

def _run(channels, response, start, rules, actions, limits=None):
    ctl = Controller(start, rules, channels, response, limits)
    for action in actions:
        ctl.step(action)
    rec = ctl.outcome()
    rec['last'] = ctl.events[-1][0] if ctl.events else None
    return rec

def comparison():
    honest = _run(ALL, 'deny', State(), Rules(), ('approve', 'release'))
    rows = {}
    for name, start, rules, actions, channel in ATTACKS:
        full = _run(ALL, 'deny', start, rules, actions)
        ablated = _run(tuple(c for c in ALL if c != channel), 'deny', start, rules, actions)
        none = _run((), 'deny', start, rules, actions)
        rows[name] = {'channel': channel, 'full_monitor_harm': full['harm'],
                      'drop_channel_harm': ablated['harm'], 'no_monitor_harm': none['harm'],
                      'complementary': full['harm'] == 0 and ablated['harm'] == 1}
    edit = _run(ALL, 'edit', State(), Rules(bind_payload=False), ('approve', 'mutate', 'release'))
    audit = _run(ALL, 'audit', State(), Rules(bind_payload=False), ('approve', 'mutate', 'release'))
    overbroad = _run(('overbroad',), 'deny', State(), Rules(), ('approve', 'release'))
    timeout = Controller(State(), Rules(bind_payload=False), ALL, 'deny', Limits(monitor=1))
    for action in ('approve', 'mutate', 'release'):
        timeout.step(action)
    return {'honest': honest, 'attacks': rows, 'edit_unbound': edit, 'audit_unbound': audit,
            'overbroad_blocks_honest': overbroad, 'monitor_timeout': timeout.outcome()}

def pump_checker(used, limits, n, length):
    prog = tuple(('xor', 0) for _ in range(length))
    for _ in range(n):
        try:
            _, steps = interpret(prog, 0, step_limit=length)
        except StepLimit:
            steps = length
        if used['checker'] + steps > limits.checker:
            used.setdefault('caps', []).append('checker')
            return 'capped'
        used['checker'] += steps
    return 'ok'

def exhaustion():
    flood = _run((), 'deny', State(), Rules(bind_payload=False),
                 ('approve', 'mutate', 'approve', 'approve', 'release'), Limits(actor=4))
    uncapped = _run((), 'deny', State(), Rules(bind_payload=False),
                    ('approve', 'mutate', 'approve', 'approve', 'release'), Limits(actor=16))
    padded = _run(ALL, 'deny', State(), Rules(),
                  ('approve', 'approve', 'approve', 'approve', 'release'), Limits(actor=8))
    used_h, used_a = {'checker': 0}, {'checker': 0}
    limits = Limits(checker=64)
    return {'actor_flood_capped': {**flood, 'enforcement': flood['harm'] == 0},
            'actor_flood_uncapped': {**uncapped, 'enforcement': uncapped['harm'] == 0},
            'padded_honest': padded,
            'checker_honest': pump_checker(used_h, limits, 20, 1),
            'checker_honest_steps': used_h['checker'],
            'checker_attack': pump_checker(used_a, limits, 20, 8),
            'checker_attack_steps': used_a['checker'],
            'checker_attack_capped': used_a.get('caps', [])}
