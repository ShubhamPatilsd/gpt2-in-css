"""R7B: print the ancestor chain (tag.class#id) of selected elements in a built index.html (R5E's _Dom parser)."""
import sys
sys.path.insert(0, sys.argv[2] if len(sys.argv) > 2 else "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X/tools")
from r5e_dead_weight import _Dom, _ancestors_or_self
page = open(sys.argv[1]).read()
d = _Dom(); d.feed(page); nodes = d.nodes
def show(pred, label, limit=1):
    hits = [i for i, n in enumerate(nodes) if pred(n)]
    print(f"\n== {label}: {len(hits)} element(s)")
    for i in hits[:limit]:
        chain = _ancestors_or_self(nodes, i)[::-1]
        print(" > ".join(f"{t}" + "".join("." + c for c in sorted(cl)[:2]) + (f"#{idv}" if idv else "") for t, cl, idv, st, p in chain))
        print(f"  depth {len(chain)}; inline style of target: {nodes[i][3][:120]!r}")
show(lambda n: "head-input-bank" in n[1], ".head-input-bank")
show(lambda n: n[0] == "svg" and "loop-signals" in n[1], "svg.loop-signals")
show(lambda n: n[2] == "token-1-captured", "#token-1-captured")
show(lambda n: "pg" in n[1] and n[0] == "div", ".pg")
show(lambda n: "status" in n[1], ".status")
show(lambda n: "core-reset" in n[1], ".core-reset")
show(lambda n: "core-controller" in n[1], ".core-controller")
show(lambda n: "final-normalization" in n[1], ".final-normalization")
show(lambda n: n[2] == "run-latched", "#run-latched")
show(lambda n: n[2] == "eos-ready", "#eos-ready")
show(lambda n: "reused-final-export" in n[1], ".reused-final-export")
