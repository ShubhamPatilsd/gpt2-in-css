#!/usr/bin/env python3
"""Evaluate fixed-round batched frontiers on the exported real HNSW graph."""

from __future__ import annotations

import hashlib
import heapq
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-hnsw-batched-frontier"
GRAPH_PATH = ROOT / "experiments" / "gpt2-hnsw-trace" / "layer0_adjacency.npz"
STATES_PATH = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
IVF_PATH = ROOT / "experiments" / "gpt2-ivf-group-router" / "index.npz"
VOCABULARY = 50_257
WIDTH = 768
STATE_COUNT = 1_024
SEED_COUNT = 256
MAX_LAYER0_DEGREE = 64
BEAMS = (1, 2, 4, 8, 16, 32)
ROUND_CHECKPOINTS = (2, 4, 6, 8, 12, 16)
SPLITS = ("train", "validation", "test")
ORACLE_BATCH = 32


def sha256_array(values: np.ndarray) -> str:
    digest = hashlib.sha256()
    view = np.ascontiguousarray(values).view(np.uint8).reshape(-1)
    for start in range(0, view.size, 8 * 1024 * 1024):
        digest.update(view[start : start + 8 * 1024 * 1024])
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def stats(values: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(values)
    return {
        "mean": float(np.mean(values)),
        "p50": int(np.percentile(values, 50, method="higher")),
        "p95": int(np.percentile(values, 95, method="higher")),
        "max": int(np.max(values)),
    }


def load_inputs() -> tuple[
    np.ndarray,
    np.ndarray,
    dict[str, np.ndarray],
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    for path in (GRAPH_PATH, STATES_PATH, IVF_PATH, MODEL_PATH):
        if not path.exists():
            raise RuntimeError(f"missing required input: {path.relative_to(ROOT)}")
    with np.load(STATES_PATH) as saved:
        hidden = saved["hidden"].astype(np.float32)
        saved_winners = saved["dense_winners"].astype(np.int64)
        split_ids = {
            name: saved[f"{name}_ids"].astype(np.int64) for name in SPLITS
        }
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float32,
    )
    with np.load(GRAPH_PATH) as graph:
        indptr = graph["indptr"].astype(np.int64)
        indices = graph["indices"].astype(np.int32)
        internal_to_label = graph["internal_to_label"].astype(np.int64)
    if hidden.shape != (STATE_COUNT, WIDTH):
        raise RuntimeError(f"unexpected hidden-state shape: {hidden.shape}")
    if weights.shape != (VOCABULARY, WIDTH):
        raise RuntimeError(f"unexpected GPT-2 weight shape: {weights.shape}")
    if indptr.shape != (VOCABULARY + 1,) or int(indptr[-1]) != len(indices):
        raise RuntimeError("invalid exported HNSW CSR shape")
    if np.any(indptr[1:] < indptr[:-1]) or np.any(indices >= VOCABULARY):
        raise RuntimeError("invalid exported HNSW CSR contents")
    if not np.array_equal(np.sort(internal_to_label), np.arange(VOCABULARY)):
        raise RuntimeError("internal_to_label is not a vocabulary permutation")
    expected_sizes = {"train": 512, "validation": 256, "test": 256}
    if {name: len(ids) for name, ids in split_ids.items()} != expected_sizes:
        raise RuntimeError("unexpected train/validation/test split sizes")
    combined = np.concatenate([split_ids[name] for name in SPLITS])
    if not np.array_equal(np.sort(combined), np.arange(STATE_COUNT)):
        raise RuntimeError("splits do not form a disjoint state partition")
    return (
        hidden,
        weights,
        split_ids,
        saved_winners,
        indptr,
        indices,
        internal_to_label,
    )


def brute_force_scores(
    hidden: np.ndarray, weights: np.ndarray, saved_winners: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    scores = np.empty((len(hidden), len(weights)), dtype=np.float32)
    winners = np.empty(len(hidden), dtype=np.int64)
    margins = np.empty(len(hidden), dtype=np.float32)
    for start in range(0, len(hidden), ORACLE_BATCH):
        stop = min(start + ORACLE_BATCH, len(hidden))
        scores[start:stop] = hidden[start:stop] @ weights.T
        winners[start:stop] = np.argmax(scores[start:stop], axis=1)
        top_two = np.partition(scores[start:stop], -2, axis=1)[:, -2:]
        margins[start:stop] = np.max(top_two, axis=1) - np.min(
            top_two, axis=1
        )
    if not np.array_equal(winners, saved_winners):
        bad = np.flatnonzero(winners != saved_winners)
        raise RuntimeError(
            f"brute-force oracle mismatch at {len(bad)} states; "
            f"first mismatch {int(bad[0])}"
        )
    return scores, winners, {
        "method": "batched float32 hidden @ unchanged float32 wte.weight.T",
        "batchSize": ORACLE_BATCH,
        "savedWinnerMatches": int(np.sum(winners == saved_winners)),
        "savedWinnerRecall": float(np.mean(winners == saved_winners)),
        "winnerSha256": sha256_array(winners),
        "minimumTop1Margin": float(np.min(margins)),
    }


def build_seed_banks(
    weights: np.ndarray,
    indptr: np.ndarray,
    internal_to_label: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    label_to_internal = np.empty(VOCABULARY, dtype=np.int32)
    label_to_internal[internal_to_label] = np.arange(VOCABULARY, dtype=np.int32)
    with np.load(IVF_PATH) as ivf:
        centers = ivf["centers"].astype(np.float32)
        cluster_labels = ivf["labels"].astype(np.int32)
    if centers.shape != (SEED_COUNT, WIDTH):
        raise RuntimeError("the fixed entry bank requires the existing 256-way IVF")

    medoid_labels = np.empty(SEED_COUNT, dtype=np.int64)
    for cluster in range(SEED_COUNT):
        members = np.flatnonzero(cluster_labels == cluster)
        if not len(members):
            raise RuntimeError(f"empty IVF cluster {cluster}")
        difference = weights[members] - centers[cluster]
        distance = np.sum(difference * difference, axis=1)
        medoid_labels[cluster] = int(members[np.argmin(distance)])

    degrees = np.diff(indptr)
    hub_order = np.lexsort((internal_to_label, -degrees))
    hub_internal = hub_order[:SEED_COUNT].astype(np.int32)
    banks = {
        "ivf-medoid-256": label_to_internal[medoid_labels],
        "layer0-degree-hub-256": hub_internal,
    }
    metadata = {}
    for name, nodes in banks.items():
        if len(nodes) != SEED_COUNT or len(np.unique(nodes)) != SEED_COUNT:
            raise RuntimeError(f"invalid seed bank {name}")
        labels = internal_to_label[nodes]
        metadata[name] = {
            "rows": SEED_COUNT,
            "internalIdsSha256": sha256_array(nodes),
            "tokenIdsSha256": sha256_array(labels),
            "minimumTokenId": int(np.min(labels)),
            "maximumTokenId": int(np.max(labels)),
            "selectionUsesCorpusStates": False,
            "description": (
                "one unchanged vocabulary row nearest each existing IVF centroid"
                if name == "ivf-medoid-256"
                else "256 highest-degree real HNSW layer-0 nodes"
            ),
        }
    return banks, metadata


def better_candidate(
    score: float,
    label: int,
    best_score: float,
    best_label: int,
) -> bool:
    return score > best_score or (score == best_score and label < best_label)


def trace_paths(
    scores: np.ndarray,
    indptr: np.ndarray,
    indices: np.ndarray,
    internal_to_label: np.ndarray,
    seed_banks: dict[str, np.ndarray],
) -> tuple[list[dict[str, object]], dict[str, np.ndarray]]:
    descriptors = [
        {
            "configId": f"{strategy}-b{beam}-r{rounds}",
            "entryStrategy": strategy,
            "beam": beam,
            "rounds": rounds,
            "fixedPaddedRowSlots": SEED_COUNT
            + rounds * beam * MAX_LAYER0_DEGREE,
        }
        for strategy in seed_banks
        for beam in BEAMS
        for rounds in ROUND_CHECKPOINTS
    ]
    config_index = {row["configId"]: i for i, row in enumerate(descriptors)}
    shape = (len(descriptors), STATE_COUNT)
    arrays = {
        "predictions": np.empty(shape, dtype=np.int64),
        "unique_scored_rows": np.empty(shape, dtype=np.int64),
        "adjacency_entries": np.empty(shape, dtype=np.int64),
        "duplicate_adjacency_entries": np.empty(shape, dtype=np.int64),
        "fixed_padding_slots": np.empty(shape, dtype=np.int64),
        "frontier_expansions": np.empty(shape, dtype=np.int64),
    }
    visited_stamp = np.zeros(VOCABULARY, dtype=np.int32)
    expanded_stamp = np.zeros(VOCABULARY, dtype=np.int32)
    stamp = 0
    max_rounds = max(ROUND_CHECKPOINTS)

    for strategy, seeds in seed_banks.items():
        seed_labels = internal_to_label[seeds]
        print(f"tracing entry strategy {strategy}", flush=True)
        for beam in BEAMS:
            started = time.perf_counter()
            for query in range(STATE_COUNT):
                stamp += 1
                visited_stamp[seeds] = stamp
                seed_scores = scores[query, seed_labels]
                seed_order = np.lexsort((seed_labels, -seed_scores))
                best_node = int(seeds[seed_order[0]])
                best_label = int(internal_to_label[best_node])
                best_score = float(scores[query, best_label])
                heap = [
                    (-float(value), int(label), int(node))
                    for value, label, node in zip(seed_scores, seed_labels, seeds)
                ]
                heapq.heapify(heap)
                unique_count = SEED_COUNT
                adjacency_count = 0
                new_unique_count = 0
                expansion_count = 0

                for round_number in range(1, max_rounds + 1):
                    frontier = []
                    while heap and len(frontier) < beam:
                        _negative_score, _label, node = heapq.heappop(heap)
                        if expanded_stamp[node] == stamp:
                            continue
                        expanded_stamp[node] = stamp
                        frontier.append(node)
                    expansion_count += len(frontier)
                    if frontier:
                        parts = [
                            indices[indptr[node] : indptr[node + 1]]
                            for node in frontier
                        ]
                        neighbors = np.concatenate(parts)
                        adjacency_count += len(neighbors)
                        unseen = neighbors[visited_stamp[neighbors] != stamp]
                        if len(unseen):
                            new_nodes = np.unique(unseen)
                            visited_stamp[new_nodes] = stamp
                            new_unique_count += len(new_nodes)
                            unique_count += len(new_nodes)
                            new_labels = internal_to_label[new_nodes]
                            new_scores = scores[query, new_labels]
                            for value, label, node in zip(
                                new_scores, new_labels, new_nodes
                            ):
                                heapq.heappush(
                                    heap,
                                    (-float(value), int(label), int(node)),
                                )
                            local_order = np.lexsort((new_labels, -new_scores))
                            candidate = int(local_order[0])
                            candidate_score = float(new_scores[candidate])
                            candidate_label = int(new_labels[candidate])
                            if better_candidate(
                                candidate_score,
                                candidate_label,
                                best_score,
                                best_label,
                            ):
                                best_node = int(new_nodes[candidate])
                                best_label = candidate_label
                                best_score = candidate_score

                    if round_number in ROUND_CHECKPOINTS:
                        config_id = (
                            f"{strategy}-b{beam}-r{round_number}"
                        )
                        row = config_index[config_id]
                        fixed_neighbor_slots = (
                            round_number * beam * MAX_LAYER0_DEGREE
                        )
                        arrays["predictions"][row, query] = best_label
                        arrays["unique_scored_rows"][row, query] = unique_count
                        arrays["adjacency_entries"][row, query] = adjacency_count
                        arrays["duplicate_adjacency_entries"][row, query] = (
                            adjacency_count - new_unique_count
                        )
                        arrays["fixed_padding_slots"][row, query] = (
                            fixed_neighbor_slots - adjacency_count
                        )
                        arrays["frontier_expansions"][row, query] = (
                            expansion_count
                        )
            print(
                f"  B={beam}: {time.perf_counter() - started:.3f}s",
                flush=True,
            )
    return descriptors, arrays


def summarize_split(
    ids: np.ndarray,
    predicted: np.ndarray,
    winners: np.ndarray,
    arrays: dict[str, np.ndarray],
    row: int,
    fixed_padded_slots: int,
) -> dict[str, object]:
    unique = arrays["unique_scored_rows"][row, ids]
    adjacency = arrays["adjacency_entries"][row, ids]
    duplicates = arrays["duplicate_adjacency_entries"][row, ids]
    padding = arrays["fixed_padding_slots"][row, ids]
    no_dedup = SEED_COUNT + adjacency
    padded = unique + duplicates + padding
    if not np.all(padded == fixed_padded_slots):
        raise RuntimeError("row accounting identity failed")
    return {
        "samples": int(len(ids)),
        "top1Matches": int(np.sum(predicted[ids] == winners[ids])),
        "top1Recall": float(np.mean(predicted[ids] == winners[ids])),
        "uniqueScoredRowsOptimistic": stats(unique),
        "adjacencyEntries": stats(adjacency),
        "duplicateAdjacencyEntriesWithoutDedup": stats(duplicates),
        "rowScoresWithoutDedupBeforePadding": stats(no_dedup),
        "fixedRoundPaddingSlots": stats(padding),
        "fixedPaddedRowScoreSlots": fixed_padded_slots,
        "frontierExpansions": stats(
            arrays["frontier_expansions"][row, ids]
        ),
    }


def summarize_configurations(
    descriptors: list[dict[str, object]],
    arrays: dict[str, np.ndarray],
    winners: np.ndarray,
    split_ids: dict[str, np.ndarray],
) -> list[dict[str, object]]:
    all_ids = np.arange(STATE_COUNT, dtype=np.int64)
    configurations = []
    for row, descriptor in enumerate(descriptors):
        predicted = arrays["predictions"][row]
        fixed = int(descriptor["fixedPaddedRowSlots"])
        configurations.append(
            {
                **descriptor,
                "sequentialRounds": descriptor["rounds"],
                "splits": {
                    "all": summarize_split(
                        all_ids, predicted, winners, arrays, row, fixed
                    ),
                    **{
                        name: summarize_split(
                            ids, predicted, winners, arrays, row, fixed
                        )
                        for name, ids in split_ids.items()
                    },
                },
            }
        )
    return configurations


def validation_rank(row: dict[str, object]) -> tuple[object, ...]:
    validation = row["splits"]["validation"]
    return (
        validation["top1Recall"],
        -validation["uniqueScoredRowsOptimistic"]["mean"],
        -row["fixedPaddedRowSlots"],
        -row["rounds"],
        -row["beam"],
        row["entryStrategy"],
    )


def select(
    configurations: list[dict[str, object]], predicate: object
) -> dict[str, object]:
    eligible = [row for row in configurations if predicate(row)]
    if not eligible:
        raise RuntimeError("no eligible configuration for selection")
    return max(eligible, key=validation_rank)


def compact_selected(row: dict[str, object]) -> dict[str, object]:
    return {
        "configId": row["configId"],
        "entryStrategy": row["entryStrategy"],
        "beam": row["beam"],
        "rounds": row["rounds"],
        "fixedPaddedRowSlots": row["fixedPaddedRowSlots"],
        "train": row["splits"]["train"],
        "validation": row["splits"]["validation"],
        "untouchedTest": row["splits"]["test"],
    }


def pareto_frontier(
    configurations: list[dict[str, object]],
) -> list[dict[str, object]]:
    ordered = sorted(
        configurations,
        key=lambda row: (
            row["splits"]["validation"]["uniqueScoredRowsOptimistic"]["mean"],
            -row["splits"]["validation"]["top1Recall"],
            row["fixedPaddedRowSlots"],
        ),
    )
    result = []
    best_recall = -1.0
    for row in ordered:
        recall = row["splits"]["validation"]["top1Recall"]
        if recall > best_recall:
            result.append(compact_selected(row))
            best_recall = recall
    return result


def selection_sentence(name: str, point: dict[str, object]) -> str:
    validation = point["validation"]
    test = point["untouchedTest"]
    unique = test["uniqueScoredRowsOptimistic"]
    duplicates = test["duplicateAdjacencyEntriesWithoutDedup"]
    padding = test["fixedRoundPaddingSlots"]
    return (
        f"**{name}:** `{point['configId']}` reaches "
        f"{validation['top1Recall']:.2%} validation and "
        f"{test['top1Recall']:.2%} untouched-test recall. Test optimistic unique "
        f"rows are {unique['mean']:.1f} mean / {unique['p95']} p95 / "
        f"{unique['max']} max; duplicate adjacency entries are "
        f"{duplicates['mean']:.1f} mean, padding is {padding['mean']:.1f} mean, "
        f"and the fixed padded schedule is {point['fixedPaddedRowSlots']} rows."
    )


def render_markdown(result: dict[str, object]) -> str:
    rows = []
    for configuration in result["configurations"]:
        train = configuration["splits"]["train"]
        validation = configuration["splits"]["validation"]
        test = configuration["splits"]["test"]
        unique = test["uniqueScoredRowsOptimistic"]
        duplicates = test["duplicateAdjacencyEntriesWithoutDedup"]
        rows.append(
            f'| {configuration["entryStrategy"]} | {configuration["beam"]} | '
            f'{configuration["rounds"]} | {train["top1Recall"]:.2%} | '
            f'{validation["top1Recall"]:.2%} | {test["top1Recall"]:.2%} | '
            f'{unique["mean"]:.1f} / {unique["p95"]} / {unique["max"]} | '
            f'{duplicates["mean"]:.1f} | '
            f'{configuration["fixedPaddedRowSlots"]} |'
        )
    selection = result["selection"]
    verdict = result["target"]
    status = "GO" if verdict["mean2000Go"] else "NO-GO"
    return f"""# CSS-unrollable batched frontier on real HNSW layer 0

**Mean-2,000 target: {status}.** {verdict["summary"]}

This experiment uses the previously exported real hnswlib 0.8.0 layer-0 graph,
all 50,257 unchanged GPT-2-small tied output rows, and the established 1,024
hidden states. Fresh float32 brute force reproduces all 1,024 saved winners.
No model weight, architecture, state, split, or graph edge is changed.

Every query first scores a fixed 256-row seed bank. Each of the fixed rounds
then expands the highest-scoring B discovered but unexpanded nodes in parallel,
scores previously unseen layer-0 neighbors by raw inner product, and retains
all discovered candidates for later top-B selection. The optimistic algorithm
deduplicates globally. A literal CSS schedule cannot cheaply do that, so the
tables separately report duplicate adjacency references and padding to B x 64
neighbor slots per round.

## Validation-only selections

{selection_sentence("Optimistic validation mean <=2,000", selection["selectedUnderMean2000"])}

{selection_sentence("Literal fixed padded <=2,048", selection["selectedUnderFixed2048"])}

{selection_sentence("Best broader frontier", selection["bestBroaderFrontier"])}

{selection_sentence("Cheapest point at best validation recall", selection["cheapestAtBestValidationRecall"])}

Selection uses validation recall only. Test is revealed only after locking each
point. Budgeted and cheapest-point ties prefer lower validation optimistic mean
rows, then fewer fixed padded slots, rounds, and beam width. The broader point
is the predetermined widest B=32, 16-round schedule, with entry strategy chosen
by validation.

## Full sweep

Test row values are mean / p95 / max for optimistic unique rows. Duplicate
entries are the mean layer-0 references that a no-dedup CSS schedule would
rescore. Fixed padded rows include the 256 seeds and every B x 64 round slot.

| Entry strategy | B | Rounds | Train recall | Validation recall | Test recall | Test unique rows | Test duplicate entries | Fixed padded rows |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- | ---: | ---: |
{chr(10).join(rows)}

## Interpretation

The optimistic unique-row count is an algorithmic lower-work view with a visited
set. The fixed padded count is the clean CSS-unrollable bound: exactly 256 +
rounds x B x 64 row-score slots and `rounds` sequential graph stages. Actual
degrees below 64 become padding; already visited or same-round repeated neighbor
IDs become duplicate scores without a dynamic deduplicator. `results.json`
contains mean/p50/p95/max distributions for every accounting category and split.

Two query-independent 256-row entries are screened: one actual vocabulary row
nearest each existing IVF centroid, and the 256 highest-degree layer-0 nodes.
Neither uses train, validation, or test states. The export did not contain the
HNSW upper levels or entry point, so this does not claim to reproduce the native
hierarchical descent.

## Validation and artifacts

- `trace.npz` stores per-state predictions and all accounting counters.
- `seed_banks.npz` stores internal IDs and token IDs for both fixed banks.
- Every accounting row satisfies `unique + duplicates + padding = fixed padded`.
- CSR bounds, token permutation, split isolation, seed uniqueness, and all 1,024
  brute-force winners are validated in `validation.json`.

## Reproduce

```sh
python3 tools/analyze_gpt2_hnsw_batched_frontier.py
python3 -m py_compile tools/analyze_gpt2_hnsw_batched_frontier.py
python3 -m json.tool experiments/gpt2-hnsw-batched-frontier/results.json >/dev/null
python3 -m json.tool experiments/gpt2-hnsw-batched-frontier/validation.json >/dev/null
```
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (
        hidden,
        weights,
        split_ids,
        saved_winners,
        indptr,
        indices,
        internal_to_label,
    ) = load_inputs()
    print("computing full-vocabulary brute-force oracle", flush=True)
    scores, winners, oracle = brute_force_scores(hidden, weights, saved_winners)
    seed_banks, seed_metadata = build_seed_banks(
        weights, indptr, internal_to_label
    )
    seed_path = OUTPUT / "seed_banks.npz"
    np.savez_compressed(
        seed_path,
        **{
            f"{name.replace('-', '_')}_internal_ids": nodes
            for name, nodes in seed_banks.items()
        },
        **{
            f"{name.replace('-', '_')}_token_ids": internal_to_label[nodes]
            for name, nodes in seed_banks.items()
        },
    )

    descriptors, arrays = trace_paths(
        scores, indptr, indices, internal_to_label, seed_banks
    )
    configurations = summarize_configurations(
        descriptors, arrays, winners, split_ids
    )
    selected_mean = select(
        configurations,
        lambda row: row["splits"]["validation"]
        ["uniqueScoredRowsOptimistic"]["mean"]
        <= 2_000,
    )
    selected_fixed = select(
        configurations,
        lambda row: row["fixedPaddedRowSlots"] <= 2_048,
    )
    cheapest_best_validation = max(configurations, key=validation_rank)
    selected_broad = select(
        configurations,
        lambda row: row["beam"] == max(BEAMS)
        and row["rounds"] == max(ROUND_CHECKPOINTS),
    )
    compact_mean = compact_selected(selected_mean)
    compact_fixed = compact_selected(selected_fixed)
    compact_broad = compact_selected(selected_broad)
    mean_go = bool(
        compact_mean["untouchedTest"]["top1Recall"] >= 0.99
        and compact_mean["validation"]["uniqueScoredRowsOptimistic"]["mean"]
        <= 2_000
    )
    fixed_go = bool(
        compact_fixed["untouchedTest"]["top1Recall"] >= 0.99
        and compact_fixed["fixedPaddedRowSlots"] <= 2_048
    )

    trace_path = OUTPUT / "trace.npz"
    np.savez_compressed(
        trace_path,
        config_ids=np.asarray(
            [row["configId"] for row in descriptors], dtype="U64"
        ),
        brute_force_winners=winners,
        **arrays,
    )
    result = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "model": {
            "name": "openai-community/gpt2",
            "weightsChanged": False,
            "architectureChanged": False,
            "vocabularyRows": VOCABULARY,
            "width": WIDTH,
            "weightsSha256": sha256_array(weights),
        },
        "corpus": {
            "path": str(STATES_PATH.relative_to(ROOT)),
            "states": STATE_COUNT,
            "hiddenSha256": sha256_array(hidden),
            "splits": {name: int(len(ids)) for name, ids in split_ids.items()},
        },
        "oracle": oracle,
        "graph": {
            "path": str(GRAPH_PATH.relative_to(ROOT)),
            "fileSha256": sha256_file(GRAPH_PATH),
            "nodes": VOCABULARY,
            "directedEdges": int(len(indices)),
            "maximumDegree": int(np.max(np.diff(indptr))),
            "indptrSha256": sha256_array(indptr),
            "indicesSha256": sha256_array(indices),
            "internalToLabelSha256": sha256_array(internal_to_label),
            "upperLevelsAvailable": False,
            "nativeEntryPointAvailable": False,
        },
        "algorithm": {
            "objective": "raw inner product against unchanged GPT-2 rows",
            "seedRows": SEED_COUNT,
            "beams": list(BEAMS),
            "rounds": list(ROUND_CHECKPOINTS),
            "fixedNeighborSlotsPerFrontierNode": MAX_LAYER0_DEGREE,
            "visitedDeduplication": "optimistic unique-row accounting",
            "frontierRule": "top B discovered, not-yet-expanded candidates",
            "winnerRule": "best actual raw-inner-product discovered row; token ID breaks exact ties",
            "sequentialStages": "one seed-bank scoring stage plus the reported graph rounds",
        },
        "entryStrategies": seed_metadata,
        "selection": {
            "rule": "highest validation recall; ties use lower validation unique mean, fixed rows, rounds, then beam; test excluded",
            "selectedUnderMean2000": compact_mean,
            "selectedUnderFixed2048": compact_fixed,
            "bestBroaderFrontier": compact_broad,
            "cheapestAtBestValidationRecall": compact_selected(
                cheapest_best_validation
            ),
        },
        "target": {
            "criterion": "untouched-test recall >=99% after validation selection",
            "meanBudget": "validation optimistic unique-row mean <=2000",
            "fixedBudget": "literal no-dedup fixed padded slots <=2048",
            "mean2000Go": mean_go,
            "fixed2048Go": fixed_go,
            "broaderFrontierReaches99": bool(
                compact_broad["untouchedTest"]["top1Recall"] >= 0.99
            ),
            "summary": (
                "A validation-selected optimistic point reaches at least 99% untouched-test recall under 2,000 mean unique rows."
                if mean_go
                else "No validation-selected point reaches 99% untouched-test recall under 2,000 mean optimistic unique rows; the widest validation-selected frontier does so only beyond that budget."
            ),
        },
        "validationParetoFrontier": pareto_frontier(configurations),
        "configurations": configurations,
        "artifacts": {
            "trace": str(trace_path.relative_to(ROOT)),
            "traceSha256": sha256_file(trace_path),
            "seedBanks": str(seed_path.relative_to(ROOT)),
            "seedBanksSha256": sha256_file(seed_path),
        },
    }
    accounting_ok = True
    for row, descriptor in enumerate(descriptors):
        fixed = int(descriptor["fixedPaddedRowSlots"])
        total = (
            arrays["unique_scored_rows"][row]
            + arrays["duplicate_adjacency_entries"][row]
            + arrays["fixed_padding_slots"][row]
        )
        accounting_ok &= bool(np.all(total == fixed))
    validation = {
        "passed": bool(accounting_ok),
        "bruteForceSavedWinnerMatches": oracle["savedWinnerMatches"],
        "bruteForceSavedWinnerRecall": oracle["savedWinnerRecall"],
        "graphCsrValidated": True,
        "internalToLabelPermutationValidated": True,
        "splitPartitionValidated": True,
        "seedBanksValidated": True,
        "seedBanksUseCorpusStates": False,
        "configurationCount": len(configurations),
        "accountingIdentityValidatedForAllStates": accounting_ok,
        "selectionUsesValidationOnly": True,
        "testExcludedFromSelection": True,
        "modelWeightsChanged": False,
        "modelArchitectureChanged": False,
    }
    if not validation["passed"]:
        raise RuntimeError("validation failed")
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUTPUT / "validation.json").write_text(
        json.dumps(validation, indent=2) + "\n"
    )
    (OUTPUT / "RESULTS.md").write_text(render_markdown(result))
    print(
        json.dumps(
            {
                "target": result["target"],
                "selection": result["selection"],
                "validation": validation,
                "results": str((OUTPUT / "results.json").relative_to(ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
