#!/usr/bin/env python3
"""Screen rigorous blockwise-Cauchy bounds for the unchanged GPT-2 head."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
OUTPUT = ROOT / "experiments" / "gpt2-blockwise-cauchy-head"
VOCABULARY = 50_257
WIDTH = 768
GROUP_SIZE = 256
GROUPS = (VOCABULARY + GROUP_SIZE - 1) // GROUP_SIZE
BLOCK_COUNTS = (1, 3, 6, 12, 24, 48, 96)
BATCH = 32


def upward(values: np.ndarray) -> np.ndarray:
    """Round non-negative floating values toward positive infinity."""
    return np.nextafter(np.asarray(values, dtype=np.float64), np.inf)


def gamma(operations: int) -> float:
    epsilon = np.finfo(np.float64).eps
    return operations * epsilon / (1.0 - operations * epsilon)


def upper_block_norms(values: np.ndarray, block_width: int) -> np.ndarray:
    """Upper-bound L2 norms including product, sum, and sqrt roundoff."""
    blocks = []
    for start in range(0, WIDTH, block_width):
        block = values[:, start:start + block_width]
        squared_sum = np.sum(block * block, axis=1, dtype=np.float64)
        upper_squared_sum = upward(squared_sum / (1.0 - gamma(2 * block_width)))
        blocks.append(upward(np.sqrt(upper_squared_sum)))
    return np.stack(blocks, axis=1)


def distribution(values: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(values)
    return {
        "mean": float(np.mean(values)),
        "minimum": int(np.min(values)),
        "median": int(np.median(values)),
        "p95": int(np.percentile(values, 95, method="higher")),
        "maximum": int(np.max(values)),
    }


def split_distribution(values: np.ndarray, saved: np.lib.npyio.NpzFile) -> dict[str, object]:
    return {
        name: distribution(values[np.asarray(saved[f"{name}_ids"], dtype=np.int64)])
        for name in ("train", "validation", "test")
    }


def evaluate(
    hidden: np.ndarray,
    weights: np.ndarray,
    represented: np.ndarray,
    residual: np.ndarray,
    block_count: int,
) -> dict[str, np.ndarray | int]:
    if WIDTH % block_count:
        raise ValueError(f"{block_count} does not divide {WIDTH}")
    block_width = WIDTH // block_count
    row_block_norms = upper_block_norms(residual, block_width)
    query_block_norms = upper_block_norms(hidden, block_width)

    candidate_counts: list[int] = []
    exact_group_counts: list[int] = []
    exact_group_rows: list[int] = []
    retained: list[bool] = []
    group_sizes = np.minimum(
        GROUP_SIZE,
        VOCABULARY - np.arange(GROUPS) * GROUP_SIZE,
    ).astype(np.int64)

    # The dot-product roundoff allowance is the standard gamma_n bound for a
    # float64 multiply/add sequence. It is tiny here, but makes the generated
    # interval outward-safe rather than relying on BLAS's last bit.
    dot_gamma = gamma(WIDTH)
    radius_gamma = gamma(2 * block_count)
    for start in range(0, len(hidden), BATCH):
        stop = min(start + BATCH, len(hidden))
        query = hidden[start:stop]
        approximate = query @ represented.T
        exact = query @ weights.T
        approximate_roundoff = dot_gamma * (np.abs(query) @ np.abs(represented).T)
        exact_roundoff = dot_gamma * (np.abs(query) @ np.abs(weights).T)
        radius_sum = query_block_norms[start:stop] @ row_block_norms.T
        radius = upward(radius_sum / (1.0 - radius_gamma))
        upper = np.nextafter(approximate + approximate_roundoff + radius, np.inf)
        lower = np.nextafter(approximate - approximate_roundoff - radius, -np.inf)
        best_lower = np.max(lower, axis=1)
        candidate_counts.extend(np.sum(
            upper >= best_lower[:, None], axis=1
        ).astype(int).tolist())

        exact_winners = np.argmax(exact, axis=1)
        retained.extend((
            upper[np.arange(len(query)), exact_winners]
            >= best_lower
        ).tolist())

        padded_upper = np.pad(
            upper,
            ((0, 0), (0, GROUPS * GROUP_SIZE - VOCABULARY)),
            constant_values=-np.inf,
        ).reshape(len(query), GROUPS, GROUP_SIZE).max(axis=2)
        padded_exact_lower = np.pad(
            np.nextafter(exact - exact_roundoff, -np.inf),
            ((0, 0), (0, GROUPS * GROUP_SIZE - VOCABULARY)),
            constant_values=-np.inf,
        ).reshape(len(query), GROUPS, GROUP_SIZE).max(axis=2)
        order = np.argsort(-padded_upper, axis=1, kind="stable")
        ordered_upper = np.take_along_axis(padded_upper, order, axis=1)
        ordered_exact_lower = np.take_along_axis(
            padded_exact_lower, order, axis=1
        )
        incumbent = np.maximum.accumulate(ordered_exact_lower, axis=1)
        done = incumbent[:, :-1] >= ordered_upper[:, 1:]
        has_done = np.any(done, axis=1)
        counts = np.where(
            has_done,
            np.argmax(done, axis=1) + 1,
            GROUPS,
        ).astype(np.int64)
        exact_group_counts.extend(counts.tolist())
        cumulative_rows = np.cumsum(group_sizes[order], axis=1)
        exact_group_rows.extend(
            cumulative_rows[np.arange(len(query)), counts - 1].tolist()
        )

    return {
        "blockCount": block_count,
        "blockWidth": block_width,
        "candidateTokens": np.asarray(candidate_counts, dtype=np.int64),
        "bestFirstExactGroups": np.asarray(exact_group_counts, dtype=np.int64),
        "bestFirstExactRows": np.asarray(exact_group_rows, dtype=np.int64),
        "winnerRetained": np.asarray(retained, dtype=bool),
    }


def main() -> None:
    if not STATES.exists():
        raise RuntimeError("missing the existing 1,024-state GPT-2 corpus")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    saved = np.load(STATES)
    hidden = np.asarray(saved["hidden"], dtype=np.float64)
    weights = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wte.weight")[:VOCABULARY],
        dtype=np.float64,
    )
    row_scales = np.max(np.abs(weights), axis=1) / 511.0
    row_scales[row_scales == 0] = 1.0
    codes = np.rint(weights / row_scales[:, None]).clip(-511, 511).astype(np.int16)
    represented = codes.astype(np.float64) * row_scales[:, None]
    residual = weights - represented

    oracle = np.empty(len(hidden), dtype=np.int64)
    for start in range(0, len(hidden), BATCH):
        stop = min(start + BATCH, len(hidden))
        oracle[start:stop] = np.argmax(hidden[start:stop] @ weights.T, axis=1)
    saved_winners = np.asarray(saved["dense_winners"], dtype=np.int64)
    if not np.array_equal(oracle, saved_winners):
        raise RuntimeError("fresh float64 head does not reproduce saved winners")

    configurations: list[dict[str, object]] = []
    for block_count in BLOCK_COUNTS:
        print(f"evaluating {block_count} Cauchy blocks", flush=True)
        measured = evaluate(hidden, weights, represented, residual, block_count)
        retained = np.asarray(measured.pop("winnerRetained"), dtype=bool)
        if not np.all(retained):
            raise RuntimeError(f"{block_count}-block bound lost an exact winner")
        row = {
            "blockCount": measured["blockCount"],
            "blockWidth": measured["blockWidth"],
            "winnerRetained": int(np.sum(retained)),
            "candidateTokens": split_distribution(
                np.asarray(measured["candidateTokens"]), saved
            ),
            "bestFirstExactGroups": split_distribution(
                np.asarray(measured["bestFirstExactGroups"]), saved
            ),
            "bestFirstExactRows": split_distribution(
                np.asarray(measured["bestFirstExactRows"]), saved
            ),
        }
        configurations.append(row)

    result = {
        "model": "openai-community/gpt2",
        "architectureAndWeightsChanged": False,
        "target": "original float GPT-2 tied output rows",
        "samples": len(hidden),
        "splits": {
            name: int(len(saved[f"{name}_ids"]))
            for name in ("train", "validation", "test")
        },
        "vocabulary": VOCABULARY,
        "width": WIDTH,
        "coarseEncoding": "row-wise symmetric signed int10",
        "certificate": (
            "h.w <= h.wq + sum_b l2(h_b)*l2((w-wq)_b); "
            "stored norms and floating interval endpoints rounded outward"
        ),
        "freshOracleMatchesSaved": int(np.sum(oracle == saved_winners)),
        "configurations": configurations,
    }
    (OUTPUT / "offline-results.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
