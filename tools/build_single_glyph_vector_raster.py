#!/usr/bin/env python3
"""Build one COLRv1 glyph that paints a live vector into an SVG filter graph."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "single-glyph-vector-raster"
INPUTS = int(os.environ.get("SINGLE_GLYPH_INPUTS", "64"))
OUTPUTS = int(os.environ.get("SINGLE_GLYPH_OUTPUTS", "64"))
UPM = 1000
BAR_WIDTH = 256
BASE_SCALE = 0.5
PAINT_SCALE = 16_384
CODEPOINT = 0xE000


def axis_tag(index: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return f"{alphabet[(index // len(alphabet)) % len(alphabet)]}{index % 1000:03d}"


def rectangle(width: int, height: int):
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((width, 0))
    pen.lineTo((width, height))
    pen.lineTo((0, height))
    pen.closePath()
    return pen.glyph()


def build_font(weights: np.ndarray, path: Path) -> None:
    glyph_order = [".notdef", "vector", "bar"]
    builder = FontBuilder(UPM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap({CODEPOINT: "vector"})
    builder.setupGlyf(
        {
            ".notdef": rectangle(1, 1),
            # Keep explicit base bounds for predictable SVG filter geometry.
            "vector": rectangle(1, 1),
            "bar": rectangle(BAR_WIDTH, 1),
        }
    )
    builder.setupHorizontalMetrics({name: (BAR_WIDTH, 0) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=max(UPM, OUTPUTS), descent=0)
    family = f"COLR Vector {INPUTS}x{OUTPUTS}"
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
        sTypoAscender=max(UPM, OUTPUTS),
        sTypoDescender=0,
        usWinAscent=max(UPM, OUTPUTS),
        usWinDescent=0,
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.setupHead(created=2_082_844_800, modified=2_082_844_800)
    builder.font.recalcTimestamp = False
    builder.save(path)

    font = TTFont(path, recalcTimestamp=False)
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

    supports = []
    for tag in tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    regions = buildVarRegionList(supports, tags)
    rows = []
    for row in weights:
        signed = []
        for value in row.tolist():
            signed.extend((-int(value), int(value)))
        rows.append(signed)
        # PaintVarScale consumes the next item for scaleY. Keep it fixed at 1.
        rows.append([0] * len(supports))
    data = buildVarData(range(len(supports)), rows, optimize=False)
    var_store = buildVarStore(regions, [data])

    solid_bar = {
        "Format": otTables.PaintFormat.PaintGlyph,
        "Glyph": "bar",
        "Paint": {
            "Format": otTables.PaintFormat.PaintSolid,
            "PaletteIndex": 0,
            "Alpha": 1.0,
        },
    }
    layers = []
    for output in range(OUTPUTS):
        scaled = {
            "Format": otTables.PaintFormat.PaintVarScale,
            "Paint": solid_bar,
            "scaleX": BASE_SCALE,
            "scaleY": 1.0,
            "VarIndexBase": 2 * output,
        }
        layers.append(
            {
                "Format": otTables.PaintFormat.PaintTranslate,
                "Paint": scaled,
                "dx": 0,
                "dy": output,
            }
        )
    font["COLR"] = buildCOLR(
        {
            "vector": {
                "Format": otTables.PaintFormat.PaintColrLayers,
                "Layers": layers,
            }
        },
        version=1,
        glyphMap=font.getReverseGlyphMap(),
        varStore=var_store,
        clipBoxes={"vector": (0, 0, BAR_WIDTH, OUTPUTS)},
        allowLayerReuse=False,
    )
    font["CPAL"] = buildCPAL([[(1.0, 0.0, 0.0, 1.0)]])
    font.recalcTimestamp = False
    font.save(path)
    compressed = TTFont(path, recalcTimestamp=False)
    compressed.flavor = "woff2"
    compressed.save(path.with_suffix(".woff2"))


def settings(vector: np.ndarray) -> str:
    return ",".join(
        f'"{axis_tag(index)}" {float(value):.9g}'
        for index, value in enumerate(vector)
    )


def main() -> None:
    if INPUTS > 256:
        raise ValueError("Chrome/OpenType variable fonts are limited to 256 axes")
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0xC01A)
    # Keep every painted scale in [0.15, 0.85] for all tested vectors.
    float_weights = rng.uniform(-0.002, 0.002, size=(OUTPUTS, INPUTS))
    weight_codes = np.rint(float_weights * PAINT_SCALE).astype(np.int16)
    initial = rng.uniform(-0.7, 0.7, size=INPUTS)
    alternate = rng.uniform(-0.7, 0.7, size=INPUTS)
    represented_weights = weight_codes.astype(np.float64) / PAINT_SCALE
    expected = [BASE_SCALE + represented_weights @ value for value in (initial, alternate)]
    reduce_count = min(OUTPUTS, 256)

    stem = f"i{INPUTS}-o{OUTPUTS}"
    ttf = OUT / f"{stem}.ttf"
    build_font(weight_codes, ttf)
    woff2 = ttf.with_suffix(".woff2")
    digest = hashlib.sha256(woff2.read_bytes()).hexdigest()[:12]
    horizontal_kernel = " ".join(["1"] * BAR_WIDTH)
    vertical_kernel = " ".join(["1"] * reduce_count)
    html = f'''<!doctype html>
<meta charset="utf-8">
<style>
@font-face{{font-family:COLRVector;src:url("{woff2.name}?v={digest}") format("woff2")}}
html,body{{margin:0;background:transparent}}
svg{{display:block;overflow:visible}}
#vector{{font-family:COLRVector;font-size:{UPM}px;line-height:1;
font-variation-settings:{settings(initial)}}}
</style>
<svg id="surface" width="{BAR_WIDTH}" height="{OUTPUTS}" viewBox="0 0 {BAR_WIDTH} {OUTPUTS}"
 xmlns="http://www.w3.org/2000/svg">
 <defs><filter id="consume" filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse"
  x="0" y="0" width="{BAR_WIDTH}" height="{OUTPUTS}" color-interpolation-filters="sRGB">
  <feConvolveMatrix in="SourceGraphic" order="{BAR_WIDTH} 1" targetX="{BAR_WIDTH - 1}"
   kernelMatrix="{horizontal_kernel}" divisor="{BAR_WIDTH}" edgeMode="none"
   preserveAlpha="false" result="vector-alpha"/>
  <feColorMatrix in="vector-alpha" values="0 0 0 1 0  0 0 0 1 0  0 0 0 1 0  0 0 0 0 1"
   result="vector"/>
  <feComponentTransfer in="vector" result="mapped">
   <feFuncR type="table" tableValues="0 .25 1"/>
   <feFuncG type="table" tableValues="0 .25 1"/>
   <feFuncB type="table" tableValues="0 .25 1"/>
  </feComponentTransfer>
  <feOffset in="mapped" dx="-{BAR_WIDTH - 1}" result="vector-at-zero"/>
  <feConvolveMatrix in="vector-at-zero" order="1 {reduce_count}" targetY="{reduce_count - 1}"
   kernelMatrix="{vertical_kernel}" divisor="{reduce_count}" edgeMode="none"
   preserveAlpha="false" result="mean"/>
  <feOffset in="mean" dx="1" dy="-{reduce_count - 1}" result="mean-at-one"/>
  <feMerge><feMergeNode in="vector-at-zero"/><feMergeNode in="mean-at-one"/></feMerge>
 </filter></defs>
 <g filter="url(#consume)"><text id="vector" x="0" y="{OUTPUTS}">&#x{CODEPOINT:X};</text></g>
</svg>
'''
    page = OUT / f"{stem}.html"
    page.write_text(html)
    reference = {
        "inputs": INPUTS,
        "outputs": OUTPUTS,
        "barWidth": BAR_WIDTH,
        "baseScale": BASE_SCALE,
        "initialSettings": settings(initial),
        "alternateSettings": settings(alternate),
        "initialExpected": expected[0].tolist(),
        "alternateExpected": expected[1].tolist(),
        "fontBytes": woff2.stat().st_size,
        "ttfBytes": ttf.stat().st_size,
        "htmlBytes": len(html.encode()),
        "runtimeJavascript": False,
        "paintLayers": OUTPUTS,
        "reduceCount": reduce_count,
    }
    (OUT / f"{stem}-reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    print({key: reference[key] for key in ("inputs", "outputs", "fontBytes", "htmlBytes")})


if __name__ == "__main__":
    main()
