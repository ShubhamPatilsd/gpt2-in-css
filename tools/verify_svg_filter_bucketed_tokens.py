#!/usr/bin/env python3
"""Verify that the 12-block browser state preserves the reference token winners."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_full_gpt2 import MODEL_PATH, SafeTensors  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
BROWSER_OUTPUT = Path(
    os.environ.get("SVG_CHAIN_OUTPUT", "/tmp/svg-filter-bucketed-final.json")
)
REFERENCE = Path(
    os.environ.get(
        "SVG_CHAIN_REFERENCE",
        ROOT / "experiments" / "svg-filter-full-block" / "reference.json",
    )
)


def top_ids(weights: np.ndarray, vector: list[float], count: int = 5) -> list[int]:
    scores = weights @ np.asarray(vector, dtype=np.float64)
    return np.argsort(scores)[-count:][::-1].astype(int).tolist()


def main() -> None:
    browser = json.loads(BROWSER_OUTPUT.read_text())
    reference = json.loads(REFERENCE.read_text())
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight"), dtype=np.float64
    )
    cases = (
        (
            "original",
            browser["finalOriginal"],
            reference["bucket_final_ln_expected"],
            11,
        ),
        (
            "alternate",
            browser["finalAlternate"],
            reference["bucket_final_ln_expected_alt"],
            477,
        ),
    )
    report: dict[str, object] = {}
    for name, actual, expected, known_winner in cases:
        browser_top = top_ids(weights, actual)
        reference_top = top_ids(weights, expected)
        if reference_top[0] != known_winner:
            raise AssertionError(
                f"{name}: reference winner changed from {known_winner} "
                f"to {reference_top[0]}"
            )
        if browser_top[0] != reference_top[0]:
            raise AssertionError(
                f"{name}: browser winner {browser_top[0]} != "
                f"reference winner {reference_top[0]}"
            )
        report[name] = {
            "winner": browser_top[0],
            "browser_top5": browser_top,
            "reference_top5": reference_top,
        }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
