#!/usr/bin/env python3
"""Calibrate and test general per-channel ranges for packed attention contexts."""

from __future__ import annotations

import json
import math

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_attention_context_scaling import PRECISION_REPORT
from build_gpt2_block_css import QUANT_BITS, WIDTH, layer_norm
from build_multitoken_attention_css import HEADS, HEAD_WIDTH, softmax
from build_signed_hvar_chain import quantize_float_rows


SEED = 20260913
CALIBRATION_SEQUENCES = 1024
TEST_SEQUENCES = 256
LENGTHS = (1, 2, 4, 8, 16, 32)
OUT = "experiments/gpt2-block-css/attention-context-precision.json"


def main() -> None:
    rng = np.random.default_rng(SEED)
    tensors = SafeTensors(MODEL_PATH)
    token_embeddings = np.asarray(tensors.tensor("wte.weight"), dtype=np.float64)
    position_embeddings = np.asarray(tensors.tensor("wpe.weight"), dtype=np.float64)
    gamma = np.asarray(tensors.tensor("h.0.ln_1.weight"), dtype=np.float64)
    beta = np.asarray(tensors.tensor("h.0.ln_1.bias"), dtype=np.float64)
    weight = np.asarray(
        tensors.tensor("h.0.attn.c_attn.weight"), dtype=np.float64
    ).T
    bias = np.asarray(tensors.tensor("h.0.attn.c_attn.bias"), dtype=np.float64)
    reconstructed = quantize_float_rows(weight, bits=QUANT_BITS).reconstructed
    qkv_precision = json.loads(PRECISION_REPORT.read_text())
    q_ranges = np.asarray(
        qkv_precision["margins"]["1.2"]["perChannelRanges"], dtype=np.float64
    )[:WIDTH]
    projection_weight = np.asarray(
        tensors.tensor("h.0.attn.c_proj.weight"), dtype=np.float64
    ).T
    projection_bias = np.asarray(
        tensors.tensor("h.0.attn.c_proj.bias"), dtype=np.float64
    )
    projection_weight = quantize_float_rows(
        projection_weight, bits=QUANT_BITS
    ).reconstructed

    def sample(count: int) -> tuple[np.ndarray, np.ndarray, dict[int, int]]:
        contexts = []
        projections = []
        counts = {length: 0 for length in LENGTHS}
        for _ in range(count):
            length = int(rng.choice(LENGTHS))
            counts[length] += 1
            start = int(rng.integers(0, 512 - length + 1))
            token_ids = rng.integers(0, token_embeddings.shape[0], size=length)
            states = np.stack([
                layer_norm(
                    token_embeddings[token_id] + position_embeddings[start + offset],
                    gamma,
                    beta,
                )
                for offset, token_id in enumerate(token_ids)
            ])
            qkv = states @ reconstructed.T + bias
            q_codes = np.rint(
                np.clip((qkv[-1, :WIDTH] + q_ranges) * 255 / (2 * q_ranges), 0, 255)
            )
            query = (-q_ranges + q_codes * (2 * q_ranges / 255)).reshape(
                HEADS, HEAD_WIDTH
            )
            key = qkv[:, WIDTH:2 * WIDTH].reshape(length, HEADS, HEAD_WIDTH)
            value = qkv[:, 2 * WIDTH:].reshape(length, HEADS, HEAD_WIDTH)
            scores = np.einsum("hd,lhd->hl", query, key) / math.sqrt(HEAD_WIDTH)
            probabilities = np.stack([softmax(row) for row in scores])
            context = np.einsum("hl,lhd->hd", probabilities, value).reshape(WIDTH)
            contexts.append(context)
            projections.append(projection_weight @ context + projection_bias)
        return np.stack(contexts), np.stack(projections), counts

    calibration, projection_calibration, calibration_counts = sample(
        CALIBRATION_SEQUENCES
    )
    test, projection_test, test_counts = sample(TEST_SEQUENCES)
    report: dict[str, object] = {
        "seed": SEED,
        "calibrationSequences": CALIBRATION_SEQUENCES,
        "testSequences": TEST_SEQUENCES,
        "lengths": list(LENGTHS),
        "calibrationLengthCounts": calibration_counts,
        "testLengthCounts": test_counts,
        "margins": {},
        "projectionMargins": {},
    }
    margins = report["margins"]
    assert isinstance(margins, dict)
    for margin in (1.05, 1.2, 1.5, 2.0):
        ranges = np.maximum(np.max(np.abs(calibration), axis=0) * margin, 0.05)
        codes = np.rint(
            np.clip((test + ranges) * 255 / (2 * ranges), 0, 255)
        )
        decoded = -ranges + codes * (2 * ranges / 255)
        error = decoded - test
        result: dict[str, object] = {
            "rangeMedian": float(np.median(ranges)),
            "rangeMaximum": float(np.max(ranges)),
            "rmse": float(np.sqrt(np.mean(error * error))),
            "maximumError": float(np.max(np.abs(error))),
            "clippedFraction": float(np.mean(np.abs(test) > ranges)),
        }
        twelve_levels = (1 << 12) - 1
        twelve_codes = np.rint(
            np.clip(
                (test + ranges) * twelve_levels / (2 * ranges),
                0,
                twelve_levels,
            )
        )
        twelve_decoded = -ranges + twelve_codes * (2 * ranges / twelve_levels)
        twelve_error = twelve_decoded - test
        result["twelveBit"] = {
            "rmse": float(np.sqrt(np.mean(twelve_error * twelve_error))),
            "maximumError": float(np.max(np.abs(twelve_error))),
            "clippedFraction": float(np.mean(np.abs(test) > ranges)),
        }
        if margin in (1.2, 1.5, 2.0):
            result["perChannelRanges"] = ranges.tolist()
        margins[str(margin)] = result
        projection_ranges = np.maximum(
            np.max(np.abs(projection_calibration), axis=0) * margin, 0.05
        )
        projection_levels = (1 << 12) - 1
        projection_codes = np.rint(
            np.clip(
                (projection_test + projection_ranges) * projection_levels
                / (2 * projection_ranges),
                0,
                projection_levels,
            )
        )
        projection_decoded = (
            -projection_ranges
            + projection_codes * (2 * projection_ranges / projection_levels)
        )
        projection_error = projection_decoded - projection_test
        projection_result: dict[str, object] = {
            "bits": 12,
            "rangeMedian": float(np.median(projection_ranges)),
            "rangeMaximum": float(np.max(projection_ranges)),
            "rmse": float(np.sqrt(np.mean(projection_error * projection_error))),
            "maximumError": float(np.max(np.abs(projection_error))),
            "clippedFraction": float(
                np.mean(np.abs(projection_test) > projection_ranges)
            ),
        }
        if margin in (1.2, 1.5, 2.0):
            projection_result["perChannelRanges"] = projection_ranges.tolist()
        projection_margins = report["projectionMargins"]
        assert isinstance(projection_margins, dict)
        projection_margins[str(margin)] = projection_result
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    printable = {
        **{key: value for key, value in report.items() if key != "margins"},
        "margins": {
            key: {item: value for item, value in result.items()
                  if item != "perChannelRanges"}
            for key, result in margins.items()
        },
        "projectionMargins": {
            key: {item: value for item, value in result.items()
                  if item != "perChannelRanges"}
            for key, result in report["projectionMargins"].items()
        },
    }
    print(json.dumps(printable, indent=2))


if __name__ == "__main__":
    main()
