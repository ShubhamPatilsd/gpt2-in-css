# bundles/F2 — Fix 2: slim the dense leaf populations (proj packs, V glyphs) + inline GELU

Built by F2 on 2026-09-18 17:42 from the patched tools copy `work/2026-09-19/F2/tools` (`experiments`/`data`
symlinks beside it, as B0). Same command as `work/2026-09-19/B0/compile-baseline.sh`; the copy's new flags
`--global-projection`, `--value-weight-once`, `--inline-gelu` default ON (`--no-…` restores the baseline emitter).

## Exact command (`work/2026-09-19/F2/compile-F2.sh`)

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F2
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/F2
```

First build 2:44 wall (120 retagged projection shard fonts for layers 2–11 generated into
`work/2026-09-19/F2/global-projection-assets/`, 245 KB each; layers 0–1 copied from
`experiments/browser-gpt2/global-projection-assets/`; nothing under `experiments/` was written); rebuilds 9 s.
Asset URLs in runtime.css point at `../../../../experiments/...` (symlink resolved) and
`../../F2/global-projection-assets/...`; both are under the repo root served by `tools/serve_precompressed.py`.

## What changed in the emitted bundle (vs `bundles/baseline`)

| | baseline | F2 |
|---|---:|---:|
| runtime.css | 34,876,568 B | 41,266,846 B (−1.28 MB packs/dead rules, +7.67 MB inline GELU: 3 typed decls × 3,072 outputs × 12 layers) |
| index.html | 6,750,560 B | 6,649,184 B |
| elements | 72,549 | 69,477 (−3,072 `i.shared-proj-packP`) |
| `.shared-proj-packP` rules | 48 × 39,770 B (1,536 var(), 768 calc() each) on 3,072 leaves = 122.2 MB declared per full restyle | none — one 158,903 B 3,072-axis list on `.shared-proj` (1 element per layer; fonts retagged to disjoint `X???` axes, HVAR/hmtx/cmap/gvar byte-identical) |
| `.fvs-v-H-S` rule | 226 B, 4 var() + 1 calc() (+ `.metric i` 28 B) on 6,144 leaves = 1.56 MB | 83.5 B, 2 var(), 0 calc (+ 28 B) = 0.69 MB; per-(H,S) weight `--fw-H-S` computed once on `.fvs-score-reader` (96 decls) |
| `.fvs-value-row` | `font:0px monospace` | carries `font:1024px FvsValue;font-kerning:none;white-space:pre` (inherited by the glyphs) |
| fc consumers `.shared-fc-cN` | 512 × `--hidden-i:--gelu(calc(…))` (@function call per output; 36,864 calls in the sheet) | 512 × (`--fz-i:calc(…)`, `--ft-i:clamp(…)`, `--hidden-i:calc(tanh form)`) — same double ops, same order; `--fz/--ft` registered `<number>` `inherits:false`, excluded from the `.head-isolation` wall |
| dead `.shared-{qkv,attn,fc}{font-family;font-variation-settings}` pre-shorthand rule | emitted (overridden) | dropped |

Offline witness (`work/2026-09-19/F2/offline_check.py`, log `offline_check.log`): (a) 12 × 3,072 global axis↔input map,
(b) 144 retagged fonts vs source shards (fvar tags/ranges, avar retag, protected tables), (c) 768 proj rows × 12 shard
chars, (d) 96 `--fw` hoists = removed per-glyph calc, (e) selector-level diff limited to the rules above — all ok.

## `diff -ru -x __pycache__ tools work/2026-09-19/F2/tools`

```diff
diff -ru -x __pycache__ tools/browser_gpt2_font_vector_cache.py work/2026-09-19/F2/tools/browser_gpt2_font_vector_cache.py
--- tools/browser_gpt2_font_vector_cache.py	2026-09-17 00:53:12
+++ work/2026-09-19/F2/tools/browser_gpt2_font_vector_cache.py	2026-09-18 17:26:01
@@ -144,6 +144,7 @@
     kv_sinks=0,
     value_layout="runs",
     prewarm_values=False,
+    value_weight_once=True,
 ):
     positions = capacity
     capacity = capacity if kv_window is None else kv_window
@@ -319,6 +320,21 @@
     css += ".fvs-score-reader{" + ";".join(soft) + "}"
     value = operators["value"]
     value_unit = VALUE_SIZE / UNITS_PER_EM
+    slim_glyphs = value_weight_once and value_layout == "runs"
+    if slim_glyphs:
+        # F2: each (head, slot) softmax weight is one registered number on the
+        # score reader; every V glyph references it instead of re-evaluating
+        # calc(var()*var()/var()). The reader sits inside the banks, so the
+        # inherited --fr-vs alias is visible there. Numerically identical.
+        weight_fields = [
+            f"--fw-{head}-{slot}" for head in range(HEADS) for slot in range(capacity)
+        ]
+        css += hybrid.regs(weight_fields)
+        css += ".fvs-score-reader{" + ";".join(
+            f"--fw-{head}-{slot}:calc(var(--fe-{head}-{slot}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
+            for head in range(HEADS)
+            for slot in range(capacity)
+        ) + "}"
     for head in range(HEADS):
         combined_settings = []
         for slot in range(capacity):
@@ -328,7 +344,9 @@
             # maximum scale after native inline width summation. Large neural
             # activations therefore cannot saturate individual glyph advances.
             weight = (
-                f"calc(var({exponent}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
+                f"var(--fw-{head}-{slot})"
+                if slim_glyphs
+                else f"calc(var({exponent}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
             )
             settings = f'"P000" {weight}'
             if value_layout == "fallback":
@@ -344,7 +362,13 @@
                     settings = '"P000" 1'
                     base_pixels = value["base"] * value_unit
                     width_rule = f"width:calc-size(max-content,calc({base_pixels:.12g}px + (size - {base_pixels:.12g}px) * {weight}));min-width:0;"
-                css += f".fvs-v-{head}-{slot}{{font-family:FvsValue;font-size:{VALUE_SIZE}px;font-variation-settings:var(--fr-v-{slot}-{head}),{settings};font-kerning:none;font-style:normal;display:block;white-space:pre;flex:none}}"
+                if slim_glyphs:
+                    # font-family/size/kerning/white-space inherit from the row
+                    # rule below; flex items are blockified; .metric i already
+                    # sets font-style. Only the per-(head, slot) list remains.
+                    css += f".fvs-v-{head}-{slot}{{font-variation-settings:var(--fr-v-{slot}-{head}),{settings};flex:none}}"
+                else:
+                    css += f".fvs-v-{head}-{slot}{{font-family:FvsValue;font-size:{VALUE_SIZE}px;font-variation-settings:var(--fr-v-{slot}-{head}),{settings};font-kerning:none;font-style:normal;display:block;white-space:pre;flex:none}}"
                 if width_rule:
                     css += f".fvs-v-{head}-{slot}{{{width_rule}}}"
         if value_layout == "fallback":
@@ -390,6 +414,8 @@
     css += (
         ".fvs-value-row{display:block;white-space:pre;font-style:normal;line-height:1}"
         if value_layout == "fallback"
+        else f".fvs-value-row{{display:inline-flex;gap:0;font:{VALUE_SIZE}px FvsValue;line-height:1;font-kerning:none;white-space:pre}}"
+        if slim_glyphs
         else ".fvs-value-row{display:inline-flex;gap:0;font:0px monospace;line-height:1}"
     )
     body = (
@@ -415,6 +441,7 @@
             "kvSlots": capacity,
             "kvSinks": kv_sinks,
             "valueLayout": value_layout,
+            "valueWeightOnce": slim_glyphs,
             "prewarmValues": prewarm_values,
             "attentionMask": "full causal"
             if capacity == positions
diff -ru -x __pycache__ tools/browser_gpt2_projection_layout.py work/2026-09-19/F2/tools/browser_gpt2_projection_layout.py
--- tools/browser_gpt2_projection_layout.py	2026-09-17 00:18:08
+++ work/2026-09-19/F2/tools/browser_gpt2_projection_layout.py	2026-09-18 17:26:01
@@ -13,7 +13,8 @@
 from fontTools.ttLib import TTFont
 
 ROOT = Path(__file__).resolve().parents[1]
-ASSETS = ROOT / "experiments/browser-gpt2/global-projection-assets"
+# F2 round: retagged shards are generated next to this tools copy.
+ASSETS = Path(__file__).resolve().parents[1] / "global-projection-assets"
 
 
 def global_projection_fonts(directory, group):
diff -ru -x __pycache__ tools/browser_gpt2_reused_adapter.py work/2026-09-19/F2/tools/browser_gpt2_reused_adapter.py
--- tools/browser_gpt2_reused_adapter.py	2026-09-17 00:17:23
+++ work/2026-09-19/F2/tools/browser_gpt2_reused_adapter.py	2026-09-18 17:26:01
@@ -21,6 +21,7 @@
     isolate_metrics=False,
     value_layout="runs",
     global_projection=False,
+    value_weight_once=True,
 ):
     body, css = compile_reused(
         blocks,
@@ -33,6 +34,7 @@
         isolate_metrics=isolate_metrics,
         value_layout=value_layout,
         global_projection=global_projection,
+        value_weight_once=value_weight_once,
     )
     # The enclosing token controller owns root --epoch. Only matrix generation
     # receipts use the finer-grained pass counter, scoped to the shared core.
@@ -153,6 +155,7 @@
         "isolatedMetricState": isolate_metrics,
         "valueLayout": value_layout,
         "globalProjection": global_projection,
+        "valueWeightOnce": value_weight_once and value_layout == "runs",
         "fontVectorOperatorVersion": 2 if codec == "font-vector" else None,
         "attentionMask": "full causal"
         if not kv_window or kv_window == capacity
diff -ru -x __pycache__ tools/browser_gpt2_reused_core.py work/2026-09-19/F2/tools/browser_gpt2_reused_core.py
--- tools/browser_gpt2_reused_core.py	2026-09-17 00:17:23
+++ work/2026-09-19/F2/tools/browser_gpt2_reused_core.py	2026-09-18 17:42:03
@@ -99,6 +99,7 @@
     isolate_metrics=False,
     value_layout="runs",
     global_projection=False,
+    value_weight_once=True,
 ):
     if global_projection and isolate_metrics:
         raise ValueError("Do not combine global projection and metric isolation ablations")
@@ -172,6 +173,13 @@
 
     if isolate_metrics:
         css = isolate_metric_state(css)
+    if h.INLINE_GELU:
+        # private scratch of the fc consumers; never inherited, never reset
+        css += "".join(
+            f'@property {p}{{syntax:"<number>";inherits:false;initial-value:0}}'
+            for stem in ("fz", "ft")
+            for p in h.names(stem, 4 * W)
+        )
 
     # Cache storage stays outside the dense MLP subtree. Only the selected
     # layer exports a context vector through layout. Scalar banks are siblings;
@@ -204,6 +212,7 @@
             kv_window=kv_window,
             kv_sinks=kv_sinks,
             value_layout=value_layout,
+            value_weight_once=value_weight_once,
         )
         css += font_css
     if geometry_cache:
diff -ru -x __pycache__ tools/browser_gpt2_runtime.py work/2026-09-19/F2/tools/browser_gpt2_runtime.py
--- tools/browser_gpt2_runtime.py	2026-09-17 00:31:22
+++ work/2026-09-19/F2/tools/browser_gpt2_runtime.py	2026-09-18 17:42:03
@@ -196,6 +196,7 @@
     font_backend="original",
     value_layout="runs",
     global_projection=False,
+    value_weight_once=True,
 ):
     if global_projection and not reuse_core:
         raise ValueError("Global projection currently requires the reused core")
@@ -235,6 +236,7 @@
             isolate_metrics,
             value_layout,
             global_projection,
+            value_weight_once,
         )
     else:
         core, core_css, metadata = compile_core(
@@ -286,7 +288,10 @@
         reset = [
             p
             for p in reset
-            if not re.fullmatch(r"--h\d+", p) and p != "--head-input-epoch"
+            if not re.fullmatch(r"--h\d+", p)
+            and p != "--head-input-epoch"
+            # F2: inherits:false fc scratch cannot reach the head; no wall needed
+            and not re.fullmatch(r"--f[zt]-\d+", p)
         ]
         css += (
             ".head-isolation{"
@@ -466,7 +471,9 @@
     # There is no local-file URL dependency and no inference API endpoint.
     def relative_asset(match):
         parsed = urlparse(match[1])
-        relative = os.path.relpath(Path(unquote(parsed.path)), directory.resolve())
+        relative = os.path.relpath(
+            Path(unquote(parsed.path)).resolve(), directory.resolve()
+        )
         return (
             'url("'
             + quote(relative, safe="/.-_")
@@ -541,8 +548,17 @@
     parser.add_argument(
         "--value-layout", choices=("runs", "fallback", "widths"), default="runs"
     )
-    parser.add_argument("--global-projection", action="store_true")
+    # F2 round: both leaf-slimming changes default ON; --no-* restores the old emitter.
     parser.add_argument(
+        "--global-projection", action=argparse.BooleanOptionalAction, default=True
+    )
+    parser.add_argument(
+        "--value-weight-once", action=argparse.BooleanOptionalAction, default=True
+    )
+    parser.add_argument(
+        "--inline-gelu", action=argparse.BooleanOptionalAction, default=True
+    )
+    parser.add_argument(
         "--kv-window",
         type=int,
         help="Optional bounded attention context; changes the attention mask",
@@ -570,6 +586,7 @@
         default="scalar",
     )
     args = parser.parse_args()
+    hybrid.INLINE_GELU = args.inline_gelu
     if not 1 <= args.blocks <= 12 or not 2 <= args.capacity <= 32:
         parser.error("blocks must be 1–12; capacity must be 2–32")
     args.output.mkdir(parents=True, exist_ok=True)
@@ -595,6 +612,7 @@
         args.font_backend,
         args.value_layout,
         args.global_projection,
+        args.value_weight_once,
     )
 
 
diff -ru -x __pycache__ tools/build_hybrid_twelve_block.py work/2026-09-19/F2/tools/build_hybrid_twelve_block.py
--- tools/build_hybrid_twelve_block.py	2026-09-17 00:17:23
+++ work/2026-09-19/F2/tools/build_hybrid_twelve_block.py	2026-09-18 17:42:03
@@ -27,6 +27,11 @@
 ASSET_OUT = OUT / "fonts"
 W = 768
 STAGES = ("ln1", "qkv", "mix", "attn", "ln2", "fc", "proj")
+# F2: replace the per-output --gelu() @function call (≈+10 µs each, M1 MB5) by the same
+# arithmetic split over three typed declarations on the consumer element. Same double ops
+# in the same order: --fz = pre-activation, --ft = clamped tanh argument, output = tanh form.
+INLINE_GELU = True
+GELU_K = ".7978845608028654"
 
 
 def names(stem, count):
@@ -164,6 +169,10 @@
         families = ",".join(
             f"{family}S{s}" for s in range(first, len(group.names) if global_axes else min(first + 3, len(group.names)))
         )
+        if compact and packs == 1:
+            # F2: the `font:` shorthand below resets this list and the stage
+            # rule re-declares it afterwards; the early copy never wins.
+            continue
         selector = f".{stem}" if compact and packs == 1 else f".{stem}-pack{pack}"
         css += f"{selector}{{font-family:{families};font-variation-settings:{settings(first)}}}"
     metrics = []
@@ -221,7 +230,15 @@
             gain = f"{num(quantized.scales[i])} * var(--range-{kind})" if dynamic_range else num(activation_range * quantized.scales[i])
             value = f"calc({raw} * {gain} + ({num(bias[i])}))"
             if kind == "fc":
-                value = f"--gelu({value})"
+                if INLINE_GELU:
+                    z, t = f"--fz-{i:03d}", f"--ft-{i:03d}"
+                    result.append(f"{z}:{value}")
+                    result.append(
+                        f"{t}:clamp(-20,calc({GELU_K} * (var({z}) + .044715 * pow(var({z}),3))),20)"
+                    )
+                    value = f"calc(.5 * var({z}) * (1 + (exp(2 * var({t})) - 1) / (exp(2 * var({t})) + 1)))"
+                else:
+                    value = f"--gelu({value})"
             elif kind == "attn":
                 value = f"calc(var(--x-{i:03d}) + {value})"
             elif kind == "proj":
```
