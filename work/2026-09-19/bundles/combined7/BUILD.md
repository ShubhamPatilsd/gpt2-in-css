# bundles/combined7 — combined6 (combined4 + R4S + R4D) + R4T consumer re-chunk (`R4T_CONSUMER_CHUNK=64`), capacity 8, default `runs` layout

Built by R4M on 2026-09-21 01:44 (`R4T_CONSUMER_CHUNK=64 work/2026-09-19/R4M/compile.sh tools7 bundles/combined7 8`; tools copy `work/2026-09-19/R4M/tools7`; same
symlinks / fonts as combined6, 283 faces). Coordinator 01:4x: `bundles/R4T/READY` landed 01:38 (8/8, verify rc 0) after R4T's `--lp-*` inherit-forwarding fix.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4M
# combined6's exports (bundles/combined6/BUILD.md) plus:
export R4T_CONSUMER_CHUNK=64
# i.e. R4T_CONSUMER_CHUNK=64 ./compile.sh tools7 bundles/combined7 8
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools7/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined7
```

## Flags

`bundles/combined6/BUILD.md`'s table (R4S_SMALL_HOPS, R4D_*) plus:

| flag | default (here) | owner | effect |
|---|---|---|---|
| `R4T_CONSUMER_CHUNK` | 64 (`0` = off = combined6) | R4T | animations per view-timeline consumer element: matvec/bridge consumers `h.matvec`/`h.bridge` chunk 512 → 64 (`.shared-qkv/attn/fc-cN`, `.cache-bridge-cN`, `.bN-bridge-cN`), `.loop-reader` 768 → 12 nested `.loop-reader-cK` (each forwards the earlier chunks' `--lp-*:inherit` — the READY-time fix, `R4T.md`), `.embedding-consumer-N` 256 → 64; R2G's `LOOP_CHAIN` gains the `.loop-reader-cK` steps. Same animations, timelines and decode declarations (R4T's checker), fewer animations per element (measured 40 → ≈20 µs per changed carrier). Manifest `r4tConsumerChunk`. |

## Merge (`R4M/merge.sh <tools7> R4T/tools-vs-R3M.diff 2`; `R4M/tools7` = `R4M/tools` (combined6) + R4T)

R4S and R4D as in combined6 (same two conflict fixes). R4T's READY-time diff (172 lines, `diff -ru` without `-N` → `r4t_consumer_chunk.py` copied from `R4T/tools`; cmp-identical
to a fresh `diff -ru R3M/tools R4T/tools`): browser_gpt2_embedding.py, browser_gpt2_reused_adapter.py (import + b11-bridge chunk + manifest), browser_gpt2_reused_core.py,
r2g_has_scope.py, r3r_fold_hop.py. **One reject: the adapter import line (adjacent to R4S's/R4D's) → `R4M/apply_r4t_import.py`.** Everything else applied with 0 fuzz.
`diff -rq R4M/tools R4M/tools7` = exactly R4T's five files + module. `R4M/tools7-vs-R3M.diff` (772 lines) is embedded below.

## Offline verification

- **`R4T_CONSUMER_CHUNK=0` (`R4M/scratch/p7-8-noR4T`) reproduces `bundles/combined6` byte-for-byte** (index.html; runtime.css URL-normalised; manifest +`r4tConsumerChunk:0`).
- `R4T/offline_check_r4t.py bundles/combined7 bundles/combined6` → see `R4M/offline_check_r4t-combined7.log` (result quoted in `R4M.md` §6).
- Witnesses 283/283 identical to combined6; `launch_browser_gpt2.py --check`: 285 static files, `runtimeJavaScript: false`.
- Sizes: runtime.css 39979812 B, index.html 6517186 B.

## Chrome correctness run

ONE passive run (NOT a timing run), `R4M/run_correctness.sh combined7` (R3M's watchdog harness with R4M paths: owner marker, toucher killed before a marker-checked release; F4's
`correctness_run.mjs`: headless Chrome, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), under `CHROME.lock`.
Power: Now drawing from 'AC Power'  -InternalBattery-0 (id=22872163) 81%; AC attached; not charging present: true; load { 5.55 5.01 5.56 }. Results in `work/2026-09-19/R4M/run-combined7/`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.01605519804514142, 'maximum': 0.11651862085027176}, 'text': "Hello, I'm sorry, but I'm".
- Whole-run counters (harness idle -> end): RecalcStyleCount 3768, LayoutCount 544 (combined4: 985 / 629; R4S alone: 3,759 / 535 — with R4S the RecalcStyleCount includes interleaved container recalcs, R4S.md §6); Nodes 132338.
- Per-token capture times (5 s poll granularity — indicative only, not a timing run; combined4's run: 22.0, 17.1, 17.2, 18.0, 24.2, 17.8, 24.7, 17.6 = 158.6 s; R4S's: 23.4, 11.9, 17.1, 18.7, 17.6, 18.6, 19.8, 19.2 = 146.3 s): 22.6, 33.6, 51.8, 68.7, 88.0, 108.4, 128.7, 146.8 s.
- Full KV cache readback (the R4M-patched `correctness_run.mjs` concatenates R4D's per-head V lists): 96/96 cache entries complete (K and V), `cacheErrors` rmse max 1.4815 / abs max 7.633 —
  the same class as combined4's run (V half 1.470 / 7.625) and R4S's (1.472 / 7.637); no wrapper needed this time. Per-token deltas from the capture times: 22.6, 11.0, 18.2, 16.9, 19.3, 20.4, 20.3, 18.1 s = 146.8 s
  (combined6's run 137.4 s — single runs at 5 s poll granularity, load 5.5; B5's pairs decide).
- READY: created.

## `diff -ruN -x __pycache__ work/2026-09-19/R3M/tools work/2026-09-19/R4M/tools7`

(772 lines = combined6's 574-line diff + R4T's diff + the import fix; also at `R4M/tools7-vs-R3M.diff`)

```diff
diff -ruN -x __pycache__ R3M/tools/browser_gpt2_embedding.py R4M/tools7/browser_gpt2_embedding.py
--- R3M/tools/browser_gpt2_embedding.py	2026-09-20 22:01:52
+++ R4M/tools7/browser_gpt2_embedding.py	2026-09-21 01:39:46
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
diff -ruN -x __pycache__ R3M/tools/browser_gpt2_font_vector_cache.py R4M/tools7/browser_gpt2_font_vector_cache.py
--- R3M/tools/browser_gpt2_font_vector_cache.py	2026-09-20 22:01:52
+++ R4M/tools7/browser_gpt2_font_vector_cache.py	2026-09-21 01:39:46
@@ -13,7 +13,9 @@
 import build_hybrid_twelve_block as hybrid
 import f4_packing as f4
 import f5_scoping as f5
+import r4d_flags as r4d
 import r2c_hoist as r2c
+import r4s_small_hops as r4s
 import numpy as np
 from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
 from build_gpt2_block_css import UNITS_PER_EM
@@ -88,7 +90,13 @@
         # the 24 per-head scales: 26 latched fields per slot instead of 48.
         names = []
         for slot in range(capacity):
-            names += [f"--fc-k-{slot}", f"--fc-v-{slot}"]
+            names += [f"--fc-k-{slot}"]
+            if r4d.UNPACK_V:
+                # R4D: 12 per-head 64-axis V lists (each V glyph parses 65 axes
+                # instead of 769); the K list stays packed (12 score glyphs/slot).
+                names += [f"--fc-v-{slot}-{head}" for head in range(HEADS)]
+            else:
+                names += [f"--fc-v-{slot}"]
             names += [
                 f"--fc-{kind}-{slot}-{head}"
                 for head in range(HEADS)
@@ -169,10 +177,14 @@
         raise ValueError("Unknown value layout")
     if prewarm_values and value_layout != "widths":
         raise ValueError("Early value preparation requires fixed font widths")
+    if prewarm_values and r4s.SMALL_HOPS:
+        raise ValueError("R4S: the score chain has no score gate to prewarm against")
     operators = fonts()
     packed = f4.PACKED_BANKS
-    if packed and value_layout != "runs":
-        raise ValueError("F4 packed banks are implemented for the runs value layout only")
+    if packed and value_layout not in ("runs", "widths"):
+        # R4D: the widths layout (fixed V font location, weight applied to the
+        # shaped width) uses the same per-slot lists and leaf structure as runs.
+        raise ValueError("F4 packed banks are implemented for the runs/widths value layouts only")
     zero = ",".join(f'"K{i:03d}" 0' for i in range(DIM))
     all_fields = storage_names(capacity)
     css = ""
@@ -181,6 +193,15 @@
             kind = f4.kind_of(name)
             vector = kind in ("k", "v")
             initial = (f4.zero_list(kind) if packed else zero) if vector else "0"
+            if vector and packed and r4d.head_of(name) is not None:
+                initial = ",".join(
+                    f'"{f4.head_axis(kind, r4d.head_of(name), i)}" 0' for i in range(DIM)
+                )
+            if vector and r4d.EMPTY_UNFILLED:
+                # R4D: one explicit zero axis (fvar defaults are 0) instead of
+                # every axis at zero: unfilled slots substitute 12 B, not ~7.7 KB.
+                head = r4d.head_of(name)
+                initial = f'"{f4.head_axis(kind, 0 if head is None else head, 0) if packed else "K000"}" 0'
             css += f'@property {name.replace("--fc-", f"--{alias}-")}{{syntax:"{"*" if vector else "<number>"}";inherits:{inherits};initial-value:{initial}}}'
     css += hybrid.regs([f"--fqs-{h}" for h in range(HEADS)] + ["--fvs-write-slot"])
     css += (
@@ -195,6 +216,23 @@
         + (",".join(all_fields) if literal else "var(--fvs-all-fields)")
         + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
     )
+    sequential = kv_window is None or (kv_sinks == 0 and capacity == positions)
+    lean = r4d.LEAN_LATCH and sequential
+    if lean:
+        # R4D: with a full causal window slots fill in order; at write-slot W only
+        # slots 0..W can hold a value (W in the banks of layers already written
+        # this token), so only their fields need a retaining transition-property
+        # entry. Slots > W have no running transition, so unlisting them cancels
+        # nothing. The full-list base rule above stays for the no-match state.
+        for write_slot in range(capacity):
+            listed = ",".join(n for n in all_fields if f4.slot_of(n) <= write_slot)
+            if not literal:
+                css += f".fvs-query{{--fvs-base-{write_slot}:{listed}}}"
+            css += (
+                f"@container fvscache style(--fvs-write-slot:{write_slot}){{.fvs-bank{{transition-property:"
+                + (listed if literal else f"var(--fvs-base-{write_slot})")
+                + "}}"
+            )
     for head in range(HEADS):
         maximum = ",".join(f"abs(var(--qkv-{head * DIM + i:03d}))" for i in range(DIM))
         css += f".fvs-query{{--fqs-{head}:max(.000001,{maximum})}}"
@@ -261,12 +299,21 @@
             css += f".fvs-query{{{scale}:max(.000001,{maximum});--fvs-live-{kind}-{head}:{settings}}}"
     for slot in range(capacity):
         fields = {name for name in all_fields if f4.slot_of(name) == slot}
-        retained = ",".join(name for name in all_fields if name not in fields) or "none"
+        retained = ",".join(
+            name for name in all_fields
+            if name not in fields and (not lean or f4.slot_of(name) < slot)
+        ) or "none"
         css += f".fvs-query{{--fvs-retained-{slot}:{retained}}}"
         writes = []
         if packed:
             # F4: the 12 live head lists concatenate into one latched list per kind.
             for kind in ("k", "v"):
+                if kind == "v" and r4d.UNPACK_V:
+                    writes += [
+                        f"--fc-v-{slot}-{head}:var(--fvs-live-v-{head})"
+                        for head in range(HEADS)
+                    ]
+                    continue
                 writes.append(
                     f"--fc-{kind}-{slot}:"
                     + ",".join(f"var(--fvs-live-{kind}-{head})" for head in range(HEADS))
@@ -285,7 +332,6 @@
         retained_value = retained if literal else f"var(--fvs-retained-{slot})"
         for layer in range(blocks):
             css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{transition-property:{retained_value};{';'.join(writes)}}}}}}}"
-    sequential = kv_window is None or (kv_sinks == 0 and capacity == positions)
     if f5.BANK_FILLED_ALIASES and sequential:
         # F5: with a full causal window slots fill in order, so while slot S
         # is being written only slots 0..S hold values; the others equal the
@@ -320,51 +366,71 @@
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
@@ -404,7 +470,16 @@
     css += ".fvs-score-reader{" + ";".join(soft) + "}"
     value = operators["value"]
     value_unit = VALUE_SIZE / UNITS_PER_EM
-    slim_glyphs = value_weight_once and value_layout == "runs"
+    slim_glyphs = value_weight_once and value_layout in ("runs", "widths")
+    hide_unfilled = r4d.HIDE_UNFILLED and sequential and value_layout in ("runs", "widths")
+    if hide_unfilled:
+        # R4D: unfilled slots' V glyphs have no box; the row subtracts one base
+        # advance per PRESENT glyph ((W+1)·base, W = write slot = position-1)
+        # instead of capacity·base, so (size - subtracted) is the same sum of
+        # weighted deltas as before (minus the snapped-advance residue of absent
+        # glyphs, see r4d_flags.py).
+        css += '@property --fvs-nbase{syntax:"<length>";inherits:true;initial-value:0px}'
+        css += f".fvs-query{{--fvs-nbase:calc((var(--fvs-write-slot) + 1) * {value['base'] * value_unit:.12g}px)}}"
     if slim_glyphs:
         # F2: each (head, slot) softmax weight is one registered number on the
         # score reader; every V glyph references it instead of re-evaluating
@@ -446,7 +521,11 @@
                     settings = '"P000" 1'
                     base_pixels = value["base"] * value_unit
                     width_rule = f"width:calc-size(max-content,calc({base_pixels:.12g}px + (size - {base_pixels:.12g}px) * {weight}));min-width:0;"
-                fr_v = f"--fr-v-{slot}" if packed else f"--fr-v-{slot}-{head}"
+                fr_v = (
+                    f"--fr-v-{slot}"
+                    if packed and not r4d.UNPACK_V
+                    else f"--fr-v-{slot}-{head}"
+                )
                 value_family = f"FvsValue{head}" if packed else "FvsValue"
                 if slim_glyphs:
                     # font-family/size/kerning/white-space inherit from the row
@@ -454,11 +533,12 @@
                     # sets font-style. Only the per-(head, slot) list remains
                     # (+ the per-head family when the banks are packed, F4).
                     family_decl = f"font-family:{value_family};" if packed else ""
-                    css += f".fvs-v-{head}-{slot}{{{family_decl}font-variation-settings:var({fr_v}),{settings};flex:none}}"
+                    # R4D: the widths rule (if any) is merged into the same rule.
+                    css += f".fvs-v-{head}-{slot}{{{family_decl}font-variation-settings:var({fr_v}),{settings};{width_rule}flex:none}}"
                 else:
                     css += f".fvs-v-{head}-{slot}{{font-family:{value_family};font-size:{VALUE_SIZE}px;font-variation-settings:var({fr_v}),{settings};font-kerning:none;font-style:normal;display:block;white-space:pre;flex:none}}"
-                if width_rule:
-                    css += f".fvs-v-{head}-{slot}{{{width_rule}}}"
+                    if width_rule:
+                        css += f".fvs-v-{head}-{slot}{{{width_rule}}}"
         if value_layout == "fallback":
             families = ",".join(f"FvsValueSlot{slot}" for slot in range(capacity))
             css += f".fvs-value-head-{head}{{display:contents;font:{VALUE_SIZE}px {families};font-variation-settings:{','.join(combined_settings)};font-kerning:none}}"
@@ -467,7 +547,12 @@
     def row(match):
         coordinate, timeline = int(match[1]), match[2]
         head, local = divmod(coordinate, DIM)
-        dimensions = f"calc-size(max-content,calc(262144px + (size - {capacity * value['base'] * value_unit:.12g}px) * var(--fb-{head}) / var(--fd-{head}) * {128 / (value['coefficient'] * value_unit):.12g}))"
+        subtracted = (
+            "var(--fvs-nbase)"
+            if hide_unfilled
+            else f"{capacity * value['base'] * value_unit:.12g}px"
+        )
+        dimensions = f"calc-size(max-content,calc(262144px + (size - {subtracted}) * var(--fb-{head}) / var(--fd-{head}) * {128 / (value['coefficient'] * value_unit):.12g}))"
         if value_layout == "fallback":
             runs = "".join(
                 f"&#x{CODEPOINT_BASE + slot * DIM + local:X};"
@@ -506,12 +591,22 @@
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
@@ -519,7 +614,33 @@
             + "</div>"
         )
     body = '<div class="fvs-query">' + body + "</div>"
-    css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
+    # R4M merge: R4D_GATE_SCORES is off under R4S (no score scroller; display:none on an
+    # anchor row would invalidate the chain's anchor-size()); --fv-S masking is unchanged.
+    gate_scores = r4d.GATE_SCORES and sequential and not r4s.SMALL_HOPS
+    if hide_unfilled or gate_scores:
+        # R4D: per-slot filled flag on the fvscache container (same expression
+        # as --fv-S on the score reader, which is inherits:false and therefore
+        # invisible to the glyph leaves).
+        css += hybrid.regs([f"--fvq-{slot}" for slot in range(capacity)]).replace(
+            "inherits:true", "inherits:false"
+        )
+        css += ".fvs-query{" + ";".join(
+            f"--fvq-{slot}:clamp(0,sign(var({write_epoch}) - {slot + 1}) + 1,1)"
+            for slot in range(capacity)
+        ) + "}"
+    if hide_unfilled:
+        for slot in range(capacity):
+            selectors = ",".join(f".fvs-v-{head}-{slot}" for head in range(HEADS))
+            css += f"@container fvscache style(--fvq-{slot}:0){{{selectors}{{display:none}}}}"
+    if gate_scores:
+        # R4D (opt-in): unfilled slots' score carriers have no box, so their 12
+        # view-timelines are inactive; --fs/--fe of those slots are masked by
+        # --fv-S anyway (both branches give the same masked values).
+        for slot in range(capacity):
+            selectors = ",".join(f".fvs-score-source .fvs-score-{head}-{slot}" for head in range(HEADS))
+            css += f"@container fvscache style(--fvq-{slot}:0){{{selectors}{{display:none}}}}"
+    if not r4s.SMALL_HOPS:  # R4S: no score timelines
+        css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
     return (
         body,
         css,
@@ -533,7 +654,13 @@
             "f4PackedBanks": packed,
             "f4NumericLists": f4.NUMERIC_LISTS,
             "latchedFieldsPerSlot": len(all_fields) // capacity,
+            "r4dEmptyUnfilled": r4d.EMPTY_UNFILLED,
+            "r4dLeanLatch": lean,
+            "r4dUnpackV": r4d.UNPACK_V,
+            "r4dHideUnfilled": hide_unfilled,
+            "r4dGateScores": gate_scores,
             "prewarmValues": prewarm_values,
+            **r4s.manifest(capacity),
             "attentionMask": "full causal"
             if capacity == positions
             else "initial sinks plus rolling recent context",
diff -ruN -x __pycache__ R3M/tools/browser_gpt2_reused_adapter.py R4M/tools7/browser_gpt2_reused_adapter.py
--- R3M/tools/browser_gpt2_reused_adapter.py	2026-09-20 22:01:52
+++ R4M/tools7/browser_gpt2_reused_adapter.py	2026-09-21 01:39:46
@@ -14,6 +14,9 @@
 from browser_gpt2_reused_core import compile_reused
 import r2f_lean_handshake as r2f
 import r3r_fold_hop as r3r
+import r4s_small_hops as r4s
+import r4d_flags as r4d
+import r4t_consumer_chunk as r4t
 
 
 def compile_reused_runtime_core(
@@ -77,7 +80,7 @@
         )
 
     last = blocks - 1
-    source, receiver, bridge_css, _ = hybrid.bridge(last, 512)
+    source, receiver, bridge_css, _ = hybrid.bridge(last, r4t.chunk(512))  # R4T: b11-bridge consumers
     source = source.replace("var(--epoch)", "var(--position)")
     export = (
         '<div class="reused-final-export">'
@@ -138,7 +141,7 @@
         # and stamp the current pass directly onto every reader.
         receipts = [
             f".shared-{kind}-receipt" for kind in ("qkv", "attn", "fc", "proj")
-        ] + [".cache-bridge-receipt", ".fvs-score-receipt"]
+        ] + [".cache-bridge-receipt"] + ([] if r4s.SMALL_HOPS else [".fvs-score-receipt"])
         pass_readers = ",".join(
             [
                 ".loop-input",
@@ -167,7 +170,8 @@
         body, tagged_position = f5.tag_inline_readers(
             body, "var(--position)", "pass-reader"
         )
-        if tagged != 7 or tagged_position != 2:
+        # R4S: the score stamp marker (one inline var(--epoch) reader) no longer exists
+        if tagged != (6 if r4s.SMALL_HOPS else 7) or tagged_position != 2:
             raise ValueError(
                 f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
             )
@@ -234,6 +238,7 @@
         "localLayerContainer": True,
         "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
         "r3rFoldHop": r3r.FOLD_HOP,
+        "r4sSmallHops": r4s.SMALL_HOPS and codec == "font-vector",
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
@@ -243,10 +248,16 @@
         "f4PackedBanks": f4.PACKED_BANKS and codec == "font-vector",
         "f4PackedHead": f4.PACKED_HEAD,
         "f4NumericLists": f4.NUMERIC_LISTS and codec == "font-vector",
+        "r4dEmptyUnfilled": r4d.EMPTY_UNFILLED and codec == "font-vector",
+        "r4dLeanLatch": r4d.LEAN_LATCH and codec == "font-vector",
+        "r4dUnpackV": r4d.UNPACK_V and codec == "font-vector",
+        "r4dHideUnfilled": r4d.HIDE_UNFILLED and codec == "font-vector",
+        "r4dGateScores": r4d.GATE_SCORES and codec == "font-vector",
         "r2cHoistFvs": r2c.HOIST_FVS,
         "r2cHoistStages": r2c.HOIST_STAGES,
         "r2cHoistQuery": r2c.HOIST_QUERY and codec == "font-vector",
         "r2cHoistEmbedding": r2c.HOIST_EMBEDDING,
+        "r4tConsumerChunk": r4t.CHUNK,
         "kvStorage": "native remembered layout"
         if codec == "geometry"
         else "native delayed whole-head font settings"
diff -ruN -x __pycache__ R3M/tools/browser_gpt2_reused_core.py R4M/tools7/browser_gpt2_reused_core.py
--- R3M/tools/browser_gpt2_reused_core.py	2026-09-20 22:01:52
+++ R4M/tools7/browser_gpt2_reused_core.py	2026-09-21 01:39:46
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
diff -ruN -x __pycache__ R3M/tools/r2g_has_scope.py R4M/tools7/r2g_has_scope.py
--- R3M/tools/r2g_has_scope.py	2026-09-20 22:01:52
+++ R4M/tools7/r2g_has_scope.py	2026-09-21 01:39:46
@@ -23,7 +23,9 @@
 
 SCOPED_HAS = os.environ.get("R2G_SCOPED_HAS", "1") not in ("0", "false", "no", "off")
 
-LOOP_CHAIN = [".core-block", ".loop-reader", ".loop-input", ".loop-signals"]
+import r4t_consumer_chunk as _r4t
+
+LOOP_CHAIN = [".core-block", ".loop-reader", *(f".{c}" for c in _r4t.loop_reader_classes(768)), ".loop-input", ".loop-signals"]
 
 
 class _Paths(html.parser.HTMLParser):
diff -ruN -x __pycache__ R3M/tools/r3r_fold_hop.py R4M/tools7/r3r_fold_hop.py
--- R3M/tools/r3r_fold_hop.py	2026-09-20 22:01:52
+++ R4M/tools7/r3r_fold_hop.py	2026-09-21 01:39:46
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
 
diff -ruN -x __pycache__ R3M/tools/r4d_flags.py R4M/tools7/r4d_flags.py
--- R3M/tools/r4d_flags.py	1969-12-31 16:00:00
+++ R4M/tools7/r4d_flags.py	2026-09-21 01:39:46
@@ -0,0 +1,50 @@
+"""R4D (2026-09-20): flatten the capacity-32 cost of the font-vector KV attention
+without changing the model. Every change is an environment flag:
+
+  R4D_EMPTY_UNFILLED=0  keep the full 768-axis zero list as the registered initial
+                        value of the `*` KV lists (--fc-k/v-*, --fr-k/v-*);
+                        ON: a one-axis `"K000" 0` / `"V000" 0` list. Unfilled slots
+                        are never aliased (F5 filter), so their 768·(cap-p) V glyph
+                        leaves and 12·(cap-p) score glyphs substitute 12 B instead of
+                        ~7.7 KB. Exact: every fvar axis of the operator fonts defaults
+                        to 0, so an omitted axis equals an explicit 0.
+  R4D_LEAN_LATCH=0      keep the 26·capacity-name `transition-property` lists;
+                        ON (full causal window only): at write-slot W the banks list
+                        only the fields of slots 0..W (write rule: 0..W-1). Slots > W
+                        were never written, have no running transition to retain, and
+                        (css-transitions §3) nothing is cancelled by unlisting them.
+  R4D_UNPACK_V=0        keep F4's one 768-axis V list per slot (1 latch);
+                        ON: 12 per-head 64-axis V lists per slot (12 latches, 37 per
+                        slot instead of 26). Each V glyph then substitutes and parses
+                        its own head's 65-axis list instead of 769 axes. Same entries
+                        (var(--fvn-v-H-i)), same tags, same fonts: exact.
+  R4D_HIDE_UNFILLED=0   keep the 768·(cap-p) unfilled V glyph leaves laid out (advance =
+                        base, weight 0); ON (full causal window only): unfilled slots' leaves
+                        are display:none and the row formula subtracts (W+1)·base instead of
+                        capacity·base (--fvs-nbase). Same arithmetic; the only difference is
+                        that the LayoutUnit-snapped base advance of an absent glyph
+                        (12320.78125 vs 12320.768 px) no longer enters `size` — a bias of
+                        ≤ 31/64 px ≈ 4e-5·fb/fd ctx units that the NumPy reference never had.
+  R4D_GATE_SCORES=1     (default OFF) display:none the score carriers of unfilled
+                        slots (their view-timelines go inactive). Masked numerically
+                        by --fv-S already; timing of timeline re-activation untested.
+"""
+
+import os
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+EMPTY_UNFILLED = flag("R4D_EMPTY_UNFILLED")
+LEAN_LATCH = flag("R4D_LEAN_LATCH")
+UNPACK_V = flag("R4D_UNPACK_V")
+HIDE_UNFILLED = flag("R4D_HIDE_UNFILLED")
+GATE_SCORES = flag("R4D_GATE_SCORES", "0")
+
+
+def head_of(name):
+    """--fc-v-{slot}-{head} -> head, or None for a packed per-slot list."""
+    parts = name.split("-")
+    return int(parts[5]) if len(parts) > 5 else None
diff -ruN -x __pycache__ R3M/tools/r4s_small_hops.py R4M/tools7/r4s_small_hops.py
--- R3M/tools/r4s_small_hops.py	1969-12-31 16:00:00
+++ R4M/tools7/r4s_small_hops.py	2026-09-21 01:39:46
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
diff -ruN -x __pycache__ R3M/tools/r4t_consumer_chunk.py R4M/tools7/r4t_consumer_chunk.py
--- R3M/tools/r4t_consumer_chunk.py	1969-12-31 16:00:00
+++ R4M/tools7/r4t_consumer_chunk.py	2026-09-21 01:39:46
@@ -0,0 +1,37 @@
+"""R4T: cap the number of view-timeline animations per consumer element.
+
+Why (R4T.md §Results): in Blink the per-frame cost of a carrier whose width changed is not fixed —
+it grows with the number of animations that share the consumer element: measured (2,000 changing
+carriers, nested consumer chain) 110 µs at 2,000 animations/element, 61 at 1,000, 42 at 500, 29 at
+250, 23 at 125, 19.7 at 62, 19.0 at 31, 19.8 at 15 => ≈18.5 µs + 0.046 µs x animations-per-element,
+almost all of it in RunPaintLifecyclePhase self (PendingAnimations::Update) — the style pass itself is
+≈10 µs per changed carrier regardless. combined4 puts 512 animations on every matvec/bridge consumer
+(`.shared-qkv-cN`, `.shared-attn-cN`, `.shared-fc-cN`, `.cache-bridge-cN`, `.bN-bridge-cN`), 768 on
+`.loop-reader` (R3R) and 256 on `.embedding-consumer-N`: ≈40 µs per changed carrier = R3A's measured
+constant. Splitting the same animations over more nested consumer elements (each still an ancestor of
+the readers, all registered numbers inherit) keeps every pass/frame identical and drops the constant to
+≈20 µs. Knee = 64 animations per element (no further gain at 31 or 15).
+
+Flag: R4T_CONSUMER_CHUNK = animations per consumer element (default 64; 0 = off, i.e. the old 512/768/256).
+Sites: browser_gpt2_reused_core.py (h.matvec chunk, h.bridge chunk), r3r_fold_hop.py (.loop-reader ->
+.loop-reader > .loop-reader-cK chain), browser_gpt2_embedding.py (.embedding-consumer-N step),
+r2g_has_scope.py (LOOP_CHAIN gains the .loop-reader-cK steps). `.fvs-score-reader` (96 animations) is left
+as is (predicted 21 vs 20 µs).
+"""
+import os
+
+_raw = os.environ.get("R4T_CONSUMER_CHUNK", "64").strip().lower()
+CHUNK = 0 if _raw in ("", "0", "false", "no", "off") else int(_raw)
+ENABLED = CHUNK > 0
+
+
+def chunk(default):
+    """Animations per consumer element for a site whose historical chunk is `default`."""
+    return min(CHUNK, default) if ENABLED else default
+
+
+def loop_reader_classes(width):
+    """Classes of the nested chunk elements between .loop-reader and .loop-input (outermost first)."""
+    if not ENABLED:
+        return []
+    return [f"loop-reader-c{k}" for k in range(0, (width + CHUNK - 1) // CHUNK)]
```
