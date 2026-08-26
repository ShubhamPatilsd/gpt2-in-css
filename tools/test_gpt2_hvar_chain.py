#!/usr/bin/env python3
"""Verify the two-layer, 768-wide GPT-2 HVAR chain offline."""

from __future__ import annotations

import json

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer

from build_gpt2_hvar_chain import (
    OUT,
    QUANT_BITS,
    SHARDS,
    SHARD_SIZE,
    WIDTH,
    model_inputs,
)
from build_matrix_backend_prototypes import axis_tag, output_glyph
from build_signed_hvar_chain import quantize_float_rows


def apply_layer(layer: int, vector: np.ndarray, activation_range: float) -> np.ndarray:
    result = np.zeros(WIDTH, dtype=np.float64)
    for shard in range(SHARDS):
        start = shard * SHARD_SIZE
        stop = start + SHARD_SIZE
        font = TTFont(OUT / f"layer-{layer}-shard-{shard}.woff2")
        location = {
            axis_tag(index): float(vector[start + index] / activation_range)
            for index in range(SHARD_SIZE)
        }
        instancer = VarStoreInstancer(
            font["HVAR"].table.VarStore, font["fvar"].axes, location
        )
        result += np.array(
            [instancer[font.getGlyphID(output_glyph(i))] for i in range(WIDTH)],
            dtype=np.float64,
        )
    return result


def main() -> None:
    metadata = json.loads((OUT / "reference.json").read_text())
    vector, weight_1, bias_1, weight_2, bias_2 = model_inputs()
    quantized_1 = quantize_float_rows(weight_1, bits=QUANT_BITS)
    quantized_2 = quantize_float_rows(weight_2, bits=QUANT_BITS)
    raw_1 = apply_layer(1, vector, metadata["input_range"])
    actual_1 = raw_1 * metadata["input_range"] * quantized_1.scales + bias_1
    raw_2 = apply_layer(2, actual_1, metadata["intermediate_range"])
    actual_2 = raw_2 * metadata["intermediate_range"] * quantized_2.scales + bias_2
    expected_1 = quantized_1.reconstructed @ vector + bias_1
    expected_2 = quantized_2.reconstructed @ expected_1 + bias_2
    np.testing.assert_allclose(actual_1, expected_1, atol=1e-12)
    np.testing.assert_allclose(actual_2, expected_2, atol=1e-12)
    html = (OUT / "index.html").read_text()
    assert "<script" not in html.lower()
    assert html.count("@font-face") == 6
    print(
        {
            "width": WIDTH,
            "quantized_chain_max_error": float(np.max(np.abs(actual_2 - expected_2))),
            "original_float_max_error": float(
                np.max(np.abs(actual_2 - (weight_2 @ (weight_1 @ vector + bias_1) + bias_2)))
            ),
            "no_javascript": True,
        }
    )


if __name__ == "__main__":
    main()
