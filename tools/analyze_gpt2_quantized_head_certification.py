#!/usr/bin/env python3
"""Screen rigorous quantization-error bounds for a staged GPT-2 output head."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
OUTPUT = ROOT / "experiments" / "gpt2-quantized-head-certification"
VOCABULARY = 50_257
GROUP_SIZE = 256
GROUPS = (VOCABULARY + GROUP_SIZE - 1) // GROUP_SIZE
BITS = (6, 7, 8, 9, 10, 11)
BATCH = 64


def percentile(values: np.ndarray, value: float) -> float:
    return float(np.percentile(values, value, method="higher"))


def summarize(values: np.ndarray) -> dict[str, float]:
    return {
        "minimum": float(values.min()),
        "median": percentile(values, 50),
        "p95": percentile(values, 95),
        "maximum": float(values.max()),
        "mean": float(values.mean()),
    }


def stopping_counts(upper: np.ndarray, exact: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(upper, axis=1)[:, ::-1]
    ordered_upper = np.take_along_axis(upper, order, axis=1)
    ordered_exact = np.take_along_axis(exact, order, axis=1)
    best = np.maximum.accumulate(ordered_exact, axis=1)
    done = best[:, :-1] >= ordered_upper[:, 1:] - 1e-6
    has_done = np.any(done, axis=1)
    counts = np.where(has_done, np.argmax(done, axis=1) + 1, upper.shape[1])
    return counts.astype(np.int64), order


def evaluate(
    hidden: np.ndarray,
    dense_winners: np.ndarray,
    weights: np.ndarray,
    bits: int,
    mode: str,
) -> dict[str, object]:
    maximum_code = 2 ** (bits - 1) - 1
    if mode == "row-wise":
        scales = np.max(np.abs(weights), axis=1) / maximum_code
        scales[scales == 0] = 1.0
        codes = np.rint(weights / scales[:, None]).clip(
            -maximum_code, maximum_code
        ).astype(np.int16)
        represented = codes.astype(np.float32) * scales[:, None]
    elif mode == "global":
        scale = float(np.max(np.abs(weights)) / maximum_code)
        codes = np.rint(weights / scale).clip(
            -maximum_code, maximum_code
        ).astype(np.int16)
        represented = codes.astype(np.float32) * scale
    else:
        raise ValueError(mode)
    difference = weights - represented
    error_norms = np.linalg.norm(difference, axis=1)

    approximate_matches = []
    group_ranks = []
    candidate_counts = []
    candidate_group_counts = []
    candidate_group_rows = []
    best_first_tokens = []
    best_first_groups = []
    best_first_group_rows = []
    bound_widths = []
    group_sizes = np.minimum(
        GROUP_SIZE,
        VOCABULARY - np.arange(GROUPS) * GROUP_SIZE,
    )
    query_norms = np.linalg.norm(hidden, axis=1)
    for start in range(0, len(hidden), BATCH):
        stop = min(start + BATCH, len(hidden))
        values = hidden[start:stop]
        scores = values @ represented.T
        exact_scores = values @ weights.T
        bounds = query_norms[start:stop, None] * error_norms[None, :]
        lower = scores - bounds
        upper = scores + bounds
        best_lower = lower.max(axis=1)
        candidates = upper >= best_lower[:, None] - 1e-6
        winner_ids = dense_winners[start:stop]
        if not np.all(candidates[np.arange(len(values)), winner_ids]):
            raise RuntimeError(f"rigorous candidate set lost a winner: {mode} {bits}")
        approximate_matches.extend((scores.argmax(axis=1) == winner_ids).tolist())
        candidate_counts.extend(candidates.sum(axis=1).tolist())
        bound_widths.extend((2 * bounds.max(axis=1)).tolist())

        padded_scores = np.full(
            (len(values), GROUPS * GROUP_SIZE), -np.inf, dtype=np.float32
        )
        padded_scores[:, :VOCABULARY] = scores
        grouped_scores = padded_scores.reshape(len(values), GROUPS, GROUP_SIZE).max(axis=2)
        winner_groups = winner_ids // GROUP_SIZE
        winner_group_scores = grouped_scores[np.arange(len(values)), winner_groups]
        group_ranks.extend(
            (1 + np.sum(grouped_scores > winner_group_scores[:, None], axis=1)).tolist()
        )

        padded_candidates = np.zeros(
            (len(values), GROUPS * GROUP_SIZE), dtype=bool
        )
        padded_candidates[:, :VOCABULARY] = candidates
        active_groups = padded_candidates.reshape(
            len(values), GROUPS, GROUP_SIZE
        ).any(axis=2)
        candidate_group_counts.extend(active_groups.sum(axis=1).tolist())
        candidate_group_rows.extend((active_groups @ group_sizes).tolist())

        token_stops, _ = stopping_counts(upper, exact_scores)
        best_first_tokens.extend(token_stops.tolist())
        padded_upper = np.full(
            (len(values), GROUPS * GROUP_SIZE), -np.inf, dtype=np.float32
        )
        padded_upper[:, :VOCABULARY] = upper
        grouped_upper = padded_upper.reshape(
            len(values), GROUPS, GROUP_SIZE
        ).max(axis=2)
        padded_exact = np.full_like(padded_upper, -np.inf)
        padded_exact[:, :VOCABULARY] = exact_scores
        grouped_exact = padded_exact.reshape(
            len(values), GROUPS, GROUP_SIZE
        ).max(axis=2)
        group_stops, group_order = stopping_counts(grouped_upper, grouped_exact)
        ordered_sizes = group_sizes[group_order]
        cumulative_rows = np.cumsum(ordered_sizes, axis=1)
        rows = cumulative_rows[np.arange(len(values)), group_stops - 1]
        best_first_groups.extend(group_stops.tolist())
        best_first_group_rows.extend(rows.tolist())

    approximate_matches_array = np.asarray(approximate_matches, dtype=bool)
    group_ranks_array = np.asarray(group_ranks, dtype=np.int64)
    candidate_counts_array = np.asarray(candidate_counts, dtype=np.int64)
    candidate_groups_array = np.asarray(candidate_group_counts, dtype=np.int64)
    candidate_rows_array = np.asarray(candidate_group_rows, dtype=np.int64)
    best_first_tokens_array = np.asarray(best_first_tokens, dtype=np.int64)
    best_first_groups_array = np.asarray(best_first_groups, dtype=np.int64)
    best_first_group_rows_array = np.asarray(best_first_group_rows, dtype=np.int64)
    return {
        "bits": bits,
        "mode": mode,
        "weightRmse": float(np.sqrt(np.mean(difference * difference))),
        "maximumRowErrorNorm": float(error_norms.max()),
        "approximateWinnerMatches": int(approximate_matches_array.sum()),
        "approximateWinnerFraction": float(approximate_matches_array.mean()),
        "winnerGroupTopK": {
            str(count): int(np.sum(group_ranks_array <= count))
            for count in (1, 2, 4, 8, 16, 32, 64, 128)
        },
        "certifiedSingleWinner": int(np.sum(candidate_counts_array == 1)),
        "certifiedSingleWinnerFraction": float(np.mean(candidate_counts_array == 1)),
        "candidateTokens": summarize(candidate_counts_array),
        "candidateGroups": summarize(candidate_groups_array),
        "rowsAfterGroupActivation": summarize(candidate_rows_array),
        "denseReductionAfterGroupActivation": float(
            VOCABULARY / candidate_rows_array.mean()
        ),
        "bestFirstExactTokens": summarize(best_first_tokens_array),
        "bestFirstExactGroups": summarize(best_first_groups_array),
        "bestFirstExactGroupRows": summarize(best_first_group_rows_array),
        "bestFirstGroupDenseReduction": float(
            VOCABULARY / best_first_group_rows_array.mean()
        ),
        "maximumPerStateBoundWidth": summarize(np.asarray(bound_widths)),
    }


def main() -> None:
    if not STATES.exists():
        raise RuntimeError("run make analyze-gpt2-supervised-group-router first")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    saved = np.load(STATES)
    hidden = saved["hidden"].astype(np.float32)
    dense_winners = saved["dense_winners"].astype(np.int64)
    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(tensors.tensor("wte.weight")[:VOCABULARY], dtype=np.float32)
    result = {
        "model": "openai-community/gpt2",
        "samples": len(hidden),
        "queryNorm": summarize(np.linalg.norm(hidden, axis=1)),
        "encodings": [],
    }
    for mode in ("global", "row-wise"):
        for bits in BITS:
            print(f"evaluating {mode} int{bits}", flush=True)
            result["encodings"].append(
                evaluate(hidden, dense_winners, weights, bits, mode)
            )
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "samples": len(hidden),
        "encodings": [
            {
                "mode": row["mode"],
                "bits": row["bits"],
                "winnerFraction": row["approximateWinnerFraction"],
                "certifiedFraction": row["certifiedSingleWinnerFraction"],
                "candidateTokensMedian": row["candidateTokens"]["median"],
                "candidateGroupsMedian": row["candidateGroups"]["median"],
                "rowsAfterGroupsMean": row["rowsAfterGroupActivation"]["mean"],
                "denseReduction": row["denseReductionAfterGroupActivation"],
                "bestFirstGroupsMedian": row["bestFirstExactGroups"]["median"],
                "bestFirstGroupRowsMean": row["bestFirstExactGroupRows"]["mean"],
                "bestFirstGroupReduction": row["bestFirstGroupDenseReduction"],
            }
            for row in result["encodings"]
        ],
        "results": str((OUTPUT / "results.json").relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
