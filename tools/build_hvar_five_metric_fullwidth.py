#!/usr/bin/env python3
"""Build a 768-input to five-output direct font-metric transport proof."""

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
OUT = ROOT / "experiments" / "hvar-five-metric-fullwidth"
WIDTH = 768
# Shift signed inputs into [0,1]. This needs one region rather than separate
# positive and negative regions per axis. The x-outline gvar header still grows
# quadratically with axis count, so 128 axes is the largest round shard size
# that stays safely below its 16-bit per-glyph offset.
SHARD = 128
SHARDS = 6
FONT_SIZE = 512
UNITS_PER_EM = 1_000
BASE = 16_000
DELTA_SCALE = 16
CHANNELS = ("ex", "cap", "ch", "ic", "lh")


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


def build_font(name: str, weights: np.ndarray, path: Path) -> None:
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
    fb.setupHorizontalMetrics({
        ".notdef": (500, 0), "zero": (BASE, 0), "water": (BASE, 0),
        "x": (500, 0), "H": (500, 0),
    })
    fb.setupHorizontalHeader(ascent=BASE, descent=0, lineGap=0)
    fb.setupNameTable({
        "familyName": f"CSS Five Metric {name}",
        "styleName": "Regular",
        "uniqueFontIdentifier": f"CSS-Five-Metric-{name}-Regular",
        "fullName": f"CSS Five Metric {name} Regular",
        "psName": f"CSSFiveMetric{name.title()}-Regular",
    })
    fb.setupOS2(
        version=4, sTypoAscender=BASE, sTypoDescender=0, sTypoLineGap=0,
        usWinAscent=BASE, usWinDescent=0, sxHeight=BASE, sCapHeight=BASE,
        fsSelection=0xC0,
    )
    fb.setupPost()
    fb.setupMaxp()
    fb.setupHead(created=2_082_844_800, modified=2_082_844_800)
    fb.font.recalcTimestamp = False
    fb.save(path)

    font = TTFont(path, recalcTimestamp=False)
    tags = [axis_tag(index) for index in range(SHARD)]
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

    supports = []
    encoded = [[] for _ in CHANNELS]
    for input_index, tag in enumerate(tags):
        supports.append({tag: (0, 1, 1)})
        for channel in range(len(CHANNELS)):
            value = int(weights[channel, input_index])
            encoded[channel].append(2 * DELTA_SCALE * value)
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
        regions,
        [buildVarData(range(len(supports)), [encoded[0], encoded[1], encoded[4]], optimize=True)],
    )
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

    def outline_tuple(support, delta):
        coordinates = [(0, 0), (0, 0), (0, delta), (0, delta)] + [(0, 0)] * 4
        return TupleVariation(support, coordinates)

    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {glyph: [] for glyph in glyphs}
    # Chrome exposes cap-height from MVAR directly, but derives ex-height from
    # the varied x outline. Only x therefore needs gvar tuples.
    for support, ex_delta in zip(supports, encoded[0]):
        gvar.variations["x"].append(outline_tuple(support, ex_delta))
    font["gvar"] = gvar
    font.recalcTimestamp = False
    font.save(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0x46554C4C)
    weights = rng.integers(-10, 11, size=(len(CHANNELS), WIDTH), dtype=np.int16)
    inputs = rng.uniform(-0.95, 0.95, size=WIDTH)
    font_bytes = []
    faces = []
    properties = []
    rules = []
    child = '<div id="result">ready</div>'
    units = ("1ex", "1cap", "1ch", "1ic", "1lh")

    for shard in range(SHARDS):
        start = shard * SHARD
        stop = start + SHARD
        font_path = OUT / f"shard-{shard}.ttf"
        web_font_path = OUT / f"shard-{shard}.woff"
        build_font(f"full{shard}", weights[:, start:stop], font_path)
        web_font = TTFont(font_path, recalcTimestamp=False)
        web_font.flavor = "woff"
        web_font.save(web_font_path)
        font_bytes.append(web_font_path.stat().st_size)
        faces.append(
            f'@font-face{{font-family:S{shard};src:url("shard-{shard}.woff") format("woff")}}')
        settings = ",".join(
            f'"{axis_tag(local)}" calc((var(--v{start + local:03d}) + 1) / 2)'
            for local in range(SHARD)
        )
        values = ";".join(
            f'--p{shard}{channel}:calc(({unit} / 1px * {UNITS_PER_EM} / {FONT_SIZE} '
            f'- {BASE}) / {DELTA_SCALE} + {-int(weights[channel, start:stop].sum())})'
            for channel, unit in enumerate(units)
        )
        rules.append(
            f'.s{shard}{{font-family:S{shard};font-size:{FONT_SIZE}px;line-height:normal;'
            f'font-variation-settings:{settings};{values}}}')
        child = f'<div class="s{shard}">{child}</div>'
        for channel in range(len(CHANNELS)):
            properties.append(
                f'@property --p{shard}{channel}{{syntax:"<number>";inherits:true;initial-value:-99999}}')

    for channel in range(len(CHANNELS)):
        properties.append(
            f'@property --o{channel}{{syntax:"<number>";inherits:true;initial-value:-99999}}')
    root_values = ";".join(
        f"--v{index:03d}:{value:.9g}" for index, value in enumerate(inputs))
    sums = ";".join(
        f'--o{channel}:calc(' + " + ".join(
            f"var(--p{shard}{channel})" for shard in range(SHARDS)) + ")"
        for channel in range(len(CHANNELS))
    )
    html = (
        '<!doctype html><meta charset="utf-8"><title>768 to five CSS metrics</title><style>'
        + "".join(faces) + "".join(properties)
        + f'.root{{{root_values}}}' + "".join(rules)
        + f'#result{{font:14px monospace;{sums}}}</style><div class="root">{child}</div>'
    )
    (OUT / "index.html").write_text(html)
    expected = weights.astype(float) @ inputs
    reference = {
        "width": WIDTH,
        "channels": list(CHANNELS),
        "inputs": inputs.tolist(),
        "weights": weights.tolist(),
        "expected": expected.tolist(),
        "font_bytes": sum(font_bytes),
        "sfnt_bytes": sum((OUT / f"shard-{shard}.ttf").stat().st_size for shard in range(SHARDS)),
        "html_bytes": len(html.encode()),
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({
        "expected": expected.tolist(),
        "font_bytes": sum(font_bytes),
        "sfnt_bytes": reference["sfnt_bytes"],
        "html_bytes": len(html.encode()),
    })


if __name__ == "__main__":
    main()
