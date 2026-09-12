import unittest
from fractions import Fraction as F
from controlled_ai.expanded import channel_map, q_curves, return_map, controller_return
from controlled_ai.landscape import effective_step
from controlled_ai.model import State, Rules
from controlled_ai.outcomes import harms
from controlled_ai.sampler import spend, SamplerError

class ExpandedTests(unittest.TestCase):
    def test_all_channel_subsets_and_witnesses(self):
        rows = channel_map()
        self.assertEqual(len(rows), 128)
        groups = {}
        for r in rows:
            groups.setdefault((r['family'], r['executor']), set()).add(tuple(r['channels']))
            for key, harmful in [('completed_harm_witness', True), ('useful_witness', False)]:
                if r[key] is None:
                    continue
                state = State(**r['initial_state'])
                for action in r[key]:
                    state = effective_step(state, action, Rules(**r['rules']), r['channels'])
                self.assertEqual(bool(harms(state)), harmful)
                if not harmful:
                    self.assertEqual(state.released, 0)
        self.assertTrue(all(len(masks) == 16 for masks in groups.values()))

    def test_exact_q_distribution_and_budget(self):
        report = q_curves()
        for r in report['rows']:
            if r.get('status') == 'empty_menu':
                self.assertFalse(r['successful_completion'])
                self.assertEqual(r['useful'], '0')
                continue
            p, Q, q = list(map(F, r['reference'])), list(map(F, r['distribution'])), F(r['q'])
            self.assertEqual(sum(Q), 1)
            self.assertTrue(all(0 <= b <= a/q for a,b in zip(p,Q)))
            if q == 1:
                self.assertEqual(p, Q)
            if r['filter'] == 'oracle_harm_filter':
                self.assertEqual(F(r['harm']), 0)
            if r['filter'] == 'unfiltered' and r['ranking'] == 'adversarial' and q == F(1,2):
                self.assertEqual(F(r['harm']), F(1,2))
            if r['filter'] == 'unfiltered' and r['ranking'] == 'useful' and q == F(1,4):
                self.assertEqual(F(r['useful']), 1)
        self.assertEqual(report['sequential_budget'], ['4','1'])
        with self.assertRaises(SamplerError):
            spend(F(1), F(1,2))

    def test_first_hit_distribution_has_hand_computed_answer(self):
        result = controller_return(State(approved=0), Rules(), (), 2, 'stochastic')
        self.assertEqual(result['return_probability'], '15/16')
        self.assertEqual(result['first_hit_probability'], ['0','3/4','3/16'])
        wait = controller_return(State(approved=0), Rules(), (), 2, 'wait')
        self.assertEqual(wait['return_probability'], '0')
        self.assertEqual(wait['unfinished_probability'], '1')

    def test_return_mass_and_nonreturn_witness(self):
        for r in return_map():
            self.assertEqual(sum(F(r[k]) for k in ('return_probability','harm_probability','unfinished_probability')),1)
            self.assertLessEqual(F(r['pending_probability']), F(r['unfinished_probability']))
            self.assertEqual(sum(map(F,r['first_hit_probability'])), F(r['return_probability']))
            state = State(**r['post_kick_state'])
            self.assertIsNotNone(r['nonreturn_witness'])
            for action in r['nonreturn_witness']:
                state = effective_step(state, action, Rules(**r['rules']), r['channels'])
            self.assertFalse(state.released == 0 and not harms(state))

    def test_invalid_controller_inputs(self):
        for horizon, policy in [(-1,'progress'), (1,'invented')]:
            with self.assertRaises(ValueError):
                controller_return(State(),Rules(),(),horizon,policy)
