#!/usr/bin/env python3
"""Test structured post-training representations for CSS GPT-2 matvecs.

Runtime-oriented counts assume HTML/CSS can cache an intermediate custom
property and reuse it.  JavaScript is not part of any proposed runtime.
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
OUT = ROOT / "experiments" / "structured-css-matrices"
WIDTH = 768
EPSILON = 1e-5
TOKEN_IDS = (0, 11, 13, 40, 198, 220, 257, 262, 286, 318, 373, 464,
             612, 995, 15496, 30000, 40000, 50256)


@dataclass(frozen=True)
class Matrix:
    name: str
    weight: np.ndarray  # output x input
    bias: np.ndarray


def layer_norm(x: np.ndarray, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
    mean = np.mean(x, axis=-1, keepdims=True)
    variance = np.mean((x - mean) ** 2, axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(variance + EPSILON) * gamma + beta


def gelu_new(x: np.ndarray) -> np.ndarray:
    inner = math.sqrt(2 / math.pi) * (x + 0.044715 * x**3)
    return 0.5 * x * (1 + np.tanh(inner))


def load_block(tensors: SafeTensors, layer: int) -> tuple[dict[str, np.ndarray], list[Matrix]]:
    prefix = f"h.{layer}"
    qkv_weight = np.asarray(tensors.tensor(f"{prefix}.attn.c_attn.weight"), dtype=np.float64)
    qkv_bias = np.asarray(tensors.tensor(f"{prefix}.attn.c_attn.bias"), dtype=np.float64)
    constants = {
        "ln1_gamma": np.asarray(tensors.tensor(f"{prefix}.ln_1.weight"), dtype=np.float64),
        "ln1_beta": np.asarray(tensors.tensor(f"{prefix}.ln_1.bias"), dtype=np.float64),
        "ln2_gamma": np.asarray(tensors.tensor(f"{prefix}.ln_2.weight"), dtype=np.float64),
        "ln2_beta": np.asarray(tensors.tensor(f"{prefix}.ln_2.bias"), dtype=np.float64),
    }
    matrices = [
        Matrix("value", qkv_weight[:, 2 * WIDTH:].T, qkv_bias[2 * WIDTH:]),
        Matrix("attention_projection",
               np.asarray(tensors.tensor(f"{prefix}.attn.c_proj.weight"), dtype=np.float64).T,
               np.asarray(tensors.tensor(f"{prefix}.attn.c_proj.bias"), dtype=np.float64)),
        Matrix("feed_forward_expansion",
               np.asarray(tensors.tensor(f"{prefix}.mlp.c_fc.weight"), dtype=np.float64).T,
               np.asarray(tensors.tensor(f"{prefix}.mlp.c_fc.bias"), dtype=np.float64)),
        Matrix("feed_forward_projection",
               np.asarray(tensors.tensor(f"{prefix}.mlp.c_proj.weight"), dtype=np.float64).T,
               np.asarray(tensors.tensor(f"{prefix}.mlp.c_proj.bias"), dtype=np.float64)),
    ]
    return constants, matrices


def forward_block(x: np.ndarray, constants: dict[str, np.ndarray], matrices: list[Matrix]) -> np.ndarray:
    n1 = layer_norm(x, constants["ln1_gamma"], constants["ln1_beta"])
    value = n1 @ matrices[0].weight.T + matrices[0].bias
    residual = x + value @ matrices[1].weight.T + matrices[1].bias
    n2 = layer_norm(residual, constants["ln2_gamma"], constants["ln2_beta"])
    hidden = gelu_new(n2 @ matrices[2].weight.T + matrices[2].bias)
    return residual + hidden @ matrices[3].weight.T + matrices[3].bias


def metrics(actual: np.ndarray, expected: np.ndarray) -> dict[str, float]:
    delta = actual - expected
    rmse = float(np.sqrt(np.mean(delta**2)))
    expected_rms = float(np.sqrt(np.mean(expected**2)))
    cosine = np.sum(actual * expected, axis=1) / (
        np.linalg.norm(actual, axis=1) * np.linalg.norm(expected, axis=1)
    )
    per_sample_rmse = np.sqrt(np.mean(delta**2, axis=1))
    return {
        "rmse": rmse,
        "relative_rmse": rmse / expected_rms,
        "max_absolute_error": float(np.max(np.abs(delta))),
        "mean_cosine": float(np.mean(cosine)),
        "worst_cosine": float(np.min(cosine)),
        "worst_token_rmse": float(np.max(per_sample_rmse)),
        "worst_token_id": int(TOKEN_IDS[int(np.argmax(per_sample_rmse))]),
    }


def truncated_svd(matrix: np.ndarray, rank: int) -> tuple[np.ndarray, np.ndarray]:
    """Return L,R with matrix ~= L@R using the smaller Gram matrix."""
    rows, columns = matrix.shape
    if rows <= columns:
        values, vectors = np.linalg.eigh(matrix @ matrix.T)
        order = np.argsort(values)[::-1][:rank]
        left = vectors[:, order]
        right = left.T @ matrix
    else:
        values, vectors = np.linalg.eigh(matrix.T @ matrix)
        order = np.argsort(values)[::-1][:rank]
        right_t = vectors[:, order]
        left = matrix @ right_t
        right = right_t.T
    return left, right


def kronecker_factors(
    weight: np.ndarray,
    out_a: int,
    out_b: int,
    in_a: int,
    in_b: int,
    rank: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    assert weight.shape == (out_a * out_b, in_a * in_b)
    rearranged = (
        weight.reshape(out_a, out_b, in_a, in_b)
        .transpose(0, 2, 1, 3)
        .reshape(out_a * in_a, out_b * in_b)
    )
    left, right = truncated_svd(rearranged, rank)
    return [
        (left[:, index].reshape(out_a, in_a), right[index].reshape(out_b, in_b))
        for index in range(rank)
    ]


def reconstruct_kronecker(factors: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
    return sum(np.kron(a, b) for a, b in factors)


def kronecker_terms(
    out_a: int, out_b: int, in_a: int, in_b: int, rank: int
) -> int:
    left_first = out_a * in_a * in_b + out_a * in_b * out_b
    right_first = in_a * in_b * out_b + out_a * in_a * out_b
    return rank * min(left_first, right_first)


def kmeans_once(data: np.ndarray, clusters: int, seed: int, iterations: int = 7) -> tuple[np.ndarray, np.ndarray, float]:
    rng = np.random.default_rng(seed)
    centers = data[rng.choice(data.shape[0], size=clusters, replace=False)].copy()
    assignments = np.zeros(data.shape[0], dtype=np.int32)
    for _ in range(iterations):
        distances = (
            np.sum(data**2, axis=1)[:, None]
            + np.sum(centers**2, axis=1)[None, :]
            - 2 * data @ centers.T
        )
        assignments = np.argmin(distances, axis=1)
        minimums = distances[np.arange(data.shape[0]), assignments]
        for cluster in range(clusters):
            members = assignments == cluster
            if np.any(members):
                centers[cluster] = np.mean(data[members], axis=0)
            else:
                replacement = int(np.argmax(minimums))
                centers[cluster] = data[replacement]
                assignments[replacement] = cluster
                minimums[replacement] = -np.inf
    error = float(np.sum((data - centers[assignments]) ** 2))
    return centers, assignments, error


def kmeans(data: np.ndarray, clusters: int, seed: int, iterations: int = 7) -> tuple[np.ndarray, np.ndarray]:
    attempts = [kmeans_once(data, clusters, seed + attempt * 65_537, iterations) for attempt in range(2)]
    centers, assignments, _error = min(attempts, key=lambda result: result[2])
    return centers, assignments


def additive_product_quantize(
    weight: np.ndarray,
    block_size: int,
    clusters: int,
    stages: int,
    seed: int,
) -> tuple[np.ndarray, dict[str, int]]:
    outputs, inputs = weight.shape
    reconstructed = np.zeros_like(weight)
    blocks = math.ceil(inputs / block_size)
    for block in range(blocks):
        start = block * block_size
        stop = min(inputs, start + block_size)
        residual = weight[:, start:stop].copy()
        for stage in range(stages):
            centers, assignments = kmeans(
                residual, clusters, seed + block * 131 + stage * 7919
            )
            selected = centers[assignments]
            reconstructed[:, start:stop] += selected
            residual -= selected
    multiply_terms = stages * clusters * inputs
    selection_terms = stages * outputs * blocks
    return reconstructed, {
        "multiply_terms": multiply_terms,
        "selection_terms": selection_terms,
        "total_terms": multiply_terms + selection_terms,
        "stored_float_values": stages * clusters * inputs,
        "stored_code_indices": stages * outputs * blocks,
    }


def shared_row_codebook(weight: np.ndarray, clusters: int, seed: int) -> tuple[np.ndarray, dict[str, int]]:
    centers, assignments = kmeans(weight, clusters, seed)
    reconstructed = centers[assignments]
    outputs, inputs = weight.shape
    return reconstructed, {
        "multiply_terms": clusters * inputs,
        "selection_terms": outputs,
        "total_terms": clusters * inputs + outputs,
        "stored_float_values": clusters * inputs,
        "stored_code_indices": outputs,
    }


def shared_column_codebook(weight: np.ndarray, clusters: int, seed: int) -> tuple[np.ndarray, dict[str, int]]:
    centers, assignments = kmeans(weight.T, clusters, seed)
    reconstructed = centers[assignments].T
    outputs, inputs = weight.shape
    return reconstructed, {
        "input_bucket_sum_terms": inputs,
        "multiply_terms": outputs * clusters,
        "total_terms": inputs + outputs * clusters,
        "stored_float_values": outputs * clusters,
        "stored_code_indices": inputs,
    }


def block_circulant(weight: np.ndarray, block_size: int) -> tuple[np.ndarray, dict[str, int]]:
    """Replace every square tile with its least-squares circulant tile."""
    outputs, inputs = weight.shape
    assert outputs % block_size == 0 and inputs % block_size == 0
    reconstructed = np.empty_like(weight)
    rows, columns = np.indices((block_size, block_size))
    diagonals = (columns - rows) % block_size
    for output_start in range(0, outputs, block_size):
        for input_start in range(0, inputs, block_size):
            tile = weight[
                output_start:output_start + block_size,
                input_start:input_start + block_size,
            ]
            coefficients = np.array([
                np.mean(tile[diagonals == diagonal])
                for diagonal in range(block_size)
            ])
            reconstructed[
                output_start:output_start + block_size,
                input_start:input_start + block_size,
            ] = coefficients[diagonals]
    stored = outputs * inputs // block_size
    return reconstructed, {
        "multiply_terms": outputs * inputs,
        "total_terms": outputs * inputs,
        "stored_float_values": stored,
        "storage_compression": outputs * inputs / stored,
    }


def repeated_quantized_chunks(weight: np.ndarray, chunk_size: int) -> dict[str, float | int]:
    """Count exact reusable chunks after signed 9-bit per-row quantization."""
    maximums = np.max(np.abs(weight), axis=1)
    scales = np.where(maximums == 0, 1, maximums / 255)
    codes = np.rint(weight / scales[:, None]).clip(-255, 255).astype(np.int16)
    outputs, inputs = codes.shape
    unique_chunks = 0
    blocks = math.ceil(inputs / chunk_size)
    for block in range(blocks):
        start = block * chunk_size
        stop = min(inputs, start + chunk_size)
        unique_chunks += np.unique(codes[:, start:stop], axis=0).shape[0]
    multiply_terms = unique_chunks * chunk_size
    combine_terms = outputs * blocks
    dense_terms = outputs * inputs
    return {
        "chunk_size": chunk_size,
        "unique_chunks": unique_chunks,
        "total_row_chunks": outputs * blocks,
        "multiply_terms": multiply_terms,
        "combine_terms": combine_terms,
        "total_terms": multiply_terms + combine_terms,
        "term_fraction": (multiply_terms + combine_terms) / dense_terms,
    }


def exact_tail_logits(
    x: np.ndarray,
    tensors: SafeTensors,
    cached_blocks: list[tuple[dict[str, np.ndarray], list[Matrix]]],
) -> np.ndarray:
    for constants, matrices in cached_blocks[1:]:
        x = forward_block(x, constants, matrices)
    final = layer_norm(
        x,
        np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64),
        np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64),
    )
    return final @ np.asarray(tensors.tensor("wte.weight"), dtype=np.float64).T


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    tensors = SafeTensors(MODEL_PATH)
    cached_blocks = [load_block(tensors, layer) for layer in range(12)]
    embeddings = np.asarray(tensors.tensor("wte.weight")[list(TOKEN_IDS)], dtype=np.float64)
    embeddings += np.asarray(tensors.tensor("wpe.weight")[0], dtype=np.float64)
    constants, matrices = cached_blocks[0]
    exact_block = forward_block(embeddings, constants, matrices)
    dense_terms = int(sum(matrix.weight.size for matrix in matrices))

    exact_logits = exact_tail_logits(exact_block, tensors, cached_blocks)
    exact_winners = np.argmax(exact_logits, axis=1)

    variants: list[tuple[str, dict[str, object], list[Matrix], int, dict[str, int]]] = []
    max_kron_rank = 8
    for inner_grid in (16, 32, 64):
        matrix_shapes = {
            "value": (WIDTH // inner_grid, inner_grid, WIDTH // inner_grid, inner_grid),
            "attention_projection": (WIDTH // inner_grid, inner_grid, WIDTH // inner_grid, inner_grid),
            "feed_forward_expansion": (3072 // inner_grid, inner_grid, WIDTH // inner_grid, inner_grid),
            "feed_forward_projection": (WIDTH // inner_grid, inner_grid, 3072 // inner_grid, inner_grid),
        }
        kron_factor_cache = {
            matrix.name: kronecker_factors(
                matrix.weight, *matrix_shapes[matrix.name], max_kron_rank
            )
            for matrix in matrices
        }
        for rank in (1, 2, 4, 8):
            approximated = [
                Matrix(
                    matrix.name,
                    reconstruct_kronecker(kron_factor_cache[matrix.name][:rank]),
                    matrix.bias,
                )
                for matrix in matrices
            ]
            terms = sum(kronecker_terms(*matrix_shapes[matrix.name], rank) for matrix in matrices)
            stored = sum(
                rank * (shape[0] * shape[2] + shape[1] * shape[3])
                for shape in matrix_shapes.values()
            )
            variants.append((
                "kronecker",
                {"rank": rank, "inner_grid": inner_grid},
                approximated,
                terms,
                {"stored_float_values": stored},
            ))

    for block_size, clusters, stages in (
        (64, 16, 1),
        (64, 32, 1),
        (64, 16, 2),
        (64, 32, 2),
        (32, 16, 2),
        (32, 32, 2),
    ):
        approximated = []
        totals = {
            "multiply_terms": 0,
            "selection_terms": 0,
            "total_terms": 0,
            "stored_float_values": 0,
            "stored_code_indices": 0,
        }
        for index, matrix in enumerate(matrices):
            reconstructed, counts = additive_product_quantize(
                matrix.weight, block_size, clusters, stages, 1729 + index * 100_003
            )
            approximated.append(Matrix(matrix.name, reconstructed, matrix.bias))
            for key, value in counts.items():
                totals[key] += value
        variants.append((
            "additive_product_codebook",
            {"block_size": block_size, "clusters": clusters, "stages": stages},
            approximated,
            totals["total_terms"],
            totals,
        ))

    for family, builder in (
        ("shared_row_codebook", shared_row_codebook),
        ("shared_column_codebook", shared_column_codebook),
    ):
        for clusters in (64, 128, 256):
            approximated = []
            totals: dict[str, int] = {}
            for index, matrix in enumerate(matrices):
                reconstructed, counts = builder(
                    matrix.weight, clusters, 811 + index * 100_003
                )
                approximated.append(Matrix(matrix.name, reconstructed, matrix.bias))
                for key, value in counts.items():
                    totals[key] = totals.get(key, 0) + value
            variants.append((
                family,
                {"clusters": clusters},
                approximated,
                totals["total_terms"],
                totals,
            ))

    for block_size in (8, 16, 32):
        approximated = []
        totals: dict[str, int | float] = {}
        for matrix in matrices:
            reconstructed, counts = block_circulant(matrix.weight, block_size)
            approximated.append(Matrix(matrix.name, reconstructed, matrix.bias))
            for key, value in counts.items():
                totals[key] = totals.get(key, 0) + value
        # Storage compression is recomputed globally; summing per-matrix ratios
        # would be meaningless.
        totals["storage_compression"] = dense_terms / int(totals["stored_float_values"])
        variants.append((
            "block_circulant",
            {"block_size": block_size},
            approximated,
            int(totals["total_terms"]),
            totals,
        ))

    results = []
    for family, configuration, approximated, terms, storage in variants:
        block_output = forward_block(embeddings, constants, approximated)
        logits = exact_tail_logits(block_output, tensors, cached_blocks)
        winners = np.argmax(logits, axis=1)
        exact_selected = exact_logits[np.arange(len(TOKEN_IDS)), exact_winners]
        approximate_selected = logits[np.arange(len(TOKEN_IDS)), exact_winners]
        results.append({
            "family": family,
            **configuration,
            "terms": int(terms),
            "term_fraction": terms / dense_terms,
            "compression": dense_terms / terms,
            **storage,
            "matrix_relative_frobenius_error": {
                original.name: float(
                    np.linalg.norm(approximate.weight - original.weight)
                    / np.linalg.norm(original.weight)
                )
                for original, approximate in zip(matrices, approximated)
            },
            **metrics(block_output, exact_block),
            "optimistic_next_token_agreement": float(np.mean(winners == exact_winners)),
            "changed_winner_token_ids": [
                int(TOKEN_IDS[i]) for i in np.flatnonzero(winners != exact_winners)
            ],
            "exact_winner_mean_logit_change": float(
                np.mean(approximate_selected - exact_selected)
            ),
        })

    repeated = {
        matrix.name: [
            repeated_quantized_chunks(matrix.weight, chunk_size)
            for chunk_size in (1, 2, 4, 8, 16)
        ]
        for matrix in matrices
    }
    report = {
        "checkpoint": "openai-community/gpt2",
        "block": 0,
        "token_ids": list(TOKEN_IDS),
        "sample_count": len(TOKEN_IDS),
        "dense_terms": dense_terms,
        "exact_next_tokens": [int(value) for value in exact_winners],
        "structured_approximations": results,
        "exact_repeated_9bit_chunks": repeated,
        "analysis_seconds": time.perf_counter() - started,
        "notes": [
            "Next-token agreement is optimistic: only block 0 is approximated; blocks 1-11 and the output head remain exact.",
            "Kronecker factors use a 32-wide inner grid and execute as two small matrix multiplications per factor.",
            "Codebook terms include both codeword dot products and per-output selected-codeword sums.",
            "Repeated chunks are exact for the current signed 9-bit per-row codes, with row scales applied separately.",
        ],
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
