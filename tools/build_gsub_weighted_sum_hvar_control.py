#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Existing variable-font mechanism as a control for the new GSUB arithmetic.

The tested continuation is affine: 2*sum(w*x)+1 can be folded into fixed weights.
This control deliberately takes advantage of that. It is not a connected GSUB
implementation and makes no claim to contain an internal second computation.
"""
import hashlib
import json
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.otlLib.builder import buildStatTable
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-weighted-sum-probe/hvar-control"
BASE = 8192


def build(width):
    weights = [3, -2, 5, 1] * (width // 4)
    family = f"WeightedHvar{width}"
    names = [".notdef", "result"] + [f"nonce{i}" for i in range(65)]
    fb = FontBuilder(1024, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({0xE000: "result", **{0xE100 + i: f"nonce{i}" for i in range(65)}})
    empty = TTGlyphPen(None).glyph()
    outlines = {name: empty for name in names}
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0)); pen.lineTo((1, 0)); pen.lineTo((0, 1)); pen.closePath()
    outlines[".notdef"] = pen.glyph()
    fb.setupGlyf(outlines)
    fb.setupHorizontalMetrics({name: ((BASE + 1 if name == "result" else 0), 0) for name in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": family + "-v1",
                       "fullName": family, "psName": family})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost(); fb.setupMaxp()
    tags = [f"X{i:03d}" for i in range(width)]
    fvar = newTable("fvar"); fvar.axes = []; fvar.instances = []
    for tag in tags:
        axis = Axis(); axis.axisTag = tag
        axis.minValue = -8; axis.defaultValue = 0; axis.maxValue = 8
        axis.flags = 0; axis.axisNameID = fb.font["name"].addName(tag)
        fvar.axes.append(axis)
    fb.font["fvar"] = fvar
    buildStatTable(fb.font, [{"tag": tag, "name": fvar.axes[i].axisNameID, "ordering": i} for i, tag in enumerate(tags)])
    supports = [support for tag in tags for support in ({tag: (-1, -1, 0)}, {tag: (0, 1, 1)})]
    rows = [[0] * len(supports) for _ in names]
    rows[1] = [delta for w in weights for delta in (-16 * w, 16 * w)]
    hvar = newTable("HVAR"); hvar.table = otTables.HVAR(); hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(buildVarRegionList(supports, tags), [buildVarData(range(len(supports)), rows, optimize=True)])
    hvar.table.AdvWidthMap = None; hvar.table.LsbMap = None; hvar.table.RsbMap = None
    fb.font["HVAR"] = hvar
    ttf = OUT / f"hvar{width}.ttf"; woff = ttf.with_suffix(".woff2")
    fb.font.save(ttf); fb.font.flavor = "woff2"; fb.font.save(woff)
    return {
        "id": f"hvar{width}", "kind": "hvar", "width": width, "weights": weights,
        "fontFamily": family, "fontFile": f"hvar-control/{woff.name}",
        "features": [], "inputCodepoints": [], "codepoint": 0xE000,
        "nonceCodepoint": 0xE100, "nonces": 65, "axes": tags,
        "output": {"offset": BASE, "fontSize": 1024, "unitsPerEm": 1024},
        "glyphs": len(names), "lookups": 0, "woff2Bytes": woff.stat().st_size,
        "ttfBytes": ttf.stat().st_size,
        "fontSha256": hashlib.sha256(woff.read_bytes()).hexdigest(),
        "operation": "2*sum_i(w_i*x_i)+1, folded into HVAR weights and default metric",
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    variants = [build(width) for width in (4, 8, 16, 64)]
    report = {"kind": "HVAR context control, not GSUB computation", "variants": variants,
              "sourceSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scope": "Same synthetic affine function, same native numerical consumption; existing variable-font mechanism"}
    (OUT / "reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps([{k: v[k] for k in ("id", "glyphs", "woff2Bytes")} for v in variants]))


if __name__ == "__main__":
    main()
