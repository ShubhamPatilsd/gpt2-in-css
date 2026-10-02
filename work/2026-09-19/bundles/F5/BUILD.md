# bundles/F5 — Fix 5 (+ Fix 4 latch survey): narrow the inherited write points

Built by F5 on 2026-09-18 from `work/2026-09-19/F5/tools` (copy of `tools/` + the patch below).
Same recipe as `bundles/baseline/BUILD.md` (B0); differs from baseline ONLY by the tools patch.
Fonts are the repo's existing assets, referenced through the `work/2026-09-19/F5/experiments` symlink
(runtime.css URLs `../../F5/experiments/...`); nothing under `experiments/` or `tools/` was written.

## Exact command (`work/2026-09-19/F5/compile-F5.sh`)

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/F5
ln -sfn ../../../experiments experiments; ln -sfn ../../../data data
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/F5
```

All F5 changes are env flags (default ON) in `tools/f5_scoping.py`; to build a variant with one reverted,
prefix e.g. `F5_SCOPED_EPOCH=0` (see the module docstring for the six flags). The manifest records the flags.

## What changed vs baseline (same 72,549 elements; index.html +33.8 KB of class attributes, runtime.css +0.73 MB)

| flag | change | emitter |
|---|---|---|
| `F5_SCOPED_HANDSHAKE` | `--native-pass`, `--loop-ready`, `--loop-ack`, `--position` re-registered `inherits:false`; the 96 `@container loopcontrol style(--pass:N)` rules now stamp `--native-pass:N` on the 14 reader selectors (`.loop-input,.loop-bank-0/1,.reused-input,.fvs-query,.fvs-score-reader,.pass-reader`, 6 receipts) instead of `.core-block`; readers of core `--epoch`/`--position` derive them from `--native-pass`; 9 inline readers (6 stage markers, 3 readback probes) get class `pass-reader` | `browser_gpt2_reused_adapter.py` |
| `F5_SCOPED_EPOCH` | body `--epoch` re-registered `inherits:false`; 8 `@container runtime style(--epoch:N){…{--epoch:N}}` stamps on its 9 readers (`.epoch-reader` ×4 inline, `.embedding-receipt`, `.position-embedding`, `.feedback-select`, `.head-input-bank`, `.b11-bridge-receipt`) | `browser_gpt2_runtime.py` |
| `F5_SCOPED_FEEDBACK` | `--feedback-1..8`, `--feedback-p-1..8`, `--frozen-prompt`, `--token` `inherits:false`; `.feedback-select,.visible-output{…:inherit}`, `.embedding-source{--token:inherit}` | `browser_gpt2_runtime.py` |
| `F5_INLINE_FORWARD` | the 1,538 `.loop-bank-b>.loop-scroll>.loop-track>.loop-metric:nth-child(N){--saved-b-N:inherit}` rules replaced by the same declaration inline on each `loop-metric` | `browser_gpt2_reused_core.py` |
| `F5_BANK_FILLED_ALIASES` | selected KV bank aliases only the 48·(S+1) fields of slots ≤ write slot S (per-(layer,slot) rules) instead of all 384 | `browser_gpt2_font_vector_cache.py` |
| `F5_BANK_LITERAL_LISTS` | bank `transition-property` lists emitted as literals instead of `var(--fvs-all-fields)`/`var(--fvs-retained-S)` | `browser_gpt2_font_vector_cache.py` |

## Offline verification

- `@property` set identical to baseline; 23 registrations flipped true→false (families above), none other.
- Reader coverage script (F5.log.md): every `var()`/`if(style())` reader of a flipped property, in rules and inline
  styles, declares the property on the same element (stamp or `inherit`) — 0 uncovered (2 self-reads on the
  declaring element are expected: `.core-valid`=`.reused-input`, `--feedback-p-*` animated on `.feedback-reader`).
- `font-witnesses.json`: 261 faces, codepoint/advance/upem identical to baseline (only path prefix differs).
- No weights, fonts or arithmetic changed; the NumPy reference (`reference_sequence`, same as B0) is therefore the
  baseline's `[11,314,1101,7926,11,475,314,1101]`.
- `tools/launch_browser_gpt2.py --check --directory bundles/F5`: passes, runtimeJavaScript false.
- Browser correctness run (one, under CHROME.lock, not a timing run): see `work/2026-09-19/F5/verify/F5.json`
  and F5.md.

## Diff of the tools copy vs `tools/` (`diff -ru -x __pycache__ tools work/2026-09-19/F5/tools`)

```diff
diff -ru -x __pycache__ tools/browser_gpt2_font_vector_cache.py work/2026-09-19/F5/tools/browser_gpt2_font_vector_cache.py
--- tools/browser_gpt2_font_vector_cache.py	2026-09-17 00:53:12
+++ work/2026-09-19/F5/tools/browser_gpt2_font_vector_cache.py	2026-09-18 17:33:45
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
diff -ru -x __pycache__ tools/browser_gpt2_reused_adapter.py work/2026-09-19/F5/tools/browser_gpt2_reused_adapter.py
--- tools/browser_gpt2_reused_adapter.py	2026-09-17 00:17:23
+++ work/2026-09-19/F5/tools/browser_gpt2_reused_adapter.py	2026-09-18 17:35:49
@@ -8,6 +8,7 @@
 import re
 
 import build_hybrid_twelve_block as hybrid
+import f5_scoping as f5
 from browser_gpt2_reused_core import compile_reused
 
 
@@ -109,8 +110,48 @@
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
+        if tagged != 7 or tagged_position != 2:
+            raise ValueError(
+                f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
+            )
+    else:
+        for step in range(1, blocks * capacity + 1):
+            css += f"@container loopcontrol style(--pass:{step}){{.core-block{{--native-pass:{step}}}}}"
     # Style-container invalidation itself can cross private-property boundaries.
     # Move per-layer containers off body entirely, outside the head's ancestry.
     css = re.sub(r"\bbody(?=[{:\s])", ".core-controller", css)
@@ -166,6 +207,12 @@
         "nativeLayerTokenHandshake": True,
         "privateLayerControl": True,
         "localLayerContainer": True,
+        "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
+        "f5ScopedEpoch": f5.SCOPED_EPOCH,
+        "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
+        "f5InlineForward": f5.INLINE_FORWARD,
+        "f5BankFilledAliases": f5.BANK_FILLED_ALIASES,
+        "f5BankLiteralLists": f5.BANK_LITERAL_LISTS,
         "kvStorage": "native remembered layout"
         if codec == "geometry"
         else "native delayed whole-head font settings"
diff -ru -x __pycache__ tools/browser_gpt2_reused_core.py work/2026-09-19/F5/tools/browser_gpt2_reused_core.py
--- tools/browser_gpt2_reused_core.py	2026-09-17 00:17:23
+++ work/2026-09-19/F5/tools/browser_gpt2_reused_core.py	2026-09-18 17:33:30
@@ -13,6 +13,7 @@
 
 import build_gpt2_block_css as b
 import build_hybrid_twelve_block as h
+import f5_scoping as f5
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
     TOKENS,
@@ -337,12 +338,25 @@
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
diff -ru -x __pycache__ tools/browser_gpt2_runtime.py work/2026-09-19/F5/tools/browser_gpt2_runtime.py
--- tools/browser_gpt2_runtime.py	2026-09-17 00:31:22
+++ work/2026-09-19/F5/tools/browser_gpt2_runtime.py	2026-09-18 17:34:05
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
Only in work/2026-09-19/F5/tools: f5_scoping.py
```
