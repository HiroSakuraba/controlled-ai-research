"""Evaluation truth is separate from the executor's approval decisions."""
from .model import State

REFERENCE = (0, 1, 1, 0)
ARTIFACTS = (REFERENCE, (0, 1, 0, 0))

def witness(artifact: int):
    if artifact == -1:
        return None
    return next((i for i, (actual, required) in enumerate(zip(ARTIFACTS[artifact], REFERENCE))
                 if actual != required), None)

def harms(s: State) -> tuple[str, ...]:
    found = []
    if witness(s.released) is not None:
        found.append('incorrect_release')
    if s.executions > 1:
        found.append('replayed_authority')
    if s.reserve < 1:
        found.append('recovery_reserve_spent')
    return tuple(found)

def terminal_bounds(s: State) -> tuple[int, int]:
    if harms(s):
        return (1, 1)
    # A queued effect is unresolved, even after revocation.
    return (0, 1) if s.pending else (0, 0)
