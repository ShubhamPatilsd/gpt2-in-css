#!/usr/bin/env python3
"""Measure realistic per-channel QKV packing error away from the demo inputs."""

from __future__ import annotations

import json

import numpy as np

from analyze_full_gpt2 import MODEL_PATH, SafeTensors
from build_gpt2_block_css import QUANT_BITS, layer_norm
from build_signed_hvar_chain import quantize_float_rows


CALIBRATION_CASES = 4096
TEST_CASES = 1024
SEED = 20260912
OUT = "experiments/gpt2-block-css/qkv-transport-precision.json"


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

    def sample(count: int) -> tuple[np.ndarray, np.ndarray]:
        token_ids = rng.integers(0, token_embeddings.shape[0], size=count)
        positions = rng.integers(0, 512, size=count)
        states = np.stack(
            [
                layer_norm(
                    token_embeddings[token_id] + position_embeddings[position],
                    gamma,
                    beta,
                )
                for token_id, position in zip(token_ids, positions, strict=True)
            ]
        )
        outputs = np.concatenate(
            [
                states[start : start + 32] @ reconstructed.T + bias
                for start in range(0, count, 32)
            ]
        )
        return states, outputs

    calibration_states, calibration = sample(CALIBRATION_CASES)
    test_states, test = sample(TEST_CASES)
    report: dict[str, object] = {
        "seed": SEED,
        "calibrationCases": CALIBRATION_CASES,
        "testCases": TEST_CASES,
        "inputAbsMaxCalibration": float(np.max(np.abs(calibration_states))),
        "inputAbsMaxTest": float(np.max(np.abs(test_states))),
        "margins": {},
    }
    margins = report["margins"]
    assert isinstance(margins, dict)
    for margin in (1.05, 1.2, 1.5):
        ranges = np.maximum(np.max(np.abs(calibration), axis=0) * margin, 0.05)
        bit_results = {}
        for bits in (6, 8, 10, 12):
            levels = (1 << bits) - 1
            codes = np.rint(
                np.clip((test + ranges) * levels / (2 * ranges), 0, levels)
            )
            decoded = -ranges + codes * (2 * ranges / levels)
            error = decoded - test
            bit_results[str(bits)] = {
                "rmse": float(np.sqrt(np.mean(error * error))),
                "maximumError": float(np.max(np.abs(error))),
                "clippedFraction": float(np.mean(np.abs(test) > ranges)),
            }
        margins[str(margin)] = {
            "rangeMedian": float(np.median(ranges)),
            "rangeMaximum": float(np.max(ranges)),
            "bits": bit_results,
        }
        if margin == 1.2:
            margins[str(margin)]["perChannelRanges"] = ranges.tolist()
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
