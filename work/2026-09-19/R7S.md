# R7S — sampling instead of argmax, in pure HTML+CSS (research + gated fixture) — 2026-10-01

Agent R7S. Scratch `work/2026-09-19/R7S/` (noise-font builder, fixture transform, probe pages, Playwright harnesses, results);
log `R7S.log.md`. No repo edits, no git; Chrome 154 headless under `CHROME.lock` (owner R7S, gate AC / disk 9 GB / swap 848 MB),
two short holds (clock probe ≈ 40 s, head fixture ≈ 4 min). Model unchanged; pages are JS-free (the harness only clicks and reads
computed values, as in R4X / the head-two-pass test).

## 0. Answer

**Yes.** The demo can sample from softmax(logits / T) with zero JavaScript and no model change, by the Gumbel-max trick applied
*inside the existing head*: argmax_i (score_i + T·g_i) with g_i i.i.d. Gumbel(0,1) is an exact sample from softmax(logit/T), and the
head already computes an argmax over 50,257 rows. The noise is a **build-time table** (64 seed columns × 50,257 rows) stored as a
7th "noise font": one glyph per row at U+80000+token, an HVAR `SEED` axis (64 tent regions, one per column) and a `TEMP` axis
(linear ramp = temperature). Each `.head-row` gets one more character; `font-variation-settings` gets `"SEED" col,"TEMP" T`; nothing
else in the head changes. Entropy comes from the user's click time: a free-running CSS animation (`--clock` 0→64 over 0.97 s) is frozen
by `animation-play-state: paused` on `#run:checked`; the seed is displayed and can be overridden from a `<select>` to replay a run.
Greedy stays the default and the reference (T = 0 ⇒ the noise glyph's advance is a constant ⇒ today's argmax, bit for bit).

**Verified in Chrome (fixture, 50,257 real rows, real ProdQ16 fonts + the noise font):** 21/21 winners equal NumPy's
`argmax(q_score + round(n[col]·T_real))` for 3 hidden states × {greedy, 3 seed columns × T ∈ {1.0, 0.7}} — including margins of 12 q
(0.09 logit); the T = 0 winners equal the unmodified head's. Cost of the extra glyph: forced style+layout per mutation 1,335 → 1,470 ms
median (+10 %); projected **+0.2–0.3 s/token** on the ≈15.5 s token (< 2 %); **+7.9 MB** font (TTF; ≈6.5 MB as WOFF2); **0 new
elements**. The entropy latch is stable and reproducible (probe: 4 loads, 4 distinct seeds, constant over 1.8 s, override → 17).

## 1. Entropy source (no `random()` — R4X: parses on 153 but evaluates 0)

| candidate | bits / run | reproducible? | bias / failure modes | cost | verdict |
|---|---|---|---|---|---|
| **(a) stopwatch**: `.clock{animation:clock .97s linear infinite}` on `--clock:0→64`; `body:has(#run:checked) .clock{animation-play-state:paused}`; `--seed:mod(round(down,var(--clock)),64)+1` | 6 (64 bins of 15 ms) — more if wanted (`steps` finer, or a 2nd slow clock) | **yes**: shown as `counter(seed)`; `<select id=seed>` auto/1..64 overrides (`body:has(#seed option[value=k]:checked){--seed-override:k}`, 64 rules) | uniform for human click timing (jitter ≫ 1 s cycle); 0.97 s period avoids 60 Hz aliasing; keyboard/touch work; **Reload restores the checked box → the restarted clock pauses at bin 1** (user must re-select the shown seed; Reset = GET navigation already) | ~0: 2 elements restyled per frame while idle before Run; paused (free) during generation | **recommended** |
| (a') same, 86,400 s transition latch on a child reading `var(--clock)` | same | same | freezes the *before-change* value (probe: 2–3 bins earlier than (a)); same semantics the demo already relies on | retained transition on 1 element | works; (a) is simpler |
| (b) mouse position: hover cells inside the Run label, `body:has(.c7:hover){--mx:7}` | 3–6 extra | yes | none for keyboard / touch; a second latched integer | 8–64 cells | optional mixer (`seed = mod(clock + 8·mx, 64)`) |
| (c) viewport size (`@media (min-width)` ladders) | 1–3, constant per user | — | nearly constant → repeats | — | reject |
| (d) time since load | = (a) with a slow clock | yes | identical mechanism | — | subsumed |

Per-step seeds: `--noise-col: mod(var(--seed) + var(--epoch) − 1, 64) + 1` — a run uses 32 distinct columns (S = 64 ≥ 32 steps),
replays identically for the same seed, and two seeds never share a column at the same step. (Columns are a cyclic shift across seeds;
with a different context at every step this is harmless; a stride `seed·K` is a one-line change.) Probe: `R7S/probe/clock-latch.html`,
`R7S/results/clock-latch.json` — latch A values 58/38/18/16 after clicks at 770/491/1,139/1,114 ms, each constant over 12 reads.

## 2. Sampling mechanism — the Gumbel noise font

**Where the term enters.** Row width today: `calc-size(max-content, round(nearest,(size − --base·1px)·120.7776 + 211968px, 4px))`,
`size` = the 6 glyph advances (3 shards × high/residual plane) = the exact q16 dot product; 4 px of width = **1 q = 1/130.1 logit**
(q = rint(logit·SCORE_GAIN·256)). A 7th glyph from the noise font adds `800 + 2·n[col,row]·(T/2)` font units to `size`; with
`size-adjust: 52.98995%` (= 4·upem/(62.5·FACTOR)) one unit is exactly 4 px of width, so **the noise is integer q at T = 1** and the
existing 4-px rounding is untouched. The constant 800 shifts every row equally (argmax, `--head-max-score` and the fine pass are
consistent; verified). HVAR: region s = {SEED tent ((s−1)/64, s/64, (s+1)/64), TEMP ramp (0,1,1)}; SEED ∈ [0,64] makes s/64 exact in
F2DOT14 (s·256) so at SEED = s only column s applies with scalar exactly 1 (fontTools check: max |delta − n| = 0 at T = 1; peak 0 is
never used because the spec ignores zero-peak regions). TEMP ∈ [0,2] with deltas 2n makes T = 1 → scalar 0.5 exact; other T are
realised as round(T/2·16384)/16384·2 (T = 0.7 → 0.699951) and the reference uses the realised value.

**Precision / bits.** Table n = rint(clip(Gumbel, −3, 12)·130.1) ∈ [−342, 1561] → 11 bits, int16 deltas; resolution 0.0077 logit
(any log-probability moved by ≤ 0.4 %); lattice vs float-Gumbel winners agree 99.75 % on 38 states (the rest *are* the table — the
reference is the table, not the ideal Gumbel). Row widths stay ≈ 1.8·10⁵ px, far inside the float32 window (R3P). Fidelity on the 38
head-two-pass states at T = 1: greedy token chosen in 8.0 % of the 64 columns vs softmax mass 8.5 %; top-5 22.7 % vs 21.6 %;
28–62 distinct winners per state (6 for the one 0.91-probability state) — the fixed table behaves like 64 draws per step.

**Selecting the column, O(1).** One axis value in one declaration: `font-variation-settings: var(--head-fvs), "SEED" var(--noise-col),
"TEMP" var(--temp)` on `.full-head` and `.head-fine` (axes unknown to a font are ignored). Best hook: append the two entries to the
`--head-fvs` list itself (`f4_packing.py:136-165`) so the column is latched by the same 86,400 s transition as the hidden state and
passes `.head-isolation` unchanged.

**Temperature.** `--temp` from `<select id=temp>` (greedy 0 · 0.7 · 0.8 · 0.9 · 1.0); 5 `:has()` rules. T = 0 is exactly today's head.
T ≤ 2 by axis range (T > 1 is "more random than the model"). argmax(logit + T·g) ≡ sampling softmax(logit/T): no logit scaling needed.

**Costs.** Fonts +7.9 MB TTF (fontTools without brotli here; ≈6.5 MB WOFF2 — random int16 barely compresses; 8-bit deltas would halve it
at 1/16-logit resolution). Markup +50,257 chars in rows and +50,257 in the fine-row `if()` strings (+0.4 MB). CSS +~75 rules (seed/temp
selects, clock, display). Elements +4 (clock, latch, two selects). Time: fixture 1,335 → 1,470 ms forced style+layout (7 glyphs vs 6,
n = 18 vs 2+2; T = 0 with the glyph present 1,356–1,392); R3H's per-glyph model (shaping 2.7 µs + ink-bounds 2.8 µs per glyph per row)
predicts +0.28 s traced incl. compositing-inputs → **+0.2–0.3 s/token** in the demo, no new frames.

**Top-k / nucleus.** Exact top-k or top-p needs the rank or the prefix-sum of 50,257 softmax terms: ranks need 50k × 50k comparisons or
a sort, prefix sums are sequential (an inline run sums advances, but each term is exp(dot) — fonts are linear, the 768-wide exp fonts do
not apply), and the head has one frame per token. Cheap substitutes, zero cost: (i) **clip the table** at g_cap (e.g. 4 logits): rows
below max − T·g_cap can never win (a deterministic "min-p"-like truncation; the current clip at 12 is effectively none, P(g > 12) = 6·10⁻⁶);
(ii) a second head pass restricted to rows with raw score ≥ M − Δ costs one more head frame (+2.6 s) and needs the raw score without
the noise glyph, i.e. a greedy pass first — implementable (toggle `--temp:0` then `--temp:T` with a `--head-threshold` clamp in the fine
pass) but not recommended at 2.6 s.

## 3. Alternatives considered

- Softmax + inverse CDF in CSS: exp per row is not a font operation (fonts are affine in the axes), the prefix sum is a 50k-deep serial
  chain (anchor/container hops: ≥ 1 pass each, R4X), and the uniform draw would need the same entropy anyway. Infeasible at 50k rows.
- Sample only among the top-k of a greedy pass: needs k winners = k head passes (each pass finds one max; masking the winner needs a
  per-row rule) → k × 2.6 s. Rejected.
- Tiny candidate set (e.g. fixed 1,000 rows): changes the model's output distribution (model change) — out of scope.
- Per-row literals for S seeds (`--n-k` inline + `if(style(--col:k))`): 3.2 M numbers, per-row `if()` on a hot 50,257-element pass,
  breaks declaration identity (R3H option 2). The font keeps every row's declaration identical.
- Adding SEED/TEMP as a 257th/258th axis of the existing ProdQ16 fonts: saves the 7th glyph (−0.1–0.3 s) but rebuilds 76 MB of fonts
  and crosses the 256-axis line (R4X: Fontations path). Not needed for a first version.

## 4. Reference / verification protocol (proposed)

1. The noise table is a published artefact: `n = rint(clip(−log(−log(U)), −3, 12)·SCORE_GAIN·256)`, U from
   `numpy.random.default_rng(20261001).random((64, 50257))` (int16, sha256 of `noise-table.npz` a0abefce…; font 7d79b225…).
2. A run is (prompt ids, seed s ∈ 1..64, T). Step t (epoch e) uses column c = mod(s + e − 1, 64) + 1 and realised T_r.
3. Reference ids: today's `verify_browser_gpt2_runtime.verify` with `scores()` → `rint(raw_q + n[c]·T_r)` (at T = 1: `q + n[c]`),
   argmax with first-index ties (= the head's lowest-group / lowest-local tie rule), sampled ids fed back (teacher-forced path).
4. Acceptance = all ids identical, as for greedy; the harness records seed, T and column per token in `verification-vectors.json`.

## 5. Build hooks (not built; the fixture was derived from `experiments/browser-gpt2/head-two-pass`)

- `R6X/tools/browser_gpt2_head.py:compile_head` — row markup: append `chr(0x80000+token)`; `six_font_faces()`: add the NoiseQ face
  (`format("truetype")` or woff2, `size-adjust`); fine `glyphs` strings: 7 chars; both `font:` lists: `,NoiseQ`.
- `R6X/tools/f4_packing.py:136-165` — append `"SEED" var(--noise-col),"TEMP" var(--temp)` to the `--head-fvs` list; `--noise-col`
  needs body's `--epoch` (registered `inherits:false`) relayed once (the `.pg` UI already does this via `@container runtime style(--epoch:t)`).
- Controls (`r6p_prompt.py` / runtime controls): `<select id=seed>`, `<select id=temp>`, `.clock`/`.latch`, `#seed-out::after`; rules as in
  `R7S/probe/clock-latch.html`.
- Noise font: `R7S/build_noise_font.py` (py3.11 + fontTools; add brotli for WOFF2). Verifier: §4 step 3.

## 6. Risks and what was not verified

- Demo-level timing (+0.2–0.3 s/token) is projected from the standalone fixture (style+layout only) and R3H's per-glyph model; the full
  frame (compositing inputs, paint) was not traced. No 32-token sampled run was executed; `.head-isolation`/`--epoch` relay untested.
- Reload semantics: the checkbox is restored by the browser, the clock restarts → seed 1 (documented; the shown seed must be re-selected).
- Ties on the integer lattice are possible (rare: 0/21 here) and deterministic (lowest id). T ≠ 1 goes through one extra rounding, modelled
  as `rint(raw + n·T_r)`; 9/9 agreed incl. a margin-12 case, but a near-half case could flip like today's greedy margins of 1 q.
- The idle clock keeps the main thread at 60 Hz until Run (2 elements, ≈ µs each) — or run it only `label[for=run]:hover` with seed 1 as fallback.
- The entropy is "which 15 ms bin the click fell in": fine for a demo, not cryptographic; 64 seeds × fixed table = at most 64 continuations
  per step per context (grow S to 256 for 4× the table, 26–32 MB).

## Appendix A — fixture results (`R7S/results/head-sample.json`, `head-greedy-control.json`; Chrome headless, cold 46.9 / 47.4 s)

| state | greedy | col 1 T=1 | col 1 T=.7 | col 17 T=1 | col 17 T=.7 | col 42 T=1 | col 42 T=.7 |
|---|---|---|---|---|---|---|---|
| 391 | 11 ✓ | 31209 ✓ (217) | 31209 ✓ (140) | 8417 ✓ (166) | 11 ✓ (38) | 10936 ✓ (216) | 10936 ✓ (57) |
| 647 | 1366 ✓ | 4382 ✓ (231) | 4382 ✓ (268) | 2033 ✓ (151) | 2033 ✓ (40) | 2546 ✓ (242) | 2546 ✓ (197) |
| 382 | 532 ✓ | 10571 ✓ (93) | 353 ✓ (46) | 8417 ✓ (132) | 11 ✓ (12) | 353 ✓ (99) | 353 ✓ (193) |

(✓ = browser `--winner` equals NumPy; parentheses = NumPy margin to the runner-up in q.) Mutation ms (forced style+layout, excluding
the first no-change mutation): sampling page T > 0 median 1,471 (1,393–1,772, n = 18), T = 0 1,356/1,392; control page 1,325/1,346.
`--head-max-score` shifted by exactly 3,200 px (= 800 units × 4 px) between the two pages at T = 0.

## Appendix B — files

`R7S/build_noise_font.py` (table + font + `head-sample/expected.json`), `R7S/noise/{gumbel-noise.ttf, noise-table.npz}`,
`R7S/make_fixture.py` → `R7S/head-sample/{index.html, head.css}`, `R7S/run_head.mjs`, `R7S/probe/clock-latch.html`,
`R7S/run_clock_probe.mjs`, `R7S/with_lock.sh`, `R7S/results/*.json`.
