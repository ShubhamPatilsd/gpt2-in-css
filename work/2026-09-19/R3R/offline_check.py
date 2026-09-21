"""R3R offline check: bundles/<name> (R3R_FOLD_HOP on) vs bundles/<ref> (combined3 = same tools with the flag off).
Every removed/added rule must fall into one of the intended categories; witnesses (keys modulo tools dir) and font url()s identical;
the DOM keeps the same element set except the loop banks, the proj consumers and the moved export.
usage: python offline_check.py <bundle> <reference-bundle>"""
import json, re, sys
from collections import Counter
from pathlib import Path

W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
name, ref = sys.argv[1], sys.argv[2]
B, R = W / "bundles" / name, W / "bundles" / ref
C, P = (B / "runtime.css").read_text(), (R / "runtime.css").read_text()
H, Q = (B / "index.html").read_text(), (R / "index.html").read_text()
fail = []


def check(cond, *msg):
    if not cond:
        fail.append(msg)


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

REMOVED = {
    "loop bank / latch": lambda s, d: ".loop-bank" in s or ".loop-scroll" in s or ".loop-track" in s or ".loop-metric" in s or "--saved-" in s or s.startswith("@property --saved-") or s.startswith("@property --lp-") or s.startswith("@keyframes loop-k-") or "--loop-phase" in s or "--loop-out" in d or "--loop-out" in s or "--saved-" in d,
    "old controller / loop-input decode": lambda s, d: s in (".core-controller", ".core-pass-reader", ".loop-input") or s.startswith("@container loopcontrol style(--loop-phase") or s.startswith("@container loopcontrol style(--pass:") and ".loop-bank" in d,
    "loop-reader anims": lambda s, d: s == ".loop-reader" and "animation-name" in d,
    "proj number consumers": lambda s, d: ".shared-proj-c" in s or s.startswith("@keyframes projk") or s.startswith("@property --projp-"),
    "proj timeline scope / viewport": lambda s, d: s.endswith(".shared-proj") and ("timeline-scope" in d) or s.endswith(".shared-proj>.scroller") or s.endswith(".shared-proj>.scroller>.track") or (s.endswith(".shared-proj") and "--markerbase-proj" in d),
    "proj receipt (viewport constants)": lambda s, d: s.endswith(".shared-proj-receipt"),
    "export display": lambda s, d: ".reused-final-export" in s,
    "reused-output loop-out": lambda s, d: s == ".reused-output" and "--loop-out" in d,
    "pass stamps incl. banks": lambda s, d: s.startswith("@container loopcontrol style(--pass:") and ".loop-bank-0" in s,
    "SMIL pulse keyframes / pass-1 initial rule (old loop_parts)": lambda s, d: s.startswith("@keyframes loop-pulse") or (s.startswith("@container loopcontrol style(--pass:1)") and "--initial-0" in d),
    "merged html timeline-scope (names added)": lambda s, d: s == "html" and "timeline-scope" in d,
    "head-isolation wall (follows the @property set)": lambda s, d: s == ".head-isolation",
    "loop-ready/ack regs": lambda s, d: s.startswith("@property --loop-ack") or s.startswith("@property --loop-captured") or s.startswith("@property --loop-held") or s.startswith("@property --loop-phase"),
}
ADDED = {
    "new controller / pass reader / loop-input": lambda s, d: s in (".core-controller", ".core-pass-reader", ".loop-input", ".loop-reader") or s.startswith("@keyframes prstamp") or s.startswith("@keyframes lpk") or s.startswith("@property --lp-") or s.startswith("@property --pr-stamp") or s.startswith("@property --held"),
    "held rules": lambda s, d: s.startswith("@container loopcontrol style(--held:1)"),
    "proj constants": lambda s, d: (s.endswith(".shared-proj") and "--pk-000" in d) or s.startswith("@property --pk-") or s.startswith("@property --pc-"),
    "proj timeline scope / viewport": lambda s, d: s == "html" and "timeline-scope" in d or s.endswith(".shared-proj>.scroller") or s.endswith(".shared-proj>.scroller>.track") or (s.endswith(".shared-proj") and ("--markerbase-proj" in d or d.startswith("font:normal"))),
    "proj receipt (viewport constants)": lambda s, d: s.endswith(".shared-proj-receipt"),
    "export display": lambda s, d: ".reused-final-export" in s,
    "head-isolation wall (follows the @property set)": lambda s, d: s == ".head-isolation",
    "pass stamps without banks": lambda s, d: s.startswith("@container loopcontrol style(--pass:") and ".loop-input,.reused-input" in s,
}


def classify(items, table, label):
    cats = Counter(); other = []
    for (sel, decl), n in items.items():
        for k, f in table.items():
            if f(sel, decl):
                cats[k] += n; break
        else:
            other.append((sel[:140], decl[:100], n))
    print(f"{label}: {sum(items.values())} rules"); [print(f"  {v:6d}  {k}") for k, v in cats.most_common()]
    for o in other[:20]: print("  UNEXPECTED", o)
    check(not other, f"{label}: unexpected rules", len(other))


classify(removed, REMOVED, "removed (in reference only)")
classify(added, ADDED, "added (in bundle only)")

# witnesses / fonts
wa = json.loads((B / "font-witnesses.json").read_text()); wb = json.loads((R / "font-witnesses.json").read_text())
norm = lambda w: {re.sub(r"/work/2026-09-19/\w+/", "/work/2026-09-19/X/", k): v for k, v in w.items()}
check(norm(wa) == norm(wb), "font witnesses identical (keys modulo tools dir)", len(wa), len(wb))
fa, fb = set(re.findall(r'url\("([^"]+)"\)', C)), set(re.findall(r'url\("([^"]+)"\)', P))
check(fa == fb, "font url()s identical", len(fa), len(fb))
# DOM
for pat, want in ((r'class="loop-bank', 0), ("loop-metric", 0), ('class="shared-proj-c', 0), ('class="core-pass-reader"', 1), ('class="reused-final-export"', 1), ("loop-signals", 1)):
    check(H.count(pat) == want, f"index.html count {pat!r} == {want}", H.count(pat))
i = H.find('<svg class="loop-signals"></svg>'); check(H[i:i + 200].count('<div class="reused-final-export">') == 1, "export right after svg.loop-signals")
check("--out-" not in H[H.find('class="reused-final-export"'):H.find('class="loop-compute"')], "export reads --loop-in-*, not --out-*")
check(H.count("var(--pc-000)") == 1 and H.count("calc-size(max-content,262144px + var(--pc-") == 768, "768 folded proj carriers", H.count("calc-size(max-content,262144px + var(--pc-"))
ea, eb = H.count("<"), Q.count("<")
print("elements (tags) bundle/ref:", ea, eb, "delta", ea - eb)
# proj constants appear in every layer block
print("pk rules per layer:", len(re.findall(r"\.shared-proj\{--pk-000:", C)), "| scroller widths:", set(re.findall(r"\.shared-proj>\.scroller\{width:(\d+)px\}", C)), "| markerbase:", set(re.findall(r"--markerbase-proj:(\d+)px", C)))
last = re.findall(r"html\{timeline-scope:([^}]*)\}", C)[-1].split(",")
check("--shared-proj-t0" in last and "--shared-proj-t767" in last and "--shared-proj-generation" in last, "final html timeline-scope has the proj names")
MC = json.loads((B / "manifest.json").read_text()); check(MC.get("r3rFoldHop") is True, "manifest r3rFoldHop")
print("sizes css/html bundle:", len(C), len(H), "ref:", len(P), len(Q))
print("RESULT:", "PASS" if not fail else "FAIL"); [print("  FAIL", *f) for f in fail]
sys.exit(1 if fail else 0)
