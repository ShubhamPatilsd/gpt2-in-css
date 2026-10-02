# bundles/R5C — combined7 + R5C ctx chains (`R5C_CTX_CHAIN=1`), 12 layers, capacity 8, `runs` layout

Built by R5C on 2026-09-24 12:48 (`work/2026-09-19/R5C/compile.sh tools ../bundles/R5C 12 8`; tools copy `work/2026-09-19/R5C/tools` =
`R4M/tools7` (combined7's emitter) + `r5c_ctx_chain.py` + hooks in four files, diff below). Fonts: the same 283 faces as combined7, referenced
relatively (no copies). Reference bundle for every comparison: `bundles/combined7`.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R5C
# combined7's exports (bundles/combined7/BUILD.md: F4_*, R2C_*, R2F_*, R2D_*, R2G_*, R3R_*, R3H_*, R4S_*, R4D_*, R4T_CONSUMER_CHUNK=64) plus:
export R5C_CTX_CHAIN=1
# i.e. ./compile.sh tools ../bundles/R5C 12 8
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R5C
```

## Flag

| flag | default | owner | effect |
|---|---|---|---|
| `R5C_CTX_CHAIN` | 1 (`0` = combined7) | R5C | The 768 V rows (`.fvs-value-row`, width = 262144 + 128·ctx) become in-flow anchor rows (`anchor-name:--r5ca-i`) of a block stage `.r5c-ctx-stage` inside `.fvs-softmax`; three parallel chains of 128 `position:fixed; container-type:size` containers `#r5c-x{s}-{k}` (width/height = `anchor-size(--r5ca-{256s+2k},{+1} width)`, container k+1 publishes `--ctx-i:calc((100cqw / 1px - 262144) / 128)` / cqh) hang off `.fvs-score-reader`; each chain bottom `.r5c-xb{s}` publishes the last two values, declares the shard's 256 R2C quotients `--fq-attn-i` and its 256-axis `font-variation-settings` (per-layer `font-family:b{L}attnS{s}`), and hosts 768 single-glyph anchor rows `.r5c-g` (`anchor-name:--r5cg-{s}-{i}`). The attn stage's 768 three-glyph carriers become 768 `position:fixed` scrollers `.scroller.r5c-sum` whose own width is `calc(anchor-size(--r5cg-0-i width) + … + anchor-size(--r5cg-2-i width))` with a constant-width (V) view-timeline subject inside (track 300 %); the readers decode `S = V·p/(1−p)` instead of `w = V/p − V` (everything else in the reader rules is byte-identical). `.shared-attn` (sums, marker scroller, readers, receipt, gate and the rest of the core) sits inside chain 2's bottom. `--range-attn` becomes the softmax element's bound `calc((max(.000001,var(--fb-0),…,var(--fb-11)) + .0002) * 1.001)` (|ctx| ≤ max stored V scale, ctx being a convex combination of the V rows). No `.cache-bridge-*` scroller / 769 view-timelines / 12 readers / receipt / gate; the ctx readback pass disappears (5 → 4 passes = 2.0 frames/layer). Manifest `r5cCtxChain`, `r5cCtxChains` 3, `r5cCtxChainContainers` 384, `r5cCtxAnchors` 768, `r5cGlyphAnchors` 2304, `r5cSumScrollers` 768. |

## Offline verification (`R5C/offline_check.py R5C combined7` → `R5C/logs/offline_check-R5C.log`, RESULT: PASS)

- **Flag off reproduces combined7**: `R5C_CTX_CHAIN=0` from `R5C/tools` at 2 layers is byte-identical (index.html, runtime.css) to the same build from `R4M/tools7`; at 12 layers the tools7 build (`R5C/scratch/off-12L`, deleted after the check) equals `bundles/combined7`: index.html byte-identical, runtime.css identical after font-URL normalisation (the tools-dir prefix), witnesses identical.
- Rule diff by category (added / removed, exact mappings checked): +384 container-size rules (`#r5c-x{s}-{k}` ← anchors 256s+2k, 256s+2k+1), +381 publishers (k ≥ 1 publishes k−1's pair), +3 bottoms (last pair + 256 quotients + the shard's 256 `A/B/C` axes, nothing else), +36 per-layer shard families, +12 subject-width and +24 marker V/3V rules, +1 `--range-attn` bound, +8 structure rules, 144 attn reader rules identical to combined7's modulo the width term; −12 `.cache-bridge-cN` readers, −2 bridge scroller rules, −3 receipt/gate rules, −12 `.shared-attn` 768-axis lists, −12 `.shared-attn{--range-attn:max|ctx|}`, −1 lifted `--fq-attn` rule, −24 `.shared-attn>.scroller` rules, pass-reader lists −`.cache-bridge-receipt`; html timeline-scope delta = exactly the 769 bridge names. No UNEXPECTED category.
- HTML: 768 `--r5ca` anchors (all before the chains), 384 containers nested in order, 3 bottoms after their 128th container, 2,304 glyph rows with codepoints `U+F0000 + 768·s + i`, 768 sum scrollers with the exact 3-term widths, marker scroller with `var(--markerbase-attn)`, `.shared-attn` is a child of `.r5c-xb2` after its glyph stage, no `cache-bridge` / `{child}` leftovers; view-timelines 9,223 → 8,454 (−769); elements 67,569 → 71,784 (+4,215 = the design count); **max depth 165 → 342** (cap 512); containing-block lint over the 141 ancestors of each chain root and the 272 ancestors of the first sum scroller: no `contain`/`transform`/`filter`/`will-change`/`perspective`/`position:absolute|relative|sticky`.
- V glyph rules, softmax rule, `@font-face` rules identical; witnesses 283/283 identical modulo the tools dir.
- NumPy: `R5C/reference_ids.py` → `[11, 314, 1101, 7926, 11, 475, 314, 1101]` (the arithmetic is unchanged); `R5C/numeric_check.py` (`R5C/logs/numeric_check.log`): the new `--range-attn` bound is 1.5–4.8× today's max|ctx| per layer (worst mean ratio 4.76), the implied F2Dot14 axis-quantisation error on the attention outputs is 1e-4..1.2e-3 rms vs today's 6-significant-digit ctx timeline transport error of 6e-3..1.3e-2 rms (which the chain removes: LayoutUnit-exact readback), sum widths S/V ∈ [0.03, 0.46] (progress 0.03–0.31; same (V+S)²/V·dp sensitivity as today's w = S).
- `tools/launch_browser_gpt2.py --check`: 285 static files / 285,577,967 B / `runtimeJavaScript: false`.
- Sizes: runtime.css 38,781,414 B (combined7 39,073,102), index.html 5,879,529 B (5,612,552).

## Chrome

See `R5C.md` §5–§6 (2-layer smoke pair `bundles/smoke-R5C-2L` / `-ref` with a light trace; ONE passive 8-token correctness run of this bundle). READY is created only on 8/8 ids + verify rc 0.

## `diff -ruN -x __pycache__ work/2026-09-19/R4M/tools7 work/2026-09-19/R5C/tools` (489 lines, also `R5C/tools-vs-tools7.diff`)

```diff
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_font_vector_cache.py R5C/tools/browser_gpt2_font_vector_cache.py
--- R4M/tools7/browser_gpt2_font_vector_cache.py	2026-09-21 01:39:46
+++ R5C/tools/browser_gpt2_font_vector_cache.py	2026-09-24 12:43:39
@@ -16,6 +16,7 @@
 import r4d_flags as r4d
 import r2c_hoist as r2c
 import r4s_small_hops as r4s
+import r5c_ctx_chain as r5c
 import numpy as np
 from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
 from build_gpt2_block_css import UNITS_PER_EM
@@ -179,6 +180,11 @@
         raise ValueError("Early value preparation requires fixed font widths")
     if prewarm_values and r4s.SMALL_HOPS:
         raise ValueError("R4S: the score chain has no score gate to prewarm against")
+    ctx_chain = r5c.CTX_CHAIN
+    if ctx_chain and not r4s.SMALL_HOPS:
+        raise ValueError("R5C: the ctx chains hang off the R4S score chain (R4S_SMALL_HOPS must be on)")
+    if ctx_chain and value_layout not in ("runs", "widths"):
+        raise ValueError("R5C: implemented for the runs/widths value layouts only")
     operators = fonts()
     packed = f4.PACKED_BANKS
     if packed and value_layout not in ("runs", "widths"):
@@ -570,6 +576,11 @@
     value_source, count = re.subn(pattern, row, context_carrier)
     if count != WIDTH:
         raise ValueError(f"Expected 768 native context carriers, found {count}")
+    if ctx_chain:
+        # R5C: the rows are in-flow anchors of a block stage (no timelines, no scroller);
+        # --range-attn is the softmax element's bound on |ctx| (r5c_ctx_chain docstring).
+        value_source = r5c.finish_value_stage(value_source)
+        css += r5c.range_rule()
     if prewarm_values:
         # Let fixed V fonts shape before attention scores are ready. Keep the
         # output generation marker blocked, so speculative geometry cannot
@@ -591,12 +602,26 @@
         if slim_glyphs
         else ".fvs-value-row{display:inline-flex;gap:0;font:0px monospace;line-height:1}"
     )
-    if r4s.SMALL_HOPS:
+    if r4s.SMALL_HOPS and ctx_chain:
+        # R5C: softmax > V anchor stage, then the three ctx chains (chain 2's bottom hosts {child})
+        ctx_html, ctx_css = r5c.chains()
+        css += ctx_css
         body = (
             score_source
             + chain_open
             + '<div class="fvs-score-reader"><div class="fvs-softmax">'
             + value_source
+            + "</div>"
+            + ctx_html
+            + "</div>"
+            + chain_close
+        )
+    elif r4s.SMALL_HOPS:
+        body = (
+            score_source
+            + chain_open
+            + '<div class="fvs-score-reader"><div class="fvs-softmax">'
+            + value_source
             + "</div></div>"
             + chain_close
         )
@@ -661,6 +686,7 @@
             "r4dGateScores": gate_scores,
             "prewarmValues": prewarm_values,
             **r4s.manifest(capacity),
+            **r5c.manifest(),
             "attentionMask": "full causal"
             if capacity == positions
             else "initial sinks plus rolling recent context",
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_reused_adapter.py R5C/tools/browser_gpt2_reused_adapter.py
--- R4M/tools7/browser_gpt2_reused_adapter.py	2026-09-21 01:39:46
+++ R5C/tools/browser_gpt2_reused_adapter.py	2026-09-24 12:43:39
@@ -17,6 +17,7 @@
 import r4s_small_hops as r4s
 import r4d_flags as r4d
 import r4t_consumer_chunk as r4t
+import r5c_ctx_chain as r5c
 
 
 def compile_reused_runtime_core(
@@ -141,7 +142,7 @@
         # and stamp the current pass directly onto every reader.
         receipts = [
             f".shared-{kind}-receipt" for kind in ("qkv", "attn", "fc", "proj")
-        ] + [".cache-bridge-receipt"] + ([] if r4s.SMALL_HOPS else [".fvs-score-receipt"])
+        ] + ([] if r5c.CTX_CHAIN else [".cache-bridge-receipt"]) + ([] if r4s.SMALL_HOPS else [".fvs-score-receipt"])
         pass_readers = ",".join(
             [
                 ".loop-input",
@@ -171,7 +172,8 @@
             body, "var(--position)", "pass-reader"
         )
         # R4S: the score stamp marker (one inline var(--epoch) reader) no longer exists
-        if tagged != (6 if r4s.SMALL_HOPS else 7) or tagged_position != 2:
+        # R5C: nor the cache-bridge stamp marker
+        if tagged != (6 if r4s.SMALL_HOPS else 7) - (1 if r5c.CTX_CHAIN else 0) or tagged_position != 2:
             raise ValueError(
                 f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
             )
@@ -239,6 +241,7 @@
         "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
         "r3rFoldHop": r3r.FOLD_HOP,
         "r4sSmallHops": r4s.SMALL_HOPS and codec == "font-vector",
+        **({k: (v if codec == "font-vector" else (False if isinstance(v, bool) else 0)) for k, v in r5c.manifest().items()}),
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_reused_core.py R5C/tools/browser_gpt2_reused_core.py
--- R4M/tools7/browser_gpt2_reused_core.py	2026-09-21 01:39:46
+++ R5C/tools/browser_gpt2_reused_core.py	2026-09-24 12:43:39
@@ -17,6 +17,7 @@
 import r2c_hoist as r2c
 import r3r_fold_hop as r3r
 import r4t_consumer_chunk as r4t
+import r5c_ctx_chain as r5c
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
     TOKENS,
@@ -198,16 +199,22 @@
     # Cache storage stays outside the dense MLP subtree. Only the selected
     # layer exports a context vector through layout. Scalar banks are siblings;
     # whole-font-vector banks nest private state around one attention graph.
-    ctx_source, ctx_receiver, ctx_css, _ = h.bridge(100, r4t.chunk(512))
-    ctx_source = ctx_source.replace("b100-bridge", "cache-bridge").replace(
-        "--out-", "--ctx-"
-    )
-    ctx_receiver = ctx_receiver.replace("b100-bridge", "cache-bridge")
-    ctx_css = ctx_css.replace("b100-bridge", "cache-bridge").replace("--x-", "--ctx-")
-    if centered_context:
-        ctx_css = re.sub(
-            r"524288 / var\((--bridge-p-\d+)\)", r"1572864 / (var(\1) + 2)", ctx_css
+    if r5c.CTX_CHAIN and font_vector_cache:
+        # R5C: the V rows become anchors read by size-container chains inside the
+        # attention graph; no bridge scroller / readers / receipt / gate. The attention
+        # body carries the {child} placeholder (the attn stage sits under chain 2's bottom).
+        ctx_source, ctx_receiver, ctx_css = r5c.context_carriers(), "", ""
+    else:
+        ctx_source, ctx_receiver, ctx_css, _ = h.bridge(100, r4t.chunk(512))
+        ctx_source = ctx_source.replace("b100-bridge", "cache-bridge").replace(
+            "--out-", "--ctx-"
         )
+        ctx_receiver = ctx_receiver.replace("b100-bridge", "cache-bridge")
+        ctx_css = ctx_css.replace("b100-bridge", "cache-bridge").replace("--x-", "--ctx-")
+        if centered_context:
+            ctx_css = re.sub(
+                r"524288 / var\((--bridge-p-\d+)\)", r"1572864 / (var(\1) + 2)", ctx_css
+            )
     css += ctx_css
     bank_props = (
         []
diff -ruN -x __pycache__ R4M/tools7/build_hybrid_twelve_block.py R5C/tools/build_hybrid_twelve_block.py
--- R4M/tools7/build_hybrid_twelve_block.py	2026-09-21 01:39:46
+++ R5C/tools/build_hybrid_twelve_block.py	2026-09-24 12:43:39
@@ -19,6 +19,7 @@
 import build_gpt2_block_css as b
 import r2c_hoist as r2c
 import r3r_fold_hop as r3r
+import r5c_ctx_chain as r5c
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from build_pretrained_gpt2 import css_number as num
 from build_signed_hvar_chain import quantize_float_rows
@@ -122,6 +123,11 @@
     fold=False,
 ):
     directory, group = font_group(layer, kind, quantized)
+    ctx_chain = r5c.CTX_CHAIN and kind == "attn"
+    if ctx_chain:
+        if global_axes or easing_bounds is not None or fold or not (dynamic_range and compact and gated):
+            raise ValueError("R5C: the attn stage needs the compact/gated/dynamic-range matvec")
+        r5c.record_attn_group(layer, group)
     if global_axes:
         from browser_gpt2_projection_layout import global_projection_fonts
 
@@ -134,7 +140,8 @@
         if easing_bounds is not None:
             raise ValueError("Dynamic input range currently requires exact GELU")
         css += regs([f"--range-{kind}"])
-        css += f".{stem}{{--range-{kind}:calc(max(.000001,{','.join(f'abs(var({p}))' for p in source)}) * 1.001)}}"
+        if not ctx_chain:  # R5C: --range-attn is declared on the softmax element (bound), not here
+            css += f".{stem}{{--range-{kind}:calc(max(.000001,{','.join(f'abs(var({p}))' for p in source)}) * 1.001)}}"
 
     hoist_stage = dynamic_range and r2c.HOIST_STAGES
     hoisted = {}
@@ -197,6 +204,10 @@
         css += f"{selector}{{font-family:{families};font-variation-settings:{settings(first)}}}"
     metrics = []
     for i in range(count):
+        if ctx_chain:
+            # R5C: one fixed scroller per output, as wide as the three shard glyph anchors
+            metrics.append(r5c.sum_carrier(i, timelines[i], len(group.names)))
+            continue
         content = ""
         for pack in range(packs):
             chars = "".join(
@@ -225,13 +236,20 @@
     else:
         css += f".{stem}{{timeline-scope:{scope_names};font:normal {b.FONT_SIZE}px {family}S0;font-kerning:none}}"
     css += f".{stem}>.scroller{{width:{viewport}px}}.{stem}>.scroller>.track{{width:{3 * viewport}px}}"
-    if compact and packs == 1:
+    if ctx_chain:
+        # R5C: the shard lists live on the chain bottoms (r5c.chains); only the per-layer
+        # family goes here, plus the subject / marker widths of this layer's viewport.
+        css += "".join(
+            f".{r5c.BOTTOM_CLASS}{s}{{font-family:{family}S{s}}}" for s in range(len(group.names))
+        )
+        css += r5c.stage_css(stem, viewport)
+    elif compact and packs == 1:
         # The shorthand above resets family; restore the entire shard fallback.
         css += (
             f".{stem}{{font-family:{','.join(f'{family}S{s}' for s in range(len(group.names)))};"
             f"font-variation-settings:{settings(0)}}}"
         )
-    if hoist_stage:
+    if hoist_stage and not ctx_chain:
         if len(hoisted) != len(source):
             raise ValueError(f"R2C hoist covered {len(hoisted)} of {len(source)} {kind} inputs")
         pairs = sorted(hoisted.items())
@@ -242,8 +260,11 @@
         # A generation tag travels through the same layout pass as the glyph
         # widths. New input closes downstream gates before stale font widths
         # can launch the next matvec. No external per-stage scheduler is used.
+        marker_width = f"calc({viewport // 4}px + var(--epoch) * 1024px)"
         metrics.append(
-            f'<i class="metric" style="width:calc({viewport // 4}px + var(--epoch) * 1024px);view-timeline:{marker} inline"></i>'
+            r5c.marker_carrier(marker_width, marker)
+            if ctx_chain
+            else f'<i class="metric" style="width:{marker_width};view-timeline:{marker} inline"></i>'
         )
         css += (
             f".{stem}-receipt{{container-name:{stem}-receipt;animation:{kind}stamp 1s linear both;"
@@ -264,7 +285,8 @@
         for i in range(start, stop):
             if easing_bounds is not None:
                 continue
-            raw = f"(({viewport} / var({progress[i]}) - {viewport}) * {b.UNITS_PER_EM} / {b.FONT_SIZE} - {int(bases[i])})"
+            width = r5c.raw_width(viewport, progress[i]) if ctx_chain else f"({viewport} / var({progress[i]}) - {viewport})"
+            raw = f"({width} * {b.UNITS_PER_EM} / {b.FONT_SIZE} - {int(bases[i])})"
             gain = f"{num(quantized.scales[i])} * var(--range-{kind})" if dynamic_range else num(activation_range * quantized.scales[i])
             value = f"calc({raw} * {gain} + ({num(bias[i])}))"
             if kind == "fc":
@@ -290,7 +312,10 @@
             f"animation-timeline:{','.join(timelines[start:stop])};animation-range:cover;{';'.join(result)}}}"
         )
         inner = f'<div class="{consumer}">{inner}</div>'
-    html = f'<div class="{stem}"><div class="scroller"><div class="track">{"".join(metrics)}</div></div>{inner}</div>'
+    if ctx_chain:
+        html = f'<div class="{stem}"><div class="{r5c.SUMS_CLASS}">{"".join(metrics)}</div>{inner}</div>'
+    else:
+        html = f'<div class="{stem}"><div class="scroller"><div class="track">{"".join(metrics)}</div></div>{inner}</div>'
     return html, css
 
 
diff -ruN -x __pycache__ R4M/tools7/r5c_ctx_chain.py R5C/tools/r5c_ctx_chain.py
--- R4M/tools7/r5c_ctx_chain.py	1969-12-31 16:00:00
+++ R5C/tools/r5c_ctx_chain.py	2026-09-24 12:42:49
@@ -0,0 +1,231 @@
+"""R5C (2026-09-24): the 768-value ctx hop (attention output -> proj input) leaves view-timelines.
+
+Flag (default ON): R5C_CTX_CHAIN=0 restores combined7's ctx transport (`.cache-bridge-source`
+scroller with 768 + 1 view-timeline carriers, 12 `.cache-bridge-cN` readers, receipt + gate,
+`.shared-attn` with the 768-axis list and 768 three-glyph rows). Requires R4S_SMALL_HOPS (the V
+rows already live inside the score chain's bottom) and the font-vector codec.
+
+Mechanism (work/2026-09-19/R5C.md). The 768 V rows (`.fvs-value-row`, width = 262144 + 128*ctx_i)
+become in-flow anchor rows (`anchor-name:--r5ca-i`) of a plain block stage inside `.fvs-softmax`.
+The attn matvec's three 256-axis shard fonts each need their 256 axis values on ONE element, so
+three PARALLEL chains of 128 `position:fixed; container-type:size` containers hang off the score
+chain's bottom (`.fvs-score-reader`): chain s, container k takes `width/height:anchor-size(--r5ca-{256s+2k},{+1} width)`,
+container k+1 publishes container k's two values as the registered inherited numbers
+`--ctx-i:calc((100cqw / 1px - 262144) / 128)` (cqh for the second), the bottom `.r5c-xb{s}`
+publishes the last two, declares the R2C quotients `--fq-attn-i:calc(var(--ctx-i) / var(--range-attn))`
+for its 256 inputs and the shard's 256-axis `font-variation-settings` (inherited by its 768 in-flow
+single-glyph rows `<i class="r5c-g" style="anchor-name:--r5cg-{s}-{i}">`, font b{L}attnS{s}).
+The fan-in (output i = the sum of its three shard glyph advances, an inline run today) becomes, per
+output, ONE `position:fixed` scroller (`.scroller.r5c-sum`) whose own width is
+`calc(anchor-size(--r5cg-0-i width) + anchor-size(--r5cg-1-i width) + anchor-size(--r5cg-2-i width))`
+with a constant-width (V) view-timeline subject inside (track 300 %): progress p = S/(S+V), the reader
+decodes S = V*p/(1-p) (today: w = V/p - V; same 6-significant-digit sensitivity 4V*dp at S ~ V).
+The whole `.shared-attn` stage (sums, marker scroller, readers, receipt, gate and everything below)
+sits inside shard chain 2's bottom, so its fixed scrollers are laid out AFTER the three glyph stages
+(nested out-of-flow roots are laid out in nesting order; F3.md §3b / F3b lint rule) and the readers
+inherit `--range-attn`.
+
+`--range-attn` (today max|ctx|*1.001 on `.shared-attn`, which needs all 768 values on one element)
+becomes a bound computed on the softmax element from numbers it already has: ctx_h = sum_s p_s v_s
+with p_s >= 0, sum p_s = 1, so |ctx_{h,i}| <= max_s |v_{s,i}| <= max_s vs_s = --fb-h (the per-head
+maximum of the stored V scales); `--range-attn:calc((max(.000001,var(--fb-0),..,var(--fb-11)) + .0002) * 1.001)`
+(+2e-4 covers the chain's 1/(64*128) rounding). Looser than max|ctx| by the averaging factor, so the
+F2Dot14 axis quantisation of ctx/range is coarser by that factor (~3e-5*range absolute) — still far below
+today's 6-digit timeline transport error of ~5e-3 per ctx value, which the chain removes (LayoutUnit exact).
+
+Passes per layer: [proj+S1 | qkv+scores+V+ctx chains+attn glyphs+sums] [attn | fc] = 4 = 2.0 frames
+(combined7: 5 = 2.5), -769 carrier animations and -12 readers -1 receipt/gate per layer.
+"""
+
+import os
+import re
+
+import r2c_hoist as r2c
+
+W, SHARD, HEADS = 768, 256, 12
+OFFSET, SCALE = 262144, 128  # the ctx carrier encoding (build_hybrid_twelve_block.bridge)
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+CTX_CHAIN = flag("R5C_CTX_CHAIN")
+
+STAGE_CLASS = "r5c-ctx-stage"  # block stage holding the 768 V anchor rows
+ROW_CLASS = "r5c-ctx-a"  # added to each .fvs-value-row
+CHAIN_CLASS = "r5c-x"  # chain container
+BOTTOM_CLASS = "r5c-xb"  # chain bottom (in-flow)
+GLYPH_STAGE_CLASS = "r5c-gs"  # in-flow block with the shard's 768 glyph rows
+GLYPH_CLASS = "r5c-g"
+SUMS_CLASS = "r5c-sums"  # wrapper of the 768 sum scrollers + the marker scroller
+SUM_CLASS = "r5c-sum"  # fixed scroller whose width is the shard-glyph sum
+MARK_CLASS = "r5c-mark"  # ordinary fixed scroller for the attn generation marker
+
+# set by build_hybrid_twelve_block.matvec (attn) before browser_gpt2_font_vector_cache.attention()
+ATTN_GROUP = {}
+
+
+def ctx_anchor(i):
+    return f"--r5ca-{i:03d}"
+
+
+def glyph_anchor(shard, i):
+    return f"--r5cg-{shard}-{i:03d}"
+
+
+def decode(unit):
+    return f"calc((100{unit} / 1px - {OFFSET}) / {SCALE})"
+
+
+def record_attn_group(layer, group):
+    """The glyph rows are layer independent: same shard count and codepoints for every layer."""
+    info = (len(group.names), tuple(group.codepoint_starts), group.output_count)
+    if ATTN_GROUP and ATTN_GROUP["info"] != info:
+        raise ValueError(f"R5C: attn font group of layer {layer} differs from layer 0: {info} vs {ATTN_GROUP['info']}")
+    ATTN_GROUP["info"] = info
+
+
+def shards():
+    if not ATTN_GROUP:
+        raise ValueError("R5C: attention() called before the attn matvec recorded its font group")
+    return ATTN_GROUP["info"][0]
+
+
+def context_carriers():
+    """Replacement for bridge()'s source: the same carrier text attention() rewrites into V rows,
+    with the anchor name in the timeline slot (finish_value_stage turns it into anchor-name)."""
+    rows = "".join(
+        f'<i class="metric" style="width:calc({OFFSET}px + var(--ctx-{i:03d}) * {SCALE}px);view-timeline:{ctx_anchor(i)} inline"></i>'
+        for i in range(W)
+    )
+    return f'<div class="{STAGE_CLASS}">{rows}</div>'
+
+
+def finish_value_stage(html):
+    """After attention()'s row rewrite: in-flow anchor rows (no .metric = no position:absolute)."""
+    new, count = re.subn(
+        r'<span class="metric fvs-value-row" style="width:([^"]*);view-timeline:(--r5ca-\d{3}) inline">',
+        r'<span class="fvs-value-row ' + ROW_CLASS + r'" style="anchor-name:\2;width:\1">',
+        html,
+    )
+    if count != W:
+        raise ValueError(f"R5C: expected {W} V rows to convert, found {count}")
+    if "view-timeline" in new or 'class="metric' in new:
+        raise ValueError("R5C: leftover timeline carriers in the V stage")
+    return new
+
+
+def range_rule():
+    """--range-attn as the softmax element's bound (see module docstring)."""
+    fbs = ",".join(f"var(--fb-{h})" for h in range(HEADS))
+    return f".fvs-score-reader{{--range-attn:calc((max(.000001,{fbs}) + .0002) * 1.001)}}"
+
+
+def settings(shard):
+    """The shard's 256-axis list with R2C's hoisted quotients (same text matvec would emit)."""
+    from build_gpt2_block_css import packed_axis_tag
+
+    return ",".join(
+        f'"{packed_axis_tag(shard, local)}" var(--fq-attn-{SHARD * shard + local:03d})'
+        for local in range(SHARD)
+    )
+
+
+def quotients(shard):
+    return ";".join(
+        f"--fq-attn-{i:03d}:calc(var(--ctx-{i:03d}) / var(--range-attn))"
+        for i in range(SHARD * shard, SHARD * (shard + 1))
+    )
+
+
+def chains(child="{child}"):
+    """Three parallel 128-deep chains hanging off the score reader; returns (html, css).
+
+    Chain s, container k: width/height = anchors 256s+2k, 256s+2k+1; container k+1 publishes
+    container k's two values; the bottom publishes the last two, hosts the quotients + shard
+    settings, the glyph stage, and (shard 2) the {child} placeholder = the attn stage and below."""
+    count, codepoints, outputs = ATTN_GROUP["info"]
+    if count * SHARD != W or outputs != W:
+        raise ValueError(f"R5C: expected {W // SHARD} shards of {SHARD} axes and {W} outputs, got {count} / {outputs}")
+    levels = SHARD // 2
+    css = [
+        f".{STAGE_CLASS}{{display:block;width:1px;height:1px;overflow:clip;visibility:hidden}}",
+        f".{ROW_CLASS}{{display:flex;position:static;height:1px;overflow:clip;min-width:0}}",
+        f".{CHAIN_CLASS}{{position:fixed;left:0;top:-300000px;container-type:size}}",
+        f".{BOTTOM_CLASS}{{display:block;width:1px;height:1px;font-size:512px;font-style:normal;font-weight:normal;line-height:1;font-kerning:none;white-space:pre}}",
+        f".{GLYPH_STAGE_CLASS}{{display:block;width:1px;height:1px;overflow:clip;visibility:hidden}}",
+        f".{GLYPH_CLASS}{{display:block;width:max-content;height:1px;overflow:clip;min-width:0;white-space:pre;font-style:normal}}",
+        f".{SUMS_CLASS}{{display:block;width:1px;height:1px}}",
+        f".{SUM_CLASS}>.track{{width:300%}}",
+        r2c.private_regs(f"--fq-attn-{i:03d}" for i in range(W)),
+    ]
+    html = []
+    for s in range(count):
+        for k in range(levels):
+            i0, i1 = SHARD * s + 2 * k, SHARD * s + 2 * k + 1
+            css.append(
+                f"#{CHAIN_CLASS}{s}-{k}{{width:anchor-size({ctx_anchor(i0)} width);height:anchor-size({ctx_anchor(i1)} width)}}"
+            )
+            if k:
+                css.append(
+                    f"#{CHAIN_CLASS}{s}-{k}{{--ctx-{i0 - 2:03d}:{decode('cqw')};--ctx-{i1 - 2:03d}:{decode('cqh')}}}"
+                )
+            html.append(f'<div class="{CHAIN_CLASS}" id="{CHAIN_CLASS}{s}-{k}">')
+        last0, last1 = SHARD * (s + 1) - 2, SHARD * (s + 1) - 1
+        css.append(
+            f".{BOTTOM_CLASS}{s}{{--ctx-{last0:03d}:{decode('cqw')};--ctx-{last1:03d}:{decode('cqh')};"
+            f"{quotients(s)};font-variation-settings:{settings(s)}}}"
+        )
+        glyphs = "".join(
+            f'<i class="{GLYPH_CLASS}" style="anchor-name:{glyph_anchor(s, i)}">&#x{codepoints[s] + i:X};</i>'
+            for i in range(W)
+        )
+        html.append(
+            f'<div class="{BOTTOM_CLASS} {BOTTOM_CLASS}{s}"><div class="{GLYPH_STAGE_CLASS}">{glyphs}</div>'
+            + (child if s == count - 1 else "")
+            + "</div>"
+            + "</div>" * levels
+        )
+    return "".join(html), "".join(css)
+
+
+def sum_carrier(i, timeline, shard_count):
+    """One output's carrier: a fixed scroller as wide as the sum of its shard glyph advances,
+    with a constant-width subject (per-layer width rule from matvec) inside."""
+    total = " + ".join(f"anchor-size({glyph_anchor(s, i)} width)" for s in range(shard_count))
+    return (
+        f'<div class="scroller {SUM_CLASS}" style="width:calc({total})"><div class="track">'
+        f'<i class="metric" style="view-timeline:{timeline} inline"></i></div></div>'
+    )
+
+
+def marker_carrier(width_expression, timeline):
+    return (
+        f'<div class="scroller {MARK_CLASS}"><div class="track">'
+        f'<i class="metric" style="width:{width_expression};view-timeline:{timeline} inline"></i></div></div>'
+    )
+
+
+def stage_css(stem, viewport):
+    """Per-layer (specialize()d) rules: subject width V and the marker scroller's V / 3V."""
+    return (
+        f".{stem} .{SUM_CLASS} .metric{{width:{viewport}px}}"
+        f".{stem} .{MARK_CLASS}{{width:{viewport}px}}.{stem} .{MARK_CLASS}>.track{{width:{3 * viewport}px}}"
+    )
+
+
+def raw_width(viewport, progress):
+    """Scroller width S from the subject's progress p = S / (S + V)."""
+    return f"({viewport} * var({progress}) / (1 - var({progress})))"
+
+
+def manifest():
+    return {
+        "r5cCtxChain": CTX_CHAIN,
+        "r5cCtxChains": W // SHARD if CTX_CHAIN else 0,
+        "r5cCtxChainContainers": W // 2 if CTX_CHAIN else 0,
+        "r5cCtxAnchors": W if CTX_CHAIN else 0,
+        "r5cGlyphAnchors": W * (W // SHARD) if CTX_CHAIN else 0,
+        "r5cSumScrollers": W if CTX_CHAIN else 0,
+    }
```
- READY created 2026-09-24 15:35:12 (8/8 ids, verify rc 0).

- **CLOSED / DO-NOT-MERGE (B6 verdict, R5C.md §8):** correct but +1.6 s/token vs combined7 (384 interleaved container recalcs per layer ≈0.35 ms each outweigh the 6 frames saved).
