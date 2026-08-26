#!/usr/bin/env python3
"""Measure exact branch-and-bound pruning for GPT-2 maximum inner product."""

from __future__ import annotations

import heapq
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_global_head_precision import final_hidden_batch


ROOT = Path(__file__).resolve().parents[1]
PRECISION = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global11"
    / "precision-analysis.json"
)
OUTPUT = ROOT / "experiments" / "gpt2-mips-pruning"
MIN_LEAF = 64
LEAF_SIZES = (64, 128, 256, 512)


@dataclass
class Node:
    ids: np.ndarray
    left: int = -1
    right: int = -1


def percentile(values: np.ndarray, p: float) -> float:
    return float(np.percentile(values, p, method="higher"))


def build_tree(weights: np.ndarray) -> tuple[list[Node], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    nodes: list[Node] = []
    centers: list[np.ndarray] = []
    radii: list[float] = []
    minimums: list[np.ndarray] = []
    maximums: list[np.ndarray] = []

    def visit(ids: np.ndarray) -> int:
        values = weights[ids]
        index = len(nodes)
        nodes.append(Node(ids=ids))
        center = values.mean(axis=0, dtype=np.float64).astype(np.float32)
        centers.append(center)
        radii.append(float(np.sqrt(np.max(np.sum(
            (values - center) ** 2, axis=1, dtype=np.float64
        )))))
        minimums.append(values.min(axis=0))
        maximums.append(values.max(axis=0))
        if len(ids) <= MIN_LEAF:
            return index
        axis = int(np.argmax(values.var(axis=0, dtype=np.float64)))
        midpoint = len(ids) // 2
        order = np.argpartition(values[:, axis], midpoint)
        left_ids = ids[order[:midpoint]]
        right_ids = ids[order[midpoint:]]
        nodes[index].left = visit(left_ids)
        nodes[index].right = visit(right_ids)
        return index

    visit(np.arange(len(weights), dtype=np.int32))
    return (
        nodes,
        np.stack(centers),
        np.asarray(radii, dtype=np.float32),
        np.stack(minimums),
        np.stack(maximums),
    )


def simulate(
    nodes: list[Node],
    bounds: np.ndarray,
    scores: np.ndarray,
    winner: int,
    leaf_size: int,
) -> dict[str, int | bool]:
    best_score = -np.inf
    best_token = -1
    evaluated_tokens = 0
    evaluated_nodes = 1
    queue: list[tuple[float, int]] = [(-float(bounds[0]), 0)]
    while queue:
        negative_bound, node_index = heapq.heappop(queue)
        if -negative_bound <= best_score + 1e-7:
            break
        node = nodes[node_index]
        if len(node.ids) <= leaf_size:
            leaf_scores = scores[node.ids]
            local = int(np.argmax(leaf_scores))
            candidate_score = float(leaf_scores[local])
            candidate_token = int(node.ids[local])
            evaluated_tokens += len(node.ids)
            if candidate_score > best_score:
                best_score = candidate_score
                best_token = candidate_token
            continue
        for child in (node.left, node.right):
            evaluated_nodes += 1
            if bounds[child] > best_score + 1e-7:
                heapq.heappush(queue, (-float(bounds[child]), child))
    return {
        "evaluatedTokens": evaluated_tokens,
        "evaluatedNodes": evaluated_nodes,
        "winnerCorrect": best_token == winner,
    }


def summarize(rows: list[dict[str, int | bool]], vocabulary: int) -> dict[str, object]:
    tokens = np.asarray([row["evaluatedTokens"] for row in rows], dtype=np.int64)
    nodes = np.asarray([row["evaluatedNodes"] for row in rows], dtype=np.int64)
    return {
        "winnerMatches": int(sum(bool(row["winnerCorrect"]) for row in rows)),
        "meanTokens": float(tokens.mean()),
        "medianTokens": percentile(tokens, 50),
        "p95Tokens": percentile(tokens, 95),
        "maximumTokens": int(tokens.max()),
        "medianVocabularyFraction": percentile(tokens, 50) / vocabulary,
        "medianNodes": percentile(nodes, 50),
        "p95Nodes": percentile(nodes, 95),
        "maximumNodes": int(nodes.max()),
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    precision = json.loads(PRECISION.read_text())
    tensors = SafeTensors(MODEL_PATH)
    token_ids = np.asarray(precision["tokenIds"], dtype=np.int64)
    queries = final_hidden_batch(token_ids, tensors).astype(np.float32)
    weights = np.asarray(
        tensors.tensor("wte.weight")[:50_257], dtype=np.float32
    )
    scores = queries @ weights.T
    winners = scores.argmax(axis=1)
    nodes, centers, radii, minimums, maximums = build_tree(weights)

    query_norms = np.linalg.norm(queries, axis=1)
    ball_bounds = queries @ centers.T + query_norms[:, None] * radii[None, :]
    positive = np.maximum(queries, 0)
    negative = np.minimum(queries, 0)
    box_bounds = positive @ maximums.T + negative @ minimums.T
    hybrid_bounds = np.minimum(ball_bounds, box_bounds)

    result: dict[str, object] = {
        "model": "openai-community/gpt2",
        "samples": len(queries),
        "vocabulary": len(weights),
        "dimensions": weights.shape[1],
        "treeNodes": len(nodes),
        "minimumLeafSize": MIN_LEAF,
        "bounds": {},
    }
    for name, bound_matrix in (
        ("l2Ball", ball_bounds),
        ("axisAlignedBox", box_bounds),
        ("minimumOfBoth", hybrid_bounds),
    ):
        by_leaf = {}
        for leaf_size in LEAF_SIZES:
            rows = [
                simulate(
                    nodes,
                    bound_matrix[sample],
                    scores[sample],
                    int(winners[sample]),
                    leaf_size,
                )
                for sample in range(len(queries))
            ]
            by_leaf[str(leaf_size)] = summarize(rows, len(weights))
        result["bounds"][name] = by_leaf

    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
