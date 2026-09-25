#!/usr/bin/env python3
"""R5E offline check: candidate bundle vs reference bundle.
usage: offline_check.py <cand-dir> <ref-dir>
- CSS: rule-level multiset diff (prelude+parents normalised) must be confined to the R5E families;
- HTML: removing the R5E diagnostic elements from the reference must give the candidate byte-for-byte;
- witnesses identical; element counts and declaration bytes of the changed populations before/after.
"""
import sys, re, json, collections
sys.path.insert(0, "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R5E/tools")
import r5e_dead_weight as r5e

cand, ref = sys.argv[1], sys.argv[2]
rd = lambda d, f: open(f"{d}/{f}", encoding="utf-8").read()
normurl = lambda s: re.sub(r'url\("(?:\.\./)+', 'url("REL/', s)
ccss, rcss = normurl(rd(cand, "runtime.css")), normurl(rd(ref, "runtime.css"))
chtml, rhtml = rd(cand, "index.html"), rd(ref, "index.html")
ok = True
def fail(msg):
    global ok; ok = False; print("FAIL:", msg)

# ---- CSS rule multisets
def rules(css):
    out = collections.Counter()
    for pre, body, parents in r5e._rules(css):
        out[(parents, pre, body)] += 1
    return out
cr, rr = rules(ccss), rules(rcss)
only_c = cr - rr; only_r = rr - cr
norm = lambda s: re.sub(r"\d+", "N", s)
fam = collections.Counter()
detail = collections.defaultdict(lambda: [0, 0, 0, 0])  # rules removed, bytes removed, rules added, bytes added
for (parents, pre, body), n in only_r.items():
    key = norm(pre) if not (pre.startswith("@property")) else "@property " + norm(pre.split()[1])
    detail[key][0] += n; detail[key][1] += n * len(body)
for (parents, pre, body), n in only_c.items():
    key = norm(pre) if not (pre.startswith("@property")) else "@property " + norm(pre.split()[1])
    detail[key][2] += n; detail[key][3] += n * len(body)
ALLOWED = {".core-reset", ".head-isolation", ".loop-input", ".fvs-query", "@property --lp-N"} | {f".loop-reader-cN"}
print("CSS rule families that differ (removed rules/bytes -> added rules/bytes):")
for k, v in sorted(detail.items(), key=lambda kv: -(kv[1][1] + kv[1][3])):
    print(f"  {k:32s} -{v[0]:5d} rules {v[1]:9d} B  +{v[2]:5d} rules {v[3]:9d} B")
    if k not in ALLOWED:
        fail(f"unexpected CSS family changed: {k}")
# specific content checks
lp_flip = sum(1 for (p, pre, body), n in only_c.items() if pre.startswith("@property --lp-") and "inherits:true" in body)
lp_flip_r = sum(1 for (p, pre, body), n in only_r.items() if pre.startswith("@property --lp-") and "inherits:false" in body)
print(f"@property --lp-*: {lp_flip_r} inherits:false removed, {lp_flip} inherits:true added")
def rule_body(css, sel):
    i = css.find(sel + "{"); j = css.index("}", i); return css[i + len(sel) + 1:j]
for wall in (".core-reset", ".head-isolation"):
    rb, cb = rule_body(rcss, wall), rule_body(ccss, wall)
    rset = {d.split(":")[0] for d in rb.split(";") if d.endswith(":initial")}
    cset = {d.split(":")[0] for d in cb.split(";") if d.endswith(":initial")}
    if not cset <= rset: fail(f"{wall}: candidate keeps properties the reference did not reset")
    others_r = [d for d in rb.split(";") if not d.endswith(":initial")]; others_c = [d for d in cb.split(";") if not d.endswith(":initial")]
    if others_r != others_c: fail(f"{wall}: non-reset declarations changed")
    fams = collections.Counter(norm(p) for p in cset)
    print(f"{wall}: {len(rset)} resets -> {len(cset)} ({len(rb)} -> {len(cb)} B); kept families {sorted(fams.items())}")
# independent re-derivation of the kept set from the REFERENCE page+sheet
_, stats = r5e.lean_walls(rcss, rhtml)
print("lean_walls re-derived on the reference:", stats)
# dead lists
for needle in ("--fvs-all-fields:", "--fvs-retained-"):
    print(f"{needle} decls: ref {rcss.count(needle)} cand {ccss.count(needle)}; readers var({needle[:-1]}: ref {rcss.count('var(' + needle[:-1])} cand {ccss.count('var(' + needle[:-1])}")
    if ccss.count("var(" + needle[:-1]) or rcss.count("var(" + needle[:-1]): fail(f"{needle} has readers")
# forwards
fw_r = sum(body.count(":inherit") for (p, pre, body), n in only_r.items() for _ in range(n) if pre.startswith(".loop-reader-c") or pre == ".loop-input")
fw_c = sum(body.count(":inherit") for (p, pre, body), n in only_c.items() for _ in range(n) if pre.startswith(".loop-reader-c") or pre == ".loop-input")
print(f"--lp forwards (:inherit) in changed loop rules: ref {fw_r} cand {fw_c}")

# ---- HTML: strip the diagnostic elements from the reference
probe = re.compile(r'<i class="readback[^"]*" (?:id="[^"]+" )?style="anchor-name:--(?:core-probe|block-\d+-probe|reused-probe)(?:-epoch)?;[^"]*"></i>')
observer = re.compile(r'<i id="core-epoch-observer" style="[^"]*"></i>')
stripped, n1 = probe.subn("", rhtml); stripped, n2 = observer.subn("", stripped)
print(f"HTML: removed {n1} readback probes + {n2} core-epoch-observer from the reference -> {'IDENTICAL to candidate' if stripped == chtml else 'DIFFERS from candidate'}")
if stripped != chtml:
    fail("HTML differs beyond the diagnostic elements")
    i = next((i for i, (x, y) in enumerate(zip(stripped, chtml)) if x != y), min(len(stripped), len(chtml)))
    print(repr(stripped[i - 80:i + 80])); print(repr(chtml[i - 80:i + 80]))
elems = lambda h: len(re.findall(r"<[a-zA-Z]", h))
print(f"elements: ref {elems(rhtml)} cand {elems(chtml)} (delta {elems(chtml) - elems(rhtml)}); inline style bytes: ref {sum(map(len, re.findall(r'style=\"([^\"]*)\"', rhtml)))} cand {sum(map(len, re.findall(r'style=\"([^\"]*)\"', chtml)))}")
print(f"sizes: runtime.css ref {len(rd(ref,'runtime.css'))} cand {len(rd(cand,'runtime.css'))}; index.html ref {len(rhtml)} cand {len(chtml)}")
# ---- witnesses
wa, wb = json.load(open(f"{cand}/font-witnesses.json")), json.load(open(f"{ref}/font-witnesses.json"))
kn = lambda w: {re.sub(r".*/2026-09-19/[^/]+/", "AGENT/", str(k)): v for k, v in w.items()} if isinstance(w, dict) else w
print("font-witnesses identical:", kn(wa) == kn(wb), "(entries", len(wa), ")")
if kn(wa) != kn(wb): fail("witnesses differ")
print("RESULT:", "PASS" if ok else "FAIL")
