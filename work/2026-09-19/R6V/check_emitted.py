"""R6V: verify a built bundle's UI CSS/HTML equals what the current r6v_progress_ui.py emits (reproducibility without a rebuild).
usage: check_emitted.py <bundle-dir> <blocks> <capacity>"""
import sys, pathlib, re, json
sys.path.insert(0, str(pathlib.Path(__file__).parent / "tools"))
import r6v_progress_ui as r6v
d = pathlib.Path(sys.argv[1]); blocks, cap = int(sys.argv[2]), int(sys.argv[3])
css = (d / "runtime.css").read_text(); html = (d / "index.html").read_text()
faces = json.loads((d / "manifest.json").read_text())["fontFaces"]
missing = []
def rules_of(block):
    # split a css string into top-level rules (handles one nesting level of @container/@keyframes)
    out, depth, cur = [], 0, ""
    for ch in block:
        cur += ch
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0: out.append(cur); cur = ""
    return out
sum_html, sum_css, sum_anchor = r6v.sum_tree([f"--font-proof-{i}" for i in range(faces)])
expected = rules_of(r6v.progress_css(blocks, cap)) + rules_of(sum_css) + rules_of(r6v.load_panel_css(sum_anchor, faces)) + rules_of(r6v.early_paint_runtime_css())
for rule in expected:
    if ":has(" in rule:  # R2G rewrites body-anchored :has() arguments to fixed-depth chains; check the declaration block only
        body = rule[rule.index("{"):]
        if body not in css: missing.append(rule[:120])
    elif rule not in css: missing.append(rule[:120])
for frag in [r6v.progress_html(), r6v.load_panel_html(faces), sum_html, r6v.inline_style(len(css))]:
    if frag not in html: missing.append("HTML: " + frag[:100])
# the CSS-phase label quotes the sheet size at assembly time (before the R2G/R5E passes): accept any MB figure
if not re.search(re.escape(r6v.early_panel_html(0)).replace(re.escape("0 MB"), r"\d+ MB"), html): missing.append("HTML: .ld panel")
print(f"{d.name}: {len(expected)} expected UI rules, {len(missing)} missing" + (": " + "; ".join(missing[:5]) if missing else ""))
sys.exit(1 if missing else 0)
