#!/usr/bin/env python3
"""R2G: build a fixture from the REAL combined bundle: the .core-controller subtree (truncated below the qkv gate)
with every style rule of runtime.css whose selector targets those elements, keeping @container wrappers,
plus all @property / @keyframes / @font-face / html{timeline-scope}.  Body-level siblings are replaced by fillers
(head 51,149 <i>, token chain) so :has() traversals see the demo's sizes.  Fonts resolve to the bundle's files.

Pages (same HTML, different mutation lists):
  real-cap   traced = #loop-captured-k.done  (frame F, the 485 pass)
  real-adv   traced = #loop-advanced-k.done  (frame A's controller part)
  real-cap-nocore  same CSS but the compute subtree removed below .loop-compute (ablation)
"""
import json, os, re, sys
from dataclasses import asdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen  # noqa: E402

B = "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
css = open(f"{B}/runtime.css").read()
html = open(f"{B}/index.html").read()

# ---------------------------------------------------------------- DOM: .core-controller subtree, cut inside .shared-qkv-gate
i0 = html.find('<div class="core-controller">')
# find the matching close by tag counting (only div/svg/g/i/span/section/output/label are used inside)
depth = 0; pos = i0; end = None
for m in re.finditer(r'<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>', html[i0:]):
    tag = m.group(2)
    if tag in ("set", "meta", "link", "input", "br", "img") or m.group(4) == "/":
        continue
    depth += -1 if m.group(1) == "/" else 1
    if depth == 0:
        end = i0 + m.end(); break
core = html[i0:end]
gate = core.find('class="shared-qkv-gate"')
if gate < 0:
    raise SystemExit("qkv gate not found")
g_open = core.find(">", gate) + 1
# find the gate's close
depth = 0; gend = None
for m in re.finditer(r'<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>', core[g_open - 1:]):
    tag = m.group(2)
    if tag in ("set", "meta", "link", "input", "br", "img") or m.group(4) == "/":
        continue
    depth += -1 if m.group(1) == "/" else 1
    if depth == 0:
        gend = g_open - 1 + m.start(); break
# splice the loop banks (#reused-result subtree: .reused-output > .loop-bank-1 > ... > .loop-bank-0 > #loop-result) into the
# (forced-open) qkv gate so the reader's 1,538 timeline subjects and the --loop-held-dependent banks exist, as at frame F
r0 = core.find('<div class="reused-output" id="reused-result">')
depth = 0; rend = None
for m in re.finditer(r'<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>', core[r0:]):
    if m.group(2) in ("set", "meta", "link", "input", "br", "img") or m.group(4) == "/":
        continue
    depth += -1 if m.group(1) == "/" else 1
    if depth == 0:
        rend = r0 + m.end(); break
reused = core[r0:rend]
print("reused-result subtree elements", len(re.findall(r'<[a-zA-Z]', reused)))
core_cut = core[:g_open] + reused + core[gend:]
print("core subtree bytes", len(core), "-> truncated", len(core_cut), "elements", len(re.findall(r'<[a-zA-Z]', core_cut)))

# ---------------------------------------------------------------- CSS: style rules targeting the kept elements
KEEP = re.compile(r'\.(core-controller|core-block|loop-reader|loop-input|loop-signals|loop-compute|loop-bank-\d|loop-scroll|loop-track|loop-metric|'
                  r'reused-input|core-reset|core-valid|pass-reader|epoch-reader|shared-ln1|shared-qkv(-c\d|-receipt|-gate)?|scroller|track|metric|'
                  r'reused-output|shared-proj-receipt|shared-attn-receipt|shared-fc-receipt|cache-bridge-receipt|fvs-score-receipt|fvs-query|fvs-score-reader)\b'
                  r'|#loop-|#reused-|#run|#fonts-|#token-|^body|^html|\.native-signals|\.detached|\.token-')
rules = []  # (wrappers tuple, selector, body)
stack = []
prev = 0
for m in re.finditer(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[{}]', css):
    c = m.group(0)
    if c == "{":
        head = css[prev:m.start()].strip(); prev = m.end()
        stack.append([head, m.end()])
    elif c == "}":
        head, start = stack.pop()
        body = css[start:m.start()]
        prev = m.end()
        if head.startswith("@property") or head.startswith("@keyframes") or head.startswith("@font-face") or head.startswith("@counter-style"):
            if not stack:
                rules.append(("atrule", head, body))
            continue
        if head.startswith("@"):
            continue  # container/media wrapper closing
        wrappers = tuple(h for h, _ in stack if h.startswith("@"))
        if any(w.startswith("@keyframes") for w in wrappers):
            continue
        if KEEP.search(head):
            rules.append((wrappers, head, body))
print("rules kept", len(rules))
# keep only layer-0 corestate blocks (the demo runs one layer at a time) and all loopcontrol/loopreceipt/runtime wrappers
def keep_wrapper(ws):
    for w in ws:
        mm = re.match(r"@container corestate style\(--layer:(\d+)\)", w)
        if mm and mm.group(1) != "0":
            return False
        mm = re.match(r"@container runtime style\(--epoch:(\d+)\)", w)
        if mm and mm.group(1) != "1":
            return False
    return True
out = []
sizes = {}
for ws, head, body in rules:
    if ws == "atrule":
        out.append(f"{head}{{{body}}}")
        sizes["atrules"] = sizes.get("atrules", 0) + len(head) + len(body)
        continue
    if not keep_wrapper(ws):
        continue
    text = f"{head}{{{body}}}"
    for w in reversed(ws):
        text = f"{w}{{{text}}}"
    out.append(text)
    key = head[:40]
    sizes[key] = sizes.get(key, 0) + len(text)
real_css = "".join(out)
# fonts: rewrite relative url("...") to the bundle directory
real_css = re.sub(r'url\("(?!file:|http|data:)([^"]+)"\)', lambda m: f'url("file://{B}/{m.group(1)}")', real_css)
print("css bytes", len(real_css))
for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])[:15]:
    print(f"  {v:9d} {k}")

# ---------------------------------------------------------------- page
body = (gen.native_signals() + '<div class="font-status"><svg class="native-signals"><g id="fonts-detected" class="done"></g><g id="fonts-loaded" class="done"></g></svg></div>'
        + '<div class="feedback-reader"><div class="feedback-select"><div class="embedding-source"><div class="position-embedding">'
        + core_cut + f'<div class="b11-bridge-c0"><div class="full-head">{gen.filler(gen.HEAD_FILL)}</div></div>'
        + '</div></div></div></div>' + gen.token_chain(True))
# the demo's <set> elements are SMIL-wired; make them inert so the harness controls .done (same elements)
body = re.sub(r'begin="loop-(ready|ack)-\d+\.animationend\+0\.001s"', 'begin="indefinite"', body)
# embed-ready gate: layer-0 rule makes --loop-ready:var(--embed-ready); force ready like the demo after embedding
extra_css = (".position-embedding{--embed-ready:1}.full-head{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
             ".shared-qkv-gate{content-visibility:visible!important}")  # all stage gates are open at frame F
page_css = real_css + extra_css
os.makedirs(OUT, exist_ok=True)
pages = []
for pid, kind, cut_core in (("real-cap", "cap", False), ("real-adv", "adv", False), ("real-cap-nocore", "cap", True)):
    b = body
    if cut_core:
        # remove everything inside .loop-compute
        j = b.find('<div class="loop-compute">'); jj = b.find(">", j) + 1
        depth = 0; kend = None
        for m in re.finditer(r'<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>', b[jj - 1:]):
            if m.group(2) in ("set", "meta", "link", "input", "br", "img") or m.group(4) == "/":
                continue
            depth += -1 if m.group(1) == "/" else 1
            if depth == 0:
                kend = jj - 1 + m.start(); break
        b = b[:jj] + b[kend:]
    muts = []
    for k in range(1, 4):
        if kind == "cap":
            muts += [({"selector": "#loop-ready-1", "name": "class", "value": "warm"} if k == 1 else
                      {"selector": f"#loop-advanced-{k - 1}", "name": "class", "value": "done"}),
                     {"selector": f"#loop-captured-{k}", "name": "class", "value": "done"}]
        else:
            muts += [{"selector": f"#loop-captured-{k}", "name": "class", "value": "done"},
                     {"selector": f"#loop-advanced-{k}", "name": "class", "value": "done"}]
    p = gen.Page(id=pid, family="real", title=f"R2G {pid}", params={"kind": kind, "core": not cut_core}, target=".core-controller",
                 verify_selector=".core-controller", verify_property="--loop-captured-pass" if kind == "cap" else "--pass",
                 hypothesis="real bundle CSS/DOM of the controller region", mutations=muts)
    pages.append(gen.write_page(OUT, p, page_css, b))
man_path = os.path.join(OUT, "manifest.json")
man = json.load(open(man_path))
ids = {p["id"] for p in man["pages"]}
man["pages"] = [p for p in man["pages"] if p["id"] not in {q.id for q in pages}] + [asdict(p) for p in pages]
json.dump(man, open(man_path, "w"), indent=1)
for p in pages:
    print(f"{p.id:18s} {p.bytes / 1e6:6.2f} MB elements~{p.element_count_hint}")
