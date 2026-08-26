#!/usr/bin/env python3
"""Verify the additive font-axis vector transport artifacts offline."""

from __future__ import annotations

import json

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer

from build_additive_font_vector_probe import OUT_ROOT, axis_tag
from build_matrix_backend_prototypes import output_glyph
from build_variable_font_scaling import inputs_for_size


def main() -> None:
    for size in (64, 256, 768):
        page = (OUT_ROOT / str(size) / "index.html").read_text()
        reference = json.loads(
            (OUT_ROOT / str(size) / "reference.json").read_text()
        )
        assert "<script" not in page.lower()
        assert page.count("@keyframes a") == size
        assert reference["size"] == size
        assert f"{size} geometry values" in page

        custom_page = (OUT_ROOT / f"custom-{size}" / "index.html").read_text()
        assert "<script" not in custom_page.lower()
        assert custom_page.count("@property --v") == size
        assert custom_page.count("@keyframes p") == size
        assert "@function --decode" in custom_page
        assert "animation-timing-function:linear" in custom_page
        assert f"{size} geometry values" in custom_page

    weights, vector = inputs_for_size(768)
    actual_first = 0.0
    for shard, start in enumerate(range(0, 768, 256)):
        font = TTFont(OUT_ROOT / "768" / f"vector-shard-{shard}.woff2")
        tags = [axis.axisTag for axis in font["fvar"].axes]
        assert tags[0] == axis_tag(start)
        assert tags[-1] == axis_tag(start + 255)
        location = {
            axis_tag(index): float(vector[index])
            for index in range(start, start + 256)
        }
        instancer = VarStoreInstancer(
            font["HVAR"].table.VarStore, font["fvar"].axes, location
        )
        actual_first += instancer[font.getGlyphID(output_glyph(0))]

    expected_first = float(weights[0].astype(np.float64) @ vector)
    assert abs(actual_first - expected_first) <= 1.5
    print(
        {
            "sizes": [64, 256, 768],
            "expected_first_output": expected_first,
            "font_first_output": actual_first,
            "registered_property_vectors": [64, 256, 768],
            "no_javascript": True,
        }
    )


if __name__ == "__main__":
    main()
