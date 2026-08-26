#!/usr/bin/env python3
"""Screen certified row-wise heads with browser axis and layout budgets."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
FINE_REFERENCE = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane"
    / "reference.json"
)
OUTPUT = ROOT / "experiments" / "gpt2-browser-certification-budget"
VOCABULARY = 50_257
WIDTH = 768
GROUP_SIZE = 256
SCORE_SCALE = 256
AXIS_STEPS = 16_384
SLACK_BUCKETS = (0, 8, 16, 24, 32)
GROUP_BUDGETS = (1, 2, 3, 4, 6, 8, 16, 32, 61)
BOUND_SCENARIOS = (
    {
        "name": "production-realized-coordinate-chromium-model",
        "target": "F2DOT14-realized hidden coordinates",
        "coarseSlackBuckets": 19,
        "fineSlackBuckets": 8,
    },
    {
        "name": "production-unrounded-coordinate-chromium-model",
        "target": "original unrounded hidden coordinates",
        "coarseSlackBuckets": 301,
        "fineSlackBuckets": 288,
    },
    {
        "name": "production-unrounded-coordinate-spec-model",
        "target": "original unrounded hidden coordinates",
        "coarseSlackBuckets": 367,
        "fineSlackBuckets": 364,
    },
)


def summary(values: np.ndarray) -> dict[str, float]:
    return {
        "minimum": float(np.min(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "maximum": float(np.max(values)),
        "mean": float(np.mean(values)),
    }


def coverage_by_group_budget(values: np.ndarray) -> dict[str, float]:
    return {
        str(budget): float(np.mean(values <= budget))
        for budget in GROUP_BUDGETS
    }


def best_first_counts(
    exact_scores: np.ndarray,
    upper_scores: np.ndarray,
    fine_slack: float,
) -> np.ndarray:
    samples, vocabulary = exact_scores.shape
    groups = math.ceil(vocabulary / GROUP_SIZE)
    padded = groups * GROUP_SIZE
    upper_padded = np.full((samples, padded), -np.inf, dtype=np.float32)
    exact_padded = np.full((samples, padded), -np.inf, dtype=np.float32)
    upper_padded[:, :vocabulary] = upper_scores
    exact_padded[:, :vocabulary] = exact_scores
    group_upper = upper_padded.reshape(samples, groups, GROUP_SIZE).max(axis=2)
    group_exact = exact_padded.reshape(samples, groups, GROUP_SIZE).max(axis=2)
    order = np.argsort(-group_upper, axis=1, kind="stable")
    counts = np.full(samples, groups, dtype=np.int32)
    for sample in range(samples):
        best = -np.inf
        for position, group in enumerate(order[sample]):
            best = max(best, float(group_exact[sample, group]))
            if position + 1 == groups:
                counts[sample] = groups
                break
            next_upper = float(group_upper[sample, order[sample, position + 1]])
            if best - fine_slack > next_upper:
                counts[sample] = position + 1
                break
    return counts


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    states = np.load(STATES)
    hidden = np.asarray(states["hidden"], dtype=np.float32)
    current_reference = json.loads(
        (ROOT / "experiments" / "gpt2-hvar-grid-output-head" / "reference.json").read_text()
    )
    current_range = float(current_reference["inputRange"])
    per_state_maximum = np.max(np.abs(hidden), axis=1)
    required_range = float(np.max(per_state_maximum) * 1.01)
    realized_hidden = (
        np.rint(hidden / required_range * AXIS_STEPS) / AXIS_STEPS * required_range
    ).astype(np.float32)
    axis_l2_bound = required_range * math.sqrt(WIDTH) / (2 * AXIS_STEPS)
    query_norm_upper = np.linalg.norm(hidden, axis=1) + axis_l2_bound

    fine_reference = json.loads(FINE_REFERENCE.read_text())
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float32,
    )
    fine_scale = float(fine_reference["weightScale"])
    target_weights = np.rint(weights / fine_scale).astype(np.int16).astype(np.float32)
    target_weights *= fine_scale
    exact_scores = realized_hidden @ target_weights.T
    dense_winners = (hidden @ weights.T).argmax(axis=1)
    target_winners = exact_scores.argmax(axis=1)

    encodings = []
    for bits in (10, 11):
        maximum_code = 2 ** (bits - 1) - 1
        row_scales = np.max(np.abs(target_weights), axis=1) / maximum_code
        row_scales[row_scales == 0] = 1.0
        codes = np.rint(target_weights / row_scales[:, None]).astype(np.int16)
        represented = codes.astype(np.float32) * row_scales[:, None]
        error_norms = np.linalg.norm(target_weights - represented, axis=1)
        coarse_scores = realized_hidden @ represented.T
        base_upper = coarse_scores + query_norm_upper[:, None] * error_norms[None, :]
        slack_results = []
        for slack_buckets in SLACK_BUCKETS:
            slack = slack_buckets / SCORE_SCALE
            counts = best_first_counts(
                exact_scores,
                base_upper + slack,
                fine_slack=slack,
            )
            slack_results.append({
                "coarseAndFineSlackBuckets": slack_buckets,
                "bestFirstGroups": summary(counts),
                "coverageByGroupBudget": coverage_by_group_budget(counts),
                "meanExactRows": float(np.mean(counts) * GROUP_SIZE),
                "denseReduction": float(VOCABULARY / (np.mean(counts) * GROUP_SIZE)),
            })
        bound_results = []
        for scenario in BOUND_SCENARIOS:
            coarse_slack = scenario["coarseSlackBuckets"] / SCORE_SCALE
            fine_slack = scenario["fineSlackBuckets"] / SCORE_SCALE
            counts = best_first_counts(
                exact_scores,
                base_upper + coarse_slack,
                fine_slack=fine_slack,
            )
            bound_results.append({
                **scenario,
                "requiredStopGapBuckets": (
                    scenario["coarseSlackBuckets"]
                    + scenario["fineSlackBuckets"]
                ),
                "bestFirstGroups": summary(counts),
                "coverageByGroupBudget": coverage_by_group_budget(counts),
                "meanExactRows": float(np.mean(counts) * GROUP_SIZE),
                "denseReduction": float(VOCABULARY / (np.mean(counts) * GROUP_SIZE)),
                "caveat": (
                    "Unrounded-coordinate scenarios bound cross-group stopping only; "
                    "they do not certify the browser-selected winner inside each "
                    "refined group without residual near-tie refinement."
                ),
            })
        encodings.append({
            "bits": bits,
            "weightRmseAgainstGlobalInt16Target": float(np.sqrt(np.mean(
                (represented - target_weights) ** 2
            ))),
            "approximateWinnerFraction": float(np.mean(
                coarse_scores.argmax(axis=1) == target_winners
            )),
            "slackScreens": slack_results,
            "boundScenarios": bound_results,
        })

    result = {
        "model": "openai-community/gpt2",
        "samples": len(hidden),
        "target": "global-int16 weights at F2DOT14-realized hidden coordinates",
        "currentInputRange": current_range,
        "statesInsideCurrentRange": int(np.sum(per_state_maximum <= current_range)),
        "requiredInputRange": required_range,
        "maximumObservedCoordinate": float(np.max(per_state_maximum)),
        "axisCoordinateStepAtRequiredRange": required_range / AXIS_STEPS,
        "axisL2ErrorBound": axis_l2_bound,
        "globalInt16TargetMatchesDenseFloat": int(np.sum(
            target_winners == dense_winners
        )),
        "encodings": encodings,
    }
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
