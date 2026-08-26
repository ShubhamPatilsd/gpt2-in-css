#!/usr/bin/env python3
"""Screen selective higher-precision coarse groups for the production head."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_groupwise_cauchy_head import upper_block_norms


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
FINE = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane" / "reference.json"
OUTPUT = ROOT / "experiments" / "gpt2-groupwise-precision-allocation"
VOCABULARY = 50_257
WIDTH = 768
GROUP_SIZE = 256
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
BLOCK_WIDTH = 8
BLOCKS = WIDTH // BLOCK_WIDTH
AXIS_STEPS = 16_384
HOT_GROUPS = (0, 1)
HOT_ALLOWANCE = 24
STOP_GAP = 49
BATCH = 32
SELECTIVE_COUNTS = (2, 4, 8, 16, 32, 64, 96, 128, 195)
CORRECTION_SHARD_WIDTHS = (256, 192, 160, 128, 96, 64, 48, 32)
TWO_PLANE_RADICES = (64, 128, 256)


def distribution(values: np.ndarray) -> dict[str, float | int]:
    return {
        "mean": float(np.mean(values)),
        "minimum": int(np.min(values)),
        "median": int(np.percentile(values, 50, method="higher")),
        "p95": int(np.percentile(values, 95, method="higher")),
        "p99": int(np.percentile(values, 99, method="higher")),
        "maximum": int(np.max(values)),
    }


def stopping_counts(
    upper: np.ndarray, exact: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(-upper, axis=1, kind="stable")
    ordered_upper = np.take_along_axis(upper, order, axis=1)
    ordered_exact = np.take_along_axis(exact, order, axis=1)
    incumbent = np.maximum.accumulate(ordered_exact, axis=1)
    done = incumbent[:, :-1] - ordered_upper[:, 1:] > STOP_GAP
    has_done = np.any(done, axis=1)
    counts = np.where(
        has_done, np.argmax(done, axis=1) + 1, GROUPS
    ).astype(np.int64)
    return counts, order


def summarized(counts: np.ndarray) -> dict[str, object]:
    return {
        "groups": distribution(counts),
        "withinOne": int(np.sum(counts <= 1)),
        "withinSix": int(np.sum(counts <= 6)),
        "withinTwelve": int(np.sum(counts <= 12)),
        "withinTwentyThree": int(np.sum(counts <= 23)),
        "tailExcessAfterSix": int(np.sum(np.maximum(counts - 6, 0))),
    }


def group_upper_for_bits(
    bits: int,
    weights: np.ndarray,
    target: np.ndarray,
    realized: np.ndarray,
    query_block_norms: np.ndarray,
    score_gain: float,
    exact_group_buckets: np.ndarray,
) -> tuple[np.ndarray, dict[str, object]]:
    maximum = 2 ** (bits - 1) - 1
    row_scales = np.max(np.abs(weights), axis=1) / maximum
    row_scales[row_scales == 0] = 1.0
    represented = (
        np.rint(weights / row_scales[:, None]).clip(-maximum, maximum)
        * row_scales[:, None]
    )
    residual = target - represented
    row_norms = upper_block_norms(residual, BLOCK_WIDTH)
    padding = GROUPS * GROUP_SIZE - VOCABULARY
    padded_norms = np.pad(row_norms, ((0, padding), (0, 0)))
    group_norms = np.nextafter(
        np.max(padded_norms.reshape(GROUPS, GROUP_SIZE, BLOCKS), axis=1),
        np.inf,
    )
    radius = query_block_norms @ group_norms.T
    upper = np.empty((len(realized), GROUPS), dtype=np.int64)
    padded_rows = GROUPS * GROUP_SIZE
    for start in range(0, len(realized), BATCH):
        stop = min(start + BATCH, len(realized))
        scores = realized[start:stop] @ represented.T * score_gain
        padded = np.full((stop - start, padded_rows), -np.inf)
        padded[:, :VOCABULARY] = scores
        group_scores = padded.reshape(stop - start, GROUPS, GROUP_SIZE).max(axis=2)
        upper[start:stop] = (
            np.floor(group_scores * 256).astype(np.int64)
            + 1
            + np.ceil(radius[start:stop] * score_gain * 256).astype(np.int64)
        )
    upper[:, list(HOT_GROUPS)] = (
        exact_group_buckets[:, list(HOT_GROUPS)] + HOT_ALLOWANCE
    )
    metadata = {
        "bits": bits,
        "residualRmse": float(np.sqrt(np.mean(residual * residual))),
        "groupResidualNormMaximum": float(np.max(group_norms)),
        "rowCodeAbsoluteMaximum": maximum,
        "rowBaseMaximumAt256Axes": int(
            np.max(np.sum(np.abs(np.rint(weights / row_scales[:, None])), axis=1))
        ),
    }
    return upper, metadata


def strategy(
    name: str,
    selected: np.ndarray,
    precision_bits: int,
    baseline_upper: np.ndarray,
    upgraded_upper: np.ndarray,
    exact: np.ndarray,
    correction_codes: np.ndarray,
    upgraded_codes: np.ndarray,
) -> dict[str, object]:
    allocated = baseline_upper.copy()
    allocated[:, selected] = upgraded_upper[:, selected]
    counts, _order = stopping_counts(allocated, exact)
    selected_rows = np.concatenate([
        np.arange(
            group * GROUP_SIZE,
            min((group + 1) * GROUP_SIZE, VOCABULARY),
            dtype=np.int64,
        )
        for group in selected
    ])
    shard_screens = []
    for shard_width in CORRECTION_SHARD_WIDTHS:
        maximum_l1 = 0
        for start in range(0, WIDTH, shard_width):
            stop = min(start + shard_width, WIDTH)
            maximum_l1 = max(
                maximum_l1,
                int(np.max(np.sum(
                    np.abs(correction_codes[selected_rows, start:stop]).astype(
                        np.int64
                    ),
                    axis=1,
                ))),
            )
        shards = math.ceil(WIDTH / shard_width)
        shard_screens.append({
            "shardDimensions": shard_width,
            "shardsPerRow": shards,
            "maximumShardL1": maximum_l1,
            "maximumBaseAdvance": maximum_l1 + 32,
            "maximumShapedAdvance": 2 * maximum_l1 + 32,
            "fitsOpenTypeAdvance": 2 * maximum_l1 + 32 <= 65_535,
            "estimatedShapedGlyphs": int(len(selected_rows) * shards),
        })
    first_feasible = next(
        (item for item in shard_screens if item["fitsOpenTypeAdvance"]), None
    )
    replacement_screens = []
    for radix in TWO_PLANE_RADICES:
        selected_codes = upgraded_codes[selected_rows]
        high = np.trunc(selected_codes / radix).astype(np.int32)
        residual = selected_codes - high * radix
        if not np.array_equal(high * radix + residual, selected_codes):
            raise RuntimeError("two-plane replacement split is not exact")
        plane_reports = []
        for plane_name, plane in (("high", high), ("residual", residual)):
            maximum_l1 = 0
            for start in range(0, WIDTH, 256):
                stop = min(start + 256, WIDTH)
                maximum_l1 = max(
                    maximum_l1,
                    int(np.max(np.sum(
                        np.abs(plane[:, start:stop]).astype(np.int64), axis=1
                    ))),
                )
            plane_reports.append({
                "plane": plane_name,
                "codeAbsoluteMaximum": int(np.max(np.abs(plane))),
                "maximumShardL1": maximum_l1,
                "maximumBaseAdvance": maximum_l1 + 32,
                "maximumShapedAdvance": 2 * maximum_l1 + 32,
                "fitsStoredAdvance": maximum_l1 + 32 <= 65_535,
                "fitsShapedAdvance": 2 * maximum_l1 + 32 <= 65_535,
            })
        replacement_screens.append({
            "radix": radix,
            "shardDimensions": 256,
            "shardsPerPlane": 3,
            "planes": 2,
            "glyphsPerUpgradedRow": 6,
            "incrementalGlyphsPerUpgradedRowOverQ10": 3,
            "estimatedShapedGlyphs": int(len(selected_rows) * 6),
            "estimatedIncrementalShapedGlyphs": int(len(selected_rows) * 3),
            "allStoredAdvancesFit": all(
                item["fitsStoredAdvance"] for item in plane_reports
            ),
            "allShapedAdvancesFit": all(
                item["fitsShapedAdvance"] for item in plane_reports
            ),
            "planeReports": plane_reports,
        })
    return {
        "name": name,
        "precisionBits": precision_bits,
        "upgradedGroups": selected.astype(int).tolist(),
        "upgradedGroupCount": int(len(selected)),
        "additionalCoarseRows": int(len(selected_rows)),
        "correctionCodeAbsoluteMaximum": int(np.max(
            np.abs(correction_codes[selected_rows]).astype(np.int64)
        )),
        "correctionTransport": {
            "firstFeasible": first_feasible,
            "shardScreens": shard_screens,
        },
        "replacementTransport": {
            "strategy": "replace selected q10 rows with exact two-plane rowwise rows",
            "screens": replacement_screens,
        },
        **summarized(counts),
    }


def main() -> None:
    started = time.perf_counter()
    saved = np.load(STATES)
    hidden = np.asarray(saved["hidden"], dtype=np.float64)
    fine_reference = json.loads(FINE.read_text())
    source_range = float(fine_reference["inputRange"])
    production_range = float(np.max(np.abs(hidden))) * 1.01
    score_gain = source_range / production_range
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    query_block_norms = upper_block_norms(realized, BLOCK_WIDTH)
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float64,
    )
    fine_scale = float(fine_reference["weightScale"])
    target = np.rint(weights / fine_scale).astype(np.int16).astype(np.float64) * fine_scale
    row_maximums = np.max(np.abs(weights), axis=1)

    def codes_for_bits(bits: int) -> np.ndarray:
        maximum = 2 ** (bits - 1) - 1
        scales = row_maximums / maximum
        scales[scales == 0] = 1.0
        return np.rint(weights / scales[:, None]).clip(
            -maximum, maximum
        ).astype(np.int32)

    codes10 = codes_for_bits(10)
    codes11 = codes_for_bits(11)
    codes12 = codes_for_bits(12)
    correction11 = codes11 * 511 - codes10 * 1023
    correction12 = codes12 * 511 - codes10 * 2047

    exact_group_buckets = np.empty((len(hidden), GROUPS), dtype=np.int64)
    target_winners = np.empty(len(hidden), dtype=np.int64)
    padded_rows = GROUPS * GROUP_SIZE
    for start in range(0, len(hidden), BATCH):
        stop = min(start + BATCH, len(hidden))
        scores = realized[start:stop] @ target.T * score_gain
        target_winners[start:stop] = np.argmax(scores, axis=1)
        padded = np.full((stop - start, padded_rows), -np.inf)
        padded[:, :VOCABULARY] = scores
        groups = padded.reshape(stop - start, GROUPS, GROUP_SIZE).max(axis=2)
        exact_group_buckets[start:stop] = np.rint(groups * 256).astype(np.int64)

    upper10, metadata10 = group_upper_for_bits(
        10, weights, target, realized, query_block_norms, score_gain,
        exact_group_buckets,
    )
    upper11, metadata11 = group_upper_for_bits(
        11, weights, target, realized, query_block_norms, score_gain,
        exact_group_buckets,
    )
    upper12, metadata12 = group_upper_for_bits(
        12, weights, target, realized, query_block_norms, score_gain,
        exact_group_buckets,
    )
    counts10, order10 = stopping_counts(upper10, exact_group_buckets)
    counts11, _ = stopping_counts(upper11, exact_group_buckets)
    counts12, _ = stopping_counts(upper12, exact_group_buckets)
    tail = counts10 > 6

    visit_frequency = np.zeros(GROUPS, dtype=np.int64)
    tail_visit_frequency = np.zeros(GROUPS, dtype=np.int64)
    for sample, count in enumerate(counts10):
        visit_frequency[order10[sample, :count]] += 1
        if tail[sample]:
            tail_visit_frequency[order10[sample, :count]] += 1
    tightening = np.mean(upper10[tail] - upper11[tail], axis=0)
    candidates = np.arange(2, GROUPS, dtype=np.int64)
    by_tail_frequency = candidates[np.argsort(
        -tail_visit_frequency[candidates], kind="stable"
    )]
    by_tightening = candidates[np.argsort(-tightening[candidates], kind="stable")]

    selective = []
    selective12 = []
    for count in SELECTIVE_COUNTS:
        selective.append(strategy(
            f"tail-frequency-top-{count}",
            by_tail_frequency[:count], 11, upper10, upper11,
            exact_group_buckets, correction11, codes11,
        ))
        selective.append(strategy(
            f"tail-tightening-top-{count}",
            by_tightening[:count], 11, upper10, upper11,
            exact_group_buckets, correction11, codes11,
        ))
        selective12.append(strategy(
            f"tail-frequency-top-{count}",
            by_tail_frequency[:count], 12, upper10, upper12,
            exact_group_buckets, correction12, codes12,
        ))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "checkpointChanged": False,
        "states": len(hidden),
        "productionInputRange": production_range,
        "scoreGain": score_gain,
        "stopGapBuckets": STOP_GAP,
        "targetWinnerCount": int(len(target_winners)),
        "precisions": [metadata10, metadata11, metadata12],
        "correctionEncoding": {
            "q11MinusQ10": {
                "factorPerRow": "rowMaxAbs/(511*1023)",
                "integerCode": "q11Code*511-q10Code*1023",
                "absoluteMaximum": int(np.max(np.abs(correction11))),
            },
            "q12MinusQ10": {
                "factorPerRow": "rowMaxAbs/(511*2047)",
                "integerCode": "q12Code*511-q10Code*2047",
                "absoluteMaximum": int(np.max(np.abs(correction12))),
            },
        },
        "uniform": {
            "q10": summarized(counts10),
            "q11": summarized(counts11),
            "q12": summarized(counts12),
        },
        "baselineTailStates": int(np.sum(tail)),
        "rankings": {
            "tailVisitFrequency": [
                {"group": int(group), "visits": int(tail_visit_frequency[group])}
                for group in by_tail_frequency[:32]
            ],
            "meanUpperTighteningOnTail": [
                {"group": int(group), "buckets": float(tightening[group])}
                for group in by_tightening[:32]
            ],
        },
        "selectiveQ11": selective,
        "selectiveQ12": selective12,
        "seconds": time.perf_counter() - started,
    }
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "uniform": result["uniform"],
        "bestSelective": min(
            [*selective, *selective12],
            key=lambda item: (
                item["groups"]["maximum"],
                item["groups"]["p95"],
                item["groups"]["mean"],
                item["upgradedGroupCount"],
            ),
        ),
        "seconds": result["seconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
