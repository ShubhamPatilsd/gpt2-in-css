"""R4T offline check: bundle (R4T_CONSUMER_CHUNK=64) vs ref (chunk 0 = combined4 recipe) built from the same tools.
Verifies: (1) max animations per element ≤ 64 in the bundle except .fvs-score-reader (96) / single-animation stamps; (2) the multiset of
(animation-name, timeline, declaration) triples over all consumer chunks is identical to the ref's (same animations, same decode formulas, same
timing properties); (3) the HTML is identical once the extra consumer wrapper elements are collapsed; (4) manifest differs only in
r4tConsumerChunk; (5) font-witnesses identical; (6) the CSS is identical outside the consumer rules and the R2G loop chain.
usage: offline_check_r4t.py <bundle-dir> <ref-dir>"""
import json, re, sys, collections
from html.parser import HTMLParser

B, R = sys.argv[1], sys.argv[2]
css_b, css_r = open(f"{B}/runtime.css").read(), open(f"{R}/runtime.css").read()
ok = True
FWD = collections.Counter()
def fail(msg):
    global ok; ok = False; print("FAIL:", msg)

CONSUMER = re.compile(r"\.((?:shared-(?:qkv|attn|fc)|cache-bridge|b\d+-bridge|embedding-consumer|loop-reader)(?:-c\d+|-\d+)?)\{([^{}]*animation-name:[^{}]*)\}")
def consumer_rules(css):
    out = {}
    for m in CONSUMER.finditer(css):
        out.setdefault(m.group(1), []).append(m.group(2))
    return out
def explode(rules):
    """-> Counter of (stem, keyframe, timeline, per-animation declarations) and Counter of shared property strings per stem"""
    triples = collections.Counter(); shared = collections.Counter()
    for cls, bodies in rules.items():
        stem = re.sub(r"-c\d+$|-\d+$", "", cls)
        for body in bodies:
            decls = dict(d.split(":", 1) for d in body.split(";") if d and ":" in d)
            names = decls.pop("animation-name").split(","); tls = decls.pop("animation-timeline").split(",")
            if len(names) != len(tls): fail(f"{cls}: {len(names)} names vs {len(tls)} timelines")
            other = {k: v for k, v in decls.items() if k.startswith("animation-")}
            values = {k: v for k, v in decls.items() if not k.startswith("animation-") and v != "inherit"}  # chunk forwarding (--lp-*:inherit) is structural
            FWD[stem] += sum(1 for v in decls.values() if v == "inherit")
            for n, t in zip(names, tls): triples[(stem, n, t)] += 1
            for k, v in values.items(): triples[(stem, "decl", k, v)] += 1
            shared[(stem, tuple(sorted(other.items())))] += len(bodies) and 1
    return triples, shared
rb, rr = consumer_rules(css_b), consumer_rules(css_r)
tb, sb = explode(rb); tr_, sr = explode(rr)
if tb != tr_:
    d1 = tb - tr_; d2 = tr_ - tb; fail(f"consumer animation/declaration multisets differ: bundle-only {list(d1.items())[:3]} ref-only {list(d2.items())[:3]}")
if set(sb) != set(sr): fail(f"animation timing properties differ: {set(sb) ^ set(sr)}")
# (1) max animations per element
mx = collections.Counter()
for m in re.finditer(r"([^{}]{1,160})\{animation-name:([^;}]+)", css_b):
    n = len(m.group(2).split(",")); sel = m.group(1).strip()
    if n > 1: mx[re.sub(r"\d+", "N", sel)] = max(mx[re.sub(r"\d+", "N", sel)], n)
print("max animations per element (bundle):", dict(mx))
import os
CAP = int(os.environ.get("R4T_CHECK_CAP", "64")); SITES = set(os.environ.get("R4T_CHUNK_SITES", "matvec,bridge,loop,embedding").split(","))
UNCHUNKED = {".fvs-score-reader", ".feedback-reader"} | ({".loop-reader"} if "loop" not in SITES else set()) | ({".embedding-consumer-N"} if "embedding" not in SITES else set()) | ({".cache-bridge-cN", ".bN-bridge-cN"} if "bridge" not in SITES else set())
for sel, n in mx.items():
    if n > CAP and sel not in UNCHUNKED: fail(f"{sel} carries {n} animations (cap {CAP}; unchunked sites {sorted(UNCHUNKED)})")
mr = collections.Counter()
for m in re.finditer(r"([^{}]{1,160})\{animation-name:([^;}]+)", css_r):
    n = len(m.group(2).split(",")); sel = re.sub(r"\d+", "N", m.group(1).strip())
    if n > 1: mr[sel] = max(mr[sel], n)
print("max animations per element (ref):   ", dict(mr))
print("inherit-forwarding declarations on chunk elements (bundle):", dict(FWD))
print("consumer elements bundle/ref:", sum(len(v) for v in rb.values()), sum(len(v) for v in rr.values()))
# (6) css outside consumer rules
strip = lambda css: re.sub(r"\.loop-reader-c\d+\)\s*>\s*:where\(", "", CONSUMER.sub("", css))
sb_, sr_ = strip(css_b), strip(css_r)
if sb_ != sr_:
    i = next((k for k in range(min(len(sb_), len(sr_))) if sb_[k] != sr_[k]), min(len(sb_), len(sr_)))
    fail(f"non-consumer CSS differs at {i}: bundle …{sb_[max(0,i-80):i+120]!r} ref …{sr_[max(0,i-80):i+120]!r}")
else: print("non-consumer CSS identical (%d B ref, %d B bundle incl. consumer rules)" % (len(css_r), len(css_b)))
# (3) html modulo consumer wrappers
VOID = {"br", "meta", "link", "input", "img", "hr", "set", "option"}
class P(HTMLParser):
    def __init__(s): super().__init__(); s.out = []; s.n = 0; s.stack = []
    def handle_starttag(s, tag, attrs):
        d = dict(attrs); c = d.get("class", ""); s.n += 1
        skip = bool(re.fullmatch(r"(shared-(?:qkv|attn|fc)|cache-bridge|b\d+-bridge)-c\d+|embedding-consumer-\d+|loop-reader-c\d+", c))
        if tag not in VOID: s.stack.append(skip)
        if skip: return
        s.out.append(("<", tag, tuple(sorted(attrs))))
    def handle_endtag(s, tag):
        skip = s.stack.pop() if s.stack else False
        if not skip: s.out.append((">", tag))
    def handle_data(s, data):
        if data.strip(): s.out.append(("t", data.strip()))
pb, pr = P(), P(); pb.feed(open(f"{B}/index.html").read()); pr.feed(open(f"{R}/index.html").read())
print("elements bundle/ref:", pb.n, pr.n, "delta", pb.n - pr.n)
if pb.out != pr.out:
    k = next((k for k in range(min(len(pb.out), len(pr.out))) if pb.out[k] != pr.out[k]), None); fail(f"HTML differs (modulo consumer wrappers) at token {k}: {pb.out[k] if k is not None else ''} vs {pr.out[k] if k is not None else ''}")
else: print("HTML identical modulo consumer wrapper elements")
mb, mr_ = json.load(open(f"{B}/manifest.json")), json.load(open(f"{R}/manifest.json"))
dk = {k for k in set(mb) | set(mr_) if mb.get(k) != mr_.get(k)}
print("manifest keys differing:", {k: (mr_.get(k), mb.get(k)) for k in dk})
if dk - {"r4tConsumerChunk", "r4tChunkSites"}: fail("manifest differs beyond r4tConsumerChunk/r4tChunkSites")
_norm = lambda t: re.sub(r"work/2026-09-19/[A-Za-z0-9]+/", "work/2026-09-19/X/", json.dumps(json.load(open(t)), sort_keys=True))  # keys carry the tools dir
fw = _norm(f"{B}/font-witnesses.json") == _norm(f"{R}/font-witnesses.json")
print("font-witnesses identical (modulo tools dir):", fw, len(json.load(open(f"{B}/font-witnesses.json")))); ok &= fw
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
