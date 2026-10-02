"""R8U copy: = R6X/check_v5_identity.py with .r8u-/.fb-warn added to the display allow-list (html is checked by check_layout_diff.py)."""
"""R6X v5 identity: <new> vs <ref> bundle. index.html must be identical after normalising the embedding receipt marker; the css rule
multiset AND order must be identical except rules of the typed-prompt wiring / R6X-R6V display layer (allow-list below); the R5E
head-isolation wall may differ only by the added `--prompt-live:initial` reset. usage: check_v5_identity.py <new> <ref>"""
import sys, pathlib, re
from collections import Counter
sys.path.insert(0, "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X")
from cssindex import rules
A, B = map(pathlib.Path, sys.argv[1:3]); ok = True
def fail(m):
    global ok; ok = False; print("FAIL", m)
MARK_OLD, MARK_NEW = "width:calc(20000px + var(--epoch)*1024px)", "width:calc(20000px + (var(--epoch) - 1 + var(--prompt-live))*1024px)"
ha, hb = (A / "index.html").read_text(), (B / "index.html").read_text()
print(f"index.html: new has {ha.count(MARK_NEW)} new-style / {ha.count(MARK_OLD)} old-style receipt marker(s); ref {hb.count(MARK_NEW)} / {hb.count(MARK_OLD)}")
if ha.replace(MARK_NEW, MARK_OLD) == hb.replace(MARK_NEW, MARK_OLD): print("index.html: IDENTICAL after normalising the receipt marker")
else: fail("index.html differs beyond the receipt marker")
def norm(s):
    s = re.sub(r'url\("(?:\.\./)+', 'url("../', s); return re.sub(r'url\("\.\./(?:(?:R5[HX]|R6[PVX])/)?assets-r5h/', 'url("../AGENT/assets-r5h/', s)
def wall(r):  # the head-isolation wall resets every registered property; drop the one added by v5 so both sides compare equal
    return (r[0], r[1], ";".join(x for x in r[2].split(";") if x != "--prompt-live:initial")) if r[1] == ".head-isolation" else r
ra = [wall((" >> ".join(c), s, d)) for c, s, d in rules(norm((A / "runtime.css").read_text()))]
rb = [wall((" >> ".join(c), s, d)) for c, s, d in rules(norm((B / "runtime.css").read_text()))]
ALLOWED = re.compile(r"(^|[\s>,{(])\.(r8u-|fb-warn|controls|tk-|pg|ld|visible-output|feedback-reader,\.visible-output|controls>label)|^html \.|@property --prompt-live|@keyframes pg-head-|\.tk-editor|\.controls>label| \{--prompt-armed:1$|(^| )\.feedback-scroller \{scrollbar-width:none$")
text = lambda r: r[0] + " " + r[1] + " {" + r[2]
ma, mb = Counter(ra), Counter(rb); extra, missing = ma - mb, mb - ma
print(f"rules: new {len(ra)} vs ref {len(rb)}; only in new {sum(extra.values())}; only in ref {sum(missing.values())}")
for k in list(extra): print("   only in NEW:", str(k)[:240])
for k in list(missing): print("   only in REF:", str(k)[:240])
bad = [k for k in list(extra) + list(missing) if not ALLOWED.search(text(k))]
if bad: fail(f"{len(bad)} differing rule(s) outside the typed-prompt/display layer: {[str(k)[:200] for k in bad[:5]]}")
seq_a = [r for r in ra if r not in extra]; seq_b = [r for r in rb if r not in missing]
print("order of the common rules:", "IDENTICAL" if seq_a == seq_b else "DIFFERS")
if seq_a != seq_b: fail("order differs")
core_a = [r for r in ra if not ALLOWED.search(text(r))]; core_b = [r for r in rb if not ALLOWED.search(text(r))]
print(f"model core rules (outside the allowed layer, wall normalised): {len(core_a)} vs {len(core_b)} — {'IDENTICAL' if core_a == core_b else 'DIFFER'}")
if core_a != core_b: fail("core rules differ")
print("RESULT:", "PASS" if ok else "FAIL")
