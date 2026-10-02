# R7T — can exact capacity-8 go clearly below 15 s/token in stock Chrome? (2026-10-01)

Agent R7T. Inputs: PLAN.md, RESULTS-round3/5/6, R5A (+census), R4T, R4X, R3H, R3F, R5C, R5E, R5M, R2E, R3P, R4A, R7P; the never-parsed
`R5A/run-combined7/time8-t1-trace.json.gz` (blink/cc/blink_gc categories; ring buffer = token 7 of combined7, 8/8 ids, swap-pressured 20.8 s
token) parsed with `R5A/anatomy.py` → `R7T/parsed-t1/time8-t1-anatomy.{md,json}`; the DOM of `bundles/combined8` (`R7T/dom_chain.py`);
two fixtures built from the REAL layer-0 fc stage and the REAL 50,257-row head (`R7T/fix/`: `gen_fix.py`, `gen_head.py`, runner `run_fix.mjs`,
lock launcher `run_fix.sh`, results `R7T/fix/results/{fc1,fc2,fc3,fc4,head1}.{jsonl,stdout.log}`, summariser `summarize.py`). Log `R7T.log.md`.
No repo edits, no bundle builds, no git. Chrome 154.0.8037.58 headless; lock holds 70 s / 74 s / 204 s / 25 s / ≈60 s, all behind R6X/R7B.

## 0. Answer

**No to 10–12; yes to ≈13.5.** Exact capacity-8 can drop from ≈15.3–16 to **≈13.3–14 s/token** with three changes that touch no numerics
(levers 1–3, ≈ −1.4…−1.7 s). Below that, every remaining second is a per-transported-value cost of the view-timeline carrier primitive
(≈8.4k values/layer, unpackable: R3P) or the head's 301k per-glyph font operations; the structural floor of this architecture in stock
Chrome is **≈12.5 s/token** (§3). Main finding: R5A's "≈45 µs per restyled carrier" in the fc/qkv/attn **write** passes is not the
carriers — a carrier costs **3 µs (+4 µs as a view-timeline subject)**; ≈70 % of each write pass is the 48/36/12 **R4T consumer chunk
elements**, which sit *above* the stage's receipt/gate and are therefore re-cascaded (64 unchanged animations ≈ 25 ms + 192 `var()` decode
declarations ≈ 28 ms per fc pass) every time the stage's inherited inputs change. Moving them *inside* the existing gate (locked during
the write pass, opened at readback — the gate already does this for the proj stage) removes that cost exactly: fixture 69–87 → 16–26 ms per fc write with the readback pass unchanged.

## 1. Ranked levers (per token; base `combined8` ≈15.3–16 s; clean-state predictions)

| # | lever | mechanism (evidence) | predicted s/token | exactness | cost | evidence |
|---|---|---|---:|---|---|---|
| **1** | **Put the R4T consumer chunk chains inside the stage gates** (`stage > scroller + receipt > gate > c0…cN > next stage`, today `stage > scroller + c0…cN > receipt > gate > next`) | The gate (`content-visibility:hidden` until the generation stamp equals the epoch) is closed during the write pass and opens in the readback frame; today only the downstream stage is behind it. Write passes: fc 3,141 el = 121 ms (token 7) — fixture: carriers alone 10 ms (A2), +view-timeline 17–27 (A3), + chain outside gate **77–87 ms** (A0/A0e/A5/A6), chain **inside gate 16–26 ms** (A7, fc4: −46…−55 ms vs A0e in the same run, readback pass unchanged at 57–60 ms); chain decls alone +28 (A4), anims +25; qkv 36 × (9.4 KB + 64 anims) ≈ 30 ms, attn 12 × (10.8 KB + 64) ≈ 11 ms. Sibling placement outside the font subtree does NOT help (A1 = A0: the chain is dirtied by the inherited `--n2-*`/`--range-*`/`--r-*`, not by the font) | **−1.0…−1.2** (fc 46–55 + qkv ≈28 + attn ≈10 ms × 12) | **exact** (structure only; `--hidden-*` bit-identical across A0/A0e/A1/A5/A6/A7 for the same inputs, incl. after the gate reopens) | 0 new elements, 0 new timelines/frames; gate semantics unchanged (its stamp is computed on the receipt, outside the lock). Emitter: `build_hybrid_twelve_block.py:254,293` (`inner = receipt>gate>{child}`; the R4T chunk wrappers must wrap `child`, not `inner`), i.e. the `r4t_consumer_chunk.chunk` call site in `browser_gpt2_reused_core.py:175` | §1a, A.1 |
| **2** | **Token-boundary SMIL handshake → style stamps** (R3F §2.2: `--epoch` on body from the 8 feedback carriers; drop `body:has(#token-k-advanced.done)`; SMIL kept only for the visible marker) | the 3 pure-handshake frames `1`/`39`/`1` still exist in combined8 (`<set … token-N-ready/ack/captured/advanced>`): 65 + 91 + 65 = **221 ms traced** (animate 28–34 + UL 15–18 + paintLC 15 each) | **−0.2** | exact (protocol) | 8 animations on body; risk: `.token-slot-k` latch arming order → 2-token smoke first | A.2 frames 31–33 |
| **3** | **Declaration-identical head rows** (R3H option 2): fold each row's `--base` into its glyph default advance so no row carries `style="--base;--tie"` | Fixture on the real head (197 block-flow groups, 6 ProdQ16 faces, FVS change): H0 page rows style **227/281 ms** → H1 identical rows **65/69 ms** (MPC hits; 7.7 → 1.3 µs/row), layout 916–973 → 886–895, CI 825 = 825, frame busy 2,004–2,119 → 1,812. Also: head pass = 1,438 incremental-marking slices (12 % of style-phase allocation) and per-row variable-trie copies (R5M: +279 MB for 50k rows with inline props under 39k registrations) | **−0.2…−0.3** (+ ≈ −0.05 GC) and **−150…−280 MB live** | exact-class **conditional**: `base_r` must land on the hmtx/HVAR lattice (upem units at 62.5 px; E2 §2.8 off-by-one-bucket class) → offline screen of all 1,024 states before adoption | rebuild 6 head faces (78 MB) with the q16 builder; `.head-row` rule loses `var(--base)` | A.3 |
| 4 | Clean-memory operation (not a page change) | GC in token 7 = 0.96 s in style + 1.17 s in layout (two `ENSURE_SWEEPING_COMPLETED` stalls 555 + 810 ms, 18k incremental-marking slices 0.57 s) vs ≈1.0 s/token clean (R3A); levers 1/3 cut allocation ≈15 % | −0.5 (state) / −0.15 (page) | exact | ≥ 8 GB free, swap empty | A.2 |
| 5 | Score-element K-list substitution (`.fvs-score-H-S{font-variation-settings:var(--fr-k-S),var(--fvs-query-H)}`, 12·p × ≈12.7 KB re-substituted per layer: 0.53 s/token at p = 8, ≈2.1 s at p = 32) → shorter numeric text if the latched K numbers are integers | 163-el pass 131 ms recalc self at p = 7 (36.5 ns/B × 1.07 MB ≈ 39 ms of it) | −0.2…−0.3 (cap 8); ≈ −1 (cap 32) | exact only if lossless | emitter text format | A.2 |
| 6 | Stage rule text (`.shared-fc` re-applies 38 + 14.6 + 18.5 KB of var() text per write; ×3 stages) | 36.5 ns/B | −0.1 | exact | — | census |

Sum of 1–3: **−1.4…−1.7 s/token → ≈13.6–14.4** from 15.3–16; with a clean-memory session ≈13. Target 10–12: not reachable (§3).

### 1a. What the fc write pass is made of (fixture `R7T/fix`: real layer-0 fc stage, 3,072 carriers × 3 shard glyphs, 48 real chunk rules, 3 trials/arm, medians)

| arm | structure | write pass (el · ms) | readback pass | Layout (dirty · ms) | ShapeText | CI | paintLC | animate |
|---|---|---|---|---|---|---|---|---|
| A2 | carriers only, no `view-timeline`, no chain | 3,081 · **9.5–11.8** | — | 9,224 · 53–57 | 3,074 × ≈9 µs | 15.5 | 0 | 0 |
| A3 | carriers with `view-timeline`, no chain | 3,081 · **23–27** | — | 9,224 · 52–54 | 28–29 ms | 15 | 0.3 | 10–15 |
| A5 | chain nested above the gate, 1 layer variant | 3,130 · **84–86** | 50 el · 57 | 9,274 · 41 | 23 ms | 15 | 18 | 17–21 |
| A0 | same, 12 `@container style(--layer)` variants | 3,130 · **77** | 50 · 58 | 9,274 · 41 | 24 | 15 | 18 | 17 |
| A0e | A0 with the epoch advancing per mutation (gate closes/opens) | 3,130 · **87** | 50 · 57 | 41 | 24 | 15 | 17 | 19 |
| A1 | chain as a sibling of the stage (outside the font subtree) | 3,131 · **78** | 50 · 58 | 41 | 24 | 16 | 18 | 17 |
| A4 | chain nested, chunk rules without `animation-*` | 3,130 · **53** | — | 42 | 24 | 14 | 0.3 | 11 |
| A6 | A0 + 4,000 inherited registered numbers on the ancestor | 3,130 · **88** | 50 · 57 | 40 | 23 | 15 | 17 | 20 |
| **A7** | **chain inside the receipt/gate**, epoch advancing (fc4; A0e in the same run: write 69–74, readback 59) | **3,082 · 16–26** | **51 el · 57–60** (gate reopens at readback: 48 chunks + gate + receipt + probe; = A0e's 58.7) | 9,226 · 41–48 (+ a 56-object, 0.1 ms unlock layout) | 23–27 | 15 | 17 | 13–24 |

Reading: a carrier whose inherited font changed costs **3 µs** of style (A2) and **+4 µs** as a timeline subject (A3); the inherited-map size
(A6) and the 12 `@container` variants (A5 vs A0) cost ≈0 per element; the **chain adds ≈55–70 ms** (A0 − A3 = decode text ≈28 ms (A4 − A3) +
3,072 unchanged animations re-examined ≈25 ms ≈ 8 µs each). The chain is dirtied by the inherited custom properties that change in the same
pass (`--n2-*`, `--range-fc`, `--r-*`), so relocating it as a sibling (A1) changes nothing; only a display lock skips it (A7). The chain's
readback pass (≈57 ms = 3,072 changed animations + the same decode text) is legitimate work and stays. Carrier layout = 41–57 ms per
3,072 (shaping ≈9 µs per 3-glyph carrier + ≈7 µs box) and ink overflow 15 ms (1.6 µs/glyph) are per-value floor terms (§3).

## 2. Directions evaluated and closed (with the numbers that close them)

| direction | finding | why closed |
|---|---|---|
| 1 PrePaint ≈46 ms/frame | Not per frame: `PrePaint` = `CompositingInputs` (ink-overflow recalculation of every re-laid-out text item on a fresh font instance) + 4–6 ms pre-paint proper. Token 7: CI 10–11 ms in qkv/ctx frames, **45–49 ms in fc/proj frames** (3,840 changed carriers × 3–12 glyphs ≈ 12 µs each), **915 ms in the head frame** (301k glyph bounds); 1.63 s/token ∝ changed glyphs | no CSS knob skips `RecalcInkOverflow` for painted text (R3H #176: `visibility:hidden` +6 %, `overflow:clip`/`contain:paint` 0); fewer glyphs per carrier needs > 256-axis fonts (R4A) |
| 1 animate + UL ≈60–70 ms/frame | `serviceScriptedAnimations` self 24 + 9.3k `serviceAnimations` 13–17 + UL self (snapshot validation) 21–28 → **6.5–7 µs per live timeline per frame** (R4T fixture 3.06, R3A R2F 5.5; pressure ×1.3) → **2.2 s/token at 35 frames** — the only truly per-frame cost | scoping timelines to the active hop: R2E — `view-timeline:none`/`display:none` lose the value (progress → 100 %), `content-visibility:hidden` keeps the client alive (4.1 µs/frame, no saving); toggling 50–95 µs per carrier per cycle vs 1–3 frames off; the 1,536 token-level timelines: 1,536 × 6.7 µs × 35 = 0.36 s gross vs ≥0.3 s toggle plus a 66k-descendant inherited write (embedding/bridge outputs are inherited at depth 5–20) |
| 1 fewer frames | 2.5 frames/layer confirmed (frames alternate `163+800 | 3141+824 | 2366+163 | 800+3141 | 824+2366`); 35 = 30 hop + head + token-start + 3 handshake | R3F (two passes/frame saturated), R5C (chain route +1.6 s) |
| 2 carrier cost | 3 + 4 µs, not 45 (§1a); inherited-map size and `@container` variants ≈0 per element; the 45 µs was the chunk chain | → lever 1 |
| 2 consumers outside the stage subtree | A1 = A0 (78 vs 77 ms): any inherited input that changes in the pass dirties the chain wherever it sits below the inputs, and proj needs `r` (R3R) so the chain must stay below them | refuted; lever 1 uses the lock instead |
| 2 two values per timeline via subject position + size (`cover` + `entry-crossing`) | solvable (w = 65536·p1/(p2 − p1)) but p2 − p1 ≈ 0.05 → ×5–10 error amplification on top of the 6-digit var() crossing → R3P's lossy class (pinned run margin 4 q-units) | not exact |
| 3 GC | allocation proxy (incremental-marking slices per pass): fc write 265, fc readback 239, qkv/KV/scores 186, loop/LN1 133, attn 50, **head 1,438**, layout phase 6,000 of 18,000/token; two sweeping stalls per token; marking ∝ live heap (0.92 GB, 468 MB of it custom-property tries, mostly the 50k unique head rows) | page-side: lever 1 (−48 × 22 KB × 12 of decode text + 3,072 animation updates per layer), lever 3 (head tries + 49k MPC inserts); the V-leaf stream is R4W (closed); no stock flag (R5G) |
| 4 head | token 7: style 441 + layout 1,279 (shaping 950 = 50,520 × 19 µs) + CI 915 + prepaint 31 = 2.7 s pressured ≈ 2.3 clean; the 197 group maxima are block/grid max-content results = layout, no style-time path reads them; `1ch` reads ONE glyph of ONE instance (R5H) and HVAR is linear (no max); 50,257 dot products via metrics = ≥10k instances (wall) | floor = 301k per-glyph ops; lever 3 trims the per-row bookkeeping (−0.2…−0.3); 3-glyph rows break bucket identity (E2 §2.8) |
| 5 metric transport hybrid | §2a | wall stands |
| 6 frames | SMIL epochs/overlap: prefill overlap impossible autoregressively; R7P costed copies; token handshake = lever 2 | — |
| extra: 768-axis plain HVAR font (1 fc glyph instead of 3, 1 proj glyph instead of 12) via Fontations | R4A: Fontations gives integer advances (0.31–0.52 unit error vs 0.03 stock → precision class lost) and evaluates region scalars per glyph at 1–3 ns × regions × axes (768 × 1,536 ≈ 2–4 ms per glyph vs ≈3 µs today) | not exact, far slower |
| extra: proj carriers 91 µs/carrier of layout (12 shard glyphs → 12 fallback runs) = 0.85 s/token | inherent to 3,072 inputs / 256 axes; splitting a carrier breaks the max-content sum | — |

### 2a. Why the face-count wall stands for a metric hybrid (one paragraph)

Font metrics give 5 numbers per *instance* (`ch`, `ic`, `cap`, `lh`; `ex` needs outline deltas and dies at gvar's 16-bit tuple offset,
`row-axis-multimetric`), so a 768-output hop needs ≥154 output groups × 3–6 input shards = 462–924 instances per layer
(`hvar-five-metric-scale`: 924 faces, 224 MB SFNT, 2.83 GB RSS, **934 ms per 768-input change** — the dependency graph of 924 instances, not
the 6.68 ms of CSS). An instance is a `FontPlatformData`/`SimpleFontData` creation (R4X: ≈0.3 ms at 16 axes, ≈1–2 ms at 128–256 axes — HVAR
region scalars for 256 axes × 512 regions) → **≥200 µs per value** before any style work, versus today's glyph path of ≈3 µs shaping + 7 µs
box + 1.6 µs ink + 7 µs carrier style + 17 µs pending update + 18 µs application ≈ **55 µs per value** plus the per-frame servicing share
(6.7 µs × 2.5 frames). The ctx (768) and proj (768) hops alone would cost ≈1.9 s/layer ≈ 22 s/token and ≈ +2.6 GB; accuracy is fine
(RMSE 0.0014 on the quantised matrix) and irrelevant. `1ch` is free only where the instance exists anyway (R5H's 96 score instances);
there is no other such site — the LN statistics are already numbers and every other producer is a shaped sum of glyphs, not an instance.

## 3. The realistic floor (exact, stock Chrome, this architecture) — clean-state estimates (token-7 trace × 0.75, fixtures)

| block | s/token | proportional to | removable? |
|---|---:|---|---|
| live-timeline servicing (animate + UL self) | 2.0 | 9,223 timelines × ≈5.5 µs × 39 frames | fewer timelines (R3P closed) or frames (R3F/R5C closed) |
| changed-animation application incl. decode text (readback passes) | 1.9 | 101k changed animations × ≈18 µs (A5 readback 57 ms / 3,072) | per value; intrinsic |
| pending-animation updates (paintLC self) | 1.5 | 101k × (14.1 µs + 46 ns × 64) (R4T; token 7: 26–43 ms/frame) | per value; chunk 64 is at the knee |
| carrier layout + shaping | 1.9 | 18.4k glyph runs/layer (fc 3, proj 12, qkv 3, attn 3 glyphs per carrier; ≈3 µs/run + ≈7 µs/box) | per value; proj's 12 faces inherent |
| carrier ink overflow (CI) | 0.8 | ≈3,840 changed text items/frame × 12 µs | no knob (R3H #176) |
| carriers' own restyle | 0.7 | 8.4k × 7 µs × 12 (A2/A3) | floor |
| consumer chains re-cascaded in write passes | **1.2** | 48/36/12 chunks × (64 anims + decode text) × 12 | **lever 1 removes it** |
| stage rule text | 0.2 | 71 KB var() text × 3 stages × 12 | lever 6 |
| qkv-readback/KV/scores/softmax/V pass + V-leaf shaping | 1.2 | 12·p K-list substitutions (lever 5), 26 latch transitions, 768·p leaf glyphs | lever 5 partial |
| head | 2.3 | 50,257 rows × (19 µs shaping + 18 µs ink + 9 µs layout + 7.7 µs style) | lever 3 trims 0.25 |
| per-pass fixed | 0.45 | 67 passes × 6.8 ms (`UpdateLayoutTree`/`updateStyle` self) | 5 passes/layer, fixed |
| token start + layer-11 export + 3 handshake frames | 0.7 | 439 + 324 + 221 ms | lever 2 removes 0.2 |
| GC (clean) | 1.0 | ≈700 MB allocated/token; marking ∝ 0.92 GB live | levers 1/3 −0.15 |
| **total** | **≈15.9** (reproduces 15.3–16) | | **after levers 1–3: ≈13.5–14; floor ≈12.5** |

Below ≈12.5 s/token needs fewer transported values (model change), a non-timeline readback (none in stock Chrome: R4X), or Chromium
changes. **Round-7 implementation candidates: lever 1** (−1.1…−1.3, exact, a wrapper-order change at one emitter call site; verify with the
2-layer smoke that the write passes shrink to ≈3,080/2,330/780 elements and the readback passes grow by 48/36/12) **and lever 2** (−0.2,
exact, protocol); **lever 3** only with its lattice screen (−0.25 and −200 MB).

## Appendix A — evidence

### A.1 Fixture `R7T/fix` (lock holds: fc1 13:38:59–13:40:09, fc2 14:09:18–14:10:32, head1 14:10:36–14:14:00, fc3 14:17:04–14:17:29, fc4 14:25:54–14:26:20)
Pages generated by `gen_fix.py` from `bundles/combined8` verbatim: the 3 layer-0 fc shard faces (`experiments/hybrid-12block-profile/fonts/b0-fc-s{0,1,2}.woff2`),
`.metric/.scroller/.track`, the 4 layer-0 `.shared-fc` rules (`--range-fc` 14.6 KB, timeline-scope + font 54 KB, FVS 18.5 KB, marker base) + the 38 KB `--fq-fc-*` rule, the 48
`.shared-fc-cN` rules (22,105 B each; 64 animations + `--fz/--ft/--hidden` × 64), receipt/gate + stamp, 3,072 `@keyframes fckN`, registrations; inputs = 768 `--n2-*` on `html.go-k`
(16 states); mutation = one CDP class change on `<html>`; JS disabled; per trial 1 warm-up + 1 traced mutation (`blink`, `cc`, `devtools.timeline`); metrics from the trace.
fc1: A0/A1/A4/A6 invalid (the generator left 12 `@container` blocks unclosed → chunk rules unapplied) — rerun as fc2; fc3: A7's gate never re-opened (`--markerbase-fc` registered
non-inherited in the fixture) → write-pass number valid, readback rerun as fc4. Values: `--hidden-000/001/1155/3071` on the chain bottom identical across A0/A0e/A1/A5/A6/A7 for the same k.

### A.2 time8-t1 trace (combined7, token 7, swap-pressured) — `R7T/parsed-t1/time8-t1-anatomy.md`
Phases: style 7,836 (recalcStyle self 6,024; GC 965; serviceAnimations 296), layout 7,766 (performLayout 4,302; ShapeText 199,452 × = 2,278; GC 1,172), compinputs 1,627,
animate 1,366, paintLC 1,102 (self 1,085), UL-other 816 (self 705), prepaint 169. 35 frames, 67 passes.
Frame classes (median ms: dur / animate / UL / paintLC / CI / style / layout): `163+800` 553/38/23/34/11/192/251; `3141+824` 571/40/28/38/46/279/137; `2366+163` 636/39/27/35/25/230/280;
`800+3141` 379/39/21/26/23/178/87; `824+2366` 459/43/22/36/13/221/117; head `50898+6` 2,744/37/18/23/915/441/1,279; handshake `1`,`39`,`1` 65/91/65; token start `895+2405` 439.
Layout classes: 351-dirty (R4S chain + V, combined7 only) 12 × 227 = 3.9 s (gone in combined8 via R5H); proj 2,471-dirty 12 × 70; fc 9,380 × 63; qkv 6,995 × 49; attn 2,416 × 25; head 101,181 × 1,279.
Pass means (recalcStyle self / marking slices): 163-el 131 / 186; 3,141-el 121 / 265; 824-el 114 / 239; 2,366-el 68 / 133; 800-el 26 / 50; head 392 / 1,438.

### A.3 Head fixture `R7T/fix/pages-head` (lock 14:10:36–14:14:00, 2 trials each)
Real 197 block-flow groups × 50,257 rows, 6 ProdQ16 faces, FVS (768 integer axes) changed per mutation. H0 page rows: pass 50,458 el 281/227 ms, layout 100,715 dirty 973/916,
CI 826/825, prepaint 28/26, ShapeText 50,258 × 785/767 ms, busy 2,119/2,004. H1 identical rows (no inline style, literal width rule): pass 65/69 ms, layout 895/886, CI 824/828,
prepaint 24/23, ShapeText 768/767, busy 1,812/1,811. Values differ by construction (cost proxy only).

### A.4 DOM facts (`R7T/dom_chain.py` on combined8)
fc carriers at depth 112: `.shared-ln2`(108) > `.shared-fc`(109) > `.scroller` > `.track` > 3,072 `<i class=metric style="view-timeline:--shared-fc-tN inline">` (3 PUA glyphs each) + marker;
chunk chain `.shared-fc-c0..c47` (110–157) is a sibling of the scroller under `.shared-fc`; `.shared-fc-receipt`(158) > `.shared-fc-gate`(159) > `.shared-proj`(160) > scroller > 768 proj
carriers (12 glyphs, inline `calc-size` widths). Same pattern for qkv (36 chunks under `.shared-qkv` at 40, gate at 78) and attn (12 chunks under `.shared-attn` at 94, gate at 107).
The write-pass element counts (3,141 / 2,366 / 800) = carriers + chunks + ≈20; the downstream stages are already behind the closed gates.
