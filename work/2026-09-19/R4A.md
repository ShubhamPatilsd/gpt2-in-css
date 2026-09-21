# R4A — can fc → GELU → proj be fused into one font evaluation per layer without leaving the precision class? (2026-09-20)

Agent R4A. Offline only: NumPy + fontTools, no Chrome, no lock, no bundle. Files: `work/2026-09-19/R4A/fused_sim.py` (R3P's
`gate_sim.py` as base; the fc hop + CSS GELU + proj hop replaced by the fused font), `fused_full.out` / `fused_results.json`
(all runs), `build_fused_font_probe.py` + `font_probe.out` (a real 769-axis fused font built with fontTools to calibrate table
sizes), `cost_table.md`. Log: `R4A.log.md`.

## 0. Verdict

**Structurally: the boundary is removable only by a font that receives all 768 LN2 outputs as axes, which Chrome's stock backend
rejects (256-axis cap, 257 rejected) and only the Fontations backend accepts (auto-selected when the font carries an `avar` v2 table).
Numerically: exact-class is reachable (ids 8/8 + float agreement, RMSE vs the float model 0.046 vs TODAY's 0.082) — but only with
K ≥ 48 GELU hat regions per hidden axis, a two-level (coarse + fine) glyph per output to get around the int16-delta/advance budget, and
compile-time (non-dynamic) input and pre-activation scales that add a clamp hazard for unseen prompts. Cost: ≈ 100 MB of variation
tables per font (≈ 15 GB raw over 12 layers) and, at the Fontations evaluation rate measured by the repo's own 768-axis probe
(1–3 ns per glyph × region × axis), 200–600 s per layer per token against a hop worth 0.35 s/layer.** The lever R3A §5 #2 valued at
−3 to −4 s/token does not exist on Chrome 153: **the −3 to −4 s estimate is wrong** because it priced the removed hop at zero
replacement cost. Recommendation: leave the pipeline at ≈ 19 s/token (R3R) and drop fusion from the round-4 list. Details below.

## 1. Formulation and what a fusion can and cannot remove

Per layer (R3R §1.1 hops 5–7, combined3/R3R): `--r` (numbers) → LN2 numbers `n2` (768) → `--fq-fc-j = n2_j / --range-fc` (768 axes in
3 × 256-axis fc shard fonts) → **3,073 fc carriers** (glyph advances, geometry) → view-timeline readback → `--fz-i` numbers → CSS
`--gelu()` → `--hidden-i` → `--range-proj`, `--fq-proj-j = hidden_j / range` (3,072 axes in 12 × 256-axis proj fonts) → 769 proj
carriers (geometry) → readback → `--out`. Two geometry→number boundaries (fc, proj). h = GELU(A·x + b) is 3,072-wide, y = B·h.

Facts that bound every formulation (spec + repo measurements):

- A font's variation machinery (`avar`, `HVAR`, `gvar`, `MVAR`) consumes only *its own* normalized axis coordinates, set from CSS
  `font-variation-settings` numbers. One font's glyph advance can reach another font only through a CSS number, i.e. a readback hop
  (S2 S-04b `:1009`: "avar2/HVAR/gvar/MVAR consume the face's own coordinates, never another font's result"; `anchor-size()` /
  `calc-size()` inside `font-variation-settings` compute to `normal`, E1 #6).
- GELU is not separable over input shards: GELU(a + b + c) ≠ f(a) + g(b) + h(c) (E1 #25). Hidden-dimension sharding *is* separable
  (y = Σ_shards B_s · GELU(A_s x + b_s)), which is what Codex's 12 × 256-hidden groups exploit — but each group still needs all 768 x.
- avar2 is a single stage: coordinates' = clamp(coords + Δ(coords)), Δ a VarStore driven by the (segment-mapped) *input* coordinates.
  It can express one dense affine map A·x (2 linear regions per input axis, F2Dot14 coefficients, output on the F2Dot14 grid) or one
  per-axis piecewise-linear map (hat regions at knots), not both in sequence. The output has the same axis count as the input, so
  **hidden units per font ≤ axisCount**. A nonlinearity of a *sum* must therefore live in HVAR (hat regions on the avar2-remapped axes),
  where each output glyph needs one int16 delta per (hidden axis, knot).
- HarfBuzz/Fontations region rule: a hat whose support straddles 0 with peak ≠ 0 evaluates to 1; 0 must be a knot (its delta is
  GELU(0)·B = 0, harmless). Knot positions are F2Dot14.
- Axis count: stock backend accepts 256, rejects 257 (`experiments/matrix-scaling/RESULTS.md`; `browser-gpt2/font-backend-probe/results.json`:
  257/768 `accepted:false`, fallback to Times). The same probe shows the **Fontations** backend (Chromium `web_font_typeface_factory.cc`
  routes any avar v2 font to it, revision 199a3a54…) accepts 257 and 768 axes, at 25–43 ms (257) and **462–1,352 ms (768) per changed
  state** for a *linear* 768 × 768 font, with **0.31–0.52 design-unit** max error (integer-rounded advances) vs 0.026–0.030 on the stock
  backend. All of Codex's avar2 fonts already ran on Fontations.

### 1.1 Options

| # | formulation | removes a geometry→number boundary? | why / cost |
|---|---|---|---|
| (i) | today: fc fonts (3 × 256 axes) → 3,073 carriers → CSS GELU → proj fonts (12 × 256 axes) → 769 carriers | — (2 boundaries) | the fc boundary exists because the GELU argument is a *sum over three shards* that only exists as geometry |
| (ii) | Codex's "sparse-diagonal avar2 GELU + linear HVAR" proj fonts: the 12 proj fonts take the 256 fc pre-activations `fz` as axes, map each through K hats in avar2, then linear HVAR B | **no** | the proj font's axes are CSS numbers; `fz` is a glyph advance of the fc fonts → the fc readback hop stays (F4's `*`-list latch moves numbers, not geometry; inheritance moves numbers). What is removed is only the CSS `--gelu()` evaluation + 3,072 `--hidden` numbers: in R3A's model these sit inside the `784` pass's 3,072 × 30 µs changed-animation term and the ≤ 0.5 s/token var()/calc residual → **≤ 0.1 s/token**. What is added: the proj fonts move to Fontations (integer advances, +0.027 RMSE by the sim's F6 term alone) and the K-hat GELU error (Codex: 0.059 max model error) — net negative under R3P's gate |
| (iii) | true fusion: a font that has **all 768 `n2` as axes** (+1 constant axis for `b`), avar2 computes a slice of A·x + b onto its own axes, HVAR applies GELU hats × B and emits proj partial sums as advances; N fonts per layer, each with 3,072/N hidden units; one carrier per output with N glyphs (as today's 12 shard glyphs) | **yes** — the fc boundary and the 3,073 fc carriers disappear; 6 → 5 hops/layer | needs ≥ 769 axes → Fontations only; N = 4 (768 hidden/font) or N = 12 (256 hidden/font) both need 769 axes per font. Numerics §2, cost §3 |
| (iv) | put GELU into the fc *carrier* (`calc-size(max-content, …)` with `exp/tanh`) or into the fc font | no | the carrier width is still geometry; the proj font needs numbers → hop unchanged (and the fc font cannot apply GELU to the cross-shard sum) |
| (v) | replace the fc view-timeline readback by container-query units / anchors (Codex's paired width/height captures) | no | a different *carrier primitive* for the same boundary (a layout → style dependency is still one pass); out of R4A's scope — it is the "lower-cost carrier primitive" item of RESULTS-round3 |
| (vi) | retrain the MLP as 12 disjoint 256-in/256-hidden groups (E1 #50) or compress x to ≤ 256 axes | no (lossy) | 48 % held-out error (#50); x has no exact 256-dim representation |

So: **only (iii) removes the boundary, and only on the Fontations backend.** Everything with ≤ 256 axes per font keeps the fc hop, and
the R3A lever-2 saving (`784` pass 107 ms + re-applied fc anims 68 ms + ½ frame 58 ms + 3,842 pending adds 108 ms + fc-carrier layout
≈ 60 ms ≈ 0.4 s/layer traced ≈ 0.35 s untraced) is available only if (iii)'s replacement cost is below that.

## 2. Accuracy model of (iii) — `R4A/fused_sim.py`

The simulator is R3P's `gate_sim.py` (TODAY = F2Dot14 axes + 1/64 px advances + 6-digit numbers + float32 width / 6-digit progress;
calibrated at 0.0113 RMSE vs Chrome's 0.0201) with the fc/GELU/proj section replaced by the fused font. Error terms, each switchable:

| term | what the font forces | modelled as |
|---|---|---|
| F1 | no dynamic `--range-fc`: a nonlinearity follows, so the input scale is compile-time. Per input dim `R_j` (a per-axis constant is free — the coefficient absorbs it) | `R_j = margin × max_t|n2_j|` over the pinned run (per layer); clamp to [−1, 1]; F2Dot14 |
| F2 | avar2 coefficients `a_ij = A_ij R_j / S_i` are int16 F2Dot14 (|a| < 2 unless LONG_WORDS) | `rint(a·16384)/16384`; bias via a constant-1 axis |
| F3 | pre-activation coordinate `z_i / S_i` rounded to F2Dot14 and clamped; `S_i` compile-time per hidden unit | `S_i = margin × max_t|z_i|`, min 6 |
| F4 | GELU as K hat regions per hidden axis (piecewise-linear); knots on the F2Dot14 grid of `S_i`; 0 is a knot; end knots ±S_i | curvature-equidistributed knots on [−6, 6] (density ∝ √|GELU″|) or uniform; exact at knots, linear between |
| F5 | HVAR deltas `D = rint(s_o B_oi GELU(knot))` int16; the glyph row's range Σ_i |B_oi|·max|h_i| must fit the advance budget (`safe_base_advance`: base + max ≤ 65,535 → 32.7 k units) → `s_o` = 32,700 / Σ_i |B_oi| |GELU(S_i)| ≈ **9–13 units per value** | interpolation of rounded knot deltas; optional **two-level glyph**: coarse int deltas + a second glyph at 1/64 font-size carrying `rint(64·(exact − coarse))` (|F| ≤ 32 units, fits) |
| F6 | Fontations integer glyph advances (probe: 0.31–0.52 unit max error) + TODAY's carrier transport (N glyphs summed in one inline box; float32 width, 6-digit progress) | `rint` per glyph, `adv64`, `w32(p6)` as `font_dot` |

Calibration (ideal path, per layer max): |n2| 2.3–19.8, |z| 5.5–62.6 (layer 2 is the outlier). Reference: the fused font uses A and B
as F2Dot14 / int16 values, not the 9-bit codes of the quantised reference, so its distance to `qref` (0.07) is mostly a *different*
weight quantisation; the fair comparator is the float model (`rmse_f`), against which TODAY sits at 0.082. Gate = ids identical +
float-winner agreement on the 8 pinned tokens (R3P's gate).

### 2.1 Results (`fused_full.out`; 12 × 256 = 12 fonts of 256 hidden units, each 769 axes; 4 × 768 where stated)

| configuration | ids | float | rmse vs qref | **rmse vs float** | max vs float | min margin |
|---|---|---|---:|---:|---:|---:|
| ideal (= qref) | ✓ | ✓ | 0 | 0.0806 | 0.486 | 4 |
| **TODAY** (R3P model) | ✓ | ✓ | 0.0113 | **0.0818** | 0.432 | 6 |
| fused, float everything, exact GELU, dynamic scales (bound) | ✓ | ✓ | 0.0716 | 0.0393 | 0.283 | 6 |
| fused exact GELU, fixed 2× per-dim scales, no font quantisation | ✓ | ✓ | 0.0738 | 0.0429 | 0.217 | 7 |
| + F2 coef14 only / + F3 coord14 only | ✓ | ✓ | 0.071 / 0.075 | 0.041 / 0.042 | | 7 / 5 |
| + F6 integer advances only | ✓ | ✓ | 0.0731 | 0.0494 | 0.326 | 6 |
| + all of F1–F3, F6 (exact GELU) | ✓ | ✓ | 0.0769 | 0.0494 | 0.291 | 12 |
| same, 4 × 768 fonts | ✓ | ✓ | 0.0830 | 0.0591 | 0.352 | **2** |
| K = 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96, single glyph (F5 int16 at s_o ≈ 13) | ✗ ✗ ✗ ✗ ✗ (✓) ✗ ✗ | | 0.94 / 0.54 / 0.39 / 0.32 / 0.29 / 0.34 / 0.33 / 0.29 | | | tok 4 → 407 at every K (K = 48 survives by 1 q-unit) |
| K = 8 / 12 / 16, GELU-only (no font quantisation) | ✗ ✗ ✗ | | 0.90 / 0.46 / 0.29 | | | tok 4 → 407 |
| K = 24 GELU-only / **two-level** | ✓ / ✓ | ✓ / ✓ | 0.112 / 0.109 | 0.100 / 0.098 | 1.04 / 1.01 | 6 / 5 |
| K = 32 GELU-only / two-level | ✓ / ✓ | ✓ / ✓ | 0.089 / 0.094 | 0.068 / 0.072 | 0.73 / 0.69 | 5 / 5 |
| **K = 48 two-level** | ✓ | ✓ | 0.0747 | **0.0461** | 0.285 | 9 |
| K = 64 two-level | ✓ | ✓ | 0.0744 | 0.0481 | 0.331 | 11 |
| K = 96 two-level | ✓ | ✓ | 0.0782 | 0.0476 | 0.266 | 9 |
| K = 32 / 64 uniform knots on [−6, 6], two-level | ✗ / ✓ | | 0.49 / 0.155 | | | curvature knots are ≈ 4× more efficient |
| K = 32 two-level, margins 4× (R_j, S_i = 4 × pinned max) | ✓ | ✓ | 0.109 | 0.087 | 0.91 | 9 |
| K = 32 / 64 two-level, margins 1.05× · global-per-layer input scale · zc = 8 | see `fused_full.out` (§2.3) | | | | | |

Reading:

1. **With exact GELU the fusion is in class** — closer to the float model than TODAY (0.049 vs 0.082) because A and B enter as
   F2Dot14/int16 instead of 9-bit codes; the F6 integer advances add ≈ 0.027 rms by themselves and the fixed scales (F1/F3) ≈ 0.01.
   The 4 × 768 layout is worse (margin 2) because 768 hidden units per glyph row push `s_o` down to 9 units/value.
2. **The K-hat GELU needs K ≥ 24 to keep the ids, K ≥ 48 to add nothing measurable** (0.046 at K = 48 vs 0.049 exact; the hat
   interpolation error ≤ h²/8·max|GELU″| ≈ 0.4·h²/8 → with the curvature-optimal spacing h ≈ 0.25 at K = 48 gives ≈ 3e-3 per hidden
   unit, negligible after B). Uniform knots need ≈ 2× more.
3. **F5 is fatal for a single glyph per output**: the int16 deltas are fine (15 bits), but the advance budget forces the row scale to
   ≈ 13 units per value because the row must cover the worst case Σ_i |B_oi|·|GELU(S_i)| (S_i is fixed at 2× the pinned max, and
   |y| ≪ that bound); the 0.29-unit rounding of each of 3,072 knot deltas gives ≈ 0.3 RMSE at any K and flips token 4. Today's proj codes
   escape this because `--range-proj` is dynamic (256 inputs per glyph, x normalised to the actual max each pass). The two-level glyph
   (coarse + 1/64 fine glyph, same regions, 2× glyphs and 2× HVAR deltas) removes F5 entirely (two-level ≡ GELU-only at every K).
4. **New hazard class**: `R_j` and `S_i` are compile-time. With margin 2× the pinned run clips 0 % of values; a prompt with
   |n2_j| > R_j or z_i > S_i is clamped (z > S_i loses the linear tail, error z − S_i). Today's dynamic ranges have no such failure
   mode. Widening the margins to 4× costs 0.087 vs 0.046 (F1/F3 grid coarsens with the scale). Exactness on *unseen* prompts therefore
   cannot be guaranteed by construction, only by calibration on a corpus — a second reason the gate is not "exact-class" in R3P's sense.

### 2.2 Precision of the mechanisms (spec / measured)

- avar2 coefficients: F2Dot14 int16 (|a| < 2; with per-dim `R_j` the max is 1.96; a global per-layer input scale needs coefficients up to
  20 → `LONG_WORDS` int32 deltas, allowed by the spec). Output coordinates F2Dot14, clamped [−1, 1].
- HVAR: regionCount uint16 ≤ 65,535 → 256 hidden × K ≤ 65,535 ⇒ K ≤ 255 (12 × 256 layout) or K ≤ 85 (4 × 768); VarData
  regionIndexCount / itemCount uint16 — fine. Deltas int16 (int32 with LONG_WORDS). Chrome 153 accepted 28 hat regions per axis on
  256 axes in Codex's group fonts (7,168 regions) and 16 per axis in the tile; nothing in the spec or the probes suggests a lower
  region cap than 65,535, but no probe exercised 13,825 regions × 769 axes (§3).
- Fontations advances are integer design units (probe 0.31–0.52 max error) — the F6 term; the stock backend's 0.03 is not available
  above 256 axes.
- fontTools builds the 769-axis fused font without complaint (`font_probe.out`: 769 axes, avar2 1,537 regions × 256 rows, HVAR 2,048
  regions × 64 glyphs → avar 7.89 MB, HVAR 9.72 MB, exactly the analytic model; WOFF2 0.66 MB, 27× on this region-list-dominated case).

### 2.3 Sensitivity rows (all 12 × 256, two-level, curvature knots; ids ✓ and float ✓ in every row)

| variant | K = 32: rmse vs qref / vs float / min margin | K = 64: rmse vs qref / vs float / min margin |
|---|---|---|
| baseline margins 2× per-dim | 0.094 / 0.072 / 5 | 0.074 / 0.048 / 11 |
| margins 4× (safer clamp headroom) | 0.109 / 0.087 / 9 | 0.082 / 0.059 / 4 |
| margins 1.05× (no headroom — unrealisable for unseen prompts) | 0.098 / 0.074 / **2** | 0.079 / 0.057 / 7 |
| global per-layer input scale (coefficients up to 20 → needs LONG_WORDS) | 0.099 / 0.075 / 6 | 0.075 / 0.053 / 7 |
| knot range zc = 8 instead of 6 | 0.093 / 0.068 / 5 | 0.076 / 0.045 / 9 |
| uniform knots on [−6, 6] | 0.490 / 0.492 / ✗ (tok 4 → 407) | 0.155 / 0.146 / 3 |

The margins move the ids' safety by ±5 q-units at K = 32 and the RMSE by ±0.02; none of the variants changes the conclusion that K ≈ 48–64
two-level is needed for TODAY's class and that the scale margin is a precision-vs-clamp trade-off that today's dynamic ranges do not have.

## 3. Cost of (iii) — `R4A/cost_table.md`

Per fused font: 769 axes; avar2 = 1,537 regions (2 per input axis + bias) with a dense 256-row VarData; HVAR = 256 × K hat regions;
every region record stores 769 axis triplets (6 B each) — the region list dominates. Fontations evaluates region scalars per glyph
(the probe's 768 × 768 × 768 = 0.45 G evaluations took 0.46–1.35 s ⇒ 1–3 ns per glyph × region × axis, uncached across glyphs;
256 axes: 0.4–0.9 ns; 257: 1.5–2.5 ns).

| design | K | regions/font | raw MB/font (region list + HVAR deltas + avar2) | raw GB / 12 layers | evals per layer | **Fontations time per layer** (1–3 ns) | if scalars were cached per instance |
|---|---:|---:|---|---:|---:|---:|---:|
| 12×256 single | 32 | 9,729 | 58 (45 + 13 + 0.8) | 8.4 | 69 G | 69–207 s | 0.18–0.54 s |
| **12×256 two-level** | **48** | 13,825 | 102 (64 + 38 + 0.8) | **14.7** | 196 G | **196–588 s** | 0.38–1.15 s |
| 12×256 two-level | 64 | 17,921 | 134 (83 + 50 + 0.8) | 19.3 | 254 G | 254–762 s | 0.50–1.49 s |
| 4×768 single | 48 | 38,401 | 236 (177 + 57 + 2.4) | 11.3 | 91 G | 91–272 s | 0.24–0.71 s |

Compare: the hop being removed costs ≈ 0.35 s/layer untraced (R3A lever 2); today's proj stage is 1.2 G evaluations on the stock
backend (12 × 768 × 512 × 256) and the whole fc + proj MLP is < 0.6 s/layer. WOFF2 would compress the region lists 20–30× but Chrome
decodes fonts to memory (Codex's 12 × 256 sparse-avar2 MLP already cost 1.8× RSS; `browser-gpt2` peaks at 3–5 GiB): 15 GB raw of
variation tables is not loadable. Even the hypothetical "Fontations caches region scalars per font instance" bound (0.4–1.2 s/layer)
is not below the 0.35 s/layer it would replace — so this is not a lever even with an upstream Chromium fix.

## 4. Verdict and ranking

| option | precision | Δ s/token | status |
|---|---|---:|---|
| leave at R3R ≈ 19.4 s/token | ids 8/8, RMSE 0.018 | 0 | **keep** |
| (ii) avar2 GELU inside the proj fonts (hop kept) | +F6 0.027 rms + K-hat error, proj fonts move to Fontations | ≤ −0.1 (CSS GELU only) | reject: no boundary removed, precision class lost |
| (iii) fused 769-axis fonts, K = 48, two-level, 12 × 256 | ids 8/8, float agree, 0.046 vs float (better than TODAY's 0.082) **but** compile-time scales (clamp hazard on unseen prompts) | −0.35 s/layer removed, **+200–600 s/layer added**; 15 GB fonts | **structurally possible only on Fontations, economically impossible** |
| (iii) with a Chromium-side scalar cache | as above | ≥ +0.05 s/layer net | not a lever |
| lossy (K = 24, single-level would still need two-level) | ids hold by 5 q-units at 0.10 rms | same cost | dominated |

**Bottom line for the coordinator**: the fc boundary is not removable on Chrome's stock font backend (256-axis cap; GELU non-separable
across shards; avar2 hidden width ≤ axis count), and the only backend that lifts the cap makes the fused fonts 3 orders of magnitude
slower than the hop they replace. The −3 to −4 s/token entry for lever 2 should be struck; the remaining round-4 candidates are the
carrier-primitive ones (RESULTS-round3 "lower-cost carrier primitive": container-query / anchor readbacks for the same boundary,
detaching token-level carriers, GC arms), none of which changes the hop count.

## 5. Method / caveats

- No Chrome run; every browser number is quoted from the repo's saved probes (`browser-gpt2/font-backend-probe/results.json`,
  `matrix-scaling/RESULTS.md`, Codex's avar2 `browser-results.json`). The Fontations rate (1–3 ns per glyph × region × axis) is a fit to
  three data points of a *linear* font; a fused font with 13,825 regions could be faster per region (SIMD) or slower (cache misses on a
  64 MB region list) — either way the ratio to the 0.35 s hop is > 100×.
- F5's two-level trick assumes a fine glyph at 1/64 of the coarse font-size shares the carrier's inline box; it is the same
  mechanism as today's 12 shard glyphs and Codex's paired glyphs, not verified for Fontations' rounding order.
- The int16-delta interpolation is modelled exactly (rounded knot deltas, hat-weighted); Fontations' integer advance rounding is
  modelled as round-to-nearest per glyph; the knot template is shared in z across hidden units and snapped per unit to its F2Dot14 grid.
- Calibration of `R_j` / `S_i` uses the pinned 8-token run only (margin 2× and 4× reported); a deployment would need a corpus.
- `gate_sim.py` was not modified; `fused_sim.py` imports it. Runtime ≈ 3 min for the 60-configuration sweep.
