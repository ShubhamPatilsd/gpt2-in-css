# bundles/R4S — combined4 + R4S small-hop fold (score hop 97 view-timelines -> anchor/size-container chain inside the qkv pass)

Built by R4S on 2026-09-20 23:39 (`work/2026-09-19/R4S/compile.sh R4S 12 8`, 13 s, 1.6 GB peak; fonts and F2's projection shards reused via the
`experiments` / `data` / `assets -> ../F4/assets` / `global-projection-assets -> ../F2/…` symlinks beside the tools copy — no new font files, 283 faces as combined4).
Recipe = `bundles/combined4/BUILD.md` with the tools copy `work/2026-09-19/R4S/tools` (= `R3M/tools` + `r4s_small_hops.py` + hooks in
`browser_gpt2_font_vector_cache.py` and `browser_gpt2_reused_adapter.py`). Design and results: `work/2026-09-19/R4S.md`.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4S
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R2G_SCOPED_HAS=1 R3R_FOLD_HOP=1 R3H_BLOCKFLOW_MAX=1
export R4S_SMALL_HOPS=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R4S
```

## Flag (environment; `0` reverts; combined4's flags unchanged, see `bundles/combined4/BUILD.md`)

| flag | default | owner | effect |
|---|---|---|---|
| `R4S_SMALL_HOPS` | 1 | R4S | the 96 attention-score glyphs become in-flow anchor rows (`anchor-name:--fsa-H-S`) of a `position:fixed` stage `.fvs-score-stage`; 48 nested `position:fixed; container-type:size` containers `#fvs-sc0..47` take `width/height:anchor-size(--fsa-… width)` from two carriers each and publish their parent's two sizes as `--fs-H-S:calc((100cqw/1px − 262144)/128)` (cqh for the second); the chain bottom `.fvs-score-reader` publishes the last two and keeps the softmax; no score scroller, stamp, receipt, gate or timeline animations. The scores and the V rows resolve inside the qkv readback pass's layout, so the ctx readback becomes that frame's second pass: 6 -> 5 passes = 3.0 -> 2.5 frames/layer (`R4S.md` §2). Manifest `r4sSmallHops`, `r4sScoreChainContainers` (48), `r4sScoreAnchors` (96). |

`R4S_SMALL_HOPS=0` reproduces R3M's tools byte-for-byte (index.html + runtime.css; checked on the 2-layer/capacity-2 build: `R4S/scratch/off-2L` == `R4S/scratch/r3m-2L`
built from `R3M/tools` with the same command; manifests differ only by the `r4sSmallHops` key).

## Offline verification (`work/2026-09-19/R4S/offline_check.py R4S combined4 8`, log `R4S/logs/offline_check-R4S.log`)

- Rule diff vs `bundles/combined4` (same URL depth, both under `bundles/`) falls entirely into the intended categories: +96 `@property --fs-*` `inherits:true` / −96 `inherits:false`;
  −98 progress/stamp/ready registrations (`--fsp-*`, `--fss`, `--fvs-score-ready`); −97 (×2 copies) `@keyframes fvs-score-*`; −score scroller / reader animations / receipt / gate rules;
  +4 chain structure rules; +48 `#fvs-scK{width:anchor-size(--fsa-h-s width);height:anchor-size(--fsa-h'-s' width)}` (exact (h,s) mapping checked: container k = carriers 2k, 2k+1);
  +47 container publishers + the `.fvs-score-reader` bottom publisher (`--fs-h-s:calc((100cqw / 1px - 262144) / 128)` / cqh; container k+1 publishes container k, exact mapping checked);
  `html{timeline-scope}` loses exactly the 96 `--fvs-score-H-S` + `--fvs-score-stamp` names; F5's pass-reader / epoch-receipt lists lose `.fvs-score-receipt`; the `.head-isolation` reset list
  loses only `--fsp-*`/`--fss`/`--fvs-score-ready`. All 96 `.fvs-score-H-S` glyph rules (font + `calc-size(max-content,calc(262144px + …))` width) and the softmax rule are byte-identical to combined4's.
- index.html: 96 `anchor-name:--fsa-*`, 48 `.fvs-sc` containers, one stage, stage and all anchors precede `#fvs-sc0` in tree order, `.fvs-score-reader` directly inside `#fvs-sc47`,
  `.fvs-softmax` inside the reader; `view-timeline` count −97; elements 67,445 vs 67,401 (+44 = stage + 48 containers − scroller/track/stamp/receipt/gate); max nesting depth 94 (combined4: 51; cap 512).
- Containing-block lint: none of the 40 ancestors of `#fvs-sc0` carries `contain`, `transform`, `filter`, `will-change`, `perspective` or `position:absolute/relative/sticky` in any rule or inline style
  (the gates carry only `content-visibility`, which is `visible` whenever the chain is live).
- `font-witnesses.json`: 283/283 identical to combined4 (keys modulo tools dir). NumPy reference ids (`R4S/reference_ids.py`, R4S tools): `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected.
  `launch_browser_gpt2.py --check`: 285 static files / 285,475,147 B / no JavaScript.
- Sizes: runtime.css 38,953,655 chars (combined4 38,973,628), index.html 5,604,468 chars (combined4 5,603,748).

## Chrome correctness run

ONE passive run (NOT a timing run), `R4S/run_correctness.sh R4S` (R3M's watchdog harness with R4S paths: owner-marked lock, toucher killed before a marker-checked release; F4's
`correctness_run.mjs`: headless Chrome 153, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), 2026-09-21 00:02:47–00:05:29 under `CHROME.lock`
(waited 513 s behind R4T's fixture), AC, load { 4.07 5.35 7.27 }. Results in `work/2026-09-19/R4S/run-R4S/{harness.log,verify.log,verification-vectors.json,pipeline-results.json}`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: tokenAgreement 8 × True, originalFloatAgreement 8 × True,
  finalHeadMatchesActualInput True, text "Hello, I'm sorry, but I'm"; `finalResidualError` rmse **0.017219** / max **0.16788** (combined4: 0.017645 / 0.13388) — different, as §2.4 predicts
  (the scores now round at the LayoutUnit instead of the timeline's float progress), same 1e-2 error class, ids identical.
- Whole-run counters (Performance.getMetrics at the end, same harness): **LayoutCount 535** (combined4 629: −94 ≈ 8 tokens × 12 removed score-readback layouts), RecalcStyleCount 3,759
  (combined4 985) — with a size-container chain the counter also counts the interleaved container recalcs (≈ 29 per layer evaluation here; F3b §2b), so it is no longer a pass count;
  the traced smoke (§5) is the exact pass accounting. Nodes 132,214 (combined4 132,170).
- Per-token capture times (5 s poll granularity, indicative only): 23.4, 11.9, 17.1, 18.7, 17.6, 18.6, 19.8, 19.2 s (sum 146.3 s; combined4's correctness run on a similar load class:
  22.0, 17.1, 17.2, 18.0, 24.2, 17.8, 24.7, 17.6 = 158.6 s). B5's paired protocol decides the s/token.
- `bundles/R4S/READY` created 2026-09-21 00:06.


## `diff -ruN -x __pycache__ work/2026-09-19/R3M/tools work/2026-09-19/R4S/tools`

(319 lines; also at `R4S/tools-vs-R3M.diff`)

```diff
diff -ruN -x __pycache__ ../R3M/tools/browser_gpt2_font_vector_cache.py tools/browser_gpt2_font_vector_cache.py
--- ../R3M/tools/browser_gpt2_font_vector_cache.py	2026-09-20 22:01:52
+++ tools/browser_gpt2_font_vector_cache.py	2026-09-20 23:36:34
@@ -14,6 +14,7 @@
 import f4_packing as f4
 import f5_scoping as f5
 import r2c_hoist as r2c
+import r4s_small_hops as r4s
 import numpy as np
 from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
 from build_gpt2_block_css import UNITS_PER_EM
@@ -169,6 +170,8 @@
         raise ValueError("Unknown value layout")
     if prewarm_values and value_layout != "widths":
         raise ValueError("Early value preparation requires fixed font widths")
+    if prewarm_values and r4s.SMALL_HOPS:
+        raise ValueError("R4S: the score chain has no score gate to prewarm against")
     operators = fonts()
     packed = f4.PACKED_BANKS
     if packed and value_layout != "runs":
@@ -320,51 +323,71 @@
     unit = QK_SIZE / UNITS_PER_EM
     score_fields = [f"--fs-{h}-{s}" for h in range(HEADS) for s in range(capacity)]
     progress_fields = [f"--fsp-{h}-{s}" for h in range(HEADS) for s in range(capacity)]
-    css += hybrid.regs(
-        score_fields + progress_fields + ["--fss", "--fvs-score-ready"]
-    ).replace("inherits:true", "inherits:false")
+    if r4s.SMALL_HOPS:
+        # R4S: the scores are published by the chain containers and inherit down to
+        # the chain bottom (the softmax element); no progress/stamp/ready scratch.
+        css += hybrid.regs(score_fields)
+    else:
+        css += hybrid.regs(
+            score_fields + progress_fields + ["--fss", "--fvs-score-ready"]
+        ).replace("inherits:true", "inherits:false")
     metrics, timelines, animations, reads = [], [], [], []
     for head in range(HEADS):
         for slot in range(capacity):
             name, timeline = f"fvs-score-{head}-{slot}", f"--fvs-score-{head}-{slot}"
             progress = f"--fsp-{head}-{slot}"
-            timelines.append(timeline)
-            animations.append(name)
-            css += f"@keyframes {name}{{from{{{progress}:-2}}to{{{progress}:1}}}}"
+            if not r4s.SMALL_HOPS:
+                timelines.append(timeline)
+                animations.append(name)
+                css += f"@keyframes {name}{{from{{{progress}:-2}}to{{{progress}:1}}}}"
             dot_family = f"FvsDot{head}" if packed else "FvsDot"
             fr_k = f"--fr-k-{slot}" if packed else f"--fr-k-{slot}-{head}"
             css += (
                 f".{name}{{font:{QK_SIZE}px {dot_family};line-height:1;font-kerning:none;font-variation-settings:var({fr_k}),var(--fvs-query-{head});"
                 f"width:calc-size(max-content,calc(262144px + (size - {dot['base'] * unit:.12g}px) * var(--fqs-{head}) * var(--fr-ks-{slot}-{head}) * {128 / (8 * dot['coefficient'] * unit):.12g}))}}"
             )
+            if r4s.SMALL_HOPS:
+                # R4S: in-flow anchor row of the fixed score stage; same class = same
+                # font / width expression, read by the container chain below.
+                metrics.append(r4s.carrier(head, slot, name, f"&#x{CODEPOINT_BASE:X};"))
+                continue
             metrics.append(
                 f'<i class="metric {name}" style="view-timeline:{timeline} inline">&#x{CODEPOINT_BASE:X};</i>'
             )
             reads.append(
                 f"--fs-{head}-{slot}:calc((1572864 / (var({progress}) + 2) - 786432) / 128)"
             )
-    metrics.append(
-        '<i class="metric" style="width:calc(262144px + var(--epoch)*1024px);view-timeline:--fvs-score-stamp inline"></i>'
-    )
-    score_source = (
-        '<div class="scroller fvs-score-source"><div class="track">'
-        + "".join(metrics)
-        + "</div></div>"
-    )
-    css += ".fvs-score-source{width:524288px}.fvs-score-source>.track{width:1572864px}"
-    css += (
-        ".fvs-score-reader{animation-name:"
-        + ",".join(animations)
-        + ";animation-duration:1s;animation-fill-mode:both;animation-timing-function:linear;animation-timeline:"
-        + ",".join(timelines)
-        + ";"
-        + ";".join(reads)
-        + "}"
-        "@keyframes fvs-score-stamp{from{--fss:0}to{--fss:1}}"
-        ".fvs-score-receipt{container-name:fvsscore;animation:fvs-score-stamp 1s linear both;animation-timeline:--fvs-score-stamp;"
-        "--fvs-score-ready:calc(1 - min(1,abs(round(nearest,(524288 / var(--fss) - 786432) / 1024,1) - var(--epoch))))}"
-        ".fvs-score-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container fvsscore style(--fvs-score-ready:1){.fvs-score-gate{content-visibility:visible}}"
-    )
+    if r4s.SMALL_HOPS:
+        # R4S: fixed stage of 12*capacity anchors, then the chain; no stamp, receipt or gate
+        # (the scores resolve in the same layout as the glyphs they come from).
+        score_source = r4s.stage(metrics)
+        chain_open, chain_close, chain_css = r4s.chain(
+            [(head, slot) for head in range(HEADS) for slot in range(capacity)]
+        )
+        css += chain_css
+    else:
+        metrics.append(
+            '<i class="metric" style="width:calc(262144px + var(--epoch)*1024px);view-timeline:--fvs-score-stamp inline"></i>'
+        )
+        score_source = (
+            '<div class="scroller fvs-score-source"><div class="track">'
+            + "".join(metrics)
+            + "</div></div>"
+        )
+        css += ".fvs-score-source{width:524288px}.fvs-score-source>.track{width:1572864px}"
+        css += (
+            ".fvs-score-reader{animation-name:"
+            + ",".join(animations)
+            + ";animation-duration:1s;animation-fill-mode:both;animation-timing-function:linear;animation-timeline:"
+            + ",".join(timelines)
+            + ";"
+            + ";".join(reads)
+            + "}"
+            "@keyframes fvs-score-stamp{from{--fss:0}to{--fss:1}}"
+            ".fvs-score-receipt{container-name:fvsscore;animation:fvs-score-stamp 1s linear both;animation-timeline:--fvs-score-stamp;"
+            "--fvs-score-ready:calc(1 - min(1,abs(round(nearest,(524288 / var(--fss) - 786432) / 1024,1) - var(--epoch))))}"
+            ".fvs-score-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container fvsscore style(--fvs-score-ready:1){.fvs-score-gate{content-visibility:visible}}"
+        )
     soft = []
     soft_fields = []
     for head in range(HEADS):
@@ -506,12 +529,22 @@
         if slim_glyphs
         else ".fvs-value-row{display:inline-flex;gap:0;font:0px monospace;line-height:1}"
     )
-    body = (
-        score_source
-        + '<div class="fvs-score-reader"><div class="fvs-score-receipt"><div class="fvs-score-gate"><div class="fvs-softmax">'
-        + value_source
-        + "</div></div></div></div>"
-    )
+    if r4s.SMALL_HOPS:
+        body = (
+            score_source
+            + chain_open
+            + '<div class="fvs-score-reader"><div class="fvs-softmax">'
+            + value_source
+            + "</div></div>"
+            + chain_close
+        )
+    else:
+        body = (
+            score_source
+            + '<div class="fvs-score-reader"><div class="fvs-score-receipt"><div class="fvs-score-gate"><div class="fvs-softmax">'
+            + value_source
+            + "</div></div></div></div>"
+        )
     for layer in reversed(range(blocks)):
         body = (
             f'<div class="fvs-bank fvs-bank-{layer}" data-layer="{layer}">'
@@ -519,7 +552,8 @@
             + "</div>"
         )
     body = '<div class="fvs-query">' + body + "</div>"
-    css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
+    if not r4s.SMALL_HOPS:  # R4S: no score timelines
+        css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
     return (
         body,
         css,
@@ -534,6 +568,7 @@
             "f4NumericLists": f4.NUMERIC_LISTS,
             "latchedFieldsPerSlot": len(all_fields) // capacity,
             "prewarmValues": prewarm_values,
+            **r4s.manifest(capacity),
             "attentionMask": "full causal"
             if capacity == positions
             else "initial sinks plus rolling recent context",
diff -ruN -x __pycache__ ../R3M/tools/browser_gpt2_reused_adapter.py tools/browser_gpt2_reused_adapter.py
--- ../R3M/tools/browser_gpt2_reused_adapter.py	2026-09-20 22:01:52
+++ tools/browser_gpt2_reused_adapter.py	2026-09-20 23:36:34
@@ -14,6 +14,7 @@
 from browser_gpt2_reused_core import compile_reused
 import r2f_lean_handshake as r2f
 import r3r_fold_hop as r3r
+import r4s_small_hops as r4s
 
 
 def compile_reused_runtime_core(
@@ -138,7 +139,7 @@
         # and stamp the current pass directly onto every reader.
         receipts = [
             f".shared-{kind}-receipt" for kind in ("qkv", "attn", "fc", "proj")
-        ] + [".cache-bridge-receipt", ".fvs-score-receipt"]
+        ] + [".cache-bridge-receipt"] + ([] if r4s.SMALL_HOPS else [".fvs-score-receipt"])
         pass_readers = ",".join(
             [
                 ".loop-input",
@@ -167,7 +168,8 @@
         body, tagged_position = f5.tag_inline_readers(
             body, "var(--position)", "pass-reader"
         )
-        if tagged != 7 or tagged_position != 2:
+        # R4S: the score stamp marker (one inline var(--epoch) reader) no longer exists
+        if tagged != (6 if r4s.SMALL_HOPS else 7) or tagged_position != 2:
             raise ValueError(
                 f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
             )
@@ -234,6 +236,7 @@
         "localLayerContainer": True,
         "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
         "r3rFoldHop": r3r.FOLD_HOP,
+        "r4sSmallHops": r4s.SMALL_HOPS and codec == "font-vector",
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
diff -ruN -x __pycache__ ../R3M/tools/r4s_small_hops.py tools/r4s_small_hops.py
--- ../R3M/tools/r4s_small_hops.py	1969-12-31 16:00:00
+++ tools/r4s_small_hops.py	2026-09-20 23:35:32
@@ -0,0 +1,110 @@
+"""R4S (2026-09-20): the attention-score hop (96 values + stamp) leaves view-timelines.
+
+Flag (default ON): R4S_SMALL_HOPS=0 restores combined4's score transport (97 view-timeline
+carriers in a scroller, `.fvs-score-reader` with 96 animations, `.fvs-score-receipt` +
+`.fvs-score-gate`).
+
+Mechanism (work/2026-09-19/R4S.md): a view-timeline hop costs one style pass and half a
+frame (two passes per frame, R3F §0). The score hop is the only per-layer hop with <= 500
+values (R4S.md §1), so it fits ONE anchor -> size-container chain (F3.md §2, F3b: <= 250
+containers, position:fixed only, anchors earlier in tree order). The 96 score glyphs become
+in-flow block rows (`anchor-name:--fsa-H-S`) of a fixed stage; 12*capacity/2 nested
+`position:fixed; container-type:size` containers take `width/height:anchor-size(...)`
+from two carriers each, and each container publishes its PARENT's two sizes as the
+registered numbers `--fs-H-S:calc((100cqw / 1px - 262144) / 128)` (cq units resolve
+against the nearest ancestor container; the chain bottom `.fvs-score-reader` publishes the
+last two and computes the softmax exactly as before). Everything resolves inside the qkv
+readback pass's layout (interleaved container recalcs), the V rows are laid out in that
+same layout, and the ctx readback becomes the frame's second pass:
+
+    before  [proj+S1 | qkv] [scores | ctx] [attn | fc]              = 6 passes = 3.0 frames/layer
+    after   [proj+S1 | qkv+scores] [ctx | attn] [fc | proj+S1'] ... = 5 passes = 2.5 frames/layer
+
+The carrier width expression (262144px + 128 * score, calc-size on the glyph advance) is
+byte-identical to combined4's, so the laid-out widths are the same LayoutUnits; only the
+width -> number transport changes: exact LayoutUnit (1/64 px -> 1.2e-4 in score units)
+instead of the timeline's float progress. No gate is needed: the scores are never stale
+relative to the glyphs they are read from (same layout), and the qkv gate above still
+closes the whole attention subtree in S1 (R3R §1.1 cascade).
+"""
+
+import os
+
+
+def flag(name):
+    return os.environ.get(name, "1") not in ("0", "false", "no", "off")
+
+
+SMALL_HOPS = flag("R4S_SMALL_HOPS")
+
+# the score carrier encoding (browser_gpt2_font_vector_cache.attention), unchanged
+OFFSET = 262144
+SCALE = 128
+
+STAGE_CLASS = "fvs-score-stage"
+ROW_CLASS = "fvs-score-a"
+CHAIN_CLASS = "fvs-sc"
+BOTTOM_CLASS = "fvs-score-reader"
+
+
+def anchor(head, slot):
+    return f"--fsa-{head}-{slot}"
+
+
+def field(head, slot):
+    return f"--fs-{head}-{slot}"
+
+
+def decode(unit):
+    return f"calc((100{unit} / 1px - {OFFSET}) / {SCALE})"
+
+
+def carrier(head, slot, cls, glyph):
+    """In-flow anchor row for one (head, slot) score glyph; `cls` keeps the font/width rule."""
+    return f'<i class="{ROW_CLASS} {cls}" style="anchor-name:{anchor(head, slot)}">{glyph}</i>'
+
+
+def stage(carriers):
+    return f'<div class="{STAGE_CLASS}">{"".join(carriers)}</div>'
+
+
+def chain(pairs):
+    """Nested fixed size containers over the ordered (head, slot) pairs.
+
+    Returns (open_html, close_html, css). Container k sizes itself from carriers 2k
+    (width) and 2k+1 (height); container k+1 publishes container k's two values; the
+    bottom element (class BOTTOM_CLASS, emitted by the caller inside open/close)
+    publishes the last two.
+    """
+    if len(pairs) % 2:
+        raise ValueError("R4S: the score chain needs an even number of carriers")
+    levels = len(pairs) // 2
+    if levels > 250:
+        raise ValueError("R4S: more than 250 containers in one chain (F3.md §2 cap)")
+    css = [
+        f".{STAGE_CLASS}{{position:fixed;left:0;top:-60000px;width:1px;height:1px;overflow:clip;visibility:hidden}}",
+        f".{ROW_CLASS}{{display:block;height:1px;overflow:clip;min-width:0;white-space:pre;font-style:normal}}",
+        f".{CHAIN_CLASS}{{position:fixed;left:0;top:-300000px;container-type:size}}",
+        f".{BOTTOM_CLASS}{{display:block;width:1px;height:1px}}",
+    ]
+    html = []
+    for k in range(levels):
+        (h0, s0), (h1, s1) = pairs[2 * k], pairs[2 * k + 1]
+        css.append(
+            f"#{CHAIN_CLASS}{k}{{width:anchor-size({anchor(h0, s0)} width);height:anchor-size({anchor(h1, s1)} width)}}"
+        )
+        if k:
+            (p0, q0), (p1, q1) = pairs[2 * k - 2], pairs[2 * k - 1]
+            css.append(f"#{CHAIN_CLASS}{k}{{{field(p0, q0)}:{decode('cqw')};{field(p1, q1)}:{decode('cqh')}}}")
+        html.append(f'<div class="{CHAIN_CLASS}" id="{CHAIN_CLASS}{k}">')
+    (p0, q0), (p1, q1) = pairs[-2], pairs[-1]
+    css.append(f".{BOTTOM_CLASS}{{{field(p0, q0)}:{decode('cqw')};{field(p1, q1)}:{decode('cqh')}}}")
+    return "".join(html), "</div>" * levels, "".join(css)
+
+
+def manifest(capacity):
+    return {
+        "r4sSmallHops": SMALL_HOPS,
+        "r4sScoreChainContainers": 12 * capacity // 2 if SMALL_HOPS else 0,
+        "r4sScoreAnchors": 12 * capacity if SMALL_HOPS else 0,
+    }
```
