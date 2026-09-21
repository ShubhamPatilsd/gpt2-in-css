Run 1 (07:44Z) + run 2 («run2time»), headless Chrome 153.0.8010.48, 800×600, `CSS.supports()` plus live
`getComputedStyle` reads on a 300×50 px `container-type: size` box, a 123 px anchor and a 1000 px-wide scroller.
Full JSON: `R4X/probe/support-results{,-2}.json`. Findings that decide the table:

| question | `CSS.supports` | live computed value | reading |
|---|---|---|---|
| `progress(100cqw, 0px, 1000px)` in a registered `<number>` | true | **0.3** (correct) | exists, but it is `calc((a−b)/(c−b))` — Chrome already accepts `calc(100cqw / 1px)`; nothing new |
| `container-progress(width, 0px, 1000px)` nearest / `width of --cq` named / `inline-size` / inside `calc()` / in `width` / on a fixed element | **true** (parses) | **0 in every form** («cprog-live») | the function is parsed but not evaluated in 153 — no named-container readback; the 2-values-per-level chain stays |
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
