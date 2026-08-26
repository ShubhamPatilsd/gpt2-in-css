#!/usr/bin/env python3
"""Verify the four-channel MVAR/HVAR font-metric probe offline."""

from __future__ import annotations

import json

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer

from build_font_metric_vector_probe import BASE_METRIC, OUT, axis_tag


def main() -> None:
    reference = json.loads((OUT / "reference.json").read_text())
    inputs = np.asarray(reference["inputs"], dtype=np.float64)
    expected = np.asarray(reference["expected"], dtype=np.float64)
    location = {axis_tag(index): float(value) for index, value in enumerate(inputs)}

    for filename in ("metric-vector.ttf", "metric-vector.woff2"):
        font = TTFont(OUT / filename)
        assert "MVAR" in font and "HVAR" in font
        mvar_instancer = VarStoreInstancer(
            font["MVAR"].table.VarStore, font["fvar"].axes, location
        )
        mvar_records = {
            record.ValueTag: mvar_instancer[record.VarIdx]
            for record in font["MVAR"].table.ValueRecord
        }
        hvar_instancer = VarStoreInstancer(
            font["HVAR"].table.VarStore, font["fvar"].axes, location
        )
        actual = np.asarray(
            [
                mvar_records["xhgt"],
                mvar_records["cpht"],
                hvar_instancer[font.getGlyphID("zero")],
                hvar_instancer[font.getGlyphID("water")],
            ],
            dtype=np.float64,
        )
        np.testing.assert_allclose(actual, expected, atol=0)

    html = (OUT / "index.html").read_text()
    assert "<script" not in html.lower()
    for unit in ("1ex", "1cap", "1ch", "1ic"):
        assert unit in html
    print({"expected": expected.tolist(), "offline_exact": True, "no_javascript": True})


if __name__ == "__main__":
    main()
