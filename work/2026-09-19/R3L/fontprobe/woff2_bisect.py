"""Build WOFF2 variants of loop-carrier font 0 to bisect what Chrome's WOFF2 decoder rejects."""
import sys, shutil
from pathlib import Path
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.ttLib.woff2 import WOFF2FlavorData
from fontTools.ttLib.tables._g_l_y_f import Glyph
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_matrix_backend_prototypes as bm
out = Path(__file__).resolve().parents[1] / "fontprobe-bundle"
PER = 128; DELTA = 16384
tags = [t for i in range(PER) for t in (f"H{i:03X}", f"L{i:03X}")]
weights = np.zeros((2 * PER + 1, 2 * PER), dtype=np.int16)
for g in range(2 * PER): weights[g, g] = DELTA
ttf = out / "A.ttf"
bm.build_direct_font_backend(weights, ttf, base_advance=16384, axis_tags=tags)   # writes A.ttf + A.woff2 (builder's own)
def save(font, name, woff2=True, notrans=False):
    if woff2:
        font.flavor = "woff2"
        if notrans:
            font.flavorData = WOFF2FlavorData(); font.flavorData.transformedTables = set()
    else:
        font.flavor = None
    font.save(out / name)
f = TTFont(ttf, recalcTimestamp=False); save(f, "B.woff2")                       # plain re-save
f = TTFont(ttf, recalcTimestamp=False); f["head"].unitsPerEm = 256; save(f, "C.woff2")
f = TTFont(ttf, recalcTimestamp=False); f["head"].unitsPerEm = 256
for a in f["fvar"].axes: a.maxValue = 16384
save(f, "D.woff2")
f = TTFont(ttf, recalcTimestamp=False); f["head"].unitsPerEm = 256
for a in f["fvar"].axes: a.maxValue = 16384
for n in f.getGlyphOrder()[1:1 + 2 * PER]: f["hmtx"][n] = (0, f["hmtx"][n][1])
save(f, "E.woff2")
f = TTFont(ttf, recalcTimestamp=False); f["head"].unitsPerEm = 256
for a in f["fvar"].axes: a.maxValue = 16384
for n in f.getGlyphOrder()[1:1 + 2 * PER]: f["hmtx"][n] = (0, f["hmtx"][n][1])
for n in f.getGlyphOrder(): f["glyf"][n] = Glyph(); f["hmtx"][n] = (f["hmtx"][n][0], 0)
f["head"].xMin = f["head"].yMin = f["head"].xMax = f["head"].yMax = 0
save(f, "F.woff2", notrans=True)
f = TTFont(ttf, recalcTimestamp=False); f["head"].unitsPerEm = 256
for a in f["fvar"].axes: a.maxValue = 16384
for n in f.getGlyphOrder()[1:1 + 2 * PER]: f["hmtx"][n] = (0, f["hmtx"][n][1])
save(f, "G.ttf", woff2=False)
f = TTFont(ttf, recalcTimestamp=False); f["head"].unitsPerEm = 256
for a in f["fvar"].axes: a.maxValue = 16384
for n in f.getGlyphOrder()[1:1 + 2 * PER]: f["hmtx"][n] = (0, f["hmtx"][n][1])
save(f, "H.woff2", notrans=True)                                                   # E without transforms
faces = {"A": "A.woff2", "B": "B.woff2", "C": "C.woff2", "D": "D.woff2", "E": "E.woff2", "F": "F.woff2", "G": "G.ttf", "H": "H.woff2"}
css = "".join(f'@font-face{{font-family:V{k};src:url("{v}") format("{"truetype" if v.endswith("ttf") else "woff2"}")}}' for k, v in faces.items())
css += "i{position:fixed;top:-9000px;left:0;width:max-content;height:1px;white-space:pre;line-height:1;font-kerning:none;font-size:4px}"
html = "".join(f'<i id="w{k}" style="font-family:V{k}">&#xE100;</i><i id="v{k}" style="font-family:V{k};font-variation-settings:\'H000\' 1000">&#xE000;</i>' for k in faces)
(out / "runtime.css").write_text(css)
(out / "index.html").write_text('<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="runtime.css">' + html)
print("variants:", {k: (out / v).stat().st_size for k, v in faces.items()})
