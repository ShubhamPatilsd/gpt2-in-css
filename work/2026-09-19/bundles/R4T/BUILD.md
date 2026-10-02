# bundles/R4T — combined4 + R4T_CONSUMER_CHUNK=64 (≤ 64 view-timeline animations per consumer element)

Built by R4T on 2026-09-21 (`work/2026-09-19/R4T/compile-R4T.sh R4T 12 8`; tools copy `work/2026-09-19/R4T/tools` = `R3M/tools` + `r4t_consumer_chunk.py`
+ 5 patched files, diff below / `R4T/tools-vs-R3M.diff`; fonts and F2's projection shards reused via the `experiments` / `data` / `assets -> ../F4/assets` /
`global-projection-assets -> ../F2/…` symlinks beside the tools copy — no new font files). Recipe = `bundles/combined4/BUILD.md` + one flag.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4T
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R2G_SCOPED_HAS=1 R3R_FOLD_HOP=1 R3H_BLOCKFLOW_MAX=1
export R4T_CONSUMER_CHUNK=64
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R4T
```

## Flag

| flag | default | effect |
|---|---|---|
| `R4T_CONSUMER_CHUNK` | 64 | animations per consumer element for the matvec consumers (`.shared-qkv/attn/fc-cN`: 512 → 64), the cache bridge and the b11 bridge (`.cache-bridge-cN`, `.b11-bridge-cN`: 512 → 64), the R3R loop reader (`.loop-reader` 768 → 12 nested `.loop-reader-cK`), the embedding consumers (`.embedding-consumer-N` 256 → 64). `0` = off (= combined4). Manifest `r4tConsumerChunk`. |

Why (`work/2026-09-19/R4T.md`): Blink's per-frame cost for a carrier whose width changed is 14 µs + 46 ns × (animations on its consumer element)
(fixture fit, R² 0.996): 38 µs at 512 (= R3A's measured 40 µs), 17 µs at 64, flat below (knee). Same animations, same decode declarations, same
passes and frames — only the elements holding the `animation-name`/`animation-timeline` lists are split (each chunk element is an ancestor of the
readers; every published number is an inherited registered property).

## Offline verification (`work/2026-09-19/R4T/offline_check_r4t.py bundles/R4T bundles/combined4`, log `R4T/offline_check-R4T.log`)

```
max animations per element (bundle): {'.shared-qkv-cN': 64, '.shared-attn-cN': 64, '.shared-fc-cN': 64, '.cache-bridge-cN': 64, '.fvs-score-reader': 96, '.loop-reader-cN': 64, '.bN-bridge-cN': 64, '.embedding-consumer-N': 64, '.feedback-reader': 8}
max animations per element (ref):    {'.shared-qkv-cN': 512, '.shared-attn-cN': 512, '.shared-fc-cN': 512, '.cache-bridge-cN': 512, '.fvs-score-reader': 96, '.loop-reader': 768, '.bN-bridge-cN': 512, '.embedding-consumer-N': 256, '.feedback-reader': 8}
consumer elements bundle/ref: 1200 164
non-consumer CSS identical (38973628 B ref, 39129954 B bundle incl. consumer rules)
elements bundle/ref: 67525 67401 delta 124
HTML identical modulo consumer wrapper elements
manifest keys differing: {'r4tConsumerChunk': (None, 64)}
font-witnesses identical (modulo tools dir): True 283
RESULT: PASS
```

Reading: every consumer element now carries ≤ 64 animations (`.fvs-score-reader` 96 untouched, `.feedback-reader` 8); the multiset of (stage, keyframe,
timeline) pairs and of the published declarations over all consumer elements equals combined4's (checked per stem); the animation timing properties
per stem are unchanged; the CSS with the consumer rules removed is byte-identical to combined4's; the HTML is identical once the 1,200 − 164 wrapper
elements are collapsed (+124 elements, all in the reused core); the manifest differs only by `r4tConsumerChunk`; 283/283 font witnesses identical
(keys modulo the tools dir). Static check (`tools/launch_browser_gpt2.py --check`): 285,654,970 asset bytes, no JavaScript. Sizes: runtime.css
39,129,954 B (combined4 38,973,628 — the extra 156 KB are the repeated `animation-duration/timing-function/fill-mode/range` per chunk element),
index.html +≈9 KB.

## Chrome runs
- First 2-layer smoke (01:37) FAILED: ids [44873, 9890]; cause = `--lp-*` (inherits:false) forwarded one level at `.loop-input`; fixed by forwarding through the `.loop-reader-cK` chain (`R4T.md` §Step-2 failure). Bundle rebuilt from the fixed tools by `R4T/finish_v2.sh`.
- 2-layer smoke `bundles/smoke-R4T-2L` (fixed) vs `smoke-R4T-2L-ref` (chunk 0, same tools), 01:00: ids [11, 3387] both; frames 26 / UpdateLayoutTree 53 / Layout 32 both; paint lifecycle 396 vs 1,018 ms (`R4T/runs/smoke-R4T-2L{,-ref}/`).
- ONE passive 8-token correctness run (`R4T/run_correctness.sh R4T`): see below / `R4T.md`.

## Diff of the tools copy vs `work/2026-09-19/R3M/tools` (`diff -ru`, = `R4T/tools-vs-R3M.diff`, after the fix)

```diff
Only in R3M/tools: __pycache__
diff -ru R3M/tools/browser_gpt2_embedding.py R4T/tools/browser_gpt2_embedding.py
--- R3M/tools/browser_gpt2_embedding.py	2026-09-20 22:01:52
+++ R4T/tools/browser_gpt2_embedding.py	2026-09-21 00:12:46
@@ -10,6 +10,7 @@
 import build_hvar_token_embedding_lookup as lookup
 import numpy as np
 import r2c_hoist as r2c
+import r4t_consumer_chunk as r4t
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 
 ROOT = Path(__file__).resolve().parents[1]
@@ -69,16 +70,18 @@
         for i in range(768)
     )
     child = '<div id="embedding-result">{child}</div>'
-    for start in reversed(range(0, 768, 256)):
+    step = r4t.chunk(256)  # R4T: animations per consumer element
+    for start in reversed(range(0, 768, step)):
+        stop = min(768, start + step)
         css += (
             f".embedding-consumer-{start}{{animation-name:"
-            + ",".join(f"embedk{i}" for i in range(start, start + 256))
+            + ",".join(f"embedk{i}" for i in range(start, stop))
             + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
-            + ",".join(f"--embed-t{i}" for i in range(start, start + 256))
+            + ",".join(f"--embed-t{i}" for i in range(start, stop))
             + ";"
             + ";".join(
                 f"--embed-{i:03d}:calc((65536 / var(--embedp-{i:03d}) - 65536 - 20000) / 4096)"
-                for i in range(start, start + 256)
+                for i in range(start, stop)
             )
             + "}"
         )
diff -ru R3M/tools/browser_gpt2_reused_adapter.py R4T/tools/browser_gpt2_reused_adapter.py
--- R3M/tools/browser_gpt2_reused_adapter.py	2026-09-20 22:01:52
+++ R4T/tools/browser_gpt2_reused_adapter.py	2026-09-21 00:16:53
@@ -14,6 +14,7 @@
 from browser_gpt2_reused_core import compile_reused
 import r2f_lean_handshake as r2f
 import r3r_fold_hop as r3r
+import r4t_consumer_chunk as r4t
 
 
 def compile_reused_runtime_core(
@@ -77,7 +78,7 @@
         )
 
     last = blocks - 1
-    source, receiver, bridge_css, _ = hybrid.bridge(last, 512)
+    source, receiver, bridge_css, _ = hybrid.bridge(last, r4t.chunk(512))  # R4T: b11-bridge consumers
     source = source.replace("var(--epoch)", "var(--position)")
     export = (
         '<div class="reused-final-export">'
@@ -247,6 +248,7 @@
         "r2cHoistStages": r2c.HOIST_STAGES,
         "r2cHoistQuery": r2c.HOIST_QUERY and codec == "font-vector",
         "r2cHoistEmbedding": r2c.HOIST_EMBEDDING,
+        "r4tConsumerChunk": r4t.CHUNK,
         "kvStorage": "native remembered layout"
         if codec == "geometry"
         else "native delayed whole-head font settings"
diff -ru R3M/tools/browser_gpt2_reused_core.py R4T/tools/browser_gpt2_reused_core.py
--- R3M/tools/browser_gpt2_reused_core.py	2026-09-20 22:01:52
+++ R4T/tools/browser_gpt2_reused_core.py	2026-09-21 00:12:46
@@ -16,6 +16,7 @@
 import f5_scoping as f5
 import r2c_hoist as r2c
 import r3r_fold_hop as r3r
+import r4t_consumer_chunk as r4t
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
     TOKENS,
@@ -170,7 +171,7 @@
                     h.names(src, count),
                     h.names(target, len(biases[i])),
                     1,
-                    512,
+                    r4t.chunk(512),
                     compact=True,
                     gated=True,
                     dynamic_range=True,
@@ -197,7 +198,7 @@
     # Cache storage stays outside the dense MLP subtree. Only the selected
     # layer exports a context vector through layout. Scalar banks are siblings;
     # whole-font-vector banks nest private state around one attention graph.
-    ctx_source, ctx_receiver, ctx_css, _ = h.bridge(100, 512)
+    ctx_source, ctx_receiver, ctx_css, _ = h.bridge(100, r4t.chunk(512))
     ctx_source = ctx_source.replace("b100-bridge", "cache-bridge").replace(
         "--out-", "--ctx-"
     )
diff -ru R3M/tools/r2g_has_scope.py R4T/tools/r2g_has_scope.py
--- R3M/tools/r2g_has_scope.py	2026-09-20 22:01:52
+++ R4T/tools/r2g_has_scope.py	2026-09-21 00:12:46
@@ -23,7 +23,9 @@
 
 SCOPED_HAS = os.environ.get("R2G_SCOPED_HAS", "1") not in ("0", "false", "no", "off")
 
-LOOP_CHAIN = [".core-block", ".loop-reader", ".loop-input", ".loop-signals"]
+import r4t_consumer_chunk as _r4t
+
+LOOP_CHAIN = [".core-block", ".loop-reader", *(f".{c}" for c in _r4t.loop_reader_classes(768)), ".loop-input", ".loop-signals"]
 
 
 class _Paths(html.parser.HTMLParser):
diff -ru R3M/tools/r3r_fold_hop.py R4T/tools/r3r_fold_hop.py
--- R3M/tools/r3r_fold_hop.py	2026-09-20 22:01:52
+++ R4T/tools/r3r_fold_hop.py	2026-09-21 00:46:44
@@ -46,6 +46,7 @@
 
 import os
 
+import r4t_consumer_chunk as r4t
 from build_pretrained_gpt2 import css_number as num
 
 
@@ -124,14 +125,31 @@
         "@keyframes prstamp{from{--pr-stamp:-2}to{--pr-stamp:1}}"
     )
     css += "".join(f"@keyframes lpk{i}{{from{{--lp-{i}:-2}}to{{--lp-{i}:1}}}}" for i in range(width))
+    chunk_classes = r4t.loop_reader_classes(width)
+    if chunk_classes:
+        # R4T: the 768 reader animations spread over nested .loop-reader-cK elements (≤ R4T_CONSUMER_CHUNK each);
+        # --lp-* are inherited registered numbers, so .loop-input reads them unchanged.
+        for k, cls in enumerate(chunk_classes):
+            ids = range(k * r4t.CHUNK, min(width, (k + 1) * r4t.CHUNK))
+            # --lp-* are registered inherits:false by the core's scoped_state and forwarded with `inherit` at .loop-input
+            # (one level): every chunk element must forward the earlier chunks' values so the innermost one holds all of them.
+            forward = "".join(f";--lp-{i}:inherit" for i in range(0, k * r4t.CHUNK))
+            css += (
+                f".{cls}{{animation-name:"
+                + ",".join(f"lpk{i}" for i in ids)
+                + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
+                + ",".join(TIMELINE.format(i=i) for i in ids)
+                + ";animation-range:cover" + forward + "}"
+            )
+    else:
+        css += (
+            ".loop-reader{animation-name:"
+            + ",".join(f"lpk{i}" for i in range(width))
+            + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
+            + ",".join(TIMELINE.format(i=i) for i in range(width))
+            + ";animation-range:cover}"
+        )
     css += (
-        ".loop-reader{animation-name:"
-        + ",".join(f"lpk{i}" for i in range(width))
-        + ";animation-duration:1s;animation-timing-function:linear;animation-fill-mode:both;animation-timeline:"
-        + ",".join(TIMELINE.format(i=i) for i in range(width))
-        + ";animation-range:cover}"
-    )
-    css += (
         ".loop-input{"
         + ";".join(f"--loop-in-{i}:calc({DECODE.format(p=f'--lp-{i}')})" for i in range(width))
         + ";--loop-ready:1}"
@@ -145,8 +163,12 @@
     for token in range(1, capacity):
         css += f"body:has(#token-{token}-advanced.done){{--pass-cap:{(token + 1) * blocks}}}"
     source = (
-        '<div class="loop-reader"><div class="loop-input"><svg class="loop-signals"></svg>'
-        '<div class="loop-compute">{child}</div></div></div>'
+        '<div class="loop-reader">'
+        + "".join(f'<div class="{cls}">' for cls in chunk_classes)
+        + '<div class="loop-input"><svg class="loop-signals"></svg>'
+        '<div class="loop-compute">{child}</div></div>'
+        + "</div>" * len(chunk_classes)
+        + "</div>"
     )
     return source, "{child}", css
 
Only in R4T/tools: r4t_consumer_chunk.py
```
