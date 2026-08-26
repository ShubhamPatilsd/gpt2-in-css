#!/usr/bin/env python3
"""Cross-validate a compact output-head query basis on multi-token GPT-2 states."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-lowrank-coarse-head" / "multitoken.json"
LENGTHS = (2, 4, 8, 16)
SEQUENCES_PER_LENGTH = 48
TRAIN_PER_LENGTH = 24
RANKS = (16, 32, 64, 95)
GROUP_SIZE = 256
HEADS = 12
HEAD_WIDTH = 64
EPSILON = 1e-5


def layer_norm(values: np.ndarray, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
    centered = values - values.mean(axis=-1, keepdims=True)
    variance = np.mean(centered * centered, axis=-1, keepdims=True)
    return centered / np.sqrt(variance + EPSILON) * gamma + beta


def gelu(values: np.ndarray) -> np.ndarray:
    return 0.5 * values * (
        1 + np.tanh(np.sqrt(2 / np.pi) * (values + 0.044715 * values**3))
    )


def final_hidden(tokens: np.ndarray, tensors: SafeTensors) -> np.ndarray:
    batch, length = tokens.shape
    x = np.asarray(tensors.tensor("wte.weight")[tokens], dtype=np.float32)
    x += np.asarray(tensors.tensor("wpe.weight")[:length], dtype=np.float32)
    causal = np.triu(np.full((length, length), -1e9, dtype=np.float32), 1)
    for layer in range(12):
        prefix = f"h.{layer}"
        normalized = layer_norm(
            x,
            tensors.tensor(f"{prefix}.ln_1.weight"),
            tensors.tensor(f"{prefix}.ln_1.bias"),
        )
        qkv = (
            normalized.reshape(batch * length, 768)
            @ tensors.tensor(f"{prefix}.attn.c_attn.weight")
            + tensors.tensor(f"{prefix}.attn.c_attn.bias")
        ).reshape(batch, length, 3, HEADS, HEAD_WIDTH)
        query, key, value = (qkv[:, :, part] for part in range(3))
        scores = np.einsum("bthd,bshd->bhts", query, key) / math.sqrt(HEAD_WIDTH)
        scores += causal[None, None, :, :]
        scores -= scores.max(axis=-1, keepdims=True)
        probabilities = np.exp(scores)
        probabilities /= probabilities.sum(axis=-1, keepdims=True)
        attended = np.einsum("bhts,bshd->bthd", probabilities, value).reshape(
            batch, length, 768
        )
        x = (
            x
            + (
                attended.reshape(batch * length, 768)
                @ tensors.tensor(f"{prefix}.attn.c_proj.weight")
                + tensors.tensor(f"{prefix}.attn.c_proj.bias")
            ).reshape(batch, length, 768)
        )
        normalized = layer_norm(
            x,
            tensors.tensor(f"{prefix}.ln_2.weight"),
            tensors.tensor(f"{prefix}.ln_2.bias"),
        )
        hidden = gelu(
            normalized.reshape(batch * length, 768)
            @ tensors.tensor(f"{prefix}.mlp.c_fc.weight")
            + tensors.tensor(f"{prefix}.mlp.c_fc.bias")
        )
        x = (
            x
            + (
                hidden @ tensors.tensor(f"{prefix}.mlp.c_proj.weight")
                + tensors.tensor(f"{prefix}.mlp.c_proj.bias")
            ).reshape(batch, length, 768)
        )
    return layer_norm(
        x[:, -1], tensors.tensor("ln_f.weight"), tensors.tensor("ln_f.bias")
    ).astype(np.float32)


def summarize(scores: np.ndarray, winners: np.ndarray) -> dict[str, object]:
    approximate = scores.argmax(axis=1)
    winner_scores = scores[np.arange(len(scores)), winners]
    ranks = 1 + np.sum(scores > winner_scores[:, None], axis=1)
    local_ranks = []
    for sample, winner in enumerate(winners):
        start = int(winner // GROUP_SIZE * GROUP_SIZE)
        stop = min(start + GROUP_SIZE, scores.shape[1])
        local_ranks.append(1 + int(np.sum(
            scores[sample, start:stop] > scores[sample, winner]
        )))
    local_ranks_array = np.asarray(local_ranks)
    return {
        "winnerMatches": int(np.sum(approximate == winners)),
        "winnerGroupMatches": int(np.sum(
            approximate // GROUP_SIZE == winners // GROUP_SIZE
        )),
        "globalRankMaximum": int(ranks.max()),
        "globalTop8Recall": int(np.sum(ranks <= 8)),
        "localRankMaximum": int(local_ranks_array.max()),
        "localTop1Recall": int(np.sum(local_ranks_array <= 1)),
        "localTop2Recall": int(np.sum(local_ranks_array <= 2)),
        "localTop4Recall": int(np.sum(local_ranks_array <= 4)),
        "localTop8Recall": int(np.sum(local_ranks_array <= 8)),
    }


def main() -> None:
    tensors = SafeTensors(MODEL_PATH)
    rng = np.random.default_rng(20260913)
    batches = {
        length: rng.integers(
            0, 50_257, size=(SEQUENCES_PER_LENGTH, length), dtype=np.int64
        )
        for length in LENGTHS
    }
    hidden_by_length = {
        length: final_hidden(tokens, tensors) for length, tokens in batches.items()
    }
    hidden = np.concatenate([hidden_by_length[length] for length in LENGTHS])
    train_ids = np.concatenate([
        np.arange(index * SEQUENCES_PER_LENGTH,
                  index * SEQUENCES_PER_LENGTH + TRAIN_PER_LENGTH)
        for index in range(len(LENGTHS))
    ])
    heldout_ids = np.setdiff1d(np.arange(len(hidden)), train_ids)
    weights = np.asarray(tensors.tensor("wte.weight")[:50_257], dtype=np.float32)
    centered_weights = weights - weights.mean(axis=0, keepdims=True)
    dense_scores = hidden @ centered_weights.T
    dense_winners = dense_scores.argmax(axis=1)

    mean = hidden[train_ids].mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(hidden[train_ids] - mean, full_matrices=False)
    basis = vt.T.astype(np.float32)
    projected_weights = centered_weights @ basis
    fixed_scores = mean @ centered_weights.T
    results: dict[str, object] = {
        "model": "openai-community/gpt2",
        "lengths": list(LENGTHS),
        "sequencesPerLength": SEQUENCES_PER_LENGTH,
        "trainingSamples": len(train_ids),
        "heldoutSamples": len(heldout_ids),
        "ranks": {},
    }
    for rank in RANKS:
        scores = fixed_scores + (
            (hidden - mean) @ basis[:, :rank]
        ) @ projected_weights[:, :rank].T
        results["ranks"][str(rank)] = {
            "training": summarize(scores[train_ids], dense_winners[train_ids]),
            "heldout": summarize(scores[heldout_ids], dense_winners[heldout_ids]),
        }
    OUTPUT.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
