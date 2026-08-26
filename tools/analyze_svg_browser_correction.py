#!/usr/bin/env python3
"""Cross-validate simple corrections fitted to real Chromium SVG outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


def score(embeddings: np.ndarray, values: np.ndarray, expected: np.ndarray) -> dict[str, object]:
    winners = np.argmax(values @ embeddings.T, axis=1)
    error = values - expected
    return {
        "winnerMatches": int(np.count_nonzero(winners == np.argmax(expected @ embeddings.T, axis=1))),
        "cases": len(values),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "maxError": float(np.max(np.abs(error))),
        "winnerIds": winners.astype(int).tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text())["cases"]
    captures = json.loads(args.captures.read_text())["outputs"]
    if len(cases) != len(captures):
        raise ValueError("case and capture counts differ")
    expected = np.asarray([case["expected"] for case in cases], dtype=np.float64)
    actual = np.asarray([capture["final"] for capture in captures], dtype=np.float64)
    embeddings = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight"), dtype=np.float64
    )

    corrected_bias = np.empty_like(actual)
    corrected_affine = np.empty_like(actual)
    fold_parameters: list[dict[str, object]] = []
    for parity in (0, 1):
        calibration = np.arange(parity, len(actual), 2)
        evaluation = np.arange(1 - parity, len(actual), 2)
        offset = np.mean(expected[calibration] - actual[calibration], axis=0)
        corrected_bias[evaluation] = actual[evaluation] + offset

        x = actual[calibration]
        y = expected[calibration]
        centered_x = x - np.mean(x, axis=0)
        centered_y = y - np.mean(y, axis=0)
        denominator = np.sum(centered_x**2, axis=0)
        slope = np.divide(
            np.sum(centered_x * centered_y, axis=0),
            denominator,
            out=np.ones_like(denominator),
            where=denominator > 1e-12,
        )
        slope = np.clip(slope, 0.5, 1.5)
        intercept = np.mean(y, axis=0) - slope * np.mean(x, axis=0)
        corrected_affine[evaluation] = actual[evaluation] * slope + intercept
        fold_parameters.append(
            {
                "calibrationParity": parity,
                "biasMin": float(np.min(offset)),
                "biasMax": float(np.max(offset)),
                "slopeMin": float(np.min(slope)),
                "slopeMax": float(np.max(slope)),
            }
        )

    payload = {
        "method": "two-fold correction fitted to real Chromium output vectors",
        "baseline": score(embeddings, actual, expected),
        "heldOutBias": score(embeddings, corrected_bias, expected),
        "heldOutDiagonalAffine": score(embeddings, corrected_affine, expected),
        "folds": fold_parameters,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: {k: v for k, v in value.items() if k != "winnerIds"}
                for key, value in payload.items()
                if isinstance(value, dict) and "winnerMatches" in value
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
