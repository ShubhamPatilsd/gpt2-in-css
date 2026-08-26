#!/usr/bin/env python3
"""Verify the signed, quantized two-layer direct-HVAR chain."""

from __future__ import annotations

import json

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer

from build_matrix_backend_prototypes import axis_tag, output_glyph
from build_signed_hvar_chain import OUT, WIDTH, quantize_float_rows, real_matrices


def apply_font(filename: str, vector: np.ndarray, activation_range: float) -> np.ndarray:
    font = TTFont(OUT / filename, recalcTimestamp=False)
    location = {
        axis_tag(index): float(vector[index] / activation_range)
        for index in range(WIDTH)
    }
    instancer = VarStoreInstancer(
        font["HVAR"].table.VarStore, font["fvar"].axes, location
    )
    return np.array(
        [instancer[font.getGlyphID(output_glyph(index))] for index in range(WIDTH)],
        dtype=np.float64,
    )


def main() -> None:
    metadata = json.loads((OUT / "reference.json").read_text())
    vector, weight_1, bias_1, weight_2, bias_2 = real_matrices()
    quantized_1 = quantize_float_rows(weight_1)
    quantized_2 = quantize_float_rows(weight_2)
    raw_1 = apply_font("layer-1.woff2", vector, metadata["input_range"])
    actual_1 = raw_1 * metadata["input_range"] * quantized_1.scales + bias_1
    raw_2 = apply_font(
        "layer-2.woff2", actual_1, metadata["intermediate_range"]
    )
    actual_2 = (
        raw_2 * metadata["intermediate_range"] * quantized_2.scales + bias_2
    )
    expected_1 = quantized_1.reconstructed @ vector + bias_1
    expected_2 = quantized_2.reconstructed @ expected_1 + bias_2
    np.testing.assert_allclose(actual_1, expected_1, atol=1e-12)
    np.testing.assert_allclose(actual_2, expected_2, atol=1e-12)
    html = (OUT / "index.html").read_text()
    assert "<script" not in html.lower()
    assert html.count("@font-face") == 2
    assert html.count("@property --l1-y-") == WIDTH
    assert html.count("@property --l2-y-") == WIDTH
    print(
        {
            "quantized_chain_max_error": float(np.max(np.abs(actual_2 - expected_2))),
            "original_model_max_error": float(
                np.max(np.abs(actual_2 - (weight_2 @ (weight_1 @ vector + bias_1) + bias_2)))
            ),
            "no_javascript": True,
        }
    )


if __name__ == "__main__":
    main()
