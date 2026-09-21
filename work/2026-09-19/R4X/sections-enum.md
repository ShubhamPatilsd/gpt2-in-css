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
| `anchor-size()` in `font-size` / `letter-spacing` / registered `<length>` / FVS | «anchor» | would gather 8k anchors on **one** element with no chain | «anchor-verdict» |
| `calc-size(max-content, size)` in a custom property / FVS | «calcsize» | same-element intrinsic size → number | **in catalog**: computes to `normal`/initial in FVS and `@function` (E1 #56, E4 §C); a sizing-only function |
| `sibling-index()` / `sibling-count()` | «sib» | tree position integers (static per element) | **in catalog** (E5 #309: −48 % bytes, −2 % cold); not a readback |
| `attr(name type(<number>))` | «attr» | attribute → typed number, static (no JS to change it) | **in catalog** (browser-gpt2 `SCALING_WORK.md`); not dynamic |
| `env()` | «env» | UA environment constants | no per-element data; no |
| `@container scroll-state(scrollable/stuck/snapped)` | «ss» | booleans, snapshotted at frame start like timelines | boolean and framed; "constant-factor only" (S4 #227); no |
| `:has()` on `:checked`; `:state()` | yes / custom-elements only (JS) | user input booleans | input channel only (S1 #77) |
| `field-sizing: content` | «fs» | form control sized to its value text | no readback into style; static value text |
| `text-box-trim` | «tbt» | trims leading/trailing half-leading in layout | layout only; no |
| `@scope` | yes | selector scoping | no data |
| `if(style()/media()/supports())` | «if» | branch on own custom properties / media | **in catalog** (18 docs); boolean gate over numbers already present |
| `random()` | «random» | pseudo-random number | irrelevant to transport (S1 #76: absent in 151) |
| `progress(a, b, c)` | «progress» | `(a−b)/(c−b)` as a number, for lengths too | **= `calc((a−b)/(c−b))`** with typed arithmetic, which Chrome already accepts (`calc(100cqw/1px)`); adds nothing |
| `container-progress(<feature> [of <name>], b, c)` | «cprog» | would read the width/height of a **named** ancestor container as a number without inheriting through every level | «cprog-verdict» |
| `media-progress()` | «mprog» | viewport feature → number | no per-element data; no |
| `round()/mod()/rem()/sign()/abs()/exp()/log()/pow()` | yes | number→number | **in catalog** everywhere (packing decodes, softmax, GELU) |
| `@container style(--v > 5)` range style queries | «range» | boolean compare on custom properties | boolean; `style(--v: 7)` equality already used for stamps (F3/fix 6) |
| `position-try-fallbacks` / `position-try-order: most-width` | yes | layout-time choice among `@position-try` blocks (inset/margin/size/alignment only) | **in catalog** (E5 #308: not an argmax); boolean-class |
| `position-visibility: no-overflow` | «pv» | hides an anchored box when it overflows — a geometry→visibility boolean, frameless | 1 bit per element; a gate candidate only (not needed: `@container` size queries already gate framelessly) |
| percentages `calc(100% / 1px)` | «pct» | would read the containing block's width | invalid by spec (percentage type unknown at style time); layout-only |

### 3.3 Cheaper view-timelines (brief item 3)

| idea | removes a frame? | removes per-value animations? | note |
|---|---|---|---|
| `animation-range` variants (`entry/exit/contain/cover`, insets) | no | no | remaps the same progress; the second range = second animation (E4 §D packing, 14 exact bits/coordinate) — **in catalog** |
| one timeline → several animations | no | no | one timeline carries one progress; animations on it all read the same value |
| `scroll-timeline` on a scroller whose offset is set declaratively (`scroll-snap-type: mandatory` + snap target at `margin-left: v`; `scroll-initial-target` is one-shot at first layout — «sit») | **no** — the scroll offset changes after Layout, the ScrollTimeline snapshot is validated at the next `UpdateLifecycle` like a ViewTimeline | no (still one timeline per value) | and it costs **one scroller (ScrollableArea + PaintLayer) per value** instead of one per stage: worse on compositing inputs (8.5 µs/dirty object, R3A §1) and RSS. Chrome does re-snap after layout (`SnapAfterLayout`), so it *works*, it just cannot be cheaper. Not in catalog (`scroll-snap`: 0 experiments); rejected on structure, no fixture |
| `animation-composition: add/accumulate` | no | no | **in catalog** (E1 §D additive animations, 10–20× slower) |
| `animation-timeline` on a pseudo-element / subject as `::before` | no | no | halves *carrier elements* at most (`::before`+`::after` per host); per-element cascade is 5 µs × ≈8.5k carriers ≈ 40 ms/layer upper bound ≈ 0.5 s/token; timelines/animations unchanged (the 40 µs + 10.7 µs/frame terms). Pseudo-element subjects «pseudo» |
| `timeline-scope` placement | no | no | **in catalog** (29 docs); scoping does not change servicing |
| detaching idle timelines | no | yes, while detached | R3A lever 7 (−0.2…−0.7 s), owned elsewhere |

### 3.4 Chrome 153 flags / features (brief item 4)

Stock only. The probe (§4) records every relevant `CSS.supports()` result offline in `support-results.json`; nothing was
enabled. The one backend switch that matters — Fontations for > 256 axes — is auto-selected by an `avar` v2 table and was
costed by R4A (200–600 s/layer): not a lever.
