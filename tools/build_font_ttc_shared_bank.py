#!/usr/bin/env python3
"""Build a TTC metric bank whose faces share one HVAR/VarRegionList."""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path

import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "font-ttc-shared-bank"
INPUTS = 64
FACES = 64
BASE = 2_000
FONT_SIZE = 512
UNITS_PER_EM = 1_000


def axis_tag(index: int) -> str:
    return f"X{index:03d}"


def glyph():
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0)); pen.lineTo((1, 0)); pen.lineTo((1, 1)); pen.lineTo((0, 1)); pen.closePath()
    return pen.glyph()


def build_base(weights: np.ndarray, path: Path) -> TTFont:
    zeros = [f"zero.row{index:03d}" for index in range(FACES)]
    waters = [f"water.row{index:03d}" for index in range(FACES)]
    order = [".notdef", "zero", "water", *zeros, *waters]
    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x30: "zero", 0x6C34: "water"})
    shape = glyph()
    fb.setupGlyf({name: shape for name in order})
    fb.setupHorizontalMetrics({name: (BASE, 0) for name in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "BankRowBase", "styleName": "Regular",
                       "uniqueFontIdentifier": "BankRowBase-Regular",
                       "fullName": "BankRowBase Regular", "psName": "BankRowBase"})
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200,
                usWinAscent=800, usWinDescent=200)
    fb.setupPost(); fb.setupMaxp(); fb.setupHead(created=2_082_844_800, modified=2_082_844_800)
    fb.font.recalcTimestamp = False
    fb.save(path)
    font = TTFont(path, recalcTimestamp=False)

    tags = [axis_tag(index) for index in range(INPUTS)]
    fvar = newTable("fvar"); fvar.axes = []; fvar.instances = []
    stat_axes = []
    for index, tag in enumerate(tags):
        axis = Axis(); axis.axisTag = tag; axis.minValue = -1; axis.defaultValue = 0
        axis.maxValue = 1; axis.flags = 0; axis.axisNameID = font["name"].addName(tag)
        fvar.axes.append(axis)
        stat_axes.append({"tag": tag, "name": axis.axisNameID, "ordering": index})
    font["fvar"] = fvar; buildStatTable(font, stat_axes)
    supports = []
    for tag in tags:
        supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    regions = buildVarRegionList(supports, tags)
    rows = [[0] * len(supports) for _ in order]
    glyph_ids = {name: index for index, name in enumerate(order)}
    for face in range(FACES):
        for glyph_name, output in ((zeros[face], face * 2), (waters[face], face * 2 + 1)):
            rows[glyph_ids[glyph_name]] = [delta for value in weights[output].tolist()
                                            for delta in (-int(value), int(value))]
    hvar = newTable("HVAR"); hvar.table = otTables.HVAR(); hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(regions, [buildVarData(range(len(supports)), rows, optimize=True)])
    hvar.table.AdvWidthMap = None; hvar.table.LsbMap = None; hvar.table.RsbMap = None
    font["HVAR"] = hvar
    font.recalcTimestamp = False
    return font


def rename_and_remap(font: TTFont, face: int) -> None:
    zero = f"zero.row{face:03d}"; water = f"water.row{face:03d}"
    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap[0x30] = zero; table.cmap[0x6C34] = water
    family = f"BankRow{face:03d}"
    for name_id, value in ((1, family), (3, f"{family}-Regular"), (4, f"{family} Regular"), (6, family)):
        font["name"].setName(value, name_id, 3, 1, 0x409)
        font["name"].setName(value, name_id, 1, 0, 0)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0x545443)
    weights = rng.integers(-16, 17, size=(FACES * 2, INPUTS), dtype=np.int16)
    inputs = rng.integers(-4, 5, size=INPUTS).astype(np.float64) / 4
    base = build_base(weights, OUT / "base.ttf")
    fonts = []
    standalone = 0
    for face in range(FACES):
        font = copy.deepcopy(base); rename_and_remap(font, face); fonts.append(font)
        stream = io.BytesIO(); font.save(stream); standalone += len(stream.getvalue())
    collection = TTCollection(); collection.fonts = fonts
    collection.save(OUT / "bank.ttc", shareTables=True)

    settings = ",".join(f'"{axis_tag(index)}" {value:g}' for index, value in enumerate(inputs))
    faces_css = []; properties = []; rules = []
    child = '<div id="result">ready</div>'
    for face in range(FACES):
        a, b = face * 2, face * 2 + 1
        faces_css.append(f'@font-face{{font-family:F{face:03d};src:url("bank.ttc#BankRow{face:03d}") format("collection")}}')
        properties.extend((f'@property --o{a:03d}{{syntax:"<number>";inherits:true;initial-value:-99999}}',
                           f'@property --o{b:03d}{{syntax:"<number>";inherits:true;initial-value:-99999}}'))
        rules.append(f'.f{face:03d}{{font-family:F{face:03d};font-size:{FONT_SIZE}px;'
                     f'font-variation-settings:{settings};--o{a:03d}:calc(1ch / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE});'
                     f'--o{b:03d}:calc(1ic / 1px * {UNITS_PER_EM} / {FONT_SIZE} - {BASE})}}')
    for face in reversed(range(FACES)):
        child = f'<div class="f{face:03d}">{child}</div>'
    html = f'''<!doctype html><meta charset="utf-8"><title>Shared TTC metric bank</title><style>
{''.join(faces_css)}{''.join(properties)}{''.join(rules)}#result{{font:14px monospace}}
</style>{child}'''
    (OUT / "index.html").write_text(html)
    expected = weights.astype(np.float64) @ inputs
    (OUT / "reference.json").write_text(json.dumps({"inputs": inputs.tolist(), "weights": weights.tolist(),
        "expected": expected.tolist(), "faces": FACES, "standalone_bytes": standalone,
        "collection_bytes": (OUT / "bank.ttc").stat().st_size}, indent=2) + "\n")
    print({"ttc_bytes": (OUT / "bank.ttc").stat().st_size, "standalone_bytes": standalone,
           "html_bytes": (OUT / "index.html").stat().st_size})


if __name__ == "__main__": main()
