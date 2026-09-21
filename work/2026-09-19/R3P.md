# R3P — round 3: pack two values per view-timeline carrier (exactness gate) — 2026-09-20

Agent R3P. Offline only (NumPy; no Chrome, no lock taken, no bundle, no tools copy). Files: `work/2026-09-19/R3P/gate_sim.py`
(browser-numerics re-implementation with per-hop hooks), `gate_results_font.json` / `gate_results_dyn.json` (all runs, per-token head margins),
`gate_font.out` / `gate_dyn.out` (console tables). Log: `R3P.log.md`.

## 0. Verdict

**No hop survives the exactness gate; stopped after §1 as instructed.** At k = 12 (the only field width that fits one carrier width and one
typed `<number>`) every arithmetic hop flips at least one of the 8 token ids or is a font-published hop that cannot be packed at its publisher.
At k = 14 the loop/bridge ids survive only with a per-pass dynamic full scale and at final-residual RMSE 0.052–0.054 vs 0.0201 today (×2.6)
— the class of degradation for which Codex's packing was rejected (S1: 0.0073 → 0.0454) — and k = 14 × 2 = 28 bits/timeline exceeds the
measured single-coordinate ceiling (14 exact bits), so it would need two animations per timeline anyway (the 40 µs/changed-animation and
28 µs/pending-add terms of R3A's model would not halve). Predicted gain of the best lossy variant ≈ −2.0 s/token, not −3.5 to −5.

## 1. Exactness gate

### 1.1 What each carrier is today (bundles/combined3; counts = `view-timeline:` declarations in index.html, 10,858 total)

| hop | carriers | publisher | width the timeline measures | progress → number | consumer (class) |
|---|---:|---|---|---|---|
| qkv | 2,304 + 1 | **font**: 3 shard glyphs (256 axes each) at 512 px in one `i.metric`; advance_i = base_i + Σ_j codes_ij·x_j, x_j = `--fq-qkv-j` = n1_j / range (F2Dot14 in the font) | Σ advances (float px), viewport 65,536 | keyframes 0→1; `--qkv-i:calc(((65536/var(--qkvp-i) − 65536)·1000/512 − base_i)·scale_i·var(--range-qkv) + bias_i)` | K,V → `--fvn-{k,v}` = qkv/ks → **font axis** (F2Dot14, 15 bits + sign); Q → `--fq-q` axis; ks/vs/fqs → numbers (b) |
| scores | 96 + 1 | **font**: bilinear FvsDot_h glyph, 468 units per Q·K unit, base 29,984 units | `calc-size(max-content, 262144px + (size − 15351.808px)·fqs·ks·0.0668)`, viewport 524,288 | keyframes −2→1; `--fs-h-s:calc((1572864/(var(--fsp)+2) − 786432)/128)` | softmax numbers `--fe/--fd/--fw` → P000 axis (14 bits) (b) |
| ctx | 768 + 1 | **font rows**: Σ over 8 slots of FvsValue glyphs (12,000 units per V·w) | `calc-size(max-content, 262144px + (size − 98566.144px)·fb/fd·0.0104)` | −2→1, same decode → `--ctx-i` | `--fq-attn` = ctx/range → **font axis** (15 + sign) (a) |
| attn | 768 + 1 | **font**: 3 shard glyphs | as qkv | 0→1; `--r-i:calc(var(--x-i) + …)` | residual add (b) |
| fc | 3,072 + 1 | **font**: 3 shard glyphs | as qkv | 0→1; `--fz-i` → `--ft-i` → `--hidden-i` (GELU numbers) | `--fq-proj` → **font axis** (15 + sign) (a) |
| proj | 768 + 1 | **font**: 12 shard glyphs | as qkv | 0→1; `--out-i:calc(var(--r-i) + …)` | residual add (b) |
| loop | 2 × 769 | **number** `--saved-b-i` (latched by 86,400 s transitions, 769 names per bank) | `calc(262144px + var(--saved-b-i)·128px)`, viewport 524,288 | −2→1; `--loop-in-i:calc((1572864/(var(--lp-b-i)+2) − 786432)/128)` | `--x-i` → LN Σ/Σ² (b) |
| bridge | 768 + 1 | **number** `--out-i` (layer 11) | same as loop | −2→1; `--x-i` on `#core-result` | final LN → head axes (b) |
| (embedding 768 + 1, feedback 8) | | not per-layer; out of scope | | | |

Only **loop and bridge are packable at the publisher** (a CSS number can be rounded and combined before it becomes a width). The six font
hops publish a *continuous* glyph advance: two 16-bit-class advances cannot be separated after summing into one inline box (31 LayoutUnit bits
< 32 + guard), a `calc-size(round())` radix trick would still push > 14 bits through one width, and the 6-digit progress serialisation caps a
single coordinate at ≈ 14–16 exact bits (below).

### 1.2 Precision delivered today (derivation + repo measurements)

1. **Width**: `Length`/`PixelsAndPercent` hold float32 → 24-bit mantissa; at 2^18–2^19 px the spacing is 1/32–1/16 px (LayoutUnit's 1/64 px
   is finer, not binding) ⇒ on the number hops v is resolved to 1/4096–1/2048; on the font hops the Σ-advance px is resolved to 1/512 px
   (≈ 0.004 units) — never binding.
2. **Progress → number**: the view-timeline progress is a double, but the animated registered `<number>` reaches the consumer's `calc()` as
   its serialisation, **6 significant digits** (the Chrome readback in `R2H/run-combined3/verification-vectors.json` is 6-digit; S1 F5:#489
   "rounded to 6 sig digits"; E1 "typed `<number>` > 24-bit packets corrupt"). Number hops: a = −2 + 3p is ≈ 0 at v = 0 (the −2 offset centres
   the fine region), so dv ≈ 3V/(a+2)²·10⁻⁶/128 ≈ 2.4·10⁻⁴ at small |v| (float width binds) rising to 0.003–0.006 at |v| = 1,000–3,000
   (|out| reaches 3.0·10³ in layers 2–10, see `gate_font.out` ranges). Font hops: p ≈ 0.7–0.8 ⇒ 0.03–0.11 px ⇒ 0.06–0.2 units of a
   ±30–50 k-unit scale.
3. **Measured channel ceiling** (Chrome 153, `experiments/guarded-timeline-capacity/browser-results.json`, 2026-09-15): **14 exact payload bits per
   geometric coordinate** (192/192 at every guard), 15 bits 191/192, 16 bits 177–183/192, 20 bits 32–45/192; `experiments/packed-timeline-precision/RESULTS.md`:
   two 8-bit digits in one width 48/48 exact, two 9-bit 39/48, **two 12-bit 4/48 (max error 72)**; "4 values per timeline" there = 2 digits × 2
   geometric coordinates (subject position and width, i.e. two animation ranges = two animations).

**Bits preserved today**: font hops ≈ 16–18 bits of their units scale (value continuous, transport noise ≈ 0.1 unit rms); number hops ≈ 20 bits
(6 digits). A 2-per-carrier field is ≤ 14 bits through a second coordinate, ≤ 12 through a single width/typed number — 2^6–2^8 coarser than today.

### 1.3 Calibration of the NumPy model against the Chrome run (final residual RMSE vs the quantised-weights reference; Chrome = 0.0201, KV 0.0028–0.0039)

| model term(s) | RMSE | KV RMSE | note |
|---|---:|---:|---|
| ideal (= `reference_sequence`) | 0 | 0 | ids = expected, float winners = expected; head margins [24,126,125,**4**,22,50,186,87] |
| F2Dot14 axes only | 0.0037 | 0.0004 | |
| 1/64-px advance snap only | 0.0011 | 0.0001 | |
| 6-digit typed numbers only | 0.0001 | 0.0000 | |
| float32 width + 6-digit progress on number hops only | **0.0106** | 0.0011 | largest modelled term today |
| same with full-precision progress | 0.0012 | 0.0001 | (if var() substitution were exact) |
| **TODAY** = axes + adv64 + sig6 + w32(p6) | **0.0113** | 0.0011 | margins [23,126,124,6,23,50,188,88] |
| TODAY + whole-unit advance rounding per shard glyph | 0.0965 | 0.0087 | 5× Chrome ⇒ Chrome's HVAR advances are not integer-rounded; excluded |

The model explains ≈ half the browser's residual noise (the rest is font-engine-internal rounding between 1/64 px and 1 unit); the gate does not
depend on it because every packing configuration below adds ≥ 2.5× Chrome's *whole* observed error.

### 1.4 Packing simulation — one hop at a time, k-bit uniform fields (ids identical? / float agreement / final-residual RMSE vs q-reference)

`font` scale = compile-time full scale (the font's max |units| = Σ|codes| + 32 per row; ±2,048 for the number hops); `dyn` = per-pass max|v| × 1.001
(realisable only for the number hops, like `--range-*`; a font's output scale is fixed by its codes).

| hop (scale) | k = 10 | k = 12 | k = 14 | k = 16 | k = 18 |
|---|---|---|---|---|---|
| qkv (font) | ✗ 1.51 (tok 4→407, 5→284) | ✓ 0.362 | ✓ 0.153 | ✓ 0.028 | ✓ 0.0077 |
| scores (font) | ✓ 0.184 | ✓ 0.046 | ✓ 0.010 | ✓ 0.0044 | ✓ 0.0008 |
| ctx (font) | ✓ 0.171 | ✓ 0.045 | ✓ 0.011 | ✓ 0.0027 | ✓ 0.0006 |
| attn (font) | ✓ 0.326 | ✓ 0.074 | ✓ 0.017 | ✓ 0.0043 | ✓ 0.0013 |
| fc (font) | ✗ 0.996 (tok 1→12, 6→314) | ✗ 0.224 (tok 1→198, 4→407) | ✓ 0.062 | ✓ 0.018 | ✓ 0.0047 |
| proj (font) | ✗ 3.37 | ✗ 0.997 (tok 4→407) | ✓ 0.213 | ✓ 0.055 | ✓ 0.014 |
| loop (fixed ±2,048) | ✗ 18.1 | ✗ 1.65 (tok 1→13, 4→407) | ✓ 0.369 | ✓ 0.116 | ✓ 0.024 |
| loop (**dyn**) | ✗ 0.297 (tok 1→13, 4→407) | ✗ 0.187 (**tok 1→13**) | ✓ 0.052 | ✓ 0.013 | ✓ 0.0036 |
| bridge (fixed ±2,048) | ✓ 1.16 | ✗ 0.285 (tok 4→407) | ✓ 0.069 | ✓ 0.018 | ✓ 0.0045 |
| bridge (**dyn**) | ✓ 0.170 | ✓ 0.042 | ✓ 0.011 | ✓ 0.0027 | ✓ 0.0007 |

Combined with TODAY's transport noise: loop k14 dyn **0.0535** (margins [12,127,126,13,20,52,186,90]); + bridge k14 dyn 0.0538; loop k12 dyn ✗
(11→13); attn+ctx+scores k14 font 0.0255; + loop/bridge k14 dyn 0.056; all hops k14 0.222 (ids ✓ by luck, tok-4 margin 20); all hops k12 ✗.
Float agreement tracks ids in every row (float winners = expected). Full tables in `gate_font.out` / `gate_dyn.out`.

**Margins**: the pinned run's token 4 (7926 vs 407) is **4 integer q-score units** from a flip in the ideal reference (6 in TODAY); every
perturbation ≥ 0.1 rms flipped it or token 1 (11 → 13, margin 24). The k = 14 configurations keep the ids with margins of 5–13 — not a robustness
statement, one rounding step.

### 1.5 Verdict per hop

| hop | packable at publisher | consumer | minimum k for identical ids | RMSE at k = 14 (today 0.020) | gate |
|---|---|---|---|---|---|
| qkv | no (font) | (a) axes 15 + sign | 12 (0.36) | 0.153 | ✗ |
| scores | no (font) | (b) | 10 | 0.010 | ✗ (publisher; 97 carriers = 0.9 %) |
| ctx | no (font rows) | (a) 15 + sign | 10 | 0.011 | ✗ (publisher) |
| attn | no (font) | (b) | 10 | 0.017 | ✗ (publisher) |
| fc | no (font) | (a) via GELU | 14 | 0.062 | ✗ |
| proj | no (font) | (b) | 14 | 0.213 | ✗ |
| loop | **yes** (number) | (b) LN | 14 dyn (12 flips token 1) | 0.052 (×2.6) | ✗ not exact; needs 28 bits/timeline |
| bridge | **yes** (number) | (b) final LN | 12 dyn | 0.011 (k12: 0.042) | ✗ at ≤ 12 / tolerable at 14 — 768 timelines once per token (−0.19 s) |

No consumer has ≤ 12–14 useful bits: the font-axis consumers are F2Dot14 (15 bits + sign relative to a per-head/per-pass max) and the values
feeding them carry 16–20 bits today.

### 1.6 R3L item 3 folded in (coordinator input, after the first draft): 6-significant-digit var() substitution

R3L measured what §1.2 (2) assumed: Blink substitutes a registered `<number>` into `var()` as text with 6 significant digits (R3L's exact model of the
1,538 loop readbacks: 0/768 mismatches at 6 digits, 5 at 7; R3L's packed variants decoded to garbage). Consequences for 2-per-carrier packing:

- (a) *"decode where the value is still geometry, or move it as a `*` token list"* — not available on a view-timeline carrier. The only way a timeline
  progress becomes a value is an **animation of a registered property**, and an animatable syntax (`<number>`, `<integer>`, `<length>`) is exactly what
  gets re-serialised on substitution; `*` is not interpolable, so it cannot be the animated output; and `calc-size()`/container units on the consumer
  cannot see the publisher's geometry (that is why the timeline exists). Hence every 2-per-carrier field passes through one 6-digit substitution.
- (b) *"each field ≤ what survives 6 digits of the decoded value"* — with one animation per carrier the decoded number is one `<number>` a ∈ (−2, 1):
  ≈ 20 bits total, ≤ **10 bits per field**, and only ≈ 14 bits are *exactly* recoverable as an integer (guarded-timeline-capacity). §1.4 at k = 10:
  qkv ✗, fc ✗, proj ✗, loop ✗ (both scales); scores 0.18, ctx 0.17, attn 0.33, bridge 0.17 keep the ids but at 8–16× today's RMSE and are
  font-published (except bridge). Getting to 14 bits per field needs the second geometric coordinate = a second animation (§2 (3)).
- Under R3L's finding the verdict of §1.5 is unchanged and stricter: no hop is exact at ≤ 10 bits/field, and no hop is exact at 14.

Lock rule (R3L item 10): this agent never created or removed `CHROME.lock`; any future R3P Chrome step would `cat CHROME.lock/owner` and only `rmdir` its own.

## 2. Decision

Stopped after §1; nothing under `R3P/tools`, no bundle, no Chrome. Reasons: (1) k = 12 — the only packing that fits one width and one typed
`<number>` < 2^24 — is not exact on any hop (loop/bridge flip a token; font hops cannot be packed at the publisher); (2) k = 14 keeps the ids only
with a per-pass dynamic scale, at RMSE ×2.6, on a run whose own head margin is 4; (3) k = 14 × 2 = 28 bits/timeline is above the measured
14-bit single-coordinate ceiling, so it costs two animations per timeline — only R3A's 10.7 µs/frame per-timeline term halves, not the 40 µs
changed-animation or 28 µs pending-add terms (5.7 s/token together); (4) E4 §4's warning ("offline-good encodings blew up after transport") applies:
the two-12-bit-digit width measured 4/48 exact in Chrome.

## 3. For the record: the best lossy variant (not built)

Loop + bridge only, k = 14, dynamic full scale S = max|out| × 1.001 (a 768-term `max()`, as `--range-*`). Publisher: `--saved-b-j` registered
`<integer>` (exact to 2^31, S1 F5:#1544) = round((v_{2j}+S)/(2S)·16383)·16384 + round((v_{2j+1}+S)/(2S)·16383) plus `--saved-b-S`; carrier = a
fixed 32,768 px inline-block cell holding a spacer of `mod(field,16384)` px and the subject of `round(down, field/16384)` px; **one** view-timeline,
**two** animations (`animation-range: entry …` reads the position field, `exit …` the width field; keyframes 0→16383 on `<integer>` properties so each
14-bit field returns as an exact integer — the measured 192/192 regime). Predicted with R3A's coefficients: timelines 10,858 → 9,705 (−1,153 ×
10.7 µs × 46 frames = **−0.57 s/token**); loop-bank latch transitions 769 → 385 per layer (−384 × 12 × 314 µs = **−1.45 s/token**, needs the
`<integer>` latch to transition like a number); animations/pending adds unchanged; total **≈ −2.0 s/token** at RMSE ≈ 0.054 and three unverified
Chrome facts (integer-typed animation on view timelines, entry/exit progress exactness, spacer + subject LayoutUnit geometry). If ever pursued: a
30 s fixture under the lock first, and the 8-token verify must be re-run — the ids are one rounding step from a flip.

## 4. Method / caveats

- `gate_sim.py` mirrors the emitter's numerics (`build_hybrid_twelve_block.matvec`, `browser_gpt2_font_vector_cache` value rows, `reused_core`
  loop decode): per-row `--range-*` = max|x| × 1.001, 9-bit per-row weight codes (`quantize_float_rows`), K/V/Q/V-row axis normalisation by
  per-head/per-slot maxima, softmax as in the CSS, GELU tanh form, the exact decode constants read from `bundles/combined3` (65,536 / 524,288
  viewports, 0→1 and −2→1 keyframes, FvsDot 468 units per Q·K, FvsValue 12,000 units per V·w). kv_window 8, sinks 0 (manifest). Runtime 13 s per
  ≈ 60 configurations.
- The 6-digit substitution assumption affects only the "today" row (0.0113 vs 0.0044 with full-precision progress); every packing verdict is
  identical under either assumption because packing noise ≥ 0.05 dominates.
- Only the pinned 8-token run was simulated (the gate as defined); a different prompt could have wider or narrower margins.
