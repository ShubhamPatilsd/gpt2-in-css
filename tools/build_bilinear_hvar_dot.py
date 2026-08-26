#!/usr/bin/env python3
"""Build a no-JS proof that HVAR regions can multiply two live CSS vectors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from fontTools.otlLib.builder import buildStatTable
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "bilinear-hvar-dot"
UNITS_PER_EM = 1_000
FONT_SIZE = 10
BASE_ADVANCE = 5_000
PRODUCT_DELTA = 4_000


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


def build_font(dimensions: int, destination: Path) -> None:
    glyph_names = [".notdef", *(f"g{index:03d}" for index in range(dimensions))]
    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyph_names)
    builder.setupCharacterMap({0xF5000 + index: name for index, name in enumerate(glyph_names[1:])})
    builder.setupGlyf({name: rectangle() for name in glyph_names})
    builder.setupHorizontalMetrics({
        name: (0 if name == ".notdef" else BASE_ADVANCE, 0)
        for name in glyph_names
    })
    builder.setupHorizontalHeader(ascent=1_000, descent=0)
    family = f"Bilinear HVAR Dot {dimensions}"
    builder.setupNameTable({
        "familyName": family,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"BilinearHVARDot{dimensions}-Regular",
        "fullName": f"{family} Regular",
        "psName": f"BilinearHVARDot{dimensions}-Regular",
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
        for index in range(dimensions)
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
    signs = []
    for index in range(dimensions):
        q_tag = axis_tag("Q", index)
        k_tag = axis_tag("K", index)
        supports.extend([
            {q_tag: negative, k_tag: negative},
            {q_tag: negative, k_tag: positive},
            {q_tag: positive, k_tag: negative},
            {q_tag: positive, k_tag: positive},
        ])
        signs.extend([1, -1, -1, 1])
    regions = buildVarRegionList(supports, tags)
    rows = [[0] * len(supports) for _ in glyph_names]
    for index in range(dimensions):
        start = index * 4
        rows[index + 1][start:start + 4] = [sign * PRODUCT_DELTA for sign in signs[start:start + 4]]
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


def css_number(value: float) -> str:
    return f"{value:.8g}"


def build_fixture(dimensions: int, cases: int) -> dict[str, object]:
    rng = np.random.default_rng(20260912 + dimensions)
    vectors = []
    for case in range(cases):
        if case == 0:
            q = np.linspace(-1, 1, dimensions)
            k = np.linspace(1, -1, dimensions)
        elif case == 1:
            q = np.ones(dimensions)
            k = np.where(np.arange(dimensions) % 2, -1.0, 1.0)
        else:
            q = rng.uniform(-1, 1, dimensions)
            k = rng.uniform(-1, 1, dimensions)
        vectors.append({"q": q.tolist(), "k": k.tolist(), "expected": float(q @ k)})

    family = f"Bilinear HVAR Dot {dimensions}"
    settings = ",".join(
        setting
        for index in range(dimensions)
        for setting in (
            f'"{axis_tag("Q", index)}" var(--q-{index})',
            f'"{axis_tag("K", index)}" var(--k-{index})',
        )
    )
    spans = []
    text = "".join(f"&#x{0xF5000 + index:X};" for index in range(dimensions))
    for case, vectors_case in enumerate(vectors):
        values = ";".join(
            item
            for index, (q_value, k_value) in enumerate(zip(vectors_case["q"], vectors_case["k"]))
            for item in (
                f"--q-{index}:{css_number(q_value)}",
                f"--k-{index}:{css_number(k_value)}",
            )
        )
        spans.append(f'<span class="dot" id="case-{case}" style="{values}">{text}</span>')
    html = (
        "<!doctype html><meta charset=\"utf-8\"><title>Bilinear HVAR dot</title>"
        f"<style>@font-face{{font-family:'{family}';src:url('dot-{dimensions}.woff2')}}"
        "body{margin:0}.dot{position:absolute;left:0;top:0;display:inline-block;"
        "white-space:nowrap;visibility:hidden}"
        f".dot{{font:{FONT_SIZE}px '{family}';font-variation-settings:{settings}}}</style>"
        + "".join(spans)
    )
    (OUT / f"dot-{dimensions}.html").write_text(html)
    reference = {
        "dimensions": dimensions,
        "axes": dimensions * 2,
        "fontSize": FONT_SIZE,
        "baseWidthPixels": dimensions * BASE_ADVANCE * FONT_SIZE / UNITS_PER_EM,
        "dotScalePixels": PRODUCT_DELTA * FONT_SIZE / UNITS_PER_EM,
        "fontBytes": (OUT / f"dot-{dimensions}.woff2").stat().st_size,
        "runtimeJavaScript": False,
        "cases": vectors,
    }
    (OUT / f"dot-{dimensions}-reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    return reference


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dimensions", type=int, nargs="+", default=[8, 32, 64])
    parser.add_argument("--cases", type=int, default=6)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    reports = []
    for dimensions in args.dimensions:
        if not 1 <= dimensions <= 64:
            parser.error("dimensions must be in [1, 64]")
        build_font(dimensions, OUT / f"dot-{dimensions}.ttf")
        reports.append(build_fixture(dimensions, args.cases))
    print(json.dumps([
        {key: report[key] for key in ("dimensions", "axes", "fontBytes")}
        for report in reports
    ], indent=2))


if __name__ == "__main__":
    main()
