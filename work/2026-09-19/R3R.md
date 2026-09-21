# R3R — one geometry→number hop less per layer: the loop-transport hop folds into the proj readback

Agent R3R, 2026-09-20. Tools copy `work/2026-09-19/R3R/tools` (= R2H's combined3 emitter + `r3r_fold_hop.py`, flag `R3R_FOLD_HOP` default ON;
`R3R_FOLD_HOP=0` reproduces R2H's output byte-for-byte — checked on the 2-layer build against `bundles/smoke-R3F-2L-ref`, which is R2H's tools).
Bundles: `bundles/smoke-R3R-2L` / `smoke-R3R-2L-ref` (2 blocks, 2 positions, flag on/off), `bundles/R3R` (12 layers, §5). Scratch/harness/logs:
`work/2026-09-19/R3R/`, `R3R.log.md`. Nothing under the repo's `tools/` or `experiments/` was modified; no commits.

## 0. Headline

**Candidate (c) is the one that removes a hop, and it needs no latch at all.** The seventh hop of a layer (proj carriers → `--out = r + proj` on
`.shared-proj-c0/c1`) is followed by a hop that does no arithmetic: `--out` → 769 loop-bank carriers → `.loop-reader` → `--x` exists only to carry 768
numbers *upward* (depth 47 → 13) and to hold them for a layer (two banks, 769 transitions per layer). With the fold the proj carriers publish
`262144px + 128·out_i` themselves (`calc-size(max-content, …)` with the residual `r_i`, the bias and the dynamic range folded into two per-layer
constants declared on `.shared-proj`), the proj timelines are scoped on `html`, and the existing `.loop-reader` / `.core-pass-reader` read them
directly. The hold that the two-bank latch provided is already provided by the stage gates (§1.3): the proj stage is restyled and laid out exactly
once per pass, in the fc-readback pass, so `--x` cannot move mid-layer. Per layer: 7 → 6 hops, 3.5 → 3 frames (§4: 12 layer passes in 6 frames on
the smoke, vs 7 frames), no bank carriers (−1,538 elements), no `--saved-*` transitions (−9,228 starts/token), no proj number consumers (−768
animations/layer). Candidates (a) and (b) cannot remove a hop (§1.2). The transport is not bit-identical to the old one (§1.5: same LayoutUnit/float
precision class, different rounding points); ids are the check — 2/2 on the smoke, §5 for 12 layers.

## 1. Per-layer dependency graph (step 1)

Emitter: `R2H/tools` (line numbers below are R2H's). Numbers = registered `<number>` custom properties resolved in style; geometry = a laid-out width
read back through a `view-timeline` + animation (one "hop" = one layout + one snapshot-driven style pass). "Pass" = `UpdateStyleAndLayout`; Blink runs at
most two per frame (R2A §5, R3F §0).

### 1.1 The seven hops of pass P (layer L = (P−1) mod 12) in combined3

| # | hop (pass name in R3F §1) | geometry (carriers, where laid out) | number consumer (element, decl) | what the numbers feed | emitter |
|---|---|---|---|---|---|
| 1 | loop transport + S1 (D′ pass 2) | 769 `.loop-metric` of the *read* bank, `width:calc(262144px + var(--saved-r-i)*128px)`, laid out when the proj gate opened in the previous D′ pass 1 | `.loop-reader` 1,538 anims → `--lp-b-i` (private) → `.loop-input{--loop-in-i:decode(--lp-r-i)}` → `.reused-input{--x-i}`; `.core-pass-reader` reads both markers → `--pass = min(max(markers)+1, cap)` | LN1 (`.shared-ln1`) → 768-axis qkv list → 2,305 qkv carriers | `probe_native_reused_loop.py:36-68`, `r2f_lean_handshake.py:98-113`, `reused_core.py:282-286` |
| 2 | qkv (A′ pass 2) | 2,304 glyph carriers + marker, laid out in S1 | `.shared-qkv-c0..c4` → `--qkv-i`; receipt → `--gate-qkv` | KV write (26 `--fc-*` latches), 96 score fonts | `build_hybrid_twelve_block.py:192-215, 243-274` |
| 3 | scores (B′ pass 1) | 97 score carriers | `.fvs-score-reader` → softmax | 96 V fonts, 768 row widths | `font_vector_cache.py` |
| 4 | ctx (B′ pass 2) | 768 V rows (+ bridge stamp) | `.cache-bridge-c0/c1` → `--ctx-i`; bridge receipt gate | 768-axis attn list → 769 attn carriers | `reused_core.py:193-203`, `hybrid.bridge` |
| 5 | attn (C′ pass 1) | 769 attn carriers | `.shared-attn-c0/c1` → **`--r-i = var(--x-i) + decode`** (`:263`) ; receipt → `--gate-attn` | LN2 → 3,072-axis fc list → 3,073 fc carriers | `matvec` |
| 6 | fc (C′ pass 2) | 3,073 fc carriers | `.shared-fc-c0..c5` → GELU → `--hidden-j`; receipt → `--gate-fc` | `--range-proj = max|hidden|·1.001` (`:135`), proj list `--fq-proj-j = hidden_j/range` (R2C) → 769 proj carriers shaped | `matvec` |
| 7 | proj (D′ pass 1) | 769 proj carriers: 12 glyphs per carrier, `width:max-content` (`.metric`), marker `131072/65536px + epoch·1024px` | `.shared-proj-c0/c1` → **`--out-i = var(--r-i) + ((w·1000/512 − base_i)·s_i·range + b_i)`** (`:249-251, 265`); receipt → `--gate-proj` opens → banks restyled: write bank `--saved-b-i:var(--loop-out-i)` (`:57-59`), read bank latched (769 transitions) | 769 loop-bank carriers laid out → hop 1 of P+1 | `matvec`, `reused_core.py:287-297`, `loop_parts` |

Gate cascade inside pass P (all gates are `content-visibility:hidden` unless the stage receipt's stamp equals `--epoch` = `--native-pass`; the receipt of
stage s sits *below* the gate of stage s−1): S1 restamps `--native-pass:P` on the 14 pass readers (`adapter.py:145-152`); the qkv receipt is not under any
gate → `--gate-qkv:0` → the qkv gate closes in S1 and everything below is display-locked (children are not restyled or laid out; view-timelines of
locked carriers keep their last snapshot — this is what holds the read bank today). Each further receipt is first restyled in P when its parent gate
opens, sees stamp P−1 ≠ P and closes its own gate in that same pass: cache-bridge gate closes at hop 2, attn gate at hop 4, **fc gate at hop 5, proj gate at
hop 6**; each opens one hop later when its marker (laid out with the stage's glyphs) reads P. Consequence used below: **the proj stage
(`.shared-proj`, its carriers, its marker) is restyled and laid out exactly once per pass, in hop 6's pass (C′ pass 2), with the final `--r` (final since
hop 5) and the final `--hidden`/`--range-proj` (computed in that pass).** The garbage `--r = x_P + attn_{P−1}` that hop 4's pass computes never reaches it
(attn gate closed in that pass).

### 1.2 Candidates

- **(a) skip the attn hop / feed fc from attention directly.** LN2 needs Σr and Σr² over 768 *numbers* and `--r-i = x_i + attn_i` needs `attn_i` as a
  number; `attn_i` is a glyph advance. A `font-variation-settings` axis value is a number in style — geometry can enter it only through a readback. No
  hop removable. Adding x as font axes (identity columns) is capped at 256 axes per font and quantised to 1 font unit (`roundf` of the HVAR delta) ≈
  0.5·s_i·range ≈ 1e-2 per element — not exact either.
- **(b) fuse ctx and attn.** Same objection: the attn font axes are `--ctx-i/range` numbers; the V-row widths are geometry. F4's `*`-list route moves
  *numbers* into untyped strings (bank K/V lists), it does not read geometry. No hop removable.
- **(c) fuse proj and loop.** Hop 7 → hop 1 is number → geometry → number with no arithmetic in between except the residual add `r_i +` and the latch.
  Both can move into the proj carriers: `r_i`, `b_i`, `base_i`, `s_i`, `--range-proj` are all available as numbers *on `.shared-proj`* (`--r-*` is
  `inherits:true` from `.shared-attn-c*`, an ancestor; `--range-proj` is declared on `.shared-proj` itself), and a carrier's width may be an affine
  function of its own max-content size (`calc-size(max-content, size·k + c)`, already used by the head rows). So carrier i can be laid out with
  `width = 262144px + 128·(r_i + b_i − base_i·s_i·range) px + size·(128·s_i·range·1000/512)` = `262144 + 128·out_i` px — the loop bank's exact
  encoding — and the top-level readers decode it with the loop bank's exact formula. **Removes hop 1 (the transport) if and only if `--x` can be kept
  stable without the two-bank latch — §1.3.**

### 1.3 Proof that no consumer reads a value before it is final (fold on)

Let the proj carriers be read by `.loop-reader` (768 anims, `--lp-i`) and the proj marker by `.core-pass-reader` (`--pr-stamp`), both html-scoped.
Define pass P's passes as S1, A2 (qkv), B1 (scores), B2 (ctx), C1 (attn), C2 (fc). Claim: (i) the proj carriers' geometry changes exactly once per
pass, in C2's layout, to `262144 + 128·out_P`; (ii) the readers see that change in the pass after C2, call it D1, and in no other pass; (iii) in D1
`--pass` becomes P+1 and S1 of P+1 runs on `--x = out_P`, so D1 ≡ S1(P+1) and the layer has 6 passes; (iv) nothing reads a stale or partial value.

(i) By §1.1's cascade the proj stage is under the fc gate, which is closed from C1 (restyled when the attn gate opened, stamp P−1) until C2 (stamp P), and
under the attn/bridge/qkv gates before that. Blink blocks child style recalc and layout of a `content-visibility:hidden` subtree in the same pass in which
the lock is acquired (evidence: the S1 pass restyles 2,323 elements although `--x` changed and would dirty the whole open core). So between S1 and C1 no
restyle/layout of the proj stage happens; in C2 the fc gate opens, `.shared-proj` is restyled with `--hidden` (new, from the fc consumers in this pass),
`--range-proj`, `--fq-proj-*`, `--pk-*`, `--pc-*` (from `--r`, final since C1) and the carriers are shaped and laid out once. Their widths are
`262144 + 128·out_P` by construction of `--pk/--pc` (arithmetic in §1.2 c). The marker is laid out in the same layout with `--epoch = P`.

(ii) View-timeline snapshots are taken after layout; a changed snapshot triggers the next style pass (within the frame if it is the first re-run, else
the next frame's first pass). C2's layout changes the proj carriers' snapshot → D1 is the next pass, in which `.loop-reader`'s 768 anims and
`.core-pass-reader`'s anim take their new values. Between D1 of P and C2 of P+1 the proj stage is locked (S1 of P+1 closes the qkv gate in D1 itself,
see iii) so its geometry and therefore `--lp-*`, `--pr-stamp` do not change again — the same mechanism that holds today's read bank under the closed proj
gate for a whole layer.

(iii) In D1: `--pr-stamp` decodes to P (exact: integer ×1024 px, `round(nearest, …, 1)`; same expression as the proj receipt's gate test with the
folded viewport), `--pass = min(P+1, cap)`; unless capped (§1.4), `--pass = P+1` → `--native-pass:P+1` stamps → the qkv receipt (never under a gate) closes
the qkv gate in this pass → the proj stage is locked with out_P. `--loop-in-i = decode(--lp-i) = out_P` (→ `--x`), `--loop-ready:1`, LN1 and the qkv list
are recomputed and the qkv carriers laid out in D1's layout: D1 = S1(P+1). A2(P+1) follows as the frame's second pass. Per layer the passes are therefore
`[D1=S1 | A2] [B1 | B2] [C1 | C2]` = 6 passes = 3 frames, and since 6 is even the pairing does not shift between layers.

(iv) Readers of `--loop-in`/`--x`: everything under `.loop-compute`; they see out_P only from D1 = S1(P+1) on, which is exactly when layer P+1 must start,
and see nothing else until D1 of P+1. Readers of the marker: `--pass`; it advances exactly when the carriers become readable (same layout, same
snapshot, same pass) — the R2F invariant ("the marker is declared/laid out/snapshotted with the data") holds with the marker *being the stage's own
generation marker*. Partial values: in the only pass where the proj stage is restyled (C2) all its inputs are final (`--r` final since C1, `--hidden`
final in C2 — the fc consumers are ancestors of the fc gate and are resolved before it in the same recalc). The old B2-pass garbage `--r` never reaches
`.shared-proj` (attn gate closed in B2). The remaining hops (2–6) are untouched.

### 1.4 Token boundary (the only place the two-bank latch did real work)

With `--pass` capped at 12k while the head runs, D1 of pass 12k would set `--loop-in = out_{12k}` while `--layer` stays 11 → layer 11 would recompute on
its own output and the layer-11 export (769 b11-bridge carriers reading `--out-*` under the proj gate) would move → the head would re-read garbage. Today
`--x` stays `out_{12k−1}` because it comes from the *other* bank. Fold: `--held = clamp(0, marker − cap + 1, 1)` on the controller (1 exactly when the
layer-11 output is readable and the cap holds), `@container loopcontrol style(--held:1){.loop-input{--loop-ready:0}}` display-locks `.loop-compute` in
D1 of 12k (same pass as the jump of `--loop-in` → its subtree is not restyled; on unlock at layer 0 it is restyled with `--loop-in:var(--input-*)`, the
embedding, as today), and the export moves out of the locked subtree: `.reused-final-export` becomes a child of `.loop-input` (sibling before
`.loop-compute`), its carriers read `--loop-in-*` (= out_{12k} in D1), its marker keeps `var(--position)`, and it is `display:none` unless `--held:1`
(it used to be `display:none` unless `--layer:11` and locked under the proj gate until D′ pass 1 — same visibility window). The head side
(`.b11-bridge-c0/c1`, `--bridge-ready`, head-input latch) is untouched: it sees the export carriers laid out in D1 and reads them in D2, as before.
When `#token-k-advanced.done` raises the cap: `--pass → 12k+1`, `--held → 0`, export hidden, layer-0 rule gives `--loop-ready:var(--embed-ready)` and
`--loop-in:var(--input-*)` exactly as today. Load state: `--pr-stamp` is registered with `initial-value:0.4` = the centered progress of a marker laid out
with pass 0 (`vp/(vp+vp/4) = 0.8 → 3·0.8−2`), so an inactive timeline (proj stage never laid out) decodes to 0 → `--pass:1`, `--held:0`, as the bank
markers' initial 0 did.

### 1.5 Precision

Today: `out_i` is computed in double on the consumer (`r + (w·1000/512 − base)·s·range + b`, w = LayoutUnit width of the glyph run), then
`calc(262144px + out·128px)` → `Length` float (ULP 1/32 px at 2^18) → LayoutUnit (1/64 px) → readback: `--x` carries `out` quantised to ≈2.4e-4.
Fold: `calc-size(…)` is evaluated at layout in float: `262144 + float(128·(r+b−base·s·range)) + float(size)·float(250·s·range)` — the glyph term is now a
float product (ULP 1/32 px at its ≈2.8e5 px magnitude) instead of a double product; then the same Length/LayoutUnit path. Both transports quantise
`out` at the 1e-4 level; the fold has one more float rounding of the same size, no coarser step, and it removes nothing the old path had. The value
is therefore **not bit-identical to combined3's** (a different rounding point in a 1e-4 transport) and strictly not a "zero precision change"; it is
precision-neutral by bound. The NumPy witness path does not model either transport (it compares tokens and float agreement with tolerance), so the
check is the ids (2/2 smoke, §4; 8/8 12-layer, §5) plus `finalResidualError` staying at the 0.02 rmse level. Folding `r` at the *glyph* scale
(padding, or identity font axes) was rejected: 1/64 px = 0.03 font units·s·range ≈ 7e-4 per element, coarser than today.

## 2. Implementation (step 2) — `R3R/tools/r3r_fold_hop.py`, hooks in three files (`bundles/R3R/BUILD.md` has the full diff)

- `build_hybrid_twelve_block.matvec(..., fold=)` (proj only): viewport pinned to 524288 (track 1572864, marker base 131072 — the loop bank's numbers, so
  |out| < 2048 is representable exactly as before; the receipt/gate formula follows the viewport); carrier inline style gains
  `width:calc-size(max-content,262144px + var(--pc-i) * 1px + size * var(--pk-i))` (layer independent — `specialize()` requires identical HTML per layer);
  per layer `.shared-proj{--pk-i:calc(var(--range-proj) * 250·s_i);--pc-i:calc((var(--r-i) + (b_i) - base_i * s_i * var(--range-proj)) * 128)}` inside the
  layer's `@container corestate style(--layer:L)` block (1,536 `<number>` `inherits:true` registrations, once); the timeline names go to
  `html{timeline-scope}` (lifted out of the layer block by `specialize()`, merged by the existing html-scope merges); the `.shared-proj-c0/c1` consumers
  are not emitted (no `--out-*`).
- `r3r.loop_parts(width, blocks, capacity)` replaces `probe_native_reused_loop.loop_parts`: controller
  `--pass:min(calc(round(decode(--pr-stamp)) + 1),var(--pass-cap))`, `--held`, `--pass-cap` token rules (R2F's), `.core-pass-reader{animation:prstamp on
  --shared-proj-generation}`, `.loop-reader{768 lpk anims on --shared-proj-t*}`, `.loop-input{--loop-in-i:calc((1572864 / (var(--lp-i) + 2) - 524288 -
  262144) / 128) … --loop-ready:1}`, `style(--held:1)` lock rule, `.loop-compute` gate as before. No banks, no `--saved-*`, no SMIL, no `--loop-phase`.
- `browser_gpt2_reused_core.py`: uses the module's loop parts; scoped-state privates = the 768 `--lp-i` (F5 forward to `.loop-input` kept), no bank
  forwards; `specialize()` lifts `html{timeline-scope}`; the `.reused-output{--loop-out-*}` rule is dropped.
- `browser_gpt2_reused_adapter.py`: skips `r2f.apply_css/apply_body` (the lean controller is emitted directly), keeps the `.core-pass-reader` wrapper,
  moves the export (`r3r.move_export`: `--out-NNN` → `--loop-in-N`, inserted after `svg.loop-signals`, `display:block` only under `style(--held:1)`),
  drops `.loop-bank-0/1` from the pass readers, manifest key `r3rFoldHop`.
- Everything else (KV banks, attention, qkv/attn/fc stages, head, token handshake, R2C/R2D/F4/F5 knobs) is byte-identical in the flag-off build.

## 3. Offline verification (2-layer build, flag on vs off)

`bundles/smoke-R3R-2L` vs `smoke-R3R-2L-ref` (R3R_FOLD_HOP=0; the latter is byte-identical to `bundles/smoke-R3F-2L-ref` = R2H tools): 73/73 font
witnesses identical, same 73 `url()` fonts; no `.loop-bank`, `--saved-b-*`, `loop-k-*`, `.loop-metric`, `--loop-phase`, `.shared-proj-c0`; `.loop-reader`
768 anims on `--shared-proj-t0..767` (`animation-range:cover`); `.loop-input` decode = the old bank decode with `--lp-i`; `.core-controller{--pass:…}` as in
§2; two `style(--held:1)` rules; `@property --pr-stamp … initial-value:0.4`; `--pk-000/--pc-000` rules once per layer inside `style(--layer:L)`; proj
scroller 524288 / marker base 131072 in both layers; the final `html{timeline-scope}` rule contains `--shared-proj-t0..767` and `--shared-proj-generation`;
carriers `width:calc-size(max-content,262144px + var(--pc-000) * 1px + size * var(--pk-000))`; `.loop-input > svg.loop-signals + .reused-final-export(--loop-in-*) +
.loop-compute`; F5's inline-reader counts (7 epoch / 2 position) unchanged (build asserts). Elements 124,445 vs 126,0xx (−1,538 bank carriers − 4 consumers);
runtime.css 14.60 vs 15.17 MB.

## 4. 2-layer smoke (step 3) — `bundles/smoke-R3R-2L`, one light-traced run under the lock

`R3R/run_chrome.sh smoke-2L 420 smoke_inner.sh smoke-R3R-2L smoke-R3R-2L` (R2F's `run_bundle.mjs`, light trace, 2 s poll, heap flag), 21:50:59–21:51:34, AC,
load ≈ 9 (lock free, waited 0 s). `R3R/runs/smoke-R3R-2L/{harness.log,frames.md,trace.json.gz,pipeline-results.json}`.

- **ids `[11, 3387]` = the 2-layer reference** (F3b/R2F/R3F smokes), done markers 2/2. RecalcStyleCount 74 / LayoutCount 41 for the whole session
  (R3F smoke: 47 + 14 = 61 recalcs, 29 + 5 = 34 layouts in its two token windows — here the windows are 44 + 7 = 51 recalcs, 30 + 2 = 32 layouts; the light
  trace below is the exact accounting).
- Per-frame table (`R3R/frames.py`), token 2 = frames 13–24 (`0:` = the hover-forced 0-element pass):

| frame | passes (elementCount:ms) | layouts (dirty) | anim b/e | what |
|---:|---|---|---|---|
| 13 | `833:58 2343:107` | 1570, 6945 | 3/0 | feedback readback → embedding readback → S1 of layer 0 |
| 14 | `0 44:59 2311:28` | 113, 3878 | 26/0 | qkv readback → KV write (26 latches) → score fonts ; scores readback → softmax → V rows |
| 15 | `0 780:25 3089:119` | 2344, 9266 | 0/0 | ctx readback → attn fonts ; attn readback → `--r` → LN2 → fc fonts |
| **16** | `0 782:109 2324:73` | 2357, **6943** | **0/0** | fc readback → `--hidden`, proj fonts+carriers laid out (2357) ; **proj readback at the top → `--pass` 2 → S1 of layer 1 in the same pass (6943 = the qkv carriers of layer 1)**. No bank pass (`1553`, 769 latch starts/cancels) and no loop-readback pass (`2334`) any more |
| 17 | `0 44:63 2311:30` | 113, 3878 | 26/0 | qkv ; scores (layer 1) |
| 18 | `0 780:26 3089:118` | 2344, 9266 | 0/0 | ctx ; attn |
| 19 | `0 782:101 780:26` | 2357, 792 | 0/0 | fc ; proj readback → `--held:1` (cap 4 reached) → `.loop-compute` locked, export shown and laid out (792 = the 769 bridge carriers + probes) |
| 20 | `0 50888:411 6:17` | 101162 | 1/2 | bridge readback → `--bridge-ready` → head pass (unchanged) |
| 21–24 | `1`, `20`, `1`, `20` | –, 11, –, – | | the head's token SMIL handshake (unchanged, out of scope) |

**12 layer passes in 6 frames = 3.0 frames/layer (R3F/R2F smoke: 14 passes in 7 frames = 3.5)**; per layer the sequence is `[proj+S1 | qkv] [scores | ctx]
[attn | fc]` with no parity shift (6 passes are even). Token 2 has 15 style passes instead of R3F's 16: the removed pass is the loop readback/bank pass of
the layer boundary (layer 0 → 1); the layer-11 boundary keeps one pass (`780`: the hold + export layout) because the head bridge is still a hop, so the 2-layer
token saves one pass but no frame (parity: R3F paired the export pass with the head, `2326|50892`). For 12 layers the token is 1 (feedback) + 12 × 6 + 1
(hold/export) + 1 (head) = 75 hop passes → 38 frames + 3 SMIL frames ≈ **41 frames/token vs 46 (R3F)**: −11 layer-boundary passes, −6 frames, −9,228
`--saved-*` transition starts/cancels (the 769 b/e pairs of the old frame 18 are gone: 0/0 in frame 16), −768 proj-consumer animations per layer.
- Token 1 (first token, frames 2–9): `2363|45`, `3|2311`, `780|3089`, `782`, `2324|44`, `0|2311|780`, `0|3089|782`, `0|780|50888` — same 6-pass layers;
  the fold pass fell into its own frame once (frame 5→6: the first layer pays the 1.5 s font-instantiation pass) and the hold pass paired with the head.

## 5. 12-layer correctness run (step 4) — `bundles/R3R`, ONE passive run (not a timing run)

`R3R/run_chrome.sh correctness-12L 900 correctness_inner.sh R3R` (F4's `correctness_run.mjs`: headless Chrome 153, `--js-flags=--heap-growing-percent=10`,
poll `#token-8-captured.done` every 5 s, one readback; lock protocol with 30 s touch + watchdog), 21:56:04–21:58:56, AC, load ≈ 3–4 (lock free, waited 0 s).
Results in `R3R/run-R3R/{harness.log,verify.log,verification-vectors.json,pipeline-results.json}`.

- **ids `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = required, done markers 8/8**; `verify_browser_gpt2_runtime.py` rc=0: tokenAgreement 8 × True,
  originalFloatAgreement 8 × True, text "Hello, I'm sorry, but I'm", finalHeadMatchesActualInput True. `finalResidualError` rmse **0.017645** / max **0.13388**
  (combined3/R3F: 0.020059 / 0.18732) — different, as §1.5 predicts (the transport rounds at different points; here slightly closer to the float reference),
  so the R3R numbers are NOT bit-identical to combined3's but at least as accurate.
- Whole-run counters (Performance.getMetrics at the end, same harness): **RecalcStyleCount 982, LayoutCount 625** (R3F 1116 / 720, combined3 1107 / 710):
  −134 recalcs ≈ 8 tokens × (12 loop-bank passes + hover 0-passes of the removed frames) and −95 layouts ≈ 8 × 12 bank layouts, in line with §4.
- Per-token capture times (5 s poll granularity, indicative only): 21.4, 18.9, 17.1, 17.9, 19.7, 19.4, 17.3, 23.8 s (mean ≈ 19.4; R3F's correctness run
  on a busier machine: 31.9, 23.8, 24.9, 27.1, 28.5, 25.3, 34.4, 30.1; combined3's: 28.3–31.5). B0's paired protocol decides the s/token.
- `bundles/R3R/READY` created.

## 6. Prediction and residual risks

- **Predicted s/token: ≈ 20–21 (combined3 24.6 / R2F 23.6 in B2's queue): −6 frames/token (46 → ≈40 at ≈110 ms), −12 × 1,553-element bank passes
  (≈205 ms each incl. 769 transition starts) − 12 × 82 ms paint-phase transition servicing, −768 anims/layer; ≈ −3.5 to −4.5 s/token traced (≈ −3 to −3.7
  untraced).** Only a paired bench (B3-style, vs combined3 or R3F) is meaningful.
- The fold relies on two Blink behaviours the old design already relied on: a `content-visibility:hidden` gate blocks child restyle/layout in the pass in
  which it closes (S1 pass sizes prove it), and view-timelines of locked subjects keep their last snapshot (the old read bank lived under the closed proj
  gate for a whole layer). New reliance: `calc-size(max-content, …)` with `var()`-substituted number coefficients on an absolutely positioned inline-flex
  `.metric` (the head rows use calc-size already); evaluated at layout in float — precision class unchanged (§1.5).
- Range: `262144 + 128·out` must stay within [0, 2·524288] px, i.e. |out| < 2048 — the same bound the loop bank imposed (`262144px + v·128px`, viewport
  524288). GPT-2's largest residual coordinates (≈ ±3e3 in dim 447 at late layers for some prompts) would overflow both designs equally; not new.
- Token boundary: correctness depends on `--held` locking `.loop-compute` in the very pass in which `--loop-in` jumps to out_{12k} (§1.4); the 8/8 run and
  the smoke (frame 19: hold + export in one pass, head in the next) show it holds. A design that removed the cap (advance `--pass` to 12k+1 immediately and
  gate layer 0 on `--embed-ready == --position`) would also work and would make `--held` unnecessary except for the export; not needed now.
- R2G's `:has()` scoping (R3F, −0.05 s) is not merged: the base is R2H per the brief. The merge is trivial (R3F touched only `browser_gpt2_runtime.py:24,566-585` +
  `r2g_has_scope.py`; R3R touched the block builder, the reused core and the adapter).
- Not measured here: s/token, frames per token on 12 layers (the smoke's 6 passes/layer structure is exact; the 12-layer per-frame count is derived).
- Follow-up folds now possible because the proj carriers are html-scoped: the head bridge (`.reused-final-export` 769 carriers + `.b11-bridge-c0/c1`) could read
  the proj carriers directly with `--bridge-ready: marker == 12·epoch` (−1 hop/token, but 768 head-receiver anims restyled 12×/token instead of 1×: ≈ +0.3 s vs −0.15 s
  — not worth it as is); the attn stage's residual `--r = x + attn` is the analogous fold target for hop 5 only if LN2's Σ could be taken from geometry (it cannot).
