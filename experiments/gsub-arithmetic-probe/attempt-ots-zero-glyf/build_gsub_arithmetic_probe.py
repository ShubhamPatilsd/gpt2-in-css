#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli"]
# ///
"""Small digital GSUB programs; all arithmetic during page inference is native."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/gsub-arithmetic-probe"
BASE = 64
CP = 0xE000


def nonlinear(value: int) -> int:
    return min(255, (value - 128) ** 2 // 128)


def name(prefix: str, value: int) -> str:
    return f"{prefix}{'m' if value < 0 else 'p'}{abs(value)}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    glyphs = [".notdef"]
    advances: dict[str, int] = {".notdef": 1}
    cmap = {}

    def group(prefix: str, values: range, output=False, mapping=None):
        for value in values:
            label = name(prefix, value)
            glyphs.append(label)
            advances[label] = BASE + value if output else 0
            if mapping is not None:
                cmap[mapping + value] = label

    for index, prefix in enumerate(("al", "bl", "ah", "bh", "x", "y")):
        group(prefix, range(16), mapping=CP + index * 16)
    for prefix in ("lt", "ht"):
        group(prefix, range(31))
    group("hc", range(1, 32))
    group("ln", range(16))
    group("hn", range(32))
    group("sum", range(512), output=True)
    group("nonlinear", range(256), output=True)
    group("pair", range(256))
    group("p0", range(-16, 30))
    group("p1", range(-22, 24))
    group("h0", range(30))
    group("h1", range(24))
    group("np", range(-41, 93))
    group("out", range(93), output=True)

    definitions = []
    calls = []

    def lookup(label, rules, called=True):
        definitions.append(f"lookup {label} {{\n" + "\n".join(rules) + f"\n}} {label};")
        if called:
            calls.append(label)

    lookup("LowAdd", [f"sub {name('al', a)} {name('bl', b)} by {name('lt', a+b)};" for a in range(16) for b in range(16)])
    lookup("HighAdd", [f"sub {name('ah', a)} {name('bh', b)} by {name('ht', a+b)};" for a in range(16) for b in range(16)])
    lookup("Increment", [f"sub {name('ht', i)} by {name('hc', i+1)};" for i in range(31)], called=False)
    definitions.append("@Carry = [" + " ".join(name("lt", i) for i in range(16, 31)) + "];")
    definitions.append("@High = [" + " ".join(name("ht", i) for i in range(31)) + "];")
    lookup("Carry", ["sub @Carry @High' lookup Increment;"])
    lookup("NormalizeLow", [f"sub {name('lt', i)} by {name('ln', i % 16)};" for i in range(31)])
    lookup("NormalizeHigh", [f"sub {name('ht', i)} by {name('hn', i)};" for i in range(31)] + [f"sub {name('hc', i)} by {name('hn', i)};" for i in range(1, 32)])
    lookup("SumPack", [f"sub {name('ln', lo)} {name('hn', hi)} by {name('sum', lo+16*hi)};" for lo in range(16) for hi in range(32)])
    add_calls = list(calls)
    calls.clear()
    lookup("NetworkInput", [f"sub {name('x', x)} {name('y', y)} by {name('pair', x*16+y)};" for x in range(16) for y in range(16)])
    lookup("NetworkExpand", [f"sub {name('pair', x*16+y)} by {name('p0', 2*x+y-16)} {name('p1', x-2*y+8)};" for x in range(16) for y in range(16)])
    lookup("NetworkActivation", [f"sub {name('p0', i)} by {name('h0', max(0, i))};" for i in range(-16, 30)] + [f"sub {name('p1', i)} by {name('h1', max(0, i))};" for i in range(-22, 24)])
    lookup("NetworkOutput", [f"sub {name('h0', x)} {name('h1', y)} by {name('np', 3*x-2*y+5)};" for x in range(30) for y in range(24)])
    lookup("NetworkFinal", [f"sub {name('np', i)} by {name('out', max(0, i))};" for i in range(-41, 93)])
    network_calls = list(calls)
    lookup("Nonlinear", [f"sub {name('sum', i)} by {name('nonlinear', nonlinear(i))};" for i in range(512)], called=False)
    feature = "languagesystem DFLT dflt;\n" + "\n".join(definitions)
    feature += "\nfeature rlig { " + " ".join(f"lookup {label};" for label in add_calls + network_calls) + " } rlig;"
    feature += "\nfeature ss01 { lookup Nonlinear; } ss01;\n"
    (OUT / "program.fea").write_text(feature)

    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(glyphs)
    builder.setupCharacterMap(cmap)
    empty = TTGlyphPen(None).glyph()
    builder.setupGlyf({glyph: empty for glyph in glyphs})
    builder.setupHorizontalMetrics({glyph: (advances[glyph], 0) for glyph in glyphs})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "GSUB Arithmetic", "styleName": "Regular", "uniqueFontIdentifier": "GSUBArithmetic-v1", "fullName": "GSUB Arithmetic", "psName": "GSUBArithmetic"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    addOpenTypeFeaturesFromString(builder.font, feature)
    builder.font.save(OUT / "arithmetic.ttf")
    builder.font.flavor = "woff2"
    builder.font.save(OUT / "arithmetic.woff2")

    css = ['@font-face{font-family:Arithmetic;src:url("arithmetic.woff2")}', '@property --a{syntax:"<integer>";inherits:true;initial-value:0}', '@property --b{syntax:"<integer>";inherits:true;initial-value:0}', '.probe{display:inline-block;vertical-align:top;font:1000px/1 Arithmetic;white-space:pre;font-kerning:none;font-feature-settings:"rlig" 1,"ss01" 0}', '.probe.nonlinear{font-feature-settings:"rlig" 1,"ss01" 1}', '.probe>*{display:inline-block}', '.encoded::before{counter-reset:al mod(var(--a),16) bl mod(var(--b),16) ah round(down,var(--a)/16,1) bh round(down,var(--b)/16,1);content:counter(al,al) counter(bl,bl) counter(ah,ah) counter(bh,bh)}', '.encoded.network::before{counter-reset:x var(--a) y var(--b);content:counter(x,x) counter(y,y)}', '.control{height:1px;width:calc((64 + var(--a) + var(--b))*1px)}', '.control.nonlinear{width:calc((64 + min(255,round(down,(var(--a) + var(--b) - 128)*(var(--a) + var(--b) - 128)/128,1)))*1px)}', '.control.network{width:calc((64 + max(0,3*max(0,2*var(--a) + var(--b) - 16) - 2*max(0,var(--a) - 2*var(--b) + 8) + 5))*1px)}', 'body{margin:0}#rows{position:absolute;inset:0;contain:layout}']
    for index, prefix in enumerate(("al", "bl", "ah", "bh", "x", "y")):
        symbols = " ".join(f'"\\{CP + index * 16 + i:x}"' for i in range(16))
        css.append(f"@counter-style {prefix}{{system:fixed 0;symbols:{symbols};suffix:''}}")
    (OUT / "index.css").write_text("\n".join(css))
    (OUT / "index.html").write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\';object-src \'none\'"><link rel="stylesheet" href="index.css"><title>GSUB arithmetic probe</title><main id="rows"></main>')
    manifest = {"fontGlyphs": len(glyphs), "fontLookups": len(builder.font["GSUB"].table.LookupList.Lookup), "adderTopLevelLookups": len(add_calls), "adderNestedCarryLookups": 1, "nonlinearExtraLookups": 1, "networkLookups": len(network_calls), "inputCodepointBase": CP, "outputAdvanceBase": BASE, "fontUnitsPerEm": 1000, "fontSizePx": 1000, "network": {"inputs": "x,y in [0,15]", "h0": "max(0,2*x+y-16)", "h1": "max(0,x-2*y+8)", "output": "max(0,3*h0-2*h1+5)", "firstLayerJointInputStates": 256, "secondLayerJointHiddenStates": 720}, "nonlinear": "min(255,floor((a+b-128)^2/128))", "runtimeScripts": 0, "files": {}}
    for path in (OUT / "arithmetic.ttf", OUT / "arithmetic.woff2", OUT / "program.fea", OUT / "index.css", OUT / "index.html", Path(__file__)):
        payload = path.read_bytes()
        manifest["files"][str(path.relative_to(ROOT))] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    (OUT / "reference.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
