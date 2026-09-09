"""Disabled-by-default provider adapters for later paid experiments.

No request is sent unless both CONTROLLED_AI_ENABLE_NETWORK and
CONTROLLED_AI_VALIDATE_PROVIDER_WIRE are exactly '1'. The second switch is
deliberate: provider wire formats and response schemas must be checked against
the funded provider before a run. The adapter records a frozen prompt
identifier and normalizes model output into the same Decision contract used by
local actors.
"""
import json, os, urllib.request
from dataclasses import dataclass
from .adapters import AdapterError, Decision, Usage, parse_action
class ProviderDisabled(RuntimeError): pass
@dataclass(frozen=True)
class ProviderConfig:
    provider: str; model: str; api_key_env: str; endpoint: str; prompt_id: str
class ProviderActor:
    def __init__(self, config, prompt): self.config,self.prompt=config,prompt
    def decide(self, observation):
        if os.environ.get('CONTROLLED_AI_ENABLE_NETWORK') != '1': raise ProviderDisabled('network adapters are disabled; set CONTROLLED_AI_ENABLE_NETWORK=1 explicitly')
        if os.environ.get('CONTROLLED_AI_VALIDATE_PROVIDER_WIRE') != '1': raise ProviderDisabled('provider wire format is not enabled; validate it and set CONTROLLED_AI_VALIDATE_PROVIDER_WIRE=1 explicitly')
        key=os.environ.get(self.config.api_key_env)
        if not key: raise ProviderDisabled('missing API key')
        payload=self._payload(observation); request=urllib.request.Request(self.config.endpoint,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=60) as response: data=json.loads(response.read())
        raw,usage=self._normalize(data); return Decision(parse_action(raw),raw,usage)
    def _payload(self, observation):
        return {'model':self.config.model,'messages':[{'role':'system','content':self.prompt},{'role':'user','content':json.dumps(observation,sort_keys=True)}],'response_format':{'type':'json_object'}}
    def _normalize(self,data):
        # Provider-specific subclasses should override this parser before live use.
        raise AdapterError('provider response parser is not configured')
class OpenAIActor(ProviderActor):
    def _normalize(self,data):
        raw=data['output'][0]['content'][0]['text']; u=data.get('usage',{})
        return raw,Usage(u.get('input_tokens',0),u.get('output_tokens',0),u.get('reasoning_tokens',0))
class AnthropicActor(ProviderActor):
    def _normalize(self,data):
        raw=data['content'][0]['text']; u=data.get('usage',{})
        return raw,Usage(u.get('input_tokens',0),u.get('output_tokens',0),u.get('thinking_tokens',0))
class XAIActor(OpenAIActor): pass
