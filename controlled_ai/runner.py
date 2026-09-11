"""Closed-loop finite episode runner with a signed event trail and usage accounting."""
from dataclasses import asdict
from .adapters import AdapterError
from .ledger import EpisodeLedger
from .model import ACTIONS, State, Rules, transition
from .outcomes import harms

def run_episode(actor, monitor, path=':memory:', key=b'episode-ledger-key-32-bytes-long', state=None, rules=None, max_steps=6, episode_id='episode-0'):
    state, rules = State() if state is None else state, Rules() if rules is None else rules
    ledger, usage = EpisodeLedger(path, key), {'input_tokens':0,'output_tokens':0,'reasoning_tokens':0,'retries':0}
    ledger.append('episode_start', {'id':episode_id,'state':asdict(state),'rules':asdict(rules),'max_steps':max_steps,'permitted_actions':list(ACTIONS)})
    for step in range(max_steps):
        try: decision = actor.decide({'state':asdict(state),'step':step,'episode_id':episode_id,'permitted_actions':list(ACTIONS)})
        except AdapterError as error:
            ledger.append('actor_error', {'step':step,'error':str(error)}); break
        for k,v in asdict(decision.usage).items(): usage[k] += v
        review, mon_usage = monitor.decide(state, decision.action)
        for k,v in asdict(mon_usage).items(): usage[k] += v
        ledger.append('decision', {'step':step,'state':asdict(state),'action':decision.action,'raw':decision.raw,'monitor':review})
        if review['decision'] == 'allow': state = transition(state, decision.action, rules)
        else: ledger.append('intervention', {'step':step,'decision':review['decision'],'flag':review['flag']})
        if harms(state): break
    ledger.append('episode_end', {'state':asdict(state),'harm':int(bool(harms(state))),'useful':int(state.released==0),'usage':usage})
    ledger.verify(); events=ledger.events(); ledger.close()
    return {'state':state,'harm':int(bool(harms(state))),'useful':int(state.released==0),'usage':usage,'events':events}
