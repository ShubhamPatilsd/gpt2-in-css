#!/usr/bin/env python3
"""R5A census of bundles/combined7: DOM elements per class/subtree (index.html) + CSS feature counts (runtime.css) + font bytes.
usage: census.py <bundle_dir> <out_json>
"""
import sys, re, os, json, collections
from html.parser import HTMLParser
bundle = os.path.abspath(sys.argv[1]); out_json = sys.argv[2]
html = open(os.path.join(bundle, "index.html"), encoding="utf-8").read()
css = open(os.path.join(bundle, "runtime.css"), encoding="utf-8").read()
norm = lambda s: re.sub(r"\d+", "N", s)

# ---------------- DOM ----------------
VOID = {"meta", "link", "input", "br", "img", "hr", "set", "animate"}
class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack = []; self.nodes = []  # (tag, classes, id, depth, parent_idx, style_bytes)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); cls = (a.get("class") or "").split(); depth = len(self.stack)
        parent = self.stack[-1] if self.stack else -1
        idx = len(self.nodes)
        self.nodes.append([tag, cls, a.get("id"), depth, parent, len(a.get("style") or ""), 0])
        if tag not in VOID: self.stack.append(idx)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID: self.stack.pop()
    def handle_endtag(self, tag):
        # pop to matching tag
        for i in range(len(self.stack) - 1, -1, -1):
            if self.nodes[self.stack[i]][0] == tag:
                del self.stack[i:]; break
p = P(); p.feed(html); nodes = p.nodes
N = len(nodes)
# subtree sizes (descendants incl. self)
sub = [1] * N
for i in range(N - 1, 0, -1):
    par = nodes[i][4]
    if par >= 0: sub[par] += sub[i]
depths = [n[3] for n in nodes]
by_tag = collections.Counter(n[0] for n in nodes)
by_class = collections.Counter()
by_class_norm = collections.Counter()
style_bytes_by_class = collections.Counter()
for n in nodes:
    key = " ".join(n[1]) or f"<{n[0]}>"
    by_class[key] += 1; by_class_norm[norm(key)] += 1
    style_bytes_by_class[norm(key)] += n[5]
# subtree census: for each element with a class, if its normalised class pattern is "subtree-like" report descendants; we report the
# elements whose subtree is >= 200 and whose ancestors don't share the same normalised class (top of a family).
fam_top = collections.defaultdict(lambda: [0, 0, 0])  # normclass -> [count of roots, total descendants, max depth]
for i, n in enumerate(nodes):
    if sub[i] < 100: continue
    key = norm(" ".join(n[1]) or f"<{n[0]}>")
    par = n[4]
    if par >= 0 and norm(" ".join(nodes[par][1]) or f"<{nodes[par][0]}>") == key: continue
    fam_top[key][0] += 1; fam_top[key][1] += sub[i] - 1; fam_top[key][2] = max(fam_top[key][2], n[3])
# top-level children of body and their subtree sizes
body = next(i for i, n in enumerate(nodes) if n[0] == "body")
top = [(i, " ".join(nodes[i][1]) or f"<{nodes[i][0]}>" + (f"#{nodes[i][2]}" if nodes[i][2] else ""), sub[i]) for i in range(N) if nodes[i][4] == body]
# leaf-ish populations: elements with no children
leaves = sum(1 for i in range(N) if sub[i] == 1)
# elements by depth histogram
depth_hist = collections.Counter(depths)
# ids
ids = [n[2] for n in nodes if n[2]]
# nested-chunk / wrapper families: classes containing '-c' followed by digits
dom = {"elements": N, "leaves": leaves, "max_depth": max(depths), "mean_depth": round(sum(depths) / N, 1),
       "by_tag": by_tag.most_common(), "ids": len(ids),
       "by_class_norm_top": by_class_norm.most_common(120),
       "inline_style_bytes_total": sum(n[5] for n in nodes),
       "inline_style_bytes_by_class_top": style_bytes_by_class.most_common(40),
       "family_roots": sorted(((k, v[0], v[1], v[2]) for k, v in fam_top.items()), key=lambda r: -r[2])[:80],
       "body_children": top, "depth_hist": sorted(depth_hist.items())}

# ---------------- CSS ----------------
# split top-level blocks: iterate with a brace counter; capture prelude and body for depth-1 rules; for @-rules with nested blocks keep nesting
rules = []  # (prelude, body, nesting_prelude)
i = 0; L = len(css); depth = 0; start = 0; stack = []
prelude_start = 0
while i < L:
    c = css[i]
    if c == '"':
        j = css.find('"', i + 1)
        while j > 0 and css[j-1] == "\\": j = css.find('"', j + 1)
        i = j + 1; continue
    if c == "{":
        pre = css[prelude_start:i].strip()
        stack.append((pre, i + 1)); depth += 1; i += 1; prelude_start = i; continue
    if c == "}":
        pre, bstart = stack.pop(); depth -= 1
        body = css[bstart:i]
        # body without nested blocks: only declarations text = remove content of nested {...} already consumed -> approximate: if body contains '{', declarations are before first '{'
        parents = [s[0] for s in stack]
        rules.append((pre, body, tuple(parents)))
        i += 1; prelude_start = i; continue
    if c == ";" and depth == 0:
        i += 1; prelude_start = i; continue
    i += 1
def decls_of(body):
    if "{" in body:
        body = body[:body.find("{")]
    return [d for d in body.split(";") if d.strip()]
fam = collections.defaultdict(lambda: {"rules": 0, "decl": 0, "bytes": 0, "var": 0, "anim_decl": 0, "fvs": 0, "example": None})
prop_inh = collections.Counter(); prop_syntax = collections.Counter(); prop_names_norm = collections.Counter()
keyframes = 0; fontfaces = []; containers = collections.Counter(); anim_names_norm = collections.Counter(); anim_name_decls = 0
view_tl = 0; tl_scope_names = 0; anchor_names = 0; transitions_decl = 0
for pre, body, parents in rules:
    if pre.startswith("@property"):
        name = pre.split()[1]; prop_names_norm[norm(name)] += 1
        m = re.search(r"inherits:\s*(true|false)", body); prop_inh[m.group(1) if m else "?"] += 1
        m = re.search(r'syntax:\s*"([^"]*)"', body); prop_syntax[m.group(1) if m else "?"] += 1
        continue
    if pre.startswith("@keyframes"):
        keyframes += 1; continue
    if pre.startswith("@font-face"):
        fontfaces.append(body); continue
    if pre.startswith("@container"):
        containers[norm(pre)] += 1
        if "{" not in body: pass
        # nested rules are recorded separately with parents
        if body.strip() and not body.strip().startswith("{") and ":" in body.split("{")[0]:
            pass
        continue
    if pre.startswith("@") and "{" in body:
        continue
    key = norm(pre)
    if parents: key = norm(parents[-1]) + " >> " + key
    f = fam[key]; ds = decls_of(body)
    f["rules"] += 1; f["decl"] += len(ds); f["bytes"] += len(body); f["var"] += body.count("var(")
    a = sum(1 for d in ds if d.strip().startswith("animation")); f["anim_decl"] += a
    f["fvs"] += body.count("font-variation-settings")
    if f["example"] is None: f["example"] = (pre[:160], body[:300])
    for d in ds:
        d = d.strip()
        if d.startswith("animation-name:") or d.startswith("animation:"):
            anim_name_decls += 1
            for nm in re.findall(r"--?[A-Za-z][-\w]*", d.split(":", 1)[1]):
                anim_names_norm[norm(nm)] += 1
        if d.startswith("view-timeline"): view_tl += 1
        if d.startswith("timeline-scope"): tl_scope_names += len(d.split(":", 1)[1].split(","))
        if d.startswith("anchor-name"): anchor_names += 1
        if d.startswith("transition"): transitions_decl += 1
# fonts
font_files = []
fam_names = collections.Counter()
for body in fontfaces:
    m = re.search(r"font-family:\s*([^;]+)", body); famname = m.group(1).strip().strip('"') if m else "?"
    fam_names[norm(famname)] += 1
    for u in re.findall(r"url\(([^)]*)\)", body):
        u = u.strip().strip('"').strip("'")
        path = os.path.normpath(os.path.join(bundle, u.split("?")[0]))
        sz = os.path.getsize(path) if os.path.exists(path) else -1
        font_files.append({"family": famname, "url": u, "path": path, "bytes": sz, "unicode_range": bool(re.search(r"unicode-range", body))})
bytes_by_dir = collections.Counter(); bytes_by_famnorm = collections.Counter(); count_by_famnorm = collections.Counter()
for ff in font_files:
    d = os.path.dirname(ff["url"]); bytes_by_dir[d] += max(ff["bytes"], 0)
    bytes_by_famnorm[norm(ff["family"])] += max(ff["bytes"], 0); count_by_famnorm[norm(ff["family"])] += 1
css_rep = {"bytes": len(css), "rules_total": len(rules), "property_rules": sum(prop_inh.values()), "property_inherits": dict(prop_inh),
           "property_syntax": prop_syntax.most_common(), "property_names_norm": prop_names_norm.most_common(60),
           "keyframes": keyframes, "animation_name_decls": anim_name_decls, "animation_names_norm": anim_names_norm.most_common(40),
           "view_timeline_decls": view_tl, "timeline_scope_names": tl_scope_names, "anchor_name_decls": anchor_names, "transition_decls": transitions_decl,
           "container_rules": containers.most_common(40), "font_faces": len(fontfaces), "font_files_missing": sum(1 for f in font_files if f["bytes"] < 0),
           "font_bytes_total": sum(max(f["bytes"], 0) for f in font_files), "font_bytes_by_dir": bytes_by_dir.most_common(),
           "font_bytes_by_family_norm": [(k, count_by_famnorm[k], v) for k, v in bytes_by_famnorm.most_common()],
           "font_unicode_range_faces": sum(1 for f in font_files if f["unicode_range"]),
           "rule_families_top_by_bytes": sorted(((k, v["rules"], v["decl"], v["bytes"], v["var"], v["anim_decl"], v["fvs"], v["example"]) for k, v in fam.items()), key=lambda r: -r[3])[:150],
           "rule_families_count": len(fam)}
json.dump({"dom": dom, "css": css_rep, "font_files": font_files}, open(out_json, "w"), indent=1)
print(json.dumps({k: v for k, v in dom.items() if k not in ("by_class_norm_top", "inline_style_bytes_by_class_top", "family_roots", "body_children", "depth_hist")}))
print("body children:", top[:40])
print("family roots (normclass, roots, descendants, depth):"); [print("  ", r) for r in dom["family_roots"][:60]]
print("by class norm top:"); [print("  ", r) for r in dom["by_class_norm_top"][:120]]
print("inline style bytes:", dom["inline_style_bytes_total"], dom["inline_style_bytes_by_class_top"][:25])
print("depth hist:", dom["depth_hist"])
print(json.dumps({k: v for k, v in css_rep.items() if k not in ("rule_families_top_by_bytes", "font_bytes_by_family_norm", "property_names_norm", "animation_names_norm", "container_rules")}))
print("property names norm:", css_rep["property_names_norm"])
print("animation names norm:", css_rep["animation_names_norm"])
print("container rules:", css_rep["container_rules"])
print("font bytes by family norm (norm, faces, bytes):"); [print("  ", r) for r in css_rep["font_bytes_by_family_norm"]]
print("rule families top by bytes (normsel, rules, decls, bytes, var(), anim decls, fvs, example):"); [print("  ", r[:7], "|", r[7][0][:120], "|", r[7][1][:160]) for r in css_rep["rule_families_top_by_bytes"]]
