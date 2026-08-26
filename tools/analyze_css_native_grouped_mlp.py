#!/usr/bin/env python3
"""Train an offline 12-font-compatible grouped student for GPT-2 block-0 MLP.

The student preserves the transport-oriented topology required by Chromium's
256-axis font limit: every one of 12 groups has 256 inputs, 256 hidden units,
and all 768 outputs.  The groups sum before the block residual is updated.

Run a quick end-to-end check with::

    CSS_GROUPED_MLP_SMOKE=1 uv run --with torch --with numpy \
      python tools/analyze_css_native_grouped_mlp.py

Important environment variables (smoke defaults are selected by the flag):

* CSS_GROUPED_MLP_SAMPLES: total corpus samples (default 768; smoke 48)
* CSS_GROUPED_MLP_STEPS: optimizer steps (default 300; smoke 2)
* CSS_GROUPED_MLP_BATCH_SIZE: training batch size (default 64; smoke 8)
* CSS_GROUPED_MLP_CONTEXT_LENGTHS: comma-separated lengths (default 8,16,32,64)
* CSS_GROUPED_MLP_DEVICE: auto, mps, cuda, or cpu
* CSS_GROUPED_MLP_SEED: deterministic seed (default 20260914)
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_pretrained_gpt2 import Gpt2Tokenizer


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "data" / "gpt2"
OUTPUT = ROOT / "experiments" / "css-native-grouped-mlp"
GROUPS = 12
INPUTS_PER_GROUP = 256
HIDDEN_PER_GROUP = 256
WIDTH = 768
HIDDEN = 3072
HEADS = 12
HEAD_WIDTH = 64
EPSILON = 1e-5

LOCAL_TEXT_FILES: dict[str, tuple[Path, ...]] = {
    "train": (
        ROOT / "README.md",
        ROOT / "OPTIMIZATIONS.md",
    ),
    "validation": (
        ROOT / "FULL_GPT2.md",
    ),
    "test": (
        ROOT / "MODEL_CANDIDATES.md",
        ROOT / "experiments" / "CSS_TOKENIZER_FEASIBILITY.md",
    ),
}


@dataclass(frozen=True)
class Config:
    smoke: bool
    samples: int
    steps: int
    batch_size: int
    corpus_batch_size: int
    context_lengths: tuple[int, ...]
    learning_rate: float
    seed: int
    device: str
    clustering_rounds: int


@dataclass(frozen=True)
class ContextRecord:
    sample_id: str
    split: str
    kind: str
    source: str
    tokens: np.ndarray
    token_hash: str


@dataclass
class BlockWeights:
    wte: np.ndarray
    wpe: np.ndarray
    ln1_weight: np.ndarray
    ln1_bias: np.ndarray
    qkv_weight: np.ndarray
    qkv_bias: np.ndarray
    attn_proj_weight: np.ndarray
    attn_proj_bias: np.ndarray
    ln2_weight: np.ndarray
    ln2_bias: np.ndarray
    fc_weight: np.ndarray
    fc_bias: np.ndarray
    proj_weight: np.ndarray
    proj_bias: np.ndarray


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    smoke = env_flag("CSS_GROUPED_MLP_SMOKE")
    default_lengths = "8,16" if smoke else "8,16,32,64"
    context_lengths = tuple(
        int(value.strip())
        for value in os.environ.get(
            "CSS_GROUPED_MLP_CONTEXT_LENGTHS", default_lengths
        ).split(",")
        if value.strip()
    )
    config = Config(
        smoke=smoke,
        samples=int(os.environ.get("CSS_GROUPED_MLP_SAMPLES", "48" if smoke else "768")),
        steps=int(os.environ.get("CSS_GROUPED_MLP_STEPS", "2" if smoke else "300")),
        batch_size=int(
            os.environ.get("CSS_GROUPED_MLP_BATCH_SIZE", "8" if smoke else "64")
        ),
        corpus_batch_size=int(
            os.environ.get("CSS_GROUPED_MLP_CORPUS_BATCH_SIZE", "4" if smoke else "12")
        ),
        context_lengths=context_lengths,
        learning_rate=float(os.environ.get("CSS_GROUPED_MLP_LR", "0.0003")),
        seed=int(os.environ.get("CSS_GROUPED_MLP_SEED", "20260914")),
        device=os.environ.get("CSS_GROUPED_MLP_DEVICE", "auto").lower(),
        clustering_rounds=int(os.environ.get("CSS_GROUPED_MLP_CLUSTER_ROUNDS", "4")),
    )
    if config.samples < 30:
        raise ValueError("CSS_GROUPED_MLP_SAMPLES must be at least 30")
    if config.steps < 0 or config.batch_size < 1 or config.corpus_batch_size < 1:
        raise ValueError("steps must be nonnegative and batch sizes must be positive")
    if not config.context_lengths:
        raise ValueError("at least one context length is required")
    if min(config.context_lengths) < 8 or max(config.context_lengths) > 1024:
        raise ValueError("context lengths must be between 8 and 1024")
    if config.device not in {"auto", "mps", "cuda", "cpu"}:
        raise ValueError("CSS_GROUPED_MLP_DEVICE must be auto, mps, cuda, or cpu")
    return config


def tensor_copy(tensors: SafeTensors, name: str) -> np.ndarray:
    return np.array(tensors.tensor(name), dtype=np.float32, copy=True)


def load_weights() -> BlockWeights:
    if MODEL_PATH != CHECKPOINT / "model.safetensors":
        raise RuntimeError(f"unexpected model helper path: {MODEL_PATH}")
    tensors = SafeTensors(MODEL_PATH)
    weights = BlockWeights(
        wte=tensors.tensor("wte.weight"),
        wpe=tensor_copy(tensors, "wpe.weight"),
        ln1_weight=tensor_copy(tensors, "h.0.ln_1.weight"),
        ln1_bias=tensor_copy(tensors, "h.0.ln_1.bias"),
        qkv_weight=tensor_copy(tensors, "h.0.attn.c_attn.weight"),
        qkv_bias=tensor_copy(tensors, "h.0.attn.c_attn.bias"),
        attn_proj_weight=tensor_copy(tensors, "h.0.attn.c_proj.weight"),
        attn_proj_bias=tensor_copy(tensors, "h.0.attn.c_proj.bias"),
        ln2_weight=tensor_copy(tensors, "h.0.ln_2.weight"),
        ln2_bias=tensor_copy(tensors, "h.0.ln_2.bias"),
        fc_weight=tensor_copy(tensors, "h.0.mlp.c_fc.weight"),
        fc_bias=tensor_copy(tensors, "h.0.mlp.c_fc.bias"),
        proj_weight=tensor_copy(tensors, "h.0.mlp.c_proj.weight"),
        proj_bias=tensor_copy(tensors, "h.0.mlp.c_proj.bias"),
    )
    expected = {
        "wpe": (1024, WIDTH),
        "qkv_weight": (WIDTH, 3 * WIDTH),
        "fc_weight": (WIDTH, HIDDEN),
        "proj_weight": (HIDDEN, WIDTH),
    }
    for name, shape in expected.items():
        if getattr(weights, name).shape != shape:
            raise ValueError(f"{name} shape {getattr(weights, name).shape} != {shape}")
    return weights


def layer_norm(values: np.ndarray, weight: np.ndarray, bias: np.ndarray) -> np.ndarray:
    centered = values - values.mean(axis=-1, keepdims=True)
    variance = np.mean(centered * centered, axis=-1, keepdims=True)
    return centered / np.sqrt(variance + EPSILON) * weight + bias


def gelu(values: np.ndarray) -> np.ndarray:
    return 0.5 * values * (
        1.0
        + np.tanh(np.sqrt(2.0 / np.pi) * (values + 0.044715 * values**3))
    )


def token_hash(tokens: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(tokens, dtype="<i4").tobytes()).hexdigest()


def split_counts(total: int) -> dict[str, int]:
    validation = max(10, total // 5)
    test = max(10, total // 5)
    train = total - validation - test
    if train < 10:
        raise ValueError("sample count is too small for isolated train/validation/test splits")
    return {"train": train, "validation": validation, "test": test}


def load_text_streams(tokenizer: Gpt2Tokenizer) -> dict[str, list[tuple[str, np.ndarray]]]:
    streams: dict[str, list[tuple[str, np.ndarray]]] = {}
    for split, paths in LOCAL_TEXT_FILES.items():
        split_streams = []
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f"required local text source is missing: {path}")
            tokens = np.asarray(tokenizer.encode(path.read_text()), dtype=np.int64)
            split_streams.append((str(path.relative_to(ROOT)), tokens))
        streams[split] = split_streams
    return streams


def make_corpus(config: Config) -> tuple[list[ContextRecord], dict[str, Any]]:
    tokenizer = Gpt2Tokenizer(CHECKPOINT / "vocab.json", CHECKPOINT / "merges.txt")
    streams = load_text_streams(tokenizer)
    counts = split_counts(config.samples)
    records: list[ContextRecord] = []
    used_token_hashes: set[str] = set()
    seed_offsets = {"train": 101, "validation": 211, "test": 307}

    for split, count in counts.items():
        random_count = count // 2
        kind_counts = {"uniform-random": random_count, "local-text": count - random_count}
        rng = np.random.default_rng(config.seed + seed_offsets[split])
        for kind, kind_count in kind_counts.items():
            accepted = 0
            attempts = 0
            while accepted < kind_count:
                attempts += 1
                if attempts > max(1000, 50 * kind_count):
                    raise RuntimeError(f"could not create unique {kind} contexts for {split}")
                length = config.context_lengths[accepted % len(config.context_lengths)]
                if kind == "uniform-random":
                    tokens = rng.integers(0, 50_257, size=length, dtype=np.int64)
                    source = f"rng-seed-{config.seed + seed_offsets[split]}"
                else:
                    eligible = [item for item in streams[split] if len(item[1]) >= length]
                    if not eligible:
                        raise RuntimeError(f"no {split} text source supports length {length}")
                    source, stream = eligible[accepted % len(eligible)]
                    start = int(rng.integers(0, len(stream) - length + 1))
                    tokens = np.array(stream[start : start + length], copy=True)
                digest = token_hash(tokens)
                if digest in used_token_hashes:
                    continue
                used_token_hashes.add(digest)
                records.append(
                    ContextRecord(
                        sample_id=f"{split}-{kind}-{accepted:05d}",
                        split=split,
                        kind=kind,
                        source=source,
                        tokens=tokens,
                        token_hash=digest,
                    )
                )
                accepted += 1

    isolation = validate_split_isolation(records)
    summary: dict[str, Any] = {
        "totalSamples": len(records),
        "splitCounts": counts,
        "bySplitAndKind": {
            split: {
                kind: sum(r.split == split and r.kind == kind for r in records)
                for kind in ("uniform-random", "local-text")
            }
            for split in counts
        },
        "contextLengths": list(config.context_lengths),
        "textSources": {
            split: [source for source, _tokens in split_streams]
            for split, split_streams in streams.items()
        },
        "isolation": isolation,
    }
    return records, summary


def validate_split_isolation(records: list[ContextRecord]) -> dict[str, Any]:
    splits = ("train", "validation", "test")
    ids = [record.sample_id for record in records]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate corpus sample IDs")
    hashes = {
        split: {record.token_hash for record in records if record.split == split}
        for split in splits
    }
    text_sources = {
        split: {
            record.source
            for record in records
            if record.split == split and record.kind == "local-text"
        }
        for split in splits
    }
    for split in splits:
        kinds = {record.kind for record in records if record.split == split}
        if kinds != {"uniform-random", "local-text"}:
            raise AssertionError(f"split {split} does not contain both corpus kinds: {kinds}")
    overlaps: dict[str, Any] = {}
    for left_index, left in enumerate(splits):
        for right in splits[left_index + 1 :]:
            key = f"{left}:{right}"
            token_overlap = hashes[left] & hashes[right]
            source_overlap = text_sources[left] & text_sources[right]
            overlaps[key] = {
                "tokenContextHashes": len(token_overlap),
                "localTextSources": len(source_overlap),
            }
            if token_overlap or source_overlap:
                raise AssertionError(f"split isolation failed for {key}: {overlaps[key]}")
    return {
        "passed": True,
        "checks": [
            "sample IDs are globally unique",
            "token-sequence hashes do not cross splits",
            "local text source files do not cross splits",
            "each split contains both random-token and local-text contexts",
        ],
        "pairwiseOverlapCounts": overlaps,
    }


def exact_block0_batch(
    tokens: np.ndarray, weights: BlockWeights
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    batch, length = tokens.shape
    states = np.asarray(weights.wte[tokens], dtype=np.float32)
    states = states + weights.wpe[None, :length, :]
    normalized = layer_norm(states, weights.ln1_weight, weights.ln1_bias)
    qkv = normalized.reshape(batch * length, WIDTH) @ weights.qkv_weight
    qkv = (qkv + weights.qkv_bias).reshape(batch, length, 3, HEADS, HEAD_WIDTH)
    query = qkv[:, -1, 0]
    key = qkv[:, :, 1]
    value = qkv[:, :, 2]
    scores = np.einsum("bhd,blhd->bhl", query, key) / math.sqrt(HEAD_WIDTH)
    scores -= scores.max(axis=-1, keepdims=True)
    probabilities = np.exp(scores)
    probabilities /= probabilities.sum(axis=-1, keepdims=True)
    attended = np.einsum("bhl,blhd->bhd", probabilities, value).reshape(batch, WIDTH)
    post_attention = (
        states[:, -1] + attended @ weights.attn_proj_weight + weights.attn_proj_bias
    )
    mlp_input = layer_norm(post_attention, weights.ln2_weight, weights.ln2_bias)
    hidden = gelu(mlp_input @ weights.fc_weight + weights.fc_bias)
    teacher_output = hidden @ weights.proj_weight + weights.proj_bias
    return (
        mlp_input.astype(np.float32),
        post_attention.astype(np.float32),
        teacher_output.astype(np.float32),
    )


def evaluate_corpus(
    records: list[ContextRecord], weights: BlockWeights, batch_size: int
) -> dict[str, dict[str, np.ndarray]]:
    by_split: dict[str, dict[str, list[np.ndarray]]] = {
        split: {"inputs": [], "residuals": [], "targets": []}
        for split in ("train", "validation", "test")
    }
    lengths = sorted({len(record.tokens) for record in records})
    for length in lengths:
        length_records = [record for record in records if len(record.tokens) == length]
        for start in range(0, len(length_records), batch_size):
            batch_records = length_records[start : start + batch_size]
            tokens = np.stack([record.tokens for record in batch_records])
            inputs, residuals, targets = exact_block0_batch(tokens, weights)
            for index, record in enumerate(batch_records):
                by_split[record.split]["inputs"].append(inputs[index])
                by_split[record.split]["residuals"].append(residuals[index])
                by_split[record.split]["targets"].append(targets[index])
    return {
        split: {name: np.stack(rows) for name, rows in arrays.items()}
        for split, arrays in by_split.items()
    }


def balanced_assignment(scores: np.ndarray) -> np.ndarray:
    """Greedily maximize group score while enforcing exactly 256 units/group."""
    if scores.shape != (HIDDEN, GROUPS):
        raise ValueError(f"unexpected assignment score shape: {scores.shape}")
    preferences = np.argsort(-scores, axis=1, kind="stable")
    sorted_scores = np.take_along_axis(scores, preferences, axis=1)
    margins = sorted_scores[:, 0] - sorted_scores[:, 1]
    order = np.lexsort((np.arange(HIDDEN), -margins))
    capacities = np.full(GROUPS, HIDDEN_PER_GROUP, dtype=np.int64)
    labels = np.full(HIDDEN, -1, dtype=np.int64)
    for unit in order:
        for group in preferences[unit]:
            if capacities[group] > 0:
                labels[unit] = group
                capacities[group] -= 1
                break
    if np.any(labels < 0) or np.any(capacities != 0):
        raise AssertionError("balanced assignment did not fill all groups")
    return labels


def initialize_groups(
    fc_weight: np.ndarray, rounds: int
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Deterministically co-cluster hidden units and retained input coordinates.

    Squared c_fc weights are normalized into per-unit input-energy signatures.
    A fixed projection gives an initial balanced ordering.  Alternating updates
    then choose each group's 256 highest aggregate-energy inputs and reassign
    hidden units by captured-energy fraction under exact 256-unit capacities.
    """
    energy = np.square(fc_weight.astype(np.float64)).T  # hidden x input
    totals = np.maximum(energy.sum(axis=1), np.finfo(np.float64).tiny)
    signatures = energy / totals[:, None]
    coordinate = np.arange(WIDTH, dtype=np.float64)
    fixed_projection = np.sin((coordinate + 1.0) * math.sqrt(2.0))
    fixed_projection += 0.5 * np.cos((coordinate + 1.0) * math.sqrt(3.0))
    ordering = np.argsort(signatures @ fixed_projection, kind="stable")
    labels = np.empty(HIDDEN, dtype=np.int64)
    for group in range(GROUPS):
        labels[ordering[group * HIDDEN_PER_GROUP : (group + 1) * HIDDEN_PER_GROUP]] = group

    subsets = np.empty((GROUPS, INPUTS_PER_GROUP), dtype=np.int64)
    for _ in range(max(1, rounds)):
        for group in range(GROUPS):
            group_energy = energy[labels == group].sum(axis=0)
            top = np.argsort(-group_energy, kind="stable")[:INPUTS_PER_GROUP]
            subsets[group] = np.sort(top)
        captured = np.stack([energy[:, subset].sum(axis=1) for subset in subsets], axis=1)
        labels = balanced_assignment(captured / totals[:, None])

    for group in range(GROUPS):
        group_energy = energy[labels == group].sum(axis=0)
        subsets[group] = np.sort(
            np.argsort(-group_energy, kind="stable")[:INPUTS_PER_GROUP]
        )
    hidden_groups = np.stack([np.flatnonzero(labels == group) for group in range(GROUPS)])
    if hidden_groups.shape != (GROUPS, HIDDEN_PER_GROUP):
        raise AssertionError(f"hidden grouping is not balanced: {hidden_groups.shape}")
    retained = sum(
        energy[hidden_groups[group]][:, subsets[group]].sum()
        for group in range(GROUPS)
    )
    all_inputs = np.concatenate(subsets)
    pair_overlaps = [
        len(np.intersect1d(subsets[left], subsets[right], assume_unique=True))
        for left in range(GROUPS)
        for right in range(left + 1, GROUPS)
    ]
    report = {
        "method": "balanced alternating c_fc input-energy co-clustering",
        "rounds": max(1, rounds),
        "hiddenUnitsPerGroup": [int(len(group)) for group in hidden_groups],
        "inputsPerGroup": [int(len(group)) for group in subsets],
        "retainedRestrictedCfcWeightEnergyFraction": float(retained / energy.sum()),
        "distinctInputCoordinatesAcrossGroups": int(len(np.unique(all_inputs))),
        "meanPairwiseInputOverlap": float(np.mean(pair_overlaps)),
        "maximumPairwiseInputOverlap": int(max(pair_overlaps)),
        "inputSubsets": subsets.tolist(),
        "hiddenUnitGroups": hidden_groups.tolist(),
    }
    return hidden_groups, subsets, report


def import_torch() -> Any:
    try:
        import torch
    except ImportError as error:
        raise SystemExit(
            "PyTorch is required. Run with: uv run --with torch --with numpy "
            "python tools/analyze_css_native_grouped_mlp.py"
        ) from error
    return torch


def choose_device(torch: Any, requested: str) -> str:
    if requested == "auto":
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    if requested == "mps" and not torch.backends.mps.is_available():
        print("MPS requested but unavailable; falling back to CPU", file=sys.stderr)
        return "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        print("CUDA requested but unavailable; falling back to CPU", file=sys.stderr)
        return "cpu"
    return requested


def build_model(
    torch: Any,
    weights: BlockWeights,
    hidden_groups: np.ndarray,
    subsets: np.ndarray,
) -> Any:
    class GroupedMLP(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            a = np.stack(
                [
                    weights.fc_weight[np.ix_(subsets[group], hidden_groups[group])]
                    for group in range(GROUPS)
                ]
            )
            b = np.stack(
                [weights.proj_weight[hidden_groups[group]] for group in range(GROUPS)]
            )
            a_bias = np.stack(
                [weights.fc_bias[hidden_groups[group]] for group in range(GROUPS)]
            )
            self.a = torch.nn.Parameter(torch.from_numpy(a.astype(np.float32)))
            self.a_bias = torch.nn.Parameter(torch.from_numpy(a_bias.astype(np.float32)))
            self.b = torch.nn.Parameter(torch.from_numpy(b.astype(np.float32)))
            self.output_bias = torch.nn.Parameter(torch.from_numpy(weights.proj_bias.copy()))
            self.register_buffer("subsets", torch.from_numpy(subsets.astype(np.int64)))

        def forward(self, values: Any) -> Any:
            selected = values[:, self.subsets]
            preactivation = torch.einsum("bgk,gkh->bgh", selected, self.a)
            preactivation = preactivation + self.a_bias[None, :, :]
            hidden = 0.5 * preactivation * (
                1.0
                + torch.tanh(
                    math.sqrt(2.0 / math.pi)
                    * (preactivation + 0.044715 * preactivation.pow(3))
                )
            )
            return torch.einsum("bgh,gho->bo", hidden, self.b) + self.output_bias

    return GroupedMLP()


def output_metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float]:
    error = prediction.astype(np.float64) - target.astype(np.float64)
    rmse = math.sqrt(float(np.mean(np.square(error))))
    target_rms = math.sqrt(float(np.mean(np.square(target.astype(np.float64)))))
    numerator = np.sum(prediction.astype(np.float64) * target.astype(np.float64), axis=1)
    denominator = np.linalg.norm(prediction.astype(np.float64), axis=1) * np.linalg.norm(
        target.astype(np.float64), axis=1
    )
    cosine = numerator / np.maximum(denominator, np.finfo(np.float64).tiny)
    return {
        "rmse": rmse,
        "relativeRmse": rmse / max(target_rms, np.finfo(np.float64).tiny),
        "meanCosineSimilarity": float(np.mean(cosine)),
        "maximumAbsoluteError": float(np.max(np.abs(error))),
        "p99AbsoluteError": float(np.quantile(np.abs(error), 0.99)),
        "referenceRms": target_rms,
    }


def evaluate_prediction(
    prediction: np.ndarray, arrays: dict[str, np.ndarray]
) -> dict[str, Any]:
    target = arrays["targets"]
    residual = arrays["residuals"]
    return {
        "samples": int(len(target)),
        "mlpOutput": output_metrics(prediction, target),
        "completeBlockResidual": output_metrics(residual + prediction, residual + target),
    }


def predict(
    torch: Any, model: Any, values: np.ndarray, device: str, batch_size: int
) -> np.ndarray:
    rows = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(values), batch_size):
            batch = torch.from_numpy(values[start : start + batch_size]).to(device)
            rows.append(model(batch).detach().cpu().numpy())
    return np.concatenate(rows)


def train_student(
    torch: Any,
    model: Any,
    corpus: dict[str, dict[str, np.ndarray]],
    config: Config,
    device: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    model.to(device)
    initial = {
        split: evaluate_prediction(
            predict(torch, model, corpus[split]["inputs"], device, config.batch_size),
            corpus[split],
        )
        for split in ("train", "validation", "test")
    }
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    train_inputs = torch.from_numpy(corpus["train"]["inputs"]).to(device)
    train_targets = torch.from_numpy(corpus["train"]["targets"]).to(device)
    order_rng = np.random.default_rng(config.seed + 401)
    best_state = copy.deepcopy(model.state_dict())
    best_validation = initial["validation"]["mlpOutput"]["rmse"]
    history: list[dict[str, float | int]] = []
    validation_interval = max(1, config.steps // 10)
    start_time = time.perf_counter()

    for step in range(1, config.steps + 1):
        indices = order_rng.integers(0, len(train_inputs), size=config.batch_size)
        batch_ids = torch.from_numpy(indices.astype(np.int64)).to(device)
        optimizer.zero_grad(set_to_none=True)
        prediction = model(train_inputs[batch_ids])
        loss = torch.mean((prediction - train_targets[batch_ids]) ** 2)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step == 1 or step == config.steps or step % validation_interval == 0:
            validation_prediction = predict(
                torch, model, corpus["validation"]["inputs"], device, config.batch_size
            )
            validation_rmse = output_metrics(
                validation_prediction, corpus["validation"]["targets"]
            )["rmse"]
            history.append(
                {
                    "step": step,
                    "trainingBatchMse": float(loss.detach().cpu()),
                    "validationRmse": validation_rmse,
                }
            )
            if validation_rmse < best_validation:
                best_validation = validation_rmse
                best_state = copy.deepcopy(model.state_dict())

    elapsed = time.perf_counter() - start_time
    model.load_state_dict(best_state)
    trained = {
        split: evaluate_prediction(
            predict(torch, model, corpus[split]["inputs"], device, config.batch_size),
            corpus[split],
        )
        for split in ("train", "validation", "test")
    }
    training = {
        "optimizer": "Adam",
        "learningRate": config.learning_rate,
        "stepsRequested": config.steps,
        "batchSize": config.batch_size,
        "gradientClipNorm": 1.0,
        "bestValidationRmse": best_validation,
        "elapsedSeconds": elapsed,
        "history": history,
    }
    return {"initialization": initial, "trained": trained}, training


def browser_projection_estimate() -> dict[str, Any]:
    source = ROOT / "experiments" / "avar2-hvar-mlp-scaling" / "browser-results.json"
    measured = json.loads(source.read_text())
    row = next(item for item in measured["results"] if item["size"] == INPUTS_PER_GROUP)
    per_font = float(row["mutationMedianMilliseconds"])
    estimate = GROUPS * per_font
    return {
        "estimatedMilliseconds": estimate,
        "gateMilliseconds": 80.0,
        "passesEstimate": estimate <= 80.0,
        "measuredForThisArchitecture": False,
        "method": "12 groups times the prior 256-axis square-font warm mutation median",
        "source": str(source.relative_to(ROOT)),
        "source256AxisMedianMilliseconds": per_font,
        "sensitivityIfCostTriplesWith768OutputRowsMilliseconds": 3.0 * estimate,
        "caveat": (
            "This is an optimistic topology estimate, not a browser measurement. "
            "Each proposed font has 768 rather than 256 output rows; font scheduling, "
            "larger HVAR data, summation, and the 768-value geometry handoff are omitted."
        ),
    }


def result_markdown(results: dict[str, Any]) -> str:
    test_initial = results["evaluation"]["initialization"]["test"]
    test_trained = results["evaluation"]["trained"]["test"]
    gates = results["decisionGates"]
    config = results["configuration"]

    def percent(value: float) -> str:
        return f"{100.0 * value:.3f}%"

    def gate_word(passed: bool) -> str:
        return "PASS" if passed else "FAIL"

    qualification = (
        "This was a smoke run. It validates the complete pipeline but is not a "
        "decision-quality fit."
        if config["smoke"]
        else "This was the configured full experiment run."
    )
    overall = "PASS" if gates["allPassed"] else "FAIL"
    return f"""# CSS-native grouped GPT-2 MLP feasibility

## Outcome

{qualification} The configured three-gate decision is **{overall}**. The
architecture removes the 3,072-scalar external activation boundary: twelve
independent 256-input/256-hidden groups each produce 768 outputs, and only the
summed 768-vector crosses into geometry.

| Held-out test metric | Restricted-teacher initialization | Trained |
| --- | ---: | ---: |
| MLP output RMSE | {test_initial['mlpOutput']['rmse']:.6f} | {test_trained['mlpOutput']['rmse']:.6f} |
| MLP output relative RMSE | {percent(test_initial['mlpOutput']['relativeRmse'])} | {percent(test_trained['mlpOutput']['relativeRmse'])} |
| MLP output cosine | {test_initial['mlpOutput']['meanCosineSimilarity']:.6f} | {test_trained['mlpOutput']['meanCosineSimilarity']:.6f} |
| MLP output maximum error | {test_initial['mlpOutput']['maximumAbsoluteError']:.6f} | {test_trained['mlpOutput']['maximumAbsoluteError']:.6f} |
| Complete block relative RMSE | {percent(test_initial['completeBlockResidual']['relativeRmse'])} | {percent(test_trained['completeBlockResidual']['relativeRmse'])} |
| Complete block cosine | {test_initial['completeBlockResidual']['meanCosineSimilarity']:.6f} | {test_trained['completeBlockResidual']['meanCosineSimilarity']:.6f} |
| Complete block maximum error | {test_initial['completeBlockResidual']['maximumAbsoluteError']:.6f} | {test_trained['completeBlockResidual']['maximumAbsoluteError']:.6f} |

## Decision gates

| Gate | Result | Status |
| --- | ---: | :---: |
| Held-out MLP-output relative RMSE <= 5% | {percent(gates['mlpOutputRelativeRmse']['actual'])} | {gate_word(gates['mlpOutputRelativeRmse']['passed'])} |
| Held-out complete-block relative RMSE <= 2% | {percent(gates['completeBlockRelativeRmse']['actual'])} | {gate_word(gates['completeBlockRelativeRmse']['passed'])} |
| Browser projection estimate <= 80 ms | {gates['browserProjectionEstimate']['actualMilliseconds']:.2f} ms | {gate_word(gates['browserProjectionEstimate']['passed'])} |

The browser number is **an estimate, not a measurement of this architecture**.
It multiplies the existing 256-axis square-font warm median by 12. It is
optimistic because each proposed group has 768 output rows, and it excludes
font scheduling, group summation, and the final 768-value geometry handoff. A
simple 3x output-row sensitivity is
{results['browserProjectionEstimate']['sensitivityIfCostTriplesWith768OutputRowsMilliseconds']:.2f} ms.
The browser gate must therefore be confirmed with a generated-font browser
probe before an architecture decision can rely on it.

## Corpus and isolation

The run used {results['corpus']['totalSamples']} block-0 post-attention `ln_2`
inputs: {results['corpus']['bySplitAndKind']['train']['uniform-random'] + results['corpus']['bySplitAndKind']['validation']['uniform-random'] + results['corpus']['bySplitAndKind']['test']['uniform-random']}
uniform-random token contexts and
{results['corpus']['bySplitAndKind']['train']['local-text'] + results['corpus']['bySplitAndKind']['validation']['local-text'] + results['corpus']['bySplitAndKind']['test']['local-text']}
local-text contexts. Train/validation/test token-sequence hashes are disjoint,
and local text files are assigned to only one split. Split-isolation checks
passed.

## Initialization and training

Hidden units were balanced at exactly 256 per group by alternating deterministic
co-clustering on squared `c_fc` input-weight energy. Each group then retained
its 256 highest aggregate-energy input coordinates. Restricted checkpoint
`c_fc`/`c_proj` weights and biases were copied directly before Adam fine-tuning.
The selected coordinates retain
{percent(results['grouping']['retainedRestrictedCfcWeightEnergyFraction'])} of
`c_fc` weight energy for their assigned hidden units.

Training used {config['steps']} steps on `{results['runtime']['device']}` with a
batch size of {config['batchSize']}. Exact teacher targets use the checkpoint's
full 768->3,072->768 MLP and GPT-2 tanh GELU. See `results.json` for per-split
metrics, all coordinate/unit assignments, optimizer history, and provenance.

## Reproduce

```sh
CSS_GROUPED_MLP_SMOKE=1 uv run --with torch --with numpy python tools/analyze_css_native_grouped_mlp.py
```

For the default full run, omit `CSS_GROUPED_MLP_SMOKE=1`. Sample count, optimizer
steps, context lengths, batch sizes, seed, learning rate, and device are exposed
through the environment variables documented at the top of the script.
"""


def main() -> None:
    config = load_config()
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch = import_torch()
    torch.manual_seed(config.seed)
    try:
        torch.use_deterministic_algorithms(True)
    except (AttributeError, RuntimeError):
        pass
    device = choose_device(torch, config.device)
    print(f"configuration: samples={config.samples}, steps={config.steps}, device={device}")

    weights = load_weights()
    print("building isolated random-token and local-text corpus")
    records, corpus_report = make_corpus(config)
    corpus = evaluate_corpus(records, weights, config.corpus_batch_size)
    print("co-clustering 3,072 hidden units into 12 balanced groups")
    hidden_groups, subsets, grouping = initialize_groups(
        weights.fc_weight, config.clustering_rounds
    )
    model = build_model(torch, weights, hidden_groups, subsets)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    print(f"evaluating initialization and training {parameter_count:,} parameters")
    evaluation, training = train_student(torch, model, corpus, config, device)
    browser = browser_projection_estimate()
    trained_test = evaluation["trained"]["test"]
    mlp_relative = trained_test["mlpOutput"]["relativeRmse"]
    block_relative = trained_test["completeBlockResidual"]["relativeRmse"]
    gates = {
        "mlpOutputRelativeRmse": {
            "threshold": 0.05,
            "actual": mlp_relative,
            "passed": mlp_relative <= 0.05,
        },
        "completeBlockRelativeRmse": {
            "threshold": 0.02,
            "actual": block_relative,
            "passed": block_relative <= 0.02,
        },
        "browserProjectionEstimate": {
            "thresholdMilliseconds": 80.0,
            "actualMilliseconds": browser["estimatedMilliseconds"],
            "passed": browser["passesEstimate"],
            "measuredForThisArchitecture": False,
        },
    }
    gates["allPassed"] = all(
        gate["passed"] for gate in gates.values() if isinstance(gate, dict)
    )
    results = {
        "experiment": "css-native-grouped-gpt2-block0-mlp",
        "model": "local data/gpt2/model.safetensors",
        "architecture": {
            "groups": GROUPS,
            "inputsPerGroup": INPUTS_PER_GROUP,
            "hiddenUnitsPerGroup": HIDDEN_PER_GROUP,
            "outputsPerGroup": WIDTH,
            "geometryBoundaryScalars": WIDTH,
            "externalHiddenBoundaryScalars": 0,
            "formula": "sum_g B_g * GELU(A_g * x[S_g] + a_g) + output_bias",
            "trainableParameters": parameter_count,
        },
        "configuration": {
            "smoke": config.smoke,
            "samples": config.samples,
            "steps": config.steps,
            "batchSize": config.batch_size,
            "corpusBatchSize": config.corpus_batch_size,
            "contextLengths": list(config.context_lengths),
            "learningRate": config.learning_rate,
            "seed": config.seed,
            "requestedDevice": config.device,
            "clusteringRounds": config.clustering_rounds,
        },
        "runtime": {
            "device": device,
            "torchVersion": torch.__version__,
            "numpyVersion": np.__version__,
        },
        "corpus": corpus_report,
        "grouping": grouping,
        "training": training,
        "evaluation": evaluation,
        "browserProjectionEstimate": browser,
        "decisionGates": gates,
        "decisionQuality": "smoke-only" if config.smoke else "configured-full-run",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (OUTPUT / "RESULTS.md").write_text(result_markdown(results))
    print(json.dumps({"decisionGates": gates, "output": str(OUTPUT)}, indent=2))


if __name__ == "__main__":
    main()
