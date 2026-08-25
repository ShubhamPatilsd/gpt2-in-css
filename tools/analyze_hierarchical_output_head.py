#!/usr/bin/env python3
"""Measure a parallel two-level exact ball index for the TinyStories head."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path

import numpy as np

import analyze_output_head_search as SEARCH
import build_output_head_benchmark as HEAD


ROOT = Path(__file__).resolve().parents[1]


def train_hierarchy(
    vectors: np.ndarray, top_clusters: int, children: int, iterations: int
) -> dict[str, object]:
    top_centers, top_radii, top_labels = SEARCH.train_kmeans(
        vectors, top_clusters, iterations, 20260824 + top_clusters
    )
    top_members = [
        np.flatnonzero(top_labels == cluster) for cluster in range(top_clusters)
    ]
    child_centers = []
    child_radii = []
    child_members = []
    for top, members in enumerate(top_members):
        count = min(children, len(members))
        if count == 1:
            centers = vectors[members].mean(axis=0, keepdims=True)
            difference = vectors[members] - centers[0]
            radii = np.asarray(
                [np.sqrt((difference * difference).sum(axis=1)).max()]
            )
            groups = [members]
        else:
            # There are hundreds of leaf fits; keep the reproducible command's
            # output readable while the shared trainer reports its iterations.
            with contextlib.redirect_stdout(io.StringIO()):
                centers, radii, local_labels = SEARCH.train_kmeans(
                    vectors[members],
                    count,
                    max(3, iterations // 2),
                    20260824 + top_clusters * 100 + top,
                )
            groups = [
                members[np.flatnonzero(local_labels == child)]
                for child in range(count)
            ]
        child_centers.append(centers)
        child_radii.append(radii)
        child_members.append(groups)
    return {
        "top_centers": top_centers,
        "top_radii": top_radii,
        "top_members": top_members,
        "child_centers": child_centers,
        "child_radii": child_radii,
        "child_members": child_members,
    }


def evaluate(
    vectors: np.ndarray, queries: np.ndarray, hierarchy: dict[str, object]
) -> dict[str, object]:
    top_centers = hierarchy["top_centers"]
    top_radii = hierarchy["top_radii"]
    child_centers = hierarchy["child_centers"]
    child_radii = hierarchy["child_radii"]
    child_members = hierarchy["child_members"]
    evaluated_counts = []
    active_top_counts = []
    active_child_counts = []
    bound_term_counts = []
    exact = True

    def evaluate_top(
        query: np.ndarray, top: int, threshold: float
    ) -> tuple[float, int, int, int]:
        centers = child_centers[top]
        radii = child_radii[top]
        groups = child_members[top]
        bounds = centers @ query + radii * np.linalg.norm(query)
        seed = int(bounds.argmax())
        seed_scores = vectors[groups[seed]] @ query
        best = float(seed_scores.max())
        evaluated = len(groups[seed])
        active_children = 1
        cutoff = max(threshold, best) - 1e-6
        for child, group in enumerate(groups):
            if child == seed or bounds[child] < cutoff:
                continue
            scores = vectors[group] @ query
            best = max(best, float(scores.max()))
            evaluated += len(group)
            active_children += 1
        return best, evaluated, active_children, len(groups)

    for query in queries:
        top_bounds = top_centers @ query + top_radii * np.linalg.norm(query)
        seed_top = int(top_bounds.argmax())
        best, evaluated, active_children, child_bounds = evaluate_top(
            query, seed_top, -np.inf
        )
        active_tops = 1
        total_child_bounds = child_bounds
        for top in range(len(top_centers)):
            if top == seed_top or top_bounds[top] < best - 1e-6:
                continue
            local_best, local_evaluated, local_active, local_bounds = evaluate_top(
                query, top, best
            )
            best = max(best, local_best)
            evaluated += local_evaluated
            active_children += local_active
            active_tops += 1
            total_child_bounds += local_bounds
        reference = float((vectors @ query).max())
        exact &= abs(best - reference) < 1e-5
        evaluated_counts.append(evaluated)
        active_top_counts.append(active_tops)
        active_child_counts.append(active_children)
        bound_term_counts.append(
            len(top_centers) * vectors.shape[1]
            + total_child_bounds * vectors.shape[1]
        )
    evaluated_array = np.asarray(evaluated_counts)
    terms = np.asarray(bound_term_counts) + evaluated_array * vectors.shape[1]
    dense = len(vectors) * vectors.shape[1]
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
        "active_top_clusters_mean": float(np.mean(active_top_counts)),
        "active_leaf_clusters_mean": float(np.mean(active_child_counts)),
        "indexed_multiply_terms_mean": float(terms.mean()),
        "mean_term_reduction": float(dense / terms.mean()),
    }


def evaluate_flat_bounds(
    vectors: np.ndarray, queries: np.ndarray, hierarchy: dict[str, object]
) -> dict[str, object]:
    """Compare exact ball, coordinate-box, and combined flat bounds fairly."""
    centers = hierarchy["top_centers"]
    radii = hierarchy["top_radii"]
    members = hierarchy["top_members"]
    minimums = np.stack([vectors[group].min(axis=0) for group in members])
    maximums = np.stack([vectors[group].max(axis=0) for group in members])
    dense_terms = len(vectors) * vectors.shape[1]
    results = {}
    for method in ("ball", "coordinate_box", "combined"):
        evaluated_counts = []
        exact = True
        for query in queries:
            ball = centers @ query + radii * np.linalg.norm(query)
            box = maximums @ np.maximum(query, 0) + minimums @ np.minimum(query, 0)
            if method == "ball":
                bounds = ball
            elif method == "coordinate_box":
                bounds = box
            else:
                bounds = np.minimum(ball, box)
            best_score = -np.inf
            best_token = -1
            evaluated = 0
            for cluster in np.argsort(-bounds):
                if bounds[cluster] < best_score - 1e-6:
                    break
                group = members[int(cluster)]
                scores = vectors[group] @ query
                local = int(scores.argmax())
                if scores[local] > best_score:
                    best_score = float(scores[local])
                    best_token = int(group[local])
                evaluated += len(group)
            exact &= best_token == int((vectors @ query).argmax())
            evaluated_counts.append(evaluated)
        counts = np.asarray(evaluated_counts)
        bound_passes = 2 if method == "combined" else 1
        terms = (
            bound_passes * len(centers) * vectors.shape[1]
            + counts * vectors.shape[1]
        )
        results[method] = {
            "exact": bool(exact),
            "tokens_evaluated_mean": float(counts.mean()),
            "tokens_evaluated_median": int(np.median(counts)),
            "mean_term_reduction": float(dense_terms / terms.mean()),
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=256)
    parser.add_argument("--children", nargs="+", type=int, default=[4, 8, 16])
    parser.add_argument("--iterations", type=int, default=8)
    arguments = parser.parse_args()
    state = HEAD.load_torch_zip(HEAD.download_checkpoint())
    vectors = state["transformer.wte.weight"].astype(np.float64)
    queries, _ = SEARCH.generate_hidden_states(state, 24)
    results = []
    flat_bound_comparison = None
    for children in arguments.children:
        print(f"training hierarchy {arguments.top} x {children}...", flush=True)
        hierarchy = train_hierarchy(
            vectors, arguments.top, children, arguments.iterations
        )
        result = {
            "top_clusters": arguments.top,
            "children": children,
            "real_hidden_states": evaluate(vectors, queries, hierarchy),
        }
        results.append(result)
        if flat_bound_comparison is None:
            flat_bound_comparison = evaluate_flat_bounds(vectors, queries, hierarchy)
        print(json.dumps(result, indent=2), flush=True)
    output = ROOT / "output-head-benchmark" / "hierarchical-analysis.json"
    payload = {
        "results": results,
        "flat_bound_comparison": flat_bound_comparison,
        "css_feasibility": {
            "status": "blocked_by_eager_global_state",
            "reason": (
                "Chromium custom functions are lazy, but a function-local custom "
                "property cannot select style() branches. Registering every leaf "
                "bound globally makes the bounds eager and erases the hierarchy's "
                "intended pruning benefit."
            ),
            "browser_probe": "tinystories/function-local-style-test.html",
        },
    }
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
