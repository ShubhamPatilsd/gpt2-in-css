# bundles/combined4 — combined3 (R2H) + R3R fold-hop + R3F `:has()` scoping + R3H #1 block-flow group max

Built by R3M on 2026-09-20 22:05 (`work/2026-09-19/R3M/compile-combined4.sh combined4`, 8 s; fonts and F2's projection shards reused via the
`experiments` / `global-projection-assets -> ../F2/…` / `assets -> ../F4/assets` symlinks beside the tools copy — no new font files, 283 faces as combined3).
Recipe = `bundles/combined3/BUILD.md` with the merged tools copy `work/2026-09-19/R3M/tools`. **R3L is NOT included** (coordinator 22:00: R3R removes the
`--saved-*` loop-bank latches R3L packs; R3L's diff fails 5/9 hunks on top of R3R — `R3M.md` §1).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R3M
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R2G_SCOPED_HAS=1 R3R_FOLD_HOP=1 R3H_BLOCKFLOW_MAX=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined4
```

## Flags (environment; `0` reverts that change; combined3's flags unchanged, see `bundles/combined3/BUILD.md`)

| flag | default | owner | effect |
|---|---|---|---|
| `R3R_FOLD_HOP` | 1 | R3R | proj carriers publish `262144px + 128·(r + proj)` via `calc-size(max-content, …)` with per-layer constants on `.shared-proj`; proj timelines scoped on `html`; `.loop-reader` / `.core-pass-reader` read them directly; no loop banks, no `--saved-*` latches, no proj number consumers; 7 -> 6 hops/layer (`R3R.md`). Manifest `r3rFoldHop`. |
| `R2G_SCOPED_HAS` | 1 | R3F (R2G generalised) | every body-anchored `:has(#id.done / :checked)` handshake argument -> fixed-depth `> :where(.a) > … > #id` chain verified against the page (69 rules / 79 arguments); no specificity change (`R3F.md` §3). Manifest `r2gScopedHas` (stats). |
| `R3H_BLOCKFLOW_MAX` | 1 | R3M (R3H.md §4 #1, template #176) | appends `.head-group{display:block;grid-template-columns:none;grid-template-rows:none}.head-row{grid-area:auto;justify-self:auto;height:0}` after the head sheet: the 197 coarse groups become block containers of in-flow zero-height rows; a block's max-content width = max child width = the old single `max-content` grid track, so `anchor-size(--head-group-g width)` is unchanged by construction; `.head-fine` stays a grid (`R3M.md` §2). Manifest `r3hBlockflowMax`. |

## Merge (`work/2026-09-19/R3M.md` §1)

`cp -R R2H/tools R3M/tools`; `patch -p1 -F3 -N < R3R/tools-vs-R2H.diff` (browser_gpt2_reused_adapter.py, browser_gpt2_reused_core.py,
build_hybrid_twelve_block.py, + r3r_fold_hop.py); `patch -p2 -F3 -N < R3F/tools-vs-R2H.diff` (browser_gpt2_runtime.py, + r2g_has_scope.py): **0 rejects,
0 fuzz, 0 offsets — disjoint files.** R3H hook = `R3M/apply_r3h_hook.py` (3 exact-string hunks in browser_gpt2_runtime.py; its import line is adjacent to
R3F's `import r2g_has_scope as r2g`, the merge's only textual overlap) + `r3h_blockflow_max.py`. Both agents' diffs are cmp-identical to the diffs embedded
in their BUILD.md; the two new modules are cmp-identical to the owners' copies.

## Offline verification (reference builds in `work/2026-09-19/R3M/scratch/` from the same tools; `runtime.css` compared after normalising the relative `url("../…")` depth, since `R3M/scratch/<x>` is one directory deeper than `bundles/<x>`; `index.html` has no URLs and is compared byte-for-byte)

- **All new flags OFF (`scratch/c4-alloff`) vs `bundles/combined3`: index.html byte-identical, runtime.css identical (URL-normalised), manifest differs only by `r3rFoldHop:false`, `r2gScopedHas:null`, `r3hBlockflowMax:false`.**
- Union checks: `c4-onlyR3R` (R2G/R3H off) reproduces `bundles/R3R` (css + index.html identical, manifest +2 keys); `c4-onlyR3F` (R3R/R3H off) reproduces `bundles/R3F` likewise; `scratch/c4` (all on) is the URL-normalised twin of this bundle.
- R3R: `R3M/offline_check_r3r.py c4 c4-noR3R` (= `R3R/offline_check.py`, paths parametrised): `RESULT: PASS` — tail:
          50  proj timeline scope / viewport
          12  proj receipt (viewport constants)
           2  held rules
           1  head-isolation wall (follows the @property set)
    elements (tags) bundle/ref: 134779 137871 delta -3092
    pk rules per layer: 12 | scroller widths: {'524288'} | markerbase: {'131072'}
    sizes css/html bundle: 38974477 5603748 ref: 39982970 5753602
    RESULT: PASS
- R3F: `R3M/offline_check_r3f.py c4 c4-noR3F` (= `R3F/offline_check.py`): `PASS` — rules 21,280 both (+69/−69 rewritten), `rewritten` = R3F's 79 arguments (loop 0, run 26, token-N-captured 4×7+5, token-N-advanced 2×7, run-latched 3, fonts-loaded 2, eos-done 1).
- R3H: `R3M/offline_check_r3h.py combined4 c4-noR3H`: `RESULT: ok` — index.html identical; css = ref + exactly the 129-byte override after `.head-fine-row:nth-child(256)` and before the control sheet; base `.head-group` grid rule, `.head-row` base rule (R2D clip swap once), two-pass `.head-row{width}` and `.head-fine` grid rule once each; cascade order verified.
- `font-witnesses.json`: 283/283 identical to combined3, R3R and R3F (keys modulo tools dir). `launch_browser_gpt2.py --check`: 285 static files / 285,494,400 B / no JavaScript. NumPy reference (`R3M/reference_ids.py`, merged tools): `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected.
- Sizes: runtime.css 39,880,338 B, index.html 6,508,382 B (combined3: 40,872,840 / 6,658,236); elements −3,092 vs the R3R-off reference (R3R's checker).

## Chrome correctness run

ONE passive run (NOT a timing run), `R3M/run_correctness.sh combined4` (R2D's watchdog harness + R3M lock fixes: owner marker, toucher killed before a marker-checked release; F4's
`correctness_run.mjs`: headless Chrome, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), under `CHROME.lock`.
Power: Now drawing from 'AC Power'  -InternalBattery-0 (id=22872163) 81%; AC attached; not charging present: true; load { 3.53 3.73 4.08 }. Results in `work/2026-09-19/R3M/run-combined4/`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.017645388115284204, 'maximum': 0.1338847690698799}, 'text': "Hello, I'm sorry, but I'm".
- Whole-run counters (harness idle -> end): RecalcStyleCount 985, LayoutCount 629 (R3R alone: 982 / 625; R3F: 1,116 / 720; combined3: 1,107 / 710); Nodes 132170.
- Per-token capture times (5 s poll granularity — indicative only, not a timing run; R3R's run: 21.4, 18.9, 17.1, 17.9, 19.7, 19.4, 17.3, 23.8): 22.0, 39.1, 56.3, 74.3, 98.5, 116.3, 141.0, 158.6 s.
- READY: created.

## `diff -ruN -x __pycache__ work/2026-09-19/R2H/tools work/2026-09-19/R3M/tools`

(= R3R's diff + R3F's diff + the R3H hook and module; 708 lines; also at `R3M/tools-vs-R2H.diff`)

```diff
diff -ruN -x __pycache__ ../R2H/tools/browser_gpt2_reused_adapter.py tools/browser_gpt2_reused_adapter.py
--- ../R2H/tools/browser_gpt2_reused_adapter.py	2026-09-19 10:10:29
+++ tools/browser_gpt2_reused_adapter.py	2026-09-20 22:01:52
@@ -13,6 +13,7 @@
 import r2c_hoist as r2c
 from browser_gpt2_reused_core import compile_reused
 import r2f_lean_handshake as r2f
+import r3r_fold_hop as r3r
 
 
 def compile_reused_runtime_core(
@@ -52,13 +53,15 @@
         "@container runtime style(--layer:0){.loop-input{--loop-ready:1;",
         "@container runtime style(--layer:0){.loop-input{--loop-ready:var(--embed-ready);",
     )
-    if r2f.LEAN_HANDSHAKE:
+    if r3r.FOLD_HOP:
+        pass  # R3R: r3r.loop_parts() already emits the lean controller (no relay, --pass-cap)
+    elif r2f.LEAN_HANDSHAKE:
         # R2F: the controller reads the bank pass markers itself; no SMIL relay,
         # no pulse-end / pass-advance frames. Token boundaries raise --pass-cap.
         css = r2f.apply_css(css, blocks, capacity)
         body = r2f.apply_body(body)
     for token in range(1, capacity):
-        if r2f.LEAN_HANDSHAKE:
+        if r2f.LEAN_HANDSHAKE or r3r.FOLD_HOP:
             break
         step = token * blocks
         old = f"body:has(#loop-advanced-{step}.done){{--pass:{step + 1}}}"
@@ -87,7 +90,12 @@
     needle = '<div class="reused-output" id="reused-result">'
     if body.count(needle) != 1:
         raise ValueError("Missing unique shared-core output")
-    body = body.replace(needle, needle + export)
+    if r3r.FOLD_HOP:
+        # R3R: the export reads the decoded layer output at .loop-input, outside the
+        # display-locked .loop-compute, and is shown only while the pass is held.
+        body, css = r3r.move_export(body, css, export, last)
+    else:
+        body = body.replace(needle, needle + export)
     css += bridge_css
     # Center the added output transport just like the shared context bridge.
     css = re.sub(
@@ -95,7 +103,8 @@
         r"1572864 / (var(\1) + 2)",
         css,
     )
-    css += f".reused-final-export{{display:none}}@container runtime style(--layer:{last}){{.reused-final-export{{display:block}}}}"
+    if not r3r.FOLD_HOP:
+        css += f".reused-final-export{{display:none}}@container runtime style(--layer:{last}){{.reused-final-export{{display:block}}}}"
     # Per-layer controller changes must not invalidate the 50k-row vocabulary
     # sibling. Keep root-only query state non-inherited and explicitly publish
     # just the current pass into the core. Token epoch still inherits normally.
@@ -133,8 +142,9 @@
         pass_readers = ",".join(
             [
                 ".loop-input",
-                ".loop-bank-0",
-                ".loop-bank-1",
+            ]
+            + ([] if r3r.FOLD_HOP else [".loop-bank-0", ".loop-bank-1"])
+            + [
                 ".reused-input",
                 ".fvs-query",
                 ".fvs-score-reader",
@@ -193,7 +203,7 @@
         + body
         + "</div></div>"
     )
-    if r2f.LEAN_HANDSHAKE:
+    if r2f.LEAN_HANDSHAKE or r3r.FOLD_HOP:
         body = r2f.wrap_controller(body)
     body += receiver
     metadata = {
@@ -223,6 +233,7 @@
         "privateLayerControl": True,
         "localLayerContainer": True,
         "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
+        "r3rFoldHop": r3r.FOLD_HOP,
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
diff -ruN -x __pycache__ ../R2H/tools/browser_gpt2_reused_core.py tools/browser_gpt2_reused_core.py
--- ../R2H/tools/browser_gpt2_reused_core.py	2026-09-19 10:10:29
+++ tools/browser_gpt2_reused_core.py	2026-09-20 22:01:52
@@ -15,6 +15,7 @@
 import build_hybrid_twelve_block as h
 import f5_scoping as f5
 import r2c_hoist as r2c
+import r3r_fold_hop as r3r
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
     TOKENS,
@@ -77,6 +78,11 @@
         m[0] for m in re.finditer(r"@(?:font-face|property)\b[^{}]*\{[^{}]*\}", css)
     )
     css = re.sub(r"@(?:font-face|property)\b[^{}]*\{[^{}]*\}", "", css)
+    if r3r.FOLD_HOP:
+        # R3R: html-scoped timeline names cannot live inside the layer container block
+        scopes = re.findall(r"html\{timeline-scope:[^{}]*\}", css)
+        css = re.sub(r"html\{timeline-scope:[^{}]*\}", "", css)
+        globals_css += "".join(scopes).replace(f"b{layer}-", "shared-")
     html = html.replace(f"b{layer}-", "shared-")
     css = css.replace(f"b{layer}-", "shared-")
     if r2c.HOIST_STAGES:
@@ -169,6 +175,7 @@
                     gated=True,
                     dynamic_range=True,
                     global_axes=global_projection and kind == "proj",
+                    fold=r3r.FOLD_HOP and kind == "proj",
                 )
             html, rule = specialize(html, rule, layer, kind)
             if kind in layouts and html != layouts[kind]:
@@ -261,9 +268,12 @@
         mix_source = "".join(banks)
     layouts["mix"] = mix_source + ctx_receiver
 
-    source, output, loop_css = loop_parts(
-        W, blocks * capacity, centered=True, selective=liveness
-    )
+    if r3r.FOLD_HOP:
+        source, output, loop_css = r3r.loop_parts(W, blocks, capacity)
+    else:
+        source, output, loop_css = loop_parts(
+            W, blocks * capacity, centered=True, selective=liveness
+        )
     css += loop_css
     css += (
         "body{container-name:runtime loopcontrol;--epoch:var(--pass);--layer:mod(calc(var(--pass) - 1),"
@@ -284,11 +294,12 @@
         + ";".join(f"--x-{i:03d}:var(--loop-in-{i})" for i in range(W))
         + "}"
     )
-    css += (
-        ".reused-output{"
-        + ";".join(f"--loop-out-{i}:var(--out-{i:03d})" for i in range(W))
-        + "}"
-    )
+    if not r3r.FOLD_HOP:  # R3R: no banks, nothing consumes --loop-out-*
+        css += (
+            ".reused-output{"
+            + ";".join(f"--loop-out-{i}:var(--out-{i:03d})" for i in range(W))
+            + "}"
+        )
     inner = (
         '<div class="reused-output" id="reused-result">'
         + h.probe("reused-probe", "out", W)
@@ -332,9 +343,12 @@
                 f"--stamp-{kind}",
                 f"--gate-{kind}",
             ]
-        lp = [f"--lp-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
-        saved = [f"--saved-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
-        outputs = [f"--loop-out-{i}" for i in range(W)]
+        if r3r.FOLD_HOP:
+            lp, saved, outputs = r3r.reader_names(W), [], []
+        else:
+            lp = [f"--lp-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
+            saved = [f"--saved-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
+            outputs = [f"--loop-out-{i}" for i in range(W)]
         private = set(progress + lp + saved + outputs + bank_props)
         css = re.sub(
             r"@property (--[\w-]+)\{[^{}]+\}",
@@ -350,9 +364,12 @@
             return selector + "{" + ";".join(f"{p}:inherit" for p in names) + "}"
 
         css += forward(".loop-input", lp)
-        css += forward(".loop-bank-0,.loop-bank-1", outputs)
-        css += forward(".loop-scroll,.loop-track", saved)
-        if f5.INLINE_FORWARD:
+        if r3r.FOLD_HOP:
+            pass  # no banks, no bank carriers
+        elif f5.INLINE_FORWARD:
+            css += forward(".loop-bank-0,.loop-bank-1", outputs)
+            css += forward(".loop-scroll,.loop-track", saved)
+
             # F5: 1,538 `.loop-metric:nth-child(N)` rules share one class
             # bucket, so every loop-metric tested all 1,538 selectors on each
             # restyle (P2: 153 us/element on the 1,553-element pass). The
@@ -365,6 +382,8 @@
             if count != 2 * (W + 1):
                 raise ValueError(f"Expected {2 * (W + 1)} loop carriers, found {count}")
         else:
+            css += forward(".loop-bank-0,.loop-bank-1", outputs)
+            css += forward(".loop-scroll,.loop-track", saved)
             for bank in range(2):
                 for i in range(W + 1):
                     css += forward(
diff -ruN -x __pycache__ ../R2H/tools/browser_gpt2_runtime.py tools/browser_gpt2_runtime.py
--- ../R2H/tools/browser_gpt2_runtime.py	2026-09-19 10:10:29
+++ tools/browser_gpt2_runtime.py	2026-09-20 22:01:52
@@ -21,6 +21,8 @@
 import r2d_knobs as r2d
 import f5_scoping as f5
 import r2c_hoist as r2c
+import r2g_has_scope as r2g
+import r3h_blockflow_max as r3h
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -264,6 +266,11 @@
         # F4: the head reads its 768 inputs only through two identical
         # font-variation-settings lists; latch that list once instead of 768 numbers.
         head_css, head_bank_regs, head_bank_decls = f4.pack_head_input(head_css)
+    if r3h.BLOCKFLOW_MAX:
+        # R3H #1 (#176): coarse groups become block containers of in-flow
+        # zero-height rows; a block's max-content width is the max child width,
+        # i.e. the same quantity the single max-content grid track computed.
+        head_css = r3h.blockflow_max(head_css)
     front, output, control_css, timeline_names = feedback(capacity)
     output_receiver = ""
     if detached_output:
@@ -562,8 +569,7 @@
     if r2d.CONTAIN_PAINT:
         css += r2d.contain_paint_css()
     css = re.sub(r'url\("(file:[^\"]+)"\)', relative_asset, css)
-    (directory / "runtime.css").write_text(css)
-    (directory / "index.html").write_text(
+    page = (
         '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="script-src \'none\';object-src \'none\'"><title>Native GPT-2 • Chromium • no JavaScript</title><link rel="stylesheet" href="runtime.css"></head><body>'
         + controls
         + font_html
@@ -571,7 +577,14 @@
         + f'<i id="core-epoch-observer" style="position:fixed;top:-30px;width:anchor-size(--block-{blocks - 1}-probe-epoch width,0px);height:1px"></i>'
         + "</body></html>"
     )
+    r2g_stats = None
+    if r2g.SCOPED_HAS:
+        # R2G/R3F: fixed-depth `:has()` arguments for every handshake rule (chains verified against the page).
+        css, r2g_stats = r2g.scope_has_arguments(css, page, capacity)
+    (directory / "runtime.css").write_text(css)
+    (directory / "index.html").write_text(page)
     metadata.update(
+        r2gScopedHas=r2g_stats,
         fontFaces=font_count,
         autostart=autostart,
         head="full-vocabulary-q16-two-pass",
@@ -586,6 +599,7 @@
         isolateHead=isolate_head,
         detachedOutput=detached_output,
         **r2d.manifest(),
+        r3hBlockflowMax=r3h.BLOCKFLOW_MAX,
         headEpochTransport="separate geometry" if capacity > 8 else "packed four bits",
         fontBackend=font_backend,
         teacherForcedInputs=teacher_forced_tokens[:capacity]
diff -ruN -x __pycache__ ../R2H/tools/build_hybrid_twelve_block.py tools/build_hybrid_twelve_block.py
--- ../R2H/tools/build_hybrid_twelve_block.py	2026-09-19 10:10:29
+++ tools/build_hybrid_twelve_block.py	2026-09-20 22:01:52
@@ -18,6 +18,7 @@
 
 import build_gpt2_block_css as b
 import r2c_hoist as r2c
+import r3r_fold_hop as r3r
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from build_pretrained_gpt2 import css_number as num
 from build_signed_hvar_chain import quantize_float_rows
@@ -118,6 +119,7 @@
     easing_bounds=None,
     dynamic_range=False,
     global_axes=False,
+    fold=False,
 ):
     directory, group = font_group(layer, kind, quantized)
     if global_axes:
@@ -157,6 +159,10 @@
     viewport = 2 ** math.ceil(
         math.log2(max(1024, max(bases) * b.FONT_SIZE / b.UNITS_PER_EM * 1.5))
     )
+    if fold:
+        # R3R: the carriers publish 262144 + 128 * out (the loop bank's encoding);
+        # one viewport for every layer so the top-level decode is layer independent.
+        viewport = r3r.VIEWPORT
     timelines = [f"--{stem}-t{i}" for i in range(count)]
     marker = f"--{stem}-generation"
     progress = names(f"{kind}p", count)
@@ -203,16 +209,22 @@
                 else f'<i class="{stem}-pack{pack}">{chars}</i>'
             )
         metric_style = f"view-timeline:{timelines[i]} inline"
+        if fold:
+            metric_style += ";" + r3r.carrier_width(i)
         if easing_bounds is not None:
             factor = activation_range * quantized.scales[i]
             multiplier = ease_scale * factor * b.UNITS_PER_EM / b.FONT_SIZE
             shift = ease_offset + ease_scale * bias[i] - ease_scale * factor * bases[i]
             metric_style += f";width:calc-size(max-content,size * {num(multiplier)} + {num(shift)}px)"
         metrics.append(f'<i class="metric" style="{metric_style}">{content}</i>')
-    css += (
-        f".{stem}{{timeline-scope:{','.join(timelines + ([marker] if gated else []))};font:normal {b.FONT_SIZE}px {family}S0;"
-        f"font-kerning:none}}.{stem}>.scroller{{width:{viewport}px}}.{stem}>.scroller>.track{{width:{3 * viewport}px}}"
-    )
+    scope_names = ','.join(timelines + ([marker] if gated else []))
+    if fold:
+        # R3R: readers above the stage (.loop-reader, .core-pass-reader) need the names on html
+        css += f"html{{timeline-scope:{scope_names}}}"
+        css += f".{stem}{{font:normal {b.FONT_SIZE}px {family}S0;font-kerning:none}}"
+    else:
+        css += f".{stem}{{timeline-scope:{scope_names};font:normal {b.FONT_SIZE}px {family}S0;font-kerning:none}}"
+    css += f".{stem}>.scroller{{width:{viewport}px}}.{stem}>.scroller>.track{{width:{3 * viewport}px}}"
     if compact and packs == 1:
         # The shorthand above resets family; restore the entire shard fallback.
         css += (
@@ -240,7 +252,13 @@
             f".{stem}-gate{{display:none}}@container {stem}-receipt style(--gate-{kind}:1){{.{stem}-gate{{display:block}}}}"
         )
         inner = f'<div class="{stem}-receipt"><div class="{stem}-gate">{{child}}</div></div>'
-    for start in reversed(range(0, count, chunk)):
+    if fold:
+        # R3R: no number consumers for this stage; the carriers carry the residual sum
+        # (constants live in this layer's block, the width expression is inline and shared).
+        css += r3r.stage_constants(stem, bases, quantized.scales, bias, b.UNITS_PER_EM, b.FONT_SIZE)
+        if layer == 0:
+            css += r3r.constant_regs(count)
+    for start in [] if fold else reversed(range(0, count, chunk)):
         stop = min(count, start + chunk)
         result = []
         for i in range(start, stop):
diff -ruN -x __pycache__ ../R2H/tools/r2g_has_scope.py tools/r2g_has_scope.py
--- ../R2H/tools/r2g_has_scope.py	1969-12-31 16:00:00
+++ tools/r2g_has_scope.py	2026-09-20 22:01:52
@@ -0,0 +1,155 @@
+"""R2G (as applied by R3F): bound the traversal of every handshake `:has()` argument.
+
+Why (R2G.md §3b/§4): Blink's `:has()` matcher walks the anchor's WHOLE subtree once per distinct argument
+(the fast-reject filter cannot reject `#id.done` once any `.done` exists), in reverse DOM order. With only
+child combinators in the argument Blink limits the traversal to a fixed depth
+(check_pseudo_has_argument_context.cc). R2G rewrote the 272 `.core-controller:where(:has(#loop-…))` rules
+(gone since R2F's lean handshake), the 7 `:where(body:has(#token-N-advanced.done)) .core-controller` rules
+and the `.core-block` visibility rule. R3F generalises the rewrite to EVERY body-anchored `:has(#id…)`
+argument in the sheet (token captured/advanced, run/run-latched/fonts-loaded/eos-done, N-ready/ack
+subjects): each `:has(#id.done)` / `:has(#id:checked)` becomes `:has(> .a > .b > … > #id.done)` with the
+exact ancestor chain read from the emitted HTML, and the chain is VERIFIED (the id's ancestor path must
+start at the anchor and equal the chain), so a DOM change fails the build instead of emitting a handshake
+that never fires. `:has()` takes the specificity of its most specific argument, so every chain step is
+written as `> :where(.a)` (zero specificity): the rewritten rules keep exactly their original specificity and
+cascade order (the token-slot / epoch / handshake rules compete with @container rules on the same properties).
+Flag: R2G_SCOPED_HAS (default on).
+"""
+from __future__ import annotations
+
+import html.parser
+import os
+import re
+
+SCOPED_HAS = os.environ.get("R2G_SCOPED_HAS", "1") not in ("0", "false", "no", "off")
+
+LOOP_CHAIN = [".core-block", ".loop-reader", ".loop-input", ".loop-signals"]
+
+
+class _Paths(html.parser.HTMLParser):
+    """Ancestor path (tag, classes) of every element with an id we care about."""
+
+    def __init__(self, wanted):
+        super().__init__()
+        self.wanted = wanted
+        self.stack = []
+        self.paths = {}
+
+    def handle_starttag(self, tag, attrs):
+        d = dict(attrs)
+        if d.get("id") in self.wanted:
+            self.paths[d["id"]] = list(self.stack)
+        if tag not in {"br", "meta", "link", "input", "img", "hr", "set", "option"}:
+            self.stack.append((tag, d.get("class", "").split()))
+
+    def handle_startendtag(self, tag, attrs):
+        d = dict(attrs)
+        if d.get("id") in self.wanted:
+            self.paths[d["id"]] = list(self.stack)
+
+    def handle_endtag(self, tag):
+        if self.stack and self.stack[-1][0] == tag:
+            self.stack.pop()
+
+
+def _step(tag, classes):
+    return f".{classes[0]}" if classes else tag
+
+
+def _chain_from(path, anchor_index):
+    steps = [_step(t, c) for t, c in path[anchor_index + 1 :]]
+    return " ".join(f"> :where({s})" for s in steps)
+
+
+def scope_has_arguments(css: str, page_html: str, capacity: int) -> tuple[str, dict]:
+    """Rewrite every handshake `:has()` argument to a fixed-depth child chain; verify against page_html."""
+    id_args = sorted(set(re.findall(r":has\((#[\w-]+)(?:\.done|:checked)\)", css)))
+    ids = set(a.lstrip("#") for a in id_args)
+    parser = _Paths(ids)
+    parser.feed(page_html)
+    paths = parser.paths
+    missing = ids - set(paths)
+    if missing:
+        raise ValueError(f"R2G: :has() ids not found in the page: {sorted(missing)[:8]}")
+
+    def anchor(path, klass):
+        for i, (tag, classes) in enumerate(path):
+            if klass in classes or tag == klass:
+                return i
+        raise ValueError(f"anchor {klass} not found in path {path}")
+
+    stats = {"rewritten": {}, "chains": {}}
+    total = 0
+
+    # 1. R2G's original loop rules (absent when R2F's lean handshake is on): anchor .core-controller.
+    n_loop = 0
+    if re.search(r"\.core-controller:where\(:has\(#loop-", css):
+        for key in ("loop-captured-1", "loop-advanced-1"):
+            p = paths[key]
+            below = p[anchor(p, "core-controller") + 1 :]
+            if [c[0] for t, c in below] != [s.lstrip(".") for s in LOOP_CHAIN]:
+                raise ValueError(f"loop signal chain mismatch for {key}: {below}")
+        loop_chain = " ".join(f"> :where({s})" for s in LOOP_CHAIN)
+        css, n_loop = re.subn(
+            r"\.core-controller:where\(:has\((#loop-(?:captured|advanced)-\d+\.done)\)\)",
+            lambda m: f".core-controller:where(:has({loop_chain} > {m[1]}))",
+            css,
+        )
+        stats["chains"]["loop"] = loop_chain
+    stats["rewritten"]["loop"] = n_loop
+    total += n_loop
+
+    # 2. every body-anchored `:has(#id.done)` / `:has(#id:checked)`: chain = ancestors strictly below body.
+    #    A compound may carry several :has() (`body:has(#run:checked):has(#token-N-captured.done)`); each
+    #    occurrence is rewritten in place after verifying that, skipping earlier balanced `:has(...)` groups,
+    #    the compound is anchored on `body`.
+    chains = {}
+    for arg in id_args:
+        key = arg.lstrip("#")
+        if key.startswith("loop-"):
+            continue
+        p = paths[key]
+        chain = _chain_from(p, anchor(p, "body"))
+        if not chain:
+            raise ValueError(f"{key} is a direct child of body (nothing to scope)")
+        chains[key] = chain
+        stats["rewritten"][key] = 0
+        stats["chains"][key] = chain
+
+    def anchored_on_body(text, pos):
+        """text[:pos] ends with the compound preceding `:has(`: skip balanced `:has(...)` groups, expect `body`."""
+        i = pos
+        while text.endswith(")", 0, i):
+            depth, j = 0, i - 1
+            while j >= 0:
+                if text[j] == ")":
+                    depth += 1
+                elif text[j] == "(":
+                    depth -= 1
+                    if depth == 0:
+                        break
+                j -= 1
+            if j < 4 or text[j - 4 : j + 1] != ":has(":
+                return False
+            i = j - 4
+        return text.endswith("body", 0, i)
+
+    def rewrite(m):
+        key = m[1].lstrip("#")
+        if key.startswith("loop-") or key not in chains:
+            return m[0]
+        if not anchored_on_body(css, m.start()):
+            raise ValueError(f"R2G: :has({m[1]}) not anchored on body at {css[max(0, m.start() - 80):m.start()]!r}")
+        stats["rewritten"][key] += 1
+        return f":has({chains[key]} > {m[1]}{m[2]})"
+
+    css = re.sub(r":has\((#[\w-]+)(\.done|:checked)\)", rewrite, css)
+    total += sum(v for k, v in stats["rewritten"].items() if k != "loop")
+
+    left = re.findall(r":has\(#[\w-]+(?:\.done|:checked)\)", css)
+    if left:
+        raise ValueError(f"R2G: unscoped :has() arguments left: {sorted(set(left))[:8]}")
+    if stats["rewritten"].get("token-1-advanced", 0) != 2 or total == 0:
+        raise ValueError(f"R2G: unexpected :has() rule counts {stats['rewritten']}")
+    stats["total"] = total
+    return css, stats
diff -ruN -x __pycache__ ../R2H/tools/r3h_blockflow_max.py tools/r3h_blockflow_max.py
--- ../R2H/tools/r3h_blockflow_max.py	1969-12-31 16:00:00
+++ tools/r3h_blockflow_max.py	2026-09-20 22:01:52
@@ -0,0 +1,60 @@
+#!/usr/bin/env python3
+"""R3H option #1 (R3H.md §4 #1): block-flow group maximum for the coarse head.
+
+Template: experiments/gpt2-mixed-hot2-blockflow-group-max-shard256 (#176,
+`tools/build_mixed_hot2_blockflow_group_probe.py:30-31`), whose two override
+rules turned each 256-row vocabulary group from a one-column grid with every
+row in cell 1/1 into a block container of in-flow zero-height rows. A block's
+max-content inline size is the maximum of its in-flow children's max-content
+contributions, exactly the quantity the single `max-content` grid track was
+computing, so `anchor-size(--head-group-g width)` is unchanged by
+construction (#176: 30/30 exact; -13 % layout, -30 % style on the same
+50,257-row topology). Only the always-on coarse groups change; `.head-fine`
+stays a grid (experiments/gpt2-mixed-hot2-all-blockflow: all-block-flow
+regressed the fine stage).
+
+Flag: R3H_BLOCKFLOW_MAX (default 1; `0` reproduces the previous bundle).
+
+What is appended to head.css (after F4's packing, before R2D's knobs):
+  .head-group{display:block;grid-template-columns:none;grid-template-rows:none}
+      keeps position:fixed, width:max-content and the epoch stamp
+      height:calc(var(--head-input-epoch)*1px) of the base rule.
+  .head-row{grid-area:auto;justify-self:auto;height:0}
+      the grid placement properties become inert; height 0 as in #176 so the
+      256 in-flow rows do not overflow the 1-px-per-epoch group. The base
+      rule's display:block, white-space:pre, overflow:hidden (R2D: clip) and
+      the two-pass `width:calc-size(max-content, …)` are untouched, so R2D's
+      exact-string `overflow_clip` swap still matches once.
+"""
+
+import os
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+BLOCKFLOW_MAX = flag("R3H_BLOCKFLOW_MAX")
+
+GROUP_RULE = (
+    ".head-group{position:fixed;left:0;top:-80000px;display:grid;"
+    "grid-template-columns:max-content;grid-template-rows:1px;width:max-content;"
+    "height:calc(var(--head-input-epoch)*1px)}"
+)
+ROW_PREFIX = ".head-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:hidden;"
+FINE_PREFIX = ".head-fine{position:fixed;left:0;top:-80000px;display:grid;grid-template-columns:max-content;grid-template-rows:1px;"
+OVERRIDE = (
+    ".head-group{display:block;grid-template-columns:none;grid-template-rows:none}"
+    ".head-row{grid-area:auto;justify-self:auto;height:0}"
+)
+
+
+def blockflow_max(head_css):
+    """Append the #176 override rules to the head stylesheet (verified shape)."""
+    for name, needle in (("group", GROUP_RULE), ("row", ROW_PREFIX), ("fine", FINE_PREFIX)):
+        count = head_css.count(needle)
+        if count != 1:
+            raise ValueError(f"R3H: expected 1 x head {name} rule, found {count}")
+    if OVERRIDE in head_css:
+        raise ValueError("R3H: block-flow override already present")
+    return head_css + OVERRIDE
diff -ruN -x __pycache__ ../R2H/tools/r3r_fold_hop.py tools/r3r_fold_hop.py
--- ../R2H/tools/r3r_fold_hop.py	1969-12-31 16:00:00
+++ tools/r3r_fold_hop.py	2026-09-20 22:01:52
@@ -0,0 +1,164 @@
+"""R3R (2026-09-20): fold the loop-transport hop into the proj readback.
+
+Flag (default ON): R3R_FOLD_HOP=0 restores the two loop banks (769 carriers each,
+769 latch transitions per layer) and the separate loop readback pass.
+
+Mechanism (work/2026-09-19/R3R.md §1): per layer the reused core needs seven
+geometry->number hops; the seventh (proj carriers -> `--out = r + proj` on the
+proj consumers) is followed by a pure *transport* hop (`--out` -> loop-bank
+carriers -> `.loop-reader` -> `--x`) whose only job is to carry 768 numbers
+from depth ~47 up to depth ~13 and to hold them for a layer (two-bank latch).
+
+Here the proj carriers themselves publish the layer output at the loop bank's
+encoding: carrier i gets
+
+    width: calc-size(max-content, 262144px + --pc-i * 1px + size * --pk-i)
+
+with per-layer constants declared on `.shared-proj` (same layer block as the
+proj weights):  --pk-i = 128 * s_i * UPM/FS * range,
+                --pc-i = 128 * (r_i + b_i - base_i * s_i * range),
+so that width = 262144 + 128 * (r_i + ((size*UPM/FS - base_i) * s_i * range + b_i))
+             = 262144 + 128 * out_i            (the loop bank's `262144px + v*128px`).
+
+The proj timelines (+ the proj generation marker) are scoped on `html`; the
+existing `.loop-reader` reads the 768 proj carriers directly (`--lp-i`, private,
+F5 forward to `.loop-input`) and `.loop-input` decodes `--loop-in-i` with the
+loop bank's exact centered formula. `.core-pass-reader` reads the proj marker:
+`--pass = min(marker + 1, --pass-cap)`.
+
+Why no latch is needed: the proj stage sits under the fc gate (and the attn,
+cache-bridge, qkv gates above it). Within a pass P the gates close in cascade
+one hop after the previous gate opens (each receipt is restyled for the first
+time in P only when its parent gate opens and then closes its own gate because
+its stamp still reads P-1), so the proj stage is restyled/laid out exactly once
+per pass, in the fc-readback pass (C2), with the final `--r` and `--hidden`.
+Its carriers hold out_P from that layout until C2 of pass P+1; the top-level
+readers see the change once, in the pass after C2's layout (= the old proj
+readback pass D1), which is where `--pass` advances and S1 of P+1 runs.
+
+Token boundary: `--pass` is capped at 12k while the head runs; with a single
+carrier set `--loop-in` would already show out_{12k} in that pass, so the core
+is display-locked while held (`--held: marker >= cap` -> `--loop-ready: 0`) and
+the layer-11 export (`.reused-final-export`, bridge carriers reading
+`--loop-in-*`) moves out of the locked subtree to `.loop-input` and is shown
+only while held (it used to be shown at --layer:11 under the proj gate).
+"""
+
+import os
+
+from build_pretrained_gpt2 import css_number as num
+
+
+def flag(name):
+    return os.environ.get(name, "1") not in ("0", "false", "no", "off")
+
+
+FOLD_HOP = flag("R3R_FOLD_HOP")
+
+# Loop-bank encoding, reused verbatim: viewport 524288, track 1572864, carrier width
+# 262144 + 128 * value, centered progress keyframes (-2 -> 1).
+VIEWPORT = 524288
+OFFSET = 262144
+SCALE = 128
+MARKER_BASE = VIEWPORT // 4  # 131072; marker width = base + pass * 1024
+
+DECODE = "(1572864 / (var({p}) + 2) - 524288 - 262144) / 128"
+MARKER_DECODE = "round(nearest,(1572864 / (var(--pr-stamp) + 2) - 524288 - 131072) / 1024,1)"
+# progress of a marker laid out with pass 0: p = vp / (vp + vp/4) = 0.8 -> centered 3p - 2 = 0.4
+MARKER_INITIAL = "0.4"
+
+STAGE = "proj"
+TIMELINE = "--shared-proj-t{i}"
+MARKER_TIMELINE = "--shared-proj-generation"
+
+
+def reader_names(width):
+    return [f"--lp-{i}" for i in range(width)]
+
+
+def carrier_width(i):
+    """Inline width of proj carrier i (layer independent; constants come from .shared-proj)."""
+    return f"width:calc-size(max-content,{OFFSET}px + var(--pc-{i:03d}) * 1px + size * var(--pk-{i:03d}))"
+
+
+def stage_constants(stem, bases, scales, biases, units_per_em, font_size):
+    """Per-layer declarations on the proj stage element (inside its layer block)."""
+    decls = []
+    for i, (base, s, bias) in enumerate(zip(bases, scales, biases)):
+        decls.append(
+            f"--pk-{i:03d}:calc(var(--range-{STAGE}) * {num(SCALE * float(s) * units_per_em / font_size)})"
+        )
+        decls.append(
+            f"--pc-{i:03d}:calc((var(--r-{i:03d}) + ({num(bias)}) - {int(base)} * {num(s)} * var(--range-{STAGE})) * {SCALE})"
+        )
+    return f".{stem}{{{';'.join(decls)}}}"
+
+
+def constant_regs(count):
+    return "".join(
+        f'@property --{k}-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}'
+        for k in ("pk", "pc")
+        for i in range(count)
+    )
+
+
+def loop_parts(width, blocks, capacity):
+    """Replacement for probe_native_reused_loop.loop_parts(): no banks, no SMIL relay."""
+    css = "".join(
+        f'@property {p}{{syntax:"<number>";inherits:true;initial-value:0}}'
+        for p in ["--pass", "--loop-ready"] + [f"--loop-in-{i}" for i in range(width)] + reader_names(width)
+    )
+    css += (
+        '@property --held{syntax:"<number>";inherits:false;initial-value:0}'
+        '@property --pass-cap{syntax:"<number>";inherits:false;initial-value:0}'
+        f'@property --pr-stamp{{syntax:"<number>";inherits:false;initial-value:{MARKER_INITIAL}}}'
+    )
+    # the controller (`body` here; the adapter renames it to .core-controller)
+    css += (
+        f"body{{--pass:min(calc({MARKER_DECODE} + 1),var(--pass-cap));--pass-cap:{blocks};--pr-stamp:inherit;"
+        f"--held:clamp(0,calc({MARKER_DECODE} - var(--pass-cap) + 1),1);container-name:loopcontrol}}"
+    )
+    css += (
+        ".core-pass-reader{animation-name:prstamp;animation-duration:1s;animation-timing-function:linear;"
+        f"animation-fill-mode:both;animation-timeline:{MARKER_TIMELINE};animation-range:cover}}"
+        "@keyframes prstamp{from{--pr-stamp:-2}to{--pr-stamp:1}}"
+    )
+    css += "".join(f"@keyframes lpk{i}{{from{{--lp-{i}:-2}}to{{--lp-{i}:1}}}}" for i in range(width))
+    css += (
+        ".loop-reader{animation-name:"
+        + ",".join(f"lpk{i}" for i in range(width))
+        + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
+        + ",".join(TIMELINE.format(i=i) for i in range(width))
+        + ";animation-range:cover}"
+    )
+    css += (
+        ".loop-input{"
+        + ";".join(f"--loop-in-{i}:calc({DECODE.format(p=f'--lp-{i}')})" for i in range(width))
+        + ";--loop-ready:1}"
+        "@container loopcontrol style(--held:1){.loop-input{--loop-ready:0}}"
+    )
+    css += ".loop-signals{position:fixed;width:1px;height:1px;top:0;left:0}"
+    css += (
+        ".loop-input{container-name:loopreceipt}.loop-compute{content-visibility:hidden;contain-intrinsic-size:0px 0px}"
+        "@container loopreceipt style(--loop-ready:1){.loop-compute{content-visibility:visible}}"
+    )
+    for token in range(1, capacity):
+        css += f"body:has(#token-{token}-advanced.done){{--pass-cap:{(token + 1) * blocks}}}"
+    source = (
+        '<div class="loop-reader"><div class="loop-input"><svg class="loop-signals"></svg>'
+        '<div class="loop-compute">{child}</div></div></div>'
+    )
+    return source, "{child}", css
+
+
+def move_export(body, css, export, last):
+    """Put the layer-11 export beside .loop-compute, reading --loop-in-*, shown only while held."""
+    import re
+
+    export = re.sub(r"--out-(\d{3})", lambda m: f"--loop-in-{int(m[1])}", export)
+    needle = '<svg class="loop-signals"></svg>'
+    if body.count(needle) != 1:
+        raise ValueError("R3R: expected one svg.loop-signals")
+    body = body.replace(needle, needle + export)
+    css += ".reused-final-export{display:none}@container loopcontrol style(--held:1){.reused-final-export{display:block}}"
+    return body, css
```
