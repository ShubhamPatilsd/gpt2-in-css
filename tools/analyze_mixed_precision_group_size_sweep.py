#!/usr/bin/env python3
"""Offline group-size/score-stride sweep for the mixed exact-upper head.

This script intentionally does not launch a browser.  It replays the retained
Chromium-realized coordinate contract on the 1,024-state corpus while changing
only the grouping and the number of contiguous low-token groups whose existing
int10 rows are replaced in place by global-int16 rows.
"""

from __future__ import annotations

import json
import math
import sys
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_certified_tail_strategies import AXIS_STEPS, STATES


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-mixed-precision-group-size-sweep"
FINE_REFERENCE = (
    ROOT
    / "experiments"
    / "gpt2-hvar-grid-output-head-global16-twoplane"
    / "reference.json"
)
RETAINED_REFERENCE = (
    ROOT / "experiments" / "gpt2-mixed-precision-hot2-upper" / "reference.json"
)
SCORE_SCALE = 256
LAYOUT_UNITS_PER_PX = 64
ALLOWANCE_BUCKETS_PER_SIDE = 24
STOP_GAP_BUCKETS = 2 * ALLOWANCE_BUCKETS_PER_SIDE
STAGES = 6
CSS_LAYOUT_LIMIT_PX = 33_554_432


@dataclass(frozen=True)
class Variant:
    group_size: int
    score_stride_px: int
    hot_groups: int

    @property
    def groups(self) -> int:
        return math.ceil(head.VOCABULARY / self.group_size)

    @property
    def exact_upper_rows(self) -> int:
        return min(head.VOCABULARY, self.group_size * self.hot_groups)

    @property
    def name(self) -> str:
        return f"g{self.group_size}-s{self.score_stride_px}"


VARIANTS = (
    Variant(128, 4, 4),
    Variant(256, 4, 2),
    Variant(512, 8, 1),
    # One 1,024-row group is the smallest nonzero deployable exact prefix, so
    # this necessarily makes 1,024 rather than approximately 512 rows exact.
    Variant(1024, 16, 1),
)

G128_TRANSPORT_STRIDES = (8, 16, 32)


def g128_transport_sweep(result: dict[str, object]) -> dict[str, object]:
    """Append stride-only transport rows without changing offline ordering."""
    baseline = next(
        row for row in result["variants"] if row["name"] == "g128-s4"
    )
    rows: list[dict[str, object]] = []
    for stride in G128_TRANSPORT_STRIDES:
        row = deepcopy(baseline)
        row["name"] = f"g128-s{stride}"
        row["scoreStridePx"] = stride
        row["stridePerTokenPx"] = stride / 128
        tie_step = stride / 128
        tie_max = 127 * tie_step
        row["tieContract"] = {
            **row["tieContract"],
            "scoreBucketStridePx": stride,
            "tieStepPx": tie_step,
            "layoutUnitsPerToken": tie_step * LAYOUT_UNITS_PER_PX,
            "tiePayloadMaximumPx": tie_max,
            "unusedTieSpacePx": stride - 128 * tie_step,
            "decode": (
                f"local=127-round(mod(width,{stride}px)/{tie_step:g}px)"
            ),
        }
        widths = deepcopy(row["widthRanges"])
        for key in ("fineCandidateBucketComponent", "mixedGroupUpper"):
            width = widths[key]
            width["pixelMinimum"] = width["bucketMinimum"] * stride
            width["pixelMaximum"] = width["bucketMaximum"] * stride
            width["fitsChromeLayoutLimit"] = (
                0 <= width["pixelMinimum"]
                and width["pixelMaximum"] < CSS_LAYOUT_LIMIT_PX
            )
        maximum = (
            widths["fineCandidateBucketComponent"]["pixelMaximum"] + tie_max
        )
        viewport = head.GROUP_VIEWPORT * stride // 4
        widths["maximumTieEncodedFineCandidatePx"] = maximum
        widths["scaledGroupViewportPx"] = viewport
        widths["maximumWidthFitsScaledGroupViewport"] = max(
            maximum, widths["mixedGroupUpper"]["pixelMaximum"]
        ) < viewport
        widths["geometryFitsChromeLayoutLimit"] = (
            widths["fineCandidateBucketComponent"]["fitsChromeLayoutLimit"]
            and widths["mixedGroupUpper"]["fitsChromeLayoutLimit"]
            and maximum < CSS_LAYOUT_LIMIT_PX
            and widths["maximumWidthFitsScaledGroupViewport"]
        )
        row["widthRanges"] = widths
        row["transportGeometry"] = {
            "allowanceBucketsPerSide": ALLOWANCE_BUCKETS_PER_SIDE,
            "allowanceWidthPxPerSide": ALLOWANCE_BUCKETS_PER_SIDE * stride,
            "stopGapBuckets": STOP_GAP_BUCKETS,
            "stopGapWidthPx": STOP_GAP_BUCKETS * stride,
            "bucketSemanticsUnchanged": True,
            "routeAndWorkInheritedFrom": "g128-s4",
        }
        rows.append(row)
    return {
        "status": "offline geometry prepared; browser gated",
        "basisVariant": "g128-s4",
        "executionOrder": [row["name"] for row in rows],
        "stopAtFirstSemanticallyExact": True,
        "noFixtureSpecificCorrection": True,
        "variants": rows,
    }


def render_transport_append(sweep: dict[str, object]) -> str:
    rows = []
    for row in sweep["variants"]:
        tie = row["tieContract"]
        geometry = row["transportGeometry"]
        widths = row["widthRanges"]
        rows.append(
            f"| {row['name']} | {row['scoreStridePx']} | "
            f"{tie['tieStepPx']:.4f} | {tie['layoutUnitsPerToken']:.0f} | "
            f"{geometry['allowanceWidthPxPerSide']} / "
            f"{geometry['stopGapWidthPx']} | "
            f"{widths['maximumTieEncodedFineCandidatePx']:,.3f} | "
            f"{'yes' if widths['geometryFitsChromeLayoutLimit'] else 'NO'} |"
        )
    return f"""

## G128 tie-spacing transport sweep

This is an append-only transport sweep. It inherits G128-s4's 1,024/1,024 target retention, routes, router work, dynamic fine work, exact rows, and weighted proxy unchanged. Only the pixel stride and fractional tie spacing change; no fixture-specific correction is permitted.

| Variant | Score stride px | Tie step px | Layout units / token | 24-bucket allowance / 48-bucket stop px | Maximum encoded fine width px | Fits |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

Bucket semantics remain 1/256 logit. Each variant emits `localTie * (scoreStridePx / 128)` and decodes `round(mod(width, scoreStridePx) / tieStepPx)`. Browser order is g128-s8, g128-s16, then g128-s32, stopping at the first semantically exact variant.
"""


def append_transport_sweep() -> None:
    result_path = OUTPUT / "offline-results.json"
    report_path = OUTPUT / "RESULTS.md"
    if not result_path.exists() or not report_path.exists():
        raise FileNotFoundError("run the baseline offline analysis first")
    result = json.loads(result_path.read_text())
    sweep = g128_transport_sweep(result)
    result["transportSweep"] = sweep
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    marker = "\n## G128 tie-spacing transport sweep\n"
    report = report_path.read_text().split(marker, 1)[0].rstrip()
    report_path.write_text(report + render_transport_append(sweep))
    print(json.dumps(sweep, indent=2))


def percentile(values: np.ndarray, fraction: float) -> float:
    return float(np.percentile(values, fraction * 100, method="higher"))


def grouped_max(values: np.ndarray, group_size: int) -> np.ndarray:
    groups = math.ceil(head.VOCABULARY / group_size)
    padded = np.full(
        (len(values), groups * group_size),
        np.iinfo(values.dtype).min,
        dtype=values.dtype,
    )
    padded[:, : head.VOCABULARY] = values
    return padded.reshape(len(values), groups, group_size).max(axis=2)


def grouped_winners(values: np.ndarray, group_size: int) -> np.ndarray:
    groups = math.ceil(head.VOCABULARY / group_size)
    winners = np.empty((len(values), groups), dtype=np.int64)
    for group in range(groups):
        start = group * group_size
        stop = min(start + group_size, head.VOCABULARY)
        # First maximum is the lower token ID, matching the one-layout-unit tie
        # payload emitted by the browser artifact.
        winners[:, group] = start + np.argmax(values[:, start:stop], axis=1)
    return winners


def stopping_route(
    mixed_upper: np.ndarray, exact_group_buckets: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    groups = mixed_upper.shape[1]
    order = np.argsort(-mixed_upper, axis=1, kind="stable")
    ordered_upper = np.take_along_axis(mixed_upper, order, axis=1)
    ordered_exact = np.take_along_axis(exact_group_buckets, order, axis=1)
    best = np.maximum.accumulate(ordered_exact, axis=1)
    done = best[:, :-1] - ordered_upper[:, 1:] > STOP_GAP_BUCKETS
    has_done = np.any(done, axis=1)
    stops = np.where(has_done, np.argmax(done, axis=1) + 1, groups)
    return order, stops.astype(np.int64)


def width_range(values: np.ndarray, stride: int) -> dict[str, float | int | bool]:
    minimum = int(np.min(values))
    maximum = int(np.max(values))
    minimum_px = minimum * stride
    maximum_px = maximum * stride
    return {
        "bucketMinimum": minimum,
        "bucketMaximum": maximum,
        "pixelMinimum": minimum_px,
        "pixelMaximum": maximum_px,
        "fitsChromeLayoutLimit": 0 <= minimum_px
        and maximum_px < CSS_LAYOUT_LIMIT_PX,
    }


def evaluate_variant(
    variant: Variant,
    fine_scores: np.ndarray,
    fine_buckets: np.ndarray,
    upper_buckets: np.ndarray,
    raw_target_winners: np.ndarray,
    exact_target_winners: np.ndarray,
) -> dict[str, object]:
    if variant.score_stride_px / variant.group_size < 1 / LAYOUT_UNITS_PER_PX:
        raise RuntimeError(f"{variant.name}: tie payload overlaps score bucket")

    groups = variant.groups
    hot_groups = tuple(range(variant.hot_groups))
    exact_group_buckets = grouped_max(fine_buckets, variant.group_size)
    exact_group_winners = grouped_winners(fine_buckets, variant.group_size)
    int10_group_upper = grouped_max(upper_buckets, variant.group_size)
    mixed_upper = int10_group_upper.copy()
    mixed_upper[:, hot_groups] = (
        exact_group_buckets[:, hot_groups] + ALLOWANCE_BUCKETS_PER_SIDE
    )
    order, stops = stopping_route(mixed_upper, exact_group_buckets)

    hot_mask = np.zeros(groups, dtype=bool)
    hot_mask[list(hot_groups)] = True
    target_groups = exact_target_winners // variant.group_size
    retained = 0
    hot_visits = 0
    for state, stop in enumerate(stops):
        route = order[state, :stop]
        retained += int(target_groups[state] in route)
        hot_visits += int(np.sum(hot_mask[route]))

    total_visits = int(np.sum(stops))
    dynamic_visits = total_visits - hot_visits
    dynamic_rows = dynamic_visits * variant.group_size
    mean_dynamic_rows = dynamic_rows / len(stops)

    tie_checks = len(fine_buckets) * variant.hot_groups
    tie_matches = 0
    for group in hot_groups:
        start = group * variant.group_size
        stop = min(start + variant.group_size, head.VOCABULARY)
        local = fine_buckets[:, start:stop]
        local_ids = np.arange(stop - start, dtype=np.int64)
        encoded = (
            local * (variant.group_size + 1)
            + (variant.group_size - 1 - local_ids)[None, :]
        )
        expected = start + np.argmax(encoded, axis=1)
        tie_matches += int(np.sum(expected == exact_group_winners[:, group]))

    # Each active remaining-group router has one source and one match operation
    # per group. Its concrete markup has 2G+7 nodes. The initial upper head is
    # common candidate work but its group-level router still scales with G.
    remaining_router_elements = STAGES * (2 * groups + 7)
    mean_active_remaining_routers = float(np.mean(stops))
    mean_router_group_slots = groups * mean_active_remaining_routers
    mean_router_source_match_ops = 2 * mean_router_group_slots

    exact_rows = variant.exact_upper_rows
    int10_rows = head.VOCABULARY - exact_rows
    precision_ratio = 16 / 10
    weighted_candidate_rows = (
        int10_rows + precision_ratio * (exact_rows + mean_dynamic_rows)
    )
    # Router source/match operations are cheap CSS geometry relative to shaping
    # a 768-axis row, but not free. Keep their explicit 0.05 diagnostic weight
    # separate and normalize the combined number later against retained G256.
    router_operation_weight = 0.05
    weighted_with_router = (
        weighted_candidate_rows
        + router_operation_weight * mean_router_source_match_ops
    )

    fine_widths = width_range(fine_buckets, variant.score_stride_px)
    upper_widths = width_range(mixed_upper, variant.score_stride_px)
    tie_max_px = (variant.group_size - 1) / LAYOUT_UNITS_PER_PX
    max_encoded_candidate_px = fine_widths["pixelMaximum"] + tie_max_px
    group_viewport_px = head.GROUP_VIEWPORT * variant.score_stride_px // 4
    geometry_fits = (
        fine_widths["fitsChromeLayoutLimit"]
        and upper_widths["fitsChromeLayoutLimit"]
        and max_encoded_candidate_px < CSS_LAYOUT_LIMIT_PX
        and max(
            max_encoded_candidate_px,
            float(upper_widths["pixelMaximum"]),
        ) < group_viewport_px
    )

    return {
        "name": variant.name,
        "groupSize": variant.group_size,
        "scoreStridePx": variant.score_stride_px,
        "scoreBucketLogitWidth": 1 / SCORE_SCALE,
        "stridePerTokenPx": variant.score_stride_px / variant.group_size,
        "groups": groups,
        "hotGroups": list(hot_groups),
        "hotTokensCovered": min(
            head.VOCABULARY, variant.hot_groups * variant.group_size
        ),
        "exactUpperRows": exact_rows,
        "exactUpperRowDifferenceFrom512": exact_rows - 512,
        "targetRetention": retained,
        "routeLength": {
            "total": total_visits,
            "mean": float(np.mean(stops)),
            "median": float(np.median(stops)),
            "p95": percentile(stops, 0.95),
            "maximum": int(np.max(stops)),
        },
        "statesStoppingWithinSix": int(np.sum(stops <= STAGES)),
        "dynamicFineWork": {
            "hotVisitsReused": hot_visits,
            "dynamicFineGridVisits": dynamic_visits,
            "dynamicFineCandidateRowsTotal": dynamic_rows,
            "meanDynamicFineCandidateRowsPerState": mean_dynamic_rows,
        },
        "routerWork": {
            "remainingRouterElementsForSixStageArtifact": remaining_router_elements,
            "remainingRouterElementsPerStage": 2 * groups + 7,
            "meanActiveRemainingRouters": mean_active_remaining_routers,
            "meanRouterGroupSlotsPerState": mean_router_group_slots,
            "meanSourceMatchOperationsPerState": mean_router_source_match_ops,
        },
        "tieContract": {
            "scoreBucketStridePx": variant.score_stride_px,
            "layoutUnitPx": 1 / LAYOUT_UNITS_PER_PX,
            "tiePayloadMaximumPx": tie_max_px,
            "unusedTieSpacePx": variant.score_stride_px - (
                variant.group_size / LAYOUT_UNITS_PER_PX
            ),
            "decode": (
                f"local={variant.group_size - 1}-round("
                f"mod(width,{variant.score_stride_px}px)*64)"
            ),
            "checks": tie_checks,
            "matches": tie_matches,
        },
        "widthRanges": {
            "fineCandidateBucketComponent": fine_widths,
            "mixedGroupUpper": upper_widths,
            "maximumTieEncodedFineCandidatePx": max_encoded_candidate_px,
            "scaledGroupViewportPx": group_viewport_px,
            "maximumWidthFitsScaledGroupViewport": max(
                max_encoded_candidate_px,
                float(upper_widths["pixelMaximum"]),
            ) < group_viewport_px,
            "geometryFitsChromeLayoutLimit": geometry_fits,
        },
        "weightedProxy": {
            "int10UpperRowWeight": 1.0,
            "globalInt16RowWeight": precision_ratio,
            "routerSourceMatchWeight": router_operation_weight,
            "precisionWeightedCandidateRowsPerState": weighted_candidate_rows,
            "routerAwareUnitsPerState": weighted_with_router,
        },
        "rawVsRoundedGlobalWinnerMatches": int(
            np.sum(raw_target_winners == exact_target_winners)
        ),
    }


def pareto_names(rows: list[dict[str, object]]) -> list[str]:
    values = [
        (
            int(row["exactUpperRows"]),
            float(row["weightedProxy"]["routerAwareUnitsPerState"]),
            float(row["routeLength"]["p95"]),
        )
        for row in rows
    ]
    frontier: list[str] = []
    for index, value in enumerate(values):
        dominated = any(
            other != index
            and all(left <= right for left, right in zip(values[other], value))
            and any(left < right for left, right in zip(values[other], value))
            for other in range(len(values))
        )
        if not dominated:
            frontier.append(str(rows[index]["name"]))
    return frontier


def render_report(result: dict[str, object]) -> str:
    rows = []
    for row in result["variants"]:
        route = row["routeLength"]
        fine = row["dynamicFineWork"]
        router = row["routerWork"]
        widths = row["widthRanges"]
        rows.append(
            "| {name} | {groups} | {hot} / {exact:+d} | {retained}/1,024 | "
            "{total:,} / {mean:.3f} / {median:.0f} / {p95:.0f} / {maximum} | {within} | "
            "{grids:,} / {rows:,} | {elements:,} / {ops:,.1f} | "
            "{fine_min:,.0f}–{fine_max:,.0f} / "
            "{upper_min:,.0f}–{upper_max:,.0f} | "
            "{proxy:,.1f} / {norm:.3f} |".format(
                name=row["name"],
                groups=row["groups"],
                hot=row["hotTokensCovered"],
                exact=row["exactUpperRowDifferenceFrom512"],
                retained=row["targetRetention"],
                total=route["total"],
                mean=route["mean"],
                median=route["median"],
                p95=route["p95"],
                maximum=route["maximum"],
                within=row["statesStoppingWithinSix"],
                grids=fine["dynamicFineGridVisits"],
                rows=fine["dynamicFineCandidateRowsTotal"],
                elements=router["remainingRouterElementsForSixStageArtifact"],
                ops=router["meanSourceMatchOperationsPerState"],
                fine_min=widths["fineCandidateBucketComponent"]["pixelMinimum"],
                fine_max=widths["maximumTieEncodedFineCandidatePx"],
                upper_min=widths["mixedGroupUpper"]["pixelMinimum"],
                upper_max=widths["mixedGroupUpper"]["pixelMaximum"],
                proxy=row["weightedProxy"]["routerAwareUnitsPerState"],
                norm=row["weightedProxy"]["normalizedToRetainedG256"],
            )
        )
    pareto = ", ".join(result["pareto"]["variantNames"])
    build = ", ".join(result["pareto"]["browserArtifactNames"])
    return f"""# Mixed exact-upper group-size/score-stride sweep

Browser status: **not launched**. The analysis and candidate selection are offline-first on the 1,024-state Chromium-realized coordinate corpus.

## Result

All variants retain **1,024/1,024** rounded-bucket targets and pass every emitted lower-token tie check. The formal frontier is **{pareto}**. Browser artifacts are prepared only for **{build or "none"}**; `g256-s4` is the already-retained control.

The offline weighted proxy favors **g128-s4** by only **1.1%** versus retained G256: it cuts dynamic candidate-row work by 43.8%, but raises route p95 from 17 to 20 and more than doubles mean router source/match work. G512 and G1024 shorten routes, but their larger dynamic grids raise the weighted proxy by 2.1% and 4.9%. Retain G256 as the default until browser timing can determine whether G128's row savings outweigh its router topology.

| Variant | Groups | Exact rows / delta from 512 | Target retained | Route total / mean / med / p95 / max | <=6 | Dynamic grids / candidate rows | Six-stage router elements / mean source+match ops | Fine / upper width range px | Weighted units / vs G256 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

The weighted diagnostic uses int10 row = 1, global-int16 row = 1.6, and each router source/match geometry operation = 0.05. It is a transparent screening proxy, not a browser latency claim.

## Encoding and readback

The score quantizer stays at **1/256 logit per bucket** for every row. Only the layout stride changes. A candidate width is `bucket * scoreStride + (groupSize - 1 - local)/64px`; group max strips the tie with `round(down, width, scoreStride)`. Readback divides by the variant stride and decodes `local = groupSize - 1 - round(mod(width, stride) * 64)`. Therefore `scoreStride/groupSize >= 1/64px` is mandatory.

The browser-error allowance remains 24 buckets per side: it is emitted as `24 * scoreStride` pixels. The strict certificate remains `best - nextUpper > 48` after widths are converted back to bucket units.

`g128-s4` leaves 2px of unused fractional space per bucket. `g256-s4`, `g512-s8`, and `g1024-s16` exactly fill the available 64-layout-unit tie payload. For G1024, one hot group is the smallest nonzero prefix, so it necessarily replaces **1,024 exact rows (+512)** rather than 512.

All reported final score widths fit Chromium's {CSS_LAYOUT_LIMIT_PX:,}px layout ceiling. Width ranges and router accounting are explicit in `offline-results.json`.

Runtime: **{result['runtimeSeconds']:.2f}s**. No browser or Chrome process was started.
"""


def main() -> None:
    started = time.perf_counter()
    if (
        not STATES.exists()
        or not FINE_REFERENCE.exists()
        or not RETAINED_REFERENCE.exists()
    ):
        raise FileNotFoundError("missing corpus or global-int16 reference")
    saved = np.load(STATES)
    hidden = np.asarray(saved["hidden"], dtype=np.float64)
    if hidden.shape != (1_024, head.WIDTH):
        raise RuntimeError(f"unexpected corpus shape {hidden.shape}")

    fine_reference = json.loads(FINE_REFERENCE.read_text())
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[: head.VOCABULARY],
        dtype=np.float64,
    )
    fine_scale = float(fine_reference["weightScale"])
    fine_codes = np.rint(weights / fine_scale).astype(np.int16)
    fine_weights = fine_codes.astype(np.float64) * fine_scale

    production_range = float(np.max(np.abs(hidden))) * 1.01
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    axis_l2 = production_range * math.sqrt(head.WIDTH) / (2 * AXIS_STEPS)
    query_norm_upper = np.linalg.norm(hidden, axis=1) + axis_l2

    maximum_code = 2**9 - 1
    row_scales = np.max(np.abs(fine_weights), axis=1) / maximum_code
    row_scales[row_scales == 0] = 1.0
    coarse_codes = np.rint(fine_weights / row_scales[:, None]).astype(np.int16)
    coarse_weights = coarse_codes.astype(np.float64) * row_scales[:, None]
    errors = np.linalg.norm(fine_weights - coarse_weights, axis=1)

    fine_scores = realized @ fine_weights.T
    coarse_scores = realized @ coarse_weights.T
    # Per-state floor changes only the nonnegative CSS representation, never
    # ordering or certificate gaps.
    score_floors = np.floor(np.min(fine_scores, axis=1)).astype(np.int64) - 1
    fine_buckets = np.rint(
        (fine_scores - score_floors[:, None]) * SCORE_SCALE
    ).astype(np.int64)
    upper_buckets = (
        np.floor(
            (
                coarse_scores
                + query_norm_upper[:, None] * errors
                - score_floors[:, None]
            )
            * SCORE_SCALE
        ).astype(np.int64)
        + 1
    )
    exact_targets = np.argmax(fine_buckets, axis=1).astype(np.int64)
    raw_targets = np.argmax(fine_scores, axis=1).astype(np.int64)

    variants = [
        evaluate_variant(
            variant,
            fine_scores,
            fine_buckets,
            upper_buckets,
            raw_targets,
            exact_targets,
        )
        for variant in VARIANTS
    ]
    retained_proxy = next(
        row["weightedProxy"]["routerAwareUnitsPerState"]
        for row in variants
        if row["name"] == "g256-s4"
    )
    for row in variants:
        row["weightedProxy"]["normalizedToRetainedG256"] = (
            row["weightedProxy"]["routerAwareUnitsPerState"] / retained_proxy
        )
        if row["targetRetention"] != len(hidden):
            raise RuntimeError(f"{row['name']} lost target retention")
        if row["tieContract"]["matches"] != row["tieContract"]["checks"]:
            raise RuntimeError(f"{row['name']} failed exact tie checks")

    retained = json.loads(RETAINED_REFERENCE.read_text())["corpusFeasibility"]
    retained_row = next(row for row in variants if row["name"] == "g256-s4")
    replay = {
        "targetRetention": retained_row["targetRetention"],
        "meanGroupsVisited": retained_row["routeLength"]["mean"],
        "p95GroupsVisited": retained_row["routeLength"]["p95"],
        "hotGroupVisits": retained_row["dynamicFineWork"]["hotVisitsReused"],
    }
    expected_replay = {
        "targetRetention": retained["targetWinnerRetained"],
        "meanGroupsVisited": retained["meanGroupsVisited"],
        "p95GroupsVisited": retained["p95GroupsVisited"],
        "hotGroupVisits": retained["hotGroupVisits"],
    }
    if replay != expected_replay:
        raise RuntimeError(
            f"G256 replay diverged from retained head: {replay} != {expected_replay}"
        )

    frontier = pareto_names(variants)
    browser_names = [
        name for name in frontier if name not in ("g256-s4",)
    ]
    result = {
        "contract": {
            "execution": "offline NumPy; no browser",
            "states": len(hidden),
            "vocabulary": head.VOCABULARY,
            "width": head.WIDTH,
            "scoreScale": SCORE_SCALE,
            "scoreBucketLogitWidth": 1 / SCORE_SCALE,
            "layoutUnitsPerPx": LAYOUT_UNITS_PER_PX,
            "allowanceBucketsPerSide": ALLOWANCE_BUCKETS_PER_SIDE,
            "stopGapBuckets": STOP_GAP_BUCKETS,
            "productionInputRange": production_range,
            "axisSteps": AXIS_STEPS,
            "rawVsRoundedGlobalWinnerMatches": int(
                np.sum(raw_targets == exact_targets)
            ),
            "retainedG256Replay": {
                "matches": True,
                "observed": replay,
                "expected": expected_replay,
            },
        },
        "variants": variants,
        "pareto": {
            "objectives": [
                "exactUpperRows:min",
                "weightedProxy.routerAwareUnitsPerState:min",
                "routeLength.p95:min",
            ],
            "variantNames": frontier,
            "browserArtifactNames": browser_names,
        },
        "runtimeSeconds": time.perf_counter() - started,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "offline-results.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    (OUTPUT / "RESULTS.md").write_text(render_report(result))
    print(
        json.dumps(
            {
                "pareto": frontier,
                "browserArtifacts": browser_names,
                "variants": [
                    {
                        "name": row["name"],
                        "retained": row["targetRetention"],
                        "meanRoute": row["routeLength"]["mean"],
                        "p95Route": row["routeLength"]["p95"],
                        "dynamicRows": row["dynamicFineWork"][
                            "dynamicFineCandidateRowsTotal"
                        ],
                        "weighted": row["weightedProxy"][
                            "normalizedToRetainedG256"
                        ],
                        "fits": row["widthRanges"][
                            "geometryFitsChromeLayoutLimit"
                        ],
                    }
                    for row in variants
                ],
                "runtimeSeconds": result["runtimeSeconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    if "--append-transport-sweep" in sys.argv[1:]:
        append_transport_sweep()
    else:
        main()
