# M1 — micro-benchmarks of the atomic Blink costs (RUN 2026-09-18 22:02–22:17Z)

Agent M1. Suite, harness, pages, raw per-trial JSONL, traces and auto-analysis live under
`audit/2026-09-18/M1-microbench/` (README.md = hypotheses and decision table; `results/analysis.md`
and `results-cold/analysis.md` = machine-generated tables and fits; `results/*.jsonl` = one line per
trial; `traces/*.trace.json.gz` = trial-0 trace per variant). Every read/command is in
`audit/2026-09-18/M1-microbench.log.md`. Nothing outside `M1-microbench/` and these two files was
touched; no git mutation.

## Run conditions

- Apple M2 Pro, 16 GiB; Google Chrome 153.0.8010.48 (new headless) via playwright 1.62.1; node v24.19.0.
  Launch: `chromium.launch({headless:true, args:[--disable-background-timer-throttling,
  --disable-renderer-backgrounding, --disable-backgrounding-occluded-windows]})`; JS disabled in the page
  context; the mutation is `DOM.setAttributeValue(<html>, class, "go-k")` (class trigger, 16 pre-baked random
  values cycled) or `style="--in:<random>"` (inline trigger). No `<script>` in any page.
- 3 trials per variant, 1 untraced warm-up mutation, fresh browser per variant, fresh context + navigation
  per trial, 500 ms quiescence (RecalcStyleCount/LayoutCount unchanged). Trace categories as specified.
- Gate: waited for P2's `parse_trace.py` to exit; no Chrome processes present; `caffeinate -dims`.
- **Power:** MB2, MB5, MB1 ran on AC (22:02–22:10Z). The host switched to battery at 22:09Z; MB3, MB4
  and the cold/inline cross-check (22:10–22:17Z) ran on battery with `--allow-battery` as instructed.
  Battery-phase numbers are marked (B) and compared only within phase. `pmset -g therm` reported no
  throttling throughout.
- Harness bug found and fixed before the first kept trial (cost 7 min): the quiescence poll took its
  baseline *after* the CDP mutation, but Blink completes the lifecycle before the next DevTools command is
  serviced, so every trial looked like "no recalc" and was force-laid-out. Baseline is now sampled before
  the mutation. The aborted first run was deleted.
- Nothing was skipped; total timed wall ≈ 15 min. All 81 variants × 3 trials completed, 0 errors,
  0 forced trials.

Notation: **ULT** = total `UpdateLayoutTree` ms inside the mutation window (median of 3, [min–max]);
**elems** = `UpdateLayoutTree.elementCount`; Layout n = `Layout` events. Unless stated, every mutation
produced exactly **1 UpdateLayoutTree, 0 Layout**, `Document::recalcStyle` was ≥95 % of main-thread
busy time, and the only invalidation reason recorded was "Related style rule" (the `html.go-k` match).

## MB2 — inheritance dirtying of unrelated descendants (AC) — decisive

`--in` changes on `<html>`; N descendants each hold b bytes of declarations that never reference `--in`.

| variant | N × b | ULT ms | elems | ratio to (a,var) |
|---|---|---:|---:|---:|
| a var (calc(var(--const)*w)) | 0 | 0.12 | 4 | — |
| a var | 1000 × 200 B | 9.70 [9.62–9.74] | 1004 | 1 |
| a var | 1000 × 2 KB | 90.19 [89.97–91.30] | 1004 | 1 |
| a var | 10000 × 200 B | 96.79 [95.90–97.89] | 10004 | 1 |
| a var | 10000 × 2 KB | 771.2 [768.1–779.8] | 10004 | 1 |
| a var | 40000 × 200 B | 472.5 [452.0–475.4] | 40004 | 1 |
| a lit (plain literals) | 1000 × 2 KB | 39.85 [39.37–40.23] | 1004 | 0.44 |
| a lit | 10000 × 2 KB | 401.5 [397.4–403.5] | 10004 | 0.52 |
| a lit | 40000 × 200 B | 262.4 [240.9–262.6] | 40004 | 0.56 |
| b `--in` inherits:false | 10000 × 2 KB | 0.10 [0.10–0.12] | 1 | 0.0001 |
| c content-visibility:hidden wrapper | 10000 × 2 KB | 0.31 [0.28–0.31] | 4 | 0.0004 |
| d contain:style on each | 10000 × 2 KB | 778.1 [770.5–785.5] | 10004 | 1.009 |
| e declarative shadow root | 10000 × 2 KB | 795.5 [788.5–797.0] | 10005 | 1.031 |
| f depth-100 chains | 10000 × 2 KB | 776.0 [771.8–779.1] | 10004 | 1.006 |

(b, c, d, e, f were also run at 1000×2 KB and 40000×200 B with the same ratios: b 0.001×, c ≤0.002×,
d 0.999×, e 0.98–1.01×, f 1.004–1.007×.)

Fits (least squares over the five (a,var) sizes / three (a,lit) sizes):
- **(a,var): ULT ms = −2.35 + 4.45 µs/element + 36.5 ns/byte** (R² 0.999) → 27 MB/s marginal, 21–48 ns/B overall.
- **(a,lit): ULT ms = −0.33 + 2.83 µs/element + 18.7 ns/byte** (R² 1.000).
- Cold/inline cross-check (B): (a,var) 3.24 + 1.39 µs/element + 43.1 ns/byte (R² 0.999); (a,lit) 0.74 + 2.03 µs/element + 18.9 ns/byte — same picture within 15 %.

Verdicts: **H2a HOLDS** — one inherited write restyles every descendant and re-applies *all* of its
declarations, dependency or not, at ≈37 ns/B for `var()` declarations and ≈19 ns/B for plain literals,
plus 3–4.5 µs per element. Literal declarations are not free (Blink's independent-inherit fast path does not
engage for registered custom properties). **H2b HOLDS** (inheritance is the sole dirtying path).
**H2c HOLDS: MB2(c) ≈ 0** — a `content-visibility:hidden` wrapper stops the cost completely (4 elements
restyled instead of 10 004). **H2d, H2e HOLD** (contain:style and shadow DOM do nothing). **H2f:** depth is
*not* a first-order cost (the inherited-map copy-per-level estimated in C1 §4.3 is negligible).
Decision: **root-bank writes are the atom**; every inherited write costs (declared bytes under it) / 27 MB/s;
locking inactive stages is sufficient and necessary; partitioning without locking buys nothing.

## MB5 — what the 43 MB/s is (AC; K = 10 000 declarations on the mutated element, 320 B each = 3.2 MB)

| spelling | var()/decl | ULT ms | µs/decl | × calc-var16 | cold/inline (B) |
|---|---:|---:|---:|---:|---:|
| lit-short (`--p: .1234`) | 0 | 7.23 [7.03–7.30] | 0.72 | 0.09 | 7.75 |
| lit-calc (16 literal products, parsed once) | 0 | 40.91 [40.73–41.63] | 4.09 | 0.50 | 49.60 |
| unreg-var16 (unregistered, 16 var()) | 16 | 37.08 [36.85–38.30] | 3.71 | 0.45 | 38.43 |
| calc-var1 (1 var() + 15 literal products) | 1 | 65.22 [64.67–65.96] | 6.52 | 0.80 | 71.14 |
| **calc-var16** (reference) | 16 | 81.75 [81.64–83.50] | 8.17 (25.5 ns/B) | 1.00 | 78.31 |
| calc-varw (weights via var(--w)) | 32 | 142.9 | — | — | **INVALID** |
| func16 (`@function` × K, 16 args) | 16 in body | 179.9 [179.4–180.7] | 17.99 | 2.20 | 197.3 |

`lit-short`/`lit-calc` show verified 0/3 *by design* (their `--p0` cannot depend on `--in`); RSC=1 confirms
the mutation ran, timings valid. **`calc-varw` is INVALID**: the 160 000-declaration `body{--wI_j:…}` rule was
not applied by Blink (computed `--w0_0` = initial 0 on body), so all 10 000 declarations evaluated to the
initial value; its time measures substitution + failure, not arithmetic. Not counted.

Decomposition (additive within 10 %): ≈0.7 µs cascade per registered declaration; ≈3.4 µs to
typed-evaluate a 16-term calc tree (lit-calc − lit-short); ≈0.2–0.25 µs per `var()` substitution
(calc-var16 − calc-var1 = 1.65 µs for 15 var(); unreg-var16 = 3.7 µs for 16 var() with no typed eval);
`@function` invocation ≈ +10 µs per call over an inline calc. **H5 verdict:** the constant "43 MB/s" is
*not* tokenizer throughput — calc-var1 and calc-var16 have identical bytes and differ by 25 %. It is
≈40 % typed calc evaluation, ≈30–45 % var() substitution/re-parse, ≈10 % cascade. Decisions: bake weights
as literals (each `var()` costs ≈0.25 µs, the same as ≈12 bytes of literal); never use one `@function`
per output (the GPT-2 head's ≈12.5 k invocations/token pay ≈125 ms of pure call overhead); and, above
all, do not restyle elements that hold declarations (MB2).

## MB1 — is per-element re-evaluation O(declared bytes)? (AC)

| variant | ULT ms | µs/decl | MB/s |
|---|---:|---:|---:|
| a K1000 M1 / M16 / M64 | 1.09 / 7.50 / 27.48 | 1.09 / 7.50 / 27.5 | 89 / 51 / 48 |
| a K10000 M1 / M16 / M64 | 12.15 / 83.02 / 268.9 | 1.22 / 8.30 / 26.9 | 81 / 46 / 49 |
| a K40000 M1 / M16 | 62.64 / 295.4 | 1.57 / 7.38 | 64 / 52 |
| a K20000 M64 (26 MB page) | 788.8 [595.1–790.1] | 39.4 | 33 (noisy) |
| b K1000 M16 / K10000 M16 / K40000 M16 | 5.43 / 51.30 / 213.5 | 5.4 / 5.1 / 5.3 | — |
| b K10000 M64 / K20000 M64 | 175.2 / 349.7 | 17.5 / 17.5 | — |
| c parent K10000 (50 siblings × 200) | 104.9 [104.4–105.1] (54 elems) | — | — |
| c one-sibling K10000 | 2.23 [2.23–2.25] (1 elem) | — | — |
| c parent / one-sibling K40000 (200 siblings) | 383.2 / 2.13 | — | — |

- **H1 HOLDS:** per-declaration cost is independent of K and linear in terms (≈0.42 µs per `var()*w`
  term, ≈1.1 µs fixed); 46–52 MB/s for M ≥ 16 — C1's 43 MB/s reproduced for a *single* restyled element.
  Two-variable fit over 9 points: 29 ns/byte, R² 0.97 (pulled by the noisy 26 MB point, whose min trial
  was 25 % faster than its median — the first sign of memory pressure at that page size).
- **H1b FAILS (strong form):** with only 1 of K declarations depending on `--in` and the rest literal calcs
  of equal bytes, cost is still 0.62–0.72× (0.44× at the noisy point) of MB1a. Blink re-applies and
  re-evaluates every declaration of a restyled element; dependency does not matter.
- **H1c HOLDS exactly:** one-sibling / parent = 0.021 (K10000, 1/n = 0.020) and 0.0056 (K40000,
  1/n = 0.005). Cost is additive over dirtied elements; scoped writes buy 1/n, unscoped partitioning nothing.

## MB3 — passes per boundary mechanism (B)

| mechanism, S=12 | ULT n | ULT ms | elems | Layout n | Layout ms | busy ms | per boundary (S12−S4)/8 |
|---|---:|---:|---:|---:|---:|---:|---|
| style (control) | 1 | 0.79 | 28 | 0 | 0 | 2.58 | +0 events, +0.05 ms |
| container (`width:calc(var*1px)` → `100cqi`) | 1 | 0.28 | 5 | 1 | 0.65 | 2.84 | +0 events, +0.05 ms (Layout) |
| anchor (`anchor-size` → size container → `100cqi`) | 1 | 0.82 | 28 | 1 | 0.73 | 3.46 | +0 events, +0.10 ms |
| view-timeline readback | **13** | 6.17 | 328 | **12** | 0.23 | 10.42 | **+1 UpdateLayoutTree, +1 Layout, +0.83 ms busy, +6.6 ms wall** |

All 36 MB3 trials verified (the chain output changed in every mechanism). Container and anchor chains
resolve in **one** style pass and **one** layout pass regardless of depth: Blink's interleaved
container-query restyle happens inside `LocalFrameView::performLayout` ("Style changed" ×12 and "Anchor
positioning" ×4 layout-invalidation records), and those interleaved recalcs are not even counted in
`elementCount`. **H3c/H3a FAIL in the pessimistic direction — good news:** geometry boundaries do *not*
cost a pass each; 12 container hops cost 0.65 ms of layout total. **H3v HOLDS:** each view-timeline hop
costs one extra frame — 13 UpdateLayoutTree + 12 Layout for S=12, 8 `Commit`s, +6.6 ms wall per boundary,
and each successive frame restyles the whole remaining chain (elementCounts 52,45,41,…,1 — quadratic in
S). Decision: the ≈119 recalcs / ≈71 layouts per token in the GPT-2 page cannot come from container/anchor
boundaries; they come from animation/timeline-style boundaries (and the `content-visibility` gate
animation, C1 §4.1–4.2). Any design chaining ≥60 timeline hops per token has a ≥0.4–1 s frame-cadence floor.

## MB4 — retained animation servicing (B)

| A | scope | fwd (finished, fill) | paused | static | Δ vs A=0 (fwd/paused/static) |
|---:|---|---:|---:|---:|---|
| 0 | sib / inh | 0.14 / 0.15 ms | | | — |
| 1 000 | sib | 0.20 | 0.18 | 0.14 | +0.06 / +0.05 / 0.00 ms |
| 10 000 | sib | 0.84 | 0.90 | 0.33 | +0.70 / +0.77 / +0.20 ms |
| 100 000 | sib | 7.39 | 7.66 | 1.69 | +7.3 / +7.5 / +1.6 ms |
| 1 000 | inh | 5.42 | 4.72 | 2.24 | 5.3 / 4.6 / 2.1 µs per element |
| 10 000 | inh | 55.6 | 51.6 | 21.7 | 5.6 / 5.1 / 2.2 µs per element |
| 100 000 | inh | 595.0 [573–611] | 517.4 | 229.7 | 5.9 / 5.2 / 2.3 µs per element |

`sib` = the A animated elements are *not* restyled (mutation on a sibling); `inh` = they are (mutation on
`<html>`). All verified.
- `sib`/fwd and `sib`/paused: ≈0.07 µs per retained animation per mutation in `UpdateLayoutTree`
  (`Document::updateStyleInvalidationIfNeeded` 8 ms at A=100k), **plus** outside it: paused animations
  cost `AnimationTimeline::serviceAnimations` 64 ms per frame at A=100k (busy 102 ms vs 36 ms for fwd vs
  20 ms static). So **H4 partially FAILS:** finished fill-forwards animations are cheap (≈0.07 µs each per
  mutation, 7 ms per 100k), but *paused/active* ones are serviced every frame at ≈0.65 µs each — 129 k
  retained transitions (E1 §H) would cost ≈9 ms per mutation plus up to ≈85 ms per frame if any are active.
- `inh`: an element with a retained animation costs 5.2–5.9 µs to restyle vs 2.2 µs for the same value as a
  static declaration — the "animation as latch" premium is **≈3.5 µs per element per restyle** (≈2.5×).
  Memory: 100 k animations = 1.9 GB renderer RSS vs 0.65 GB static.

## Invalid / caveats

- `mb5-calc-varw-K10000` invalid (weight rule not applied; see MB5). Nothing else failed verification or
  was forced; no errors in 243 + 48 trials.
- `mb1a-K20000-M64` (26 MB page): trial spread 595–790 ms; treat as noisy.
- Battery phases (MB3, MB4, cold cross-check) are internally consistent (≤3 % spreads) but should not be
  compared in absolute terms to the AC phases; the cold/inline cross-check of MB2(a)/MB5 reproduced the AC
  numbers within −15 %…+21 % with identical rank order and fit structure (43 vs 37 ns/B var, 19 vs 19 ns/B lit),
  which also shows the class-trigger/warm-up design was not a cache artefact.
- Headless frame cadence: MB3 view-timeline "wall per boundary" (6.6 ms) reflects headless BeginFrame
  scheduling, not 16.7 ms vsync.

## What this changes for the project

1. The per-token cost model is: Σ over every element restyled × (2.8–4.5 µs + 19–37 ns × its declared
   bytes) + Σ over every declaration (0.7 µs + 3.4 µs per 16-term calc + 0.25 µs per var()) + 10 µs per
   `@function` call. Bytes matter, dependency does not; elements not restyled cost 0.
2. `content-visibility:hidden` is a complete cut (MB2c); `inherits:false` on the changing property is
   a complete cut (MB2b); `contain`, shadow roots and flattening are not cuts.
3. Container/anchor geometry hops are essentially free in passes (1 style + 1 layout per frame for the whole
   chain); timeline hops cost a frame each and re-restyle the downstream chain. The 119/71 passes per token
   are a scheduling artefact of animation-driven boundaries, not of geometry.
4. Retained animations: finished `forwards` ones are cheap when untouched, ≈2.5× a static value when
   restyled, and paused/active ones cost per frame; KV retention via animations should be replaced by
   static declarations under a locked wrapper.

Commands used: `python3 gen.py`; `BUDGET_MIN=75 ./run_all.sh` (MB2, MB5, MB1); `./run_rest.sh` (MB3, MB4,
cold cross-check with `--allow-battery`); `node analyze.mjs --md results/analysis.md`;
`node analyze.mjs --results results-cold --md results-cold/analysis.md`.
