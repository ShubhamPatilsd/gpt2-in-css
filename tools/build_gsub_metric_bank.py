#!/usr/bin/env python3
"""Expose many HVAR matrix rows through one font and GSUB selectors."""

from __future__ import annotations

import json
import math
import os
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

from build_font_multimetric_probe import BASE, FONT_SIZE, UNITS_PER_EM, axis_tag


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get(
    "GSUB_METRIC_BANK_OUT", ROOT / "experiments" / "gsub-metric-bank"
)).resolve()
INPUT_WIDTH = int(os.environ.get("GSUB_METRIC_BANK_INPUTS", "32"))
OUTPUT_WIDTH = int(os.environ.get("GSUB_METRIC_BANK_OUTPUTS", "64"))
FONT_FORMAT = os.environ.get("GSUB_METRIC_BANK_FORMAT", "woff")
if FONT_FORMAT not in {"ttf", "woff", "woff2"}:
    raise ValueError("GSUB_METRIC_BANK_FORMAT must be ttf, woff, or woff2")


def rectangle(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((width, 0))
    pen.lineTo((width, height))
    pen.lineTo((0, height))
    pen.closePath()
    return pen.glyph()


def settings(values: np.ndarray) -> str:
    return ",".join(
        f'"{axis_tag(index)}" {float(value):.12g}'
        for index, value in enumerate(values)
    )


def build_font(weights: np.ndarray, destination: Path) -> None:
    pair_count = math.ceil(OUTPUT_WIDTH / 2)
    zeros = [f"z{index:03d}" for index in range(pair_count)]
    waters = [f"w{index:03d}" for index in range(pair_count)]
    glyphs = [".notdef", "zero", "water", *zeros, *waters]
    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({0x30: "zero", 0x6C34: "water"})
    fb.setupGlyf({name: rectangle(1, 1) for name in glyphs})
    fb.setupHorizontalMetrics({name: (BASE, 0) for name in glyphs})
    fb.setupHorizontalHeader(ascent=BASE, descent=0, lineGap=0)
    fb.setupNameTable({
        "familyName": "GSUB Metric Bank",
        "styleName": "Regular",
        "uniqueFontIdentifier": "GSUBMetricBank-Regular",
        "fullName": "GSUB Metric Bank Regular",
        "psName": "GSUBMetricBank-Regular",
    })
    fb.setupOS2(
        version=4,
        sTypoAscender=BASE,
        sTypoDescender=0,
        sTypoLineGap=0,
        usWinAscent=BASE,
        usWinDescent=0,
        fsSelection=0xC0,
    )
    fb.setupPost()
    fb.setupMaxp()
    fb.setupHead(created=2_082_844_800, modified=2_082_844_800)
    fb.font.recalcTimestamp = False
    fb.save(destination)

    font = TTFont(destination, recalcTimestamp=False)
    tags = [axis_tag(index) for index in range(INPUT_WIDTH)]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for index, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = 0
        axis.defaultValue = 0
        axis.maxValue = 1
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    supports = [{tag: (0, 1, 1)} for tag in tags]
    regions = buildVarRegionList(supports, tags)
    rows = [[0] * INPUT_WIDTH for _ in glyphs]
    glyph_index = {name: index for index, name in enumerate(glyphs)}
    for pair in range(pair_count):
        first = pair * 2
        rows[glyph_index[zeros[pair]]] = (2 * weights[first]).astype(np.int16).tolist()
        if first + 1 < OUTPUT_WIDTH:
            rows[glyph_index[waters[pair]]] = (
                2 * weights[first + 1]
            ).astype(np.int16).tolist()
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions,
        [buildVarData(range(INPUT_WIDTH), rows, optimize=True)],
    )
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {name: [] for name in glyphs}
    font["gvar"] = gvar

    feature = (
        "feature cv01 {\n"
        + "  sub zero from [" + " ".join(zeros) + "];\n"
        + "  sub water from [" + " ".join(waters) + "];\n"
        + "} cv01;\n"
    )
    addOpenTypeFeaturesFromString(font, feature)
    font.recalcTimestamp = False
    font.save(destination)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0x47535542)
    weights = rng.integers(
        -16, 17, size=(OUTPUT_WIDTH, INPUT_WIDTH), dtype=np.int16
    )
    inputs = rng.integers(-4, 5, size=INPUT_WIDTH).astype(np.float64) / 4
    alternate_inputs = inputs.copy()
    alternate_inputs[::5] = np.clip(alternate_inputs[::5] + 0.25, -1, 1)
    expected = weights.astype(np.float64) @ inputs
    alternate_expected = weights.astype(np.float64) @ alternate_inputs

    temporary = OUT / "metric-bank.ttf"
    build_font(weights, temporary)
    sfnt_bytes = temporary.stat().st_size
    if FONT_FORMAT == "ttf":
        destination = temporary
    else:
        font = TTFont(temporary, recalcTimestamp=False)
        font.flavor = FONT_FORMAT
        destination = OUT / f"metric-bank.{FONT_FORMAT}"
        font.save(destination)
        temporary.unlink()

    properties = "".join(
        f'@property --o{output}{{syntax:"<number>";inherits:true;initial-value:-99999}}'
        for output in range(OUTPUT_WIDTH)
    )
    rules = []
    pair_count = math.ceil(OUTPUT_WIDTH / 2)
    for pair in range(pair_count):
        first = pair * 2
        declarations = [
            f"--o{first}:calc(1ch / 1px * {UNITS_PER_EM} / {FONT_SIZE} "
            f"- {BASE + int(weights[first].sum())})"
        ]
        if first + 1 < OUTPUT_WIDTH:
            declarations.append(
                f"--o{first + 1}:calc(1ic / 1px * {UNITS_PER_EM} / {FONT_SIZE} "
                f"- {BASE + int(weights[first + 1].sum())})"
            )
        rules.append(
            f'.g{pair:03d}{{font-feature-settings:"cv01" {pair + 1};'
            + ";".join(declarations)
            + "}"
        )
    content = '<div id="result">GSUB metric bank</div>'
    for pair in reversed(range(pair_count)):
        content = f'<div class="g{pair:03d}">{content}</div>'
    font_filename = destination.name
    html = (
        '<!doctype html><meta charset="utf-8"><title>GSUB metric bank</title><style>'
        f'@font-face{{font-family:GSUBBank;src:url("{font_filename}") '
        f'format("{("truetype" if FONT_FORMAT == "ttf" else FONT_FORMAT)}")}}'
        + properties
        + f'.bank{{font-family:GSUBBank;font-size:{FONT_SIZE}px;line-height:normal;'
        + 'font-variation-settings:'
        + settings((inputs + 1) / 2)
        + "}"
        + "".join(rules)
        + "</style>"
        + f'<div id="bank" class="bank">{content}</div>'
    )
    (OUT / "index.html").write_text(html)
    reference = {
        "inputWidth": INPUT_WIDTH,
        "totalInputWidth": INPUT_WIDTH,
        "shardCount": 1,
        "outputWidth": OUTPUT_WIDTH,
        "inputs": inputs.tolist(),
        "alternateInputs": alternate_inputs.tolist(),
        "weights": weights.tolist(),
        "expected": expected.tolist(),
        "alternateExpected": alternate_expected.tolist(),
        "fontBytes": destination.stat().st_size,
        "sfntBytes": sfnt_bytes,
        "htmlBytes": len(html.encode()),
        "shifted": True,
        "backend": "gsub-metric-bank",
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({
        "inputs": INPUT_WIDTH,
        "outputs": OUTPUT_WIDTH,
        "selectors": pair_count,
        "font_bytes": destination.stat().st_size,
        "sfnt_bytes": sfnt_bytes,
        "html_bytes": len(html.encode()),
    })


if __name__ == "__main__":
    main()
