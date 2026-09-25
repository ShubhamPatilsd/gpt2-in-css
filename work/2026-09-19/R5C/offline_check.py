"""R5C offline check: bundles/<name> (R5C_CTX_CHAIN on) vs bundles/<ref> (same tools, flag off, e.g. combined7).
usage: python offline_check.py <bundle> <reference-bundle>"""
import json, re, sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
name, ref = sys.argv[1], sys.argv[2]
B, R = W / "bundles" / name, W / "bundles" / ref
C, P = (B / "runtime.css").read_text(), (R / "runtime.css").read_text()
H, Q = (B / "index.html").read_text(), (R / "index.html").read_text()
man = json.loads((B / "manifest.json").read_text())
L, cap = man["blocks"], man["capacity"]
NW, SH, SHARDS = 768, 256, 3
LEVELS = SH // 2
fail = []
def check(cond, *msg):
    if not cond: fail.append(msg)
def rules(css):
    css = re.sub(r"@(?:font-face)\b[^{}]*\{[^{}]*\}", "", css)
    out = Counter(); buf, stack, quote = "", [], None
    for ch in css:
        if quote:
            buf += ch
            if ch == quote: quote = None
        elif ch in "\"'": quote = ch; buf += ch
        elif ch == "{": stack.append(buf.strip()); buf = ""
        elif ch == "}":
            if buf.strip(): out[(" ".join(stack), buf.strip())] += 1
            buf = ""; stack.pop()
        else: buf += ch
    return out
rc, rp = rules(C), rules(P)
added, removed = rc - rp, rp - rc
cats = Counter()
SWAP = re.compile(r"\((\d+) \* var\((--attnp-\d{3})\) / \(1 - var\(\2\)\)\)")
def norm_decode(body):
    return SWAP.sub(lambda m: f"({m[1]} / var({m[2]}) - {m[1]})", body)
def cat_added(sel, body):
    last = sel.split()[-1]
    if last in (".r5c-ctx-stage", ".r5c-ctx-a", ".r5c-x", ".r5c-xb", ".r5c-gs", ".r5c-g", ".r5c-sums", ".r5c-sum>.track"): return "chain/stage structure"
    if re.fullmatch(r"#r5c-x[0-2]-\d+", last) and body.startswith("width:anchor-size(--r5ca-"): return "container size = anchors"
    if re.fullmatch(r"#r5c-x[0-2]-\d+", last) and "100cqw / 1px - 262144" in body and "100cqh / 1px - 262144" in body: return "publisher (cq units -> --ctx)"
    if re.fullmatch(r"\.r5c-xb[0-2]", last) and "100cqw / 1px - 262144" in body and "--fq-attn-" in body and "font-variation-settings:" in body: return "chain bottom (last two ctx + quotients + shard list)"
    if re.fullmatch(r"\.r5c-xb[0-2]", last) and re.fullmatch(r"font-family:b\d+attnS[0-2]", body): return "per-layer shard family on the bottom"
    if last == ".metric" and ".r5c-sum" in sel and re.fullmatch(r"width:\d+px", body): return "per-layer subject width V"
    if last in (".r5c-mark", ".r5c-mark>.track") and re.fullmatch(r"width:\d+px", body): return "per-layer marker scroller V / 3V"
    if last == ".fvs-score-reader" and body.startswith("--range-attn:calc((max(.000001,var(--fb-0)"): return "--range-attn bound on the softmax element"
    if re.fullmatch(r"\.shared-attn-c\d+", last) and "animation-timeline" in body and "--attnp-" in body: return "attn reader (swapped decode)"
    if last.startswith("html") and "timeline-scope" in body: return "html timeline-scope (bridge names removed)"
    if "--native-pass:" in body and ".fvs-score-reader" in sel and ".cache-bridge-receipt" not in sel: return "pass-reader list without .cache-bridge-receipt"
    if last.startswith(".pass-reader,") or (sel.startswith(".pass-reader,") and body == "--epoch:var(--native-pass)" and ".cache-bridge-receipt" not in sel): return "epoch receipt list without .cache-bridge-receipt"
    return "UNEXPECTED ADDED " + sel[:100] + " | " + body[:120]
def cat_removed(sel, body):
    last = sel.split()[-1]
    if last in (".cache-bridge-source", ".cache-bridge-source>.track"): return "bridge scroller"
    if re.fullmatch(r"\.cache-bridge-c\d+", last): return "bridge readers"
    if "--native-pass:" in body and ".cache-bridge-receipt" in sel: return "pass-reader list with .cache-bridge-receipt"
    if sel.startswith(".pass-reader,") and body == "--epoch:var(--native-pass)" and ".cache-bridge-receipt" in sel: return "epoch receipt list with .cache-bridge-receipt"
    if last.startswith(".cache-bridge-receipt") or ".cache-bridge-gate" in last or "cache-bridge" in sel: return "bridge receipt/gate"
    if last == ".shared-attn" and body.startswith("font-family:") and "font-variation-settings:" in body: return "attn stage 768-axis list"
    if last == ".shared-attn" and body.startswith("--range-attn:calc(max(.000001,abs(var(--ctx-"): return "attn dynamic range max|ctx|"
    if last == ".shared-attn" and body.startswith("--fq-attn-000:calc(var(--ctx-000)"): return "attn hoisted quotients (lifted once)"
    if last in (".shared-attn>.scroller", ".shared-attn>.scroller>.track"): return "attn stage scroller V / 3V"
    if re.fullmatch(r"\.shared-attn-c\d+", last) and "animation-timeline" in body and "--attnp-" in body: return "attn reader (old decode)"
    if last.startswith("html") and "timeline-scope" in body: return "html timeline-scope (old)"
    if "--native-pass:" in body and ".cache-bridge-receipt" in sel: return "pass-reader list with .cache-bridge-receipt"
    if sel.startswith(".pass-reader,") and body == "--epoch:var(--native-pass)" and ".cache-bridge-receipt" in sel: return "epoch receipt list with .cache-bridge-receipt"
    return "UNEXPECTED REMOVED " + sel[:100] + " | " + body[:120]
for (sel, body), n in added.items(): cats["+ " + cat_added(sel, body)] += n
for (sel, body), n in removed.items(): cats["- " + cat_removed(sel, body)] += n
for k, v in sorted(cats.items()): print(f"{v:6d}  {k}")
check(not any("UNEXPECTED" in k for k in cats), "unexpected rule categories")
check(cats["+ container size = anchors"] == SHARDS * LEVELS, "container size rules", cats["+ container size = anchors"])
check(cats["+ publisher (cq units -> --ctx)"] == SHARDS * (LEVELS - 1), "publisher rules", cats["+ publisher (cq units -> --ctx)"])
check(cats["+ chain bottom (last two ctx + quotients + shard list)"] == SHARDS, "bottom rules")
check(cats["+ per-layer shard family on the bottom"] == SHARDS * L, "family rules", cats["+ per-layer shard family on the bottom"])
check(cats["+ per-layer subject width V"] == L and cats["+ per-layer marker scroller V / 3V"] == 2 * L, "V rules")
check(cats["+ --range-attn bound on the softmax element"] == 1, "range rule")
check(cats["+ attn reader (swapped decode)"] == cats["- attn reader (old decode)"] > 0, "reader rule counts")
check(cats["- bridge readers"] == 12 and cats["- attn stage 768-axis list"] == L and cats["- attn dynamic range max|ctx|"] == L, "removed counts", cats["- bridge readers"], cats["- attn stage 768-axis list"], cats["- attn dynamic range max|ctx|"])
# exact anchor -> container -> publisher mapping
for s in range(SHARDS):
    for k in range(LEVELS):
        i0, i1 = SH * s + 2 * k, SH * s + 2 * k + 1
        check((f"#r5c-x{s}-{k}", f"width:anchor-size(--r5ca-{i0:03d} width);height:anchor-size(--r5ca-{i1:03d} width)") in rc, "size rule", s, k)
        if k:
            check((f"#r5c-x{s}-{k}", f"--ctx-{i0 - 2:03d}:calc((100cqw / 1px - 262144) / 128);--ctx-{i1 - 2:03d}:calc((100cqh / 1px - 262144) / 128)") in rc, "publisher rule", s, k)
    bottoms = [b for (q, b) in rc if q == f".r5c-xb{s}" and "--fq-attn-" in b]
    check(len(bottoms) == 1, "one bottom rule", s)
    bt = bottoms[0]
    check(bt.startswith(f"--ctx-{SH*(s+1)-2:03d}:calc((100cqw / 1px - 262144) / 128);--ctx-{SH*(s+1)-1:03d}:calc((100cqh / 1px - 262144) / 128);"), "bottom publishes last two", s)
    letter = "ABC"[s]
    for j in range(SH):
        i = SH * s + j
        check(f"--fq-attn-{i:03d}:calc(var(--ctx-{i:03d}) / var(--range-attn))" in bt, "quotient", i)
        check(f'"{letter}{j:03d}" var(--fq-attn-{i:03d})' in bt, "axis entry", i)
    check(bt.count("--fq-attn-") == 2 * SH and bt.count('"') == 2 * SH, "bottom has exactly its 256 axes", s)
# reader decode: identical to the reference after swapping the width term
old = {(q, norm_decode(b)) for (q, b) in rp if re.fullmatch(r"\.shared-attn-c\d+", q) and "--attnp-" in b}
new = {(q, norm_decode(b)) for (q, b) in rc if re.fullmatch(r"\.shared-attn-c\d+", q) and "--attnp-" in b}
check(old == new, "reader decode equal modulo width term", len(old), len(new), len(old ^ new))
check(all("/ (1 - var(" in b for (q, b) in rc if re.fullmatch(r"\.shared-attn-c\d+", q) and "--attnp-" in b), "new decode uses p/(1-p)")
# the V-row width rules and the softmax are untouched
for h in range(12):
    for s in range(cap):
        sel = f".fvs-v-{h}-{s}"
        check({b for (q, b) in rc if q == sel} == {b for (q, b) in rp if q == sel}, "V glyph rule identical", sel)
soft_on = sorted(b for (q, b) in rc if q == ".fvs-score-reader" and "--fm-0" in b); soft_ref = sorted(b for (q, b) in rp if q == ".fvs-score-reader" and "--fm-0" in b)
check(soft_on == soft_ref and len(soft_on) == 1, "softmax rule identical")
for tok in ("cache-bridge", "abs(var(--ctx-", ".shared-attn{font-family:"):
    check(tok not in C, "leftover in css", tok)
faces_on = re.findall(r"@font-face\{[^{}]*\}", C); faces_ref = re.findall(r"@font-face\{[^{}]*\}", P)
check(faces_on == faces_ref, "font-face rules identical", len(faces_on), len(faces_ref))
scope = re.findall(r"html\{timeline-scope:([^}]+)\}", C); scope_ref = re.findall(r"html\{timeline-scope:([^}]+)\}", P)
delta = set(scope_ref[-1].split(",")) - set(scope[-1].split(","))
check(delta == {f"--cache-bridge-t{i}" for i in range(NW)} | {"--cache-bridge-stamp"} and set(scope[-1].split(",")) <= set(scope_ref[-1].split(",")), "html scope delta = bridge names", len(delta))
# html
for tok in ("cache-bridge", "{child}", 'class="metric fvs-value-row"', "view-timeline:--r5ca-"):
    check(tok not in H, "leftover in html", tok)
check(H.count("anchor-name:--r5ca-") == NW and H.count('<span class="fvs-value-row r5c-ctx-a" style="anchor-name:--r5ca-') == NW, "V anchors", H.count("anchor-name:--r5ca-"))
check(H.count('class="r5c-x"') == SHARDS * LEVELS, "containers", H.count('class="r5c-x"'))
check(H.count('class="scroller r5c-sum"') == NW and H.count('class="scroller r5c-mark"') == 1, "sum/marker scrollers")
check(Q.count("view-timeline:") - H.count("view-timeline:") == NW + 1, "view-timeline delta", Q.count("view-timeline:") - H.count("view-timeline:"))
check(H.count('<div class="r5c-ctx-stage">') == 1 and H.count('<div class="fvs-score-reader"><div class="fvs-softmax"><div class="r5c-ctx-stage">') == 1, "reader>softmax>stage")
for i in range(NW):
    total = " + ".join(f"anchor-size(--r5cg-{s}-{i:03d} width)" for s in range(SHARDS))
    check(f'<div class="scroller r5c-sum" style="width:calc({total})"><div class="track"><i class="metric" style="view-timeline:--shared-attn-t{i} inline"></i></div></div>' in H, "sum carrier", i)
    for s in range(SHARDS):
        check(f'<i class="r5c-g" style="anchor-name:--r5cg-{s}-{i:03d}">&#x{0xF0000 + s * NW + i:X};</i>' in H, "glyph row", s, i)
check(H.count("anchor-name:--r5cg-") == SHARDS * NW, "glyph anchors")
check('<div class="scroller r5c-mark"><div class="track"><i class="metric pass-reader" style="width:calc(var(--markerbase-attn) + var(--epoch) * 1024px);view-timeline:--shared-attn-generation inline"></i></div></div>' in H, "marker carrier")
# tree order and nesting
stage_pos = H.find('<div class="r5c-ctx-stage">'); x00 = H.find('id="r5c-x0-0"'); attn = H.find('<div class="shared-attn">')
check(0 < stage_pos < x00 < attn, "stage < chains < attn stage")
check(all(H.find(f"anchor-name:--r5ca-{i:03d}") < x00 for i in range(NW)), "all V anchors precede the chains")
for s in range(SHARDS):
    for k in range(LEVELS - 1):
        check(H.find(f'id="r5c-x{s}-{k}"') < H.find(f'id="r5c-x{s}-{k + 1}"'), "chain order", s, k)
    check(H.find(f'id="r5c-x{s}-{LEVELS - 1}"') < H.find(f'class="r5c-xb r5c-xb{s}"'), "bottom after last container", s)
    check(H.find(f'class="r5c-xb r5c-xb{s}"') < H.find(f"anchor-name:--r5cg-{s}-000") < H.find(f"anchor-name:--r5cg-{s}-767") < attn, "glyph stage before attn stage", s)
check(H.find('class="r5c-xb r5c-xb2"') < attn, "attn stage inside/after bottom 2")
check(H.count('<div class="shared-attn">') == 1, "one attn stage")
VOID = {"meta", "link", "input", "br", "img", "hr", "source"}
class Pz(HTMLParser):
    def __init__(s): super().__init__(); s.stack = []; s.maxd = 0; s.n = 0; s.anc = {}; s.marks = {}
    def handle_starttag(s, tag, attrs):
        a = dict(attrs); s.n += 1
        s.stack.append((tag, a.get("class", ""), a.get("id", ""), a.get("style", "")))
        s.maxd = max(s.maxd, len(s.stack))
        key = a.get("id", "")
        cls = a.get("class", "").split()
        for w in ("r5c-x0-0", "r5c-x1-0", "r5c-x2-0"):
            if key == w: s.anc[w] = list(s.stack[:-1])
        if "r5c-sum" in cls and "sum" not in s.anc: s.anc["sum"] = list(s.stack[:-1])
        for w in ("fvs-score-reader", "shared-attn", "r5c-xb2", "reused-output"):
            if w in cls and w not in s.marks: s.marks[w] = len(s.stack)
        if "shared-attn" in cls:
            s.inside_attn = [f for f in s.stack if "r5c-xb2" in f[1].split()]
        if tag in VOID: s.stack.pop()
    def handle_endtag(s, tag):
        for i in range(len(s.stack) - 1, -1, -1):
            if s.stack[i][0] == tag: del s.stack[i:]; break
pa, pb = Pz(), Pz(); pa.feed(H); pb.feed(Q)
print(f"elements bundle/ref: {pa.n} {pb.n} delta {pa.n - pb.n}; max depth {pa.maxd} (ref {pb.maxd}); depths: {pa.marks}")
check(pa.maxd < 512, "depth cap", pa.maxd)
# added: ctx stage, containers, bottoms, glyph stages, glyph rows, sums wrapper, 3 per sum scroller, marker scroller; removed: bridge scroller+track+marker+receipt+gate (5) + 12 readers, attn scroller+track+768 rows+marker
check(pa.n - pb.n == (1 + SHARDS * LEVELS + SHARDS + SHARDS + SHARDS * NW + 1 + 3 * NW + 3) - (5 + 12) - (2 + NW + 1), "element delta", pa.n - pb.n)
check(pa.inside_attn, ".shared-attn is a descendant of .r5c-xb2")
check(pa.marks["shared-attn"] == pa.marks["r5c-xb2"] + 1, "attn stage is a child of bottom 2")
bad_props = ("contain:", "transform:", "filter:", "will-change:", "backdrop-filter:", "perspective:", "position:absolute", "position:relative", "position:sticky")
def compound_tokens(last):
    return set(re.findall(r"[.#][\w-]+", last))
sel_bodies = [(q, b) for (q, b) in rc if any(p in b for p in bad_props)]
for key, anc in pa.anc.items():
    hits = []
    for tag, cls, ident, style in anc:
        toks = [f".{c}" for c in cls.split()] + ([f"#{ident}"] if ident else [])
        for q, b in sel_bodies:
            last = q.split()[-1] if q else ""
            if (set(toks) & compound_tokens(last)) and not last.startswith("@"):
                hits.append((tag, cls, ident, q[-80:], [d for d in b.split(";") if any(p.rstrip(":") in d for p in bad_props)]))
        if any(p in style for p in bad_props): hits.append((tag, cls, ident, "inline", style))
    check(not hits, "ancestor CB lint", key, hits[:3])
    print(f"ancestors of {key} ({len(anc)}):", " > ".join((c or t) + ("#" + i if i else "") for t, c, i, _ in anc)[-400:])
def norm_w(d): return {re.sub(r"^.*?/(experiments|assets|global-projection-assets)/", r"\1/", k): v for k, v in d.items()}
w1, w2 = json.loads((B / "font-witnesses.json").read_text()), json.loads((R / "font-witnesses.json").read_text())
check(norm_w(w1) == norm_w(w2), "font witnesses identical (modulo tools dir)", len(w1), len(w2))
print("witnesses identical:", norm_w(w1) == norm_w(w2), len(w1), "raw identical:", w1 == w2)
print(f"sizes css/html bundle: {len(C)} {len(H)} ref: {len(P)} {len(Q)}")
print("manifest:", {k: v for k, v in man.items() if k.startswith("r5c")})
check(man.get("r5cCtxChain") is True and man.get("r5cCtxChainContainers") == SHARDS * LEVELS, "manifest")
for f in fail: print("FAIL", *f)
print("RESULT:", "PASS" if not fail else f"FAIL ({len(fail)})")
sys.exit(1 if fail else 0)
