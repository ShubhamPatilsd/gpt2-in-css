#!/usr/bin/env python3
"""Train a small deployable ReLU router for GPT-2 vocabulary groups."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_supervised_group_router import (
    GROUPS,
    GROUP_SIZE,
    VOCABULARY,
    breakdown,
    compact_evaluation,
    evaluation,
    guarded_fallback,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments" / "gpt2-supervised-group-router" / "states.npz"
OUTPUT = ROOT / "experiments" / "gpt2-nonlinear-group-router"
HIDDEN = int(os.environ.get("GPT2_NONLINEAR_ROUTER_HIDDEN", "128"))
EPOCHS = int(os.environ.get("GPT2_NONLINEAR_ROUTER_EPOCHS", "300"))
SEEDS = tuple(range(int(os.environ.get("GPT2_NONLINEAR_ROUTER_SEEDS", "3"))))
BATCH = 128
LEARNING_RATE = 0.003
WEIGHT_DECAY = 1e-5


def forward(
    features: np.ndarray,
    w1: np.ndarray,
    b1: np.ndarray,
    w2: np.ndarray,
    b2: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    preactivation = features @ w1 + b1
    hidden = np.maximum(preactivation, 0)
    return hidden @ w2 + b2, hidden, preactivation


def train(
    features: np.ndarray,
    targets: np.ndarray,
    winners: np.ndarray,
    train_ids: np.ndarray,
    validation_ids: np.ndarray,
    seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    rng = np.random.default_rng(20260913 + seed)
    w1 = (
        rng.normal(size=(features.shape[1], HIDDEN)).astype(np.float32)
        * math.sqrt(2 / features.shape[1])
    )
    b1 = np.zeros(HIDDEN, dtype=np.float32)
    w2 = (
        rng.normal(size=(HIDDEN, GROUPS)).astype(np.float32)
        * math.sqrt(2 / HIDDEN)
    )
    b2 = np.zeros(GROUPS, dtype=np.float32)
    parameters = [w1, b1, w2, b2]
    first_moments = [np.zeros_like(value) for value in parameters]
    second_moments = [np.zeros_like(value) for value in parameters]
    step = 0
    best_key = (-1.0, -1.0, -math.inf)
    best = None
    best_epoch = 0
    history = []

    for epoch in range(1, EPOCHS + 1):
        for start in range(0, len(train_ids), BATCH):
            ids = rng.permutation(train_ids) if start == 0 else shuffled
            shuffled = ids
            batch_ids = shuffled[start : start + BATCH]
            predicted, hidden, preactivation = forward(
                features[batch_ids], w1, b1, w2, b2
            )
            difference = predicted - targets[batch_ids]
            shifted = predicted - predicted.max(axis=1, keepdims=True)
            probabilities = np.exp(shifted)
            probabilities /= probabilities.sum(axis=1, keepdims=True)
            probabilities[np.arange(len(batch_ids)), winners[batch_ids] // GROUP_SIZE] -= 1
            output_gradient = probabilities / len(batch_ids)
            output_gradient += 0.05 * 2 * difference / (len(batch_ids) * GROUPS)
            gradients = [
                features[batch_ids].T @ (
                    (output_gradient @ w2.T) * (preactivation > 0)
                ) + WEIGHT_DECAY * w1,
                np.sum((output_gradient @ w2.T) * (preactivation > 0), axis=0),
                hidden.T @ output_gradient + WEIGHT_DECAY * w2,
                np.sum(output_gradient, axis=0),
            ]
            step += 1
            for index, (parameter, gradient) in enumerate(zip(parameters, gradients)):
                first_moments[index] *= 0.9
                first_moments[index] += 0.1 * gradient
                second_moments[index] *= 0.999
                second_moments[index] += 0.001 * gradient * gradient
                corrected_first = first_moments[index] / (1 - 0.9**step)
                corrected_second = second_moments[index] / (1 - 0.999**step)
                parameter -= LEARNING_RATE * corrected_first / (
                    np.sqrt(corrected_second) + 1e-8
                )

        if epoch % 10 != 0 and epoch != EPOCHS:
            continue
        all_scores = forward(features, w1, b1, w2, b2)[0]
        validation = evaluation(all_scores, winners, validation_ids)
        validation_loss = float(np.mean(
            (all_scores[validation_ids] - targets[validation_ids]) ** 2
        ))
        key = (
            validation["top2Fraction"],
            validation["top1Fraction"],
            -validation_loss,
        )
        history.append({
            "epoch": epoch,
            "validationLoss": validation_loss,
            **compact_evaluation(validation),
        })
        if key > best_key:
            best_key = key
            best_epoch = epoch
            best = {
                "w1": w1.copy(), "b1": b1.copy(),
                "w2": w2.copy(), "b2": b2.copy(),
            }
    if best is None:
        raise RuntimeError("training produced no checkpoint")
    return best, {
        "seed": seed,
        "bestEpoch": best_epoch,
        "bestValidationKey": list(best_key),
        "history": history,
    }


def main() -> None:
    if not SOURCE.exists():
        raise RuntimeError("run make analyze-gpt2-supervised-group-router first")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    saved = np.load(SOURCE)
    hidden = saved["hidden"].astype(np.float32)
    winners = saved["dense_winners"].astype(np.int64)
    sources = saved["sources"]
    lengths = saved["lengths"]
    splits = {
        name: saved[f"{name}_ids"].astype(np.int64)
        for name in ("train", "validation", "test")
    }
    mean = hidden[splits["train"]].mean(axis=0)
    std = hidden[splits["train"]].std(axis=0)
    std[std < 1e-5] = 1.0
    features = ((hidden - mean) / std).astype(np.float32)

    tensors = SafeTensors(MODEL_PATH)
    weights = np.asarray(tensors.tensor("wte.weight")[:VOCABULARY], dtype=np.float32)
    dense_scores = hidden @ weights.T
    padded = np.full((len(hidden), GROUPS * GROUP_SIZE), -np.inf, dtype=np.float32)
    padded[:, :VOCABULARY] = dense_scores
    group_scores = padded.reshape(len(hidden), GROUPS, GROUP_SIZE).max(axis=2)
    targets = group_scores - group_scores.mean(axis=1, keepdims=True)
    target_scale = float(targets[splits["train"]].std())
    targets /= max(target_scale, 1e-6)

    runs = []
    checkpoints = []
    for seed in SEEDS:
        print(f"training seed={seed}", flush=True)
        checkpoint, metadata = train(
            features, targets, winners,
            splits["train"], splits["validation"], seed,
        )
        scores = forward(features, **checkpoint)[0]
        validation = evaluation(scores, winners, splits["validation"])
        metadata["validation"] = compact_evaluation(validation)
        runs.append(metadata)
        checkpoints.append(checkpoint)
    best_index = max(
        range(len(runs)),
        key=lambda index: (
            runs[index]["validation"]["top2Fraction"],
            runs[index]["validation"]["top1Fraction"],
        ),
    )
    best = checkpoints[best_index]
    scores = forward(features, **best)[0]
    validation = evaluation(scores, winners, splits["validation"])
    test = evaluation(scores, winners, splits["test"])
    result = {
        "model": "openai-community/gpt2",
        "architecture": [768, HIDDEN, GROUPS],
        "activation": "ReLU",
        "parameters": 768 * HIDDEN + HIDDEN + HIDDEN * GROUPS + GROUPS,
        "epochs": EPOCHS,
        "trainingSamples": len(splits["train"]),
        "validationSamples": len(splits["validation"]),
        "testSamples": len(splits["test"]),
        "target": "winning-group cross-entropy plus 0.05 exact-group-score MSE",
        "runs": runs,
        "selectedSeed": runs[best_index]["seed"],
        "validation": compact_evaluation(validation),
        "test": compact_evaluation(test),
        "testBreakdown": breakdown(
            scores, winners, splits["test"], sources, lengths
        ),
        "guardedFallback": guarded_fallback(validation, test),
    }
    np.savez_compressed(
        OUTPUT / f"router-h{HIDDEN}.npz",
        mean=mean, std=std, target_scale=target_scale, **best,
    )
    (OUTPUT / f"results-h{HIDDEN}.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "architecture": result["architecture"],
        "parameters": result["parameters"],
        "selectedSeed": result["selectedSeed"],
        "validation": result["validation"],
        "test": result["test"],
        "guardedFallback": result["guardedFallback"],
        "results": str((OUTPUT / "results.json").relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
