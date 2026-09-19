# R2D — round 2: lock the output head outside its own pass, and cheap per-frame knobs — report

Agent R2D, 2026-09-19. Tools copy: `work/2026-09-19/R2D/tools` (= F4's copy + `r2d_knobs.py` + 5 hunks in `browser_gpt2_runtime.py`).
Bundle: `work/2026-09-19/bundles/R2D/` (BUILD.md there: command, flag table, full `diff -ru`). Log: `R2D.log.md`. Nothing under repo
`tools/` or `experiments/` was modified; no commits. Chrome runs (all under `CHROME.lock`): two 2-token light-trace A/B probes
(02:41–03:00), correctness run #1 (lock + clip, 09:42, battery) and correctness run #2 (the READY bundle, §5).

## 1. What gates the head today, and what the 51,247-element pass is

- Topology (`browser_gpt2_runtime.py` F4 copy :329-408, `head-two-pass/head.css`): `.full-head{content-visibility:hidden}` is opened by TWO rules:
  `@container headinput not style(--head-input-epoch:0){.full-head{content-visibility:visible}}` (:364) and
  `@container b11-bridge style(--bridge-ready:1){.full-head{content-visibility:visible}}` (:408, detached output). `--head-input-epoch` is
  latched by an 86,400 s transition on `.head-input-bank` and never returns to 0 after token 1, so from token 1 on the head was
  **permanently unlocked** (the code comment says so deliberately: "so feedback geometry stays alive throughout subsequent iterations" —
  a leftover from before `--detached-output`, when the token slots lived inside the head).
- What restyles the 51k rows: only the head's own input. The `.head-isolation` wall resets every registered property except
  `--head-fvs`/`--head-input-epoch`/`--hq-*`/`--fvn-*`/`--f[zt]-*`; F5 made `--epoch` non-inherited. B0's combined trace confirms:
  the 51,247-element pass occurs **exactly once per token**, 3.8–4.0 s before each `--saved-token-N` latch = the moment `--bridge-ready`
  flips to 1 and `--head-fvs` changes (R2A §4 reached the same conclusion independently: it is the head matmul — 50,257 rows re-shaped).
  The histogram's "1.4/token" was 7 passes counted over 5 complete windows. **This pass is inherent and cannot be removed by a lock.**
- What the lock CAN do: the head rows otherwise stay laid out / painted / compositing-input-walked / hit-tested on the other ~84 frames per
  token. The lock skips them there.

## 2. What changed (all in `work/2026-09-19/R2D/tools`, env flags in `r2d_knobs.py`)

| flag (default) | file:line | change |
|---|---|---|
| `R2D_HEAD_LOCK` (ON) | `browser_gpt2_runtime.py:365-375`, `r2d_knobs.py:head_lock_css` | the permanent `headinput` unlock rule is not emitted; `.full-head` is visible only while `@container b11-bridge style(--bridge-ready:1)` (end of layer 11 → the epoch advance). Driven by the existing container-style stamp: no new animations or frames. Requires `--detached-output` (raises otherwise): the token slots retain `--saved-token-N` by their own transitions outside the head, and `#token-N-ack` (the epoch advance) fires only after `#token-N-captured`, so the head hides strictly after the winner was captured. While hidden, `.detached-head-reader`'s `anchor-size(--detached-head-result …)` falls back to 0 → `--head-output-epoch:0` → `--saved-token-N` → −1 is caught by the slot's retained transition (the same mechanism that retains it today when the next head pass sets N+1). At the end of the run `--epoch` stays 8, so `--bridge-ready` stays 1 and the head is visible for the readback. |
| `R2D_OVERFLOW_CLIP` (ON) | `r2d_knobs.py:overflow_clip`, applied at `browser_gpt2_runtime.py:555-556` | `.head-row` (50,257), `.head-fine-row` (256), `.metric` (8,551): `overflow:hidden` → `overflow:clip;min-width:0` (asserted 1 replacement each). Same clipping; the boxes stop being scroll containers. `min-width:0` pins the grid items' automatic minimum to what a scroll container already had (the only sizing difference between the two values). |
| `R2D_CONTAIN_PAINT` (ON) | `r2d_knobs.py:CONTAIN_PAINT_ROOTS`, `:559-560` | `.head-group,.head-fine,.loop-scroll,.embedding-scroller{contain:paint}` (R2B MB9). Roots chosen so that no descendant is read from outside via anchor-size()/container units and no `position:fixed` descendant changes containing block; `.position-embedding`, `.head-isolation`, `.full-head`, `.head-coarse-reader` excluded (they contain `.detached-head-source`, whose anchor is read by `.detached-head-reader` outside; `#core-epoch-observer` reads `--block-11-probe-epoch` from outside). `.scroller`/`.readback` already have `contain:strict`. |
| `R2D_POINTER_EVENTS` (**OFF**) | `r2d_knobs.py:pointer_events_css`, `:557-558` | `pointer-events:none` on the compute roots. A/B: no gain (§3) → default OFF. |
| manifest | `browser_gpt2_runtime.py:583-585` | `r2dHeadLock`, `r2dOverflowClip`, `r2dPointerEvents`, `r2dContainPaint` |

Compositing audit (step 2c, `bundles/combined`): 0 `will-change`, 0 `transform`; `opacity` only inside the two 1 ms handshake keyframes
(`native-handshake`, `loop-pulse`: `.99 → 1` on SVG `<g>`, main-thread, no compositor layers); 21 `position:fixed` rules + 7 inline
probes (all off-screen sizing probes or scrollers the pipeline reads); `content-visibility` flips = the 12 stage gates (needed).
`PaintArtifactCompositor::Update` is 26 ms over 572 frames and the Compositor thread 2.1 s over 7 tokens: compositing is not a cost
centre, nothing removed. `contain:paint`/`visibility:hidden` on the whole compute tree were rejected: paint containment turns the
root into the containing block of every `position:fixed` probe/scroller inside it, and the detached-head anchor is read from outside.

## 3. A/B (2 tokens each, light trace, B0 harness `B0_CAPACITY=2`, heap flag ON, AC, 02:41–03:00; `R2D/ab/`)

Arms: A = `bundles/R2D-lock` (lock only), B = `bundles/R2D-allknobs` (lock + clip + pointer-events). Control = B0's `combined` light trace
(same harness/machine, 18:xx the previous evening, contended) — a same-session `combined` control was not run (2-run budget, then the
coordinator stopped timing runs: battery + load). Per-frame ms = phase inclusive ms / frames in the token window (`R2D/ab/frames.py`).

| run | token | wall s | frames | passes | whole-DOM pass (ms) | style | layout | animate | pre-paint | comp. inputs | paint LC | hit-test | frame ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| combined (B0) | 3 | 34.1 | 85 | 171 | 1 (601) | 183.6 | 62.2 | 41.2 | 22.3 | 19.8 | 63.7 | 11.8 | 400 |
| combined (B0) | 4 | 35.4 | 85 | 171 | 1 (813) | 190.8 | 66.0 | 42.1 | 22.6 | 20.2 | 66.4 | 12.2 | 416 |
| A lock | 1 | 32.8 | 91 | 172 | 1 (475) | 187.4 | 49.0 | 30.7 | 19.9 | 17.8 | 50.5 | 8.0 | 362 |
| A lock | 2 | 32.2 | 85 | 171 | 1 (581) | 172.2 | 59.2 | 37.6 | 22.3 | 19.9 | 61.3 | 10.7 | 379 |
| B lock+clip+pe | 1 | 32.3 | 91 | 172 | 1 (470) | 187.2 | 46.3 | 29.7 | 19.1 | 17.1 | 50.4 | 8.1 | 357 |
| B lock+clip+pe | 2 | 32.4 | 85 | 171 | 1 (583) | 176.6 | 55.8 | 37.9 | 22.5 | 20.1 | 62.0 | 11.2 | 381 |

Head frame anatomy (R2A's `frame_anatomy.py`, B token 2, `R2D/ab/runs/ab-all-tok2-frames.md` #80): 3,565 ms = style 16 + 217 + 583,
layout 32 + **1,473 (101,164 dirty)**, compositing inputs **922**, pre-paint **958**, paint LC 207, 771 transitions — vs R2A's `combined`
head frame 3,543 = 814 / 1,446 / 935 / 975 / 222.

Reading:
1. **Head lock**: correct (2/2 ids in both arms; token 2 exercised hide → unlock → capture → hide) and structurally neutral: 85 frames,
   171 passes, 1 whole-DOM pass per token, all unchanged. The whole-DOM pass itself was 470–583 ms vs 601–813 in the control (−20 to −30 %,
   provisional: different session). Per-frame phases moved ≤ 5 % — as R2A found, pre-paint/compositing inputs scale with dirty layout
   objects and paint LC with pending animations, not with idle PaintLayers, so locking an idle subtree buys nothing there.
2. **`overflow:clip`** (B − A, same session): pre-paint 22.5 vs 22.3, compositing inputs 20.1 vs 19.9, paint LC 62.0 vs 61.3, hit-test 11.2
   vs 10.7 ms/frame — unchanged; layout −6 % in both tokens (55.8 vs 59.2; 46.3 vs 49.0). The head frame is byte-for-byte the same shape
   (922/958 vs 935/975 ms). **R2A's R4 hypothesis (a PaintLayer + scrollable area per `overflow:hidden` row driving compositing inputs and
   pre-paint) is not confirmed**; those 1.9 s of the head frame are per-dirty-layout-object cost that does not depend on overflow.
   Kept ON for the small layout gain and zero observed risk.
3. **`pointer-events:none`**: hit-test unchanged (the hover hit-test is the harness mouse resting on `#run`; B1's protocol) → OFF.
4. **`contain:paint`**: added after the A/B on R2B's MB9 measurement (12.6 → 0.02 ms/frame paint walk on a 50k static subtree); not A/B'd
   here — B1 benches the READY bundle.

Harness incident: run B's node harness hung in playwright `browser.close()` after Chrome had exited normally (trace and JSON already saved,
`dataLossOccurred:false`, no crash report in `~/Library/Logs/DiagnosticReports`, renderer RSS steady 4.1 GB) and held `CHROME.lock` for
3 h until the coordinator killed it. Not the bundle (run A closed normally with the same code). Fix in `R2D/ab/run_ab.sh` and
`R2D/run_correctness.sh`: wall-clock cap (420 s A/B, 900 s correctness) + Chrome-exit watchdog (node alive 60 s after Chrome vanished →
kill, rc 124); long jobs via `nohup` + short polls.

## 4. Offline verification (`bundles/R2D`)

- Selector-level diff vs `bundles/combined` = exactly: head unlock rule swapped (`headinput` → `b11-bridge`), 3 `overflow:clip` rules,
  1 `contain:paint` rule; `index.html` byte-identical; 283 font witnesses equal (values); manifest adds the 4 `r2d*` flags;
  `launch_browser_gpt2.py --check` 285 static files / 287,459,001 B / no JavaScript.
- NumPy reference (`R2D/reference_ids.py`, verify's recipe, R2D tools copy): `[11,314,1101,7926,11,475,314,1101]` = expected.
- Emitter checks: `r2d_knobs.overflow_clip` asserts exactly one match per rule; the lock raises without `--detached-output`.

## 5. Chrome correctness runs (passive, `R2D/run_correctness.sh`, poll `#token-8-captured.done` every 5 s, one readback, `verify_browser_gpt2_runtime.py`)

| run | bundle | power / load | ids | verify |
|---|---|---|---|---|
| #1 (09:42–09:49, `R2D/run-R2D-lockclip/`) | lock + `overflow:clip` (`bundles/R2D-lockclip`, = READY bundle minus `contain:paint`) | battery 80 % discharging, load 8.4/16.4/11.2 | **[11, 314, 1101, 7926, 11, 475, 314, 1101] 8/8**, 8/8 done markers, harness wall 401.6 s (≈43 s/token at 5 s poll; not a timing run) | rc 0: tokenAgreement 8/8, originalFloatAgreement 8/8, finalResidual rmse 0.0193 / max 0.187 (= `combined`), finalHeadMatchesActualInput (1101), head list sample `"X000" -12,"X001" -4,…` unchanged, `--epoch` 8 at readback |
| **#2 (09:51–09:58, `R2D/run-R2D/`) — the READY bundle** | lock + `overflow:clip` + `contain:paint` (`bundles/R2D`) | battery 76 % discharging, load 5.0/8.6/9.3 | **[11, 314, 1101, 7926, 11, 475, 314, 1101] 8/8**, 8/8 done markers, harness wall 418.1 s (not a timing run) | rc 0: tokenAgreement 8/8, originalFloatAgreement 8/8, finalResidual rmse 0.0193 / max 0.187 (= `combined`), finalHeadMatchesActualInput (1101), head list sample unchanged; text "Hello, I'm sorry, but I'm" |

`bundles/R2D/READY` created 09:59 on run #2's 8/8. Both runs used the watchdog harness (`R2D/run_correctness.sh`); neither tripped it; Chrome exited and the lock was released normally each time.


## 6. Residual risks / follow-ups

- The head lock changes when `.detached-head-reader`'s anchor resolves (fallback 0 while hidden). The state machine tolerates both 0 and a
  stale value (§2), and 2 + 8 + 8 tokens passed, but `#head-epoch-observer` now reads 0/0 during the core (B0's final readback shows
  `headObserver {0,0}` when `--epoch` has advanced past the last captured token, e.g. in a 2-token probe; in an 8-token run `--epoch` stays 8
  and the head stays visible).
- `overflow:clip` + `min-width:0`: sizing verified by 8/8 ids (the argmax depends on every row width); no fixture beyond that.
- `contain:paint` roots: verified by the correctness run only; if a future emitter change puts an anchor or a `position:fixed` probe under
  `.head-group`/`.head-fine`/`.loop-scroll`/`.embedding-scroller`, the containing-block change would silently move it — keep the root list in
  `r2d_knobs.py` in sync.
- Timing: only 2-token traced probes (this bundle minus `contain:paint`); no untraced s/token. Expected gain is small (whole-DOM pass −0.1 to
  −0.2 s, layout −6 %/frame, plus whatever `contain:paint` gives); the 3.5 s head frame and the 85 frames/token are untouched.
- Disk: `R2D/ab/runs/ab-all-trace.json.gz` (46 MB) kept for R2A's tool; delete when B1 no longer needs it. Sibling bundles `R2D-lock`,
  `R2D-allknobs`, `R2D-lockclip` are 46 MB each (fonts relative), no READY.
