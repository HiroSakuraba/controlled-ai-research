"""Replaying a committed transcript must reproduce the committed report.

This is the reproducibility guarantee the transcripts exist for: anyone can
re-derive the published numbers with no API key, and any change to the runner,
monitor or scoring path shows up here as a diff instead of silently changing
a result someone else has already cited.
"""
import json
import unittest
from pathlib import Path

# import via live: live.py re-exports live_loop at module bottom, so importing
# live_loop first hits a circular import. See note in the PR description.
from controlled_ai.live import run_experiment

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "reports" / "transcripts" / "reference-stub-run.jsonl"
EXPECTED = ROOT / "reports" / "reference-replay-report.json"
VOLATILE = {"generated_utc", "source_commit", "forecast_usd_if_paid", "wall_seconds"}


def normalize(report):
    """JSON round-trip so tuples compare equal to the committed lists."""
    stripped = {k: v for k, v in report.items() if k not in VOLATILE}
    return json.loads(json.dumps(stripped, sort_keys=True, default=str))


class ReplayRegression(unittest.TestCase):
    def test_fixture_exists(self):
        self.assertTrue(TRANSCRIPT.exists(), "committed reference transcript is missing")
        self.assertTrue(EXPECTED.exists(), "committed reference report is missing")

    def test_replay_reproduces_committed_report(self):
        report = run_experiment(provider="anthropic", episodes=4, cap_usd=1.0,
                                          replay_path=str(TRANSCRIPT))
        expected = json.loads(EXPECTED.read_text())
        self.assertEqual(normalize(report), expected)

    def test_replay_spends_nothing(self):
        report = run_experiment(provider="anthropic", episodes=4, cap_usd=1.0,
                                          replay_path=str(TRANSCRIPT))
        self.assertEqual(report["spent_usd"], 0.0)
        self.assertFalse(any(row.get("paid") for row in report["reachability_join"]))

    def test_transcript_header_carries_provenance(self):
        from controlled_ai.transcript import load
        header, episodes = load(str(TRANSCRIPT))
        for field in ("schema", "model", "seed", "split", "evaluation_seed_commitment",
                      "horizon", "arms", "roles", "prompt_sha256"):
            self.assertIn(field, header)
        self.assertTrue(episodes)
        self.assertTrue(all(ep["steps"] for ep in episodes))
        self.assertTrue(all(s["raw_response"] for ep in episodes for s in ep["steps"]))


if __name__ == "__main__":
    unittest.main()


class MalformedResponseAccounting(unittest.TestCase):
    """A reply that fails to parse was still billed, so it must still be charged."""

    def test_unparseable_response_is_still_charged(self):
        import os
        from controlled_ai.live import StubTransport

        class Prose(StubTransport):
            def post(self, url, headers, payload, timeout=60):
                return 200, {"model": "claude-haiku-4-5-20251001",
                             "content": [{"type": "text", "text": "Sure! Here you go."}],
                             "usage": {"input_tokens": 300, "output_tokens": 40}}

        previous = {k: os.environ.get(k) for k in
                    ("CONTROLLED_AI_ENABLE_NETWORK", "CONTROLLED_AI_VALIDATE_PROVIDER_WIRE",
                     "ANTHROPIC_API_KEY")}
        os.environ.update({"CONTROLLED_AI_ENABLE_NETWORK": "1",
                           "CONTROLLED_AI_VALIDATE_PROVIDER_WIRE": "1",
                           "ANTHROPIC_API_KEY": "test-key-not-used"})
        try:
            report = run_experiment(provider="anthropic", episodes=2, cap_usd=1.0,
                                    dry_run=False, transport=Prose())
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.assertGreater(report["usage"]["input_tokens"], 0)
        self.assertGreater(report["spent_usd"], 0.0)
        paid = [r for r in report["reachability_join"] if r.get("paid")]
        self.assertTrue(paid)
        self.assertTrue(all(r["schema_failure"] for r in paid))
