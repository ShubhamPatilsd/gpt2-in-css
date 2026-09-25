"""R5H offline check: bundles/<name> (R5H_CH_SCORES on) vs bundles/<ref> (same tools, R5H off -> R4S chain or the view-timeline hop).
usage: python offline_check.py <bundle> <reference-bundle> [capacity]
Checks: rule diff confined to the intended families (with exact counts), the exact slot rule for every (head, slot), the per-head
softmax/weight split == the reference's single-element rule, no leftovers of the old hop, HTML structure (12 chains of `capacity`
nested slot elements inside the ctx track, each bottom hosting exactly its head's 64 rows, nothing positioned/contained between
.track and the rows except our divs), depth, element delta, font witnesses identical modulo the 12 dot-font paths, manifest."""
import json, re, sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
name, ref = sys.argv[1], sys.argv[2]
B, R = W / "bundles" / name, W / "bundles" / ref
C, P = (B / "runtime.css").read_text(), (R / "runtime.css").read_text()
H, Q = (B / "index.html").read_text(), (R / "index.html").read_text()
man, rman = json.loads((B / "manifest.json").read_text()), json.loads((R / "manifest.json").read_text())
cap = int(sys.argv[3]) if len(sys.argv) > 3 else man["capacity"]
N = 12 * cap
ref_is_r4s = bool(rman.get("r4sSmallHops"))
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
SLOT = re.compile(r"\.fvs-score-(\d+)-(\d+)")
def cat_added(sel, body):
    if sel.startswith("@property --fs-") and "inherits:true" in body: return "fs registration inherits:true"
    if SLOT.fullmatch(sel) and body.startswith("display:block;font:512px FvsDot") and "1ch / 1px" in body: return "slot rule (font + 1ch decode)"
    if re.fullmatch(r"\.fvs-sr-\d+", sel) and "--fm-" in body: return "per-head softmax"
    if re.fullmatch(r"\.fvs-sr-\d+", sel) and body.startswith("--fw-"): return "per-head weights"
    if sel.startswith("html") and "timeline-scope" in body: return "html timeline-scope (score names removed)"
    if "--native-pass:" in body and ".fvs-score-reader" in sel and ".fvs-score-receipt" not in sel: return "pass-reader list without .fvs-score-receipt"
    if sel.startswith(".pass-reader,") and body == "--epoch:var(--native-pass)" and ".fvs-score-receipt" not in sel: return "epoch receipt list without .fvs-score-receipt"
    if sel == ".head-isolation" and "--fsp-" not in body and "--fss" not in body: return "head-isolation reset list (no --fsp/--fss)"
    return "UNEXPECTED ADDED " + sel[:100] + " | " + body[:120]
def cat_removed(sel, body):
    if sel.startswith("@property --fs-") and "inherits:false" in body: return "fs registration inherits:false"
    if sel.startswith("@property --fsp-") or sel.startswith("@property --fss") or sel.startswith("@property --fvs-score-ready"): return "progress/stamp/ready registration"
    if sel.startswith("@keyframes fvs-score-"): return "score keyframes"
    if SLOT.fullmatch(sel) and body.startswith("font:512px FvsDot") and "calc-size(max-content" in body: return "score carrier rule (font + width)"
    if sel in (".fvs-score-source", ".fvs-score-source>.track"): return "score scroller"
    if sel == ".fvs-score-reader" and "animation-timeline" in body: return "score reader animations"
    if sel.startswith(".fvs-score-receipt") or ".fvs-score-gate" in sel or "fvsscore" in sel: return "score receipt/gate"
    if sel in (".fvs-score-stage", ".fvs-score-a", ".fvs-sc", ".fvs-score-reader") and ("position:fixed" in body or body.startswith("display:block")): return "R4S chain structure"
    if re.fullmatch(r"#fvs-sc\d+", sel) and body.startswith("width:anchor-size("): return "R4S container size"
    if (re.fullmatch(r"#fvs-sc\d+", sel) or sel == ".fvs-score-reader") and "100cqw / 1px" in body: return "R4S publisher"
    if sel == ".fvs-score-reader" and "--fm-0" in body: return "single-element softmax"
    if sel == ".fvs-score-reader" and body.startswith("--fw-"): return "single-element weights"
    if sel.startswith("html") and "timeline-scope" in body: return "html timeline-scope (old)"
    if "--native-pass:" in body and ".fvs-score-receipt" in sel: return "pass-reader list with .fvs-score-receipt"
    if sel.startswith(".pass-reader,") and body == "--epoch:var(--native-pass)" and ".fvs-score-receipt" in sel: return "epoch receipt list with .fvs-score-receipt"
    if sel == ".head-isolation" and "--fsp-" in body: return "head-isolation reset list (with --fsp/--fss)"
    return "UNEXPECTED REMOVED " + sel[:100] + " | " + body[:120]
for (sel, body), n in added.items(): cats["+ " + cat_added(sel, body)] += n
for (sel, body), n in removed.items(): cats["- " + cat_removed(sel, body)] += n
for k, v in sorted(cats.items()): print(f"{v:6d}  {k}")
check(not any("UNEXPECTED" in k for k in cats), "unexpected rule categories")
check(cats["+ slot rule (font + 1ch decode)"] == N and cats["- score carrier rule (font + width)"] == N, "slot/carrier rule counts", N)
check(cats["+ per-head softmax"] == 12 and cats["+ per-head weights"] == 12 and cats["- single-element softmax"] == 1 and cats["- single-element weights"] == 1, "softmax split counts")
if ref_is_r4s:
    check(cats["+ fs registration inherits:true"] == 0 and cats["- fs registration inherits:false"] == 0, "fs registrations unchanged vs R4S")
    check(cats["- R4S container size"] == N // 2 and cats["- R4S publisher"] == N // 2, "R4S chain rules removed", cats["- R4S container size"], cats["- R4S publisher"])
else:
    check(cats["+ fs registration inherits:true"] == N and cats["- fs registration inherits:false"] == N, "fs registrations", N)
    check(cats["- score keyframes"] >= N + 1, "keyframes removed", cats["- score keyframes"])
# exact slot rules: the carrier rule's font declarations + the decode with the carrier's constants
m = re.search(r"\.fvs-score-0-0\{font:512px FvsDot0;line-height:1;font-kerning:none;font-variation-settings:var\(--fr-k-0\),var\(--fvs-query-0\);width:calc-size\(max-content,calc\(262144px \+ \(size - ([0-9.]+)px\) \* var\(--fqs-0\) \* var\(--fr-ks-0-0\) \* ([0-9.e-]+)\)\)\}", P)
check(m, "reference carrier rule found")
base_px, k128 = (float(m[1]), float(m[2])) if m else (None, None)
for h in range(12):
    for s in range(cap):
        sel = f".fvs-score-{h}-{s}"
        a = [b for (q, b) in rc if q == sel]
        check(len(a) == 1, "one slot rule", sel, len(a))
        if not a: continue
        mm = re.fullmatch(rf"display:block;font:512px FvsDot{h};line-height:1;font-kerning:none;font-variation-settings:var\(--fr-k-{s}\),var\(--fvs-query-{h}\);--fs-{h}-{s}:calc\(\(1ch / 1px - ([0-9.]+)\) \* var\(--fqs-{h}\) \* var\(--fr-ks-{s}-{h}\) \* ([0-9.e-]+)\)", a[0])
        check(mm, "slot rule shape", sel, a[0][:200])
        if mm and m:
            check(float(mm[1]) == base_px, "slot base == carrier base", sel, mm[1], m[1])
            check(abs(float(mm[2]) * 128 - k128) <= 1e-12 * k128, "slot k == carrier k / 128", sel, mm[2], m[2])
        ref_rule = [b for (q, b) in rp if q == sel]
        check(len(ref_rule) == 1 and ref_rule[0].split(";width:")[0] == a[0].split(";--fs-")[0].replace("display:block;", ""), "font declarations identical to the carrier's", sel)
# per-head softmax/weights == the reference single rule, split by head, byte for byte
soft_ref = [b for (q, b) in rp if q == ".fvs-score-reader" and "--fm-0" in b]
w_ref = [b for (q, b) in rp if q == ".fvs-score-reader" and b.startswith("--fw-")]
check(len(soft_ref) == 1 and len(w_ref) == 1, "reference softmax/weight rules")
if soft_ref and w_ref:
    soft_on = ";".join(next(b for (q, b) in rc if q == f".fvs-sr-{h}" and "--fm-" in b) for h in range(12))
    w_on = ";".join(next(b for (q, b) in rc if q == f".fvs-sr-{h}" and b.startswith("--fw-")) for h in range(12))
    check(soft_on == soft_ref[0], "softmax declarations identical (concatenated per head)")
    check(w_on == w_ref[0], "weight declarations identical (concatenated per head)")
fv_on = [b for (q, b) in rc if q == ".fvs-score-reader" and b.startswith("--fv-0:")]; fv_ref = [b for (q, b) in rp if q == ".fvs-score-reader" and b.startswith("--fv-0:")]
check(fv_on == fv_ref and len(fv_on) == 1, "--fv-S rule identical on .fvs-score-reader")
for tok in ("--fsp-", "--fss", "--fvs-score-ready", "fvsscore", "fvs-score-source", "fvs-score-receipt", "fvs-score-gate", "--fvs-score-stamp", "@keyframes fvs-score-", "anchor-size(--fsa", "fvs-score-stage", "#fvs-sc", "100cqw / 1px - 262144"):
    check(tok not in C, "leftover in css", tok)
scope = re.findall(r"html\{timeline-scope:([^}]+)\}", C)
check(all("--fvs-score" not in sc for sc in scope), "html scope has no score names")
# fonts: 12 FvsDotH faces point at the R5H assets; value faces unchanged
dots = re.findall(r'@font-face\{font-family:FvsDot(\d+);src:url\("([^"]+)"\)\}', C)
check(len(dots) == 12 and all("assets-r5h/font-vector-operators-r5h/dot-h" in u and u.endswith("-r5h.woff2") for _, u in dots), "12 R5H dot faces", dots[:2])
vals = re.findall(r'@font-face\{font-family:FvsValue(\d+);src:url\("([^"]+)"\)\}', C); vals_ref = re.findall(r'@font-face\{font-family:FvsValue(\d+);src:url\("([^"]+)"\)\}', P)
check(vals == vals_ref, "value faces unchanged")
# html
for tok in ("fvs-score-source", "fvs-score-receipt", "fvs-score-gate", "view-timeline:--fvs-score", "anchor-name:--fsa-", 'class="fvs-sc"', "fvs-score-stage"):
    check(tok not in H, "leftover in html", tok)
check(Q.count("view-timeline:") - H.count("view-timeline:") == (0 if ref_is_r4s else N + 1), "view-timeline delta", Q.count("view-timeline:") - H.count("view-timeline:"))
VOID = {"meta", "link", "input", "br", "img", "hr", "source"}
class Pz(HTMLParser):
    def __init__(s):
        super().__init__(); s.stack = []; s.maxd = 0; s.n = 0; s.rows_by_bottom = Counter(); s.bad_between = []; s.chains = []; s.bottom_depth = {}
        s.bottom_ok = 0; s.track = None
    def handle_starttag(s, tag, attrs):
        a = dict(attrs); s.n += 1; cls = a.get("class", ""); classes = cls.split()
        s.stack.append((tag, cls, a.get("id", ""), a.get("style", "")))
        s.maxd = max(s.maxd, len(s.stack))
        if "track" in classes and s.track is None and any("cache-bridge-source" in c for _, c, _, _ in s.stack[:-1]):
            s.track = len(s.stack)
        if "fvs-score-reader" in classes:
            head = next((c for c in classes if c.startswith("fvs-sr-")), None)
            s.bottom_depth[head] = len(s.stack)
            # ancestors between the track and this bottom must be exactly the head's slot elements 0..cap-1
            between = [c for _, c, _, _ in s.stack[s.track:-1]] if s.track else []
            expect = [f"fvs-score-{head[7:]}-{k}" for k in range(cap)] if head else None
            s.chains.append((head, between == expect, between[:3]))
        if "fvs-value-row" in classes:
            bottoms = [c for _, c, _, _ in s.stack if "fvs-score-reader" in c]
            m2 = re.search(r"var\(--fb-(\d+)\)", a.get("style", ""))
            key = (bottoms[-1] if bottoms else None, m2[1] if m2 else None)
            s.rows_by_bottom[key] += 1
            for t, c, i, st in s.stack[s.track:-1] if s.track else []:
                if not (c.startswith("fvs-score-") or "fvs-score-reader" in c): s.bad_between.append((t, c, i))
        if tag in VOID: s.stack.pop()
    def handle_endtag(s, tag):
        for i in range(len(s.stack) - 1, -1, -1):
            if s.stack[i][0] == tag: del s.stack[i:]; break
pa, pb = Pz(), Pz(); pa.feed(H); pb.feed(Q)
print(f"elements bundle/ref: {pa.n} {pb.n} delta {pa.n - pb.n}; max depth {pa.maxd} (ref {pb.maxd}); track depth {pa.track}; bottoms {len(pa.bottom_depth)} at depth {sorted(set(pa.bottom_depth.values()))}")
check(pa.maxd < 500, "depth cap", pa.maxd)
check(len(pa.chains) == 12 and all(ok for _, ok, _ in pa.chains) and sorted(h for h, _, _ in pa.chains) == sorted(f"fvs-sr-{h}" for h in range(12)), "12 chains: track > slot 0..cap-1 > bottom", pa.chains[:3])
check(all(pa.rows_by_bottom[(f"fvs-score-reader fvs-sr-{h}", str(h))] == 64 for h in range(12)) and sum(pa.rows_by_bottom.values()) == 768, "each bottom hosts exactly its head's 64 rows", dict(pa.rows_by_bottom))
check(not pa.bad_between, "nothing but slot/bottom elements between .track and the rows", pa.bad_between[:3])
check(H.count('class="fvs-score-reader fvs-sr-') == 12 and H.count("fvs-score-reader") == 12, "12 bottoms")
check(sum(H.count(f'<div class="fvs-score-{h}-{s}">') for h in range(12) for s in range(cap)) == N, "slot elements", N)
expected_delta = (12 * (cap + 1) + 1) - ((1 + 1 + N // 2 + N + 1) if ref_is_r4s else (1 + 1 + 1 + N + 1 + 1 + 1 + 1))  # +softmax wrapper only vs [stage,rows,containers,reader,softmax] / [scroller,track,N carriers,stamp,reader,receipt,gate,softmax]
check(pa.n - pb.n == expected_delta, "element delta", pa.n - pb.n, expected_delta)
# containing-block sanity: no rule targets our slot/bottom classes with positioning/contain/transform
bad_props = ("position:", "contain:", "transform:", "filter:", "will-change:", "perspective:", "overflow:")
hits = [(q, b) for (q, b) in rc if (q.startswith(".fvs-score-") or q.startswith(".fvs-sr-")) and not q.startswith(".fvs-score-reader,") and any(p in b for p in bad_props)]
check(not hits, "slot/bottom rules carry no positioning/containment", hits[:2])
# witnesses: identical modulo the 12 dot paths (values must match)
def norm(w): return {re.sub(r"^.*?/(experiments|assets|assets-r5h|global-projection-assets|data)/", r"\1/", k): v for k, v in w.items()}
w1, w2 = norm(json.loads((B / "font-witnesses.json").read_text())), norm(json.loads((R / "font-witnesses.json").read_text()))
only1, only2 = sorted(set(w1) - set(w2)), sorted(set(w2) - set(w1))
same = sum(1 for k in w1 if k in w2 and w1[k] == w2[k])
check(same == len(w1) - 12 and len(only1) == 12 and len(only2) == 12, "witnesses: all but the 12 dot faces identical", same, len(w1), len(only1), len(only2))
def strip(k): return re.sub(r"^.*dot-h(\d+)-.*$", r"\1", k)
pairs = {strip(k): (w1[k], w2.get(k2)) for k in only1 for k2 in only2 if strip(k) == strip(k2)}
# the witness generator renders the LOWEST cmap codepoint: U+0030 in the R5H fonts (same glyph) vs U+F5800 in F4's; advance/upem must match
check(len(pairs) == 12 and all(a["advance"] == b["advance"] and a["upem"] == b["upem"] and a["codepoint"] == 0x30 and b["codepoint"] == 0xF5800 for a, b in pairs.values()), "dot witnesses: same advance/upem, codepoint U+0030 (R5H) vs U+F5800 (F4)", list(pairs.items())[:1])
print("witness sample:", next(iter(pairs.items())) if pairs else None)
print(f"sizes css/html bundle: {len(C)} {len(H)} ref: {len(P)} {len(Q)}")
print("manifest:", {k: man.get(k) for k in ("r5hChScores", "r4sSmallHops", "capacity", "valueLayout", "r4tConsumerChunk")})
check(man.get("r5hChScores") is True and man.get("r4sSmallHops") is False, "manifest flags")
for f in fail: print("FAIL", *f)
print("RESULT:", "PASS" if not fail else f"FAIL ({len(fail)})")
sys.exit(1 if fail else 0)
