#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Diagnostic font: one precomputed answer per glyph, no arithmetic rules."""
import hashlib
import json
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-reader-isolation"
OUT.mkdir(parents=True, exist_ok=True)
low, high, offset = -2751, 2529, 8192
answers = list(range(low, high + 1, 2))
names = [".notdef"] + [f"answer{i}" for i in range(len(answers))] + [f"nonce{i}" for i in range(65)]
fb = FontBuilder(1024, isTTF=True)
fb.setupGlyphOrder(names)
fb.setupCharacterMap({**{0xF0000+i: f"answer{i}" for i in range(len(answers))},
                      **{0xE100+i: f"nonce{i}" for i in range(65)}})
empty = TTGlyphPen(None).glyph()
outlines = {name: empty for name in names}
pen = TTGlyphPen(None)
pen.moveTo((0, 0)); pen.lineTo((1, 0)); pen.lineTo((0, 1)); pen.closePath()
outlines[".notdef"] = pen.glyph()
fb.setupGlyf(outlines)
metrics = {name: (0, 0) for name in names}
metrics.update({f"answer{i}": (offset+y, 0) for i, y in enumerate(answers)})
metrics[".notdef"] = (1, 0)
fb.setupHorizontalMetrics(metrics)
fb.setupHorizontalHeader(ascent=800, descent=-200)
fb.setupNameTable({"familyName": "ReaderAnswerControl", "styleName": "Regular",
                   "uniqueFontIdentifier": "ReaderAnswerControl-v1", "fullName": "ReaderAnswerControl",
                   "psName": "ReaderAnswerControl"})
fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
fb.setupPost(); fb.setupMaxp()
fb.font.save(OUT / "answer-control.ttf")
fb.font.flavor = "woff2"
font_file = OUT / "answer-control.woff2"
fb.font.save(font_file)
manifest = {"family": "ReaderAnswerControl", "kind": "precomputed-answer diagnostic only",
            "minimumAnswer": low, "maximumAnswer": high, "step": 2, "offset": offset,
            "codepoint": 0xF0000, "nonceCodepoint": 0xE100, "nonces": 65,
            "glyphs": len(names), "fontFile": font_file.name,
            "woff2Bytes": font_file.stat().st_size,
            "fontSha256": hashlib.sha256(font_file.read_bytes()).hexdigest(),
            "sourceSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(OUT / "reference.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest))
