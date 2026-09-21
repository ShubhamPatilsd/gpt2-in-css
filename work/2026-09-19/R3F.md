# R3F — fold the remaining hop frames (round 3)

Agent R3F, 2026-09-20. Tools copy `work/2026-09-19/R3F/tools` (= R2H's combined3 emitter + `r2g_has_scope.py`, flag `R2G_SCOPED_HAS` default ON).
Bundles: `work/2026-09-19/bundles/R3F` (12 layers; `BUILD.md` = command + `diff -ruN` vs R2H/tools), `bundles/smoke-R3F-2L` (2 blocks, 2 positions),
`bundles/smoke-R3F-2L-ref` (same, flag off). Scratch/harness/logs: `work/2026-09-19/R3F/`, `R3F.log.md`. Nothing under repo `tools/` or `experiments/`
was modified; no commits.

## 0. Headline

**The per-layer fold the brief asks for is already saturated in R2F.** Blink runs at most two `UpdateStyleAndLayout` per frame after a
scroll-snapshot change (R2A §5; confirmed on every one of the 46 frames of the R2F 12-layer trace), a layer needs 7 geometry→number hops
(loop-transport+S1, qkv, scores, ctx, attn, fc, proj), and R2F's steady state pairs **every** hop pass with a neighbour: 86 hop passes/token in
43 frames, 12 × 3.5 = 42 layer frames + 1 head frame, **no frame with an idle second slot and no latch-forced boundary** — the 26 KV-bank
latches (`--fc-*`) start in the qkv pass while the scores pass runs in the same frame (frames 0/7/14/… below), so the "A→B latch boundary" of
R2A is not a boundary at all. 3.5 frames/layer is therefore the floor for this hop count; the "≤ 2–3 frames/layer" target needs one hop less
per layer, which is an arithmetic/transport change (§2), not a handshake change. The only non-hop frames left are the 3 token-boundary SMIL
frames (`1 6`, `39`, `1`: 290 ms ≈ 1.2 % of the token); their R2F-style fold is designed in §2 but not built (single correctness run allowed,
gain ≤ 0.3 s/token). What R3F ships is step 3 of the brief — R2G's `:has()` scoping, generalised to all 79 handshake arguments (§3) — with
the smoke/12-layer verification of §4–§5. Predicted effect ≈ −0.05 s/token (R2G's −0.35 s was 90 % the 272 loop rules R2F already deleted).

## 1. Steady-state frame sequence of R2F (step 1)

Source: `R3A/light-R2F-t1-anatomy.md` token-5 frame rows (R3A's streaming parse of `bench/runs/R2F/R2F-t1-trace.json.gz`; identical structure
in tokens 2–7: 132 passes / 87 layouts / 46 frames per token). Per frame: `0:14` = the 14 ms zero-element forced pass of the post-layout hover
update (present in every frame even with the pointer parked at −50,−50; see §6), then pass 1 (consumes the geometry laid out in the previous
frame, snapshotted at the animate step) and pass 2 (re-run after `RunScrollSnapshotClientSteps` reports the change of pass 1's layout).

| frame (layer L) | pass 1 | pass 2 | what forces the boundary to the next frame |
|---|---|---|---|
| A′ | `2323` loop readback (bank b marker/values) → `--pass`+1 → S1: `--x`, LN1, qkv fonts; layout 6,943 | `126` qkv readback → `--fvs-live` → KV write (26 `--fc-*` latch transitions start) → score fonts; layout 339 | 2-pass cap only (scores would be pass 3) |
| B′ | `6919` scores readback → softmax → V fonts, row widths; layout 8,496 | `780` ctx readback → attn fonts; layout 2,344 | 2-pass cap |
| C′ | `3089` attn readback → residual → LN2 → fc fonts; layout 9,266 | `784` fc readback → GELU → proj list; layout 2,359 | 2-pass cap |
| D′ | `1553` proj readback → `--out` → bank write (769 `--saved-*` latch transitions start/cancel) ; layout 1,600 | `2323` loop readback of the NEXT layer → `--pass`+1 → S1(L+1); layout 6,943 | 2-pass cap |
| A″ (L+1) | `126` qkv(L+1) | `6919` scores(L+1) | … the pairing shifts by one hop every layer (7 is odd) |

So the 7-pass period repeats every 3.5 frames: `[loop+S1 | qkv] [scores | ctx] [attn | fc] [proj | loop+S1′] [qkv′ | scores′] [ctx′ | attn′] [fc′ | proj′]`.
Per token: 12 × 7 = 84 layer passes + `863` (feedback readback → `--epoch` consumers → embedding fonts) + `2342` (embedding readback → S1 L0)
+ `2326` (L11 proj readback → b11 bridge export) + `50892` (bridge readback → `--head-fvs` → head restyle, 1.3 s layout) = 88 hop passes in 44
frames (all 2-per-frame) + 3 token-handshake frames (`1:18 6:9` ready-pulse end → SMIL captured → `:has()` consumers + ack pulse; `39:24`
`--saved-token` latch / ack; `1:14` ack pulse end → SMIL advanced) − 1 (the `863|2342` frame is one of the 44) = **46 frames**, 87 layouts, 132 passes
(88 hop + 44 hover zero-passes; the 3 handshake frames have no layout or a 7-object one).

Adjacent hop pairs with no latch between them: **all seven** (the KV latch does not block scores; the loop-bank latch holds the *read* bank, the
loop readback reads the *write* bank). Pairs already sharing a frame: all of them, alternating by layer parity. Nothing is left to fold at this hop
count.

## 2. What a further frame reduction would take (step 2, design only)

1. **One hop less per layer (3.5 → 3 frames, −6 frames ≈ −0.66 s and −12 × 84 ms loop passes ≈ −1 s/token).** The loop-transport hop exists
   because `--out = r + proj` is decoded on a descendant (`.reused-output`) and must travel up to `.core-controller` as `--x` while `--x` stays
   frozen for the other 6 hops (two-bank latch). Removing it means the controller reads the proj *carriers* directly (timelines scoped on `html`,
   as R2F's `.core-pass-reader` reads the bank markers) — but then the residual `r` must already be inside the proj carrier widths and must not
   move mid-layer. `r = x + attn` changes at hop 5 (attn readback), so `padding-left:calc(var(--r-i)*1px)` on the carriers or a residual axis in
   the proj fonts would both move the carriers at hop 5 and break the layer; a latched copy of `r` needs 768 more transitions per layer (R6 cost
   ≈ 0.25 s/layer). Net: not a handshake fold; it is the "fewer carriers / fused B·GELU(A·x)" Phase-2 item of PLAN.md.
2. **Token boundary (3 SMIL frames ≈ 0.29 s/token traced, ≈ 0.25 untraced).** R2F-analogue: `--epoch` on `body` is `inherits:false` and stamped to
   9 readers; compute it as `1 + Σ_k clamp(0, var(--feedback-k) + 1, 1)` from the 8 feedback carriers (`--feedback-k` = −1 until token k exists)
   with the 8 `feedback{k}` animations duplicated on `body` (timelines already scoped on `html`), drop the `body:has(#token-k-advanced.done){--epoch}`
   rules and the `body:has(#token-k-captured.done) .token-slot-k{transition-property}` arming (redundant for the same reason as `--loop-held`),
   keep the SMIL chain only for the visible output / `#token-k-captured.done` harness marker. Expected: the `1 6`/`39`/`1` frames disappear, the
   `863|2342` frame follows the head frame directly. Risk: the `.token-slot-k` latch (`if(style(--head-output-epoch:k)…)` + 86400 s transition)
   would be armed only by the base rule; needs a 2-token smoke before a 12-layer run. Not built in R3F (one correctness run budget; ≤ 1.2 %).
3. **Zero-element hover pass, 44 × 14 ms ≈ 0.62 s/token (harness, B0).** Every frame carries a forced `UpdateStyleAndLayout` with 0 elements and a
   hit-test although the pointer is parked off-viewport: Blink's post-layout hover update runs whenever the mouse position is *known*. Clicking
   Run without a mouse (focus `#run` via CDP `DOM.focus`, `Input.dispatchKeyEvent` Space) should leave `MouseEventManager::IsMousePositionUnknown()`
   true and skip the update entirely. Hypothesis for B0 to test in a fixture; not in R3F's scope.

## 3. Step 3 — R2G `:has()` scoping, generalised (`R3F/tools/r2g_has_scope.py`, hook `browser_gpt2_runtime.py:24,566-585`)

R2G's module asserted the 272 `.core-controller:where(:has(#loop-…))` rules exist; with R2F they do not, so the module was extended rather than
copied verbatim: every body-anchored `:has(#id.done)` / `:has(#id:checked)` in the final sheet (79 arguments / 69 rules in the 12-layer bundle:
`#run:checked` 26, `#token-N-captured.done` 33, `#token-N-advanced.done` 14, `#run-latched.done` 3, `#fonts-loaded.done` 2, `#eos-done.done` 1)
becomes `:has(> :where(.a) > :where(.b) > … > #id.done)` with the id's exact ancestor chain read from the emitted `index.html` (chained
`body:has(x):has(y)` compounds handled; anchor verified as `body`; build fails on any mismatch or leftover). `:where()` steps keep specificity and
cascade order identical (`:has()` takes its argument's specificity, and these rules compete with `@container` rules on the same properties). R2G's
loop-rule rewrite is kept for builds with `R2F_LEAN_HANDSHAKE=0`. Manifest key `r2gScopedHas`.

Expected gain, from R2G's 7.5 ns/visited element: the only subject restyled in the steady loop is `.core-controller` (12×/token, 7 token-advanced
arguments × 69k elements ≈ 3.6 ms) → ≈ −45 ms/token traced; the token-slot / run / status subjects restyle once per token. **≈ −0.05 s/token**,
i.e. inside B0's noise; the bundle is shipped for correctness and as the base for the next fold, not as a measurable win.

## 4. 2-layer smoke (step 4) — `bundles/smoke-R3F-2L` (2 blocks, 2 positions), one light-traced run under the lock

`R3F/run_chrome.sh smoke-2L 420 smoke_inner.sh …` (R2F's `run_bundle.mjs`, light trace, 2 s poll, heap flag), 20:38:54–20:39:35 (AC, load ≈ 4.8;
the lock was taken in the 120 s gap between two B3 paired steps after an 80-min wait). `R3F/runs/smoke-R3F-2L/{harness.log,frames.md,trace.json.gz}`.

- **ids `[11, 3387]` = the 2-layer reference** (F3b `smoke-TL-2L`, R2F smoke), done markers 2/2 — every rewritten `:has()` chain fires in Chrome
  (`#run:checked` → run-start, `#run-latched.done`/`#fonts-loaded.done` → `.core-block` unlock, `#token-1-captured/advanced.done` → slot latch,
  `--epoch:2`, `--pass-cap`, display). RecalcStyleCount deltas 47 + 14, LayoutCount 29 + 5 (token windows at 2 s poll granularity).
- Per-frame table (`R3F/frames.py`), token 2 = frames 15–25: `832|2342` (feedback → embedding readback → S1 L0), `44|2311` (qkv + KV write | scores),
  `780|3089` (ctx | attn), `784|1553` (fc | proj → banks, 769/769 latch start/cancel), `2334|44` (loop readback + `--pass`+1 + S1 L1 | qkv), `2311|780`,
  `3089|784`, `2326|50892` (L1 proj → bridge | head), then the 3 token-handshake frames `1 6`, `20`, `1`. **14 layer passes in 7 frames = 3.5 frames/layer,
  byte-for-byte the same frame structure as R2F's smoke (R2F.md §3)** — as expected, the `:has()` rewrite changes no data flow; nothing to diagnose.

## 5. 12-layer correctness run (step 5) — `bundles/R3F`, ONE passive run (not a timing run)

`R3F/run_chrome.sh correctness-12L 900 correctness_inner.sh R3F` (F4's `correctness_run.mjs`: headless Chrome 153, `--js-flags=--heap-growing-percent=10`,
poll `#token-8-captured.done` every 5 s, one readback; lock protocol with 30 s touch + watchdog), 21:11:45–21:15:47, AC, load ≈ 5 (B3's paired pass
and its trace parsing in the background). Results in `R3F/run-R3F/{harness.log,verify.log,verification-vectors.json,pipeline-results.json}`.

- **ids `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = required, done markers 8/8**; `verify_browser_gpt2_runtime.py` rc=0: tokenAgreement 8 × True,
  originalFloatAgreement 8 × True, text "Hello, I'm sorry, but I'm", `finalResidualError` rmse 0.02005934198718561 / max 0.18731616094288484 —
  **bit-identical to combined3's run** (`R2H/run-combined3/verify.log`), as it must be: the change touches selectors only.
- Whole-run counters (Performance.getMetrics at the end, same F4 harness as the earlier runs): RecalcStyleCount 1116, LayoutCount 720; combined3 1107 / 710, R2F 1109 / 712 —
  same pass structure within the hover/poll jitter. Frames: not traced in this run (the frame structure is the smoke's §4 = R2F's 46/token).
- Per-token capture times (5 s poll, loaded machine — indicative only): 31.9, 23.8, 24.9, 27.1, 28.5, 25.3, 34.4, 30.1 s (combined3's own correctness
  run under the same load class: 28.3, 23.9, 28.6, 25.6, 26.1, 27.1, 24.1, 31.5). B0's protocol decides the s/token.
- `bundles/R3F/READY` created 2026-09-20 21:16:44.

## 6. Prediction and residual risks

- **Predicted s/token: ≈ 23.5 (R2F 23.6, combined3 24.6 in B2's queue): −0.05 s from the 79 scoped `:has()` arguments, no frame change (46/token).**
  A bench is only worth it paired against combined3 (B3-style); the difference is below the run-to-run spread.
- Frame budget: 46 frames/token = 44 hop-pair frames + 3 token-handshake − 1; at the 2-pass cap and 7 hops/layer the layer loop cannot lose frames.
  The next real reductions are (a) the token-handshake fold (§2.2, −3 frames ≈ −0.3 s), (b) the hover zero-pass (§2.3, harness, ≈ −0.6 s),
  (c) one hop less per layer (§2.1, ≈ −1.7 s but an arithmetic/font change), (d) fewer live timelines (R2A R2, per-frame cost).
- `:has()` chains are verified at build time against the emitted HTML with Python's html.parser (no implicit-close rules); the smoke and the 12-layer
  run show every handshake firing in Chrome, so the chains match Blink's DOM for this page. A future DOM change fails the build (ValueError) rather
  than stalling the page. `R2G_SCOPED_HAS=0` reproduces combined3's runtime.css.
- The `:where()` steps keep specificity; Blink's fixed-depth traversal is decided by the child combinators, not by the compounds — if a Blink version
  treated `:where()` in a `:has()` argument as unbounded, the cost would return to combined3's, never below correctness.
- Not measured here: the −0.05 s itself (predicted from R2G's 7.5 ns/visit × 7 arguments × 69k elements × 12 controller restyles).
