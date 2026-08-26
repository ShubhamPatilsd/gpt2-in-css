#!/usr/bin/env python3
"""Screen overlapping IVF lists for the fixed GPT-2 output head.

This is deliberately an offline analysis.  It never changes GPT-2 weights or
hidden states.  Vocabulary rows are assigned to several centroid lists, the
centroids route each saved hidden state, and the original float32 wte/lm_head
rows are the only rows used by the exact second stage.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-overlapping-ivf"
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
BASE_INDEX = ROOT / "experiments" / "gpt2-ivf-group-router" / "index.npz"
VOCABULARY = 50_257
WIDTH = 768
ASSIGNMENTS = (1, 2, 4, 8)
BASE_PROBES = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256)
LEAF_PROBES = (
    1, 2, 3, 4, 5, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256,
    384, 512, 768, 1024,
)
CHILDREN = 4
CHILD_ITERATIONS = int(os.environ.get("GPT2_OVERLAP_CHILD_ITERATIONS", "6"))
ROW_BATCH = int(os.environ.get("GPT2_OVERLAP_ROW_BATCH", "512"))
QUERY_BATCH = int(os.environ.get("GPT2_OVERLAP_QUERY_BATCH", "16"))
VALIDATION_RECALL_TARGET = 0.99
MEAN_CSS_ROW_BUDGET = 2_000
FIXED_CSS_ROW_BUDGET = 2_048


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def array_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    return hashlib.sha256(contiguous.view(np.uint8)).hexdigest()


def stable_top_descending(scores: np.ndarray, count: int) -> np.ndarray:
    """Return top indices, ordered by score descending then ID ascending."""
    if count == scores.shape[1]:
        return np.argsort(-scores, axis=1, kind="stable").astype(np.int32)
    candidates = np.argpartition(scores, scores.shape[1] - count, axis=1)[
        :, -count:
    ]
    values = np.take_along_axis(scores, candidates, axis=1)
    within = np.lexsort((candidates, -values), axis=1)
    return np.take_along_axis(candidates, within, axis=1).astype(np.int32)


def train_local_children(
    vectors: np.ndarray, parent_centers: np.ndarray, parent_labels: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Refine every existing parent into four deterministic local k-means leaves."""
    leaf_centers = np.empty((len(parent_centers) * CHILDREN, WIDTH), dtype=np.float32)
    local_counts = np.zeros(len(leaf_centers), dtype=np.int32)
    for parent in range(len(parent_centers)):
        ids = np.flatnonzero(parent_labels == parent)
        points = vectors[ids]
        if not len(points):
            raise RuntimeError(f"base centroid {parent} is unexpectedly empty")

        # Deterministic farthest-first initialization.  Tiny parent-relative
        # perturbations make the unavoidable duplicate seeds distinct when a
        # parent has fewer than four vocabulary rows.
        chosen: list[int] = []
        first = int(np.argmax(np.sum((points - parent_centers[parent]) ** 2, axis=1)))
        chosen.append(first)
        while len(chosen) < min(CHILDREN, len(points)):
            seed_points = points[np.asarray(chosen)]
            distances = np.sum(
                (points[:, None, :] - seed_points[None, :, :]) ** 2, axis=2
            )
            candidate = int(np.argmax(np.min(distances, axis=1)))
            if candidate in chosen:
                candidate = int(next(i for i in range(len(points)) if i not in chosen))
            chosen.append(candidate)
        centers = points[np.resize(np.asarray(chosen), CHILDREN)].copy()
        if len(points) < CHILDREN:
            for child in range(len(points), CHILDREN):
                dimension = (parent * CHILDREN + child) % WIDTH
                centers[child, dimension] += np.float32((child + 1) * 1e-6)

        labels = np.zeros(len(points), dtype=np.int32)
        for _iteration in range(CHILD_ITERATIONS):
            point_norms = np.sum(points * points, axis=1)
            center_norms = np.sum(centers * centers, axis=1)
            distances = (
                point_norms[:, None]
                + center_norms[None, :]
                - 2.0 * points @ centers.T
            )
            labels = np.argmin(distances, axis=1).astype(np.int32)
            counts = np.bincount(labels, minlength=CHILDREN)
            for child in range(CHILDREN):
                if counts[child]:
                    centers[child] = np.mean(points[labels == child], axis=0)
                else:
                    nearest = np.min(distances, axis=1)
                    replacement = int(np.argmax(nearest))
                    centers[child] = points[replacement]
                    dimension = (parent * CHILDREN + child) % WIDTH
                    centers[child, dimension] += np.float32((child + 1) * 1e-6)

        offset = parent * CHILDREN
        leaf_centers[offset : offset + CHILDREN] = centers
        local_counts[offset : offset + CHILDREN] = np.bincount(
            labels, minlength=CHILDREN
        )
    return leaf_centers, local_counts


def metric_scores(
    vectors: np.ndarray, centers: np.ndarray, metric: str, *, assignment: bool
) -> np.ndarray:
    dots = vectors @ centers.T
    if metric == "raw-dot":
        return dots
    if metric == "cosine":
        center_norms = np.maximum(np.linalg.norm(centers, axis=1), 1e-12)
        # Query normalization is a common positive factor and cannot change the
        # ranking.  Assignment must normalize each vocabulary row as well.
        scores = dots / center_norms[None, :]
        if assignment:
            vector_norms = np.maximum(np.linalg.norm(vectors, axis=1), 1e-12)
            scores = scores / vector_norms[:, None]
        return scores
    if metric == "l2-mips":
        if assignment:
            # Negative squared L2 distance, omitting the row-only term.
            return 2.0 * dots - np.sum(centers * centers, axis=1)[None, :]
        # Hidden states and embedding rows do not share a useful L2 scale.  The
        # MIPS-consistent representative of an L2-built list is centroid dot.
        return dots
    raise ValueError(f"unknown metric: {metric}")


def assign_rows(
    weights: np.ndarray, centers: np.ndarray, metric: str
) -> np.ndarray:
    assignments = np.empty((len(weights), max(ASSIGNMENTS)), dtype=np.int32)
    for start in range(0, len(weights), ROW_BATCH):
        batch = weights[start : start + ROW_BATCH]
        scores = metric_scores(batch, centers, metric, assignment=True)
        assignments[start : start + len(batch)] = stable_top_descending(
            scores, max(ASSIGNMENTS)
        )
    return assignments


def query_order(hidden: np.ndarray, centers: np.ndarray, metric: str) -> np.ndarray:
    scores = metric_scores(hidden, centers, metric, assignment=False)
    return stable_top_descending(scores, len(centers))


def higher_percentile(values: np.ndarray, percentile: float) -> float:
    return float(np.percentile(values, percentile, method="higher"))


def stats(values: np.ndarray) -> dict[str, float | int]:
    return {
        "mean": float(np.mean(values)),
        "p95": higher_percentile(values, 95),
        "maximum": int(np.max(values)),
    }


def list_statistics(sizes: np.ndarray, assignment_count: int) -> dict[str, Any]:
    return {
        "assignmentCount": assignment_count,
        "totalListEntries": int(np.sum(sizes)),
        "uniqueVocabularyRows": VOCABULARY,
        "duplicateEntriesBeyondUnique": int(np.sum(sizes) - VOCABULARY),
        "duplicationFactor": float(np.sum(sizes) / VOCABULARY),
        "emptyLists": int(np.sum(sizes == 0)),
        "minimum": int(np.min(sizes)),
        "mean": float(np.mean(sizes)),
        "median": float(np.median(sizes)),
        "p95": higher_percentile(sizes, 95),
        "maximum": int(np.max(sizes)),
        "fixedDomSlotsPerSelectedList": int(np.max(sizes)),
    }


def evaluate_metric(
    assignments8: np.ndarray,
    order: np.ndarray,
    split_ids: dict[str, np.ndarray],
    probes: tuple[int, ...],
) -> dict[str, Any]:
    center_count = order.shape[1]
    inverse = np.empty_like(order)
    inverse[np.arange(len(order))[:, None], order] = np.arange(center_count)
    output: dict[str, Any] = {}

    for assignment_count in ASSIGNMENTS:
        selected_assignments = assignments8[:, :assignment_count]
        sizes = np.bincount(
            selected_assignments.ravel(), minlength=center_count
        ).astype(np.int32)
        max_list_size = int(np.max(sizes))
        summed_entries = np.cumsum(sizes[order], axis=1, dtype=np.int64)
        unique_counts = np.empty((len(order), len(probes)), dtype=np.int32)
        winner_ranks = np.empty(len(order), dtype=np.int32)

        for start in range(0, len(order), QUERY_BATCH):
            stop = min(start + QUERY_BATCH, len(order))
            gathered = inverse[start:stop, selected_assignments]
            minimum_rank = np.min(gathered, axis=2)
            for probe_index, probe in enumerate(probes):
                unique_counts[start:stop, probe_index] = np.sum(
                    minimum_rank < probe, axis=1
                )
            winner_ranks[start:stop] = minimum_rank[
                np.arange(stop - start), DENSE_WINNERS[start:stop]
            ]

        split_results: dict[str, Any] = {}
        for split_name, ids in split_ids.items():
            probe_results: dict[str, Any] = {}
            for probe_index, probe in enumerate(probes):
                unique = unique_counts[ids, probe_index].astype(np.int64)
                entries = summed_entries[ids, probe - 1]
                padded_entries = probe * max_list_size
                found = winner_ranks[ids] < probe
                unique_with_centers = unique + center_count
                entries_with_centers = entries + center_count
                padded_with_centers = padded_entries + center_count
                probe_results[str(probe)] = {
                    "winnerInclusionCount": int(np.sum(found)),
                    "exactWinnerRecall": float(np.mean(found)),
                    "uniqueRows": stats(unique),
                    "uniqueRowsIncludingCentroids": stats(unique_with_centers),
                    "summedListEntriesWithDuplicates": stats(entries),
                    "cssRowsIncludingCentroids": stats(entries_with_centers),
                    "fixedPaddedListEntries": int(padded_entries),
                    "fixedPaddedRowsIncludingCentroids": int(padded_with_centers),
                    "fixedDomSlotsPerSelectedList": max_list_size,
                    "meanDuplicateInflationOverUnion": float(
                        np.mean(entries / np.maximum(unique, 1))
                    ),
                }
            split_results[split_name] = {
                "examples": int(len(ids)), "probes": probe_results
            }
        output[str(assignment_count)] = {
            "listStatistics": list_statistics(sizes, assignment_count),
            "splits": split_results,
        }
    return output


def candidates_from_validation(sweeps: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for codebook_name, codebook in sweeps.items():
        for metric_name, metric in codebook["metrics"].items():
            for assignment_count, assignment in metric["assignments"].items():
                probes = assignment["splits"]["validation"]["probes"]
                for probe_count, values in probes.items():
                    candidates.append(
                        {
                            "codebook": codebook_name,
                            "metric": metric_name,
                            "assignmentCount": int(assignment_count),
                            "probeCount": int(probe_count),
                            "validationRecall": values["exactWinnerRecall"],
                            "validationMeanUniqueRowsIncludingCentroids": values[
                                "uniqueRowsIncludingCentroids"
                            ]["mean"],
                            "validationMeanCssRowsIncludingCentroids": values[
                                "cssRowsIncludingCentroids"
                            ]["mean"],
                            "validationMaxCssRowsIncludingCentroids": values[
                                "cssRowsIncludingCentroids"
                            ]["maximum"],
                            "fixedPaddedRowsIncludingCentroids": values[
                                "fixedPaddedRowsIncludingCentroids"
                            ],
                            "fixedDomSlotsPerSelectedList": values[
                                "fixedDomSlotsPerSelectedList"
                            ],
                        }
                    )
    return candidates


def select_validation_only(sweeps: dict[str, Any]) -> dict[str, Any]:
    candidates = candidates_from_validation(sweeps)
    recall_ok = [
        item for item in candidates
        if item["validationRecall"] >= VALIDATION_RECALL_TARGET
    ]
    fixed_ok = [
        item for item in recall_ok
        if item["fixedPaddedRowsIncludingCentroids"] <= FIXED_CSS_ROW_BUDGET
    ]
    mean_ok = [
        item for item in recall_ok
        if item["validationMeanCssRowsIncludingCentroids"] < MEAN_CSS_ROW_BUDGET
    ]
    fixed_budget_pool = [
        item for item in candidates
        if item["fixedPaddedRowsIncludingCentroids"] <= FIXED_CSS_ROW_BUDGET
    ]
    mean_budget_pool = [
        item for item in candidates
        if item["validationMeanCssRowsIncludingCentroids"] < MEAN_CSS_ROW_BUDGET
    ]

    def best_recall(pool: list[dict[str, Any]], cost_name: str) -> dict[str, Any] | None:
        if not pool:
            return None
        return min(
            pool,
            key=lambda item: (
                -item["validationRecall"], item[cost_name],
                item["validationMeanCssRowsIncludingCentroids"],
                item["assignmentCount"], item["probeCount"], item["metric"],
            ),
        )

    recall_floor_candidate = (
        min(
            recall_ok,
            key=lambda item: (
                item["validationMeanCssRowsIncludingCentroids"],
                item["fixedPaddedRowsIncludingCentroids"],
                -item["validationRecall"], item["assignmentCount"],
                item["probeCount"], item["metric"],
            ),
        )
        if recall_ok else None
    )
    fixed_budget_candidate = best_recall(
        fixed_budget_pool, "fixedPaddedRowsIncludingCentroids"
    )
    mean_budget_candidate = best_recall(
        mean_budget_pool, "validationMeanCssRowsIncludingCentroids"
    )

    pool = fixed_ok if fixed_ok else mean_ok
    mode = "fixed-2048" if fixed_ok else "mean-under-2000"
    if not pool:
        # Keep a concrete, validation-locked diagnostic index even on no-go.  It
        # is the cheapest point that reaches the validation recall floor; test
        # is still absent from this choice.
        return {
            "status": "no-validation-feasible-candidate",
            "mode": "diagnostic-recall-floor",
            "candidate": recall_floor_candidate,
            "candidateMeetsCombinedValidationConstraints": False,
            "validationRecallEligibleCandidates": len(recall_ok),
            "fixedBudgetEligibleCandidates": 0,
            "meanBudgetEligibleCandidates": 0,
            "validationFrontier": {
                "cheapestAtRecallFloor": recall_floor_candidate,
                "bestInsideMeanBudget": mean_budget_candidate,
                "bestInsideFixedBudget": fixed_budget_candidate,
            },
        }

    # Validation decides everything: maximize recall inside the credible budget,
    # then minimize the applicable CSS cost, duplicate assignment count, probes,
    # and centroid count.  Test values are not consulted here.
    def key(item: dict[str, Any]) -> tuple[Any, ...]:
        primary_cost = (
            item["fixedPaddedRowsIncludingCentroids"]
            if mode == "fixed-2048"
            else item["validationMeanCssRowsIncludingCentroids"]
        )
        return (
            -item["validationRecall"],
            primary_cost,
            item["validationMeanCssRowsIncludingCentroids"],
            item["assignmentCount"],
            item["probeCount"],
            0 if item["codebook"] == "ivf-256" else 1,
            item["metric"],
        )

    selected = min(pool, key=key)
    return {
        "status": "locked-on-validation",
        "mode": mode,
        "candidate": selected,
        "candidateMeetsCombinedValidationConstraints": True,
        "validationRecallEligibleCandidates": len(recall_ok),
        "fixedBudgetEligibleCandidates": len(fixed_ok),
        "meanBudgetEligibleCandidates": len(mean_ok),
        "validationFrontier": {
            "cheapestAtRecallFloor": recall_floor_candidate,
            "bestInsideMeanBudget": mean_budget_candidate,
            "bestInsideFixedBudget": fixed_budget_candidate,
        },
    }


def lookup_probe(sweeps: dict[str, Any], candidate: dict[str, Any], split: str) -> dict[str, Any]:
    return sweeps[candidate["codebook"]]["metrics"][candidate["metric"]][
        "assignments"
    ][str(candidate["assignmentCount"])]["splits"][split]["probes"][
        str(candidate["probeCount"])
    ]


def invert_lists(assignments: np.ndarray, center_count: int) -> tuple[np.ndarray, np.ndarray]:
    buckets: list[list[int]] = [[] for _ in range(center_count)]
    for token, centers in enumerate(assignments):
        for center in centers:
            buckets[int(center)].append(token)
    offsets = np.zeros(center_count + 1, dtype=np.int64)
    for center, bucket in enumerate(buckets):
        offsets[center + 1] = offsets[center] + len(bucket)
    entries = np.fromiter(
        (token for bucket in buckets for token in bucket),
        dtype=np.int32,
        count=int(offsets[-1]),
    )
    return offsets, entries


def write_deterministic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """Write an npz with stable ordering and ZIP metadata."""
    with zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.save(buffer, arrays[name], allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)


def selected_exact_oracle(
    weights: np.ndarray,
    hidden: np.ndarray,
    dense_winners: np.ndarray,
    assignments: np.ndarray,
    order: np.ndarray,
    probes: int,
) -> dict[str, Any]:
    matched = 0
    included = 0
    for query_id in range(len(hidden)):
        selected = order[query_id, :probes]
        mask = np.any(
            assignments[:, :, None] == selected[None, None, :], axis=(1, 2)
        )
        candidates = np.flatnonzero(mask)
        candidate_winner = int(candidates[np.argmax(weights[candidates] @ hidden[query_id])])
        winner_present = bool(mask[dense_winners[query_id]])
        included += int(winner_present)
        matched += int(winner_present and candidate_winner == dense_winners[query_id])
        if winner_present and candidate_winner != dense_winners[query_id]:
            raise AssertionError("candidate exact scan disagrees with dense oracle")
    return {
        "queries": int(len(hidden)),
        "denseWinnerIncluded": included,
        "includedQueriesWhoseExactCandidateArgmaxMatchesDense": matched,
        "allIncludedQueriesMatch": bool(matched == included),
    }


def render_results(result: dict[str, Any]) -> str:
    selection = result["selection"]
    lines = [
        "# GPT-2 overlapping IVF output-head screen",
        "",
        "## Decision",
        "",
    ]
    if selection["candidate"] is None:
        lines.extend(
            [
                "**NO-GO.** No configuration reached 99% validation recall inside",
                "the CSS-realistic mean 2,000-row budget (and none fit fixed 2,048).",
            ]
        )
    else:
        candidate = selection["candidate"]
        reveal = selection["testReveal"]
        decision = selection["decision"]
        verdict = "GO" if decision == "go" else "NO-GO"
        if selection["candidateMeetsCombinedValidationConstraints"]:
            description = "the feasible operating point"
        else:
            description = "the cheapest diagnostic point reaching 99% validation recall"
        lines.extend(
            [
                f"**{verdict}.** Validation locked {description}:",
                f"`{candidate['codebook']}` / `{candidate['metric']}` /",
                f"A={candidate['assignmentCount']} / P={candidate['probeCount']}.",
                f"Untouched-test recall after locking is {reveal['exactWinnerRecall']:.3%}.",
                "",
                "The decision uses duplicated list entries, not the deduplicated union.",
                f"Test mean CSS rows including centroids are {reveal['cssRowsIncludingCentroids']['mean']:.1f};",
                f"the fixed padded topology is {reveal['fixedPaddedRowsIncludingCentroids']} rows.",
            ]
        )
        if not selection["candidateMeetsCombinedValidationConstraints"]:
            lines.extend(
                [
                    "No validation configuration simultaneously reaches 99% recall",
                    "and stays below 2,000 mean CSS-realistic rows; none fits fixed 2,048.",
                ]
            )

    lines.extend(
        [
            "",
            "## Validation-locked diagnostic configuration by split",
            "",
            "| Split | Recall | Unique rows + centroids mean / p95 / max | CSS duplicate rows + centroids mean / p95 / max | Fixed padded rows |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    if selection["candidate"] is not None:
        for split in ("train", "validation", "test"):
            values = selection["lockedMetrics"][split]
            unique = values["uniqueRowsIncludingCentroids"]
            css = values["cssRowsIncludingCentroids"]
            lines.append(
                f"| {split} | {values['exactWinnerRecall']:.3%} | "
                f"{unique['mean']:.1f} / {unique['p95']:.0f} / {unique['maximum']} | "
                f"{css['mean']:.1f} / {css['p95']:.0f} / {css['maximum']} | "
                f"{values['fixedPaddedRowsIncludingCentroids']} |"
            )

    frontier = selection.get("validationFrontier", {})
    if frontier:
        lines.extend(
            [
                "",
                "## Validation frontier",
                "",
                "| Validation-only criterion | Configuration | Recall | Mean unique rows | Mean CSS rows | Max list / fixed padded rows |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for label, key in (
            ("Cheapest at >=99% recall", "cheapestAtRecallFloor"),
            ("Best below 2,000 mean rows", "bestInsideMeanBudget"),
            ("Best within fixed 2,048", "bestInsideFixedBudget"),
        ):
            item = frontier.get(key)
            if item is None:
                lines.append(f"| {label} | none | - | - | - | - |")
                continue
            config = (
                f"`{item['codebook']}` `{item['metric']}` "
                f"A={item['assignmentCount']} P={item['probeCount']}"
            )
            lines.append(
                f"| {label} | {config} | {item['validationRecall']:.3%} | "
                f"{item['validationMeanUniqueRowsIncludingCentroids']:.1f} | "
                f"{item['validationMeanCssRowsIncludingCentroids']:.1f} | "
                f"{item['fixedDomSlotsPerSelectedList']} / "
                f"{item['fixedPaddedRowsIncludingCentroids']} |"
            )

        recall_floor = frontier.get("cheapestAtRecallFloor")
        mean_budget = frontier.get("bestInsideMeanBudget")
        if (
            recall_floor is not None
            and mean_budget is not None
            and recall_floor["assignmentCount"] == 1
        ):
            lines.extend(
                [
                    "",
                    "The cheapest validation recall-floor point falls back to A=1;",
                    "overlap does not buy the target operating point. The best mean-budget",
                    f"point uses A={mean_budget['assignmentCount']} and exposes the deployment gap:",
                    f"{mean_budget['validationMeanUniqueRowsIncludingCentroids']:.1f} deduplicated",
                    f"rows versus {mean_budget['validationMeanCssRowsIncludingCentroids']:.1f}",
                    "actual list-entry rows, with fixed padding dominated by its",
                    f"{mean_budget['fixedDomSlotsPerSelectedList']}-entry largest list.",
                ]
            )

    lines.extend(
        [
            "",
            "## What was screened",
            "",
            "The unchanged 50,257 float32 `wte.weight` rows were assigned to their",
            "top A=1,2,4,8 lists. `l2-mips` uses nearest-centroid L2 assignment",
            "with centroid dot-product query routing; `raw-dot` uses dot product for",
            "both; `cosine` normalizes rows and centers for assignment and ranks",
            "queries by normalized-centroid dot product. The first codebook is the",
            "existing 256-centroid index byte-for-byte. The finer codebook refines",
            "each existing parent with four deterministic local k-means children,",
            "then scores all 1,024 leaves flat so there is no parent-routing miss.",
            "",
            "Every probe point in `results.json` reports exact winner inclusion and",
            "mean/p95/max for (1) the unique union, an unattainable lower bound for",
            "this CSS deployment, and (2) summed list entries with duplicates. It",
            "also reports fixed padding as P times the largest list. Validation alone",
            "chooses the configuration; test is revealed only after that lock.",
            "",
            "## CSS scoring topology",
            "",
            "1. Score 256 or 1,024 centroid rows against the 768-value hidden state.",
            "2. Select the top P centroid/list banks.",
            "3. Score each bank's original GPT-2 rows exactly. Overlapping token rows",
            "   occupy and score duplicate DOM entries; no dynamic deduplication is",
            "   assumed. A uniform bank allocates the global maximum list length.",
            "4. Reduce all list-entry scores to one argmax. Duplicate token IDs are",
            "   harmless for correctness but fully charged in deployment size.",
            "",
            "## Oracle and reproducibility",
            "",
            f"The brute-force float32 head reproduced {result['oracleChecks']['savedDenseWinnerMatches']}",
            f"of {result['corpus']['states']} saved winners. The locked diagnostic",
            "candidate's exact scans agree with the dense winner whenever it is present.",
            "Hashes in `results.json` bind the states, unchanged output-head rows,",
            "starting index, and deterministic production `index.npz`.",
            "",
            "```sh",
            "python3 tools/analyze_gpt2_overlapping_ivf.py",
            "python3 -m py_compile tools/analyze_gpt2_overlapping_ivf.py",
            "python3 -m json.tool experiments/gpt2-overlapping-ivf/results.json >/dev/null",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    global DENSE_WINNERS
    if not STATES.exists() or not BASE_INDEX.exists():
        raise RuntimeError("missing saved states or existing 256-centroid IVF index")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    saved = np.load(STATES, allow_pickle=False)
    hidden = saved["hidden"].astype(np.float32)
    DENSE_WINNERS = saved["dense_winners"].astype(np.int64)
    split_ids = {
        name: saved[f"{name}_ids"].astype(np.int64)
        for name in ("train", "validation", "test")
    }
    if hidden.shape != (1024, WIDTH):
        raise RuntimeError(f"unexpected hidden-state shape: {hidden.shape}")
    if len(set(np.concatenate(list(split_ids.values())).tolist())) != len(hidden):
        raise RuntimeError("train/validation/test IDs must be a disjoint partition")

    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY], dtype=np.float32
    )
    base = np.load(BASE_INDEX, allow_pickle=False)
    base_centers = base["centers"].astype(np.float32)
    base_labels = base["labels"].astype(np.int32)
    if weights.shape != (VOCABULARY, WIDTH) or base_centers.shape != (256, WIDTH):
        raise RuntimeError("unexpected GPT-2 row or base-center shape")

    # Full-head brute force in bounded batches; this is the ground truth against
    # which every list-inclusion result is interpreted.
    brute_winners = np.empty(len(hidden), dtype=np.int64)
    for start in range(0, len(hidden), 32):
        logits = hidden[start : start + 32] @ weights.T
        brute_winners[start : start + len(logits)] = np.argmax(logits, axis=1)
    dense_matches = int(np.sum(brute_winners == DENSE_WINNERS))
    if dense_matches != len(hidden):
        mismatch = np.flatnonzero(brute_winners != DENSE_WINNERS)[:8]
        raise AssertionError(f"saved dense winners disagree at {mismatch.tolist()}")

    print("training deterministic 256x4 local refinement", flush=True)
    leaf_centers, local_leaf_counts = train_local_children(
        weights, base_centers, base_labels
    )
    codebooks = {
        "ivf-256": (base_centers, BASE_PROBES),
        "hierarchical-256x4-flat-1024": (leaf_centers, LEAF_PROBES),
    }
    metrics = ("l2-mips", "raw-dot", "cosine")
    sweeps: dict[str, Any] = {}
    assignments_cache: dict[tuple[str, str], np.ndarray] = {}
    orders_cache: dict[tuple[str, str], np.ndarray] = {}

    for codebook_name, (centers, probes) in codebooks.items():
        print(f"screening {codebook_name} ({len(centers)} centers)", flush=True)
        codebook_metrics: dict[str, Any] = {}
        for metric in metrics:
            print(f"  assigning/routing {metric}", flush=True)
            assignments8 = assign_rows(weights, centers, metric)
            order = query_order(hidden, centers, metric)
            assignments_cache[(codebook_name, metric)] = assignments8
            orders_cache[(codebook_name, metric)] = order
            codebook_metrics[metric] = {
                "assignmentScore": {
                    "l2-mips": "negative squared L2",
                    "raw-dot": "raw centroid dot product",
                    "cosine": "row/centroid cosine similarity",
                }[metric],
                "queryScore": {
                    "l2-mips": "MIPS-consistent raw centroid dot product",
                    "raw-dot": "raw centroid dot product",
                    "cosine": "dot product with unit-normalized centroid",
                }[metric],
                "assignments": evaluate_metric(
                    assignments8, order, split_ids, probes
                ),
            }
        sweeps[codebook_name] = {
            "centroids": len(centers),
            "probeCounts": list(probes),
            "metrics": codebook_metrics,
        }

    selection = select_validation_only(sweeps)
    index_arrays: dict[str, np.ndarray] = {
        "base_centers": base_centers,
        "base_labels": base_labels,
        "leaf_centers": leaf_centers,
        "leaf_parent": np.repeat(np.arange(256, dtype=np.int32), CHILDREN),
        "local_leaf_counts": local_leaf_counts,
    }
    oracle_selected: dict[str, Any] | None = None
    if selection["candidate"] is not None:
        candidate = selection["candidate"]
        locked_metrics = {
            split: lookup_probe(sweeps, candidate, split)
            for split in ("train", "validation", "test")
        }
        test_reveal = locked_metrics["test"]
        selection["lockedMetrics"] = locked_metrics
        selection["testReveal"] = test_reveal
        if not selection["candidateMeetsCombinedValidationConstraints"]:
            selection["decision"] = "no-go-validation-budget"
        elif test_reveal["exactWinnerRecall"] < VALIDATION_RECALL_TARGET:
            selection["decision"] = "no-go-test-recall"
        else:
            selection["decision"] = "go"
        key = (candidate["codebook"], candidate["metric"])
        locked_assignments = assignments_cache[key][
            :, :candidate["assignmentCount"]
        ]
        locked_order = orders_cache[key]
        locked_centers = codebooks[candidate["codebook"]][0]
        offsets, entries = invert_lists(locked_assignments, len(locked_centers))
        index_arrays.update(
            {
                "selected_centers": locked_centers,
                "selected_row_assignments": locked_assignments,
                "selected_list_offsets": offsets,
                "selected_list_entries": entries,
                "selected_assignment_count": np.asarray(
                    [candidate["assignmentCount"]], dtype=np.int32
                ),
                "selected_probe_count": np.asarray(
                    [candidate["probeCount"]], dtype=np.int32
                ),
                "selected_fixed_slots_per_list": np.asarray(
                    [np.max(np.diff(offsets))], dtype=np.int32
                ),
            }
        )
        oracle_selected = selected_exact_oracle(
            weights,
            hidden,
            DENSE_WINNERS,
            locked_assignments,
            locked_order,
            candidate["probeCount"],
        )
    else:
        selection["decision"] = "no-go"

    index_path = OUTPUT / "index.npz"
    write_deterministic_npz(index_path, index_arrays)
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "model": "openai-community/gpt2",
        "fixedModelAndHead": True,
        "corpus": {
            "states": int(len(hidden)),
            "width": WIDTH,
            "train": int(len(split_ids["train"])),
            "validation": int(len(split_ids["validation"])),
            "test": int(len(split_ids["test"])),
            "splitsAreDisjoint": True,
        },
        "screen": {
            "assignmentCounts": list(ASSIGNMENTS),
            "childIterations": CHILD_ITERATIONS,
            "validationRecallTarget": VALIDATION_RECALL_TARGET,
            "meanCssRowsIncludingCentroidsBudgetExclusive": MEAN_CSS_ROW_BUDGET,
            "fixedPaddedRowsIncludingCentroidsBudgetInclusive": FIXED_CSS_ROW_BUDGET,
            "selectionUsesTest": False,
            "cssAccountingIncludesDuplicateListEntries": True,
            "fixedPaddingUsesGlobalMaximumListLength": True,
        },
        "hashes": {
            "statesNpzSha256": file_sha256(STATES),
            "wteRowsFloat32Sha256": array_sha256(weights),
            "startingIndexNpzSha256": file_sha256(BASE_INDEX),
            "startingCentersFloat32Sha256": array_sha256(base_centers),
            "productionIndexNpzSha256": file_sha256(index_path),
        },
        "codebookBuild": {
            "ivf-256": "unchanged centers from existing index",
            "hierarchical-256x4-flat-1024": {
                "parents": 256,
                "childrenPerParent": CHILDREN,
                "localKmeansIterations": CHILD_ITERATIONS,
                "queryScoring": "all 1024 leaves flat",
                "offlineLocalLeafOccupancy": list_statistics(local_leaf_counts, 1),
            },
        },
        "sweeps": sweeps,
        "selection": selection,
        "oracleChecks": {
            "bruteForceHeadQueries": int(len(hidden)),
            "savedDenseWinnerMatches": dense_matches,
            "allSavedDenseWinnersMatch": bool(dense_matches == len(hidden)),
            "selectedCandidateExactScan": oracle_selected,
            "fullProbeCoversAllRowsByConstruction": True,
        },
    }
    results_path = OUTPUT / "results.json"
    results_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "RESULTS.md").write_text(render_results(result))
    print(
        json.dumps(
            {
                "selection": selection,
                "index": str(index_path.relative_to(ROOT)),
                "results": str(results_path.relative_to(ROOT)),
            },
            indent=2,
        ),
        flush=True,
    )


DENSE_WINNERS = np.empty(0, dtype=np.int64)


if __name__ == "__main__":
    main()
