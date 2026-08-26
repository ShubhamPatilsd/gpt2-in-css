#!/usr/bin/env python3
"""Screen activation quantization strategies on the real GPT-2-small checkpoint.

This is deliberately an offline screening model, not a claim to reproduce every
Chromium filter rounding boundary.  It reproduces the important constraints of
the SVG backend:

* signed activations cross 8-bit materialized surfaces;
* matrix weights cross normalized 8-bit PNG surfaces after the project's 9-bit
  row quantization;
* each materialized activation group has one symmetric scale;
* all twelve one-token GPT-2 blocks and the real tied output head are evaluated.

The purpose is to reject bad quantization layouts cheaply before generating a
large HTML/SVG graph and measuring it in Chromium.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "svg-filter-full-block" / "quantization-strategies.json"
WIDTH = 768
LEVELS = 255.0
HEADROOM = 1.08
EPSILON = 1e-5


def layer_norm(
    vector: np.ndarray, gamma: np.ndarray, beta: np.ndarray
) -> np.ndarray:
    mean = np.mean(vector)
    variance = np.mean((vector - mean) ** 2)
    return (vector - mean) / np.sqrt(variance + EPSILON) * gamma + beta


def gelu_new(vector: np.ndarray) -> np.ndarray:
    inner = math.sqrt(2 / math.pi) * (vector + 0.044715 * vector**3)
    return 0.5 * vector * (1 + np.tanh(inner))


@dataclass(frozen=True)
class Block:
    ln1_gamma: np.ndarray
    ln1_beta: np.ndarray
    attention_weight: np.ndarray
    attention_bias: np.ndarray
    ln2_gamma: np.ndarray
    ln2_beta: np.ndarray
    fc_weight: np.ndarray
    fc_bias: np.ndarray
    projection_weight: np.ndarray
    projection_bias: np.ndarray


def row_quantized(weight: np.ndarray) -> np.ndarray:
    """Match the project's 9-bit signed row quantizer."""
    maximum_code = (1 << (9 - 1)) - 1
    maximums = np.max(np.abs(weight), axis=1)
    scales = np.where(maximums == 0, 1.0, maximums / maximum_code)
    codes = np.rint(weight / scales[:, None]).clip(
        -maximum_code, maximum_code
    )
    return codes.astype(np.float64) * scales[:, None]


def png_weight_quantized(weight: np.ndarray) -> np.ndarray:
    """Model the subsequent normalized 8-bit RG weight image."""
    row_scale = np.maximum(np.max(np.abs(weight), axis=1), 1e-12)
    normalized = weight / row_scale[:, None]
    encoded = np.rint(np.abs(normalized) * LEVELS) / LEVELS
    return np.sign(normalized) * encoded * row_scale[:, None]


def load_checkpoint() -> tuple[np.ndarray, np.ndarray, list[Block], np.ndarray, np.ndarray]:
    tensors = SafeTensors(MODEL_PATH)
    embedding = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    position = np.asarray(tensors.tensor("wpe.weight")[0], dtype=np.float64)
    # Preserve the two fixtures used by the browser chain: Hello and its negation.
    initial = embedding[15496] + position
    inputs = np.stack((initial, -initial))
    blocks: list[Block] = []
    for index in range(12):
        prefix = f"h.{index}"
        c_attn_weight = np.asarray(
            tensors.tensor(f"{prefix}.attn.c_attn.weight"), dtype=np.float64
        )
        c_attn_bias = np.asarray(
            tensors.tensor(f"{prefix}.attn.c_attn.bias"), dtype=np.float64
        )
        value_weight = c_attn_weight[:, 2 * WIDTH :].T
        value_bias = c_attn_bias[2 * WIDTH :]
        projection = np.asarray(
            tensors.tensor(f"{prefix}.attn.c_proj.weight"), dtype=np.float64
        ).T
        projection_bias = np.asarray(
            tensors.tensor(f"{prefix}.attn.c_proj.bias"), dtype=np.float64
        )
        blocks.append(
            Block(
                ln1_gamma=np.asarray(
                    tensors.tensor(f"{prefix}.ln_1.weight"), dtype=np.float64
                ),
                ln1_beta=np.asarray(
                    tensors.tensor(f"{prefix}.ln_1.bias"), dtype=np.float64
                ),
                attention_weight=row_quantized(projection @ value_weight),
                attention_bias=projection @ value_bias + projection_bias,
                ln2_gamma=np.asarray(
                    tensors.tensor(f"{prefix}.ln_2.weight"), dtype=np.float64
                ),
                ln2_beta=np.asarray(
                    tensors.tensor(f"{prefix}.ln_2.bias"), dtype=np.float64
                ),
                fc_weight=row_quantized(
                    np.asarray(
                        tensors.tensor(f"{prefix}.mlp.c_fc.weight"), dtype=np.float64
                    ).T
                ),
                fc_bias=np.asarray(
                    tensors.tensor(f"{prefix}.mlp.c_fc.bias"), dtype=np.float64
                ),
                projection_weight=row_quantized(
                    np.asarray(
                        tensors.tensor(f"{prefix}.mlp.c_proj.weight"), dtype=np.float64
                    ).T
                ),
                projection_bias=np.asarray(
                    tensors.tensor(f"{prefix}.mlp.c_proj.bias"), dtype=np.float64
                ),
            )
        )
    final_gamma = np.asarray(tensors.tensor("ln_f.weight"), dtype=np.float64)
    final_beta = np.asarray(tensors.tensor("ln_f.bias"), dtype=np.float64)
    return inputs, embedding, blocks, final_gamma, final_beta


def exact_forward(
    inputs: np.ndarray,
    blocks: list[Block],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
) -> np.ndarray:
    states = inputs.copy()
    for block in blocks:
        normalized = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        states = states + normalized @ block.attention_weight.T + block.attention_bias
        normalized = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in states]
        )
        hidden = gelu_new(normalized @ block.fc_weight.T + block.fc_bias)
        states = states + hidden @ block.projection_weight.T + block.projection_bias
    return np.stack([layer_norm(x, final_gamma, final_beta) for x in states])


def log_kmeans(values: np.ndarray, groups: int, iterations: int = 40) -> np.ndarray:
    """Cluster positive ranges in log2 space and return a group id per channel."""
    logs = np.log2(np.maximum(values, 1e-12))
    if groups == 1:
        return np.zeros(len(logs), dtype=np.int16)
    centers = np.quantile(logs, np.linspace(0, 1, groups))
    ids = np.zeros(len(logs), dtype=np.int16)
    for _ in range(iterations):
        new_ids = np.argmin(np.abs(logs[:, None] - centers[None, :]), axis=1)
        new_centers = centers.copy()
        for group in range(groups):
            members = logs[new_ids == group]
            if len(members):
                new_centers[group] = float(np.mean(members))
        if np.array_equal(new_ids, ids) and np.allclose(new_centers, centers):
            break
        ids = new_ids.astype(np.int16)
        centers = new_centers
    return ids


def log_uniform(values: np.ndarray, groups: int) -> np.ndarray:
    logs = np.log2(np.maximum(values, 1e-12))
    if groups == 1 or float(np.max(logs) - np.min(logs)) < 1e-12:
        return np.zeros(len(logs), dtype=np.int16)
    edges = np.linspace(float(np.min(logs)), float(np.max(logs)), groups + 1)
    return np.clip(
        np.searchsorted(edges, logs, side="right") - 1, 0, groups - 1
    ).astype(np.int16)


def quantize_surface(
    values: np.ndarray,
    groups: int,
    clustering: str,
) -> tuple[np.ndarray, dict[str, float | int]]:
    bounds = np.maximum(np.max(np.abs(values), axis=0) * HEADROOM, 1e-9)
    ids = log_kmeans(bounds, groups) if clustering == "kmeans" else log_uniform(bounds, groups)
    scales = np.empty_like(bounds)
    used = 0
    for group in range(groups):
        mask = ids == group
        if not np.any(mask):
            continue
        used += 1
        scales[mask] = float(np.max(bounds[mask]))
    # CENTER is exactly 128/255 in the SVG implementation, so signed values have
    # 127 usable positive steps and 128 negative steps around the center code.
    encoded = np.clip(np.rint(128.0 + values / (2 * scales) * LEVELS), 0, 255)
    decoded = (encoded - 128.0) / LEVELS * (2 * scales)
    error = decoded - values
    return decoded, {
        "groups_used": used,
        "surface_rmse": float(np.sqrt(np.mean(error**2))),
        "surface_max_error": float(np.max(np.abs(error))),
    }


def smooth_linear(
    activations: np.ndarray,
    weight: np.ndarray,
    bias: np.ndarray,
    groups: int,
    clustering: str,
    alpha: float,
) -> tuple[np.ndarray, dict[str, float | int]]:
    activation_max = np.maximum(np.max(np.abs(activations), axis=0), 1e-8)
    weight_max = np.maximum(np.max(np.abs(weight), axis=0), 1e-8)
    if alpha == 0:
        smooth = np.ones_like(activation_max)
    else:
        smooth = activation_max**alpha / weight_max ** (1.0 - alpha)
        smooth = np.clip(smooth, 1e-5, 1e5)
    transformed_activations, surface = quantize_surface(
        activations / smooth, groups, clustering
    )
    transformed_weight = png_weight_quantized(weight * smooth[None, :])
    return transformed_activations @ transformed_weight.T + bias, surface


def quantized_forward(
    inputs: np.ndarray,
    blocks: list[Block],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    *,
    groups: int,
    clustering: str,
    alpha: float,
) -> tuple[np.ndarray, dict[str, float | int]]:
    states, first = quantize_surface(inputs, groups, clustering)
    surface_squared_error = first["surface_rmse"] ** 2
    surface_count = 1
    max_surface_error = first["surface_max_error"]
    groups_used_total = int(first["groups_used"])

    def materialize(values: np.ndarray) -> np.ndarray:
        nonlocal surface_squared_error, surface_count, max_surface_error, groups_used_total
        result, stats = quantize_surface(values, groups, clustering)
        surface_squared_error += stats["surface_rmse"] ** 2
        surface_count += 1
        max_surface_error = max(max_surface_error, stats["surface_max_error"])
        groups_used_total += int(stats["groups_used"])
        return result

    def affine(values: np.ndarray, weight: np.ndarray, bias: np.ndarray) -> np.ndarray:
        nonlocal surface_squared_error, surface_count, max_surface_error, groups_used_total
        result, stats = smooth_linear(values, weight, bias, groups, clustering, alpha)
        surface_squared_error += stats["surface_rmse"] ** 2
        surface_count += 1
        max_surface_error = max(max_surface_error, stats["surface_max_error"])
        groups_used_total += int(stats["groups_used"])
        return materialize(result)

    for block in blocks:
        normalized = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        learned = affine(normalized, block.attention_weight, block.attention_bias)
        states = materialize(states + learned)
        normalized = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in states]
        )
        pre = affine(normalized, block.fc_weight, block.fc_bias)
        hidden = materialize(gelu_new(pre))
        projected = affine(hidden, block.projection_weight, block.projection_bias)
        states = materialize(states + projected)
    final = materialize(
        np.stack([layer_norm(x, final_gamma, final_beta) for x in states])
    )
    return final, {
        "mean_surface_rmse": float(np.sqrt(surface_squared_error / surface_count)),
        "max_surface_error": float(max_surface_error),
        "materializations": surface_count,
        "mean_groups_used": float(groups_used_total / surface_count),
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
    return {
        "name": name,
        "rmse": float(np.sqrt(np.mean(error**2))),
        "max_error": float(np.max(np.abs(error))),
        "cosine": [
            float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
            for a, b in zip(actual, expected)
        ],
        "winner_ids": winners.tolist(),
        "expected_winner_ids": expected_winners.tolist(),
        "winner_matches": (winners == expected_winners).tolist(),
        **transport,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument(
        "--cases",
        type=Path,
        help="Optional robustness cases.json; uses its unquantized token inputs.",
    )
    parser.add_argument(
        "--quick-32",
        action="store_true",
        help="Run only the retained 32-group logarithmic layout.",
    )
    args = parser.parse_args()
    inputs, embedding, blocks, final_gamma, final_beta = load_checkpoint()
    fixtures: list[str] = ["GPT-2 token 15496 plus position 0", "negated fixture"]
    if args.cases is not None:
        case_payload = json.loads(args.cases.read_text())
        inputs = np.asarray(
            [case["input_expected"] for case in case_payload["cases"]],
            dtype=np.float64,
        )
        fixtures = [
            f'{case["token_id"]}: {case["token"]}' for case in case_payload["cases"]
        ]
    expected = exact_forward(inputs, blocks, final_gamma, final_beta)

    results: list[dict[str, object]] = []
    if args.quick_32:
        actual, transport = quantized_forward(
            inputs,
            blocks,
            final_gamma,
            final_beta,
            groups=32,
            clustering="uniform",
            alpha=0.0,
        )
        results.append(
            summarize(
                "uniform-32-groups-alpha-0",
                actual,
                expected,
                embedding,
                transport,
            )
        )
    # First isolate grouping quality with no SmoothQuant transformation.
    for clustering in (() if args.quick_32 else ("uniform", "kmeans")):
        for groups in (1, 2, 4, 8, 16, 32):
            actual, transport = quantized_forward(
                inputs,
                blocks,
                final_gamma,
                final_beta,
                groups=groups,
                clustering=clustering,
                alpha=0.0,
            )
            results.append(
                summarize(
                    f"{clustering}-{groups}-groups-alpha-0",
                    actual,
                    expected,
                    embedding,
                    transport,
                )
            )

    # Sweep SmoothQuant on the most promising practical group counts. Alpha 0 is
    # already present above; 0.5 is the usual starting point, but GPT-2/SVG may
    # prefer a different activation/weight error tradeoff.
    for groups in (() if args.quick_32 else (4, 8, 16)):
        for alpha in (0.25, 0.5, 0.75, 1.0):
            actual, transport = quantized_forward(
                inputs,
                blocks,
                final_gamma,
                final_beta,
                groups=groups,
                clustering="kmeans",
                alpha=alpha,
            )
            results.append(
                summarize(
                    f"kmeans-{groups}-groups-alpha-{alpha:g}",
                    actual,
                    expected,
                    embedding,
                    transport,
                )
            )

    results.sort(key=lambda item: (not all(item["winner_matches"]), item["rmse"]))
    payload = {
        "model": str(MODEL_PATH),
        "fixtures": fixtures,
        "scope": "offline SVG 8-bit materialization screen; confirm finalists in Chromium",
        "reference_winner_ids": np.argmax(expected @ embedding.T, axis=1).tolist(),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
