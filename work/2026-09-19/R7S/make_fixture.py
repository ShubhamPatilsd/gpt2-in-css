#!/usr/bin/env python3
"""R7S: derive the sampling head fixture from experiments/browser-gpt2/head-two-pass (no repo edits).
Adds a 7th glyph (U+80000+token, the noise font) to every .head-row and to every fine-row glyph string,
appends the NoiseQ family and the "SEED"/"TEMP" axes to both font lists, registers --noise-col/--temp.
"""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC = ROOT / "experiments/browser-gpt2/head-two-pass"
OUT = HERE / "head-sample"
meta = json.loads((OUT / "expected.json").read_text())
size_adjust = meta["sizeAdjustPercent"]
font_url = (HERE / "noise" / meta["font"]).resolve().as_uri()

html = (SRC / "index.html").read_text()
css = (SRC / "head.css").read_text()

# 1. rows: append the noise code point
def row_sub(m):
    token = int(m.group(1)); glyphs = m.group(3)
    assert len(glyphs) == 6 and ord(glyphs[0]) - 0x20000 == token, (token, glyphs)
    return f'{m.group(0)[:-len(glyphs)-4]}{glyphs}{chr(0x80000 + token)}</i>'
pat_row = re.compile(r'<i class="head-row" data-token="(\d+)" style="([^"]*)">([^<]*)</i>')
html, n_rows = pat_row.subn(row_sub, html)
assert n_rows == 50257, n_rows

# 2. fine-row glyph strings inside if(): "6 chars" -> "7 chars"
pat_str = re.compile('"([\U00020000-\U0002FFFF][\U00030000-\U0003FFFF][\U00040000-\U0004FFFF][\U00050000-\U0005FFFF][\U00060000-\U0006FFFF][\U00070000-\U0007FFFF])"')
def str_sub(m):
    token = ord(m.group(1)[0]) - 0x20000
    return f'"{m.group(1)}{chr(0x80000 + token)}"'
css, n_str = pat_str.subn(str_sub, css)
assert n_str == 50257, n_str

# 3. font family lists + axes
fam_old = "font:62.5px ProdQ16H0,ProdQ16R0,ProdQ16H1,ProdQ16R1,ProdQ16H2,ProdQ16R2"
assert css.count(fam_old) == 2
css = css.replace(fam_old, fam_old + ",NoiseQ")
# the two identical 768-axis lists end with the X2FF entry
pat_fvs = re.compile(r'("X0LB" round\(nearest,calc\(var\(--h767\)/266\.248396912\*16384\),1\))')
css, n_fvs = pat_fvs.subn(r'\1,"SEED" var(--noise-col),"TEMP" var(--temp)', css)
assert n_fvs == 2, n_fvs

# 4. face + properties (prepended)
face = (f'@font-face{{font-family:NoiseQ;src:url("{font_url}") format("truetype");size-adjust:{size_adjust:.9f}%}}'
        '@property --noise-col{syntax:"<number>";inherits:true;initial-value:0}'
        '@property --temp{syntax:"<number>";inherits:true;initial-value:0}')
css = face + css
# the page: keep CSP (harness evaluates via CDP), re-point to local head.css
(OUT / "head.css").write_text(css)
(OUT / "index.html").write_text(html)
print({"rows": n_rows, "fineStrings": n_str, "fvsLists": n_fvs, "cssBytes": len(css.encode()), "htmlBytes": len(html.encode())})
