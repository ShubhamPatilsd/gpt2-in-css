#!/usr/bin/env python3
"""Measure whether a 256-axis bottleneck can approximate GPT-2's FC layers."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_pretrained_gpt2 import Gpt2Tokenizer


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-fc-lowrank"
CHECKPOINT = ROOT / "data" / "gpt2"
RANKS = (64, 128, 256, 384, 512)
PROMPTS = (
    "Hello",
    "Once upon a time",
    "The quick brown fox",
    "Paris is the capital of",
    "In a shocking finding, scientists",
    "She opened the door and",
    "To be or not to be",
    "CSS can perform matrix multiplication",
    "The meaning of life is",
    "Machine learning models predict",
)
HEADS = 12
HEAD_WIDTH = 64
EPSILON = 1e-5


def layer_norm(vector: np.ndarray, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
    mean = np.mean(vector, axis=-1, keepdims=True)
    variance = np.mean((vector - mean) ** 2, axis=-1, keepdims=True)
    return (vector - mean) / np.sqrt(variance + EPSILON) * gamma + beta


def gelu(value: np.ndarray) -> np.ndarray:
    return 0.5 * value * (
        1 + np.tanh(math.sqrt(2 / math.pi) * (value + 0.044715 * value**3))
    )


def softmax(value: np.ndarray) -> np.ndarray:
    shifted = value - np.max(value, axis=-1, keepdims=True)
    exponent = np.exp(shifted)
    return exponent / np.sum(exponent, axis=-1, keepdims=True)


def tensor(tensors: SafeTensors, name: str) -> np.ndarray:
    return np.asarray(tensors.tensor(name), dtype=np.float64)


def factor_fc_layers(tensors: SafeTensors) -> tuple[list[tuple[np.ndarray, np.ndarray, np.ndarray]], list[dict[str, object]]]:
    factors = []
    summaries = []
    for layer in range(12):
        weight = tensor(tensors, f"h.{layer}.mlp.c_fc.weight")
        u, singular, vh = np.linalg.svd(weight, full_matrices=False)
        factors.append((u, singular, vh))
        total = float(np.sum(singular**2))
        summaries.append({
            "layer": layer,
            "retainedEnergy": {
                str(rank): float(np.sum(singular[:rank] ** 2) / total)
                for rank in RANKS
            },
        })
    return factors, summaries


def forward(
    token_ids: list[int],
    tensors: SafeTensors,
    factors: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
    rank: int | None,
    quantization_bits: int | None = None,
    quantization_range: float = 4.0,
) -> np.ndarray:
    positions = np.arange(len(token_ids))
    x = tensor(tensors, "wte.weight")[token_ids] + tensor(tensors, "wpe.weight")[positions]
    causal = np.triu(np.full((len(token_ids), len(token_ids)), -np.inf), 1)
    for layer in range(12):
        prefix = f"h.{layer}"
        normalized = layer_norm(
            x,
            tensor(tensors, f"{prefix}.ln_1.weight"),
            tensor(tensors, f"{prefix}.ln_1.bias"),
        )
        qkv = (
            normalized @ tensor(tensors, f"{prefix}.attn.c_attn.weight")
            + tensor(tensors, f"{prefix}.attn.c_attn.bias")
        ).reshape(len(token_ids), 3, HEADS, HEAD_WIDTH)
        query, key, value = (qkv[:, index] for index in range(3))
        scores = np.einsum("thd,shd->hts", query, key) / math.sqrt(HEAD_WIDTH)
        attention = softmax(scores + causal[None, :, :])
        mixed = np.einsum("hts,shd->thd", attention, value).reshape(len(token_ids), -1)
        x = (
            x
            + mixed @ tensor(tensors, f"{prefix}.attn.c_proj.weight")
            + tensor(tensors, f"{prefix}.attn.c_proj.bias")
        )
        normalized = layer_norm(
            x,
            tensor(tensors, f"{prefix}.ln_2.weight"),
            tensor(tensors, f"{prefix}.ln_2.bias"),
        )
        if quantization_bits is not None:
            maximum_code = 2 ** (quantization_bits - 1) - 1
            step = quantization_range / maximum_code
            normalized = (
                np.clip(np.rint(normalized / step), -maximum_code, maximum_code)
                * step
            )
        if rank is None:
            preactivation = (
                normalized @ tensor(tensors, f"{prefix}.mlp.c_fc.weight")
                + tensor(tensors, f"{prefix}.mlp.c_fc.bias")
            )
        else:
            u, singular, vh = factors[layer]
            preactivation = (
                (normalized @ u[:, :rank] * singular[:rank]) @ vh[:rank]
                + tensor(tensors, f"{prefix}.mlp.c_fc.bias")
            )
        x = (
            x
            + gelu(preactivation) @ tensor(tensors, f"{prefix}.mlp.c_proj.weight")
            + tensor(tensors, f"{prefix}.mlp.c_proj.bias")
        )
    hidden = layer_norm(x[-1], tensor(tensors, "ln_f.weight"), tensor(tensors, "ln_f.bias"))
    return tensor(tensors, "wte.weight") @ hidden


def main() -> None:
    started = time.perf_counter()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    tokenizer = Gpt2Tokenizer(CHECKPOINT / "vocab.json", CHECKPOINT / "merges.txt")
    factors, layers = factor_fc_layers(tensors)
    cases = []
    aggregate = {rank: [] for rank in RANKS}
    for prompt in PROMPTS:
        token_ids = tokenizer.encode(prompt)
        exact = forward(token_ids, tensors, factors, None)
        exact_winner = int(np.argmax(exact))
        exact_top10 = set(np.argpartition(exact, -10)[-10:].tolist())
        approximations = []
        for rank in RANKS:
            approximate = forward(token_ids, tensors, factors, rank)
            winner = int(np.argmax(approximate))
            exact_winner_rank = int(1 + np.sum(approximate > approximate[exact_winner]))
            result = {
                "rank": rank,
                "winner": winner,
                "top1Matches": winner == exact_winner,
                "exactWinnerRank": exact_winner_rank,
                "logitRmse": float(np.sqrt(np.mean((approximate - exact) ** 2))),
                "top10Overlap": len(exact_top10 & set(np.argpartition(approximate, -10)[-10:].tolist())),
            }
            approximations.append(result)
            aggregate[rank].append(result)
        cases.append({
            "prompt": prompt,
            "tokens": token_ids,
            "exactWinner": exact_winner,
            "approximations": approximations,
        })

    summary = []
    for rank in RANKS:
        values = aggregate[rank]
        summary.append({
            "rank": rank,
            "top1Matches": sum(item["top1Matches"] for item in values),
            "cases": len(values),
            "medianExactWinnerRank": float(np.median([item["exactWinnerRank"] for item in values])),
            "maximumExactWinnerRank": max(item["exactWinnerRank"] for item in values),
            "meanTop10Overlap": float(np.mean([item["top10Overlap"] for item in values])),
            "meanLogitRmse": float(np.mean([item["logitRmse"] for item in values])),
        })
    report = {
        "model": "gpt2-small",
        "prompts": len(PROMPTS),
        "layers": layers,
        "summary": summary,
        "cases": cases,
        "elapsedSeconds": time.perf_counter() - started,
    }
    (OUTPUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "summary": summary,
        "meanRetainedEnergy": {
            str(rank): float(np.mean([
                layer["retainedEnergy"][str(rank)] for layer in layers
            ])) for rank in RANKS
        },
        "elapsedSeconds": report["elapsedSeconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
