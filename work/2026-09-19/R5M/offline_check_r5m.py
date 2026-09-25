#!/usr/bin/env python3
"""R5M offline check: bundle (R5M_HEAD_LITERAL=1) vs ref (combined7 recipe). Verifies:
(1) runtime.css identical after url-depth normalisation; (2) font-witnesses identical; (3) manifest differs only in r5mHeadLiteral (if present);
(4) index.html identical once every head-row style attribute is removed; (5) every head row's inline width literal equals the ref row's --base
(same data-token order), with the exact two-pass expression, and no head row declares any custom property; (6) counts (50,257 rows).
usage: offline_check_r5m.py <bundle-dir> <ref-dir>"""
import json, re, sys
B, R = sys.argv[1], sys.argv[2]
ok = True
def fail(m):
    global ok; ok = False; print("FAIL:", m)
norm = lambda s: re.sub(r'url\("(?:\.\./)+', 'url("../', s)
cb, cr = open(f"{B}/runtime.css").read(), open(f"{R}/runtime.css").read()
print("runtime.css identical (url-normalised):", norm(cb) == norm(cr)) if norm(cb) == norm(cr) else fail("runtime.css differs")
wb, wr = json.load(open(f"{B}/font-witnesses.json")), json.load(open(f"{R}/font-witnesses.json"))
nk = lambda w: {re.sub(r"^.*?/(experiments|assets|global-projection-assets|data)/", r"\1/", k): {x: y for x, y in v.items() if x != "mtime"} for k, v in w.items()}
print("witnesses identical:", nk(wb) == nk(wr)) if nk(wb) == nk(wr) else fail("witnesses differ")
mb, mr = json.load(open(f"{B}/manifest.json")), json.load(open(f"{R}/manifest.json"))
dk = {k for k in set(mb) | set(mr) if mb.get(k) != mr.get(k)}
print("manifest diff keys:", sorted(dk)) if dk <= {"r5mHeadLiteral"} else fail(f"manifest differs in {sorted(dk)}")
hb, hr = open(f"{B}/index.html").read(), open(f"{R}/index.html").read()
ROW = re.compile(r'<i class="head-row" data-token="(\d+)" style="([^"]*)">')
rows_b, rows_r = ROW.findall(hb), ROW.findall(hr)
print("head rows:", len(rows_b), len(rows_r))
if not (len(rows_b) == len(rows_r) == 50257): fail("row count")
sb, sr = ROW.sub(r'<i class="head-row" data-token="\1">', hb), ROW.sub(r'<i class="head-row" data-token="\1">', hr)
print("index.html identical modulo head-row style attributes:", sb == sr) if sb == sr else fail("index.html differs outside head-row styles")
eff = re.search(r'\.head-row\{width:calc-size\(max-content,round\(nearest,\(size - var\(--base\)\*1px\)\*([\d.]+) \+ ([-\d.]+px),4px\)\)\}', cr)
if not eff: fail("two-pass .head-row width rule not found in ref css")
else:
    factor, offset = eff.group(1), eff.group(2); bad = 0
    for (tb, stb), (tr, strr) in zip(rows_b, rows_r):
        m = re.fullmatch(r'--base:([-\d.]+);--tie:(\d+)', strr); w = re.fullmatch(r'width:calc-size\(max-content,round\(nearest,\(size - ([-\d.]+)px\)\*([\d.]+) \+ ([-\d.]+px),4px\)\)', stb)
        if tb != tr or not m or not w or w.group(1) != m.group(1) or w.group(2) != factor or w.group(3) != offset or '--' in stb: bad += 1
    print(f"row literals == ref --base with factor {factor} offset {offset}: {len(rows_b)-bad}/{len(rows_b)} ok") if not bad else fail(f"{bad} rows mismatch")
    # the tie-bearing rule must be cascade-dominated by the two-pass rule in the ref (later position, same specificity) so --tie is dead
    p_tie = cr.find('.head-row{grid-area:1/1'); p_two = cr.find(eff.group(0))
    print("two-pass rule after tie rule:", p_two > p_tie) if p_two > p_tie else fail("cascade order")
print("script tags:", hb.count("<script"), "| inline style bytes:", sum(len(s) for _, s in rows_b), "vs", sum(len(s) for _, s in rows_r))
print("RESULT:", "PASS" if ok else "FAIL")
