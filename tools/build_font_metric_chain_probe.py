#!/usr/bin/env python3
"""Build direct font-metric-to-font-axis chaining probes."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "font-metric-chain-probe"
UPEM = 1_000
FONT_SIZE = 256
BASE = 8_000
SCALE = 256
AXIS_RANGE = 16
CHANNELS = ("ex", "cap", "ch", "ic", "lh")
UNITS = ("1ex", "1cap", "1ch", "1ic", "1lh")


def rectangle(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((width, 0))
    pen.lineTo((width, height))
    pen.lineTo((0, height))
    pen.closePath()
    return pen.glyph()


def setup_axes(font: TTFont, tags: list[str], minimum: float, maximum: float) -> None:
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for index, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = minimum
        axis.defaultValue = 0
        axis.maxValue = maximum
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)


def build_producer(weights: np.ndarray, path: Path) -> None:
    glyphs = [".notdef", "zero", "water", "x", "H"]
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({0x30: "zero", 0x6C34: "water", 0x78: "x", 0x48: "H"})
    fb.setupGlyf({
        ".notdef": rectangle(1, 1), "zero": rectangle(1, 1),
        "water": rectangle(1, 1), "x": rectangle(1, BASE),
        "H": rectangle(1, BASE),
    })
    fb.setupHorizontalMetrics({
        ".notdef": (500, 0), "zero": (BASE, 0), "water": (BASE, 0),
        "x": (500, 0), "H": (500, 0),
    })
    fb.setupHorizontalHeader(ascent=BASE, descent=0, lineGap=0)
    fb.setupNameTable({
        "familyName": "CSS Metric Chain Producer", "styleName": "Regular",
        "uniqueFontIdentifier": "CSS-Metric-Chain-Producer",
        "fullName": "CSS Metric Chain Producer", "psName": "CSSMetricChainProducer",
    })
    fb.setupOS2(
        version=4, sTypoAscender=BASE, sTypoDescender=0, sTypoLineGap=0,
        usWinAscent=BASE, usWinDescent=0, sxHeight=BASE, sCapHeight=BASE,
        fsSelection=0xC0,
    )
    fb.setupPost()
    fb.setupMaxp()
    fb.save(path)
    font = TTFont(path, recalcTimestamp=False)
    tags = [f"X{i:03d}" for i in range(5)]
    setup_axes(font, tags, -1, 1)
    supports = []
    encoded = [[] for _ in CHANNELS]
    for input_index, tag in enumerate(tags):
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
        for channel in range(5):
            delta = SCALE * int(weights[channel, input_index])
            encoded[channel].extend((-delta, delta))
    regions = buildVarRegionList(supports, tags)
    hvar_rows = [[0] * len(supports) for _ in glyphs]
    hvar_rows[1] = encoded[2]
    hvar_rows[2] = encoded[3]
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions, [buildVarData(range(len(supports)), hvar_rows, optimize=True)])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar
    mvar = newTable("MVAR")
    mvar.table = otTables.MVAR()
    mvar.table.Version = 0x00010000
    mvar.table.Reserved = 0
    mvar.table.VarStore = buildVarStore(
        regions, [buildVarData(range(len(supports)), [encoded[0], encoded[1], encoded[4]])])
    mvar.table.ValueRecordSize = 8
    mvar.table.ValueRecordCount = 3
    records = []
    for index, tag in enumerate(("xhgt", "cpht", "hasc")):
        record = otTables.MetricsValueRecord()
        record.ValueTag = tag
        record.VarIdx = index
        records.append(record)
    mvar.table.ValueRecord = sorted(records, key=lambda record: record.ValueTag)
    font["MVAR"] = mvar
    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {glyph: [] for glyph in glyphs}
    for support, delta in zip(supports, encoded[0]):
        coordinates = [(0, 0), (0, 0), (0, delta), (0, delta)] + [(0, 0)] * 4
        gvar.variations["x"].append(TupleVariation(support, coordinates))
    font["gvar"] = gvar
    font.save(path)


def build_consumer(weights: np.ndarray, path: Path) -> None:
    glyphs = [".notdef", "zero"]
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({0x30: "zero"})
    fb.setupGlyf({glyph: rectangle(1, 1) for glyph in glyphs})
    fb.setupHorizontalMetrics({".notdef": (500, 0), "zero": (BASE, 0)})
    fb.setupHorizontalHeader(ascent=BASE, descent=0, lineGap=0)
    fb.setupNameTable({
        "familyName": "CSS Metric Chain Consumer", "styleName": "Regular",
        "uniqueFontIdentifier": "CSS-Metric-Chain-Consumer",
        "fullName": "CSS Metric Chain Consumer", "psName": "CSSMetricChainConsumer",
    })
    fb.setupOS2(
        version=4, sTypoAscender=BASE, sTypoDescender=0, sTypoLineGap=0,
        usWinAscent=BASE, usWinDescent=0, fsSelection=0xC0,
    )
    fb.setupPost()
    fb.setupMaxp()
    fb.save(path)
    font = TTFont(path, recalcTimestamp=False)
    tags = [f"Y{i:03d}" for i in range(5)]
    setup_axes(font, tags, -AXIS_RANGE, AXIS_RANGE)
    supports = []
    deltas = []
    for tag, weight in zip(tags, weights):
        delta = int(weight) * SCALE * AXIS_RANGE
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
        deltas.extend((-delta, delta))
    regions = buildVarRegionList(supports, tags)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        regions,
        [buildVarData(range(len(supports)), [[0] * len(supports), deltas], optimize=True)],
    )
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar
    font.save(path)


def css_header(registered: bool) -> str:
    registrations = ""
    if registered:
        registrations = "".join(
            f'@property --m{i}{{syntax:"<number>";inherits:true;initial-value:-999}}'
            for i in range(5)
        )
    registrations += '@property --z{syntax:"<number>";inherits:true;initial-value:-999}'
    return f'''@font-face{{font-family:Producer;src:url("producer.ttf")}}
@font-face{{font-family:Consumer;src:url("consumer.ttf")}}
{registrations}
.root{{--x0:-.75;--x1:.25;--x2:.5;--x3:-.4;--x4:.8}}
.producer{{font-family:Producer;font-size:{FONT_SIZE}px;line-height:normal;
font-variation-settings:"X000" var(--x0),"X001" var(--x1),"X002" var(--x2),"X003" var(--x3),"X004" var(--x4)}}
.consumer{{font-family:Consumer;font-size:{FONT_SIZE}px;line-height:normal}}
'''


def metric_assignments() -> str:
    return ";".join(
        f"--m{i}:calc(({unit} / 1px * {UPEM} / {FONT_SIZE} - {BASE}) / {SCALE})"
        for i, unit in enumerate(UNITS)
    )


def consumer_settings(expressions: list[str]) -> str:
    return ",".join(f'"Y{i:03d}" {expression}' for i, expression in enumerate(expressions))


def page(style: str, body: str, title: str) -> str:
    return f'<!doctype html><meta charset="utf-8"><title>{title}</title><style>{style}</style>{body}'


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    first = np.asarray([
        [2, -1, 0, 1, 3],
        [-2, 1, 2, 0, 1],
        [1, 3, -1, 2, 0],
        [0, -2, 3, 1, -1],
        [3, 0, 1, -3, 2],
    ], dtype=np.int16)
    second = np.asarray([1, -2, 3, -4, 5], dtype=np.int16)
    inputs = np.asarray([-0.75, 0.25, 0.5, -0.4, 0.8])
    intermediate = first.astype(float) @ inputs
    expected = float(second.astype(float) @ intermediate)
    build_producer(first, OUT / "producer.ttf")
    build_consumer(second, OUT / "consumer.ttf")

    capture = metric_assignments()
    axis_vars = [f"var(--m{i})" for i in range(5)]
    output = f'--z:calc((1ch / 1px * {UPEM} / {FONT_SIZE} - {BASE}) / {SCALE})'
    registered = css_header(True) + (
        f'.producer{{{capture}}}.consumer{{font-variation-settings:{consumer_settings(axis_vars)};{output}}}'
    )
    body = '<div class="root"><div class="producer"><div id="result" class="consumer">ready</div></div></div>'
    (OUT / "registered.html").write_text(page(registered, body, "registered metric chain"))

    unregistered = css_header(False) + (
        f'.producer{{{capture}}}.consumer{{font-variation-settings:{consumer_settings(axis_vars)};{output}}}'
    )
    (OUT / "unregistered.html").write_text(page(unregistered, body, "unregistered metric chain"))

    direct_expressions = [
        f"calc(({unit} / 1px * {UPEM} / {FONT_SIZE} - {BASE}) / {SCALE})"
        for unit in UNITS
    ]
    direct = css_header(False) + (
        f'.consumer{{font-variation-settings:{consumer_settings(direct_expressions)};{output}}}'
    )
    (OUT / "direct.html").write_text(page(direct, body, "direct metric expressions"))

    # One scalar can cross a font boundary through computed font-size. `1ch`
    # on font-size resolves against the parent producer; `1em` on the child
    # then recovers that length. It cannot carry the other four values.
    size_axis = f'calc((1em / 1px * {UPEM} / {FONT_SIZE} - {BASE}) / {SCALE})'
    size_output = f'--z:calc((1ch / 1em * {UPEM} - {BASE}) / {SCALE})'
    font_size = css_header(False) + (
        f'.carrier{{font-size:1ch}}.consumer{{font-size:inherit;'
        f'font-variation-settings:"Y000" {size_axis};{size_output}}}'
    )
    size_body = '<div class="root"><div class="producer"><div class="carrier"><div id="result" class="consumer">ready</div></div></div></div>'
    (OUT / "font-size.html").write_text(page(font_size, size_body, "font-size metric carrier"))

    calc_size = css_header(False) + (
        f'.consumer{{font-variation-settings:"Y000" calc(calc-size(auto,size) / 1px);{output}}}'
    )
    (OUT / "calc-size.html").write_text(page(calc_size, body, "calc-size axis attempt"))

    (OUT / "reference.json").write_text(json.dumps({
        "inputs": inputs.tolist(),
        "first_weights": first.tolist(),
        "intermediate": intermediate.tolist(),
        "second_weights": second.tolist(),
        "expected": expected,
        "font_size_expected_input": float(intermediate[2]),
        "font_bytes": (OUT / "producer.ttf").stat().st_size + (OUT / "consumer.ttf").stat().st_size,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
