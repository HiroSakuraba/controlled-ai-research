import json
import os
import unittest

from controlled_ai.adapters import AdapterError
from controlled_ai.live import (
    ARMS,
    HONEST_OBJECTIVE,
    observation_fields,
    run_cell,
    run_experiment,
    usage_usd,
)
from controlled_ai.model import ACTIONS, Rules, State
from controlled_ai.providers import ProviderDisabled


class RecordingActor:
    def __init__(self, actions=('approve',)):
        self.actions = list(actions)
        self.i = 0
        self.observations = []

    def decide(self, observation):
        from controlled_ai.adapters import Decision, Usage, parse_action
        self.observations.append(observation)
        action = self.actions[self.i] if self.i < len(self.actions) else 'approve'
        self.i += 1
        raw = json.dumps({'action': action}, separators=(',', ':'))
        return Decision(parse_action(raw), raw, Usage(3, 2))


class BrokenActor:
    def decide(self, observation):
        raise AdapterError('invalid JSON action')


class LiveDriverTests(unittest.TestCase):
    def test_dry_run_joins_solver_and_scripted_propensity(self):
        report = run_experiment(provider='local', episodes=4, dry_run=True, roles=('adversary',))
        self.assertTrue(report['dry_run'])
        self.assertFalse(report['network_called'])
        self.assertEqual(report['provider'], 'local')
        self.assertIsNone(report['model'])
        self.assertEqual(len(report['evaluation_seed_commitment']), 64)
        for arm in ARMS:
            self.assertIn(arm, report['arms'])
            self.assertGreaterEqual(report['arms'][arm]['offered'], 4)
        join = report['reachability_join']
        self.assertTrue(join)
        reachable_untrusted = [r for r in join if r['arm'] == 'untrusted' and r['harm_reachable'] == 1]
        self.assertTrue(reachable_untrusted)
        # Hardened rules close payload/replay/reserve from these starts; the
        # pending fixture is already armed, so combined reachability stays 1.
        payload_combined = {r['harm_reachable'] for r in join if r['arm'] == 'combined' and r['family'] == 'payload'}
        pending_combined = {r['harm_reachable'] for r in join if r['arm'] == 'combined' and r['family'] == 'pending'}
        self.assertEqual(payload_combined, {0})
        self.assertEqual(pending_combined, {1})
        self.assertIn('untrusted_vs_combined', report['pairs'])
        self.assertEqual(report['spent_usd'], 0.0)

    def test_observation_lists_actions_and_objective(self):
        fields = observation_fields(HONEST_OBJECTIVE)
        self.assertEqual(fields['permitted_actions'], list(ACTIONS))
        self.assertIn('release', fields['objective'])

    def test_schema_failure_is_counted_not_retried(self):
        fixture = {
            'id': 'schema-1',
            'family': 'payload',
            'state': State(),
            'rules': Rules(bind_payload=False),
            'actions': ('approve', 'mutate', 'release'),
        }
        from controlled_ai import live
        original = live.local_actor
        live.local_actor = lambda role, fx: BrokenActor()
        try:
            row = run_cell(fixture, 'untrusted', 'adversary', 'local', True, 3)
        finally:
            live.local_actor = original
        self.assertEqual(row['schema_failure'], 1)
        self.assertEqual(row['harm'], 0)

    def test_runner_observation_includes_permitted_actions(self):
        from controlled_ai.adapters import RuleMonitor
        from controlled_ai.runner import run_episode
        actor = RecordingActor(('approve', 'release'))
        run_episode(actor, RuleMonitor(()), max_steps=2)
        self.assertEqual(actor.observations[0]['permitted_actions'], list(ACTIONS))

    def test_usage_prices_reported_tokens_not_12k_assumption(self):
        cost = usage_usd('claude-haiku-4-5-20251001', {'input_tokens': 190, 'output_tokens': 12, 'reasoning_tokens': 0})
        self.assertLess(cost, 0.01)
        self.assertGreater(cost, 0.0)

    def test_live_path_stays_gated(self):
        os.environ.pop('CONTROLLED_AI_ENABLE_NETWORK', None)
        os.environ.pop('CONTROLLED_AI_VALIDATE_PROVIDER_WIRE', None)
        with self.assertRaises(ProviderDisabled):
            run_experiment(provider='anthropic', episodes=1, dry_run=False)

    def test_dry_run_forecasts_bill_and_does_not_claim_target_met(self):
        report = run_experiment(provider='local', episodes=4, dry_run=True, roles=('honest', 'adversary'))
        self.assertGreater(report['forecast_usd_if_paid'], 0.0)
        self.assertEqual(report['spent_usd'], 0.0)
        self.assertEqual(report['stopped']['reason'], 'episode_cap')
        self.assertNotEqual(report['stopped']['reason'], 'target_met')

    def test_paid_skip_does_not_crash_and_honest_unreachable_is_paid(self):
        os.environ['CONTROLLED_AI_ENABLE_NETWORK'] = '1'
        os.environ['CONTROLLED_AI_VALIDATE_PROVIDER_WIRE'] = '1'
        os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-test'
        from controlled_ai.live import StubTransport
        try:
            report = run_experiment(
                provider='anthropic',
                episodes=4,
                dry_run=False,
                transport=StubTransport(),
                cap_usd=1.0,
            )
        finally:
            for key in ('CONTROLLED_AI_ENABLE_NETWORK', 'CONTROLLED_AI_VALIDATE_PROVIDER_WIRE', 'ANTHROPIC_API_KEY'):
                os.environ.pop(key, None)
        self.assertFalse(report['dry_run'])
        self.assertEqual(report['stopped']['reason'], 'episode_cap')
        join = report['reachability_join']
        skipped = [r for r in join if r.get('skipped') == 'unreachable']
        honest_unreach = [r for r in join if r['role'] == 'honest' and r['harm_reachable'] == 0]
        self.assertTrue(skipped)
        self.assertTrue(all(r['role'] == 'adversary' for r in skipped))
        self.assertTrue(honest_unreach)
        self.assertTrue(all(r['paid'] and r['model_harm'] is not None for r in honest_unreach))
        self.assertTrue(all(r['model_harm'] is not None for r in join if r['paid']))
        pairs = report['pairs']['untrusted_vs_combined']
        self.assertGreater(pairs['pairs'], 2)
        self.assertGreater(report['spent_usd'], 0.0)
        self.assertIsInstance(report['stopped']['summary']['harm'], int)


if __name__ == '__main__':
    unittest.main()
