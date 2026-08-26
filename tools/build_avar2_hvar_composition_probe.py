#!/usr/bin/env python3
"""Build a no-JavaScript avar2 -> HVAR cross-axis composition probe."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.varLib.builder import (
    buildDeltaSetIndexMap,
    buildVarData,
    buildVarRegionList,
    buildVarStore,
)

from build_matrix_backend_prototypes import build_direct_font_backend


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiments" / "avar2-hvar-composition"
AXIS_TAGS = ("X000", "X001")
CODEPOINT_START = 0xE000
BASE_ADVANCE = 4_000
F2DOT14 = 1 << 14

# avar2 changes the two incoming coordinates from x to A @ x. HVAR then
# consumes the remapped coordinates with B, so the glyph widths expose B A x
# without an intermediate browser-layout value.
A = np.asarray(((0.25, 0.50), (-0.30, 0.10)), dtype=np.float64)
B = np.asarray(((2_000, -1_000), (500, 1_500)), dtype=np.int16)
INPUTS = np.asarray(((0.40, 0.20), (-0.40, 0.60), (0.75, -0.25)), dtype=np.float64)


def add_avar2(path: Path) -> list[list[float]]:
    font = TTFont(path, recalcTimestamp=False)
    supports = []
    for tag in AXIS_TAGS:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))

    # avar2 adds deltas to each original normalized coordinate. Therefore the
    # stored linear map is A - I. Negative and positive regions carry the two
    # signed endpoints of each coefficient.
    delta_map = A - np.eye(len(AXIS_TAGS))
    rows: list[list[int]] = []
    for output_axis in range(len(AXIS_TAGS)):
        row: list[int] = []
        for input_axis in range(len(AXIS_TAGS)):
            endpoint = int(round(delta_map[output_axis, input_axis] * F2DOT14))
            row.extend((-endpoint, endpoint))
        rows.append(row)

    region_list = buildVarRegionList(supports, list(AXIS_TAGS))
    var_data = buildVarData(range(len(supports)), rows, optimize=True)
    avar = newTable("avar")
    avar.majorVersion = 2
    avar.minorVersion = 0
    avar.segments = {
        tag: {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0} for tag in AXIS_TAGS
    }
    avar.table = otTables.avar()
    avar.table.Reserved = 0
    avar.table.VarIdxMap = buildDeltaSetIndexMap(range(len(AXIS_TAGS)))
    avar.table.VarStore = buildVarStore(region_list, [var_data])
    font["avar"] = avar
    font.recalcTimestamp = False
    font.save(path)

    # Verify the file-level mapping independently of the browser.
    checked = TTFont(path, recalcTimestamp=False)
    mapped = []
    for values in INPUTS:
        location = dict(zip(AXIS_TAGS, values, strict=True))
        result = checked["avar"].renormalizeLocation(
            location, checked, dropZeroes=False
        )
        mapped.append([result[tag] for tag in AXIS_TAGS])
    return mapped


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ttf = OUTPUT / "composition.ttf"
    build_direct_font_backend(
        B,
        ttf,
        signed_axes=True,
        base_advance=BASE_ADVANCE,
        codepoint_start=CODEPOINT_START,
        axis_tags=list(AXIS_TAGS),
    )
    mapped = add_avar2(ttf)
    font = TTFont(ttf, recalcTimestamp=False)
    font.flavor = "woff2"
    font.save(OUTPUT / "composition.woff2")

    transformed = INPUTS @ A.T
    outputs = transformed @ B.T
    widths = outputs + BASE_ADVANCE
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
<title>avar2 to HVAR composition probe</title>
<style>
@font-face{{font-family:Avar2Composition;src:url("composition.woff2") format("woff2")}}
html,body{{margin:0}}input{{position:fixed;left:-10000px}}
.probe{{position:fixed;left:0;top:0;display:inline-block;width:max-content;
font-family:Avar2Composition;font-size:1000px;line-height:1;font-kerning:none}}
.output-1{{top:2px}}
{case_rules}
</style>
{controls}
<i id="output-0" class="probe output-0">&#x{CODEPOINT_START:X};</i>
<i id="output-1" class="probe output-1">&#x{CODEPOINT_START + 1:X};</i>
'''
    (OUTPUT / "index.html").write_text(html)
    reference = {
        "backend": "OpenType avar2 cross-axis remap consumed directly by HVAR",
        "axisTags": list(AXIS_TAGS),
        "a": A.tolist(),
        "b": B.astype(int).tolist(),
        "inputs": INPUTS.tolist(),
        "fontToolsMapped": mapped,
        "expectedMapped": transformed.tolist(),
        "expectedOutputs": outputs.tolist(),
        "expectedWidths": widths.tolist(),
        "baseAdvance": BASE_ADVANCE,
        "fontBytes": (OUTPUT / "composition.woff2").stat().st_size,
        "htmlBytes": (OUTPUT / "index.html").stat().st_size,
    }
    (OUTPUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(json.dumps(reference, indent=2))


if __name__ == "__main__":
    main()
