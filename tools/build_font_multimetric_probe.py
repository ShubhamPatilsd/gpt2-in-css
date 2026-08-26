#!/usr/bin/env python3
"""Build an HTML/CSS-only probe for parallel variable-font metric outputs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "font-multimetric-probe"
INPUT_WIDTH = 32
UNITS_PER_EM = 1_000
FONT_SIZE = 512
BASE = 2_000
CHANNELS = ["ex", "cap", "ch", "ic", "lh", "vertical-ch", "vertical-ic"]


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def rectangle(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((width, 0))
    pen.lineTo((width, height))
    pen.lineTo((0, height))
    pen.closePath()
    return pen.glyph()


def data() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0x4D554C54)
    weights = rng.integers(-16, 17, size=(len(CHANNELS), INPUT_WIDTH), dtype=np.int16)
    inputs = rng.integers(-4, 5, size=INPUT_WIDTH).astype(np.float64) / 4
    # Make every expected channel fractional so the browser probe also reveals
    # each metric's interpolation/rounding granularity.
    for channel in range(len(CHANNELS)):
        while float(weights[channel] @ inputs).is_integer():
            weights[channel, 0] += 1
    return weights, inputs


def build_font(
    weights: np.ndarray,
    destination: Path,
    family_name: str = "CSS Multi Metric",
    shifted_axes: bool = False,
    outline_variations: bool = True,
) -> None:
    input_width = int(weights.shape[1])
    if weights.shape[0] < 5:
        raise ValueError("multimetric font requires at least five output rows")
    identifier = "".join(character for character in family_name if character.isalnum())
    glyphs = [".notdef", "zero", "water", "x", "H"]
    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({0x30: "zero", 0x6C34: "water", 0x78: "x", 0x48: "H"})
    fb.setupGlyf({
        ".notdef": rectangle(1, 1),
        "zero": rectangle(1, 1),
        "water": rectangle(1, 1),
        "x": rectangle(1, BASE),
        "H": rectangle(1, BASE),
    })
    fb.setupHorizontalMetrics({name: ((BASE if name in {"zero", "water"} else 500), 0) for name in glyphs})
    fb.setupHorizontalHeader(ascent=BASE, descent=0, lineGap=0)
    fb.setupVerticalMetrics({name: (BASE, 0) for name in glyphs})
    fb.setupVerticalHeader(ascent=BASE // 2, descent=-(BASE // 2), lineGap=0)
    fb.setupNameTable({
        "familyName": family_name,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"{identifier}-Regular",
        "fullName": f"{family_name} Regular",
        "psName": f"{identifier}-Regular",
    })
    fb.setupOS2(
        version=4,
        sTypoAscender=BASE,
        sTypoDescender=0,
        sTypoLineGap=0,
        usWinAscent=BASE,
        usWinDescent=0,
        sxHeight=BASE,
        sCapHeight=BASE,
        fsSelection=0xC0,
    )
    fb.setupPost()
    fb.setupMaxp()
    fb.setupHead(created=2_082_844_800, modified=2_082_844_800)
    fb.font.recalcTimestamp = False
    fb.save(destination)

    font = TTFont(destination, recalcTimestamp=False)
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    tags = [axis_tag(i) for i in range(input_width)]
    for index, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = 0 if shifted_axes else -1
        axis.defaultValue = 0
        axis.maxValue = 1
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    supports = []
    for tag in tags:
        if shifted_axes:
            supports.append({tag: (0, 1, 1)})
        else:
            supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    regions = buildVarRegionList(supports, tags)

    def row(values: np.ndarray) -> list[int]:
        if shifted_axes:
            return [2 * value for value in values.astype(np.int16).tolist()]
        return [
            delta
            for value in values.astype(np.int16).tolist()
            for delta in (-value, value)
        ]

    hvar_rows = [[0] * len(supports) for _ in glyphs]
    hvar_rows[1] = row(weights[2])
    hvar_rows[2] = row(weights[3])
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(regions, [buildVarData(range(len(supports)), hvar_rows, optimize=True)])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    vvar_rows = [[0] * len(supports) for _ in glyphs]
    if weights.shape[0] >= 7:
        vvar_rows[1] = row(weights[5])
        vvar_rows[2] = row(weights[6])
    vvar = newTable("VVAR")
    vvar.table = otTables.VVAR()
    vvar.table.Version = 0x00010000
    vvar.table.VarStore = buildVarStore(regions, [buildVarData(range(len(supports)), vvar_rows, optimize=True)])
    vvar.table.AdvHeightMap = None
    vvar.table.TsbMap = None
    vvar.table.BsbMap = None
    vvar.table.VOrgMap = None
    font["VVAR"] = vvar

    mvar_data = buildVarData(
        range(len(supports)),
        [row(weights[0]), row(weights[1]), row(weights[4])],
        optimize=True,
    )
    mvar = newTable("MVAR")
    mvar.table = otTables.MVAR()
    mvar.table.Version = 0x00010000
    mvar.table.Reserved = 0
    mvar.table.VarStore = buildVarStore(regions, [mvar_data])
    mvar.table.ValueRecordSize = 8
    mvar.table.ValueRecordCount = 3
    records = []
    for tag, index in (("xhgt", 0), ("cpht", 1), ("hasc", 2)):
        record = otTables.MetricsValueRecord()
        record.ValueTag = tag
        record.VarIdx = index
        records.append(record)
    mvar.table.ValueRecord = sorted(records, key=lambda item: item.ValueTag)
    font["MVAR"] = mvar

    def outline_variation(tag: str, negative: bool, delta: int) -> TupleVariation:
        coords = [(0, 0), (0, 0), (0, delta), (0, delta)] + [(0, 0)] * 4
        return TupleVariation({tag: ((-1, -1, 0) if negative else (0, 1, 1))}, coords)

    def outline_row(values: np.ndarray) -> list[TupleVariation]:
        output = []
        for tag, value in zip(tags, values.astype(np.int16).tolist()):
            if shifted_axes:
                output.append(outline_variation(tag, False, 2 * value))
            else:
                output.extend(
                    (
                        outline_variation(tag, True, -value),
                        outline_variation(tag, False, value),
                    )
                )
        return output

    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {name: [] for name in glyphs}
    if outline_variations:
        gvar.variations["x"] = outline_row(weights[0])
        gvar.variations["H"] = outline_row(weights[1])
    font["gvar"] = gvar

    font.recalcTimestamp = False
    font.save(destination)


def build_html(inputs: np.ndarray, expected: np.ndarray) -> str:
    settings = ",".join(f'"{axis_tag(i)}" {value:g}' for i, value in enumerate(inputs))
    properties = "\n".join(
        f'@property --o{i}{{syntax:"<number>";inherits:true;initial-value:-99999}}'
        for i in range(len(CHANNELS))
    )
    expected_text = ", ".join(f"{value:g}" for value in expected)
    return f'''<!doctype html>
<meta charset="utf-8">
<title>Variable-font multimetric probe</title>
<style>
@font-face{{font-family:MultiMetric;src:url("multi-metric.ttf") format("truetype")}}
{properties}
.producer{{font-family:MultiMetric;font-size:{FONT_SIZE}px;font-variation-settings:{settings};line-height:normal;
--o0:calc(1ex / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE});
--o1:calc(1cap / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE});
--o2:calc(1ch / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE});
--o3:calc(1ic / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE});
--o4:calc(1lh / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE});}}
.vertical{{writing-mode:vertical-rl;
--o5:calc(1ch / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE});
--o6:calc(1ic / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE});}}
.upright{{text-orientation:upright}}
.result{{font:16px monospace;writing-mode:horizontal-tb}}
.vglyph{{position:fixed;visibility:hidden;white-space:nowrap}}
</style>
<p>Expected: {expected_text}</p>
<div class="producer"><div class="vertical" id="mixed">
  <span class="vglyph" id="vzero">0</span><span class="vglyph" id="vwater">水</span>
  <div class="result" id="result">probe</div>
</div><div class="vertical upright" id="upright"><div class="result" id="upright-result">probe</div></div></div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weights, inputs = data()
    expected = weights.astype(np.float64) @ inputs
    build_font(weights, OUT / "multi-metric.ttf")
    (OUT / "index.html").write_text(build_html(inputs, expected))
    (OUT / "reference.json").write_text(json.dumps({
        "channels": CHANNELS,
        "input_width": INPUT_WIDTH,
        "units_per_em": UNITS_PER_EM,
        "font_size": FONT_SIZE,
        "base": BASE,
        "inputs": inputs.tolist(),
        "weights": weights.tolist(),
        "expected": expected.tolist(),
    }, indent=2) + "\n")
    print({"expected": expected.tolist(), "ttf_bytes": (OUT / "multi-metric.ttf").stat().st_size})


if __name__ == "__main__":
    main()
