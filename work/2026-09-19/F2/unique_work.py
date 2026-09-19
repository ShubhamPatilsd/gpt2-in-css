"""Per-element unique vs shared declaration work in the core subtree (coordinator re-aim).
For every element under div.core-block: matched rules (single-class rules, plain or inside the ACTIVE
container branches --layer:0 / --fvs-write-slot:0 / --pass:1; `.metric i`; #id rules; loop-metric nth-child)
+ inline style. Bytes, var() and calc() counts; 'unique' = inline + id/nth-child rules (one element each);
'shared' = class rules; MPC groups = distinct (matched-rule-set, parent-class) signatures.
Cost model (M1 §8.1/8.3): 4.45 µs/element + 36.5 ns per var()-bearing byte applied; shared rule bytes are
charged once per MPC group (Blink shares the applied result), unique bytes once per element."""
import re, sys, json
from collections import defaultdict, Counter
from html.parser import HTMLParser
from pathlib import Path
W = Path("/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19")
name = sys.argv[1]
css = (W / f"bundles/{name}/runtime.css").read_text(); html = (W / f"bundles/{name}/index.html").read_text()
def inner_rules(css):
    res = {}; ctx = []; i = 0; n = len(css)
    while True:
        j = css.find("{", i)
        if j < 0: break
        k = css.find("}", j + 1); sel = css[i:j].strip().lstrip("}").strip(); j2 = css.find("{", j + 1)
        if j2 != -1 and j2 < k: ctx.append(sel); i = j + 1; continue
        res.setdefault((tuple(ctx), sel), []).append(css[j + 1:k]); i = k + 1
        while i < n and css[i] == "}":
            if ctx: ctx.pop()
            i += 1
    return res
rules = inner_rules(css)
ACTIVE = {"@container corestate style(--layer:0)", "@container fvscache style(--fvs-write-slot:0)", "@container loopcontrol style(--pass:1)", "@container runtime style(--epoch:1)"}
by_class, by_id, misc = defaultdict(list), defaultdict(list), []
for (ctx, sel), bodies in rules.items():
    if any(c.startswith("@") and c not in ACTIVE for c in ctx): continue
    if sel.startswith("@"): continue
    for sel1 in sel.split(","):
        sel1 = sel1.strip()
        body = ";".join(bodies)
        m = re.fullmatch(r"\.([\w-]+)", sel1)
        if m: by_class[m[1]].append(body); continue
        m = re.fullmatch(r"#([\w-]+)", sel1)
        if m: by_id[m[1]].append(body); continue
        m = re.fullmatch(r"\.loop-bank-(\d)>\.loop-scroll>\.loop-track>\.loop-metric:nth-child\((\d+)\)", sel1)
        if m: by_id[f"loop-metric-{m[1]}-{m[2]}"].append(body); continue
        misc.append((sel1, body))
metric_i = ";".join(b for s, b in misc if s == ".metric i")
class P(HTMLParser):
    def __init__(s): super().__init__(); s.stack = []; s.rows = []; s.incore = 0
    def handle_starttag(s, tag, attrs):
        a = dict(attrs); cls = a.get("class", "").split(); idd = a.get("id", ""); style = a.get("style", "")
        parent = s.stack[-1] if s.stack else None
        s.stack.append((tag, cls, idd, style, parent))
        if "core-block" in cls: s.incore = len(s.stack)
        if s.incore: s.rows.append(s.stack[-1])
        if tag in ("set", "meta", "link", "input", "br"): s.stack.pop()
    def handle_startendtag(s, tag, attrs): s.handle_starttag(tag, attrs); 
    def handle_endtag(s, tag):
        if s.stack:
            if s.incore == len(s.stack): s.incore = 0
            s.stack.pop()
p = P(); p.feed(html)
def stats(text): return len(text), text.count("var("), text.count("calc("), text.count("--gelu(")
def sig(row):
    tag, cls, idd, style, parent = row
    return tag + "." + ".".join(re.sub(r"\d+", "N", c) for c in cls)
groups = defaultdict(lambda: dict(n=0, shared=Counter(), unique=Counter(), mpc=set(), decls=0))
def loop_metric_id(row):
    tag, cls, idd, style, parent = row
    if "loop-metric" not in cls or parent is None: return None
    # position among siblings unknown here; count the nth-child rule as unique (1 decl each)
    return "loop-metric-nth"
for row in p.rows:
    tag, cls, idd, style, parent = row
    shared = "".join("".join(by_class[c]) for c in cls)
    if tag == "i" and parent and "metric" in parent[1]: shared += metric_i
    unique = style + "".join(by_id.get(idd, []))
    if "loop-metric" in cls: unique += "--saved-N-N:inherit"
    g = groups[sig(row)]; g["n"] += 1
    for k, v in zip(("bytes", "var", "calc", "fn"), stats(shared)): g["shared"][k] += v
    for k, v in zip(("bytes", "var", "calc", "fn"), stats(unique)): g["unique"][k] += v
    g["mpc"].add((tuple(sorted(cls)), tuple(sorted(parent[1])) if parent else (), bool(style), idd if by_id.get(idd) else ""))
print(f"# {name}: core-block subtree = {len(p.rows)} elements")
print("| element class | n | shared rule B/elem (var,calc,@fn) | unique B/elem (var,calc) | MPC groups | est. µs/pass (floor + unique + shared once per group) |")
print("|---|---:|---:|---:|---:|---:|")
tot = 0
for s, g in sorted(groups.items(), key=lambda kv: -(kv[1]["n"] * 4.45 + kv[1]["unique"]["bytes"] * .0365 + len(kv[1]["mpc"]) * (kv[1]["shared"]["bytes"] / kv[1]["n"]) * .0365)):
    n = g["n"]; sb = g["shared"]["bytes"] / n; ub = g["unique"]["bytes"] / n
    est = n * 4.45 + g["unique"]["bytes"] * .0365 + len(g["mpc"]) * sb * .0365 + g["shared"]["fn"] / n * len(g["mpc"]) * 10
    tot += est
    print(f"| {s} | {n} | {sb:,.0f} ({g['shared']['var']/n:.0f},{g['shared']['calc']/n:.0f},{g['shared']['fn']/n:.0f}) | {ub:,.0f} ({g['unique']['var']/n:.0f},{g['unique']['calc']/n:.0f}) | {len(g['mpc'])} | {est:,.0f} |")
print(f"| **total** | {len(p.rows)} | | | | **{tot/1000:,.1f} ms** |")
