#!/usr/bin/env python3
"""Verify generated HTML/CSS-only matrix backend artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.varLib.varStore import VarStoreInstancer
from PIL import Image

from build_matrix_backend_prototypes import (
    FONT_BASE_ADVANCE,
    OUT,
    SIZE,
    SVG_DIVISOR,
    SVG_WEIGHT_MAX,
    axis_tag,
    deterministic_inputs,
    output_glyph,
)


def main() -> None:
    font_weights, font_input, svg_weights, svg_input = deterministic_inputs()
    font_expected = font_weights.astype(np.float64) @ font_input

    metadata = json.loads((OUT / "reference.json").read_text())
    assert metadata["size"] == SIZE
    np.testing.assert_allclose(metadata["font"]["expected"], font_expected)

    font_errors: dict[str, float] = {}
    location = {axis_tag(i): float(font_input[i]) for i in range(SIZE)}
    for filename in ("variable-matvec.ttf", "variable-matvec.woff2"):
        font = TTFont(OUT / filename)
        assert len(font["fvar"].axes) == SIZE
        assert "HVAR" in font
        instance = instantiateVariableFont(font, location, inplace=False)
        actual = np.array(
            [
                instance["hmtx"][output_glyph(i)][0] - FONT_BASE_ADVANCE
                for i in range(SIZE)
            ],
            dtype=np.float64,
        )
        error = float(np.max(np.abs(actual - font_expected)))
        assert error <= 0.5
        font_errors[filename] = error

    for filename in ("variable-matvec-direct.ttf", "variable-matvec-direct.woff2"):
        font = TTFont(OUT / filename)
        assert len(font["fvar"].axes) == SIZE
        instancer = VarStoreInstancer(
            font["HVAR"].table.VarStore, font["fvar"].axes, location
        )
        actual = np.array(
            [instancer[font.getGlyphID(output_glyph(i))] for i in range(SIZE)],
            dtype=np.float64,
        )
        error = float(np.max(np.abs(actual - font_expected)))
        assert error == 0
        font_errors[filename] = error

    stored_pixels = np.asarray(Image.open(OUT / "svg-weights.png").convert("L"))
    recovered_weights = (stored_pixels // 17).T.astype(np.uint8)
    np.testing.assert_array_equal(recovered_weights, svg_weights)
    svg_expected = svg_weights.astype(np.float64) @ (
        svg_input.astype(np.float64) / SVG_WEIGHT_MAX
    )
    np.testing.assert_allclose(metadata["svg"]["expected"], svg_expected)
    expected_reference = np.rint(
        np.clip(svg_expected / (SVG_WEIGHT_MAX * SVG_DIVISOR), 0, 1) * 255
    ).astype(np.uint8)
    actual_reference = np.asarray(
        Image.open(OUT / "svg-reference.png").convert("L")
    ).reshape(-1)
    np.testing.assert_array_equal(actual_reference, expected_reference)

    for filename in (
        "index.html",
        "variable-font.html",
        "variable-font-direct.html",
        "svg-pixel.html",
    ):
        html = (OUT / filename).read_text()
        assert "<script" not in html.lower()
    assert 'order="1 64"' in (OUT / "svg-pixel.html").read_text()

    print(
        {
            "font_max_error_units": font_errors,
            "woff2_bytes": (OUT / "variable-matvec.woff2").stat().st_size,
            "direct_woff2_bytes": (OUT / "variable-matvec-direct.woff2").stat().st_size,
            "svg_weight_bytes": (OUT / "svg-weights.png").stat().st_size,
            "no_javascript": True,
        }
    )


if __name__ == "__main__":
    main()
