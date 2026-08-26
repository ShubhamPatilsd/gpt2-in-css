#!/usr/bin/env python3
"""Validate promising six-bit hidden transports on a larger held-out set."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_packed_activation_precision import (
    CASES,
    exact_forward,
    hidden_scheme_forward,
    load_checkpoint,
    reference_ranges,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "packed-activation-precision" / "log-validation.json"
CALIBRATION_CASES = 256
EVALUATION_CASES = 1024
NATURAL_CASES = 64
CONFIGURATIONS = (
    ("linear-asymmetric", 1.1),
    ("importance-asym-566", 1.1),
    ("log-asymmetric-0.5", 1.1),
    ("log-asymmetric-15", 1.5),
    ("log-asymmetric-4", 2.0),
    ("importance-asym-468", 1.1),
    ("importance-asym-567", 1.1),
    ("importance-asym-477", 1.1),
    ("sensitivity-asym-468", 1.1),
    ("sensitivity-asym-567", 1.1),
    ("sensitivity-asym-477", 1.1),
    ("importance-asym-3456", 1.1),
    ("importance-asym-3555", 1.1),
    ("importance-asym-4455", 1.1),
    ("sensitivity-asym-3456", 1.1),
    ("tiergroup-sensitivity-asym-3456", 1.1),
    ("tiergroup-sensitivity-asym-3456", 1.5),
    ("tiergroup-sensitivity-asym-3456", 2.0),
    ("tiercluster2-sensitivity-asym-3456", 1.1),
    ("tiercluster4-sensitivity-asym-3456", 1.1),
    ("tiercluster8-sensitivity-asym-3456", 1.1),
    ("tiercluster16-sensitivity-asym-3456", 1.1),
    ("tiercluster32-sensitivity-asym-3456", 1.1),
    ("sensitivity-asym-3555", 1.1),
    ("sensitivity-asym-4455", 1.1),
)


def winners(states: np.ndarray, embedding: np.ndarray, batch: int = 32) -> np.ndarray:
    result = []
    for start in range(0, len(states), batch):
        result.extend(np.argmax(states[start : start + batch] @ embedding.T, axis=1))
    return np.asarray(result, dtype=np.int64)


def main() -> None:
    payload = json.loads(CASES.read_text())
    natural_inputs = np.asarray(
        [case["input_expected"] for case in payload["cases"]], dtype=np.float64
    )
    _, embedding, blocks, final_gamma, final_beta = load_checkpoint()
    position = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wpe.weight")[0], dtype=np.float64
    )
    natural_ids = {int(case["token_id"]) for case in payload["cases"]}
    candidates = np.asarray(
        [index for index in range(len(embedding)) if index not in natural_ids],
        dtype=np.int64,
    )
    rng = np.random.default_rng(0x4C4F4756)
    sampled = rng.choice(
        candidates,
        size=CALIBRATION_CASES + EVALUATION_CASES - NATURAL_CASES,
        replace=False,
    )
    calibration = embedding[sampled[:CALIBRATION_CASES]] + position
    evaluation = np.concatenate((
        natural_inputs[:NATURAL_CASES],
        embedding[sampled[CALIBRATION_CASES:]] + position,
    ))
    expected = exact_forward(evaluation, blocks, final_gamma, final_beta)
    expected_winners = winners(expected, embedding)
    rows = []
    ranges_by_headroom = {
        headroom: reference_ranges(calibration, blocks, headroom)
        for headroom in sorted({configuration[1] for configuration in CONFIGURATIONS})
    }
    for scheme, headroom in CONFIGURATIONS:
        actual, clipped, total = hidden_scheme_forward(
            evaluation,
            blocks,
            final_gamma,
            final_beta,
            ranges_by_headroom[headroom],
            6,
            scheme,
        )
        actual_winners = winners(actual, embedding)
        error = actual - expected
        rows.append({
            "scheme": scheme,
            "headroom": headroom,
            "winnerMatches": int(np.count_nonzero(actual_winners == expected_winners)),
            "winnerMatchFraction": float(np.mean(actual_winners == expected_winners)),
            "naturalWinnerMatches": int(np.count_nonzero(
                actual_winners[:NATURAL_CASES] == expected_winners[:NATURAL_CASES]
            )),
            "naturalWinnerMatchFraction": float(np.mean(
                actual_winners[:NATURAL_CASES] == expected_winners[:NATURAL_CASES]
            )),
            "finalHiddenRmse": float(np.sqrt(np.mean(error**2))),
            "clippedFraction": float(clipped / total),
        })
    result = {
        "calibrationCases": CALIBRATION_CASES,
        "evaluationCases": EVALUATION_CASES,
        "naturalCases": NATURAL_CASES,
        "scope": "All 12 GPT-2-small blocks; only post-GELU hidden vectors quantized",
        "results": rows,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
