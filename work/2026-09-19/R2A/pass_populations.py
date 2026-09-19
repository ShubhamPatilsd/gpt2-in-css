#!/usr/bin/env python3
"""R2A: match UpdateLayoutTree elementCount signatures to DOM populations.
Gate-aware subtree sizes: an element with a closed content-visibility gate class contributes itself but not its
descendants; display:none subtrees contribute nothing. For every element we print the visible subtree size
under several gate states, and search single roots / pairs of sibling-ish roots that hit the target counts.
usage: pass_populations.py index.html
"""
import sys, collections, itertools
from html.parser import HTMLParser
path = sys.argv[1]
TARGETS = [126, 357, 368, 484, 485, 487, 780, 784, 1438, 1553, 2326, 2917, 2934, 3089, 6919, 51247]
class N:
    __slots__ = ("tag","attrs","children","parent","depth","cls","id")
    def __init__(s, tag, attrs, parent, depth):
        s.tag, s.attrs, s.parent, s.depth = tag, attrs, parent, depth; s.children = []
        s.cls = set((attrs.get("class") or "").split()); s.id = attrs.get("id")
class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.root = N("#root", {}, None, -1); s.cur = s.root; s.all = []
    def handle_starttag(s, tag, attrs):
        a = dict(attrs); node = N(tag, a, s.cur, s.cur.depth + 1); s.cur.children.append(node); s.all.append(node)
        if tag not in ("meta","input","link","br","set","animate","use","path","rect","circle","stop"): s.cur = node
    def handle_startendtag(s, tag, attrs):
        a = dict(attrs); node = N(tag, a, s.cur, s.cur.depth + 1); s.cur.children.append(node); s.all.append(node)
    def handle_endtag(s, tag):
        c = s.cur
        while c is not s.root and c.tag != tag: c = c.parent
        if c is not s.root: s.cur = c.parent
p = P(); p.feed(open(path, encoding="utf-8", errors="replace").read())
print("elements", len(p.all))
GATES = ["shared-qkv-gate", "fvs-score-gate", "cache-bridge-gate", "shared-attn-gate", "shared-fc-gate", "shared-proj-gate", "loop-compute", "full-head", "core-block", "input-ready"]
NONE = ["reused-final-export"]  # display:none except layer 11
def label(n):
    return f"d{n.depth} {n.tag}{'#'+n.id if n.id else ''}{'.'+'.'.join(sorted(n.cls)[:3]) if n.cls else ''}"
def size(n, closed, none):
    """visible subtree size incl. n under the set of closed gate classes"""
    if n.cls & none: return 0
    if n.cls & closed: return 1
    return 1 + sum(size(c, closed, none) for c in n.children)
# named nodes
byname = {}
for n in p.all:
    for c in n.cls: byname.setdefault(c, []).append(n)
    if n.id: byname.setdefault("#" + n.id, []).append(n)
states = {
  "all-closed": set(GATES) - {"core-block", "input-ready"},
  "qkv-open": {"fvs-score-gate", "cache-bridge-gate", "shared-attn-gate", "shared-fc-gate", "shared-proj-gate", "full-head"},
  "qkv+score-open": {"cache-bridge-gate", "shared-attn-gate", "shared-fc-gate", "shared-proj-gate", "full-head"},
  "..+bridge-open": {"shared-attn-gate", "shared-fc-gate", "shared-proj-gate", "full-head"},
  "..+attn-open": {"shared-fc-gate", "shared-proj-gate", "full-head"},
  "..+fc-open": {"shared-proj-gate", "full-head"},
  "all-open-but-head": {"full-head"},
  "all-open": set(),
  "loop-compute-closed": {"loop-compute", "full-head"},
}
roots = ["core-controller", "core-block", "loop-reader", "loop-input", "loop-signals", "loop-compute", "reused-input", "shared-ln1", "shared-qkv", "shared-qkv-c0", "shared-qkv-c4", "shared-qkv-receipt", "shared-qkv-gate",
         "fvs-query", "fvs-bank-0", "fvs-bank-11", "fvs-score-reader", "fvs-score-receipt", "fvs-score-gate", "fvs-softmax", "cache-bridge-source",
         "cache-bridge-c0", "cache-bridge-receipt", "cache-bridge-gate", "shared-attn", "shared-attn-c0", "shared-attn-receipt", "shared-attn-gate", "shared-ln2", "shared-fc", "shared-fc-c0", "shared-fc-c5", "shared-fc-receipt", "shared-fc-gate",
         "shared-proj", "shared-proj-c0", "shared-proj-receipt", "shared-proj-gate", "reused-output", "reused-final-export", "loop-bank-1", "loop-bank-0",
         "b11-bridge-c0", "b11-bridge-receipt", "b11-bridge-gate", "#core-result", "final-normalization", "head-input-bank", "head-isolation", "full-head", "head-coarse-reader", "head-fine",
         "detached-head-reader", "detached-head-state", "token-slot-8", "token-slot-1", "token-state", "feedback-reader", "feedback-select", "embedding-source", "embedding-scroller", "embedding-consumer-0", "embedding-receipt", "#embedding-result", "position-embedding", "font-status", "controls"]
hdr = ["root"] + list(states)
rows = []
for r in roots:
    ns = byname.get(r)
    if not ns: continue
    n = ns[0]
    rows.append([label(n)] + [size(n, st, set(NONE)) for st in states.values()])
w = max(len(r[0]) for r in rows)
print("\nvisible subtree sizes (element itself + descendants not under a closed gate; .reused-final-export display:none):")
print(" ".join(["root".ljust(w)] + [h.rjust(16) for h in list(states)]))
for r in rows: print(" ".join([r[0].ljust(w)] + [str(v).rjust(16) for v in r[1:]]))
# search: which (root, state) sizes equal a target; also combos of two disjoint roots (head + token slots etc.)
print("\nexact hits:")
allsz = {}
for r in rows:
    for st, v in zip(states, r[1:]):
        allsz.setdefault(v, []).append((r[0], st))
for t in TARGETS:
    if t in allsz: print(f"  {t}: {allsz[t][:6]}")
print("\nnear hits (|delta|<=40) for unmatched targets:")
for t in TARGETS:
    if t in allsz: continue
    near = sorted(((abs(v - t), v, r[0], st) for r in rows for st, v in zip(states, r[1:]) if abs(v - t) <= 40))[:6]
    print(f"  {t}: {near}")
# small subtrees of interest: sizes of svg.loop-signals, detached head reader, body-level misc
for name in ("loop-signals", "detached-head-reader", "font-status", "controls", "native-signals", "feedback-reader"):
    for n in byname.get(name, [])[:1]: print(name, "size", size(n, set(), set()), "children", len(n.children))
# body direct children summary
body = byname["body"][0] if "body" in byname else p.all[1]
for n in p.all:
    if n.tag == "body": body = n; break
print("\nbody children (label, full size):")
agg = collections.Counter()
for c in body.children:
    agg[(c.tag, ".".join(sorted(c.cls)[:2]))] += size(c, set(), set())
for k, v in agg.most_common(20): print("  ", k, v)
