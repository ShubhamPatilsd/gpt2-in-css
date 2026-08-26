#!/usr/bin/env python3
"""Offline sweep for in-place exact-upper hot-K policies.

The sweep deliberately emits no browser artifact and launches no browser.  It
replays the retained mixed-precision routing contract on the 1,024-state corpus:
hot groups replace (rather than add to) existing upper rows, expose the standard
rounded-bucket/lower-token winner, and receive the routing allowance only after
the group maximum.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_certified_tail_strategies import AXIS_STEPS, STATES


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-mixed-precision-hotk-sweep"
FINE_REFERENCE = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global16-twoplane" / "reference.json"
)
K_VALUES = (0, 1, 2, 4, 8, 16, 32)
GROUPS = math.ceil(head.VOCABULARY / head.GROUP_SIZE)
HOT_UPPER_ALLOWANCE_BUCKETS = 24
STOP_GAP_BUCKETS = 48
STAGES = 6


def percentile(values: np.ndarray, fraction: float) -> float:
    return float(np.percentile(values, fraction * 100, method="higher"))


def group_max(values: np.ndarray) -> np.ndarray:
    padded = np.full(
        (len(values), GROUPS * head.GROUP_SIZE),
        np.iinfo(values.dtype).min,
        dtype=values.dtype,
    )
    padded[:, : head.VOCABULARY] = values
    return padded.reshape(len(values), GROUPS, head.GROUP_SIZE).max(axis=2)


def lower_token_group_winners(buckets: np.ndarray) -> np.ndarray:
    """Argmax of (bucket, -token), matching the emitted exact CSS tie code."""
    winners = np.empty((len(buckets), GROUPS), dtype=np.int64)
    for group in range(GROUPS):
        start = group * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        # np.argmax returns the first maximum, hence the lower token on a tie.
        winners[:, group] = start + np.argmax(buckets[:, start:stop], axis=1)
    return winners


def stopping_route(
    mixed_upper: np.ndarray, fine_group_buckets: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(-mixed_upper, axis=1, kind="stable")
    ordered_upper = np.take_along_axis(mixed_upper, order, axis=1)
    ordered_fine = np.take_along_axis(fine_group_buckets, order, axis=1)
    best = np.maximum.accumulate(ordered_fine, axis=1)
    done = best[:, :-1] - ordered_upper[:, 1:] > STOP_GAP_BUCKETS
    has_done = np.any(done, axis=1)
    stops = np.where(has_done, np.argmax(done, axis=1) + 1, GROUPS).astype(np.int64)
    return order, stops


def visit_counts(order: np.ndarray, stops: np.ndarray) -> np.ndarray:
    counts = np.zeros(GROUPS, dtype=np.int64)
    for row, stop in enumerate(stops):
        counts[order[row, :stop]] += 1
    return counts


def evaluate_policy(
    name: str,
    selection: str,
    hot_groups: tuple[int, ...],
    int10_upper: np.ndarray,
    fine_group_buckets: np.ndarray,
    fine_group_winners: np.ndarray,
    fine_buckets: np.ndarray,
    target_groups: np.ndarray,
) -> dict[str, object]:
    mixed_upper = int10_upper.copy()
    if hot_groups:
        mixed_upper[:, hot_groups] = (
            fine_group_buckets[:, hot_groups] + HOT_UPPER_ALLOWANCE_BUCKETS
        )
    order, stops = stopping_route(mixed_upper, fine_group_buckets)
    hot_mask = np.zeros(GROUPS, dtype=bool)
    hot_mask[list(hot_groups)] = True
    hot_visits = 0
    retained = 0
    visited_counts = np.zeros(GROUPS, dtype=np.int64)
    for row, stop in enumerate(stops):
        route = order[row, :stop]
        visited_counts[route] += 1
        hot_visits += int(np.sum(hot_mask[route]))
        retained += int(target_groups[row] in route)

    # Independently reconstruct the browser's lexicographic winner from the
    # maximum bucket and the first (lowest-token) position attaining it.
    tie_checks = 0
    tie_matches = 0
    for group in hot_groups:
        start = group * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        local = fine_buckets[:, start:stop]
        local_ids = np.arange(stop - start, dtype=np.int64)
        encoded = (
            local * (head.GROUP_SIZE + 1)
            + (head.GROUP_SIZE - 1 - local_ids)[None, :]
        )
        expected = start + np.argmax(encoded, axis=1)
        tie_checks += len(local)
        tie_matches += int(np.sum(fine_group_winners[:, group] == expected))

    total_visits = int(np.sum(stops))
    dynamic_fine_visits = total_visits - hot_visits
    exact_rows = len(hot_groups) * head.GROUP_SIZE
    mean_dynamic_rows = dynamic_fine_visits * head.GROUP_SIZE / len(stops)
    # Simple topology proxy: candidate rows touched per state. It intentionally
    # counts an in-place upper replacement as one row, not as an added row.
    candidate_row_proxy = head.VOCABULARY + mean_dynamic_rows
    # Precision-weighted companion proxy makes the static/dynamic trade-off
    # visible: int10 row=1 unit, global-int16 row=1.6 units.
    precision_ratio = 16 / 10
    precision_proxy = (
        head.VOCABULARY
        + exact_rows * (precision_ratio - 1)
        + mean_dynamic_rows * precision_ratio
    )
    return {
        "name": name,
        "selection": selection,
        "k": len(hot_groups),
        "groups": list(hot_groups),
        "exactUpperRowsReplaced": exact_rows,
        "upperRowsAdded": 0,
        "fineGridVisitsRemoved": hot_visits,
        "dynamicFineGridVisits": dynamic_fine_visits,
        "totalGroupVisits": total_visits,
        "routeLength": {
            "mean": float(np.mean(stops)),
            "median": float(np.median(stops)),
            "p95": percentile(stops, 0.95),
            "maximum": int(np.max(stops)),
        },
        "statesStoppingWithinSix": int(np.sum(stops <= STAGES)),
        "finalExactTargetRetention": retained,
        "lexicographicTieChecks": tie_checks,
        "lexicographicTieMatches": tie_matches,
        "workProxy": {
            "definition": "upper candidate rows + mean dynamic fine candidate rows per state",
            "candidateRowsPerState": candidate_row_proxy,
            "meanDynamicFineRowsPerState": mean_dynamic_rows,
            "precisionWeightedRowUnitsPerState": precision_proxy,
            "precisionWeights": {"int10": 1.0, "globalInt16": precision_ratio},
        },
        "perGroupVisitCounts": visited_counts.tolist(),
    }


def pareto_indices(rows: list[dict[str, object]]) -> list[int]:
    """Pareto on static exact rows, dynamic work, and route p95."""
    values = [
        (
            int(row["exactUpperRowsReplaced"]),
            float(row["workProxy"]["candidateRowsPerState"]),
            float(row["routeLength"]["p95"]),
        )
        for row in rows
    ]
    result: list[int] = []
    for index, value in enumerate(values):
        dominated = any(
            other != index
            and all(left <= right for left, right in zip(values[other], value))
            and any(left < right for left, right in zip(values[other], value))
            for other in range(len(values))
        )
        if not dominated:
            result.append(index)
    return result


def render_report(result: dict[str, object]) -> str:
    primary = result["policies"]["contiguousLow"]
    diagnostic = result["policies"]["frequencyRanked"]
    pareto = result["pareto"]
    rows = []
    for row in primary:
        rows.append(
            "| {k} | `{groups}` | {exact:,} | {removed:,} | {visits:,} | "
            "{mean:.3f} / {median:.0f} / {p95:.0f} / {maximum} | {within}/1,024 | "
            "{retained}/1,024 | {ties}/{checks} | {proxy:,.1f} |".format(
                k=row["k"],
                groups=",".join(str(group) for group in row["groups"]) or "none",
                exact=row["exactUpperRowsReplaced"],
                removed=row["fineGridVisitsRemoved"],
                visits=row["totalGroupVisits"],
                mean=row["routeLength"]["mean"],
                median=row["routeLength"]["median"],
                p95=row["routeLength"]["p95"],
                maximum=row["routeLength"]["maximum"],
                within=row["statesStoppingWithinSix"],
                retained=row["finalExactTargetRetention"],
                ties=row["lexicographicTieMatches"],
                checks=row["lexicographicTieChecks"],
                proxy=row["workProxy"]["candidateRowsPerState"],
            )
        )
    selection_rows = []
    for low, ranked in zip(primary, diagnostic):
        selection_rows.append(
            f'| {low["k"]} | `{",".join(map(str, low["groups"])) or "none"}` | '
            f'`{",".join(map(str, ranked["groups"])) or "none"}` | '
            f'{ranked["totalGroupVisits"] - low["totalGroupVisits"]:+d} | '
            f'{ranked["dynamicFineGridVisits"] - low["dynamicFineGridVisits"]:+d} |'
        )
    return f"""# Mixed-precision hot-K offline sweep

Browser status: **not launched**. This report is derived entirely from the 1,024-state NumPy corpus.

## Result

Every policy retained **1,024/1,024** final target groups and passed every standard rounded-bucket-then-lower-token tie check. No policy adds rows: each hot row replaces its existing int10 upper row in place.

The deployable primary sweep uses contiguous low groups `0..K-1`. The nondominated K values under static exact rows, candidate-row work, and route p95 are **{", ".join(map(str, pareto["contiguousLowK"]))}**. The smallest browser screen that preserves the useful knees is **{", ".join(map(str, pareto["browserCandidateK"]))}**; K=2 is retained as the measured anchor/control.

| K | Hot groups | Exact upper rows replaced | Fine grids removed | Total group visits | Route mean / median / p95 / max | Stop <=6 | Target retained | Tie checks | Candidate-row proxy/state |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

The candidate-row proxy is `50,257 upper rows + 256 × mean non-hot visits`; it does not pretend that int10 and global-int16 rows have identical browser cost. `offline-results.json` also records a transparent 1.6x precision-weighted companion proxy.

## Group selection check

Frequency ranking is computed once from the K=0 route, then frozen. It is diagnostic because it was selected on this same corpus. Contiguous low IDs remain the browser policy so selection does not depend on the evaluated states.

| K | Contiguous low | K=0 frequency-ranked | Ranked minus low visits | Ranked minus low dynamic fine visits |
|---:|---|---|---:|---:|
{chr(10).join(selection_rows)}

## Pareto interpretation

- Formal objectives: minimize exact upper rows, candidate-row work proxy, and route p95. Values with identical p95 can dominate a larger K when they do no more dynamic work.
- Browser candidates are a deliberately small representative subset of the nondominated frontier, selected at material marginal-work knees plus retained K=2. This is a screening set, not a browser timing conclusion.
- Exact upper rows replaced are `{head.GROUP_SIZE} × K`; `upperRowsAdded` is zero for every K.

Runtime: **{result["runtimeSeconds"]:.2f}s**. No browser or Chrome process was started.
"""


def main() -> None:
    started = time.perf_counter()
    if not STATES.exists() or not FINE_REFERENCE.exists():
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
    fine_weights = np.rint(weights / fine_scale).astype(np.int16).astype(np.float64) * fine_scale
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
    fine_buckets = np.rint(fine_scores * head.SCORE_SCALE).astype(np.int64)
    coarse_scores = realized @ coarse_weights.T
    upper_buckets = (
        np.floor((coarse_scores + query_norm_upper[:, None] * errors) * head.SCORE_SCALE)
        .astype(np.int64)
        + 1
    )
    int10_upper = group_max(upper_buckets)
    fine_group_buckets = group_max(fine_buckets)
    fine_group_winners = lower_token_group_winners(fine_buckets)
    target_winners = np.argmax(fine_scores, axis=1)
    target_groups = target_winners // head.GROUP_SIZE

    control_order, control_stops = stopping_route(int10_upper, fine_group_buckets)
    frequencies = visit_counts(control_order, control_stops)
    ranked_groups = np.argsort(-frequencies, kind="stable").astype(int).tolist()

    contiguous: list[dict[str, object]] = []
    ranked: list[dict[str, object]] = []
    for k in K_VALUES:
        contiguous.append(
            evaluate_policy(
                f"contiguous-low-{k}",
                "predeclared-contiguous-low",
                tuple(range(k)),
                int10_upper,
                fine_group_buckets,
                fine_group_winners,
                fine_buckets,
                target_groups,
            )
        )
        ranked.append(
            evaluate_policy(
                f"frequency-ranked-{k}",
                "diagnostic-ranked-on-k0-corpus",
                tuple(sorted(ranked_groups[:k])),
                int10_upper,
                fine_group_buckets,
                fine_group_winners,
                fine_buckets,
                target_groups,
            )
        )

    for row in [*contiguous, *ranked]:
        if row["finalExactTargetRetention"] != len(hidden):
            raise RuntimeError(f'{row["name"]} lost target retention')
        if row["lexicographicTieMatches"] != row["lexicographicTieChecks"]:
            raise RuntimeError(f'{row["name"]} failed lexicographic tie checks')
        if row["upperRowsAdded"] != 0:
            raise RuntimeError(f'{row["name"]} added rows')

    frontier = [contiguous[index]["k"] for index in pareto_indices(contiguous)]
    # Pick logarithmic knees with a retained measured anchor. Exclude K=0 from
    # candidate builds; it is the existing exact/int10 control, not a new mixed page.
    marginal = []
    for previous, current in zip(contiguous, contiguous[1:]):
        delta_rows = current["exactUpperRowsReplaced"] - previous["exactUpperRowsReplaced"]
        saved_visits = previous["dynamicFineGridVisits"] - current["dynamicFineGridVisits"]
        marginal.append({
            "fromK": previous["k"],
            "toK": current["k"],
            "dynamicFineVisitsSaved": saved_visits,
            "exactRowsAdded": delta_rows,
            "visitsSavedPer256Rows": saved_visits / (delta_rows / head.GROUP_SIZE),
        })
    # K=1,4,8 span the steep early frontier; K=2 is the retained measured point.
    preferred = [k for k in (1, 2, 4, 8) if k in frontier]
    if not preferred:
        preferred = [k for k in frontier if k != 0][:3]

    result = {
        "contract": {
            "states": len(hidden),
            "groups": GROUPS,
            "groupSize": head.GROUP_SIZE,
            "hotKValues": list(K_VALUES),
            "hotUpperAllowanceBuckets": HOT_UPPER_ALLOWANCE_BUCKETS,
            "stopGapBuckets": STOP_GAP_BUCKETS,
            "tie": "rounded 1/256 score bucket, then lower token ID",
            "rowsAdded": 0,
            "execution": "offline NumPy; no browser",
        },
        "selectionEvidence": {
            "k0FrequencyOrder": ranked_groups,
            "k0VisitCounts": frequencies.tolist(),
            "contiguousMatchesFrequencySet": {
                str(k): set(range(k)) == set(ranked_groups[:k]) for k in K_VALUES
            },
        },
        "policies": {"contiguousLow": contiguous, "frequencyRanked": ranked},
        "pareto": {
            "objectives": [
                "exactUpperRowsReplaced:min",
                "candidateRowsPerState:min",
                "routeLength.p95:min",
            ],
            "contiguousLowK": frontier,
            "browserCandidateK": preferred,
            "marginalContiguousLow": marginal,
        },
        "runtimeSeconds": time.perf_counter() - started,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "offline-results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUTPUT / "RESULTS.md").write_text(render_report(result))
    print(json.dumps({
        "paretoK": frontier,
        "browserCandidateK": preferred,
        "rows": [{
            "k": row["k"],
            "groups": row["groups"],
            "visits": row["totalGroupVisits"],
            "removed": row["fineGridVisitsRemoved"],
            "dynamic": row["dynamicFineGridVisits"],
            "p95": row["routeLength"]["p95"],
            "within6": row["statesStoppingWithinSix"],
            "proxy": row["workProxy"]["candidateRowsPerState"],
        } for row in contiguous],
        "runtimeSeconds": result["runtimeSeconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
