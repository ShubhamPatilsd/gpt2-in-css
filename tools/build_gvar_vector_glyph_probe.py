#!/usr/bin/env python3
"""Render many live matvec outputs as rectangles inside one variable glyph."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.ttLib.woff2 import WOFF2FlavorData

from build_gpt2_block_css import QUANT_BITS, model_data, packed_axis_tag
from build_pretrained_gpt2 import css_number
from build_signed_hvar_chain import quantize_float_rows, safe_base_advance


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "gvar-vector-glyph"
OUTPUTS = int(os.environ.get("GVAR_VECTOR_OUTPUTS", "256"))
INPUTS = 256
UPM = 1000
BAR_WIDTH = 256
CODEPOINT = 0xE000


def vector_glyph(output_count: int, widths: int | np.ndarray):
    pen = TTGlyphPen(None)
    for output in range(output_count):
        # Font y grows upward. Reverse rows so output 0 renders at screen y=0.
        bottom = output_count - output - 1
        top = bottom + 1
        width = int(widths if np.isscalar(widths) else widths[output])
        pen.moveTo((0, bottom))
        pen.lineTo((width, bottom))
        pen.lineTo((width, top))
        pen.lineTo((0, top))
        pen.closePath()
    return pen.glyph()


def rectangle(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((width, 0))
    pen.lineTo((width, height))
    pen.lineTo((0, height))
    pen.closePath()
    return pen.glyph()


def build_font(
    codes: np.ndarray,
    path: Path,
    *,
    base: int | None = None,
    base_offsets: np.ndarray | None = None,
    axis_shard: int = 0,
) -> int:
    base = safe_base_advance(codes) if base is None else base
    widths = (
        np.full(codes.shape[0], base, dtype=np.int64)
        if base_offsets is None
        else base + np.asarray(base_offsets, dtype=np.int64)
    )
    if np.min(widths) < -32768 or np.max(widths) > 32767:
        raise ValueError("base glyph coordinates exceed TrueType int16 range")
    # A tiny second varying glyph lets gvar move the 512 axis tuples into its
    # shared-tuple table. Without it, the main glyph's tuple header exceeds the
    # format's 16-bit data offset before coordinate compression even begins.
    glyph_order = [".notdef", "vector", "tupleShare"]
    builder = FontBuilder(UPM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap({CODEPOINT: "vector"})
    builder.setupGlyf(
        {
            ".notdef": rectangle(1, 1),
            "vector": vector_glyph(codes.shape[0], widths),
            "tupleShare": rectangle(1, 1),
        }
    )
    builder.setupHorizontalMetrics(
        {".notdef": (1, 0), "vector": (2 * base, 0), "tupleShare": (1, 0)}
    )
    builder.setupHorizontalHeader(ascent=max(UPM, codes.shape[0]), descent=0)
    family = f"GVAR Vector {codes.shape[0]}"
    builder.setupNameTable(
        {
            "familyName": family,
            "styleName": "Regular",
            "uniqueFontIdentifier": family.replace(" ", ""),
            "fullName": f"{family} Regular",
            "psName": f"{family.replace(' ', '')}-Regular",
        }
    )
    builder.setupOS2(
        version=4,
        sTypoAscender=max(UPM, codes.shape[0]),
        sTypoDescender=0,
        usWinAscent=max(UPM, codes.shape[0]),
        usWinDescent=0,
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.setupHead(created=2_082_844_800, modified=2_082_844_800)
    builder.font.recalcTimestamp = False
    builder.save(path)

    font = TTFont(path, recalcTimestamp=False)
    tags = [packed_axis_tag(axis_shard, index) for index in range(INPUTS)]
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

    variations = []
    tuple_share_variations = []
    code_columns = codes.T.astype(np.int16)
    for axis, tag in enumerate(tags):
        column = code_columns[axis].tolist()
        for negative in (True, False):
            coordinates = []
            sign = -1 if negative else 1
            for value in column:
                delta = sign * value
                coordinates.extend(((0, 0), (delta, 0), (delta, 0), (0, 0)))
            coordinates.extend(((0, 0),) * 4)
            support = {tag: (-1, -1, 0) if negative else (0, 1, 1)}
            variations.append(TupleVariation(support, coordinates))
            tuple_share_variations.append(
                TupleVariation(
                    support,
                    [(0, 0), (sign, 0), (sign, 0), (0, 0)]
                    + [(0, 0)] * 4,
                )
            )
    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {
        ".notdef": [],
        "vector": variations,
        "tupleShare": tuple_share_variations,
    }
    font["gvar"] = gvar
    font.recalcTimestamp = False
    font.save(path)
    compressed = TTFont(path, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.flavorData = WOFF2FlavorData(transformedTables=set())
    compressed.save(path.with_suffix(".woff2"))
    return base


def settings(vector: np.ndarray) -> str:
    return ",".join(
        f'"{packed_axis_tag(0, index)}" {css_number(float(value))}'
        for index, value in enumerate(vector)
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    q_fc = quantize_float_rows(model_data()["fc_weight"], bits=QUANT_BITS)
    codes = q_fc.codes[:OUTPUTS, :INPUTS]
    rng = np.random.default_rng(0x47564152)
    initial = rng.uniform(-0.72, 0.72, size=INPUTS)
    alternate = rng.uniform(-0.72, 0.72, size=INPUTS)
    expected = [codes.astype(np.float64) @ value for value in (initial, alternate)]
    path = OUT / f"vector-{OUTPUTS}.ttf"
    base = build_font(codes, path)
    woff2 = path.with_suffix(".woff2")
    tag = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
    scale_x = BAR_WIDTH / (2 * base)
    kernel = " ".join(["1"] * BAR_WIDTH)
    html = f'''<!doctype html>
<meta charset="utf-8">
<style>
@font-face{{font-family:VectorGlyph;src:url("vector-{OUTPUTS}.woff2?v={tag}") format("woff2")}}
html,body{{margin:0;background:transparent}}
svg{{display:block;overflow:visible}}
#bank{{font-family:VectorGlyph;font-size:{UPM}px;font-variation-settings:{settings(initial)};fill:red}}
</style>
<svg id="surface" width="{BAR_WIDTH}" height="{OUTPUTS}" viewBox="0 0 {BAR_WIDTH} {OUTPUTS}"
 xmlns="http://www.w3.org/2000/svg">
 <defs><filter id="reduce" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
  x="0" y="0" width="{BAR_WIDTH}" height="{OUTPUTS}" color-interpolation-filters="sRGB">
  <feConvolveMatrix in="SourceGraphic" order="{BAR_WIDTH} 1" targetX="{BAR_WIDTH - 1}"
   kernelMatrix="{kernel}" divisor="{BAR_WIDTH}" edgeMode="none" preserveAlpha="false"
   x="{BAR_WIDTH - 1}" y="0" width="1" height="{OUTPUTS}" result="widths"/>
  <feColorMatrix in="widths" values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1"/>
 </filter></defs>
 <g filter="url(#reduce)"><text id="bank" x="0" y="{OUTPUTS}"
  transform="scale({css_number(scale_x)} 1)">&#x{CODEPOINT:X};</text></g>
</svg>
'''
    stem = f"n{OUTPUTS}"
    (OUT / f"{stem}.html").write_text(html)
    reference = {
        "outputs": OUTPUTS,
        "inputs": INPUTS,
        "base": base,
        "barWidth": BAR_WIDTH,
        "initialSettings": settings(initial),
        "alternateSettings": settings(alternate),
        "initialExpected": expected[0].tolist(),
        "alternateExpected": expected[1].tolist(),
        "fontBytes": woff2.stat().st_size,
        "ttfBytes": path.stat().st_size,
        "htmlBytes": len(html.encode()),
        "runtimeJavascript": False,
    }
    (OUT / f"{stem}-reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({key: reference[key] for key in ("outputs", "base", "fontBytes", "htmlBytes")})


if __name__ == "__main__":
    main()
