#!/usr/bin/env python3
"""Measure whether two independently quantized SVG chains can be ensembled.

The two browser captures use the same GPT-2 inputs and model but different
range calibration.  Their 768-value final states are mixed before the tied
output head.  A single global alpha is screened, including cross-validation,
so the experiment does not add prompt- or coordinate-specific corrections.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-quantization-ensemble"
CASES = Path(
    os.environ.get(
        "SVG_ENSEMBLE_CASES", "/tmp/gpt2-css-natural-cases.eSHoiy/cases.json"
    )
)
STANDARD = Path(
    os.environ.get(
        "SVG_ENSEMBLE_STANDARD",
        "/tmp/svg-filter-prompt-robustness-natural64.json",
    )
)
CALIBRATED = Path(
    os.environ.get(
        "SVG_ENSEMBLE_CALIBRATED",
        "/tmp/svg-filter-prompt-robustness-natural64-batch.json",
    )
)
ALPHAS = np.linspace(0.0, 1.0, 101)


def load_outputs(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text())["outputs"]


def evaluate(
    states: np.ndarray,
    expected: np.ndarray,
    expected_winners: np.ndarray,
    logits: np.ndarray,
) -> dict[str, object]:
    winners = np.argmax(logits, axis=1)
    errors = states - expected
    sorted_logits = np.partition(logits, -2, axis=1)[:, -2:]
    margins = sorted_logits[:, 1] - sorted_logits[:, 0]
    return {
        "matches": int(np.count_nonzero(winners == expected_winners)),
        "accuracy": float(np.mean(winners == expected_winners)),
        "meanRmse": float(np.mean(np.sqrt(np.mean(errors**2, axis=1)))),
        "globalRmse": float(np.sqrt(np.mean(errors**2))),
        "maximumAbsError": float(np.max(np.abs(errors))),
        "meanPredictedMargin": float(np.mean(margins)),
        "winners": winners.astype(int).tolist(),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = json.loads(CASES.read_text())["cases"]
    standard_rows = load_outputs(STANDARD)
    calibrated_rows = load_outputs(CALIBRATED)
    if not (len(cases) == len(standard_rows) == len(calibrated_rows)):
        raise ValueError("case and capture counts differ")
    for case, standard, calibrated in zip(
        cases, standard_rows, calibrated_rows, strict=True
    ):
        ids = {case["token_id"], standard["token_id"], calibrated["token_id"]}
        if len(ids) != 1:
            raise ValueError(f"capture order mismatch: {ids}")

    exact = np.asarray([case["expected"] for case in cases], dtype=np.float64)
    expected_winners = np.asarray(
        [case["expected_winner"] for case in cases], dtype=np.int64
    )
    standard = np.asarray(
        [row["final"] for row in standard_rows], dtype=np.float64
    )
    calibrated = np.asarray(
        [row["final"] for row in calibrated_rows], dtype=np.float64
    )
    embeddings = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight"), dtype=np.float64
    )
    standard_logits = standard @ embeddings.T
    calibrated_logits = calibrated @ embeddings.T

    sweep = []
    for alpha in ALPHAS:
        mixed = (1 - alpha) * standard + alpha * calibrated
        logits = (1 - alpha) * standard_logits + alpha * calibrated_logits
        result = evaluate(mixed, exact, expected_winners, logits)
        sweep.append(
            {
                "alphaCalibrated": float(alpha),
                "matches": result["matches"],
                "accuracy": result["accuracy"],
                "globalRmse": result["globalRmse"],
            }
        )
    best = max(
        sweep,
        key=lambda item: (item["matches"], -item["globalRmse"]),
    )

    # Eight deterministic folds. Select alpha on seven folds and report only
    # the held-out winners, preventing the global mixture from being judged
    # solely on the same examples that selected it.
    folds = np.arange(len(cases)) % 8
    held_out_predictions = np.empty(len(cases), dtype=np.int64)
    cross_validation = []
    for fold in range(8):
        train = folds != fold
        test = folds == fold
        candidates = []
        for alpha in ALPHAS:
            result = evaluate(
                (1 - alpha) * standard[train] + alpha * calibrated[train],
                exact[train],
                expected_winners[train],
                (1 - alpha) * standard_logits[train]
                + alpha * calibrated_logits[train],
            )
            candidates.append((result["matches"], -result["globalRmse"], alpha))
        _, _, selected_alpha = max(candidates)
        test_result = evaluate(
            (1 - selected_alpha) * standard[test]
            + selected_alpha * calibrated[test],
            exact[test],
            expected_winners[test],
            (1 - selected_alpha) * standard_logits[test]
            + selected_alpha * calibrated_logits[test],
        )
        held_out_predictions[test] = np.asarray(test_result["winners"], dtype=np.int64)
        cross_validation.append(
            {
                "fold": fold,
                "selectedAlphaCalibrated": float(selected_alpha),
                "testMatches": test_result["matches"],
                "testCount": int(np.count_nonzero(test)),
            }
        )

    standard_result = evaluate(
        standard, exact, expected_winners, standard_logits
    )
    calibrated_result = evaluate(
        calibrated, exact, expected_winners, calibrated_logits
    )
    midpoint_result = evaluate(
        0.5 * standard + 0.5 * calibrated,
        exact,
        expected_winners,
        0.5 * standard_logits + 0.5 * calibrated_logits,
    )
    best_result = evaluate(
        (1 - best["alphaCalibrated"]) * standard
        + best["alphaCalibrated"] * calibrated,
        exact,
        expected_winners,
        (1 - best["alphaCalibrated"]) * standard_logits
        + best["alphaCalibrated"] * calibrated_logits,
    )
    cross_validated_matches = int(
        np.count_nonzero(held_out_predictions == expected_winners)
    )
    payload = {
        "cases": len(cases),
        "representation": "one global weighted average of two 768-value SVG final states",
        "standard": standard_result,
        "calibrated": calibrated_result,
        "midpoint": midpoint_result,
        "bestGlobal": {
            "alphaCalibrated": best["alphaCalibrated"],
            **best_result,
        },
        "eightFoldCrossValidation": {
            "matches": cross_validated_matches,
            "accuracy": cross_validated_matches / len(cases),
            "folds": cross_validation,
        },
        "sweep": sweep,
        "sources": {
            "cases": str(CASES),
            "standard": str(STANDARD),
            "calibrated": str(CALIBRATED),
        },
    }
    (OUT / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(
        json.dumps(
            {
                "standard": {
                    "matches": standard_result["matches"],
                    "globalRmse": standard_result["globalRmse"],
                },
                "calibrated": {
                    "matches": calibrated_result["matches"],
                    "globalRmse": calibrated_result["globalRmse"],
                },
                "midpoint": {
                    "matches": midpoint_result["matches"],
                    "globalRmse": midpoint_result["globalRmse"],
                },
                "bestGlobal": {
                    "alphaCalibrated": best["alphaCalibrated"],
                    "matches": best_result["matches"],
                    "globalRmse": best_result["globalRmse"],
                },
                "crossValidatedMatches": cross_validated_matches,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
