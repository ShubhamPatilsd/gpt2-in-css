#!/usr/bin/env python3
"""Build 64-term projected QK fonts using bilinear HVAR regions only."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from fontTools.otlLib.builder import buildStatTable
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

from build_attention_context_scaling import PRECISION_REPORT
from build_gpt2_block_css import UNITS_PER_EM, WIDTH


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "bilinear-projected-kv-qk"
SUM_OUT = ROOT / "experiments" / "bilinear-sum-projected-kv-qk"
HEADS = 12
HEAD_WIDTH = WIDTH // HEADS
TARGET_DELTA = 12_000
CODEPOINT_BASE = 0xF5800


def rectangle():
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((1, 0))
    pen.lineTo((1, 1))
    pen.lineTo((0, 1))
    pen.closePath()
    return pen.glyph()


def axis_tag(prefix: str, index: int) -> str:
    return f"{prefix}{index:03d}"


def build_head_font(
    *,
    head: int,
    query_ranges: np.ndarray,
    key_ranges: np.ndarray,
    destination: Path,
    summed_glyph: bool,
) -> tuple[int, int, list[int]]:
    products = query_ranges * key_ranges
    dot_scale = max(
        1,
        math.floor(
            (30_000 / float(np.sum(products)))
            if summed_glyph
            else (TARGET_DELTA / float(np.max(products)))
        ),
    )
    coefficients = np.rint(products * dot_scale).astype(np.int64)
    base = int(np.sum(coefficients) if summed_glyph else np.max(coefficients)) + 32
    glyph_names = (
        [".notdef", "dot"]
        if summed_glyph
        else [".notdef", *(f"g{index:03d}" for index in range(HEAD_WIDTH))]
    )
    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyph_names)
    builder.setupCharacterMap(
        {CODEPOINT_BASE: "dot"}
        if summed_glyph
        else {
            CODEPOINT_BASE + index: glyph_names[index + 1]
            for index in range(HEAD_WIDTH)
        }
    )
    builder.setupGlyf({name: rectangle() for name in glyph_names})
    builder.setupHorizontalMetrics({
        name: (0 if name == ".notdef" else base, 0)
        for name in glyph_names
    })
    builder.setupHorizontalHeader(ascent=1_000, descent=0)
    variant = "Sum" if summed_glyph else "Coordinate"
    family = f"Bilinear {variant} Projected KV QK H{head}"
    builder.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"Bilinear{variant}ProjectedKVQKH{head}-Regular",
        "fullName": f"{family} Regular",
        "psName": f"Bilinear{variant}ProjectedKVQKH{head}-Regular",
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
    tags = [
        tag
        for index in range(HEAD_WIDTH)
        for tag in (axis_tag("Q", index), axis_tag("K", index))
    ]
    fvar = newTable("fvar")
    fvar.axes = []
    fvar.instances = []
    stat_axes = []
    for order, tag in enumerate(tags):
        axis = Axis()
        axis.axisTag = tag
        axis.minValue = -1
        axis.defaultValue = 0
        axis.maxValue = 1
        axis.flags = 0
        axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": order})
    font["fvar"] = fvar
    buildStatTable(font, stat_axes)

    negative = (-1, -1, 0)
    positive = (0, 1, 1)
    supports = []
    for index in range(HEAD_WIDTH):
        q_tag = axis_tag("Q", index)
        k_tag = axis_tag("K", index)
        supports.extend([
            {q_tag: negative, k_tag: negative},
            {q_tag: negative, k_tag: positive},
            {q_tag: positive, k_tag: negative},
            {q_tag: positive, k_tag: positive},
        ])
    regions = buildVarRegionList(supports, tags)
    rows = [[0] * len(supports) for _ in glyph_names]
    for index, coefficient in enumerate(coefficients):
        start = index * 4
        glyph_row = rows[1] if summed_glyph else rows[index + 1]
        glyph_row[start:start + 4] = [
            int(coefficient), -int(coefficient), -int(coefficient), int(coefficient)
        ]
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
    font.recalcTimestamp = False
    font.flavor = "woff2"
    font.save(destination.with_suffix(".woff2"))
    return dot_scale, base, coefficients.tolist()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layouts", choices=("coordinate", "sum"), nargs="+", default=["coordinate", "sum"]
    )
    args = parser.parse_args()
    precision = json.loads(PRECISION_REPORT.read_text())
    ranges = np.asarray(
        precision["margins"]["1.2"]["perChannelRanges"], dtype=np.float64
    )
    reports = []
    for layout in args.layouts:
        summed_glyph = layout == "sum"
        out = SUM_OUT if summed_glyph else OUT
        out.mkdir(parents=True, exist_ok=True)
        heads = []
        total_font_bytes = 0
        font_prefix = "bilinear-sum-projected-kv-qk" if summed_glyph else "bilinear-projected-kv-qk"
        for head in range(HEADS):
            start = head * HEAD_WIDTH
            stop = start + HEAD_WIDTH
            query_ranges = ranges[start:stop]
            key_ranges = ranges[WIDTH + start:WIDTH + stop]
            ttf_path = out / f"{font_prefix}-h{head}.ttf"
            dot_scale, base, coefficients = build_head_font(
                head=head,
                query_ranges=query_ranges,
                key_ranges=key_ranges,
                destination=ttf_path,
                summed_glyph=summed_glyph,
            )
            font_bytes = ttf_path.with_suffix(".woff2").stat().st_size
            total_font_bytes += font_bytes
            heads.append({
                "head": head,
                "queryRanges": query_ranges.tolist(),
                "keyRanges": key_ranges.tolist(),
                "dotScale": dot_scale,
                "base": base,
                "coefficients": coefficients,
                "glyphCount": 1 if summed_glyph else HEAD_WIDTH,
                "fontBytes": font_bytes,
            })
        reference = {
            "heads": HEADS,
            "headWidth": HEAD_WIDTH,
            "axesPerFont": HEAD_WIDTH * 2,
            "glyphLayout": layout,
            "codepointBase": CODEPOINT_BASE,
            "totalFontBytes": total_font_bytes,
            "runtimeJavaScript": False,
            "headsReference": heads,
        }
        (out / "reference.json").write_text(json.dumps(reference, indent=2) + "\n")
        reports.append({
            "layout": layout,
            "heads": HEADS,
            "axesPerFont": HEAD_WIDTH * 2,
            "totalFontBytes": total_font_bytes,
        })
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
