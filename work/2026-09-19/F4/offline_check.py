"""F4 offline witness for bundles/combined vs bundles/combined-pre.
(a) KV bank structure: 26 latched fields/slot, 208-name base list, write rules concatenate the 12 head lists, alias rules, glyph
    rules read the packed lists in per-head fonts, live lists carry head tags; (b) 24 retagged fonts vs v2 sources (fvar tags/ranges,
    protected tables byte-identical, URLs resolve); (c) head input: 2 latches, --hq expressions == head.css expression, both head lists
    replaced, wall exempts --head-fvs; (d) selector-level diff combined-pre -> combined limited to the intended rules; (e) witnesses."""
import hashlib, json, re, sys
from collections import Counter
from pathlib import Path
from fontTools.ttLib import TTFont
sys.path.insert(0, "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F4/tools")
from f4_packing import head_axis
W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
R = Path("/Users/shubhampatil/Documents/programming/gpt2-css")
C = (W / "bundles/combined/runtime.css").read_text(); P = (W / "bundles/combined-pre/runtime.css").read_text()
HC = (W / "bundles/combined/index.html").read_text(); HP = (W / "bundles/combined-pre/index.html").read_text()
fail = []
def check(cond, *msg):
    if not cond: fail.append(msg)
HEADS, DIM, CAP, BLOCKS = 12, 64, 8, 12
# ---------------- (a) banks
base = re.search(r'\.fvs-bank\{transition-property:([^;]+);', C)[1].split(",")
check(len(base) == 26 * CAP, "base list", len(base))
expected_fields = []
for s in range(CAP):
    expected_fields += [f"--fc-k-{s}", f"--fc-v-{s}"] + [f"--fc-{k}-{s}-{h}" for h in range(HEADS) for k in ("ks", "vs")]
check(base == expected_fields, "base list order")
base_pre = re.search(r'\.fvs-bank\{transition-property:([^;]+);', P)[1].split(",")
check(len(base_pre) == 48 * CAP, "pre base list", len(base_pre))
props = Counter(re.findall(r'@property (--f[cr]-\w+-\d+(?:-\d+)?)\{syntax:"(\*|<number>)";inherits:(true|false);initial-value:', C))
check(sum(props.values()) == 2 * 26 * CAP, "fc/fr registrations", sum(props.values()))
for s in range(CAP):
    for kind in ("k", "v"):
        for alias, inh in (("fc", "false"), ("fr", "true")):
            check(props[(f"--{alias}-{kind}-{s}", "*", inh)] == 1, "vector reg", alias, kind, s)
            m = re.search(rf'@property --{alias}-{kind}-{s}\{{syntax:"\*";inherits:{inh};initial-value:([^}}]+)\}}', C)
            check(m and m[1] == ",".join(f'"{head_axis(kind, h, i)}" 0' for h in range(HEADS) for i in range(DIM)), "zero list", alias, kind, s)
# write rules: per (layer, slot)
writes = re.findall(r'@container corestate style\(--layer:(\d+)\)\{@container fvscache style\(--fvs-write-slot:(\d+)\)\{\.fvs-bank-\1\{transition-property:([^;]+);([^}]+)\}\}\}', C)
check(len(writes) == BLOCKS * CAP, "write rules", len(writes))
for layer, slot, retained, decls in writes:
    s = int(slot); ret = retained.split(",")
    check(len(ret) == 26 * (CAP - 1) and not any(f"-{s}" == n[len(f"--fc-k"):] or n in expected_fields[26*s:26*s+26] for n in ret), "retained", layer, slot, len(ret))
    d = dict(x.split(":", 1) for x in decls.split(";"))
    check(len(d) == 26, "write decl count", layer, slot, len(d))
    for kind in ("k", "v"):
        check(d.get(f"--fc-{kind}-{s}") == ",".join(f"var(--fvs-live-{kind}-{h})" for h in range(HEADS)), "packed write", layer, slot, kind)
    for h in range(HEADS):
        for kind in ("ks", "vs"):
            check(d.get(f"--fc-{kind}-{s}-{h}") == f"var(--fvs-live-{kind}-{h})", "scale write", layer, slot, h, kind)
# alias rules (F5 filled): per (layer, slot) 26*(slot+1) aliases
aliases = re.findall(r'@container corestate style\(--layer:(\d+)\)\{@container fvscache style\(--fvs-write-slot:(\d+)\)\{\.fvs-bank-\1\{(--fr-[^}]+)\}\}\}', C)
check(len(aliases) == BLOCKS * CAP, "alias rules", len(aliases))
for layer, slot, decls in aliases:
    d = decls.split(";"); s = int(slot)
    check(len(d) == 26 * (s + 1), "alias count", layer, slot, len(d))
    check(all(x == f"{n.replace('--fc-', '--fr-')}:var({n})" for x, n in zip(d, expected_fields[: 26 * (s + 1)])), "alias content", layer, slot)
# live lists on .fvs-query
for h in range(HEADS):
    for kind, off in (("k", 768), ("v", 1536)):
        m = re.search(rf'--fvs-live-{kind}-{h}:([^;}}]+)', C)
        quot = lambda i: f'calc(var(--qkv-{off + h*DIM + i:03d}) / var(--fvs-live-{kind}s-{h}))'
        numeric = "f4NumericLists" in open(W / "bundles/combined/manifest.json").read() and '"f4NumericLists": true' in open(W / "bundles/combined/manifest.json").read()
        exp = ",".join(f'"{head_axis(kind, h, i)}" ' + (f"var(--fvn-{kind}-{h}-{i})" if numeric else quot(i)) for i in range(DIM))
        check(m and m[1] == exp, "live list", kind, h)
        if numeric:
            decl = re.search(rf'\.fvs-query\{{(--fvn-{kind}-{h}-0:[^}}]+)\}}', C)
            check(decl and decl[1] == ";".join(f"--fvn-{kind}-{h}-{i}:{quot(i)}" for i in range(DIM)), "fvn decls", kind, h)
            check(len(re.findall(rf'@property --fvn-{kind}-{h}-\d+\{{syntax:"<number>";inherits:false;initial-value:0\}}', C)) == DIM, "fvn regs", kind, h)
        mp = re.search(rf'--fvs-live-{kind}-{h}:([^;}}]+)', P)
        exp_pre = ",".join(f'"K{i:03d}" {quot(i)}' for i in range(DIM))
        check(mp and mp[1] == exp_pre, "live list in combined-pre", kind, h)
# glyph rules
for h in range(HEADS):
    for s in range(CAP):
        sc = re.search(rf'\.fvs-score-{h}-{s}\{{([^}}]+)\}}', C)[1]; scp = re.search(rf'\.fvs-score-{h}-{s}\{{([^}}]+)\}}', P)[1]
        check(sc == scp.replace("FvsDot", f"FvsDot{h}").replace(f"var(--fr-k-{s}-{h})", f"var(--fr-k-{s})"), "score rule", h, s)
        vg = re.search(rf'\.fvs-v-{h}-{s}\{{([^}}]+)\}}', C)[1]; vgp = re.search(rf'\.fvs-v-{h}-{s}\{{([^}}]+)\}}', P)[1]
        check(vg == f"font-family:FvsValue{h};" + vgp.replace(f"var(--fr-v-{s}-{h})", f"var(--fr-v-{s})"), "value glyph rule", h, s, vg[:80])
check(re.search(r'\.fvs-value-row\{[^}]*font:1024px FvsValue0;', C), "row family")
check(len(re.findall(r'var\(--fr-[kv]-\d+-\d+\)', C)) == 0 and len(re.findall(r'--fc-[kv]-\d+-\d+', C)) == 0, "no unpacked vector names remain")
na = len(fail); print("(a) banks:", "FAIL" if fail else "ok")
# ---------------- (b) fonts
faces = re.findall(r'@font-face\{font-family:(Fvs(Dot|Value)(\d+));src:url\("([^"]+)"\)', C)
check(len(faces) == 24, "font faces", len(faces))
src = {"Dot": R / "experiments/browser-gpt2/font-vector-operators-v2/dot.woff2", "Value": R / "experiments/browser-gpt2/font-vector-operators-v2/value.woff2"}
for fam, kind, h, url in faces:
    h = int(h); url = url.split("?")[0]
    path = (W / "bundles/combined" / url).resolve()
    check(path.exists() and str(path).startswith(str(W / "F4/assets")), "font path", fam, url)
    if not path.exists(): continue
    g, o = TTFont(path, lazy=True), TTFont(src[kind], lazy=True)
    otags = [a.axisTag for a in o["fvar"].axes]; tags = [a.axisTag for a in g["fvar"].axes]
    exp = [head_axis("k" if kind == "Dot" else "v", h, int(t[1:])) if t.startswith("K") else t for t in otags]
    check(tags == exp and len(tags) == (128 if kind == "Dot" else 65), "fvar tags", fam, tags[:3])
    check([(a.minValue, a.defaultValue, a.maxValue) for a in g["fvar"].axes] == [(a.minValue, a.defaultValue, a.maxValue) for a in o["fvar"].axes], "fvar ranges", fam)
    for tbl in ("HVAR", "hmtx", "cmap", "glyf", "loca", "maxp", "hhea"):
        check(g.getTableData(tbl) == o.getTableData(tbl), "table", fam, tbl)
    check(hashlib.sha256(src[kind].read_bytes()).hexdigest()[:16] in path.name, "source digest in name", fam)
print("(b) 24 retagged fonts vs v2 sources:", "FAIL" if len(fail) > na else "ok"); na = len(fail)
# ---------------- (c) head
bank = re.search(r'\.head-input-bank\{(--hq-0:[^}]+)\}', C)
check(bank, "head bank rule")
if bank:
    d = bank[1].split(";")
    hq = [x for x in d if x.startswith("--hq-")]
    check(len(hq) == 768 and all(x == f"--hq-{i}:round(nearest,calc(var(--final-h-{i:03d})/266.248396912*16384),1)" for i, x in enumerate(hq)), "hq decls")
    fvs = [x for x in d if x.startswith("--head-fvs:")]
    check(len(fvs) == 1, "head-fvs decl")
    head_css_src = (R / "experiments/browser-gpt2/head-two-pass/head.css").read_text()
    orig = re.search(r'\.full-head\{[^}]*font-variation-settings:([^;}]+)', head_css_src)[1]
    entries = re.findall(r'"(X[0-9A-Z]{3})" round\(nearest,calc\(var\(--h(\d+)\)/266\.248396912\*16384\),1\)', orig)
    check(len(entries) == 768 and fvs and fvs[0] == "--head-fvs:" + ",".join(f'"{t}" var(--hq-{i})' for t, i in entries), "head list tags")
    check("transition-property:--head-fvs,--head-input-epoch" in bank[1] and "allow-discrete" in bank[1], "head transition")
check(len(re.findall(r'font-variation-settings:var\(--head-fvs\)', C)) == 2, "head lists replaced", len(re.findall(r'font-variation-settings:var\(--head-fvs\)', C)))
check(len(re.findall(r'var\(--h\d+\)', C)) == 0, "no var(--hN) left", len(re.findall(r'var\(--h\d+\)', C)))
wall = re.search(r'\.head-isolation\{([^}]+)\}', C)[1]
check("--head-fvs:initial" not in wall and "--hq-" not in wall and "--h0:initial" not in wall and "--fvn-" not in wall, "wall exemptions")
check(re.search(r'@property --head-fvs\{syntax:"\*";inherits:true;', C), "head-fvs reg")
check(len(re.findall(r'@property --hq-\d+\{syntax:"<number>";inherits:false;', C)) == 768, "hq regs")
# latch totals
def latch_names(css):
    """selector tail -> listed transition-property names, for every rule body containing 86400s (find-based, linear)."""
    out = Counter(); i = 0
    while True:
        j = css.find("86400s", i)
        if j < 0: break
        b0 = css.rfind("{", 0, j); b1 = css.find("}", j); s0 = max(css.rfind("}", 0, b0), css.rfind("{", 0, b0))
        body = css[b0 + 1:b1]; tp = re.search(r'transition-property:([^;}]+)', body)
        out[css[s0 + 1:b0].strip()[-60:]] = len(tp[1].split(",")) if tp else 0
        i = b1
    return out
print("(c) head:", "FAIL" if len(fail) > na else "ok"); na = len(fail)
print("    86400s rules (selector tail -> listed names) combined:", dict(latch_names(C)))
print("    86400s rules combined-pre:", dict(latch_names(P)))
# ---------------- (d) selector-level diff
def inner_rules(css):
    res = {}; ctx = []; i = 0; n = len(css)
    while True:
        j = css.find("{", i)
        if j < 0: break
        k = css.find("}", j + 1)
        sel = css[i:j].strip().lstrip("}").strip()
        j2 = css.find("{", j + 1)
        if j2 != -1 and j2 < k:
            ctx.append(sel); i = j + 1; continue
        res.setdefault(" / ".join(ctx + [sel]), []).append(css[j + 1:k])
        i = k + 1
        while i < n and css[i] == "}":
            if ctx: ctx.pop()
            i += 1
    return res
rp, rc = inner_rules(P), inner_rules(C)
only_p = sorted(set(rp) - set(rc)); only_c = sorted(set(rc) - set(rp)); changed = sorted(k for k in set(rp) & set(rc) if rp[k] != rc[k])
short = lambda keys: dict(Counter(re.sub(r'\d+', 'N', k) for k in keys))
print("(d) rules only in combined-pre:", short(only_p)); print("(d) rules only in combined:", short(only_c)); print("(d) rules changed:", short(changed))
print("(d) rule counts", len(rp), len(rc), "| html elements", HP.count("<i"), HC.count("<i"), "| html identical:", HP == HC)
# ---------------- (e) witnesses
wc = json.load(open(W / "bundles/combined/font-witnesses.json")); wp = json.load(open(W / "bundles/combined-pre/font-witnesses.json"))
common = set(wc) & set(wp)
check(all(wc[k] == wp[k] for k in common), "common witnesses equal")
print(f"(e) witnesses: combined {len(wc)} (pre {len(wp)}), common {len(common)} equal={all(wc[k] == wp[k] for k in common)}, new:", sorted(Path(k).name for k in set(wc) - set(wp))[:3], "... removed:", sorted(Path(k).name for k in set(wp) - set(wc)))
print("bytes: css", len(P), "->", len(C), "| html", len(HP), "->", len(HC))
json.dump({"fail": fail}, open(W / "F4/offline_check.json", "w"))
print("FAILURE KINDS:", dict(Counter(f[0] for f in fail))); print("FAILURES (first 10):", fail[:10] if fail else "none")
