# R3H — the output-head frame, dissected (round 3, analysis only, no Chrome)

Agent R3H, 2026-09-20. Inputs: `bench/runs/R2F/R2F-t1-trace.json.gz` (current bundle, 7 tokens),
`bench/runs/combined/combined-mouseoff-t1-trace.json.gz` (6 tokens), `audit/2026-09-18/P2-scratch/full-trace.json.gz`
(baseline, 3 tokens) — each streamed twice at most (`R3H/head_frame.py`, `R3H/head_frame2.py`; outputs `R3H/*-head*.json/.md`).
Emitter read from `R2H/tools/browser_gpt2_head.py` (`compile_head`, decoder `two-pass`), `R2H/tools/browser_gpt2_runtime.py:257-425,455-490`,
`R2H/tools/f4_packing.py:135-167`, `experiments/browser-gpt2/head-two-pass/{head.css,head-body.html,browser-results.json}`,
and the built `bundles/combined3/{runtime.css,index.html}`. Log: `R3H.log.md`. Traced ms below; untraced ≈ ×0.9
(R2F: traced token mean 25.2 s vs untraced median 23.6; combined: 36.3 vs 30.3 → 0.83–0.94).

## 0. Headline

1. **One head evaluation = exactly one frame per token, 3.12–3.46 s traced (median 3.19 s, R2F), ≈ 2.9 s untraced = 12 % of the
   23.6 s token.** It is the frame whose second style pass is the 50,892-element restyle; it also carries the layer-11 export
   (2,326-element pass + 769 `--saved-1-*` latch transitions, ≈ 0.45 s) because the snapshot re-run puts both in one lifecycle.
2. **Anatomy (median, R2F):** style 420 ms (50,892 elements, 7.9 µs each; all 50,257 `.head-row` + 256 `.head-fine-row` change style,
   zero unchanged, zero MPC sharing) · layout 1,320 ms = **text shaping 840 ms (50,520 `ShapeTextIncludingFirstLine` calls, one per row,
   16 µs = 6 glyphs)** + layout self 457 ms (101,162 dirty of 140,920 layout objects = the whole head subtree) ·
   **compositing inputs 856 ms** · pre-paint 37 ms · paint 11 + cull 9 · paint-lifecycle self 200 ms (771 transitions, 3,078 pending adds) ·
   frame floor 95 ms (animate 55 + UL self 24 + hover 15) · nested GC 80–310 ms.
3. **Correction to R2A §4 / RESULTS-round2:** "compositing inputs 0.94 s + pre-paint 0.98 s" double-counts — the devtools `PrePaint`
   event *wraps* `RunCompositingInputsLifecyclePhase` (855 ms) and `RunPrePaintLifecyclePhase` (35 ms). Per-layout-object pre-paint
   bookkeeping is 0.35 µs/object and negligible; the 0.85 s is one phase, `PaintLayer::UpdateDescendantDependentFlags`.
4. **Yes, 50,257 separate line boxes:** each `<i class=head-row>` is a `display:block` grid item → LayoutBlockFlow + LayoutText + one
   inline formatting context → one shaping call and one text fragment item per row (50,257 + 256 fine + 7 = 50,520 calls, every token).
5. **The 856 ms "compositing inputs" is, with high probability, text ink-overflow recalculation = per-glyph bounds lookups on the fresh
   font instance (6 glyphs × 50,257 rows ≈ 2.8 µs/glyph)** [inference, §3.2]: it is unchanged by `overflow:hidden→clip` (R2D; combined
   855 vs R2F 856 vs combined3-style R2D A/B 922/935), unchanged by locking, and in Codex's standalone head trace it fell 31 % when rows
   went from 5 to 3 glyphs with the same 50,521 text runs (#178). Shaping + bounds = 1.7 s = 53 % of the frame are *per-glyph font work*.
6. **Cost split of the 3.19 s:** per-glyph font work 1.70 s (53 %) · per-element/object bookkeeping (style 420 + layout self 457 + pre-paint
   37) 0.91 s (29 %) · non-head passengers (layer-11 export 240 + paint-LC latch cost 200 + frame floor 95) 0.53 s (17 %) · GC ≈ 0.16 s.
7. **The production head is already the fastest exact head Codex measured:** standalone two-pass mutation mean 2,762 ms / median 2,767 /
   min 2,447 (n = 37, 37/37 exact, cold 45.0 s) vs the best certified cascade #178 at 2,741 mean / 3,810 p90 (30/30) — equal mean,
   no certificate, no serial tail. Option (b) cannot win the mean and loses the tail (§4).
8. **Cheapest certified win: #176's block-flow group maximum** (in-flow zero-height rows instead of a 1-column grid with all rows in cell
   1/1): measured −13 % layout / −30 % style / −14 % wall on a 50,257-row head, 30/30 exact. Predicted here **−0.30 ± 0.1 s untraced**
   (head frame 2.9 → 2.6 s). Prototype first. Everything else in the head is ≤ −0.4 s and needs a font rebuild or a Blink probe.

## 1. Head-frame anatomy per token (Q1)

`R3H/R2F-head.md` (current bundle), `R3H/combined-mouseoff-head.md`, `R3H/P2-full-head.md`. The head frame is found as the
`ProxyMain::BeginMainFrame` containing the `UpdateLayoutTree` with elementCount ≥ 20 k; there is exactly one per token in every trace.

| trace | token | frame ms | passes (elementCount:ms) | layouts (dirty/total:ms) | shaping calls / ms | comp. inputs | pre-paint | paint-LC | GC nested |
|---|---:|---:|---|---|---|---:|---:|---:|---:|
| R2F | 1 | 3,119 | 0:13 · 2326:212 · **50892:378** | 2374/39013:28 · **101157/140147:1334** | 50,519 / 830 | 856 | 894 (incl. CI) | 194 | 150 |
| R2F | 2 | 3,145 | 0:13 · 2326:204 · 50892:419 | 2374/39013:30 · 101162/140920:1312 | 50,520 / 828 | 854 | 890 | 210 | 161 |
| R2F | 3 | 3,147 | 0:14 · 2326:208 · 50892:445 | …:30 · 101162/140920:1272 | 50,519 / 821 | 854 | 891 | 211 | 108 |
| R2F | 4 | 3,279 | 0:15 · 2326:210 · 50892:420 | …:31 · 101162/140920:1429 | 50,520 / 840 | 849 | 886 | 214 | 263 |
| R2F | 5 | 3,273 | 0:16 · 2326:205 · 50892:527 | …:29 · 101162/140920:1309 | 50,520 / 887 | 861 | 897 | 212 | 234 |
| R2F | 6 | 3,455 | 0:16 · 2326:206 · 50892:619 | …:30 · 101162/140920:1320 | 50,519 / 908 | 859 | 897 | 293 | 307 |
| R2F | 7 | 3,186 | 0:16 · 2326:206 · 50892:382 | …:31 · 101162/140920:1355 | 50,519 / 930 | 866 | 906 | 214 | 78 |
| combined (mouse off) | 2–7 median | 3,486 | 0:15 · 2326:209 · **51247:619** | 2373/39396:30 · 101164/141303:1395 | 50,520 / 928 | 855 | 895 | 215 | 99 |
| P2 baseline | 1–3 median | 4,341 (+ a 2nd whole-DOM pass 63,946 el. = 0.9–2.9 s at token-ack, gone since F5) | 0:16 · 2326:248 · **63933:1413** | 2373/43937:9 · 101164/145844:1453 | 50,520 / 940 | 909 | 948 | 201 | 602 |

Sequence inside the frame (R2F token 2, `R3H/R2F-head2.md`): animate 49 ms (hover hit-test 13.7 + `serviceScriptedAnimations` 35) →
`UpdateLifecycle` self 22 → **iteration 1** `UpdateStyleAndLayout`: style 13 (0 el.) + style 204 (2,326 el. = `.shared-fc-receipt` subtree
with all gates open: proj readback → `#reused-result` → layer-11 loop-bank latch, 769 transitions start, `--head-fvs` + `--head-input-epoch`
transitions) + layout 30 ms (2,374 dirty of **39,013** — the head is locked, its 101 k layout objects do not exist for this layout) →
snapshot re-run → **iteration 2**: style 419 ms (50,892 el.) + layout 1,312 ms (101,162 dirty of **140,920**: the head subtree is
≈ 101.9 k objects = 50,257 × (LayoutBlockFlow + LayoutText) + 197 sections + 256 × 2 fine rows + ≈ 900 reducer boxes; 99.3 % dirty) →
`PrePaint` 890 = `RunCompositingInputsLifecyclePhase` **855** + `RunPrePaintLifecyclePhase` 35 → paint lifecycle 210 (paint 11, cull rect 9,
self 199 = `PendingAnimations::Update` for 771 transitions + 3,078 `pending_animations.cc:Add`) → commit 0.1 ms. Animation events in the
frame: 769 `--saved-1-*` starts on `.loop-bank-1`, `native-handshake` start on `g#token-N-ready` — i.e. **coarse pass, fine pass,
winner decode and the token-ready pulse all resolve inside this single frame** (anchor-size / container-query interleaving happens inside the
one `Layout` event; no third style pass).

Style counters of the 50,892 pass (`Document::updateStyle` args): `elementsStyled 50,892 · stylesChanged 50,893 · stylesUnchanged 0 ·
rulesMatched 152,888 (3/element) · rulesFastRejected 50,682 · matchedPropertyCacheAdded 48,884 · matchedPropertyCacheHit 1,378 ·
independentInheritedStylesPropagated 1 · customPropertiesApplied 0`. Every row gets a fresh ComputedStyle and a fresh MPC entry (its inline
`style="--base:…;--tie:…"` makes each row's declaration set unique), 7.9 µs each; the 48.9 k MPC insertions per token are also the likely
source of the frame's nested GC (`V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED` 52–122 ms + 2–3 k incremental-marking steps).

Shaping: 50,520 calls, median 15–16 µs, p90 18–24 µs, max 7–8 ms (the first call per new font instance); all but 4–5 sit in the head
layout. Per token the whole page shapes ≈ 202 k runs (R2F summary: 1,413,662 / 7 tokens), so the head is 25 % of shaping calls but 53 % of
the shaping time (its runs are 6 glyphs of 256-axis HVAR fonts; core carriers are 1–2 glyphs).

## 2. What one head evaluation does (Q2) — `compile_head(decoder="two-pass")`

- **Fonts.** Six `@font-face`s `ProdQ16{H,R}{0,1,2}` = 3 shards × 256 axes (`X000…X2FF` = the 768 final-LN outputs) × 2 planes
  (`score-high-k.woff2` 9.3 MB with `size-adjust:25600%`, `score-residual-k.woff2` 16 MB): the q16 row weight is radix-256 split into a
  high glyph (×256 via size-adjust) and a residual glyph; each row's 6 code points `U+2xxxx…U+7xxxx + token` fall in disjoint cmaps so the
  6-family `font` list shapes 6 fallback runs per row. Glyph outlines are a 1-unit square (WOFF2 rejects all-contourless glyf), `gvar` empty;
  all arithmetic is HVAR advance deltas (`build_gpt2_global_q16_layernorm_integer_full.py:120-165`). Font size 62.5 px; axes are integers
  `round(nearest, h_i / 266.248 × 16384, 1)` (E2 #94's integer-axis transport).
- **Input.** F4: `.head-input-bank` computes 768 `--hq-i` (inherits:false) and one `*` list `--head-fvs:"X000" var(--hq-0),…`
  (inherits:true), latched by an 86,400 s transition released while `@container b11-bridge style(--bridge-ready:1)`; `.head-isolation`
  resets every other registered property (502 KB, one element) so nothing but `--head-fvs`/`--head-input-epoch`/`--hq-*` crosses into the
  head. `.full-head{font-variation-settings:var(--head-fvs)}` — the inherited font change is what restyles the 50,257 rows.
- **Coarse pass — 197 groups × 256 rows, exact q16 score per row.** `section.head-group{position:fixed;display:grid;grid-template-columns:
  max-content;grid-template-rows:1px;width:max-content;height:calc(var(--head-input-epoch)*1px)}` (anchor `--head-group-g`); every
  `i.head-row{grid-area:1/1;display:block;justify-self:start;height:1px;white-space:pre;overflow:clip;width:calc-size(max-content,
  round(nearest,(size − var(--base)·1px)·120.777609693 + 211968px, 4px))}` — the row's max-content (6 advances = the dot product plus a
  per-row analytic base) minus its inline `--base`, scaled, offset by the LayerNorm-bound floor 211,968 px, rounded to 4 px. The grid's single
  max-content column = **max over the 256 row widths** (grid track sizing) → group score `S_g` (a multiple of 4 px). The two-pass override
  drops the `+ var(--tie)/64·1px` tie term of the direct decoder, so the inline `--tie` is dead in this bundle.
- **Group argmax (all `position:fixed` anchor boxes, resolved in layout).** `.head-score-g{width:round(down,anchor-size(--head-group-g
  width),4px)}` (197) → `reduce_geometry` fan-in 16: 13 `.head-max-0-j{width:max(16 anchor-size())}` + `.head-max-1-0` = global max `M`
  → `.head-match-g{width:clamp(0px, S_g − M + 1px, 1px) × (197−g)×4 + mod(group width,4px)}` (197; 1 px only for the winning group,
  encoding g) → 13 + 1 `.head-choice` max nodes → `.head-coarse-reader{container-type:size; width:anchor-size(--head-choice-1-0 width);
  height:M×16 + choice height}` → `.head-group-state{--head-group-index:197 − round(100cqi/4px); --head-max-score:round(down,100cqb/16px);
  --head-pipeline-epoch:mod(round(100cqb/1px),16)}`.
- **Fine pass — 256 rows.** `.head-fine` (grid, same font list, `font-variation-settings:var(--head-fvs)`, `height:--head-pipeline-epoch
  px`, anchor `--head-local`) holds 256 `i.head-fine-row` whose `::before{content:var(--fine-glyphs)}` and `--fine-base` are chosen by a
  197-way `if(style(--head-group-index:g): …)` per `:nth-child(k)` rule (256 rules, 3.89 MB); width
  `calc-size(max-content, clamp(0px, round(score) − --head-max-score·1px + 1px, 1px) × --rank)` with `--rank = 256 − k` → only the row
  whose score equals the group max has non-zero width = its rank → `.head-final-reader` (container) → `.head-result{--winner:
  --head-group-index×256 + 256 − round(100cqi/1px); --head-output-epoch:round(100cqb/1px)}`. Ties: the highest rank (lowest local index) wins.
- **Decode / hand-off.** `i.detached-head-source{position:fixed; anchor-name:--detached-head-result; width:--head-output-epoch px;
  height:max(0,--winner) px}` → outside the head `.detached-head-reader{container-type:size; width/height:anchor-size(…)}` →
  `.detached-head-state{--head-output-epoch, --winner}` → `token-slot-N` latches `--saved-token-N` (transition), SMIL `token-N-ready →
  captured → ack → advanced` (3 frames ≈ 0.29 s, `[1,6]` 97 · `[39]` 106 · `[1]` 85 ms) → `--epoch`+1 → `--bridge-ready:0` re-locks the head
  (R2D). Text: `@counter-style gpt2-vocabulary{system:fixed -1; symbols:"" <50,257 decoded strings>}` and
  `.visible-output::after{counter-reset:token1 var(--display-token-1) …; content:counter(token1,gpt2-vocabulary) …}` with
  `body:has(#token-N-captured.done) .visible-output{--display-token-N:var(--feedback-N)}`.
- **Standalone cost of exactly this head** (`head-two-pass/browser-results.json`, Chrome 153, 37 mutations): mean 2,762 ms, median 2,767,
  min 2,447, max 3,623, cold 45.0 s, 37/37 exact. The demo's frame adds ≈ 0.45 s of layer-11 export/latch and floor → 3.1–3.5 s traced.

## 3. Cost model per head evaluation (Q3)

### 3.1 Fitted unit costs (R2F medians; combined and P2 agree within 5 % on every head-proper phase)

| phase | ms | unit | per unit | scales with |
|---|---:|---|---:|---|
| style, 50,892 elements | 420 (378–619) | element | 7.9 µs | elements whose font changed (all rows); no MPC/independent-inherit sharing because of the inline `--base`/`--tie` |
| text shaping, 50,520 runs | 840 (821–930) | row | 16.4 µs = 2.7 µs/glyph | glyphs × axes (6 runs, 256 HVAR regions each) |
| layout self (`performLayout` − shaping) | 457 (430–518) | layout object | 4.5 µs (9.1 µs/row) | grid item + block + line box per row; #176 shows −13 % of Layout when rows are in-flow blocks |
| compositing inputs (`UpdateDescendantDependentFlags`) | 856 (849–866) | row | 17 µs = 2.8 µs/glyph | glyph count (§3.2), not overflow type, not PaintLayer count |
| pre-paint proper | 37 | layout object | 0.35 µs | dirty objects |
| paint + cull rect | 20 | — | — | ≈ 12 cc layers |
| paint-lifecycle self | 200 (194–293) | transition / pending add | 107 µs / 27 µs | 771 latch transitions + 3,078 re-queued animations (layer-11 export, not head) |
| layer-11 export pass + its layout | 236 | — | — | passenger in this frame (would cost a frame floor if split off) |
| frame floor (animate, UL self, hover) | 95 | live timelines | 11 µs/timeline (R2A) | not head |
| GC nested | 160 (78–307) | — | — | allocation churn (50 k ComputedStyle + 49 k MPC entries per token) |
| **frame** | **3,186** | | | |

Untraced scaling ×0.9: head frame ≈ 2.9 s/token; the head-proper part (style + layout + CI + pre-paint) 2.57 s traced ≈ 2.3 s untraced.

### 3.2 Shaping vs bookkeeping, and what "compositing inputs" is

- **Per-glyph font work 1.70 s (53 %)**: shaping 0.84 + glyph-bounds 0.86. **Per-element/object bookkeeping 0.91 s (29 %)**: style 0.42 +
  layout self 0.46 + pre-paint 0.04. **Not head 0.53 s (17 %)**: export 0.24 + latch paint-LC 0.20 + floor 0.09. GC 0.16.
- Why the 856 ms is glyph bounds, not layout-object bookkeeping [inference from Blink structure + three measurements]:
  (i) `RunCompositingInputsLifecyclePhase` runs only `PaintLayer::UpdateDescendantDependentFlags()`, which also performs the deferred
  `RecalcVisualOverflow` → `FragmentItem::RecalcInkOverflow` → `Font::TextInkBounds` → `SimpleFontData::BoundsForGlyph` for every glyph of
  every dirty text item; the bounds cache lives on the `SimpleFontData`, which is new every token because `font-variation-settings`
  changed → 50,257 × 6 cold Skia/CoreText bounds lookups ≈ 2.8 µs each. (ii) R2D changed `overflow:hidden→clip` (no PaintLayer per row)
  and locked the head: CI 922/935 → 855 ± 5 in every bundle since — not PaintLayers, not overflow. (iii) #178's standalone trace: same
  50,521 text runs, 5 → 3 glyphs per row, compositing inputs 698 → 480 ms (−31 %) and pre-paint 735 → 516 (their "pre-paint" is the same
  wrapping event) while layout fell only 14 % — "glyph multiplicity remains observable even when text run count is fixed". (iv) 8.5 µs per
  dirty layout object would be absurd for a flag walk; 2.8 µs per glyph is the normal CoreText metrics cost. The 0.35 µs/object
  `RunPrePaintLifecyclePhase` shows what real per-object tree bookkeeping costs here.
- Consequence: **≈ 1.7 s of the 3.2 s frame is proportional to glyphs per row (6) and cannot be moved by DOM/containment/locking**; only
  fewer glyphs (a numerics/transport change) or a warm bounds cache (impossible while the font instance changes each token) touches it.
  `visibility:hidden` on rows does not skip ink overflow (#176: +6 %); `contain:paint`/`overflow:clip` do not either (R2D, MB9).

## 4. Ranked options (Q4) — exact winner preserved, no model change; Δ untraced s/token on the 23.6 s R2F base

| # | option | mechanism / evidence | predicted Δ | exactness risk | cold-load risk | verdict |
|---|---|---|---:|---|---|---|
| **1** | **Block-flow group max (#176 verbatim)**: `.head-group{display:block;width:max-content;…}`, `.head-row{display:block;height:0;width:calc-size(…)}` (in-flow zero-height children; a block's max-content = max child width); keep `.head-fine` as grid (all-block-flow regressed the fine stage 4.6 %) | Codex trace on the same 50,257-row topology: layout 1,620 → 1,405 (−13 %), style 620 → 433 (−30 %), CI unchanged, wall −14 %; broad 30/30 exact; here −0.13 × 1,320 − 0.30 × 420 ≈ −300 ms traced | **−0.30 ± 0.10** | none measured (score arithmetic, 4-px rounding and reducers unchanged; tie term unused); verify `anchor-size(--head-group-g width)` of a block equals the grid's max-content column (#176 did) and that `height:calc(--head-input-epoch·1px)` still stamps the epoch | #176: cold 62.5 → 50.4 s (better) | **prototype first**: ~10 lines in `browser_gpt2_head.py`, rebuild `head-two-pass`, verify 8/8 ids |
| 2 | **Declaration-identical rows**: drop the dead inline `--tie`; fold `--base` into the fonts (per-row constant added to the residual/high default advance, `B − base_r ≥ 0`, so `max_r` is preserved; the affine `(size − B)·F + floor` moves to `.head-score-g`) → every `.head-row` has the same declarations → MPC hits instead of 48.9 k inserts, fewer ComputedStyle allocations, less GC | style 7.9 µs → ≈ 3 µs/element (MPC-hit path) ≈ −250 ms; GC −50…−100 ms | **−0.25 ± 0.15** | medium: base must be representable on the hmtx/HVAR lattice (upem, 1/64 px snapping; E2 §2.8 "712/3072 buckets off by one" is exactly this class of error); `round(…,4px)` then applies to a 197-way max instead of per row — identical result only if the per-row rounding never changed a winner (it is applied to `S_g` again by `.head-score`, so equivalent) | font rebuild (6 × 9–16 MB WOFF2), no size change | second; do after #1, gated on an offline exactness screen of the 1,024 states |
| 3 | **Lean token handshake** (R2F's technique on `token-N-ready/captured/ack/advanced`): fold the 3 post-head frames (`[1,6]` 97 · `[39]` 106 · `[1]` 85 ms) into the `--epoch` advance | 2–3 pure-handshake frames × ≈ 95 ms floor | **−0.15…−0.25** | protocol only; the slot latch (`--saved-token-N` retained transition) must still see the winner before the head re-locks | none | third; same class as R2F, independent of the head |
| 4 | **Probe H1 (glyph-bounds) — no CSS knob known**: fixture 50 k rows × {3, 6} glyphs × {variable, static font} × {`visibility:hidden`, `color:transparent`}; read `Blink.CompositingInputs.UpdateTime` on the 2nd mutation | if a static font's 2nd mutation shows CI ≈ 0 and variable shows 850, H1 is confirmed and the only lever is glyphs/row | 0 (knowledge) / up to −0.75 if a knob appears | — | — | run the fixture (15 min of Chrome) before spending on any DOM restructuring aimed at CI |
| 5 | (b) Codex's certified coarse-to-fine cascades (int10 3-glyph scan + Cauchy certificate + exact 12-glyph stages) | warm: #136 6-stage 4.806 s / cold 49.1 s; 16 stages 5.63 s / 86.9 s; 61 stages 5.9 s / 199–228 s; #96 groupwise Cauchy 1,979 ms mean (4 samples) but production-range 8.5–14.2 s on 11–23-stage states; #178 best chain 2,741 mean / 3,810 p90 / 56.7 s cold; certification budget #83: int10 median 3 / p95 17 / max 55 exact groups. Here a 3-glyph coarse would save ≤ ½ × 1.70 s = 0.85 s traced but adds ≥ 1 snapshot frame (≥ 0.25 s) + router/certificate passes + 12-glyph stages, and every extra serial stage in the demo is a ≥ 250 ms hop | median ≈ −0.2…+0.3; **p95 +2…+8 s** | certificate contract is "realized F2DOT14 coordinates", not float-exact; bucket-drift allowances (24–27 buckets) | +5…+40 s cold, 51–79 MB more fonts | **reject** — the reasons (serial tail, eager shaping of every visited group, cold) are unchanged by F5/R2F; the exact q16 scan already equals #178's mean with zero tail |
| 6 | (a) `display:contents`/inline rows | an inline run of 256 rows in one formatting context *sums* widths (the argmax needs a max); `calc-size(max-content)` needs a box per row | not viable | — | — | subsumed by (d) |
| 7 | (d) one text node per group (256 `<br>` lines; per-row transform folded into the font as in #2) | #163: newline text sums lines in Chrome 153 (`<br>` needed → 50,060 LayoutBR objects), cold 65.7 vs 61.7 s, loses local identity (fine pass would still supply it); #168 min-content words: **mutation 1.18–1.33× slower** at every size, 197 groups > 180 s. Ink-overflow items and shaping glyphs are unchanged (one text item per line) | ≈ 0 to **+10 %** | tie/identity | worse cold | reject on Codex's warm data |
| 8 | (c) `content-visibility` / locking of fine groups not in play | the fine pass is already 256 rows in one frame; the coarse pass must touch all 197 groups; R2D already locks the whole head on the other 45 frames | **0** | — | — | nothing left to lock |
| 9 | split the layer-11 export out of the head frame | it would cost a frame floor (95 ms) to save nothing; the export's 769 latch transitions (200 ms paint-LC + 200 ms style) are F5 §112's "pack the slot latch" item, not a head item | 0 | — | — | note only |
| 10 | 3-glyph exact rows (radix change so q16 fits 3 advances) | would halve the 1.70 s of per-glyph work (−0.75 s untraced) | −0.75 | E2 §2.8/E3 §C: every 6-glyph→fewer-glyph transport so far broke bucket identity by one bucket (1/64 px advance snapping, 32,768 px advance cap) | rebuild | out of scope (transport change); listed for scale |

Sum of 1 + 2 + 3 ≈ **−0.7 ± 0.3 s/token** (23.6 → ≈ 22.9; head frame 2.9 → ≈ 2.3 s untraced). The remaining ≈ 2.0 s is the 301 k
per-glyph font operations plus the 50 k layout objects — inherent to "one exact q16 row per token as a 6-glyph text run".

## 5. Method notes / caveats

- Single streaming pass per trace with `R3H/head_frame.py` (all main-thread events within [latch − 9 s, latch + 0.5 s] of every token,
  60–75 s per trace); a second pass (`head_frame2.py`, ±5 s) added `Document::updateStyle` counters, `LocalFrameView::layout` endData
  and parent chains. Self times by the P2 stack method; frame attribution by timestamp containment in `ProxyMain::BeginMainFrame`.
- The light trace has no per-glyph, ink-overflow or PaintLayer events; §3.2 is an inference supported by R2D's null result, #178's
  glyph-count sensitivity and Blink's lifecycle structure, and is marked as such with a discriminating fixture (option 4).
- `compositing inputs` and `pre-paint` totals in R2A §1/§4 and RESULTS-round2 ("≈1.9 s compositing/pre-paint") must be read as one phase of
  ≈ 0.9 s; R2A's 18.8 µs/dirty-object regression is therefore ≈ 9 µs and glyph-driven.
- Font internals (upem, hmtx lattice) could not be read: the system python lacks `brotli` for WOFF2; the builder source
  (`build_gpt2_global_q16_layernorm_integer_full.py`) was used instead. Option 2's lattice check needs `pip install brotli` first.
- Nothing under repo `tools/`, `experiments/` or `bundles/` was modified; no Chrome was run.
