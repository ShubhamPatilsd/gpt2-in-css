# R5C — the 768-value ctx hop leaves view-timelines: three parallel 128-deep anchor → size-container chains + per-output anchor-sum scrollers, read inside the qkv pass (2.5 → 2.0 frames/layer, −769 carriers/layer)

Agent R5C, 2026-09-24. Tools copy `work/2026-09-19/R5C/tools` (= `R4M/tools7`, combined7's emitter, + `r5c_ctx_chain.py`, flag `R5C_CTX_CHAIN` default ON;
`R5C_CTX_CHAIN=0` reproduces combined7 byte-for-byte, §4). Bundles: `bundles/smoke-R5C-2L` / `smoke-R5C-2L-ref` (2 blocks, 2 positions, flag on/off), `bundles/R5C`
(12 layers, capacity 8; `BUILD.md` = recipe + flag + offline results + `diff -ruN R4M/tools7 R5C/tools`). Scratch / harness / logs: `work/2026-09-19/R5C/`, `R5C.log.md`.
Nothing under the repo's `tools/` or `experiments/` was modified; no commits.

## 0. Headline — CLOSED (works, exact, 2.0 frames/layer, but a net regression of +1.6 s/token)

**The mechanism works exactly as designed and the frames are saved — and it is a net loss.** The 2-layer smoke (§5) shows the layer at **4 passes = 2.0 frames
(combined7 5 = 2.5)**, the ctx readback pass gone, both smokes `[11, 3387]`, the 12-layer run **8/8 ids, verify rc 0** (§6, `finalResidualError` rmse 0.01683 vs
combined7 0.01606, max 0.109 vs 0.117 — same class; the looser `--range-attn` bound shows at the 1e-3 level as predicted). But every one of the 384 chain containers
per layer costs an **interleaved style recalc inside Layout of ≈0.23 ms (smoke, capacity 2) to ≈0.35 ms (B6, capacity 8)** — 5–7× F3's isolated-prototype 50 µs,
because each level's recalc happens under the attention graph's inherited maps (bank aliases, scores, weights, the core's ≈10k inherited numbers) — i.e.
**≈ +87 ms per layer of Layout at capacity 2 and ≈ +134 ms at capacity 8, against ≈ 40–50 ms per layer saved** by removing the ctx pass and half a frame.
B6's paired bench (3 lock-held pairs vs combined7, ref drift 0.4): **+1.6 s/token [+1.3 … +1.9], all pairs the same sign; RecalcStyleCount +4,596/token (= 384 × 12),
LayoutCount −12/token, RSS −27 MB.** No variant brings an exact-class 768-value hop below ≈100 containers per layer (§8), so **the anchor → size-container chain
route is closed for hops of more than ≈100 values**; it stays valid only for the ≤ 100-value hops (R4S's scores). `bundles/R5C` is READY in the correctness
sense (8/8, verify rc 0) but carries `DO-NOT-MERGE` (regression); `R5C_CTX_CHAIN=0` reproduces combined7 byte-for-byte.

## 1. The ctx hop, mapped in the emitter (step 1)

Emitter = `R4M/tools7` (combined7). Per layer after R4S: `[proj+S1 | qkv+scores+softmax+V] [ctx | attn] [fc | proj'] …` = 5 passes = 2.5 frames.

| role | element(s) | where in the tree (combined7, cap 8) | pass |
|---|---|---|---|
| **producers** | 768 `<span class="metric fvs-value-row" style="width:calc-size(max-content,calc(262144px + (size − nbase)·fb_h/fd_h·K));view-timeline:--cache-bridge-tI">` — the p·V glyph run per output coordinate (`browser_gpt2_font_vector_cache.attention()`, `row()`), + 1 generation marker | inside `.fvs-softmax` inside the score-chain bottom `.fvs-score-reader` (depth 141) inside the `.cache-bridge-source` scroller (`h.bridge(100)` in `browser_gpt2_reused_core.compile_reused`, depth 143) | laid out in the qkv pass's Layout (A2) — since R4S the softmax and the V rows are restyled by the interleaved recalc at `#fvs-sc47` |
| **transport** | 769 view-timelines (`html{timeline-scope}`), 12 nested readers `.cache-bridge-c0..11` (64 animations each, R4T chunk) → `--ctx-i:calc((524288/p − 524288 − 262144)/128)`; `.cache-bridge-receipt` / `-gate` | siblings AFTER `.fvs-query` (`layouts["mix"] = font_body + ctx_receiver`, depth 80–93) | **B1 = the ctx readback pass** (≈780 elements: readers + the attn stage) |
| **consumers** | `.shared-attn` (`h.matvec(kind="attn")`): `--range-attn:max(|ctx|)·1.001`, 768 R2C quotients `--fq-attn-i:calc(var(--ctx-i)/var(--range-attn))` (inherits:false, on the same element), `font-variation-settings` with all 768 axes (`A000–A255`, `B…`, `C…`), 3 shard fonts `b{L}attnS0..2` (256 axes each, `unicode-range` per shard), 768 `.metric` rows of 3 glyphs (one per shard; the row width = the sum of the 3 advances) + marker in the stage scroller; readers `.shared-attn-c0..11` decode `--r-i = x_i + ((V/p − V)·UPM/FS − bases_i)·scale_i·range + bias_i` | `.shared-attn` at depth 94 (inside the bridge gate), 71 levels below it to the deepest leaf (`.shared-proj` 161, max 165) | attn rows laid out in B1's Layout; **B2 = attn readback** → `--r` → LN2 → fc fonts |

The hop is a pure transport: geometry (768 row widths, LayoutUnit-exact) → 768 numbers on ONE element → 3 × 256 axis values. Everything that makes it a
frame boundary is the view-timeline snapshot (+1 pass, +½ frame) plus the 769 carrier animations.

## 2. Design (step 2)

### 2.1 Why the chains are 3 × 128 and not 12 × 32

A size-container chain publishes 2 values per level (cqw, cqh) to everything *below* it; the values a consumer needs must all be on one element. The consumer
here is a shard font with 256 axes (`build_gpt2_block_css.SHARD = 256`): shard s's glyph needs `--ctx-{256s..256s+255}` on one element → 128 levels per shard.
Shorter chains need fewer axes per font — 12 chains of 32 = 64-axis per-head fonts = 144 new attn fonts (12 layers × 12 heads), 9,216 glyph rows per layer
instead of 2,304, changed font witnesses. The container count is the same either way (768/2 = 384 per layer); only the depth profile differs.
Σdepth² per layer: **3 × 128² = 49,152 (Σdepth²/2 = 24,576)** vs 12 × 32² = 12,288. F3.md §2 measured the per-level cost flat (4.8 ms/128, 13.6 ms/250, 28 ms/500
= 40–55 µs per level: the next container's subtree is skipped by the main recalc and resumed at its own layout, so each level restyles ≈2 elements, not the
rest of the chain), and F3b's 391-deep out chain ran at 57 µs/level. So the expected chain cost is **linear: 384 × ≈50 µs ≈ 19 ms per layer ≈ 0.23 s/token**; if
the quadratic model of RESULTS-round1 applied it would be 24.6k × 5 µs ≈ 0.12 s per pass. The smoke's Layout time (§5) is the arbiter.

### 2.2 The fan-in: 3 shard glyphs per output can no longer share an inline run

Today output i is one row with three glyphs (three fonts, one 768-axis list). With per-shard chains the three glyphs live in three different subtrees, so the
sum has to happen in geometry: `anchor-size()`. `anchor-size()` is accepted only on positioned boxes, and an anchored box may only see anchors that are
descendants of its containing block unless that block is the viewport (F3.md §2 finding 2) — so the summing box must be `position:fixed`. A fixed box
escapes every ancestor scroller (its containing-block chain ends at the LayoutView), so it cannot itself be a view-timeline *subject* inside a stage scroller,
and a `position:absolute` subject inside a scroller only sees anchors inside that scroller. The shape that satisfies all three constraints: **each output's
carrier is a fixed scroller whose OWN width is the sum** (`width:calc(anchor-size(--r5cg-0-i width) + anchor-size(--r5cg-1-i width) + anchor-size(--r5cg-2-i width))`),
with a constant-width subject (V) and a `300 %` track inside. Progress p = S/(S+V) and the reader decodes **S = V·p/(1−p)** (today w = V/p − V): the sensitivity
to the 6-significant-digit `var()` substitution of p is (V+S)²/V·dp in both cases — the same numbers, because S is exactly today's w (the same three advances).
768 scrollers replace the one stage scroller + 768 absolutely positioned rows (768 more `PaintLayerScrollableArea`s; RSS in §6).

### 2.3 Where the readers of deep anchors may live: nesting order = layout order

Nested `position:fixed` boxes are laid out by the LayoutView's out-of-flow pass in *nesting* order (each sweep lays out the candidates found so far and
collects the fixed descendants of what it just laid out); an anchor is visible to a fixed box only if it was laid out before it (F3.md §3b: "anchors in
other OOF roots only if earlier in tree order" is the same rule at one nesting level). The V rows sit inside `#fvs-sc47` (sweep 48); the ctx chain roots are
fixed children of `.fvs-score-reader` (sweep 49 →), their bottoms and in-flow glyph stages are laid out at sweep 176; the sum scrollers must therefore be
fixed boxes *inside* a chain bottom (sweep 177) — so **the whole `.shared-attn` stage (sums, marker scroller, readers, receipt, gate and the rest of the core
below it) moves into chain 2's bottom**. That also gives the readers `--range-attn` by inheritance (§2.4). Depth: `.fvs-score-reader` 141 + 1 + 128 + 1 +
`.shared-attn`'s 71 levels = **342 (measured on `bundles/R5C`; cap 512; the 12 nested bank wrappers need not be flattened)**.

### 2.4 `--range-attn` without all 768 values on one element

The dynamic range (`max|ctx|·1.001`) normalises the axis values into the fonts' [−1, 1]; per-shard maxima cannot be shared across chains. Replacement, computed on
the softmax element (an ancestor of all three chains) from numbers it already has: ctx_h = Σ_s p_s·v_s with p_s ≥ 0, Σ p_s = 1, so |ctx_{h,i}| ≤ max_s |v_{s,i}| ≤
max_s vs_{s,h} = `--fb-h` (the per-head maximum of the stored V scales, already declared there). `--range-attn:calc((max(.000001,var(--fb-0),…,var(--fb-11)) + .0002) * 1.001)`
(+2e-4 covers the chain's 1/(64·128) rounding; the `.000001` floor keeps it positive). This bound is looser than max|ctx| by the softmax averaging factor:
NumPy over the 8-token run (`R5C/numeric_check.py`) gives 1.5–4.8× per layer (worst mean 4.76, layer 9), so the F2Dot14 quantisation of ctx/range is coarser
by that factor: **1e-4..1.2e-3 rms on the attention outputs, against 6e-3..1.3e-2 rms from today's 6-digit timeline transport of ctx, which the chain removes**
(LayoutUnit-exact: 1/(64·128) ≈ 1.2e-4 per value). Net: the same exact-class, strictly less error than combined7 on this hop; not bit-identical. The gate that
the bound is data-independent matters: a normaliser that could be exceeded would clip an axis silently, and the bound holds for any input by construction.

### 2.5 Layout per layer (HTML shared by all 12 layers; per-layer constants in the layer block)

```
.fvs-score-reader (softmax; --range-attn)                                                    depth 141
  .fvs-softmax > .r5c-ctx-stage (block, 1×1 px, overflow:clip) > 768 .fvs-value-row.r5c-ctx-a  anchor-name:--r5ca-i (display:flex, same calc-size width)
  #r5c-x0-0 > … > #r5c-x0-127 > .r5c-xb.r5c-xb0                                                fixed size containers: width/height = anchor-size(--r5ca-{2k},{2k+1});
  #r5c-x1-0 > … > .r5c-xb1                                                                     k+1 publishes k's pair as --ctx-i; the bottom publishes the last pair,
  #r5c-x2-0 > … > #r5c-x2-127 > .r5c-xb.r5c-xb2                                                declares --fq-attn-{256s..} and the shard's 256-axis list (inherited by)
       .r5c-gs > 768 <i class=r5c-g anchor-name:--r5cg-{s}-{i}>&#x{F0000+768s+i};</i>          the glyph rows (width:max-content, font b{L}attnS{s} per layer)
       .shared-attn > .r5c-sums > 768 .scroller.r5c-sum{width:Σ anchor-size} > .track{300%} > .metric{width:V; view-timeline:--shared-attn-tI}   (+ .r5c-mark scroller
                    > .shared-attn-c0 … receipt > gate > ln2 > fc > proj > …                     for the generation marker)                              depth 271…342
```

Passes: A2 (qkv readback) → scores chain → softmax → V rows → ctx chains → glyph stages → sum scrollers, all in ONE Layout; the attn timelines snapshot after
it → B1 = attn readback → `--r` → LN2 → fc fonts; B2 = fc readback → proj carriers; C1 = proj readback = S1'. **4 passes = 2.0 frames/layer**, even period
(no pairing alternation). Gates: the cache-bridge receipt/gate are gone (ctx and the attn fonts are in the same Layout — nothing can be stale); the attn
receipt still closes its gate in A2 (stamp P−1 vs epoch P, evaluated in the interleaved recalc) and opens it in B1, exactly as before.

## 3. Implementation (step 3) — `R5C/tools/r5c_ctx_chain.py` + hooks (`bundles/R5C/BUILD.md` has the 489-line diff)

- `r5c_ctx_chain.py`: `context_carriers()` (the 768 bridge-shaped carriers with the anchor name in the timeline slot, so `attention()`'s `row()` rewrite is untouched),
  `finish_value_stage()` (→ `<span class="fvs-value-row r5c-ctx-a" style="anchor-name:--r5ca-i;width:…">`), `range_rule()`, `chains()` (3 × 128 containers, bottoms with
  the R2C quotients — same expression text matvec would hoist — and the shard's `A/B/C` list, glyph stages, `{child}` in bottom 2), `sum_carrier()`, `marker_carrier()`,
  `stage_css()` (per-layer subject width V and marker V/3V), `raw_width()` (V·p/(1−p)), `record_attn_group()` (asserts the shard count / codepoints are layer independent), `manifest()`.
- `browser_gpt2_reused_core.compile_reused`: under the flag `ctx_source = r5c.context_carriers()`, no bridge css / receiver (the attention body carries `{child}`).
- `browser_gpt2_font_vector_cache.attention`: requires R4S_SMALL_HOPS and the runs/widths layout; V stage + range rule; body = stage + score chain + `.fvs-score-reader > [.fvs-softmax > V stage, chains]`; manifest.
- `build_hybrid_twelve_block.matvec` (attn only): no `.shared-attn` axis list / quotients / `--range-attn` rule (still `regs`), per-layer `.r5c-xb{s}{font-family}` + V rules, sum + marker carriers instead of the rows/scroller, decode width term swapped; the `.shared-attn{timeline-scope;font;…}` rule, receipt, gate and reader rules are otherwise unchanged.
- `browser_gpt2_reused_adapter`: F5 receipt list −`.cache-bridge-receipt`, inline `var(--epoch)` reader assertion 6 → 5, manifest `r5c*`.

## 4. Offline verification (step 4) — `R5C/offline_check.py <bundle> <ref>`, logs in `R5C/logs/`

| build | reference | result |
|---|---|---|
| `R5C_CTX_CHAIN=0`, 2 blocks / 2 positions, R5C tools | same command, `R4M/tools7` | **index.html and runtime.css byte-identical**; witnesses identical modulo the tools-dir key prefix; manifest +6 `r5c*` keys |
| `R5C_CTX_CHAIN=0`, 12 layers / cap 8, `R4M/tools7` (twin deleted after the check) | `bundles/combined7` | index.html byte-identical, runtime.css identical after font-URL normalisation, witnesses identical |
| `bundles/smoke-R5C-2L` vs `smoke-R5C-2L-ref` | rule diff by category + structure | `RESULT: PASS` — elements 62,360 → 66,575 (+4,215), max depth 165 → 296 |
| `bundles/R5C` vs `bundles/combined7` | same checker | `RESULT: PASS`: +384 container-size rules with the exact (s,k) → anchors 256s+2k, 256s+2k+1 mapping, +381 publishers (k+1 → k), +3 bottoms (last pair + exactly their 256 quotients and 256 axes), +36 per-layer shard families, +12/+24 V rules, +1 `--range-attn` bound, 144 reader rules identical modulo the width term, −12 bridge readers, −12 `.shared-attn` lists, −12 max|ctx| ranges, −1 lifted quotient rule, −bridge scroller/receipt/gate, html scope −769 bridge names, no UNEXPECTED category; html: 768 V anchors before the chains, 384 containers nested in order, 2,304 glyph rows with codepoints `U+F0000+768s+i`, 768 sum scrollers with the exact 3-term widths, `.shared-attn` = child of `.r5c-xb2` after its glyph stage, no `cache-bridge`/`{child}` leftovers, view-timelines 9,223 → 8,454 (−769), **elements 67,569 → 71,784 (+4,215), max depth 165 → 342**, containing-block lint over the 141/272 ancestors of the chain roots / first sum scroller clean; V glyph rules, softmax, `@font-face` identical; **witnesses 283/283 identical** modulo the tools dir |
| NumPy ids (`R5C/reference_ids.py`) | expected | `[11, 314, 1101, 7926, 11, 475, 314, 1101]` (arithmetic unchanged; the reference models neither transport) |
| `R5C/numeric_check.py` | — | range bound / max|ctx| 1.5–4.8×; F2Dot14 output error 1e-4..1.2e-3 rms (new) vs 6e-3..1.3e-2 rms today's ctx transport; S/V 0.03–0.46 (§2.2, §2.4) |
| `tools/launch_browser_gpt2.py --check` on `bundles/R5C` | — | 285 static files / 285,577,967 B / no JavaScript |

Sizes: runtime.css 38,781,414 B (combined7 39,073,102), index.html 5,879,529 B (5,612,552).

## 5. 2-layer smoke pair (step 5) — `bundles/smoke-R5C-2L` (on) vs `smoke-R5C-2L-ref` (off), one lock hold, light trace

`R5C/chrome_all.sh` → `run_chrome.sh smoke-pair` (gate met 14:22 after 5,220 s: free 4 GB, swap used 2,860 MB, AC; lock after 875 s behind R5A's trace), 14:36:59–14:38:14,
load ≈ 3–4. Results `R5C/runs/smoke-R5C-2L{,-ref}/{harness.log,frames.md,trace.json.gz,pipeline-results.json}`, per-frame tables via `R5C/frames.py`.

- **ids `[11, 3387]` in both** (= the 2-layer reference); done markers 2/2; elements 66,575 vs 62,360; fonts 73 / 73.
- Token 2 (the steady-state token; frames.py's token attribution puts it under "1" because the trace clock is offset — the rows are identified by their pass shapes):

| | frame | passes (elementCount:ms) | layouts (dirty:ms) | what |
|---|---:|---|---|---|
| **off** | 14 | `865:52 2405:101` | 1601, 6997 | epoch/feedback → embedding readback → S1 of layer 0 |
| | 15 | `0:9 81:62 800:36` | **161:65**, 2416:16 | **qkv readback + scores chain + softmax + V rows (Layout 65 ms) ; ctx readback → attn fonts (36 + 16 ms)** |
| | 16 | `0:9 3141:106 824:122` | 9380:46, 2471:54 | attn readback → `--r` → LN2 → fc fonts ; fc readback → `--hidden` → proj carriers |
| | 17 | `0:10 2366:60 81:78` | 6995:37, 161:65 | proj readback → S1 of layer 1 ; qkv(L1) + scores + V |
| | 18 | `0:9 800:26 3141:116` | 2416:16, 9380:47 | ctx' ; attn' |
| | 19 | `0:9 824:99 791:24` | 2471:52, 813:1 | fc' ; proj' → hold |
| | 20 | `0:10 50898:385 6:10` | 101181:1076 | bridge → head (unchanged) |
| **on** | 12 | `865:52 2405:101` | 1601, 6997 | epoch → embedding → S1 of layer 0 |
| | 13 | `0:9 67:55 3141:119` | **1370:152**, 9289:70 | **qkv readback + scores + V rows + 3 ctx chains + attn glyph stages + 768 sum scrollers, all in ONE Layout (1,370 dirty objects, 152 ms) ; attn readback → LN2 → fc fonts as the frame's second pass** |
| | 14 | `0:9 824:112 2366:71` | 2380:75, 6995:36 | fc readback → proj carriers ; proj readback → S1 of layer 1 |
| | 15 | `0:9 67:56 3141:116` | 1370:149, 9289:70 | qkv(L1)+…+sums ; attn' |
| | 16 | `0:9 824:118 791:25` | 2380:86, 813:1 | fc' ; proj' → hold |
| | 17 | `0:10 50898:335 6:10` | 101181:1094 | head (unchanged) |

- **Frame structure: 8 layer passes in 4 frames = 2.0 frames/layer (off: 10 passes in 5 frames = 2.5)**, sequence `[qkv+scores+ctx+attn-fonts | attn] [fc | proj+S1']` with an
  even period (no pairing alternation); the ctx readback pass (`800:36` + Layout `2416:16` ≈ 52 ms) is gone. Whole-session counters idle → end: on RecalcStyleCount 16 → (the
  interleaved recalcs are counted, F3b §2b), LayoutCount 12 → 12 + 22 + 1; per token 2: **ULT 8 vs 10, Layout 8 vs 10** (the traced passes; `R5C/logs/frames-*.json`).
- **Where the time went (the constants):** the qkv frame's Layout grew from **65 ms (161 dirty objects: the 12-container score chain + the 2,311-element V-row restyle) to
  152 ms (1,370 objects)** = **+87 ms for 384 more containers → ≈0.23 ms per chain container** (interleaved recalc + layout of one fixed size container publishing two
  inherited numbers under the attention graph's inherited maps; F3 §2 measured 40–55 µs for the same shape in an empty page, F3b 340 µs with `--gelu()`), plus the 768
  sum scrollers and 2,304 glyph rows inside the same Layout. Removed per layer: the ctx pass ≈ 52 ms + half a frame's fixed cost. Layer wall time in the smoke
  (frame durations, 2 layers): off 15–19 = 1,672 ms (836/layer), on 13–16 = 1,747 ms (874/layer) → **+38 ms/layer at capacity 2** (≈ +0.45 s/token if it scaled linearly to
  12 layers); B6 measured +1.6 s/token at capacity 8, i.e. ≈ +134 ms/layer ≈ **0.35 ms per container** (the inherited maps under the banks are larger at capacity 8:
  296 `--fr-*` alias entries and 8× the score/weight fields).

## 6. 12-layer correctness run — `bundles/R5C`, ONE passive run (not a timing run)

`run_chrome.sh correctness-R5C` → `correctness_inner.sh R5C` (R4M's `correctness_run.mjs`: headless Chrome 153, `--js-flags=--heap-growing-percent=10`, poll
`#token-8-captured.done` every 5 s, one readback), 15:32:11–15:34:57 under `CHROME.lock` (waited 3,215 s behind R5H's c32 run), AC, free 5 GB, swap used 2,829 MB,
load { 2.5 3.7 4.4 }. Results `R5C/run-R5C/{harness.log,verify.log,verification-vectors.json,pipeline-results.json}`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc 0: tokenAgreement 8 × True, originalFloatAgreement
  8 × True, finalHeadMatchesActualInput True, text "Hello, I'm sorry, but I'm"; `finalResidualError` rmse **0.016834** / max **0.10932** (combined7 0.016055 / 0.11652):
  the looser `--range-attn` bound (§2.4) costs ≈ 5 % rmse, the exact ctx transport lowers the maximum — same 1e-2 class, ids identical.
- Whole-run counters: **RecalcStyleCount 40,474 (combined7 3,768: +36.7k over 8 tokens = the 384 × 12 interleaved container recalcs per token)**, **LayoutCount 434
  (combined7 544: −110 ≈ −14/token, the removed ctx readback layouts)**, Nodes 138,089 (132,338).
- Per-token capture times (5 s poll granularity, indicative only): 23.3, 14.0, 12.1, 19.6, 12.5, 23.7, 21.2, 18.3 s (sum 144.6 s; combined7's run 146.8 s under a similar load class).
- `bundles/R5C/READY` created 15:35 by `R5C/finish.sh` (8/8 + verify rc 0); **`DO-NOT-MERGE` added after B6's verdict** (the bundle is correct but slower).
- **B6 (coordinator, paired bench, 3 lock-held pairs vs combined7, quiet machine, ref drift 0.4): +1.6 s/token [+1.3 … +1.9], all pairs the same sign; RecalcStyleCount
  +4,596/token; LayoutCount −12/token; RSS −27 MB.**

## 7. Prediction as written before the runs (kept for the record — the measured outcome is §5/§6/§8)

- **Frames**: 12 layers × (2.5 − 2.0) = −6 frames/token × ≈117 ms ≈ **−0.70 s/token**; −12 ctx readback passes (≈780 elements each + fixed pass cost) ≈ −0.1..−0.3 s.
- **Carriers**: −769 timeline animations per layer evaluation × ≈16 µs ≈ −0.15 s/token; −769 live timelines × ≈10.7 µs per frame × ≈29 frames ≈ −0.24 s/token of idle servicing.
- **Costs**: +384 containers × ≈50 µs ≈ +0.23 s/token (interleaved recalcs inside A2's Layout); +768 fixed scrollers + 1,536 extra glyph elements (2,304 single-glyph
  rows vs 768 three-glyph rows; same 2,304 shaped segments, 3 font instances) ≈ +0.1..0.2 s/token; +768 × 3 anchor lookups (cheap).
- **Net predicted ≈ −0.8 ± 0.4 s/token** (combined7 ≈ 16.0 → ≈ 15.2); only a paired bench (B6) is meaningful. If the chain restyle were quadratic (Σdepth²/2 = 24.6k
  element recalcs per layer), the containers would cost ≈ +1.5 s/token and the change would be a loss — the smoke's per-frame Layout time decides.
- **Memory**: +768 fixed containers/scrollers per page graph (F3 §2b: ≈ 35 KB per positioned box ≈ +40 MB) + 768 `PaintLayerScrollableArea`s; −1 scroller. B6's RSS column decides.
- **Chromium behaviours relied on** (all load-bearing in F3/F3b/R4S already): fixed boxes see every anchor laid out before them; nested OOF roots are laid out in
  nesting order (the sum scrollers are two sweeps after the glyph stages by construction — if Chromium ever laid out propagated fixed descendants before their
  siblings' contents, the sums would read the previous pass's advances: the 2/2 and 8/8 ids are the check); a scroller's own width feeding a view-timeline
  progress is snapshotted after the same Layout (the 769 attn timelines already do this with the subject width).
- **Precision**: ctx transport exact to 1.2e-4 (was ≈ 5e-3); axis normaliser 1.5–4.8× looser (§2.4); attn transport unchanged in class. Expect `finalResidualError`
  at or below combined7's 0.0161 rmse; the ids are the acceptance test.
- **Depth**: 342 of 512 at capacity 8; each extra capacity slot adds 6 levels (the score chain), so capacity 32 (R4C's `-c32` demo) would be ≈ 342 + 144 = 486 — tight but under the cap; not built here.

## 8. Verdict: CLOSED — and why no variant reopens it

**Constants.** Frames saved: 6 per token (12 × 0.5) × ≈117 ms ≈ 0.70 s, plus 12 ctx passes ≈ 0.6 s of style+layout — realised as LayoutCount −12/token and the
2.0-frame period in the smoke. Cost: **384 interleaved container recalcs per layer × 0.23 ms (cap 2) … 0.35 ms (cap 8) = 87 … 134 ms per layer = 1.0 … 1.6 s/token**,
which is what B6 measured (+1.6 s/token). The 50 µs/level of F3's prototype does not transfer to the real page: each level's recalc runs under the attention graph's
inherited custom-property maps, and the per-level cost scales with them (R4S's score chain showed the same at capacity 32, R4S.md). The break-even for this
mechanism is therefore ≈ 40–50 ms per layer ≈ **100–140 containers per layer at capacity 8** — i.e. a hop of ≈ 200–280 values at best, and only if it also removes a
pass and half a frame.

**Can the container count for a 768-value hop drop below ≈100?** No:
- 2 values per container (cqw + cqh) is the container-unit limit (`cqi/cqb/cqmin/cqmax` alias the same two; R4X §1). Packing two values into one dimension via
  `round(down, 100cqw/1px, …)` / `mod()` is numerically possible (the publisher is a pure `calc()`, no `var()` rounding) but halves the bits: exact-class needs the
  full 1/(64·128) resolution of the 2^18-px carrier (≈ 24 bits), and two 12-bit halves are not exact-class → 4 values/container is out; 192 containers would still be > 100 anyway.
- Reading the anchors directly on the consumer without containers is impossible: `anchor-size()` is accepted only in sizing/inset/margin properties of positioned boxes,
  never in `font-variation-settings` or custom properties (R4X §1, E1 #2, re-verified on Chrome 153); `container-progress(width of --name)` (named-container readback,
  which would remove the chain and the inheritance through every level) parses but evaluates 0 on 153 (R4X #3).
- The per-shard depth is set by the font's axis count (256 → 128 levels); fewer, wider fonts are rejected (> 256 axes, R4A), and more, narrower fonts (per-head 64 axes)
  do not change the container total (768/2 = 384) — only the depth profile.
- Font-metric readback (`1ch`, R5H's route) reads a font instance's metrics, not a laid-out width; the ctx producers are shaped runs (p·V glyph sums), so this hop
  cannot be turned into a metric read without first getting the 768 numbers onto elements — which is the transport itself.
- The hop's size is the model's (768 = d_model); bounding or sparsifying it is a model change.

So the anchor → size-container chain is a valid, exact, frame-free readback **only for small hops (≲ 100 values: R4S's 96 scores, LN statistics if they ever
became a hop)**; for the 768-value ctx/attn/proj hops and the 3,072-value fc hop the interleaved recalcs cost more than the frames they save. This closes the
anchor-chain route for hops > ≈100 values; the remaining levers for the large hops are fewer transported values or a cheaper carrier primitive (RESULTS-round3).

## 5b. Smoke pair — harness results (appended unattended by R5C/finish.sh, 2026-09-24 15:35:12)

### smoke-R5C-2L

```
{"t":2654,"event":"loaded","elements":66575,"fonts":73}
{"t":4930,"event":"pre-run-idle","RecalcStyleCount":16,"LayoutCount":12,"Nodes":127733}
{"t":18307,"event":"token-captured","token":1,"sinceRunMs":10714,"ts":393531.082441,"RecalcStyleCount":1644,"LayoutCount":35,"dRecalc":1628,"dLayout":23,"dRecalcS":6.07,"dLayoutS":4.02}
{"t":20435,"event":"token-captured","token":2,"sinceRunMs":15267,"ts":393533.210897,"RecalcStyleCount":1648,"LayoutCount":36,"dRecalc":4,"dLayout":1,"dRecalcS":0.04,"dLayoutS":0.01}
{"t":33209,"event":"final","tokens":[11,3387],"tokensText":"","doneMarkers":{"1":true,"2":true},"cachesComplete":0,"tokenTimes":{"1":10714,"2":15267},"diag":{}}
```

Per-token frame summary (R5C/frames.py, full table in `R5C/runs/smoke-R5C-2L/frames.md`):

| token | frames with a style pass | UpdateLayoutTree | Layout | frame ms |
|---:|---:|---:|---:|---:|
| 1 | 17 | 35 | 22 | 13066 |
| 2 | 4 | 4 | 1 | 223 |


### smoke-R5C-2L-ref

```
{"t":2692,"event":"loaded","elements":62360,"fonts":73}
{"t":4968,"event":"pre-run-idle","RecalcStyleCount":17,"LayoutCount":12,"Nodes":121982}
{"t":18166,"event":"token-captured","token":1,"sinceRunMs":10533,"ts":393566.6094,"RecalcStyleCount":115,"LayoutCount":39,"dRecalc":98,"dLayout":27,"dRecalcS":6.69,"dLayoutS":3.07}
{"t":20299,"event":"token-captured","token":2,"sinceRunMs":15094,"ts":393568.742913,"RecalcStyleCount":119,"LayoutCount":40,"dRecalc":4,"dLayout":1,"dRecalcS":0.04,"dLayoutS":0.01}
{"t":33966,"event":"final","tokens":[11,3387],"tokensText":"","doneMarkers":{"1":true,"2":true},"cachesComplete":0,"tokenTimes":{"1":10533,"2":15094},"diag":{}}
```

Per-token frame summary (R5C/frames.py, full table in `R5C/runs/smoke-R5C-2L-ref/frames.md`):

| token | frames with a style pass | UpdateLayoutTree | Layout | frame ms |
|---:|---:|---:|---:|---:|
| 1 | 20 | 41 | 26 | 12901 |
| 2 | 4 | 4 | 1 | 236 |


## 6b. 12-layer correctness run — harness results (appended unattended)

```
{"t":3344,"event":"loaded","elements":71784,"fonts":283}
{"t":28693,"event":"token-captured","token":1,"sinceRunMs":23305}
{"t":42702,"event":"token-captured","token":2,"sinceRunMs":37314}
{"t":54762,"event":"token-captured","token":3,"sinceRunMs":49374}
{"t":74357,"event":"token-captured","token":4,"sinceRunMs":68969}
{"t":86863,"event":"token-captured","token":5,"sinceRunMs":81475}
{"t":110520,"event":"token-captured","token":6,"sinceRunMs":105132}
{"t":131721,"event":"token-captured","token":7,"sinceRunMs":126333}
{"t":150005,"event":"token-captured","token":8,"sinceRunMs":144617}
{"t":157250,"event":"final","packedBanks":true,"packedHead":true,"headSample":"\"X000\" -12,\"X001\" -3,\"X002\" 4,\"X003\" -13,\"X004\" 8,\"X005\" -20,\"X006\" 89,\"X007\" -5,\"X008\" 5,\"X009\" 9,\"X00A\" -3,\"X00B\" -11,","tokens":[11,314,1101,7926,11,475,314,1101],"tokensText":"","bodyProps":{"--epoch":"8","--winner":"-1","--head-output-epoch":"0","--token":"15496"},"doneMarkers":{"1":true,"2":true,"3":true,"4":true,"5":true,"6":true,"7":true,"8":true},"rawSample":{"k":{"list":"\"K000\" -0.515165,\"K001\" 0.956542,\"K002\" 0.0725739,\"K003\" -0.0955284,\"K004\" 0.277453,\"K005\" 0.233878,\"K006\" -0.070758,\"K007\" 0.0710487,\"K008\" -0.902708,\"K009\" 0.","scales":[2.42466,2.2681,2.1122

{'tokens': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceQ9Q16': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'referenceAttentionMask': 'full causal', 'tokenAgreement': [True, True, True, True, True, True, True, True], 'finalResidualError': {'finite': 768, 'rmse': 0.01683353880045853, 'maximum': 0.10931616094288188}, 'finalHeadActualInputWinner': 1101, 'finalHeadMatchesActualInput': True, 'originalFloatWinners': [11, 314, 1101, 7926, 11, 475, 314, 1101], 'originalFloatAgreement': [True, True, True, True, True, True, True, True], 'text': "Hello, I'm sorry, but I'm"}
```
