#!/usr/bin/env python3
"""Evaluate certified group-level blockwise-Cauchy GPT-2 head bounds."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
PRIOR = ROOT / "experiments" / "gpt2-blockwise-cauchy-head" / "offline-results.json"
OUTPUT = ROOT / "experiments" / "gpt2-groupwise-cauchy-head"
VOCABULARY = 50_257
WIDTH = 768
GROUP_SIZE = 256
GROUPS = (VOCABULARY + GROUP_SIZE - 1) // GROUP_SIZE
BLOCK_COUNTS = (1, 3, 6, 12, 24, 48, 96)
BATCH = 32


def upward(values: np.ndarray) -> np.ndarray:
    return np.nextafter(np.asarray(values, dtype=np.float64), np.inf)


def downward(values: np.ndarray) -> np.ndarray:
    return np.nextafter(np.asarray(values, dtype=np.float64), -np.inf)


def gamma(operations: int) -> float:
    epsilon = np.finfo(np.float64).eps
    return operations * epsilon / (1.0 - operations * epsilon)


def upper_block_norms(values: np.ndarray, block_width: int) -> np.ndarray:
    """Upper-bound row block norms, including float64 product/sum error."""
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


def pad_groups(values: np.ndarray, fill: float) -> np.ndarray:
    padding = GROUPS * GROUP_SIZE - VOCABULARY
    return np.pad(values, ((0, 0), (0, padding)), constant_values=fill).reshape(
        len(values), GROUPS, GROUP_SIZE
    )


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
    row_residual_norms = upper_block_norms(residual, block_width)
    padded_residual_norms = np.pad(
        row_residual_norms,
        ((0, GROUPS * GROUP_SIZE - VOCABULARY), (0, 0)),
        constant_values=0.0,
    ).reshape(GROUPS, GROUP_SIZE, block_count)
    # The group coefficient is rounded up after taking the row maximum.
    group_residual_norms = upward(np.max(padded_residual_norms, axis=1))
    query_block_norms = upper_block_norms(hidden, block_width)

    exact_group_counts: list[int] = []
    exact_group_rows: list[int] = []
    candidate_group_counts: list[int] = []
    retained: list[bool] = []
    group_sizes = np.minimum(
        GROUP_SIZE,
        VOCABULARY - np.arange(GROUPS) * GROUP_SIZE,
    ).astype(np.int64)
    dot_gamma = gamma(WIDTH)
    radius_gamma = gamma(2 * block_count)

    for start in range(0, len(hidden), BATCH):
        stop = min(start + BATCH, len(hidden))
        query = hidden[start:stop]
        approximate = query @ represented.T
        exact = query @ weights.T
        approximate_roundoff = dot_gamma * (np.abs(query) @ np.abs(represented).T)
        exact_roundoff = dot_gamma * (np.abs(query) @ np.abs(weights).T)

        # Certified group coarse term: max_i h.q_i, with each computed dot
        # widened upward before taking the maximum.
        represented_upper = upward(approximate + approximate_roundoff)
        group_represented_upper = np.max(
            pad_groups(represented_upper, -np.inf), axis=2
        )
        radius_sum = query_block_norms[start:stop] @ group_residual_norms.T
        group_radius = upward(radius_sum / (1.0 - radius_gamma))
        group_upper = upward(group_represented_upper + group_radius)

        exact_lower = downward(exact - exact_roundoff)
        group_exact_lower = np.max(pad_groups(exact_lower, -np.inf), axis=2)
        best_lower = np.max(group_exact_lower, axis=1)
        candidate_group_counts.extend(
            np.sum(group_upper >= best_lower[:, None], axis=1).astype(int).tolist()
        )

        exact_winners = np.argmax(exact, axis=1)
        winner_groups = exact_winners // GROUP_SIZE
        retained.extend((
            group_upper[np.arange(len(query)), winner_groups] >= best_lower
        ).tolist())

        order = np.argsort(-group_upper, axis=1, kind="stable")
        ordered_upper = np.take_along_axis(group_upper, order, axis=1)
        ordered_exact_lower = np.take_along_axis(group_exact_lower, order, axis=1)
        incumbent = np.maximum.accumulate(ordered_exact_lower, axis=1)
        done = incumbent[:, :-1] >= ordered_upper[:, 1:]
        has_done = np.any(done, axis=1)
        counts = np.where(has_done, np.argmax(done, axis=1) + 1, GROUPS).astype(np.int64)
        exact_group_counts.extend(counts.tolist())
        cumulative_rows = np.cumsum(group_sizes[order], axis=1)
        exact_group_rows.extend(
            cumulative_rows[np.arange(len(query)), counts - 1].tolist()
        )

    return {
        "blockCount": block_count,
        "blockWidth": block_width,
        "candidateGroups": np.asarray(candidate_group_counts, dtype=np.int64),
        "bestFirstExactGroups": np.asarray(exact_group_counts, dtype=np.int64),
        "bestFirstExactRows": np.asarray(exact_group_rows, dtype=np.int64),
        "winnerRetained": np.asarray(retained, dtype=bool),
        "groupResidualNorms": group_residual_norms,
    }


def prior_configuration(prior: dict[str, object], block_count: int) -> dict[str, object]:
    return next(
        row for row in prior["configurations"] if row["blockCount"] == block_count
    )


def main() -> None:
    if not STATES.exists() or not PRIOR.exists():
        raise RuntimeError("missing saved-state corpus or prior blockwise results")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    saved = np.load(STATES)
    prior = json.loads(PRIOR.read_text())
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
    chosen_group_norms: np.ndarray | None = None
    for block_count in BLOCK_COUNTS:
        print(f"evaluating {block_count} groupwise Cauchy blocks", flush=True)
        measured = evaluate(hidden, weights, represented, residual, block_count)
        retained = np.asarray(measured.pop("winnerRetained"), dtype=bool)
        group_norms = np.asarray(measured.pop("groupResidualNorms"), dtype=np.float64)
        if not np.all(retained):
            raise RuntimeError(f"{block_count}-block group bound lost an exact winner")
        if block_count == 96:
            chosen_group_norms = group_norms
        configurations.append({
            "blockCount": measured["blockCount"],
            "blockWidth": measured["blockWidth"],
            "winnerRetained": int(np.sum(retained)),
            "candidateGroups": split_distribution(
                np.asarray(measured["candidateGroups"]), saved
            ),
            "bestFirstExactGroups": split_distribution(
                np.asarray(measured["bestFirstExactGroups"]), saved
            ),
            "bestFirstExactRows": split_distribution(
                np.asarray(measured["bestFirstExactRows"]), saved
            ),
        })
    if chosen_group_norms is None:
        raise RuntimeError("96-block group norms were not produced")

    global_prior = prior_configuration(prior, 1)
    rowwise_prior = prior_configuration(prior, 96)
    chosen = next(row for row in configurations if row["blockCount"] == 96)
    plausible = (
        chosen["bestFirstExactGroups"]["validation"]["mean"]
        < global_prior["bestFirstExactGroups"]["validation"]["mean"]
        and chosen["bestFirstExactGroups"]["test"]["mean"]
        < global_prior["bestFirstExactGroups"]["test"]["mean"]
        and chosen["bestFirstExactRows"]["test"]["maximum"] <= 4096
    )
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
        "groupSize": GROUP_SIZE,
        "groups": GROUPS,
        "coarseEncoding": "row-wise symmetric signed int10",
        "certificate": (
            "max_i h.w_i <= max_i h.q_i + sum_b l2(h_b)*max_i l2((w_i-q_i)_b); "
            "stored norms and floating interval endpoints rounded outward"
        ),
        "freshOracleMatchesSaved": int(np.sum(oracle == saved_winners)),
        "configurations": configurations,
        "comparison": {
            "globalPerRow1Block": {
                "bestFirstExactGroups": global_prior["bestFirstExactGroups"],
                "bestFirstExactRows": global_prior["bestFirstExactRows"],
            },
            "perRow96Block": {
                "bestFirstExactGroups": rowwise_prior["bestFirstExactGroups"],
                "bestFirstExactRows": rowwise_prior["bestFirstExactRows"],
            },
            "groupwise96Block": {
                "bestFirstExactGroups": chosen["bestFirstExactGroups"],
                "bestFirstExactRows": chosen["bestFirstExactRows"],
            },
        },
        "browserGate": {
            "plausible": bool(plausible),
            "criteria": (
                "96-block groupwise validation/test mean exact groups beat the global "
                "per-row bound and test maximum exact rows is at most 4096"
            ),
        },
    }
    (OUTPUT / "offline-results.json").write_text(json.dumps(result, indent=2) + "\n")
    # The browser builder consumes this exact outward-rounded matrix rather
    # than recomputing it with a potentially different reduction path.
    np.save(OUTPUT / "group-residual-norms-96.npy", chosen_group_norms)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
