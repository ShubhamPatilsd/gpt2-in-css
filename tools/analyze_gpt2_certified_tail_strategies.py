#!/usr/bin/env python3
"""Analyze compact tails after a shallow certified GPT-2 output-head prefix."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
FINE_REFERENCE = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-global16-twoplane"
    / "reference.json"
)
OUTPUT = ROOT / "experiments" / "gpt2-certified-tail-strategies"
VOCABULARY = 50_257
WIDTH = 768
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
SCORE_SCALE = 256
AXIS_STEPS = 16_384
COARSE_ALLOWANCE_BUCKETS = 19
FINE_ALLOWANCE_BUCKETS = 8
PREFIXES = (4, 6, 8, 16)
BATCH_SIZES = (1, 2, 4, 8, 16)
MATRIX_BATCH = 32


def percentile(values: np.ndarray, q: float) -> float:
    return float(np.percentile(values, q, method="higher"))


def distribution(values: np.ndarray) -> dict[str, float | int | None]:
    if len(values) == 0:
        return {
            "count": 0,
            "minimum": None,
            "median": None,
            "p95": None,
            "maximum": None,
            "mean": None,
        }
    return {
        "count": int(len(values)),
        "minimum": int(np.min(values)),
        "median": percentile(values, 50),
        "p95": percentile(values, 95),
        "maximum": int(np.max(values)),
        "mean": float(np.mean(values)),
    }


def score_groups(
    hidden: np.ndarray,
    target_weights: np.ndarray,
    represented_weights: np.ndarray,
    error_norms: np.ndarray,
    query_norm_upper: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    group_exact = np.empty((len(hidden), GROUPS), dtype=np.float32)
    group_upper = np.empty_like(group_exact)
    target_winners = np.empty(len(hidden), dtype=np.int64)
    padded = GROUPS * GROUP_SIZE
    coarse_allowance = COARSE_ALLOWANCE_BUCKETS / SCORE_SCALE

    for start in range(0, len(hidden), MATRIX_BATCH):
        stop = min(start + MATRIX_BATCH, len(hidden))
        values = hidden[start:stop]
        exact = values @ target_weights.T
        coarse = values @ represented_weights.T
        upper = (
            coarse
            + query_norm_upper[start:stop, None] * error_norms[None, :]
            + coarse_allowance
        )
        target_winners[start:stop] = np.argmax(exact, axis=1)

        exact_padded = np.full((len(values), padded), -np.inf, dtype=np.float32)
        upper_padded = np.full_like(exact_padded, -np.inf)
        exact_padded[:, :VOCABULARY] = exact
        upper_padded[:, :VOCABULARY] = upper
        group_exact[start:stop] = exact_padded.reshape(
            len(values), GROUPS, GROUP_SIZE
        ).max(axis=2)
        group_upper[start:stop] = upper_padded.reshape(
            len(values), GROUPS, GROUP_SIZE
        ).max(axis=2)
        print(f"scored states {start}:{stop}", flush=True)

    return group_exact, group_upper, target_winners


def stopping_counts(
    ordered_upper: np.ndarray,
    ordered_exact: np.ndarray,
) -> np.ndarray:
    best_lower = (
        np.maximum.accumulate(ordered_exact, axis=1)
        - FINE_ALLOWANCE_BUCKETS / SCORE_SCALE
    )
    done = best_lower[:, :-1] > ordered_upper[:, 1:]
    has_done = np.any(done, axis=1)
    return np.where(
        has_done,
        np.argmax(done, axis=1) + 1,
        ordered_upper.shape[1],
    ).astype(np.int64)


def main() -> None:
    if not STATES.exists():
        raise RuntimeError("missing the 1,024-state router corpus")
    if not FINE_REFERENCE.exists():
        raise RuntimeError("missing the global-int16 fine-head reference")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    saved = np.load(STATES)
    hidden = np.asarray(saved["hidden"], dtype=np.float32)
    if len(hidden) != 1_024 or hidden.shape[1] != WIDTH:
        raise RuntimeError(f"unexpected state matrix shape: {hidden.shape}")

    maximum_coordinate = float(np.max(np.abs(hidden)))
    production_range = maximum_coordinate * 1.01
    realized_hidden = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    ).astype(np.float32)
    axis_l2_bound = production_range * math.sqrt(WIDTH) / (2 * AXIS_STEPS)
    query_norm_upper = np.linalg.norm(hidden, axis=1) + axis_l2_bound

    fine_reference = json.loads(FINE_REFERENCE.read_text())
    fine_scale = float(fine_reference["weightScale"])
    float_weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float32,
    )
    fine_codes = np.rint(float_weights / fine_scale).astype(np.int16)
    target_weights = fine_codes.astype(np.float32) * fine_scale

    maximum_code = 2 ** (10 - 1) - 1
    row_scales = np.max(np.abs(target_weights), axis=1) / maximum_code
    row_scales[row_scales == 0] = 1.0
    coarse_codes = np.rint(target_weights / row_scales[:, None]).astype(np.int16)
    represented_weights = coarse_codes.astype(np.float32) * row_scales[:, None]
    error_norms = np.linalg.norm(target_weights - represented_weights, axis=1)

    group_exact, group_upper, target_winners = score_groups(
        realized_hidden,
        target_weights,
        represented_weights,
        error_norms,
        query_norm_upper,
    )
    order = np.argsort(-group_upper, axis=1, kind="stable")
    ordered_upper = np.take_along_axis(group_upper, order, axis=1)
    ordered_exact = np.take_along_axis(group_exact, order, axis=1)
    stop_counts = stopping_counts(ordered_upper, ordered_exact)
    target_groups = target_winners // GROUP_SIZE
    group_sizes = np.minimum(
        GROUP_SIZE,
        VOCABULARY - np.arange(GROUPS) * GROUP_SIZE,
    ).astype(np.int64)

    prefix_results: list[dict[str, object]] = []
    all_retained = True
    for prefix in PREFIXES:
        fallback = stop_counts > prefix
        fallback_indices = np.flatnonzero(fallback)
        parallel_groups = np.zeros(len(hidden), dtype=np.int64)
        parallel_rows = np.zeros(len(hidden), dtype=np.int64)
        total_rows = np.zeros(len(hidden), dtype=np.int64)
        sequential_groups = np.maximum(stop_counts - prefix, 0)
        retained = np.ones(len(hidden), dtype=bool)
        closure_certified = np.ones(len(hidden), dtype=bool)

        for sample in fallback_indices:
            prefix_best_lower = (
                float(np.max(ordered_exact[sample, :prefix]))
                - FINE_ALLOWANCE_BUCKETS / SCORE_SCALE
            )
            remaining_order = order[sample, prefix:]
            active = group_upper[sample, remaining_order] >= prefix_best_lower
            candidate_groups = remaining_order[active]
            parallel_groups[sample] = len(candidate_groups)
            parallel_rows[sample] = int(np.sum(group_sizes[candidate_groups]))
            total_rows[sample] = int(
                np.sum(group_sizes[order[sample, :prefix]])
                + parallel_rows[sample]
            )
            retained[sample] = bool(
                target_groups[sample] in order[sample, :prefix]
                or target_groups[sample] in candidate_groups
            )

            excluded = remaining_order[~active]
            final_best_lower = (
                max(
                    float(np.max(ordered_exact[sample, :prefix])),
                    float(np.max(group_exact[sample, candidate_groups])),
                )
                - FINE_ALLOWANCE_BUCKETS / SCORE_SCALE
            )
            closure_certified[sample] = bool(
                len(excluded) == 0
                or final_best_lower > float(np.max(group_upper[sample, excluded]))
            )

        if not np.all(retained):
            lost = np.flatnonzero(~retained).tolist()
            raise RuntimeError(f"K={prefix} candidate closure lost target groups: {lost}")
        if not np.all(closure_certified):
            failed = np.flatnonzero(~closure_certified).tolist()
            raise RuntimeError(f"K={prefix} parallel closure did not certify: {failed}")
        all_retained = all_retained and bool(np.all(retained))

        fixed_batches = []
        batched_best_first = []
        for batch_size in BATCH_SIZES:
            tested = min(prefix + batch_size, GROUPS)
            residual = stop_counts > tested
            fixed_batches.append({
                "additionalGroups": batch_size,
                "totalPrefixGroups": tested,
                "residualFallbackStates": int(np.sum(residual)),
                "residualFallbackRateOverall": float(np.mean(residual)),
                "residualFallbackRateConditionalOnPrefixFallback": (
                    float(np.sum(residual) / len(fallback_indices))
                    if len(fallback_indices)
                    else 0.0
                ),
            })

            needed_groups = np.maximum(stop_counts - prefix, 0)
            batch_counts = np.ceil(needed_groups / batch_size).astype(np.int64)
            scored_groups = np.minimum(
                batch_counts * batch_size,
                GROUPS - prefix,
            )
            overcomputed_groups = scored_groups - needed_groups
            # A batch performs B serial cheap upper routers, then one parallel
            # exact-score/merge wave. This is an abstract dependency-depth
            # model; it intentionally does not claim wall-clock latency.
            critical_levels = scored_groups + batch_counts
            maximum_needed = int(np.max(needed_groups))
            maximum_batches = math.ceil(maximum_needed / batch_size)
            batched_best_first.append({
                "batchSize": batch_size,
                "batchesOverall": distribution(batch_counts),
                "batchesConditionalOnPrefixFallback": distribution(
                    batch_counts[fallback]
                ),
                "groupsScoredOverall": distribution(scored_groups),
                "groupsScoredConditionalOnPrefixFallback": distribution(
                    scored_groups[fallback]
                ),
                "overcomputedGroupsConditionalOnPrefixFallback": distribution(
                    overcomputed_groups[fallback]
                ),
                "abstractCriticalLevelsConditionalOnPrefixFallback": distribution(
                    critical_levels[fallback]
                ),
                "corpusMaximum": {
                    "additionalGroupsActuallyNeeded": maximum_needed,
                    "batches": maximum_batches,
                    "staticFineScorers": min(
                        maximum_needed,
                        maximum_batches * batch_size,
                    ),
                    "abstractCriticalLevels": maximum_needed + maximum_batches,
                    "serialGroupThenScoreLevels": 2 * maximum_needed,
                },
            })

        prefix_rows = np.sum(group_sizes[order[:, :prefix]], axis=1)
        prefix_results.append({
            "prefixGroups": prefix,
            "certifiedAtPrefixStates": int(np.sum(~fallback)),
            "certifiedAtPrefixRate": float(np.mean(~fallback)),
            "fallbackStates": int(np.sum(fallback)),
            "fallbackRate": float(np.mean(fallback)),
            "parallelUncertaintyClosure": {
                "additionalCandidateGroupsOverall": distribution(parallel_groups),
                "additionalCandidateGroupsConditionalOnFallback": distribution(
                    parallel_groups[fallback]
                ),
                "additionalExactRowsOverall": distribution(parallel_rows),
                "additionalExactRowsConditionalOnFallback": distribution(
                    parallel_rows[fallback]
                ),
                "totalExactRowsIncludingPrefixOverall": distribution(
                    prefix_rows + parallel_rows
                ),
                "totalExactRowsIncludingPrefixConditionalOnFallback": distribution(
                    total_rows[fallback]
                ),
                "targetWinnerRetainedStates": int(np.sum(retained)),
                "closureCertifiedStates": int(np.sum(closure_certified)),
            },
            "sequentialBestFirstTail": {
                "additionalGroupsOverall": distribution(sequential_groups),
                "additionalGroupsConditionalOnFallback": distribution(
                    sequential_groups[fallback]
                ),
            },
            "fixedNextBatches": fixed_batches,
            "repeatedBatchedBestFirstTail": batched_best_first,
        })

    result = {
        "model": "openai-community/gpt2",
        "samples": len(hidden),
        "target": "global-int16 weights at F2DOT14-realized hidden coordinates",
        "realization": "nearest F2DOT14 grid, matching the retained production analyzer",
        "productionInputRange": production_range,
        "maximumObservedCoordinate": maximum_coordinate,
        "coarseEncoding": "row-wise signed int10",
        "groupSize": GROUP_SIZE,
        "groups": GROUPS,
        "coarseAllowanceBuckets": COARSE_ALLOWANCE_BUCKETS,
        "fineAllowanceBuckets": FINE_ALLOWANCE_BUCKETS,
        "requiredStopGapBuckets": (
            COARSE_ALLOWANCE_BUCKETS + FINE_ALLOWANCE_BUCKETS
        ),
        "bestFirstGroups": distribution(stop_counts),
        "targetWinnerRetainedByEveryCandidateClosure": all_retained,
        "prefixes": prefix_results,
    }
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
