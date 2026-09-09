import unittest
from controlled_ai.analysis import episode_summary, exact_sign_pvalue, paired_summary, stopping_rule, wilson
from controlled_ai.calibration import comparison, evaluate
class AnalysisTests(unittest.TestCase):
    def test_wilson_and_exact_paired_test(self):
        lo,hi=wilson(0,100); self.assertEqual(lo,0.); self.assertLess(hi,.04)
        self.assertLess(exact_sign_pvalue(10,0),.01)
    def test_summary_and_stopping(self):
        rows=[{'harm':0,'useful':1} for _ in range(100)]
        self.assertTrue(stopping_rule(rows,100,10,0,0.04)['stop']); self.assertEqual(episode_summary(rows)['harm'],0)
    def test_paired_treatment(self):
        rows=[{'episode':'a','system':'untrusted','harm':1,'useful':0},{'episode':'a','system':'combined','harm':0,'useful':1}]
        self.assertEqual(paired_summary(rows)['harm_reduced'],1)
    def test_calibration_detects_overbroad_false_blocks(self):
        c=comparison(); self.assertEqual(c['specified']['false_block_rate'],0); self.assertGreater(c['overbroad']['false_block_rate'],0)
        self.assertEqual(evaluate()['true_positive_rate'],1)
