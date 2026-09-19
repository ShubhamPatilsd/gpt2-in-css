#!/usr/bin/env python3
"""Make 12 retagged copies of the repo's 256-axis HVAR font (experiments/gpt2-block-css/mlp-proj-s0.ttf).
Copy k: axis tags X{k*256+i:03X} (X000..XBFF over the 12 copies), axis range -16384..16384 (default 0),
cmap U+F0000 + k*768 + i -> glyph y{i:03d} (disjoint per copy so one text run can hit every font of a
12-font stack). Only fvar/cmap/name change; HVAR/hmtx/glyf/gvar bytes untouched (F2's recipe)."""
import os, sys
from fontTools.ttLib import TTFont
SRC = "/Users/shubhampatil/Documents/programming/gpt2-css/experiments/gpt2-block-css/mlp-proj-s0.ttf"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages", "fonts")
os.makedirs(OUT, exist_ok=True)
for k in range(12):
    t = TTFont(SRC)
    axes = t["fvar"].axes
    assert len(axes) == 256
    for i, ax in enumerate(axes):
        ax.axisTag = f"X{k*256+i:03X}"
        ax.minValue, ax.defaultValue, ax.maxValue = -16384.0, 0.0, 16384.0
    # STAT axis tags must match fvar (Chrome ignores STAT for variation, but keep consistent)
    if "STAT" in t:
        stat = t["STAT"].table
        if stat.DesignAxisRecord:
            for i, rec in enumerate(stat.DesignAxisRecord.Axis):
                if i < 256:
                    rec.AxisTag = f"X{k*256+i:03X}"
    for sub in t["cmap"].tables:
        new = {}
        for cp, g in sub.cmap.items():
            i = cp - 0xF0000
            assert 0 <= i < 768, (cp, g)
            new[0xF0000 + k * 768 + i] = g
        sub.cmap = new
    for rec in t["name"].names:
        if rec.nameID in (1, 4, 6):
            rec.string = f"R2B{k}"
    out = os.path.join(OUT, f"r2b-{k}.ttf")
    t.save(out)
    print(out, os.path.getsize(out))
# sanity re-read
t = TTFont(os.path.join(OUT, "r2b-11.ttf"), lazy=True)
print("copy 11 axes", t["fvar"].axes[0].axisTag, t["fvar"].axes[-1].axisTag, t["fvar"].axes[0].maxValue, "cmap min", hex(min(t.getBestCmap())), "HVAR", "HVAR" in t)
