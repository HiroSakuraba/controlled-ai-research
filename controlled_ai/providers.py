"""Disabled-by-default provider adapters for later paid experiments.

No request is sent unless both CONTROLLED_AI_ENABLE_NETWORK and
CONTROLLED_AI_VALIDATE_PROVIDER_WIRE are exactly '1'. Allowed models are
pinned to GPT-5.6 Luna and Claude Haiku 4.5. Keys stay in the environment
and are never written into episode records.
"""
import json
import os
from pathlib import Path
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
MODEL_ENV = {
    "openai": "CONTROLLED_AI_OPENAI_MODEL",
    "anthropic": "CONTROLLED_AI_ANTHROPIC_MODEL",
}
DEFAULT_MODELS = {
    "openai": OPENAI_MODEL,
    "anthropic": ANTHROPIC_MODEL,
}


class ProviderDisabled(RuntimeError):
    pass


class ProviderConfigError(ValueError):
    pass


def load_env(path=".env"):
    """Literal KEY=value only; no shell evaluation, existing environment wins."""
    path = Path(path)
    if not path.exists():
        return
    allowed = set(KEY_ENV.values()) | set(MODEL_ENV.values()) | {
        "CONTROLLED_AI_ENABLE_NETWORK",
        "CONTROLLED_AI_VALIDATE_PROVIDER_WIRE",
        "CONTROLLED_AI_OPENAI_REASONING_EFFORT",
    }
    values = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not sep or name not in allowed or name in values:
            raise ProviderConfigError("invalid .env entry on line %d" % number)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    for name, value in values.items():
        os.environ.setdefault(name, value)


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


def pinned_model(provider):
    if provider not in ALLOWED_MODELS:
        raise ProviderConfigError("unknown provider")
    requested = os.environ.get(MODEL_ENV.get(provider, ""), DEFAULT_MODELS.get(provider, "")).strip()
    if not requested:
        requested = next(iter(ALLOWED_MODELS[provider]))
    if requested not in ALLOWED_MODELS[provider]:
        raise ProviderConfigError(
            "model %r is not allowed for %s; pin %s"
            % (requested, provider, next(iter(ALLOWED_MODELS[provider])))
        )
    return requested


def served_model_allowed(provider, reported):
    """Accept dated Luna/Haiku ids; reject other families."""
    if provider not in ALLOWED_MODELS or not isinstance(reported, str):
        return False
    name = reported.strip()
    if not name:
        return False
    if provider == "openai":
        return name == OPENAI_MODEL or name.startswith(OPENAI_MODEL + "-")
    if provider == "anthropic":
        if name in ALLOWED_MODELS["anthropic"]:
            return True
        return "haiku-4-5" in name or "haiku-4.5" in name
    return name in ALLOWED_MODELS[provider]


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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AdapterError("provider redirect rejected")


class HttpTransport:
    def post(self, url, headers, payload, timeout=60):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                exc.read()
            except Exception:
                pass
            raise AdapterError("provider HTTP %s" % exc.code) from exc
        except urllib.error.URLError as exc:
            raise AdapterError("provider unreachable") from exc
        except json.JSONDecodeError as exc:
            raise AdapterError("provider returned invalid JSON") from exc


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
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise AdapterError("model output was not a JSON object")
    return raw[start : end + 1]


def _reasoning_effort():
    effort = os.environ.get("CONTROLLED_AI_OPENAI_REASONING_EFFORT", "none").strip() or "none"
    if effort != "none":
        raise ProviderConfigError("Luna reasoning effort must be none; got %r" % effort)
    return effort


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
        if not served_model_allowed(self.config.provider, reported):
            raise ProviderConfigError(
                "provider returned an unapproved model: %s" % reported
            )

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
        }
        if "chat/completions" in self.config.endpoint:
            payload["max_completion_tokens"] = 256
            payload["reasoning_effort"] = _reasoning_effort()
            return payload
        payload["max_tokens"] = 256
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
        try:
            model = pinned_model(provider)
            allowed, error = True, None
        except ProviderConfigError as exc:
            model = os.environ.get(MODEL_ENV[provider], default_model)
            allowed, error = False, str(exc)
        rows.append({
            "provider": provider,
            "model": model,
            "model_allowed": allowed,
            "key_present": bool(os.environ.get(KEY_ENV[provider], "").strip()),
            "live_calls_allowed": live_calls_allowed(),
            "error": error,
        })
    return {"claim": "Provider setup only. No network call. No key values.", "providers": rows}


if __name__ == "__main__":
    load_env()
    print(json.dumps(describe_setup(), indent=2, sort_keys=True))
