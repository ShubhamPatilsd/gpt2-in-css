#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Build distinct fixed matrix rows, with per-row GSUB and multi-glyph HVAR."""
from __future__ import annotations

import argparse
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

import build_gsub_weighted_sum_probe as gsub

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-shared-matrix-probe"
BASE = 8192


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def matrix(width, rows):
    state = 0x51F15E ^ width
    result = []
    choices = [-3, -2, -1, 1, 2, 3]
    while len(result) < rows:
        row = []
        for _ in range(width):
            state ^= (state << 13) & 0xFFFFFFFF
            state ^= state >> 17
            state ^= (state << 5) & 0xFFFFFFFF
            state &= 0xFFFFFFFF
            row.append(choices[state % len(choices)])
        if row not in result:
            result.append(row)
    return result


def build_hvar(width, weights):
    family = f"SharedMatrixHVAR{width}"
    names = [".notdef"] + [f"result{row}" for row in range(len(weights))] + [f"nonce{i}" for i in range(65)]
    fb = FontBuilder(1024, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({**{0xE000 + r: f"result{r}" for r in range(len(weights))}, **{0xE100 + i: f"nonce{i}" for i in range(65)}})
    empty = TTGlyphPen(None).glyph()
    outlines = {name: empty for name in names}
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0)); pen.lineTo((1, 0)); pen.lineTo((0, 1)); pen.closePath()
    outlines[".notdef"] = pen.glyph()
    fb.setupGlyf(outlines)
    fb.setupHorizontalMetrics({name: ((BASE + 1 if name.startswith("result") else 0), 0) for name in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": family + "-v1", "fullName": family, "psName": family})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost(); fb.setupMaxp()
    tags = [f"X{i:03d}" for i in range(width)]
    fvar = newTable("fvar"); fvar.axes = []; fvar.instances = []
    for tag in tags:
        axis = Axis(); axis.axisTag = tag; axis.minValue = -8; axis.defaultValue = 0; axis.maxValue = 8
        axis.flags = 0; axis.axisNameID = fb.font["name"].addName(tag); fvar.axes.append(axis)
    fb.font["fvar"] = fvar
    buildStatTable(fb.font, [{"tag": tag, "name": fvar.axes[i].axisNameID, "ordering": i} for i, tag in enumerate(tags)])
    supports = [support for tag in tags for support in ({tag: (-1, -1, 0)}, {tag: (0, 1, 1)})]
    deltas = [[0] * len(supports)]
    deltas += [[delta for weight in row for delta in (-16 * weight, 16 * weight)] for row in weights]
    deltas += [[0] * len(supports) for _ in range(65)]
    hvar = newTable("HVAR"); hvar.table = otTables.HVAR(); hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(buildVarRegionList(supports, tags), [buildVarData(range(len(supports)), deltas, optimize=True)])
    hvar.table.AdvWidthMap = None; hvar.table.LsbMap = None; hvar.table.RsbMap = None
    fb.font["HVAR"] = hvar
    directory = OUT / "hvar"; directory.mkdir(parents=True, exist_ok=True)
    ttf = directory / f"n{width}.ttf"; woff = ttf.with_suffix(".woff2")
    fb.font.save(ttf); fb.font.flavor = "woff2"; fb.font.save(woff)
    return {"fontFamily": family, "fontFile": str(woff.relative_to(OUT)), "fontSha256": sha(woff), "woff2Bytes": woff.stat().st_size,
            "ttfBytes": ttf.stat().st_size, "glyphs": len(names), "axes": tags, "codepoints": [0xE000 + r for r in range(len(weights))],
            "nonceCodepoint": 0xE100, "nonces": 65, "outputOffset": BASE, "fontSize": 1024, "unitsPerEm": 1024}


def build_width(width, row_count):
    weights = matrix(width, row_count)
    rows = []
    for index, row in enumerate(weights):
        directory = OUT / "gsub" / f"n{width}" / f"row{index}"
        prior = directory / f"w{width}-sequential" / "reference.json"
        cached = json.loads(prior.read_text()) if prior.exists() else None
        if cached and cached["weights"] == row and all((directory / file).exists() and sha(directory / file) == info["sha256"] for file, info in cached["files"].items()):
            record = cached
            print(f"reuse n{width} row{index}", flush=True)
        else:
            gsub.WEIGHTS = tuple(row)
            record = gsub.build(width, "sequential", directory)
        file = directory / record["fontFile"]
        rows.append({"row": index, "weights": row, "fontFamily": f"SharedGSUB{width}Row{index}",
                     "fontFile": str(file.relative_to(OUT)), "fontSha256": sha(file), "woff2Bytes": file.stat().st_size,
                     "outputOffset": record["output"]["offset"], "features": record["features"],
                     "inputCodepoints": record["inputCodepoints"], "nonceCodepoint": record["nonceCodepoint"], "nonces": record["nonces"],
                     "structure": record["structure"], "compilerSourceAtBuildSha256": record["compilerSourceAtBuildSha256"]})
    hvar = build_hvar(width, weights)
    return {"width": width, "outputRows": row_count, "weights": weights, "gsub": rows, "hvar": hvar}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--widths", nargs="+", type=int, default=[4, 16, 64])
    parser.add_argument("--rows", type=int, default=16)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "reference.json"
    old = json.loads(path.read_text()) if path.exists() else {"matrices": []}
    keep = [m for m in old["matrices"] if m["width"] not in args.widths]
    for width in args.widths:
        keep.append(build_width(width, args.rows))
        report = {"description": "One inherited input vector, distinct fixed weighted output rows", "formula": "output[r] = 2*sum_i(weights[r][i]*input[i])+1",
                  "inputDomain": [-8, 7], "matrices": sorted(keep, key=lambda m: m["width"]), "compilerSha256": sha(Path(__file__)),
                  "reusedGsubCompilerSha256": sha(Path(gsub.__file__)), "gsubRepresentation": "Separate fixed font and shaping run per output row; only parent input writes are shared",
                  "hvarRepresentation": "One N-axis font contains all output glyphs; one parent font-variation-settings value is inherited by every output"}
        path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
