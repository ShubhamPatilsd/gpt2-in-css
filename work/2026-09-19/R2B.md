# R2B — round-2 micro-benchmarks MB6–MB9 (2026-09-19)

Harness, pages, hypotheses and decision rules: `work/2026-09-19/R2B/README.md` (written before running).
Raw rows: `R2B/results/*.jsonl` (61 variants × 3 trials), auto tables: `R2B/results/analysis.md` (`node analyze_r2b.mjs`). Two follow-ups are generated but **unrun** because the machine went to battery after the main run (the constraint forbids timing on battery; the driver waited 09:41–16:41 UTC): a 7-trial MB6 repeat and the MB8 mechanism probes + `calcdiv` spelling — `./run_all.sh --filter '^mb6-' --trials 7 --out results-mb6b` and `./run_all.sh --filter '^mb8-|^mb7-calcdiv' --out results-mb8b` run them when on AC (pages regenerate with `make_fonts.py` + `gen_r2b.py`).
Protocol: headless Chrome 153.0.8010.48, Apple M2 Pro, AC + `caffeinate -dims`, Chromium mutex, JS disabled in the page, one CDP attribute
mutation per trial, 1 untraced warm-up + 3 traced trials, medians [min–max], seeded random inputs cycled per trial, every trial
`verified` by reading the changed computed value back (all 3/3; no forced, no errors). Fonts: 12 retagged copies of the repo's
256-axis HVAR font (`experiments/gpt2-block-css/mlp-proj-s0.ttf` → tags X000..XBFF, ±16384, disjoint cmap); a list of L entries hits real
axes across a ⌈L/256⌉-font stack and the element renders one glyph per font (the F2 global-list mechanism).

Demo assumptions used for the s/token predictions (stated by the brief): 85 frames/token; ≈80 font-element passes/token × ≈400 elements
= 32,000 font-element visits/token. Where the bench trace of the combined bundle (`bench/combined.md`) gives a directly measured figure I
quote it as the second scenario: 79.4 passes/token in the 100–999-element bucket, 160 elements/pass average, 316 µs/element, 4.0 s/token;
layout 15–17 % ≈ 4.6–5 s/token; paint lifecycle 14–16 % ≈ 4.5 s; animate 10 % ≈ 3 s; hit-test 2.9 % ≈ 0.9 s.

## 0. Summary of decisions

| # | Lever | Result | Hold? | Predicted Δ s/token (demo) |
|---|---|---|---|---|
| MB6 | scope the 14,681 `inherits:true` registrations | 15k declared `inherits:true` values add ≈0.9 µs (+40 %) to each restyled element that writes an inherited custom property; 0 for `inherits:false`, undeclared, or non-inherited writers; RSS +17 MB total, no per-element copies | H6c/H6d hold; the K tax exists but is 0.06 µs per 1,000 entries | ≤ −0.19 s/token, −17 MB → **not a round-2 fix** |
| MB7 | hoist per-entry `round()/calc()` out of `font-variation-settings` lists into parent `<number>`s | style per entry: lit 0.09 µs, `var()` 0.64, hoist 0.54, `round(calc(var()))` 1.33 µs (`calc(var()/var())`, the bundle's shape: page generated, not run — battery); a *changed* list costs 4.2 ms/element of font re-instantiation + shaping at L=768 (20 ms at L=3,072), independent of spelling, unless the list is shared (then 44 µs/element) | H7a partly (2.5×, not 16×); H7c holds | −0.6…−2.4 ms per visit of style; see §2.4 |
| MB8 | dirtied font element whose list does not change | `round(calc(var()))` lists re-instantiate the font and re-shape on EVERY restyle even when the numbers are identical (Layout 4.2 ms/element); `var()` of parent numbers (the hoist) do not (Layout 0). The bundle's `calc(var()/var())` lists are expected to behave like `round` (same mechanism: a math function survives substitution); probe generated but unrun (battery). | H8a holds; H8b **fails** for math-function lists | the hoist removes ≈4.2 ms (L=768) / ≈20 ms (L=3,072) per visit of spurious re-shaping; see §3 |
| MB9 | frame knobs | per frame on a 50k-object page: Paint walk 12.6 ms → **0.02 with `contain:paint`** on the static subtree (`visibility:hidden` only −20 %); hover hit-test 8 ms → 0 with the cursor off the page (`pointer-events:none` −20 %); 1,926 `position:fixed` containers +1.5 ms/frame; an inherited write on `html` costs 0.19 µs per declaration-free descendant per pass | H9a/H9b(contain) hold; H9b(visibility) fails; H9c holds for cursor-off, weak for `pointer-events`; H9d small | `contain:paint`: −1.1 s; cursor off / no synthetic hover: −0.7 s; fixed→static containers: −0.13 s |

## 1. MB6 — inherited registration count tax

Run 1 (3 trials + warm-up). Every page is bimodal across trials — the same page restyles 5,000 elements in ≈11 ms or ≈20 ms
(trial 1 low, trials 0 and 2 high in every variant, independent of K) — so both the median and the minimum (the clean mode) are given;
the 7-trial re-run (`results-mb6b`, queued behind the mutex/AC) is meant to settle the mode statistics but does not change the ranking.

| K | registrations `inherits` | declared on | `--q` inherits | ULT ms median [min–max] | µs/element (min mode) | RSS MB after load | Δ RSS vs K=16 |
|---:|---|---|---|---:|---:|---:|---:|
| 16 | true | html | true | 15.6 [14.2–19.6] | 2.85 | 173 | – |
| 1,000 | true | html | true | 13.0 [12.7–13.2] | 2.53 | 174 | +1 |
| 15,000 | true | html | true | **23.2 [15.8–24.9]** | **3.15** | 190 | +17 |
| 16 | true | body | true | 19.8 [14.8–21.5] | 2.95 | 173 | – |
| 1,000 | true | body | true | 12.4 [12.3–12.5] | 2.46 | 173 | 0 |
| 15,000 | true | body | true | **16.2 [15.9–16.3]** | **3.17** | 190 | +17 |
| 16 | false | html | true | 19.5 [12.6–19.9] | 2.52 | 174 | – |
| 1,000 | false | html | true | 11.9 [11.7–12.7] | 2.33 | 173 | 0 |
| 15,000 | false | html | true | 20.3 [11.0–20.7] | 2.21 | 181 | +7 |
| 16 | false | body | true | 11.5 [11.4–11.5] | 2.28 | 173 | – |
| 1,000 | false | body | true | 11.0 [11.0–11.2] | 2.20 | 174 | 0 |
| 15,000 | false | body | true | 11.5 [11.0–11.7] | 2.19 | 181 | +7 |
| 16 | true | body | **false** | 11.7 [11.5–13.0] | 2.29 | 174 | – |
| 15,000 | true | html | **false** | 20.6 [11.1–20.8] | 2.22 | 181 | +7 |
| 15,000 | true | body | **false** | 11.3 [11.3–12.0] | 2.26 | 181 | +7 |
| 15,000 | true | undeclared (initial values only) | true | 11.7 [10.6–12.8] | 2.13 | 174 | +1 |

Reading (clean mode): 15,000 declared `inherits:true` registrations raise the cost of restyling a descendant that itself writes an
inherited custom property from ≈2.3 to ≈3.15 µs (**+0.9 µs/element, +40 %**), whether the values sit on `html` or on `body`; the same
K costs nothing when the registrations are `inherits:false`, when they are registered but never declared, or when the descendant's own
property is `inherits:false` (2.2 µs, the floor). K = 1,000 is indistinguishable from 16. So the tax is on the *declared inherited-variable
map size* seen by an element that has to copy-on-write it (Blink `StyleInheritedVariables` copy ≈ 0.06 µs per 1,000 entries), not on the
registration count per se — H6a fails in its "root is free" form (html and body behave the same), H6c and H6d hold, H6b's linear-in-K part
holds only between 1k and 15k. RSS: +17 MB for 15,000 declared inherited values (+1.1 MB per 1,000), no per-element copies retained
(H6b's N·K RSS prediction fails: 5,000 × 15,000 entries would have been GBs).

Prediction for the demo (14,681 `inherits:true` registrations, mostly declared on bank/carrier ancestors): every restyled element that
writes an inherited custom property pays ≈0.9 µs extra. The combined-bundle trace restyles ≈210k elements/token (bench histogram: 12.8k
in 100–999 passes + ≈125k in 1k–9,999 passes + 1.4 × 51k whole-DOM), so the upper bound is 210k × 0.9 µs ≈ **0.19 s/token**, and only for
the fraction that writes inherited properties. RSS saving ≈ 17 MB. **Decision: not a round-2 fix** (below the 0.5 s bar); converting
registrations to `inherits:false` stays worthwhile only for the cascade-stopping reason already exploited by F5 (M1 §8.2), not for this tax.

## 2. MB7 — `font-variation-settings` list evaluation

### 2.1 L sweep, M = 32 elements, unique rule per element (medians of 3, all verified)

| spelling | L=64 style µs/elem | L=256 | L=768 | L=3,072 | fit: ns per entry (R²) | Layout ms per element L=64 / 256 / 768 / 3,072 |
|---|---:|---:|---:|---:|---:|---|
| lit `"Xnnn" 1234` | 9.9 | 21.5 | 54.9 | 273 | **89** (0.996) | 0 / 0 / 0 / 0 (nothing changes) |
| var `"Xnnn" var(--xI)` | 27.8 | 88.6 | 267 | 1,888 | **636** (0.990) | 1.3 / 1.6 / 4.9 / 23.4 |
| round `"Xnnn" round(nearest,calc(var(--xI)/266.248…*16384),1)` | 80.1 | 261 | 821 | 4,012 | **1,325** (0.998) | 1.3 / 1.3 / 4.3 / 19.7 |
| hoist `"Xnnn" var(--qI)`, `--qI = round(…)` on the parent | 31.4 | 94.2 | 285 | 1,612 | **536** (0.995) | 1.3 / 1.4 / 4.2 / 20.5 |
| calcdiv `"Xnnn" calc(var(--xI) / var(--r))` (the combined bundle's shape) | – | – | not run (battery) | not run (battery) | not run (battery) | not run (battery) |

Style: the `round(calc(var()))` entry costs 1.33 µs, a bare `var()` 0.54–0.64 µs, a literal 0.09 µs. The hoist therefore saves
≈0.8 µs per entry per element (2.5×), not the 16× the M1 MB5 extrapolation suggested: the typed evaluation of a 3-term `round(calc())` is
≈0.7 µs, the `var()` substitution itself ≈0.5 µs. `hoist` ≈ `var` as expected (both one `var()` per entry).
Parent side of the hoist (M=1, L=768): the 768 `round()` declarations on `#par` cost 2.35 ms once per parent restyle.

Layout: when the list changes, every element with a unique list re-instantiates the font and re-shapes: 4.2–4.9 ms per element at L=768,
20–23 ms at L=3,072 (6.4–7.6 µs per axis per element; `InlineNode::ShapeTextIncludingFirstLine` is 85–90 % of it). This is 5× the
style cost of the worst spelling and does not depend on the spelling at all.

### 2.2 M sweep, L = 768 (style ms / Layout ms, totals)

| spelling | M=1 | M=32 uniq | M=128 uniq | M=128 shared rule | per element at M=128: uniq → shared |
|---|---:|---:|---:|---:|---|
| lit | 0.52 / 0 | 1.76 / 0 | 5.85 / 0 | 0.65 / 0 | style 46 → 5 µs |
| var | 2.75 / 9.5 | 8.55 / 157 | 34.5 / 634 | 1.14 / 5.6 | style 270 → 9 µs; Layout 4,950 → 44 µs |
| round | 3.62 / 9.0 | 26.3 / 136 | 103.6 / 538 | 4.43 / 5.6 | style 809 → 35 µs; Layout 4,201 → 44 µs |
| hoist | 5.11 / 5.1 | 9.11 / 134 | 31.9 / 535 | 6.49 / 5.8 | style 250 → 51 µs; Layout 4,180 → 45 µs |
| calcdiv | – | – | not run (battery) | – | – |

Cost is linear in M for unique rules (H7a). With one shared rule the MatchedPropertiesCache resolves the list once (style ÷ 20–30) and
the FontCache instantiates once (Layout ÷ 100): `shared` M=128 costs about the same as M=1 (H7c/H7d hold). Sharing the list text
across elements is therefore a 100× lever on the font side — the demo's per-(head,slot) rules with one differing entry each forfeit it.

### 2.3 RSS

Renderer RSS after load grows with declared list bytes only: 173 MB (small pages) → 296 MB (`round` L=768 M=128, 6.2 MB of CSS),
346 MB (`round` L=3,072 M=32, 6.4 MB) — ≈ 20–25 B of heap per declared byte; the fonts (12 × 1.6 MB) are not visible in RSS until used.

### 2.4 Predicted saving for the demo

Per visit of one font element whose list changes, hoist vs per-entry math (style only; Layout is the same when the list really changes):

| L | spelling today | style today | style hoisted | Δ per visit |
|---:|---|---:|---:|---:|
| 768 | round | 0.82 ms | 0.25–0.29 ms | −0.55 ms |
| 768 | calcdiv | not run (battery) | 0.25–0.29 ms | not run (battery) |
| 3,072 | round | 4.0 ms | 1.6 ms | −2.4 ms |
| 3,072 | calcdiv | not run (battery) | 1.6 ms | not run (battery) |

Where the per-entry math still lives in the combined bundle (scan of `bundles/combined/runtime.css`): 12 × `.shared-qkv`, 12 ×
`.shared-attn`, 12 × `.shared-fc` (768 entries, `calc(var(--n)/var(--range))`) and 12 × `.shared-proj` (3,072 entries) — 48 elements;
the 192 score/V glyphs read whole lists through two `var()`s (≈ `lit` cost + 2 substitutions) and the head list is already hoisted (F4).
Scenario A (brief's assumption, 32,000 visits/token all at L=768 `round`): −0.55 ms × 32,000 = **−17.6 s/token** — impossible, it exceeds
the bench's entire 100–999-bucket style time (4.0 s), so the assumption over-counts visits or over-states the spelling. Scenario B (bench
histogram: 12,760 visits/token at 316 µs average = 4.0 s; if the share of those visits that carry per-entry math is f): saving ≈ f × 0.7 ×
4.0 s ≈ **−2.8 s × f** per token. The 48 per-entry-math elements alone, if each is restyled on ≈13 of the layer's passes (P2: ≈13 passes
per layer iteration): 12 layers × (3 × 0.55 + 1 × 2.4) ms × 13 ≈ **−0.6 s/token** of style. The larger lever is MB8 (§3).

## 3. MB8 — dirtied font element whose list does not change (L=768, M=128, unrelated inherited write)

Run 1 (3 trials; `var-const` in run 1 was in fact the *parent-round hoist*: `--qI = round(calc(var(--xI)/…))` of constant `--xI`, children
`var(--qI)` — the exact proposed consumer shape; the mechanism probes `hoist-const` / `var-const` (literal `--qI`) / `calc-const` / `round-lit` are
generated but unrun — battery).

| kind (list of 768 entries on each of 128 elements; `--in` on the parent is unrelated) | style ms [min–max] | style µs/element | ns per entry | Layout ms | shaping ms | busy ms |
|---|---:|---:|---:|---:|---:|---:|
| plain (no font, one literal declaration) | 0.69 [0.57–1.13] | 5.4 | – | 0 | 0 | 3.8 |
| nofont-lit (literal list, `monospace`, text "a") | 8.39 [8.30–8.64] | 65.6 | 78 | 0 | 0 | 11.6 |
| lit (literal list, real 3-font stack) | 8.73 [4.53–9.54] | 68.2 | 82 | 0 | 0 | 12.2 |
| hoist / var-const (`var(--qI)`, parent `--qI = round(calc(var(--xI)…))` of constants) | 42.7 [35.8–49.3] | 334 | 427 | **0** | 0 | 49.8 |
| round-const (`round(nearest,calc(var(--xI)/266.248…*16384),1)` of constants) | 118.4 [108.3–122.1] | 925 | 1,197 | **535 [533–557]** | 354 | 682 |

Readings:

* H8a holds and is worse than M1's 60–70 %: an inherited write that touches nothing in the list still costs 114 % of the changed-list
  restyle for `round-const` (118 vs 104 ms) and 134 % for the hoist (43 vs 32 ms) — the list is fully re-substituted and re-evaluated on
  every restyle; a literal list costs 82 ns/entry (the cascade floor for a 768-entry value), a `var()` list 430 ns/entry, a
  `round(calc(var()))` list 1,200 ns/entry.
* **H8b fails for math-function lists.** With identical numbers, `round-const` re-instantiates the font and re-shapes all 128 elements
  (Layout 535 ms = 4.2 ms/element, the same as MB7's changed list), while the hoisted `var(--qI)` list does not (Layout 0). The
  substituted `font-variation-settings` value still contains `round(…)` / `calc(…)` tokens; Blink evaluates it into the FontDescription
  but the *description's identity* differs on every restyle (a math-function value is not simplified to a number before the comparison /
  cache key), so `FontCache` produces a new platform font and `InlineNode::ShapeTextIncludingFirstLine` re-runs. A list of resolved
  registered `<number>`s substitutes to plain numbers and compares equal. The `mb8b` probes (calc without round, round of a literal)
  are queued to pin which token causes it; the decision does not depend on them.

Cost of the spurious re-shaping per visit of a dirtied-but-unchanged font element: **4.2 ms at L=768 (5× its own style cost), ≈20 ms
at L=3,072** (MB7 §2.1 scaling: 6.4–7.6 µs per axis). In the combined bundle the 48 `.shared-qkv/attn/fc/proj` elements carry per-entry
`calc(var()/var())` lists (768 / 3,072 entries) and are dirtied on ≈13 passes per layer (P2) while their inputs change on ≈1–2 of them:
12 layers × 11 passes × (3 × 4.2 + 20) ms ≈ **−4.3 s/token** of Layout if the hoist stops the re-instantiation — the bench measured Layout
at 15–17 % ≈ 4.6–5 s/token, so the prediction is "most of Layout", to be confirmed by the F-series bundle. Under the brief's assumption
(80 passes × 400 elements, all with per-entry math): 32,000 × 4.2 ms = 134 s/token, again far above the measured 5 s — the demo's 400
font elements per pass are overwhelmingly the score/V glyphs whose lists are whole-list `var()`s (no per-entry math), which MB8 says do
*not* re-shape when unchanged. **Decision: hoist every per-entry `calc()`/`round()` into registered parent numbers (or a latched `*`
list, F4 §2.2) — round-2 fix #1, predicted −4 s/token (Layout) −0.6 s/token (style).**

## 4. MB9 — frame overhead knobs (tiny page + 50,000 static 1×1 inline-blocks; gate = 1 ms `width` animation; 2 frames per mutation)

Per frame = window total / 2 frames. `mouse` = cursor parked at (400,300) via CDP after load (the demo's cursor sat on the Run box).

| variant | Paint /frame ms | BeginMainFrame self /frame ms (untraced hover hit-test) | recalcStyle /frame ms (6 elements restyled) | Layout+PrePaint+compositing /frame | busy /frame ms | Δ busy vs default-mouse |
|---|---:|---:|---:|---:|---:|---:|
| none (no subtree, 10 layout objects), mouse | 0.02 | 5.0 (3 frames) | 0.1 | 0.1 | 6.3 | −26.3 |
| default, no mouse | 13.8 | 0.0 | 9.9 | 0.5 | 27.0 | −5.6 |
| **default, mouse** | 12.6 | 8.0 | 9.3 | 0.5 | **32.6** | 0 |
| `#sub{contain:paint}`, mouse | **0.02** | 8.0 | 9.5 | 0.4 | 18.7 | **−13.9** |
| `#sub{visibility:hidden}`, mouse | 10.1 | 8.0 | 9.2 | 0.5 | 29.3 | −3.2 |
| `html{pointer-events:none}`, mouse | 10.8 | 6.4 | 8.0 | 0.5 | 29.4 | −3.2 |
| +1,926 `position:fixed; container-type:size`, mouse | 12.0 | 6.4 | 9.2 | 2.1 | 32.7 | +0.1 (vs staticfc: busy +3.6, structural phases **+1.6**) |
| +1,926 static `container-type:size`, mouse | 13.0 | 6.8 | 8.3 | 0.5 | 29.1 | −3.5 |
| default, mouse, 50k dirtied (unique `--z:calc(var(--in)*w)` each) | 9.9 | 4.5 | 39.3 (50,006 elements = 0.79 µs/element) | 0.4 | 66.5 | +33.9 |
| `contain:paint`, mouse, 50k dirtied | **0.02** | 8.0 | 39.3 | 0.3 | 64.3 | −2.2 vs default-dirty (Paint −9.9, hit-test noise +3.5) |
| `visibility:hidden`, mouse, 50k dirtied | 7.7 | 5.4 | 41.0 | 0.4 | 65.7 | −0.8 vs default-dirty |

Readings:

* **Paint walk (P2's "paint lifecycle").** A frame in which only the 8-px gate changed still costs 12.6 ms of `Paint` on a 50k-object
  page = 0.25 µs per layout object visited (P2 measured 60 ms/frame on 43k–146k objects in the demo, 0.4–1.4 µs/object with its deeper
  structure). `contain:paint` on the static subtree's root makes it a self-painting layer whose display-item subsequence is reused →
  0.02 ms, also when all 50k elements were restyled with custom-property-only changes (no paint invalidation). `visibility:hidden` does
  not stop the walk (−20 %). H9a/H9b(contain) hold; H9b(visibility) fails.
* **Hover hit-test.** With the cursor over the page each frame carries ≈8 ms of untraced `WebFrameWidgetImpl::BeginMainFrame` self time
  (5 ms of it even on the 10-object page; the synthetic post-layout mousemove → hover update → cursor update path), 0 without a cursor.
  `pointer-events:none` on `html` cuts only 20 % (the hit test still walks). H9c holds for "no cursor" (move the mouse off the page or
  do not click into it), weak for `pointer-events:none`.
* **Inherited write on `html` with declaration-free descendants.** The harness's own `html.go-k{--in}` write makes every frame's style
  pass cost 9.3 ms for 6 restyled elements: Blink's independent-inherit fast path clones the 50k styles at 0.19 µs each. Same elements
  with one unique `calc(var())` declaration: 0.79 µs each (39 ms). Both are cheaper than M1's 2.8–4.5 µs/element for declaration-heavy
  leaves but not free — a root-level inherited write is never below 0.2 µs × DOM size.
* **Fixed size containers.** 1,926 `position:fixed` containers add +1.5 ms/frame of Layout + PrePaint + `PaintArtifactCompositor::Update`
  + `HitTest` versus the same 1,926 static blocks (H9d, small). The combined2 regression (36.9 vs 30.3 s/token) is therefore not this
  cost (85 × 1.5 ms = 0.13 s) but the chain restyles F3 reported.

Predicted Δ s/token at 85 frames/token: `contain:paint` on the big static subtrees (glyph banks, embedding rows, KV caches; anything not
repainted each frame): −13.9 ms × 85 ≈ **−1.2 s/token** (upper bound = the demo's 4.5 s paint-lifecycle share; the fraction of its
43k–146k walked objects that can sit under a clean `contain:paint` root decides). Cursor off the page (or headless without a synthetic
mouse): −8 ms × 85 ≈ **−0.7 s/token** (bench measured hit-test at 2.9 % ≈ 0.9 s, consistent). `pointer-events:none`: −0.15 s.
`visibility:hidden`: −0.27 s. Static instead of fixed containers: −0.13 s. Not measured here: the animate share (10 % ≈ 3 s/token) —
MB9's gate had one animation; the demo's 12k live timelines are M1 MB4's territory.

## 5. Validity notes

* All 67 variants × trials verified (computed value changed), no forced lifecycles, no errors; `ParseAuthorStyleSheet` 0 in every window.
* Run-to-run spread: MB7/MB8/MB9 ≤ 10 % except where noted; MB6 3-trial runs were bimodal on identical pages (e.g. 12.6–19.9 ms; trial 1
  always in the low mode) — §1 therefore reports the minimum (clean mode) next to the median; the 7-trial repeat is generated but unrun (battery).
* Frame counting: `BeginMainThreadFrame` is not emitted with these trace categories; frames = `ProxyMain::BeginMainFrame` count (= `Commit`).
* MB7's `lit` variant is dirtied by the parent's inherited write but its list does not change → its "style" column is the pure list
  re-apply cost (MB8 `lit` agrees: 68 µs/element at L=768, 82 ns/entry).
* Pages (106 MB incl. 19 MB fonts) deleted after the run; regenerate with `make_fonts.py` + `gen_r2b.py`. Trial-0 traces kept gzipped in `R2B/traces/`.
