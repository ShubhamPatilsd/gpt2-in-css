# bundles/combined6 — combined4 (R3M) + R4S small-hop score chain + R4D capacity fixes (capacity 8, default `runs` value layout)

Built by R4M on 2026-09-21 00:47 (`work/2026-09-19/R4M/compile.sh tools bundles/combined6 8`, 10 s; fonts and F2's projection shards reused via the
`experiments` / `data` / `assets -> ../F4/assets` / `global-projection-assets -> ../F2/…` symlinks beside the tools copy — no new font files, 283 faces as combined4).
Recipe = `bundles/combined4/BUILD.md` with the merged tools copy `work/2026-09-19/R4M/tools`. **R4T is NOT included** (see the flag table). This is the
capacity-8 bundle for B5's paired bench vs combined4; the demo candidate is `bundles/combined6-c32`.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4M
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R2G_SCOPED_HAS=1 R3R_FOLD_HOP=1 R3H_BLOCKFLOW_MAX=1
export R4S_SMALL_HOPS=1
export R4D_EMPTY_UNFILLED=1 R4D_LEAN_LATCH=1 R4D_UNPACK_V=1 R4D_HIDE_UNFILLED=1 R4D_GATE_SCORES=0
# (R4T_CONSUMER_CHUNK not set: R4T is not part of this bundle)
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 8 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout runs --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined6
```

## Flags (environment; `0` reverts that change; combined4's flags unchanged, see `bundles/combined4/BUILD.md`)

| flag | default | owner | effect |
|---|---|---|---|
| `R4S_SMALL_HOPS` | 1 | R4S | the 96·(capacity/8) attention-score glyphs become in-flow anchor rows of a `position:fixed` stage; `12·capacity/2` nested `position:fixed; container-type:size` containers `#fvs-sc0..` take `width/height:anchor-size(--fsa-H-S width)` and publish `--fs-H-S:calc((100cqw/1px − 262144)/128)` (cqh for the second); no score scroller / 97 view-timelines / receipt / gate / stamp; the ctx readback becomes the frame's second pass (6 → 5 passes, 3.0 → 2.5 frames/layer; `R4S.md`). Manifest `r4sSmallHops`, `r4sScoreChainContainers`, `r4sScoreAnchors`. |
| `R4D_EMPTY_UNFILLED` | 1 | R4D | KV `@property` initial values = one zero axis instead of the 768-axis zero list (unfilled slots substitute 12 B, not ≈7.7 KB). Exact (fvar defaults are 0). |
| `R4D_LEAN_LATCH` | 1 | R4D | per-write-slot `.fvs-bank{transition-property}` lists of slots 0..W only (full causal window); write rule lists 0..W−1. |
| `R4D_UNPACK_V` | 1 | R4D | 12 per-head 64-axis V lists per slot (`--fc/--fr-v-S-H`) instead of one packed 768-axis list. Exact. |
| `R4D_HIDE_UNFILLED` | 1 | R4D | unfilled slots' V glyph leaves `display:none` via `@container fvscache style(--fvq-S:0)`; row widths subtract `var(--fvs-nbase)` = (W+1)·base. Residue ≤ (cap−1)/64 px of snapped base advance (`R4D.md`). |
| `R4D_GATE_SCORES` | 0 | R4D | (opt-in) `display:none` unfilled score carriers. **R4M merge: additionally forced off under `R4S_SMALL_HOPS`** (its selector targets the score scroller R4S removes; `display:none` on an anchor row would invalidate the chain's `anchor-size()`); manifest `r4dGateScores` reflects the effective value. |
| `R4T_CONSUMER_CHUNK` | — | R4T | **NOT included** (coordinator 00:46: R4T's 2-layer smoke failed correctness, `[44873, 9890]` vs `[11, 3387]`; if R4T becomes READY it becomes combined7). The merge script (`R4M/merge.sh <tools> <R4T diff> 2`) already applies R4T's diff with one exact-string import fix (`R4M/apply_r4t_import.py`); the 3-way preview built and its flag-off output was byte-identical (`R4M.log.md` 00:17). |

## Merge (`work/2026-09-19/R4M.md` §1; `R4M/merge.sh`)

`cp -R R3M/tools R4M/tools`; `patch -p1 -F3 -N < R4S/tools-vs-R3M.diff` (browser_gpt2_font_vector_cache.py, browser_gpt2_reused_adapter.py, + r4s_small_hops.py): 0 rejects;
`patch -p2 -F3 -N < R4D/tools-vs-R3M.diff` (same two files; r4d_flags.py copied from R4D/tools — R4D's diff is `diff -ru` without `-N`): **2 rejects, both adjacent-line
overlaps with R4S, resolved by `R4M/apply_conflicts.py` (exact-string edits)**: (1) the adapter import line (`import r4d_flags as r4d` after `import r4s_small_hops as r4s`);
(2) R4D's hide-unfilled / gate-scores block, anchored on the `html{timeline-scope}` line that R4S wrapped in `if not r4s.SMALL_HOPS:` — inserted before R4S's guard, with
`gate_scores = r4d.GATE_SCORES and sequential and not r4s.SMALL_HOPS` (see the flag table). Both diffs cmp-identical to the owners' BUILD.md diffs at merge time
(R4D's re-diffed against R4D/tools at 00:31); new modules cmp-identical to the owners' copies. Semantic interaction checked: R4D's `display:none` container rules
address the named container `fvscache` (`.fvs-query`), so the unnamed `.fvs-sc` size containers R4S inserts above the V rows are skipped; `--fvs-nbase` / `--fs-*` inherit
through the chain; R4D's per-head V leaf lists and R4S's chain touch disjoint elements.

## Offline verification (reference builds in `work/2026-09-19/R4M/scratch/` from the same tools; `runtime.css` compared after normalising the relative `url("../…")` depth; `index.html` byte-for-byte; `R4M/compare_bundles.py`)

- **All new flags OFF (`scratch/p8-alloff`) vs `bundles/combined4`: index.html byte-identical, runtime.css identical (URL-normalised), manifest differs only by the 6 new keys (false/null).**
- Union checks: only-R4S (`scratch/p8-noR4D`, R4D off) reproduces `bundles/R4S`; only-R4D (`scratch/p8-noR4S`, R4S off) reproduces `bundles/combined5` (css + index.html identical, manifest +1/+5 keys). This bundle is the URL-normalised twin of `R4M/scratch/p8` (0 manifest differences).
- R4S: `R4S/offline_check.py p8 p8-noR4S 8` → `RESULT: PASS` — +96 `--fs` registrations inherits:true / −96 inherits:false, −98 progress/stamp/ready registrations, −194 score keyframes, −scroller/−reader animations/−receipt/−gate, +4 structure, +48 container-size rules, +48 publishers, html scope −97 names, pass-reader/epoch lists −`.fvs-score-receipt`; elements 67,445 vs 67,401 (+44), max depth 94 (reader 89; cap 512).
- R4D: `R4D/rule_diff.py` (flag-off reference vs bundle): differing leaf-rule families = exactly R4D's BUILD.md list (KV `@property` initials, `--fc/--fr-v-S-H` registrations, `.fvs-v-H-S` leaves, bank write rules, per-write-slot `.fvs-bank` lists, `.fvs-query` lists + `--fvq-S` flags, 8 `display:none` container rules, `@property --fvs-nbase`, `.head-isolation` wall). Interaction grep: 8 fvq rules, 0 `.fvs-score-source`, 768 `var(--fvs-nbase)` rows, 48 chain containers / 96 anchors, manifest `r4dGateScores:false`.
- `font-witnesses.json`: 283/283 identical to combined4 / R4S / combined5 / combined4-c32 / c32b / c32c (keys modulo tools dir). `launch_browser_gpt2.py --check`: 285 static files, `runtimeJavaScript: false`.
- NumPy reference ids with the merged tools (`R4M/reference_ids.log`): 8-token `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected; 32-token teacher-forced (kv_window None / 32) and free-running == the saved ctx32 ids (`R4M/reference_ids_32.json` == `R4C/reference_ids_32.json`).
- Sizes: runtime.css 39752852 B, index.html 6512942 B.

## Chrome correctness run

ONE passive run (NOT a timing run), `R4M/run_correctness.sh combined6` (R3M's watchdog harness with R4M paths: owner-marked lock, toucher killed before a marker-checked release; F4's
`correctness_run.mjs`: headless Chrome 153, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), 2026-09-21 01:16:25–01:19:27 under `CHROME.lock`
(waited 1,605 s behind R4X). Power: AC (81 %, not charging); load { 5.72 5.76 5.66 }. Results in `work/2026-09-19/R4M/run-combined6/`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0 (unchanged tool, run through `R4M/verify_wrapper.py`, see below):
  tokenAgreement 8 × True, originalFloatAgreement 8 × True, finalHeadMatchesActualInput True, text "Hello, I'm sorry, but I'm"; `finalResidualError` rmse **0.016055** / max **0.11652**
  (combined4 0.017645 / 0.13388; R4S alone 0.017219 / 0.16788 — same 1e-2 class, ids identical).
- **Harness readback gap (not a page issue):** F4's `correctness_run.mjs` reads the packed V list `--fc-v-S` from each bank; with `R4D_UNPACK_V` the V list is stored as 12 per-head lists
  `--fc-v-S-H`, so the V half of every KV cache entry came back null (96 × 768) and the stock verify crashed in `profile_hybrid_twelve_block.error` (TypeError on None). `R4M/verify_wrapper.py`
  replaces the nulls by NaN (original kept as `verification-vectors.raw.json`), runs the unchanged verify (rc 0; `cacheErrors` rmse None for the V-half-less entries) and adds the **K-half cache
  errors** to `numerical-results.json`: 96/96 complete, rmse median 0.0019 / max 1.492 (layer 11), abs max 5.62 — the identical class as combined4's run (0.0018 / 1.493 / 5.624) and R4S's
  (0.0019 / 1.494 / 5.629), recomputed from their `verification-vectors.json` with the same code. `R4M/correctness_run.mjs` now concatenates the per-head lists when the packed one is empty (future runs).
- Whole-run counters (harness idle → end): RecalcStyleCount 3,752, LayoutCount **527** (combined4 985 / 629; R4S alone 3,759 / 535 — with R4S the RecalcStyleCount includes the interleaved
  container recalcs and is no longer a pass count, R4S.md §6); Nodes 132,214.
- Per-token capture times (5 s poll granularity — indicative only, not a timing run): 23.2, 11.7, 18.5, 11.7, 17.5, 19.6, 17.5, 17.8 s = **137.4 s** total (cumulative 23.2, 34.9, 53.3, 65.0, 82.5,
  102.1, 119.6, 137.4; combined4's correctness run 158.6 s, R4S's 146.3 s, combined5's bench_native run 150.8 s). B5's paired protocol decides the s/token.
- `bundles/combined6/READY` created 2026-09-21 01:22.

## `diff -ruN -x __pycache__ work/2026-09-19/R3M/tools work/2026-09-19/R4M/tools`

(574 lines = R4S's diff + R4D's diff + the two conflict resolutions; also at `R4M/tools-vs-R3M.diff`)

```diff
diff -ruN -x __pycache__ R3M/tools/browser_gpt2_font_vector_cache.py R4M/tools/browser_gpt2_font_vector_cache.py
--- R3M/tools/browser_gpt2_font_vector_cache.py	2026-09-20 22:01:52
+++ R4M/tools/browser_gpt2_font_vector_cache.py	2026-09-21 00:46:59
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
diff -ruN -x __pycache__ R3M/tools/browser_gpt2_reused_adapter.py R4M/tools/browser_gpt2_reused_adapter.py
--- R3M/tools/browser_gpt2_reused_adapter.py	2026-09-20 22:01:52
+++ R4M/tools/browser_gpt2_reused_adapter.py	2026-09-21 00:46:59
@@ -14,6 +14,8 @@
 from browser_gpt2_reused_core import compile_reused
 import r2f_lean_handshake as r2f
 import r3r_fold_hop as r3r
+import r4s_small_hops as r4s
+import r4d_flags as r4d
 
 
 def compile_reused_runtime_core(
@@ -138,7 +140,7 @@
         # and stamp the current pass directly onto every reader.
         receipts = [
             f".shared-{kind}-receipt" for kind in ("qkv", "attn", "fc", "proj")
-        ] + [".cache-bridge-receipt", ".fvs-score-receipt"]
+        ] + [".cache-bridge-receipt"] + ([] if r4s.SMALL_HOPS else [".fvs-score-receipt"])
         pass_readers = ",".join(
             [
                 ".loop-input",
@@ -167,7 +169,8 @@
         body, tagged_position = f5.tag_inline_readers(
             body, "var(--position)", "pass-reader"
         )
-        if tagged != 7 or tagged_position != 2:
+        # R4S: the score stamp marker (one inline var(--epoch) reader) no longer exists
+        if tagged != (6 if r4s.SMALL_HOPS else 7) or tagged_position != 2:
             raise ValueError(
                 f"Unexpected inline pass readers: {tagged} epoch, {tagged_position} position"
             )
@@ -234,6 +237,7 @@
         "localLayerContainer": True,
         "r2fLeanHandshake": r2f.LEAN_HANDSHAKE,
         "r3rFoldHop": r3r.FOLD_HOP,
+        "r4sSmallHops": r4s.SMALL_HOPS and codec == "font-vector",
         "f5ScopedHandshake": f5.SCOPED_HANDSHAKE,
         "f5ScopedEpoch": f5.SCOPED_EPOCH,
         "f5ScopedFeedback": f5.SCOPED_FEEDBACK,
@@ -243,6 +247,11 @@
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
diff -ruN -x __pycache__ R3M/tools/r4d_flags.py R4M/tools/r4d_flags.py
--- R3M/tools/r4d_flags.py	1969-12-31 16:00:00
+++ R4M/tools/r4d_flags.py	2026-09-21 00:46:59
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
diff -ruN -x __pycache__ R3M/tools/r4s_small_hops.py R4M/tools/r4s_small_hops.py
--- R3M/tools/r4s_small_hops.py	1969-12-31 16:00:00
+++ R4M/tools/r4s_small_hops.py	2026-09-21 00:46:59
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
