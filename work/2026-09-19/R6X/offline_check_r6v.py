"""R6X copy of R6V/offline_check.py (+ normalisation of the one intended R6X layout rule, see below).
R6V offline check: the UI bundle differs from its reference ONLY by the UI subtree / UI rules.
usage: offline_check.py <ui-bundle-dir> <ref-bundle-dir>
1. index.html: after removing the R6V insertions (head <style>, body <link> moved back to <head>, .ld / .ld2 panels,
   .ld-sum elements, .pg reader) the UI page must equal the reference page byte for byte.
2. runtime.css: the multiset of style rules of the UI sheet minus the UI rules (selectors/contexts naming .pg*, .ld*,
   fontload, the early-paint lock selector, @keyframes pg-est-*) must equal the reference sheet's multiset
   (URL depth normalised as R4M/R5X compare_bundles.py).
3. manifest: differing keys only r6v* and r2gScopedHas.* (the UI adds body-anchored :has() rules that R2G rewrites and
   verifies against the page); font-witnesses identical modulo mtime."""
import json, re, sys, pathlib
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from cssindex import rules

UI, REF = map(pathlib.Path, sys.argv[1:3])
ok = True


def fail(msg):
    global ok
    ok = False
    print("FAIL", msg)


# ---- 1. HTML
h = (UI / "index.html").read_text()
r = (REF / "index.html").read_text()
removed = Counter()
def strip(pattern, name, s, count=None):
    n = len(re.findall(pattern, s))
    removed[name] = n
    if count is not None and n != count:
        fail(f"{name}: expected {count} occurrences, found {n}")
    return re.sub(pattern, "", s)

link = '<link rel="stylesheet" href="runtime.css">'
if "<style>" in h:
    h = strip(r"<style>.*?</style>", "head <style>", h, 1)
    if h.count(link) != 1 or h.index(link) < h.index("<body>"):
        fail("body <link> not found exactly once after <body>")
    h = h.replace(link, "", 1).replace("</title></head>", "</title>" + link + "</head>", 1)
h = strip(r'<div class="ld">.*?</div>', ".ld panel", h)
h = strip(r'<div class="ld2">.*?</div>', ".ld2 panel", h)
h = strip(r'<i class="ld-sum ld-sum-\d+-\d+"></i>', ".ld-sum", h)
h = strip(r'<div class="pg">.*?</span></div>', ".pg reader", h)
pg = re.search(r'<div class="pg">.*?</span></div>', (UI / "index.html").read_text())
if pg is None or pg.group(0).count("<") - pg.group(0).count("</") != 8:
    fail("the .pg reader is not the expected 8-element subtree")
if h == r:
    print(f"index.html: IDENTICAL after removing the UI insertions {dict(removed)} ({len((UI / 'index.html').read_bytes())} vs {len((REF / 'index.html').read_bytes())} B)")
else:
    i = next((i for i, (x, y) in enumerate(zip(h, r)) if x != y), min(len(h), len(r)))
    fail(f"index.html differs beyond the UI insertions at {i}: UI[...]={h[max(0, i - 80):i + 120]!r} REF[...]={r[max(0, i - 80):i + 120]!r}")
# the reader must be the first child of .core-controller
if not re.search(r'<div class="core-controller"><div class="pg">', (UI / "index.html").read_text()):
    fail(".pg is not the first child of .core-controller")

# ---- 2. CSS
def norm(s):
    s = re.sub(r'url\("(?:\.\./)+', 'url("../', s)
    return re.sub(r'url\("\.\./(?:R5[HX]/)?assets-r5h/', 'url("../AGENT/assets-r5h/', s)

ui_css, ref_css = norm((UI / "runtime.css").read_text()), norm((REF / "runtime.css").read_text())
# R6X: the merge moves the output text below the progress row (R6X/apply_conflicts.py edit 1: r6p.OUTPUT_TOP 146 -> 184); this is the ONE
# intended model-sheet difference vs the R6P-only twin -> normalise it (exactly one occurrence) and report it
R6X_RULE = (".visible-output{top:184px}", ".visible-output{top:146px}")
if ui_css.count(R6X_RULE[0]) != 1: fail(f"R6X layout rule {R6X_RULE[0]} found {ui_css.count(R6X_RULE[0])} times (expected 1)")
ui_css = ui_css.replace(*R6X_RULE); print(f"R6X: normalised {R6X_RULE[0]} -> {R6X_RULE[1]} (1 occurrence) before the rule comparison")
UI_MARK = re.compile(r"(^|[\s>,{(])\.(pg|ld)[\w-]*(?=$|[\s>,{:.)\[])|fontload|@keyframes pg-est-|body>:not\(\.controls\):not\(\.ld\)|^html \.visible-output$|@keyframes pg-head-")  # R6X: + the v2 layout rule `html .visible-output{bottom;overflow}`
def split(css):
    ui, model = Counter(), Counter()
    for ctx, sel, dec in rules(css):
        key = (" >> ".join(ctx), sel, dec)
        text = " ".join(ctx) + " " + sel
        (ui if UI_MARK.search(text) else model)[key] += 1
    return ui, model
ui_rules, ui_model = split(ui_css)
ref_ui, ref_model = split(ref_css)
if ref_ui:
    fail(f"reference sheet contains {sum(ref_ui.values())} UI-marked rules: {list(ref_ui)[:3]}")
extra = ui_model - ref_model
missing = ref_model - ui_model
if extra or missing:
    fail(f"model rules differ: +{sum(extra.values())} / -{sum(missing.values())}")
    for k in list(extra)[:5]: print("   only in UI:", str(k)[:300])
    for k in list(missing)[:5]: print("   only in REF:", str(k)[:300])
else:
    print(f"runtime.css: model rules IDENTICAL ({sum(ref_model.values())} rules); UI rules {sum(ui_rules.values())}, "
          f"{sum(len(k[0]) + len(k[1]) + len(k[2]) + 2 for k in ui_rules.elements())} B of declarations+selectors; "
          f"sheet {len(ui_css)} vs {len(ref_css)} chars (+{len(ui_css) - len(ref_css)})")
by_kind = Counter()
for (ctx, sel, dec), n in ui_rules.items():
    kind = "keyframes" if "pg-est" in ctx and "@keyframes" in ctx else "@container corestate" if "corestate" in ctx else "@container runtime" if "runtime" in ctx else "@container fontload" if "fontload" in ctx else "plain"
    by_kind[kind] += n
print("   UI rules by kind:", dict(by_kind))
# every model rule must keep its relative order too: compare the sequence of model rules
seq_ui = [k for k in (( " >> ".join(c), s, d) for c, s, d in rules(ui_css)) if not UI_MARK.search(k[0] + " " + k[1])]
seq_ref = [(" >> ".join(c), s, d) for c, s, d in rules(ref_css)]
if seq_ui != seq_ref:
    fail("model rule ORDER differs")
else:
    print("   model rule order identical")

# ---- 3. manifest / witnesses
def flat(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict): out.update(flat(v, pre + k + "."))
        else: out[pre + k] = json.dumps(v, sort_keys=True)
    return out
mu, mr = flat(json.loads((UI / "manifest.json").read_text())), flat(json.loads((REF / "manifest.json").read_text()))
diff = sorted(k for k in set(mu) | set(mr) if mu.get(k) != mr.get(k))
bad = [k for k in diff if not (k.startswith("r6v") or k.startswith("r2gScopedHas."))]
if bad:
    fail(f"manifest keys differ outside r6v*/r2gScopedHas.*: {bad}")
print("manifest differing keys:", "; ".join(f"{k}: {mr.get(k)} -> {mu.get(k)}" for k in diff))
def wit(p):
    w = json.loads((p / "font-witnesses.json").read_text())
    # keys are absolute paths through the agent dir's symlinks (R5X/experiments/... vs R6V/experiments/...): normalise the agent dir
    return {re.sub(r"^.*?/2026-09-19/R\w+/", "AGENT/", k): {kk: vv for kk, vv in v.items() if kk != "mtime"} for k, v in w.items()}
wu, wr = wit(UI), wit(REF)
if wu != wr:
    fail(f"font-witnesses differ ({len(wu)} vs {len(wr)})")
else:
    print(f"font-witnesses: {len(wu)}/{len(wr)} identical (modulo mtime)")
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
