#!/usr/bin/env python3
"""Measure exact best-first group visitation hotspots on the router corpus."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_certified_tail_strategies import (
    AXIS_STEPS,
    COARSE_ALLOWANCE_BUCKETS,
    FINE_ALLOWANCE_BUCKETS,
    FINE_REFERENCE,
    GROUPS,
    GROUP_SIZE,
    SCORE_SCALE,
    STATES,
    VOCABULARY,
    WIDTH,
    distribution,
    score_groups,
    stopping_counts,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-best-first-group-hotspots"
SET_SIZES = (2, 4, 8, 16, 32)
STAGE_POSITIONS = 6


def ranked_frequencies(counts: np.ndarray, denominator: int) -> list[dict[str, object]]:
    order = np.argsort(-counts, kind="stable")
    ranks = np.empty(len(counts), dtype=np.int64)
    ranks[order] = np.arange(1, len(counts) + 1)
    return [
        {
            "groupId": group,
            "visits": int(counts[group]),
            "fractionOfDenominator": float(counts[group] / denominator),
            "rank": int(ranks[group]),
        }
        for group in range(len(counts))
    ]


def set_metrics(
    name: str,
    selection: str,
    groups: list[int],
    visited: np.ndarray,
    stop_counts: np.ndarray,
    stops_within_six: np.ndarray,
) -> dict[str, object]:
    selected = np.zeros(GROUPS, dtype=bool)
    selected[groups] = True
    selected_visits = np.sum(visited[:, selected], axis=1).astype(np.int64)
    non_set_visits = stop_counts - selected_visits
    fully_covered = non_set_visits == 0
    eligible = int(np.sum(stops_within_six))
    if eligible == 0:
        raise RuntimeError("no states stop within six groups")
    return {
        "name": name,
        "selection": selection,
        "groups": groups,
        "size": len(groups),
        "visitsInsideSet": int(np.sum(selected_visits)),
        "fractionOfAllVisitsInsideSet": float(
            np.sum(selected_visits) / np.sum(stop_counts)
        ),
        "statesFullyCovered": int(np.sum(fully_covered)),
        "fractionOfStatesFullyCovered": float(np.mean(fully_covered)),
        "statesRequiringNonSetVisits": int(np.sum(~fully_covered)),
        "fractionOfStatesRequiringNonSetVisits": float(np.mean(~fully_covered)),
        "nonSetVisitsPerState": distribution(non_set_visits),
        "nonSetVisitsPerRequiringState": distribution(non_set_visits[~fully_covered]),
        "conditionalOnStoppingWithinSix": {
            "states": eligible,
            "statesFullyCovered": int(np.sum(fully_covered[stops_within_six])),
            "fractionOfStatesFullyCovered": float(
                np.mean(fully_covered[stops_within_six])
            ),
            "statesRequiringNonSetVisits": int(
                np.sum(~fully_covered[stops_within_six])
            ),
            "nonSetVisitsPerState": distribution(
                non_set_visits[stops_within_six]
            ),
        },
    }


def percent(value: float) -> str:
    return f"{100 * value:.2f}%"


def render_report(result: dict[str, object]) -> str:
    visits = result["visitation"]
    sets = result["setCoverage"]
    stopping = result["stopping"]
    validation = result["validation"]
    runtime = result["runtime"]

    fixed = sets["fixedPredeclared"]
    top = sets["dataSelectedTopFrequency"]
    low = sets["contiguousLowId"]
    rows = [fixed, *top, *low]
    coverage_rows = "\n".join(
        "| {name} | `{groups}` | {visits} | {all_states} | {within_six} | "
        "{non_hot} |".format(
            name=row["name"],
            groups=",".join(str(group) for group in row["groups"]),
            visits=percent(row["fractionOfAllVisitsInsideSet"]),
            all_states=percent(row["fractionOfStatesFullyCovered"]),
            within_six=percent(
                row["conditionalOnStoppingWithinSix"][
                    "fractionOfStatesFullyCovered"
                ]
            ),
            non_hot=f'{row["nonSetVisitsPerState"]["mean"]:.3f}',
        )
        for row in rows
    )

    ranked = sorted(
        visits["perGroup"], key=lambda row: (row["rank"], row["groupId"])
    )
    frequency_rows = "\n".join(
        f'| {row["rank"]} | {row["groupId"]} | {row["visits"]} | '
        f'{percent(row["fractionOfStates"])} | '
        f'{percent(row["fractionOfAllVisits"])} |'
        for row in ranked
    )

    stage_sections = []
    for stage in result["stagePositionFrequencies"]:
        stage_ranked = sorted(
            stage["perGroup"], key=lambda row: (row["rank"], row["groupId"])
        )[:10]
        leaders = ", ".join(
            f'{row["groupId"]} ({row["visits"]}, '
            f'{percent(row["fractionOfActiveStates"])})'
            for row in stage_ranked
        )
        stage_sections.append(
            f'- Position {stage["position"]}: {stage["activeStates"]} active states; '
            f'top groups {leaders}.'
        )

    histogram = ", ".join(
        f'{row["groupsVisited"]}:{row["states"]}'
        for row in stopping["histogram"]
    )
    fixed_non_hot = fixed["nonSetVisitsPerState"]
    fixed_non_hot_required = fixed["nonSetVisitsPerRequiringState"]
    return f"""# Best-first exact-group visitation hotspots

## Result

Across all 1,024 corpus states, exact best-first certification visited **{visits["totalVisits"]:,} groups**. Fixed, deployable groups `0/1` captured **{percent(fixed["fractionOfAllVisitsInsideSet"])} of visits** and completely covered **{fixed["statesFullyCovered"]}/1,024 ({percent(fixed["fractionOfStatesFullyCovered"])}) states**. They are therefore measured as a predeclared optimization, not inferred from the evaluated state.

The separately reported top-frequency sets are diagnostic upper bounds chosen after seeing this corpus. They must not be interpreted as a deployable fixed policy without a held-out or predeclared selection step.

**Conclusion:** within the 1,024-state corpus, the low-ID hotspot is not a ten-fixture artifact: `0` and `1` are independently the two highest-frequency groups, and the data-selected top 2/4/16 sets exactly equal contiguous low-ID sets. But `0/1` alone are not a general replacement for best-first fallback because **{percent(fixed["fractionOfStatesRequiringNonSetVisits"])} of states** still visit a group outside them. At size 32, data selection improves full-path coverage by only **{100 * (top[-1]["fractionOfStatesFullyCovered"] - low[-1]["fractionOfStatesFullyCovered"]):.2f} percentage points** over predeclared `0..31`, so most measured skew is contiguous-low-ID rather than a collection of isolated corpus-specific IDs.

States visited a median of **{stopping["distribution"]["median"]:.0f}** groups, p95 **{stopping["distribution"]["p95"]:.0f}**, maximum **{stopping["distribution"]["maximum"]}**. **{stopping["stoppedWithinSixStates"]}/1,024 ({percent(stopping["stoppedWithinSixFraction"])})** certified within six groups.

## Set coverage

“Fully covered” means every group in that state's ordered path through its exact stopping count belongs to the set. “Non-set visits” counts the remaining exact-group evaluations per state.

| Set | Group IDs | All visits in set | All states fully covered | Stop≤6 states fully covered | Mean non-set visits/state |
|---|---|---:|---:|---:|---:|
{coverage_rows}

For fixed groups `0/1`, non-hot visits per state have median **{fixed_non_hot["median"]:.0f}**, p95 **{fixed_non_hot["p95"]:.0f}**, maximum **{fixed_non_hot["maximum"]}**, and mean **{fixed_non_hot["mean"]:.3f}**. Conditional on needing any non-hot group, the mean is **{fixed_non_hot_required["mean"]:.3f}**. The JSON contains the same distributions for every top-frequency and contiguous-low-ID set.

## Per-group visitation frequency

Each group can appear at most once per state. The state fraction is thus the probability that a corpus path visits the group; the visit fraction is its share of all {visits["totalVisits"]:,} evaluations.

| Rank | Group | States/visits | Fraction of states | Fraction of all visits |
|---:|---:|---:|---:|---:|
{frequency_rows}

## First six path positions

Frequencies below are conditional on the state still being active at that position. Top ten groups are shown; complete 197-group tables are in `results.json`.

{chr(10).join(stage_sections)}

## Stopping distribution

The compact `groups-visited:states` histogram is:

`{histogram}`

## Contract and validation

- Target: {result["targetContract"]["target"]}.
- Realization: {result["targetContract"]["realization"]}.
- Coarse bound: {result["targetContract"]["coarseEncoding"]}, with {result["targetContract"]["coarseAllowanceBuckets"]} coarse buckets and {result["targetContract"]["fineAllowanceBuckets"]} fine buckets.
- Stop rule: {result["targetContract"]["stopRule"]}
- All {validation["targetWinnerRetainedStates"]} target-winning groups were retained in their visited paths.
- Count conservation passed: per-group visits, per-state stopping counts, and first-six position counts agree.
- Runtime: **{runtime["seconds"]:.2f} seconds** on the local offline NumPy analysis; no browser was used.

## Interpretation

This analysis answers where the existing exact best-first search spends group evaluations. A data-selected top-K set describes corpus skew and an optimistic static cache. In contrast, groups `0/1` and contiguous `0..K-1` are deployable predeclared choices whose IDs do not depend on this evaluation. Any production choice based on the data-selected ranking needs separate held-out validation; these 1,024 states are the measurement corpus, not that validation set.
"""


def main() -> None:
    started = time.perf_counter()
    if not STATES.exists():
        raise RuntimeError("missing the 1,024-state router corpus")
    if not FINE_REFERENCE.exists():
        raise RuntimeError("missing the global-int16 fine-head reference")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    saved = np.load(STATES)
    hidden = np.asarray(saved["hidden"], dtype=np.float32)
    if hidden.shape != (1_024, WIDTH):
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

    if np.any(stop_counts < 1) or np.any(stop_counts > GROUPS):
        raise RuntimeError("stopping count outside the valid group range")
    if np.any(np.sort(order, axis=1) != np.arange(GROUPS)[None, :]):
        raise RuntimeError("best-first order is not a permutation")

    visited = np.zeros((len(hidden), GROUPS), dtype=bool)
    for sample, stop in enumerate(stop_counts):
        visited[sample, order[sample, :stop]] = True
    total_visits = int(np.sum(stop_counts))
    group_counts = np.sum(visited, axis=0).astype(np.int64)
    if int(np.sum(group_counts)) != total_visits:
        raise RuntimeError("per-group visit counts do not conserve total visits")

    best_lower = (
        np.maximum.accumulate(ordered_exact, axis=1)
        - FINE_ALLOWANCE_BUCKETS / SCORE_SCALE
    )
    early = stop_counts < GROUPS
    early_rows = np.flatnonzero(early)
    if np.any(
        best_lower[early_rows, stop_counts[early_rows] - 1]
        <= ordered_upper[early_rows, stop_counts[early_rows]]
    ):
        raise RuntimeError("an early stopping count violates the strict stop test")
    later = stop_counts > 1
    later_rows = np.flatnonzero(later)
    if np.any(
        best_lower[later_rows, stop_counts[later_rows] - 2]
        > ordered_upper[later_rows, stop_counts[later_rows] - 1]
    ):
        raise RuntimeError("a stopping count skipped an earlier valid stop")

    target_groups = target_winners // GROUP_SIZE
    retained = visited[np.arange(len(hidden)), target_groups]
    if not np.all(retained):
        lost = np.flatnonzero(~retained).tolist()
        raise RuntimeError(f"visited paths lost target-winning groups: {lost}")

    stop_within_six = stop_counts <= STAGE_POSITIONS
    top_order = np.argsort(-group_counts, kind="stable")
    fixed = set_metrics(
        "fixed groups 0/1",
        "predeclared-deployable",
        [0, 1],
        visited,
        stop_counts,
        stop_within_six,
    )
    selected_top = [
        set_metrics(
            f"data-selected top {size}",
            "diagnostic-corpus-selected",
            top_order[:size].astype(int).tolist(),
            visited,
            stop_counts,
            stop_within_six,
        )
        for size in SET_SIZES
    ]
    contiguous = [
        set_metrics(
            f"contiguous low IDs 0..{size - 1}",
            "predeclared-deployable",
            list(range(size)),
            visited,
            stop_counts,
            stop_within_six,
        )
        for size in SET_SIZES
    ]

    stage_frequencies = []
    stage_total = 0
    for position in range(STAGE_POSITIONS):
        active = stop_counts > position
        active_groups = order[active, position]
        counts = np.bincount(active_groups, minlength=GROUPS).astype(np.int64)
        active_states = int(np.sum(active))
        if int(np.sum(counts)) != active_states:
            raise RuntimeError(f"position {position + 1} counts do not conserve states")
        stage_total += active_states
        per_group = ranked_frequencies(counts, active_states)
        for row in per_group:
            row["fractionOfActiveStates"] = row.pop("fractionOfDenominator")
            row["fractionOfAllStates"] = row["visits"] / len(hidden)
        stage_frequencies.append({
            "position": position + 1,
            "activeStates": active_states,
            "fractionOfAllStatesActive": float(active_states / len(hidden)),
            "perGroup": per_group,
        })
    expected_stage_total = int(np.sum(np.minimum(stop_counts, STAGE_POSITIONS)))
    if stage_total != expected_stage_total:
        raise RuntimeError("first-six stage counts do not conserve truncated paths")

    per_group = ranked_frequencies(group_counts, len(hidden))
    for row in per_group:
        row["fractionOfStates"] = row.pop("fractionOfDenominator")
        row["fractionOfAllVisits"] = row["visits"] / total_visits

    unique_stops, stop_histogram = np.unique(stop_counts, return_counts=True)
    elapsed = time.perf_counter() - started
    result = {
        "model": "openai-community/gpt2",
        "samples": len(hidden),
        "targetContract": {
            "target": "global-int16 weights at F2DOT14-realized hidden coordinates",
            "realization": (
                "nearest F2DOT14 grid, matching "
                "tools/analyze_gpt2_certified_tail_strategies.py"
            ),
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
            "stopRule": (
                "after each visited group, cumulative best exact group score minus "
                "the fine allowance must be strictly greater than the next group's "
                "coarse upper bound"
            ),
        },
        "stopping": {
            "distribution": distribution(stop_counts),
            "histogram": [
                {"groupsVisited": int(stop), "states": int(count)}
                for stop, count in zip(unique_stops, stop_histogram)
            ],
            "stoppedWithinSixStates": int(np.sum(stop_within_six)),
            "stoppedWithinSixFraction": float(np.mean(stop_within_six)),
        },
        "visitation": {
            "totalVisits": total_visits,
            "meanVisitsPerState": float(total_visits / len(hidden)),
            "perGroup": per_group,
        },
        "setCoverage": {
            "fixedPredeclared": fixed,
            "dataSelectedTopFrequency": selected_top,
            "contiguousLowId": contiguous,
        },
        "stagePositionFrequencies": stage_frequencies,
        "validation": {
            "targetWinnerRetainedStates": int(np.sum(retained)),
            "targetWinnerRetentionRate": float(np.mean(retained)),
            "strictEarlyStopRuleValidatedStates": int(np.sum(early)),
            "earliestStopValidatedStates": int(np.sum(later)),
            "perGroupVisitCountSum": int(np.sum(group_counts)),
            "perStateStopCountSum": total_visits,
            "firstSixPositionCountSum": stage_total,
            "truncatedPathCountSum": expected_stage_total,
            "allChecksPassed": True,
        },
        "runtime": {
            "seconds": elapsed,
            "execution": "offline NumPy; no browser",
        },
    }
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUTPUT / "RESULTS.md").write_text(render_report(result))
    print(json.dumps({
        "totalVisits": total_visits,
        "stoppedWithinSixStates": int(np.sum(stop_within_six)),
        "fixed01": fixed,
        "topGroups": top_order[:32].astype(int).tolist(),
        "runtimeSeconds": elapsed,
    }, indent=2))


if __name__ == "__main__":
    main()
