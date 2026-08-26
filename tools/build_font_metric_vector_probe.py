#!/usr/bin/env python3
"""Build a no-JS probe that returns four matvec rows as CSS font units."""

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
from fontTools.ttLib.woff2 import WOFF2FlavorData
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "font-metric-vector"
INPUT_WIDTH = 64
UNITS_PER_EM = 1_000
FONT_SIZE = 512
BASE_METRIC = 2_000


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


def deterministic_data() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0x4D564152)
    weights = rng.integers(-20, 21, size=(4, INPUT_WIDTH), dtype=np.int16)
    inputs = rng.integers(-4, 5, size=INPUT_WIDTH).astype(np.float64) / 4
    return weights, inputs


def build_font(
    weights: np.ndarray,
    destination: Path,
    *,
    family_name: str = "CSS Metric Vector",
    base_metric: int = BASE_METRIC,
    signed_axes: bool = True,
) -> None:
    if weights.shape[0] != 4:
        raise ValueError("font-metric transport exposes exactly four rows per font")
    glyph_order = [".notdef", "zero", "water", "x", "H"]
    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap({0x30: "zero", 0x6C34: "water", 0x78: "x", 0x48: "H"})
    builder.setupGlyf(
        {
            ".notdef": rectangle(1, 1),
            "zero": rectangle(1, 1),
            "water": rectangle(1, 1),
            # Chromium derives `ex` from the x glyph's outline instead of the
            # OS/2 sxHeight/MVAR metric, so give that outline the same base.
            "x": rectangle(1, base_metric),
            "H": rectangle(1, base_metric),
        }
    )
    builder.setupHorizontalMetrics(
        {
            ".notdef": (0, 0),
            "zero": (base_metric, 0),
            "water": (base_metric, 0),
            "x": (500, 0),
            "H": (500, 0),
        }
    )
    builder.setupHorizontalHeader(ascent=base_metric, descent=0)
    builder.setupNameTable(
        {
            "familyName": family_name,
            "styleName": "Regular",
            "uniqueFontIdentifier": f"{family_name}-regular",
            "fullName": f"{family_name} Regular",
            "psName": f"{family_name.replace(' ', '')}-Regular",
        }
    )
    builder.setupOS2(
        version=4,
        sTypoAscender=base_metric,
        sTypoDescender=0,
        usWinAscent=base_metric,
        usWinDescent=0,
        sxHeight=base_metric,
        sCapHeight=base_metric,
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
    tags = [axis_tag(index) for index in range(weights.shape[1])]
    for index, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = -1 if signed_axes else 0
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
        if signed_axes:
            supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
        else:
            supports.append({tag: (0, 1, 1)})
    region_list = buildVarRegionList(supports, tags)

    def encoded_row(row: np.ndarray) -> list[int]:
        values = row.astype(np.int16).tolist()
        if signed_axes:
            return [delta for value in values for delta in (-value, value)]
        return values

    hvar_rows = [[0] * len(supports) for _ in glyph_order]
    hvar_rows[1] = encoded_row(weights[2])
    hvar_rows[2] = encoded_row(weights[3])
    hvar_data = buildVarData(range(len(supports)), hvar_rows, optimize=True)
    hvar = newTable("HVAR")
    hvar.table = otTables.HVAR()
    hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(region_list, [hvar_data])
    hvar.table.AdvWidthMap = None
    hvar.table.LsbMap = None
    hvar.table.RsbMap = None
    font["HVAR"] = hvar

    mvar_data = buildVarData(
        range(len(supports)),
        [encoded_row(weights[0]), encoded_row(weights[1])],
        optimize=True,
    )
    mvar = newTable("MVAR")
    mvar.table = otTables.MVAR()
    mvar.table.Version = 0x00010000
    mvar.table.Reserved = 0
    mvar.table.VarStore = buildVarStore(region_list, [mvar_data])
    mvar.table.ValueRecordSize = 8
    mvar.table.ValueRecordCount = 2
    records = []
    for tag, index in (("xhgt", 0), ("cpht", 1)):
        record = otTables.MetricsValueRecord()
        record.ValueTag = tag
        record.VarIdx = index
        records.append(record)
    mvar.table.ValueRecord = sorted(records, key=lambda record: record.ValueTag)
    font["MVAR"] = mvar

    def outline_variation(tag: str, peak: int, delta: int) -> TupleVariation:
        # Four contour points followed by the four TrueType phantom points.
        coordinates = [
            (0, 0),
            (0, 0),
            (0, delta),
            (0, delta),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ]
        support = {tag: (-1, -1, 0) if peak < 0 else (0, 1, 1)}
        return TupleVariation(support, coordinates)

    def outline_row(row: np.ndarray) -> list[TupleVariation]:
        variations = []
        for tag, weight in zip(tags, row.astype(np.int16).tolist()):
            if signed_axes:
                variations.append(outline_variation(tag, -1, -weight))
            variations.append(outline_variation(tag, 1, weight))
        return variations

    # Supplying both outlines also makes their axis tuples shareable in gvar,
    # which keeps a 256-axis font below the table's 16-bit tuple-data offset.
    x_variations = outline_row(weights[0])
    h_variations = outline_row(weights[1])

    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {glyph: [] for glyph in glyph_order}
    gvar.variations["x"] = x_variations
    gvar.variations["H"] = h_variations
    font["gvar"] = gvar

    font.recalcTimestamp = False
    font.save(destination)
    compressed = TTFont(destination, recalcTimestamp=False)
    compressed.flavor = "woff2"
    # The glyf/loca transform can emit WOFF2 streams Chromium rejects for the
    # large multi-axis gvar table. Brotli-compress the raw tables instead.
    compressed.flavorData = WOFF2FlavorData(transformedTables=set())
    compressed.save(destination.with_suffix(".woff2"))


def build_html(inputs: np.ndarray, expected: np.ndarray) -> str:
    settings = ",".join(
        f'"{axis_tag(index)}" {value:g}' for index, value in enumerate(inputs)
    )
    expected_text = ", ".join(f"{value:g}" for value in expected)
    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Four-output font-metric matvec</title>
<style>
@font-face{{font-family:MetricVector;src:url("metric-vector.woff2?v=2") format("woff2")}}
@property --o0{{syntax:"<number>";inherits:true;initial-value:-99999}}
@property --o1{{syntax:"<number>";inherits:true;initial-value:-99999}}
@property --o2{{syntax:"<number>";inherits:true;initial-value:-99999}}
@property --o3{{syntax:"<number>";inherits:true;initial-value:-99999}}
html{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
body{{margin:2rem;max-width:52rem}}
.producer{{
  font-family:MetricVector;
  font-size:{FONT_SIZE}px;
  font-variation-settings:{settings};
  --o0:calc(1ex / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE_METRIC});
  --o1:calc(1cap / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE_METRIC});
  --o2:calc(1ch / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE_METRIC});
  --o3:calc(1ic / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE_METRIC});
}}
.result{{font:14px ui-monospace,SFMono-Regular,Menlo,monospace}}
.bar{{height:1rem;background:#222;margin:.35rem 0;width:calc((var(--value) + 1000) * .25px)}}
</style>
<h1>Four matrix outputs from one variable-font instance</h1>
<p>Expected: {expected_text}</p>
<div class="producer">
  <div class="result" id="result">
    <div class="bar" style="--value:var(--o0)"></div>
    <div class="bar" style="--value:var(--o1)"></div>
    <div class="bar" style="--value:var(--o2)"></div>
    <div class="bar" style="--value:var(--o3)"></div>
  </div>
</div>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weights, inputs = deterministic_data()
    expected = weights.astype(np.float64) @ inputs
    build_font(weights, OUT / "metric-vector.ttf")
    (OUT / "index.html").write_text(build_html(inputs, expected))
    (OUT / "reference.json").write_text(
        json.dumps(
            {
                "input_width": INPUT_WIDTH,
                "base_metric": BASE_METRIC,
                "font_size": FONT_SIZE,
                "inputs": inputs.tolist(),
                "weights": weights.tolist(),
                "expected": expected.tolist(),
                "channels": ["ex", "cap", "ch", "ic"],
            },
            indent=2,
        )
        + "\n"
    )
    print(
        {
            "expected": expected.tolist(),
            "ttf_bytes": (OUT / "metric-vector.ttf").stat().st_size,
            "woff2_bytes": (OUT / "metric-vector.woff2").stat().st_size,
        }
    )


if __name__ == "__main__":
    main()
