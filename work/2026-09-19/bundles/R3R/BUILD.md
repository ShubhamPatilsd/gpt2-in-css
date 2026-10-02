# bundles/R3R — combined3 + R3R fold (loop-transport hop folded into the proj readback)

Built by R3R on 2026-09-20 21:53 (`work/2026-09-19/R3R/compile.sh R3R`, ≈11 s; fonts reused through the `experiments` / `global-projection-assets -> ../F2/…` /
`assets -> ../F4/assets` symlinks beside the tools copy — no new font files, 283 faces as combined3). Recipe = `bundles/combined3/BUILD.md` with the tools copy
`work/2026-09-19/R3R/tools` (= R2H/tools + `r3r_fold_hop.py` + hooks in `build_hybrid_twelve_block.py`, `browser_gpt2_reused_core.py`, `browser_gpt2_reused_adapter.py`).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R3R
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R3R_FOLD_HOP=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R3R
```

## Flag

| flag | default | effect (`work/2026-09-19/R3R.md`) |
|---|---|---|
| `R3R_FOLD_HOP` | 1 | proj carriers publish `262144px + 128·(r + proj)` via `calc-size(max-content, …)` with per-layer constants on `.shared-proj`; proj timelines scoped on `html`; `.loop-reader` / `.core-pass-reader` read them directly (`--pass = min(marker+1, cap)`); no loop banks, no `--saved-*` latches, no proj number consumers; `.loop-compute` display-locked while the pass is held (`--held`), layer-11 export moved beside it reading `--loop-in-*`. `0` reproduces R2H's output byte-for-byte (checked on the 2-layer build). Manifest key `r3rFoldHop`. |

All other flags as combined3 (R2G's `:has()` scoping is not included: the base is R2H).

## Offline verification (`R3R/offline_check.py R3R combined3`, log `R3R/offline_check-R3R.log`)

PASS: rule diff limited to the intended categories (removed: 7,030 loop-bank/latch rules incl. 1,538 `--saved`/`--lp` registrations and keyframes, 24 proj
consumer rules, 12 proj receipts/scopes/viewports per layer, old controller/loop-input/loop-reader, SMIL pulse keyframes, pass-1 `--initial` rule; added:
new controller/pass reader/loop-input/loop-reader + 768 `lpk` keyframes/`--lp` registrations, 1,536 `--pk/--pc` registrations + 12 per-layer constant rules,
2 `--held` rules, 96 pass stamps without the banks, html-scoped proj timelines, pinned proj viewport 524288 / marker base 131072); font witnesses 283/283
identical to combined3 (keys modulo tools dir); same 283 font `url()`s; index.html: 0 loop banks, 0 proj consumers, 768 folded carriers, export after
`svg.loop-signals` reading `--loop-in-*`; −1,546 elements. `launch_browser_gpt2.py --check`: 285,478,409 asset bytes, no JavaScript.
NumPy reference (`R3R/reference_ids.py`, R3R tools): `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected.

## Chrome runs

- 2-layer smoke `bundles/smoke-R3R-2L` (2 blocks, 2 positions; `smoke-R3R-2L-ref` = flag off): ids `[11, 3387]` = reference; per layer 6 passes / 3 frames
  (`R3R/runs/smoke-R3R-2L/frames.md`).
- 12-layer correctness run (ONE passive run, F4 harness, 21:56–21:59, AC): ids `[11, 314, 1101, 7926, 11, 475, 314, 1101]` 8/8, verify rc=0, finalResidualError rmse 0.017645 / max 0.13388 (combined3: 0.020059 / 0.18732 — transport rounds differently, §1.5 of R3R.md), RecalcStyleCount 982 / LayoutCount 625 (R3F 1116 / 720). `R3R/run-R3R/`. READY created 2026-09-20.

## diff -ruN work/2026-09-19/R2H/tools work/2026-09-19/R3R/tools

```diff
diff -ruN -x _ ../R2H/tools/browser_gpt2_reused_adapter.py tools/browser_gpt2_reused_adapter.py
--- ../R2H/tools/browser_gpt2_reused_adapter.py	2026-09-19 10:10:29
+++ tools/browser_gpt2_reused_adapter.py	2026-09-20 21:47:30
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
diff -ruN -x _ ../R2H/tools/browser_gpt2_reused_core.py tools/browser_gpt2_reused_core.py
--- ../R2H/tools/browser_gpt2_reused_core.py	2026-09-19 10:10:29
+++ tools/browser_gpt2_reused_core.py	2026-09-20 21:50:36
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
diff -ruN -x _ ../R2H/tools/build_hybrid_twelve_block.py tools/build_hybrid_twelve_block.py
--- ../R2H/tools/build_hybrid_twelve_block.py	2026-09-19 10:10:29
+++ tools/build_hybrid_twelve_block.py	2026-09-20 21:47:30
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
diff -ruN -x _ ../R2H/tools/r3r_fold_hop.py tools/r3r_fold_hop.py
--- ../R2H/tools/r3r_fold_hop.py	1969-12-31 16:00:00
+++ tools/r3r_fold_hop.py	2026-09-20 21:46:26
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
