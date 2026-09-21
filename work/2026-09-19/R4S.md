# R4S — the small hops: the score hop (97 carriers) moves off view-timelines onto an anchor → size-container chain inside the qkv pass (3.0 → 2.5 frames/layer)

Agent R4S, 2026-09-20. Tools copy `work/2026-09-19/R4S/tools` (= R3M's combined4 emitter + `r4s_small_hops.py`, flag `R4S_SMALL_HOPS` default ON;
`R4S_SMALL_HOPS=0` reproduces R3M's output byte-for-byte — checked on the 2-layer build: `R4S/scratch/off-2L` == `R4S/scratch/r3m-2L` built from `R3M/tools`).
Bundles: `bundles/smoke-R4S-2L` / `smoke-R4S-2L-ref` (2 blocks, 2 positions, flag on/off), `bundles/R4S` (12 layers, §6; `BUILD.md` = recipe + flag + offline results +
`diff -ruN R3M/tools R4S/tools`). Scratch/harness/logs: `work/2026-09-19/R4S/`, `R4S.log.md`. Nothing under the repo's `tools/` or `experiments/` was modified; no commits.

## 0. Headline

**Yes: the score hop is the one small hop per layer, and it moves off view-timelines without a new frame.** Of the six per-layer hops only the attention scores (96 values
+ 1 stamp) are ≤ 500 values; LN1/LN2 statistics are `calc()` sums over registered numbers on one element (no carriers, no transport), the generation markers ride with their
stage's data, and the token-level feedback hop (8 values) is already hidden in the SMIL handshake frames (§1). The 96 score glyphs become in-flow anchor rows of a fixed stage and a
48-deep `position:fixed; container-type:size` chain (`anchor-size()` sizes, `100cqw/100cqh → --fs-H-S` publishers, F3/F3b rules) resolves them inside the **qkv readback pass's own
Layout**; the softmax and the 768 V rows are restyled/laid out in that same Layout (interleaved container recalc), so the ctx readback becomes the frame's second pass and the score
gate/receipt/stamp/scroller/96 animations disappear (§2). Per layer 6 → 5 passes, **3.0 → 2.5 frames** (smoke §5: 10 layer passes in 5 frames, sequence `[qkv+scores | ctx] [attn | fc]
[proj+S1 | qkv'+scores'] …`, 13 passes/13 layouts per 2-layer token vs 15/15), i.e. ≈ 35 frames/token vs 41. Correctness: 2/2 smoke ids, **8/8 ids on 12 layers** with verify rc 0
(§6, LayoutCount 535 vs 629). Precision improves at the rounding point that changed (scores exact to the carrier's LayoutUnit, no float-progress rounding; `finalResidualError`
rmse 0.01722 vs 0.01765, max 0.168 vs 0.134 — same class, §2.4). Predicted ≈ −0.8 ± 0.2 s/token (≈ 17.4 vs 18.2); 2.0 frames/layer needs the 768-value ctx hop as a 384-deep chain,
which reaches ≈ 496 of the 512-element parser cap unless the 12 nested bank wrappers are flattened first (§7). `bundles/R4S` READY.

## 1. Inventory: every hop with ≤ ~500 values (step 1)

Emitter = `R3M/tools` (combined4). A "hop" is a geometry → number boundary (carrier widths → view-timeline → animated `<number>` → decode); "pass" = one
`UpdateStyleAndLayout`; Blink runs at most two per frame (R3F §0). Per layer after R3R (R3R.md §1.1 minus hop 1): qkv 2,305 → scores 97 → ctx 769 → attn 769 → fc 3,073 → proj 769.

| hop | values (carriers) | produced by (pass) | laid out where | consumer (element, what it does) | consumer's pass today | size class |
|---|---:|---|---|---|---|---|
| scores | 96 + 1 stamp | `.fvs-query` restyled when the qkv gate opens: 96 `.fvs-score-H-S` glyphs (FvsDot fonts, `font-variation-settings:var(--fr-k-S),var(--fvs-query-H)`, `width:calc-size(max-content,262144px + (size − base)·fqs·frks·k)`) | `.fvs-score-source` scroller (html-scoped timelines) | `.fvs-score-reader` (96 anims → `--fs-H-S`), softmax on the same element (`--fm/--fe/--fd/--fb/--fw`), `.fvs-score-receipt` opens `.fvs-score-gate` → `.fvs-softmax` → 768 V rows shaped | **B1** (own pass, first of frame B) | **small — moved (§2)** |
| LN1 statistics | 0 | `.shared-ln1{--mean1:calc(Σ var(--x-i))/768;--var1:…;--n1-i:…}` (`build_gpt2_block_css.norm_declarations`) | — (pure `<number>` arithmetic in style) | LN1 → `--fq-qkv-*` → qkv fonts, same pass (S1) | S1 | **not a hop** — no carriers, no transport |
| LN2 statistics | 0 | `.shared-ln2{--mean2,--var2,--n2-i}` from `--r-*` (numbers on `.shared-attn-c*`) | — | fc fonts, same pass (B2) | B2 | **not a hop** |
| generation markers | 1 each (qkv, ctx, attn, fc, proj) | laid out with their stage's carriers | the stage's scroller | `-receipt` → `--gate-*` (same pass as the stage's data readback) | with the data | ride along — no separate pass |
| feedback (token level) | 8 (`.feedback-metric-k`, `--saved-token-k`) | the token latch (SMIL `39` frame) | `.feedback-scroller` | `.feedback-reader` → `--feedback-k` → `.feedback-select{--token}` → embedding fonts when `--epoch` advances | latched before the `863` epoch pass; its readback is not a per-token pass of its own (R3F §1) | small but already free — no pass to save; the 3 SMIL frames are R3F §2.2's item |
| qkv / ctx / attn / fc / proj | 2,305 / 769 / 769 / 3,073 / 769 | — | — | — | — | large: ≥ 769 values need ≥ 385 containers per chain (F3 cap ≈ 250, parser 512, F3b's 391-deep out chain was the exception at depth ≤ 434); ctx discussed in §7 |
| head bridge (token level) | 769 (`.reused-final-export`) | hold pass | — | `.b11-bridge-c0/c1` → head | own pass (paired with the head frame) | large |

So the only per-layer hop that is small is the **score hop**; LN statistics are not transported at all (they are `calc()` sums over 768 registered numbers on one
element and cost style time, not frames). The feedback hop is small but its readback already hides inside the token handshake frames.

## 2. Design: the score hop as an anchor → size-container chain that completes inside the qkv pass's lifecycle (step 2)

### 2.1 Where the score values are born and die inside pass P (layer L)

R3R §1.1's cascade: S1 (= proj readback of P−1) restamps `--native-pass:P`, the qkv receipt (never gated) closes the qkv gate → the whole attention subtree
(`.fvs-query` and below) is display-locked; A2 (qkv readback) opens the qkv gate → `.fvs-query` is restyled with the new `--qkv-*` (`--fqs-H`, `--fvs-query-H`,
`--fvs-live-*`, the bank write; the current slot's K/V arrive live because the write slot's fields are excluded from the bank's `transition-property`), the 96 score
glyphs are shaped and laid out in A2's layout. Today their readback needs the next pass (B1): `.fvs-score-reader`'s 96 timelines snapshot after A2's layout,
B1 decodes `--fs-H-S`, the softmax and the 768 V rows are restyled/laid out, and only then the ctx snapshot changes → B2 = ctx readback. The score gate exists
solely to keep the V rows from being laid out in A2 with the stale (P−1) scores (the receipt sees stamp P−1 in A2 and closes the gate; it opens in B1).

**Claim: with a chain the scores are consumed in A2's own layout, the V rows are laid out in that same layout, and the ctx readback becomes B1.** The chain
(F3.md §2, F3b §1 rules): the 96 glyphs become in-flow block rows (`anchor-name:--fsa-H-S`) of a `position:fixed` stage; after the stage in tree order, 48 nested
`position:fixed; container-type:size` containers `#fvs-sc0..47`, container k with `width:anchor-size(--fsa-{2k} width); height:anchor-size(--fsa-{2k+1} width)`,
container k+1 declaring `--fs-{2k}:calc((100cqw / 1px − 262144) / 128); --fs-{2k+1}:calc((100cqh / 1px − 262144) / 128)` (cq units resolve against the nearest
*ancestor* container, F3b's one-element-per-level shape); the chain bottom `.fvs-score-reader` (in-flow, inside `#fvs-sc47`) publishes the last two and hosts
the unchanged softmax declarations and `.fvs-softmax` (V rows, ctx marker, the `.cache-bridge-source` scroller). Inside A2's Layout: the stage's rows are laid out
(fixed OOF root earlier in tree order → its anchors are acceptable to the later fixed containers, F3 §3b), then `#fvs-sc0` sizes itself, Blink's interleaved
container recalc restyles `#fvs-sc1` (its two `--fs` values), … , `#fvs-sc47` is laid out, the bottom's subtree (reader + 768 rows × (1 + p) glyph elements) is
restyled ONCE with all 96 scores (size-container subtrees are skipped in the main recalc and resumed at their container's layout — F3 §2 measured ≈ 2 elements
per level, not the subtree, and F3b's 391-deep out chain hosting the rest of the core confirms it), and the V rows are laid out. Their view-timelines snapshot
after A2's layout → B1 = ctx readback (`.cache-bridge-c0/c1` → `--ctx-*`; the bridge receipt sees the ctx marker = P → opens the bridge gate → attn fonts laid out),
B2 = attn readback → `--r` → LN2 → fc fonts, C1 = fc readback → `--hidden` → proj carriers (+ `--pass` marker), C2 = proj readback = S1(P+1). Five passes.

### 2.2 Gate / latch semantics (R3R §1.3 re-checked)

- **No stale read.** The score gate is dropped: the scores can no longer be stale relative to the glyphs they come from — both are laid out in the same Layout,
  and the interleaved recalc of the bottom happens *after* `#fvs-sc47` has its final size. The V rows' other inputs are final in A2: `--fr-*` bank aliases (this
  pass's write is live for the current slot, latched for the others), `--fv-S` (from `--position`, stamped in S1), `--fw-H-S` (from `--fs` and `--fr-vs`).
- **No spurious layout between A2 and the next A2.** The attention subtree is under the qkv gate, which is open from A2 to C2 and closes in S1(P+1) (same pass in
  which `--native-pass` changes). In B1/B2/C1/C2 nothing the subtree depends on changes: `--ctx`/`--r`/`--hidden` are declared below or beside it, the container sizes do
  not change (no interleaved recalc), so the V rows keep A2's geometry and the ctx snapshot changes exactly once per pass. In S1 the qkv receipt closes the gate before
  its children are restyled (R3R (i): the S1 pass sizes prove the lock blocks child restyle/layout in the pass in which it is acquired).
- **Cache-bridge receipt.** Unchanged mechanism, one pass earlier: in A2 it is restyled when the qkv gate opens, its `--bridge-stamp` snapshot is still B1(P−1)'s → decodes P−1 →
  bridge gate closes in A2 (was: closes in A2 too — R3R "cache-bridge gate closes at hop 2"); the new ctx marker (P) is laid out in A2's layout, so the bridge gate opens in B1.
- **Token boundary / hold / export / head** (R3R §1.4): untouched — the score hop is inside the layer, the hold logic reads the proj marker.
- **Load state:** `--fs-*` initial 0 before the first layout; with no gate the V rows are laid out with uniform softmax during the first A2 only if the chain were
  unresolved, but the chain resolves in that same layout (fixed containers lay out after the stage in the OOF pass), so the first ctx snapshot already carries real data.
  Before the core opens (`.core-block`/`.loop-compute` locked) nothing is laid out, as today.

### 2.3 Expected frame sequence per layer

```
before (combined4):  [proj+S1 | qkv] [scores | ctx] [attn | fc]                            6 passes = 3.0 frames/layer, no parity shift
after  (R4S):        [proj+S1 | qkv+scores+softmax+V] [ctx | attn] [fc | proj+S1'] [qkv'… | ctx'] [attn' | fc']   5 passes = 2.5 frames/layer
```
5 is odd, so the pairing alternates between consecutive layers (as R2F's 7-pass period did, R3F §1) — every pass still pairs with a neighbour because the
two-passes-per-frame rule only caps the count (pass 2 of a frame is the re-run after a snapshot change, any hop can be it), and there is no latch boundary in the
loop (the 26 KV latches start in A2 while B1 runs, as before; the proj readback needs no latch since R3R). Per token: 1 (epoch → embedding layout) + 12 × 5 + 1
(hold/export) + 1 (head) = 63 hop passes → 32 frames + 3 SMIL handshake frames ≈ **35 frames/token vs 41 (combined4)**: −6 frames, −12 style passes, −97 timeline
animations per layer evaluation (−1,164 serviced animations/token), −1 scroller.

### 2.4 Precision (the only rounding-point change)

The carrier width expression is byte-identical to combined4's (`calc-size(max-content,calc(262144px + (size − base)·fqs·frks·k))` on the same glyph in the same
font at the same size), so the laid-out LayoutUnit widths are the same numbers — provided the max-content of a one-glyph `display:block` row equals that of the
old one-glyph `display:inline-flex` `.metric` (both come from the same inline min/max-content computation of the shaped run; the ids are the check). The transport
changes: today `--fs` = f(float timeline progress) ≈ 14–24 significant bits at a 2^18 px magnitude; now `--fs = (100cqw/1px − 262144)/128` with `100cqw` = the
container's LayoutUnit width converted exactly (2^18 px with 1/64 px steps = 24 bits, exact in float), i.e. the score is exact to 1/(64·128) ≈ 1.2e-4 — the old path's
LayoutUnit quantisation minus its float-progress rounding. Strictly better by bound, not bit-identical to combined4's scores; the softmax arithmetic after it is the
same double `exp()`/sum on the same element. Range: widths 262144 ± 128·|score| < 2^24 px for |score| < 2^17 (F3 precision window), far above GPT-2 scores.

## 3. Implementation (step 3) — `R4S/tools/r4s_small_hops.py`, hooks in two files (`bundles/R4S/BUILD.md` has the 319-line diff)

- `r4s_small_hops.py`: flag `R4S_SMALL_HOPS`; `carrier(head, slot, cls, glyph)` = `<i class="fvs-score-a fvs-score-H-S" style="anchor-name:--fsa-H-S">…</i>` (same class →
  same font/width rule as combined4); `stage(rows)` = `<div class="fvs-score-stage">` (`position:fixed;left:0;top:-60000px;width:1px;height:1px;overflow:clip;visibility:hidden`;
  rows `display:block;height:1px;overflow:clip;min-width:0;white-space:pre;font-style:normal`); `chain(pairs)` = 12·capacity/2 nested `<div class="fvs-sc" id="fvs-scK">`
  (`position:fixed;left:0;top:-300000px;container-type:size`, `#fvs-scK{width:anchor-size(--fsa-{2K} width);height:anchor-size(--fsa-{2K+1} width)}`, publisher rules
  `#fvs-scK{--fs-{2K−2}:calc((100cqw / 1px - 262144) / 128);--fs-{2K−1}:calc((100cqh / 1px - 262144) / 128)}` for K ≥ 1 and the same on `.fvs-score-reader` for the last pair;
  `.fvs-score-reader{display:block;width:1px;height:1px}`); asserts an even carrier count and ≤ 250 levels. Encoding constants 262144 / 128 = the existing score carrier's.
- `browser_gpt2_font_vector_cache.attention()`: with the flag, `--fs-H-S` are registered `inherits:true` (they must flow from the publishers to the bottom) and `--fsp-*`,
  `--fss`, `--fvs-score-ready` are not registered; per (head, slot) no `@keyframes`, no timeline/animation names, the carrier is the anchor row; `score_source` = the stage;
  `chain(...)` css appended; no scroller / reader-animation / stamp-keyframes / receipt / gate rules; body = stage + chain open + `<div class="fvs-score-reader"><div class="fvs-softmax">`
  + V rows + `</div></div>` + chain close; the `html{timeline-scope}` rule for the score names is not emitted; `prewarm_values` with the flag raises (no score gate to prewarm against);
  manifest gains `r4sSmallHops`, `r4sScoreChainContainers`, `r4sScoreAnchors`. The softmax, `--fv-S`, `--fw-H-S`, V-row and bank code paths are untouched.
- `browser_gpt2_reused_adapter.py`: F5's receipt list drops `.fvs-score-receipt` (so the `--native-pass` stamps and the `--epoch:var(--native-pass)` rule no longer name it);
  the inline `var(--epoch)` reader assertion becomes 6 (the score stamp marker was one of the 7); manifest `r4sSmallHops`.
- Untouched: qkv/attn/fc/proj matvecs, R3R fold, KV banks, R2C/R2D/R2F/R2G/R3H, head, token handshake. Flag off = R3M's code path (byte-identical output, §4).

## 4. Offline verification (step 3, `R4S/offline_check.py <bundle> <ref> [capacity]`)

| build | reference | result |
|---|---|---|
| `scratch/off-2L` (R4S tools, flag off, 2 blocks / 2 positions) | `scratch/r3m-2L` (R3M tools, same command, same directory depth) | **index.html and runtime.css byte-identical**; manifest differs only by `r4sSmallHops` |
| `bundles/smoke-R4S-2L` (flag on) vs `bundles/smoke-R4S-2L-ref` (flag off) | rule diff by category | `RESULT: PASS` (`R4S/logs/offline_check-smoke.log`): +24/−24 `--fs` registrations (true/false), −26 progress/stamp/ready registrations, −50 (= 2 × 25) score keyframes, −scroller/−reader anims/−receipt/−gate, +4 structure, +12 container-size rules with the exact (h,s) → (2k, 2k+1) mapping, +12 publishers with the exact k+1 → k mapping, html scope −25 names, pass-reader/epoch lists −`.fvs-score-receipt`, `.head-isolation` reset −`--fsp/--fss/--ready` only; all 24 `.fvs-score-H-S` rules and the softmax rule byte-identical; 24 anchors, 12 containers, stage and anchors precede `#fvs-sc0`, reader inside `#fvs-sc11`; elements 62,236 vs 62,228 (+8), depth 51 → 51 (reader 31 → 43); witnesses 73/73 identical |
| `bundles/R4S` (12 layers, capacity 8) vs `bundles/combined4` | same checker | same categories at 96/98/194/48/47 (`R4S/logs/offline_check-R4S.log`); elements 67,445 vs 67,401 (+44), max depth 94 (reader 89; cap 512); containing-block lint over the 40 ancestors of `#fvs-sc0`: none has `contain`/`transform`/`filter`/`will-change`/`perspective`/`position:absolute|relative|sticky` (gates: `content-visibility` only); 283/283 witnesses identical modulo the tools-dir key prefix (the checker's raw compare flags the prefix; `R4S.log.md` 23:41) |
| NumPy reference ids (`R4S/reference_ids.py`, R4S tools) | expected | `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected (the arithmetic is unchanged; the reference does not model either transport) |
| `launch_browser_gpt2.py --check` on `bundles/R4S` | — | 285 static files / 285,475,147 B / no JavaScript |

Sizes: runtime.css 38,953,655 chars (combined4 38,973,628), index.html 5,604,468 (5,603,748).

## 5. 2-layer smoke (step 3) — `bundles/smoke-R4S-2L`, one light-traced run under the lock

`R4S/run_chrome.sh smoke-2L 420 smoke_inner.sh smoke-R4S-2L smoke-R4S-2L` (R2F's `run_bundle.mjs`, light trace, 2 s poll, heap flag), 23:53:02–23:53:43, AC, load ≈ 10 (lock held by
R4C's 32-token run for 789 s before). `R4S/runs/smoke-R4S-2L/{harness.log,frames.md,trace.json.gz,pipeline-results.json}`.

- **ids `[11, 3387]` = the 2-layer reference** (F3b/R2F/R3F/R3R smokes), done markers 2/2; 62,236 elements, 73 fonts. Whole-session counters idle → end: RecalcStyleCount +102,
  LayoutCount +28 (R3R's smoke on the same harness: 74 / 41 whole session, i.e. its token windows 44 + 7 recalcs, 30 + 2 layouts; here 89 + 13 and 24 + 4 — the interleaved container
  recalcs are counted by RecalcStyleCount, F3b §2b, so layouts and the traced passes are the comparable numbers).
- Per-frame table (`R4S/frames.py`), token 2 = frames 15–21 (`0:` = the hover-forced 0-element pass):

| frame | passes (elementCount:ms) | layouts (dirty:ms) | anim b/e | what |
|---:|---|---|---|---|
| 15 | `833:78 2343:113` | 1570, 6945 | 3/0 | epoch/feedback → embedding readback → S1 of layer 0 |
| **16** | `0 40:67 780:42` | **99:76**, 2344 | 26/0 | **qkv readback → KV write (26 latches) → score rows laid out → chain → softmax → V rows, all inside the 99-object Layout (the 2,311-element V-row restyle is now interleaved in layout, not a pass) ; ctx readback → attn fonts as the frame's second pass.** R3R had `44:59 2311:28` here and `780` in the next frame |
| 17 | `0 3089:120 782:134` | 9266, 2357 | 0/0 | attn readback → `--r` → LN2 → fc fonts ; fc readback → `--hidden` → proj carriers |
| 18 | `0 2324:76 40:85` | 6943, 99 | 26/0 | proj readback → `--pass` 2 → S1 of layer 1 ; qkv(L1) + scores + softmax + V rows |
| 19 | `0 780:29 3089:130` | 2344, 9266 | 0/0 | ctx ; attn (layer 1) |
| 20 | `0 782:114 780:28` | 2357, 792 | 0/0 | fc ; proj readback → `--held:1` → export laid out (792) |
| 21 | `0 50888:384 6:11` | 101162 | 1/2 | bridge readback → head (unchanged) |
| 22–25 | `1`, `20`, `1`, `20` | –, 11, –, – | | the token SMIL handshake (unchanged) |

**10 layer passes in 5 frames = 2.5 frames/layer (R3R/combined4 smoke: 12 passes in 6 frames = 3.0)**, sequence `[qkv+scores | ctx] [attn | fc] [proj+S1 | qkv'+scores'] [ctx' | attn'] [fc' | hold]`
— the odd period alternates the pairing between layers exactly as §2.3 predicted; no idle second slot, no extra pass anywhere. Token 2 has 13 style passes (R3R 15: −1 per layer =
the score readback pass) and 13 layouts (R3R 15). The qkv pass grew from `44:59` + Layout 113 to `40:67` + Layout `99:76` (the score rows + chain + interleaved V-row restyle
now sit inside Layout) while the separate `2311:28` pass and its Layout (3,878 objects) disappeared — main-thread cost per layer is at worst flat, minus one pass's fixed overhead and half a frame.
For 12 layers: 1 + 12 × 5 + 1 + 1 = 63 hop passes → 32 frames + 3 SMIL ≈ **35 frames/token vs 41 (combined4)**.
- Token 1 (frames 4–11): `2363 41`, `780`, `3089`, `782`, `2324 40`, `780 3089`, `782 780`, head — the first layer pays the 1.9 s font-instantiation pass and its hops fall into
  separate frames (as in R3R's smoke); the second layer already shows the 5-pass pairing.

## 6. 12-layer correctness run (step 3) — `bundles/R4S`, ONE passive run (not a timing run)

ONE passive run (NOT a timing run), `R4S/run_correctness.sh R4S` (R3M's watchdog harness with R4S paths: owner-marked lock, toucher killed before a marker-checked release; F4's
`correctness_run.mjs`: headless Chrome 153, `--js-flags=--heap-growing-percent=10`, poll `#token-8-captured.done` every 5 s, one readback), 2026-09-21 00:02:47–00:05:29 under `CHROME.lock`
(waited 513 s behind R4T's fixture), AC, load { 4.07 5.35 7.27 }. Results in `work/2026-09-19/R4S/run-R4S/{harness.log,verify.log,verification-vectors.json,pipeline-results.json}`.

- ids **[11, 314, 1101, 7926, 11, 475, 314, 1101]** (= required), done markers 8/8; `verify_browser_gpt2_runtime.py` rc=0: tokenAgreement 8 × True, originalFloatAgreement 8 × True,
  finalHeadMatchesActualInput True, text "Hello, I'm sorry, but I'm"; `finalResidualError` rmse **0.017219** / max **0.16788** (combined4: 0.017645 / 0.13388) — different, as §2.4 predicts
  (the scores now round at the LayoutUnit instead of the timeline's float progress), same 1e-2 error class, ids identical.
- Whole-run counters (Performance.getMetrics at the end, same harness): **LayoutCount 535** (combined4 629: −94 ≈ 8 tokens × 12 removed score-readback layouts), RecalcStyleCount 3,759
  (combined4 985) — with a size-container chain the counter also counts the interleaved container recalcs (≈ 29 per layer evaluation here; F3b §2b), so it is no longer a pass count;
  the traced smoke (§5) is the exact pass accounting. Nodes 132,214 (combined4 132,170).
- Per-token capture times (5 s poll granularity, indicative only): 23.4, 11.9, 17.1, 18.7, 17.6, 18.6, 19.8, 19.2 s (sum 146.3 s; combined4's correctness run on a similar load class:
  22.0, 17.1, 17.2, 18.0, 24.2, 17.8, 24.7, 17.6 = 158.6 s). B5's paired protocol decides the s/token.
- `bundles/R4S/READY` created 2026-09-21 00:06.


## 7. Prediction and residual risks

- **Predicted s/token ≈ 17.3–17.5 (combined4 18.2 paired, B4):** −6 frames/token × ≈117 ms ≈ −0.70 s; −12 score-readback passes (each carried the hover 0-pass + snapshot
  bookkeeping, the 2,311-element restyle itself moved into the qkv pass's Layout) ≈ −0.1 s; −97 timeline animations per layer evaluation × 40 µs × 12 ≈ −0.05 s; +48 interleaved
  container recalcs × 12 ≈ +0.02 s (F3b's 340 µs per container is an upper bound: these publish 2 numbers each, no `--gelu()`). Net ≈ **−0.8 ± 0.2 s/token**. Only B5's paired bench
  vs combined4 is meaningful.
- **What was moved and what cannot be:** the score hop is the only per-layer hop ≤ 500 values (§1). The next fold at the same place is the **ctx hop** (768 V-row widths → `--ctx-*`),
  which would make the layer `[proj+S1 | qkv+scores+ctx+attn fonts] [attn | fc]` = **4 passes = 2.0 frames/layer** (−6 more frames ≈ −0.7 s): the V rows are already anchors-in-waiting
  (in-flow rows inside a fixed stage — they are `.metric` carriers in a scroller today), the consumer needs all 768 numbers on ONE element (`.shared-attn`'s 768-axis
  `font-variation-settings`), so one chain of 384 one-element levels (F3b's out-chain shape, validated at 391 deep) hanging off the score chain's bottom, hosting the attn stage
  and everything below it (LN2, fc, proj, reused-output, export probes: the deepest path is 51 − 29 = 22 levels below the mix). Depth: 89 (reader) + 1 + 384 + 22 ≈ **496 of the 512
  parser cap** — feasible only if the 12 nested `.fvs-bank-L` wrappers (F5 fix 5 #2, never done) are flattened first (−11 levels → ≈ 485) or the chain packs more than two values per
  level; not attempted here (768 values, outside the small-hop brief; needs a depth budget and its own smoke).
- **Chromium behaviours relied on (all already load-bearing in F3a/combined2 and combined4):** anchors in an earlier fixed OOF root are acceptable to later fixed containers whose
  containing block is the viewport (F3 §3b — the ancestor lint in `offline_check.py` guards the containing block: any future `contain`/`transform`/`filter`/`will-change`/
  `position` on one of the 40 ancestors of `#fvs-sc0` silently zeroes the scores → build-time FAIL); size-container subtrees are restyled at their container's layout
  (F3 §2, F3b); `content-visibility:hidden` gates block child restyle/layout in the pass they close (R3R). New here: a one-glyph `display:block` row's max-content equals the old
  inline-flex `.metric`'s (same shaped-run width; the 2/2 ids and the 12-layer run are the check).
- **Precision:** scores are now exact to the carrier's LayoutUnit (1/64 px → 1.2e-4); the timeline's float-progress rounding is gone. Not bit-identical to combined4's scores,
  strictly no coarser; expect `finalResidualError` to move at the 1e-3 level (§6 has the number). The NumPy witness path does not model either transport.
- **Memory:** +48 `position:fixed` containers with 262144-px sizes (F3 §2b: ≈ 35 KB each ≈ +1.7 MB) and +1 fixed stage, −1 scroller (PaintLayerScrollableArea); B5's RSS column decides,
  expected within noise.
- **Not measured here:** s/token; the 12-layer per-frame count (derived from the smoke's exact 5-pass period); the interleaved recalc cost at capacity 8 (the smoke ran capacity 2:
  12 containers, 768 × 3 V glyph elements; at capacity 8 the chain is 48 deep and the V-row subtree 768 × 9 elements — same shape as combined4's B1 pass).
