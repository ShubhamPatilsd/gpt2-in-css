"""R4S offline check: bundles/<name> (R4S_SMALL_HOPS on) vs bundles/<ref> (same tools, flag off).
usage: python offline_check.py <bundle> <reference-bundle> [capacity]"""
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
cap = int(sys.argv[3]) if len(sys.argv) > 3 else man["capacity"]
N, LEVELS = 12 * cap, 12 * cap // 2
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
def cat_added(sel, body):
    if sel.startswith("@property --fs-") and "inherits:true" in body: return "fs registration inherits:true"
    if sel in (".fvs-score-stage", ".fvs-score-a", ".fvs-sc", ".fvs-score-reader") and ("position:fixed" in body or "display:block" in body): return "chain structure"
    if re.fullmatch(r"#fvs-sc\d+", sel) and body.startswith("width:anchor-size(--fsa-"): return "container size = anchors"
    if (re.fullmatch(r"#fvs-sc\d+", sel) or sel == ".fvs-score-reader") and "100cqw / 1px - 262144" in body and "100cqh / 1px - 262144" in body: return "publisher (cq units -> --fs)"
    if sel.startswith("html") and "timeline-scope" in body: return "html timeline-scope (score names removed)"
    if "--native-pass:" in body and ".fvs-score-reader" in sel and ".fvs-score-receipt" not in sel: return "pass-reader list without .fvs-score-receipt"
    if sel.startswith(".pass-reader,") and body == "--epoch:var(--native-pass)" and ".fvs-score-receipt" not in sel: return "epoch receipt list without .fvs-score-receipt"
    if sel == ".head-isolation" and "--fsp-" not in body and "--fss" not in body: return "head-isolation reset list (no --fsp/--fss)"
    return "UNEXPECTED ADDED " + sel[:100] + " | " + body[:120]
def cat_removed(sel, body):
    if sel.startswith("@property --fs-") and "inherits:false" in body: return "fs registration inherits:false"
    if sel.startswith("@property --fsp-") or sel.startswith("@property --fss") or sel.startswith("@property --fvs-score-ready"): return "progress/stamp/ready registration"
    if sel.startswith("@keyframes fvs-score-"): return "score keyframes"
    if sel in (".fvs-score-source", ".fvs-score-source>.track"): return "score scroller"
    if sel == ".fvs-score-reader" and "animation-timeline" in body: return "score reader animations"
    if sel.startswith(".fvs-score-receipt") or ".fvs-score-gate" in sel or "fvsscore" in sel: return "score receipt/gate"
    if sel.startswith("html") and "timeline-scope" in body: return "html timeline-scope (old)"
    if "--native-pass:" in body and ".fvs-score-receipt" in sel: return "pass-reader list with .fvs-score-receipt"
    if sel.startswith(".pass-reader,") and body == "--epoch:var(--native-pass)" and ".fvs-score-receipt" in sel: return "epoch receipt list with .fvs-score-receipt"
    if sel == ".head-isolation" and "--fsp-" in body: return "head-isolation reset list (with --fsp/--fss)"
    return "UNEXPECTED REMOVED " + sel[:100] + " | " + body[:120]
for (sel, body), n in added.items(): cats["+ " + cat_added(sel, body)] += n
for (sel, body), n in removed.items(): cats["- " + cat_removed(sel, body)] += n
for k, v in sorted(cats.items()): print(f"{v:6d}  {k}")
check(not any("UNEXPECTED" in k for k in cats), "unexpected rule categories")
check(cats["+ fs registration inherits:true"] == N and cats["- fs registration inherits:false"] == N, "fs registrations", N)
check(cats["+ container size = anchors"] == LEVELS, "container size rules", cats["+ container size = anchors"], LEVELS)
check(cats["+ publisher (cq units -> --fs)"] == LEVELS, "publisher rules", cats["+ publisher (cq units -> --fs)"], LEVELS)
check(cats["- score keyframes"] % (N + 1) == 0 and cats["- score keyframes"] >= N + 1, "keyframes removed", cats["- score keyframes"])
hi_on = [b for (q, b) in rc if q == ".head-isolation"]; hi_ref = [b for (q, b) in rp if q == ".head-isolation"]
check(len(hi_on) == len(hi_ref) and all(set(a.split(";")) - set(b.split(";")) == set() and all(d.startswith(("--fsp-", "--fss", "--fvs-score-ready")) for d in set(b.split(";")) - set(a.split(";"))) for a, b in zip(sorted(hi_on), sorted(hi_ref))), "head-isolation reset delta is only --fsp/--fss/--fvs-score-ready")
# exact publisher mapping: container k publishes pairs 2k-2, 2k-1 (k>=1), bottom publishes the last two; container k sized by pairs 2k, 2k+1
pairs = [(h, s) for h in range(12) for s in range(cap)]
for k in range(LEVELS):
    (h0, s0), (h1, s1) = pairs[2 * k], pairs[2 * k + 1]
    check((f"#fvs-sc{k}", f"width:anchor-size(--fsa-{h0}-{s0} width);height:anchor-size(--fsa-{h1}-{s1} width)") in rc, "size rule", k)
    if k:
        (p0, q0), (p1, q1) = pairs[2 * k - 2], pairs[2 * k - 1]
        check((f"#fvs-sc{k}", f"--fs-{p0}-{q0}:calc((100cqw / 1px - 262144) / 128);--fs-{p1}-{q1}:calc((100cqh / 1px - 262144) / 128)") in rc, "publisher rule", k)
(p0, q0), (p1, q1) = pairs[-2], pairs[-1]
check((".fvs-score-reader", f"--fs-{p0}-{q0}:calc((100cqw / 1px - 262144) / 128);--fs-{p1}-{q1}:calc((100cqh / 1px - 262144) / 128)") in rc, "bottom publisher")
# score glyph rules and softmax identical
for h in range(12):
    for s in range(cap):
        sel = f".fvs-score-{h}-{s}"
        a = {b for (q, b) in rc if q == sel}; b = {bb for (q, bb) in rp if q == sel}
        check(a == b and len(a) == 1 and "calc-size(max-content,calc(262144px" in next(iter(a)), "score glyph rule identical", sel)
soft_on = sorted(b for (q, b) in rc if q == ".fvs-score-reader" and "--fm-0" in b); soft_ref = sorted(b for (q, b) in rp if q == ".fvs-score-reader" and "--fm-0" in b)
check(soft_on == soft_ref and len(soft_on) == 1, "softmax rule identical")
for tok in ("--fsp-", "--fss", "--fvs-score-ready", "fvsscore", "fvs-score-source", "fvs-score-receipt", "fvs-score-gate", "--fvs-score-stamp", "@keyframes fvs-score-"):
    check(tok not in C, "leftover in css", tok)
scope = re.findall(r"html\{timeline-scope:([^}]+)\}", C); scope_ref = re.findall(r"html\{timeline-scope:([^}]+)\}", P)
check(len(scope) == len(scope_ref) and all("--fvs-score" not in sc for sc in scope), "html scope", len(scope), len(scope_ref))
check(set(scope_ref[-1].split(",")) - set(scope[-1].split(",")) == {f"--fvs-score-{h}-{s}" for h in range(12) for s in range(cap)} | {"--fvs-score-stamp"} and set(scope[-1].split(",")) <= set(scope_ref[-1].split(",")), "scope delta (final merged rule)")
# html
for tok in ("fvs-score-source", "fvs-score-receipt", "fvs-score-gate", "view-timeline:--fvs-score"):
    check(tok not in H, "leftover in html", tok)
check(H.count("anchor-name:--fsa-") == N, "anchors", H.count("anchor-name:--fsa-"))
check(H.count('class="fvs-sc"') == LEVELS, "containers", H.count('class="fvs-sc"'))
check(H.count('class="fvs-score-stage"') == 1, "stage")
check(Q.count("view-timeline:") - H.count("view-timeline:") == N + 1, "view-timeline delta", Q.count("view-timeline:") - H.count("view-timeline:"))
check(H.count('<div class="fvs-score-reader"><div class="fvs-softmax">') == 1, "reader>softmax")
stage_pos, chain_pos = H.find('class="fvs-score-stage"'), H.find('id="fvs-sc0"')
check(0 < stage_pos < chain_pos, "stage before chain")
check(H.find(f'id="fvs-sc{LEVELS-1}"') < H.find('class="fvs-score-reader"'), "reader inside last container")
check(all(H.find(f"anchor-name:--fsa-{h}-{s}") < chain_pos for h, s in pairs), "all anchors precede the chain")
# depth / ancestors / element counts
VOID = {"meta", "link", "input", "br", "img", "hr", "source"}
class Pz(HTMLParser):
    def __init__(s): super().__init__(); s.stack = []; s.maxd = 0; s.n = 0; s.anc = None; s.reader = None
    def handle_starttag(s, tag, attrs):
        a = dict(attrs); s.n += 1
        s.stack.append((tag, a.get("class", ""), a.get("id", ""), a.get("style", "")))
        s.maxd = max(s.maxd, len(s.stack))
        if a.get("id") == "fvs-sc0": s.anc = list(s.stack[:-1])
        if "fvs-score-reader" in a.get("class", "").split() and s.reader is None: s.reader = len(s.stack)
        if tag in VOID: s.stack.pop()
    def handle_endtag(s, tag):
        for i in range(len(s.stack) - 1, -1, -1):
            if s.stack[i][0] == tag: del s.stack[i:]; break
pa, pb = Pz(), Pz(); pa.feed(H); pb.feed(Q)
print(f"elements bundle/ref: {pa.n} {pb.n} delta {pa.n - pb.n}; max depth {pa.maxd} (ref {pb.maxd}); reader depth {pa.reader} (ref {pb.reader})")
check(pa.maxd < 500, "depth cap", pa.maxd)
check(pa.n - pb.n == (1 + LEVELS) - (2 + 1 + 2), "element delta", pa.n - pb.n)
# containing-block lint on the chain's ancestors: no rule with these properties may target an ancestor by class or id
bad_props = ("contain:", "transform:", "filter:", "will-change:", "backdrop-filter:", "perspective:", "position:absolute", "position:relative", "position:sticky")
sel_bodies = [(q, b) for (q, b) in rc if any(p in b for p in bad_props)]
hits = []
for tag, cls, ident, style in pa.anc:
    toks = [f".{c}" for c in cls.split()] + ([f"#{ident}"] if ident else [])
    for q, b in sel_bodies:
        last = q.split()[-1] if q else ""
        if any(t in last for t in toks) and not last.startswith("@"):
            hits.append((tag, cls, ident, q[-80:], [d for d in b.split(";") if any(p.rstrip(":") in d for p in bad_props)]))
    if any(p in style for p in bad_props): hits.append((tag, cls, ident, "inline", style))
check(not hits, "ancestor CB lint", hits)
print("ancestors of the chain:", " > ".join((c or t) + ("#" + i if i else "") for t, c, i, _ in pa.anc))
w1, w2 = json.loads((B / "font-witnesses.json").read_text()), json.loads((R / "font-witnesses.json").read_text())
check(w1 == w2, "font witnesses identical", len(w1), len(w2))
print("witnesses identical:", w1 == w2, len(w1))
print(f"sizes css/html bundle: {len(C)} {len(H)} ref: {len(P)} {len(Q)}")
print("manifest r4sSmallHops:", man.get("r4sSmallHops"))
for f in fail: print("FAIL", *f)
print("RESULT:", "PASS" if not fail else f"FAIL ({len(fail)})")
sys.exit(1 if fail else 0)
