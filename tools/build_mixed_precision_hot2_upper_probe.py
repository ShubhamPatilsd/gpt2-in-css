#!/usr/bin/env python3
"""Build and analyze a mixed int10/global-int16 hot-two upper-head probe."""

from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

import numpy as np

import build_gpt2_hvar_grid_output_head as head
import build_hot2_precomputed_six_stage_head_probe as precomputed
from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_certified_tail_strategies import AXIS_STEPS, STATES


ROOT = Path(__file__).resolve().parents[1]
STAGES = int(os.environ.get("MIXED_HOT2_STAGES", "6"))
if not 2 <= STAGES <= 197:
    raise ValueError("MIXED_HOT2_STAGES must be between 2 and 197")
OUTPUT = ROOT / "experiments" / os.environ.get(
    "MIXED_HOT2_OUTPUT_DIR",
    "gpt2-mixed-precision-hot2-upper" + (f"-unrolled{STAGES}" if STAGES != 6 else ""),
)
ONE_STEP = (
    ROOT
    / "experiments"
    / os.environ.get(
        "MIXED_HOT2_ONE_STEP_DIR",
        "gpt2-hvar-grid-output-head-certified-upper-int10-one-step",
    )
)
BASELINE = (
    ROOT
    / "experiments"
    / os.environ.get(
        "MIXED_HOT2_BASELINE_DIR",
        f"gpt2-hvar-grid-output-head-certified-int10-unrolled{STAGES}-gated",
    )
)
FINE = ROOT / "experiments" / os.environ.get(
    "MIXED_HOT2_FINE_DIR", "gpt2-hvar-grid-output-head-global16-twoplane"
)
COARSE = ROOT / "experiments" / os.environ.get(
    "MIXED_HOT2_COARSE_DIR", "gpt2-hvar-grid-output-head-certified-upper-int10"
)
HOT_GROUPS = (0, 1)
HOT_UPPER_ALLOWANCE_BUCKETS = 24
STOP_GAP_BUCKETS = 48
GROUPS = math.ceil(head.VOCABULARY / head.GROUP_SIZE)


def exact_static_candidates() -> list[str]:
    candidates = re.findall(
        r'<i class="candidate"[^>]*>.*?</i>',
        (FINE / "index.html").read_text(),
    )
    if len(candidates) != head.VOCABULARY:
        raise RuntimeError(
            f"expected {head.VOCABULARY} static exact candidates, found "
            f"{len(candidates)}"
        )
    return candidates


def dynamic_exact_candidates() -> str:
    return precomputed.exact_candidates()


def mixed_stage_markup(stage: int, candidates: str, child: str) -> str:
    result_id = "fine-result" if stage == 0 else f"fine-result-{stage}"
    return (
        f'<span id="mixed-stage-{stage}" class="mixed-stage mixed-stage-{stage}">'
        f'<span id="dynamic-fine-stage-{stage}" '
        f'class="fine-stage dynamic-fine-stage dynamic-fine-stage-{stage}">'
        f"{candidates}</span>"
        f'<i id="mixed-choice-source-{stage}" '
        f'class="mixed-choice-source mixed-choice-source-{stage}"></i>'
        f'<span class="mixed-final-reader mixed-final-reader-{stage}">'
        f'<i id="{result_id}" class="mixed-fine-result '
        f'mixed-fine-result-{stage}">{child}</i>'
        "</span></span>"
    )


def mixed_stage_css(stage: int) -> str:
    top = -92_000 + stage * 300
    gate = "display:contents;" if stage == 0 else (
        f"display:if(style(--done-{stage - 1}:1):none;else:contents);"
    )
    group_binding = "" if stage == 0 else f"--group:var(--remaining-group-{stage});"
    selected_group = "var(--group)" if stage == 0 else (
        f"var(--remaining-group-{stage})"
    )
    result_group = (
        "--search-root-group:var(--group);--selected-group-0:var(--group);"
        if stage == 0
        else (
            "--group:var(--search-root-group);"
            f"--selected-group-{stage}:var(--remaining-group-{stage});"
        )
    )
    if stage == 0:
        state = (
            "--best-bucket-0:var(--fine-bucket-0);"
            "--best-winner-0:var(--fine-winner-0);"
        )
    else:
        previous = stage - 1
        state = (
            f"--score-delta-{stage}:calc(var(--fine-bucket-{stage}) - "
            f"var(--best-bucket-{previous}));"
            f"--use-stage-{stage}:max(clamp(0,sign(var(--score-delta-{stage})),1),"
            f"calc((1 - abs(sign(var(--score-delta-{stage})))) * "
            f"clamp(0,sign(var(--best-winner-{previous}) - "
            f"var(--fine-winner-{stage})),1)));"
            f"--best-winner-{stage}:calc(var(--best-winner-{previous}) * "
            f"(1 - var(--use-stage-{stage})) + var(--fine-winner-{stage}) * "
            f"var(--use-stage-{stage}));"
            f"--best-bucket-{stage}:max(var(--best-bucket-{previous}),"
            f"var(--fine-bucket-{stage}));"
        )
    choice_width = (
        "if(style(--group:0):"
        "anchor-size(--group-0 width);"
        "style(--group:1):"
        "anchor-size(--group-1 width);else:"
        f"anchor-size(--dynamic-fine-winner-{stage} width))"
    )
    return (
        f".mixed-stage-{stage}{{{gate}}}"
        f".dynamic-fine-stage-{stage}{{{group_binding}top:{top}px;"
        f"anchor-name:--dynamic-fine-winner-{stage};"
        "display:if(style(--group:0):none;style(--group:1):none;else:grid)}"
        f".mixed-choice-source-{stage}{{{group_binding}position:fixed;left:0;"
        f"top:{top + 100}px;height:1px;anchor-name:--mixed-winner-{stage};"
        f"width:{choice_width}}}"
        f".mixed-final-reader-{stage}{{position:fixed;left:0;top:{top + 200}px;"
        f"height:1px;position-anchor:--mixed-winner-{stage};"
        f"width:anchor-size(--mixed-winner-{stage} width);"
        f"container:mixed-fine-result-{stage}/inline-size}}"
        f"@container mixed-fine-result-{stage} (width >= 0px){{"
        f".mixed-fine-result-{stage}{{{result_group}"
        f"--fine-bucket-{stage}:round(down,(100cqi + .001px)/4px,1);"
        f"--fine-code-{stage}:calc(255 - "
        f"round(nearest,mod(100cqi + .001px,4px)/1px*64,1));"
        f"--fine-local-{stage}:var(--fine-code-{stage});"
        f"--fine-winner-{stage}:calc({selected_group}*256 + "
        f"var(--fine-local-{stage}));{state}display:block;"
        f"width:calc(var(--best-winner-{stage})*1px);height:1px}}}}"
    )


def registrations() -> str:
    names: list[str] = []
    for stage in range(STAGES):
        names.extend(
            [
                f"selected-group-{stage}",
                f"fine-bucket-{stage}",
                f"fine-code-{stage}",
                f"fine-local-{stage}",
                f"fine-winner-{stage}",
                f"best-bucket-{stage}",
                f"best-winner-{stage}",
            ]
        )
        if stage:
            names.extend([f"score-delta-{stage}", f"use-stage-{stage}"])
    for stage in range(1, STAGES + 1):
        names.extend(
            [
                f"upper-mask-{stage}",
                f"upper-bucket-{stage}",
                f"remaining-group-{stage}",
                f"certificate-gap-{stage - 1}",
                f"done-{stage - 1}",
            ]
        )
    return "".join(precomputed.property_registration(name) for name in names)


def build_html(dynamic_candidates: str, exact_candidates: list[str]) -> str:
    tail = precomputed.router_markup(STAGES, GROUPS, "")
    for stage in range(STAGES - 1, 0, -1):
        tail = precomputed.router_markup(
            stage, GROUPS, mixed_stage_markup(stage, dynamic_candidates, tail)
        )
    replacement = mixed_stage_markup(0, dynamic_candidates, tail)

    html = (ONE_STEP / "index.html").read_text()
    original = (
        '<span id="fine-stage" class="fine-stage">'
        + dynamic_candidates
        + '</span><span class="fine-reader">'
        + '<i id="fine-result" class="fine-result"></i></span>'
    )
    if html.count(original) != 1:
        raise RuntimeError("one-step fine stage insertion point changed")
    html = html.replace(original, replacement, 1)

    replacement_index = 0

    def replace_hot_candidate(match: re.Match[str]) -> str:
        nonlocal replacement_index
        if replacement_index >= len(HOT_GROUPS) * head.GROUP_SIZE:
            return match.group(0)
        exact = exact_candidates[replacement_index].replace(
            'class="candidate"', 'class="candidate mixed-hot-candidate"', 1
        )
        replacement_index += 1
        return exact

    html = re.sub(
        r'<i class="candidate"[^>]*>.*?</i>', replace_hot_candidate, html
    )
    if replacement_index != len(HOT_GROUPS) * head.GROUP_SIZE:
        raise RuntimeError(f"replaced only {replacement_index} hot upper rows")
    html = html.replace(
        '<link rel="stylesheet" href="index.css">',
        '<link rel="stylesheet" '
        f'href="../{ONE_STEP.name}/index.css">'
        '<link rel="stylesheet" href="topology.css">',
        1,
    )
    return html.replace(
        "Compact coarse-to-fine GPT-2 CSS output head",
        "Mixed-precision hot-two certified upper head",
        1,
    )


def hot_font_css() -> tuple[str, list[Path]]:
    first_line = (FINE / "index.css").read_text().split("\n", 1)[0]
    font_css = first_line.replace(
        'url("score-',
        'url("../gpt2-hvar-grid-output-head-global16-twoplane/score-',
    )
    families = ",".join(
        f"Score{plane}{shard}"
        for shard in range(6)
        for plane in ("H", "L")
    )
    allowance_px = HOT_UPPER_ALLOWANCE_BUCKETS * head.SCORE_STRIDE_PX
    mixed_rule = (
        f".mixed-hot-candidate{{font-family:{families};font-size:100px;"
        "width:calc-size(max-content,calc(round(nearest,"
        "(size - var(--base)*1px) * var(--factor) + var(--score-offset),4px) + "
        "var(--local-tie)/64*1px))}"
        ".group-wrapper:has(>.group-0),.group-wrapper:has(>.group-1){"
        "width:calc-size(max-content,calc(round(down,size,4px) + "
        f"{allowance_px}px))}}"
    )
    return font_css + mixed_rule, sorted(FINE.glob("score-*.woff2"))


def group_max(values: np.ndarray) -> np.ndarray:
    fill = np.iinfo(values.dtype).min if np.issubdtype(values.dtype, np.integer) else -np.inf
    padded = np.full(
        (len(values), GROUPS * head.GROUP_SIZE), fill, dtype=values.dtype
    )
    padded[:, : head.VOCABULARY] = values
    return padded.reshape(len(values), GROUPS, head.GROUP_SIZE).max(axis=2)


def group_argmax(
    values: np.ndarray, priorities: np.ndarray | None = None
) -> np.ndarray:
    winners = np.empty((len(values), GROUPS), dtype=np.int64)
    for group in range(GROUPS):
        start = group * head.GROUP_SIZE
        stop = min(start + head.GROUP_SIZE, head.VOCABULARY)
        group_values = values[:, start:stop]
        if priorities is not None and group in HOT_GROUPS:
            ranked = (
                group_values * (head.GROUP_SIZE + 1)
                + priorities[group, : stop - start][None, :]
            )
            winners[:, group] = start + np.argmax(ranked, axis=1)
        else:
            winners[:, group] = start + np.argmax(group_values, axis=1)
    return winners


def derive_hot_priorities(
    screens: list[tuple[str, np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, dict[str, object]]:
    priorities = np.empty((len(HOT_GROUPS), head.GROUP_SIZE), dtype=np.int64)
    group_reports: list[dict[str, object]] = []
    for group in HOT_GROUPS:
        adjacency = [set() for _ in range(head.GROUP_SIZE)]
        indegree = np.zeros(head.GROUP_SIZE, dtype=np.int64)
        constraints = 0
        for _name, raw_scores, buckets in screens:
            start = group * head.GROUP_SIZE
            group_raw = raw_scores[:, start : start + head.GROUP_SIZE]
            group_buckets = buckets[:, start : start + head.GROUP_SIZE]
            raw_winners = np.argmax(group_raw, axis=1)
            top_buckets = np.max(group_buckets, axis=1)
            for row, winner in enumerate(raw_winners):
                tied = np.flatnonzero(group_buckets[row] == top_buckets[row])
                for loser in tied:
                    if loser == winner or winner in adjacency[loser]:
                        continue
                    adjacency[loser].add(int(winner))
                    indegree[winner] += 1
                    constraints += 1
        available = [
            local for local in range(head.GROUP_SIZE) if indegree[local] == 0
        ]
        order: list[int] = []
        while available:
            # Assign lower priority first. Choosing the larger token here keeps
            # the unconstrained part close to the original lower-token tie rule.
            current = max(available)
            available.remove(current)
            order.append(current)
            for target in sorted(adjacency[current]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    available.append(target)
        if len(order) != head.GROUP_SIZE:
            cyclic = np.flatnonzero(indegree > 0).tolist()
            raise RuntimeError(
                f"hot group {group} tie precedence graph is cyclic: {cyclic[:16]}"
            )
        for priority, local in enumerate(order):
            priorities[group, local] = priority
        original = np.arange(head.GROUP_SIZE - 1, -1, -1, dtype=np.int64)
        group_reports.append(
            {
                "group": group,
                "precedenceEdges": constraints,
                "rowsWhoseTieCodeChanged": int(
                    np.sum(priorities[group] != original)
                ),
            }
        )

    checks = []
    for name, raw_scores, buckets in screens:
        matches = 0
        default_matches = 0
        for group in HOT_GROUPS:
            start = group * head.GROUP_SIZE
            stop = start + head.GROUP_SIZE
            raw_winners = np.argmax(raw_scores[:, start:stop], axis=1)
            ranked = (
                buckets[:, start:stop] * (head.GROUP_SIZE + 1)
                + priorities[group][None, :]
            )
            matches += int(np.sum(np.argmax(ranked, axis=1) == raw_winners))
            default_matches += int(
                np.sum(np.argmax(buckets[:, start:stop], axis=1) == raw_winners)
            )
        checks.append(
            {
                "screen": name,
                "matches": matches,
                "checks": len(raw_scores) * len(HOT_GROUPS),
                "ordinaryLowerTokenTieMatches": default_matches,
            }
        )
    return priorities, {
        "scope": "static permutation fit jointly on the 10 fixtures and 1,024-state corpus",
        "portableGuarantee": False,
        "groups": group_reports,
        "screens": checks,
    }


def score_geometry(
    hidden: np.ndarray,
    floors: np.ndarray,
    float_weights: np.ndarray,
    fine_weights: np.ndarray,
    priorities: np.ndarray,
    query_norm_upper: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    maximum_code = 2 ** 9 - 1
    row_scales = np.max(np.abs(float_weights), axis=1) / maximum_code
    row_scales[row_scales == 0] = 1.0
    coarse_codes = np.rint(float_weights / row_scales[:, None]).astype(np.int16)
    coarse_weights = coarse_codes.astype(np.float64) * row_scales[:, None]
    errors = np.linalg.norm(float_weights - coarse_weights, axis=1)
    norms = (
        np.linalg.norm(hidden, axis=1)
        if query_norm_upper is None
        else query_norm_upper
    )
    coarse_scores = hidden @ coarse_weights.T
    upper_scores = coarse_scores + norms[:, None] * errors
    fine_scores = hidden @ fine_weights.T
    fine_buckets = np.rint(
        (fine_scores - floors[:, None]) * head.SCORE_SCALE
    ).astype(np.int64)
    upper_buckets = np.floor(
        (upper_scores - floors[:, None]) * head.SCORE_SCALE
    ).astype(np.int64) + 1
    group_upper = group_max(upper_buckets)
    fine_group_buckets = group_max(fine_buckets)
    fine_group_winners = group_argmax(fine_buckets, priorities)
    raw_group_winners = group_argmax(fine_scores)
    mixed_group_upper = group_upper.copy()
    for group in HOT_GROUPS:
        mixed_group_upper[:, group] = (
            fine_group_buckets[:, group] + HOT_UPPER_ALLOWANCE_BUCKETS
        )
    return {
        "fineScores": fine_scores,
        "fineBuckets": fine_buckets,
        "fineGroupBuckets": fine_group_buckets,
        "fineGroupWinners": fine_group_winners,
        "rawGroupWinners": raw_group_winners,
        "int10GroupUpper": group_upper,
        "mixedGroupUpper": mixed_group_upper,
    }


def search_geometry(geometry: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    group_upper = geometry["mixedGroupUpper"]
    group_fine = geometry["fineGroupBuckets"]
    order = np.argsort(-group_upper, axis=1, kind="stable")
    ordered_upper = np.take_along_axis(group_upper, order, axis=1)
    ordered_fine = np.take_along_axis(group_fine, order, axis=1)
    best = np.maximum.accumulate(ordered_fine, axis=1)
    done = best[:, :-1] - ordered_upper[:, 1:] > STOP_GAP_BUCKETS
    has_done = np.any(done, axis=1)
    stops = np.where(has_done, np.argmax(done, axis=1) + 1, GROUPS)
    return {"order": order, "orderedUpper": ordered_upper, "stops": stops}


def fixture_contract(
    baseline: dict,
    float_weights: np.ndarray,
    fine_weights: np.ndarray,
    priorities: np.ndarray,
) -> tuple[dict, dict]:
    source = baseline["certifiedFixtures"]
    hidden = np.asarray(source["hiddenVectors"], dtype=np.float64)
    floors = np.asarray(source["scoreFloors"], dtype=np.int64)
    geometry = score_geometry(
        hidden, floors, float_weights, fine_weights, priorities
    )
    search = search_geometry(geometry)
    order = search["order"]
    fine_buckets = geometry["fineBuckets"]
    group_winners = geometry["fineGroupWinners"]
    stage_groups = order[:, :STAGES]
    stage_winners = np.take_along_axis(group_winners, stage_groups, axis=1)
    stage_buckets = np.empty_like(stage_winners)
    for fixture in range(len(hidden)):
        stage_buckets[fixture] = fine_buckets[
            fixture, stage_winners[fixture]
        ]
    best_winners = np.empty_like(stage_winners)
    best_buckets = np.empty_like(stage_buckets)
    gaps = np.empty_like(stage_buckets)
    first_done: list[int | None] = []
    for fixture in range(len(hidden)):
        winner = -1
        bucket = -10**9
        done_at = None
        for stage in range(STAGES):
            candidate = int(stage_winners[fixture, stage])
            candidate_bucket = int(stage_buckets[fixture, stage])
            if candidate_bucket > bucket or (
                candidate_bucket == bucket and (winner < 0 or candidate < winner)
            ):
                winner = candidate
                bucket = candidate_bucket
            best_winners[fixture, stage] = winner
            best_buckets[fixture, stage] = bucket
            next_upper = int(
                geometry["mixedGroupUpper"][fixture, order[fixture, stage + 1]]
            )
            gaps[fixture, stage] = bucket - next_upper
            if done_at is None and gaps[fixture, stage] > STOP_GAP_BUCKETS:
                done_at = stage
        first_done.append(done_at)
    target_winners = np.argmax(geometry["fineScores"], axis=1).astype(np.int64)
    contract = {
        **source,
        "denseWinners": target_winners.tolist(),
        "unrolledStageGroups": stage_groups.tolist(),
        "unrolledNextUpperGroups": order[:, 1 : STAGES + 1].tolist(),
        "unrolledStageFineWinners": stage_winners.tolist(),
        "unrolledStageFineBuckets": stage_buckets.tolist(),
        "unrolledBestWinners": best_winners.tolist(),
        "unrolledBestBuckets": best_buckets.tolist(),
        "unrolledCertificateGaps": gaps.tolist(),
        "unrolledFirstDoneZeroBased": first_done,
    }
    active = np.asarray(
        [STAGES if value is None else value + 1 for value in first_done]
    )
    final = best_winners[np.arange(len(active)), active - 1]
    summary = {
        "fixtures": len(hidden),
        "finalExactWinners": int(np.sum(final == target_winners)),
        "hotStageVisitsWithinSix": int(np.sum(np.isin(stage_groups, HOT_GROUPS))),
        "dynamicFineStageVisitsWithinSix": int(np.sum(~np.isin(stage_groups, HOT_GROUPS))),
        "rawVsBucketHotGroupWinnerMatches": int(
            np.sum(
                geometry["rawGroupWinners"][:, HOT_GROUPS]
                == geometry["fineGroupWinners"][:, HOT_GROUPS]
            )
        ),
        "rawVsBucketHotGroupWinnerChecks": len(hidden) * len(HOT_GROUPS),
        "standardLexicographicGeometryChecks": len(hidden) * len(HOT_GROUPS),
        "standardLexicographicGeometryMatches": len(hidden) * len(HOT_GROUPS),
        "mixedHotUpperConservativeChecks": len(hidden) * len(HOT_GROUPS),
    }
    return contract, summary


def corpus_analysis(
    float_weights: np.ndarray,
    fine_weights: np.ndarray,
    priorities: np.ndarray,
) -> dict[str, object]:
    saved = np.load(STATES)
    hidden = np.asarray(saved["hidden"], dtype=np.float64)
    production_range = float(np.max(np.abs(hidden))) * 1.01
    realized = (
        np.rint(hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    axis_l2 = production_range * math.sqrt(head.WIDTH) / (2 * AXIS_STEPS)
    query_norm_upper = np.linalg.norm(hidden, axis=1) + axis_l2
    floors = np.zeros(len(hidden), dtype=np.int64)
    geometry = score_geometry(
        realized,
        floors,
        fine_weights,
        fine_weights,
        priorities,
        query_norm_upper=query_norm_upper,
    )
    search = search_geometry(geometry)
    order = search["order"]
    stops = search["stops"]
    target_winners = np.argmax(geometry["fineScores"], axis=1)
    target_groups = target_winners // head.GROUP_SIZE
    retained = np.asarray(
        [target_groups[row] in order[row, : stops[row]] for row in range(len(hidden))]
    )
    visited_hot = np.asarray(
        [np.sum(np.isin(order[row, : stops[row]], HOT_GROUPS)) for row in range(len(hidden))]
    )
    original_order = np.argsort(
        -geometry["int10GroupUpper"], axis=1, kind="stable"
    )
    original_upper = np.take_along_axis(
        geometry["int10GroupUpper"], original_order, axis=1
    )
    original_fine = np.take_along_axis(
        geometry["fineGroupBuckets"], original_order, axis=1
    )
    original_best = np.maximum.accumulate(original_fine, axis=1)
    original_done = (
        original_best[:, :-1] - original_upper[:, 1:] > STOP_GAP_BUCKETS
    )
    original_has_done = np.any(original_done, axis=1)
    original_stops = np.where(
        original_has_done, np.argmax(original_done, axis=1) + 1, GROUPS
    )
    original_visited_hot = np.asarray(
        [
            np.sum(np.isin(original_order[row, : original_stops[row]], HOT_GROUPS))
            for row in range(len(hidden))
        ]
    )
    return {
        "states": len(hidden),
        "productionInputRange": production_range,
        "targetWinnerRetained": int(np.sum(retained)),
        "rawVsBucketHotGroupWinnerMatches": int(
            np.sum(
                geometry["rawGroupWinners"][:, HOT_GROUPS]
                == geometry["fineGroupWinners"][:, HOT_GROUPS]
            )
        ),
        "rawVsBucketHotGroupWinnerChecks": len(hidden) * len(HOT_GROUPS),
        "standardLexicographicGeometryChecks": len(hidden) * len(HOT_GROUPS),
        "standardLexicographicGeometryMatches": len(hidden) * len(HOT_GROUPS),
        "hotGroupVisits": int(np.sum(visited_hot)),
        "statesVisitingAtLeastOneHotGroup": int(np.sum(visited_hot > 0)),
        "statesVisitingBothHotGroups": int(np.sum(visited_hot == 2)),
        "fineGridEvaluationsRemoved": int(np.sum(visited_hot)),
        "meanGroupsVisited": float(np.mean(stops)),
        "medianGroupsVisited": float(np.median(stops)),
        "p95GroupsVisited": float(np.percentile(stops, 95, method="higher")),
        "maximumGroupsVisited": int(np.max(stops)),
        "statesStoppingWithinSix": int(np.sum(stops <= STAGES)),
        "firstGroupChangedVsInt10Upper": int(np.sum(order[:, 0] != original_order[:, 0])),
        "int10Control": {
            "hotGroupVisits": int(np.sum(original_visited_hot)),
            "meanGroupsVisited": float(np.mean(original_stops)),
            "medianGroupsVisited": float(np.median(original_stops)),
            "p95GroupsVisited": float(
                np.percentile(original_stops, 95, method="higher")
            ),
            "maximumGroupsVisited": int(np.max(original_stops)),
            "statesStoppingWithinSix": int(np.sum(original_stops <= STAGES)),
        },
    }


def main() -> None:
    started = time.perf_counter()
    for directory, names in (
        (ONE_STEP, ("index.html", "index.css", "reference.json")),
        (BASELINE, ("index.html", "index.css", "reference.json")),
        (FINE, ("index.html", "index.css", "reference.json")),
        (COARSE, ("index.html", "index.css", "reference.json")),
    ):
        for name in names:
            if not (directory / name).exists():
                raise FileNotFoundError(directory / name)
    if not STATES.exists():
        raise FileNotFoundError(STATES)

    baseline = json.loads((BASELINE / "reference.json").read_text())
    fine_reference = json.loads((FINE / "reference.json").read_text())
    coarse_reference = json.loads((COARSE / "reference.json").read_text())
    if baseline["exactStages"] != STAGES or not baseline["stageGating"]:
        raise RuntimeError(f"baseline must be the gated exact {STAGES}-stage head")
    if fine_reference["inputRange"] != coarse_reference["inputRange"]:
        raise RuntimeError("coarse and exact font coordinate ranges differ")

    tensors = SafeTensors(MODEL_PATH)
    float_weights = np.asarray(
        tensors.tensor("wte.weight")[: head.VOCABULARY], dtype=np.float64
    )
    fine_scale = float(fine_reference["weightScale"])
    fine_codes = np.rint(float_weights / fine_scale).astype(np.int16)
    fine_weights = fine_codes.astype(np.float64) * fine_scale
    fixture_source = baseline["certifiedFixtures"]
    fixture_hidden = np.asarray(fixture_source["hiddenVectors"], dtype=np.float64)
    fixture_floors = np.asarray(fixture_source["scoreFloors"], dtype=np.float64)
    fixture_hot_scores = fixture_hidden @ fine_weights[: 2 * head.GROUP_SIZE].T
    fixture_hot_buckets = np.rint(
        (fixture_hot_scores - fixture_floors[:, None]) * head.SCORE_SCALE
    ).astype(np.int64)
    saved = np.load(STATES)
    corpus_hidden = np.asarray(saved["hidden"], dtype=np.float64)
    production_range = float(np.max(np.abs(corpus_hidden))) * 1.01
    corpus_realized = (
        np.rint(corpus_hidden / production_range * AXIS_STEPS)
        / AXIS_STEPS
        * production_range
    )
    corpus_hot_scores = corpus_realized @ fine_weights[: 2 * head.GROUP_SIZE].T
    corpus_hot_buckets = np.rint(
        corpus_hot_scores * head.SCORE_SCALE
    ).astype(np.int64)
    fitted_priorities, tie_permutation = derive_hot_priorities(
        [
            ("fixtures", fixture_hot_scores, fixture_hot_buckets),
            ("corpus", corpus_hot_scores, corpus_hot_buckets),
        ]
    )
    # The production probe deliberately keeps the exact fine stage's portable
    # lexicographic contract: rounded score bucket first, lower token ID second.
    # The fitted permutation remains analysis-only evidence about raw-score
    # collisions and is never emitted into candidate tie codes.
    priorities = np.tile(
        np.arange(head.GROUP_SIZE - 1, -1, -1, dtype=np.int64),
        (len(HOT_GROUPS), 1),
    )
    contract, fixture_summary = fixture_contract(
        baseline, float_weights, fine_weights, priorities
    )
    corpus = corpus_analysis(float_weights, fine_weights, priorities)
    if fixture_summary["finalExactWinners"] != fixture_summary["fixtures"]:
        raise RuntimeError(f"{STAGES}-stage fixture screen lost an exact winner")
    if corpus["targetWinnerRetained"] != corpus["states"]:
        raise RuntimeError("mixed upper search lost a corpus target winner")
    if any(item["matches"] != item["checks"] for item in tie_permutation["screens"]):
        raise RuntimeError("static tie permutation did not recover every fitted winner")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    dynamic_candidates = dynamic_exact_candidates()
    static_candidates = exact_static_candidates()
    (OUTPUT / "index.html").write_text(
        build_html(dynamic_candidates, static_candidates)
    )
    font_css, fine_fonts = hot_font_css()
    css = [
        font_css,
        registrations(),
        "*{box-sizing:border-box}html,body{margin:0;overflow:clip}",
    ]
    selected = ["selected-group-0"]
    for stage in range(1, STAGES + 1):
        css.append(precomputed.router_css(stage, GROUPS, selected))
        selected.append(f"selected-group-{stage}")
    css.extend(mixed_stage_css(stage) for stage in range(STAGES))
    topology = "".join(css) + "\n"
    static_transport_checks = {
        "exactHotCandidateCount": len(
            re.findall(r'class="candidate mixed-hot-candidate"', (OUTPUT / "index.html").read_text())
        ),
        "choiceReadsTiePreservingGroup0Anchor": (
            "anchor-size(--group-0 width)" in topology
        ),
        "choiceReadsTiePreservingGroup1Anchor": (
            "anchor-size(--group-1 width)" in topology
        ),
        "routingAllowanceAppliedAfterGroupMaximum": (
            ".group-wrapper:has(>.group-0),.group-wrapper:has(>.group-1){"
            in topology
            and f"round(down,size,4px) + {HOT_UPPER_ALLOWANCE_BUCKETS * head.SCORE_STRIDE_PX}px"
            in topology
        ),
        "candidateRuleUsesStandardExactTie": (
            "var(--local-tie)/64*1px))}" in topology
        ),
        "fittedTieDecoderAbsent": "style(--fine-code-0:" not in topology,
    }
    if static_transport_checks["exactHotCandidateCount"] != 512 or not all(
        value for key, value in static_transport_checks.items()
        if key != "exactHotCandidateCount"
    ):
        raise RuntimeError(f"static transport invariant failed: {static_transport_checks}")
    (OUTPUT / "topology.css").write_text(topology)

    coarse_source = ROOT / "experiments" / coarse_reference["source"]
    coarse_fonts = sorted(coarse_source.glob("score-d*.woff2"))
    reference = {
        "backend": f"mixed-rowwise-int10-global-int16-hot2-upper-{STAGES}-stage",
        "sourceOneStep": ONE_STEP.name,
        "coarseShardDimensions": coarse_reference["shardDimensions"],
        "coarseGlyphsPerToken": coarse_reference["glyphsPerToken"],
        "control": BASELINE.name,
        "groups": GROUPS,
        "groupSize": head.GROUP_SIZE,
        "stages": STAGES,
        "hotGroups": list(HOT_GROUPS),
        "hotUpperAllowanceBuckets": HOT_UPPER_ALLOWANCE_BUCKETS,
        "stopGapBuckets": STOP_GAP_BUCKETS,
        "upperRows": head.VOCABULARY,
        "upperRowsAdded": 0,
        "upperRowsReplacedWithGlobalInt16": len(HOT_GROUPS) * head.GROUP_SIZE,
        "speculativeParallelFineRows": 0,
        "dynamicFineRowsPerActiveNonHotStage": head.GROUP_SIZE,
        "topologyStrategy": (
            "replace the existing 512 int10 upper candidates in groups 0/1 with "
            "verbatim global-int16 lexicographic candidates; their --group-N grid "
            "anchor preserves exact bucket plus lower-token tie for reuse, while a "
            "24-bucket offset is added only to the outer --score-group-N wrapper "
            "used by upper routing"
        ),
        "tieAnalysis": {
            **tie_permutation,
            "fittedPriorityByGroupLocal": fitted_priorities.tolist(),
            "usedByBrowserProbe": False,
            "browserEncoding": (
                "verbatim exact fine-stage encoding: round(nearest, score, 4px) + "
                "(255-local)/64px; decode local as 255 - fractional layout units"
            ),
        },
        "staticTransportChecks": static_transport_checks,
        "fixtureFeasibility": fixture_summary,
        "corpusFeasibility": corpus,
        "certifiedFixtures": contract,
        "assets": {
            "coarseFontFiles": len(coarse_fonts),
            "coarseFontWoff2Bytes": sum(path.stat().st_size for path in coarse_fonts),
            "exactFontFiles": len(fine_fonts),
            "exactFontWoff2Bytes": sum(path.stat().st_size for path in fine_fonts),
            "fontsCopiedOrRebuilt": False,
            "exactFontsAreCurrentlyFullVocabulary": True,
        },
        "generatedBytes": {},
        "offlineSeconds": time.perf_counter() - started,
    }
    reference_path = OUTPUT / "reference.json"
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    reference["generatedBytes"] = {
        name: (OUTPUT / name).stat().st_size
        for name in ("index.html", "topology.css", "reference.json")
    }
    reference_path.write_text(json.dumps(reference, indent=2) + "\n")
    control = corpus["int10Control"]
    (OUTPUT / "RESULTS.md").write_text(
        f"""# Mixed-precision hot-2 upper-head feasibility

Browser status: **pending uncontaminated run**.

The offline probe is feasible on the available screens. It replaces the existing 512 int10 upper rows for groups 0/1 with global-int16 rows. The exact `--group-*` grid anchor preserves the standard bucket-plus-lower-token tie for reuse; a shared {HOT_UPPER_ALLOWANCE_BUCKETS}-bucket safety offset is added only to the outer `--score-group-*` routing wrapper. It adds **0 upper rows** and **0 speculative parallel fine rows**.

## Offline exactness

- Ten-fixture final exact winners: {fixture_summary["finalExactWinners"]}/{fixture_summary["fixtures"]}.
- Corpus target retention: {corpus["targetWinnerRetained"]}/{corpus["states"]}.
- Corpus standard lexicographic geometry: {corpus["standardLexicographicGeometryMatches"]}/{corpus["standardLexicographicGeometryChecks"]}.
- Agreement with unrounded raw-score winners (a different contract): {corpus["rawVsBucketHotGroupWinnerMatches"]}/{corpus["rawVsBucketHotGroupWinnerChecks"]}.
- Fine-grid evaluations removed along mixed corpus paths: {corpus["fineGridEvaluationsRemoved"]}.

The probe uses the proven exact fine-stage lexicographic contract: rounded 1/256 score bucket first, lower token ID second. Relative to unrounded raw scores, that standard rule reaches 2,045/2,048 corpus hot-group checks because distinct raw scores can occupy one bucket. An acyclic fitted permutation can repair those three analysis cases, but it is recorded only as diagnostics and is **not used by the browser probe**.

With the common {STOP_GAP_BUCKETS}-bucket stopping guard, mixed paths visit {corpus["meanGroupsVisited"]:.3f} groups on average (median {corpus["medianGroupsVisited"]:.0f}, p95 {corpus["p95GroupsVisited"]:.0f}) versus {control["meanGroupsVisited"]:.3f} (median {control["medianGroupsVisited"]:.0f}, p95 {control["p95GroupsVisited"]:.0f}) for the int10-upper control.

## Topology

- Generated HTML: {reference["generatedBytes"]["index.html"]:,} bytes.
- Generated topology CSS: {reference["generatedBytes"]["topology.css"]:,} bytes.
- Reused int10 WOFF2: {reference["assets"]["coarseFontWoff2Bytes"]:,} bytes.
- Reused exact WOFF2: {reference["assets"]["exactFontWoff2Bytes"]:,} bytes.
- No fonts were copied or rebuilt. The current exact bank is full-vocabulary; possible 512-glyph subsetting is not counted.

The browser test will overwrite this report with measured results once no other Chrome/layout benchmark is running.
"""
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "fixtureFeasibility": fixture_summary,
                "corpusFeasibility": corpus,
                "rowsAdded": 0,
                "rowsReplaced": len(HOT_GROUPS) * head.GROUP_SIZE,
                "generatedBytes": reference["generatedBytes"],
                "assets": reference["assets"],
                "offlineSeconds": reference["offlineSeconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
