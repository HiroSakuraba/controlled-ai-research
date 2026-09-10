import json
import os
import unittest

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
    luna_config,
)


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


class PinTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(luna_config().model, OPENAI_MODEL)
        self.assertEqual(haiku_config().model, ANTHROPIC_MODEL)

    def test_rejects_sol_and_sonnet(self):
        with self.assertRaises(ProviderConfigError):
            ProviderConfig("openai", "gpt-5.6-sol", "OPENAI_API_KEY", "https://api.openai.com/v1/responses", "x")
        with self.assertRaises(ProviderConfigError):
            ProviderConfig("anthropic", "claude-sonnet-5", "ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/messages", "x")


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
        ):
            os.environ.pop(key, None)

    def test_openai_payload_pins_luna(self):
        capture = []
        body = {
            "model": OPENAI_MODEL,
            "choices": [{"message": {"content": '{"action":"approve"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
        }
        actor = OpenAIActor(luna_config(), "be terse", transport=FakeTransport(body=body, capture=capture))
        decision = actor.decide({"permitted_actions": ["approve"]})
        self.assertEqual(capture[0]["payload"]["model"], OPENAI_MODEL)
        self.assertEqual(decision.action, "approve")
        self.assertEqual(actor.last_reported_model, OPENAI_MODEL)

    def test_anthropic_uses_x_api_key_header(self):
        capture = []
        body = {
            "model": ANTHROPIC_MODEL,
            "content": [{"type": "text", "text": '{"action":"approve"}'}],
            "usage": {"input_tokens": 8, "output_tokens": 2},
        }
        actor = AnthropicActor(haiku_config(), "be terse", transport=FakeTransport(body=body, capture=capture))
        decision = actor.decide({"permitted_actions": ["approve"]})
        self.assertEqual(capture[0]["headers"]["x-api-key"], "sk-ant-test")
        self.assertNotIn("Authorization", capture[0]["headers"])
        self.assertEqual(decision.action, "approve")

    def test_rejects_openai_upgrade(self):
        body = {"model": "gpt-5.6-terra", "choices": [{"message": {"content": '{"action":"approve"}'}}]}
        actor = OpenAIActor(luna_config(), "x", transport=FakeTransport(body=body))
        with self.assertRaises(ProviderConfigError):
            actor.decide({})

    def test_describe_setup_omits_keys(self):
        blob = json.dumps(describe_setup())
        self.assertNotIn("sk-test-openai", blob)
        self.assertNotIn("sk-ant-test", blob)


if __name__ == "__main__":
    unittest.main()
