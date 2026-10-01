"""R6V: exact-string edits to tools/browser_gpt2_runtime.py (fails loudly if any anchor string is not unique)."""
import pathlib, sys
p = pathlib.Path(__file__).parent / "tools/browser_gpt2_runtime.py"
s = p.read_text()
def swap(old, new):
    global s
    if s.count(old) != 1:
        sys.exit(f"anchor count {s.count(old)} != 1 for: {old[:90]!r}")
    s = s.replace(old, new, 1)
# 1. import
swap("import r5e_dead_weight as r5e\n", "import r5e_dead_weight as r5e\nimport r6v_progress_ui as r6v  # R6V: display-only progress UI\n")
# 2. font barrier: sum tree + fonts-phase panel (after the min-tree reductions and the fontready signals)
swap(
    '    signals = \'<div class="font-status"><svg xmlns="http://www.w3.org/2000/svg" class="native-signals"><g id="fonts-detected"></g><g id="fonts-loaded"><set attributeName="class" to="done" begin="fonts-detected.animationend+0.001s" fill="freeze"/></g></svg></div>\'\n',
    '    signals = \'<div class="font-status"><svg xmlns="http://www.w3.org/2000/svg" class="native-signals"><g id="fonts-detected"></g><g id="fonts-loaded"><set attributeName="class" to="done" begin="fonts-detected.animationend+0.001s" fill="freeze"/></g></svg></div>\'\n'
    '    if r6v.FONT_COUNT:  # R6V: N-of-283 loaded-fonts counter (sum of the proof widths) + its panel\n'
    '        sum_html, sum_css, sum_anchor = r6v.sum_tree(anchors)\n'
    '        reductions += sum_html\n'
    '        css += sum_css + r6v.load_panel_css(sum_anchor, len(faces))\n'
    '        signals += r6v.load_panel_html(len(faces))\n',
)
# 3. progress reader inside .core-controller + its CSS (after the model/controls are final, before R2G/R5E passes)
swap(
    "    if r2d.OVERFLOW_CLIP:\n        css = r2d.overflow_clip(css)\n",
    "    if r6v.ON:  # R6V: per-token progress reader (first child of .core-controller) + token counter\n"
    "        model = r6v.insert_progress(model)\n"
    "        css += r6v.progress_css(blocks, capacity)\n"
    "    if r2d.OVERFLOW_CLIP:\n        css = r2d.overflow_clip(css)\n",
)
# 4. page assembly: inline style + body <link> after the early panel
swap(
    "    page = (\n        '<!doctype html><html><head><meta charset=\"utf-8\"><meta http-equiv=\"Content-Security-Policy\" content=\"script-src \\'none\\';object-src \\'none\\'\"><title>Native GPT-2 • Chromium • no JavaScript</title><link rel=\"stylesheet\" href=\"runtime.css\"></head><body>'\n        + controls\n        + font_html\n",
    "    link = '<link rel=\"stylesheet\" href=\"runtime.css\">'\n"
    "    head_style, early_panel, body_link = '', '', ''\n"
    "    if r6v.EARLY_PAINT:  # R6V: paint the controls + loading panel before the big sheet is fetched/parsed\n"
    "        head_style, early_panel, body_link, link = r6v.inline_style(len(css)), r6v.early_panel_html(len(css)), link, ''\n"
    "    page = (\n        '<!doctype html><html><head><meta charset=\"utf-8\"><meta http-equiv=\"Content-Security-Policy\" content=\"script-src \\'none\\';object-src \\'none\\'\"><title>Native GPT-2 • Chromium • no JavaScript</title>' + head_style + link + '</head><body>'\n        + controls\n        + early_panel\n        + body_link\n        + font_html\n",
)
# 5. manifest
swap("        **r5e.manifest(),\n", "        **r5e.manifest(),\n        **r6v.manifest(),\n")
p.write_text(s)
print("patched", p)
