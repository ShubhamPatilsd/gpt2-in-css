#!/usr/bin/env python3
"""Verify one generated variable-font scaling experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.varLib.varStore import VarStoreInstancer

from build_matrix_backend_prototypes import FONT_BASE_ADVANCE, ROOT, axis_tag, output_glyph
from build_variable_font_scaling import inputs_for_size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, required=True)
    args = parser.parse_args()
    size = args.size
    directory = ROOT / "experiments" / "matrix-scaling" / str(size)
    metadata = json.loads((directory / "reference.json").read_text())
    weights, vector = inputs_for_size(size)
    expected = weights.astype(np.float64) @ vector
    np.testing.assert_allclose(metadata["expected"], expected)

    location = {axis_tag(index): float(vector[index]) for index in range(size)}
    errors = {}
    for filename in ("variable-matvec.ttf", "variable-matvec.woff2"):
        font = TTFont(directory / filename, recalcTimestamp=False)
        assert len(font["fvar"].axes) == size
        assert "HVAR" in font
        if metadata.get("compiler") == "direct-hvar":
            instancer = VarStoreInstancer(
                font["HVAR"].table.VarStore, font["fvar"].axes, location
            )
            actual = np.array(
                [instancer[font.getGlyphID(output_glyph(index))] for index in range(size)],
                dtype=np.float64,
            )
        else:
            instance = instantiateVariableFont(font, location, inplace=False)
            actual = np.array(
                [
                    instance["hmtx"][output_glyph(index)][0] - FONT_BASE_ADVANCE
                    for index in range(size)
                ],
                dtype=np.float64,
            )
        max_error = float(np.max(np.abs(actual - expected)))
        assert max_error <= 0.5
        errors[filename] = max_error

    html = (directory / "variable-font.html").read_text()
    assert "<script" not in html.lower()
    assert html.count("@property --vf-y-") == size
    print({"size": size, "max_error_font_units": errors, "no_javascript": True})


if __name__ == "__main__":
    main()
