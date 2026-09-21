# R3K — harness fix: keyboard trigger removes the forced per-frame hover pass

Agent R3K, 2026-09-20 21:20–21:50. Scope: one env-gated edit to `B0/bench_native.mjs` (backup `B0/bench_native.mjs.pre-keyboard`, diff
`R3K/bench_native.keyboard.diff`), scratch under `R3K/` (`run_pair.sh`, `frame_anatomy.py` = R2A's + token-1 window + `r3k` hover summary,
`runs/combined3-{click,keyboard}.*`). Log `R3K.log.md`. Nothing else touched; B4's driver NOT modified (see §4).

## 1. What changed in `B0/bench_native.mjs` (default behaviour unchanged)

`B0_TRIGGER` (new; default `click`):
- `click` = exactly the previous path: `DOM.getBoxModel(#run)` → `Input.dispatchMouseEvent` mousePressed/mouseReleased → mouseoff park (`B0_MOUSEOFF`, default −50,−50).
- `keyboard` = `DOM.focus(#run)` (before the `P2-run` mark, one-time pre-run) → `Input.dispatchKeyEvent` keyDown(text " ", code Space, vk 32) + keyUp.
  **No `Input.dispatchMouseEvent` is ever sent**, so `MouseEventManager::IsMousePositionUnknown()` stays true and Blink skips the post-layout hover update.
  Result JSON gains `trigger`; `mouseOff.mode` reads `"none (keyboard trigger, no mouse event dispatched)"`. Any other value throws.
`node --check` passes. Running benches (B4) keep `click` until the env is set.

## 2. Measurement — TWO 2-token light-traced sessions of `bundles/combined3` under the lock (21:24:47–21:37:01, AC, load ≈ 3.9)

`R3K/run_pair.sh combined3 240`: one server, `B0_CAPACITY=2 B0_TRACE=1 B0_HEAP=1 B0_CAP_MS=240000`, arm 1 `B0_TRIGGER=click` (mouseoff default), arm 2 `B0_TRIGGER=keyboard`.
Parsed with `B0/parse_trace.py` (token bounds = `--saved-token-N` latches) + `R3K/frame_anatomy.py` for tokens 1 and 2 (`R3K/runs/combined3-<arm>-tok<k>-frames.{json,md}`).

**Both arms: ids `11, 314` (= combined3's first two tokens of "Hello, I'm sorry, but I'm"), `#token-1/2-captured.done` 2/2, `--saved-token-1/2` = 11/314, run-latched.**
The keyboard arm STARTED the page from the key event (`run-keyed` 4.81 s after nav; token 1 captured 26.65 s later).

| token | arm | frames | wall s | style passes | 0-elem passes (ms) | 1-elem passes | layouts | `handleMouseMoveEvent` incl ms | `LayoutView::HitTest` ms | UpdateLayoutTree ms | Layout ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 (run→latch 1) | click+mouseoff | 51 | 29.85 | 131 | **39 (613)** | 2 | 88 | **679** | 677 | 15,411 | 4,534 |
| 1 | keyboard | 51 | 26.43 | 94 | **0 (0)** | 3 | 89 | **0** | 0 | 13,413 | 4,307 |
| 2 (latch 1→latch 2) | click+mouseoff | 46 | 25.64 | 132 | **42 (661)** | 2 | 87 | **723** | 722 | 10,619 | 4,732 |
| 2 | keyboard | 46 | 23.13 | 89 | **0 (0)** | 1 | 87 | **0** | 0 | 9,293 | 4,482 |

- Hit tests at the parked pointer (`-50,-50`, `move=true`, node null): click arm 46 / 44 per token; keyboard arm **0**. The remaining hit tests (`450,150` and `450,270` on `HTML`,
  15–18 each per token, ≈ 10 ms/token) are present identically in BOTH arms (not mouse-driven; viewport-centre probes) — not a trigger artifact.
- Non-hover pass sequence (element counts in order) is **identical** between arms for the whole layer loop (`126, 6919, 780, 3089, 784, 1553, 2323 … 2326, 50892 … 863, 2342`;
  token 2: 90 vs 89 passes). The only difference: the token-boundary SMIL frame's `1, 6` (click) becomes one `7`-element pass (keyboard) — the forced hover
  `UpdateStyleAndLayout` was splitting that frame's recalc in two. Token 1 keyboard additionally shows `1, 40, 1` right at the start (focus ring / `:focus-visible` + checkbox toggle,
  the harness's own start, ≈ 1 ms) where the click arm has the click's `150,28 INPUT#run` hit tests instead.
- Frame count identical (51 / 46), layout count identical (87 / 87 in token 2), style/layout structure otherwise byte-for-byte R3F §1's.

**Measured saving (harness artifact removed): 0.68 s (token 1) / 0.72 s (token 2) per token = `EventHandler::handleMouseMoveEvent` inclusive (0-element pass 613–661 ms
+ ~60 ms hit test), i.e. 42–44 forced `UpdateStyleAndLayout` calls/token gone (UpdateStyleAndLayout 133 → 89).** This matches R3F §2.3's estimate (≈ 0.62 s). The wall
difference in this single pair (−3.4 / −2.5 s) and the UpdateLayoutTree total (−2.0 / −1.3 s) exceed that because the arms ran 6 min apart on a loaded machine (load ≈ 4,
cua-driver at 45 % CPU); only the hover terms are attributable with certainty — they are exactly zero in the keyboard arm.

## 3. Verdict

Hypothesis confirmed: starting the run without any mouse event removes every forced hover pass (44/token → 0) and its hit test, with identical ids, identical frame count,
identical layouts and an otherwise identical pass sequence. Pure harness artifact worth **≈ 0.7 s/token (≈ 3 % of combined3's ≈ 24 s)** on every bench row taken so far
(mouseoff rows included).

## 4. Recommendation for B4 (not applied by R3K)

Switch BOTH arms of every subsequent pair to the keyboard trigger; never split a pair across trigger modes (an in-flight `ref, cand` pair must finish in `click` before the switch).
Exact one-line change in `B4/paired4.sh` line 43 (the only `run_bench.sh` call; `run_bench.sh` passes the environment through to `bench_native.mjs` unchanged):

    B0_FORCE=0 B0_TRIGGER=keyboard $B/run_bench.sh $bundle $label 1 0 600000 > $D/$bundle-$label.out 2>&1; rc=$?

(equivalently `export B0_TRIGGER=keyboard` at the top of `paired4.sh`), then restart the driver at a pair boundary (`nohup zsh B4/paired4.sh &` is idempotent). Annotate the
new rows "trigger=keyboard (no hover pass; −0.7 s/token vs mouseoff rows)" — absolute s/token is not comparable to earlier rows, paired Δ is. Optional cosmetic: add
`trigger=${B0_TRIGGER:-click}` to `run_bench.sh`'s START logline / `bench_bundle.sh`'s notes so the config is recorded (both currently print only `mouseoff`).

## 5. Hazards noted

- Both 2-token harness runs hung in the final `browser.close()` after `saved` (JSON + trace complete) until `run_pair.sh`'s outer watchdog (cap + 120 s) killed them, so the lock
  was held ≈ 12 min instead of ≈ 5. Specific to stopping at `B0_CAPACITY=2` while the renderer is still mid-token-3 (B0's 8-token runs end on the page's own completion);
  anyone reusing `B0_CAPACITY<8` should keep a Chrome-gone/close watchdog like `R3F/run_chrome.sh`'s.
- `R2A/frame_anatomy.py` cannot parse token 1 (`bounds[0]` missing); `R3K/frame_anatomy.py` sets it to the run mark.
