# bundles/F3a — Fix 3 (+ Fix 6 for the MLP hops): frameless fc→proj→out transport, 12 layers, capacity 8

Built by F3b on 2026-09-18/19 from `work/2026-09-19/F3b/tools` = `cp -R work/2026-09-19/F5/tools` (all six F5 flags ON)
+ `f3_chain_mlp.py` (new) + two hooks (`browser_gpt2_reused_core.py` compile_reused, `browser_gpt2_reused_adapter.py`).
Same recipe as `work/2026-09-19/B0/compile-baseline.sh` / `F5/compile-F5.sh`; flags: `F3_CHAIN_MLP=1` (default), `F3_CHAIN_LEVEL=1` (default).

## Exact command (`work/2026-09-19/F3b/compile.sh F3a 12 8`)

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F3b   # has experiments/ and data/ symlinks -> repo
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/F3a
```

Wall 6.7 s, peak RSS 3.0 GB (no fonts rebuilt: the fc/proj HVAR shards already exist under `experiments/`).

## What changed in the emitted page (vs bundles/F5, same tools base)

| | F5 | F3a |
|---|---:|---:|
| inline `view-timeline` carriers | 10,858 | 7,016 (−3,842 = fc 3,072+marker, proj 768+marker) |
| `timeline-scope` rules | 53 | 29 |
| `animation-timeline` rules | 242 | 122 |
| `anchor-name` (inline) | 464 | 12,764 (+3,072 fc rows, +9,216 proj rows, +12 range anchors) |
| `anchor-size(` in CSS | 3,049 | 15,349 |
| `container-type` | 3 | 4 (`.f3-c`: 1,926 fixed size containers) |
| index.html / runtime.css | 5.88 MB / 34.7 MB | 6.23 MB / 31.2 MB |
| max HTML nesting depth | — | 434 (< 512 parser cap; `.f3-mlp` at depth 37, out chain 391 deep) |
| `.shared-fc/-proj` receipt + gate | 2 per layer | 0 (Fix 6 for these hops); qkv/attn/ctx/score gates and the loop-bank latch unchanged |

Per layer: fc glyph rows are `anchor-name` anchors (3 shard glyphs each, fallback fonts sum their advances); 12 chains of 128
`position:fixed; container-type:size` containers sized by `anchor-size()` pairs; each container publishes its parent's two
values through `100cqw/100cqh` as `--hidden-*` (GELU decode); each chain bottom computes the shard's `--range-proj`, publishes
it as an anchor and hosts that shard's 768 proj glyph rows; one 6+384-container out chain sums the 12 shard advances
(`calc(Σ anchor-size(--f3p{j}_{i}) * var(--f3pr{j}))`) and decodes `--out-*` (+ residual `--r-*`) on the element that hosts the
rest of the core. Emission order = data-flow order (Chromium only lets a nested fixed reader see anchors in earlier
out-of-flow roots, F3.md §3b). One element per chain level (`F3_CHAIN_LEVEL=1`): the next container is itself the publisher.

## Offline verification

- `work/2026-09-19/F3b/lint_f3b.py bundles/F3a`: LINT OK — 79,870 elements, max depth 434; the 36 ancestors of `.f3-mlp` carry no
  position/contain/transform/filter/will-change/overflow (only the `content-visibility` gates, visible when the layer is active);
  12,300 `anchor-size()` references all resolve to a unique anchor earlier in tree order (0 order violations); per-layer decode
  declarations 36,864 hidden + 9,216 out; no leftover fc/proj receipts, gates or timelines.
- `font-witnesses.json`: 261 faces, identical codepoint/advance/upem to bundles/F5 (keys differ only by the tools-copy path prefix).
- `tools/launch_browser_gpt2.py --check --directory bundles/F3a`: passes, 278,300,266 asset bytes, `runtimeJavaScript:false`.
- Arithmetic unchanged: same q9 row-quantised weights, same HVAR shard fonts, same decode
  `(advance·UPM/FS − base)·scale·range + bias`, same `--gelu()`; offline reference ids for the run are those of
  `verify_browser_gpt2_runtime.py` (`referenceQ9Q16`), unchanged: 11,314,1101,7926,11,475,314,1101. Prototype B (F3.md §3b)
  measured the identical chain arithmetic on layer 0 at RMSE 3.6–4.0e-3 vs the NumPy witness (timeline path: 1.1e-2).

## Browser correctness run

PASS (`work/2026-09-19/F3b/runs/F3a/`, 2026-09-19 under CHROME.lock, headless Chrome 153, passive 5 s poll): ids 11,314,1101,7926,11,475,314,1101 = 8/8 (`verify_browser_gpt2_runtime.py` tokenAgreement all True), finalResidual rmse 1.42e-2, 96/96 caches; LayoutCount 680 for 8 tokens (85/token vs 109/token for F5). READY created. Details in `F3b.md` §3a.

## Diff of the tools copy vs repo `tools/` (`diff -ruN -x __pycache__ tools work/2026-09-19/F3b/tools`)

The F5 part (first 300 lines of the diff) is the one documented in `bundles/F5/BUILD.md`; the F3b part follows.

```diff
diff -ruN -x __pycache__ tools/browser_gpt2_font_vector_cache.py work/2026-09-19/F3b/tools/browser_gpt2_font_vector_cache.py
--- tools/browser_gpt2_font_vector_cache.py	2026-09-17 00:53:12
+++ work/2026-09-19/F3b/tools/browser_gpt2_font_vector_cache.py	2026-09-18 19:30:42
@@ -11,6 +11,7 @@
 from pathlib import Path
 
 import build_hybrid_twelve_block as hybrid
+import f5_scoping as f5
 import numpy as np
 from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
 from build_gpt2_block_css import UNITS_PER_EM
@@ -168,10 +169,13 @@
         ".fvs-query{container-name:fvscache;--fvs-write-slot:calc(min("
         f"var({write_epoch}) - 1,{kv_sinks} + mod(max(0,var({write_epoch}) - 1 - {kv_sinks}),{capacity - kv_sinks})))}}"
     )
+    literal = f5.BANK_LITERAL_LISTS
     css += (
         ".fvs-query{--fvs-all-fields:"
         + ",".join(all_fields)
-        + "}.fvs-bank{transition-property:var(--fvs-all-fields);transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
+        + "}.fvs-bank{transition-property:"
+        + (",".join(all_fields) if literal else "var(--fvs-all-fields)")
+        + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
     )
     for head in range(HEADS):
         maximum = ",".join(f"abs(var(--qkv-{head * DIM + i:03d}))" for i in range(DIM))
@@ -220,13 +224,30 @@
                 writes.append(
                     f"--fc-{kind}-{slot}-{head}:var(--fvs-live-{kind}-{head})"
                 )
+        retained_value = retained if literal else f"var(--fvs-retained-{slot})"
         for layer in range(blocks):
-            css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{transition-property:var(--fvs-retained-{slot});{';'.join(writes)}}}}}}}"
-    for layer in range(blocks):
-        aliases = ";".join(
-            f"{name.replace('--fc-', '--fr-')}:var({name})" for name in all_fields
-        )
-        css += f"@container runtime style(--layer:{layer}){{.fvs-bank-{layer}{{{aliases}}}}}"
+            css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{transition-property:{retained_value};{';'.join(writes)}}}}}}}"
+    sequential = kv_window is None or (kv_sinks == 0 and capacity == positions)
+    if f5.BANK_FILLED_ALIASES and sequential:
+        # F5: with a full causal window slots fill in order, so while slot S
+        # is being written only slots 0..S hold values; the others equal the
+        # zero initial value that --fr-* already has. Alias only those.
+        for layer in range(blocks):
+            for slot in range(capacity):
+                # names are --fc-{kind}-{slot}-{head}
+                filled = [
+                    name for name in all_fields if int(name.split("-")[-2]) <= slot
+                ]
+                aliases = ";".join(
+                    f"{name.replace('--fc-', '--fr-')}:var({name})" for name in filled
+                )
+                css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{{aliases}}}}}}}"
+    else:
+        for layer in range(blocks):
+            aliases = ";".join(
+                f"{name.replace('--fc-', '--fr-')}:var({name})" for name in all_fields
+            )
+            css += f"@container runtime style(--layer:{layer}){{.fvs-bank-{layer}{{{aliases}}}}}"
     for kind, family in (("dot", "FvsDot"), ("value", "FvsValue")):
         css += f'@font-face{{font-family:{family};src:url("{(FONT_DIR / (kind + ".woff2")).as_uri()}")}}'
     if value_layout == "fallback":
diff -ruN -x __pycache__ tools/browser_gpt2_reused_adapter.py work/2026-09-19/F3b/tools/browser_gpt2_reused_adapter.py
--- tools/browser_gpt2_reused_adapter.py	2026-09-17 00:17:23
+++ work/2026-09-19/F3b/tools/browser_gpt2_reused_adapter.py	2026-09-18 19:44:16
@@ -8,6 +8,8 @@
 import re
 
 import build_hybrid_twelve_block as hybrid
+import f3_chain_mlp as f3
+import f5_scoping as f5
 from browser_gpt2_reused_core import compile_reused
 
 
@@ -109,8 +111,50 @@
         css,
     )
     css += hybrid.regs(["--native-pass"])
-    for step in range(1, blocks * capacity + 1):
-        css += f"@container loopcontrol style(--pass:{step}){{.core-block{{--native-pass:{step}}}}}"
+    if f5.SCOPED_HANDSHAKE:
+        # F5: the pass counter and the layer handshake flags are read by a
+        # handful of elements but, inherited, restyled the whole open core
+        # (P2 Table 3: ~12.27k-element passes). Register them non-inherited
+        # and stamp the current pass directly onto every reader.
+        receipts = [
+            f".shared-{kind}-receipt" for kind in ("qkv", "attn", "fc", "proj")
+        ] + [".cache-bridge-receipt", ".fvs-score-receipt"]
+        pass_readers = ",".join(
+            [
+                ".loop-input",
+                ".loop-bank-0",
+                ".loop-bank-1",
+                ".reused-input",
+                ".fvs-query",
+                ".fvs-score-reader",
+                ".pass-reader",
+            ]
+            + receipts
+        )
+        for step in range(1, blocks * capacity + 1):
+            css += f"@container loopcontrol style(--pass:{step}){{{pass_readers}{{--native-pass:{step}}}}}"
+        css += (
+            ",".join([".pass-reader"] + receipts) + "{--epoch:var(--native-pass)}"
+            ".reused-input,.core-valid,.fvs-query,.fvs-score-reader,.pass-reader{--position:calc(round(down,calc((var(--native-pass) - 1) / "
+            + str(blocks)
+            + "),1) + 1)}"
+        )
+        css = f5.make_private(
+            css, ["--loop-ready", "--loop-ack", "--native-pass", "--position"]
+        )
+        body, tagged = f5.tag_inline_readers(body, "var(--epoch)", "pass-reader")
+        body, tagged_position = f5.tag_inline_readers(
+            body, "var(--position)", "pass-reader"
+        )
+        # F3: the fc and proj generation markers no longer exist (no timeline hop).
+        expected_epoch_readers = 5 if f3.CHAIN_MLP else 7
+        if tagged != expected_epoch_readers or tagged_position != 2:
+            raise ValueError(
+                f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
+            )
+    else:
+        for step in range(1, blocks * capacity + 1):
+            css += f"@container loopcontrol style(--pass:{step}){{.core-block{{--native-pass:{step}}}}}"
     # Style-container invalidation itself can cross private-property boundaries.
     # Move per-layer containers off body entirely, outside the head's ancestry.
     css = re.sub(r"\bbody(?=[{:\s])", ".core-controller", css)
@@ -166,6 +210,13 @@
         "nativeLayerTokenHandshake": True,
         "privateLayerControl": True,
         "localLayerContainer": True,
+        "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
+        "f5ScopedEpoch": f5.SCOPED_EPOCH,
+        "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
+        "f5InlineForward": f5.INLINE_FORWARD,
+        "f5BankFilledAliases": f5.BANK_FILLED_ALIASES,
+        "f5BankLiteralLists": f5.BANK_LITERAL_LISTS,
+        **f3.metadata(),
         "kvStorage": "native remembered layout"
         if codec == "geometry"
         else "native delayed whole-head font settings"
diff -ruN -x __pycache__ tools/browser_gpt2_reused_core.py work/2026-09-19/F3b/tools/browser_gpt2_reused_core.py
--- tools/browser_gpt2_reused_core.py	2026-09-17 00:17:23
+++ work/2026-09-19/F3b/tools/browser_gpt2_reused_core.py	2026-09-18 19:52:34
@@ -13,6 +13,8 @@
 
 import build_gpt2_block_css as b
 import build_hybrid_twelve_block as h
+import f3_chain_mlp as f3
+import f5_scoping as f5
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
     TOKENS,
@@ -102,6 +104,11 @@
 ):
     if global_projection and isolate_metrics:
         raise ValueError("Do not combine global projection and metric isolation ablations")
+    if f3.CHAIN_MLP:
+        # F3: the proj hop no longer has packs or a global axis list; both
+        # ablations only shaped the timeline proj matvec and are moot here.
+        isolate_metrics = False
+        global_projection = False
     geometry_cache = codec == "geometry"
     font_vector_cache = codec == "font-vector"
     custom_cache = geometry_cache or font_vector_cache
@@ -130,6 +137,11 @@
         for kind in h.STAGES:
             if kind == "mix":
                 continue
+            if f3.CHAIN_MLP and kind == "proj":
+                # F3: the fc hop's anchor chains already host the proj shard
+                # columns and the out chain; nothing separate to nest here.
+                layouts[kind] = "{child}"
+                continue
             if kind in ("ln1", "ln2"):
                 n = 1 if kind == "ln1" else 2
                 html, rule = h.wrapper(
@@ -145,6 +157,15 @@
                         )
                     ),
                 )
+            elif f3.CHAIN_MLP and kind == "fc":
+                # F3 (Fix 3 + Fix 6 for the MLP hops): fc glyph rows are anchors,
+                # 12 fixed size-container chains gather them into --hidden-*,
+                # per-shard proj glyph columns hang under each chain bottom and
+                # one out chain sums the 12 shard advances into --out-*; no
+                # view-timeline, no generation receipt, no gate for fc/proj.
+                html, rule, once = f3.mlp_chain(layer, matrices[2], biases[2], matrices[3], biases[3])
+                if layer == 0:
+                    css += once
             else:
                 i = ("qkv", "attn", "fc", "proj").index(kind)
                 src, count = (("n1", W), ("ctx", W), ("n2", W), ("hidden", 4 * W))[i]
@@ -337,12 +358,25 @@
         css += forward(".loop-input", lp)
         css += forward(".loop-bank-0,.loop-bank-1", outputs)
         css += forward(".loop-scroll,.loop-track", saved)
-        for bank in range(2):
-            for i in range(W + 1):
-                css += forward(
-                    f".loop-bank-{bank}>.loop-scroll>.loop-track>.loop-metric:nth-child({i + 1})",
-                    [f"--saved-{bank}-{i}"],
-                )
+        if f5.INLINE_FORWARD:
+            # F5: 1,538 `.loop-metric:nth-child(N)` rules share one class
+            # bucket, so every loop-metric tested all 1,538 selectors on each
+            # restyle (P2: 153 us/element on the 1,553-element pass). The
+            # same forwarding as an inline declaration costs one rule.
+            body, count = re.subn(
+                r'<i class="loop-metric" style="width:calc\(262144px \+ var\((--saved-\d-\d+)\) \* 128px\);',
+                r'<i class="loop-metric" style="\1:inherit;width:calc(262144px + var(\1) * 128px);',
+                body,
+            )
+            if count != 2 * (W + 1):
+                raise ValueError(f"Expected {2 * (W + 1)} loop carriers, found {count}")
+        else:
+            for bank in range(2):
+                for i in range(W + 1):
+                    css += forward(
+                        f".loop-bank-{bank}>.loop-scroll>.loop-track>.loop-metric:nth-child({i + 1})",
+                        [f"--saved-{bank}-{i}"],
+                    )
         css += forward(".cache-active", bank_props)
         css += forward(
             ",".join(f".live-mix-{layer}" for layer in range(blocks)), bank_props
diff -ruN -x __pycache__ tools/browser_gpt2_runtime.py work/2026-09-19/F3b/tools/browser_gpt2_runtime.py
--- tools/browser_gpt2_runtime.py	2026-09-17 00:31:22
+++ work/2026-09-19/F3b/tools/browser_gpt2_runtime.py	2026-09-18 19:30:42
@@ -17,6 +17,7 @@
 
 import build_gpt2_block_css as b
 import build_hybrid_twelve_block as hybrid
+import f5_scoping as f5
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -382,6 +383,40 @@
             ".detached-head-state{--head-output-epoch:round(nearest,100cqi/1px,1);--winner:round(nearest,100cqb/1px,1)}"
             f"@container b{blocks - 1}-bridge style(--bridge-ready:1){{.full-head{{content-visibility:visible}}}}"
         )
+    if f5.SCOPED_FEEDBACK:
+        # F5: the token feedback state lives on .feedback-reader (depth 2,
+        # ~71.9k descendants) and is read by two of its children and by
+        # .embedding-source. Inherited, every readback restyled the document.
+        css = f5.make_private_prefix(
+            css, ["--feedback-", "--frozen-prompt", "--token"]
+        )
+        css += (
+            ".feedback-select,.visible-output{--frozen-prompt:inherit;"
+            + ";".join(f"--feedback-{i}:inherit" for i in range(1, capacity + 1))
+            + "}.embedding-source{--token:inherit}"
+        )
+    if f5.SCOPED_EPOCH and reuse_core and f5.SCOPED_HANDSHAKE:
+        # F5: body{--epoch} inherited into all 72k elements (P2: the whole-DOM
+        # pass at token-N-ack). Stamp the epoch onto its nine readers instead.
+        # Core-internal readers use the pass counter (pass-reader, adapter).
+        epoch_readers = ",".join(
+            [
+                ".epoch-reader",
+                ".embedding-receipt",
+                ".position-embedding",
+                ".feedback-select",
+                ".head-input-bank",
+                f".b{blocks - 1}-bridge-receipt",
+            ]
+        )
+        for e in range(1, capacity + 1):
+            css += f"@container runtime style(--epoch:{e}){{{epoch_readers}{{--epoch:{e}}}}}"
+        css = f5.make_private(css, ["--epoch"])
+        model, tagged = f5.tag_inline_readers(
+            model, "var(--epoch)", "epoch-reader", skip_class="pass-reader"
+        )
+        if tagged != 3:
+            raise ValueError(f"Unexpected inline epoch readers in model: {tagged}")
     font_html, font_css, font_count = font_barrier(css, directory)
     css += font_css
     scopes = re.findall(r"html\{timeline-scope:([^}]+)\}", css)
@@ -430,6 +465,12 @@
     )
 
     controls += '<svg xmlns="http://www.w3.org/2000/svg" class="native-signals"><g id="run-start"></g><g id="run-latched"><set attributeName="class" to="done" begin="run-start.animationend+0.001s" fill="freeze"/></g></svg>'
+    if f5.SCOPED_EPOCH and reuse_core and f5.SCOPED_HANDSHAKE:
+        controls, tagged_controls = f5.tag_inline_readers(
+            controls, "var(--epoch)", "epoch-reader"
+        )
+        if tagged_controls != 1:
+            raise ValueError(f"Unexpected inline epoch readers in controls: {tagged_controls}")
     speed = (
         "Measured warm speed: about 78 seconds/token on M2 Pro."
         if (blocks, capacity) == (12, 8)
diff -ruN -x __pycache__ tools/f3_chain_mlp.py work/2026-09-19/F3b/tools/f3_chain_mlp.py
--- tools/f3_chain_mlp.py	1969-12-31 16:00:00
+++ work/2026-09-19/F3b/tools/f3_chain_mlp.py	2026-09-18 19:55:28
@@ -0,0 +1,242 @@
+"""F3b (2026-09-19): frameless fc -> proj -> out transport for the reused core.
+
+Fix 3 (work/2026-09-19/F3.md): every view-timeline readback costs one frame, one
+extra style pass and one layout per boundary, and re-restyles the downstream
+chain.  A geometry -> number hop through `anchor-size()` on a `position:fixed`
+size container and container-query units on its child resolves inside ONE
+style/layout lifecycle.  This module emits the MLP (fc 768->3072, GELU,
+proj 3072->768, +r) of one layer in that form; the HTML is layer-independent
+(one reused graph), the per-layer constants live in `@container runtime
+style(--layer:L)` rules exactly like the timeline emitter.
+
+Layout of one layer (data-flow order = tree order, F3.md §3b ordering rule):
+
+  .f3-mlp                         common ancestor; --range-fc = max|n2|*1.001
+    .f3-stage.f3-fc (fixed)       3,072 in-flow rows, anchor-name --f3f{i};
+                                  row width = sum of the 3 fc shard glyphs
+                                  (fallback fonts), font-variation-settings = n2
+    12 x fc chains (fixed size containers, one element per level, F3_CHAIN_LEVEL=1)
+      #f3c{j}-{k}                 width/height = anchor-size(--f3f{2k},{2k+1})
+                                  and publishes the PARENT container's two
+                                  values as --hidden-* (GELU decode)
+      #f3r{j} (in-flow bottom)    --range-proj = max|hidden shard j|*1.001,
+                                  anchor #f3m{j} width = range*1024px,
+                                  .f3-stage #f3s{j}: 768 proj glyph rows of
+                                  shard j, anchor-name --f3p{j}_{i}
+    out chain (fixed size containers, 6 range levels + 384 value levels)
+      #f3g{t}                     reads --f3m{2t},{2t+1} -> --f3pr{j}
+      #f3o{k}                     width = sum_j anchor-size(--f3p{j}_{2k}) * --f3pr{j}
+      #f3b (in-flow bottom)       publishes --out-766/767 and hosts {child}
+
+Chromium rules obeyed (F3.md §2/§3b): only `position:fixed` containers (any
+absolute/relative/contained ancestor would become the containing block and hide
+the anchors -> silent zeros); anchors precede their readers in tree order;
+chain depth <= 391 elements (HTML parser nesting cap 512); widths < 2^24 px.
+
+Env flags (default ON):
+  F3_CHAIN_MLP=0     keep the view-timeline matvec() for fc and proj
+  F3_CHAIN_LEVEL=2   fc chains with two elements per level (container + plain
+                     child), the exact Prototype A/B shape; default 1 = the
+                     next container itself publishes its parent's values.
+                     The out chain (768 values = 390 levels) always uses 1.
+"""
+
+import os
+
+import build_gpt2_block_css as b
+import build_hybrid_twelve_block as h
+import numpy as np
+from build_pretrained_gpt2 import css_number as num
+
+W, M = 768, 3072
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+CHAIN_MLP = flag("F3_CHAIN_MLP")
+CHAIN_LEVEL = int(os.environ.get("F3_CHAIN_LEVEL", "1"))
+if CHAIN_LEVEL not in (1, 2):
+    raise ValueError("F3_CHAIN_LEVEL must be 1 or 2")
+
+RANGE_PX = 1024  # --range-proj travels as an anchor of width range*1024px
+SHARDS_PROJ = M // b.SHARD  # 12
+SHARDS_FC = W // b.SHARD  # 3
+FC_CHAIN = b.SHARD // 2  # 128 containers per fc chain (2 values each)
+OUT_CHAIN = W // 2  # 384 containers in the out chain
+RANGE_CHAIN = SHARDS_PROJ // 2  # 6 containers carry the 12 shard ranges
+
+PX_TO_UNITS = f"{b.UNITS_PER_EM} / {b.FONT_SIZE}"
+
+
+def _chain(ids, size, bottom, level):
+    """Nested fixed size containers.
+
+    ids[k]   element id of level k
+    size[k]  (width, height) CSS values for level k (None -> a plain in-flow
+             block: the chain bottom)
+    bottom   html placed inside the last level
+    level    1: level k's element itself publishes level k-1's two values;
+             2: a plain child of k-1 (`#<id>p`) wraps level k and publishes.
+    Returns (html, once_css) with the layer-independent width/height rules;
+    the caller emits the publish declarations (see _publisher).
+    """
+    parts, css, depth = [], [], 0
+    for k, ident in enumerate(ids):
+        if size[k] is not None:
+            css.append(f"#{ident}{{width:{size[k][0]};height:{size[k][1]}}}")
+        if level == 2 and k >= 1:
+            parts.append(f'<div class="f3-p" id="{ident}p">')
+            depth += 1
+        cls = "f3-c" if size[k] is not None else "f3-b"
+        parts.append(f'<div class="{cls}" id="{ident}">')
+        depth += 1
+    parts.append(bottom)
+    parts.append("</div>" * depth)
+    return "".join(parts), "".join(css)
+
+
+def _publisher(ident, level):
+    """Selector of the element publishing the values of the container above `ident`."""
+    return f"#{ident}p" if level == 2 else f"#{ident}"
+
+
+def mlp_chain(layer, qfc, bfc, qproj, bproj):
+    """Return (html, per_layer_css, once_css) for one layer's fc+proj hops.
+
+    html is identical for every layer (checked by compile_reused's layouts
+    identity); per_layer_css is wrapped by specialize() into
+    `@container runtime style(--layer:L)`; once_css must be emitted once.
+    """
+    dfc, gfc = h.font_group(layer, "fc", qfc)
+    dproj, gproj = h.font_group(layer, "proj", qproj)
+    if len(gfc.names) != SHARDS_FC or len(gproj.names) != SHARDS_PROJ:
+        raise ValueError("F3 chain MLP expects 3 fc shards and 12 proj shards")
+    fc_bases = np.sum(np.stack(gfc.row_bases), axis=0)  # (3072,)
+    proj_bases = np.stack(gproj.row_bases)  # (12, 768)
+    n2, hid, outn, r = h.names("n2", W), h.names("hidden", M), h.names("out", W), h.names("r", W)
+    ranges = [f"--f3pr{j}" for j in range(SHARDS_PROJ)]
+    fam_fc, fam_proj = f"b{layer}fc", f"b{layer}proj"
+
+    layer_css = []
+    once = []
+    # --- per-layer font faces (specialize() hoists @font-face out of the layer rule)
+    layer_css.append(b.font_faces(f"b{layer}-fc", gfc).replace('url("', f'url("{dfc.as_uri()}/'))
+    layer_css.append(b.font_faces(f"b{layer}-proj", gproj).replace('url("', f'url("{dproj.as_uri()}/'))
+    layer_css.append(
+        f".f3-fc{{font-family:{','.join(f'{fam_fc}S{s}' for s in range(SHARDS_FC))}}}"
+    )
+    for j in range(SHARDS_PROJ):
+        layer_css.append(f"#f3s{j}{{font-family:{fam_proj}S{j}}}")
+
+    # --- once: registrations, structure, layer-independent settings
+    once.append(h.regs(["--range-fc", "--range-proj"] + ranges))
+    once.append(
+        ".f3-stage{position:fixed;left:0;top:-60000px;visibility:hidden;font-kerning:none;"
+        f"white-space:pre;line-height:1;font-size:{b.FONT_SIZE}px;font-style:normal;font-weight:normal}}"
+        ".f3-row{display:block;height:1px;width:max-content;font-style:normal}"
+        ".f3-c{position:fixed;left:0;top:0;container-type:size}"
+        ".f3-p,.f3-b{display:block;height:1px;width:1px}"
+        ".f3-m{display:block;height:1px}"
+    )
+    once.append(
+        f".f3-mlp{{--range-fc:calc(max(.000001,{','.join(f'abs(var({p}))' for p in n2)}) * 1.001)}}"
+    )
+    fc_settings = b.pack_font_settings(n2, 1, 0).replace(" / 1)", " / var(--range-fc))")
+    once.append(f".f3-fc{{font-variation-settings:{fc_settings}}}")
+
+    # --- fc anchors: one row per hidden unit, 3 shard glyphs (fallback fonts sum their advances)
+    fc_rows = "".join(
+        f'<i class="f3-row" style="anchor-name:--f3f{i}">'
+        + "".join(f"&#x{gfc.codepoint_starts[s] + i:X};" for s in range(SHARDS_FC))
+        + "</i>"
+        for i in range(M)
+    )
+    html = [f'<div class="f3-mlp"><div class="f3-stage f3-fc" id="f3fs">{fc_rows}</div>']
+
+    # --- 12 fc chains, each hosting its proj shard column
+    for j in range(SHARDS_PROJ):
+        ids = [f"f3c{j}-{k}" for k in range(FC_CHAIN)] + [f"f3r{j}"]
+        size = [
+            (f"anchor-size(--f3f{b.SHARD * j + 2 * k} width)", f"anchor-size(--f3f{b.SHARD * j + 2 * k + 1} width)")
+            for k in range(FC_CHAIN)
+        ] + [None]
+        local = hid[b.SHARD * j : b.SHARD * (j + 1)]
+        proj_settings = ",".join(
+            f'"{b.packed_axis_tag(j % b.PACK_SHARDS, l)}" calc(var({local[l]}) / var(--range-proj))'
+            for l in range(b.SHARD)
+        )
+        once.append(
+            f"#f3r{j}{{--range-proj:calc(max(.000001,{','.join(f'abs(var({p}))' for p in local)}) * 1.001)}}"
+            f"#f3m{j}{{width:calc(var(--range-proj) * {RANGE_PX}px)}}"
+            f"#f3s{j}{{font-variation-settings:{proj_settings}}}"
+        )
+        prow = "".join(
+            f'<i class="f3-row" style="anchor-name:--f3p{j}_{i}">&#x{gproj.codepoint_starts[j] + i:X};</i>'
+            for i in range(W)
+        )
+        bottom = (
+            f'<i class="f3-m" id="f3m{j}" style="anchor-name:--f3m{j}"></i>'
+            f'<div class="f3-stage" id="f3s{j}">{prow}</div>'
+        )
+        chain_html, chain_css = _chain(ids, size, bottom, CHAIN_LEVEL)
+        once.append(chain_css)
+        html.append(chain_html)
+        # per-layer GELU decode: level k+1 publishes container k's two values
+        for k in range(FC_CHAIN):
+            decls = []
+            for i, unit in ((b.SHARD * j + 2 * k, "cqw"), (b.SHARD * j + 2 * k + 1, "cqh")):
+                raw = f"(100{unit} / 1px * {PX_TO_UNITS} - {int(fc_bases[i])})"
+                decls.append(
+                    f"{hid[i]}:--gelu(calc({raw} * {num(qfc.scales[i])} * var(--range-fc) + ({num(bfc[i])})))"
+                )
+            layer_css.append(f"{_publisher(ids[k + 1], CHAIN_LEVEL)}{{{';'.join(decls)}}}")
+
+    # --- out chain: 6 range containers, then 384 value containers, bottom hosts {child}
+    ids = [f"f3g{t}" for t in range(RANGE_CHAIN)] + [f"f3o{k}" for k in range(OUT_CHAIN)] + ["f3b"]
+    size = [
+        (f"anchor-size(--f3m{2 * t} width)", f"anchor-size(--f3m{2 * t + 1} width)")
+        for t in range(RANGE_CHAIN)
+    ]
+    for k in range(OUT_CHAIN):
+        wsum = " + ".join(f"anchor-size(--f3p{j}_{2 * k} width) * var({ranges[j]})" for j in range(SHARDS_PROJ))
+        hsum = " + ".join(f"anchor-size(--f3p{j}_{2 * k + 1} width) * var({ranges[j]})" for j in range(SHARDS_PROJ))
+        size.append((f"calc({wsum})", f"calc({hsum})"))
+    size.append(None)
+    # the out chain must hold 768 values: only one element per level fits the parser cap
+    chain_html, chain_css = _chain(ids, size, "{child}", 1)
+    once.append(chain_css)
+    html.append(chain_html)
+    html.append("</div>")
+    # range publishers are layer-independent
+    for t in range(RANGE_CHAIN):
+        once.append(
+            f"{_publisher(ids[t + 1], 1)}{{{ranges[2 * t]}:calc(100cqw / 1px / {RANGE_PX});"
+            f"{ranges[2 * t + 1]}:calc(100cqh / 1px / {RANGE_PX})}}"
+        )
+    # per-layer output decode (+ residual r)
+    for k in range(OUT_CHAIN):
+        decls = []
+        for i, unit in ((2 * k, "cqw"), (2 * k + 1, "cqh")):
+            bases = " + ".join(f"{int(proj_bases[j][i])} * var({ranges[j]})" for j in range(SHARDS_PROJ))
+            raw = f"(100{unit} / 1px * {PX_TO_UNITS} - ({bases}))"
+            decls.append(f"{outn[i]}:calc(var({r[i]}) + {raw} * {num(qproj.scales[i])} + ({num(bproj[i])}))")
+        layer_css.append(f"{_publisher(ids[RANGE_CHAIN + k + 1], 1)}{{{';'.join(decls)}}}")
+    return "".join(html), "".join(layer_css), "".join(once)
+
+
+def chain_depth():
+    """Elements added below .f3-mlp on the deepest path (for the 512 parser cap check)."""
+    out = 1 + (RANGE_CHAIN + OUT_CHAIN) + 1  # .f3-mlp + containers + #f3b
+    fc = 1 + FC_CHAIN * CHAIN_LEVEL + CHAIN_LEVEL + 2  # .f3-mlp + containers(+publishers) + #f3r + .f3-stage + row
+    return max(out, fc)
+
+
+def metadata():
+    return {
+        "f3ChainMlp": CHAIN_MLP,
+        "f3ChainLevel": CHAIN_LEVEL,
+        "f3ChainContainers": SHARDS_PROJ * FC_CHAIN + RANGE_CHAIN + OUT_CHAIN,
+        "f3ChainAnchors": M + SHARDS_PROJ * W + SHARDS_PROJ,
+    }
diff -ruN -x __pycache__ tools/f5_scoping.py work/2026-09-19/F3b/tools/f5_scoping.py
--- tools/f5_scoping.py	1969-12-31 16:00:00
+++ work/2026-09-19/F3b/tools/f5_scoping.py	2026-09-18 19:30:42
@@ -0,0 +1,88 @@
+"""F5 (2026-09-19): narrow the inherited write points of the reused runtime.
+
+Every change is behind an environment flag (default ON) so it can be reverted
+independently when building:
+
+  F5_SCOPED_HANDSHAKE=0  keep --loop-ready/--loop-ack/--native-pass/--position inherited
+  F5_SCOPED_EPOCH=0      keep the token --epoch inherited from body
+  F5_SCOPED_FEEDBACK=0   keep --feedback-*/--feedback-p-*/--frozen-prompt/--token inherited
+  F5_INLINE_FORWARD=0    keep the 1,538 `.loop-metric:nth-child(N){--saved:inherit}` rules
+  F5_BANK_FILLED_ALIASES=0  alias all 48*capacity KV fields instead of only filled slots
+  F5_BANK_LITERAL_LISTS=0   keep `transition-property:var(--fvs-*)` instead of literal lists
+
+Mechanism (audit/2026-09-18/SYNTHESIS.md §8.1-8.2): a registered custom property
+written with inherits:true restyles every non-locked descendant of the element
+it is written on; inherits:false restyles one element. Readers get an explicit
+republish (`inherit`, or a container-query stamp of the same value).
+"""
+
+import os
+import re
+
+
+def flag(name):
+    return os.environ.get(name, "1") not in ("0", "false", "no", "off")
+
+
+SCOPED_HANDSHAKE = flag("F5_SCOPED_HANDSHAKE")
+SCOPED_EPOCH = flag("F5_SCOPED_EPOCH")
+SCOPED_FEEDBACK = flag("F5_SCOPED_FEEDBACK")
+INLINE_FORWARD = flag("F5_INLINE_FORWARD")
+BANK_FILLED_ALIASES = flag("F5_BANK_FILLED_ALIASES")
+BANK_LITERAL_LISTS = flag("F5_BANK_LITERAL_LISTS")
+
+_PROPERTY = re.compile(r"@property (--[\w-]+)\{[^{}]+\}")
+
+
+def make_private(css, names):
+    """Re-register the given custom properties with inherits:false."""
+    names = set(names)
+
+    def swap(match):
+        if match[1] in names:
+            return match[0].replace("inherits:true", "inherits:false")
+        return match[0]
+
+    return _PROPERTY.sub(swap, css)
+
+
+def make_private_prefix(css, prefixes):
+    prefixes = tuple(prefixes)
+
+    def swap(match):
+        if match[1].startswith(prefixes):
+            return match[0].replace("inherits:true", "inherits:false")
+        return match[0]
+
+    return _PROPERTY.sub(swap, css)
+
+
+_TAG = re.compile(r"<(i|span|div|output)\b([^>]*?)>")
+
+
+def tag_inline_readers(html, needle, cls, skip_class=None):
+    """Add `cls` to every element whose inline style contains `needle`.
+
+    Elements that already carry `skip_class` are left alone (they were tagged
+    by an inner compiler stage with a different republish source).
+    """
+    count = 0
+
+    def visit(match):
+        nonlocal count
+        attrs = match[2]
+        style = re.search(r'style="([^"]*)"', attrs)
+        if not style or needle not in style[1]:
+            return match[0]
+        existing = re.search(r'class="([^"]*)"', attrs)
+        if existing:
+            classes = existing[1].split()
+            if cls in classes or (skip_class and skip_class in classes):
+                return match[0]
+            attrs = attrs.replace(existing[0], f'class="{existing[1]} {cls}"', 1)
+        else:
+            attrs = f' class="{cls}"' + attrs
+        count += 1
+        return f"<{match[1]}{attrs}>"
+
+    return _TAG.sub(visit, html), count
```
