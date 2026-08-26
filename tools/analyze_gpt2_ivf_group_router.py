#!/usr/bin/env python3
"""Evaluate a k-means/IVF vocabulary router on saved GPT-2 states."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-ivf-group-router"
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
CLUSTERS = int(os.environ.get("GPT2_IVF_CLUSTERS", "256"))
ITERATIONS = int(os.environ.get("GPT2_IVF_ITERATIONS", "6"))
PROBES = (1, 2, 4, 8, 16, 32, 64, 128, 192, 256)


def train_kmeans(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20260913)
    centers = vectors[rng.choice(len(vectors), size=CLUSTERS, replace=False)].copy()
    squared_norms = np.sum(vectors * vectors, axis=1)
    labels = np.zeros(len(vectors), dtype=np.int32)
    for iteration in range(ITERATIONS):
        center_norms = np.sum(centers * centers, axis=1)
        sums = np.zeros_like(centers)
        counts = np.zeros(CLUSTERS, dtype=np.int64)
        inertia = 0.0
        for start in range(0, len(vectors), 2_048):
            batch = vectors[start : start + 2_048]
            distances = (
                squared_norms[start : start + len(batch), None]
                + center_norms[None, :]
                - 2 * batch @ centers.T
            )
            batch_labels = distances.argmin(axis=1)
            labels[start : start + len(batch)] = batch_labels
            inertia += float(np.sum(distances[np.arange(len(batch)), batch_labels]))
            np.add.at(sums, batch_labels, batch)
            counts += np.bincount(batch_labels, minlength=CLUSTERS)
        occupied = counts > 0
        centers[occupied] = sums[occupied] / counts[occupied, None]
        empty = np.flatnonzero(~occupied)
        if len(empty):
            centers[empty] = vectors[
                rng.choice(len(vectors), size=len(empty), replace=False)
            ]
        print(
            f"iteration {iteration + 1}/{ITERATIONS}: "
            f"mean squared radius={inertia / len(vectors):.6f}",
            flush=True,
        )
    members = [np.flatnonzero(labels == cluster) for cluster in range(CLUSTERS)]
    radii = np.zeros(CLUSTERS, dtype=np.float32)
    for cluster, ids in enumerate(members):
        if len(ids):
            difference = vectors[ids] - centers[cluster]
            radii[cluster] = np.sqrt(np.max(np.sum(difference * difference, axis=1)))
    return centers, radii, labels


def evaluate_order(
    name: str,
    order: np.ndarray,
    labels: np.ndarray,
    winners: np.ndarray,
    sizes: np.ndarray,
    ids: np.ndarray,
) -> dict[str, object]:
    expected = labels[winners[ids]]
    ranked = order[ids]
    result = {}
    for probes in PROBES:
        selected = ranked[:, :probes]
        found = np.any(selected == expected[:, None], axis=1)
        rows = np.sum(sizes[selected], axis=1)
        result[str(probes)] = {
            "recall": int(np.sum(found)),
            "fraction": float(np.mean(found)),
            "meanExactRows": float(np.mean(rows)),
            "p95ExactRows": float(np.percentile(rows, 95, method="higher")),
            "maximumExactRows": int(np.max(rows)),
            "meanRowsIncludingCenters": float(CLUSTERS + np.mean(rows)),
            "meanDenseReduction": float(len(labels) / (CLUSTERS + np.mean(rows))),
        }
    return {"ranking": name, "probes": result}


def main() -> None:
    if not STATES.exists():
        raise RuntimeError(
            "missing supervised-router states; run "
            "make analyze-gpt2-supervised-group-router first"
        )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    saved = np.load(STATES)
    hidden = saved["hidden"].astype(np.float32)
    winners = saved["dense_winners"].astype(np.int64)
    sources = saved["sources"]
    lengths = saved["lengths"]
    split_ids = {
        name: saved[f"{name}_ids"].astype(np.int64)
        for name in ("train", "validation", "test")
    }
    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(tensors.tensor("wte.weight")[:50_257], dtype=np.float32)
    centers, radii, labels = train_kmeans(weights)
    sizes = np.bincount(labels, minlength=CLUSTERS)
    center_scores = hidden @ centers.T
    ball_bounds = center_scores + np.linalg.norm(hidden, axis=1)[:, None] * radii[None, :]
    rankings = {
        "centroid-dot": np.argsort(center_scores, axis=1)[:, ::-1],
        "l2-upper-bound": np.argsort(ball_bounds, axis=1)[:, ::-1],
    }

    result: dict[str, object] = {
        "model": "openai-community/gpt2",
        "clusters": CLUSTERS,
        "iterations": ITERATIONS,
        "clusterSizes": {
            "minimum": int(sizes.min()),
            "median": float(np.median(sizes)),
            "p95": float(np.percentile(sizes, 95, method="higher")),
            "maximum": int(sizes.max()),
        },
        "splits": {},
    }
    for split_name, ids in split_ids.items():
        split_result = {
            name: evaluate_order(name, order, labels, winners, sizes, ids)
            for name, order in rankings.items()
        }
        if split_name == "test":
            split_result["breakdown"] = {}
            for source_id, source_name in enumerate(("uniform-random", "local-text")):
                split_result["breakdown"][source_name] = {}
                for length in (2, 4, 8, 16):
                    subset = ids[(sources[ids] == source_id) & (lengths[ids] == length)]
                    split_result["breakdown"][source_name][str(length)] = {
                        name: evaluate_order(
                            name, order, labels, winners, sizes, subset
                        )["probes"]
                        for name, order in rankings.items()
                    }
        result["splits"][split_name] = split_result

    np.savez_compressed(
        OUTPUT / "index.npz", centers=centers, radii=radii, labels=labels
    )
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    summary = {
        name: {
            probes: values
            for probes, values in result["splits"]["test"][name]["probes"].items()
            if probes in {"1", "2", "4", "8", "16", "32"}
        }
        for name in rankings
    }
    print(json.dumps({
        "clusterSizes": result["clusterSizes"],
        "test": summary,
        "results": str((OUTPUT / "results.json").relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
