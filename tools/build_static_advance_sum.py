#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Affine control: encode individual products in static glyph advances.

Normal text layout adds the contributions. No internal reusable sum, carry
program, nonlinear operation, or whole-vector answer table is claimed.
"""
import hashlib
import json
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-partitioned-digits"
WEIGHTS = (3, -2, 5, 1)


def main():
    directory = OUT / "static-advances"
    directory.mkdir(parents=True, exist_ok=True)
    names = [".notdef"] + [f"w{w}v{v}" for w in range(4) for v in range(16)] + [f"nonce{i}" for i in range(65)]
    cmap = {0xE000 + 16*w + v: f"w{w}v{v}" for w in range(4) for v in range(16)}
    cmap.update({0xE800 + i: f"nonce{i}" for i in range(65)})
    metrics = {".notdef": (1, 0)}
    for index, weight in enumerate(WEIGHTS):
        minimum = min(-8 * weight, 7 * weight)
        for v in range(16):
            metrics[f"w{index}v{v}"] = (2 * (weight * (v - 8) - minimum), 0)
    metrics.update({f"nonce{i}": (65, 0) for i in range(65)})
    fb = FontBuilder(1024, isTTF=True)
    fb.setupGlyphOrder(names); fb.setupCharacterMap(cmap)
    outlines = {name: TTGlyphPen(None).glyph() for name in names}
    pen = TTGlyphPen(None); pen.moveTo((0, 0)); pen.lineTo((1, 0)); pen.lineTo((0, 1)); pen.closePath()
    outlines[".notdef"] = pen.glyph()
    fb.setupGlyf(outlines); fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    family = "StaticAdvanceSum"
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": family,
                      "fullName": family, "psName": family})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost(); fb.setupMaxp()
    fb.font.save(directory / "weighted.ttf")
    fb.font.flavor = "woff2"; fb.font.save(directory / "weighted.woff2")
    files = {f"static-advances/weighted.{ext}": {"bytes": (directory/f"weighted.{ext}").stat().st_size,
             "sha256": hashlib.sha256((directory/f"weighted.{ext}").read_bytes()).hexdigest()} for ext in ("ttf", "woff2")}
    variants = []
    for n in (4, 16, 64, 256):
        weights = list(WEIGHTS) * (n // 4)
        offset = 64 - 2 * sum(min(-8*w, 7*w) for w in weights)
        variants.append({"id": f"static-w{n}", "width": n, "topology": "static-product-advances",
                         "weights": weights, "fontFamily": family, "fontFile": "static-advances/weighted.woff2",
                         "features": [], "disableControls": [], "inputCodepoints": [0xE000+16*(i%4) for i in range(n)],
                         "nonceCodepoint": 0xE800, "nonces": 65,
                         "output": {"offset": offset, "fontSize": 1024, "unitsPerEm": 1024},
                         "structure": {"fontGlyphs": len(names), "fontLookups": 0, "referencedSubtables": 0,
                                       "inputTextGlyphs": n+1, "finalGlyphs": n+1}, "files": files})
    report = {"description": "Affine-only static product-width control. Four weight alphabets; no GSUB, variation axes, carry propagation or internal next-stage state. Text layout sums individual advances.",
              "compilerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "variants": variants}
    (OUT / "static-reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"glyphs": len(names), "files": files}))


if __name__ == "__main__":
    main()
