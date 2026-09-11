import unittest
from controlled_ai.landscape import bounded_outcomes, build_landscape, effective_step
from controlled_ai.model import State, Rules
from controlled_ai.monitor import ALL
from controlled_ai.outcomes import harms
from controlled_ai.solver import solve


class LandscapeTests(unittest.TestCase):
    def test_monitor_changes_completed_reachability(self):
        rules = Rules(bind_payload=False)
        self.assertTrue(bounded_outcomes(State(), rules)['completed_harm_reachable'])
        self.assertFalse(bounded_outcomes(State(), rules, ALL)['completed_harm_reachable'])

    def test_pending_upper_is_not_completed_harm(self):
        state = State(revoked=True, pending=True)
        self.assertEqual(solve(state, Rules(), 0)['harm_upper'], 1)
        result = bounded_outcomes(state, Rules(), ALL, 6)
        self.assertFalse(result['completed_harm_reachable'])
        self.assertTrue(result['unresolved_pending_at_horizon'])
        self.assertFalse(result['useful_without_harm_reachable'])

    def test_generated_witnesses_replay(self):
        report = build_landscape()
        self.assertEqual(len(report['rows']), 96)
        for row in report['rows']:
            for key, wanted in [('completed_harm_witness', True), ('useful_witness', False)]:
                path = row[key]
                if path is None:
                    continue
                state = State(**row['initial_state'])
                for action in path:
                    state = effective_step(state, action, Rules(**row['rules']), row['monitor_channels'])
                self.assertEqual(bool(harms(state)), wanted)
                if not wanted:
                    self.assertEqual(state.released, 0)
                self.assertLessEqual(len(path), row['horizon'])

    def test_unmonitored_search_agrees_with_existing_solver_lower(self):
        for row in build_landscape()['rows']:
            if not row['monitor_channels']:
                self.assertEqual(int(row['completed_harm_reachable']), row['rules_only_harm_lower'])
