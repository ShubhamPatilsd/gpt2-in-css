#!/usr/bin/env python3
"""Production-range screen for the direct q16-minus-q10 groupwise cascade."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_groupwise_cauchy_head import upper_block_norms


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane" / "reference.json"
OUTPUT = ROOT / "experiments" / "gpt2-groupwise-cauchy-blockflow-cascade" / "offline-results.json"
VOCABULARY = 50_257
WIDTH = 768
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
BLOCK_COUNT = 96
BLOCK_WIDTH = 8
AXIS_STEPS = 16_384
HOT_GROUPS = (0, 1)
HOT_ALLOWANCE = 24
THRESHOLDS = (27, 48)
BATCH = 32


def distribution(values: np.ndarray) -> dict[str, float | int]:
    return {
        "mean": float(np.mean(values)),
        "minimum": int(np.min(values)),
        "median": int(np.median(values)),
        "p95": int(np.percentile(values, 95, method="higher")),
        "maximum": int(np.max(values)),
    }


def split_distribution(
    values: np.ndarray, saved: np.lib.npyio.NpzFile
) -> dict[str, object]:
    return {
        name: distribution(values[np.asarray(saved[f"{name}_ids"], dtype=np.int64)])
        for name in ("train", "validation", "test")
    }


def wave_schedule(
    counts: np.ndarray, prefix: int, wave_sizes: tuple[int, ...]
) -> dict[str, object]:
    boundaries = prefix + np.cumsum(np.asarray(wave_sizes, dtype=np.int64))
    if int(boundaries[-1]) < int(np.max(counts)):
        raise ValueError("wave schedule does not cover the observed tail")
    evaluated = counts.copy()
    score_merge_rounds = counts.copy()
    critical_levels = counts * 2
    tail = counts > prefix
    tail_wave = np.argmax(counts[tail, None] <= boundaries[None, :], axis=1)
    evaluated[tail] = boundaries[tail_wave]
    score_merge_rounds[tail] = prefix + tail_wave + 1
    critical_levels[tail] = (
        prefix * 2
        + (boundaries[tail_wave] - prefix)
        + tail_wave
        + 1
    )
    return {
        "prefix": prefix,
        "waveSizes": list(wave_sizes),
        "boundaries": boundaries.astype(int).tolist(),
        "tailStates": int(np.sum(tail)),
        "exactGroupsEvaluated": distribution(evaluated),
        "scoreMergeRounds": distribution(score_merge_rounds),
        "abstractCriticalLevels": distribution(critical_levels),
        "extraGroupsMean": float(np.mean(evaluated - counts)),
        "extraGroupsTotal": int(np.sum(evaluated - counts)),
    }


def main() -> None:
    if not STATES.exists() or not FINE.exists():
        raise FileNotFoundError("missing states or fine-head reference")
    saved = np.load(STATES)
    hidden = np.asarray(saved["hidden"], dtype=np.float64)
    fine_scale = float(json.loads(FINE.read_text())["weightScale"])
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float64,
    )
    target = np.rint(weights / fine_scale).astype(np.int16).astype(np.float64) * fine_scale
    row_scales = np.max(np.abs(weights), axis=1) / 511.0
    row_scales[row_scales == 0] = 1.0
    coarse = (
        np.rint(weights / row_scales[:, None]).clip(-511, 511)
        * row_scales[:, None]
    )
    residual = target - coarse
    row_norms = upper_block_norms(residual, BLOCK_WIDTH)
    padding = GROUPS * GROUP_SIZE - VOCABULARY
    padded_norms = np.pad(row_norms, ((0, padding), (0, 0)), constant_values=0.0)
    group_norms = np.nextafter(
        np.max(padded_norms.reshape(GROUPS, GROUP_SIZE, BLOCK_COUNT), axis=1),
        np.inf,
    )

    production_range = float(np.max(np.abs(hidden))) * 1.01
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    query_norms = upper_block_norms(realized, BLOCK_WIDTH)
    radius = query_norms @ group_norms.T
    group_sizes = np.minimum(
        GROUP_SIZE, VOCABULARY - np.arange(GROUPS) * GROUP_SIZE
    ).astype(np.int64)
    padded_rows = GROUPS * GROUP_SIZE
    upper_buckets = np.empty((len(hidden), GROUPS), dtype=np.int64)
    exact_group_buckets = np.empty_like(upper_buckets)
    coarse_group_scores = np.empty((len(hidden), GROUPS), dtype=np.float64)
    target_group_scores = np.empty_like(coarse_group_scores)
    target_winners = np.empty(len(hidden), dtype=np.int64)
    float_winners = np.empty(len(hidden), dtype=np.int64)

    for start in range(0, len(hidden), BATCH):
        stop = min(start + BATCH, len(hidden))
        query = realized[start:stop]
        coarse_scores = query @ coarse.T
        exact_scores = query @ target.T
        float_scores = query @ weights.T
        target_winners[start:stop] = np.argmax(exact_scores, axis=1)
        float_winners[start:stop] = np.argmax(float_scores, axis=1)

        coarse_padded = np.full((len(query), padded_rows), -np.inf)
        exact_padded = np.full_like(coarse_padded, -np.inf)
        coarse_padded[:, :VOCABULARY] = coarse_scores
        exact_padded[:, :VOCABULARY] = exact_scores
        coarse_group = coarse_padded.reshape(len(query), GROUPS, GROUP_SIZE).max(axis=2)
        exact_group = exact_padded.reshape(len(query), GROUPS, GROUP_SIZE).max(axis=2)
        exact_bucket = np.rint(exact_group * 256).astype(np.int64)
        upper = (
            np.floor(coarse_group * 256).astype(np.int64)
            + 1
            + np.ceil(radius[start:stop] * 256).astype(np.int64)
        )
        upper[:, list(HOT_GROUPS)] = exact_bucket[:, list(HOT_GROUPS)] + HOT_ALLOWANCE
        upper_buckets[start:stop] = upper
        exact_group_buckets[start:stop] = exact_bucket
        coarse_group_scores[start:stop] = coarse_group
        target_group_scores[start:stop] = exact_group

    winner_groups = target_winners // GROUP_SIZE
    target_group_upper = upper_buckets[np.arange(len(hidden)), winner_groups]
    target_group_exact = exact_group_buckets[np.arange(len(hidden)), winner_groups]
    retained = target_group_upper >= target_group_exact
    if not np.all(retained):
        raise RuntimeError("direct group certificate lost a target group")

    order = np.argsort(-upper_buckets, axis=1, kind="stable")
    ordered_upper = np.take_along_axis(upper_buckets, order, axis=1)
    ordered_exact = np.take_along_axis(exact_group_buckets, order, axis=1)
    incumbent = np.maximum.accumulate(ordered_exact, axis=1)
    cumulative_rows = np.cumsum(group_sizes[order], axis=1)
    threshold_results = {}
    browser_fixture_indices: list[int] = []
    counts_at_48: np.ndarray | None = None
    for threshold in THRESHOLDS:
        done = incumbent[:, :-1] - ordered_upper[:, 1:] > threshold
        has_done = np.any(done, axis=1)
        counts = np.where(has_done, np.argmax(done, axis=1) + 1, GROUPS).astype(np.int64)
        rows = cumulative_rows[np.arange(len(hidden)), counts - 1]
        prefix = 6
        fallback = counts > prefix
        prefix_best = incumbent[:, prefix - 1]
        remaining_order = order[:, prefix:]
        remaining_upper = np.take_along_axis(upper_buckets, remaining_order, axis=1)
        competitive = remaining_upper >= (prefix_best[:, None] - threshold)
        parallel_groups = np.sum(competitive, axis=1).astype(np.int64)
        parallel_rows = np.sum(group_sizes[remaining_order] * competitive, axis=1)
        prefix_rows = cumulative_rows[:, prefix - 1]
        closure_rows = prefix_rows + parallel_rows
        threshold_results[str(threshold)] = {
            "bestFirstExactGroups": split_distribution(counts, saved),
            "bestFirstExactRows": split_distribution(rows, saved),
            "statesStoppingWithinSix": int(np.sum(counts <= 6)),
            "statesStoppingWithinTwelve": int(np.sum(counts <= 12)),
            "overall": distribution(counts),
            "sixStageParallelClosure": {
                "fallbackStates": int(np.sum(fallback)),
                "competitiveGroupsOverall": distribution(parallel_groups),
                "competitiveGroupsOnFallback": distribution(parallel_groups[fallback]),
                "totalRowsOnFallback": distribution(closure_rows[fallback]),
            },
        }
        if threshold == 48:
            counts_at_48 = counts.copy()
            target_groups = target_winners // GROUP_SIZE
            candidates = [
                int(np.argmax(counts)),
                int(np.flatnonzero(counts == np.max(counts[counts <= 12]))[0]),
                int(np.flatnonzero(counts == np.max(counts[counts <= 6]))[0]),
                int(np.flatnonzero((counts == 1) & (target_groups == 0))[0]),
                int(np.flatnonzero((counts == 1) & (target_groups == 1))[0]),
                int(np.flatnonzero((counts == 1) & (target_groups > 1))[0]),
            ]
            browser_fixture_indices = list(dict.fromkeys(candidates))

    if counts_at_48 is None:
        raise RuntimeError("threshold 48 fixture counts were not computed")

    block_axis_range = math.sqrt(BLOCK_WIDTH) * production_range
    coefficients = np.ceil(group_norms * block_axis_range * 128.0)
    source_range = float(json.loads(FINE.read_text())["inputRange"])
    homogeneous_gain = source_range / production_range
    homogeneous_exact = np.rint(
        target_group_scores * homogeneous_gain * 256
    ).astype(np.int64)
    homogeneous_upper = (
        np.floor(coarse_group_scores * homogeneous_gain * 256).astype(np.int64)
        + 1
        + np.ceil(radius * homogeneous_gain * 256).astype(np.int64)
    )
    homogeneous_upper[:, list(HOT_GROUPS)] = (
        homogeneous_exact[:, list(HOT_GROUPS)] + HOT_ALLOWANCE
    )
    homogeneous_order = np.argsort(-homogeneous_upper, axis=1, kind="stable")
    homogeneous_ordered_upper = np.take_along_axis(
        homogeneous_upper, homogeneous_order, axis=1
    )
    homogeneous_ordered_exact = np.take_along_axis(
        homogeneous_exact, homogeneous_order, axis=1
    )
    homogeneous_incumbent = np.maximum.accumulate(
        homogeneous_ordered_exact, axis=1
    )
    homogeneous_stop_gap = 49
    homogeneous_done = (
        homogeneous_incumbent[:, :-1] - homogeneous_ordered_upper[:, 1:]
        > homogeneous_stop_gap
    )
    homogeneous_has_done = np.any(homogeneous_done, axis=1)
    homogeneous_counts = np.where(
        homogeneous_has_done,
        np.argmax(homogeneous_done, axis=1) + 1,
        GROUPS,
    ).astype(np.int64)
    homogeneous_wave_schedules = {
        "serial23": wave_schedule(homogeneous_counts, 23, (1,)),
        "prefix12Then11": wave_schedule(homogeneous_counts, 12, (11,)),
        "prefix8Then5Then10": wave_schedule(homogeneous_counts, 8, (5, 10)),
        "prefix7Then4Then12": wave_schedule(homogeneous_counts, 7, (4, 12)),
        "prefix6Then2Then4Then8Then3": wave_schedule(
            homogeneous_counts, 6, (2, 4, 8, 3)
        ),
        "prefix6Then4Then6Then7": wave_schedule(
            homogeneous_counts, 6, (4, 6, 7)
        ),
        "prefix6Then17": wave_schedule(homogeneous_counts, 6, (17,)),
    }
    result = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "target": (
            "global-int16 tied output weights at production-range F2DOT14-realized "
            "hidden coordinates, 1/256 score buckets, lower token id on ties"
        ),
        "targetMatchesOriginalFloatWinner": int(np.sum(target_winners == float_winners)),
        "states": len(hidden),
        "productionInputRange": production_range,
        "blockAxisRange": block_axis_range,
        "certificate": (
            "max_i h.q16_i <= max_i h.q10_i + "
            "sum_b ||h_b||_2 max_i ||(q16_i-q10_i)_b||_2"
        ),
        "winnerGroupsRetained": int(np.sum(retained)),
        "thresholds": threshold_results,
        "browserFixtureIndices": browser_fixture_indices,
        "browserFixtures": [
            {
                "stateIndex": index,
                "requiredGroupsAt48": int(counts_at_48[index]),
                "targetWinner": int(target_winners[index]),
            }
            for index in browser_fixture_indices
        ],
        "productionFontFeasibility": {
            "coefficientMaximum": int(coefficients.max()),
            "baseAdvanceMaximum": int(np.sum(coefficients, axis=1).max()),
            "coefficientFitsInt16": bool(coefficients.max() <= 32_767),
            "baseFitsUint16BeforeZeroBaseRewrite": bool(
                np.sum(coefficients, axis=1).max() <= 65_535
            ),
        },
        "homogeneousProductionRescale": {
            "sourceInputRange": source_range,
            "scoreGain": homogeneous_gain,
            "stopGapBuckets": homogeneous_stop_gap,
            "upperTransportShortfallBuckets": 1,
            "bestFirstExactGroups": split_distribution(homogeneous_counts, saved),
            "overall": distribution(homogeneous_counts),
            "statesStoppingWithinSix": int(np.sum(homogeneous_counts <= 6)),
            "statesStoppingWithinTwelve": int(np.sum(homogeneous_counts <= 12)),
            "statesStoppingWithinTwentyTwo": int(np.sum(homogeneous_counts <= 22)),
            "statesStoppingWithinTwentyThree": int(np.sum(homogeneous_counts <= 23)),
            "tailWaveSchedules": homogeneous_wave_schedules,
        },
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    np.save(OUTPUT.parent / "homogeneous-group-counts.npy", homogeneous_counts)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
