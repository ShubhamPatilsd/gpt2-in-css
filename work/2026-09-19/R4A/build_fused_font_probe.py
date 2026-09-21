#!/usr/bin/env python3
"""Build a reduced fused font (769 axes, avar2 A.x dense over 256 hidden rows, HVAR K hats per hidden axis,
G glyphs) to calibrate raw table sizes and WOFF2 compression of the R4A cost model. Offline only."""
import sys, time, io
import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.varLib.builder import buildVarRegionList, buildVarData, buildVarStore
from fontTools.varLib.varStore import OnlineVarStoreBuilder  # noqa
from fontTools.ttLib.tables._f_v_a_r import Axis

AXES = 769; HIDDEN = int(sys.argv[1]) if len(sys.argv) > 1 else 256; K = int(sys.argv[2]) if len(sys.argv) > 2 else 8
GLYPHS = int(sys.argv[3]) if len(sys.argv) > 3 else 64
t0 = time.time()
rng = np.random.default_rng(0)
tags = [f"{i:04d}"[-4:].replace("0", "a", 1) if False else f"{i:04x}" for i in range(AXES)]
tags = [(t + "zzzz")[:4] for t in tags]
names = [".notdef"] + [f"g{i}" for i in range(GLYPHS)]
fb = FontBuilder(1000, isTTF=True)
fb.setupGlyphOrder(names)
fb.setupCharacterMap({0xE000 + i: f"g{i}" for i in range(GLYPHS)})
from fontTools.pens.ttGlyphPen import TTGlyphPen
pen = TTGlyphPen(None); pen.moveTo((0, 0)); pen.lineTo((10, 0)); pen.lineTo((10, 10)); pen.closePath(); gl = pen.glyph()
fb.setupGlyf({n: gl for n in names})
fb.setupHorizontalMetrics({n: (32732, 0) for n in names})
fb.setupHorizontalHeader(ascent=800, descent=-200)
fb.setupNameTable({"familyName": "R4AFused", "styleName": "Regular"})
fb.setupOS2(); fb.setupPost()
fb.setupFvar([(t, -1.0, 0.0, 1.0, t) for t in tags], [])
font = fb.font
# avar2: dense A over the first HIDDEN axes (outputs) from all 768 input axes + bias axis: 2 regions per input axis + 1
sup = []
for t in tags[:768]:
    sup.extend(({t: (-1, -1, 0)}, {t: (0, 1, 1)}))
sup.append({tags[768]: (0, 1, 1)})
regions = buildVarRegionList(sup, tags)
rows = np.clip(rng.normal(0, 300, size=(HIDDEN, len(sup))), -32767, 32767).astype(int).tolist()
data = buildVarData(range(len(sup)), rows, optimize=False)
avar = newTable("avar"); avar.majorVersion = 2; avar.minorVersion = 0
avar.segments = {t: {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0} for t in tags}
avar.table = otTables.avar(); avar.table.Reserved = 0
from fontTools.varLib.builder import buildDeltaSetIndexMap
avar.table.VarIdxMap = buildDeltaSetIndexMap([i if i < HIDDEN else 0xFFFF for i in range(AXES)] if False else list(range(HIDDEN)) + [0xFFFF] * (AXES - HIDDEN))
avar.table.VarStore = buildVarStore(regions, [data])
font["avar"] = avar
t1 = time.time()
# HVAR: K hats per hidden axis
knots = np.linspace(-1, 1, K + 1); knots = knots[np.abs(knots) > 1e-9] if (K + 1) % 2 else knots
hsup = []
for t in tags[:HIDDEN]:
    for j, k in enumerate(knots):
        st = knots[j - 1] if j else -1.0; en = knots[j + 1] if j + 1 < len(knots) else 1.0
        hsup.append({t: (float(st), float(k), float(en))})
hregions = buildVarRegionList(hsup, tags)
hrows = [[0] * len(hsup)] + np.clip(rng.normal(0, 40, size=(GLYPHS, len(hsup))), -32767, 32767).astype(int).tolist()
hdata = buildVarData(range(len(hsup)), hrows, optimize=False)
hvar = newTable("HVAR"); hvar.table = otTables.HVAR(); hvar.table.Version = 0x00010000
hvar.table.VarStore = buildVarStore(hregions, [hdata])
hvar.table.AdvWidthMap = None; hvar.table.LsbMap = None; hvar.table.RsbMap = None
font["HVAR"] = hvar
buf = io.BytesIO(); font.save(buf); raw = buf.getvalue(); t2 = time.time()
f2 = TTFont(io.BytesIO(raw)); sizes = {tag: f2.reader.tables[tag].length for tag in f2.reader.tables}
print(f"AXES={AXES} HIDDEN={HIDDEN} K={K} GLYPHS={GLYPHS}: avar2 regions {len(sup)}, HVAR regions {len(hsup)}; raw TTF {len(raw)/1e6:.2f} MB; build {t2-t0:.0f}s")
print("  table sizes:", {k: v for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])[:5]})
f2.flavor = "woff2"; wb = io.BytesIO(); f2.save(wb); w = len(wb.getvalue())
print(f"  WOFF2 {w/1e6:.2f} MB (ratio {len(raw)/w:.1f}x); avar {sizes['avar']/1e6:.2f} MB (model {((len(sup))*AXES*6 + HIDDEN*len(sup)*2)/1e6:.2f}), HVAR {sizes['HVAR']/1e6:.2f} MB (model {(len(hsup)*AXES*6 + (GLYPHS+1)*len(hsup)*2)/1e6:.2f}) {time.time()-t0:.0f}s")
