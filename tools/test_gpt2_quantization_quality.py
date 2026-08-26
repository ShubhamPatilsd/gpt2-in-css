"""Small contracts; evaluator also checks actual checkpoint forward/cache paths."""

import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
from evaluate_gpt2_quantization_quality import (
    Calibration,
    Model,
    dynamic_int8,
    load_model,
    metrics,
    repetition,
)
from evaluate_svg_w8a8_generation import Runner, apply_surface, fit_surface


class QuantizationQualityTests(unittest.TestCase):
    def test_int8_zero_and_per_row_scaling(self):
        values = np.array([[0, 0, 0], [-100, 0, 100], [-1, 0.2, 1]], np.float32)
        actual = dynamic_int8(values, axis=-1)
        self.assertTrue(np.isfinite(actual).all())
        np.testing.assert_array_equal(actual[:2], values[:2])
        self.assertLess(abs(actual[2, 1] - 0.2), 1 / 127)

    def test_calibration_channel_maxima_equivalence(self):
        rng = np.random.default_rng(7)
        values = rng.normal(size=(3, 5, 64)).astype(np.float32)
        calibration = Calibration()
        Calibration.record(calibration.surfaces, "x", values[:1])
        Calibration.record(calibration.surfaces, "x", values[1:])
        plan = calibration.plans()["x"]
        expected = fit_surface(values.reshape(-1, 64))
        np.testing.assert_array_equal(plan.step, expected.step)
        actual, clipped = apply_surface(values, plan)
        self.assertEqual(clipped, 0)
        self.assertLessEqual(float(np.max(np.abs(actual - values) / plan.step)), 0.501)

    def test_distribution_metrics_identical_and_nonidentical(self):
        logits = np.array([[1, 2, 3], [3, 2, 1]], np.float32)
        same = metrics(logits, logits, [2, 0])
        np.testing.assert_array_equal(same["kl"], 0)
        np.testing.assert_array_equal(same["tv"], 0)
        np.testing.assert_array_equal(same["agreement"], 1)
        changed = metrics(-logits, logits, [2, 0])
        self.assertTrue(np.all(changed["kl"] > 0))
        self.assertTrue(np.all(changed["nll"] > same["nll"]))

    def test_repetition(self):
        self.assertEqual(repetition([])["repeated_4gram_fraction"], 0)
        self.assertEqual(repetition([1] * 8)["longest_identical_token_run"], 8)
        self.assertEqual(repetition([1] * 8)["repeated_4gram_fraction"], 0.8)
        self.assertEqual(repetition(list(range(8)))["repeated_4gram_fraction"], 0)


@unittest.skipUnless(
    (Path(__file__).resolve().parents[1] / "data/gpt2/model.safetensors").exists(),
    "local GPT-2 checkpoint required",
)
class CheckpointIntegrationTests(unittest.TestCase):
    def test_causality_and_svg_legacy_agreement(self):
        checkpoint = load_model()
        calibration = Calibration()
        reference = Model(checkpoint)
        reference.trace = calibration
        ids = [15496, 11, 616, 1438, 318]  # Hello, my name is
        full, _ = reference.hidden([ids])
        reference.trace = None
        short, _ = reference.hidden([ids[:3]])
        np.testing.assert_allclose(full[:, :3], short, rtol=0, atol=0.0003)
        model = Model(checkpoint, "svg", calibration)
        blocks = [
            replace(
                block,
                qkv_weight=model.weights[f"b{i}.qkv"],
                attention_projection_weight=model.weights[f"b{i}.attention"],
                fc_weight=model.weights[f"b{i}.fc"],
                mlp_projection_weight=model.weights[f"b{i}.projection"],
            )
            for i, block in enumerate(checkpoint[2])
        ]
        legacy = Runner(
            checkpoint[0],
            checkpoint[1],
            blocks,
            checkpoint[3],
            checkpoint[4],
            plans=model.plans,
            output_embedding=model.weights["head"].T,
        )
        hidden, _ = model.hidden([ids])
        actual = model.linear("head", hidden)[0]
        expected = np.stack([legacy.token(token) for token in ids])
        np.testing.assert_allclose(actual, expected, rtol=0, atol=0.002)
        self.assertEqual(actual.argmax(-1).tolist(), expected.argmax(-1).tolist())


if __name__ == "__main__":
    unittest.main()
