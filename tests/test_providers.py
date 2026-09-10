import json
import os
import tempfile
import unittest
from pathlib import Path

from controlled_ai.adapters import AdapterError
from controlled_ai.provider_report import setup_report, write_setup_report
from controlled_ai.providers import (
    ANTHROPIC_MODEL,
    OPENAI_MODEL,
    AnthropicActor,
    OpenAIActor,
    ProviderConfig,
    ProviderConfigError,
    ProviderDisabled,
    describe_setup,
    haiku_config,
    live_calls_allowed,
    load_env,
    luna_config,
    pinned_model,
    require_live,
    served_model_allowed,
)


APPROVE = '{"action":"approve"}'


class FakeTransport:
    def __init__(self, status=200, body=None, capture=None):
        self.status = status
        self.body = body or {}
        self.capture = capture if capture is not None else []

    def post(self, url, headers, payload, timeout=60):
        self.capture.append({"url": url, "headers": headers, "payload": payload})
        return self.status, self.body


class GateTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("CONTROLLED_AI_ENABLE_NETWORK", None)
        os.environ.pop("CONTROLLED_AI_VALIDATE_PROVIDER_WIRE", None)

    def test_disabled_by_default(self):
        self.assertFalse(live_calls_allowed())
        actor = OpenAIActor(luna_config(), "x")
        with self.assertRaises(ProviderDisabled):
            actor.decide({"permitted_actions": ["approve"]})

    def test_both_flags_required(self):
        os.environ["CONTROLLED_AI_ENABLE_NETWORK"] = "1"
        os.environ.pop("CONTROLLED_AI_VALIDATE_PROVIDER_WIRE", None)
        self.assertFalse(live_calls_allowed())
        with self.assertRaises(ProviderDisabled):
            require_live()
        os.environ["CONTROLLED_AI_VALIDATE_PROVIDER_WIRE"] = "1"
        os.environ.pop("CONTROLLED_AI_ENABLE_NETWORK", None)
        self.assertFalse(live_calls_allowed())


class PinTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("CONTROLLED_AI_OPENAI_MODEL", None)
        os.environ.pop("CONTROLLED_AI_ANTHROPIC_MODEL", None)

    def test_defaults(self):
        self.assertEqual(luna_config().model, OPENAI_MODEL)
        self.assertEqual(haiku_config().model, ANTHROPIC_MODEL)
        os.environ.pop("CONTROLLED_AI_OPENAI_MODEL", None)
        os.environ.pop("CONTROLLED_AI_ANTHROPIC_MODEL", None)
        self.assertEqual(pinned_model("openai"), OPENAI_MODEL)
        self.assertEqual(pinned_model("anthropic"), ANTHROPIC_MODEL)

    def test_rejects_sol_and_sonnet(self):
        with self.assertRaises(ProviderConfigError):
            ProviderConfig("openai", "gpt-5.6-sol", "OPENAI_API_KEY", "https://api.openai.com/v1/responses", "x")
        with self.assertRaises(ProviderConfigError):
            ProviderConfig("anthropic", "claude-sonnet-5", "ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/messages", "x")
        os.environ["CONTROLLED_AI_OPENAI_MODEL"] = "gpt-5.6-sol"
        with self.assertRaises(ProviderConfigError):
            pinned_model("openai")

    def test_haiku_alias_allowed(self):
        os.environ["CONTROLLED_AI_ANTHROPIC_MODEL"] = "claude-haiku-4-5"
        self.assertEqual(pinned_model("anthropic"), "claude-haiku-4-5")

    def test_served_dated_ids(self):
        self.assertTrue(served_model_allowed("openai", "gpt-5.6-luna-2026-09-01"))
        self.assertTrue(served_model_allowed("anthropic", "claude-haiku-4-5-20251001-preview"))
        self.assertFalse(served_model_allowed("openai", "gpt-5.6-terra"))
        self.assertFalse(served_model_allowed("anthropic", "claude-sonnet-5"))


class EnvLoaderTests(unittest.TestCase):
    def tearDown(self):
        for key in (
            "OPENAI_API_KEY",
            "CONTROLLED_AI_OPENAI_MODEL",
            "CONTROLLED_AI_ENABLE_NETWORK",
        ):
            os.environ.pop(key, None)

    def test_literal_load_and_existing_wins(self):
        os.environ["OPENAI_API_KEY"] = "sk-already-set"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text(
                "# comment\n"
                "OPENAI_API_KEY=sk-from-file\n"
                "CONTROLLED_AI_OPENAI_MODEL=gpt-5.6-luna\n"
            )
            load_env(path)
        self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-already-set")
        self.assertEqual(os.environ["CONTROLLED_AI_OPENAI_MODEL"], "gpt-5.6-luna")

    def test_rejects_unknown_and_shell_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("EVIL=$(whoami)\n")
            with self.assertRaises(ProviderConfigError):
                load_env(path)


class ClientTests(unittest.TestCase):
    def setUp(self):
        os.environ["CONTROLLED_AI_ENABLE_NETWORK"] = "1"
        os.environ["CONTROLLED_AI_VALIDATE_PROVIDER_WIRE"] = "1"
        os.environ["OPENAI_API_KEY"] = "sk-test-openai"
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"

    def tearDown(self):
        for key in (
            "CONTROLLED_AI_ENABLE_NETWORK",
            "CONTROLLED_AI_VALIDATE_PROVIDER_WIRE",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "CONTROLLED_AI_OPENAI_REASONING_EFFORT",
        ):
            os.environ.pop(key, None)

    def test_openai_payload_pins_luna(self):
        capture = []
        body = {
            "model": OPENAI_MODEL,
            "choices": [{"message": {"content": APPROVE}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
        }
        actor = OpenAIActor(luna_config(), "be terse", transport=FakeTransport(body=body, capture=capture))
        decision = actor.decide({"permitted_actions": ["approve"]})
        self.assertEqual(capture[0]["payload"]["model"], OPENAI_MODEL)
        self.assertEqual(capture[0]["payload"]["max_completion_tokens"], 256)
        self.assertEqual(capture[0]["payload"]["reasoning_effort"], "none")
        self.assertEqual(decision.action, "approve")
        self.assertEqual(actor.last_reported_model, OPENAI_MODEL)

    def test_anthropic_uses_x_api_key_header(self):
        capture = []
        body = {
            "model": ANTHROPIC_MODEL,
            "content": [{"type": "text", "text": APPROVE}],
            "usage": {"input_tokens": 8, "output_tokens": 2},
        }
        actor = AnthropicActor(haiku_config(), "be terse", transport=FakeTransport(body=body, capture=capture))
        decision = actor.decide({"permitted_actions": ["approve"]})
        self.assertEqual(capture[0]["headers"]["x-api-key"], "sk-ant-test")
        self.assertNotIn("Authorization", capture[0]["headers"])
        self.assertEqual(decision.action, "approve")

    def test_rejects_openai_upgrade(self):
        body = {"model": "gpt-5.6-terra", "choices": [{"message": {"content": APPROVE}}]}
        actor = OpenAIActor(luna_config(), "x", transport=FakeTransport(body=body))
        with self.assertRaises(ProviderConfigError):
            actor.decide({})

    def test_accepts_dated_luna_id(self):
        body = {
            "model": "gpt-5.6-luna-2026-09-01",
            "choices": [{"message": {"content": APPROVE}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 1},
        }
        actor = OpenAIActor(luna_config(), "x", transport=FakeTransport(body=body))
        decision = actor.decide({})
        self.assertEqual(actor.last_reported_model, "gpt-5.6-luna-2026-09-01")
        self.assertEqual(decision.action, "approve")

    def test_accepts_haiku_dated_variant(self):
        body = {
            "model": "claude-haiku-4-5-20251001-preview",
            "content": [{"type": "text", "text": APPROVE}],
            "usage": {"input_tokens": 4, "output_tokens": 1},
        }
        actor = AnthropicActor(haiku_config(), "x", transport=FakeTransport(body=body))
        decision = actor.decide({})
        self.assertEqual(actor.last_reported_model, "claude-haiku-4-5-20251001-preview")
        self.assertEqual(decision.action, "approve")

    def test_rejects_reasoning_upgrade(self):
        os.environ["CONTROLLED_AI_OPENAI_REASONING_EFFORT"] = "high"
        body = {
            "model": OPENAI_MODEL,
            "choices": [{"message": {"content": APPROVE}}],
        }
        actor = OpenAIActor(luna_config(), "x", transport=FakeTransport(body=body))
        with self.assertRaises(ProviderConfigError):
            actor.decide({})

    def test_invalid_json_is_adapter_error(self):
        body = {
            "model": ANTHROPIC_MODEL,
            "content": [{"type": "text", "text": "sure, I will help"}],
            "usage": {"input_tokens": 2, "output_tokens": 2},
        }
        actor = AnthropicActor(haiku_config(), "x", transport=FakeTransport(body=body))
        with self.assertRaises(AdapterError):
            actor.decide({})

    def test_describe_setup_omits_keys(self):
        blob = json.dumps(describe_setup())
        self.assertNotIn("sk-test-openai", blob)
        self.assertNotIn("sk-ant-test", blob)


class IsolatedGateTests(unittest.TestCase):
    def test_client_respects_gate_even_with_key(self):
        os.environ["OPENAI_API_KEY"] = "sk-test-openai"
        os.environ.pop("CONTROLLED_AI_ENABLE_NETWORK", None)
        os.environ.pop("CONTROLLED_AI_VALIDATE_PROVIDER_WIRE", None)
        actor = OpenAIActor(luna_config(), "x", transport=FakeTransport(body={"model": OPENAI_MODEL}))
        with self.assertRaises(ProviderDisabled):
            actor.decide({})
        os.environ.pop("OPENAI_API_KEY", None)


class SetupReportTests(unittest.TestCase):
    def tearDown(self):
        for key in (
            "CONTROLLED_AI_ENABLE_NETWORK",
            "CONTROLLED_AI_VALIDATE_PROVIDER_WIRE",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "CONTROLLED_AI_OPENAI_REASONING_EFFORT",
        ):
            os.environ.pop(key, None)

    def test_report_has_readiness_and_omits_keys(self):
        os.environ["OPENAI_API_KEY"] = "sk-test-openai"
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        report = setup_report()
        blob = json.dumps(report)
        self.assertNotIn("sk-test-openai", blob)
        self.assertNotIn("sk-ant-test", blob)
        self.assertFalse(report["network_called"])
        self.assertEqual(report["status"], "ready_for_live_after_flags")
        self.assertTrue(report["pins_ok"])
        self.assertIn("request_contract", report)
        self.assertEqual(len(report["providers"]), 2)

    def test_write_setup_report_creates_local_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "provider-setup-local.json"
            report = write_setup_report(path)
            saved = json.loads(path.read_text())
            self.assertEqual(report["written_to"], str(path))
            self.assertEqual(saved["claim"], report["claim"])
            self.assertFalse(saved["network_called"])
            self.assertNotIn("written_to", saved)


if __name__ == "__main__":
    unittest.main()
