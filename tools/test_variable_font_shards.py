#!/usr/bin/env python3
"""Verify the three-font 768×768 CSS matvec experiment."""

from __future__ import annotations

import json

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer

from build_matrix_backend_prototypes import axis_tag, output_glyph
from build_variable_font_scaling import inputs_for_size
from build_variable_font_shards import OUT, SHARD_COUNT, SHARD_SIZE, SIZE


def main() -> None:
    weights, vector = inputs_for_size(SIZE)
    expected = weights.astype(np.float64) @ vector
    metadata = json.loads((OUT / "reference.json").read_text())
    np.testing.assert_allclose(metadata["expected"], expected)

    actual = np.zeros(SIZE, dtype=np.float64)
    shard_errors = []
    for shard in range(SHARD_COUNT):
        font = TTFont(OUT / f"shard-{shard}.woff2", recalcTimestamp=False)
        assert len(font["fvar"].axes) == SHARD_SIZE
        assert "HVAR" in font
        location = {
            axis_tag(index): float(vector[shard * SHARD_SIZE + index])
            for index in range(SHARD_SIZE)
        }
        instancer = VarStoreInstancer(
            font["HVAR"].table.VarStore, font["fvar"].axes, location
        )
        partial = np.array(
            [
                instancer[font.getGlyphID(output_glyph(index))]
                for index in range(SIZE)
            ],
            dtype=np.float64,
        )
        actual += partial
        start = shard * SHARD_SIZE
        partial_expected = (
            weights[:, start:start + SHARD_SIZE].astype(np.float64)
            @ vector[start:start + SHARD_SIZE]
        )
        shard_errors.append(float(np.max(np.abs(partial - partial_expected))))

    max_error = float(np.max(np.abs(actual - expected)))
    assert max_error <= SHARD_COUNT * 0.5
    html = (OUT / "index.html").read_text()
    assert "<script" not in html.lower()
    assert html.count("@font-face") == SHARD_COUNT
    assert html.count("@property --vf-y-") == SIZE
    print(
        {
            "size": SIZE,
            "shards": SHARD_COUNT,
            "max_error_font_units": max_error,
            "max_partial_errors": shard_errors,
            "no_javascript": True,
        }
    )


if __name__ == "__main__":
    main()
