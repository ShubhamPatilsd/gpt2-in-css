# R3M copy of R3F/offline_check.py: bundle args may be directory paths (R3M/scratch/...) instead of names under bundles/.
"""R3F offline check: bundles/<name> (R2G_SCOPED_HAS on) vs bundles/<ref> (same tools, flag off).
Rule-level diff must be limited to rules whose selector contains `:has(`; each changed rule must be the
same rule with the argument scoped; index.html byte-identical; @property / @font-face / witnesses identical.
usage: python offline_check.py <bundle> <reference-bundle>"""
import json, re, sys
from collections import Counter
from pathlib import Path
W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
name, ref = sys.argv[1], sys.argv[2]
B, R = (Path(name) if "/" in name else W / "bundles" / name), (Path(ref) if "/" in ref else W / "bundles" / ref)
C, P = (B / "runtime.css").read_text(), (R / "runtime.css").read_text()
fail = []
def check(cond, *msg):
    if not cond: fail.append(msg)
MC, MP = json.loads((B / "manifest.json").read_text()), json.loads((R / "manifest.json").read_text())
check((B / "index.html").read_bytes() == (R / "index.html").read_bytes(), "index.html identical")
check(MC.get("r2gScopedHas") and MP.get("r2gScopedHas") is None, "flag in manifests")
def rules(css):
    css = re.sub(r"@(?:font-face|property)\b[^{}]*\{[^{}]*\}", "", css)
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
unscope = lambda s: re.sub(r":has\((?:> :where\([^()]*\) )+> ", ":has(", s)
for (sel, decl), n in added.items():
    check(":has(" in sel, "added rule without :has()", sel[:120])
    check(removed.get((unscope(sel), decl), 0) == n, "added rule is not a scoped copy of a removed one", sel[:160])
for (sel, decl), n in removed.items():
    check(":has(" in sel, "removed rule without :has()", sel[:120])
occ = sum(n * sel.count(":has(> :where(") for (sel, decl), n in added.items())
check(sum(added.values()) == sum(removed.values()) and occ == MC["r2gScopedHas"]["total"], "counts", sum(added.values()), sum(removed.values()), occ, MC["r2gScopedHas"]["total"])
check(re.findall(r"@property [^}]*\}", C) == re.findall(r"@property [^}]*\}", P), "registrations identical")
check(re.findall(r"@font-face\{[^}]*\}", C) == re.findall(r"@font-face\{[^}]*\}", P), "font faces identical")
check(not re.search(r":has\(#[\w-]+(?:\.done|:checked)\)", C), "no unscoped id argument left")
wc = json.loads((B / "font-witnesses.json").read_text()); wp = json.loads((R / "font-witnesses.json").read_text())
norm = lambda d: {re.sub(r"/work/2026-09-19/[\w-]+/", "/X/", k): {x: y for x, y in v.items() if x != "mtime"} for k, v in d.items()}
check(norm(wc) == norm(wp), "witnesses identical (modulo tools-copy path / mtime)")
print("rules", {"bundle": sum(rc.values()), "ref": sum(rp.values()), "added": sum(added.values()), "removed": sum(removed.values())}, "css bytes", len(C), len(P), "rewritten", MC["r2gScopedHas"]["rewritten"])
print("FAIL" if fail else "PASS", len(fail))
for f in fail: print(" -", f)
