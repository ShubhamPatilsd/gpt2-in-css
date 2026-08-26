#!/usr/bin/env python3
"""Measure global output-weight quantization on many real GPT-2 states."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_pretrained_gpt2 import gelu_new


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-hvar-grid-output-head-global11"
SAMPLE_COUNT = 256
SEED = 20260913
EPSILON = 1e-5


def layer_norm_batch(
    values: np.ndarray, gamma: np.ndarray, beta: np.ndarray
) -> np.ndarray:
    centered = values - values.mean(axis=1, keepdims=True)
    variance = np.mean(centered * centered, axis=1, keepdims=True)
    return centered / np.sqrt(variance + EPSILON) * gamma + beta


def final_hidden_batch(token_ids: np.ndarray, tensors: SafeTensors) -> np.ndarray:
    x = np.asarray(
        tensors.tensor("wte.weight")[token_ids] + tensors.tensor("wpe.weight")[0],
        dtype=np.float32,
    )
    for layer in range(12):
        prefix = f"h.{layer}"
        normalized = layer_norm_batch(
            x,
            tensors.tensor(f"{prefix}.ln_1.weight"),
            tensors.tensor(f"{prefix}.ln_1.bias"),
        )
        qkv = (
            normalized @ tensors.tensor(f"{prefix}.attn.c_attn.weight")
            + tensors.tensor(f"{prefix}.attn.c_attn.bias")
        )
        value = qkv[:, 1536:]
        x = (
            x
            + value @ tensors.tensor(f"{prefix}.attn.c_proj.weight")
            + tensors.tensor(f"{prefix}.attn.c_proj.bias")
        )
        normalized = layer_norm_batch(
            x,
            tensors.tensor(f"{prefix}.ln_2.weight"),
            tensors.tensor(f"{prefix}.ln_2.bias"),
        )
        hidden = gelu_new(
            normalized @ tensors.tensor(f"{prefix}.mlp.c_fc.weight")
            + tensors.tensor(f"{prefix}.mlp.c_fc.bias")
        )
        x = (
            x
            + hidden @ tensors.tensor(f"{prefix}.mlp.c_proj.weight")
            + tensors.tensor(f"{prefix}.mlp.c_proj.bias")
        )
    return layer_norm_batch(
        x, tensors.tensor("ln_f.weight"), tensors.tensor("ln_f.bias")
    )


def main() -> None:
    tensors = SafeTensors(MODEL_PATH)
    rng = np.random.default_rng(SEED)
    fixed = np.array([
        0, 1, 11, 13, 257, 464, 477, 612, 15496,
        11776, 17618, 21328, 27542, 45983, 46716,
    ], dtype=np.int64)
    random_ids = rng.choice(
        50_257, size=SAMPLE_COUNT - len(fixed), replace=False
    ).astype(np.int64)
    token_ids = np.concatenate((fixed, random_ids))
    hidden = final_hidden_batch(token_ids, tensors).astype(np.float32)
    embeddings = np.asarray(tensors.tensor("wte.weight")[:50_257], dtype=np.float32)
    dense_logits = hidden @ embeddings.T
    dense_winners = dense_logits.argmax(axis=1)
    sorted_top = np.partition(dense_logits, -2, axis=1)[:, -2:]
    dense_margins = sorted_top.max(axis=1) - sorted_top.min(axis=1)
    results: dict[str, object] = {
        "sampleCount": SAMPLE_COUNT,
        "seed": SEED,
        "tokenIds": token_ids.tolist(),
        "denseWinners": dense_winners.astype(int).tolist(),
        "minimumDenseTop2Margin": float(dense_margins.min()),
        "medianDenseTop2Margin": float(np.median(dense_margins)),
        "encodings": {},
    }
    score_scales = (256, 1024, 2048, 4096)
    results["denseScoreBucketMatches"] = {
        str(score_scale): int((
            np.rint(dense_logits * score_scale).argmax(axis=1)
            == dense_winners
        ).sum())
        for score_scale in score_scales
    }
    maximum = float(np.max(np.abs(embeddings)))
    for bits in (10, 11, 12, 13, 16):
        max_code = 2 ** (bits - 1) - 1
        scale = maximum / max_code
        quantized = np.rint(embeddings / scale).astype(np.int16).astype(np.float32)
        quantized *= scale
        logits = hidden @ quantized.T
        winners = logits.argmax(axis=1)
        matches = winners == dense_winners
        results["encodings"][f"globalInt{bits}"] = {
            "scale": scale,
            "winnerMatches": int(matches.sum()),
            "winnerMatchRate": float(matches.mean()),
            "winnerGroupMatches": int((
                winners // 256 == dense_winners // 256
            ).sum()),
            "mismatchedInputs": token_ids[~matches].astype(int).tolist(),
            "winners": winners.astype(int).tolist(),
            "logitRmse": float(np.sqrt(np.mean((logits - dense_logits) ** 2))),
            "weightRmse": float(np.sqrt(np.mean((quantized - embeddings) ** 2))),
            "scoreBucketMatches": {
                str(score_scale): int((
                    np.rint(logits * score_scale).argmax(axis=1)
                    == dense_winners
                ).sum())
                for score_scale in score_scales
            },
        }
    for bits in (10, 11, 12, 13, 16):
        max_code = 2 ** (bits - 1) - 1
        row_scales = np.max(np.abs(embeddings), axis=1) / max_code
        row_scales[row_scales == 0] = 1
        row_quantized = np.rint(
            embeddings / row_scales[:, None]
        ).astype(np.int16)
        row_quantized = row_quantized.astype(np.float32) * row_scales[:, None]
        row_logits = hidden @ row_quantized.T
        row_winners = row_logits.argmax(axis=1)
        row_matches = row_winners == dense_winners
        results["encodings"][f"rowInt{bits}"] = {
            "winnerMatches": int(row_matches.sum()),
            "winnerMatchRate": float(row_matches.mean()),
            "winnerGroupMatches": int((
                row_winners // 256 == dense_winners // 256
            ).sum()),
            "mismatchedInputs": token_ids[~row_matches].astype(int).tolist(),
            "winners": row_winners.astype(int).tolist(),
            "logitRmse": float(np.sqrt(np.mean((row_logits - dense_logits) ** 2))),
            "weightRmse": float(np.sqrt(np.mean((row_quantized - embeddings) ** 2))),
            "scoreBucketMatches": {
                str(score_scale): int((
                    np.rint(row_logits * score_scale).argmax(axis=1)
                    == dense_winners
                ).sum())
                for score_scale in score_scales
            },
        }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "precision-analysis.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    print(json.dumps({
        "sampleCount": results["sampleCount"],
        "minimumDenseTop2Margin": results["minimumDenseTop2Margin"],
        "medianDenseTop2Margin": results["medianDenseTop2Margin"],
        "encodings": results["encodings"],
    }, indent=2))


if __name__ == "__main__":
    main()
