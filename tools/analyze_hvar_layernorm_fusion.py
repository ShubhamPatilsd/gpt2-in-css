#!/usr/bin/env python3
"""Measure 9-bit HVAR accuracy when LayerNorm is fused into its matrix."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import EPSILON, WIDTH, layer_norm
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "hvar-layernorm-fusion"
TOKEN_IDS = [0, 11, 13, 40, 198, 220, 257, 262, 286, 318, 373, 464, 612, 995, 15496, 30000, 40000, 50256]


def fused_parameters(weight: np.ndarray, gamma: np.ndarray, beta: np.ndarray, bias: np.ndarray):
    scaled = weight * gamma[np.newaxis, :]
    centered = scaled - np.mean(scaled, axis=1, keepdims=True)
    fused_bias = weight @ beta + bias
    return centered, fused_bias


def error_stats(errors: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "mae": float(np.mean(np.abs(errors))),
        "max_error": float(np.max(np.abs(errors))),
    }


def evaluate(
    name: str,
    inputs: list[np.ndarray],
    weight: np.ndarray,
    bias: np.ndarray,
    gamma: np.ndarray,
    beta: np.ndarray,
) -> dict[str, object]:
    quantized_weight = quantize_float_rows(weight, bits=9).reconstructed
    fused_weight, fused_bias = fused_parameters(weight, gamma, beta, bias)
    quantized_fused_rows = {
        bits: quantize_float_rows(fused_weight, bits=bits) for bits in (9, 10)
    }
    baseline_errors = []
    fused_errors = {bits: [] for bits in quantized_fused_rows}
    cross_errors = {bits: [] for bits in quantized_fused_rows}
    for vector in inputs:
        normalized = layer_norm(vector, gamma, beta)
        exact = weight @ normalized + bias
        baseline = quantized_weight @ normalized + bias
        sigma = np.sqrt(np.mean((vector - np.mean(vector)) ** 2) + EPSILON)
        baseline_errors.append(baseline - exact)
        for bits, rows in quantized_fused_rows.items():
            fused = rows.reconstructed @ vector / sigma + fused_bias
            fused_errors[bits].append(fused - exact)
            cross_errors[bits].append(fused - baseline)
    max_shard_bases = {
        str(bits): max(
            int(np.max(np.sum(np.abs(rows.codes[:, start : start + 256]).astype(np.int64), axis=1) + 32))
            for start in range(0, rows.codes.shape[1], 256)
        )
        for bits, rows in quantized_fused_rows.items()
    }
    return {
        "name": name,
        "shape": list(weight.shape),
        "baseline_9bit": error_stats(np.asarray(baseline_errors)),
        "fused_9bit": error_stats(np.asarray(fused_errors[9])),
        "fused_10bit": error_stats(np.asarray(fused_errors[10])),
        "fused_vs_baseline_9bit": error_stats(np.asarray(cross_errors[9])),
        "fused_vs_baseline_10bit": error_stats(np.asarray(cross_errors[10])),
        "max_safe_base_by_bits": max_shard_bases,
        "fused_weight_max": float(np.max(np.abs(fused_weight))),
        "original_weight_max": float(np.max(np.abs(weight))),
    }


def main() -> None:
    tensors = SafeTensors(MODEL_PATH)
    embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    position = np.asarray(tensors.tensor("wpe.weight")[0], dtype=np.float64)
    inputs = [embeddings[token] + position for token in TOKEN_IDS]

    c_attn_weight = np.asarray(tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64).T
    c_attn_bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    ln1_gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    ln1_beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)

    value_weight = c_attn_weight[2 * WIDTH :]
    value_bias = c_attn_bias[2 * WIDTH :]
    proj_weight = np.asarray(tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64).T
    proj_bias = np.asarray(tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64)
    residual_inputs = []
    for vector in inputs:
        n1 = layer_norm(vector, ln1_gamma, ln1_beta)
        residual_inputs.append(vector + proj_weight @ (value_weight @ n1 + value_bias) + proj_bias)

    fc_weight = np.asarray(tensors.tensor("h.0.mlp.c_fc.weight"), dtype=np.float64).T
    fc_bias = np.asarray(tensors.tensor("h.0.mlp.c_fc.bias"), dtype=np.float64)
    ln2_gamma = np.asarray(tensors.tensor("h.0.ln_2.weight"), dtype=np.float64)
    ln2_beta = np.asarray(tensors.tensor("h.0.ln_2.bias"), dtype=np.float64)

    result = {
        "checkpoint": "openai-community/gpt2",
        "block": 0,
        "token_ids": TOKEN_IDS,
        "sample_count": len(TOKEN_IDS),
        "matrices": [
            evaluate("ln1_to_qkv", inputs, c_attn_weight, c_attn_bias, ln1_gamma, ln1_beta),
            evaluate("ln2_to_fc", residual_inputs, fc_weight, fc_bias, ln2_gamma, ln2_beta),
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
