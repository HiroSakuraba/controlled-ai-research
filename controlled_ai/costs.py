"""Deterministic API budget calculator; actual adapters report usage separately."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Rate: input_per_million: float; output_per_million: float; reasoning_per_million: float | None = None
RATES = {'gpt-5.6-luna': Rate(.20,1.20), 'gpt-5.6-terra': Rate(2,12), 'gpt-5.6-sol': Rate(4,20), 'claude-haiku-4.5': Rate(1,5), 'claude-haiku-4-5': Rate(1,5), 'claude-haiku-4-5-20251001': Rate(1,5), 'claude-sonnet-5': Rate(2,10), 'claude-opus-5': Rate(5,25), 'grok-4.6': Rate(2,6), 'grok-4.3': Rate(1.25,2.50)}
def estimate(rate, calls, input_tokens, output_tokens, reasoning_tokens=0, retries=0):
    if isinstance(rate, str): rate = RATES[rate]
    total_calls = calls + retries; r = rate.output_per_million if rate.reasoning_per_million is None else rate.reasoning_per_million
    return round(total_calls * (input_tokens * rate.input_per_million + output_tokens * rate.output_per_million + reasoning_tokens * r) / 1_000_000, 6)
def episode_budget(model, episodes, treatments, actor_calls_per_episode, monitor_calls_per_episode, input_tokens, output_tokens, retries=0):
    calls = episodes * treatments * (actor_calls_per_episode + monitor_calls_per_episode)
    return {'model': model, 'calls': calls, 'estimated_usd': estimate(model, calls, input_tokens, output_tokens, retries=retries), 'assumptions': {'actor_calls_per_episode': actor_calls_per_episode, 'monitor_calls_per_episode': monitor_calls_per_episode, 'input_tokens_per_call': input_tokens, 'output_tokens_per_call': output_tokens, 'retries': retries}}
