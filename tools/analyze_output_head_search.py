#!/usr/bin/env python3
"""Measure exact ball-cluster MIPS pruning on TinyStories hidden states."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def import_benchmark_builder() -> object:
    path = ROOT / "tools" / "build_output_head_benchmark.py"
    spec = importlib.util.spec_from_file_location("output_head_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = import_benchmark_builder()


def train_kmeans(
    vectors: np.ndarray, clusters: int, iterations: int, seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    centers = vectors[rng.choice(len(vectors), size=clusters, replace=False)].copy()
    squared_norms = (vectors * vectors).sum(axis=1)
    labels = np.zeros(len(vectors), dtype=np.int32)
    for iteration in range(iterations):
        center_norms = (centers * centers).sum(axis=1)
        sums = np.zeros_like(centers)
        counts = np.zeros(clusters, dtype=np.int64)
        inertia = 0.0
        for start in range(0, len(vectors), 2048):
            batch = vectors[start : start + 2048]
            distances = (
                squared_norms[start : start + len(batch), None]
                + center_norms[None, :]
                - 2 * batch @ centers.T
            )
            batch_labels = distances.argmin(axis=1)
            labels[start : start + len(batch)] = batch_labels
            inertia += float(distances[np.arange(len(batch)), batch_labels].sum())
            np.add.at(sums, batch_labels, batch)
            counts += np.bincount(batch_labels, minlength=clusters)
        empty = np.flatnonzero(counts == 0)
        centers[counts > 0] = sums[counts > 0] / counts[counts > 0, None]
        if len(empty):
            centers[empty] = vectors[rng.choice(len(vectors), len(empty), replace=False)]
        print(
            f"  k={clusters} iteration {iteration + 1}/{iterations}: "
            f"mean squared radius {inertia / len(vectors):.6f}",
            flush=True,
        )

    members = [np.flatnonzero(labels == cluster) for cluster in range(clusters)]
    radii = np.zeros(clusters, dtype=np.float64)
    for cluster, indices in enumerate(members):
        if len(indices):
            difference = vectors[indices] - centers[cluster]
            radii[cluster] = np.sqrt((difference * difference).sum(axis=1)).max()
    return centers, radii, labels


def generate_hidden_states(
    state: dict[str, np.ndarray], steps: int
) -> tuple[np.ndarray, list[dict[str, object]]]:
    tokenizer = BUILDER.BUILDER.Gpt2Tokenizer(
        ROOT / "data" / "tiny-gpt2" / "vocab.json",
        ROOT / "data" / "tiny-gpt2" / "merges.txt",
    )
    prompts = ["Once upon a time", "The little girl", "One day"]
    hidden_states = []
    records = []
    embeddings = state["transformer.wte.weight"]
    for prompt in prompts:
        context = tokenizer.encode(prompt)
        generated = []
        for _ in range(steps):
            hidden = BUILDER.final_hidden(context, state)
            logits = embeddings @ hidden
            winner = int(logits.argmax())
            hidden_states.append(hidden)
            generated.append(winner)
            context.append(winner)
        records.append(
            {
                "prompt": prompt,
                "tokens": generated,
                "text": "".join(tokenizer.decode_token(token) for token in generated),
            }
        )
    return np.stack(hidden_states), records


def evaluate_index(
    vectors: np.ndarray,
    queries: np.ndarray,
    centers: np.ndarray,
    radii: np.ndarray,
    labels: np.ndarray,
) -> dict[str, object]:
    members = [np.flatnonzero(labels == cluster) for cluster in range(len(centers))]
    evaluated_counts = []
    visited_counts = []
    exact = True
    for query in queries:
        upper_bounds = centers @ query + radii * np.linalg.norm(query)
        order = np.argsort(-upper_bounds)
        best_score = -np.inf
        best_token = -1
        evaluated = 0
        visited = 0
        for cluster in order:
            if upper_bounds[cluster] < best_score - 1e-6:
                break
            indices = members[int(cluster)]
            if not len(indices):
                continue
            scores = vectors[indices] @ query
            local = int(scores.argmax())
            if scores[local] > best_score:
                best_score = float(scores[local])
                best_token = int(indices[local])
            evaluated += len(indices)
            visited += 1
        reference_scores = vectors @ query
        reference_token = int(reference_scores.argmax())
        exact &= best_token == reference_token
        evaluated_counts.append(evaluated)
        visited_counts.append(visited)
    evaluated_array = np.asarray(evaluated_counts)
    visited_array = np.asarray(visited_counts)
    dense_terms = len(vectors) * vectors.shape[1]
    term_counts = len(centers) * vectors.shape[1] + evaluated_array * vectors.shape[1]
    return {
        "queries": len(queries),
        "exact": bool(exact),
        "tokens_evaluated": {
            "minimum": int(evaluated_array.min()),
            "median": int(np.median(evaluated_array)),
            "p95": int(np.percentile(evaluated_array, 95)),
            "maximum": int(evaluated_array.max()),
            "mean": float(evaluated_array.mean()),
        },
        "clusters_visited": {
            "minimum": int(visited_array.min()),
            "median": int(np.median(visited_array)),
            "p95": int(np.percentile(visited_array, 95)),
            "maximum": int(visited_array.max()),
            "mean": float(visited_array.mean()),
        },
        "dense_multiply_terms": dense_terms,
        "indexed_multiply_terms": {
            "median": int(np.median(term_counts)),
            "p95": int(np.percentile(term_counts, 95)),
            "maximum": int(term_counts.max()),
            "mean": float(term_counts.mean()),
        },
        "mean_term_reduction": float(dense_terms / term_counts.mean()),
    }


def winner_margin_summary(vectors: np.ndarray, queries: np.ndarray) -> dict[str, float]:
    scores = queries @ vectors.T
    top_two = np.partition(scores, -2, axis=1)[:, -2:]
    margins = top_two.max(axis=1) - top_two.min(axis=1)
    return {
        "minimum": float(margins.min()),
        "median": float(np.median(margins)),
        "p05": float(np.percentile(margins, 5)),
        "maximum": float(margins.max()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clusters", nargs="+", type=int, default=[64, 256])
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--steps", type=int, default=24)
    arguments = parser.parse_args()
    state = BUILDER.load_torch_zip(BUILDER.download_checkpoint())
    embeddings = state["transformer.wte.weight"].astype(np.float64)
    print("generating real TinyStories hidden states...", flush=True)
    hidden_states, generations = generate_hidden_states(state, arguments.steps)
    rng = np.random.default_rng(20260824)
    random_queries = rng.normal(size=hidden_states.shape)
    random_queries /= np.linalg.norm(random_queries, axis=1, keepdims=True)
    random_queries *= np.median(
        np.linalg.norm(hidden_states, axis=1)
    )
    report: dict[str, object] = {
        "vocabulary": len(embeddings),
        "width": embeddings.shape[1],
        "real_queries": len(hidden_states),
        "real_winner_margins": winner_margin_summary(embeddings, hidden_states),
        "random_winner_margins": winner_margin_summary(embeddings, random_queries),
        "generations": generations,
        "indexes": [],
    }
    for clusters in arguments.clusters:
        print(f"training {clusters}-cluster exact ball index...", flush=True)
        centers, radii, labels = train_kmeans(
            embeddings, clusters, arguments.iterations, 20260824 + clusters
        )
        real = evaluate_index(embeddings, hidden_states, centers, radii, labels)
        random = evaluate_index(embeddings, random_queries, centers, radii, labels)
        result = {"clusters": clusters, "real_hidden_states": real, "random": random}
        report["indexes"].append(result)
        print(json.dumps(result, indent=2), flush=True)
    output = ROOT / "output-head-benchmark" / "search-analysis.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
