#!/usr/bin/env python3
"""Screen lower-dimensional coarse output heads with exact group refinement."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_global_head_precision import final_hidden_batch


ROOT = Path(__file__).resolve().parents[1]
PRECISION = (
    ROOT / "experiments" / "gpt2-hvar-grid-output-head-global11"
    / "precision-analysis.json"
)
OUTPUT = ROOT / "experiments" / "gpt2-lowrank-coarse-head"
RANKS = (16, 32, 64, 96, 128, 192, 256, 384)
TOP_COUNTS = (1, 2, 4, 8, 16, 32, 64, 128, 256)
GROUP_SIZE = 256


def percentile(values: np.ndarray, p: float) -> float:
    return float(np.percentile(values, p, method="higher"))


def summarize(scores: np.ndarray, dense_winners: np.ndarray) -> dict[str, object]:
    approximate_winners = scores.argmax(axis=1)
    dense_groups = dense_winners // GROUP_SIZE
    approximate_groups = approximate_winners // GROUP_SIZE
    dense_scores = scores[np.arange(len(scores)), dense_winners]
    ranks = 1 + np.sum(scores > dense_scores[:, None], axis=1)
    representative_matches = []
    for sample, winner in enumerate(dense_winners):
        start = int(winner // GROUP_SIZE * GROUP_SIZE)
        stop = min(start + GROUP_SIZE, scores.shape[1])
        representative = start + int(np.argmax(scores[sample, start:stop]))
        representative_matches.append(representative == winner)
    return {
        "winnerMatches": int(np.sum(approximate_winners == dense_winners)),
        "winnerGroupMatches": int(np.sum(approximate_groups == dense_groups)),
        "denseWinnerRankMedian": percentile(ranks, 50),
        "denseWinnerRankP95": percentile(ranks, 95),
        "denseWinnerRankMaximum": int(ranks.max()),
        "perGroupRepresentativeRecall": int(np.sum(representative_matches)),
        "topKRecall": {
            str(count): int(np.sum(ranks <= count)) for count in TOP_COUNTS
        },
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
    dense_scores = queries @ weights.T
    dense_winners = dense_scores.argmax(axis=1)

    # A vocabulary-wide row mean contributes one query-dependent constant to
    # every token score, so remove it before measuring ranking subspaces.
    centered_weights = weights - weights.mean(axis=0, keepdims=True)
    covariance = centered_weights.T @ centered_weights
    eigenvalues, eigenvectors = np.linalg.eigh(covariance.astype(np.float64))
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    basis = eigenvectors[:, order[:max(RANKS)]].astype(np.float32)
    projected_queries = queries @ basis
    projected_weights = centered_weights @ basis

    coordinate_energy = np.diag(covariance)
    coordinate_order = np.argsort(coordinate_energy)[::-1]
    total_energy = float(eigenvalues.sum())
    result: dict[str, object] = {
        "model": "openai-community/gpt2",
        "samples": len(queries),
        "vocabulary": len(weights),
        "dimensions": weights.shape[1],
        "ranks": {},
    }
    for rank in RANKS:
        pca_scores = projected_queries[:, :rank] @ projected_weights[:, :rank].T
        dimensions = coordinate_order[:rank]
        coordinate_scores = (
            queries[:, dimensions] @ centered_weights[:, dimensions].T
        )
        result["ranks"][str(rank)] = {
            "pcaEnergyFraction": float(eigenvalues[:rank].sum() / total_energy),
            "pca": summarize(pca_scores, dense_winners),
            "largestEnergyCoordinates": summarize(coordinate_scores, dense_winners),
        }

    # Cross-validate a basis learned from the distribution of final hidden
    # states. Their mean contribution is token-dependent but query-independent,
    # so a browser head can fold it into each candidate's fixed base.
    rng = np.random.default_rng(20260913)
    permutation = rng.permutation(len(queries))
    train_ids = permutation[: len(queries) // 2]
    heldout_ids = permutation[len(queries) // 2 :]
    query_mean = queries[train_ids].mean(axis=0, keepdims=True)
    _, _, query_vt = np.linalg.svd(
        queries[train_ids] - query_mean, full_matrices=False
    )
    query_basis = query_vt.T.astype(np.float32)
    query_projected_weights = centered_weights @ query_basis
    fixed_scores = query_mean @ centered_weights.T
    result["queryDistributionPca"] = {
        "trainingSamples": len(train_ids),
        "heldoutSamples": len(heldout_ids),
        "ranks": {},
    }
    for rank in (16, 32, 64, 96, 127):
        approximate_scores = fixed_scores + (
            (queries - query_mean) @ query_basis[:, :rank]
        ) @ query_projected_weights[:, :rank].T
        result["queryDistributionPca"]["ranks"][str(rank)] = {
            "training": summarize(
                approximate_scores[train_ids], dense_winners[train_ids]
            ),
            "heldout": summarize(
                approximate_scores[heldout_ids], dense_winners[heldout_ids]
            ),
        }
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
