# R4W — cut the ∝ p per-pass allocation of the V leaves without changing numerics (R4V §5.1 fix)

Agent R4W, 2026-09-21 03:56–. Work under `R4W/` (`tools/` = R4D/tools + `r4w_precat.py` + emitter edits; `compile-r4w.sh`, `build_all.sh`,
`run_chain.sh`, `leaf_bytes.py`, `numpy_ids_40.py`, `compare3.py`, `trace-parse/`, `runs/`, `run-combined4-c32d/`). Log `R4W.log.md`.
No repo `tools/` or `experiments/` edits, no git. Bundles: `bundles/combined4-c32d` (BUILD.md), `bundles/smoke-R4W-2L{,-ref}`.

## 0. Headline

STATUS: complete. Chrome: smoke pair identical; c32d prompt-40 32/32 at 1,045.4 s (14.11 + 1.107·k); control c32c Hello late 32/32 at 969.7 s
(13.39 + 1.012·k vs 758.7 s / 0.646·k early) → memory state drives the slope, the fix did not move it (§4–5).

- **Mechanism confirmed (§1).** In c32c every filled V leaf declares `font-variation-settings:var(--fr-v-S-H),"P000" 1` (2 var() refs). Blink re-does
  var() substitution for every element it restyles: the referenced list is copied into a fresh token stream (**1,061 B mean, 1,033–1,167 B**, prompt-40
  trajectory), re-tokenised, parsed into a 65-entry CSSValueList and converted to a new FontVariationSettings + FontDescription hash on EVERY restyle
  of the leaf, whether or not the list changed. The list itself IS latched once (the bank's `--fc-v-S-H` changes only at the write; the layer's
  alias `--fr-v-S-H` changes only per layer) — it is the leaf-side re-substitution that allocates. R4V's trace (`R4W/trace-parse/`) shows the
  leaf subtree (25,351 elements = 24,576 leaves + 768 rows + 7) is restyled **12× per token** (one per layer), so per filled position per token:
  768 × 12 × ≈1.07 KB = **9.85 MB of substituted text** plus the parsed CSSValueLists/FontVariationSettings (≈3 KB per leaf-restyle → ≈40 MB in
  total, matching R4V's 40 MB/position/token RSS growth). The trace also puts the GC cost at **2.8 s/token at k≈7.5** (`V8.GC_*` nested 17.0 s of
  146 s generate = 11.6 %, of which `GC_HEAP_ENSURE_SWEEPING_COMPLETED` 8.1 s, incremental marking with embedder (Oilpan) tracing 3.0 s, MajorGC 1.1 s;
  gc_nested per token 1.6–3.8 s at k=5…10).
- **Fix (a) as literally specified saves ≈1 % (§2).** Folding `,"P000" 1` into the latched value and making the leaf a single `var()` removes the
  10-byte literal only; Blink has no single-var() fast path (`StyleCascade::ResolveVariableReference` always builds a TokenSequence copy and reparses).
  Kept as `R4W_V_PRECAT=alias` for measurement, not built.
- **What was built (`R4W_V_PRECAT=1`, default, "wrapper" — alternative (c) ported to the widths layout).** Per-slot value fonts (retagged v2 operator,
  unicode-range gated), the head's complete 65·p-axis settings on ONE `display:contents` wrapper per head (12 substitutions per restyle instead of
  768·p), leaves with **no font property and no font-variation-settings at all** (Font inherited by pointer), weight still applied in the leaf width
  (`calc-size` + `var(--fw-H-S)`) — so the numerics are those of combined4-c32c, not the fallback layout's P-axis quantisation. Substituted bytes per
  filled leaf per restyle **1,069 B → 8 B** (the `--fw` number); var() refs per leaf 2 → 1; parsed axes per restyle at p=32 **1,597,440 → 24,960**;
  substituted text per filled position per token **9.85 MB → 0.07 MB (+153 KB on the 12 wrappers)**.
- **Exactness (§3):** same numbers → axes with the same HVAR regions in fonts whose advance tables are byte-identical (HVAR/hmtx/glyf/loca/maxp/hhea
  asserted; HVAR evaluation at random locations equal across source / F4 head fonts / R4W slot fonts), P000 = 1 as before, row formula untouched.
  NumPy prompt-40 ids with the R4W tools = `R4P/reference_ids_32_40.json` (32/32). Rule diff confined to the intended families; index.html identical
  modulo leaf characters, head wrappers and the font barrier; no JS.

## 1. What allocates per pass (task 1)

Leaf rule today (`bundles/combined4-c32c/runtime.css`, emitted at `R4D/tools/browser_gpt2_font_vector_cache.py:498–514`):
`.fvs-v-H-S{font-family:FvsValueH;font-variation-settings:var(--fr-v-S-H),"P000" 1;width:calc-size(max-content,calc(12320.768px + (size - 12320.768px) * var(--fw-H-S)));min-width:0;flex:none}`
— 180 literal bytes, 2 var() references. `--fr-v-S-H` (`@property syntax:"*" inherits:true`) is the layer's alias of the bank's latched `--fc-v-S-H`
(`.fvs-bank-L{--fr-v-S-H:var(--fc-v-S-H)}` under `@container runtime style(--layer:L)`, :336–343); the latched field is written once per KV slot
(:296–316) and retained by the transition latch. So the LIST is latched and, seen from the leaf, changes only when the layer changes.

What Blink does per leaf per restyle nevertheless (Blink source from memory, consistent with the trace):
1. `StyleCascade::ResolveVariableReference` → `TokenSequence`: appends the referenced CSSVariableData's original text (**1,061 B mean** for a
   64-axis list of 6-significant-digit numbers, `R4W/leaf_bytes.py`) + the literal tokens → new String + CSSVariableData.
2. `Parse(font-variation-settings)` → tokeniser over the ~1.1 KB → **65 CSSFontVariationValue + CSSValueList** (Oilpan, ≈2.5–3 KB).
3. `StyleBuilderConverter::ConvertFontVariationSettings` → new **FontVariationSettings** (65 × 8 B, RefCounted).
4. `FontBuilder::CreateFont` (font-family is set on the leaf) → `Font(description)` → `FontFallbackMap::Get` → **FontDescription hash incl. the 65
   axes** (uncached `FontVariationSettings::GetHash`), lookup of the shared FontFallbackList.
5. `width` var() substitution + calc-size parse (~100 B, a small CSSMathExpression tree) — stays in c32d.
6. Font instance creation (`FontCache::GetFontPlatformData`) only when the (S,H,layer) instance is new: 287 calls / 16.8 ms in the 6-token trace
   window — NOT the per-pass cost. Shaping (`InlineNode::ShapeTextIncludingFirstLine`, 1.19 M calls, 14.3 s in the window) is layout, per glyph
   per layer, unchanged by this fix.

Counts from R4V's trace (`R4W/trace-parse/p40-10tok-analysis.txt`, tokens 5–10 of a prompt-40 run): style passes per token 79; passes by
elementCount: 25,351 elements ×12/token (the value-row subtree; 0.9–1.9 s per token at k=5–10, noisy — GC-like), 50,888 ×1 (whole document),
414/782/3,089/2,324 ×11–13 (query/bank/reader subtrees; the 414-element passes cost 1.4–3.1 s per token, i.e. 0.3–0.6 ms per element — the K-list
concatenations and latches, not this task). GC: `gc_total_ms_generate` 16,950 ms of 146,170 ms; per token gc_nested 1.9/1.6/3.8/2.9/2.7/3.6 s
(k=5…10), majorGC 2–3 per token, `V8.GC_MC_INCREMENTAL(_EMBEDDER_TRACING)` ≈117 K slices each.

Accounting per filled position per token (768 leaves × 12 restyles): substituted text 9.85 MB; with the CSSValueList + FontVariationSettings
(≈3–3.5 KB per leaf-restyle) ≈ 38–42 MB — R4V's 40 MB. Unfilled leaves (display:none via `@container fvscache style(--fvq-S:0)`) are ALSO
resolved every restyle (Blink computes the style of a display:none element itself) but substitute the 12-byte initial `"Vxxx" 0` — the ∝ p term is
the bytes, not the element count.

## 2. What changed (task 2) — `R4W/tools/r4w_precat.py` (new), `R4W/tools/browser_gpt2_font_vector_cache.py`

| where (R4W/tools/browser_gpt2_font_vector_cache.py) | change |
|---|---|
| :17 | `import r4w_precat as r4w` |
| :188–191 | `precat = r4w.mode()` when widths + F4 packed + R4D_UNPACK_V; `wrapper_v` / `alias_v` |
| :204–213 | `@property --fc/--fr-v-S-H` initial values with per-slot tags `"V{S·64}" 0` (wrapper) |
| :296–305 | `--fvs-live-v-H` = `if(style(--fvs-write-slot:S):<slot-tagged list>;…;else:…)` (wrapper; the emitter's existing fallback form, `settings_for(slot)`) |
| :321–328 | write rule `--fc-v-S-H:var(--fvs-live-v-H)` + `,"P000" 1` (alias mode only) |
| :367–375 | @font-face: FvsDotH kept; FvsValueH dropped in wrapper mode; 32 `FvsValueSlotS` faces with `unicode-range:U+F5800+S·64…` from `r4w.slot_fonts()` |
| :528–543 | leaf rule: wrapper `.fvs-v-H-S{width:…var(--fw-H-S)…;min-width:0;flex:none}` (no font property); alias `font-variation-settings:var(--fr-v-S-H)` |
| :551–557 | `.fvs-value-head-H{display:contents;font:1024px FvsValueSlot0,…;font-kerning:none;font-style:normal;font-variation-settings:var(--fr-v-0-H),…,var(--fr-v-31-H),"P000" 1}` |
| :577–585 | `row()`: leaf char `U+F5800+S·64+i`, `<div class="fvs-value-head-H">` around each head's 64 rows |
| :610–616 | `.fvs-value-row{display:inline-flex;gap:0;line-height:1;white-space:pre}` (no `font:` shorthand — it would reset the inherited settings and create a Font per row) |
| :675 | manifest `r4wVPrecat` |
| `r4w_precat.py` | flag parsing; `slot_fonts()`: v2 `value.woff2` (P000 + 64 axes) → V axes retagged `V{S·64+i}`, cmap +S·64, name/STAT; HVAR/hmtx/glyf/loca/maxp/hhea asserted byte-identical; written to `R4W/assets-r4w/font-vector-operators-r4w/value-sS-<digest>-r4w.woff2` |

Why not the fallback layout as-is (alternative (c)): it puts the weight back on the P axis (`"P{S}" var(--fw-H-S)` on the wrapper) — the runs-layout
numerics (1/16384 P quantisation) that c32c deliberately replaced, and every weight change would re-instantiate all 32 slot fonts of the head. The
wrapper variant keeps c32c's numerics exactly and keeps the (S,H,layer) instance count (144·p per token).

Bytes per filled leaf per restyle (`R4W/leaf_bytes.py`, prompt-40 lists): c32c **2 var(), 180 B literal, ≈1,069 B substituted**; c32d **1 var(),
108 B literal, ≈8 B substituted**; wrapper 32 var(), ≈65·p·16 B substituted per head per restyle (12 × 12 × 1,061 B = 153 KB per filled position
per token). Alias mode would be 1 var(), ≈1,059 B (−10 B).

Costs the wrapper adds (all state-independent or small): 12 × 2,080-axis lists tokenised per restyle (≈660 KB CSS for the 12 `if()` live lists,
55 KB per head, evaluated once per `.fvs-query` pass); each new (S,H,layer) font instance filters 65 axes against a 2,080-entry list
(`FontCustomPlatformData::GetFontPlatformData`, ~65×2,080 tag compares ≈ 50–100 µs; 144·p instances/token → ≤0.5 s/token at p=32);
FontDescription/FontCacheKey hashes of 2,080 axes at the 12 wrappers per restyle and per new instance (not per leaf: leaves inherit the Font).

## 3. Offline verification (task 3) — R4W.log.md 04:16–04:25

- Builds: `R4W_V_PRECAT=1 compile-r4w.sh smoke-R4W-2L 8 2`, `=0 … smoke-R4W-2L-ref 8 2`, `=1 … combined4-c32d 32 12` (logs `R4W/compile-*.log`).
- `R4D/rule_diff.py` c32c → c32d (66,716 → 66,769 leaf rules): removed `.fvs-v-N-N` 384, `@property --fc-v/--fr-v` 372+372 (12 S=H values coincide),
  `.fvs-query` 12, `@font-face` 12, `.fvs-value-row` 1, barrier `.font-proof-N` 19 / `.font-all-N-N` 2; added `.fvs-v-N-N` 384, `@property` 372+372,
  `.fvs-query` 12 (660,868 B: the live-v if() lists), `.fvs-value-head-N` 12, `@font-face` 32, `.fvs-value-row` 1, barrier 39+3. Nothing else differs.
  Smoke pair: same families (96/88/88/12/8…).
- `index.html`: byte-identical after normalising the value-row leaf characters (64 → 2,048 distinct), the 12 head wrappers and the barrier
  probes/proofs/reductions (283 → 303 faces); 768 rows in both. Same for the smoke pair.
- `font-witnesses.json`: 271 shared faces identical (codepoint/advance/upem); −12 `value-hH-…-f4.woff2`, +32 `value-sS-…-r4w.woff2` (advance 12032/1000).
- `tools/launch_browser_gpt2.py --check`: `runtimeJavaScript:false` for combined4-c32d, smoke-R4W-2L, smoke-R4W-2L-ref.
- Font exactness: `VarStoreInstancer` over HVAR at 4 random 64-axis locations (P000 = 1 and 0.5): 64 advances identical for source `value.woff2`,
  F4 `value-h0`, `value-h3`, R4W `value-s3`, `value-s31`, all = 12032 + 12000·P·V_i.
- NumPy ids: `R4W/numpy_ids_40.py` (R4W tools copy, free-running 32 steps, 14 s) = `R4P/reference_ids_32_40.json` free-running = teacher-forced, 32/32.
  `diff -rq R4D/tools R4W/tools` = the emitter + `r4w_precat.py` only, so the reference path is untouched by construction.
- var()/bytes per leaf: §2 (`R4W/leaf_bytes.out`).

## 4. Chrome (task 4) — `R4W/run_chain.sh` (one lock acquisition 05:02–05:22: smoke pair, then the 32-token run), `R4W/compare3.py`

### 4.1 2-layer smoke pair (05:02–05:04, load 3.1–3.5)
`smoke-R4W-2L-ref` (R4W_V_PRECAT=0) ids `[11, 3387, 3387, 3387, 3387, 3387, 3387, 3387]`, `smoke-R4W-2L` (=1) ids identical, done markers 8/8 both,
≈55 s each (`R4W/runs/`). The if() slot-tagged live lists, the 32 unicode-range slot fonts and the head wrappers work in this Chrome. **PASS.**

### 4.2 combined4-c32d, prompt 40, ONE passive 32-token run (05:04:28–05:22:35, load 3.2–4.3, keyboard, heap=1, trace=0)
`R4W/run-combined4-c32d/c32d-run1.summary.md`: **ids 32/32** = `R4P/reference_ids_32_40.json` → `bundles/combined4-c32d/READY` written as
correctness-only with a timing caveat. **Total 1,045.4 s**; fit(k≥2) wall **14.11 + 1.107·k** (c32c run C, same prompt: 12.66 + 1.129·k, 1,008.6 s;
c32c Hello early: 12.79 + 0.646·k, 758.7 s); style 4.09 + 0.521·k (run C 4.37 + 0.566·k), layout **4.20 + 0.442·k** (run C 2.65 + 0.415·k);
pass counts unchanged (84.2/76.3 per token); `ThreadTime/wall` 0.93; JS heap 0.6–2.0 MB. Renderer RSS: 3.0 GB (k=1) → peak 5.6 GB (k=4–7) →
declines to 2.9–3.4 GB (k=30–32) — the same saw-tooth/decline as run C (5.0 → 2.8 GB); mean 4.4 GB vs run C 3.8 / Hello 6.0 GB. Machine state
(`c32d-run1.vm_stat.*`): swap 4.5 of 5 GB used; compressor 909 K → 1,045 K stored pages (≈15–16 GB compressed) during the run; free pages 235 K → 411 K;
`memory_pressure` "free 71 % → 65 %". So this run, like run C, ran with the OS actively compressing/swapping. Per-k table with RSS: `R4W/compare3-c32d.md`.

| k | c32c Hello early (R4D) s (style/layout) RSS MB | c32c p40 run C (R4M) | c32d p40 (R4W) |
|---:|---|---|---|
| 1 | 22.0 (9.0/3.7) 2622 | 21.2 (8.7/3.8) 2889 | 24.7 (9.1/5.8) 3000 |
| 4 | 16.2 (6.3/4.0) 4846 | 17.4 (7.1/4.2) 4461 | 20.0 (7.4/6.1) 5244 |
| 8 | 17.7 (7.0/4.6) 5528 | 21.3 (8.3/6.3) 4482 | 22.7 (7.4/8.4) 5201 |
| 12 | 19.4 (7.8/5.2) 6806 | 24.8 (10.3/7.5) 4273 | 26.5 (9.8/8.9) 5137 |
| 16 | 21.3 (8.3/6.4) 7073 | 30.2 (14.2/8.5) 3762 | 31.2 (11.4/12.3) 4784 |
| 20 | 24.8 (8.5/9.1) 6720 | 33.5 (12.4/15.7) 3286 | 37.8 (15.3/13.2) 4039 |
| 24 | 26.9 (12.0/7.7) 6502 | 40.4 (20.0/11.5) 3402 | 38.7 (14.5/15.9) 3931 |
| 28 | 32.7 (14.7/10.2) 5847 | 41.2 (18.8/13.7) 2925 | 46.5 (17.6/18.6) 3470 |
| 32 | 35.2 (15.0/10.9) 5719 | 50.2 (24.8/15.0) 2807 | 49.0 (21.1/16.0) 3196 |
| fit k≥2 | 12.79 + 0.646·k | 12.66 + 1.129·k | 14.11 + 1.107·k |
| style / layout fits | 4.46+0.299·k / 2.66+0.270·k | 4.37+0.566·k / 2.65+0.415·k | 4.09+0.521·k / 4.20+0.442·k |
| total | 758.7 s | 1,008.6 s | 1,045.4 s |

Reading: (i) the per-position slope did **not** move (1.107 vs 1.129; style −8 %, layout +7 %) although the leaf-side substituted bytes fell 99 %
(offline-verified, §2) — the V-leaf re-substitution is NOT what sets the slope in this memory state; (ii) the RSS trajectory is unchanged in shape,
so the ∝ p garbage that drives the decline/GC cadence is not (mainly) the leaf lists either — the remaining ∝ p substitution streams are the 12·p
score glyphs (`var(--fr-k-S),var(--fvs-query-H)`: ≈12.7 KB packed K list + 1 KB query each, per restyle of the score subtree) and the current
bank's 37·p aliases (≈25 KB·p per bank restyle), plus layout-side shaping/flex work ∝ p that no style-side fix touches; (iii) the wrapper design
costs **≈ +1.5 s/token in the layout intercept** (layout 5.8 vs 3.8 s at k=1; style intercept unchanged) — most likely per-leaf shaping through the
32-family unicode-range fallback list / per-instance 2,080-axis filtering — a real regression at small k; (iv) run-to-run noise between the two p40
runs is ≈ ±2 s/token, so a ≤5 % slope change is unresolvable in single runs.

### 4.3 Control: combined4-c32c, DEFAULT Hello prompt, late session (`R4W/run_control_c32c_hello.sh`, 05:40:28–05:57:19, waited 875 s)
`R4W/run-combined4-c32c/c32c-runD-hello-late.summary.md`: ids **32/32** = `R4C/reference_ids_32.json`. **Total 969.7 s**; fit(k≥2) wall **13.39 + 1.012·k**
(early Hello run of the SAME bundle: 12.79 + 0.646·k, 758.7 s); style 5.00 + 0.474·k (early 4.46 + 0.299·k), layout 2.22 + 0.419·k (early 2.66 + 0.270·k);
pass counts identical (84.2/76.2). RSS: peak 5.4 GB (k≈8), declining to 3.1–3.4 GB by k=30–32, mean 4.1 GB (early Hello: mean 6.0 GB, peak 7.2 GB, no decline).
Machine (`c32c-runD-hello-late.vm_stat.*`): swap 4.4 → 4.3 of 5 GB used, compressor 997 K → 1,030 K stored pages, free 64–68 %; load 3.8–4.1 at start.
**The same bundle on the same prompt: 758.7 s in the early (free-memory) session vs 969.7 s now (+28 %, slope 0.65 → 1.01).** The decision rule's
"≈1,000 s" branch applies: memory state is the driver; the 758.7 s figure was a favourable-state result; the prompt does not matter (p40 run C 1,008.6 s
and this Hello run 969.7 s are within run-to-run noise of each other, ≈4 %). R4V's count analysis stands.

### 4.4 Four-way comparison (`R4W/compare4.md`; per-k `s (style/layout) RSS-mean MB`)

| k | c32c Hello early (R4D 00:30) | c32c p40 run C (R4M 03:24) | c32d p40 (R4W 05:04) | c32c Hello late (R4W 05:40) |
|---:|---|---|---|---|
| 1 | 22.0 (9.0/3.7) 2622 | 21.2 (8.7/3.8) 2889 | 24.7 (9.1/5.8) 3000 | 21.3 (8.6/3.7) 2893 |
| 4 | 16.2 (6.3/4.0) 4846 | 17.4 (7.1/4.2) 4461 | 20.0 (7.4/6.1) 5244 | 19.6 (7.6/4.5) 4571 |
| 8 | 17.7 (7.0/4.6) 5528 | 21.3 (8.3/6.3) 4482 | 22.7 (7.4/8.4) 5201 | 21.1 (8.3/5.6) 5179 |
| 12 | 19.4 (7.8/5.2) 6806 | 24.8 (10.3/7.5) 4273 | 26.5 (9.8/8.9) 5137 | 23.2 (9.4/6.5) 4748 |
| 16 | 21.3 (8.3/6.4) 7073 | 30.2 (14.2/8.5) 3762 | 31.2 (11.4/12.3) 4784 | 31.2 (13.0/9.7) 4295 |
| 20 | 24.8 (8.5/9.1) 6720 | 33.5 (12.4/15.7) 3286 | 37.8 (15.3/13.2) 4039 | 32.7 (15.4/9.1) 3948 |
| 24 | 26.9 (12.0/7.7) 6502 | 40.4 (20.0/11.5) 3402 | 38.7 (14.5/15.9) 3931 | 34.7 (19.4/10.0) 3446 |
| 28 | 32.7 (14.7/10.2) 5847 | 41.2 (18.8/13.7) 2925 | 46.5 (17.6/18.6) 3470 | 42.6 (19.8/12.4) 3483 |
| 32 | 35.2 (15.0/10.9) 5719 | 50.2 (24.8/15.0) 2807 | 49.0 (21.1/16.0) 3196 | 49.6 (20.0/18.1) 3344 |
| fit k≥2 (wall) | 12.79 + 0.646·k | 12.66 + 1.129·k | 14.11 + 1.107·k | 13.39 + 1.012·k |
| style / layout | 4.46+0.299·k / 2.66+0.270·k | 4.37+0.566·k / 2.65+0.415·k | 4.09+0.521·k / 4.20+0.442·k | 5.00+0.474·k / 2.22+0.419·k |
| RSS mean / peak MB | 6023 / 7226 (monotone) | 3761 / 5075 (declining) | 4412 / 5627 (declining) | 4146 / 5423 (declining) |
| total | 758.7 s | 1,008.6 s | 1,045.4 s | 969.7 s |

Reading: the three late-session runs (p40 c32c, p40 c32d, Hello c32c) sit within ≈8 % of each other in total and within 0.10 s/token/position in
slope, all with the declining-RSS signature; the one early-session run is 22–27 % faster with RSS allowed to grow. Prompt: no effect. Bundle
c32c → c32d: slope −2 % (noise), layout intercept +1.5–2.0 s/token (real: 5.8 vs 3.7 s at k=1, 8.4 vs 5.6 at k=8), total +7.8 % vs the Hello-late run
and +3.6 % vs the p40 run — i.e. **c32d is slower than c32c under this memory state**, and the ∝ p allocation it removed was not what the memory
state acts on.

## 5. Verdict and risks

- **Mechanism verdict.** The premise is confirmed (leaf lists ARE re-substituted/re-parsed per restyle, ≈1.07 KB + a 65-entry CSSValueList per filled
  leaf, 12 restyles/token) and the fix removes it exactly (offline-verified; smoke ids identical; 32/32 on prompt 40). But the CONSEQUENCE R4V predicted
  is refuted by the run: with 99 % of the leaf-side substituted bytes gone, the per-position slope (1.107 vs 1.129 s/token/position), the style slope
  (0.52 vs 0.57), the RSS saw-tooth/decline and the GC-like noise are unchanged within single-run noise, and layout got ≈1.5 s/token slower at all k.
  The control run (§4.3) shows the slope of the UNCHANGED bundle went 0.646 → 1.012 s/token/position between sessions on the same prompt, so the
  slope is set by machine memory state (swap/compressor pressure forcing renderer RSS down → GC/purge/cache-rebuild work ∝ p), and the leaf-list
  re-substitution is not the ∝ p allocation that state acts on (removing it changed nothing but the intercept). Do not adopt c32d as the demo
  bundle: it is correct and exact but slower (+1.5–2 s/token layout intercept, +4–8 % total under pressure); its only demonstrated benefit is
  offline (bytes parsed per restyle). R4V's count analysis stands; R4V's §5.1 prediction ("slope becomes state-independent, −0.15…−0.3") is refuted.
  What would settle the fix's residual value: a paired c32c/c32d run in a clean-memory session (no swap in use, ≥8 GB free); and a c32d trace to
  locate the +1.5 s/token layout cost (per-leaf shaping through the 32-family unicode-range list is the prime suspect — a per-head font-family
  ordering that puts the filled slots first, or per-row families, would test it).
- Remaining ∝ p style-side substitution not touched: 12·p score glyphs (`var(--fr-k-S)` ≈12.7 KB packed K list each), the current bank's 37·p aliases.
  Layout-side ∝ p (shaping 768·p glyphs per layer, flex layout of 768 rows × p items) carries 0.42–0.44 s/token/position in every run and is untouched.
- Machine state during both p40 runs: swap 4.5/5 GB used, compressor ≈0.9–1.05 M stored pages (≈15 GB compressed), other apps resident; renderer RSS
  pushed down from 5–5.6 GB to ≈3 GB by the OS. Any timing verdict on this fix needs a clean-memory session (≥8 GB free, no swap use).
- Chrome behaviour verified only for: if() slot-tagged lists, 32 unicode-range slot faces, 2,080-axis wrapper settings (all worked; ids exact).
  Not verified: cause of the +1.5 s/token layout intercept (hypothesis: per-leaf shaping through the 32-family fallback list / 2,080-axis instance
  filtering) — a trace of c32d would settle it; Blink internals cited from memory, not a checkout.
- font-witnesses not identical by construction (−12 head value fonts, +32 slot fonts); 271 shared entries identical.
