# R4X — readback / vector primitives not in the catalog: is there anything that beats view-timelines?

Agent R4X, 2026-09-20/21. Scratch `work/2026-09-19/R4X/` (probe page + runner, fixture generator, pages, results); log
`work/2026-09-19/R4X.log.md`. Chrome 153.0.8010.48 headless, AC + `caffeinate -dims`, one Chrome under `CHROME.lock`
(owner-stamped R4X, touched every 30 s, removed only when ours). Fixture pages contain no JS; the support probe is a
JS-enabled *measurement* page (like the repo's `CSS.supports` probes), never a model page.

## 0. Verdict

**No primitive outside the catalog exists in stock Chrome 153 that moves a geometry into a CSS number, and none of
the enumerated properties/functions removes the frame that view-timelines cost.** Style can read geometry through exactly
four channels (§1): container-query units (2 values per `container-type:size` level, frameless), font-metric units
`ch/ic/ex/cap/lh` (5 values per font *instance*, frameless and layout-free), `anchor-size()` (unbounded fan-in but only
into sizing/inset/margin of positioned boxes — re-verified on 153: never `font-size`, `letter-spacing`, a registered
`<length>`, or `font-variation-settings`), and scroll/view timelines (one frame per hop). Everything in the brief's lists
is one of these, a boolean (`@container` size/style/scroll-state queries, `if()`, `position-try`), a static tree fact
(`sibling-index()`, `attr()`, `env()`), or a number→number transform (`progress()`, `round()`, …). The two functions that
*would* have changed the picture — `container-progress(width of --name)` (a named-ancestor readback that would flatten
F3's inherited chain) and `media-progress()` — **parse on 153 (`CSS.supports` true) but evaluate to 0 in every form**
(§4): stubs, not levers. `anchor-size()` acceptance is unchanged. Style range queries (`style(--v > 5)`), `inherit()` and a
working `random()` are absent.

What the round can use: (1) the **frameless incumbent** for the large hops stays F3's anchor → `position:fixed`
size-container chain (measured here again at 184 µs/value in a 96-value hop, 1 pass / 1 layout / 1 frame, exact to
1/64 px); (2) one **un-catalogued application** of the metric channel: the **scores hop (97 carriers/layer) can be read
with `1ch` on the very elements that already instantiate the 96 bilinear score fonts**, so it is font-instance-neutral —
the wall that killed metric transport at width 768 (E1 §E, `hvar-five-metric-scale`) does not apply. Fixture (§5): 1
style pass, **no shaping, no timelines, one frame**, 368 µs/value all-in (of which ≈ 300 µs is the font instantiation the
page pays today anyway), error 0.007 units vs 0.09 for the timeline path (13× more precise). Projected −0.25 to −0.3 s/token
(97 timelines + 97 changed animations + one 12.7 ms pass per layer), exact-class; sketch in §6.1. (3) `::before`
pseudo-elements are valid view-timeline subjects on 153 (verified) — at most halves carrier *elements*, keeps every
timeline cost; a micro-lever for R4T, not a primitive. Recommendation: hand qkv/fc/proj to the F3/R4S container line
unchanged, build §6.1 for the scores, and re-probe `container-progress()` on each new Chrome.

## 1. What the style system can actually read back (the inventory the enumeration reduces to)

A value that starts as geometry (a glyph advance) can re-enter *style* (a `font-variation-settings` number) through
exactly four Blink channels; every property/function in the brief's lists is either one of these, a boolean, a static
tree fact, or a number→number transform that presupposes the value is already a number:

| channel | what it exposes to style | values per unit | frame? | where it is allowed | catalog |
|---|---|---|---|---|---|
| **container-query units** `cqw/cqh/cqi/cqb/cqmin/cqmax` | content-box width & height of the *nearest* ancestor `container-type: size` box | **2 per container level** (cqmin/cqmax are min/max of the same two) | no (interleaved recalc inside Layout) | any `<length>` (→ `<number>` via typed `calc(… / 1px)`) | E1 #2/#55, F3, M1 §8.4 |
| **font-metric units** `ch ic ex cap lh` (+ `em`) | advance of `0`, advance of `水`, OS/2 x-height, cap-height, line-height of the element's *primary font instance* (HVAR/MVAR applied) | **5 per font instance** (VVAR not exposed; GSUB/cmap14 ignored) | **no — no layout at all** (style-time) | any `<length>` incl. custom properties on the same element; in font properties they resolve against the parent | E1 §E #70/#73, E4 #235, E5 #310 (row-axis), `hvar-five-metric-scale` |
| **`anchor-size()` / `anchor()`** | border-box size / edges of any acceptable anchor (unbounded fan-in via `calc(Σ anchor-size())`) | many → **1 length**, but only into `width/height/min-*/max-*`, insets, margins of a **positioned** box | no | sizing/inset/margin of OOF boxes only; never `font-size`, `letter-spacing`, custom properties, FVS (re-verified on 153, §4) | E1 §B/#5–9, F3 |
| **scroll-/view-timelines** | scroll offset / subject position+size as animation progress on *any* element via `timeline-scope` | 1 progress per timeline (2 with two ranges/axes) | **yes** (+1 pass, +1 layout, +1 frame per hop; 10.7 µs/frame/timeline servicing) | animated registered properties | E1 §B, E4 §D, E6 2h, R3A |

Everything else on the list, checked one by one in §3, collapses onto this table: `font-size → opsz` is a `<length>`
consumer of channel 1/3 (`opsz-container-handoff`, E4 #292); `font-size`/`zoom` multipliers are layout-side rank-1
scalings whose *output* is still geometry (`inline-attention-reducer`, E4 #267); `progress()` is `calc(a/b)`; container
size/style queries, `scroll-state()`, `if()`, `position-try` are booleans; `sibling-index()`, `attr()`, `env()` are static.

## 2. Ranked table

Ranked by expected s/token gain for the geometry→number problem (8k values/layer). "bits" = usable payload precision of the channel;
"µs/value" = this report's fixtures (§5) or the cited measurement; per-token figures use R3A's constants (40 µs per changed
animation, 28 µs per pending add, 10.7 µs per live timeline per frame, 46 frames/token, 12.7 ms per style pass).

| # | candidate | mechanism | exists in 153? | frame removed? | bits | µs/value (measured / est.) | catalog status | verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | **scores hop via `1ch` on the score elements** | glyph `0` of each `FvsDot` font = the score glyph; `--fs-H-S: calc(1ch/1px …)` on the element that already carries that instance; 8 nested slots inherit into the softmax element | yes (§4 t13; §5 arm M) | removes the hop's **style pass + 97 timelines + 97 animations**, not a whole frame (the ctx timeline hop still needs it) | ≈ 18 (float px → 6-digit `var()`; max err 0.007 units on a 1500-unit advance) | **368 measured** (≈ 300 of it = font instantiation paid today anyway; transport ≲ 70) | mechanism E1 #70/#73 (rejected for width 768 on face count); *this application* not in catalog | **build** — −0.25…−0.3 s/token est., exact-class, no model change (§6.1) |
| 2 | anchor → `position:fixed` size-container chain (F3) | `width/height: anchor-size()` → `100cqw/100cqh` → numbers, interleaved recalc in one Layout | yes | **yes** (1 pass, 1 layout, 1 frame per hop) | 48 exact (E1 #55); ≤ 2^24 px window | **184 measured** (96 values); 19 synthetic / ≈100 real-MLP (F3) | **in catalog** (F3, M1 §8.4) | incumbent for qkv/fc/proj; owned by F3/R4S |
| 3 | `container-progress(width of --name, a, b)` | named-ancestor width → number without inheriting through every level; would remove F3's per-level `--v` declarations and the Σdepth restyle | **parses, evaluates 0** (all 6 spellings, §4) | would keep F3's 0 frames | 48 (cq path) | n/a | not in catalog | **not available on 153** — re-probe on each Chrome release |
| 4 | `anchor-size()` in `font-size` / registered `<length>` / FVS | one element gathering 8k anchors with no chain | **no** (`CSS.supports` false; registered length computes 0px) | — | — | — | in catalog (E1 #5–9, `cross-shard-font-composition` on 153) | closed, re-confirmed |
| 5 | `progress(len, a, b)` | length → number | yes (0.3 correct) | no | as source | 0 (pure calc) | not in catalog | = `calc((a−b)/(c−b))`, which Chrome already accepts; **nothing new** |
| 6 | `font-size: 100cqw` → automatic `opsz` | cq length → one axis without `@property` | yes | no (needs the container graph anyway) | 24 (font-size float) | = container graph (262 ms / 3,072 lanes, E4 #292) | **in catalog** | no gain |
| 7 | layout-side multipliers: `font-size` em-scale, `zoom`, `tab-size`, `word-spacing: %` (parses on 153), `letter-spacing: %` | rank-1 multiply of one glyph advance by a style-time number, summed by inline layout | yes | no (output is geometry) | 24 | 1.3–4.2× slower than flat CSS (E4 #267) | **in catalog** (`inline-attention-reducer`); `%` spacing not tried but same class | no |
| 8 | `::before` / `::after` as view-timeline subjects | halve carrier *elements* (2 subjects per host) | **yes** (verified live, §4) | no | 14–18 (timeline) | saves ≤ 5 µs × ≈8.5k carriers per pass ≈ 0.5 s/token upper bound; timelines unchanged | not in catalog | micro-lever for R4T; not a primitive |
| 9 | `scroll-timeline` + declarative scroll offset (`scroll-snap` re-snap after layout; `scroll-initial-target` is one-shot) | scroll offset = value | yes (both properties) | no (snapshot at next `UpdateLifecycle`, same as ViewTimeline) | 14–18 | ≥ timeline + one `ScrollableArea`/PaintLayer per value | not in catalog | rejected on structure (worse compositing/RSS), no fixture |
| 10 | `@container scroll-state()`, `@container (width > x)`, `position-visibility` | geometry → boolean | yes (size query 5 ✓, scroll-state 6 ✓) | size query: frameless; scroll-state: snapshot | 1 | — | size/style stamps in catalog (fix 6); scroll-state "constant-factor" (S4 #227) | gates only |
| 11 | font-metric units for wide hops (`row-axis` bank, 5-metric bank) | 5 numbers per instance, no layout | yes | yes | ≈ 18–24 | ≈ 1,200 (instance creation at 128–256 axes) + 2.8 GB RSS | **in catalog** (E1 §E, E5 #310, `hvar-five-metric-scale`) | closed for 768/3,072-wide hops; only instance-neutral uses (row 1) |
| 12 | `sibling-index()/count()`, `attr(type())`, `if()`, `env()`, `@scope`, `field-sizing`, `text-box-trim` | static / boolean / layout-only | yes (all but none give per-element geometry) | no | — | — | first three in catalog | no |
| 13 | `@container style(--v > 5)`, `inherit()`, `random()`, `media-progress()` | range query / list concat / sampling / viewport → number | **absent or stub** (§4) | — | — | — | `inherit()`/`random()` absent in 151 (S1) — still absent | no |
| 14 | `calc-size(max-content, size)` in FVS / custom property | intrinsic size → number | parses, computes 0px / `normal` | — | — | — | **in catalog** (E1 #56) | closed |

## 3. The enumeration, item by item

### 3.1 `<length>` properties that reach font selection or inline layout without a registered number (brief item 1)

| property | mechanism | rank / where the value ends up | per-glyph cost vs a 256-axis HVAR glyph | catalog |
|---|---|---|---|---|
| `font-size` + `font-optical-sizing: auto` | font-size (px) becomes the `opsz` coordinate | **1 axis per element**; the length must already be style-time (`100cqi`), so it saves only the `@property`, not the container | equal to font-size-only control (3,072 lanes 262.5 ms, dominated by the anchor/container graph) | **in catalog**: `opsz-container-handoff` (E4 #292, #10 in §4) — "exact, free relative to font-size" |
| `font-size` as em-scale | advance_px = units × font-size / upem → **rank-1 multiply** of one glyph's dot product by a style-time scalar; summed by inline layout across spans | output is geometry again; one text run per (glyph, scalar) pair | 1.30–1.66× **slower** than flat CSS at ctx 8–16; +6,144 value spans | **in catalog**: `inline-attention-reducer` (E4 #267) |
| `zoom: <number>` | same multiply at layout level for the whole subtree | rank-1; 4.19× slower than flat | | **in catalog** (same experiment) |
| `font-weight` / `font-width(-stretch)` / `font-style: oblique <angle>` | `<number>` / `<percentage>` / `<angle>` → automatic `wght`/`wdth`/`slnt` | 3 extra axes per element from *numbers* (not lengths): no new readback; `slnt` via oblique failed (Chrome picks −14) | free | **in catalog** (`opsz-container-handoff` "four coordinates") |
| `font-size-adjust: <metric> <number>` | used size = font-size × n / aspect(primary font) → a **division by a font metric** (ex/cap/ch/ic aspect) | rank-1 scaling of all advances by 1/metric; result is geometry | shaping unchanged | not tried as transport; only `ic-height` tried for VVAR (E1 #68, rejected). No gain: division of numbers is free in `calc()` once the metric is a number (channel 2) |
| `letter-spacing`, `word-spacing`, `text-indent`, `padding/border/margin` on inline boxes | add a style-time `<length>` to a run's advance | addition only (rank-0: `+ v·1px`); `word-spacing: <percentage>` (a multiply of the space advance) is not supported in Chrome (§4) | free | `letter-spacing` "reasoning only" for clamp headroom (S3 #338); as adder it duplicates `calc(offset + …)` in `width` |
| `tab-size: <number>` | tab advance = n × advance of the **space glyph** of the primary font (HVAR-variable) — a layout-time multiply of one dot product by a number | one product per line start (tab stops break sums); **one glyph (space) per font instance** → same face-multiplicity wall as `ch`/`ic` | 1 run per product + 1 instance per output row | not tried; dominated by channel 2 (which gives the same product at style time via `calc(var(--w) * 1ch)`) |
| `line-height: <number>` | × font-size → block height | style-time number × style-time length; nothing geometric enters | — | trivial; no |
| `vertical-align`, `text-underline-offset`, `text-decoration-thickness: from-font` | consume MVAR/post metrics in layout/paint | not exposed to style; paint-only | — | no |
| `text-combine-upright: digits`, ruby, MathML `math-depth`/`font-size: math` | layout-only compressions / integer depth counters | `math-depth` is an integer counter (like `sibling-index`), not geometry | — | no |

Nothing in this class produces a rank-k contribution that a *font* does not already produce more cheaply (one 256-axis
glyph = 256 products per shaped glyph, ≈17 µs per row incl. shaping, R3A §3). Every `<length>` consumer needs the length
to be style-time first, which is channel 1 or 2 again.

### 3.2 Functions/features that turn geometry (or tree state) into a value (brief item 2)

| candidate | exists in 153? | what it yields | verdict |
|---|---|---|---|
| container units `calc(100cqw / 1px)` | yes | 2 numbers per size container, frameless, 48 exact bits (E1 #55), ≤ 2^24 px window (F3 §2 #5) | **incumbent frameless primitive** (F3); cost 19 µs/value synthetic, ≈100 µs/value in the real MLP page (F3 §3b) |
| `anchor-size()` in `font-size` / `letter-spacing` / registered `<length>` / FVS | **no** (re-verified: `font-size`/`letter-spacing`/FVS false; registered `<length>` computes `0px`) | would gather 8k anchors on **one** element with no chain | closed; catalog confirmed on 153 |
| `calc-size(max-content, size)` in a custom property / FVS | parses; computes 0px / `normal` | same-element intrinsic size → number | **in catalog**: computes to `normal`/initial in FVS and `@function` (E1 #56, E4 §C); a sizing-only function |
| `sibling-index()` / `sibling-count()` | yes (11 ✓) | tree position integers (static per element) | **in catalog** (E5 #309: −48 % bytes, −2 % cold); not a readback |
| `attr(name type(<number>))` | yes (11 ✓) | attribute → typed number, static (no JS to change it) | **in catalog** (browser-gpt2 `SCALING_WORK.md`); not dynamic |
| `env()` | parses; no value | UA environment constants | no per-element data; no |
| `@container scroll-state(scrollable/stuck/snapped)` | yes (`scrollable: none` applied) | booleans, snapshotted at frame start like timelines | boolean and framed; "constant-factor only" (S4 #227); no |
| `:has()` on `:checked`; `:state()` | yes / custom-elements only (JS) | user input booleans | input channel only (S1 #77) |
| `field-sizing: content` | yes | form control sized to its value text | no readback into style; static value text |
| `text-box-trim` | yes | trims leading/trailing half-leading in layout | layout only; no |
| `@scope` | yes | selector scoping | no data |
| `if(style()/media()/supports())` | yes (7 ✓) | branch on own custom properties / media | **in catalog** (18 docs); boolean gate over numbers already present |
| `random()` | parses; evaluates 0 | pseudo-random number | irrelevant to transport (S1 #76: absent in 151) |
| `progress(a, b, c)` | **yes** (0.3 ✓) | `(a−b)/(c−b)` as a number, for lengths too | **= `calc((a−b)/(c−b))`** with typed arithmetic, which Chrome already accepts (`calc(100cqw/1px)`); adds nothing |
| `container-progress(<feature> [of <name>], b, c)` | **parses, evaluates 0** (6 spellings) | would read the width/height of a **named** ancestor container as a number without inheriting through every level | **not functional on 153** — the one candidate that would have flattened the chain; re-probe later Chromes |
| `media-progress()` | parses, evaluates 0 | viewport feature → number | no per-element data; no |
| `round()/mod()/rem()/sign()/abs()/exp()/log()/pow()` | yes | number→number | **in catalog** everywhere (packing decodes, softmax, GELU) |
| `@container style(--v > 5)` range style queries | no (rule not applied) | boolean compare on custom properties | boolean; `style(--v: 7)` equality already used for stamps (F3/fix 6) |
| `position-try-fallbacks` / `position-try-order: most-width` | yes | layout-time choice among `@position-try` blocks (inset/margin/size/alignment only) | **in catalog** (E5 #308: not an argmax); boolean-class |
| `position-visibility: no-overflow` | parses (not exercised) | hides an anchored box when it overflows — a geometry→visibility boolean, frameless | 1 bit per element; a gate candidate only (not needed: `@container` size queries already gate framelessly) |
| percentages `calc(100% / 1px)` | parses in `CSS.supports`; not resolvable | would read the containing block's width | invalid by spec (percentage type unknown at style time); layout-only |

### 3.3 Cheaper view-timelines (brief item 3)

| idea | removes a frame? | removes per-value animations? | note |
|---|---|---|---|
| `animation-range` variants (`entry/exit/contain/cover`, insets) | no | no | remaps the same progress; the second range = second animation (E4 §D packing, 14 exact bits/coordinate) — **in catalog** |
| one timeline → several animations | no | no | one timeline carries one progress; animations on it all read the same value |
| `scroll-timeline` on a scroller whose offset is set declaratively (`scroll-snap-type: mandatory` + snap target at `margin-left: v`; `scroll-initial-target` is one-shot at first layout — both parse on 153; `scroll-start` does not) | **no** — the scroll offset changes after Layout, the ScrollTimeline snapshot is validated at the next `UpdateLifecycle` like a ViewTimeline | no (still one timeline per value) | and it costs **one scroller (ScrollableArea + PaintLayer) per value** instead of one per stage: worse on compositing inputs (8.5 µs/dirty object, R3A §1) and RSS. Chrome does re-snap after layout (`SnapAfterLayout`), so it *works*, it just cannot be cheaper. Not in catalog (`scroll-snap`: 0 experiments); rejected on structure, no fixture |
| `animation-composition: add/accumulate` | no | no | **in catalog** (E1 §D additive animations, 10–20× slower) |
| `animation-timeline` on a pseudo-element / subject as `::before` | no | no | halves *carrier elements* at most (`::before`+`::after` per host); per-element cascade is 5 µs × ≈8.5k carriers ≈ 40 ms/layer upper bound ≈ 0.5 s/token; timelines/animations unchanged (the 40 µs + 10.7 µs/frame terms). Pseudo-element subjects **work on 153** (`::before` subject drove a reader to 0.5 after two frames) |
| `timeline-scope` placement | no | no | **in catalog** (29 docs); scoping does not change servicing |
| detaching idle timelines | no | yes, while detached | R3A lever 7 (−0.2…−0.7 s), owned elsewhere |

### 3.4 Chrome 153 flags / features (brief item 4)

Stock only. The probe (§4) records every relevant `CSS.supports()` result offline in `support-results.json`; nothing was
enabled. The one backend switch that matters — Fontations for > 256 axes — is auto-selected by an `avar` v2 table and was
costed by R4A (200–600 s/layer): not a lever.


## 4. Chrome 153 support / behaviour probe (`R4X/probe/support.html`, results `R4X/probe/support-results.json`)

Run 1 (07:44Z) + run 2 (08:21Z), headless Chrome 153.0.8010.48, 800×600, `CSS.supports()` plus live
`getComputedStyle` reads on a 300×50 px `container-type: size` box, a 123 px anchor and a 1000 px-wide scroller.
Full JSON: `R4X/probe/support-results{,-2}.json`. Findings that decide the table:

| question | `CSS.supports` | live computed value | reading |
|---|---|---|---|
| `progress(100cqw, 0px, 1000px)` in a registered `<number>` | true | **0.3** (correct) | exists, but it is `calc((a−b)/(c−b))` — Chrome already accepts `calc(100cqw / 1px)`; nothing new |
| `container-progress(width, 0px, 1000px)` nearest / `width of --cq` named / `inline-size` / inside `calc()` / in `width` / on a fixed element | **true** (parses) | **0 in every form** (0 / 0 / 0 / 0 / `auto` / 0) | the function is parsed but not evaluated in 153 — no named-container readback; the 2-values-per-level chain stays |
| `media-progress(width, 0px, 1000px)` | true | **0** (viewport 800 ⇒ 0.8 expected) | same: stub |
| `random(0, 100)` | true (number form only) | 0 | stub; irrelevant to transport anyway |
| `anchor-size(--a width)` in `font-size` / `letter-spacing` / registered `<length>` / `padding-left` / `font-variation-settings` | **false / false / (parses) / false / false** | `16px` (initial) / `normal` / **`0px`** / — / — | confirmed on 153: `anchor-size()` reaches `width/height`, insets and margins only (E1 #5–9, `cross-shard-font-composition`) — a size-container boundary remains mandatory |
| `calc-size(max-content, size)` in `font-size` / registered length | false / parses | — / `0px` | sizing-only (E1 #56) |
| `@container --cq (width > 100px)` named size query | — | **5** (fires, frameless at load) | boolean, catalogued as gate |
| `@container style(--v > 5)` range query | — | 2 (not applied) | range style queries absent; equality `style(--v: 7)` is what fix 6 uses (my equality control queried the wrong element — the container has no `--v` — so it read 2 as well; the mechanism is proven elsewhere: F3, `css-if-multibranch-probe`) |
| `@container scroll-state(scrollable: none)` | true | **6** (applied) | boolean; snapshot-based like timelines |
| `sibling-index()` / `attr(x type(<number>))` / `if(style())` | true | 11 / 11 / 7 | work; static or boolean |
| `inherit(--n)` | **false** | — | still absent (S1 #144) |
| `env(safe-area-inset-left, 42)` | true | 0 | no data |
| `--n: calc(100% / 1px)` | true (parses) | — | percentages cannot resolve at style time; not usable |
| `word-spacing: 50%`, `letter-spacing: 10%` | **true / true** | — | percentage spacing parses on 153 (a multiply of the space/glyph advance by a number in layout) — layout-side rank-1 like `font-size`, one glyph per font; no new readback |
| `font-width: 87.5%` | false (`font-stretch` true) | — | alias not yet |
| font-metric units `ch ic ex cap lh em` in a registered `<number>` | true | 12.002 / 20 / 9.02 / 11.74 / 30 / 300 | channel 2 confirmed style-time |
| `cqw/cqh/cqi/cqmin/cqmax` in a registered `<number>`; `font-size: 100cqw`; `1em` of that | true | 300 / 50 / 300 / 50 / 300 / 300px / 300 | channel 1 confirmed; `zoom: 2` does not perturb the number |
| **`::before` pseudo-element as `view-timeline` subject** | — | `--n` on the reader = **0.5** after two frames (element control at offset 1000 → 0, both correct) | pseudo-element subjects **work** on 153 — carriers could be `::before/::after` (2 per host) — but they are still timelines: same frame, same 40 µs / 10.7 µs terms |
| `scroll-initial-target`, `scroll-marker-group`, `field-sizing: content`, `text-box-trim`, `interpolate-size`, `position-visibility`, `position-area`, `anchor-scope`, `reading-flow`, `corner-shape`, `contrast-color()`, `@function` | all true; `scroll-start` false | — | present; none exposes per-element geometry as a value (§3) |


## 5. Fixture — the scores hop three ways (`R4X/gen_scores.py`, pages `R4X/pages/`, results `R4X/results/scores.*`)

Same synthetic font for all arms (`r4x-score.ttf`: 16 axes `X000–X015` in [−1, 1], 32 HVAR regions, glyph `0` advance =
1500 + Σ cⱼ·xⱼ units, cⱼ ∈ [−30, 30]); 12 "heads" × 8 "slots" = 96 producers, each with its own
`font-variation-settings: "X00j" calc(var(--q-h-j) × K[s][j])` (one distinct font instance per producer, exactly as the
emitter's 96 `FvsDot` carriers); 16 pre-baked input sets `html.go-k{--q-h-j}`; one CDP class mutation on `<html>`
changes all 192 inputs; F3's `proto_run.mjs` (M1 pattern: JS off, fresh context, 1 warm-up, traced mutation, quiescence,
`CSS.getComputedStyleForNode` verification of all 96 numbers against NumPy). 3 trials each, AC, `caffeinate`.

| arm | structure (per layer today ⇔ fixture) | `UpdateLayoutTree` (elements) | `Layout` | frames (`Commit`) | busy ms | style ms | layout ms | exact / within 1e-3 | max abs err (units) |
|---|---|---|---|---:|---:|---:|---:|---|---:|
| **T** view-timeline (today) | 96 `position:absolute` `.metric` carriers in one 65,536 px `.scroller>.track`, `view-timeline` each, one `#reader` with 96 animations, emitter decode `(65536/p − 65536)/0.512` | 2 (100, 1) | 1 (96 shaped runs) | **2** | 37.0 (37.0 / 37.0 / 43.1) | 4.6–6.9 | 23.5–27.2 | 0 / 96/96 | 0.083–0.098 |
| **M** `1ch` metric | 12 chains × 8 nested empty `display:block` elements, each `font:512px R4XScore` + its FVS + `--fs-h-s: calc(1ch / 1px / 0.512)` (registered, inherited), read on the chain bottom | 1 (111) | **1 (2–3 ms, **0 shaped runs**)** | **1** | 35.3 (36.3 / 30.3 / 35.3) | 24.1–31.2 (96 `SimpleFontData` instantiations) | 2.1–3.2 | 0–1 / 96/96 | **0.0068–0.0073** |
| **C** anchor → fixed container chain (F3) | 96 in-flow `anchor-name` carriers; per head 4 nested `position:fixed; container-type:size` boxes (`width/height: anchor-size()`), child declares 2 numbers from `100cqw/100cqh` | 1 (123) | 1 | **1** | 17.5–18.0 | 1.6–1.9 | 14.1–14.6 | 0 / **96/96** | 0.034–0.036 (= 1/64 px ÷ 0.512) |

**Reading.** (i) Only the timeline arm needs a second lifecycle: 2 `UpdateLayoutTree`, 2 `Commit`s (the animation
update of the *next* frame samples the new widths) — M1 §8.4 and R3A reproduced at the scores scale. (ii) The metric arm
does **no shaping at all** (0 `ShapeText` events; its 2–3 ms `Layout` is the block boxes whose font changed) and its
single style pass carries the 96 font instantiations that T and C pay inside `performLayout` (`SimpleFontData` creation
≈ 0.3 ms per instance in style vs ≈ 0.15–0.25 ms via HarfBuzz in layout — the reason M's busy time is not lower than
C's). In the emitter these instances exist today (one per (H,S) score carrier), so M's *marginal* transport cost is the
≈ 4–7 ms of the pass minus the instantiations — well under the 97 animations' 40 µs each + the 12.7 ms fixed second pass
it removes. (iii) Precision: M 0.007 units (6-digit `var()` substitution of a ≈1500-unit value), C 0.035 units (1/64 px ÷
0.512), T 0.083–0.098 units (float32 width + 6-digit progress) — the same ordering R3P §1.2 derived. (iv) The run-2 C
page (carriers re-styled `position:absolute`→`static` inline-blocks) never reached quiescence in the runner and was
killed to free the lock; the C row is run 1 (identical anchors → chain semantics).


## 6. Design sketches

### 6.1 Scores hop through `1ch` (the one primitive application the catalog does not contain)

Today (emitter `browser_gpt2_font_vector_cache.py:238-330`): per layer 96 `<i class="metric fvs-score-H-S">` carriers, each
`font: 512px FvsDot; font-variation-settings: var(--fr-k-S-H), var(--fvs-query-H)` (one distinct font *instance* per
(H,S)), width = `calc-size(max-content, …)` scaled by `--fqs-H · --fr-ks-S-H`, `view-timeline: --fvs-score-H-S inline`;
`.fvs-score-reader` carries 96 animations + 1 stamp animation, decodes `--fs-H-S`, runs the softmax on the same element,
then `--fe-H-S` inherit into the V glyph rows. The hop costs 97 timelines (97 × 10.7 µs × 46 frames ≈ 48 ms/token of
servicing + 97 × 40 µs × 12 changed-animation applications ≈ 47 ms/token), one `ScrollTimeline` re-snapshot pass per layer
(the second style pass of frame `0 126 6919`, R3A §1c) and the stamp/receipt/gate trio.

Sketch (no model change, fonts rebuilt by the tools copy, same axes and codes):

1. **Font**: in each `FvsDot` font (one per layer/head pair or the shared one, as built today) add a cmap entry
   `U+0030 → FvsDot_H` (the '0' glyph *is* the dot glyph; today the glyph sits at `CODEPOINT_BASE`). HVAR unchanged.
   `1ch` on an element whose primary font is that instance is then the bilinear score advance in px, at style time.
2. **Producer elements**: replace the 96 in-flow carriers by 12 chains of 8 nested `display:block` empty elements
   `.fvs-score-H-S` with today's `font` and `font-variation-settings` declarations plus
   `--fs-H-S: calc((1ch / 1px - base_px) * var(--fqs-H) * var(--fr-ks-S-H) * k_H)` (the same decode as the width
   expression, minus the `calc-size` offset/viewport terms). `--fs-*` registered `<number>`, `inherits: true` (today
   `inherits: false`) so the 8 slot values reach the chain bottom; the chain bottom is `.fvs-softmax` (today's softmax
   block moves from the reader to here). No `.scroller/.track`, no `view-timeline`, no `timeline-scope` entries, no
   `@keyframes`, no reader/receipt/gate for this hop: the softmax is now a *style dependency* of the same pass that sets
   the score FVS.
3. **Ordering**: `--fs` on the slot element resolves `1ch` against its **own** font (custom properties use the element's
   font; `font-variation-settings` uses the parent's — E1 #70), so the slot's FVS must not itself depend on `--fs` (it
   does not: it depends on `--fr-k-*` and `--fvs-query-H`).
4. **Gate**: the `fvsscore` stamp is not needed — the V rows depend on `--fe-*` directly; the existing
   `--fvs-value-epoch` container-style gate keeps working because `--fe` now updates in the same pass as the query.

Expected effect: −97 timelines/animations per layer (−1,164 of the ≈10.9k live timelines), no separate second style pass
for the scores (the `6919` V-row pass merges into the `126` pass), no `ScrollTimeline` re-snapshot for it. Precision: the
`ch` channel is the shaped advance in float px (§5 measures it against the timeline decode); the 6-digit `var()`
substitution applies to both paths at the softmax. Cost per value: §5. Risk: the chain adds 8 × 12 = 96 extra font
instantiations? No — the 96 (H,S) instances exist today (each carrier has a distinct FVS); the elements merely move.
The bottom element sees 8 inherited numbers; the score reader today inherits nothing from the carriers, so the V rows'
declaration sets are unchanged.

### 6.2 qkv / fc hops — no new primitive; what the inventory says

For a 768-in / 2,304- or 3,072-out hop every channel in §1 has been costed:

| channel | values per unit | units needed for fc (3,072 out) | frameless? | measured cost | who costed it |
|---|---|---|---|---|---|
| view-timeline (today) | 1 | 3,073 timelines | no (+1 frame, +1 pass, +1 layout) | ≈ 560 µs/value/token (40 changed + 28 pending add + 46 × 10.7 servicing) | R3A §1b–2 |
| container chain | 2 | 12 chains × 128 fixed containers | **yes** | 19 µs/value synthetic, ≈ 100 µs/value in the real MLP page, 1 frame per MLP instead of 3 | F3 §2, §3b |
| font metric units | 5 | 615 instances × 3 input shards | yes | ≈ 1.2 ms/value (instance creation ≈ 1–2 ms at 128–256 axes), 2.8 GB RSS | `hvar-five-metric-scale` |
| `opsz` / `font-size` | 1 axis per element | needs the container graph anyway | yes | = container graph | E4 #292 |

So for qkv/fc the only frameless design remains F3's anchor → `position:fixed` size-container chain; nothing enumerated
here adds a channel with > 2 values per element or removes the depth-128 chain. The one thing that would have changed
this — a named-container readback (`container-progress(width of --name)`) or `anchor-size()` accepted in a custom
property — **does not exist on 153** (§4: `container-progress()` parses but evaluates 0; `anchor-size()` rejected outside sizing/inset/margin). R4X therefore hands the qkv/fc hops back to the F3 line unchanged and recommends spending
the fixture budget on §6.1 (scores) and the LN-statistics/small hops where channel 2 is instance-neutral.


## 7. Method / caveats

- Chrome 153.0.8010.48 headless via the repo's Playwright (node v24.19.0), AC power, `caffeinate -dims`; two lock holds
  (07:44–08:00Z, 08:21–08:35Z), owner-stamped `R4X`, touched every 30 s, released by `rmdir` of our own lock only; waited on
  R4C → R4D → B5 for ≈ 2 h 40 min in total; never launched next to another headless Chrome (pattern
  `^/Applications/.*Google Chrome .*--headless` checked before launch).
- Fixture harness: `work/2026-09-19/F3/proto_run.mjs` unchanged (M1 pattern: JS-disabled context, load → quiescence →
  1 warm-up mutation → traced CDP `html.class=go-k` mutation → quiescence → `CSS.getComputedStyleForNode` verification).
  3 trials per arm; the T/M numbers are run 2 (corrected pages), C is run 1. Run-1 T decoded wrong values because inline
  sibling subjects accumulate start offsets (fixed by copying the emitter's `position:absolute` `.metric`); run-1 M read
  the base advance because a later `.s{font:…}` shorthand reset `font-variation-settings` (fixed by rule order) — both
  runs' cost counts were unaffected, only the values.
- The support probe is a JS-enabled page (`CSS.supports` + `getComputedStyle`) — a measurement fixture, like the repo's
  `tools/test_*_probe.mjs`; no flag was enabled. Two of its controls were mis-specified (`style(--v: 7)` queried the
  container, not the element; `width: calc(container-progress()…)` fell back to `auto`) and are read accordingly.
- Per-token projections use R3A's fitted constants and the combined4 frame structure; they are not paired benches.
- Nothing under repo `tools/` or `experiments/` was modified; no bundle produced; fonts are synthetic (5.2 KB).
