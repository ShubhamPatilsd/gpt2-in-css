#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Bounded support gate for an alternative font machine, not an arithmetic test."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from fontTools.fontBuilder import FontBuilder
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables.DefaultTable import DefaultTable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/aat-support-probe"


def build(kind):
    fb = FontBuilder(1024, isTTF=True)
    names = [".notdef", "input", "answer"]
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({0xE000: "input", 0xE001: "answer"})
    fb.setupGlyf({g: TTGlyphPen(None).glyph() for g in names})
    fb.setupHorizontalMetrics({".notdef": (17, 0), "input": (100, 0), "answer": (700, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    family = "AATSupport" + kind
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": family,
                      "fullName": family, "psName": family})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    fb.setupMaxp()
    if kind == "morx":
        # AAT lookup format 8: first glyph 1, one replacement, new glyph 2.
        lookup = struct.pack(">4H", 8, 1, 1, 2)
        # Version 2; one chain; enabled by default; horizontal noncontextual map.
        subtable = struct.pack(">3I", 12 + len(lookup), 4, 1) + lookup
        chain = struct.pack(">4I", 1, 16 + len(subtable), 0, 1) + subtable
        table = DefaultTable("morx")
        table.data = struct.pack(">2I", 0x00020000, 1) + chain
        fb.font["morx"] = table
    elif kind == "gsub":
        addOpenTypeFeaturesFromString(fb.font, "languagesystem DFLT dflt; feature liga { sub input by answer; } liga;")
    ttf = OUT / f"{kind}.ttf"
    fb.font.save(ttf)
    fb.font.flavor = "woff2"
    fb.font.save(OUT / f"{kind}.woff2")
    command = ["/opt/homebrew/bin/hb-shape", str(ttf), "\ue000", "--output-format=json", "--no-glyph-names"]
    shaped = subprocess.run(command, text=True, capture_output=True, check=True)
    return {"kind": kind, "family": family, "standaloneHarfBuzz": json.loads(shaped.stdout),
            "files": {f"{kind}.{ext}": {"bytes": (OUT / f"{kind}.{ext}").stat().st_size,
                      "sha256": hashlib.sha256((OUT / f"{kind}.{ext}").read_bytes()).hexdigest()}
                      for ext in ("ttf", "woff2")}}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    records = [build(kind) for kind in ("plain", "morx", "gsub")]
    assert records[0]["standaloneHarfBuzz"][0]["ax"] == 100
    assert all(r["standaloneHarfBuzz"][0]["ax"] == 700 for r in records[1:])
    result = {"purpose": "Does a downloaded font execute AAT substitutions? No arithmetic or performance claim.",
              "harfbuzzVersion": subprocess.check_output(["/opt/homebrew/bin/hb-shape", "--version"], text=True).splitlines()[0],
              "builderSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "records": records}
    (OUT / "reference.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
