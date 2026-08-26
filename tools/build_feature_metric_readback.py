#!/usr/bin/env python3
"""Build a no-JS numbered-GSUB/HVAR metric readback experiment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "feature-metric-readback"
INPUT_WIDTH = 32
PAIRS = 64
UNITS_PER_EM = 1_000
FONT_SIZE = 512
BASE = 2_000


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def rectangle() -> object:
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def test_data() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0x53414C54)
    weights = rng.integers(-20, 21, size=(PAIRS * 2, INPUT_WIDTH), dtype=np.int16)
    inputs = rng.integers(-4, 5, size=INPUT_WIDTH).astype(np.float64) / 4
    return weights, inputs


def build_font(weights: np.ndarray, path: Path) -> None:
    zeros = [f"zero.alt{index:03d}" for index in range(PAIRS)]
    waters = [f"water.alt{index:03d}" for index in range(PAIRS)]
    glyph_order = [".notdef", "zero", "water", *zeros, *waters]
    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x30: "zero", 0x6C34: "water"})
    shape = rectangle()
    fb.setupGlyf({name: shape for name in glyph_order})
    fb.setupHorizontalMetrics({name: (BASE, 0) for name in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({
        "familyName": "CSS Feature Metric Rows",
        "styleName": "Regular",
        "uniqueFontIdentifier": "CSS-Feature-Metric-Rows-Regular",
        "fullName": "CSS Feature Metric Rows Regular",
        "psName": "CSSFeatureMetricRows-Regular",
    })
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200,
                usWinAscent=800, usWinDescent=200, sxHeight=500, sCapHeight=700)
    fb.setupPost()
    fb.setupMaxp()
    fb.setupHead(created=2_082_844_800, modified=2_082_844_800)
    fb.font.recalcTimestamp = False
    fb.save(path)

    font = TTFont(path, recalcTimestamp=False)
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    tags = [axis_tag(index) for index in range(INPUT_WIDTH)]
    for index, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = -1
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
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    regions = buildVarRegionList(supports, tags)

    def encode(values: np.ndarray) -> list[int]:
        return [delta for value in values.astype(np.int16).tolist()
                for delta in (-value, value)]

    rows = [[0] * len(supports) for _ in glyph_order]
    glyph_ids = {name: index for index, name in enumerate(glyph_order)}
    for pair in range(PAIRS):
        rows[glyph_ids[zeros[pair]]] = encode(weights[pair * 2])
        rows[glyph_ids[waters[pair]]] = encode(weights[pair * 2 + 1])
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions, [buildVarData(range(len(supports)), rows, optimize=True)])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    alternates_zero = " ".join(zeros)
    alternates_water = " ".join(waters)
    addOpenTypeFeaturesFromString(font, f'''feature salt {{
      sub zero from [{alternates_zero}];
      sub water from [{alternates_water}];
    }} salt;''')
    font.recalcTimestamp = False
    font.save(path)


def nested_metric_nodes() -> str:
    child = '<div id="result">ready</div>'
    for pair in reversed(range(PAIRS)):
        child = f'<div class="pair pair-{pair:03d}">{child}</div>'
    return child


def common_css(inputs: np.ndarray) -> str:
    settings = ",".join(
        f'"{axis_tag(index)}" {value:g}' for index, value in enumerate(inputs))
    return f'''@font-face{{font-family:FeatureRows;src:url("feature-rows.ttf") format("truetype")}}
html{{font:14px monospace}} body{{margin:2rem}}
.root{{font-family:FeatureRows;font-size:{FONT_SIZE}px;font-variation-settings:{settings}}}
'''


def metric_html(inputs: np.ndarray) -> str:
    properties = []
    rules = []
    for pair in range(PAIRS):
        a = pair * 2
        b = a + 1
        properties.extend((
            f'@property --o{a:03d}{{syntax:"<number>";inherits:true;initial-value:-99999}}',
            f'@property --o{b:03d}{{syntax:"<number>";inherits:true;initial-value:-99999}}',
        ))
        rules.append(
            f'.pair-{pair:03d}{{font-feature-settings:"salt" {pair + 1};'
            f'--o{a:03d}:calc(1ch / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE});'
            f'--o{b:03d}:calc(1ic / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE})}}')
    return f'''<!doctype html><meta charset="utf-8"><title>Feature-indexed metric readback</title>
<style>{common_css(inputs)}{''.join(properties)}{''.join(rules)}
#result{{font:14px monospace}}</style>
<div class="root">{nested_metric_nodes()}</div>
'''


def geometry_html(inputs: np.ndarray) -> str:
    spans = "".join(
        f'<span class="glyph zero p{pair:03d}">0</span><span class="glyph water p{pair:03d}">水</span>'
        for pair in range(PAIRS))
    rules = "".join(
        f'.p{pair:03d}{{font-feature-settings:"salt" {pair + 1}}}'
        for pair in range(PAIRS))
    return f'''<!doctype html><meta charset="utf-8"><title>Feature-indexed geometry baseline</title>
<style>{common_css(inputs)}{rules}.glyph{{display:inline-block;line-height:1}}</style>
<div class="root">{spans}</div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weights, inputs = test_data()
    expected = weights.astype(np.float64) @ inputs
    build_font(weights, OUT / "feature-rows.ttf")
    (OUT / "index.html").write_text(metric_html(inputs))
    (OUT / "geometry.html").write_text(geometry_html(inputs))
    (OUT / "reference.json").write_text(json.dumps({
        "input_width": INPUT_WIDTH,
        "pairs": PAIRS,
        "units_per_em": UNITS_PER_EM,
        "font_size": FONT_SIZE,
        "base": BASE,
        "inputs": inputs.tolist(),
        "weights": weights.tolist(),
        "expected": expected.tolist(),
    }, indent=2) + "\n")
    print({"outputs": len(expected), "font_bytes": (OUT / "feature-rows.ttf").stat().st_size,
           "html_bytes": (OUT / "index.html").stat().st_size})


if __name__ == "__main__":
    main()
