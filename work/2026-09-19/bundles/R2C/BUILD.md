# bundles/R2C — combined (F2 + F5 + F4) + hoisted `font-variation-settings` arithmetic (R2C)

Built by R2C on 2026-09-19 (`work/2026-09-19/R2C/compile-R2C.sh`, 5 s). Same recipe as `bundles/combined/BUILD.md`
(F2/F5/F4 flags default ON) plus R2C's flags, default ON: `R2C_HOIST_FVS` (master), `R2C_HOIST_STAGES`, `R2C_HOIST_QUERY`,
`R2C_HOIST_EMBEDDING` (`=0` disables one population). Sibling `bundles/R2C-qonly` = the same build with `R2C_HOIST_STAGES=0`
(query + embedding hoists only; offline-verified, NOT Chrome-run, no READY).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R2C
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R2C
```

## What R2C changed in the emitted bundle (vs `bundles/combined`)

| list | combined entry | R2C entry | hoisted declaration (once, on the SAME element, registered `<number>` `inherits:false`) |
|---|---|---|---|
| `.shared-qkv` / `.shared-attn` / `.shared-fc` (768 entries, 12 layer rules each) | `"A000" calc(var(--n1-000) / var(--range-qkv))` | `"A000" var(--fq-qkv-000)` | `.shared-qkv{--fq-qkv-000:calc(var(--n1-000) / var(--range-qkv));…}` — ONE top-level rule per stage (identical for all layers, lifted out of the `@container runtime style(--layer:L)` blocks) |
| `.shared-proj` (3,072 entries) | `"X000" calc(var(--hidden-000) / var(--range-proj))` | `"X000" var(--fq-proj-0000)` | `.shared-proj{--fq-proj-0000:calc(var(--hidden-000) / var(--range-proj));…}` |
| `--fvs-query-H` on `.fvs-query` (12 × 64 entries; read by the 8 score glyphs of head H) | `"Q000" calc(var(--qkv-000) / var(--fqs-0))` | `"Q000" var(--fq-q-0-0)` | `.fvs-query{--fq-q-0-0:calc(var(--qkv-000) / var(--fqs-0));…}` (F4's `--fvn` pattern) |
| `.embedding-source` (2 entries) | `"GRUP" round(down,calc(var(--token) / 256),1),"LOCL" mod(var(--token),256)` | `"GRUP" var(--fq-token-group),"LOCL" var(--fq-token-local)` | `.embedding-source{--fq-token-group:round(down,calc(var(--token) / 256),1);--fq-token-local:mod(var(--token),256)}` |

Every hoisted expression is the ORIGINAL entry's arithmetic byte-for-byte (`R2C/offline_check.py` (a): 65,282 entries compared,
65,282 identical; the declaration text is generated from the matched entry). 6,146 new `@property … <number> inherits:false`
registrations (2,304 + 3,072 + 768 + 2), each once; `.head-isolation` wall exempts `--fq-*` (never inherited). No HTML change
(index.html identical), no font change (283 witnesses identical), `--range-*`/`--fqs-*` untouched.
var()/calc() per list element: qkv/attn/fc 1,536/768 -> 768/0; proj 6,144/3,072 -> 3,072/0; `--fvs-query-H` 128/64 -> 64/0 (per score glyph:
64 calc parses removed); embedding 2/1 -> 2/0. runtime.css 41,666,858 B -> 40,927,799 B; `launch_browser_gpt2.py --check` 285 static
files / 286,719,849 B. Asset URLs relative (`../../F4/assets/...`, `../../F2/global-projection-assets/...`, `../../../../experiments/...`).
Chrome correctness run: see `work/2026-09-19/R2C.md` §4 (READY is created only if it passes).

## Tools copy

`work/2026-09-19/R2C/tools` = `work/2026-09-19/F4/tools` + `r2c_hoist.py` and edits to `build_hybrid_twelve_block.py` (matvec),
`browser_gpt2_reused_core.py` (specialize lift), `browser_gpt2_font_vector_cache.py` (query lists), `browser_gpt2_embedding.py`,
`browser_gpt2_runtime.py` (wall exemption), `browser_gpt2_reused_adapter.py` (manifest). Symlinks beside the copy: `experiments`, `data`,
`global-projection-assets -> ../F2/global-projection-assets`, `assets -> ../F4/assets` (no font copies made).

## `diff -ru -x __pycache__ work/2026-09-19/F4/tools work/2026-09-19/R2C/tools`

```diff
diff -ru -x __pycache__ F4/tools/browser_gpt2_embedding.py R2C/tools/browser_gpt2_embedding.py
--- F4/tools/browser_gpt2_embedding.py	2026-09-18 18:18:20
+++ R2C/tools/browser_gpt2_embedding.py	2026-09-19 02:36:01
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
diff -ru -x __pycache__ F4/tools/browser_gpt2_font_vector_cache.py R2C/tools/browser_gpt2_font_vector_cache.py
--- F4/tools/browser_gpt2_font_vector_cache.py	2026-09-18 19:38:03
+++ R2C/tools/browser_gpt2_font_vector_cache.py	2026-09-19 02:36:01
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
diff -ru -x __pycache__ F4/tools/browser_gpt2_reused_adapter.py R2C/tools/browser_gpt2_reused_adapter.py
--- F4/tools/browser_gpt2_reused_adapter.py	2026-09-18 19:38:03
+++ R2C/tools/browser_gpt2_reused_adapter.py	2026-09-19 02:36:01
@@ -10,6 +10,7 @@
 import build_hybrid_twelve_block as hybrid
 import f4_packing as f4
 import f5_scoping as f5
+import r2c_hoist as r2c
 from browser_gpt2_reused_core import compile_reused
 
 
@@ -220,6 +221,10 @@
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
diff -ru -x __pycache__ F4/tools/browser_gpt2_reused_core.py R2C/tools/browser_gpt2_reused_core.py
--- F4/tools/browser_gpt2_reused_core.py	2026-09-18 18:20:03
+++ R2C/tools/browser_gpt2_reused_core.py	2026-09-19 02:36:01
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
diff -ru -x __pycache__ F4/tools/browser_gpt2_runtime.py R2C/tools/browser_gpt2_runtime.py
--- F4/tools/browser_gpt2_runtime.py	2026-09-18 19:38:03
+++ R2C/tools/browser_gpt2_runtime.py	2026-09-19 02:36:01
@@ -19,6 +19,7 @@
 import build_hybrid_twelve_block as hybrid
 import f4_packing as f4
 import f5_scoping as f5
+import r2c_hoist as r2c
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -301,6 +302,8 @@
             and p != "--head-fvs"
             and not re.fullmatch(r"--hq-\d+", p)
             and not re.fullmatch(r"--fvn-[kv]-\d+-\d+", p)
+            # R2C: hoisted list quotients are inherits:false scratch; no wall needed
+            and not p.startswith(r2c.PREFIX)
             # F2: inherits:false fc scratch cannot reach the head; no wall needed
             and not re.fullmatch(r"--f[zt]-\d+", p)
         ]
diff -ru -x __pycache__ F4/tools/build_hybrid_twelve_block.py R2C/tools/build_hybrid_twelve_block.py
--- F4/tools/build_hybrid_twelve_block.py	2026-09-18 18:20:03
+++ R2C/tools/build_hybrid_twelve_block.py	2026-09-19 02:36:01
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
Only in R2C/tools: r2c_hoist.py
```

## `diff -ru -x __pycache__ tools work/2026-09-19/R2C/tools` (vs the repo tools, includes F2/F5/F4)

See `work/2026-09-19/R2C/tools-vs-repo.diff` (10 files, 47 hunks); the F2/F5/F4 parts are reproduced in `bundles/combined/BUILD.md`.
