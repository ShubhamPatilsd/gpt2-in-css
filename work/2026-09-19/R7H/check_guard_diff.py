"""R7H: <on> vs <ref> bundle. index.html must differ only by the two guard elements; the css rule multiset must differ only by the guard
rules (allow-list: --fb-*, fbcal/fbecho keyframes, --feedback-tcal, the two extended animation lists, the html timeline-scope list, .fb-warn,
.feedback-metric-cal, @container … --fb-… gates); font-witnesses.json identical. usage: check_guard_diff.py <on> <ref>"""
import sys, pathlib, re, json
from collections import Counter
sys.path.insert(0, "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X")
from cssindex import rules
A, B = map(pathlib.Path, sys.argv[1:3]); ok = True
def fail(m):
    global ok; ok = False; print("FAIL", m)
ha, hb = (A / "index.html").read_text(), (B / "index.html").read_text()
hn = ha.replace('<i class="feedback-metric feedback-metric-cal"></i>', "").replace('<small class="fb-warn"></small>', "")
print("index.html:", "identical after removing the 2 guard elements" if hn == hb else "DIFFERS beyond the guard elements", f"({len(ha)} vs {len(hb)} B; cal metric x{ha.count('feedback-metric-cal')}, fb-warn x{ha.count('fb-warn')})")
if hn != hb: fail("html")
flat = lambda css: [" ".join(c) + ("{" if c else "") + h + "{" + d + "}" + ("}" if c else "") for c, h, d in rules(css)]
ra, rb = flat((A / "runtime.css").read_text()), flat((B / "runtime.css").read_text())
ca, cb = Counter(ra), Counter(rb)
only_a = list((ca - cb).elements()); only_b = list((cb - ca).elements())
GUARD = re.compile(r"--fb-|fbcal|fbecho|--feedback-tcal|\.fb-warn|\.feedback-metric-cal|html\{timeline-scope:|\.feedback-reader\{animation-name:|\.token-state\{animation-name:|^\.head-isolation\{")
bad_a = [r for r in only_a if not GUARD.search(r)]
# modified (not new) rules: the html timeline-scope list, the extended .feedback-reader animation list, and the R5E head-isolation wall
# (it resets every registered property, so it now also resets the 35 non-inherited --fb-* numbers — the v5 `--prompt-live:initial` precedent)
MOD = (".head-isolation{", "html{timeline-scope:", ".feedback-reader{animation-name:")
bad_b = [r for r in only_b if not r.startswith(MOD)]
print(f"rules: on {len(ra)} ref {len(rb)}; only-in-on {len(only_a)} (non-guard {len(bad_a)}), only-in-ref {len(only_b)} (unexpected {len(bad_b)})")
for r in bad_a[:5]: print("  unexpected new:", r[:160])
for r in bad_b[:5]: print("  unexpected missing:", r[:160])
if bad_a or bad_b: fail("css")
kinds = Counter(("@property" if "@property" in r[:12] else "@keyframes" if "@keyframes" in r[:12] else "@container" if "@container" in r[:12] else r.split("{")[0][:40]) for r in only_a)
print("new rules by kind:", dict(kinds))
# order: the guard rules are appended right after feedback()'s control css; everything else keeps its relative order
da, db = set(ca - cb), set(cb - ca)
ra_wo = [r for r in ra if r not in da]; rb_wo = [r for r in rb if r not in db]
print("relative order of shared rules:", "identical" if ra_wo == rb_wo else "DIFFERS")
if ra_wo != rb_wo: fail("order")
for f in ("font-witnesses.json",):
    norm = lambda t: re.sub(r"/work/2026-09-19/R[0-9A-Z]+/", "/work/2026-09-19/AGENT/", t)  # witness keys are font paths through the agent dir's symlinks
    same = norm((A / f).read_text()) == norm((B / f).read_text()); print(f, "identical (agent-dir path normalised)" if same else "DIFFERS")
    if not same: fail(f)
ma, mb = json.loads((A / "manifest.json").read_text()), json.loads((B / "manifest.json").read_text())
diff = [k for k in set(ma) | set(mb) if ma.get(k) != mb.get(k)]; print("manifest keys differing:", diff)
print("RESULT:", "PASS" if ok else "FAIL")
