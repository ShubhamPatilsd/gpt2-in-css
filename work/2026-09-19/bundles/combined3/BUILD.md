# bundles/combined3 — F4 `combined` (F2+F5+F4) + R2C hoist + R2F lean handshake + R2D knobs

Built by R2H on 2026-09-19 10:12 (`work/2026-09-19/R2H/compile-combined3.sh combined3`, 10.4 s; fonts and F2's projection shards are reused via the
`experiments` / `global-projection-assets -> ../F2/…` / `assets -> ../F4/assets` symlinks beside the tools copy — no new font files). Recipe = B0's / F4's
(`bundles/combined/BUILD.md`) with the merged tools copy `work/2026-09-19/R2H/tools`.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2H
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined3
```

## Flags (environment; every one defaults as listed, `0` reverts that change)

| flag | default | owner | effect (see the owner's report) |
|---|---|---|---|
| `F4_PACKED_BANKS`, `F4_PACKED_HEAD`, `F4_NUMERIC_LISTS` | 1 | F4 | packed KV banks / packed head input / numeric list entries (`combined`) |
| `R2C_HOIST_FVS` (+ `R2C_HOIST_STAGES`, `R2C_HOIST_QUERY`, `R2C_HOIST_EMBEDDING`) | 1 | R2C | every `"TAG" calc(var(a) / var(b))` list entry -> `"TAG" var(--fq-…)` with the quotient as a typed `<number>` `inherits:false` on the same element (4 stage lists, 12 query lists, embedding); 6,146 registrations |
| `R2F_LEAN_HANDSHAKE` | 1 | R2F | controller reads the two loop-bank pass markers itself (`.core-pass-reader` wrapper, `--pass:min(calc(max(markers)+1),var(--pass-cap))`); removes the 96 ready-pulse / 96 captured / 95 ack-pulse / 95 advance rules, the 2 `--loop-held` rules and the 576 SMIL `<g>`/`<set>` elements |
| `R2D_HEAD_LOCK` | 1 | R2D | `.full-head` visible only under `@container b11-bridge style(--bridge-ready:1)` (requires `--detached-output`) |
| `R2D_OVERFLOW_CLIP` | 1 | R2D | `.head-row`, `.head-fine-row`, `.metric`: `overflow:hidden` -> `overflow:clip;min-width:0` |
| `R2D_CONTAIN_PAINT` | 1 | R2D | `.head-group,.head-fine,.loop-scroll,.embedding-scroller{contain:paint}` |
| `R2D_POINTER_EVENTS` | **0** | R2D | `pointer-events:none` on compute roots (A/B showed no gain; OFF as R2D shipped it) |

Manifest keys: `r2cHoistFvs/Stages/Query/Embedding`, `r2fLeanHandshake`, `r2dHeadLock`, `r2dOverflowClip`, `r2dPointerEvents`, `r2dContainPaint`.

## Merge (`work/2026-09-19/R2H.md` §1)

`cp -R F4/tools R2H/tools`, then `patch -p1 -F3 < R2C/tools-vs-F4.diff`, `patch -p3 -F3 < R2F/tools-vs-F4.diff`, `patch -p3 -F3 < R2D/tools-vs-F4.diff`
(+ `r2c_hoist.py`, `r2d_knobs.py` copied; `r2f_lean_handshake.py` came from R2F's `-N` diff). 0 rejects, 0 fuzz, 0 offsets, **no conflicts**: the
overlapping files are `browser_gpt2_runtime.py` (R2C + R2D: adjacent import lines; R2D's hunks at :365/:555/:585 are disjoint from R2C's :305) and
`browser_gpt2_reused_adapter.py` (R2C + R2F: adjacent import lines and adjacent manifest lines, as R2F §6 predicted). Checks: `diff R2C/tools R2H/tools` =
exactly R2F's adapter hunks + R2D's runtime hunks; the three new modules are byte-identical to the agents' copies; the 4 files only R2C touched are
identical to R2C's copy; and **a build of the same tools with `R2C_HOIST_FVS=0 R2F_LEAN_HANDSHAKE=0 R2D_HEAD_LOCK=0 R2D_OVERFLOW_CLIP=0 R2D_CONTAIN_PAINT=0`
(`bundles/combined3-alloff`) reproduces `bundles/combined`'s runtime.css and index.html byte-for-byte** (manifest differs only by the 9 new flag keys).

## Offline verification (sibling reference builds `combined3-noR2C`, `-noR2F`, `-noR2D`, `-alloff`; no READY on any of them)

- R2C: `R2H/offline_check_r2c.py combined3 combined3-noR2C` (= `R2C/offline_check.py` with the reference bundle parametrised): `RESULT: ok` — 61 lists /
  65,282 entries, all expressions byte-identical to the reference's entry arithmetic; 6,146 `--fq-*` `<number>` `inherits:false` registrations; wall clean;
  one hoist rule per stage; selector diff limited to the 4 stage lists (12->13), `.fvs-query` (12->24), `.embedding-source` (1->2) + `@property`s;
  index.html identical to the reference.
- R2F: `R2F/offline_check.py combined3 combined3-noR2F`: `PASS` — rules 22,841 vs 23,210 (+12 / −381), elements 68,947 vs 69,522 (−575), fonts/witnesses identical.
- R2D: `R2H/selector_diff.py combined3 combined3-noR2D`: 4 removed / 5 added rules = exactly the head unlock swap (`headinput` -> `b11-bridge`), the 3
  `overflow:clip;min-width:0` rules and the `contain:paint` rule; R2D's emitter asserts (one match per clip rule, `--detached-output` present) passed in the build.
- `font-witnesses.json`: 283 entries identical to `bundles/combined` (keys modulo the tools-copy dir). `launch_browser_gpt2.py --check`: 285 static files /
  286,636,756 B / no JavaScript. NumPy reference (`R2H/reference_ids.py`, R2H tools): `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected.
- Sizes: runtime.css 40,872,840 B (combined 41,666,858), index.html 6,658,236 B (combined 6,686,370), 283 font faces.

## Chrome correctness run

ONE passive run (NOT a timing run), `R2H/run_correctness.sh combined3` (R2D's watchdog harness: wall cap, Chrome-exit watchdog, 30 s lock toucher; F4's
`correctness_run.mjs`: headless Chrome, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), under `CHROME.lock`.
Power: Now drawing from 'AC Power'  -InternalBattery-0 (id=22872163) 81%; AC attached; not charging present: true; load { 5.32 5.10 4.75 }. Results in `work/2026-09-19/R2H/run-combined3/`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.02005934198718561, 'maximum': 0.18731616094288484}, 'text': "Hello, I'm sorry, but I'm".
- Whole-run counters (harness idle -> end): RecalcStyleCount 1107, LayoutCount 710 (R2F alone: 1,109 / 712; combined: 1,420 / 888); Nodes 133716.
- Per-token capture times (5 s poll granularity, AC, load ≈5 — indicative only, not a timing run): 28.3, 52.2, 80.8, 106.4, 132.5, 159.6, 183.7, 215.2 s.
- READY: created 2026-09-20 16:22:42. The bundle files are byte-identical to the 2026-09-19 10:12 build (rebuilt after the 09-20 asset deletion/restoration; see `R2H.md` §7).

## `diff -ru -x __pycache__ work/2026-09-19/F4/tools work/2026-09-19/R2H/tools`

(= the union of `R2C/tools-vs-F4.diff`, `R2F/tools-vs-F4.diff`, `R2D/tools-vs-F4.diff`; the diff against the repo's `tools/` is `R2H/tools-vs-repo.diff`, 898 lines)

```diff
diff -ru -x __pycache__ ../F4/tools/browser_gpt2_embedding.py tools/browser_gpt2_embedding.py
--- ../F4/tools/browser_gpt2_embedding.py	2026-09-18 18:18:20
+++ tools/browser_gpt2_embedding.py	2026-09-19 10:10:29
@@ -9,6 +9,7 @@
 
 import build_hvar_token_embedding_lookup as lookup
 import numpy as np
+import r2c_hoist as r2c
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 
 ROOT = Path(__file__).resolve().parents[1]
@@ -33,6 +34,19 @@
 ]
 
 
+TOKEN_GROUP = "round(down,calc(var(--token) / 256),1)"
+TOKEN_LOCAL = "mod(var(--token),256)"
+if r2c.HOIST_EMBEDDING:
+    # R2C: the two token-derived axis values as typed numbers on the same element.
+    TOKEN_SETTINGS = '"GRUP" var(--fq-token-group),"LOCL" var(--fq-token-local)'
+    TOKEN_HOIST = r2c.private_regs(["--fq-token-group", "--fq-token-local"]) + (
+        f".embedding-source{{--fq-token-group:{TOKEN_GROUP};--fq-token-local:{TOKEN_LOCAL}}}"
+    )
+else:
+    TOKEN_SETTINGS = f'"GRUP" {TOKEN_GROUP},"LOCL" {TOKEN_LOCAL}'
+    TOKEN_HOIST = ""
+
+
 def compile_embedding(directory=OUT, with_epoch=False):
     properties = "".join(
         f'@property --embed-{i:03d}{{syntax:"<number>";inherits:true;initial-value:0}}'
@@ -40,11 +54,11 @@
         f"@keyframes embedk{i}{{from{{--embedp-{i:03d}:0}}to{{--embedp-{i:03d}:1}}}}"
         for i in range(768)
     )
-    css = properties + (
+    css = properties + TOKEN_HOIST + (
         '@property --token{syntax:"<number>";inherits:true;initial-value:15496}'
         f'@font-face{{font-family:EmbeddingLookup;src:url("{(directory / "embedding-lookup.woff2").resolve().as_uri()}") format("woff2")}}'
         ".embedding-source{font:1000px EmbeddingLookup;font-kerning:none;"
-        'font-variation-settings:"GRUP" round(down,calc(var(--token) / 256),1),"LOCL" mod(var(--token),256);'
+        f"font-variation-settings:{TOKEN_SETTINGS};"
         "timeline-scope:" + ",".join(f"--embed-t{i}" for i in range(768)) + "}"
         ".embedding-scroller{position:fixed;left:0;top:-50000px;width:65536px;height:1px;overflow-x:scroll;overflow-y:hidden}"
         ".embedding-track{position:relative;width:196608px;height:1px}"
diff -ru -x __pycache__ ../F4/tools/browser_gpt2_font_vector_cache.py tools/browser_gpt2_font_vector_cache.py
--- ../F4/tools/browser_gpt2_font_vector_cache.py	2026-09-18 19:38:03
+++ tools/browser_gpt2_font_vector_cache.py	2026-09-19 10:10:29
@@ -13,6 +13,7 @@
 import build_hybrid_twelve_block as hybrid
 import f4_packing as f4
 import f5_scoping as f5
+import r2c_hoist as r2c
 import numpy as np
 from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
 from build_gpt2_block_css import UNITS_PER_EM
@@ -201,6 +202,14 @@
             f'"Q{i:03d}" calc(var(--qkv-{head * DIM + i:03d}) / var(--fqs-{head}))'
             for i in range(DIM)
         )
+        if r2c.HOIST_QUERY:
+            # R2C: every score glyph of this head (one per slot) re-parsed these 64
+            # calc()s; evaluate them once here as typed numbers (F4's --fvn pattern).
+            query, pairs = r2c.hoist_settings(
+                query, lambda _src, i, head=head: f"--fq-q-{head}-{i}"
+            )
+            css += r2c.private_regs(name for name, _ in pairs)
+            css += ".fvs-query{" + r2c.declarations(pairs) + "}"
         css += f".fvs-query{{--fvs-query-{head}:{query}}}"
         for kind, offset in (("k", WIDTH), ("v", 2 * WIDTH)):
             scale = f"--fvs-live-{kind}s-{head}"
diff -ru -x __pycache__ ../F4/tools/browser_gpt2_reused_adapter.py tools/browser_gpt2_reused_adapter.py
--- ../F4/tools/browser_gpt2_reused_adapter.py	2026-09-18 19:38:03
+++ tools/browser_gpt2_reused_adapter.py	2026-09-19 10:10:29
@@ -10,7 +10,9 @@
 import build_hybrid_twelve_block as hybrid
 import f4_packing as f4
 import f5_scoping as f5
+import r2c_hoist as r2c
 from browser_gpt2_reused_core import compile_reused
+import r2f_lean_handshake as r2f
 
 
 def compile_reused_runtime_core(
@@ -50,7 +52,14 @@
         "@container runtime style(--layer:0){.loop-input{--loop-ready:1;",
         "@container runtime style(--layer:0){.loop-input{--loop-ready:var(--embed-ready);",
     )
+    if r2f.LEAN_HANDSHAKE:
+        # R2F: the controller reads the bank pass markers itself; no SMIL relay,
+        # no pulse-end / pass-advance frames. Token boundaries raise --pass-cap.
+        css = r2f.apply_css(css, blocks, capacity)
+        body = r2f.apply_body(body)
     for token in range(1, capacity):
+        if r2f.LEAN_HANDSHAKE:
+            break
         step = token * blocks
         old = f"body:has(#loop-advanced-{step}.done){{--pass:{step + 1}}}"
         new = f"body:has(#token-{token}-advanced.done){{--pass:{step + 1}}}"
@@ -183,8 +192,10 @@
         '<div class="core-controller"><div class="core-block" id="block-0">'
         + body
         + "</div></div>"
-        + receiver
     )
+    if r2f.LEAN_HANDSHAKE:
+        body = r2f.wrap_controller(body)
+    body += receiver
     metadata = {
         "blocks": blocks,
         "capacity": capacity,
@@ -211,6 +222,7 @@
         "nativeLayerTokenHandshake": True,
         "privateLayerControl": True,
         "localLayerContainer": True,
+        "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
@@ -220,6 +232,10 @@
         "f4PackedBanks": f4.PACKED_BANKS and codec == "font-vector",
         "f4PackedHead": f4.PACKED_HEAD,
         "f4NumericLists": f4.NUMERIC_LISTS and codec == "font-vector",
+        "r2cHoistFvs": r2c.HOIST_FVS,
+        "r2cHoistStages": r2c.HOIST_STAGES,
+        "r2cHoistQuery": r2c.HOIST_QUERY and codec == "font-vector",
+        "r2cHoistEmbedding": r2c.HOIST_EMBEDDING,
         "kvStorage": "native remembered layout"
         if codec == "geometry"
         else "native delayed whole-head font settings"
diff -ru -x __pycache__ ../F4/tools/browser_gpt2_reused_core.py tools/browser_gpt2_reused_core.py
--- ../F4/tools/browser_gpt2_reused_core.py	2026-09-18 18:20:03
+++ tools/browser_gpt2_reused_core.py	2026-09-19 10:10:29
@@ -14,6 +14,7 @@
 import build_gpt2_block_css as b
 import build_hybrid_twelve_block as h
 import f5_scoping as f5
+import r2c_hoist as r2c
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
     TOKENS,
@@ -78,6 +79,10 @@
     css = re.sub(r"@(?:font-face|property)\b[^{}]*\{[^{}]*\}", "", css)
     html = html.replace(f"b{layer}-", "shared-")
     css = css.replace(f"b{layer}-", "shared-")
+    if r2c.HOIST_STAGES:
+        # R2C: the hoisted quotient declarations are layer-independent; one copy.
+        css, lifted = r2c.lift_stage_rules(css)
+        globals_css += lifted
     marker = re.search(r"width:calc\((\d+)px \+ var\(--epoch\) \* 1024px\)", html)
     if marker:
         css += f".shared-{kind}{{--markerbase-{kind}:{marker[1]}px}}"
diff -ru -x __pycache__ ../F4/tools/browser_gpt2_runtime.py tools/browser_gpt2_runtime.py
--- ../F4/tools/browser_gpt2_runtime.py	2026-09-18 19:38:03
+++ tools/browser_gpt2_runtime.py	2026-09-19 10:10:29
@@ -18,7 +18,9 @@
 import build_gpt2_block_css as b
 import build_hybrid_twelve_block as hybrid
 import f4_packing as f4
+import r2d_knobs as r2d
 import f5_scoping as f5
+import r2c_hoist as r2c
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -301,6 +303,8 @@
             and p != "--head-fvs"
             and not re.fullmatch(r"--hq-\d+", p)
             and not re.fullmatch(r"--fvn-[kv]-\d+-\d+", p)
+            # R2C: hoisted list quotients are inherits:false scratch; no wall needed
+            and not p.startswith(r2c.PREFIX)
             # F2: inherits:false fc scratch cannot reach the head; no wall needed
             and not re.fullmatch(r"--f[zt]-\d+", p)
         ]
@@ -361,7 +365,17 @@
     # scorer on fallback fonts or provisional zero inputs during cold load.
     # The retained epoch never returns to zero after the first complete core,
     # so feedback geometry stays alive throughout subsequent iterations.
-    css += ".head-input-bank{container-name:headinput}.full-head{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container headinput not style(--head-input-epoch:0){.full-head{content-visibility:visible}}"
+    if r2d.HEAD_LOCK:
+        # R2D: the head is skipped (style, layout, paint, compositing inputs,
+        # hit test) except while --bridge-ready:1, i.e. from the end of layer
+        # 11 until the epoch advances. The token slots live outside the head
+        # (detached output) and retain the winner by transition, so nothing
+        # reads the head's geometry while it is locked.
+        if not detached_output:
+            raise ValueError("R2D_HEAD_LOCK requires --detached-output")
+        css += r2d.head_lock_css(blocks)
+    else:
+        css += ".head-input-bank{container-name:headinput}.full-head{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container headinput not style(--head-input-epoch:0){.full-head{content-visibility:visible}}"
     core = core.replace(
         "{child}",
         '<div class="final-normalization"><div class="head-input-bank"><i id="head-input-observer" style="position:fixed;top:-30px;width:calc(var(--head-input-epoch)*1px);height:1px"></i>'
@@ -541,6 +555,12 @@
             + '")'
         )
 
+    if r2d.OVERFLOW_CLIP:
+        css = r2d.overflow_clip(css)
+    if r2d.POINTER_EVENTS:
+        css += r2d.pointer_events_css()
+    if r2d.CONTAIN_PAINT:
+        css += r2d.contain_paint_css()
     css = re.sub(r'url\("(file:[^\"]+)"\)', relative_asset, css)
     (directory / "runtime.css").write_text(css)
     (directory / "index.html").write_text(
@@ -565,6 +585,7 @@
         scheduler="CSS receipts and SVG SMIL events",
         isolateHead=isolate_head,
         detachedOutput=detached_output,
+        **r2d.manifest(),
         headEpochTransport="separate geometry" if capacity > 8 else "packed four bits",
         fontBackend=font_backend,
         teacherForcedInputs=teacher_forced_tokens[:capacity]
diff -ru -x __pycache__ ../F4/tools/build_hybrid_twelve_block.py tools/build_hybrid_twelve_block.py
--- ../F4/tools/build_hybrid_twelve_block.py	2026-09-18 18:20:03
+++ tools/build_hybrid_twelve_block.py	2026-09-19 10:10:29
@@ -17,6 +17,7 @@
 import numpy as np
 
 import build_gpt2_block_css as b
+import r2c_hoist as r2c
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from build_pretrained_gpt2 import css_number as num
 from build_signed_hvar_chain import quantize_float_rows
@@ -133,12 +134,25 @@
         css += regs([f"--range-{kind}"])
         css += f".{stem}{{--range-{kind}:calc(max(.000001,{','.join(f'abs(var({p}))' for p in source)}) * 1.001)}}"
 
+    hoist_stage = dynamic_range and r2c.HOIST_STAGES
+    hoisted = {}
+    index_of = {name: i for i, name in enumerate(source)}
+
     def settings(first):
         if global_axes:
             divisor = f"var(--range-{kind})" if dynamic_range else num(activation_range)
-            return ",".join(f'"{b.global_axis_tag(i)}" calc(var({name}) / {divisor})' for i, name in enumerate(source))
-        fixed = b.pack_font_settings(source, 1 if dynamic_range else activation_range, first)
-        return fixed.replace(" / 1)", f" / var(--range-{kind}))") if dynamic_range else fixed
+            text = ",".join(f'"{b.global_axis_tag(i)}" calc(var({name}) / {divisor})' for i, name in enumerate(source))
+        else:
+            fixed = b.pack_font_settings(source, 1 if dynamic_range else activation_range, first)
+            text = fixed.replace(" / 1)", f" / var(--range-{kind}))") if dynamic_range else fixed
+        if hoist_stage:
+            # R2C: `"TAG" calc(var(--src) / var(--range-kind))` -> `"TAG" var(--fq-kind-idx)`;
+            # the quotient (same text) is declared once below as a typed number on this element.
+            text, pairs = r2c.hoist_settings(
+                text, lambda src, _k: f"--fq-{kind}-{index_of[src]:03d}"
+            )
+            hoisted.update(pairs)
+        return text
     bases = np.sum(np.stack(group.row_bases), axis=0)
     viewport = 2 ** math.ceil(
         math.log2(max(1024, max(bases) * b.FONT_SIZE / b.UNITS_PER_EM * 1.5))
@@ -205,6 +219,12 @@
             f".{stem}{{font-family:{','.join(f'{family}S{s}' for s in range(len(group.names)))};"
             f"font-variation-settings:{settings(0)}}}"
         )
+    if hoist_stage:
+        if len(hoisted) != len(source):
+            raise ValueError(f"R2C hoist covered {len(hoisted)} of {len(source)} {kind} inputs")
+        pairs = sorted(hoisted.items())
+        css += r2c.private_regs(name for name, _ in pairs)
+        css += f".{stem}{{{r2c.declarations(pairs)}}}"
     inner = "{child}"
     if gated:
         # A generation tag travels through the same layout pass as the glyph
Only in tools: r2c_hoist.py
Only in tools: r2d_knobs.py
Only in tools: r2f_lean_handshake.py
```
