#!/usr/bin/env python3
"""Screen exact residual-space rotations for the SVG 8-bit backend."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analyze_svg_quantization_strategies import (
    Block,
    exact_forward,
    gelu_new,
    layer_norm,
    load_checkpoint,
    png_weight_quantized,
    quantized_forward,
    quantize_surface,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "experiments" / "svg-w8a8-screen" / "cases" / "cases.json"
DEFAULT_OUT = ROOT / "experiments" / "svg-residual-rotation" / "results.json"
WIDTH = 768


@dataclass(frozen=True)
class RotatedBlock:
    attention_weight: np.ndarray
    attention_bias: np.ndarray
    fc_weight: np.ndarray
    fc_bias: np.ndarray
    projection_weight: np.ndarray
    projection_bias: np.ndarray


def mean_preserving_rotation(seed: int, block_size: int) -> np.ndarray:
    """Return a block-orthogonal matrix R with R @ 1 = 1."""
    if WIDTH % block_size:
        raise ValueError(f"block size {block_size} must divide {WIDTH}")
    rng = np.random.default_rng(seed)
    rotation = np.zeros((WIDTH, WIDTH), dtype=np.float64)
    for start in range(0, WIDTH, block_size):
        mean_axis = np.ones(block_size, dtype=np.float64) / np.sqrt(block_size)
        basis_seed = rng.standard_normal((block_size, block_size))
        basis_seed[:, 0] = mean_axis
        basis, _ = np.linalg.qr(basis_seed)
        if float(basis[:, 0] @ mean_axis) < 0:
            basis[:, 0] *= -1
        signs = rng.choice((-1.0, 1.0), size=block_size)
        signs[0] = 1.0
        rotation[start:start + block_size, start:start + block_size] = (
            basis * signs[None, :]
        ) @ basis.T
    return rotation


def residual_ranges(inputs: np.ndarray, blocks: list[Block]) -> np.ndarray:
    states = inputs.copy()
    ranges = np.max(np.abs(states), axis=0)
    for block in blocks:
        normalized = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        states = states + normalized @ block.attention_weight.T + block.attention_bias
        ranges = np.maximum(ranges, np.max(np.abs(states), axis=0))
        normalized = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in states]
        )
        hidden = gelu_new(normalized @ block.fc_weight.T + block.fc_bias)
        states = states + hidden @ block.projection_weight.T + block.projection_bias
        ranges = np.maximum(ranges, np.max(np.abs(states), axis=0))
    return ranges


def calibrated_spread_rotation(ranges: np.ndarray, block_size: int) -> np.ndarray:
    """Mix each high-range channel with channels from lower range quartiles."""
    if WIDTH % block_size:
        raise ValueError(f"block size {block_size} must divide {WIDTH}")
    ranked = np.argsort(ranges)[::-1]
    group_count = WIDTH // block_size
    rotation = np.zeros((WIDTH, WIDTH), dtype=np.float64)
    spread = np.full((block_size, block_size), 2.0 / block_size)
    spread -= np.eye(block_size)
    for group in range(group_count):
        indices = [ranked[group + band * group_count] for band in range(block_size)]
        rotation[np.ix_(indices, indices)] = spread
    return rotation


def transform_blocks(blocks: list[Block], rotation: np.ndarray) -> list[RotatedBlock]:
    transformed = []
    for block in blocks:
        attention_weight = (
            rotation
            @ (block.attention_weight * block.ln1_gamma[None, :])
            @ rotation.T
        )
        attention_bias = rotation @ (
            block.attention_weight @ block.ln1_beta + block.attention_bias
        )
        fc_weight = (
            block.fc_weight * block.ln2_gamma[None, :]
        ) @ rotation.T
        fc_bias = block.fc_weight @ block.ln2_beta + block.fc_bias
        projection_weight = rotation @ block.projection_weight
        projection_bias = rotation @ block.projection_bias
        transformed.append(
            RotatedBlock(
                attention_weight=attention_weight,
                attention_bias=attention_bias,
                fc_weight=fc_weight,
                fc_bias=fc_bias,
                projection_weight=projection_weight,
                projection_bias=projection_bias,
            )
        )
    return transformed


def base_layer_norm_batch(values: np.ndarray) -> np.ndarray:
    return np.stack([
        layer_norm(value, np.ones(WIDTH), np.zeros(WIDTH)) for value in values
    ])


def exact_rotated_forward(
    inputs: np.ndarray,
    blocks: list[RotatedBlock],
    rotation: np.ndarray,
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
) -> np.ndarray:
    states = inputs @ rotation.T
    for block in blocks:
        normalized = base_layer_norm_batch(states)
        states = states + normalized @ block.attention_weight.T + block.attention_bias
        normalized = base_layer_norm_batch(states)
        hidden = gelu_new(normalized @ block.fc_weight.T + block.fc_bias)
        states = states + hidden @ block.projection_weight.T + block.projection_bias
    normalized = base_layer_norm_batch(states)
    return (normalized @ rotation) * final_gamma + final_beta


def quantized_rotated_forward(
    inputs: np.ndarray,
    blocks: list[RotatedBlock],
    rotation: np.ndarray,
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    groups: int,
) -> tuple[np.ndarray, dict[str, float | int]]:
    surface_errors = []
    surface_max_errors = []

    def materialize(values: np.ndarray) -> np.ndarray:
        result, stats = quantize_surface(values, groups, "uniform")
        surface_errors.append(float(stats["surface_rmse"]))
        surface_max_errors.append(float(stats["surface_max_error"]))
        return result

    def affine(values: np.ndarray, weight: np.ndarray, bias: np.ndarray) -> np.ndarray:
        inputs_quantized = materialize(values)
        weights_quantized = png_weight_quantized(weight)
        return materialize(inputs_quantized @ weights_quantized.T + bias)

    states = materialize(inputs @ rotation.T)
    for block in blocks:
        normalized = base_layer_norm_batch(states)
        learned = affine(normalized, block.attention_weight, block.attention_bias)
        states = materialize(states + learned)
        normalized = base_layer_norm_batch(states)
        pre = affine(normalized, block.fc_weight, block.fc_bias)
        hidden = materialize(gelu_new(pre))
        projected = affine(hidden, block.projection_weight, block.projection_bias)
        states = materialize(states + projected)
    normalized = base_layer_norm_batch(states)
    final = materialize((normalized @ rotation) * final_gamma + final_beta)
    return final, {
        "materializations": len(surface_errors),
        "mean_surface_rmse": float(np.sqrt(np.mean(np.square(surface_errors)))),
        "max_surface_error": float(max(surface_max_errors)),
    }


def summarize(
    name: str,
    actual: np.ndarray,
    expected: np.ndarray,
    embedding: np.ndarray,
    transport: dict[str, float | int],
) -> dict[str, object]:
    error = actual - expected
    winners = np.argmax(actual @ embedding.T, axis=1)
    expected_winners = np.argmax(expected @ embedding.T, axis=1)
    margins = []
    for vector in actual:
        logits = vector @ embedding.T
        top = np.argpartition(logits, -2)[-2:]
        ordered = top[np.argsort(logits[top])]
        margins.append(float(logits[ordered[-1]] - logits[ordered[-2]]))
    return {
        "name": name,
        "rmse": float(np.sqrt(np.mean(error**2))),
        "max_error": float(np.max(np.abs(error))),
        "winner_matches": (winners == expected_winners).tolist(),
        "winner_match_rate": float(np.mean(winners == expected_winners)),
        "winner_ids": winners.tolist(),
        "minimum_logit_margin": min(margins),
        **transport,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--case-count", type=int, default=16)
    parser.add_argument("--calibration-count", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0x524F5441)
    parser.add_argument("--block-size", type=int, default=768)
    parser.add_argument("--rotation", choices=("random", "spread"), default="random")
    parser.add_argument("--groups", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    checkpoint_inputs, embedding, blocks, final_gamma, final_beta = load_checkpoint()
    del checkpoint_inputs
    case_payload = json.loads(args.cases.read_text())
    start = args.calibration_count
    cases = case_payload["cases"][start:start + args.case_count]
    inputs = np.asarray([case["input_expected"] for case in cases], dtype=np.float64)
    if args.calibration_count:
        calibration_cases = case_payload["cases"][:args.calibration_count]
        calibration_inputs = np.asarray(
            [case["input_expected"] for case in calibration_cases], dtype=np.float64
        )
    else:
        calibration_inputs = inputs
    expected = exact_forward(inputs, blocks, final_gamma, final_beta)

    if args.rotation == "spread":
        rotation = calibrated_spread_rotation(
            residual_ranges(calibration_inputs, blocks), args.block_size
        )
    else:
        rotation = mean_preserving_rotation(args.seed, args.block_size)
    orthogonal_error = float(np.max(np.abs(rotation @ rotation.T - np.eye(WIDTH))))
    mean_error = float(np.max(np.abs(rotation @ np.ones(WIDTH) - np.ones(WIDTH))))
    transformed = transform_blocks(blocks, rotation)
    exact_rotated = exact_rotated_forward(
        inputs, transformed, rotation, final_gamma, final_beta
    )
    equivalence_error = float(np.max(np.abs(exact_rotated - expected)))

    baseline_results = []
    results = []
    for groups in args.groups:
        baseline_actual, baseline_transport = quantized_forward(
            inputs,
            blocks,
            final_gamma,
            final_beta,
            groups=groups,
            clustering="uniform",
            alpha=0.0,
        )
        baseline_results.append(summarize(
            f"baseline-uniform-{groups}",
            baseline_actual,
            expected,
            embedding,
            baseline_transport,
        ))
        actual, transport = quantized_rotated_forward(
            inputs,
            transformed,
            rotation,
            final_gamma,
            final_beta,
            groups,
        )
        results.append(summarize(
            f"rotated-uniform-{groups}", actual, expected, embedding, transport
        ))
    payload = {
        "caseCount": len(cases),
        "calibrationCount": args.calibration_count,
        "seed": args.seed,
        "blockSize": args.block_size,
        "rotation": args.rotation,
        "orthogonalError": orthogonal_error,
        "meanPreservationError": mean_error,
        "exactEquivalenceMaxError": equivalence_error,
        "referenceWinnerIds": np.argmax(expected @ embedding.T, axis=1).tolist(),
        "baselineResults": baseline_results,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
