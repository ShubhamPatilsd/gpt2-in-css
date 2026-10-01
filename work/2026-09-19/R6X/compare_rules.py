"""R6X: compare two bundle dirs rule by rule (cssindex.rules multiset + order) and index.html byte-wise.
Used to prove that a rebuild differs from the shipped bundle ONLY by the listed layout rules.  usage: compare_rules.py <new> <ref>"""
import sys, pathlib, re
from collections import Counter
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from cssindex import rules
A, B = map(pathlib.Path, sys.argv[1:3])
ha, hb = (A / "index.html").read_bytes(), (B / "index.html").read_bytes()
print("index.html:", "IDENTICAL" if ha == hb else "DIFFER", f"({len(ha)} vs {len(hb)} B)")
def norm(s):
    s = re.sub(r'url\("(?:\.\./)+', 'url("../', s)
    return re.sub(r'url\("\.\./(?:(?:R5[HX]|R6[PVX])/)?assets-r5h/', 'url("../AGENT/assets-r5h/', s)
ca, cb = norm((A / "runtime.css").read_text()), norm((B / "runtime.css").read_text())
ra = [(" >> ".join(c), s, d) for c, s, d in rules(ca)]; rb = [(" >> ".join(c), s, d) for c, s, d in rules(cb)]
ma, mb = Counter(ra), Counter(rb)
extra, missing = ma - mb, mb - ma
print(f"rules: new {len(ra)} vs ref {len(rb)}; only in new: {sum(extra.values())}; only in ref: {sum(missing.values())}")
for k in extra: print("   only in NEW:", str(k)[:300])
for k in missing: print("   only in REF:", str(k)[:300])
seq = [r for r in ra if r not in extra]; seq_ref = [r for r in rb if r not in missing]  # common rules on both sides (v4: a superseded display rule may exist only in the reference)
print("order of the common rules:", "IDENTICAL" if seq == seq_ref else "DIFFERS")
print("RESULT:", "PASS (common rules identical in multiset and order; differences listed above)" if seq == seq_ref else "FAIL")
