#!/usr/bin/env python3
"""R4X scores-hop fixture: 96 (12 heads x 8 slots) HVAR dot products -> 96 CSS numbers, three transports.
 T: view-timeline readback (today's carrier, emitter decode)      M: `1ch` font-metric unit on the producing element (no layout)
 C: in-flow anchors -> position:fixed size-container chain (F3)   Pages + meta JSON for F3/proto_run.mjs. No JS in pages."""
import json, sys
from pathlib import Path
import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.varLib.builder import buildVarData, buildVarRegionList, buildVarStore

HERE = Path(__file__).resolve().parent
OUT = HERE / "pages"
HEADS, SLOTS, AX = 12, 8, 16
UPEM, BASE, FS = 1000, 1500, 512
PX = FS / UPEM          # px per unit
V = 65536               # timeline viewport width (as the emitter's qkv scroller)
rng = np.random.default_rng(20260920)
C = rng.integers(-30, 31, size=AX)                       # per-axis advance deltas (units)
K = rng.choice([-1.0, -0.5, 0.5, 1.0], size=(SLOTS, AX))  # per-slot "keys"
Q = np.round(rng.uniform(-1, 1, size=(16, HEADS, AX)), 4)  # 16 input sets ("go-k")
def f2dot14(x):
    return np.trunc(x * 16384) / 16384
def expected(k, trunc):
    out = []
    for h in range(HEADS):
        for s in range(SLOTS):
            coord = Q[k, h] * K[s]
            if trunc: coord = f2dot14(coord)
            out.append(float(BASE + (C * coord).sum()))
    return out

def rect(w, hgt):
    pen = TTGlyphPen(None); pen.moveTo((0, 0)); pen.lineTo((w, 0)); pen.lineTo((w, hgt)); pen.lineTo((0, hgt)); pen.closePath(); return pen.glyph()

def build_font(dest):
    glyphs = [".notdef", "space", "zero"]
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(glyphs)
    fb.setupCharacterMap({0x20: "space", 0x30: "zero"})
    fb.setupGlyf({".notdef": rect(1, 1), "space": rect(1, 1), "zero": rect(1, 700)})
    fb.setupHorizontalMetrics({".notdef": (500, 0), "space": (500, 0), "zero": (BASE, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200, lineGap=0)
    fb.setupNameTable({"familyName": "R4XScore", "styleName": "Regular", "uniqueFontIdentifier": "R4XScore-Regular", "fullName": "R4XScore Regular", "psName": "R4XScore-Regular"})
    fb.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200, sTypoLineGap=0, usWinAscent=800, usWinDescent=200, sxHeight=500, sCapHeight=700, fsSelection=0xC0)
    fb.setupPost(); fb.setupMaxp(); fb.setupHead(created=2_082_844_800, modified=2_082_844_800)
    fb.font.recalcTimestamp = False
    fb.save(dest)
    font = TTFont(dest, recalcTimestamp=False)
    fvar = newTable("fvar"); fvar.axes = []; fvar.instances = []
    tags = [f"X{i:03d}" for i in range(AX)]; stat = []
    for i, tag in enumerate(tags):
        a = Axis(); a.axisTag = tag; a.minValue = -1; a.defaultValue = 0; a.maxValue = 1; a.flags = 0
        a.axisNameID = font["name"].addName(tag); fvar.axes.append(a); stat.append({"tag": tag, "name": a.axisNameID, "ordering": i})
    font["fvar"] = fvar; buildStatTable(font, stat)
    supports = []
    for tag in tags: supports.extend(({tag: (-1, -1, 0)}, {tag: (0, 1, 1)}))
    regions = buildVarRegionList(supports, tags)
    rows = [[0] * len(supports) for _ in glyphs]
    rows[2] = [d for c in C.tolist() for d in (-c, c)]
    hvar = newTable("HVAR"); hvar.table = otTables.HVAR(); hvar.table.Version = 0x00010000
    hvar.table.VarStore = buildVarStore(regions, [buildVarData(range(len(supports)), rows, optimize=True)])
    hvar.table.AdvWidthMap = None; hvar.table.LsbMap = None; hvar.table.RsbMap = None
    font["HVAR"] = hvar
    font.save(dest)

def fvs(h, s):
    return ",".join(f'"X{j:03d}" calc(var(--q-{h}-{j}) * {K[s, j]:g})' for j in range(AX))
def inputs_css():
    css = ""
    for k in range(16):
        css += f"html.go-{k}{{" + ";".join(f"--q-{h}-{j}:{Q[k, h, j]:g}" for h in range(HEADS) for j in range(AX)) + "}"
    return css
def reg(names, inherits):
    return "".join(f'@property {n}{{syntax:"<number>";inherits:{inherits};initial-value:-1}}' for n in names)
COMMON = (f"@font-face{{font-family:R4XScore;src:url(r4x-score.ttf)}}body{{margin:0}}"
          f".metric{{position:absolute;left:0;top:0;display:inline-flex;width:max-content;height:1px;overflow:clip;min-width:0;white-space:pre;font:{FS}px R4XScore;font-kerning:none;line-height:1}}"
          f".s{{display:block;font:{FS}px R4XScore;font-kerning:none;line-height:1}}")  # emitter .metric (browser_gpt2_core.py:78 / combined4 runtime.css); .s BEFORE .m-* rules
COMMON += "".join(f".m-{h}-{s}{{font-variation-settings:{fvs(h, s)}}}" for h in range(HEADS) for s in range(SLOTS))

def page_T():
    fs = [f"--fs-{h}-{s}" for h in range(HEADS) for s in range(SLOTS)]
    ps = [f"--p-{h}-{s}" for h in range(HEADS) for s in range(SLOTS)]
    tl = [f"--t-{h}-{s}" for h in range(HEADS) for s in range(SLOTS)]
    css = COMMON + inputs_css() + reg(fs + ps, "false")
    css += "html{timeline-scope:" + ",".join(tl) + "}"
    css += f".scroller{{position:fixed;left:0;top:0;width:{V}px;height:600px;overflow-x:scroll;contain:strict}}.track{{position:relative;height:1px;width:{V * 3}px}}"
    css += "".join(f"@keyframes k-{h}-{s}{{from{{--p-{h}-{s}:0}}to{{--p-{h}-{s}:1}}}}" for h in range(HEADS) for s in range(SLOTS))
    css += ("#reader{animation-name:" + ",".join(f"k-{h}-{s}" for h in range(HEADS) for s in range(SLOTS)) +
            ";animation-duration:1s;animation-fill-mode:both;animation-timing-function:linear;animation-range:cover;animation-timeline:" + ",".join(tl) + ";" +
            ";".join(f"--fs-{h}-{s}:calc(({V} / var(--p-{h}-{s}) - {V}) / {PX:g})" for h in range(HEADS) for s in range(SLOTS)) + "}")
    body = '<div class="scroller"><div class="track">' + "".join(f'<i class="metric m-{h}-{s}" style="view-timeline:--t-{h}-{s} inline">0</i>' for h in range(HEADS) for s in range(SLOTS)) + '</div></div><div id="reader"></div>'
    verify = [{"selector": "#reader", "props": fs}]
    return css, body, verify

def page_M():
    fs = [f"--fs-{h}-{s}" for h in range(HEADS) for s in range(SLOTS)]
    css = COMMON + inputs_css() + reg(fs, "true")
    css += "".join(f".s.m-{h}-{s}{{--fs-{h}-{s}:calc(1ch / 1px / {PX:g})}}" for h in range(HEADS) for s in range(SLOTS))
    body = ""
    for h in range(HEADS):
        body += "".join(f'<div class="s m-{h}-{s}">' for s in range(SLOTS)) + f'<b id="soft-{h}"></b>' + "</div>" * SLOTS
    verify = [{"selector": f"#soft-{h}", "props": [f"--fs-{h}-{s}" for s in range(SLOTS)]} for h in range(HEADS)]
    return css, body, verify

def page_C():
    fs = [f"--fs-{h}-{s}" for h in range(HEADS) for s in range(SLOTS)]
    css = COMMON + inputs_css() + reg(fs, "true")
    css += ".anchors{position:relative;height:1px;width:200000px}.anchors>.metric{position:static;display:inline-block}.c{position:fixed;left:0;top:0;container-type:size;visibility:hidden}"
    body = '<div class="anchors">' + "".join(f'<i class="metric m-{h}-{s}" style="anchor-name:--g-{h}-{s}">0</i>' for h in range(HEADS) for s in range(SLOTS)) + "</div>"
    for h in range(HEADS):
        for s in range(0, SLOTS, 2):
            body += (f'<div class="c" style="width:anchor-size(--g-{h}-{s} width);height:anchor-size(--g-{h}-{s + 1} width)">'
                     f'<div class="r" style="--fs-{h}-{s}:calc(100cqw / 1px / {PX:g});--fs-{h}-{s + 1}:calc(100cqh / 1px / {PX:g})">')
        body += f'<b id="soft-{h}"></b>' + "</div></div>" * (SLOTS // 2)
    verify = [{"selector": f"#soft-{h}", "props": [f"--fs-{h}-{s}" for s in range(SLOTS)]} for h in range(HEADS)]
    return css, body, verify

def write(pid, builder):
    css, body, verify = builder()
    html = f'<!doctype html><html class="go-0"><head><meta charset="utf-8"><title>{pid}</title><style>{css}</style></head><body>{body}</body></html>'
    (OUT / f"{pid}.html").write_text(html)
    meta = {"id": pid, "file": f"{pid}.html", "verify": verify, "tolerance": 1e-3,
            "expected": {str(k): expected(k, False) for k in range(16)},
            "expected_f2dot14": {str(k): expected(k, True) for k in range(16)}}
    (OUT / f"{pid}.json").write_text(json.dumps(meta))
    print(pid, len(html), "bytes;", sum(len(v["props"]) for v in verify), "values")

OUT.mkdir(exist_ok=True)
build_font(OUT / "r4x-score.ttf")
t = TTFont(OUT / "r4x-score.ttf"); print("font: axes", len(t["fvar"].axes), "HVAR regions", t["HVAR"].table.VarStore.VarRegionList.RegionCount, "bytes", (OUT / "r4x-score.ttf").stat().st_size)
for pid, b in (("scores-T-timeline", page_T), ("scores-M-metric", page_M), ("scores-C-chain", page_C)): write(pid, b)
e0 = expected(0, False); print("expected[0] range", min(e0), max(e0), "px range", min(e0) * PX, max(e0) * PX)
print("f2dot14 truncation max delta (units):", max(abs(a - b) for k in range(16) for a, b in zip(expected(k, False), expected(k, True))))
