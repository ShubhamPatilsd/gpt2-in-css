#!/usr/bin/env python3
"""Estimate whether radix-packed HVAR metrics can hold real GPT-2 dot products."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from build_gpt2_block_css import gelu_new, layer_norm, model_data
from build_signed_hvar_chain import quantize_float_rows


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "font-packed-metrics" / "real-feasibility.json"
MATRICES = ("v_weight", "attn_proj_weight", "fc_weight", "mlp_proj_weight")


def bits_for_signed(value: np.ndarray) -> np.ndarray:
    return np.ceil(np.log2(2 * np.abs(value) + 1)).astype(np.int64)


def main() -> None:
    data = model_data()
    quantized = {
        name: quantize_float_rows(data[name], bits=9) for name in MATRICES
    }
    n1 = layer_norm(data["x"], data["ln1_gamma"], data["ln1_beta"])
    value = quantized["v_weight"].reconstructed @ n1 + data["v_bias"]
    attention = (
        quantized["attn_proj_weight"].reconstructed @ value
        + data["attn_proj_bias"]
    )
    residual = data["x"] + attention
    n2 = layer_norm(residual, data["ln2_gamma"], data["ln2_beta"])
    pre = quantized["fc_weight"].reconstructed @ n2 + data["fc_bias"]
    hidden = gelu_new(pre)
    inputs = {
        "v_weight": n1,
        "attn_proj_weight": value,
        "fc_weight": n2,
        "mlp_proj_weight": hidden,
    }

    result: dict[str, object] = {
        "metric_payload_bits": 16,
        "weight_bits": 9,
        "method": (
            "Quantize each normalized activation to a signed integer, evaluate the "
            "integer dot product, and count the signed bits required by adjacent pairs."
        ),
        "matrices": {},
    }
    matrices: dict[str, object] = result["matrices"]  # type: ignore[assignment]
    for name in MATRICES:
        qrows = quantized[name]
        vector = inputs[name]
        normalized = vector / (float(np.max(np.abs(vector))) * 1.01)
        by_activation_bits = {}
        for activation_bits in (4, 6, 8):
            maximum = (1 << (activation_bits - 1)) - 1
            codes = np.rint(normalized * maximum).astype(np.int64)
            raw = qrows.codes.astype(np.int64) @ codes
            bits = bits_for_signed(raw)
            even = len(bits) // 2 * 2
            pair_bits = bits[:even].reshape(-1, 2).sum(axis=1)
            by_activation_bits[str(activation_bits)] = {
                "single_bits_median": float(np.median(bits)),
                "single_bits_p99": float(np.quantile(bits, 0.99)),
                "single_bits_max": int(np.max(bits)),
                "pair_bits_median": float(np.median(pair_bits)),
                "pairs_fitting_one_16bit_metric_fraction": float(
                    np.mean(pair_bits <= 16)
                ),
            }
        matrices[name] = {
            "outputs": int(qrows.codes.shape[0]),
            "inputs": int(qrows.codes.shape[1]),
            "activation_quantization": by_activation_bits,
        }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
