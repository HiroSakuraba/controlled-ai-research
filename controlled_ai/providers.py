"""Disabled-by-default provider adapters for later paid experiments.

No request is sent unless both CONTROLLED_AI_ENABLE_NETWORK and
CONTROLLED_AI_VALIDATE_PROVIDER_WIRE are exactly '1'. Allowed models are
pinned to GPT-5.6 Luna and Claude Haiku 4.5. Keys stay in the environment
and are never written into episode records.
"""
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .adapters import AdapterError, Decision, Usage, parse_action

OPENAI_MODEL = "gpt-5.6-luna"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_ALIASES = frozenset({
    ANTHROPIC_MODEL,
    "claude-haiku-4-5",
    "claude-haiku-4.5",
})
ALLOWED_MODELS = {
    "openai": frozenset({OPENAI_MODEL}),
    "anthropic": ANTHROPIC_ALIASES,
    "xai": frozenset({"grok-4.3"}),
}
DEFAULT_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "xai": "https://api.x.ai/v1/chat/completions",
}
KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
}


class ProviderDisabled(RuntimeError):
    pass


class ProviderConfigError(ValueError):
    pass


def live_calls_allowed():
    return (
        os.environ.get("CONTROLLED_AI_ENABLE_NETWORK") == "1"
        and os.environ.get("CONTROLLED_AI_VALIDATE_PROVIDER_WIRE") == "1"
    )


def require_live():
    if os.environ.get("CONTROLLED_AI_ENABLE_NETWORK") != "1":
        raise ProviderDisabled("network adapters are disabled; set CONTROLLED_AI_ENABLE_NETWORK=1 explicitly")
    if os.environ.get("CONTROLLED_AI_VALIDATE_PROVIDER_WIRE") != "1":
        raise ProviderDisabled(
            "provider wire format is not enabled; validate it and set CONTROLLED_AI_VALIDATE_PROVIDER_WIRE=1 explicitly"
        )


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    api_key_env: str
    endpoint: str
    prompt_id: str

    def __post_init__(self):
        allowed = ALLOWED_MODELS.get(self.provider)
        if not allowed:
            raise ProviderConfigError("unknown provider")
        if self.model not in allowed:
            raise ProviderConfigError(
                "model %r is not allowed for %s; pin %s"
                % (self.model, self.provider, next(iter(allowed)))
            )


def luna_config(prompt_id="actor-v1"):
    return ProviderConfig("openai", OPENAI_MODEL, KEY_ENV["openai"], DEFAULT_ENDPOINTS["openai"], prompt_id)


def haiku_config(prompt_id="actor-v1"):
    return ProviderConfig("anthropic", ANTHROPIC_MODEL, KEY_ENV["anthropic"], DEFAULT_ENDPOINTS["anthropic"], prompt_id)


class HttpTransport:
    def post(self, url, headers, payload, timeout=60):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            exc.read()
            raise AdapterError("provider HTTP %s" % exc.code) from None
        except urllib.error.URLError as exc:
            raise AdapterError("provider unreachable") from exc


def _headers(provider, key):
    if provider == "anthropic":
        return {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    return {"Authorization": "Bearer " + key, "Content-Type": "application/json"}


def _extract_json_object(text):
    if not isinstance(text, str) or not text.strip():
        raise AdapterError("empty model output")
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    start, end = raw.find("{'), raw.rfind("}")
    if start < 0 or end <= start:
        raise AdapterError("model output was not a JSON object")
    return raw[start : end + 1]


class ProviderActor:
    def __init__(self, config, prompt, transport=None):
        self.config, self.prompt = config, prompt
        self.transport = transport or HttpTransport()
        self.last_reported_model = None

    def decide(self, observation):
        require_live()
        key = os.environ.get(self.config.api_key_env)
        if not key:
            raise ProviderDisabled("missing API key")
        payload = self._payload(observation)
        status, data = self.transport.post(
            self.config.endpoint,
            _headers(self.config.provider, key),
            payload,
        )
        if status != 200 or not isinstance(data, dict):
            raise AdapterError("provider returned %s" % status)
        reported = data.get("model") or self.config.model
        self._check_served_model(reported)
        self.last_reported_model = reported
        raw, usage = self._normalize(data)
        parsed = _extract_json_object(raw)
        return Decision(parse_action(parsed), parsed, usage)

    def _check_served_model(self, reported):
        if self.config.provider == "openai" and not str(reported).startswith("gpt-5.6-luna"):
            raise ProviderConfigError("openai served %r instead of gpt-5.6-luna" % reported)
        if self.config.provider == "anthropic" and "haiku" not in str(reported):
            raise ProviderConfigError("anthropic served %r instead of Haiku 4.5" % reported)

    def _payload(self, observation):
        user = json.dumps(observation, sort_keys=True)
        if self.config.provider == "anthropic":
            return {
                "model": self.config.model,
                "max_tokens": 256,
                "system": self.prompt,
                "messages": [{"role": "user", "content": user}],
            }
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": user},
            ],
            "max_tokens": 256,
        }
        if "chat/completions" in self.config.endpoint:
            return payload
        payload["response_format"] = {"type": "json_object"}
        return payload

    def _normalize(self, data):
        raise AdapterError("provider response parser is not configured")


class OpenAIActor(ProviderActor):
    def _normalize(self, data):
        if data.get("choices"):
            raw = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            return raw, Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), 0)
        raw = data["output"][0]["content"][0]["text"]
        usage = data.get("usage") or {}
        return raw, Usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0), usage.get("reasoning_tokens", 0))


class AnthropicActor(ProviderActor):
    def _normalize(self, data):
        raw = data["content"][0]["text"]
        usage = data.get("usage") or {}
        return raw, Usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0), usage.get("thinking_tokens", 0))


class XAIActor(OpenAIActor):
    pass


def describe_setup():
    rows = []
    for provider, default_model in (("openai", OPENAI_MODEL), ("anthropic", ANTHROPIC_MODEL)):
        env_name = "CONTROLLED_AI_OPENAI_MODEL" if provider == "openai" else "CONTROLLED_AI_ANTHROPIC_MODEL"
        requested = os.environ.get(env_name, default_model).strip()
        try:
            ProviderConfig(provider, requested, KEY_ENV[provider], DEFAULT_ENDPOINTS[provider], "dry-run")
            allowed, error = True, None
        except ProviderConfigError as exc:
            allowed, error = False, str(exc)
        rows.append({
            "provider": provider,
            "model": requested,
            "model_allowed": allowed,
            "key_present": bool(os.environ.get(KEY_ENV[provider], "").strip()),
            "live_calls_allowed": live_calls_allowed(),
            "error": error,
        })
    return {"claim": "Provider setup only. No network call. No key values.", "providers": rows}


if __name__ == "__main__":
    print(json.dumps(describe_setup(), indent=2, sort_keys=True))
