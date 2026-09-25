"""R5H font exactness: for each R5H dot font vs its F4 source — every table except cmap byte-identical (head: checksum only),
cmap = source + {U+0030 -> dot}, and the HVAR-instanced advance of the dot glyph equal at random axis locations (fontTools VarStoreInstancer).
usage: uv run --with fonttools --with brotli --with numpy python font_check.py"""
import random, sys
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.varStore import VarStoreInstancer
from fontTools.varLib.models import normalizeLocation
W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
SRC = W / "F4/assets/font-vector-operators-f4"; NEW = W / "R5H/assets-r5h/font-vector-operators-r5h"
random.seed(5)
fail = 0
def advance(font, glyph, loc):
    axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes}
    nloc = normalizeLocation(loc, axes)
    inst = VarStoreInstancer(font["HVAR"].table.VarStore, font["fvar"].axes, nloc)
    gid = font.getGlyphID(glyph)
    m = font["HVAR"].table.AdvWidthMap
    idx = m.mapping[glyph] if m else gid
    return font["hmtx"].metrics[glyph][0] + inst[idx]
for src in sorted(SRC.glob("dot-h*-f4.woff2"), key=lambda p: int(p.stem.split("-")[1][1:])):
    new = NEW / f"{src.stem}-r5h.woff2"
    a, b = TTFont(src, recalcTimestamp=False), TTFont(new, recalcTimestamp=False)
    tags = sorted(set(a.keys()) | set(b.keys())) ; tags.remove("GlyphOrder")
    diff = []
    for t in tags:
        x, y = a.getTableData(t), b.getTableData(t)
        if t == "head": x, y = x[:8] + x[12:], y[:8] + y[12:]
        if x != y: diff.append(t)
    cm_a = {(t.format, t.platformID, t.platEncID): dict(t.cmap) for t in a["cmap"].tables}
    cm_b = {(t.format, t.platformID, t.platEncID): dict(t.cmap) for t in b["cmap"].tables}
    cmap_ok = set(cm_a) == set(cm_b) and all(cm_b[k] == {**cm_a[k], 0x30: "dot"} for k in cm_a)
    axes = [ax.axisTag for ax in a["fvar"].axes]
    adv_ok = True; samples = []
    for _ in range(6):
        loc = {t: random.uniform(-1, 1) for t in axes}
        va, vb = advance(a, "dot", loc), advance(b, "dot", loc)
        samples.append(round(va, 3)); adv_ok &= (va == vb)
    ok = (diff == ["cmap"]) and cmap_ok and adv_ok and b.getGlyphOrder() == a.getGlyphOrder()
    fail += not ok
    print(f"{src.name} -> {new.name}: tables differing {diff} cmap+U+0030 {cmap_ok} glyphorder {a.getGlyphOrder()} HVAR advances equal at 6 random 128-axis locations {adv_ok} (e.g. {samples[:3]}) {'OK' if ok else 'FAIL'}")
print("RESULT:", "PASS" if not fail else f"FAIL ({fail})")
sys.exit(1 if fail else 0)
