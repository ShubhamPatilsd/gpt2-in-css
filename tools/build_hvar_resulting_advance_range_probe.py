#!/usr/bin/env python3
"""Build a focused probe for out-of-range resulting HVAR advances."""

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
OUT = ROOT / "experiments" / "hvar-resulting-advance-range"
UNITS_PER_EM = 1_000
FONT_SIZE = 64
AXIS_TAG = "TEST"
CODEPOINT_START = 0xE100

# name, target base, delta at min, delta at max, fixed compensator.
# The max endpoint is the range-under-test; min is a meaningful in-range
# endpoint rather than an alias for default. All HVAR deltas fit int16.
CASES = (
    ("negative-mild", 1_000, 2_000, -2_000, 5_000),
    ("negative-large", 1_000, 11_000, -11_000, 15_000),
    ("above-mild", 65_000, -2_000, 2_000, 1_000),
    ("above-large", 65_000, -30_000, 30_000, 1_000),
    ("control-low", 1_000, 900, -900, 5_000),
    ("control-high", 65_000, -500, 500, 1_000),
    ("control-zero", 1_000, 1_000, -1_000, 5_000),
)


def glyph():
    """A tiny contour avoids zero-glyf WOFF2 rejection without affecting widths."""
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def result(base: int, delta_min: int, delta_max: int, axis: int) -> int:
    return base + (delta_min if axis == -1 else delta_max if axis == 1 else 0)


def hypotheses(value: int, compensator: int) -> dict[str, dict[str, int]]:
    per_glyph_clamped = min(65_535, max(0, value))
    per_glyph_wrapped = value % 65_536
    unclamped_run = value + compensator + 1
    return {
        "target": {
            "unclamped": value,
            "clamp0To65535": per_glyph_clamped,
            "uint16Wrap": per_glyph_wrapped,
        },
        "run": {
            "unclamped": unclamped_run,
            "perGlyphClamp0To65535": per_glyph_clamped + compensator + 1,
            "perGlyphUint16Wrap": per_glyph_wrapped + compensator + 1,
            "runClamp0To65535": min(65_535, max(0, unclamped_run)),
            "runUint16Wrap": unclamped_run % 65_536,
        },
    }


def build_font(destination: Path) -> list[dict[str, object]]:
    order = [".notdef"]
    cmap: dict[int, str] = {}
    metrics: dict[str, tuple[int, int]] = {".notdef": (500, 0)}
    rows = [[0, 0]]
    records: list[dict[str, object]] = []
    next_codepoint = CODEPOINT_START

    for index, (name, base, delta_min, delta_max, compensator) in enumerate(CASES):
        target_name = f"target{index}"
        compensator_name = f"compensator{index}"
        sentinel_name = f"sentinel{index}"
        codepoints = [next_codepoint, next_codepoint + 1, next_codepoint + 2]
        next_codepoint += 3
        for glyph_name, codepoint, advance, deltas in (
            (target_name, codepoints[0], base, [delta_min, delta_max]),
            (compensator_name, codepoints[1], compensator, [0, 0]),
            (sentinel_name, codepoints[2], 1, [0, 0]),
        ):
            order.append(glyph_name)
            cmap[codepoint] = glyph_name
            metrics[glyph_name] = (advance, 0)
            rows.append(deltas)
        records.append({
            "name": name,
            "codepoints": codepoints,
            "base": base,
            "deltaAtMin": delta_min,
            "deltaAtMax": delta_max,
            "compensator": compensator,
            "predictions": {
                str(axis): hypotheses(result(base, delta_min, delta_max, axis), compensator)
                for axis in (-1, 0, 1)
            },
        })

    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf({name: glyph() for name in order})
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=UNITS_PER_EM, descent=0, lineGap=0)
    builder.setupNameTable({
        "familyName": "HVAR Result Range Probe",
        "styleName": "Regular",
        "uniqueFontIdentifier": "hvar-result-range-probe-regular",
        "fullName": "HVAR Result Range Probe Regular",
        "psName": "HVARResultRangeProbe-Regular",
    })
    builder.setupOS2(
        version=4, sTypoAscender=UNITS_PER_EM, sTypoDescender=0, sTypoLineGap=0,
        usWinAscent=UNITS_PER_EM, usWinDescent=0, fsSelection=0xC0,
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.setupHead(created=2_082_844_800, modified=2_082_844_800)
    builder.font.recalcTimestamp = False
    builder.save(destination)

    font = TTFont(destination, recalcTimestamp=False)
    axis = Axis()
    axis.axisTag = AXIS_TAG
    axis.minValue = -1
    axis.defaultValue = 0
    axis.maxValue = 1
    axis.flags = 0
    axis.axisNameID = font["name"].addName("Resulting advance test")
    fvar = newTable("fvar")
    fvar.axes = [axis]
    fvar.instances = []
    font["fvar"] = fvar
    buildStatTable(font, [{"tag": AXIS_TAG, "name": axis.axisNameID, "ordering": 0}])
    region_list = buildVarRegionList([
        {AXIS_TAG: (-1.0, -1.0, 0.0)},
        {AXIS_TAG: (0.0, 1.0, 1.0)},
    ], [AXIS_TAG])
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(
        region_list, [buildVarData([0, 1], rows, optimize=False)])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar
    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {name: [] for name in order}
    font["gvar"] = gvar
    font.recalcTimestamp = False
    font.save(destination)
    compressed = TTFont(destination, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(destination.with_suffix(".woff2"))
    return records


def build_html(records: list[dict[str, object]]) -> str:
    html_rows = []
    svg_rows = []
    for index, record in enumerate(records):
        target, compensator, sentinel = [chr(value) for value in record["codepoints"]]
        forward = target + compensator + sentinel
        reverse = compensator + target + sentinel
        html_rows.append(
            f'<div data-case="{record["name"]}"><span class="target">{target}</span>'
            f'<span class="forward">{forward}</span><span class="reverse">{reverse}</span></div>')
        y = 64 + index * 70
        svg_rows.append(
            f'<g data-svg-case="{record["name"]}"><text class="target" x="0" y="{y}">{target}</text>'
            f'<text class="forward" x="0" y="{y}">{forward}</text>'
            f'<text class="reverse" x="0" y="{y}">{reverse}</text></g>')
    return f'''<!doctype html><meta charset="utf-8"><title>HVAR resulting advance range probe</title>
<style>
@font-face{{font-family:RangeProbe;src:url("range-probe.woff2") format("woff2")}}
body{{margin:0;width:20000px}}
#html,svg{{font-family:RangeProbe;font-size:{FONT_SIZE}px;font-kerning:none;font-synthesis:none}}
#html>div{{height:70px;white-space:nowrap}}
#html span{{display:inline-block;margin-right:20px;white-space:pre}}
svg{{position:absolute;left:-30000px;top:0;width:20000px;height:{len(records) * 70 + 70}px;overflow:visible}}
</style><div id="html">{''.join(html_rows)}</div>
<svg id="svg" xmlns="http://www.w3.org/2000/svg">{''.join(svg_rows)}</svg>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ttf = OUT / "range-probe.ttf"
    records = build_font(ttf)
    (OUT / "index.html").write_text(build_html(records))
    font = TTFont(ttf, recalcTimestamp=False)
    serialized_rows = {
        glyph_name: list(font["HVAR"].table.VarStore.VarData[0].Item[glyph_id])
        for glyph_id, glyph_name in enumerate(font.getGlyphOrder())
    }
    reference = {
        "unitsPerEm": UNITS_PER_EM,
        "fontSizePx": FONT_SIZE,
        "scale": FONT_SIZE / UNITS_PER_EM,
        "axisTag": AXIS_TAG,
        "axisValues": [-1, 0, 1],
        "cases": records,
        "fontValidation": {
            "basesAreUint16": all(0 <= case[1] <= 65_535 and 0 <= case[4] <= 65_535 for case in CASES),
            "deltasAreInt16": all(-32_768 <= delta <= 32_767 for case in CASES for delta in case[2:4]),
            "serializedHvarRows": serialized_rows,
            "ttfBytes": ttf.stat().st_size,
            "woff2Bytes": ttf.with_suffix(".woff2").stat().st_size,
        },
    }
    (OUT / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print(f"built {OUT}")


if __name__ == "__main__":
    main()
