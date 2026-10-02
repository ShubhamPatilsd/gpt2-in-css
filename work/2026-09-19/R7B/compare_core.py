"""R7B identity check: <new> (R7B flags on) vs <ref> (R6X build at the same capacity). Lists EXACTLY what differs.
index.html: after removing the 7th head-row glyph (U+80000+token), the R7B controls/signals and the second SMIL begin
condition, it must be identical. runtime.css: rules (cssindex.rules; url-normalised) are compared as multiset + order after
undoing the three sampling edits inside existing rules (`,NoiseQ` in the two head font lists, the 7th glyph in the 256 fine
strings, the two noise axes on the bank's --head-fvs); every remaining difference must be an R7B rule (allow-list) or the
font-barrier growth (one more face) and is listed. usage: compare_core.py <new> <ref>"""
import sys, pathlib, re
from collections import Counter
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "R6X"))
from cssindex import rules
A, B = map(pathlib.Path, sys.argv[1:3]); ok = True
def fail(m):
    global ok; ok = False; print("FAIL", m)
NOISE = re.compile("[\U00080000-\U0008FFFF]")
# ---- index.html
ha, hb = (A / "index.html").read_text(), (B / "index.html").read_text()
n_glyph = len(NOISE.findall(ha))
na = NOISE.sub("", ha)
na, n_begin = re.subn(r";r7b-prefill-ready-\d+\.animationend\+0\.001s", "", na)
na, n_pre = re.subn(r'<g id="r7b-prefill-ready-\d+"></g>', "", na)
na, n_stop = re.subn(r'<g id="r7b-stop-ready-\d+"></g><g id="r7b-complete-\d+"><set [^>]*/></g>', "", na)
na, n_ctl = re.subn(r'<label>Seed <select id="r7b-seed">.*?</select></label> <label>Sampling <select id="r7b-temp">.*?</select></label> ', "", na)
na, n_out = re.subn(r'<small class="r7b-seed-out"></small>', "", na)
na, n_wit = re.subn(r'<i class="font-witness" style="font-family:NoiseQ;[^"]*">&#x80000;</i>', "", na)
na, n_proof = re.subn(r'<i class="font-proof font-proof-(\d+)"></i>(?=<i class="head-reduction font-all)', lambda m: "" if int(m[1]) == hb.count('class="font-proof font-proof-') else m[0], na)
print(f"index.html: removed {n_glyph} noise glyphs, {n_begin} second begin conditions, {n_pre} prefill signals, {n_stop} stop signal pairs, {n_ctl} control groups, {n_out} readouts, {n_wit} noise witness, {n_proof} proof (font barrier +1 face)")
if na == hb: print("index.html: IDENTICAL after removing the R7B additions")
else:
    i = next((i for i, (x, y) in enumerate(zip(na, hb)) if x != y), min(len(na), len(hb)))
    fail(f"index.html differs beyond the R7B additions at {i}: NEW {na[max(0,i-100):i+150]!r}\n REF {hb[max(0,i-100):i+150]!r}")
# ---- runtime.css
def norm(s):
    s = re.sub(r'url\("(?:\.\./)+', 'url("../', s)
    return re.sub(r'url\("\.\./(?:(?:R5[HX]|R6[PVX]|R7B)/)?assets-r5h/', 'url("../AGENT/assets-r5h/', s)
ca, cb = norm((A / "runtime.css").read_text()), norm((B / "runtime.css").read_text())
edits = Counter()
def undo(decl):
    global edits
    d, n = re.subn(r",NoiseQ\b", "", decl); edits["NoiseQ in font list"] += n
    d, n = re.subn(r',"SEED" var\(--noise-col\),"TEMP" var\(--temp\)', "", d); edits["noise axes on --head-fvs"] += n
    d, n = NOISE.subn("", d); edits["7th glyph in fine strings"] += n
    return d
ra = [(" >> ".join(c), s, undo(d)) for c, s, d in rules(ca)]
rb = [(" >> ".join(c), s, d) for c, s, d in rules(cb)]
print("undone sampling edits inside existing rules:", dict(edits))
ALLOWED = re.compile(r"r7b-|--seed|--temp|--clock|--noise-col|--r7b-n|NoiseQ|\.pg-tok::after|\.pg-lay::after|\.pg::after \{animation:none$|\.full-head \{content-visibility:hidden$|#token-\d+-ack \{animation:none!important|\.status::after \{content:\"Complete • \d+ new tokens|\.pg \{display:none|^body \{animation:r7b-clock|animation-play-state")
BARRIER = re.compile(r"\.font-proof-\d+|\.font-all-|\.font-status|\.ld-probe|\.ld2-fill|\.ld-n::after|@container fontload|\.ld-sum|@font-face")
text = lambda r: r[0] + " " + r[1] + " {" + r[2]
ma, mb = Counter(ra), Counter(rb); extra, missing = ma - mb, mb - ma
print(f"rules: new {len(ra)} vs ref {len(rb)}; only in new {sum(extra.values())}; only in ref {sum(missing.values())}")
groups = Counter()
bad = []
for k in list(extra) + list(missing):
    t = text(k)
    if ALLOWED.search(t): groups["R7B rule: " + re.sub(r"\d+", "N", k[1])[:70] + ("  [ctx " + re.sub(r"\d+(\.\d+)?", "N", k[0])[:60] + "]" if k[0] else "")] += 1
    elif BARRIER.search(t): groups["font barrier (+1 face): " + re.sub(r"\d+", "N", k[1])[:60]] += 1
    else: bad.append(t)
for g, n in sorted(groups.items()): print(f"   {n:5d} x {g}")
if bad: fail(f"{len(bad)} differing rule(s) outside the R7B / font-barrier layer:"); [print("      ", b[:300]) for b in bad[:12]]
seq_a = [r for r in ra if r not in extra]; seq_b = [r for r in rb if r not in missing]
print("order of the common rules:", "IDENTICAL" if seq_a == seq_b else "DIFFERS")
if seq_a != seq_b: fail("order differs")
core_a = [r for r in ra if not ALLOWED.search(text(r)) and not BARRIER.search(text(r))]; core_b = [r for r in rb if not ALLOWED.search(text(r)) and not BARRIER.search(text(r))]
print(f"model core rules (outside the R7B + font-barrier layers, sampling edits undone): {len(core_a)} vs {len(core_b)} — {'IDENTICAL' if core_a == core_b else 'DIFFER'}")
if core_a != core_b: fail("core rules differ")
print("RESULT:", "PASS" if ok else "FAIL")
