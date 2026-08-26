#!/usr/bin/env python3
"""Test post-training low-rank QK and value/output attention factors."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import QUANT_BITS, WIDTH, layer_norm
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "lowrank-attention"
HEADS = 12
HEAD_WIDTH = 64
LENGTHS = (2, 4, 8, 16, 32)
SEQUENCES_PER_LENGTH = 32
RANKS = (8, 16, 24, 32, 40, 48, 56, 60, 62, 63, 64)


def factor_product(left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return factors A,B with left@right.T == A@B.T, ordered by singular value."""
    q_left, r_left = np.linalg.qr(left, mode="reduced")
    q_right, r_right = np.linalg.qr(right, mode="reduced")
    u, singular, vt = np.linalg.svd(r_left @ r_right.T, full_matrices=False)
    root = np.sqrt(singular)
    return (q_left @ u) * root, (q_right @ vt.T) * root


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values, axis=-1, keepdims=True)
    weights = np.exp(shifted)
    return weights / np.sum(weights, axis=-1, keepdims=True)


def summarize(errors: list[np.ndarray]) -> dict[str, float]:
    values = np.concatenate([error.ravel() for error in errors])
    return {
        "rmse": float(np.sqrt(np.mean(values * values))),
        "mae": float(np.mean(np.abs(values))),
        "maxError": float(np.max(np.abs(values))),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    positions = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    qkv_weight = np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T
    qkv_bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    qkv_weight = quantize_float_rows(qkv_weight, bits=QUANT_BITS).reconstructed
    projection_weight = np.asarray(
        tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
    ).T
    projection_bias = np.asarray(tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64)
    projection_weight = quantize_float_rows(
        projection_weight, bits=QUANT_BITS
    ).reconstructed

    qk_factors = []
    value_factors = []
    for head in range(HEADS):
        columns = slice(head * HEAD_WIDTH, (head + 1) * HEAD_WIDTH)
        query = np.vstack((qkv_weight[columns].T, qkv_bias[columns]))
        key_rows = slice(WIDTH + head * HEAD_WIDTH, WIDTH + (head + 1) * HEAD_WIDTH)
        key = np.vstack((qkv_weight[key_rows].T, qkv_bias[key_rows]))
        qk_factors.append(factor_product(query, key))

        value_rows = slice(2 * WIDTH + head * HEAD_WIDTH, 2 * WIDTH + (head + 1) * HEAD_WIDTH)
        value = np.vstack((qkv_weight[value_rows].T, qkv_bias[value_rows]))
        output = projection_weight[:, columns]
        value_factors.append(factor_product(value, output))

    rng = np.random.default_rng(0x4C4F5752)
    samples = []
    for length in LENGTHS:
        for _ in range(SEQUENCES_PER_LENGTH):
            tokens = rng.integers(0, embeddings.shape[0], size=length)
            states = embeddings[tokens] + positions[:length]
            normalized = np.stack([layer_norm(row, gamma, beta) for row in states])
            augmented = np.pad(normalized, ((0, 0), (0, 1)), constant_values=1)
            qkv = normalized @ qkv_weight.T + qkv_bias
            query = qkv[-1, :WIDTH].reshape(HEADS, HEAD_WIDTH)
            key = qkv[:, WIDTH:2 * WIDTH].reshape(length, HEADS, HEAD_WIDTH)
            value = qkv[:, 2 * WIDTH:].reshape(length, HEADS, HEAD_WIDTH)
            scores = np.einsum("hd,shd->hs", query, key) / math.sqrt(HEAD_WIDTH)
            probabilities = softmax(scores)
            context = np.einsum("hs,shd->hd", probabilities, value).ravel()
            residual = states[-1] + projection_weight @ context + projection_bias
            samples.append((length, states[-1], augmented, scores, probabilities, residual))

    results = {}
    for rank in RANKS:
        score_errors = []
        probability_errors = []
        residual_score_only_errors = []
        residual_value_only_errors = []
        residual_both_errors = []
        winner_matches = []
        by_length: dict[int, list[float]] = {length: [] for length in LENGTHS}
        for length, state, augmented, scores, probabilities, residual in samples:
            candidate_scores = np.empty_like(scores)
            for head, (left, right) in enumerate(qk_factors):
                q = augmented[-1] @ left[:, :rank]
                k = augmented @ right[:, :rank]
                candidate_scores[head] = k @ q / math.sqrt(HEAD_WIDTH)
            candidate_probabilities = softmax(candidate_scores)

            def projected(candidate_weights: np.ndarray, value_rank: int) -> np.ndarray:
                output = np.zeros(WIDTH)
                for head, (left, right) in enumerate(value_factors):
                    compressed_values = augmented @ left[:, :value_rank]
                    compressed_context = candidate_weights[head] @ compressed_values
                    output += right[:, :value_rank] @ compressed_context
                return state + output + projection_bias

            score_only = projected(candidate_probabilities, HEAD_WIDTH)
            value_only = projected(probabilities, rank)
            both = projected(candidate_probabilities, rank)
            score_errors.append(candidate_scores - scores)
            probability_errors.append(candidate_probabilities - probabilities)
            residual_score_only_errors.append(score_only - residual)
            residual_value_only_errors.append(value_only - residual)
            residual_both_errors.append(both - residual)
            winner_matches.append(
                np.argmax(candidate_scores, axis=1) == np.argmax(scores, axis=1)
            )
            by_length[length].append(float(np.sqrt(np.mean((both - residual) ** 2))))
        results[str(rank)] = {
            "boxesPerSource": HEADS * rank * 2,
            "boxReductionFraction": 1 - rank / HEAD_WIDTH,
            "score": summarize(score_errors),
            "probability": summarize(probability_errors),
            "residualScoreOnly": summarize(residual_score_only_errors),
            "residualValueOnly": summarize(residual_value_only_errors),
            "residualBoth": summarize(residual_both_errors),
            "attentionWinnerAgreement": float(np.mean(np.concatenate(winner_matches))),
            "bothResidualRmseByLength": {
                str(length): float(np.mean(values)) for length, values in by_length.items()
            },
        }

    report = {
        "checkpoint": str(MODEL_PATH),
        "sequenceLengths": LENGTHS,
        "sequencesPerLength": SEQUENCES_PER_LENGTH,
        "weights": f"signed {QUANT_BITS}-bit HVAR reference",
        "method": "per-head SVD of augmented affine QK and value/output products",
        "results": results,
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
