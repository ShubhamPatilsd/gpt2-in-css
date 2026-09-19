# R2F — remove the pure-handshake frames (E, G) and fold the pass advance (F) into hop frame D

Agent R2F, 2026-09-19. Tools copy `work/2026-09-19/R2F/tools` (= F4 tools + `r2f_lean_handshake.py`, flag `R2F_LEAN_HANDSHAKE`, default ON).
Bundles: `work/2026-09-19/bundles/R2F` (12 layers, BUILD.md has command + `diff -ruN`), `bundles/smoke-R2F-2L` (2 layers, 2 positions),
`bundles/smoke-R2F-2L-ref` (same with the flag OFF). Scratch/harness: `work/2026-09-19/R2F/`. Log: `R2F.log.md`.
Nothing under repo `tools/` or `experiments/` was modified; no commits.

## 1. The per-layer frame sequence in `combined` (step 1; from the emitter + R2A's token-5 frame table)

State lives on `.core-controller` (container `loopcontrol`/`corestate`): `--pass` P, `--loop-phase` b = (P−1) mod 2 (bank to write; read bank r = 1−b),
`--layer`, `--position`; F5 stamps `--native-pass:P` onto the 14 readers via `@container loopcontrol style(--pass:P)`; every stage receipt derives
`--epoch` from it and opens its `content-visibility` gate only when the stage's marker carrier reads back the current pass
(`build_hybrid_twelve_block.py:209-222`). The loop banks (`probe_native_reused_loop.py:loop_parts`) sit under the proj gate:
`.reused-output > .loop-bank-1 > .loop-bank-0`; each bank has 769 `.loop-metric` view-timeline carriers (768 values + the pass marker
`--saved-b-768:var(--native-pass)`), read back by 1,538 animations on `.loop-reader` (`--lp-b-i`) and decoded on `.loop-input`.

| frame | passes (elements) | what starts it | style / layout work | values transported |
|---|---|---|---|---|
| A | `2934 \| 126` | `:has(#loop-advanced-(P−1).done)` → `--pass:P` (first pass); snapshot re-run (second) | S1: `--native-pass`/`--epoch` restamp closes all 6 stage gates, `--x` ← loop readback of bank r, LN1, qkv fonts; layout (shaping) → snapshot → qkv readback → `--fvs-live` → KV bank write (26 latch transitions) → 96 score fonts | x → qkv |
| B | `0 \| 6919 \| 780` | snapshot (score glyph widths) | scores readback → softmax → 96 V fonts → row widths; snapshot → ctx readback → attn fonts | scores → ctx |
| C | `0 \| 3089 \| 784` | snapshot | attn readback → residual → LN2 → fc fonts; snapshot → fc readback → proj list | r → hidden |
| D | `0 \| 1553 \| 357` | snapshot | proj readback → `--out` → proj gate opens → **both banks restyled**: write bank b `transition-property:none` + values + marker P, read bank r loses its phase rule → 769 latch transitions start (trace: 770/769 anim start/end here, 0 in A); layout → snapshot → `.loop-reader` (1,538 anims) → `.loop-input{--loop-ack:1}` (marker == P) → `#loop-ready-P{animation:loop-pulse 1ms}` | out → banks; marker |
| **E** | `1` | the 1 ms pulse ends (`#loop-ready-P` restyled); SMIL timer +1 ms → `#loop-captured-P.done` | none (pure handshake, 103 ms) | — |
| **F** | `485` | `:has(#loop-captured-P.done)` | `.core-controller{--loop-captured-pass:P}` → `--loop-held:1` (arms the write bank's transition list) + `#loop-ack-P{animation:loop-pulse}`; the 485-element restyle is the controller, `.core-block`, `.loop-reader`, `.loop-input`, `svg.loop-signals` + its 480 `<g>`/`<set>` (312 ms, 223 of it this pass) | — |
| **G** | `1` | ack pulse ends; SMIL → `#loop-advanced-P.done` | none (103 ms) | — |

85 frames/token = 12 × (A B C D + E F G) + 1 head. Why E/F/G exist: the fact "bank b now carries pass P's output" (`--loop-ack`) is computed on
`.loop-input`, a *descendant* of the pass controller; CSS state can only travel upward through `:has()` on DOM state, and without JS only SMIL can
turn an animation event into DOM state — hence pulse → `animationend` → `<set class=done>` → `:has()`, twice (captured, then advanced). The
captured step's only job (`--loop-held` arming the write bank's `transition-property` before the pass flips) is redundant: the banks are under the
proj gate, `content-visibility:hidden` also blocks child style recalc, so the banks are restyled only when the proj gate opens (frame D), and Blink
starts transitions from the *after-change* `transition-property`, whose base rule already lists all 769 names.

## 2. Redesign (step 2) — `R2F/tools/r2f_lean_handshake.py`, wired in `browser_gpt2_reused_adapter.py:14,54-62,195-197,224`

- A wrapper `<div class="core-pass-reader">` above `.core-controller` carries 2 animations on the existing keyframes/timelines
  `loop-k-{0,1}-768` / `--loop-t-{0,1}-768` (scoped on `html`), i.e. it reads both bank pass markers directly.
  `.core-controller{--lp-0-768:inherit;--lp-1-768:inherit}` (private props, F5 pattern) and
  `--pass:min(calc(max(round(decode(lp0)),round(decode(lp1))) + 1),var(--pass-cap))` with the same centered decode the data carriers use.
- The write bank's marker is declared in the same rule as its 768 values, laid out in the same layout, snapshotted in the same
  `RunScrollSnapshotClientSteps`, and latched by the same transition list when the bank turns into the read bank — so `max(markers) = P` exactly when
  P's output is readable (the fact `--loop-ack` encoded). `--pass` therefore becomes P+1 in D's second pass, the pass that used to start the pulse; that
  same recalc restamps `--native-pass`/`--epoch`, closes every stage gate (banks stay locked, so the write bank is *not* restyled with the new phase —
  its marker cannot run ahead), unlocks `.loop-compute` (`--loop-ready`: bank b's marker == (P+1)−1) and runs S1 of the next layer.
- Token boundary: `--pass-cap` (`<number>`, inherits:false; 12 initially) replaces the `--pass:12k+1` declaration in the existing
  `:where(body:has(#token-k-advanced.done)) .core-controller{…}` rules; at P = 12k the controller holds `min(P+1, P) = P` until the head's SMIL ack.
- Removed: 96 ready-pulse, 96 captured, 95 ack-pulse, 95 advance rules, the 2 `--loop-held` bank rules, the 2 `--loop-ack` calcs, and the
  384 `<g>` + 192 `<set>` SMIL elements (`svg.loop-signals` kept, empty). Nothing else changes (offline check §4).
- Expected frames: per layer 7 style passes (S1 + 6 readbacks; the loop readback and S1 share a pass) at Blink's 2 `UpdateStyleAndLayout` per
  frame → 3.5 frames/layer, no latch boundary needed (the KV write still happens inside A's second pass as before); layers no longer align to
  frames (the layer boundary sits inside a frame). Predicted: 85 → ≈43–45 frames/token; −(24 × 103 ms + 12 × 312 ms) ≈ −6 s traced (≈ −5 s untraced) minus
  the S1 work that moves into D (unchanged size).

## 3. 2-layer smoke (step 3) — `bundles/smoke-R2F-2L` (2 blocks, 2 positions), one traced run

Harness `R2F/run_bundle.mjs` (F3b's, light trace), under the mutex, on battery (correctness only; wall 23.2 s for both tokens incl. a 4.5 s head
frame — the machine was at load 15–28). First attempt at 06:10 died in `page.goto` after 600 s; `R2F/diag_load.mjs` then showed both the lean and the
reference smoke page load in ≈2 s and sit idle (18 recalcs, stable), so it was machine load, not the page. Second attempt (`R2F/runs/smoke-R2F-2L/`):

- **ids `[11, 3387]` = the 2-layer reference** (`smoke-TL-2L`: `[11, 3387]`, F3b.md §5). `verify_browser_gpt2_runtime.py` could not score the KV
  readback only because F3b's harness parses unpacked bank lists (F4's packed `--fc-k-S` lists → `cachesComplete 0`); the 12-layer run uses F4's harness.
- Per-frame table `R2F/runs/smoke-R2F-2L/frames.md` (`R2F/frames.py`). Token 2 (steady state, frames 15–25; `0:` = the hover-forced 0-element pass):

| frame | passes (elementCount:ms) | layouts (dirty) | anim start/end | what |
|---:|---|---|---|---|
| 15 | `832:84 2342:162` | 1571, 6944 | 2/0 | feedback/embedding readback → S1 of layer 0 |
| 16 | `0:20 44:86 2311:52` | 113, 3878 | 26/0 | qkv readback → KV bank write (26 latches) → score fonts; scores readback → softmax → V rows |
| 17 | `0:22 780:39 3089:194` | 2344, 9266 | 0/0 | ctx readback → attn fonts; attn readback → LN2 → fc fonts |
| 18 | `0:23 784:156 1553:308` | 2359, 1600 | 769/769 | fc readback → proj fonts; proj readback → `--out` → banks (769 latch start + 769 cancel) |
| 19 | `0:22 2334:123 44:111` | 6944, 113 | 27/0 | **loop readback → `--pass`+1 → S1 of layer 1 in one pass**; qkv readback |
| 20 | `0:21 2311:28 780:54` | 3878, 2344 | 0/0 | scores; ctx |
| 21 | `0:21 3089:159 784:172` | 9266, 2359 | 0/0 | attn; fc |
| 22 | `0:19 2326:305 50892:598` | 2374, 101162 | 770/771 | proj readback → layer-1 export (770 = 769 latches + `--head-fvs`) → head pass, same frame as before |
| 23–25 | `1:22 6:7`, `20:25`, `1:22` | –, 11, – | 0/1, 1/0, 0/1 | the head's token SMIL handshake (unchanged, not in scope) |

**14 layer passes in 7 frames = 3.5 frames/layer (target ≤ 4)**; the pass advance + S1 happen inside the frame that reads the banks; no 1-element
pulse frames, no 485-element pass, no `--loop-held`/captured frame. Token-1 window (startup + 2 layers + head): 50 `UpdateLayoutTree`, 32 `Layout`,
23 frames; token 2 (frames 15–25): 27 `UpdateLayoutTree` (11 of them hover 0-passes), 19 `Layout`, 11 frames. The equivalent `combined` layout is
7 frames/layer (R2A §5), i.e. the 2-layer token would have had 14 + 5 frames. Extrapolated to 12 layers: 12 × 3.5 + embedding + head + 3 token frames
≈ 47 frames/token vs 85.

## 4. Offline verification

`R2F/offline_check.py R2F combined`: PASS — selector-level diff limited to the handshake rules (+12 / −381), −575 elements (= 6·96 SMIL elements − 1 wrapper),
+1 registration (`--pass-cap`), `@font-face` list and `font-witnesses.json` identical (modulo the tools-copy path in the keys), the bank write rules /
marker declaration / base 86400 s latch lists unchanged, the 8 stamp-rule families intact. `launch_browser_gpt2.py --check`: assets resolve.

## 5. 12-layer correctness run — `bundles/R2F`, ONE passive run (not a timing run)

`R2F/run_correctness.sh R2F` (F4's `correctness_run.mjs`, packed readback, 5 s poll, `--js-flags=--heap-growing-percent=10`), under the mutex,
10:02–10:07, **on battery**, machine load ≈ 15–25 from other agents. `R2F/run-R2F/{harness.log,verify.log,verification-vectors.json,pipeline-results.json}`.

- **ids `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = reference, 8/8** (`verify_browser_gpt2_runtime.py`: tokenAgreement all True, originalFloatAgreement
  all True, text "Hello, I'm sorry, but I'm"); `finalResidualError` rmse 0.019328970092677755 / max 0.18731862085027728 — **bit-identical to F4's
  `combined` run** (same numbers in `F4/run-combined/verify.log`), as expected: the change touches no arithmetic.
- Whole-run counters (harness idle → end): `RecalcStyleCount` 1,109 vs 1,420 for combined (−311 ≈ 96 layer passes × 3 protocol passes + fewer hover
  passes), `LayoutCount` 712 vs 888 (−176).
- Per-token capture times (5 s poll granularity, battery, loaded machine — indicative only): 37.6, 31.3, 32.8, 35.2, 34.6, 39.4, 33.0, 41.2 s
  (combined under F4's AC run: 35.9, 28.5, 29.4, 33.9, 27.4, 36.0, 27.5, 33.4 s). B0's protocol decides the s/token.
- `bundles/R2F/READY` created.

## 6. Residual risks / follow-ups

- The latch now relies only on Blink starting transitions from the *after-change* `transition-property` (CSS Transitions §3; the base bank rule lists
  all 769 names) — the `--loop-held` pre-arming is gone. The traces show the expected 769 starts / 769 cancels at every proj readback (frames 18, 22 above)
  and the ids are exact, so this holds in Chrome 153; another engine could differ.
- `--pass` is now a computed number (`min(calc(max(round(..),round(..)) + 1),var(--pass-cap))`) queried by 97 `style(--pass:N)` rules; it is exact because
  the markers are integers passed through the same carrier decode as the data and rounded. A garbage marker readback would advance the pass wrongly
  (the old `--loop-ack` equality test would only have stalled); the marker is written/laid out/latched with the data, so a wrong marker implies wrong data anyway.
- The wrapper `.core-pass-reader` reads bank timelines from *inside* its own subtree (`.core-controller` descendants). Blink resolves this with its 2
  `UpdateStyleAndLayout` iterations per frame; no third iteration was observed and the page idles at load (diag), so no snapshot ping-pong.
- Layers no longer align to frames (a layer boundary sits inside frame D'). Tools that count "frames per layer" from pass signatures must use the 7-pass
  period (S1, qkv, scores, ctx, attn, fc, proj), not frame boundaries.
- Merge with R2E (hop-gated timelines): this diff touches only `browser_gpt2_reused_adapter.py` (import, one block after `compile_reused`, the body
  wrap, one manifest key) plus the new module; R2E's hunks in the same file are the `r2c_hoist` import and the manifest tail — adjacent but disjoint.
- Not measured here: s/token (B0's protocol). Prediction from R2A §6 R1 + the F-frame fold: −(24 × 103 ms + 12 × 312 ms − 12 × ≈60 ms of S1 work that
  merely moves) ≈ −5.5 s traced ≈ −4.5 s untraced per token; the merged loop-readback/S1 pass should also shrink R2A's unexplained 357/485-element passes.
