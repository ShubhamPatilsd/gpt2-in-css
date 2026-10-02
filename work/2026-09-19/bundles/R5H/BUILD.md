# bundles/R5H — combined7 recipe + R5H `ch` score readback (`R5H_CH_SCORES=1`, forces `R4S_SMALL_HOPS` off), capacity 8, `--value-layout runs`

Built by R5H on 2026-09-24 12:38 (`work/2026-09-19/R5H/compile.sh bundles/R5H 8 12`; tools copy `work/2026-09-19/R5H/tools` = `R4M/tools7` + `r5h_ch_scores.py` + hooks
in `browser_gpt2_font_vector_cache.py` / `browser_gpt2_reused_adapter.py`; same symlinks as R4M (assets → F4/assets, data, experiments, global-projection-assets) plus
`R5H/assets-r5h/font-vector-operators-r5h/` = the 12 F4 dot fonts with cmap U+0030 → `dot`, every other table byte-identical, asserted at build). Reference for pairs: `bundles/combined7 (R4S chain)`.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R5H
# combined7's exports (bundles/combined7/BUILD.md: F4_*, R2C_*, R2F_*, R2D_*, R2G_*, R3R_*, R3H_*, R4D_*, R4T_CONSUMER_CHUNK=64) plus:
export R5H_CH_SCORES=1        # default; forces R4S_SMALL_HOPS=0 at import (r5h_ch_scores.py)
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/R5H
```

## Flag

| flag | default | owner | effect |
|---|---|---|---|
| `R5H_CH_SCORES` | 1 (`0` = combined7's code path: R4S chain if `R4S_SMALL_HOPS=1`, else the view-timeline score hop) | R5H | the 12·capacity `.fvs-score-H-S` score carriers (shaped glyph + `calc-size` width + view-timeline / anchor chain) become EMPTY `display:block` elements with the same `font`/`font-variation-settings` and `--fs-H-S:calc((1ch / 1px - base_px) * var(--fqs-H) * var(--fr-ks-S-H) * 1/(8·coef·unit))` (registered `<number>`, `inherits:true`); per head the capacity slot elements nest inside the ctx scroller's `.track` and the chain bottom `.fvs-score-reader.fvs-sr-H` carries head H's softmax (`--fm/--fe/--fd/--fb/--fw`, declarations byte-identical to the old single-element rule, split by head) and hosts head H's 64 V rows (position:absolute against `.track`, geometry unchanged). No score scroller, timelines, keyframes, stamp, receipt, gate, anchors or containers. `@font-face FvsDotH` → `R5H/assets-r5h/…/dot-hH-…-f4-r5h.woff2`. Manifest `r5hChScores`. |

## Offline verification (R5H.md §4; logs in `R5H/logs/`)

- **`R5H_CH_SCORES=0` reproduces `bundles/combined7` byte-for-byte** (`R5H/scratch/off-8`: index.html identical, runtime.css identical after URL-depth normalisation, manifest +`r5hChScores:false`, witnesses 283/283).
- `R5H/offline_check.py R5H combined7` → **RESULT: PASS** (`R5H/logs/offline_check-R5H-vs-combined7.log`): rule diff confined to the intended families with exact counts; all 96 slot rules = the carrier's font declarations + the decode with the carrier's base/k constants; per-head softmax/weight declarations == the reference's single rule; 12 chains `.track > .fvs-score-H-0 > … > .fvs-score-H-7 > .fvs-score-reader.fvs-sr-H` each hosting exactly its head's 64 rows; no leftovers of the old hop; 12 R5H dot faces, value faces unchanged; witnesses identical except the 12 dot entries (same advance 29984 / upem 1000; the witness now renders U+0030).
- `R5H/font_check.py` → PASS: for each of the 12 dot fonts only `cmap` differs (head: checksum only), cmap = source + {U+0030: dot}, HVAR-instanced advances equal at random 128-axis locations.
- NumPy ids (R5H tools): 8-token `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected; 32-token prompt 40 = `R4P/reference_ids_32_40.json` (32/32). The reference does not model the transport (as for R4S).
- `tools/launch_browser_gpt2.py --check`: `runtimeJavaScript: false`.
- Sizes: runtime.css  39969975 B, index.html  6511183 B.

## Chrome

See `R5H.md` §5 (smoke trio, 8-token correctness, 32-token prompt-40 run). READY is created only after the Chrome correctness run.

## `diff -ruN -x __pycache__ work/2026-09-19/R4M/tools7 work/2026-09-19/R5H/tools` (     401 lines; also at `R5H/tools-vs-tools7.diff`; combined7's own diff vs R3M is in `bundles/combined7/BUILD.md`)

```diff
diff -ruN -x _ R4M/tools7/browser_gpt2_font_vector_cache.py R5H/tools/browser_gpt2_font_vector_cache.py
--- R4M/tools7/browser_gpt2_font_vector_cache.py	2026-09-21 01:39:46
+++ R5H/tools/browser_gpt2_font_vector_cache.py	2026-09-24 12:32:24
@@ -16,6 +16,7 @@
 import r4d_flags as r4d
 import r2c_hoist as r2c
 import r4s_small_hops as r4s
+import r5h_ch_scores as r5h  # R5H: forces r4s.SMALL_HOPS off when R5H_CH_SCORES is on
 import numpy as np
 from build_bilinear_projected_kv_qk import CODEPOINT_BASE, build_head_font
 from build_gpt2_block_css import UNITS_PER_EM
@@ -179,6 +180,8 @@
         raise ValueError("Early value preparation requires fixed font widths")
     if prewarm_values and r4s.SMALL_HOPS:
         raise ValueError("R4S: the score chain has no score gate to prewarm against")
+    if prewarm_values and r5h.CH_SCORES:
+        raise ValueError("R5H: the ch score readback has no score gate to prewarm against")
     operators = fonts()
     packed = f4.PACKED_BANKS
     if packed and value_layout not in ("runs", "widths"):
@@ -353,11 +356,17 @@
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
@@ -366,9 +375,10 @@
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
@@ -379,12 +389,21 @@
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
@@ -400,7 +419,10 @@
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
@@ -431,9 +453,10 @@
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
@@ -467,7 +490,13 @@
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
@@ -489,11 +518,18 @@
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
@@ -544,9 +580,12 @@
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
@@ -565,11 +604,19 @@
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
@@ -591,7 +638,10 @@
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
@@ -616,7 +666,7 @@
     body = '<div class="fvs-query">' + body + "</div>"
     # R4M merge: R4D_GATE_SCORES is off under R4S (no score scroller; display:none on an
     # anchor row would invalidate the chain's anchor-size()); --fv-S masking is unchanged.
-    gate_scores = r4d.GATE_SCORES and sequential and not r4s.SMALL_HOPS
+    gate_scores = r4d.GATE_SCORES and sequential and not r5h.no_score_hop()
     if hide_unfilled or gate_scores:
         # R4D: per-slot filled flag on the fvscache container (same expression
         # as --fv-S on the score reader, which is inherits:false and therefore
@@ -639,7 +689,7 @@
         for slot in range(capacity):
             selectors = ",".join(f".fvs-score-source .fvs-score-{head}-{slot}" for head in range(HEADS))
             css += f"@container fvscache style(--fvq-{slot}:0){{{selectors}{{display:none}}}}"
-    if not r4s.SMALL_HOPS:  # R4S: no score timelines
+    if not r5h.no_score_hop():  # R4S / R5H: no score timelines
         css += "html{timeline-scope:" + ",".join(timelines + ["--fvs-score-stamp"]) + "}"
     return (
         body,
@@ -661,6 +711,7 @@
             "r4dGateScores": gate_scores,
             "prewarmValues": prewarm_values,
             **r4s.manifest(capacity),
+            **r5h.manifest(capacity),
             "attentionMask": "full causal"
             if capacity == positions
             else "initial sinks plus rolling recent context",
diff -ruN -x _ R4M/tools7/browser_gpt2_reused_adapter.py R5H/tools/browser_gpt2_reused_adapter.py
--- R4M/tools7/browser_gpt2_reused_adapter.py	2026-09-21 01:39:46
+++ R5H/tools/browser_gpt2_reused_adapter.py	2026-09-24 12:27:34
@@ -15,6 +15,7 @@
 import r2f_lean_handshake as r2f
 import r3r_fold_hop as r3r
 import r4s_small_hops as r4s
+import r5h_ch_scores as r5h  # R5H: forces r4s.SMALL_HOPS off when R5H_CH_SCORES is on
 import r4d_flags as r4d
 import r4t_consumer_chunk as r4t
 
@@ -141,7 +142,7 @@
         # and stamp the current pass directly onto every reader.
         receipts = [
             f".shared-{kind}-receipt" for kind in ("qkv", "attn", "fc", "proj")
-        ] + [".cache-bridge-receipt"] + ([] if r4s.SMALL_HOPS else [".fvs-score-receipt"])
+        ] + [".cache-bridge-receipt"] + ([] if r5h.no_score_hop() else [".fvs-score-receipt"])
         pass_readers = ",".join(
             [
                 ".loop-input",
@@ -170,8 +171,8 @@
         body, tagged_position = f5.tag_inline_readers(
             body, "var(--position)", "pass-reader"
         )
-        # R4S: the score stamp marker (one inline var(--epoch) reader) no longer exists
-        if tagged != (6 if r4s.SMALL_HOPS else 7) or tagged_position != 2:
+        # R4S / R5H: the score stamp marker (one inline var(--epoch) reader) no longer exists
+        if tagged != (6 if r5h.no_score_hop() else 7) or tagged_position != 2:
             raise ValueError(
                 f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
             )
@@ -239,6 +240,7 @@
         "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
         "r3rFoldHop": r3r.FOLD_HOP,
         "r4sSmallHops": r4s.SMALL_HOPS and codec == "font-vector",
+        "r5hChScores": r5h.CH_SCORES and codec == "font-vector",
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
diff -ruN -x _ R4M/tools7/r5h_ch_scores.py R5H/tools/r5h_ch_scores.py
--- R4M/tools7/r5h_ch_scores.py	1969-12-31 16:00:00
+++ R5H/tools/r5h_ch_scores.py	2026-09-24 12:26:27
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
