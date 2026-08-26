#!/usr/bin/env python3
"""Screen fixed activation precision across all 12 one-token GPT-2 blocks."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from analyze_svg_quantization_strategies import (
    exact_forward,
    gelu_new,
    layer_norm,
    load_checkpoint,
)
from analyze_full_gpt2 import MODEL_PATH, SafeTensors


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "experiments" / "svg-w8a8-screen" / "cases" / "cases.json"
OUT = ROOT / "experiments" / "packed-activation-precision"
HEADROOMS = (1.10, 1.50, 2.00, 4.00)
CALIBRATION_CASES = 256
EVALUATION_CASES = 256
NATURAL_CASES = 64


def reference_ranges(
    inputs: np.ndarray, blocks: list[object], headroom: float
) -> list[dict[str, np.ndarray]]:
    states = np.asarray(inputs, dtype=np.float64).copy()
    ranges = []
    for block in blocks:
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        learned = normalized1 @ block.attention_weight.T + block.attention_bias
        residual = states + learned
        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in residual]
        )
        hidden = gelu_new(normalized2 @ block.fc_weight.T + block.fc_bias)
        states = residual + hidden @ block.projection_weight.T + block.projection_bias
        ranges.append({
            "residual": np.maximum(np.max(np.abs(residual), axis=0) * headroom, 1e-9),
            "hidden": np.maximum(np.max(np.abs(hidden), axis=0) * headroom, 1e-9),
            "hidden_min": np.minimum(np.min(hidden, axis=0) * headroom, 0),
            "hidden_max": np.maximum(np.max(hidden, axis=0) * headroom, 0),
            "state": np.maximum(np.max(np.abs(states), axis=0) * headroom, 1e-9),
            "state_min": np.minimum(np.min(states, axis=0) * headroom, 0),
            "state_max": np.maximum(np.max(states, axis=0) * headroom, 0),
        })
    return ranges


def quantize(values: np.ndarray, bounds: np.ndarray, bits: int) -> tuple[np.ndarray, int]:
    maximum = (1 << (bits - 1)) - 1
    normalized = values / bounds
    clipped = int(np.count_nonzero(np.abs(normalized) > 1))
    codes = np.rint(np.clip(normalized, -1, 1) * maximum)
    return codes / maximum * bounds, clipped


def quantize_hidden(
    values: np.ndarray,
    block_ranges: dict[str, np.ndarray],
    bits: int,
    scheme: str,
) -> tuple[np.ndarray, int]:
    if scheme == "linear-symmetric":
        return quantize(values, block_ranges["hidden"], bits)
    if scheme == "linear-asymmetric":
        low = block_ranges["hidden_min"]
        high = block_ranges["hidden_max"]
        span = np.maximum(high - low, 1e-9)
        normalized = (values - low) / span
        clipped = int(np.count_nonzero((normalized < 0) | (normalized > 1)))
        levels = (1 << bits) - 1
        codes = np.rint(np.clip(normalized, 0, 1) * levels)
        return low + codes / levels * span, clipped
    if scheme.startswith("log-asymmetric-"):
        mu = float(scheme.removeprefix("log-asymmetric-"))
        low = block_ranges["hidden_min"]
        high = block_ranges["hidden_max"]
        span = np.maximum(high - low, 1e-9)
        normalized = (values - low) / span
        clipped = int(np.count_nonzero((normalized < 0) | (normalized > 1)))
        normalized = np.clip(normalized, 0, 1)
        levels = (1 << bits) - 1
        encoded = np.log1p(mu * normalized) / np.log1p(mu)
        codes = np.rint(encoded * levels)
        decoded = np.expm1(codes / levels * np.log1p(mu)) / mu
        return low + decoded * span, clipped

    bounds = block_ranges["hidden"]
    normalized = values / bounds
    clipped = int(np.count_nonzero(np.abs(normalized) > 1))
    normalized = np.clip(normalized, -1, 1)
    maximum = (1 << (bits - 1)) - 1
    if scheme == "sqrt-symmetric":
        encoded = np.sign(normalized) * np.sqrt(np.abs(normalized))
        codes = np.rint(encoded * maximum)
        decoded = np.sign(codes) * (np.abs(codes) / maximum) ** 2
    elif scheme.startswith("mulaw"):
        mu = float(scheme.removeprefix("mulaw"))
        encoded = np.sign(normalized) * np.log1p(mu * np.abs(normalized)) / np.log1p(mu)
        codes = np.rint(encoded * maximum)
        decoded = np.sign(codes) * np.expm1(
            np.abs(codes) / maximum * np.log1p(mu)
        ) / mu
    else:
        raise ValueError(f"unknown hidden quantizer {scheme}")
    return decoded * bounds, clipped


def quantized_forward(
    inputs: np.ndarray,
    blocks: list[object],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    ranges: list[dict[str, np.ndarray]],
    state_bits: int | None,
    hidden_bits: int | None = None,
) -> tuple[np.ndarray, int, int]:
    if hidden_bits is None:
        if state_bits is None:
            raise ValueError("hidden_bits is required when state transport is continuous")
        hidden_bits = state_bits
    states = np.asarray(inputs, dtype=np.float64).copy()
    clipped = 0
    values = 0
    for block, block_ranges in zip(blocks, ranges):
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        learned = normalized1 @ block.attention_weight.T + block.attention_bias
        states = states + learned
        if state_bits is not None:
            states, count = quantize(states, block_ranges["residual"], state_bits)
            clipped += count
            values += states.size
        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in states]
        )
        hidden, count = quantize(
            gelu_new(normalized2 @ block.fc_weight.T + block.fc_bias),
            block_ranges["hidden"],
            hidden_bits,
        )
        clipped += count
        values += hidden.size
        projection = hidden @ block.projection_weight.T + block.projection_bias
        states = states + projection
        if state_bits is not None:
            states, count = quantize(states, block_ranges["state"], state_bits)
            clipped += count
            values += states.size
    final = np.stack([layer_norm(x, final_gamma, final_beta) for x in states])
    return final, clipped, values


def hidden_scheme_forward(
    inputs: np.ndarray,
    blocks: list[object],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    ranges: list[dict[str, np.ndarray]],
    hidden_bits: int,
    scheme: str,
) -> tuple[np.ndarray, int, int]:
    """Quantize only the wide MLP boundary, leaving 768-wide states exact."""
    states = np.asarray(inputs, dtype=np.float64).copy()
    clipped = 0
    values = 0
    for block, block_ranges in zip(blocks, ranges):
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        learned = normalized1 @ block.attention_weight.T + block.attention_bias
        states = states + learned
        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in states]
        )
        hidden_values = gelu_new(
            normalized2 @ block.fc_weight.T + block.fc_bias
        )
        if scheme.startswith((
            "importance-asym-",
            "sensitivity-asym-",
            "tiergroup-sensitivity-asym-",
        )) or scheme.startswith("tiercluster"):
            cluster_count = None
            prefix = (
                "importance-asym-"
                if scheme.startswith("importance-asym-")
                else (
                    "tiergroup-sensitivity-asym-"
                    if scheme.startswith("tiergroup-sensitivity-asym-")
                    else (
                        "sensitivity-asym-"
                        if scheme.startswith("sensitivity-asym-")
                        else scheme.split("sensitivity-asym-")[0] + "sensitivity-asym-"
                    )
                )
            )
            if prefix.startswith("tiercluster"):
                cluster_count = int(
                    prefix.split("-", 1)[0].removeprefix("tiercluster")
                )
            precisions = tuple(
                int(digit) for digit in scheme.removeprefix(prefix)
            )
            importance = np.linalg.norm(block.projection_weight, axis=0)
            if prefix != "importance-asym-":
                importance = importance * (
                    block_ranges["hidden_max"] - block_ranges["hidden_min"]
                )
            ranking = np.argsort(importance)
            bits_by_channel = np.empty(hidden_values.shape[1], dtype=np.int64)
            if len(precisions) == 2:
                half = hidden_values.shape[1] // 2
                bits_by_channel[ranking[:half]] = precisions[0]
                bits_by_channel[ranking[half:]] = precisions[1]
            elif len(precisions) == 3:
                third = hidden_values.shape[1] // 3
                bits_by_channel[ranking[:third]] = precisions[0]
                bits_by_channel[ranking[third : 2 * third]] = precisions[1]
                bits_by_channel[ranking[2 * third :]] = precisions[2]
            elif len(precisions) == 4:
                quarter = hidden_values.shape[1] // 4
                bits_by_channel[ranking[:quarter]] = precisions[0]
                bits_by_channel[ranking[quarter : 2 * quarter]] = precisions[1]
                bits_by_channel[ranking[2 * quarter : 3 * quarter]] = precisions[2]
                bits_by_channel[ranking[3 * quarter :]] = precisions[3]
            else:
                raise ValueError(f"invalid importance scheme {scheme}")
            levels = (1 << bits_by_channel) - 1
            low = block_ranges["hidden_min"].copy()
            high = block_ranges["hidden_max"].copy()
            if prefix == "tiergroup-sensitivity-asym-":
                # One shared affine decoder per precision bank. This sacrifices
                # some abstract quantization quality but avoids multiplying
                # geometric carrier error by 3,072 different channel spans.
                for precision in precisions:
                    selected = bits_by_channel == precision
                    low[selected] = np.min(low[selected])
                    high[selected] = np.max(high[selected])
            elif cluster_count is not None:
                # Sort channels with equal precision by calibrated span and
                # share one decoder range inside each cluster. More clusters
                # approach per-channel quantization; fewer clusters bound how
                # strongly geometric code error can be amplified.
                channel_span = high - low
                for precision in precisions:
                    selected = np.flatnonzero(bits_by_channel == precision)
                    selected = selected[np.argsort(channel_span[selected])]
                    for cluster in np.array_split(selected, cluster_count):
                        low[cluster] = np.min(low[cluster])
                        high[cluster] = np.max(high[cluster])
            span = np.maximum(high - low, 1e-9)
            normalized = (hidden_values - low) / span
            count = int(np.count_nonzero((normalized < 0) | (normalized > 1)))
            hidden = low + np.rint(
                np.clip(normalized, 0, 1) * levels
            ) / levels * span
        else:
            hidden, count = quantize_hidden(
                hidden_values, block_ranges, hidden_bits, scheme
            )
        clipped += count
        values += hidden.size
        states = states + hidden @ block.projection_weight.T + block.projection_bias
    final = np.stack([layer_norm(x, final_gamma, final_beta) for x in states])
    return final, clipped, values


def state_scheme_forward(
    inputs: np.ndarray,
    blocks: list[object],
    final_gamma: np.ndarray,
    final_beta: np.ndarray,
    ranges: list[dict[str, np.ndarray]],
    low_bits: int,
    high_bits: int,
    companding: str,
) -> tuple[np.ndarray, int, int]:
    """Keep MLP activations exact and quantize each cross-block state."""
    states = np.asarray(inputs, dtype=np.float64).copy()
    clipped = 0
    values = 0
    for block, block_ranges in zip(blocks, ranges):
        normalized1 = np.stack(
            [layer_norm(x, block.ln1_gamma, block.ln1_beta) for x in states]
        )
        learned = normalized1 @ block.attention_weight.T + block.attention_bias
        residual = states + learned
        normalized2 = np.stack(
            [layer_norm(x, block.ln2_gamma, block.ln2_beta) for x in residual]
        )
        hidden = gelu_new(normalized2 @ block.fc_weight.T + block.fc_bias)
        states = residual + hidden @ block.projection_weight.T + block.projection_bias
        bounds = block_ranges["state"]
        normalized = states / bounds
        clipped += int(np.count_nonzero(np.abs(normalized) > 1))
        normalized = np.clip(normalized, -1, 1)
        ranking = np.argsort(bounds)
        bits_by_channel = np.empty(states.shape[1], dtype=np.int64)
        half = states.shape[1] // 2
        bits_by_channel[ranking[:half]] = low_bits
        bits_by_channel[ranking[half:]] = high_bits
        levels = (1 << bits_by_channel) - 1
        if companding == "linear":
            encoded = (normalized + 1) / 2
            codes = np.rint(encoded * levels)
            decoded = codes / levels * 2 - 1
        elif companding == "sqrt":
            encoded = (np.sign(normalized) * np.sqrt(np.abs(normalized)) + 1) / 2
            codes = np.rint(encoded * levels)
            signed = codes / levels * 2 - 1
            decoded = np.sign(signed) * np.abs(signed) ** 2
        else:
            raise ValueError(f"unknown state companding {companding}")
        states = decoded * bounds
        values += states.size
    final = np.stack([layer_norm(x, final_gamma, final_beta) for x in states])
    return final, clipped, values


def summarize(
    actual: np.ndarray,
    expected: np.ndarray,
    embedding: np.ndarray,
    expected_winners: np.ndarray,
    expected_top5: np.ndarray,
    clipped: int,
    total: int,
) -> dict[str, object]:
    winners = np.argmax(actual @ embedding.T, axis=1)
    error = actual - expected
    winner_in_reference_top5 = np.asarray([
        winner in expected_top5[index] for index, winner in enumerate(winners)
    ])
    return {
        "winner_matches": int(np.count_nonzero(winners == expected_winners)),
        "cases": int(len(expected)),
        "winner_match_fraction": float(np.mean(winners == expected_winners)),
        "natural_winner_match_fraction": float(np.mean(
            winners[:NATURAL_CASES] == expected_winners[:NATURAL_CASES]
        )),
        "winner_in_reference_top5_fraction": float(np.mean(winner_in_reference_top5)),
        "hidden_rmse": float(np.sqrt(np.mean(error**2))),
        "hidden_max_error": float(np.max(np.abs(error))),
        "mean_cosine": float(np.mean([
            np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            for a, b in zip(actual, expected)
        ])),
        "clipped_fraction": float(clipped / total),
        "winner_ids": winners.tolist(),
    }


def main() -> None:
    payload = json.loads(CASES.read_text())
    natural_inputs = np.asarray(
        [case["input_expected"] for case in payload["cases"]], dtype=np.float64
    )
    _, embedding, blocks, final_gamma, final_beta = load_checkpoint()
    position = np.asarray(
        SafeTensors(MODEL_PATH).tensor("wpe.weight")[0], dtype=np.float64
    )
    natural_ids = {int(case["token_id"]) for case in payload["cases"]}
    candidates = np.asarray(
        [index for index in range(len(embedding)) if index not in natural_ids],
        dtype=np.int64,
    )
    rng = np.random.default_rng(0x5041434B)
    sampled = rng.choice(
        candidates,
        size=CALIBRATION_CASES + EVALUATION_CASES - NATURAL_CASES,
        replace=False,
    )
    calibration = embedding[sampled[:CALIBRATION_CASES]] + position
    evaluation = np.concatenate((
        natural_inputs[:NATURAL_CASES],
        embedding[sampled[CALIBRATION_CASES:]] + position,
    ))
    expected = exact_forward(evaluation, blocks, final_gamma, final_beta)
    expected_scores = expected @ embedding.T
    expected_winners = np.argmax(expected_scores, axis=1)
    results = []
    expected_top5 = np.argpartition(expected_scores, -5, axis=1)[:, -5:]
    for headroom in HEADROOMS:
        ranges = reference_ranges(calibration, blocks, headroom)
        for bits in range(4, 11):
            actual, clipped, total = quantized_forward(
                evaluation, blocks, final_gamma, final_beta, ranges, bits
            )
            results.append({
                "bits": bits,
                "headroom": headroom,
                **summarize(
                    actual, expected, embedding, expected_winners,
                    expected_top5, clipped, total,
                ),
            })
    mixed_results = []
    for headroom in HEADROOMS[:3]:
        ranges = reference_ranges(calibration, blocks, headroom)
        for state_bits in (None, 8, 10, 12):
            for hidden_bits in range(4, 9):
                actual, clipped, total = quantized_forward(
                    evaluation, blocks, final_gamma, final_beta, ranges,
                    state_bits, hidden_bits,
                )
                mixed_results.append({
                    "state_bits": state_bits,
                    "hidden_bits": hidden_bits,
                    "headroom": headroom,
                    **summarize(
                        actual, expected, embedding, expected_winners,
                        expected_top5, clipped, total,
                    ),
                })
    companding_results = []
    for headroom in HEADROOMS[:3]:
        ranges = reference_ranges(calibration, blocks, headroom)
        for scheme in (
            "linear-symmetric",
            "linear-asymmetric",
            "sqrt-symmetric",
            "mulaw15",
            "mulaw255",
            "log-asymmetric-0.25",
            "log-asymmetric-0.5",
            "log-asymmetric-1",
            "log-asymmetric-2",
            "log-asymmetric-4",
            "log-asymmetric-8",
            "log-asymmetric-15",
            "importance-asym-455",
            "importance-asym-456",
            "importance-asym-466",
            "importance-asym-566",
            "importance-asym-468",
            "importance-asym-567",
            "importance-asym-477",
            "sensitivity-asym-468",
            "sensitivity-asym-567",
            "sensitivity-asym-477",
            "importance-asym-3456",
            "importance-asym-3555",
            "importance-asym-4455",
            "sensitivity-asym-3456",
            "sensitivity-asym-3555",
            "sensitivity-asym-4455",
            "importance-asym-48",
            "importance-asym-58",
            "importance-asym-49",
        ):
            actual, clipped, total = hidden_scheme_forward(
                evaluation, blocks, final_gamma, final_beta, ranges, 6, scheme
            )
            companding_results.append({
                "scheme": scheme,
                "state_bits": None,
                "hidden_bits": 6,
                "headroom": headroom,
                **summarize(
                    actual, expected, embedding, expected_winners,
                    expected_top5, clipped, total,
                ),
            })
    state_transport_results = []
    for headroom in HEADROOMS[:3]:
        ranges = reference_ranges(calibration, blocks, headroom)
        for low_bits, high_bits in ((8, 9), (9, 10), (10, 10)):
            for companding in ("linear", "sqrt"):
                actual, clipped, total = state_scheme_forward(
                    evaluation, blocks, final_gamma, final_beta, ranges,
                    low_bits, high_bits, companding,
                )
                state_transport_results.append({
                    "low_bits": low_bits,
                    "high_bits": high_bits,
                    "companding": companding,
                    "headroom": headroom,
                    **summarize(
                        actual, expected, embedding, expected_winners,
                        expected_top5, clipped, total,
                    ),
                })
    output = {
        "scope": (
            "All 12 GPT-2-small blocks and the tied output head; one-token contexts. "
            "Post-attention residual, post-GELU hidden, and block state are quantized."
        ),
        "weight_precision": "existing signed 9-bit row quantization",
        "activation_scales": (
            f"per-channel maxima from the first {CALIBRATION_CASES} cases with "
            f"headroom multipliers {HEADROOMS}"
        ),
        "evaluation_cases": int(len(evaluation)),
        "natural_prompt_token_cases": NATURAL_CASES,
        "expected_winner_ids": expected_winners.tolist(),
        "results": results,
        "mixed_results": mixed_results,
        "companding_results": companding_results,
        "state_transport_results": state_transport_results,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(output, indent=2) + "\n")
    deployment_ranges = reference_ranges(calibration, blocks, 2.0)
    (OUT / "hidden-ranges-headroom2.json").write_text(json.dumps({
        "calibration_cases": CALIBRATION_CASES,
        "headroom": 2.0,
        "scheme": "per-channel asymmetric min/max",
        "blocks": [
            {
                "minimum": block_ranges["hidden_min"].tolist(),
                "maximum": block_ranges["hidden_max"].tolist(),
                "state_bound": block_ranges["state"].tolist(),
                "state_minimum": block_ranges["state_min"].tolist(),
                "state_maximum": block_ranges["state_max"].tolist(),
                "residual_bound": block_ranges["residual"].tolist(),
            }
            for block_ranges in deployment_ranges
        ],
    }, separators=(",", ":")) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
