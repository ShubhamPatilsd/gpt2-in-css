# R2B — round-2 micro-benchmarks MB6–MB9 (written before running)

Harness: copies of `audit/2026-09-18/M1-microbench/{run.mjs,parse_trace.mjs,gen.py,analyze.mjs}` (originals
untouched; the quiescence-baseline fix is in `run.mjs`). Local changes, all in this directory:

* `run.mjs`: pages with `params.mouse=true` get one CDP `Input.dispatchMouseEvent(mouseMoved, 400,300)` after load so
  Blink's post-layout fake-mousemove hover hit test runs each frame (P2 #3 — the demo's cursor sat on the Run box);
  per-trial row gains HitTest / PrePaint / Paint / frame count / renderer RSS / self-ms of named lifecycle events.
* `parse_trace.mjs`: exports `eventsByName` (count / inclusive / self µs for every main-thread complete event in the
  window) so the analysis can pick `LocalFrameView::RunPaintLifecyclePhase`, `PageAnimator::serviceScriptedAnimations`,
  `EventHandler::handleMouseMoveEvent` etc. by name.
* `gen_r2b.py`: MB6–MB9 pages (imports gen.py's Page/Builder/mutation contract). `make_fonts.py`: 12 retagged copies
  of `experiments/gpt2-block-css/mlp-proj-s0.ttf` (256 HVAR axes each → tags X000..XBFF, range ±16384, disjoint cmap).
* `analyze_r2b.mjs`: median tables + fits (written after the pages, before looking at results).

Protocol (as M1): headless Chrome 153, JS disabled in the page, one CDP attribute mutation per trial, 1 untraced
warm-up + 3 traced trials, medians, `verified` must be 3/3, seeded random values (16 pre-baked per page, cycled per
trial), AC power required by preflight, `caffeinate -dims`, Chromium mutex `work/2026-09-19/CHROME.lock`.
Pages total ≈ 110 MB; deleted after the run (fonts 19 MB kept? no — deleted too, regenerable by `make_fonts.py`).

Run:
```sh
NODE=/Users/shubhampatil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
cd work/2026-09-19/R2B && ./run_all.sh          # takes the lock, checks AC, runs mb6..mb9, releases
$NODE analyze_r2b.mjs --md results/analysis.md
```

## MB6 — inherited registration count tax (16 pages)

Root (`html` or `body`) declares K ∈ {16, 1,000, 15,000} registered custom properties (`inherits:true` or
`inherits:false`) with literal values. `#par` (child of body) carries `--in`; N = 5,000 descendants each have ONE unique
declaration `--q: calc(var(--in)*w)`; `--q` registered `inherits:true` (demo-like, `q1`) or `inherits:false` (`q0`).
Mutation: `--in` on `#par` (all 5,000 dirtied). Extra: `undeclared` = 15,000 registrations with initial values only.

* H6a: Blink's `StyleInheritedVariables` stores the *root's* map by pointer and a per-element delta. With K on `html`,
  descendants share the root map → per-element cost and RSS **independent of K**.
* H6b: With K declared on `body` (not the root), `body`'s delta holds K entries; every descendant that writes an inherited
  custom property (`q1`) must copy that delta → per-element cost grows **linearly in K** (µs/element ∝ K) and RSS grows
  ∝ N·K. With `q0` (non-inherited `--q`) no copy → flat.
* H6c: `inherits:false` registrations never enter the inherited map → flat in K for both `on` positions.
* H6d: registrations without declarations cost nothing per element.

Decision: if `onbody-q1` grows with K (≥ +1 µs/element per 1,000 registrations) → mass-scoping the demo's 14,681
`inherits:true` registrations (or declaring inherited values only on `html`) is a round-2 fix: predicted saving =
slope × (K_demo) × Σ dirtied elements per token. If flat everywhere → registration count is NOT a tax; drop the item.

## MB7 — `font-variation-settings` list evaluation (28 pages, real 256-axis HVAR fonts)

`#par` holds `--x0 = var(--in)` and `--x1..--x{L-1}` literal registered numbers (±266); M font elements
(`display:inline-block`, `font:16px R2B0,…`, one glyph per font in the stack) carry an L-entry list, L ∈ {64, 256, 768,
3,072}, spelled (i) `lit` `"Xnnn" 1234` literal; (ii) `var` `"Xnnn" var(--xI)`; (iii) `round`
`"Xnnn" round(nearest,calc(var(--xI)/266.248396912*16384),1)` (the demo's current consumer shape); (iv) `hoist`
`"Xnnn" var(--qI)` with `--qI = round(…)` computed once on `#par`. `uniq` = per-element rule with one differing trailing
entry (defeats MatchedPropertiesCache, as the demo's per-(head,slot) rules do); `shared` = one `.f` rule for all M.
Mutation: `--in` on `#par`. L sweep at M=32; M ∈ {1, 128} at L=768; shared at L=768, M=128.

* H7a (M1 §8.3 law): restyle ms = M · (c_e + L · c_entry[spelling]); c_entry(round) ≈ c(typed calc + round + 1 var)
  ≈ 8–17× c_entry(var) ≈ c_entry(hoist); c_entry(lit) ≈ cascade floor (~0.05 µs).
* H7b: `hoist` total = M·L·c(var) + L·c(round) on the parent (paid once) → beats `round` by a factor ≈ M when M ≫ 1.
* H7c: a changed list re-instantiates the font: Layout ms (shaping) grows with L (axis application in HVAR/CoreText
  instantiation) and with M for `uniq` (M distinct instances) but is ≈ flat in M for `shared` (one instance,
  FontCache key = settings string) — if it is NOT flat, Blink re-creates per element.
* H7d: in `shared` mode restyle ms is ≪ `uniq` (MPC hit after the first element).

Decision: per-entry constants → predicted saving for the demo = 80 passes × 400 font elements × 768 entries ×
(c_round − c_hoist) per token. If (c_round − c_hoist) ≥ 0.5 µs/entry the hoist saves ≥ 12 s/token-equivalent of list
evaluation at the demo's shape and is round-2 fix #1; if < 0.1 µs/entry the 316 µs/element measured in round 1 comes
from font instantiation (H7c), not list parsing, and the fix is to share instances instead.

## MB8 — dirtied font element whose list does NOT change (5 pages, L=768, M=128)

Same structure as MB7-uniq but the mutation (`--in` on `#par`) is NOT referenced by any list entry: `plain`
(no font, one trivial literal declaration), `nofont-lit` (768-entry literal list on `monospace`, text "a"), `lit`
(literal list, real fonts), `var-const` (`var(--qI)` to constant parent numbers), `round-const` (`round(calc(var(--xI)…))`
of constant parent numbers).

* H8a (M1 MB1b): the list is re-applied on every restyle: `lit` ≈ 0.05 µs/entry, `var-const` ≈ 0.3 µs/entry,
  `round-const` ≈ 60–70 % of MB7-round — i.e. the demo pays the `round(calc(var()))` list on every dirtying even when
  nothing changed.
* H8b: since the resolved list is identical, Blink's `FontDescription` compares equal → no new font instance, Layout ≈ 0
  (vs MB7 where it changes). If Layout > 0 here, font re-instantiation is triggered by restyle alone.

Decision: cost(round-const) − cost(plain) per element = the tax on every one of the ≈ 80 × 400 font-element visits that
happen without an input change → add to the MB7 saving estimate.

## MB9 — frame overhead knobs (12 pages, tiny page + 50k-element static subtree)

`#gate` (8×8 fixed box, `background: hsl(var(--gv)…)`) runs a 1 ms `forwards` animation `g{k}` when the harness sets
`html.go-k` (the demo's gate pattern) → 1–2 frames. `#sub` = 50,000 `<i class=s>` 1×1 inline-blocks in an 800 px block
(≈ 63 lines). Knobs: `none` (no subtree; floor), `default-nomouse`, `default-mouse` (cursor parked at 400,300),
`containpaint` (`#sub{contain:paint}`), `vishidden` (`#sub{visibility:hidden}`), `noptr` (`html{pointer-events:none}`),
`fixedfc` (+1,926 `position:fixed; container-type:size` 1×1 divs), `staticfc` (same 1,926 as static blocks),
and `-dirty` variants where the same class flip also writes `--in` that every one of the 50k elements reads through a
unique `--z: calc(var(--in)*w)` (so the frame follows a 50k-element restyle, like the demo's whole-DOM passes).

* H9a: per-frame `PrePaint` + paint-lifecycle self time scales with the number of layout objects the paint walk visits
  when anything is dirty: `default` ≫ `none`; `dirty` > non-dirty.
* H9b: `contain:paint` on `#sub` lets PrePaint/paint skip the subtree when it is clean → ≈ `none` for non-dirty frames;
  `visibility:hidden` additionally removes the 50k from the hit-test and paint walks → ≈ `none` even when dirty.
* H9c: hit-test (`EventHandler::handleMouseMoveEvent` / `LayoutView::HitTest`) appears only with the cursor over the
  page (`mouse`) and is ∝ layout objects under the cursor's stacking order; `pointer-events:none` on html or moving the
  cursor off removes it (P2: 15 ms/frame × 85 frames = 1.3 s/token).
* H9d: 1,926 `position:fixed` containers add per-frame prepaint/compositing cost (each fixed box needs its own paint
  property nodes/cull rects) relative to the same 1,926 static blocks — the combined2 regression.

Decision: for each knob, Δ(per-frame ms) × 85 frames/token = predicted s/token saving; adopt knobs with ≥ 0.5 s/token.

### MB8 addendum (after run 1, before the MB8 re-run)

Run 1's `var-const` page in fact declared the parent's `--qI` as `round(nearest,calc(var(--xI)/…*16384),1)` of constant
`--xI` (the exact proposed hoist), not literal integers. It showed Layout = 0 while `round-const` re-shaped every element
(Layout 535 ms). To pin the mechanism the MB8 family is re-run with: `var-const` (literal integer `--qI` on the parent),
`hoist-const` (parent `--qI = round(calc(var(--xI)…))`, child `var(--qI)` — run 1's var-const), `calc-const`
(`calc(var(--xI)/…*16384)` in the list, no `round()`), `round-lit` (`round(nearest,<literal>,1)`, no `var()`).
H8c: a `font-variation-settings` value that still contains a math function after `var()` substitution (`round(…)`,
`calc(…)`) is not simplified to a number before the FontDescription compare, so every restyle produces a "new" font and
re-shapes the text even when the numbers are identical; substituting an already-resolved registered `<number>` yields a
plain number and compares equal. Decision: if `calc-const` and `round-lit` also re-shape while `hoist-const` does not, the
hoist removes the spurious re-instantiation on every dirtied font element, worth Layout µs/element × visits/token.
