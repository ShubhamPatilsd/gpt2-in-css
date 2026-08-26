#!/usr/bin/env python3
"""Screen small supervised routers for the 197 GPT-2 vocabulary groups."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from analyze_gpt2_multitoken_query_subspace import final_hidden
from build_pretrained_gpt2 import Gpt2Tokenizer


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "gpt2-supervised-group-router"
LENGTHS = (2, 4, 8, 16)
SAMPLES_PER_SOURCE_LENGTH = int(os.environ.get("GPT2_ROUTER_SAMPLES", "64"))
GROUP_SIZE = 256
VOCABULARY = 50_257
GROUPS = math.ceil(VOCABULARY / GROUP_SIZE)
REPRESENTATIVE_COUNTS = (1, 2, 4, 8, 16, 32, 64, 96, 128, 192, 256)
RIDGE_LAMBDAS = (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0)


def corpus_batches(tokenizer: Gpt2Tokenizer, rng: np.random.Generator) -> dict[int, np.ndarray]:
    paths = (
        ROOT / "README.md",
        ROOT / "OPTIMIZATIONS.md",
        ROOT / "experiments" / "numeric-backend-decision" / "RESULTS.md",
        ROOT / "experiments" / "smil-stage-scheduler" / "RESULTS.md",
    )
    streams = [
        np.asarray(tokenizer.encode(path.read_text()), dtype=np.int64)
        for path in paths if path.exists()
    ]
    if not streams:
        raise RuntimeError("no local text corpus")
    result = {}
    for length in LENGTHS:
        rows = []
        eligible = [stream for stream in streams if len(stream) >= length]
        for _ in range(SAMPLES_PER_SOURCE_LENGTH):
            stream = eligible[int(rng.integers(len(eligible)))]
            start = int(rng.integers(len(stream) - length + 1))
            rows.append(stream[start : start + length])
        result[length] = np.stack(rows)
    return result


def split_ids(source: np.ndarray, length: np.ndarray) -> dict[str, np.ndarray]:
    train, validation, test = [], [], []
    for source_id in range(2):
        for context_length in LENGTHS:
            ids = np.flatnonzero((source == source_id) & (length == context_length))
            first = len(ids) // 2
            second = first + len(ids) // 4
            train.extend(ids[:first])
            validation.extend(ids[first:second])
            test.extend(ids[second:])
    return {
        "train": np.asarray(train, dtype=np.int64),
        "validation": np.asarray(validation, dtype=np.int64),
        "test": np.asarray(test, dtype=np.int64),
    }


def top_groups(scores: np.ndarray, count: int = 2) -> np.ndarray:
    partial = np.argpartition(scores, -count, axis=1)[:, -count:]
    values = np.take_along_axis(scores, partial, axis=1)
    order = np.argsort(values, axis=1)[:, ::-1]
    return np.take_along_axis(partial, order, axis=1)


def evaluation(scores: np.ndarray, winners: np.ndarray, ids: np.ndarray) -> dict[str, object]:
    ranked = top_groups(scores[ids], 8)
    expected = winners[ids] // GROUP_SIZE
    margin = (
        np.take_along_axis(scores[ids], ranked[:, :1], axis=1)[:, 0]
        - np.take_along_axis(scores[ids], ranked[:, 1:2], axis=1)[:, 0]
    )
    return {
        "samples": len(ids),
        "top1Recall": int(np.sum(ranked[:, 0] == expected)),
        "top2Recall": int(np.sum(np.any(ranked[:, :2] == expected[:, None], axis=1))),
        "top4Recall": int(np.sum(np.any(ranked[:, :4] == expected[:, None], axis=1))),
        "top8Recall": int(np.sum(np.any(ranked[:, :8] == expected[:, None], axis=1))),
        "top1Fraction": float(np.mean(ranked[:, 0] == expected)),
        "top2Fraction": float(np.mean(np.any(ranked[:, :2] == expected[:, None], axis=1))),
        "top4Fraction": float(np.mean(np.any(ranked[:, :4] == expected[:, None], axis=1))),
        "top8Fraction": float(np.mean(np.any(ranked[:, :8] == expected[:, None], axis=1))),
        "margins": margin,
        "predicted": ranked[:, 0],
        "expected": expected,
    }


def compact_evaluation(result: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in result.items() if key not in {
        "margins", "predicted", "expected"
    }}


def guarded_fallback(
    validation: dict[str, object], test: dict[str, object]
) -> dict[str, object]:
    validation_correct = validation["predicted"] == validation["expected"]
    incorrect_margins = validation["margins"][~validation_correct]
    threshold = (
        float(np.max(incorrect_margins)) + 1e-7
        if len(incorrect_margins) else -math.inf
    )
    accepted = test["margins"] > threshold
    correct = test["predicted"] == test["expected"]
    return {
        "validationZeroErrorMarginThreshold": threshold,
        "testAccepted": int(np.sum(accepted)),
        "testCoverage": float(np.mean(accepted)),
        "testAcceptedCorrect": int(np.sum(correct & accepted)),
        "testAcceptedPrecision": (
            float(np.mean(correct[accepted])) if np.any(accepted) else None
        ),
        "testFallback": int(np.sum(~accepted)),
    }


def breakdown(
    scores: np.ndarray,
    winners: np.ndarray,
    ids: np.ndarray,
    sources: np.ndarray,
    lengths: np.ndarray,
) -> dict[str, object]:
    result = {}
    for source_id, source_name in enumerate(("uniform-random", "local-text")):
        source_result = {}
        for context_length in LENGTHS:
            subset = ids[(sources[ids] == source_id) & (lengths[ids] == context_length)]
            source_result[str(context_length)] = compact_evaluation(
                evaluation(scores, winners, subset)
            )
        result[source_name] = source_result
    return result


def representative_scores(
    hidden: np.ndarray,
    weights: np.ndarray,
    local_winners: np.ndarray,
    train_ids: np.ndarray,
    count: int,
) -> tuple[np.ndarray, list[list[int]]]:
    selected = np.zeros((GROUPS, count), dtype=np.int64)
    selected_tokens: list[list[int]] = []
    for group in range(GROUPS):
        start = group * GROUP_SIZE
        stop = min(start + GROUP_SIZE, VOCABULARY)
        frequencies = np.bincount(
            local_winners[train_ids, group] - start,
            minlength=stop - start,
        )
        order = np.argsort(frequencies, kind="stable")[::-1]
        tokens = start + order[: min(count, len(order))]
        if len(tokens) < count:
            tokens = np.pad(tokens, (0, count - len(tokens)), mode="edge")
        selected[group] = tokens
        selected_tokens.append(tokens.tolist())
    flat = selected.reshape(-1)
    scores = (hidden @ weights[flat].T).reshape(len(hidden), GROUPS, count)
    return scores.max(axis=2), selected_tokens


def ridge_scores(
    hidden: np.ndarray,
    targets: np.ndarray,
    winners: np.ndarray,
    splits: dict[str, np.ndarray],
) -> tuple[np.ndarray, float, dict[str, object]]:
    train_ids = splits["train"]
    validation_ids = splits["validation"]
    mean = hidden[train_ids].mean(axis=0)
    std = hidden[train_ids].std(axis=0)
    std[std < 1e-5] = 1.0
    features = (hidden - mean) / std / math.sqrt(hidden.shape[1])
    features = np.concatenate((features, np.ones((len(features), 1))), axis=1)
    train_features = features[train_ids]
    kernel = train_features @ train_features.T
    identity = np.eye(len(train_ids), dtype=np.float32)
    validation_results = {}
    candidates = []
    for regularization in RIDGE_LAMBDAS:
        alpha = np.linalg.solve(
            kernel + regularization * identity,
            targets[train_ids],
        )
        weights = train_features.T @ alpha
        scores = features @ weights
        result = evaluation(scores, winners, validation_ids)
        validation_results[str(regularization)] = compact_evaluation(result)
        candidates.append((result["top2Fraction"], result["top1Fraction"], -regularization, regularization, scores))
    _, _, _, best_regularization, best_scores = max(candidates, key=lambda item: item[:3])
    return best_scores, best_regularization, validation_results


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tensors = SafeTensors(MODEL_PATH)
    tokenizer = Gpt2Tokenizer(
        ROOT / "data" / "gpt2" / "vocab.json",
        ROOT / "data" / "gpt2" / "merges.txt",
    )
    rng = np.random.default_rng(20260913)
    batches = {
        0: {
            length: rng.integers(
                0, VOCABULARY,
                size=(SAMPLES_PER_SOURCE_LENGTH, length),
                dtype=np.int64,
            )
            for length in LENGTHS
        },
        1: corpus_batches(tokenizer, rng),
    }

    hidden_parts = []
    source_parts = []
    length_parts = []
    for source_id in range(2):
        for context_length in LENGTHS:
            print(f"forward source={source_id} length={context_length}", flush=True)
            values = final_hidden(batches[source_id][context_length], tensors)
            hidden_parts.append(values)
            source_parts.append(np.full(len(values), source_id, dtype=np.int8))
            length_parts.append(np.full(len(values), context_length, dtype=np.int8))
    hidden = np.concatenate(hidden_parts)
    sources = np.concatenate(source_parts)
    lengths = np.concatenate(length_parts)
    splits = split_ids(sources, lengths)

    weights = np.asarray(tensors.tensor("wte.weight")[:VOCABULARY], dtype=np.float32)
    print("scoring dense vocabulary", flush=True)
    dense_scores = hidden @ weights.T
    dense_winners = dense_scores.argmax(axis=1)
    padded = np.full((len(hidden), GROUPS * GROUP_SIZE), -np.inf, dtype=np.float32)
    padded[:, :VOCABULARY] = dense_scores
    grouped = padded.reshape(len(hidden), GROUPS, GROUP_SIZE)
    local_indices = grouped.argmax(axis=2)
    local_winners = (
        local_indices + np.arange(GROUPS, dtype=np.int64)[None, :] * GROUP_SIZE
    )
    group_scores = grouped.max(axis=2)

    result: dict[str, object] = {
        "model": "openai-community/gpt2",
        "groupSize": GROUP_SIZE,
        "groups": GROUPS,
        "samplesPerSourceLength": SAMPLES_PER_SOURCE_LENGTH,
        "samples": len(hidden),
        "splitSamples": {name: len(ids) for name, ids in splits.items()},
        "uniqueWinnerGroups": {
            name: int(len(np.unique(dense_winners[ids] // GROUP_SIZE)))
            for name, ids in splits.items()
        },
        "majorityBaselines": {},
        "representativeRouters": {},
    }
    train_group_counts = np.bincount(
        dense_winners[splits["train"]] // GROUP_SIZE,
        minlength=GROUPS,
    )
    majority_groups = np.argsort(train_group_counts)[::-1]
    for split_name in ("validation", "test"):
        expected = dense_winners[splits[split_name]] // GROUP_SIZE
        result["majorityBaselines"][split_name] = {
            "top1Group": int(majority_groups[0]),
            "top1Fraction": float(np.mean(expected == majority_groups[0])),
            "top2Groups": majority_groups[:2].tolist(),
            "top2Fraction": float(np.mean(np.isin(expected, majority_groups[:2]))),
        }
    for count in REPRESENTATIVE_COUNTS:
        print(f"representatives={count}", flush=True)
        scores, selected = representative_scores(
            hidden, weights, local_winners, splits["train"], count
        )
        validation = evaluation(scores, dense_winners, splits["validation"])
        test = evaluation(scores, dense_winners, splits["test"])
        result["representativeRouters"][str(count)] = {
            "scoredRows": GROUPS * count,
            "rowReduction": float(VOCABULARY / (GROUPS * count)),
            "validation": compact_evaluation(validation),
            "test": compact_evaluation(test),
            "testBreakdown": breakdown(
                scores, dense_winners, splits["test"], sources, lengths
            ),
            "guardedFallback": guarded_fallback(validation, test),
            "selectedTokens": selected if count <= 2 else None,
        }

    ridge_targets = {
        "oneHotGroup": np.eye(GROUPS, dtype=np.float32)[dense_winners // GROUP_SIZE],
        "groupMaximumScore": (
            group_scores - group_scores.mean(axis=1, keepdims=True)
        ) / max(float(group_scores.std()), 1e-6),
    }
    result["linearRidgeRouters"] = {}
    for target_name, targets in ridge_targets.items():
        print(f"ridge target={target_name}", flush=True)
        scores, regularization, validation_sweep = ridge_scores(
            hidden, targets, dense_winners, splits
        )
        validation = evaluation(scores, dense_winners, splits["validation"])
        test = evaluation(scores, dense_winners, splits["test"])
        result["linearRidgeRouters"][target_name] = {
            "weights": (hidden.shape[1] + 1) * GROUPS,
            "selectedRegularization": regularization,
            "validationSweep": validation_sweep,
            "validation": compact_evaluation(validation),
            "test": compact_evaluation(test),
            "testBreakdown": breakdown(
                scores, dense_winners, splits["test"], sources, lengths
            ),
            "guardedFallback": guarded_fallback(validation, test),
        }

    np.savez_compressed(
        OUTPUT / "states.npz",
        hidden=hidden,
        sources=sources,
        lengths=lengths,
        dense_winners=dense_winners,
        train_ids=splits["train"],
        validation_ids=splits["validation"],
        test_ids=splits["test"],
    )
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "samples": result["samples"],
        "splitSamples": result["splitSamples"],
        "uniqueWinnerGroups": result["uniqueWinnerGroups"],
        "majorityBaselines": result["majorityBaselines"],
        "representativeTest": {
            count: values["test"]
            for count, values in result["representativeRouters"].items()
        },
        "linearRidgeTest": {
            name: values["test"]
            for name, values in result["linearRidgeRouters"].items()
        },
        "results": str((OUTPUT / "results.json").relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
