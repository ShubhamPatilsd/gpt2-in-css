# bundles/combined8-c32 — combined7 recipe + R5E (dead-declaration hygiene, all four flags on) + R5H (`1ch` score readback, `R5H_CH_SCORES=1` → `R4S_SMALL_HOPS` forced off), capacity 32, `--value-layout widths` (R4D flags, R4T chunk 64, R4S_SMALL_HOPS=0 — widths numerics are not bit-identical; ids are the acceptance, as combined7-c32)

Built by R5X on 2026-09-24 16:23 (`work/2026-09-19/R5X/compile.sh bundles/combined8-c32 32 12` with `VALUE_LAYOUT=widths R4S_SMALL_HOPS=0`; tools copy `work/2026-09-19/R5X/tools` = `R4M/tools7` (combined7's emitter) + `R5E/tools-vs-tools7.diff`
+ `R5H/tools-vs-tools7.diff`, one conflict resolved by `R5X/apply_conflicts.py`; symlinks as R4M (assets → F4/assets, data, experiments, global-projection-assets) plus
`R5X/assets-r5h/font-vector-operators-r5h/` = R5H's 12 F4 dot fonts with cmap U+0030 → `dot` (every other table byte-identical; re-asserted by the emitter at each build).
Reference for pairs: `bundles/combined7-c32`. Round-5 verdicts folded in: R5E (exact hygiene, neutral) and R5H (the cap-32 win; neutral at cap 8); R5C (regression, `bundles/R5C/DO-NOT-MERGE`) and R5M (memory not cut) are NOT in this bundle.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R5X
# combined7's exports (bundles/combined7/BUILD.md: F4_*, R2C_*, R2F_*, R2D_*, R2G_*, R3R_*, R3H_*, R4D_*, R4T_CONSUMER_CHUNK=64; R4S_SMALL_HOPS=0) plus:
export R5E_LEAN_WALLS=1 R5E_LP_INHERIT=1 R5E_DROP_DEAD_LISTS=1 R5E_KEEP_DIAG=0 R5H_CH_SCORES=1
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 32 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout widths --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined8-c32
```

## Flags (new since combined7; the rest as `bundles/combined7/BUILD.md`)

| flag | default (here) | owner | effect |
|---|---|---|---|
| `R5H_CH_SCORES` | 1 (`0` = combined7's code path) | R5H | the 12·capacity `.fvs-score-H-S` score carriers become EMPTY `display:block` elements with the same `font`/`font-variation-settings` and `--fs-H-S:calc((1ch / 1px − base) · var(--fqs-H) · var(--fr-ks-S-H) · k/128)`; per head the slot elements nest inside the ctx scroller's `.track`, the chain bottom `.fvs-score-reader.fvs-sr-H` carries head H's softmax/weights and hosts its 64 V rows. No score scroller/timelines/keyframes/stamp/receipt/gate and no R4S anchors/containers (`R4S_SMALL_HOPS` is forced off at import). `@font-face FvsDotH` → `R5X/assets-r5h/…-r5h.woff2`. Manifest `r5hChScores`, `r4sSmallHops:false`. |
| `R5E_LEAN_WALLS` | 1 | R5E | `.core-reset` 16,156 `--p:initial` → 0; `.head-isolation` 26,889 → 3,913 (kept set derived mechanically at build from the wall's ancestor chain; manifest `r5eLeanWallStats`) |
| `R5E_LP_INHERIT` | 1 | R5E | `--lp-*` stay `inherits:true`; the 768 + 4,224 `--lp-i:inherit` forwards on `.loop-input` / `.loop-reader-cK` are not emitted |
| `R5E_DROP_DEAD_LISTS` | 1 | R5E | `.fvs-query{--fvs-all-fields}` and the 32 `--fvs-retained-S` lists (0 readers with literal bank lists) not emitted |
| `R5E_KEEP_DIAG` | 0 | R5E | the 3 readback probe pairs + `#core-epoch-observer` removed (`=1` restores them) |

## Merge (`R5X/merge.sh`; `R5X/tools-vs-tools7.diff`, 831 lines, embedded below)

`cp -R R4M/tools7 R5X/tools`; `patch -p2 -F3 -N < R5E/tools-vs-tools7.diff` (6 files, 0 rejects); `patch -p2 -F3 -N < R5H/tools-vs-tools7.diff` (3 files, **1 reject**: `browser_gpt2_reused_adapter.py`
hunk @@ -171,8 — the inline pass-reader count assertion both owners edit). Resolved by `R5X/apply_conflicts.py` as an exact-string edit to the union
`diag = 1 if r5e.KEEP_DIAG else 0; if tagged != (6 if r5h.no_score_hop() else 7) - 1 + diag or tagged_position != 1 + diag` (R5E: −1 + diag for the probe epoch twins; R5H: `no_score_hop()`
covers R4S or R5H for the missing score stamp reader; both act on the same body). The two import-line hunks (adjacent lines in the same import blocks) applied with fuzz in the intended
places. `r5e_dead_weight.py` / `r5h_ch_scores.py` cmp-identical to the owners'; `diff -rq`: merged − R5E/tools = exactly R5H's 2 files + module, merged − R5H/tools = exactly R5E's 5 files + module.
Semantic interaction R5E × R5H (checked in the built bundles by the owners' checkers): R5E's `lean_walls` is derived from the built page (R5H's slot chains are below the walls, not above them:
kept sets identical to R5E's own build); R5E's probe removal and R5H's stamp removal both lower the adapter's inline-reader count (the union assertion above); R5H's per-head bottoms and R5E's
`--lp` inheritance touch disjoint subtrees.

## Offline verification (`R5X.md` §2; logs in `R5X/logs/`; twins built one at a time in `R5X/scratch/` and deleted after their checks)

- **All new flags off** (`R5E_LEAN_WALLS=0 R5E_LP_INHERIT=0 R5E_DROP_DEAD_LISTS=0 R5E_KEEP_DIAG=1 R5H_CH_SCORES=0`) **reproduces `bundles/combined7-c32` byte-for-byte** (index.html identical; runtime.css identical after URL-depth normalisation; manifest +6 keys; witnesses 283/283).
- R5H-only twin (R5E flags off) == `bundles/R5H-c32` (index.html identical, css identical modulo the agent dir of the 12 dot-font URLs, manifest +5 R5E keys, witnesses 283/283 modulo the file mtime field).
- Owners' checkers, unmodified, on same-depth twin pairs (the shipped bundle's URL text differs from a scratch twin's by one directory level, which trips both checkers' raw URL compares — R4M.md §6.1's artefact; the all-on twin is URL-normalised identical to this bundle with 0 manifest differences): `R5E/offline_check.py` all-on vs R5H-only → **RESULT: PASS**; `R5H/offline_check.py` all-on vs R5E-only (cap 32) → **RESULT: PASS**.
- NumPy ids with the merged tools: 8-token `[11, 314, 1101, 7926, 11, 475, 314, 1101]`; prompt-40 free-running 32/32 == `R4P/reference_ids_32_40.json` (== teacher-forced).
- Witnesses vs `combined7-c32`: 271/283 identical + the 12 F4 dot faces replaced by R5H's `-r5h` faces (same advance 29984 / upem 1000; the witness renders U+0030). `launch_browser_gpt2.py --check`: 285 static files, `runtimeJavaScript: false`.
- Sizes: runtime.css 49311014 B, index.html 7125736 B (`combined7-c32`: see its BUILD.md); elements 86438 (`combined7-c32` 86439).

## Chrome

ONE passive 32-token run, prompt token 40 ("I", `B0_PROMPT_TOKEN=40`) vs `R4P/reference_ids_32_40.json`, 2026-09-24 16:58:41–17:14:35 under `CHROME.lock` (gate: AC, disk 4 GB, swap used 3,250 → 3,356 MB, load ≈4–5; `R5X/run-combined8-c32/c32-p40.{json,summary.md,memstate.txt}`): ids **32/32**, **total 905.6 s** (k=1 18.5 / 8 19.3 / 16 29.5 / 24 35.3 / 32 43.3; fit 2..32 = 12.05 + 0.975·k), **RecalcStyleCount flat 72/token** (72.0 − 0.012·k; c32c 84, combined6-c32 with R4S 126 + 70.8·k), LayoutCount 64 flat, RSS renderer peak 4,415 MB. vs R5H-c32 918.2 s (same slope, −12.6 s), c32c 758.7 s (clean-memory Hello run, not comparable) / 1,008.6 s and combined7-c32 1,050.1 s (swap-loaded prompt 40). **READY 17:14:35.** Details and per-token table `R5X.md` §4.

## `diff -ruN -x __pycache__ work/2026-09-19/R4M/tools7 work/2026-09-19/R5X/tools` (831 lines; also at `R5X/tools-vs-tools7.diff`; combined7's own diff vs R3M is in `bundles/combined7/BUILD.md`)

```diff
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_font_vector_cache.py R5X/tools/browser_gpt2_font_vector_cache.py
--- R4M/tools7/browser_gpt2_font_vector_cache.py	2026-09-21 01:39:46
+++ R5X/tools/browser_gpt2_font_vector_cache.py	2026-09-24 16:21:15
@@ -14,8 +14,10 @@
 import f4_packing as f4
 import f5_scoping as f5
 import r4d_flags as r4d
+import r5e_dead_weight as r5e
 import r2c_hoist as r2c
 import r4s_small_hops as r4s
+import r5h_ch_scores as r5h  # R5H: forces r4s.SMALL_HOPS off when R5H_CH_SCORES is on
 import numpy as np
 from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
 from build_gpt2_block_css import UNITS_PER_EM
@@ -179,6 +181,8 @@
         raise ValueError("Early value preparation requires fixed font widths")
     if prewarm_values and r4s.SMALL_HOPS:
         raise ValueError("R4S: the score chain has no score gate to prewarm against")
+    if prewarm_values and r5h.CH_SCORES:
+        raise ValueError("R5H: the ch score readback has no score gate to prewarm against")
     operators = fonts()
     packed = f4.PACKED_BANKS
     if packed and value_layout not in ("runs", "widths"):
@@ -210,9 +214,8 @@
     )
     literal = f5.BANK_LITERAL_LISTS
     css += (
-        ".fvs-query{--fvs-all-fields:"
-        + ",".join(all_fields)
-        + "}.fvs-bank{transition-property:"
+        ("" if (literal and r5e.DROP_DEAD_LISTS) else ".fvs-query{--fvs-all-fields:" + ",".join(all_fields) + "}")  # R5E: unread when literal
+        + ".fvs-bank{transition-property:"
         + (",".join(all_fields) if literal else "var(--fvs-all-fields)")
         + ";transition-duration:1ms;transition-delay:86400s;transition-timing-function:steps(1,end);transition-behavior:allow-discrete}"
     )
@@ -303,7 +306,8 @@
             name for name in all_fields
             if name not in fields and (not lean or f4.slot_of(name) < slot)
         ) or "none"
-        css += f".fvs-query{{--fvs-retained-{slot}:{retained}}}"
+        if not (literal and r5e.DROP_DEAD_LISTS):  # R5E: unread when literal
+            css += f".fvs-query{{--fvs-retained-{slot}:{retained}}}"
         writes = []
         if packed:
             # F4: the 12 live head lists concatenate into one latched list per kind.
@@ -353,11 +357,17 @@
     if packed:
         # F4: 12 dot + 12 value fonts, K axes retagged per head (F2's recipe).
         for head, (dot_path, value_path) in enumerate(f4.packed_operator_fonts(FONT_DIR)):
+            if r5h.CH_SCORES:
+                # R5H: same dot font + cmap U+0030 -> dot (so `1ch` is the score advance)
+                dot_path = r5h.ch_dot_font(dot_path)
             css += f'@font-face{{font-family:FvsDot{head};src:url("{dot_path.as_uri()}")}}'
             css += f'@font-face{{font-family:FvsValue{head};src:url("{value_path.as_uri()}")}}'
     else:
         for kind, family in (("dot", "FvsDot"), ("value", "FvsValue")):
-            css += f'@font-face{{font-family:{family};src:url("{(FONT_DIR / (kind + ".woff2")).as_uri()}")}}'
+            face_path = FONT_DIR / (kind + ".woff2")
+            if kind == "dot" and r5h.CH_SCORES:
+                face_path = r5h.ch_dot_font(face_path)
+            css += f'@font-face{{font-family:{family};src:url("{face_path.as_uri()}")}}'
     if value_layout == "fallback":
         for slot, path in enumerate(fallback_value_fonts(capacity)):
             start = CODEPOINT_BASE + slot * DIM
@@ -366,9 +376,10 @@
     unit = QK_SIZE / UNITS_PER_EM
     score_fields = [f"--fs-{h}-{s}" for h in range(HEADS) for s in range(capacity)]
     progress_fields = [f"--fsp-{h}-{s}" for h in range(HEADS) for s in range(capacity)]
-    if r4s.SMALL_HOPS:
+    if r4s.SMALL_HOPS or r5h.CH_SCORES:
         # R4S: the scores are published by the chain containers and inherit down to
         # the chain bottom (the softmax element); no progress/stamp/ready scratch.
+        # R5H: each score element publishes its own `--fs` from `1ch`; same inheritance.
         css += hybrid.regs(score_fields)
     else:
         css += hybrid.regs(
@@ -379,12 +390,21 @@
         for slot in range(capacity):
             name, timeline = f"fvs-score-{head}-{slot}", f"--fvs-score-{head}-{slot}"
             progress = f"--fsp-{head}-{slot}"
-            if not r4s.SMALL_HOPS:
+            if not r5h.no_score_hop():  # R4S / R5H: no score timelines or keyframes
                 timelines.append(timeline)
                 animations.append(name)
                 css += f"@keyframes {name}{{from{{{progress}:-2}}to{{{progress}:1}}}}"
             dot_family = f"FvsDot{head}" if packed else "FvsDot"
             fr_k = f"--fr-k-{slot}" if packed else f"--fr-k-{slot}-{head}"
+            if r5h.CH_SCORES:
+                # R5H: empty block element with the same font instance; the score is
+                # (1ch - base) * fqs * frks / (8 * coef * unit) = the width decode
+                # ((width - 262144) / 128) of the carrier rule below, without the carrier.
+                css += r5h.slot_rule(
+                    head, slot, QK_SIZE, dot_family, fr_k,
+                    dot["base"] * unit, 1 / (8 * dot["coefficient"] * unit),
+                )
+                continue
             css += (
                 f".{name}{{font:{QK_SIZE}px {dot_family};line-height:1;font-kerning:none;font-variation-settings:var({fr_k}),var(--fvs-query-{head});"
                 f"width:calc-size(max-content,calc(262144px + (size - {dot['base'] * unit:.12g}px) * var(--fqs-{head}) * var(--fr-ks-{slot}-{head}) * {128 / (8 * dot['coefficient'] * unit):.12g}))}}"
@@ -400,7 +420,10 @@
             reads.append(
                 f"--fs-{head}-{slot}:calc((1572864 / (var({progress}) + 2) - 786432) / 128)"
             )
-    if r4s.SMALL_HOPS:
+    if r5h.CH_SCORES:
+        # R5H: no carriers at all; the per-head slot chains are emitted around the V rows (row()).
+        score_source = ""
+    elif r4s.SMALL_HOPS:
         # R4S: fixed stage of 12*capacity anchors, then the chain; no stamp, receipt or gate
         # (the scores resolve in the same layout as the glyphs they come from).
         score_source = r4s.stage(metrics)
@@ -431,9 +454,10 @@
             "--fvs-score-ready:calc(1 - min(1,abs(round(nearest,(524288 / var(--fss) - 786432) / 1024,1) - var(--epoch))))}"
             ".fvs-score-gate{content-visibility:hidden;contain-intrinsic-size:0px 0px}@container fvsscore style(--fvs-score-ready:1){.fvs-score-gate{content-visibility:visible}}"
         )
-    soft = []
+    soft_by_head = [[] for _ in range(HEADS)]
     soft_fields = []
     for head in range(HEADS):
+        soft = soft_by_head[head]
         maximum, denominator, bases = f"--fm-{head}", f"--fd-{head}", f"--fb-{head}"
         soft_fields += [maximum, denominator, bases]
         valid_scores = ",".join(
@@ -467,7 +491,13 @@
     )
     # Scores and their animated progress are local scratch. Resolve softmax
     # on the same element so these arrays need not inherit into every V glyph.
-    css += ".fvs-score-reader{" + ";".join(soft) + "}"
+    if r5h.CH_SCORES:
+        # R5H: one softmax element per head (the bottom of that head's slot chain).
+        for head in range(HEADS):
+            css += f".{r5h.head_class(head)}{{" + ";".join(soft_by_head[head]) + "}"
+    else:
+        soft = [d for head in range(HEADS) for d in soft_by_head[head]]
+        css += ".fvs-score-reader{" + ";".join(soft) + "}"
     value = operators["value"]
     value_unit = VALUE_SIZE / UNITS_PER_EM
     slim_glyphs = value_weight_once and value_layout in ("runs", "widths")
@@ -489,11 +519,18 @@
             f"--fw-{head}-{slot}" for head in range(HEADS) for slot in range(capacity)
         ]
         css += hybrid.regs(weight_fields)
-        css += ".fvs-score-reader{" + ";".join(
-            f"--fw-{head}-{slot}:calc(var(--fe-{head}-{slot}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
-            for head in range(HEADS)
-            for slot in range(capacity)
-        ) + "}"
+        if r5h.CH_SCORES:
+            for head in range(HEADS):
+                css += f".{r5h.head_class(head)}{{" + ";".join(
+                    f"--fw-{head}-{slot}:calc(var(--fe-{head}-{slot}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
+                    for slot in range(capacity)
+                ) + "}"
+        else:
+            css += ".fvs-score-reader{" + ";".join(
+                f"--fw-{head}-{slot}:calc(var(--fe-{head}-{slot}) * var(--fr-vs-{slot}-{head}) / var(--fb-{head}))"
+                for head in range(HEADS)
+                for slot in range(capacity)
+            ) + "}"
     for head in range(HEADS):
         combined_settings = []
         for slot in range(capacity):
@@ -544,9 +581,12 @@
             css += f".fvs-value-head-{head}{{display:contents;font:{VALUE_SIZE}px {families};font-variation-settings:{','.join(combined_settings)};font-kerning:none}}"
     pattern = r'<i class="metric" style="width:calc\(262144px \+ var\(--(?:ctx|out)-(\d+)\) \* 128px\);view-timeline:([^ ]+) inline"></i>'
 
+    row_order = []
+
     def row(match):
         coordinate, timeline = int(match[1]), match[2]
         head, local = divmod(coordinate, DIM)
+        row_order.append(coordinate)
         subtracted = (
             "var(--fvs-nbase)"
             if hide_unfilled
@@ -565,11 +605,19 @@
             f'<i class="fvs-v-{head}-{slot}">&#x{CODEPOINT_BASE + local:X};</i>'
             for slot in range(capacity)
         )
-        return f'<span class="metric fvs-value-row" style="width:{dimensions};view-timeline:{timeline} inline">{runs}</span>'
+        prefix = suffix = ""
+        if r5h.CH_SCORES:
+            # R5H: head H's 64 rows sit inside head H's slot chain + softmax bottom
+            # (in the track: the rows stay position:absolute against .track).
+            prefix = r5h.chain_open(head, capacity) if local == 0 else ""
+            suffix = r5h.chain_close(capacity) if local == DIM - 1 else ""
+        return f'{prefix}<span class="metric fvs-value-row" style="width:{dimensions};view-timeline:{timeline} inline">{runs}</span>{suffix}'
 
     value_source, count = re.subn(pattern, row, context_carrier)
     if count != WIDTH:
         raise ValueError(f"Expected 768 native context carriers, found {count}")
+    if r5h.CH_SCORES and row_order != list(range(WIDTH)):
+        raise ValueError("R5H: context carriers are not in coordinate order (per-head chains need contiguous heads)")
     if prewarm_values:
         # Let fixed V fonts shape before attention scores are ready. Keep the
         # output generation marker blocked, so speculative geometry cannot
@@ -591,7 +639,10 @@
         if slim_glyphs
         else ".fvs-value-row{display:inline-flex;gap:0;font:0px monospace;line-height:1}"
     )
-    if r4s.SMALL_HOPS:
+    if r5h.CH_SCORES:
+        # R5H: the 12 per-head chains + softmax bottoms are inside value_source's track.
+        body = '<div class="fvs-softmax">' + value_source + "</div>"
+    elif r4s.SMALL_HOPS:
         body = (
             score_source
             + chain_open
@@ -616,7 +667,7 @@
     body = '<div class="fvs-query">' + body + "</div>"
     # R4M merge: R4D_GATE_SCORES is off under R4S (no score scroller; display:none on an
     # anchor row would invalidate the chain's anchor-size()); --fv-S masking is unchanged.
-    gate_scores = r4d.GATE_SCORES and sequential and not r4s.SMALL_HOPS
+    gate_scores = r4d.GATE_SCORES and sequential and not r5h.no_score_hop()
     if hide_unfilled or gate_scores:
         # R4D: per-slot filled flag on the fvscache container (same expression
         # as --fv-S on the score reader, which is inherits:false and therefore
@@ -639,7 +690,7 @@
         for slot in range(capacity):
             selectors = ",".join(f".fvs-score-source .fvs-score-{head}-{slot}" for head in range(HEADS))
             css += f"@container fvscache style(--fvq-{slot}:0){{{selectors}{{display:none}}}}"
-    if not r4s.SMALL_HOPS:  # R4S: no score timelines
+    if not r5h.no_score_hop():  # R4S / R5H: no score timelines
         css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
     return (
         body,
@@ -661,6 +712,7 @@
             "r4dGateScores": gate_scores,
             "prewarmValues": prewarm_values,
             **r4s.manifest(capacity),
+            **r5h.manifest(capacity),
             "attentionMask": "full causal"
             if capacity == positions
             else "initial sinks plus rolling recent context",
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_reused_adapter.py R5X/tools/browser_gpt2_reused_adapter.py
--- R4M/tools7/browser_gpt2_reused_adapter.py	2026-09-21 01:39:46
+++ R5X/tools/browser_gpt2_reused_adapter.py	2026-09-24 16:21:15
@@ -15,8 +15,10 @@
 import r2f_lean_handshake as r2f
 import r3r_fold_hop as r3r
 import r4s_small_hops as r4s
+import r5h_ch_scores as r5h  # R5H: forces r4s.SMALL_HOPS off when R5H_CH_SCORES is on
 import r4d_flags as r4d
 import r4t_consumer_chunk as r4t
+import r5e_dead_weight as r5e
 
 
 def compile_reused_runtime_core(
@@ -84,9 +86,9 @@
     source = source.replace("var(--epoch)", "var(--position)")
     export = (
         '<div class="reused-final-export">'
-        + hybrid.probe(f"block-{last}-probe", "out", 768).replace(
+        + (hybrid.probe(f"block-{last}-probe", "out", 768).replace(
             "var(--epoch)", "var(--position)"
-        )
+        ) if r5e.KEEP_DIAG else "")  # R5E: diagnostic readback only
         + source
         + "</div>"
     )
@@ -141,7 +143,7 @@
         # and stamp the current pass directly onto every reader.
         receipts = [
             f".shared-{kind}-receipt" for kind in ("qkv", "attn", "fc", "proj")
-        ] + [".cache-bridge-receipt"] + ([] if r4s.SMALL_HOPS else [".fvs-score-receipt"])
+        ] + [".cache-bridge-receipt"] + ([] if r5h.no_score_hop() else [".fvs-score-receipt"])
         pass_readers = ",".join(
             [
                 ".loop-input",
@@ -170,8 +172,9 @@
         body, tagged_position = f5.tag_inline_readers(
             body, "var(--position)", "pass-reader"
         )
-        # R4S: the score stamp marker (one inline var(--epoch) reader) no longer exists
-        if tagged != (6 if r4s.SMALL_HOPS else 7) or tagged_position != 2:
+        # R4S / R5H: the score stamp marker (one inline var(--epoch) reader) no longer exists
+        diag = 1 if r5e.KEEP_DIAG else 0  # R5E: the reused-probe / block-11-probe epoch twins
+        if tagged != (6 if r5h.no_score_hop() else 7) - 1 + diag or tagged_position != 1 + diag:  # R5X: R5E x R5H union
             raise ValueError(
                 f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
             )
@@ -199,7 +202,7 @@
     receiver = receiver.replace(
         "{child}",
         '<div id="core-result">'
-        + hybrid.probe("core-probe", "x", 768)
+        + (hybrid.probe("core-probe", "x", 768) if r5e.KEEP_DIAG else "")  # R5E
         + "{child}</div>",
     )
     body = (
@@ -239,6 +242,7 @@
         "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
         "r3rFoldHop": r3r.FOLD_HOP,
         "r4sSmallHops": r4s.SMALL_HOPS and codec == "font-vector",
+        "r5hChScores": r5h.CH_SCORES and codec == "font-vector",
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_reused_core.py R5X/tools/browser_gpt2_reused_core.py
--- R4M/tools7/browser_gpt2_reused_core.py	2026-09-21 01:39:46
+++ R5X/tools/browser_gpt2_reused_core.py	2026-09-24 16:21:15
@@ -16,6 +16,7 @@
 import f5_scoping as f5
 import r2c_hoist as r2c
 import r3r_fold_hop as r3r
+import r5e_dead_weight as r5e
 import r4t_consumer_chunk as r4t
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import (
@@ -303,7 +304,7 @@
         )
     inner = (
         '<div class="reused-output" id="reused-result">'
-        + h.probe("reused-probe", "out", W)
+        + (h.probe("reused-probe", "out", W) if r5e.KEEP_DIAG else "")  # R5E
         + output.replace("{child}", '<i id="loop-result"></i>')
         + "</div>"
     )
@@ -345,7 +346,8 @@
                 f"--gate-{kind}",
             ]
         if r3r.FOLD_HOP:
-            lp, saved, outputs = r3r.reader_names(W), [], []
+            # R5E: --lp-* stay inherits:true (no forwards) under R5E_LP_INHERIT
+            lp, saved, outputs = ([] if r5e.LP_INHERIT else r3r.reader_names(W)), [], []
         else:
             lp = [f"--lp-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
             saved = [f"--saved-{bank}-{i}" for bank in range(2) for i in range(W + 1)]
diff -ruN -x __pycache__ R4M/tools7/browser_gpt2_runtime.py R5X/tools/browser_gpt2_runtime.py
--- R4M/tools7/browser_gpt2_runtime.py	2026-09-21 01:39:46
+++ R5X/tools/browser_gpt2_runtime.py	2026-09-24 16:21:15
@@ -23,6 +23,7 @@
 import r2c_hoist as r2c
 import r2g_has_scope as r2g
 import r3h_blockflow_max as r3h
+import r5e_dead_weight as r5e
 import numpy as np
 from analyze_full_gpt2 import MODEL_PATH, SafeTensors
 from browser_gpt2_core import compile_core
@@ -460,7 +461,7 @@
         model, tagged = f5.tag_inline_readers(
             model, "var(--epoch)", "epoch-reader", skip_class="pass-reader"
         )
-        if tagged != 3:
+        if tagged != (3 if r5e.KEEP_DIAG else 2):  # R5E: #core-probe's epoch twin
             raise ValueError(f"Unexpected inline epoch readers in model: {tagged}")
     font_html, font_css, font_count = font_barrier(css, directory)
     css += font_css
@@ -574,13 +575,17 @@
         + controls
         + font_html
         + model
-        + f'<i id="core-epoch-observer" style="position:fixed;top:-30px;width:anchor-size(--block-{blocks - 1}-probe-epoch width,0px);height:1px"></i>'
+        + (f'<i id="core-epoch-observer" style="position:fixed;top:-30px;width:anchor-size(--block-{blocks - 1}-probe-epoch width,0px);height:1px"></i>' if r5e.KEEP_DIAG else '')  # R5E
         + "</body></html>"
     )
     r2g_stats = None
     if r2g.SCOPED_HAS:
         # R2G/R3F: fixed-depth `:has()` arguments for every handshake rule (chains verified against the page).
         css, r2g_stats = r2g.scope_has_arguments(css, page, capacity)
+    r5e_stats = None
+    if r5e.LEAN_WALLS:
+        # R5E: shrink the two inheritance walls to the properties that can be non-initial there
+        css, r5e_stats = r5e.lean_walls(css, page)
     (directory / "runtime.css").write_text(css)
     (directory / "index.html").write_text(page)
     metadata.update(
@@ -600,6 +605,8 @@
         detachedOutput=detached_output,
         **r2d.manifest(),
         r3hBlockflowMax=r3h.BLOCKFLOW_MAX,
+        **r5e.manifest(),
+        r5eLeanWallStats=r5e_stats,
         headEpochTransport="separate geometry" if capacity > 8 else "packed four bits",
         fontBackend=font_backend,
         teacherForcedInputs=teacher_forced_tokens[:capacity]
diff -ruN -x __pycache__ R4M/tools7/r3r_fold_hop.py R5X/tools/r3r_fold_hop.py
--- R4M/tools7/r3r_fold_hop.py	2026-09-21 01:39:46
+++ R5X/tools/r3r_fold_hop.py	2026-09-24 16:21:15
@@ -47,6 +47,7 @@
 import os
 
 import r4t_consumer_chunk as r4t
+import r5e_dead_weight as r5e
 from build_pretrained_gpt2 import css_number as num
 
 
@@ -133,7 +134,7 @@
             ids = range(k * r4t.CHUNK, min(width, (k + 1) * r4t.CHUNK))
             # --lp-* are registered inherits:false by the core's scoped_state and forwarded with `inherit` at .loop-input
             # (one level): every chunk element must forward the earlier chunks' values so the innermost one holds all of them.
-            forward = "".join(f";--lp-{i}:inherit" for i in range(0, k * r4t.CHUNK))
+            forward = "" if r5e.LP_INHERIT else "".join(f";--lp-{i}:inherit" for i in range(0, k * r4t.CHUNK))  # R5E
             css += (
                 f".{cls}{{animation-name:"
                 + ",".join(f"lpk{i}" for i in ids)
diff -ruN -x __pycache__ R4M/tools7/r5e_dead_weight.py R5X/tools/r5e_dead_weight.py
--- R4M/tools7/r5e_dead_weight.py	1969-12-31 16:00:00
+++ R5X/tools/r5e_dead_weight.py	2026-09-24 16:21:15
@@ -0,0 +1,278 @@
+"""R5E (2026-09-24): remove the declarations and elements that every style pass
+re-applies without carrying a live value (work/2026-09-19/R5E.md).
+
+Blink re-applies EVERY declaration of a dirtied element (audit SYNTHESIS §8.1:
+4.45 us/element + 36.5 ns/byte for var() declarations, 0.72 us per short literal
+declaration). The combined7 census (R5A/census.md, R5E.md §1) found four
+populations that are restyled per layer pass or per token but carry no value:
+
+  R5E_LEAN_WALLS=0       keep the two inheritance walls as emitted: `.core-reset`
+                         (16,156 `--p:initial`, 309 KB, restyled every layer pass)
+                         and `.head-isolation` (24,105 `--p:initial`, 463 KB, ~5
+                         restyles per token). ON: each wall keeps only the
+                         registered properties that some ancestor-or-self of the
+                         wall element declares (CSS rule whose rightmost compound
+                         can match it, inline style, or keyframes it animates);
+                         every other property is provably at its initial value on
+                         the wall's parent, so `initial` there is a no-op. Derived
+                         mechanically from the assembled page + sheet at build
+                         time (lean_walls()); identical computed values and
+                         identical dirtying (the wall still pins every property
+                         that can change above it).
+  R5E_LP_INHERIT=0       keep R3R/F5's private `--lp-*` (proj readback numbers,
+                         inherits:false) with 768 `--lp-i:inherit` forwards on
+                         `.loop-input` plus R4T's 4,224 forwards on the nested
+                         `.loop-reader-cK` chunks. ON: `--lp-*` stay registered
+                         inherits:true (as r3r_fold_hop registers them) and the
+                         forwards disappear. Same values at `.loop-input`; the
+                         subtree they now inherit into is exactly the subtree the
+                         decoded `--loop-in-*` (inherits:true) already dirty in the
+                         same pass.
+  R5E_DROP_DEAD_LISTS=0  keep `.fvs-query{--fvs-all-fields:…}` and the 8
+                         `--fvs-retained-S` lists. ON (F5_BANK_LITERAL_LISTS only):
+                         not emitted — the bank rules inline the literal lists and
+                         nothing references these unregistered properties.
+  R5E_KEEP_DIAG=1        keep the three geometry readback probe pairs
+                         (`#core-probe`, `#block-11-probe`, `#reused-probe`: 15–19 KB
+                         inline width calcs over 768 var() each, position:fixed,
+                         plus their `*-epoch` twins) and `#core-epoch-observer`.
+                         Default OFF: removed. `#reused-probe` sits in the proj
+                         stage and is restyled + laid out every layer; the others
+                         per token. The verifier reads computed styles of
+                         `#core-result`, `.head-input-bank`, `.fvs-bank-L` and
+                         `.token-slot-N`, none of which change.
+"""
+
+import os
+import re
+from html.parser import HTMLParser
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+LEAN_WALLS = flag("R5E_LEAN_WALLS")
+LP_INHERIT = flag("R5E_LP_INHERIT")
+DROP_DEAD_LISTS = flag("R5E_DROP_DEAD_LISTS")
+KEEP_DIAG = flag("R5E_KEEP_DIAG", "0")
+
+WALLS = (".core-reset", ".head-isolation")
+
+
+def manifest():
+    return {
+        "r5eLeanWalls": LEAN_WALLS,
+        "r5eLpInherit": LP_INHERIT,
+        "r5eDropDeadLists": DROP_DEAD_LISTS,
+        "r5eKeepDiag": KEEP_DIAG,
+    }
+
+
+# ---------------------------------------------------------------- DOM ancestry
+_VOID = {"meta", "link", "input", "br", "img", "hr", "set", "animate"}
+
+
+class _Dom(HTMLParser):
+    def __init__(self):
+        super().__init__(convert_charrefs=False)
+        self.stack, self.nodes = [], []  # node = (tag, classes, id, style, parent)
+
+    def handle_starttag(self, tag, attrs):
+        a = dict(attrs)
+        node = (tag, frozenset((a.get("class") or "").split()), a.get("id"), a.get("style") or "",
+                self.stack[-1] if self.stack else -1)
+        self.nodes.append(node)
+        if tag not in _VOID:
+            self.stack.append(len(self.nodes) - 1)
+
+    def handle_startendtag(self, tag, attrs):
+        self.handle_starttag(tag, attrs)
+        if tag not in _VOID:
+            self.stack.pop()
+
+    def handle_endtag(self, tag):
+        for i in range(len(self.stack) - 1, -1, -1):
+            if self.nodes[self.stack[i]][0] == tag:
+                del self.stack[i:]
+                break
+
+
+def _ancestors_or_self(nodes, index):
+    out = []
+    while index >= 0:
+        out.append(nodes[index])
+        index = nodes[index][4]
+    return out
+
+
+# ---------------------------------------------------------------- CSS scanning
+def _rules(css):
+    """Yield (prelude, body, parents) for every block, nested blocks included; body = the
+    declarations before any nested '{'; parents = tuple of enclosing preludes (outermost first)."""
+    i, n, start = 0, len(css), 0
+    stack = []
+    while i < n:
+        c = css[i]
+        if c == '"':
+            j = css.find('"', i + 1)
+            while j > 0 and css[j - 1] == "\\":
+                j = css.find('"', j + 1)
+            i = j + 1
+            continue
+        if c == "{":
+            stack.append((css[start:i].strip(), i + 1))
+            i += 1
+            start = i
+            continue
+        if c == "}":
+            pre, bstart = stack.pop()
+            body = css[bstart:i]
+            k = body.find("{")
+            yield pre, (body if k < 0 else body[:k]), tuple(p for p, _ in stack)
+            i += 1
+            start = i
+            continue
+        if c == ";" and not stack:
+            i += 1
+            start = i
+            continue
+        i += 1
+
+
+def _split_top(text, sep):
+    parts, depth, cur = [], 0, []
+    for ch in text:
+        if ch in "([":
+            depth += 1
+        elif ch in ")]":
+            depth -= 1
+        if ch == sep and depth == 0:
+            parts.append("".join(cur))
+            cur = []
+        else:
+            cur.append(ch)
+    parts.append("".join(cur))
+    return parts
+
+
+def _rightmost_compound(selector):
+    depth = 0
+    for k in range(len(selector) - 1, -1, -1):
+        ch = selector[k]
+        if ch in ")]":
+            depth += 1
+        elif ch in "([":
+            depth -= 1
+        elif depth == 0 and ch in " >+~":
+            return selector[k + 1:]
+    return selector
+
+
+_CLASS = re.compile(r"\.([\w-]+)")
+_ID = re.compile(r"#([\w-]+)")
+_TYPE = re.compile(r"^([a-zA-Z][\w-]*|\*)")
+
+
+def _compound_matches(compound, node):
+    """Could `compound` match `node`? Pseudo-classes are ignored (superset = safe)."""
+    # strip functional pseudo-class arguments so their inner selectors do not count as constraints
+    flat, depth, out = compound, 0, []
+    for ch in flat:
+        if ch == "(":
+            depth += 1
+            continue
+        if ch == ")":
+            depth -= 1
+            continue
+        if depth == 0:
+            out.append(ch)
+    flat = "".join(out)
+    tag, classes, ident = node[0], node[1], node[2]
+    m = _TYPE.match(flat)
+    if m and m.group(1) != "*" and m.group(1).lower() != tag:
+        return False
+    for c in _CLASS.findall(flat):
+        if c not in classes:
+            return False
+    for i in _ID.findall(flat):
+        if i != ident:
+            return False
+    return True
+
+
+_DECL_PROP = re.compile(r"(?:^|;)\s*(--[\w-]+)\s*:")
+_ANIM_NAMES = re.compile(r"(?:^|;)\s*animation(?:-name)?\s*:([^;]*)")
+_IDENT = re.compile(r"[A-Za-z_-][\w-]*")
+
+
+def _declared_props(body):
+    return set(_DECL_PROP.findall(body))
+
+
+def _animation_names(body):
+    names = set()
+    for value in _ANIM_NAMES.findall(body):
+        for part in value.split(","):
+            for tok in _IDENT.findall(part):
+                names.add(tok)
+    return names
+
+
+def lean_walls(css, page, walls=WALLS):
+    """Shrink each wall rule to the properties that can be non-initial on the wall element.
+
+    Returns (css, stats). A property is kept when an ancestor-or-self of the wall element
+    (a) declares it in a rule whose rightmost compound can match that element,
+    (b) declares it in its inline style, or
+    (c) animates it (keyframes referenced by an animation on such a rule).
+    """
+    dom = _Dom()
+    dom.feed(page)
+    nodes = dom.nodes
+    keyframes = {}
+    matched_rules = []
+    for pre, body, parents in _rules(css):
+        if parents and parents[-1].startswith("@keyframes"):
+            keyframes.setdefault(parents[-1].split()[1], set()).update(_declared_props(body))
+            continue
+        if pre.startswith("@"):
+            continue
+        matched_rules.append((pre, body))
+    stats = {}
+    for wall in walls:
+        cls = wall.lstrip(".")
+        targets = [i for i, n in enumerate(nodes) if cls in n[1]]
+        if len(targets) != 1:
+            raise ValueError(f"R5E: expected one {wall} element, found {len(targets)}")
+        chain = _ancestors_or_self(nodes, targets[0])
+        live, anims = set(), set()
+        for node in chain:
+            live |= _declared_props(node[3])
+        for pre, body in matched_rules:
+            if pre == wall:
+                continue  # the wall rule itself
+            for selector in _split_top(pre, ","):
+                comp = _rightmost_compound(selector.strip())
+                if any(_compound_matches(comp, node) for node in chain):
+                    live |= _declared_props(body)
+                    anims |= _animation_names(body)
+                    break
+        for name in anims:
+            live |= keyframes.get(name, set())
+        start = css.find(wall + "{")
+        if start < 0 or css.find(wall + "{", start + 1) >= 0:
+            raise ValueError(f"R5E: expected exactly one {wall} rule")
+        end = css.index("}", start)
+        decls = css[start + len(wall) + 1:end].split(";")
+        kept, dropped = [], 0
+        for d in decls:
+            name = d.split(":", 1)[0].strip()
+            if d.strip().endswith(":initial") and name.startswith("--") and name not in live:
+                dropped += 1
+                continue
+            kept.append(d)
+        css = css[:start] + wall + "{" + ";".join(kept) + "}" + css[end + 1:]
+        stats[wall] = {"kept": len([d for d in kept if d.strip().endswith(":initial")]),
+                       "dropped": dropped, "liveOnAncestors": len(live), "ancestors": len(chain) - 1}
+    return css, stats
diff -ruN -x __pycache__ R4M/tools7/r5h_ch_scores.py R5X/tools/r5h_ch_scores.py
--- R4M/tools7/r5h_ch_scores.py	1969-12-31 16:00:00
+++ R5X/tools/r5h_ch_scores.py	2026-09-24 16:21:15
@@ -0,0 +1,149 @@
+"""R5H (2026-09-24): the attention-score hop read back with `ch` font-metric units (R4X §6.1).
+
+Flag (default ON): R5H_CH_SCORES=0 restores the R4S / view-timeline score transport. When ON
+the flag forces R4S_SMALL_HOPS off (both replace the same hop).
+
+Mechanism (work/2026-09-19/R5H.md). Today every (head, slot) score is the advance of the
+`dot` glyph of a bilinear `FvsDot{head}` font instance (font-variation-settings = the slot's
+latched K list + the live Q list): the glyph is shaped, its `max-content` width is encoded
+into a carrier width, and the width is transported back into a `<number>` either through a
+view-timeline (combined4) or through an anchor -> size-container chain (R4S). Blink exposes
+the advance of glyph U+0030 of an element's *primary font instance* (HVAR applied) directly
+to style as the `ch` unit, and a custom property on the element resolves `ch` against the
+element's OWN font (E1 #70/#73, R4X §1/§5 arm M). So:
+
+  * fonts: the 12 F4 dot fonts get one extra cmap entry, U+0030 -> `dot` (every other table
+    byte-identical; asserted at build), written to R5H/assets-r5h/;
+  * per (head, slot) an EMPTY `display:block` element carries today's `font` +
+    `font-variation-settings` declarations and
+    `--fs-H-S: calc((1ch / 1px - base_px) * var(--fqs-H) * var(--fr-ks-S-H) * 1/(8*coef*unit))`
+    (the width decode minus the 262144 / 128 carrier encoding), registered `<number>`
+    `inherits:true`;
+  * per head the `capacity` slot elements nest (chain) and the chain bottom
+    `.fvs-score-reader.fvs-sr-H` hosts head H's softmax declarations and its 64 V rows.
+    The 12 chains sit inside the ctx scroller's `.track` (the rows are position:absolute with
+    the track as containing block, so their geometry is unchanged); depth grows by
+    capacity + 1 instead of R4S's 12*capacity/2 containers.
+
+No shaping, no layout, no containers, no timelines, no gate: the scores, the softmax and the
+V-row widths are plain style dependencies of the qkv readback pass in which `.fvs-query` is
+restyled, and the V rows are laid out in that pass's layout (ctx readback = next pass), i.e.
+5 passes / 2.5 frames per layer like R4S, with RecalcStyleCount flat in the filled positions
+(no interleaved container recalcs; R4M §4.1's 70.8*k penalty disappears).
+"""
+
+import os
+from pathlib import Path
+
+import r4s_small_hops as r4s
+from fontTools.ttLib import TTFont
+
+
+def flag(name, default="1"):
+    return os.environ.get(name, default) not in ("0", "false", "no", "off")
+
+
+CH_SCORES = flag("R5H_CH_SCORES")
+if CH_SCORES:
+    # R5H replaces R4S's chain for the same hop; the two are mutually exclusive.
+    r4s.SMALL_HOPS = False
+
+ASSETS = Path(__file__).resolve().parents[1] / "assets-r5h" / "font-vector-operators-r5h"
+ZERO = 0x30
+BOTTOM_CLASS = "fvs-score-reader"
+
+
+def no_score_hop():
+    """True when the score hop has neither scroller, timelines, receipt nor gate (R4S or R5H)."""
+    return CH_SCORES or r4s.SMALL_HOPS
+
+
+def head_class(head):
+    return f"fvs-sr-{head}"
+
+
+def _table_bytes(font):
+    return {tag: font.getTableData(tag) for tag in font.keys() if tag != "GlyphOrder"}
+
+
+def ch_dot_font(source):
+    """`source` dot font + cmap U+0030 -> the score glyph; every other table byte-identical.
+
+    Built once into ASSETS (name = <source stem>-r5h.woff2) and re-verified on every call.
+    """
+    source = Path(source)
+    ASSETS.mkdir(parents=True, exist_ok=True)
+    target = ASSETS / f"{source.stem}-r5h.woff2"
+    original = TTFont(source, recalcTimestamp=False)
+    unicode_tables = [t for t in original["cmap"].tables if t.isUnicode()]
+    if not unicode_tables:
+        raise ValueError(f"R5H: {source} has no unicode cmap subtable")
+    glyphs = {g for t in unicode_tables for g in t.cmap.values()}
+    if len(glyphs) != 1:
+        raise ValueError(f"R5H: expected exactly one mapped glyph in {source}, found {sorted(glyphs)}")
+    (score_glyph,) = glyphs
+    if any(ZERO in t.cmap for t in unicode_tables):
+        raise ValueError(f"R5H: {source} already maps U+0030")
+    if not target.exists():
+        font = TTFont(source, recalcTimestamp=False)
+        for table in font["cmap"].tables:
+            if table.isUnicode():
+                table.cmap[ZERO] = score_glyph
+        font.flavor = "woff2"
+        staging = target.with_suffix(".tmp.woff2")
+        font.save(staging)
+        staging.replace(target)
+    # verify (always): only cmap differs (+ head.checkSumAdjustment); cmap = original + {U+0030: glyph}
+    built = TTFont(target, recalcTimestamp=False)
+    before, after = _table_bytes(original), _table_bytes(built)
+    if set(before) != set(after):
+        raise ValueError(f"R5H: table set changed for {source}: {sorted(set(before) ^ set(after))}")
+    for tag in before:
+        if tag == "cmap":
+            continue
+        a, b = before[tag], after[tag]
+        if tag == "head":
+            # bytes 8..12 = checkSumAdjustment (recomputed on save); everything else must match
+            a, b = a[:8] + a[12:], b[:8] + b[12:]
+        if a != b:
+            raise ValueError(f"R5H: table {tag} changed for {source}")
+    for t_old, t_new in zip(original["cmap"].tables, built["cmap"].tables):
+        if (t_old.format, t_old.platformID, t_old.platEncID) != (t_new.format, t_new.platformID, t_new.platEncID):
+            raise ValueError(f"R5H: cmap subtable layout changed for {source}")
+        expected = dict(t_old.cmap)
+        if t_old.isUnicode():
+            expected[ZERO] = score_glyph
+        if dict(t_new.cmap) != expected:
+            raise ValueError(f"R5H: cmap subtable {t_new.format}/{t_new.platformID}/{t_new.platEncID} wrong for {source}")
+    if built.getGlyphOrder() != original.getGlyphOrder():
+        raise ValueError(f"R5H: glyph order changed for {source}")
+    return target
+
+
+def slot_rule(head, slot, size, family, fr_k, base_px, kconst):
+    """The (head, slot) score element: today's font declarations + the ch decode."""
+    return (
+        f".fvs-score-{head}-{slot}{{display:block;font:{size}px {family};line-height:1;font-kerning:none;"
+        f"font-variation-settings:var({fr_k}),var(--fvs-query-{head});"
+        f"{r4s.field(head, slot)}:calc((1ch / 1px - {base_px:.12g}) * var(--fqs-{head}) * var(--fr-ks-{slot}-{head}) * {kconst:.12g})}}"
+    )
+
+
+def chain_open(head, capacity):
+    """Nested slot elements of one head, then the head's softmax bottom (caller emits the rows)."""
+    return "".join(f'<div class="fvs-score-{head}-{slot}">' for slot in range(capacity)) + (
+        f'<div class="{BOTTOM_CLASS} {head_class(head)}">'
+    )
+
+
+def chain_close(capacity):
+    return "</div>" * (capacity + 1)
+
+
+def manifest(capacity):
+    return {
+        "r5hChScores": CH_SCORES,
+        "r5hScoreElements": 12 * capacity if CH_SCORES else 0,
+        "r5hScoreChains": 12 if CH_SCORES else 0,
+        "r5hScoreChainDepth": capacity + 1 if CH_SCORES else 0,
+    }
```
