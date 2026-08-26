#!/usr/bin/env python3
"""Screen certified query-aware ball trees for the GPT-2 row-int10 head.

The index is fitted using only the saved corpus's training split.  Every bound
is nevertheless geometric (not statistical): for every query it upper-bounds
every represented row in a node.  The validation and test splits therefore
measure generalization of index quality, while correctness is certified for
all queries.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
OUTPUT = ROOT / "experiments" / "gpt2-certified-vocabulary-ball-tree"
VOCABULARY = 50_257
WIDTH = 768
MAX_SUBSPACE_RANK = 32
SUBSPACE_RANKS = (8, 16, 32)
CAP_COUNTS = (4, 8, 16)
LEAF_SIZES = (32, 64, 128, 256)
SEED = 20260914
# Bounds are formed in float64, while the 1024 x 50,257 reference/leaf cache is
# float32 to keep memory reasonable.  This outward pad dominates one float32
# score ulp at the observed magnitudes; the exhaustive node verifier below is
# the final guard.
BOUND_RELATIVE_PAD = 2e-6


@dataclass
class Node:
    ids: np.ndarray
    center: np.ndarray
    radius: float
    projection_minimum: np.ndarray
    projection_maximum: np.ndarray
    projection_radii: np.ndarray
    orthogonal_radii: np.ndarray
    cap_minimum: np.ndarray
    cap_maximum: np.ndarray
    cap_orthogonal_radii: np.ndarray
    children: list[int] = field(default_factory=list)


def percentile(values: np.ndarray, q: float) -> float:
    return float(np.percentile(values, q, method="higher"))


def distribution(values: np.ndarray) -> dict[str, float | int]:
    return {
        "minimum": int(np.min(values)),
        "median": percentile(values, 50),
        "p95": percentile(values, 95),
        "maximum": int(np.max(values)),
        "mean": float(np.mean(values)),
    }


def split_distribution(values: np.ndarray, splits: dict[str, np.ndarray]) -> dict[str, object]:
    result: dict[str, object] = {"all": distribution(values)}
    for name, ids in splits.items():
        result[name] = distribution(values[ids])
    return result


def row_int10(weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    maximum_code = 2**9 - 1
    scales = np.max(np.abs(weights), axis=1) / maximum_code
    scales[scales == 0] = 1.0
    codes = np.rint(weights / scales[:, None]).astype(np.int16)
    represented = codes.astype(np.float64) * scales[:, None]
    return represented, scales


def query_basis(train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    _left, singular, right = np.linalg.svd(train, full_matrices=False)
    return right[:MAX_SUBSPACE_RANK].T.copy(), singular


def spherical_anchors(train: np.ndarray, count: int, rng: np.random.Generator) -> np.ndarray:
    unit = train / np.linalg.norm(train, axis=1, keepdims=True)
    first = int(rng.integers(len(unit)))
    anchors = [unit[first]]
    closest = 1.0 - unit @ anchors[0]
    for _ in range(1, count):
        chosen = int(np.argmax(closest))
        anchors.append(unit[chosen])
        closest = np.minimum(closest, 1.0 - unit @ anchors[-1])
    centers = np.stack(anchors)
    for _ in range(12):
        assignment = np.argmax(unit @ centers.T, axis=1)
        updated = centers.copy()
        for cluster in range(count):
            members = unit[assignment == cluster]
            if len(members):
                candidate = members.mean(axis=0)
                norm = np.linalg.norm(candidate)
                if norm:
                    updated[cluster] = candidate / norm
        if np.max(np.abs(updated - centers)) < 1e-10:
            break
        centers = updated
    return centers


def kmeans_partition(
    values: np.ndarray,
    ids: np.ndarray,
    clusters: int,
    rng: np.random.Generator,
) -> list[np.ndarray]:
    local = values[ids]
    first = int(rng.integers(len(local)))
    centers = [local[first]]
    closest = np.sum((local - centers[0]) ** 2, axis=1)
    for _ in range(1, clusters):
        chosen = int(np.argmax(closest))
        centers.append(local[chosen])
        distance = np.sum((local - centers[-1]) ** 2, axis=1)
        closest = np.minimum(closest, distance)
    center_matrix = np.stack(centers)
    assignment = np.zeros(len(local), dtype=np.int32)
    local_norms = np.sum(local * local, axis=1)
    for _ in range(8):
        distances = (
            local_norms[:, None]
            + np.sum(center_matrix * center_matrix, axis=1)[None, :]
            - 2.0 * local @ center_matrix.T
        )
        updated_assignment = np.argmin(distances, axis=1).astype(np.int32)
        if np.array_equal(updated_assignment, assignment):
            assignment = updated_assignment
            break
        assignment = updated_assignment
        for cluster in range(clusters):
            members = local[assignment == cluster]
            if len(members):
                center_matrix[cluster] = members.mean(axis=0)
    groups = [ids[assignment == cluster] for cluster in range(clusters)]
    return [group for group in groups if len(group)]


def make_node(
    weights: np.ndarray,
    projected: np.ndarray,
    anchors: np.ndarray,
    ids: np.ndarray,
) -> Node:
    values = weights[ids]
    center = values.mean(axis=0)
    center_projection = center @ BASIS
    projection_residual = projected[ids] - center_projection
    projection_minimum = projection_residual.min(axis=0)
    projection_maximum = projection_residual.max(axis=0)

    total_squared = np.empty(len(ids), dtype=np.float64)
    for start in range(0, len(ids), 4096):
        stop = min(start + 4096, len(ids))
        residual = values[start:stop] - center
        total_squared[start:stop] = np.einsum("ij,ij->i", residual, residual)
    radius = math.sqrt(max(0.0, float(np.max(total_squared))))

    cumulative = np.cumsum(projection_residual * projection_residual, axis=1)
    projection_radii = np.empty(len(SUBSPACE_RANKS), dtype=np.float64)
    orthogonal_radii = np.empty(len(SUBSPACE_RANKS), dtype=np.float64)
    for index, rank in enumerate(SUBSPACE_RANKS):
        projection_radii[index] = math.sqrt(max(0.0, float(np.max(cumulative[:, rank - 1]))))
        orthogonal_radii[index] = math.sqrt(max(
            0.0, float(np.max(total_squared - cumulative[:, rank - 1]))
        ))

    cap_projection = values @ anchors.T - center @ anchors.T
    cap_minimum = cap_projection.min(axis=0)
    cap_maximum = cap_projection.max(axis=0)
    cap_orthogonal_radii = np.sqrt(np.maximum(
        0.0,
        np.max(total_squared[:, None] - cap_projection * cap_projection, axis=0),
    ))
    return Node(
        ids=ids,
        center=center,
        radius=radius,
        projection_minimum=projection_minimum,
        projection_maximum=projection_maximum,
        projection_radii=projection_radii,
        orthogonal_radii=orthogonal_radii,
        cap_minimum=cap_minimum,
        cap_maximum=cap_maximum,
        cap_orthogonal_radii=cap_orthogonal_radii,
    )


def build_tree(
    weights: np.ndarray,
    projected: np.ndarray,
    anchors: np.ndarray,
    partition_values: np.ndarray,
    branching: int,
    minimum_leaf: int,
    rng: np.random.Generator,
) -> list[Node]:
    nodes: list[Node] = []

    def visit(ids: np.ndarray) -> int:
        index = len(nodes)
        nodes.append(make_node(weights, projected, anchors, ids))
        if len(ids) <= minimum_leaf:
            return index
        child_count = min(branching, max(2, math.ceil(len(ids) / minimum_leaf)))
        groups = kmeans_partition(partition_values, ids, child_count, rng)
        if len(groups) <= 1 or max(len(group) for group in groups) == len(ids):
            order = np.argsort(partition_values[ids, 0], kind="stable")
            groups = [group for group in np.array_split(ids[order], child_count) if len(group)]
        nodes[index].children = [visit(group) for group in groups]
        return index

    visit(np.arange(len(weights), dtype=np.int32))
    return nodes


def bound_matrices(
    queries: np.ndarray,
    nodes: list[Node],
    basis: np.ndarray,
    anchors: np.ndarray,
) -> dict[str, np.ndarray]:
    centers = np.stack([node.center for node in nodes])
    center_scores = queries @ centers.T
    query_norms = np.linalg.norm(queries, axis=1)
    radii = np.asarray([node.radius for node in nodes])
    results = {"l2Ball": center_scores + query_norms[:, None] * radii[None, :]}

    query_projection = queries @ basis
    for rank_index, rank in enumerate(SUBSPACE_RANKS):
        coordinates = query_projection[:, :rank]
        projected_norms = np.linalg.norm(coordinates, axis=1)
        perpendicular = np.sqrt(np.maximum(0.0, query_norms**2 - projected_norms**2))
        minimums = np.stack([node.projection_minimum[:rank] for node in nodes])
        maximums = np.stack([node.projection_maximum[:rank] for node in nodes])
        box_support = (
            np.maximum(coordinates, 0) @ maximums.T
            + np.minimum(coordinates, 0) @ minimums.T
        )
        projection_radii = np.asarray([node.projection_radii[rank_index] for node in nodes])
        projected_ball = projected_norms[:, None] * projection_radii[None, :]
        orthogonal_radii = np.asarray([node.orthogonal_radii[rank_index] for node in nodes])
        residual = np.minimum(box_support, projected_ball) + perpendicular[:, None] * orthogonal_radii
        results[f"querySubspaceR{rank}"] = np.minimum(
            results["l2Ball"], center_scores + residual
        )

    query_anchor = queries @ anchors.T
    anchor_perpendicular = np.sqrt(np.maximum(
        0.0, query_norms[:, None] ** 2 - query_anchor * query_anchor
    ))
    cap_minimum = np.stack([node.cap_minimum for node in nodes])
    cap_maximum = np.stack([node.cap_maximum for node in nodes])
    cap_orthogonal = np.stack([node.cap_orthogonal_radii for node in nodes])
    cap_terms = np.where(
        query_anchor[:, :, None] >= 0,
        query_anchor[:, :, None] * cap_maximum.T[None, :, :],
        query_anchor[:, :, None] * cap_minimum.T[None, :, :],
    ) + anchor_perpendicular[:, :, None] * cap_orthogonal.T[None, :, :]
    for cap_count in CAP_COUNTS:
        cap_bound = center_scores + np.min(cap_terms[:, :cap_count, :], axis=1)
        results[f"sphericalCaps{cap_count}"] = np.minimum(results["l2Ball"], cap_bound)

    results["combinedR16Caps8"] = np.minimum(
        results["querySubspaceR16"], results["sphericalCaps8"]
    )
    for name in results:
        values = results[name]
        values += BOUND_RELATIVE_PAD * (1.0 + np.abs(values))
    return results


def node_exact_maxima(scores: np.ndarray, nodes: list[Node]) -> np.ndarray:
    maxima = np.empty((len(scores), len(nodes)), dtype=np.float32)
    for index in range(len(nodes) - 1, -1, -1):
        node = nodes[index]
        if node.children:
            maxima[:, index] = np.max(maxima[:, node.children], axis=1)
        else:
            maxima[:, index] = np.max(scores[:, node.ids], axis=1)
    return maxima


def search_one(
    scores: np.ndarray,
    nodes: list[Node],
    bounds: np.ndarray,
    leaf_size: int,
) -> tuple[int, int, int, int, int]:
    best_score = -math.inf
    best_token = VOCABULARY
    rows_scored = 0
    internal_scored = 1
    node_bounds_scored = 1
    leaves_scored = 0
    queue: list[tuple[float, int]] = [(-float(bounds[0]), 0)]
    while queue:
        negative_bound, index = heapq.heappop(queue)
        upper = -negative_bound
        if upper < best_score:
            break
        node = nodes[index]
        if not node.children or len(node.ids) <= leaf_size:
            local_scores = scores[node.ids]
            local_best = float(np.max(local_scores))
            tied = node.ids[local_scores == local_best]
            token = int(np.min(tied))
            rows_scored += len(node.ids)
            leaves_scored += 1
            if local_best > best_score or (local_best == best_score and token < best_token):
                best_score = local_best
                best_token = token
            continue
        for child in node.children:
            child_node = nodes[child]
            node_bounds_scored += 1
            if child_node.children and len(child_node.ids) > leaf_size:
                internal_scored += 1
            child_bound = float(bounds[child])
            if child_bound >= best_score:
                heapq.heappush(queue, (-child_bound, child))
    return best_token, rows_scored, internal_scored, node_bounds_scored, leaves_scored


def evaluate(
    scores: np.ndarray,
    winners: np.ndarray,
    nodes: list[Node],
    bounds: np.ndarray,
    leaf_size: int,
    splits: dict[str, np.ndarray],
) -> tuple[dict[str, object], dict[str, list[int]]]:
    rows = np.empty(len(scores), dtype=np.int32)
    internals = np.empty(len(scores), dtype=np.int32)
    node_bounds = np.empty(len(scores), dtype=np.int32)
    leaves = np.empty(len(scores), dtype=np.int32)
    found = np.empty(len(scores), dtype=np.int32)
    for sample in range(len(scores)):
        found[sample], rows[sample], internals[sample], node_bounds[sample], leaves[sample] = search_one(
            scores[sample], nodes, bounds[sample], leaf_size
        )
    matches = found == winners
    summary = {
        "winnerMatches": int(np.sum(matches)),
        "winnerRetentionRate": float(np.mean(matches)),
        "leafRowsScored": split_distribution(rows, splits),
        "leafRowFractionOfFullScan": {
            name: {key: value / VOCABULARY for key, value in values.items()}
            for name, values in split_distribution(rows, splits).items()
        },
        "internalNodesScored": split_distribution(internals, splits),
        "allNodeBoundsScored": split_distribution(node_bounds, splits),
        "leavesScored": split_distribution(leaves, splits),
    }
    raw = {
        "winner": found.astype(int).tolist(),
        "winnerMatches": matches.astype(int).tolist(),
        "leafRowsScored": rows.astype(int).tolist(),
        "internalNodesScored": internals.astype(int).tolist(),
        "allNodeBoundsScored": node_bounds.astype(int).tolist(),
        "leavesScored": leaves.astype(int).tolist(),
    }
    return summary, raw


def render_report(result: dict[str, object]) -> str:
    best = result["bestMeasured"]
    baseline = result["baseline"]
    rows = []
    for tree_name, tree in result["trees"].items():
        for bound_name, by_leaf in tree["bounds"].items():
            for leaf, metrics in by_leaf.items():
                all_rows = metrics["leafRowsScored"]["all"]
                all_nodes = metrics["internalNodesScored"]["all"]
                rows.append(
                    f'| {tree_name} | {bound_name} | {leaf} | '
                    f'{metrics["winnerMatches"]}/1024 | {all_rows["median"]:.0f} | '
                    f'{all_rows["p95"]:.0f} | {all_rows["maximum"]} | '
                    f'{all_nodes["median"]:.0f} | {all_nodes["p95"]:.0f} |'
                )
    return f"""# Certified query-aware vocabulary ball tree

## Result

The strongest measured configuration retained the exact row-int10 winner for **{best['winnerMatches']}/1,024 states**. It scored a median **{best['leafRowsScored']['all']['median']:.0f}** leaf rows, p95 **{best['leafRowsScored']['all']['p95']:.0f}**, and maximum **{best['leafRowsScored']['all']['maximum']}**, versus **{baseline['rowsPerQuery']:,} rows** for the full int10 scan. Median retained row work was **{100 * best['leafRowFractionOfFullScan']['all']['median']:.2f}%** of baseline.

This is materially stronger than the prior axis-split full-space L2/box screen: the new hierarchy is k-means-partitioned in a training-query metric, and its strongest bound takes the minimum of a full L2 ball, a rank-16 query-subspace residual bound, and eight spherical-cap residual bounds. The index was fitted only on the saved 512-state training split; validation and test states were not used to fit its basis, anchors, or partition.

## Measurements

| Tree | Certified bound | Leaf threshold | Exact winners | Median rows | p95 rows | Max rows | Median internal nodes | p95 internal nodes |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

The complete split distributions, all per-state raw counts, tree geometry, and bound checks are in `results.json` and `raw-results.json`.

## Certification contract

- Target rows are the checkpoint's 50,257 output embeddings after independent symmetric signed-int10 quantization per row (code range -511..511).
- Full-scan winners and leaf scores use the same realized row-int10 matrix and saved float32 hidden states.
- For node representative `c`, the plain bound is `h·c + ||h||₂ r`.
- The subspace bound stores rigorous coordinate intervals and an orthogonal residual radius; the cap bound stores a scalar interval and perpendicular residual radius for each unit anchor. Taking the minimum of valid upper bounds remains valid.
- Ties are resolved by the lowest token id, matching `argmax`; pruning is strict below the incumbent score.
- Every stored node bound was checked against that node's exact maximum for every one of the 1,024 queries. Maximum observed bound violation was **{result['validation']['maximumBoundViolation']:.3g}**.

## Interpretation

This is an offline feasibility screen, not a claim that CSS can branch dynamically at this cost. Internal-node bounds have nontrivial arithmetic and storage: subspace/cap bounds exchange vocabulary-row dot products for representative dots plus interval/radius terms. The separate internal-node and leaf-row distributions make that tradeoff explicit. Query fitting is corpus-specific, while correctness is geometric for any query evaluated against the stored bounds.

Runtime was **{result['runtimeSeconds']:.2f}s** with offline NumPy; no browser was used.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branching", nargs="+", type=int, default=[8, 16])
    parser.add_argument("--minimum-leaf", type=int, default=32)
    args = parser.parse_args()
    started = time.perf_counter()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    saved = np.load(STATES)
    queries = np.asarray(saved["hidden"], dtype=np.float64)
    if queries.shape != (1_024, WIDTH):
        raise RuntimeError(f"unexpected query corpus shape {queries.shape}")
    splits = {
        "train": np.asarray(saved["train_ids"], dtype=np.int64),
        "validation": np.asarray(saved["validation_ids"], dtype=np.int64),
        "test": np.asarray(saved["test_ids"], dtype=np.int64),
    }
    train = queries[splits["train"]]
    global BASIS
    BASIS, singular = query_basis(train)
    rng = np.random.default_rng(SEED)
    anchors = spherical_anchors(train, max(CAP_COUNTS), rng)

    checkpoint_weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY], dtype=np.float64
    )
    weights, row_scales = row_int10(checkpoint_weights)
    del checkpoint_weights
    projected = weights @ BASIS
    query_coordinates = train @ BASIS[:, :16]
    metric_scale = np.sqrt(np.mean(query_coordinates * query_coordinates, axis=0))
    metric_scale /= max(float(np.max(metric_scale)), np.finfo(np.float64).tiny)
    partition_values = projected[:, :16] * metric_scale[None, :]

    scores = np.empty((len(queries), VOCABULARY), dtype=np.float32)
    winners = np.empty(len(queries), dtype=np.int64)
    winner_scores = np.empty(len(queries), dtype=np.float64)
    top2_margins = np.empty(len(queries), dtype=np.float64)
    for start in range(0, len(queries), 32):
        stop = min(start + 32, len(queries))
        exact = queries[start:stop] @ weights.T
        scores[start:stop] = exact.astype(np.float32)
        winners[start:stop] = np.argmax(exact, axis=1)
        winner_scores[start:stop] = exact[np.arange(stop - start), winners[start:stop]]
        top = np.partition(exact, -2, axis=1)[:, -2:]
        top2_margins[start:stop] = top[:, 1] - top[:, 0]
    # The float32 score cache is used by both branch-and-bound and its reference.
    winners = np.argmax(scores, axis=1)

    result: dict[str, object] = {
        "model": "openai-community/gpt2",
        "target": "per-row symmetric signed-int10 output embeddings",
        "samples": len(queries),
        "dimensions": WIDTH,
        "vocabulary": VOCABULARY,
        "seed": SEED,
        "baseline": {
            "name": "full row-int10 scan",
            "rowsPerQuery": VOCABULARY,
            "totalRows": VOCABULARY * len(queries),
        },
        "corpus": {
            "path": str(STATES.relative_to(ROOT)),
            "splits": {name: len(ids) for name, ids in splits.items()},
        },
        "checkpoint": str(MODEL_PATH.relative_to(ROOT)),
        "quantization": {
            "codeMinimum": -511,
            "codeMaximum": 511,
            "minimumRowScale": float(np.min(row_scales)),
            "medianRowScale": float(np.median(row_scales)),
            "maximumRowScale": float(np.max(row_scales)),
        },
        "queryFit": {
            "fitSplit": "train only",
            "subspaceRanks": list(SUBSPACE_RANKS),
            "capCounts": list(CAP_COUNTS),
            "trainingSingularEnergyFraction": {
                str(rank): float(np.sum(singular[:rank] ** 2) / np.sum(singular**2))
                for rank in SUBSPACE_RANKS
            },
        },
        "fullScan": {
            "winner": winners.astype(int).tolist(),
            "winnerScoreFloat64BeforeCache": winner_scores.tolist(),
            "top2MarginFloat64BeforeCache": top2_margins.tolist(),
        },
        "trees": {},
    }
    raw: dict[str, object] = {
        "fullScanWinner": winners.astype(int).tolist(),
        "trees": {},
    }
    maximum_violation = 0.0
    candidates: list[dict[str, object]] = []
    for branching in args.branching:
        tree_started = time.perf_counter()
        nodes = build_tree(
            weights,
            projected,
            anchors,
            partition_values,
            branching,
            args.minimum_leaf,
            np.random.default_rng(SEED + branching),
        )
        bounds = bound_matrices(queries, nodes, BASIS, anchors)
        exact_maxima = node_exact_maxima(scores, nodes)
        tree_name = f"kmeans-b{branching}-minleaf{args.minimum_leaf}"
        tree_result: dict[str, object] = {
            "branching": branching,
            "minimumLeafSize": args.minimum_leaf,
            "nodes": len(nodes),
            "internalNodes": int(sum(bool(node.children) for node in nodes)),
            "leaves": int(sum(not node.children for node in nodes)),
            "maximumDepth": None,
            "leafSize": distribution(np.asarray([
                len(node.ids) for node in nodes if not node.children
            ], dtype=np.int64)),
            "bounds": {},
        }
        depths = np.zeros(len(nodes), dtype=np.int32)
        for index, node in enumerate(nodes):
            for child in node.children:
                depths[child] = depths[index] + 1
        tree_result["maximumDepth"] = int(np.max(depths))
        raw["trees"][tree_name] = {}
        for bound_name, matrix in bounds.items():
            violation = float(np.max(exact_maxima.astype(np.float64) - matrix))
            maximum_violation = max(maximum_violation, violation)
            if violation > 2e-6:
                raise RuntimeError(f"{bound_name} violated by {violation}")
            by_leaf: dict[str, object] = {}
            raw_by_leaf: dict[str, object] = {}
            for leaf_size in LEAF_SIZES:
                summary, per_query = evaluate(
                    scores, winners, nodes, matrix, leaf_size, splits
                )
                if summary["winnerMatches"] != len(queries):
                    raise RuntimeError(
                        f"{tree_name}/{bound_name}/{leaf_size} lost winners"
                    )
                by_leaf[str(leaf_size)] = summary
                raw_by_leaf[str(leaf_size)] = per_query
                candidates.append({
                    "tree": tree_name,
                    "bound": bound_name,
                    "leafSize": leaf_size,
                    **summary,
                })
            tree_result["bounds"][bound_name] = by_leaf
            raw["trees"][tree_name][bound_name] = raw_by_leaf
        tree_result["buildAndEvaluateSeconds"] = time.perf_counter() - tree_started
        result["trees"][tree_name] = tree_result
        print(
            f"completed {tree_name}: {len(nodes)} nodes in "
            f"{tree_result['buildAndEvaluateSeconds']:.2f}s",
            flush=True,
        )

    best = min(
        candidates,
        key=lambda row: (
            row["leafRowsScored"]["all"]["median"],
            row["leafRowsScored"]["all"]["p95"],
            row["internalNodesScored"]["all"]["median"],
        ),
    )
    result["bestMeasured"] = best
    result["validation"] = {
        "allWinnerChecksPassed": True,
        "allNodeBoundsCheckedForAllQueries": True,
        "maximumBoundViolation": maximum_violation,
        "boundViolationTolerance": 2e-6,
    }
    result["runtimeSeconds"] = time.perf_counter() - started
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUTPUT / "raw-results.json").write_text(json.dumps(raw) + "\n")
    (OUTPUT / "RESULTS.md").write_text(render_report(result))
    print(json.dumps({
        "best": {
            "tree": best["tree"],
            "bound": best["bound"],
            "leafSize": best["leafSize"],
            "leafRowsScored": best["leafRowsScored"]["all"],
            "internalNodesScored": best["internalNodesScored"]["all"],
            "winnerMatches": best["winnerMatches"],
        },
        "runtimeSeconds": result["runtimeSeconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
