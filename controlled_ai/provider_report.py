"""Local provider readiness report. No network calls and no key values."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .providers import (
    ANTHROPIC_MODEL,
    DEFAULT_ENDPOINTS,
    KEY_ENV,
    OPENAI_MODEL,
    describe_setup,
    live_calls_allowed,
)


def _flag(name):
    raw = os.environ.get(name)
    return {"name": name, "set": raw is not None, "is_one": raw == "1"}


def _reasoning_status():
    raw = os.environ.get("CONTROLLED_AI_OPENAI_REASONING_EFFORT", "none")
    requested = (raw or "none").strip() or "none"
    return {"requested": requested, "allowed": requested == "none", "required": "none"}


def setup_report(env_path=".env"):
    env_path = Path(env_path)
    providers = describe_setup()["providers"]
    reasoning = _reasoning_status()
    pins_ok = all(row["model_allowed"] for row in providers)
    keys_present = all(row["key_present"] for row in providers)
    prefixes_ok = all(row.get("key_prefix_ok") is not False for row in providers)
    live = live_calls_allowed()
    if not pins_ok:
        status = "blocked_bad_pin"
    elif not reasoning["allowed"]:
        status = "blocked_reasoning_upgrade"
    elif live and keys_present and prefixes_ok:
        status = "live_armed"
    elif keys_present and prefixes_ok:
        status = "ready_for_live_after_flags"
    elif keys_present:
        status = "blocked_key_prefix"
    else:
        status = "offline_missing_keys"
    next_steps = []
    if not env_path.exists():
        next_steps.append("copy .env.example to .env and add keys locally")
    if not keys_present:
        next_steps.append("set OPENAI_API_KEY and ANTHROPIC_API_KEY in .env")
    if not pins_ok:
        next_steps.append("reset model ids to gpt-5.6-luna and claude-haiku-4-5-20251001")
    if not reasoning["allowed"]:
        next_steps.append("set CONTROLLED_AI_OPENAI_REASONING_EFFORT=none")
    if status == "ready_for_live_after_flags":
        next_steps.append("leave network flags unset until a paid run is intended")
    if status == "live_armed":
        next_steps.append("network flags are on; this report still made no HTTP request")
    if not next_steps:
        next_steps.append("dry-run complete; keep network flags unset")
    return {
        "claim": "Local provider setup report. No network call. No key values. No paid run.",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "network_called": False,
        "status": status,
        "live_calls_allowed": live,
        "pins_ok": pins_ok,
        "keys_present": keys_present,
        "env_file": {
            "path": str(env_path),
            "exists": env_path.exists(),
            "loader": "literal KEY=value; existing environment wins; no shell evaluation",
        },
        "flags": [
            _flag("CONTROLLED_AI_ENABLE_NETWORK"),
            _flag("CONTROLLED_AI_VALIDATE_PROVIDER_WIRE"),
        ],
        "reasoning": reasoning,
        "request_contract": {
            "openai_chat_completions": {
                "model": OPENAI_MODEL,
                "endpoint": DEFAULT_ENDPOINTS["openai"],
                "max_completion_tokens": 256,
                "reasoning_effort": "none",
            },
            "anthropic_messages": {
                "model": ANTHROPIC_MODEL,
                "endpoint": DEFAULT_ENDPOINTS["anthropic"],
                "max_tokens": 256,
                "extended_thinking": False,
            },
            "redirects": "rejected",
            "served_model_policy": "accept dated Luna or Haiku ids; reject Sol, Terra, Sonnet, Opus",
            "action_schema": {"action": "<name from ACTIONS>"},
        },
        "providers": providers,
        "next_steps": next_steps,
    }


def write_setup_report(path="reports/provider-setup-local.json", env_path=".env"):
    report = setup_report(env_path)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    report["written_to"] = str(dest)
    return report
