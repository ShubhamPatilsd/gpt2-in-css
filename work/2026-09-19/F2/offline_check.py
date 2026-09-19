"""F2 offline witness: prove the slimmed bundle computes the same operators as baseline.
(a) global proj list: tag X<base36 idx> <-> --hidden-idx, 12 layers; (b) retagged fonts: fvar tags in order,
HVAR/hmtx/cmap/gvar byte-identical to the source shard, avar segments retagged only; ?v= digest matches;
(c) HTML: each shared-proj metric row i holds the 12 shard chars codepoint_start[s]+i; (d) --fw hoist matches the
removed per-glyph calc exactly; (e) selector-level diff baseline vs F2 limited to the intended rules."""
import hashlib, re, sys, json
from pathlib import Path
from html.parser import HTMLParser
from fontTools.ttLib import TTFont
sys.path.insert(0, "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F2/tools")
from build_gpt2_block_css import global_axis_tag
W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
F = (W / "bundles/F2/runtime.css").read_text(); B = (W / "bundles/baseline/runtime.css").read_text()
H = (W / "bundles/F2/index.html").read_text()
fail = []
# ---------------- (a)
lists = re.findall(r'\.shared-proj\{font-family:([^;]+);font-variation-settings:([^}]+)\}', F)
assert len(lists) == 12, len(lists)
for layer, (fam, settings) in enumerate(lists):
    fams = fam.split(",")
    if fams != [f"b{layer}projS{s}" for s in range(12)]: fail.append(("family order", layer, fams[:3]))
    axes = re.findall(r'"(X[0-9A-Z]{3})" calc\(var\(--hidden-(\d{3,4})\) / var\(--range-proj\)\)', settings)
    if len(axes) != 3072 or settings.count('"') != 6144: fail.append(("axis count", layer, len(axes)))
    for i, (tag, idx) in enumerate(axes):
        if int(idx) != i or tag != global_axis_tag(i): fail.append(("axis map", layer, i, tag, idx)); break
na=len(fail); print("(a) global proj lists: 12 layers x 3072 axes checked", "FAIL" if fail else "ok")
# ---------------- (b)
faces = re.findall(r'@font-face\{font-family:(b(\d+)projS(\d+));src:url\("([^"?]+)\?v=([0-9a-f]+)"\) format\("woff2"\);unicode-range:U\+([0-9A-F]+)-([0-9A-F]+)\}', F)
assert len(faces) == 144, len(faces)
srcdirs = {0: Path("/Users/shubhampatil/Documents/programming/gpt2-css/experiments/gpt2-block-css")}
for L in range(1, 12): srcdirs[L] = Path(f"/Users/shubhampatil/Documents/programming/gpt2-css/experiments/gpt2-flat-12block-chain/layer{L:02d}")
checked = 0
for fam, L, s, url, v, lo, hi in faces:
    L, s = int(L), int(s)
    path = (W / "bundles/F2" / url).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest()[:12] != v: fail.append(("digest", fam))
    stem = "mlp-proj-rowbase" if L == 0 else f"b{L}-mlp-proj-rowbase"
    src = srcdirs[L] / f"{stem}-s{s}.woff2"
    if not path.name.startswith(f"{stem}-s{s}-{hashlib.sha256(src.read_bytes()).hexdigest()[:16]}-global-v1"): fail.append(("source name", fam, path.name))
    g, o = TTFont(path, lazy=True), TTFont(src, lazy=True)
    tags = [a.axisTag for a in g["fvar"].axes]; otags = [a.axisTag for a in o["fvar"].axes]
    if tags != [global_axis_tag(s * 256 + i) for i in range(len(tags))] or len(tags) != 256: fail.append(("fvar tags", fam, tags[:2]))
    mapping = dict(zip(otags, tags))
    for tbl in ("HVAR", "hmtx", "cmap", "gvar", "glyf", "loca", "maxp", "hhea"):
        if tbl in o and (tbl not in g or g.getTableData(tbl) != o.getTableData(tbl)): fail.append(("table", fam, tbl))
    for attr in ("unitsPerEm", "flags", "xMin", "yMin", "xMax", "yMax", "indexToLocFormat", "macStyle"):
        if getattr(g["head"], attr) != getattr(o["head"], attr): fail.append(("head", fam, attr))
    if "avar" in o:
        if {mapping[k]: val for k, val in o["avar"].segments.items()} != g["avar"].segments: fail.append(("avar", fam))
    # fvar axis ranges / defaults unchanged
    for a, b_ in zip(g["fvar"].axes, o["fvar"].axes):
        if (a.minValue, a.defaultValue, a.maxValue) != (b_.minValue, b_.defaultValue, b_.maxValue): fail.append(("fvar range", fam))
    cmap = o.getBestCmap(); cps = sorted(cmap)
    if int(lo, 16) != 0xF0000 + s * 768 or int(hi, 16) != int(lo, 16) + 767 or cps[0] != int(lo, 16) or len(cps) != 768: fail.append(("unicode-range", fam, lo, hi, hex(cps[0]), len(cps)))
    checked += 1
print(f"(b) {checked} retagged fonts vs sources", "FAIL" if len(fail)>na else "ok"); na=len(fail)
# ---------------- (c)
m = re.search(r'<div class="shared-proj"><div class="scroller"><div class="track">(.*?)</div></div>', H)
rows = re.findall(r'<i class="metric" style="view-timeline:--shared-proj-t(\d+) inline">([^<]*)</i>', m[1])
if len(rows) != 768: fail.append(("proj rows", len(rows)))
for i, (t, content) in enumerate(rows):
    cps = [int(c, 16) for c in re.findall(r'&#x([0-9A-F]+);', content)]
    if int(t) != i or cps != [0xF0000 + s * 768 + i for s in range(12)]: fail.append(("proj row chars", i, cps[:3])); break
if "shared-proj-pack" in H or "shared-proj-pack" in F: fail.append(("pack remnants",))
print("(c) 768 proj metric rows x 12 shard chars", "FAIL" if len(fail)>na else "ok"); na=len(fail)
# ---------------- (d)
fw = dict(re.findall(r'(--fw-\d+-\d+):(calc\((?:[^()]|\([^()]*\))*\))', F))
glyphF = dict(re.findall(r'\.fvs-v-(\d+-\d+)\{([^}]*)\}', F)); glyphB = dict(re.findall(r'\.fvs-v-(\d+-\d+)\{([^}]*)\}', B))
if len(fw) != 96: fail.append(("fw count", len(fw)))
for h in range(12):
    for s in range(8):
        if fw.get(f"--fw-{h}-{s}") != f"calc(var(--fe-{h}-{s}) * var(--fr-vs-{s}-{h}) / var(--fb-{h}))": fail.append(("fw expr", h, s, fw.get(f"--fw-{h}-{s}")))
        rule = glyphF[f"{h}-{s}"]
        if rule != f'font-variation-settings:var(--fr-v-{s}-{h}),"P000" var(--fw-{h}-{s});flex:none': fail.append(("glyph rule", h, s, rule))
        old = glyphB[f"{h}-{s}"]
        if f'"P000" calc(var(--fe-{h}-{s}) * var(--fr-vs-{s}-{h}) / var(--fb-{h}))' not in old or f"var(--fr-v-{s}-{h})," not in old: fail.append(("baseline glyph", h, s))
reader_decl = re.search(r'\.fvs-score-reader\{(--fw-0-0:[^}]*)\}', F)
if not reader_decl: fail.append(("fw not on reader",))
print("(d) 96 --fw hoists + 96 glyph rules", "FAIL" if len(fail)>na else "ok"); na=len(fail)
# ---------------- (e) selector-level diff
def inner_rules(css):
    """Linear scan: (container-chain / selector) -> [body]. Strings in this sheet contain no braces."""
    res = {}; ctx = []; i = 0; n = len(css)
    while True:
        j = css.find("{", i)
        if j < 0: break
        k = css.find("}", j + 1)
        sel = css[i:j].strip().lstrip("}").strip()
        # nested block if another '{' comes before the next '}'
        j2 = css.find("{", j + 1)
        if j2 != -1 and j2 < k:
            ctx.append(sel); i = j + 1; continue
        res.setdefault(" / ".join(ctx + [sel]), []).append(css[j + 1:k])
        i = k + 1
        # pop closed containers: consecutive '}' after this rule
        while i < n and css[i] == "}":
            if ctx: ctx.pop()
            i += 1
    return res
rb, rf = inner_rules(B), inner_rules(F)
only_b = sorted(set(rb) - set(rf)); only_f = sorted(set(rf) - set(rb)); changed = sorted(k for k in set(rb) & set(rf) if rb[k] != rf[k])
def short(keys):
    from collections import Counter
    return Counter(re.sub(r'\d+', 'N', k) for k in keys)
print("(e) rules only in baseline:", dict(short(only_b)))
print("(e) rules only in F2:", dict(short(only_f)))
print("(e) rules changed:", dict(short(changed)))
print("(e) rule counts", len(rb), len(rf))
json.dump({"fail": fail}, open(W / "F2/offline_check.json", "w"))
from collections import Counter
print("FAILURE KINDS:", dict(Counter(f[0] for f in fail)))
print("FAILURES (first 12):", fail[:12] if fail else "none")
