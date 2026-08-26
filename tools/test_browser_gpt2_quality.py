"""Numerical scoring tests; actual native hidden-state capture is tested separately."""

import unittest

import numpy as np
from evaluate_browser_gpt2_quality import distribution_metrics, log_probs


class QualityMetricTests(unittest.TestCase):
    def test_identical_distributions_have_unit_ratio_and_zero_divergence(self):
        probs = log_probs(np.log([[0.75, 0.25], [0.2, 0.8]]))
        result = distribution_metrics(probs, probs, np.array([0, 1]))
        self.assertAlmostEqual(result["perplexity"], 1 / np.sqrt(0.75 * 0.8))
        self.assertEqual(result["perplexityRatio"], 1)
        self.assertEqual(result["meanKLReferenceToActual"], 0)
        self.assertEqual(result["meanTotalVariation"], 0)

    def test_shift_invariance_and_known_total_variation(self):
        a = log_probs(np.log([[0.5, 0.5]]))
        b = log_probs(np.log([[0.75, 0.25]]) + 10000)
        result = distribution_metrics(a, b, np.array([0]))
        self.assertAlmostEqual(result["perplexityRatio"], 1.5)
        self.assertAlmostEqual(result["meanTotalVariation"], 0.25)
        self.assertGreater(result["meanKLReferenceToActual"], 0)


if __name__ == "__main__":
    unittest.main()
