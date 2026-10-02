"""R8U: flag-on bundle vs the live (flag-off) bundle.
html: everything from the body <link rel=stylesheet> on (fonts, witnesses, tokenizer chain, model) byte-identical; the pre-link part may
differ only in <title>, the inline <style>, the new <header class="r8u-head"> and the footer <aside> (text + font); .controls, the
native-signals svg, .tk-panel and the .ld panel byte-identical.
css: rules differing (multiset) must be UI rules from an explicit selector allow-list; each modified rule's declaration diff is printed;
all other rules ("model core") identical in multiset AND order; witnesses identical (agent dir normalised).
usage: check_layout_diff.py <on> <ref>"""
import sys, pathlib, re, json
from collections import Counter, defaultdict
sys.path.insert(0, "/Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R6X")
from cssindex import rules
A, B = map(pathlib.Path, sys.argv[1:3]); ok = True
def fail(m):
    global ok; ok = False; print("FAIL", m)
ha, hb = (A / "index.html").read_text(), (B / "index.html").read_text()
L = '<link rel="stylesheet" href="runtime.css">'
assert ha.count(L) == 1 and hb.count(L) == 1
pa, ta = ha.split(L); pb, tb = hb.split(L)
print("html after the body <link>:", "BYTE-IDENTICAL" if ta == tb else "DIFFERS", f"({len(ta)} chars)");  ta == tb or fail("model html")
def parts(p):
    out = {}
    out["title"] = re.search(r"<title>.*?</title>", p).group(0)
    out["style"] = re.search(r"<style>.*?</style>", p).group(0)
    out["header"] = (re.search(r'<header class="r8u-head">.*?</header>', p) or [""])[0]
    out["aside"] = re.search(r"<aside.*?</aside>", p).group(0)
    rest = p
    for k in ("title", "style", "header", "aside"):
        if out[k]: rest = rest.replace(out[k], "<" + k.upper() + ">", 1)
    out["rest"] = rest
    return out
qa, qb = parts(pa), parts(pb)
OPT = '<details class="r8u-opt"><summary>Options</summary></details>'
ed = re.search(r'(<style id="tk-editor"[^>]*>)\.tk-root \{\n--draft-prompt:\n"(.*?)"\n;\n\}(</style>)', qa["rest"])
print(f"html: Options disclosure x{qa['rest'].count(OPT)}; 5-line editor text: {bool(ed)}")
rest = qa["rest"].replace("<HEADER>", "").replace(OPT, "")
if ed: rest = rest.replace(ed[0], ed[1] + '.tk-root { --draft-prompt: "' + ed[2] + '"; }' + ed[3])
print("html pre-link remainder (head meta, .controls, svg, .tk-panel incl. the editor text, .ld, observer) after removing the header + Options element:", "BYTE-IDENTICAL" if rest == qb["rest"] else "DIFFERS")
rest == qb["rest"] or fail("pre-link remainder")
for k in ("title", "header", "aside"):
    if qa[k] != qb[k]: print(f"  {k}: REF {qb[k][:400]!r}\n  {' ' * len(k)}  ON  {qa[k][:600]!r}")
# inline style: rule-level diff
sa = rules(qa["style"][7:-8]); sb = rules(qb["style"][7:-8])
print("inline <style>: ref", len(sb), "rules, on", len(sa))
for r in [r for r in sa if r not in sb]: print("   inline only in ON :", r[1], "{", r[2][:200])
for r in [r for r in sb if r not in sa]: print("   inline only in REF:", r[1], "{", r[2][:200])
# css
def norm(s):
    s = re.sub(r'url\("(?:\.\./)+', 'url("../', s); return s
ra = [(" >> ".join(c), s, d) for c, s, d in rules(norm((A / "runtime.css").read_text()))]
rb = [(" >> ".join(c), s, d) for c, s, d in rules(norm((B / "runtime.css").read_text()))]
ma, mb = Counter(ra), Counter(rb); extra, missing = ma - mb, mb - ma
UI = re.compile(r"^(\.r8u-[\w-]+.*|\.controls.*|\.tk-panel.*|\.tk-editor.*|\.tk-tokens|\.pg|\.ld-probe|\.ld-track|\.ld2-fill|\.ld-slide,\.ld2-fill|\.fb-warn|html \.visible-output|html \.tk-aside|\.visible-output|body:has\(> :where\(\.controls\) > :where\(label\) > #run:checked\) \.controls>label:nth-of-type\(2\)|body>:not\(\.controls\):not\(\.ld\):not\(\.tk-panel\)(:not\(\.r8u-head\))?)$")
print(f"css rules: on {len(ra)} ref {len(rb)}; only in ON {sum(extra.values())}; only in REF {sum(missing.values())}")
HTMLUI = re.compile(r"^html (body )?\.(tk-tokens|pg|pg-text|pg-bar|pg-lay|pg-exact|pg-est|visible-output)\b")  # UI overrides (also inside @container contexts)
isui = lambda k: (not k[0] and UI.match(k[1])) or HTMLUI.match(k[1])
bad = [k for k in list(extra) + list(missing) if not isui(k)]
for k in bad: print("   NOT A UI RULE:", str(k)[:300])
if bad: fail(f"{len(bad)} non-UI rule differences")
by = defaultdict(lambda: [[], []])
for k in extra.elements(): by[k[1]][0].append(k[2])
for k in missing.elements(): by[k[1]][1].append(k[2])
for sel, (on, ref) in by.items():
    if on and ref and len(on) == len(ref) == 1:
        da, db = on[0].split(";"), ref[0].split(";")
        rm, ad = [d for d in db if d not in da], [d for d in da if d not in db]
        print(f"   MODIFIED {sel} : -{rm} +{ad}")
        if not sel.startswith(".controls") and any(not re.match(r"(top|max-height):", d) for d in rm + ad): fail(f"{sel}: modified beyond top/max-height")
    else:
        for d in ref: print(f"   ONLY REF {sel} {{{d[:200]}}}")
        for d in on: print(f"   NEW      {sel} {{{d[:200]}}}")
seq_a = [r for r in ra if r not in extra]; seq_b = [r for r in rb if r not in missing]
print("order of the common rules:", "IDENTICAL" if seq_a == seq_b else "DIFFERS"); seq_a == seq_b or fail("order")
core_a = [r for r in ra if r not in extra]; core_b = [r for r in rb if r not in missing]
print(f"model core rules (every rule except the {len(extra)}/{len(missing)} allow-listed UI rules that differ): {len(core_a)} vs {len(core_b)} — {'IDENTICAL (multiset and order)' if core_a == core_b and Counter(core_a) == Counter(core_b) else 'DIFFER'}")
core_a == core_b or fail("core")
nw = lambda t: re.sub(r"/work/2026-09-19/R[0-9A-Z]+/", "/work/2026-09-19/AGENT/", t)
w = nw((A / "font-witnesses.json").read_text()) == nw((B / "font-witnesses.json").read_text())
print("font-witnesses.json:", "identical (agent dir normalised)" if w else "DIFFERS"); w or fail("witnesses")
ja, jb = json.loads(nw((A / "manifest.json").read_text())), json.loads(nw((B / "manifest.json").read_text()))
mk = [k for k in set(ja) | set(jb) if ja.get(k) != jb.get(k)]
print("manifest keys differing:", mk)
for k in mk:
    if k != "r2gScopedHas": fail(f"manifest {k}")
    else:
        ra_, rb_ = ja[k].get("rewritten", {}), jb[k].get("rewritten", {})
        d = {x: (rb_.get(x), ra_.get(x)) for x in set(ra_) | set(rb_) if ra_.get(x) != rb_.get(x)}
        print(f"   r2gScopedHas: total {jb[k].get('total')} -> {ja[k].get('total')}; rewritten changes {d}; chains equal for common ids:",
              all(ja[k]['chains'].get(x) == jb[k]['chains'].get(x) for x in jb[k]['chains']))
        if set(d) - {"run"} or ja[k].get("total") - jb[k].get("total") != 1: fail("r2g stats beyond the one Run state rule")
print("RESULT:", "PASS" if ok else "FAIL")
