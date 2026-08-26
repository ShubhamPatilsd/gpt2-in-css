#!/usr/bin/env python3
"""Build an avar2 + nonlinear HVAR miniature MLP in one variable font."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

from build_avar2_hvar_composition_probe import (
    A,
    AXIS_TAGS,
    BASE_ADVANCE,
    CODEPOINT_START,
    INPUTS,
    add_avar2,
)
from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "avar2-hvar-mlp"
B = np.asarray(((2_000, -1_000), (500, 1_500)), dtype=np.int16)
KNOTS = np.linspace(-1, 1, 17)


def gelu(value: np.ndarray | float) -> np.ndarray | float:
    return 0.5 * value * (
        1 + np.tanh(math.sqrt(2 / math.pi) * (value + 0.044715 * value**3))
    )


def supports_and_knots() -> tuple[list[dict[str, tuple[float, float, float]]], list[tuple[int, float]]]:
    supports: list[dict[str, tuple[float, float, float]]] = []
    indexed_knots: list[tuple[int, float]] = []
    zero = len(KNOTS) // 2
    for axis, tag in enumerate(AXIS_TAGS):
        for index, knot in enumerate(KNOTS):
            if index == zero:
                continue
            if index < zero:
                start = KNOTS[index - 1] if index > 0 else -1.0
                end = KNOTS[index + 1]
            else:
                start = KNOTS[index - 1]
                end = KNOTS[index + 1] if index + 1 < len(KNOTS) else 1.0
            supports.append({tag: (float(start), float(knot), float(end))})
            indexed_knots.append((axis, float(knot)))
    return supports, indexed_knots


def piecewise_gelu(values: np.ndarray) -> np.ndarray:
    return np.interp(values, KNOTS, gelu(KNOTS))


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ttf = OUTPUT / "mlp.ttf"
    # Start with the correct fvar/cmap/HVAR structure, then replace the linear
    # HVAR store with triangular basis functions for GELU on each remapped axis.
    build_direct_font_backend(
        np.zeros_like(B),
        ttf,
        signed_axes=True,
        base_advance=BASE_ADVANCE,
        codepoint_start=CODEPOINT_START,
        axis_tags=list(AXIS_TAGS),
    )
    font = TTFont(ttf, recalcTimestamp=False)
    supports, indexed_knots = supports_and_knots()
    rows = [[0] * len(supports)]
    for output in range(B.shape[0]):
        rows.append([
            int(round(float(B[output, axis]) * float(gelu(knot))))
            for axis, knot in indexed_knots
        ])
    region_list = buildVarRegionList(supports, list(AXIS_TAGS))
    var_data = buildVarData(range(len(supports)), rows, optimize=True)
    font["HVAR"].table.VarStore = buildVarStore(region_list, [var_data])
    font.recalcTimestamp = False
    font.save(ttf)
    mapped = add_avar2(ttf)
    font = TTFont(ttf, recalcTimestamp=False)
    font.flavor = "woff2"
    font.save(OUTPUT / "mlp.woff2")

    transformed = INPUTS @ A.T
    approximated_hidden = piecewise_gelu(transformed)
    exact_hidden = gelu(transformed)
    represented_outputs = approximated_hidden @ B.T
    exact_outputs = exact_hidden @ B.T
    represented_widths = represented_outputs + BASE_ADVANCE
    controls = "".join(
        f'<input type="radio" name="case" id="case-{index}"'
        f'{" checked" if index == 0 else ""}>'
        for index in range(len(INPUTS))
    )
    case_rules = "".join(
        f'body:has(#case-{index}:checked) .probe{{font-variation-settings:'
        + ",".join(
            f'"{tag}" {value:.10g}'
            for tag, value in zip(AXIS_TAGS, values, strict=True)
        )
        + "}"
        for index, values in enumerate(INPUTS)
    )
    html = f'''<!doctype html>
<meta charset="utf-8">
<title>avar2 plus nonlinear HVAR MLP probe</title>
<style>
@font-face{{font-family:Avar2MLP;src:url("mlp.woff2") format("woff2")}}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}
.probe{{position:fixed;left:0;top:0;display:inline-block;width:max-content;
font-family:Avar2MLP;font-size:1000px;line-height:1;font-kerning:none}}
.output-1{{top:2px}}
{case_rules}
</style>
{controls}
<i id="output-0" class="probe output-0">&#x{CODEPOINT_START:X};</i>
<i id="output-1" class="probe output-1">&#x{CODEPOINT_START + 1:X};</i>
'''
    (OUTPUT / "index.html").write_text(html)
    reference = {
        "backend": "avar2 dense map followed by piecewise-GELU HVAR projection",
        "expression": "B @ GELU(A @ x)",
        "axisTags": list(AXIS_TAGS),
        "a": A.tolist(),
        "b": B.astype(int).tolist(),
        "geluKnots": KNOTS.tolist(),
        "variationRegions": len(supports),
        "inputs": INPUTS.tolist(),
        "fontToolsMapped": mapped,
        "expectedMapped": transformed.tolist(),
        "approximatedHidden": approximated_hidden.tolist(),
        "exactHidden": np.asarray(exact_hidden).tolist(),
        "representedOutputs": represented_outputs.tolist(),
        "exactOutputs": np.asarray(exact_outputs).tolist(),
        "representedWidths": represented_widths.tolist(),
        "approximationMaximum": float(np.max(np.abs(represented_outputs - exact_outputs))),
        "baseAdvance": BASE_ADVANCE,
        "fontBytes": (OUTPUT / "mlp.woff2").stat().st_size,
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps(reference, indent=2))


if __name__ == "__main__":
    main()
