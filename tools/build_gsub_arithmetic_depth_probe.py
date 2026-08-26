#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Compile repeated two-coordinate digital cells, not whole-chain answer tables."""
from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-arithmetic-depth-probe"
DEPTHS = (1, 2, 4, 8)
NONCES = 65


def build_font(depth):
    order = [".notdef"] + [f"nonce{i}" for i in range(NONCES)]
    for layer in range(depth + 1):
        order += [f"{coord}{layer}v{i}" for coord in ("x", "y") for i in range(16)]
    order += [f"p{layer}v{i}" for layer in range(depth) for i in range(256)]
    order += [f"out{i}" for i in range(256)]
    metrics = {glyph: (0, 0) for glyph in order}
    metrics.update({f"out{i}": (64 + i, 0) for i in range(256)})
    cmap = {0xE000 + i: f"x0v{i}" for i in range(16)}
    cmap.update({0xE010 + i: f"y0v{i}" for i in range(16)})
    cmap.update({0xE100 + i: f"nonce{i}" for i in range(NONCES)})
    empty = TTGlyphPen(None).glyph()
    outlines = {glyph: empty for glyph in order}
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0)); pen.lineTo((1, 0)); pen.lineTo((0, 1)); pen.closePath()
    outlines[".notdef"] = pen.glyph()
    builder = FontBuilder(1024, isTTF=True)
    builder.setupGlyphOrder(order); builder.setupCharacterMap(cmap)
    builder.setupGlyf(outlines); builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": f"GSUB Depth {depth}", "styleName": "Regular", "uniqueFontIdentifier": f"GSUBDepth{depth}-v1", "fullName": f"GSUB Depth {depth}", "psName": f"GSUBDepth{depth}"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost(); builder.setupMaxp()
    fea = ["languagesystem DFLT dflt;"]
    for layer in range(depth):
        fea.append(f"lookup Pair{layer} {{")
        for x in range(16):
            for y in range(16):
                fea.append(f"sub x{layer}v{x} y{layer}v{y} by p{layer}v{x*16+y};")
        fea.append(f"}} Pair{layer};\nlookup Expand{layer} {{")
        for x in range(16):
            for y in range(16):
                ny = (x + y*y + 3*y + layer + 1) % 16
                fea.append(f"sub p{layer}v{x*16+y} by x{layer+1}v{y} y{layer+1}v{ny};")
        fea.append(f"}} Expand{layer};\nfeature ss{layer+1:02d} {{ lookup Pair{layer}; lookup Expand{layer}; }} ss{layer+1:02d};")
    fea.append("lookup PackOutput {")
    for x in range(16):
        for y in range(16):
            fea.append(f"sub x{depth}v{x} y{depth}v{y} by out{x*16+y};")
    fea.append("} PackOutput;\nfeature ss20 {lookup PackOutput;} ss20;")
    program = "\n".join(fea) + "\n"
    addOpenTypeFeaturesFromString(builder.font, program)
    (OUT / f"depth{depth}.fea").write_text(program)
    builder.font.save(OUT / f"depth{depth}.ttf")
    builder.font.flavor = "woff2"; builder.font.save(OUT / f"depth{depth}.woff2")
    return {"depth": depth, "glyphs": len(order), "lookups": len(builder.font["GSUB"].table.LookupList.Lookup), "layerJointInputEntries": 256*depth, "layerExpansionEntries": 256*depth, "finalReadoutEntries": 256, "woff2Bytes": (OUT / f"depth{depth}.woff2").stat().st_size, "ttfBytes": (OUT / f"depth{depth}.ttf").stat().st_size}


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth16", action="store_true", help="Only the final depth-16 point, saved separately")
    args = parser.parse_args()
    depths = (16,) if args.depth16 else DEPTHS
    if args.depth16:
        OUT = OUT / "depth16"
    OUT.mkdir(parents=True, exist_ok=True)
    fonts = [build_font(depth) for depth in depths]
    features = ",".join(f'"ss{i:02d}" 1' for i in (*range(1, max(depths)+1), 20))
    css = ["body{margin:0}.group{position:relative;contain:layout}.item{display:inline-block;vertical-align:top}.source{display:inline-block;white-space:pre;font-size:1024px;line-height:1;font-kerning:none}", f".source{{font-feature-settings:{features}}}", ".gsub::before{counter-reset:a var(--a) b var(--b) nonce var(--nonce);content:counter(nonce,nonce) counter(a,x) counter(b,y)}", ".receiver{position:absolute;container-type:inline-size}.decoded{--packed:calc(100cqw/1px - 64);--dx:round(down,var(--packed)/16,1);--dy:mod(var(--packed),16);width:calc((64 + 16*var(--dx) + var(--dy))*1px);height:1px}"]
    for prop in ("a", "b", "nonce"):
        css.append(f'@property --{prop}{{syntax:"<integer>";inherits:true;initial-value:0}}')
    for prop in ("packed", "dx", "dy"):
        css.append(f'@property --{prop}{{syntax:"<number>";inherits:false;initial-value:-999}}')
    for layer in range(max(depths)+1):
        for coord in ("x", "y"):
            css.append(f'@property --{coord}{layer}{{syntax:"<integer>";inherits:false;initial-value:0}}')
    for tag, start, count in (("x", 0xE000, 16), ("y", 0xE010, 16), ("nonce", 0xE100, NONCES)):
        symbols = " ".join(f'"\\{start+i:x}"' for i in range(count))
        css.append(f"@counter-style {tag}{{system:fixed 0;symbols:{symbols};suffix:''}}")
    for depth in depths:
        css.append(f'@font-face{{font-family:Depth{depth};src:url("depth{depth}.woff2")}}.d{depth}.gsub{{font-family:Depth{depth}}}')
        rules = ["--x0:var(--a)", "--y0:var(--b)"]
        for layer in range(depth):
            rules += [f"--x{layer+1}:var(--y{layer})", f"--y{layer+1}:mod(var(--x{layer}) + var(--y{layer})*var(--y{layer}) + 3*var(--y{layer}) + {layer+1},16)"]
        rules.append(f"width:calc((64 + 16*var(--x{depth}) + var(--y{depth}))*1px)")
        css.append(f".d{depth}.control{{" + ";".join(rules) + ";height:1px}")
    (OUT / "index.css").write_text("\n".join(css) + "\n")
    (OUT / "index.html").write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\';object-src \'none\'"><link rel="stylesheet" href="index.css"><title>GSUB depth amortization</title><main id="fixtures"></main>')
    paths = [path for path in OUT.iterdir() if path.suffix in (".ttf", ".woff2", ".fea", ".css", ".html")] + [Path(__file__)]
    report = {"depths": depths, "cell": "(x,y) -> (y, mod(x+y*y+3*y+layer+1,16)); zero-indexed layer", "kind": "Reversible nonlinear two-coordinate digital cell, not a real MLP", "inputs": "all256 pairs x,y in[0,15]", "perLayer": "Pair ligature consumes BOTH tagged inputs; multiple substitution emits BOTH separately tagged next-layer coordinates", "noWholeChainLookup": True, "nonces": NONCES, "fonts": fonts, "files": {str(path.relative_to(ROOT)): {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths}}
    (OUT / "reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["fonts"], indent=2))


if __name__ == "__main__":
    main()
