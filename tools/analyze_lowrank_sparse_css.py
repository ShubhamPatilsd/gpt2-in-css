#!/usr/bin/env python3
"""Measure low-rank and sparse direct-CSS approximations of GPT-2 block 0.

This is an offline analysis/build tool.  The proposed runtime remains HTML/CSS:
each retained multiply would become one native CSS calc() term.  We evaluate the
actual GPT-2-small weights and real token/position embeddings before generating
any enormous stylesheet.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "lowrank-sparse-css"
WIDTH = 768
EPSILON = 1e-5
RANKS = (32, 64, 128, 256, 384)
SPARSITIES = (0.50, 0.75, 0.90)
HYBRID_CONFIGURATIONS = (
    (32, 0.90),
    (64, 0.90),
    (128, 0.90),
    (64, 0.95),
    (128, 0.95),
    (128, 0.975),
)
TOKEN_IDS = (
    0,      # !
    11,     # ,
    13,     # .
    40,     # I
    198,    # newline
    220,    # space
    257,    # " a"
    262,    # " the"
    286,    # " of"
    318,    # " is"
    373,    # " was"
    464,    # "The"
    612,    # " there"
    995,    # " world"
    15496,  # "Hello"
    30000,  # uncommon vocabulary region
    40000,  # uncommon vocabulary region
    50256,  # end-of-text
)


@dataclass(frozen=True)
class Matrix:
    name: str
    weight: np.ndarray  # output x input
    bias: np.ndarray


@dataclass(frozen=True)
class Factors:
    left: np.ndarray   # output x max_rank
    right: np.ndarray  # max_rank x input
    singular_values: np.ndarray


def layer_norm(x: np.ndarray, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
    mean = np.mean(x, axis=-1, keepdims=True)
    variance = np.mean((x - mean) ** 2, axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(variance + EPSILON) * gamma + beta


def gelu_new(x: np.ndarray) -> np.ndarray:
    inner = math.sqrt(2 / math.pi) * (x + 0.044715 * x**3)
    return 0.5 * x * (1 + np.tanh(inner))


def load_data() -> tuple[np.ndarray, dict[str, np.ndarray], list[Matrix]]:
    tensors = SafeTensors(MODEL_PATH)
    prefix = "h.0"
    embeddings = np.asarray(tensors.tensor("wte.weight")[list(TOKEN_IDS)], dtype=np.float64)
    embeddings += np.asarray(tensors.tensor("wpe.weight")[0], dtype=np.float64)
    qkv_weight = np.asarray(tensors.tensor(f"{prefix}.attn.c_attn.weight"), dtype=np.float64)
    qkv_bias = np.asarray(tensors.tensor(f"{prefix}.attn.c_attn.bias"), dtype=np.float64)
    constants = {
        "ln1_gamma": np.asarray(tensors.tensor(f"{prefix}.ln_1.weight"), dtype=np.float64),
        "ln1_beta": np.asarray(tensors.tensor(f"{prefix}.ln_1.bias"), dtype=np.float64),
        "ln2_gamma": np.asarray(tensors.tensor(f"{prefix}.ln_2.weight"), dtype=np.float64),
        "ln2_beta": np.asarray(tensors.tensor(f"{prefix}.ln_2.bias"), dtype=np.float64),
    }
    matrices = [
        Matrix("value", qkv_weight[:, 2 * WIDTH :].T, qkv_bias[2 * WIDTH :]),
        Matrix(
            "attention_projection",
            np.asarray(tensors.tensor(f"{prefix}.attn.c_proj.weight"), dtype=np.float64).T,
            np.asarray(tensors.tensor(f"{prefix}.attn.c_proj.bias"), dtype=np.float64),
        ),
        Matrix(
            "feed_forward_expansion",
            np.asarray(tensors.tensor(f"{prefix}.mlp.c_fc.weight"), dtype=np.float64).T,
            np.asarray(tensors.tensor(f"{prefix}.mlp.c_fc.bias"), dtype=np.float64),
        ),
        Matrix(
            "feed_forward_projection",
            np.asarray(tensors.tensor(f"{prefix}.mlp.c_proj.weight"), dtype=np.float64).T,
            np.asarray(tensors.tensor(f"{prefix}.mlp.c_proj.bias"), dtype=np.float64),
        ),
    ]
    return embeddings, constants, matrices


def factorize(weight: np.ndarray, max_rank: int) -> Factors:
    """Compute a truncated SVD through the smaller 768x768 Gram matrix."""
    outputs, inputs = weight.shape
    if outputs >= inputs:
        gram = weight.T @ weight
        values, vectors = np.linalg.eigh(gram)
        order = np.argsort(values)[::-1][:max_rank]
        right_t = vectors[:, order]
        left = weight @ right_t
        right = right_t.T
    else:
        gram = weight @ weight.T
        values, vectors = np.linalg.eigh(gram)
        order = np.argsort(values)[::-1][:max_rank]
        left = vectors[:, order]
        right = left.T @ weight
    singular = np.sqrt(np.maximum(values[order], 0))
    return Factors(left=left, right=right, singular_values=singular)


def rowwise_sparse(weight: np.ndarray, sparsity: float) -> np.ndarray:
    """Keep the same largest-magnitude fraction in every output row."""
    inputs = weight.shape[1]
    keep = max(1, int(round(inputs * (1 - sparsity))))
    indices = np.argpartition(np.abs(weight), inputs - keep, axis=1)[:, -keep:]
    sparse = np.zeros_like(weight)
    rows = np.arange(weight.shape[0])[:, None]
    sparse[rows, indices] = weight[rows, indices]
    return sparse


def apply_dense(matrix: Matrix, x: np.ndarray) -> np.ndarray:
    return x @ matrix.weight.T + matrix.bias


def apply_factors(matrix: Matrix, factors: Factors, rank: int, x: np.ndarray) -> np.ndarray:
    return (x @ factors.right[:rank].T) @ factors.left[:, :rank].T + matrix.bias


def apply_sparse(matrix: Matrix, sparse: np.ndarray, x: np.ndarray) -> np.ndarray:
    return x @ sparse.T + matrix.bias


def forward(
    x: np.ndarray,
    constants: dict[str, np.ndarray],
    matrices: list[Matrix],
    apply,
) -> np.ndarray:
    n1 = layer_norm(x, constants["ln1_gamma"], constants["ln1_beta"])
    value = apply(matrices[0], n1)
    residual = x + apply(matrices[1], value)
    n2 = layer_norm(residual, constants["ln2_gamma"], constants["ln2_beta"])
    hidden = gelu_new(apply(matrices[2], n2))
    return residual + apply(matrices[3], hidden)


def metrics(actual: np.ndarray, expected: np.ndarray) -> dict[str, float]:
    difference = actual - expected
    actual_norms = np.linalg.norm(actual, axis=1)
    expected_norms = np.linalg.norm(expected, axis=1)
    cosine = np.sum(actual * expected, axis=1) / (actual_norms * expected_norms)
    per_token_rmse = np.sqrt(np.mean(difference**2, axis=1))
    rmse = float(np.sqrt(np.mean(difference**2)))
    expected_rms = float(np.sqrt(np.mean(expected**2)))
    return {
        "rmse": rmse,
        "relative_rmse": rmse / expected_rms,
        "mae": float(np.mean(np.abs(difference))),
        "max_absolute_error": float(np.max(np.abs(difference))),
        "mean_cosine": float(np.mean(cosine)),
        "worst_cosine": float(np.min(cosine)),
        "worst_token_rmse": float(np.max(per_token_rmse)),
        "worst_token_id": int(TOKEN_IDS[int(np.argmax(per_token_rmse))]),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    inputs, constants, matrices = load_data()
    exact = forward(inputs, constants, matrices, apply_dense)
    dense_terms = int(sum(matrix.weight.size for matrix in matrices))

    factors: dict[str, Factors] = {}
    factorization_seconds: dict[str, float] = {}
    matrix_stats: dict[str, dict[str, object]] = {}
    for matrix in matrices:
        matrix_started = time.perf_counter()
        factors[matrix.name] = factorize(matrix.weight, max(RANKS))
        factorization_seconds[matrix.name] = time.perf_counter() - matrix_started
        total_energy = float(np.sum(matrix.weight**2))
        singular = factors[matrix.name].singular_values
        matrix_stats[matrix.name] = {
            "shape": list(matrix.weight.shape),
            "dense_terms": int(matrix.weight.size),
            "top_rank_energy_fraction": {
                str(rank): float(np.sum(singular[:rank] ** 2) / total_energy)
                for rank in RANKS
            },
        }

    low_rank_results = []
    for rank in RANKS:
        approximated = forward(
            inputs,
            constants,
            matrices,
            lambda matrix, x, rank=rank: apply_factors(
                matrix, factors[matrix.name], rank, x
            ),
        )
        terms = int(
            sum(rank * (matrix.weight.shape[0] + matrix.weight.shape[1]) for matrix in matrices)
        )
        low_rank_results.append(
            {
                "rank": rank,
                "terms": terms,
                "term_fraction": terms / dense_terms,
                "compression": dense_terms / terms,
                "intermediate_css_numbers": rank * len(matrices),
                **metrics(approximated, exact),
            }
        )

    sparse_results = []
    sparse_matrix_stats: dict[str, dict[str, object]] = {matrix.name: {} for matrix in matrices}
    for sparsity in SPARSITIES:
        sparse_weights = {
            matrix.name: rowwise_sparse(matrix.weight, sparsity) for matrix in matrices
        }
        approximated = forward(
            inputs,
            constants,
            matrices,
            lambda matrix, x, sparse_weights=sparse_weights: apply_sparse(
                matrix, sparse_weights[matrix.name], x
            ),
        )
        terms = int(sum(np.count_nonzero(weight) for weight in sparse_weights.values()))
        sparse_results.append(
            {
                "sparsity": sparsity,
                "terms": terms,
                "term_fraction": terms / dense_terms,
                "compression": dense_terms / terms,
                **metrics(approximated, exact),
            }
        )
        for matrix in matrices:
            sparse = sparse_weights[matrix.name]
            residual = matrix.weight - sparse
            sparse_matrix_stats[matrix.name][str(sparsity)] = {
                "terms": int(np.count_nonzero(sparse)),
                "retained_weight_energy_fraction": float(
                    np.sum(sparse**2) / np.sum(matrix.weight**2)
                ),
                "weight_rmse": float(np.sqrt(np.mean(residual**2))),
            }

    hybrid_results = []
    for rank, residual_sparsity in HYBRID_CONFIGURATIONS:
        residuals = {}
        for matrix in matrices:
            low_rank = (
                factors[matrix.name].left[:, :rank]
                @ factors[matrix.name].right[:rank]
            )
            residuals[matrix.name] = rowwise_sparse(
                matrix.weight - low_rank, residual_sparsity
            )

        def apply_hybrid(matrix: Matrix, x: np.ndarray) -> np.ndarray:
            factor = factors[matrix.name]
            low_rank_output = (
                x @ factor.right[:rank].T
            ) @ factor.left[:, :rank].T
            return low_rank_output + x @ residuals[matrix.name].T + matrix.bias

        approximated = forward(inputs, constants, matrices, apply_hybrid)
        rank_terms = int(
            sum(rank * (matrix.weight.shape[0] + matrix.weight.shape[1]) for matrix in matrices)
        )
        residual_terms = int(sum(np.count_nonzero(weight) for weight in residuals.values()))
        terms = rank_terms + residual_terms
        hybrid_results.append(
            {
                "rank": rank,
                "residual_sparsity": residual_sparsity,
                "rank_terms": rank_terms,
                "residual_terms": residual_terms,
                "terms": terms,
                "term_fraction": terms / dense_terms,
                "compression": dense_terms / terms,
                "intermediate_css_numbers": rank * len(matrices),
                **metrics(approximated, exact),
            }
        )

    report = {
        "checkpoint": "openai-community/gpt2",
        "block": 0,
        "sequence_length": 1,
        "token_ids": list(TOKEN_IDS),
        "sample_count": len(TOKEN_IDS),
        "dense_terms": dense_terms,
        "exact_output": {
            "rms": float(np.sqrt(np.mean(exact**2))),
            "mean_absolute": float(np.mean(np.abs(exact))),
            "max_absolute": float(np.max(np.abs(exact))),
        },
        "matrix_stats": matrix_stats,
        "low_rank": low_rank_results,
        "rowwise_magnitude_sparsity": sparse_results,
        "low_rank_plus_sparse_residual": hybrid_results,
        "sparse_matrix_stats": sparse_matrix_stats,
        "factorization_seconds": factorization_seconds,
        "analysis_seconds": time.perf_counter() - started,
        "notes": [
            "Term counts cover only the four dense matrix multiplies in one one-token block.",
            "Bias, LayerNorm, GELU, and residual arithmetic are exact float64 in every variant.",
            "A rank-r direct-CSS matrix needs r*(inputs+outputs) multiply terms and r reusable intermediate CSS numbers.",
            "Sparsity is enforced independently per output row so every output retains equal fan-in.",
        ],
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    # The existing exact direct-CSS block uses 5,252,351 terms, a 94,323,192
    # byte stylesheet, and 2.48--2.66 seconds per same-page mutation.  Scale
    # those empirical values by arithmetic term count as a deliberately rough
    # lower-bound estimate; low-rank variants also add stage boundaries.
    baseline_terms = 5_252_351
    baseline_bytes = 94_323_192
    baseline_median_ms = 2_570
    estimates = []
    for family, variants in (
        ("low_rank", low_rank_results),
        ("magnitude_sparse", sparse_results),
        ("low_rank_plus_sparse_residual", hybrid_results),
    ):
        for variant in variants:
            estimates.append(
                {
                    "family": family,
                    "rank": variant.get("rank"),
                    "sparsity": variant.get("sparsity"),
                    "residual_sparsity": variant.get("residual_sparsity"),
                    "terms": variant["terms"],
                    "estimated_raw_css_bytes": round(
                        baseline_bytes * variant["terms"] / baseline_terms
                    ),
                    "estimated_same_page_recompute_ms": round(
                        baseline_median_ms * variant["terms"] / baseline_terms
                    ),
                    "warning": "Linear extrapolation only; low-rank introduces extra dependency stages.",
                }
            )
    browser_estimate = {
        "empirical_baseline": {
            "source": "experiments/matrix-scaling/RESULTS.md",
            "terms": baseline_terms,
            "raw_css_bytes": baseline_bytes,
            "same_page_recompute_ms_range": [2480, 2660],
        },
        "estimates": estimates,
    }
    (OUT / "browser-estimate.json").write_text(
        json.dumps(browser_estimate, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
