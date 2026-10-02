# bundles/combined4-c32c — combined4-c32b + `--value-layout widths` (R4D, 2026-09-21)

**= `bundles/combined4-c32b` (same tools copy, same flags) with the emitter's existing `--value-layout widths` instead of `runs`.** `index.html` is
byte-identical to combined4-c32b; runtime.css differs ONLY in the 384 `.fvs-v-H-S` rules (R4D/rule_diff.py): the V glyph keeps its font at a FIXED
location (`var(--fr-v-S-H),"P000" 1`) and the softmax weight multiplies the shaped delta in the item width instead of the P000 axis:
`width:calc-size(max-content,calc(12320.768px + (size - 12320.768px) * var(--fw-H-S)));min-width:0`. Rows sum the same `base + w·Δ` terms, so the
row formula is unchanged. Effect: a filled (head, slot) font instance no longer changes on every pass (only when the layer changes), which is the
coordinator's "constant font instance" lever (C2 §6 item 7: prior 1-layer fixture −18 % wall at 32 populated, worst RMSE 0.000609 vs 0.000895).
**Numerics: NOT bit-identical to c32b** — the weight is no longer quantised to the P000 axis's 1/16384 (error ≤ 12000/32768·1.024 ≈ 0.375 px per glyph);
instead the shaped width and the item width are LayoutUnit-snapped (≤ 1/64 px each, ≈ 0.03 px per glyph). Same math, ~12× less per-glyph
quantisation, so the browser output moves TOWARDS the float reference that produces the 32 ids (offline gate: analytical bound + the prior fixture's
measured RMSE). Correctness must still be confirmed by a Chrome run (ids 32/32) before READY.

## Recipe (only `--value-layout widths` differs from combined4-c32b)

Built 2026-09-21 00:14 by `R4D_VALUE_LAYOUT=widths work/2026-09-19/R4D/compile-r4d.sh combined4-c32c 32` (log `R4D/compile-c32c.log`).

Tools copy `work/2026-09-19/R4D/tools` = `rsync -a --exclude __pycache__ R3M/tools/` (combined4's emitter, itself = `bundles/combined4/BUILD.md`'s diff vs the repo `tools/`)
plus the R4D edits below. Same four symlinks beside the tools copy as R3M/R4C (`assets -> ../F4/assets`, `data`, `experiments`, `global-projection-assets -> ../F2/global-projection-assets`).
Fonts reused (283 faces, `font-witnesses.json` identical to `combined4-c32` modulo the tools path); no new font files.

Reference bundle: `bundles/combined4-c32` — identical recipe (same env flags, same CLI), the ONLY difference is the R4D tools edit (flags default ON):

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4D
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R2G_SCOPED_HAS=1 R3R_FOLD_HOP=1 R3H_BLOCKFLOW_MAX=1
# R4D flags (tools/r4d_flags.py): R4D_EMPTY_UNFILLED=1 R4D_LEAN_LATCH=1 R4D_UNPACK_V=1 R4D_HIDE_UNFILLED=1 (defaults) R4D_GATE_SCORES=0 (default OFF)
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 32 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout widths --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined4-c32c
```

## What the R4D flags change (all exact by construction: same numbers reach the same fonts)

- **R4D_EMPTY_UNFILLED**: `@property --fc-k-S/--fr-k-S/--fc-v-S-H/--fr-v-S-H` initial-value = one zero axis (`"K000" 0` / `"V{h·64}" 0`) instead of the
  768-axis zero list. Unfilled slots are never aliased (F5 filter), so their V glyph leaves (768 per slot) and score glyphs (12 per slot) substitute 12 B
  instead of ≈7.7 KB per restyle. Every fvar axis of the 24 operator fonts has default 0 (checked), so omitted axes = explicit zeros.
- **R4D_LEAN_LATCH**: `@container fvscache style(--fvs-write-slot:W){.fvs-bank{transition-property: fields of slots 0..W}}` (32 rules) and the write rule
  lists slots 0..W−1 instead of "all but W". Slots > W were never written (full causal window, slots fill in order) so they have no running transition;
  unlisting a property with no transition cancels nothing (css-transitions §3). The full-list `.fvs-bank` base rule remains for the no-match state.
- **R4D_UNPACK_V**: 12 per-head 64-axis V lists per slot (`--fc-v-S-H`, 37 latched fields per slot instead of 26) so each of the 768·p filled V glyphs
  substitutes/parses/shapes its own head's 65-axis list instead of a 769-axis one. Same `var(--fvn-v-H-i)` entries, same head tags (`V{h·64+i}`), same
  fonts (`FvsValue{h}`), same weights; the K list stays packed (`--fc-k-S`).
- **R4D_HIDE_UNFILLED**: `--fvq-S` (`<number>`, inherits:false, = the score reader's `--fv-S` expression) on the `fvscache` container and
  `@container fvscache style(--fvq-S:0){.fvs-v-0-S,…,.fvs-v-11-S{display:none}}` (32 rules): unfilled slots' 768 V glyph leaves have no box (no
  shaping, no flex item). The 768 row widths subtract `var(--fvs-nbase)` = `(--fvs-write-slot + 1)·12320.768px` (one base advance per PRESENT glyph)
  instead of the literal `32·12320.768px`, so `(size - subtracted)` is the same sum of weighted V deltas. Only difference: an absent glyph's
  LayoutUnit-snapped base advance (12320.78125 px vs the literal 12320.768) no longer enters `size` — a residue of ≤ (32−1)/64 px ≈ 4e-5·fb/fd ctx
  units per row that the NumPy reference never modelled (the KV path's measured rmse vs float is 3e-3, F4 §5). `index.html` differs from `combined4-c32` only
  in these 768 constants.
- **R4D_GATE_SCORES** (OFF here): would `display:none` the score carriers of unfilled slots.

## Offline verification (R4D/rule_diff.py, R4D/R4D.md)

- `index.html` = `combined4-c32` with the 768 row constants replaced by `var(--fvs-nbase)` (checked by string replacement); `font-witnesses.json` 283/283 identical; `launch_browser_gpt2.py --check`: static, `runtimeJavaScript: false`.
- Leaf-rule diff of runtime.css vs `combined4-c32` is confined to: the KV `@property` registrations (initial values; `--fc/--fr-v-S-H` replace `--fc/--fr-v-S`),
  `.fvs-v-H-S` (reads `var(--fr-v-S-H)`), the 12·32 bank write rules (per-head V writes, lean retained lists), the 32 new per-write-slot `.fvs-bank`
  transition lists, `.fvs-query` list declarations (`--fvs-all-fields`, `--fvs-retained-S`) the 32 `@property --fvq-S` + `.fvs-query` flag declarations, the 32 `display:none` container rules, `@property --fvs-nbase` and the `.head-isolation` wall (now resets 12·32
  `--fr-v-S-H` names instead of 32). Nothing else differs.
- Model unchanged → reference ids unchanged: 32 ids in `R4C/reference_ids_32.json` (NumPy teacher-forced and free-running = pinned ctx32 tokens).

## diff -ru work/2026-09-19/R3M/tools work/2026-09-19/R4D/tools

```diff
diff -ru --exclude __pycache__ R3M/tools/browser_gpt2_font_vector_cache.py R4D/tools/browser_gpt2_font_vector_cache.py
--- R3M/tools/browser_gpt2_font_vector_cache.py	2026-09-20 22:01:52
+++ R4D/tools/browser_gpt2_font_vector_cache.py	2026-09-21 00:06:55
@@ -13,6 +13,7 @@
 import build_hybrid_twelve_block as hybrid
 import f4_packing as f4
 import f5_scoping as f5
+import r4d_flags as r4d
 import r2c_hoist as r2c
 import numpy as np
 from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
@@ -88,7 +89,13 @@
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
@@ -171,8 +178,10 @@
         raise ValueError("Early value preparation requires fixed font widths")
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
@@ -181,6 +190,15 @@
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
@@ -195,6 +213,23 @@
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
@@ -261,12 +296,21 @@
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
@@ -285,7 +329,6 @@
         retained_value = retained if literal else f"var(--fvs-retained-{slot})"
         for layer in range(blocks):
             css += f"@container runtime style(--layer:{layer}){{@container fvscache style(--fvs-write-slot:{slot}){{.fvs-bank-{layer}{{transition-property:{retained_value};{';'.join(writes)}}}}}}}"
-    sequential = kv_window is None or (kv_sinks == 0 and capacity == positions)
     if f5.BANK_FILLED_ALIASES and sequential:
         # F5: with a full causal window slots fill in order, so while slot S
         # is being written only slots 0..S hold values; the others equal the
@@ -404,7 +447,16 @@
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
@@ -446,7 +498,11 @@
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
@@ -454,11 +510,12 @@
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
@@ -467,7 +524,12 @@
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
@@ -519,6 +581,29 @@
             + "</div>"
         )
     body = '<div class="fvs-query">' + body + "</div>"
+    gate_scores = r4d.GATE_SCORES and sequential
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
     css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
     return (
         body,
@@ -533,6 +618,11 @@
             "f4PackedBanks": packed,
             "f4NumericLists": f4.NUMERIC_LISTS,
             "latchedFieldsPerSlot": len(all_fields) // capacity,
+            "r4dEmptyUnfilled": r4d.EMPTY_UNFILLED,
+            "r4dLeanLatch": lean,
+            "r4dUnpackV": r4d.UNPACK_V,
+            "r4dHideUnfilled": hide_unfilled,
+            "r4dGateScores": r4d.GATE_SCORES and sequential,
             "prewarmValues": prewarm_values,
             "attentionMask": "full causal"
             if capacity == positions
diff -ru --exclude __pycache__ R3M/tools/browser_gpt2_reused_adapter.py R4D/tools/browser_gpt2_reused_adapter.py
--- R3M/tools/browser_gpt2_reused_adapter.py	2026-09-20 22:01:52
+++ R4D/tools/browser_gpt2_reused_adapter.py	2026-09-21 00:02:36
@@ -14,6 +14,7 @@
 from browser_gpt2_reused_core import compile_reused
 import r2f_lean_handshake as r2f
 import r3r_fold_hop as r3r
+import r4d_flags as r4d
 
 
 def compile_reused_runtime_core(
@@ -243,6 +244,11 @@
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
Only in R4D/tools: r4d_flags.py
```
