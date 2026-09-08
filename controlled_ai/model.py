"""A bounded, fully observed environment. Actions have deterministic effects."""
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class State:
    artifact: int = 0  # 0: required truth table; 1: corrupt truth table
    approved: int = -1
    released: int = -1
    consumed: bool = False
    revoked: bool = False
    pending: bool = False
    ordinary: int = 2
    reserve: int = 1
    executions: int = 0

@dataclass(frozen=True)
class Rules:
    bind_payload: bool = True
    prevent_replay: bool = True
    cancel_pending: bool = True
    protect_reserve: bool = True

ACTIONS = ('approve', 'mutate', 'release', 'queue', 'revoke', 'tick', 'spend', 'restart')

def transition(s: State, action: str, rules: Rules) -> State:
    if action not in ACTIONS:
        raise ValueError(action)
    if action == 'restart':
        return s if rules.prevent_replay else replace(s, consumed=False)
    if action == 'tick':
        return replace(s, pending=False, released=1) if s.pending else s
    if action == 'revoke':
        return replace(s, revoked=True, pending=False if rules.cancel_pending else s.pending)
    if s.revoked:
        return s
    if action == 'approve':
        # An independent checker approves only the required artifact, once.
        return replace(s, approved=0) if s.artifact == 0 and s.approved == -1 else s
    if action == 'mutate':
        return replace(s, artifact=1)
    if action in ('release', 'queue'):
        if s.approved == -1 or (rules.prevent_replay and s.consumed):
            return s
        if rules.bind_payload and (s.artifact != s.approved or action != 'release'):
            return s
        return replace(s, consumed=True, executions=min(2, s.executions + 1),
                       released=s.artifact if action == 'release' else s.released,
                       pending=action == 'queue' or s.pending)
    if action == 'spend':
        if s.ordinary:
            return replace(s, ordinary=s.ordinary - 1)
        if not rules.protect_reserve:
            return replace(s, reserve=0)
    return s
