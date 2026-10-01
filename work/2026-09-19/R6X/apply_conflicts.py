"""R6X: resolve the semantic conflicts of R6P (typed prompt panel) x R6V (progress UI + early paint) after both diffs are applied
on R5X/tools. Every edit is an exact-string replacement that fails loudly if its anchor is not unique. Flag-off behaviour is
unchanged: with R6P_TYPED_PROMPT=0 or R6V_PROGRESS_UI=0 every edit below is a no-op in the emitted bytes.

1. Layout (browser_gpt2_runtime.py, module level, right after the imports): both owners placed their panel row at top 52 px
   (R6P: .tk-panel label + editable <style>, then .tk-tokens at 118, .visible-output at 146; R6V: .ld/.ld2/.pg row at 52 with the
   output at the base 110). With both on, R6V's row moves to 146 (below the token readout) and the output text to 184.
2. Early paint lock (same block): R6V's inline <style> hides every body child but .controls/.ld until runtime.css applies;
   R6P's .tk-panel is a body child (appended to `controls`) and must stay visible -> the lock selector gains :not(.tk-panel)
   (the sheet tail that lifts the lock uses the same module constant, so both stay in step).
3. Inline styles for the panel (browser_gpt2_runtime.py, EARLY_PAINT block): a <style> element is display:none in the UA
   sheet, so the panel needs its visual rules in the inline head <style> to be visible/editable before the 51 MB sheet
   arrives; r6p_prompt.panel_css is split into panel_inline_css() (visual rules) + the rest (same concatenation -> byte-identical
   output) and the runtime inserts panel_inline_css() before </style> of R6V's inline sheet. The :has() rule and the layout
   overrides stay in runtime.css only (R2G rewrites :has() rules of the sheet, not of the page).
usage: python3 apply_conflicts.py <tools-dir>"""
import sys, pathlib
tools = pathlib.Path(sys.argv[1])


def edit(path, old, new, count=1):
    p = tools / path; s = p.read_text()
    assert s.count(old) == count, (path, old[:70], s.count(old))
    p.write_text(s.replace(old, new))
    print(f"edited {path}: {old[:60]!r} ...")


# 0: the one textual reject — both owners add their import after `import r5e_dead_weight as r5e`; R6P's applied, R6V's is inserted after it
edit("browser_gpt2_runtime.py",
     "import r6p_prompt as r6p  # R6P: pre-Run prompt echo fix + typed free-text prompt (prefill)\n",
     "import r6p_prompt as r6p  # R6P: pre-Run prompt echo fix + typed free-text prompt (prefill)\n"
     "import r6v_progress_ui as r6v  # R6V: display-only progress UI\n")
(tools / "browser_gpt2_runtime.py.rej").unlink()  # = exactly that hunk (checked in merge.log)

# 1 + 2: coordination block (module level, before `import numpy as np`, i.e. after both r6p/r6v imports)
edit("browser_gpt2_runtime.py",
     "import numpy as np\nfrom analyze_full_gpt2 import MODEL_PATH, SafeTensors\n",
     "if r6p.TYPED and r6v.ON:  # R6X merge: R6P's prompt panel (top 52) + token readout (118) occupy R6V's panel row -> move the\n"
     "    r6v.TOP_PX = 146  # loading/progress row below the readout (R6V default 52) ...\n"
     "    r6p.OUTPUT_TOP = 184  # ... and the output text below that (R6P default 146; base 110)\n"
     "    r6v.HIDE_SELECTOR = \"body>:not(.controls):not(.ld):not(.tk-panel)\"  # the early-paint lock must not hide the prompt panel\n"
     "import numpy as np\nfrom analyze_full_gpt2 import MODEL_PATH, SafeTensors\n")

# 3a: runtime inserts the panel's visual rules into R6V's inline head <style>
edit("browser_gpt2_runtime.py",
     "        head_style, early_panel, body_link, link = r6v.inline_style(len(css)), r6v.early_panel_html(len(css)), link, ''\n"
     "        css += r6v.early_paint_runtime_css()\n",
     "        head_style, early_panel, body_link, link = r6v.inline_style(len(css)), r6v.early_panel_html(len(css)), link, ''\n"
     "        if r6p.TYPED:  # R6X: the prompt panel (a <style contenteditable>, display:none in the UA sheet) must be visible/editable before the sheet arrives\n"
     "            head_style = head_style.replace(\"</style>\", r6p.panel_inline_css() + \"</style>\", 1)\n"
     "        css += r6v.early_paint_runtime_css()\n")

# 3b: r6p_prompt.panel_css split (identical concatenation) + OUTPUT_TOP constant
edit("r6p_prompt.py",
     'def panel_css(capacity):\n'
     '    return (\n'
     '        ".tk-panel{position:fixed;left:24px;right:24px;top:52px;z-index:100;font:13px/1.4 system-ui;color:#444}"\n'
     '        ".tk-panel label{display:block;margin-bottom:2px}"\n'
     '        ".tk-editor{display:block;box-sizing:border-box;width:100%;max-width:800px;padding:4px 8px;border:1px solid #aaa;border-radius:4px;"\n'
     '        "background:#fff;color:#111;font:13px/1.4 ui-monospace,Menlo,monospace;white-space:pre;overflow:hidden;caret-color:#111}"\n'
     '        ".tk-editor:focus{outline:2px solid Highlight}"\n'
     '        "body:has(#run-latched.done) .tk-editor{-webkit-user-modify:read-only;pointer-events:none;opacity:.6}"\n'
     '        ".visible-output{top:146px}"\n'
     '        ".tk-aside{top:auto!important;bottom:16px}"\n'
     '    )\n',
     'OUTPUT_TOP = 146  # R6X: .visible-output top in px (the merge with R6V moves it below the progress row)\n'
     '\n'
     '\n'
     'def panel_inline_css():\n'
     '    """R6X: the panel\'s visual rules; also emitted in R6V\'s early-paint inline <style> so the editor is visible before the sheet."""\n'
     '    return (\n'
     '        ".tk-panel{position:fixed;left:24px;right:24px;top:52px;z-index:100;font:13px/1.4 system-ui;color:#444}"\n'
     '        ".tk-panel label{display:block;margin-bottom:2px}"\n'
     '        ".tk-editor{display:block;box-sizing:border-box;width:100%;max-width:800px;padding:4px 8px;border:1px solid #aaa;border-radius:4px;"\n'
     '        "background:#fff;color:#111;font:13px/1.4 ui-monospace,Menlo,monospace;white-space:pre;overflow:hidden;caret-color:#111}"\n'
     '        ".tk-editor:focus{outline:2px solid Highlight}"\n'
     '    )\n'
     '\n'
     '\n'
     'def panel_css(capacity):\n'
     '    return (\n'
     '        panel_inline_css()\n'
     '        + "body:has(#run-latched.done) .tk-editor{-webkit-user-modify:read-only;pointer-events:none;opacity:.6}"\n'
     '        f".visible-output{{top:{OUTPUT_TOP}px}}"\n'
     '        ".tk-aside{top:auto!important;bottom:16px}"\n'
     '    )\n')
# 4 (R6X v2 19:1x; v4 21:0x: coordinator's robust sizing for unknown screens — max-height/min-height instead of bottom:96px, footer anchored below the output's max extent; after the coordinator's review of typed-once-final.png): the output text (.visible-output, fixed, top 184) ran into the
# footer (.tk-aside, fixed, bottom 16 px; R6P's rule) once it reached 2 lines in a short viewport. Layout-only fix emitted as ONE extra rule
# at the end of the sheet (selector `html .visible-output`, so it is recognisable and outranks the base rules): the output box is bounded
# above the footer (3 footer lines + margins) and scrolls if the text is longer. No model rule changes (R6X/compare_rules.py proves it).
edit("browser_gpt2_runtime.py",
     "        css += r6v.early_paint_runtime_css()\n",
     "        css += r6v.early_paint_runtime_css()\n"
     "    if r6p.TYPED and r6v.ON:  # R6X: keep the output text above the fixed footer (.tk-aside, bottom 16px); scroll when longer than the box\n"
     "        css += \"html .visible-output{max-height:calc(100vh - 280px);min-height:4lh;overflow:auto}\"  # v4: box = content, clamped; never shorter than 4 lines\n"
     "        css += \"html .tk-aside{top:calc(192px + max(128px,100vh - 280px))!important;bottom:auto}\"  # v4: footer right below the output's maximum extent (off-screen in very short windows, never overlapping)\n"
     "        css += r6x_head_phase_css(blocks)\n")

# 5 (R6X v3, user request via the coordinator): during the vocabulary-head phase (`--held:1`) R6V's bar was full and static. Add a 13th
# segment as the two pseudo-elements of the existing `.pg` reader (no new DOM): `.pg::before` = grey track right of the 12 segments,
# `.pg::after` = a distinct-colour fill that, while --held:1, grows by a compositor-only transform:scaleX() over the ESTIMATED head time
# (R5A §1 / coordinator: ≈2.6–3 s → 2.8 s, labelled an estimate) and pulses in opacity; the label becomes "vocabulary head: 50,257 rows →
# next token… (fill ≈ estimate)". transform/opacity only (R6V's smooth-fill rule: no width animation, no main-thread frames).
edit("browser_gpt2_runtime.py",
     "import numpy as np\nfrom analyze_full_gpt2 import MODEL_PATH, SafeTensors\n",
     "import numpy as np\nfrom analyze_full_gpt2 import MODEL_PATH, SafeTensors\n"
     "\n"
     "\n"
     "def r6x_head_phase_css(blocks, head_seconds=2.8):\n"
     "    \"\"\"R6X: 13th bar segment for the vocabulary-head phase (--held:1 on the corestate container), pseudo-elements of .pg only.\"\"\"\n"
     "    seg = r6v.BAR_PX / blocks\n"
     "    left = r6v.BAR_PX + 4\n"
     "    return (\n"
     "        f\".pg::before,.pg::after{{content:\\\"\\\";position:absolute;left:{left:g}px;top:22px;width:{seg - 2:g}px;height:8px;display:block}}\"\n"
     "        \".pg::before{background:#e3ded2}\"\n"
     "        \".pg::after{background:#d9822b;transform-origin:0 50%;transform:scaleX(0);will-change:transform,opacity}\"\n"
     "        f\"@container corestate style(--held:1){{.pg::after{{animation:pg-head-fill {head_seconds}s linear forwards,pg-head-pulse .7s ease-in-out infinite alternate}}\"\n"
     "        '.pg-lay::after{content:\" · vocabulary head: 50,257 rows → next token… (fill ≈ estimate)\"}}'\n"
     "        \"@keyframes pg-head-fill{from{transform:scaleX(0)}to{transform:scaleX(1)}}\"\n"
     "        \"@keyframes pg-head-pulse{from{opacity:.45}to{opacity:1}}\"\n"
     "    )\n")
# 6 (R6X v5, 2026-10-01, user reports #2/#3: typed prompt shown, dropdown prompt run). Root causes (R6X.md §10): (R2) the embedding receipt
# stamps the EPOCH only (`width:calc(20000px + var(--epoch)*1024px)`): pre-Run the idle embedding of the dropdown token is already stamped 1,
# so at Run layer 0 may consume it before the typed token's re-layout + view-timeline readback lands; (R1) the 86,400 s transition latch
# freezes the before-change values if armed values and latch ever land in the same style pass. Fix: token-fresh receipt (marker encodes
# epoch - 1 + --prompt-live, 0 -> 1 at arming), sticky arming (#run:checked OR #run-latched.done), editor read-only from #run:checked, Run
# enabled only after Ready, latch removed (nothing can change after Run), display/echo keyed on --prompt-armed so it always shows the
# model-facing count/ids. Model core rules untouched.
edit("r6p_prompt.py",
     "    css += '@property --prompt-count{syntax:\"<integer>\";inherits:true;initial-value:0}'\n",
     "    css += '@property --prompt-count{syntax:\"<integer>\";inherits:true;initial-value:0}'\n"
     "    css += '@property --prompt-live{syntax:\"<integer>\";inherits:true;initial-value:0}'  # R6X v5: 1 from arming on (token-fresh embedding receipt)\n")
edit("r6p_prompt.py",
     '        ".tk-root{display:contents;--prompt-armed:inherit}"  # body sets --prompt-armed; .tk-root sets --draft-prompt itself\n',
     '        ".tk-root{display:contents;--prompt-armed:inherit;--prompt-live:if(style(--prompt-armed:1):1;else:0)}"  # body sets --prompt-armed; .tk-root sets --draft-prompt itself; R6X v5: --prompt-live inherited by the model\n')
edit("r6p_prompt.py",
     '        "body:has(#run:checked){--prompt-armed:1}"\n',
     '        "body:has(#run:checked),body:has(#run-latched.done){--prompt-armed:1}"  # R6X v5: sticky (survives unchecking Run / continue)\n')
edit("r6p_prompt.py",
     '        # freeze the model-facing values once the model may start (fonts loaded AND run latched), as --frozen-prompt\n'
     '        props = f"--prompt-token-id-{k},--prompt-has-{k}" + (",--prompt-count" if k == last else "")\n'
     '        css += f"body:has(#fonts-loaded.done):has(#run-latched.done) .tk-high-{k}{{transition-property:{props};{LATCH}}}"\n',
     '        # R6X v5: no transition latch — a same-pass arm+latch would freeze the pre-armed values (-1 / 0); instead nothing can change\n'
     '        # after Run: arming is sticky, the editor is read-only from #run:checked and Run is enabled only after fonts-loaded\n')
edit("r6p_prompt.py",
     '        ".feedback-reader,.visible-output{--draft-prompt:inherit;--pt-present-0:inherit}"\n'
     '        ".visible-output{--display-prompt:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));"\n'
     '        \'--draft-echo:if(style(--prompt-count:0):var(--draft-prompt);else:"")}\'\n',
     '        ".feedback-reader,.visible-output{--draft-prompt:inherit;--pt-present-0:inherit;--prompt-armed:inherit}"\n'
     '        # R6X v5: before Run a live preview (typed text hides the dropdown symbol); from Run on ONLY the model-facing values\n'
     '        # (--prompt-has-0 / --prompt-token-id-k / --prompt-count) so the output can never show a prompt the model did not use\n'
     '        ".visible-output{--dp-live:if(style(--pt-present-0:1):-1;else:var(--frozen-prompt));"\n'
     '        "--dp-armed:if(style(--prompt-has-0:1):-1;else:var(--frozen-prompt));"\n'
     '        "--display-prompt:if(style(--prompt-armed:1):var(--dp-armed);else:var(--dp-live));"\n'
     '        \'--draft-echo:if(style(--prompt-armed:1):"";else:var(--draft-prompt))}\'\n')
edit("r6p_prompt.py",
     '        + "body:has(#run-latched.done) .tk-editor{-webkit-user-modify:read-only;pointer-events:none;opacity:.6}"\n',
     '        + "body:has(#run:checked) .tk-editor,body:has(#run-latched.done) .tk-editor{-webkit-user-modify:read-only;pointer-events:none;opacity:.6}"  # R6X v5: locked from the click itself\n'
     '        + ".controls>label:nth-of-type(2){pointer-events:none;opacity:.6}body:has(#fonts-loaded.done) .controls>label:nth-of-type(2){pointer-events:auto;opacity:1}"  # R6X v5: Run only after Ready (the tokenizer fonts must be in before the ids are armed)\n')
# token-fresh embedding receipt: the stamp marker encodes epoch - 1 + --prompt-live (0 before arming -> never "ready" for epoch 1 with the idle embedding)
edit("browser_gpt2_runtime.py",
     "        model = r6p.wrap_model(model)\n",
     "        model = r6p.wrap_model(model)\n"
     "        _marker_old = 'width:calc(20000px + var(--epoch)*1024px)'  # R6X v5: token-fresh receipt (see apply_conflicts.py edit 6)\n"
     "        _marker_new = 'width:calc(20000px + (var(--epoch) - 1 + var(--prompt-live))*1024px)'\n"
     "        if model.count(_marker_old) != 1:\n"
     "            raise ValueError(f'R6X: expected exactly one embedding epoch marker, found {model.count(_marker_old)}')\n"
     "        model = model.replace(_marker_old, _marker_new, 1)\n")
# 7 (R6X v6, 2026-10-01, cause found by R7H): in HEADED Chrome with macOS "Show scroll bars: Always" a classic 15 px scrollbar sits inside the
# `.feedback-scroller{width:524288px;height:1px;overflow:scroll}` scrollport, while the id decode hardcodes scrollport 524288 px (the metric is
# `.feedback-metric-e{width:65536px + (saved+1)*8px}`, 8 px per id): the readback is biased by (65536 + 8(id+1))*15/524288/8 → rounds to +1 for
# every id >= 9283 (Shubham: 17132 -> 17133 in both headed runs; Hello max 7926 / Once max 8737 pass barely; the 2-layer smokes max 6646 never flip;
# headless runs have no scrollbar). Control-CSS fix: hide the scrollbar on that scroller (Chrome >= 121). Flag R6X_SCROLLBAR_FIX (default 1).
edit("browser_gpt2_runtime.py",
     "        css += r6x_head_phase_css(blocks)\n",
     "        css += r6x_head_phase_css(blocks)\n"
     "    if os.environ.get(\"R6X_SCROLLBAR_FIX\", \"1\") not in (\"0\", \"false\", \"no\", \"off\"):  # R6X v6 (R7H): headed Chrome's classic scrollbar must not shrink the id-readback scrollport\n"
     "        css += \".feedback-scroller{scrollbar-width:none}\"\n")
print("conflicts resolved")
