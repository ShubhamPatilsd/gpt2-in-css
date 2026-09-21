# R4C — 32-token generation with combined4's emitter: feasible (18.9 min, 32/32 ids, 5.8 GB peak RSS); slope 1.14 s/token per position, all in per-pass cost

Agent R4C, 2026-09-20 23:20–24:00. Bundle `bundles/combined4-c32` (BUILD.md, READY), tools copy `R4C/tools` (byte-identical to `R3M/tools`), scripts and
run data under `R4C/` (`compile-c32.sh`, `reference_ids_32.py/.json`, `populations.py/.txt`, `run_c32.sh`, `summarize32.py`, `slope_model.py`,
`run-combined4-c32/c32-run1.{json,summary.md}`). Log `R4C.log.md`. No repo `tools/` or `experiments/` edits, no git.

## 0. Headline

- **Feasible.** combined4 at `--capacity 32` generates 32 tokens in **1,132.9 s (18.9 min)**, ids **32/32** = the NumPy reference = Codex's saved ctx32 ids,
  vs Codex's v1 ctx32 bundle **3,177 s** (2.8× faster; per-token 25.6 → 57.7 s vs 57 → 143 s). Renderer RSS peak **5.84 GB** (Codex 5.2 GB) — a GC saw-tooth
  of 2–4 GB per token under `--heap-growing-percent=10`, median 3.4 GB; the DOM itself is static (Nodes 169.5k before and after).
- **Slope 1.14 s/token per position** (fit 16.3 + 1.14·k over k=2..32; Codex's bundle ≈2.9). Not a pass-count effect: 84 recalcs + 76 layouts per token
  at every position. It is per-pass cost growth, split **style +0.49 / layout +0.54 / other +0.09 s per position**, i.e. the per-position populations
  make the SAME passes slower — exactly the "filled slot" terms: 9,216 more filled V glyphs (768 rows × 12 layers) and 144 more score glyphs per token per
  position, each carrying a distinct 768-axis `font-variation-settings` instance, plus 312 more in-delay latch transitions per position.
- **Capacity step**: at equal position c32 is +5–7 s/token above combined4 (tokens 2–7: 19.8–25.0 vs 15.2–18.9): 18,432 extra (unfilled) V glyph leaves,
  +288 live score timelines, 4× longer bank `transition-property` lists, 3.5× the `:has()`/`@container` rules — paid from token 1 (§3).
- Curve is not straight: ≈0.69 s/position over tokens 2–18, a **+9 s step over tokens 19–22** (style +4, layout +5), then ≈1.1 s/position — consistent
  with a font-instance cache overflowing once the number of live distinct variation instances passes a threshold (hypothesis, §4).
- Best emitter fixes (no model change, §5): (1) `display:none` for unfilled V glyphs (kills the capacity step: ≈ −1.1…−1.5 s/token at p=1 → −20…−25 s total);
  (2) carry the softmax weight outside the variation instance (font-size instead of the `P000` axis) so filled V instances are constant across passes and
  tokens → cacheable, predicted −0.3…−0.5 s/token per position (≈ −40 % of the slope; exactness-gated); (3) per-head 64-axis V lists instead of the packed
  768-axis list per glyph (−0.15…−0.25 s/position) and paused-animation latches instead of in-delay transitions (−0.12 s/position). Together ≈ 16 + 0.5·k →
  ≈ 780 s for 32 tokens. Bounded KV window (model change) would give combined4's flat ≈18–19 s/token → ≈600 s.

## 1. Build (step 1) — `bundles/combined4-c32/BUILD.md`

Only `--capacity 8 → 32` (CLI `--capacity`; the emitter validates 2–32). Side effects of capacity > 8: the head epoch transport switches to
`split_head_receipt` ("separate geometry": a second size container carries the epoch; the packed-4-bit form is only valid below epoch 16); the token
handshake gets 32 slots (`token-N-captured/-advanced`, R2G rewrote 98 `run` `:has()` arguments instead of 26). All other hooks (F4/F5/R2C/R2D/R2F/R2G/R3R/R3H)
applied without assertion failures. Static check 285 files / 297.3 MB / no JS; font-witnesses 283/283 identical to combined4 (7/7 shared keys identical
with the pinned v1 ctx32 bundle; the rest are v2/F2/F4 fonts, not comparable). Reference ids: teacher-forced (kv_window None and 32) and free-running
NumPy q9/q16 = Codex's saved 32 ids (`R4C/reference_ids_32.json`).

Populations (c32 vs combined4, `R4C/populations.txt`): elements 67,401 → 86,315 (+788/slot: 768 `.fvs-v-H-S` + 12 `.fvs-score-H-S` + slot/feedback metrics);
`.fvs-v-H-S` leaves 6,144 → 24,576; score carriers with view-timelines 96 → 384 (timeline-scope entries 80,117 → 80,717); bank `transition-property`
208 → 832 names, and each of the 384 write rules inlines an 806-name literal list (F5 literal lists: 310,438 listed names in the sheet vs 17,710);
`@property` 39,426 → 41,946; `@container` 660 → 2,244; `:has(` 85 → 301; runtime.css 39.0 → 50.1 MB, index.html 5.6 → 6.3 MB. Per position p (all layers):
in-delay latch transitions 312·p (F4: 26 per slot per layer), `--fr-*` aliases 26·p on the written bank (F5 filled-slot filter), filled V glyphs 9,216·p,
filled score glyphs 144·p. NOT gated by fill: every unfilled V glyph still substitutes `var(--fr-v-S)` whose `@property` initial value is the full
768-axis zero list (≈7.7 KB) — the fonts ignore foreign tags, so it is numerically harmless but not free.

## 2. Run (step 2) — one passive run, `R4C/run_c32.sh` (lock discipline of R3M/run_correctness.sh; Chrome matched by `^/Applications/.*Google Chrome .*--headless`; owner-stamped lock; AC checked every 30 s)

B0/bench_native.mjs, `B0_CAPACITY=32 B0_TRIGGER=keyboard B0_HEAP=1 B0_TRACE=0 B0_CAP_MS=2400000`, headless Chrome 153, caffeinate; poll
`#token-k-captured.done` at 1 Hz (passive), RSS via `ps` at 1 Hz, `Performance.getMetrics` at 1 Hz. Load 5.8–10 during the run (other agents' compiles; contended
— absolute numbers ≈ +5–10 % vs quiet). Lock held 23:33:22–23:53:00, released by the driver (owner marker verified); R4T took it next — no overlapping Chromes.

| k | s | ΔRecalc | ΔLayout | style s | layout s | other s | RSS max MB |   | k | s | ΔRecalc | ΔLayout | style s | layout s | other s | RSS max MB |
|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 25.6 | 89 | 80 | 14.2 | 4.3 | 7.5 | 3,651 | | 17 | 32.4 | 84 | 76 | 14.5 | 10.2 | 7.9 | 5,786 |
| 2 | 19.8 | 84 | 76 | 8.6 | 4.6 | 7.2 | 3,847 | | 18 | 31.7 | 84 | 76 | 13.8 | 10.1 | 7.7 | 5,613 |
| 3 | 21.8 | 84 | 76 | 9.4 | 5.3 | 7.2 | 3,948 | | 19 | 36.4 | 84 | 76 | 12.8 | 14.5 | 8.5 | 5,209 |
| 4 | 23.5 | 84 | 76 | 10.3 | 5.3 | 7.3 | 4,099 | | 20 | 37.4 | 82 | 74 | 17.1 | 10.7 | 8.8 | 4,487 |
| 5 | 24.1 | 84 | 76 | 9.7 | 7.0 | 7.4 | 4,081 | | 21 | 40.8 | 86 | 78 | 17.8 | 14.8 | 8.7 | 4,881 |
| 6 | 25.0 | 84 | 76 | 11.9 | 5.9 | 7.4 | 4,130 | | 22 | 45.1 | 84 | 76 | 19.5 | 16.4 | 9.3 | 4,250 |
| 7 | 23.9 | 84 | 76 | 10.2 | 6.0 | 7.2 | 4,229 | | 23 | 44.1 | 84 | 76 | 16.2 | 18.1 | 8.7 | 4,454 |
| 8 | 30.3 | 84 | 76 | 15.4 | 7.4 | 8.1 | 4,090 | | 24 | 44.8 | 84 | 76 | 15.1 | 21.0 | 8.9 | 4,295 |
| 9 | 24.6 | 84 | 76 | 9.7 | 6.9 | 7.3 | 5,841 | | 25 | 45.8 | 84 | 76 | 23.5 | 12.6 | 8.7 | 3,887 |
| 10 | 27.9 | 84 | 76 | 12.6 | 7.4 | 7.6 | 4,980 | | 26 | 46.4 | 84 | 76 | 23.3 | 14.2 | 8.7 | 3,795 |
| 11 | 27.4 | 84 | 76 | 10.2 | 9.9 | 7.5 | 5,138 | | 27 | 47.3 | 84 | 76 | 23.2 | 14.6 | 8.9 | 3,737 |
| 12 | 27.3 | 84 | 76 | 12.5 | 7.7 | 7.5 | 5,400 | | 28 | 47.5 | 84 | 76 | 21.5 | 17.1 | 9.2 | 3,738 |
| 13 | 31.6 | 84 | 76 | 15.2 | 8.8 | 8.0 | 5,434 | | 29 | 50.6 | 84 | 76 | 18.5 | 21.4 | 9.5 | 3,885 |
| 14 | 29.9 | 84 | 76 | 14.4 | 8.5 | 8.0 | 5,627 | | 30 | 48.3 | 84 | 76 | 19.8 | 19.3 | 9.4 | 3,853 |
| 15 | 31.1 | 84 | 76 | 11.9 | 8.8 | 8.0 | 5,512 | | 31 | 53.5 | 82 | 74 | 22.5 | 17.9 | 10.2 | 3,637 |
| 16 | 29.5 | 84 | 76 | 12.8 | 8.6 | 7.5 | 5,583 | | 32 | 57.7 | 82 | 74 | 26.2 | 21.6 | 9.9 | 3,933 |

(style/layout/other = CDP RecalcStyleDuration / LayoutDuration / TaskDuration − both, nearest 1 Hz sample after each capture; "other" = paint, compositing,
animation servicing, GC outside style. ids: all 32 = reference. Total: RecalcStyle 494 s + Layout 367 s + other 265 s = 1,126 s of 1,133 s wall.)

RSS: renderer 1,796 MB before Run; during generation min 757 / median 3,424 / peak 5,841 MB (token 9); browser tree peak 6,276 MB; the saw-tooth amplitude
(2–4 GB within a token) is the Oilpan/V8 heap growing to the `--heap-growing-percent=10` limit and collapsing; peaks fall after token 20 (3.6–3.9 GB) while
time per token rises — memory is not the slope. LayoutObjects 169,471 → 177,788 (+260/token: the handshake's `display` toggles), Nodes unchanged.

## 3. Slope fit and attribution (step 3)

Fits over k=2..32 (rmse 2.6): **s/token = 16.3 + 1.141·k**; style = 7.2 + 0.485·k; layout = 2.6 + 0.538·k; other = 6.5 + 0.088·k; RecalcStyleCount =
84.3 − 0.02·k; LayoutCount = 76.3 − 0.02·k. Piecewise: tokens 2–18 slope 0.69 (style 0.30, layout 0.32, other 0.04); tokens 22–32 slope 1.11 (style 0.55,
layout 0.36, other 0.12); step +9 s between 18 and 22.

What grows per position p, and what it costs (constants: R3A 5 µs/element, 40 µs/changed carrier, 218–250 µs/transition start, 10.7 µs/live timeline/frame;
F5 5.7 µs per in-delay transition per style pass; 84 passes, ≈40 frames per token):

| population | per position | modelled s/token per position | evidence |
|---|---:|---:|---|
| in-delay KV latch transitions (26 × 12 layers) | +312 | 312 × 5.7 µs × 84 passes = **0.15** (style) | F5 §4 constant; 4.8 s/token at p=32 |
| filled V glyphs (768 rows × 12 layers), each a distinct 768-axis `font-variation-settings` instance (`var(--fr-v-S),"P000" var(--fw-H-S)`, the weight axis changes every pass) | +9,216 | style residual 0.485 − 0.15 = **0.34** → ≈36 µs per filled glyph per token; layout **0.54** → ≈58 µs per filled glyph per token (unfilled glyphs share one zero-list instance: a font-cache hit) | pass counts flat, so only per-element cost can grow; R3A's head shaping is 17.6 µs/row with a shared instance — a distinct instance per glyph (HarfBuzz face/instance creation + shaping) at ≈58 µs is plausible |
| filled score glyphs (12 heads × 12 layers), distinct K-list × query instance | +144 | included above (1.5 % of the glyph count) | |
| `--fr-*` alias declarations on the written bank | +26 | negligible (one element) | |
| changed carrier animations, transition starts, live timelines, frames | 0 | 0 | flat: 312 starts/token, 384 score timelines exist from the start |
| other (paint/compositing/GC) | | **0.09** | LayoutObjects +260/token; GC saw-tooth amplitude falls with p |

So ≈87 % of the slope is the **filled-glyph population** (style 0.34 + layout 0.54 of 1.14) and ≈13 % the latch transitions. The 19–22 step (style and
layout both jump, RecalcStyle/Layout counts unchanged) fits a **cache-capacity effect**: Blink's font-instance/shape caches hold a bounded number of
distinct variation instances; once the live set (≈24·p per layer × 12 = 288·p instances, plus the head's) exceeds it, instances are evicted and re-created
every pass. This is a hypothesis from the shape of the curve — a light trace of tokens 17–23 (`blink.fonts`, `FontCache::GetFontPlatformData`,
`HarfBuzzFace`) would confirm it. Codex's ctx32 bundle (v1: 4,005 B per V glyph rule with 64 duplicated Q axes, 48 latches/slot) had slope ≈2.9 for the same
populations — F2 (slim V rule) and F4 (packed latches) already cut the per-position cost 2.5×.

## 4. Feasibility for a demo (step 4)

- **Time**: 1,133 s for 32 tokens (≈19 min; 25.6 s to the first token after a 33 s load, 57.7 s for the last). Median 31.6 s/token. With a quiet machine
  ≈ −5–10 %. Codex's ctx32 run: 3,177 s.
- **Memory**: peak renderer RSS 5.84 GB / browser tree 6.28 GB (needs a ≥16 GB machine; the pinned run was 5.2 GB). Without the heap flag the saw-tooth would be
  smaller (fix 1 arm in round 1 measured GC at 3.5–16 % of a token) — a candidate for a B5 arm, not measured here.
- **Correctness**: 32/32 ids in Chrome, bit-identical to the NumPy reference and Codex's saved run.
- Verdict: a 32-token demo is feasible today with combined4-c32 at ≈19 min; the per-position slope makes tokens 25–32 cost 2–3× token 2.

## 5. Emitter changes that flatten the slope WITHOUT changing the model (predicted from §3)

1. **Unfilled V glyphs `display:none`** (capacity step, not slope): `@container fvscache style(--fv-S:0){.fvs-v-*-S{display:none}}` (the `--fv-S` fill flags
   already exist on `.fvs-score-reader`; the glyphs' `if(style(--fv-S:1)…)` weights already read them). Removes 768·(32−p)·12 leaves from every ctx pass
   (5 µs × 18,432 × 12 ≈ 1.1 s at p=1 plus their zero-list substitution and zero-advance shaping) → **≈ −1.1…−1.5 s/token at p=1, decaying to 0 at p=32,
   ≈ −20…−25 s total**; also makes c32 ≈ combined4 for the first 8 tokens. One layout-object creation per glyph when its slot fills (one-time). Exact.
2. **Move the softmax weight out of the variation instance**: `font-variation-settings: var(--fr-v-S)` only, weight via `font-size: calc(1024px * var(--fw-H-S))`
   (advance is linear in font-size; the row's `calc-size` decoder rescales by the same constant). Then every filled glyph's instance is fixed for the life
   of the slot (per layer) → font-cache hits across passes AND tokens instead of a fresh instance per pass; predicted **−0.3…−0.5 s/token per position**
   (most of the layout slope and part of the style slope; ≈ −40 % of 1.14). **Exactness-gated**: font-size × advance goes through LayoutUnit (1/64 px) once
   per glyph instead of the F2Dot14 axis quantisation; needs the 2-layer smoke + 32-token ids check (R3P: precision budget is thin).
3. **Per-head 64-axis V lists** (`--fr-v-S-H`, 1.5 KB) instead of substituting the packed 768-axis list (7.7–10 KB) into all 12 heads' glyphs: 12× fewer
   bytes parsed per filled glyph and a 64-axis instance key → **−0.15…−0.25 s/token per position** in style; costs +22 latches per slot per layer
   (+264·p × 5.7 µs × 84 = +0.13 s/position) unless combined with 4. Net ≈ −0.1 alone, ≈ −0.25 with 4.
4. **Latch filled slots as paused animations instead of in-delay transitions** (F5 §4: 0.3 µs/frame + 2.4 µs on restyle vs 5.7 µs on EVERY style pass):
   312·p × (5.7 − 2.4) µs × 84 → **−0.09…−0.12 s/token per position**; or at least stop re-resolving them by putting the banks under a display lock
   between their write and the next read (they are read every layer, so only the "lock filled slots" variant in F5's fixture applies).
5. (smaller) drop the 384 inlined 806-name `transition-property` literals (`F5_BANK_LITERAL_LISTS=0` → `var(--fvs-retained)`): 9.3 MB of sheet, parse-once;
   no per-token effect expected.
Predicted together (1+2+3+4): slope 1.14 → ≈0.5, intercept 16 → ≈15 → 32 tokens ≈ **780 s** (−30 %), first 8 tokens ≈ combined4's 18–19 s.

**Model change (separate decision)**: `--kv-window 8` (already implemented: ring slots, `kvWindow`/`kvSinks` in the manifest; `--kv-sinks` keeps the first
tokens) makes the page identical to combined4 in population → flat ≈18–19 s/token → 32 tokens ≈ **600 s**, RSS ≈ combined4's; ids diverge from the
full-causal reference after position 8 (the NumPy reference with `kv_window=8` would define the new target). `--kv-window 16` halves the slope terms.

## 6. Notes

- The run was contended (load 6–10, other agents compiling); this is not a paired timing row — B5 should pair c32 vs combined4 (first 8 tokens) if the
  capacity step matters for the plan.
- `summarize32.py`'s metric deltas use the nearest 1 Hz `Performance.getMetrics` sample after each capture (samples lag while the main thread is busy):
  per-token counts are exact to ±1 pass; durations ±0.5 s.
- `slope_model.py` (per-token fits and the modelled terms) is reusable for any capacity-32 run JSON.
