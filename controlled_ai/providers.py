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
