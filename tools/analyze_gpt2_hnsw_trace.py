#!/usr/bin/env python3
"""Measure real hnswlib traversal counters on unchanged GPT-2 states."""

from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-hnsw-trace"
BUILD_SCRIPT = ROOT / "tools" / "build_instrumented_hnswlib.sh"
LIB_DIR = OUTPUT / "build" / "lib"
STATES_PATH = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
VOCABULARY = 50_257
WIDTH = 768
STATE_COUNT = 1_024
SPLITS = ("train", "validation", "test")
EF_SEARCH_VALUES = (128, 256, 512, 1024)
M = 32
EF_CONSTRUCTION = 200
BUILD_THREADS = 8
QUERY_THREADS = 1
RANDOM_SEED = 20_260_914
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


def load_instrumented_hnswlib() -> object:
    suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    candidates = sorted(
        path for path in LIB_DIR.glob("hnswlib*") if path.name.endswith(suffixes)
    )
    if not candidates:
        print("building local instrumented hnswlib 0.8.0", flush=True)
        subprocess.run([str(BUILD_SCRIPT)], cwd=ROOT, check=True)
    sys.path.insert(0, str(LIB_DIR))
    module = importlib.import_module("hnswlib")
    required = ("reset_metrics", "get_metrics", "get_layer0_adjacency")
    probe = module.Index(space="ip", dim=1)
    if not all(hasattr(probe, name) for name in required):
        raise RuntimeError("imported hnswlib is not the local instrumented build")
    module_path = Path(module.__file__).resolve()
    if module_path.parent != LIB_DIR.resolve():
        raise RuntimeError(f"hnswlib imported from unexpected path: {module_path}")
    return module


def load_inputs() -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], np.ndarray]:
    if not STATES_PATH.exists():
        raise RuntimeError("missing existing 1,024-state corpus")
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
    if hidden.shape != (STATE_COUNT, WIDTH):
        raise RuntimeError(f"unexpected hidden-state shape: {hidden.shape}")
    if weights.shape != (VOCABULARY, WIDTH):
        raise RuntimeError(f"unexpected GPT-2 weight shape: {weights.shape}")
    expected_sizes = {"train": 512, "validation": 256, "test": 256}
    if {name: len(ids) for name, ids in split_ids.items()} != expected_sizes:
        raise RuntimeError("unexpected train/validation/test split sizes")
    combined = np.concatenate([split_ids[name] for name in SPLITS])
    if not np.array_equal(np.sort(combined), np.arange(STATE_COUNT)):
        raise RuntimeError("state splits do not form a disjoint 1,024-state partition")
    return hidden, weights, split_ids, saved_winners


def brute_force_oracle(
    hidden: np.ndarray, weights: np.ndarray, saved_winners: np.ndarray
) -> tuple[np.ndarray, dict[str, object]]:
    winners = np.empty(len(hidden), dtype=np.int64)
    margins = np.empty(len(hidden), dtype=np.float32)
    for start in range(0, len(hidden), ORACLE_BATCH):
        stop = min(start + ORACLE_BATCH, len(hidden))
        scores = hidden[start:stop] @ weights.T
        winners[start:stop] = np.argmax(scores, axis=1)
        top_two = np.partition(scores, -2, axis=1)[:, -2:]
        margins[start:stop] = np.max(top_two, axis=1) - np.min(top_two, axis=1)
    if not np.array_equal(winners, saved_winners):
        bad = np.flatnonzero(winners != saved_winners)
        raise RuntimeError(
            f"brute-force winners disagree with saved corpus at {len(bad)} states; "
            f"first mismatch is state {int(bad[0])}"
        )
    return winners, {
        "method": "batched float32 hidden @ unchanged float32 wte.weight.T",
        "batchSize": ORACLE_BATCH,
        "savedWinnerMatches": int(np.sum(winners == saved_winners)),
        "savedWinnerRecall": float(np.mean(winners == saved_winners)),
        "winnerSha256": sha256_array(winners),
        "minimumTop1Margin": float(np.min(margins)),
    }


def summarize_split(
    ids: np.ndarray,
    predicted: np.ndarray,
    winners: np.ndarray,
    distance_computations: np.ndarray,
    hops: np.ndarray,
) -> dict[str, object]:
    row_score_upper_bound = distance_computations[ids] + 1
    return {
        "samples": int(len(ids)),
        "top1Matches": int(np.sum(predicted[ids] == winners[ids])),
        "top1Recall": float(np.mean(predicted[ids] == winners[ids])),
        "distanceComputations": stats(distance_computations[ids]),
        "hops": stats(hops[ids]),
        "css768dRowScoreUpperBound": stats(row_score_upper_bound),
        "cssScalarMultiplyAccumulatesUpperBound": stats(
            row_score_upper_bound * WIDTH
        ),
    }


def validate_counter_isolation(index: object, query: np.ndarray) -> dict[str, object]:
    index.set_ef(EF_SEARCH_VALUES[0])
    observations = []
    for _ in range(2):
        index.reset_metrics()
        before = dict(index.get_metrics())
        labels, distances = index.knn_query(query[None, :], k=1, num_threads=1)
        after = dict(index.get_metrics())
        observations.append(
            (int(labels[0, 0]), float(distances[0, 0]), before, after)
        )
    index.reset_metrics()
    zero_after_reset = dict(index.get_metrics())
    first, second = observations
    passed = bool(
        first == second
        and first[2] == {"distance_computations": 0, "hops": 0}
        and first[3]["distance_computations"] > 0
        and first[3]["hops"] > 0
        and zero_after_reset == {"distance_computations": 0, "hops": 0}
    )
    if not passed:
        raise RuntimeError("instrumented counter reset/isolation validation failed")
    return {
        "passed": True,
        "queryRowsPerMeasurement": 1,
        "repeatedResultIdentical": True,
        "countersZeroBeforeAndAfterReset": True,
        "firstQueryCounters": first[3],
    }


def evaluate(
    index: object,
    hidden: np.ndarray,
    winners: np.ndarray,
    split_ids: dict[str, np.ndarray],
) -> tuple[list[dict[str, object]], np.ndarray, np.ndarray, np.ndarray]:
    predictions = np.empty((len(EF_SEARCH_VALUES), len(hidden)), dtype=np.int64)
    distance_counts = np.empty_like(predictions)
    hop_counts = np.empty_like(predictions)
    configurations = []
    all_ids = np.arange(len(hidden), dtype=np.int64)
    for ef_index, ef_search in enumerate(EF_SEARCH_VALUES):
        print(f"tracing efSearch={ef_search} one state at a time", flush=True)
        index.set_ef(ef_search)
        started = time.perf_counter()
        for query in range(len(hidden)):
            index.reset_metrics()
            labels, _distances = index.knn_query(
                hidden[query : query + 1], k=1, num_threads=QUERY_THREADS
            )
            counters = index.get_metrics()
            predictions[ef_index, query] = int(labels[0, 0])
            distance_counts[ef_index, query] = int(
                counters["distance_computations"]
            )
            hop_counts[ef_index, query] = int(counters["hops"])
        elapsed = time.perf_counter() - started
        configurations.append(
            {
                "efSearch": ef_search,
                "queryMode": "one state per knn_query after reset_metrics",
                "queryThreads": QUERY_THREADS,
                "querySecondsFor1024": float(elapsed),
                "splits": {
                    "all": summarize_split(
                        all_ids,
                        predictions[ef_index],
                        winners,
                        distance_counts[ef_index],
                        hop_counts[ef_index],
                    ),
                    **{
                        name: summarize_split(
                            ids,
                            predictions[ef_index],
                            winners,
                            distance_counts[ef_index],
                            hop_counts[ef_index],
                        )
                        for name, ids in split_ids.items()
                    },
                },
            }
        )
    return configurations, predictions, distance_counts, hop_counts


def save_adjacency(index: object) -> dict[str, object]:
    print("exporting real HNSW layer-0 adjacency", flush=True)
    indptr, indices, internal_to_label = index.get_layer0_adjacency()
    indptr = np.asarray(indptr, dtype=np.uint64)
    indices = np.asarray(indices, dtype=np.uint32)
    internal_to_label = np.asarray(internal_to_label, dtype=np.uint64)
    if indptr.shape != (VOCABULARY + 1,) or internal_to_label.shape != (VOCABULARY,):
        raise RuntimeError("unexpected exported layer-0 adjacency shape")
    if int(indptr[0]) != 0 or int(indptr[-1]) != len(indices):
        raise RuntimeError("invalid layer-0 CSR offsets")
    if np.any(indptr[1:] < indptr[:-1]) or np.any(indices >= VOCABULARY):
        raise RuntimeError("invalid layer-0 CSR indices")
    if not np.array_equal(np.sort(internal_to_label), np.arange(VOCABULARY)):
        raise RuntimeError("internal-to-label map is not a vocabulary permutation")
    degrees = np.diff(indptr).astype(np.int64)
    path = OUTPUT / "layer0_adjacency.npz"
    np.savez_compressed(
        path,
        indptr=indptr,
        indices=indices,
        internal_to_label=internal_to_label,
    )
    return {
        "path": str(path.relative_to(ROOT)),
        "format": "NumPy NPZ containing CSR indptr/indices in internal-ID space and internal_to_label token IDs",
        "nodes": VOCABULARY,
        "directedEdges": int(len(indices)),
        "degree": stats(degrees),
        "maximumConfiguredLayer0Degree": 2 * M,
        "indptrSha256": sha256_array(indptr),
        "indicesSha256": sha256_array(indices),
        "internalToLabelSha256": sha256_array(internal_to_label),
        "fileSha256": sha256_file(path),
    }


def compact_selected(configuration: dict[str, object]) -> dict[str, object]:
    return {
        "efSearch": configuration["efSearch"],
        "validation": configuration["splits"]["validation"],
        "untouchedTest": configuration["splits"]["test"],
    }


def render_markdown(result: dict[str, object]) -> str:
    table_rows = []
    for configuration in result["configurations"]:
        for split in SPLITS:
            values = configuration["splits"][split]
            distances = values["distanceComputations"]
            hops = values["hops"]
            table_rows.append(
                f'| {configuration["efSearch"]} | {split} | '
                f'{values["top1Matches"]}/{values["samples"]} '
                f'({values["top1Recall"]:.2%}) | '
                f'{distances["mean"]:.1f} / {distances["p50"]} / '
                f'{distances["p95"]} / {distances["max"]} | '
                f'{hops["mean"]:.1f} / {hops["p50"]} / '
                f'{hops["p95"]} / {hops["max"]} |'
            )
    selected = result["selection"]["validationSelected"]
    test = selected["untouchedTest"]
    row_scores = test["css768dRowScoreUpperBound"]
    scalar_macs = test["cssScalarMultiplyAccumulatesUpperBound"]
    hops = test["hops"]
    adjacency = result["graph"]["layer0Adjacency"]
    return f"""# Real hnswlib GPT-2 traversal trace

Real hnswlib 0.8.0 was rebuilt locally over all 50,257 unchanged GPT-2-small
tied output rows with `space=\"ip\"`, M=32, efConstruction=200, and 8 insertion
threads. GPT-2 weights, architecture, vocabulary, and the existing 1,024-state
corpus are unchanged. Batched brute force independently reproduced all
{result["oracle"]["savedWinnerMatches"]:,}/1,024 saved dense winners.

## Counter results

Counters were reset immediately before every one-state query and read
immediately afterward; query execution was single-threaded. Values are
mean / p50 / p95 / max, with integer percentiles using the conservative
`higher` method.

| efSearch | Split | Exact top-1 recall | Distance-computation counter | Sequential expansions / hops |
| ---: | :--- | :--- | :--- | :--- |
{chr(10).join(table_rows)}

## Validation-selected untouched test

The locked rule is highest validation recall, then lowest efSearch. It selected
**efSearch={selected["efSearch"]}** without consulting test. Its untouched-test
recall is **{test["top1Recall"]:.2%}** ({test["top1Matches"]}/{test["samples"]}).

For CSS feasibility, efSearch is only a dynamic queue-width parameter. The
instrumented traversal at this selected test point performs **{hops["mean"]:.1f}
mean / {hops["p50"]} p50 / {hops["p95"]} p95 / {hops["max"]} max sequential
candidate expansions**. The conservative count of 768-dimensional vocabulary
row scores, including the initial entry-point score omitted by hnswlib's
counter, is **{row_scores["mean"]:.1f} mean / {row_scores["p50"]} p50 /
{row_scores["p95"]} p95 / {row_scores["max"]} max**. This is a CSS upper bound:
the upstream counter adds the full adjacency-list length at every expansion,
including already-visited neighbors whose distance function is skipped.
At the mean, those row scores contain **{scalar_macs["mean"] / 1_000_000:.2f}
million scalar multiply-accumulates** before winner selection.

## What was instrumented

The generated hnswlib copy exposes `reset_metrics()` and `get_metrics()` for
the existing `HierarchicalNSW::metric_distance_computations` and `metric_hops`
atomics. In stock 0.8.0, `searchKnn` does not enable the existing base-layer
`collect_metrics` template flag; the local patch enables it for both base
search paths. This changes only atomic bookkeeping, not graph construction,
candidate ordering, stopping, distances, or returned labels.

`metric_hops` counts expanded adjacency lists across greedy upper layers and
the ef-controlled layer-0 search. `metric_distance_computations` is the sum of
their list lengths. It counts all upper-layer neighbor scores but conservatively
overcounts layer-0 distance calls when a neighbor was already visited, and it
omits the one initial entry-point score. Accordingly, `counter + 1` is reported
as the conservative number of 768-d row scores for a static CSS realization.

## Real graph export

The built layer-0 graph is saved as `{adjacency["path"]}` with
{adjacency["nodes"]:,} nodes and {adjacency["directedEdges"]:,} directed edges.
It contains CSR `indptr` and `indices` in hnswlib internal-ID space plus
`internal_to_label`, which maps each internal node to its GPT-2 token ID. This
is the clean input for a later CSS-native batched-frontier traversal; no such
sweep is performed here.

## Validation

- The local extension identifies as hnswlib 0.8.0-instrumented and imports from
  the experiment build directory, not uv's cache.
- Reset/read isolation was repeated on one query and produced identical labels,
  distances, and counters with zeros before each query.
- All 1,024 saved winners match fresh float32 brute force over every unchanged
  vocabulary row.
- The CSR export has valid monotone offsets, in-range internal IDs, and a full
  50,257-token label permutation.
- `validation.json` records these checks; `trace.npz` retains per-state counters
  and predictions for all four efSearch settings.

## Reproduce

```sh
tools/build_instrumented_hnswlib.sh
python3 tools/analyze_gpt2_hnsw_trace.py
python3 -m py_compile tools/analyze_gpt2_hnsw_trace.py
python3 -m json.tool experiments/gpt2-hnsw-trace/results.json >/dev/null
python3 -m json.tool experiments/gpt2-hnsw-trace/validation.json >/dev/null
```
"""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    hnswlib = load_instrumented_hnswlib()
    hidden, weights, split_ids, saved_winners = load_inputs()

    print("brute-force verifying all 1,024 winners", flush=True)
    winners, oracle = brute_force_oracle(hidden, weights, saved_winners)

    index = hnswlib.Index(space="ip", dim=WIDTH)
    index.init_index(
        max_elements=VOCABULARY,
        M=M,
        ef_construction=EF_CONSTRUCTION,
        random_seed=RANDOM_SEED,
        allow_replace_deleted=False,
    )
    index.set_num_threads(BUILD_THREADS)
    started = time.perf_counter()
    index.add_items(
        weights,
        np.arange(VOCABULARY, dtype=np.int64),
        num_threads=BUILD_THREADS,
    )
    build_seconds = time.perf_counter() - started
    if index.get_current_count() != VOCABULARY:
        raise RuntimeError("HNSW index did not contain the full vocabulary")
    print(f"built HNSW index in {build_seconds:.3f}s", flush=True)

    adjacency = save_adjacency(index)
    counter_validation = validate_counter_isolation(index, hidden[0])
    configurations, predictions, distance_counts, hop_counts = evaluate(
        index, hidden, winners, split_ids
    )
    selected = max(
        configurations,
        key=lambda row: (
            row["splits"]["validation"]["top1Recall"],
            -row["efSearch"],
        ),
    )

    extension_path = Path(hnswlib.__file__).resolve()
    trace_path = OUTPUT / "trace.npz"
    np.savez_compressed(
        trace_path,
        ef_search=np.asarray(EF_SEARCH_VALUES, dtype=np.int64),
        predictions=predictions,
        distance_computations=distance_counts,
        hops=hop_counts,
        brute_force_winners=winners,
    )
    result = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "model": {
            "name": "openai-community/gpt2",
            "architectureChanged": False,
            "weightsChanged": False,
            "vocabularyRows": VOCABULARY,
            "width": WIDTH,
            "weightSha256": sha256_array(weights),
        },
        "corpus": {
            "path": str(STATES_PATH.relative_to(ROOT)),
            "states": STATE_COUNT,
            "hiddenSha256": sha256_array(hidden),
            "splits": {name: int(len(ids)) for name, ids in split_ids.items()},
            "splitIdsSha256": {
                name: sha256_array(ids) for name, ids in split_ids.items()
            },
        },
        "oracle": oracle,
        "instrumentation": {
            "library": "hnswlib",
            "upstreamVersion": "0.8.0",
            "moduleVersion": hnswlib.__version__,
            "extensionPath": str(extension_path.relative_to(ROOT)),
            "extensionSha256": sha256_file(extension_path),
            "patchPath": str((OUTPUT / "instrumentation.patch").relative_to(ROOT)),
            "baseLayerMetricCollectionActivated": True,
            "searchBehaviorChanged": False,
            "counterQueryRows": 1,
            "counterQueryThreads": QUERY_THREADS,
            "percentileMethod": "higher",
        },
        "index": {
            "space": "ip",
            "distance": "1 - raw inner product",
            "M": M,
            "efConstruction": EF_CONSTRUCTION,
            "randomSeed": RANDOM_SEED,
            "buildThreads": BUILD_THREADS,
            "buildSeconds": float(build_seconds),
            "elements": int(index.get_current_count()),
            "parallelConstructionMayNotBeBitDeterministic": True,
        },
        "graph": {"layer0Adjacency": adjacency},
        "configurations": configurations,
        "selection": {
            "rule": "highest validation top-1 recall; ties choose lower efSearch; test is not used",
            "validationSelected": compact_selected(selected),
        },
        "cssFeasibility": {
            "efSearchIsNotABound": True,
            "sequentialCandidateExpansions": "metric_hops",
            "conservative768dRowScores": "metric_distance_computations + 1 initial entry-point score",
            "counterOvercountsVisitedLayer0Neighbors": True,
            "selectedUntouchedTest": {
                "efSearch": selected["efSearch"],
                "sequentialCandidateExpansions": selected["splits"]["test"]["hops"],
                "rowScores768dUpperBound": selected["splits"]["test"]["css768dRowScoreUpperBound"],
                "scalarMultiplyAccumulatesUpperBound": selected["splits"]["test"]["cssScalarMultiplyAccumulatesUpperBound"],
            },
        },
        "artifacts": {
            "trace": str(trace_path.relative_to(ROOT)),
            "traceSha256": sha256_file(trace_path),
        },
    }
    validation = {
        "passed": True,
        "extensionImportedFromExperimentBuild": extension_path.parent == LIB_DIR.resolve(),
        "moduleVersion": hnswlib.__version__,
        "counterIsolation": counter_validation,
        "bruteForceSavedWinnerMatches": oracle["savedWinnerMatches"],
        "bruteForceSavedWinnerRecall": oracle["savedWinnerRecall"],
        "layer0CsrValidated": True,
        "allCountersPositive": bool(np.all(distance_counts > 0) and np.all(hop_counts > 0)),
        "singleStateQueries": True,
        "testExcludedFromSelection": True,
    }
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUTPUT / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    (OUTPUT / "RESULTS.md").write_text(render_markdown(result))
    print(json.dumps({
        "selected": result["selection"]["validationSelected"],
        "results": str((OUTPUT / "results.json").relative_to(ROOT)),
        "validation": validation,
    }, indent=2))


if __name__ == "__main__":
    main()
