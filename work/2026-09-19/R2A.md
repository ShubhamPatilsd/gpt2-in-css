# R2A — round-2 trace anatomy of the `combined` bundle (no Chromium runs)

Agent R2A, 2026-09-19. Read-only analysis of the existing light traces. Scratch + parsers: `work/2026-09-19/R2A/`
(`frame_anatomy.py` streaming per-frame parser derived from P2's `parse_trace.py`; `topology.py`, `pass_populations.py`
for the DOM; outputs `*-frames.md/.json`, `anatomy-tables.md`, `pass-populations.txt`, `fvs-shapes.txt`). Log: `R2A.log.md`.

Trace used: `bench/runs/combined/combined-t1-trace.json.gz` (141 MB gz, 33.8 M events; the P2-run mark was lost to
ring-buffer data loss, so times are relative to P2-end − generate wall, exactly as B0's summary does). Window analysed:
**token 5** (93,016–129,341 ms after run; 36.3 s traced wall; 85 frames, 171 style passes, 109 layouts) and token 4 as a
stability check (numbers agree within 3 %; `R2A/combined-tok4-frames.md`). Comparison: `bench/runs/F3a/F3a-t1-trace.json.gz`
token 5 (39.1 s, 73 frames). Traced tokens run ≈20 % slower than the untraced 30.3 s median; all ms below are traced-window
values, scale by ≈0.83 for untraced s/token. Elements in `combined` index.html: 69,522 (html.parser walk).

## 0. Headline

1. **A frame costs ≈ 105–120 ms before any compute** (median: animate 59.5 + `UpdateLifecycle` self 23.9 + paint-lifecycle
   floor 18.7 + hover hit-test 16.7 (61 of 85 frames) + 2×7.5 `UpdateLayoutTree` fixed), and essentially all of it is
   **per-live-timeline bookkeeping**: ≈19,200 `AnimationTimeline::serviceAnimations` calls per frame (10,858 view-timelines,
   each serviced once in the animate step and once per style pass), snapshot validation of the same 10.9 k
   `ScrollSnapshotClient`s in `UpdateLifecycle`, and `PendingAnimations::Update` in the paint phase. F3a, which has 3,842 fewer
   timelines, pays 57 ms instead of 103 ms for the same empty frame → **≈11 µs per live view-timeline per frame ≈ 0.95 ms/token
   per timeline ≈ 9–10 s/token for the 10.9 k carriers** (≈30 % of the token). This is the block RESULTS-round1 calls
   "frames 35 %".
2. **"Paint lifecycle 16 %" (5.68 s/token) has nothing to do with painting or layers** (`Paint` 14 ms, ≈12 cc layers,
   `PaintArtifactCompositor::Update` 4 ms). Regression over the 85 frames (R² = 0.97):
   `RunPaintLifecyclePhase self = 18.7 ms + 26.7 µs × (animations re-queued in PendingAnimations) + ≈110 µs × (CSS
   transitions started/ended)`. Per token: 1.6 s floor + **3.05 s for 114 k pending-animation updates** (every carrier
   animation whose timeline moved, 8.5 k per layer) + **1.0 s for the 9.3 k latch transitions** (769 `--saved-*` per layer
   + 26 `--fc-*` bank latches). It is `DocumentAnimations::UpdateAnimations(kPaintClean)` → `PendingAnimations::Update` →
   `Animation::PreCommit` per animation [inference from Blink structure; the trace only shows the self time].
3. **The 100–999-element passes (55 % of style) are not `font-variation-settings` list evaluation.** In `combined` the four
   stage lists are `"Xnnn" calc(var(--h) / var(--range))` — **zero `round()`** (the 1,044 `round(` in the sheet are 768
   `--hq-N` head publishers, 200 `width` and 76 gate stamps). The lists live on 4 wrapper elements per layer and cost
   ≈5,400 `calc()` evaluations ≈ 15–20 ms/layer ≈ **0.2 s/token (≈2 % of the bucket)**. The bucket is 5 populations
   (126 / 784 / 780 / 357 / 485) whose cost fits `5 µs × elements + 40 µs × (timeline animation whose timeline changed) +
   22 µs × (timeline animation restyled unchanged) + 218 µs × (transition started)` for all populations **except the two
   loop-handshake passes (357 and 485 elements, 208 + 223 ms per layer = 5.2 s/token), which cost 3–6× the model** — the
   biggest unexplained item (§2, §6).
4. The whole-DOM pass is exactly **1 per token** (the 1.4 in the histogram is 7 passes over 5 complete tokens plus two
   partial windows), it is the head matmul itself (`--head-fvs` flips `.full-head`'s font → 50,257 rows must restyle), and
   the frame that contains it costs 3.5 s/token = 10 %: style 0.8 s, **layout 1.42 s, compositing inputs 0.94 s, pre-paint
   0.98 s**, paint 0.22 s. Compositing inputs + pre-paint over the whole token (3.7 s) fit 18.8 µs × dirty layout objects
   (R² 0.90), consistent with a PaintLayer per `overflow:hidden` box (50,257 `.head-row` + 8,551 `.metric`).
5. Frames per token = 12 × (4 hop frames + 1 pass-advance frame + 2 pulse-end frames) + 1 head frame = 85. The 24
   pulse-end frames do 1-element style passes and cost 103 ms each (2.5 s/token); the 12 pass-advance frames cost 312 ms
   each, 223 ms of it the 485-element pass.

## 1. Anatomy of one frame (Q1)

Main-thread events inside `ProxyMain::BeginMainFrame`, token 5, 85 frames (`R2A/anatomy-tables.md`). "Sum" = per token.

| event (nesting) | median ms/frame | mean | sum ms/token | frames with it | median count/frame |
|---|---:|---:|---:|---:|---:|
| **frame** (`ProxyMain::BeginMainFrame`) | 333 | 426 | 36,177 | 85 | 1 |
| `WebFrameWidgetImpl::BeginMainFrame` = animate step | 59.5 | 55.0 | 4,677 | 85 | 1 |
| ├ `PageAnimator::serviceScriptedAnimations` **self** | 29.8 | 29.8 | 2,536 | 85 | 1 |
| └ `AnimationTimeline::serviceAnimations` (in animate) | 24.7 | 25.5 | 2,164 | 85 | ≈10,000 |
| `WebFrameWidgetImpl::UpdateLifecycle` **self** (scroll-snapshot validation, untraced) | 23.9 | 23.9 | 2,029 | 85 | 1 |
| `LocalFrameView::UpdateStyleAndLayout` iterations | — | — | — | 85 | **2** (max 2 per frame) |
| `UpdateLayoutTree` incl. | 224.7 | 192.4 | 16,356 | 85 | 2 |
| ├ `UpdateLayoutTree` self + `Document::updateStyle` self (fixed ≈ 7.5 ms/pass) | 7.5 | 9.0 | 764 + 369 | 85 | 2 |
| ├ `Document::recalcStyle` self | 195.8 | 155.5 | 13,215 | 85 | 2 |
| └ `AnimationTimeline::serviceAnimations` (inside style passes, `UpdateAnimationTimingIfNeeded`) | — | 13.2 | 1,122 | 85 | ≈5,200/pass |
| `Layout` incl. | 38.0 | 73.2 | 6,219 | 61 | 2 |
| └ `InlineNode::ShapeTextIncludingFirstLine` | 0 | 26.0 | 2,210 | 48 | 3,842 |
| `Blink.CompositingInputs.UpdateTime` | 0.5 | 20.6 | 1,753 | 69 | 2 |
| `PrePaint` incl. | 2.0 | 23.2 | 1,970 | 85 | 2 |
| `LocalFrameView::RunPaintLifecyclePhase` incl. | 38.5 | 66.8 | 5,678 | 85 | 1 |
| ├ `Paint` / `Blink.Paint.UpdateTime` | 0.2 | 0.2 | 14 / 31 | 61 | 2 |
| ├ `PaintArtifactCompositor::Update` / `Layerize` / `Commit` | 0.0 / 0.1 / 0.1 | | 4 / 4 / 22 | 85 | 1 |
| └ **self** (= `PendingAnimations::Update`, untraced) | 38 | 66.4 | 5,642 | 85 | 1 |
| `EventHandler::handleMouseMoveEvent` (hover update after layout; `HitTest` at (150,28) = `INPUT#run`) | 16.7 | 12.6 | 1,072 | 61 | 1 |
| `V8.GC_*` nested | 12.3 | 19.5 | 1,661 | 77 | — |
| gap between frames (idle) | 1.6 | 1.8 | 153 | 84 | — |

- Layer count is irrelevant: `UpdateLayer` ids 9–11, `LayerTreeHost::DoUpdateLayers` 14 µs; `Layerize` 0.1 ms. No `cc::`
  layer-count args exist in the light trace; the compositor thread is busy 2.1 s over the whole run.
- Which sub-event dominates "paint lifecycle"? `RunPaintLifecyclePhase` **self** (99.4 %). Per-frame regression
  (token 5, R² 0.974; token 4 gives 18.5 / 26.4 / 109 µs, R² 0.979):
  `self = 18.7 ms + 26.7 µs × pendingAdds + 126 µs × transition ends − 19 µs × starts` (starts ≈ ends, net ≈ 107 µs per
  latch transition). `pendingAdds` = `LocalFrameView::ScheduleAnimation` events from `pending_animations.cc:Add`, i.e.
  animations whose timeline moved this frame: 2,331 (qkv hop), 830 (V rows), 3,842 (fc + proj hops), 2,308 (loop hop);
  114 k per token. Correlation with the number of composited layers: none (constant); with layout objects: none (the
  alternative regression on serviceAnimations / styled elements / dirty layout objects gives R² 0.53).
- Compositing inputs + pre-paint (3.7 s/token) fit `−50 + 18.8 µs × dirty layout objects` (R² 0.90); 1.9 s of it is the
  head frame (101,164 dirty objects).
- Animate step fits `30.7 ms + 1.18 µs × serviceAnimations calls` (R² 0.48 — the self part is the timeline iteration
  and `ValidateTimelines`; ≈10 k timelines).
- Fixed cost per `UpdateLayoutTree` even with 0 or 1 element: ≈17 ms (61 hover-forced 0-element passes + 24 pulse
  1-element passes = 1.45 s/token), of which ≈6.5 ms is servicing ≈5.2 k timelines and ≈7.5 ms `UpdateLayoutTree`/
  `updateStyle` self.

### F3a comparison (why combined2 lost) — same frame anatomy, token 5, 73 frames

| | combined (85 frames) | F3a (73 frames) | Δ |
|---|---:|---:|---:|
| animate (`BeginMainFrame` incl.), median / sum | 59.5 ms / 4.68 s | 34.7 ms / 2.32 s | −2.4 s |
| `serviceAnimations` calls per frame | 19,172 | 11,014 | −42 % (3,842 fewer timelines) |
| `UpdateLifecycle` self, median / sum | 23.9 / 2.03 s | 11.9 / 0.85 s | −1.2 s |
| `RunPaintLifecyclePhase` incl., sum | 5.68 s | 3.30 s | −2.4 s (floor 18.7 → 10.9 ms) |
| hover hit-test, sum | 1.07 s | 0.62 s | −0.45 s |
| empty (1-element) frame, median | 103 ms | 57 ms | **−46 ms per frame** |
| style (`UpdateLayoutTree`), sum | 16.36 s | 9.65 s | −6.7 s |
| **`Layout`, sum** | **6.22 s** | **21.27 s** | **+15.1 s** |
| └ `performLayout` self | 3.63 s | 17.08 s | +13.5 s |
| compositing inputs + pre-paint | 3.72 s | 3.71 s | 0 |
| chain frame `0 3092 347` (replaces combined's C+D frames 624+719 ms) | — | 1,493 ms, of which **Layout 1,085 ms** (8,141 dirty objects) | +150 ms/layer |

So the anchor/`position:fixed` container chain did **not** raise paint-lifecycle cost (it fell by 2.4 s because the fc/proj
carriers and their 3,842 timelines are gone); it moved the work into **layout**: the 1,926 nested `anchor-size()`
containers re-lay out at ≈1.1 s per layer (13 s/token) — the "Anchor positioning" invalidations of P2 Table 4 — which
outweighs the −6.7 s style, −2.4 s animate, −2.4 s paint and 12 fewer frames. Corrects RESULTS-round1's "1,926
`position:fixed` containers raised paint-lifecycle cost".

## 2. The 100–999-element passes (Q2) — 9.2 s of 16.4 s style in token 5 (56 %)

Populations identified by gate-aware subtree sizes of `bundles/combined/index.html` (`R2A/pass-populations.txt`; a
`content-visibility:hidden` gate contributes itself but no descendants; `.reused-final-export` is `display:none` outside
layer 11). Restyles/token are counted from the frame table; "min" = restyles implied by the data flow (one per hop per layer).

| elementCount | population (root, gate state) | hop / trigger | restyles per token (min) | ms/pass | µs/element | what the cost is (model: 5 µs/elem + 40 µs/changed anim + 22 µs/unchanged anim + 218 µs/transition) |
|---:|---|---|---:|---:|---:|---|
| **126** | `.shared-qkv-c0` subtree with the score gate closed: 5 qkv consumers (2,304 timeline anims) + receipt + gate + `.fvs-query` + 12 `.fvs-bank` + 97 score carriers + score reader/receipt/gate + cache-bridge chain | qkv readback → `--qkv-*` → `--fvs-live-*` → bank write (26 `--fc-*` transitions) → 96 score glyph fonts | 12 (12) + 1 variant | 131 | 1,040 | 2,304 changed anims ≈ 92 ms + 26 transitions ≈ 6 ms + 96 font instantiations + bank alias substitution (≈30 ms). fvs: 96 two-entry lists + 12 × 64-axis `--fvs-live` lists ≈ 3 ms |
| **784** | `.shared-fc-c0` subtree, fc gate open / proj gate closed: 6 fc consumers (3,072 anims) + receipt + gate + `.shared-proj` + 769 proj carriers + proj-c0/c1 (768 anims, unchanged) + receipt + gate | fc readback → `--hidden-*` → proj list (3,072 entries) | 12 (12) | 120 | 153 | 3,072 changed anims ≈ 105 ms (model 145: fc anims are cheaper, ≈30 µs); **fvs list 3,072 × `calc(var()/var())` ≈ 10 ms (8 %)** |
| **780** | `.cache-bridge-c0` subtree, bridge open / attn closed: 2 consumers (768 anims) + receipt + gate + `.shared-attn` + 769 attn carriers + attn-c0/c1 + receipt + gate | V-row readback → `--ctx-*` → attn list (768 entries) | 12 (12) | 42 | 54 | 768 changed anims ≈ 31 ms + 780 × 5 µs; fvs ≈ 3 ms |
| **357** | `.loop-reader` (1,538 loop anims) + `.loop-input` (768 `--loop-in-i` calcs) + ≈354 of the 577 `svg.loop-signals` g/set elements | loop-bank readback → `--lp-b-i` → `--loop-in-*`; starts `loop-pulse` on `#loop-ready-N` | 12 (12) + 1 variant (368) | 208 | 583 | **model predicts 64 ms; measured 208** — 1,538 anims on one element and/or the SMIL `<g>/<set>` restyle; no fvs |
| **485 / 484** | `.core-controller`, `.core-block`, `.loop-reader`, `.loop-input`, `svg.loop-signals` + 384 `<g>` + 96 `<set>` | pass advance: SMIL `<set class=done>` → `:has()` → `--pass`+1 → `@container loopcontrol style(--pass:N)`; starts `loop-pulse` on `#loop-ack-N` | 12 (**0** — protocol, not data flow) + 1 variant (487) | 223–237 | 470 | **model predicts 36 ms; measured 223** — same anomaly; nothing in it evaluates fonts |

Sum: 12 × (131 + 120 + 42 + 208 + 228) + variants ≈ 9.2 s/token of traced style. `font-variation-settings` list
evaluation inside this bucket ≈ 12 × (10 + 3 + 3) ≈ 0.2 s/token; the qkv list (768 entries) sits in the 2,934-pass
(§3). **Per-entry shape (`R2A/fvs-shapes.txt`): `.shared-proj` 3,072 entries × 2 `var()` + 1 `calc()`, 158,743 B, 12 copies
(one per `--layer` block); `.shared-qkv/attn/fc` 768 entries × 2 `var()` + 1 `calc()`, ≈35 KB each × 12; `.fvs-v-H-S`
(96 rules) `var(--fr-v-S),"P000" var(--fw-H-S)`; `.fvs-score-H-S` (96) `var(--fr-k-S),var(--fvs-query-H)`; `.full-head`,
`.head-fine` `var(--head-fvs)`; `.embedding-source` 2 entries with one `round()`. No `round()` in any stage list** — round-2
target 1 ("hoist per-axis rounding into the publishers") has no target in this bundle.

What the 316 µs/element really is: per-animation work on the few consumer elements. Fit over the 7 non-loop populations
(`R2A.log.md` item 23): 5.0 µs per restyled element, **40 µs per timeline animation whose timeline changed** (the
`--p-i` keyframe interpolation is re-applied and the animation re-queued), 22 µs per animation restyled with an unchanged
timeline, **218 µs per CSS transition started** (the 769 `--saved-b-i` latches, §3). The loop passes (357, 485) are
3–6× above the model (≈330 ms/layer ≈ 4 s/token unexplained; candidates: the 1,538-name `animation-name/-timeline` lists
of `.loop-reader` resolved against `html{timeline-scope}` (3 competing `html{}` rules, last one 3,181 names), or the 480
SVG `<g>`/`<set>` SMIL elements under 96 `@container loopcontrol style(--pass:N)` rules).

## 3. The 1k–9,999-element passes (Q3) — 5.8 s of 16.4 s (35 %)

| elementCount | population | hop | restyles/token (min) | ms/pass | µs/element | cost content |
|---:|---|---|---:|---:|---:|---|
| **3,089** | `.shared-attn-c0` subtree, attn gate open / fc closed: attn-c0/c1 (768 anims) + receipt + gate + `.shared-ln2` + `.shared-fc` (768-entry list) + 3,073 fc carriers + fc-c0..c5 (3,072 anims, unchanged) + receipt + gate | attn readback → `--r-*` → LN2 → fc fonts | 12 (12) | 112 | 36 | 768 × 40 + 3,072 × 22 + 3,089 × 5 ≈ 113 ✓; fvs list 768 entries ≈ 3 ms |
| **2,934** | `.core-controller` → `.core-block` → `.loop-reader` → `.loop-input` (+ 577 loop-signals) → `.loop-compute` → `.reused-input` (768 `--x`) → `.shared-ln1` → `.shared-qkv` (768-entry list) + 2,305 qkv carriers + 5 consumers (2,304 anims, unchanged) + receipt + gate; all stage gates closed | S1: `--loop-phase`/`--pass` → new `--x` vector | 12 (12) + 1 variant (2,917 at token start) | 104 | 35 | 3,842 × 22 + 2,934 × 5 ≈ 98 ✓ |
| **1,553** | `.shared-proj-c0` subtree, all gates open: proj-c0/c1 (768 anims) + receipt + gate + `#reused-result` + probe + `.loop-bank-1` (769 `--saved-1-i`) + 769 loop carriers + `.loop-bank-0` (769) + 769 carriers + `#loop-result` | proj readback → `--out-*` → loop-bank latch: **769 transitions start + 769 end** | 12 (12) | 205 | 132 | 769 × 218 µs ≈ 168 ms + 768 × 40 + 1,553 × 5 ≈ 206 ✓ — it is the latch, not the `:nth-child` bucket F5 removed |
| **6,919** | `.fvs-score-reader` subtree: reader (96 anims) + receipt + gate + `.fvs-softmax` + `.cache-bridge-source` track + 768 `span.fvs-value-row` (view-timelines) + 6,144 `i.fvs-v-H-S` | scores readback → softmax → 96 V fonts → row widths | 12 (12) | 38 | 5.5 | pure inheritance propagation: 6,919 × 5 µs; the 96 two-entry glyph lists are the only fvs work |
| 2,326 | `.shared-fc-receipt` subtree with all gates open (proj stage + `#reused-result` + `.loop-bank-1` chain) | layer-11 → head hand-over (`--epoch`/`--native-pass` republish on the receipt), same frame as the head pass | 1 (1) | 215 | 92 | 769 transitions of the layer-11 bank in the same frame |
| 1,438 + 2,917 | embedding consumers (3 × 256 anims) → `#embedding-result` → `.position-embedding` → S1 of layer 0 (2,917 = 2,934 − 17 `epoch-reader`s) | token start: `--saved-token-N` → `--feedback` → embedding readback → `--x` | 1 + 1 | 105 + 158 | 73 / 54 | as 2,934 |

All 12/token populations are at the data-flow minimum. The per-element costs are 5–36 µs except the latch pass; the
retained-list latch (`.loop-bank-0/1{transition-property: 769 names}`) costs ≈218 µs per transition start in style plus
≈107 µs in the paint phase (§1) ≈ **0.25 s per layer ≈ 3 s/token** in total for 9,228 `--saved-*` transitions per token.

## 4. The whole-DOM pass (Q4)

- Exactly **1 per token** (7 passes in the 7 windows incl. two partial ones; token 5 at 125,351 ms = 3,990 ms before the
  token-5 latch, 1,994 ms before `token-5-ready`). elementCount 51,247 = `.b11-bridge-c0` subtree with `.full-head` open
  (51,150) + the `.detached-head-reader` token-slot chain (76) + ≈20 body-level readers; **the core (16.1 k) is not in it**
  (F5's scoping worked).
- Frame anatomy of the head frame (`0 2326 51247`, 3,543 ms; token 4: 3,726 ms): style 17 + 219 + 578 ms, `Layout`
  31 + **1,416 ms (101,164 dirty of 141 k objects)**, **compositing inputs 935 ms, pre-paint 975 ms**, paint lifecycle
  222 ms (771 transitions incl. layer-11's 769 `--saved-1-*`, `--head-fvs`, `--head-input-epoch`), 3,078 pending adds
  (769 b11-bridge carriers + …).
- Cause (invalidation tracking is not in the light trace; inferred from the transitions that start in the same frame and
  F4 §2.2): `.head-input-bank` receives `--head-fvs` (`*`, **inherits:true**) and `--head-input-epoch`; `@container headinput`
  flips `.full-head{content-visibility}` open and `.full-head{font-variation-settings:var(--head-fvs)}` changes the
  inherited font of all 50,257 `i.head-row` + 256 `.head-fine-row`. **The restyle is the head matmul**: each row's
  `width:calc-size(max-content, round(...))` must be re-shaped, so the 51 k restyle and the 101 k-object layout are inherent.
  Only the 0.8 s of style is "restyle"; the remaining 2.9 s of the frame are layout (1.4 s), compositing inputs (0.9 s)
  and pre-paint (1.0 s) — the latter two scale with dirty layout objects at 18.8 µs each across the token (R² 0.90) and
  are the strongest hint of a PaintLayer / paint-property node per `overflow:hidden` row (`.head-row{overflow:hidden}`,
  `.metric{overflow:hidden}`), see §6 (R4).
- The `.head-isolation` wall (502 KB of `--attnp-*:initial` etc.) is one element and negligible; `.head-row` is 231 B.

## 5. Frame count derivation (Q5) — token 5, grouped by pass signature

| pass signature (elementCounts in order) | frames/token | median ms | style | layout | animate | UL self | comp. inputs | pre-paint | paint LC | hover | pending adds | transitions start/end | trigger → what the frame does |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| **A** `2934 126` | 11 (+1 variant `0 126 6919`) | 513 | 235 | 110 | 38 | 25 | 14 | 16 | 81 | 0 | 2,331 | 26/0 | `:has()` ack → `--loop-phase` → S1 (`--x`) → qkv fonts → layout → **snapshot re-run** → qkv readback → bank write (26 latch transitions) |
| **B** `0 6919 780` | 11 (+1 `0 780 3089`) | 309 | 99 | 86 | 61 | 25 | 8 | 13 | 39 | 18 | 830 | 0/0 | bank transitions take effect at paint-clean → next frame: score glyphs → scores readback → softmax → V rows → snapshot re-run → ctx readback → attn fonts |
| **C** `0 3089 784` | 11 (+1 `0 784 1553`) | 624 | 253 | 125 | 61 | 26 | 46 | 52 | 124 | 16 | 3,842 | 0/0 | attn readback (2nd snapshot change of B was deferred) → LN2 → fc fonts → layout → snapshot re-run → fc readback → proj fonts |
| **D** `0 1553 357` | 10 (+1 `0 368`) | 719 | 430 | 38 | 63 | 23 | 0 | 2 | 154 | 17 | 2,308 | 770/769 | proj readback → `--out` → loop-bank latch (769 transitions) → snapshot re-run → loop readback → `--loop-in` → `loop-pulse` starts on `#loop-ready-N` |
| **E** `1` | 12 (23 with G; one is the `2 6` token variant) | 103 | 17 | 0 | 60 | 22 | 0 | 1 | 19 | 18 | 0 | 0/1 | `loop-pulse` (1 ms) ends → `animationend` → SMIL `<set>` adds `.done` → 1-element restyle. **Pure handshake frame** |
| **F** `485` / `484` / `487` | 12 | 312 | 223–237 | 8 | 40 | 22 | 0 | 0 | 18 | 0 | 1 | 1/0 | `:has(.done)` → `--pass`+1 → `@container loopcontrol style(--pass:N)` restyle of controller/reader/input/signals → `loop-pulse` on `#loop-ack-N` |
| **G** `1` | 12 | 103 | 17 | 0 | 60 | 22 | 0 | 1 | 19 | 18 | 0 | 0/1 | ack pulse ends → SMIL `.done`. **Pure handshake frame** |
| head `0 2326 51247` | 1 | 3,543 | 814 | 1,446 | 65 | 28 | 935 | 975 | 222 | 18 | 3,078 | 771/771 | layer-11 export → b11 bridge readback → `--head-fvs` → head restyle + layout |
| token `2 6`, `487`, `1438 2917` | 1 + 1 + 1 | 117 / 332 / 525 | | | | | | | | | | | `token-N-ready/ack` handshake, `--saved-token` → feedback → embedding readback → S1 of layer 0 |

85 = 12 × (A B C D) + 12 × F + 24 × (E, G) + 1 head. Two snapshot-driven hops fit in one frame (Blink re-runs
style+layout **once** after `RunScrollSnapshotClientSteps` reports a change — every hop frame has exactly 2
`UpdateStyleAndLayout` iterations, never 3), so the 7 timeline hops + the S1 write need 4 frames; the bank latch
(a transition, effective only after the paint-clean `PendingAnimations::Update`) forces the A→B boundary. **Pure
handshake frames: E and G (24/token, 2.5 s, ≈100 % fixed cost); F (12/token, 3.7 s) is protocol, not data flow.**
The 61 `0`-element passes (17 ms each) are the hover-update's forced `UpdateStyleAndLayout` inside
`handleMouseMoveEvent` — they exist because the harness leaves the mouse on `INPUT#run` at (150,28).

## 6. Ranked reductions (predicted traced-window s/token; multiply by ≈0.83 for untraced)

| # | change | mechanism / evidence | predicted Δ | assumptions / risk |
|---|---|---|---:|---|
| **R1** | **Remove the two pulse-end frames per layer (E, G)** — e.g. one pulse instead of two (ready+ack) or replace the `loop-pulse`→`animationend`→SMIL `<set>`→`:has()` relay with a state change that the snapshot re-run can carry | 24 frames × 103 ms of pure timeline bookkeeping (§5) | **−2.5 s** (−3.5 s if F's 85 ms fixed cost also folds into D) | the SMIL relay exists to create a *new frame* for the `:has()` state flip; a fixture must show the pass counter can advance in the same frame as the loop readback without racing the latch |
| **R2** | **Cut live view-timelines during the layer loop** — every timeline costs ≈11 µs/frame (F3a: −3,842 timelines → −46 ms/frame). Candidates that are not needed in the loop: 769 embedding + 769 b11-bridge + 32 feedback carriers (`view-timeline-name:none` unless the head/token phase; or check whether `display:none` already detaches them), and chaining the 97 score carriers | animate 4.7 s + UL self 2.0 s + paint floor 1.6 s + style fixed 1.1 s ≈ 9.4 s/token ∝ 10.9 k timelines (§1) | **−1.4 s** for 1,570 token-level timelines; **−0.1 s** per 100 timelines chained | timelines inside `display:none`/locked subtrees may already be cheap — measure with a 2-page fixture (10 k carriers, toggled) before building |
| **R3** | **Harness: move the mouse off the page** (or `Input.dispatchMouseEvent` mouseMoved to (−1,−1) after clicking Run) | 61 hover updates × 17.6 ms (`handleMouseMoveEvent` incl. the forced 0-element style pass) = 1.07 s/token, 3 % | **−1.0 s** | zero risk; also applies to users only if their cursor is off the page — for the demo, `pointer-events:none` does *not* skip the hit-test walk, so keep as a harness fix |
| **R4** | **`overflow:clip` instead of `overflow:hidden` on `.head-row` (50,257) and `.metric` (8,551)** | compositing inputs + pre-paint = 3.7 s/token at 18.8 µs per dirty layout object (head frame 1.9 s, hop frames C 98 ms/layer); `overflow:hidden` makes each box a scroll container (PaintLayer + scrollable area) [inference — Blink internals, not in the trace] | **−1.5 to −2.5 s** | verify in a fixture that `calc-size(max-content)` widths and the view-timeline subject rects are unchanged (`overflow:clip` is not a scroll container); the `.scroller` itself must keep `overflow-x:scroll` |
| **R5** | **Explain and fix the loop-handshake passes (357 + 485 elements: 431 ms/layer, 5.2 s/token, model predicts 100 ms)** — probe (a) restyle of `.loop-reader` alone (1,538 anims scoped on `html`), (b) restyle of `svg.loop-signals` (384 `<g>` + 192 `<set>`) alone, (c) `.loop-input` 60 KB `--loop-in` block. Likely fixes: split `.loop-reader` per bank parity (769 anims each, scoped on a nearer ancestor), replace the 480 SMIL elements by 2 (one `<set>` per direction with per-pass `@container` rules) | §2 model residual ≈ 330 ms/layer | **−2 to −4 s** | needs the probe first; the 485-pass is not a data-flow restyle at all (F is protocol) so R1's redesign may subsume it |
| R6 | Loop-bank latch transitions (769 start + 769 end per layer: 218 µs style + 107 µs paint each ≈ 0.25 s/layer) | §3 | −3.0 s if a transition-free latch existed | F4 §2.1: not packable without a numerics change; listed for scale only |
| R7 | Hoist per-axis rounding (round-2 target 1) | no `round()` in the stage lists; list evaluation ≈ 0.2 s/token | **≈ 0** | drop from the plan |

Sum of the low-risk items R1 + R3 + R4 ≈ −5 to −6 s traced ≈ −4 to −5 s untraced (30.3 → ≈26 s/token); R2 + R5 are
worth another −3 to −5 s if the fixtures confirm the mechanisms.

## 7. Method notes / caveats

- Single streaming pass per trace (`R2A/frame_anatomy.py`, 60–70 s, ≈2.3 M main-thread X events kept for one token; no
  temp files). Self times use P2's stack method on the window's events; frame attribution by timestamp containment in
  `ProxyMain::BeginMainFrame`. "pending adds" = `LocalFrameView::ScheduleAnimation` (X + instant) with
  `function_name == "Add"` (pending_animations.cc); transition starts/ends = devtools `Animation` async events `b/running` and `e`.
- The light trace has no invalidation-tracking or per-function style/animation events; the attribution of
  `RunPaintLifecyclePhase` self to `PendingAnimations::Update`, of `UpdateLifecycle` self to snapshot validation, and the
  PaintLayer-per-overflow hypothesis are inferences from Blink's lifecycle structure that fit the regressions; they are
  marked as such and each has a fixture proposed.
- Population matching used gate-aware subtree sizes; 126/780/784/2326/3089/6919 match exactly, 1553 within 1, 2934 within
  ≈35 (body-level `epoch-reader`/`pass-reader` tags), 357/485 are partial `svg.loop-signals` counts (485 = 5 + 384 `<g>` +
  96 `<set>` exactly).
- The `combined2` trace was not analysed (F3a isolates the chain effect against F5; combined2 = combined + chain shows the
  same +Layout signature in `bench/combined2.md`).
