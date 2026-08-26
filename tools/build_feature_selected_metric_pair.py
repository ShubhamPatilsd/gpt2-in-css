#!/usr/bin/env python3
"""Test whether GSUB-selected glyphs can expose two HVAR rows through ch/ic."""

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
OUT = ROOT / "experiments" / "feature-selected-metric-pair"
INPUTS = 8
PAIRS = 8
UNITS_PER_EM = 1_000
FONT_SIZE = 256
BASE = 8_000


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def rectangle():
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def build_font(weights: np.ndarray, destination: Path) -> None:
    glyphs = [".notdef", "zero", "water"]
    glyphs += [f"k{pair}" for pair in range(PAIRS)]
    glyphs += [f"v{pair}" for pair in range(PAIRS)]
    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyphs)
    builder.setupCharacterMap({0x30: "zero", 0x6C34: "water"})
    builder.setupGlyf({name: rectangle() for name in glyphs})
    builder.setupHorizontalMetrics({name: (BASE, 0) for name in glyphs})
    builder.setupHorizontalHeader(ascent=1_000, descent=0)
    builder.setupNameTable({
        "familyName": "Feature Metric Pair",
        "styleName": "Regular",
        "uniqueFontIdentifier": "FeatureMetricPair-Regular",
        "fullName": "Feature Metric Pair Regular",
        "psName": "FeatureMetricPair-Regular",
    })
    builder.setupOS2(
        version=4,
        sTypoAscender=1_000,
        sTypoDescender=0,
        usWinAscent=1_000,
        usWinDescent=0,
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.setupHead(created=2_082_844_800, modified=2_082_844_800)
    builder.font.recalcTimestamp = False
    builder.save(destination)

    font = TTFont(destination, recalcTimestamp=False)
    tags = [axis_tag(index) for index in range(INPUTS)]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
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

    supports = [
        support
        for tag in tags
        for support in ({tag: (-1, -1, 0)}, {tag: (0, 1, 1)})
    ]
    regions = buildVarRegionList(supports, tags)

    def variation_row(values: np.ndarray) -> list[int]:
        return [delta for value in values.tolist() for delta in (-int(value), int(value))]

    rows = [[0] * len(supports) for _ in glyphs]
    glyph_index = {name: index for index, name in enumerate(glyphs)}
    for pair in range(PAIRS):
        rows[glyph_index[f"k{pair}"]] = variation_row(weights[pair, 0])
        rows[glyph_index[f"v{pair}"]] = variation_row(weights[pair, 1])
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions,
        [buildVarData(range(len(supports)), rows, optimize=True)],
    )
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    feature_source = (
        "languagesystem DFLT dflt;\n"
        "feature cv01 {\n"
        + "  sub zero from [" + " ".join(f"k{pair}" for pair in range(PAIRS)) + "];\n"
        + "  sub water from [" + " ".join(f"v{pair}" for pair in range(PAIRS)) + "];\n"
        + "} cv01;\n"
    )
    addOpenTypeFeaturesFromString(font, feature_source)
    font.recalcTimestamp = False
    font.save(destination)


def build_html(inputs: np.ndarray) -> str:
    settings = ",".join(
        f'"{axis_tag(index)}" {value:g}' for index, value in enumerate(inputs)
    )
    pairs = "".join(
        f'<i class="pair pair-{pair}" style="font-feature-settings:\'cv01\' {pair + 1}"></i>'
        for pair in range(PAIRS)
    )
    glyph_checks = "".join(
        f'<span class="glyph-check glyph-check-{pair}" '
        f'style="font-feature-settings:\'cv01\' {pair + 1}">0水</span>'
        for pair in range(PAIRS)
    )
    face_rules = "".join(
        f'@font-face{{font-family:FeatureMetricPair{pair};'
        'src:url("feature-metric-pair.ttf") format("truetype");'
        f'font-feature-settings:"cv01" {pair + 1}}}'
        for pair in range(PAIRS)
    )
    face_pairs = "".join(
        f'<i class="face-pair face-pair-{pair}" '
        f'style="font-family:FeatureMetricPair{pair}"></i>'
        for pair in range(PAIRS)
    )
    return f'''<!doctype html>
<meta charset="utf-8">
<title>Feature-selected ch/ic HVAR pairs</title>
<style>
@font-face{{font-family:FeatureMetricPair;src:url("feature-metric-pair.ttf") format("truetype")}}
{face_rules}
.producer{{font-family:FeatureMetricPair;font-size:{FONT_SIZE}px;font-variation-settings:{settings}}}
.pair{{position:fixed;display:block;width:1ch;height:1ic}}
.glyph-check{{position:fixed;display:inline-block;white-space:nowrap}}
.face-pair{{position:fixed;display:block;width:1ch;height:1ic}}
.dynamic-check{{position:fixed;display:inline-block;white-space:nowrap}}
#dynamic-var{{--choice:1;font-feature-settings:"cv01" var(--choice)}}
#dynamic-round{{--choice-number:1.2;font-feature-settings:"cv01" calc(round(nearest,var(--choice-number),1))}}
</style>
<div class="producer">{pairs}{glyph_checks}{face_pairs}
<span class="dynamic-check" id="dynamic-var">0水</span>
<span class="dynamic-check" id="dynamic-round">0水</span>
</div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0xC701)
    weights = rng.integers(-24, 25, size=(PAIRS, 2, INPUTS), dtype=np.int16)
    inputs = rng.integers(-4, 5, size=INPUTS).astype(np.float64) / 4
    build_font(weights, OUT / "feature-metric-pair.ttf")
    (OUT / "index.html").write_text(build_html(inputs))
    (OUT / "reference.json").write_text(json.dumps({
        "inputs": inputs.tolist(),
        "weights": weights.tolist(),
        "pairs": PAIRS,
        "inputWidth": INPUTS,
        "unitsPerEm": UNITS_PER_EM,
        "fontSize": FONT_SIZE,
        "base": BASE,
        "runtimeJavaScript": False,
    }, indent=2) + "\n")
    print({
        "pairs": PAIRS,
        "fontBytes": (OUT / "feature-metric-pair.ttf").stat().st_size,
    })


if __name__ == "__main__":
    main()
