"""Provider-neutral decision contract; no API keys or network calls required."""
import json
from dataclasses import dataclass
from .model import ACTIONS

class AdapterError(ValueError): pass
@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0; output_tokens: int = 0; reasoning_tokens: int = 0; retries: int = 0
@dataclass(frozen=True)
class Decision:
    action: str; raw: str; usage: Usage

def parse_action(raw):
    try: item = json.loads(raw)
    except json.JSONDecodeError as e: raise AdapterError('invalid JSON action') from e
    if set(item) != {'action'} or item['action'] not in ACTIONS: raise AdapterError('invalid action schema')
    return item['action']

class ScriptedActor:
    """Local stand-in for a model; its output follows the same JSON contract."""
    def __init__(self, actions, input_tokens=0, output_tokens=12): self.actions, self.i, self.input_tokens, self.output_tokens = tuple(actions), 0, input_tokens, output_tokens
    def decide(self, observation):
        action = self.actions[self.i] if self.i < len(self.actions) else 'approve'; self.i += 1
        raw = json.dumps({'action': action}, separators=(',', ':'))
        return Decision(parse_action(raw), raw, Usage(self.input_tokens, self.output_tokens))

class RuleMonitor:
    def __init__(self, channels, response='deny', input_tokens=0, output_tokens=8): self.channels, self.response, self.input_tokens, self.output_tokens = tuple(channels), response, input_tokens, output_tokens
    def decide(self, state, action):
        from .monitor import CHANNELS
        flag = next((c for c in self.channels if CHANNELS[c](state, action)), None)
        raw = json.dumps({'decision': self.response if flag else 'allow', 'flag': flag}, separators=(',', ':'))
        return json.loads(raw), Usage(self.input_tokens, self.output_tokens)
