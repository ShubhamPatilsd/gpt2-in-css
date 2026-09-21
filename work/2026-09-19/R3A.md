# R3A — round-3 diagnostic trace of `bundles/R2F` (2026-09-20)

Agent R3A. One heavy-category traced 8-token session of the current best bundle (R2F, 23.6 s/token untraced), taken after B3's
paired pass under the Chromium mutex; analysed against B0's light trace of the same bundle (`bench/runs/R2F/R2F-t1`).
Files: `work/2026-09-19/R3A/` — `trace_heavy.mjs` (harness), `run_heavy.sh`, `driver.sh`, `anatomy.py` (frame/phase/pass parser,
extends R2A's `frame_anatomy.py`), `style_counters.py` (per-pass style counters + `SelectorStats`), `frame_regress.py` (per-frame fits),
`svc_check.py`, `inventory.py`; outputs `heavy-anatomy.{json,md}`, `heavy-style.{json,md}`, `heavy-frames.{json,md}`, `light-R2F-t1-anatomy.{json,md}`,
`svc_check.out`; trace `R3A/runs/R2F-heavy-trace.json.gz` (98 MB, gzip-streamed by Chrome, no raw JSON ever written) + `R2F-heavy.json`. Log: `R3A.log.md`.

## 0. Headline

1. **The heavy categories do not expose the sub-events the plan hoped for.** Over the light set, `disabled-by-default-blink.debug` adds only
   `SelectorStats` (per-selector matching time/attempts per pass) and `args.counters` on `Document::updateStyle` (elementsStyled, rulesMatched,
   matchedPropertyCache adds/hits, stylesAnimated, …); `blink.animations` adds nothing beyond the light run; `disabled-by-default-blink.debug.layout`
   adds one arg on `performLayout`. **No trace event exists for `PendingAnimations::Update`, ScrollTimeline/ViewTimeline snapshot validation,
   `CSSAnimations::CalculateTransitionUpdate`, `var()` resolution or container-query evaluation** (Chrome 153). Those parts remain self time of
   `RunPaintLifecyclePhase`, `UpdateLifecycle`, `serviceScriptedAnimations` and `Document::recalcStyle`; they are split below by per-frame / per-pass
   regression on the counts the trace does carry (which the new data confirms to ±5 %).
2. **Frame anatomy (light units, 46 frames/token): ≈117 ms fixed per frame ≈ 5.4 s/token traced ≈ 4.9 s untraced (21 %).** Per frame: animate step
   40 ms (26 ms `serviceScriptedAnimations` self + 11.6 ms = 10.0 k `serviceAnimations` calls), `UpdateLifecycle` self 22–30 ms (snapshot validation,
   untraced), paint-lifecycle floor 22 ms (`PendingAnimations::Update`, untraced; fit 22.1 ms + 28.2 µs × pending add + 96 µs × transition start,
   R² 0.89), a 0-element style pass 14.4 ms (**Blink's `RecomputeMouseHoverStateIfNeeded` at the start of every `BeginMainFrame` — it survived the
   mouseoff fix**), and 2 × 6.8 ms `UpdateLayoutTree`/`updateStyle` self + 5.9 ms of `serviceAnimations` inside the second pass. Every frame services
   the timelines **three times** (≈10.0 k in the animate step, ≈8.0 k in the hover 0-pass, ≈8.6 k in the second style pass = 26.6 k calls ≈ 31 ms at
   1.15 µs). **Per live view-timeline: 10.7 µs/frame all-in, of which 2.9 µs is traced `serviceAnimations`** — the 2 µs R2E's shallow fixture measured is
   exactly the traced part; the other ≈8 µs is untraced self time of the three sweeps and is what R2A's F3a comparison attributed to timelines.
3. **Style (10.4 s traced-light = 40 %) is animation-effect application, not rule matching.** `SelectorStats`: 1.19 M match attempts, 609 k rules
   matched, **250 ms/token (2.4 % of style)**, of which ≈200 ms are the `:has()` rules R2G found. Per-pass costs fit R2A's model to ±10 %:
   40 µs per timeline animation whose timeline changed (102.5 k/token ≈ 4.1 s), 218 µs per transition started (9,228/token ≈ 2.0 s), 22 µs per
   animation restyled unchanged (≈0.8 s), 5 µs per element (239 k/token ≈ 1.2 s), 12.7 ms fixed per pass (132/token ≈ 1.7 s), GC inside style ≈ 1.0 s.
   `matchedPropertyCacheHit` is ≈0 except the 6,919-element V-glyph pass (6,048 hits) and the head rows (1.1 k): every other element runs a full cascade.
4. **R2G's residual is gone in R2F.** The merged loop-readback/pass-advance/S1 pass (2,323 elements, 10/token) costs 64 ms recalc = 1,538 × 40 µs +
   2,323 × 5 µs + 8 ms `:has()`; there is no capture pass any more. The "whole-document per-pass residual" is the fixed 12.7 ms/pass (4.0 `UpdateLayoutTree`
   self + 2.8 `updateStyle` self + 5.9 servicing ≈8.6 k timelines) — it is timeline count, not handshake logic.
5. **Head frame 3.3–3.5 s traced-light (≈3.0 s untraced, 13 %)**: style 0.75–0.84 s (recalc 10.5 µs × 50,892 rows; `.head-row` matching 11 ms;
   GC sweep stall 0.16–0.21 s), layout 1.34 s (shaping 0.88–0.91 s = 50,257 rows × 17.6 µs; `performLayout` self 0.43 s = 4.3 µs per dirty object),
   compositing inputs 0.86 s (8.5 µs × 101,162 dirty objects), pre-paint 0.04 s, paint lifecycle 0.21–0.29 s (770 layer-11 latch transitions + 536
   pending adds in the same frame), animate 0.045 s.
6. **Trace inflation**: heavy tokens 4–7 = 33.1 s/token (+40 % vs untraced 23.6, +27 % vs light 26.1; in-run untraced tokens 1–2 were 26.6/23.8 with
   load ≈3–4). The inflation sits in style (10.4 → 14.7 s: the per-element counters + `SelectorStats`), shaping events (2.0 → 2.3 s) and GC
   (1.0 → 1.8–3.5 s of `V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED` stalls). Because a "lighter run without blink.debug" is exactly B0's light R2F-t1
   trace (same bundle, same protocol, parsed here with the same scripts), the shares are quoted from it and no second lock slot was used.

## 1. Frame anatomy (Q1) — per steady token; light R2F-t1 tokens 5–6 (26.1 s) vs heavy tokens 4–7 (33.1 s)

### 1a. Per-token phase self time (ms; each event attributed to its nearest lifecycle-phase ancestor, so phases sum to busy time)

| phase (container) | light tok 5 | light tok 6 | **light mean** | heavy mean (4–7) | heavy/light | what the trace shows inside it |
|---|---:|---:|---:|---:|---:|---|
| wall | 25,129 | 27,060 | **26,094** | 33,074 | 1.27 | 46 frames, 132 style passes, 87 layouts per token in both |
| style (`UpdateLayoutTree`) | 10,106 | 10,613 | **10,359** | 14,700 | 1.42 | `Document::recalcStyle` self 7,490/7,862; `serviceAnimations` 773/815 (658 k calls); `UpdateLayoutTree` self 528/546; `updateStyle` self 384/360; GC 925/1,025 |
| layout | 5,315 | 5,850 | **5,583** | 7,251 | 1.30 | `performLayout` self 3,210–3,600; `ShapeTextIncludingFirstLine` 2,004 (181 k calls); GC 46–87 |
| paint lifecycle (`RunPaintLifecyclePhase`) | 4,852 | 5,590 | **5,221** | 5,204 | 1.00 | **self 4,825/5,556 (99.5 %)**; `CullRectUpdate` 14; `Paint` 5; `PaintArtifactCompositor::Update` 2 |
| animate (`WebFrameWidgetImpl::BeginMainFrame`) | 1,790 | 1,853 | **1,821** | 2,268 | 1.25 | `serviceScriptedAnimations` self 1,210/1,258; `serviceAnimations` 532/546 (457 k calls); `ScheduleAnimation` 45 |
| compositing inputs | 1,577 | 1,590 | **1,584** | 1,740 | 1.10 | `Blink.CompositingInputs.UpdateTime` self; fit −61 ms + 9.3 µs × dirty layout objects (R² 0.95) |
| `UpdateLifecycle` self ("UL-other") | 1,177 | 1,215 | **1,196** | 1,468 | 1.23 | self 990/1,020 + 108 k `ScheduleAnimation` X events 113 ms + `UpdateStyleAndLayout` self 68 |
| pre-paint | 178 | 179 | **178** | 212 | 1.19 | |
| hover (`handleMouseMoveEvent`) | 18 | 19 | **18** | 39 | | mouseoff works for the hit test — but see the 0-element pass in §1b |
| other (tasks, commit, a11y) | 32 | 48 | 40 | 85 | | |
| GC nested in the above | 1,017 | 1,081 | **1,049** | 1,797–3,493 | | `HEAP_ENSURE_SWEEPING_COMPLETED` 2/token 666–679 ms; incremental-marking steps 18.5 k × 15 µs = 271 ms |

### 1b. One frame — fixed cost that does not depend on the hop's compute (light medians; heavy in brackets)

| sub-step | ms/frame | per token (46) | per live timeline (10.9 k) | measured how / what it is |
|---|---:|---:|---:|---|
| animate: `PageAnimator::serviceScriptedAnimations` **self** | 26.3 [34.3] | 1.21 s | 2.4 µs | untraced: timeline iteration, `ValidateTimelines`, `UpdateAnimationTimingForAnimationFrame` [inference: Blink structure] |
| animate: `AnimationTimeline::serviceAnimations` X | 11.6 [13.4] | 0.53 s | 1.1 µs | 9,944 [10,562] calls/frame × 1.16 µs — the only directly traced per-timeline cost of the animate step |
| animate: `ScheduleAnimation` (ScheduleServiceOnNextFrame) | 1.0 | 0.05 s | | 930/frame |
| **hover-recompute 0-element pass** (`UpdateStyleAndLayout` at +0.0 ms of `BeginMainFrame`) | 14.4 [17.7] | 0.60 s [0.74] | 0.7 µs | `EventHandler::RecomputeMouseHoverStateIfNeeded` runs a style+layout update before `ServiceScriptedAnimations` in every frame once the frame has seen a mouse (the Run click); 8.0 k `serviceAnimations` calls inside (≈6 ms) + ≈8 ms pass fixed; the hit test itself is 0.15 ms with the pointer parked |
| `UpdateLifecycle` **self** | 21.5 [27.2] | 0.99 s [1.25] | 2.0 µs | untraced: `RunScrollSnapshotClientSteps` / `ValidateScrollSnapshotClients` over the ≈10.9 k `ScrollSnapshotClient`s [inference]; fit vs dirty objects is flat (R² of dirty alone 0.95 comes from the head frame) |
| second style pass: `serviceAnimations` X | 5.9 | 0.78 s | 0.8 µs | 8.3–9.0 k calls in the **second** `UpdateStyleAndLayout` of the frame (`UpdateAnimationTimingIfNeeded`); 0 in the first |
| 2 × (`UpdateLayoutTree` self + `updateStyle` self) | 2 × 6.8 | 0.90 s | | 4.0 + 2.8 ms per pass, independent of elementCount (0-element passes show the same) |
| paint lifecycle **floor** | 22 [22.1] | 1.0 s | 2.0 µs | intercept of `RunPaintLifecyclePhase self = 22.1 ms + 28.2 µs × pending adds + 95.9 µs × transition starts` (heavy, n = 184 frames, R² 0.886; light R2A: 18.7/26.7/107) = `PendingAnimations::Update` [inference] |
| **frame fixed total** | **≈117 [≈140]** | **5.4 s [6.4]** | **10.7 µs** | of which traced `serviceAnimations`: 31 ms = 2.9 µs/timeline; untraced self: ≈86 ms |

Per-frame proportional parts (not fixed): paint lifecycle 28.2 µs × pending add (114.9 k adds/token = 3.24 s) + 96 µs × transition start
(9,545/token = 0.92 s); compositing inputs + pre-paint 19.0 µs × dirty layout object (R² 0.95); layout 18.2 µs × dirty object (R² 0.83) on top of shaping.

### 1c. Frame types (light medians, ms; 46/token = 12 layers × 3.5 hop frames + head + embedding/S1 + 3 token-handshake frames)

| pass signature (elementCounts) | /token | dur | animate | UL self | paintLC | style | layout | comp+prepaint | pending adds | transitions | what it carries |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `0 126 6919` | 6 | 469 | 41 | 22 | 79 | 181 | 134 | 7 | 442 | 26 | qkv readback → KV write (26 latches) → score fonts; softmax → V rows |
| `0 6919 780` | 6 | 284 | 36 | 24 | 37 | 92 | 84 | 12 | 120 | 0 | V rows → ctx readback → attn fonts |
| `0 780 3089` | 6 | 374 | 38 | 23 | 53 | 162 | 73 | 25 | 236 | 0 | ctx → attn; attn readback → LN2 → fc fonts |
| `0 3089 784` | 6 | 594 | 39 | 29 | 119 | 235 | 120 | 49 | 712 | 0 | attn → fc; fc readback → proj list (3,072 anims) |
| `0 784 1553` | 6 | 727 | 44 | 29 | 221 | 321 | 93 | 18 | 882 | 769 | fc → proj; proj readback → loop-bank latch (769 transitions) |
| `0 1553 2323` | 5 | 674 | 41 | 30 | 199 | 295 | 75 | 16 | 389 | 769 | latch; loop readback + `--pass`+1 + S1 → qkv fonts |
| `0 2323 126` (+`0 2334 126`) | 6 | 548 | 40 | 28 | 135 | 217 | 113 | 16 | 542 | 26 | S1; qkv readback → KV write |
| `0 2326 50892` (head) | 1 | 3,364 | 42 | 34 | 252 | 794 | 1,344 | 897 | 536 | 770 | layer-11 export → head matmul (§3) |
| `863 2342` | 1 | 416 | 36 | 25 | 32 | 179 | 126 | 17 | 122 | 2 | token start: `--saved-token` → embedding → S1 of layer 0 |
| `1 6`, `39`, `1` | 3 | 101 / 103 / 85 | 34–37 | 18–21 | 17 | 14–25 | 0–8 | 1 | 0 | 0–1 | **token-level SMIL handshake — the only pure-handshake frames left (0.29 s/token)** |

## 2. Inside a style pass (Q2) — what the new counters and `SelectorStats` expose

Per-token counters (`Document::updateStyle` args, heavy, identical for tokens 4–7): elementsStyled 239,493; rulesMatched 608,770; rulesFastRejected 158,552;
rulesRejected 45,907; matchedPropertyCacheAdded 164,280; matchedPropertyCacheHit 73,872; stylesAnimated 802; stylesChanged 240,168; pseudoElementsStyled 0;
customPropertiesApplied 0 and matchedPropertyApply 0 (these two counters are dead in this Chrome — no signal). `SelectorStats` (sum of per-selector
elapsed, all 132 passes): **250.9 ms/token = 1.19 M match attempts (0.21 µs each), 694 k matches; 2.4 % of traced style, ≈1.9 % after inflation.**

| pass (elementCount) | /token | recalc ms light [heavy] | selector ms | attempts | rules matched | MPC add / hit | cost model (R2A coefficients) → predicted | dominant term |
|---|---:|---:|---:|---:|---:|---:|---|---|
| 1,553 proj readback → loop latch | 11–12 | 186–190 [210–216] | 0.58 | 5,778 | 3,132 | 1,548 / 0 | 769 × 218 + 768 × 40 + 1,553 × 5 = **207** | **transition starts (81 %)** |
| 126 qkv readback → KV write → scores | 12 | 100–113 [113–162] | 0.55 | 2,136 | 479 | 105 / 9 | 2,304 × 40 + 26 × 218 = **98** + 96 font instantiations | changed-timeline anims (2,304 on 5 consumers) |
| 3,089 attn → LN2 → fc fonts | 12 | 96–100 [131–159] | 0.63 | 10,484 | 6,207 | 3,079 / 0 | 768 × 40 + 3,072 × 22 + 3,089 × 5 = **114** | unchanged fc anims restyled (59 %) |
| 784 fc readback → proj list | 12 | 89–93 [113–136] | 0.37 | 3,558 | 1,596 | 774 / 0 | 3,072 × 30 = **92** | changed fc anims (3,072 on 6 consumers) |
| 2,323 loop readback + pass advance + S1 | 10 | 63–65 [85–97] | **8.27** | 8,238 | 4,691 | 2,313 / 0 | 1,538 × 40 + 2,323 × 5 + 8 (`:has()`) = **82** | changed loop anims; the `:where(body:has(#token-N-advanced.done)) .core-controller` rules cost 1.0–2.2 ms **each** |
| 6,919 softmax → V fonts → rows | 12 | 31–33 [44–50] | 1.53 | 20,996 | 20,000 | 869 / **6,048** | 6,919 × 4.6 | pure inheritance; only pass with MPC hits |
| 780 ctx → attn fonts | 12 | 20–22 [26–32] | 0.28 | 3,447 | 1,584 | 774 / 0 | 768 × 26 | changed anims |
| 50,892 head | 1 | 321–350 [543–769] | **21.2** | 204,919 | 152,890 | 49,147 / 1,115 | 50,892 × 6.5 | `.head-row` matching 11 ms; row restyle |
| 0 (hover recompute) | 42 | 0 [0] | 0.17 | 1,224 | 0 | 0 | pass fixed 14.4 | fixed cost only |
| 863 / 2,342 / 39 / 6 / 1 (token boundary) | 1 each | 80–92 | **10–20 each** | | | | | `body:has(#token-N-…)` rules 1–3.8 ms each |

Reading: rule matching is ≈2 % of style; **animation-effect application on the few consumer elements is ≈50 %** (4.1 s changed + 0.8 s unchanged),
**transitions ≈20 %** (2.0 s), per-element cascade ≈12 % (1.2 s; 164 k full cascades/token, MPC useless because every carrier has a distinct inline
`width`), per-pass fixed ≈16 % (1.7 s, mostly timeline servicing), GC ≈10 %. `var()` substitution / `calc()` list evaluation and container-query
evaluation have no event; their upper bound is the model residual (≤ 0.5 s/token, consistent with R2A's 0.2 s list estimate).

## 3. Head frame (Q3) — light tok 5 / tok 6 (3,273 / 3,455 ms; heavy 3,825–5,054 incl. GC stalls)

| step | ms | per unit | notes |
|---|---:|---|---|
| `2326` pass (layer-11 export, 769 latch transitions) | 205 / 206 | 769 × 218 µs | same frame as the head pass |
| `50892` pass: recalc | 520 / 550 | 10.5 µs/row | `.head-row` selector 11.2 ms (100 k attempts); 1,115 MPC hits only |
| `50892` pass: GC inside | 161 / 213 | | `HEAP_ENSURE_SWEEPING_COMPLETED` stall lands here in 3 of 6 traced tokens |
| layout: `ShapeTextIncludingFirstLine` | 884 / 905 | 17.6 µs × 50,257 rows | the matmul itself (inherent) |
| layout: `performLayout` self | 439 / 430 | 4.3 µs × 101,162 dirty objects | |
| compositing inputs | 861 / 859 | 8.5 µs × dirty object | `Blink.CompositingInputs.UpdateTime`; R2A's PaintLayer-per-`overflow:hidden` hypothesis; R2D's `overflow:clip` A/B moved it ≤ 0.1 s |
| pre-paint | 37 / 37 | | |
| paint lifecycle | 212 / 293 | 22 + 536 × 28 µs + 770 × 96 µs = 111 + ≈100–180 | the layer-11 latch paid twice (style 168 ms + paint 74 ms) |
| animate + UL self + hover pass | 45 + 34 + 16 | | as any frame |

## 4. The loop passes R2G could not explain (Q4)

In `combined`, frames F (485) and D's 357 pass cost 431 ms/layer against a 100 ms model. In R2F both are gone: the loop hop is the `2,323` pass
(64 ms recalc, model 82) inside frame `0 1553 2323`, and the pass advance happens in the same recalc. What is left of a "whole-document residual" is
the **fixed 12.7 ms per pass** — 4.0 ms `UpdateLayoutTree` self + 2.8 ms `Document::updateStyle` self + 5.9 ms average `serviceAnimations`
(8.3–9.0 k calls in every second pass of a frame, none in the first) — 132 passes ≈ 1.7 s/token, plus `SelectorStats`' 8 ms of `:has()` per controller
restyle. Nothing in the trace supports a container-propagation or KV-transition term beyond these (the 12 nested `.fvs-bank-L` in-delay transitions
do not appear in `stylesAnimated`, which is 802/token ≈ 67/layer = the 26 KV latches + 2 × ≈20 receipt/gate elements).

## 5. Ranked round-3 levers (predicted untraced s/token from 23.6; traced-light × 0.90)

| # | lever | measured sub-event it removes | predicted Δ | risk / evidence |
|---|---|---|---:|---|
| **1** | **Halve the carriers and animations by packing 2 values per carrier/animation** (7,680 stage carriers → 3,840; F4 already packs the KV banks 2-per-number) | per live timeline 10.7 µs/frame × 46 frames (§1b) → 3,840 × 0.49 ms = 1.9 s; changed-timeline application 40 µs × ≈51 k/token = 2.0 s; pending adds 28 µs × ≈57 k = 1.6 s; layout of half the carriers ≈ 0.5 s | **−3.5 to −5 s** | precision of 2-per-number packing on the 24-bit width path (F4 §2 did it for the banks); decode cost per consumer doubles (small) |
| **2** | **Fuse fc → proj (avar2 `B·GELU(A·x)`, phase-2 candidate)**: removes one hop per layer | `784` pass 107 ms + 3,072 fc anims re-applied in the `3089` pass 68 ms + 0.5 frame fixed 58 ms + 3,842 pending adds 108 ms + fc-carrier layout ≈ 60 ms ≈ 0.4 s/layer | **−3 to −4 s** | numerics (avar2 GELU approximation) — experiments/avar2-gelu-linear-hvar-full-mlp exist |
| **3** | **Loop-bank latch with fewer transitions** (769 starts + 769 cancels per layer; the `1553` pass + paint) | 218 µs style + 96 µs paint per transition start = 9,228 × 314 µs = 2.9 s traced | **−1.3 s** with 2-per-number packing of `--saved-*` (385 transitions/layer); −2.6 s if a list-valued (`<number>+`) latch could be read back per component — CSS has no list indexing, so only via the carriers' own decode | F4 §2.1: not packable without a numerics change; a `<number>+` `@property` transitions component-wise in Blink (equal-length lists) — a fixture question |
| **4** | **Drop the hover-recompute pass**: never let the pointer enter the frame (activate `#run` by keyboard: focus + Space via CDP `Input.dispatchKeyEvent`) | 42–48 × 14.4 ms `UpdateStyleAndLayout` passes at the start of every frame (`RecomputeMouseHoverStateIfNeeded`) = 0.60–0.68 s traced | **−0.55 s** | harness-only, zero risk to the page; for users it applies only when the pointer is off the page |
| **5** | **GC sweeping stalls** (`--heap-growing-percent=10`, B0's fix-1 arms) | `V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED` 2/token, 0.67 s light (1.0–2.2 s heavy); incremental marking 0.27 s | **−0.3 to −0.6 s** | B0 owns the measurement; RSS trade-off |
| **6** | **Token-level handshake via the R2F trick** (`1`, `1 6`, `39` frames + `863` pass) | 3 pure-handshake frames 0.29 s + `body:has(#token-N-…)` matching 10–20 ms × 5 passes | **−0.3 s** | same mechanism as R2F (marker readback instead of SMIL pulse) |
| **7** | **Detach the token-level carriers during the layer loop** (768 embedding + 769 b11-bridge + 7 pass-readers) | 1,544 timelines × 46 frames × 2.9–10.7 µs = 0.2–0.76 s | **−0.2 to −0.7 s** | R2E: values are lost on detach — acceptable for carriers re-derived every token; re-attach ≈5 µs/carrier |
| **8** | `:has()` fixed-depth rewrite (R2G `emitter.diff`) | `SelectorStats`: ≈200 ms/token in the `:where(body:has(#token-N-advanced.done)) .core-controller` and `body:has(#token-N-captured.done)` rules | **−0.2 s** | prototyped, static-checked |
| 9 | Head frame: `overflow:clip` / PaintLayer count | compositing inputs 0.86 s = 8.5 µs × 101 k dirty objects | −0.1 to −0.3 s | R2D's A/B showed only ≈ −6 % of it; the 0.9 s shaping + 0.44 s layout are the matmul |

Sum of 1 + 3 + 4 + 5 + 6 + 8 (no model change) ≈ −6 to −8 s → ≈ 16–17 s/token; with 2 (avar2 fusion) ≈ 13 s/token. The 46 hop frames cannot drop
below 12 × 3.5 + 5 without fewer hops (lever 2) or a snapshot-free gather.

## 6. Method / caveats

- Run: `R3A/driver.sh` waited for `B3/DONE` (169 min), took `CHROME.lock` at 21:16:57 (mkdir; touched every 30 s; released 21:24:03 when Chrome exited),
  AC + `caffeinate -dims`, pointer parked at (−50,−50), passive completion (`DOM.querySelector` at 1 Hz), no geometry reads; categories
  `blink,blink.style,blink.animations,blink.user_timing,disabled-by-default-blink.debug,disabled-by-default-blink.debug.layout,devtools.timeline,disabled-by-default-devtools.timeline,cc,v8.gc`,
  ring 1.5 GB (`recordContinuously`), tracing started at the token-2 capture so the ring holds the steady tokens (it ended 70.8 % full, no data loss);
  load1 3–4 with `cua-driver` at ≈45 % CPU (B0's original quiet gate would have called it CONTENDED). Tokens 26.6 23.8 | 28.6 31.2 33.6 33.2 34.8 35.2 s; ids 8/8.
- `blink.style` is not a Blink category (Blink's is `blink_style`, already implied by `blink`); harmless.
- Token windows = `--saved-token-N` transition starts (as B0). Self times by stack over all main-thread X events of the window; phase attribution by
  nearest ancestor among the lifecycle containers. `SelectorStats` is emitted after each pass (inside `updateStyleAndLayoutIfNeededRecursive`) and was
  joined to the preceding `UpdateLayoutTree`.
- The `serviceAnimations` split (10.0 k / 8.0 k / 8.6 k per frame) is from direct timestamp containment (`svc_check.out`); `anatomy.py`'s phase table
  puts the hover 0-pass calls under "style".
- Everything marked [inference] (`PendingAnimations::Update`, snapshot validation, `RecomputeMouseHoverStateIfNeeded`) is Blink structure fitting the
  observed positions and regressions; no trace event names them.
