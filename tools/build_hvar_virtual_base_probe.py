#!/usr/bin/env python3
"""Build a probe for accumulating a >uint16 virtual HVAR base."""

from __future__ import annotations

import json
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "hvar-virtual-base"
UNITS_PER_EM = 1000
FONT_SIZE = 10
AXIS_COUNT = 30
AXIS_TAGS = [f"V{index:03d}" for index in range(AXIS_COUNT)]
CODEPOINT_START = 0xE200


def vector(positive_count: int, positive: int, negative_count: int, negative: int) -> list[int]:
    values = [0] * AXIS_COUNT
    for index in range(positive_count):
        values[index] = positive
    for index in range(negative_count):
        values[15 + index] = negative
    return values


CASES = [
    ("small", 1000, vector(1, 30000, 1, -20000)),
    ("crosses-uint16", 65000, vector(1, 30000, 2, -25000)),
    ("virtual-301k", 1000, vector(10, 30000, 10, -29000)),
    ("virtual-493k", 1000, vector(15, 32767, 15, -30000)),
]


def glyph() -> object:
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def build_font(destination: Path, region_order: list[int]) -> list[dict[str, object]]:
    glyph_order = [".notdef"]
    cmap: dict[int, str] = {}
    metrics: dict[str, tuple[int, int]] = {".notdef": (0, 0)}
    rows = [[0] * AXIS_COUNT]
    records = []
    for index, (name, base, deltas) in enumerate(CASES):
        target = f"target{index}"
        sentinel = f"sentinel{index}"
        target_codepoint = CODEPOINT_START + 2 * index
        sentinel_codepoint = target_codepoint + 1
        for glyph_name, codepoint, advance, row in (
            (target, target_codepoint, base, deltas),
            (sentinel, sentinel_codepoint, 1, [0] * AXIS_COUNT),
        ):
            glyph_order.append(glyph_name)
            cmap[codepoint] = glyph_name
            metrics[glyph_name] = (advance, 0)
            rows.append([row[column] for column in region_order])
        records.append(
            {
                "name": name,
                "codepoints": [target_codepoint, sentinel_codepoint],
                "base": base,
                "positiveBias": sum(value for value in deltas if value > 0),
                "negativeContribution": sum(value for value in deltas if value < 0),
                "expected": base + sum(deltas),
            }
        )

    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf({name: glyph() for name in glyph_order})
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=UNITS_PER_EM, descent=0)
    builder.setupNameTable(
        {
            "familyName": f"HVAR Virtual Base {destination.stem}",
            "styleName": "Regular",
            "uniqueFontIdentifier": f"hvar-virtual-base-{destination.stem}",
            "fullName": f"HVAR Virtual Base {destination.stem}",
            "psName": f"HVARVirtualBase-{destination.stem}",
        }
    )
    builder.setupOS2(
        sTypoAscender=UNITS_PER_EM,
        sTypoDescender=0,
        usWinAscent=UNITS_PER_EM,
        usWinDescent=0,
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.setupHead(created=2_082_844_800, modified=2_082_844_800)
    builder.font.recalcTimestamp = False
    builder.save(destination)

    font = TTFont(destination, recalcTimestamp=False)
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for ordering, tag in enumerate(AXIS_TAGS):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = 0
        axis.defaultValue = 0
        axis.maxValue = 1
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": ordering})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    supports = [{AXIS_TAGS[index]: (0, 1, 1)} for index in region_order]
    region_list = buildVarRegionList(supports, AXIS_TAGS)
    # optimize=False preserves the serialized positive-first/negative-first
    # order, which catches implementations that saturate while accumulating.
    var_data = buildVarData(range(AXIS_COUNT), rows, optimize=False)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(region_list, [var_data])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {name: [] for name in glyph_order}
    font["gvar"] = gvar
    font.recalcTimestamp = False
    font.save(destination)
    compressed = TTFont(destination, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(destination.with_suffix(".woff2"))
    return records


def render_html(records: list[dict[str, object]]) -> str:
    settings = ",".join(f'"{tag}" 1' for tag in AXIS_TAGS)
    rows = []
    for index, record in enumerate(records):
        text = "".join(chr(codepoint) for codepoint in record["codepoints"])
        rows.append(
            f'<g data-case="{record["name"]}" transform="translate(0 {index * 100})">'
            f'<text class="base" x="20" y="25">{text}</text>'
            f'<text class="bias-first" x="20" y="55">{text}</text>'
            f'<text class="negative-first" x="20" y="85">{text}</text>'
            "</g>"
        )
    return f'''<!doctype html>
<meta charset="utf-8">
<title>HVAR virtual base probe</title>
<style>
@font-face{{font-family:BiasFirst;src:url("bias-first.woff2?v=1") format("woff2")}}
@font-face{{font-family:NegativeFirst;src:url("negative-first.woff2?v=1") format("woff2")}}
svg{{display:block;width:700px;height:{len(records) * 100}px;overflow:visible}}
text{{font-size:{FONT_SIZE}px;font-kerning:none}}
.base{{font-family:BiasFirst}}
.bias-first{{font-family:BiasFirst;font-variation-settings:{settings}}}
.negative-first{{font-family:NegativeFirst;font-variation-settings:{settings}}}
</style>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 {len(records) * 100}">
{''.join(rows)}
</svg>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bias_first = list(range(AXIS_COUNT))
    negative_first = list(range(15, AXIS_COUNT)) + list(range(15))
    records = build_font(OUT / "bias-first.ttf", bias_first)
    other = build_font(OUT / "negative-first.ttf", negative_first)
    if records != other:
        raise RuntimeError("order variants produced different references")
    (OUT / "index.html").write_text(render_html(records))
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "unitsPerEm": UNITS_PER_EM,
                "fontSize": FONT_SIZE,
                "scale": FONT_SIZE / UNITS_PER_EM,
                "axes": AXIS_COUNT,
                "cases": records,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"built {OUT}")


if __name__ == "__main__":
    main()
