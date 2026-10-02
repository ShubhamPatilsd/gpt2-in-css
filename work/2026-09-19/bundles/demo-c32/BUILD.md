# bundles/demo-c32 — round 8 (R8U): production page layout on the round-7 bundle (model, controls and handshakes unchanged)

Built by R8U on 2026-10-02 with `work/2026-09-19/R8U/compile.sh` (= `R7X/compile.sh` + the `R8U_LAYOUT` passthrough, default 1; tools copy
`work/2026-09-19/R8U/tools` = `R7X/tools` + `r8u_layout.py` + module constants `PANEL_TOP`/`TOKENS_TOP` (r6p_prompt.py) and `WARN_TOP`
(r7h_id_guard.py) whose defaults are the old literals + the R8U block in `browser_gpt2_runtime.py`). `R8U_LAYOUT=0` rebuilds the round-7 bundle
byte for byte (index.html + runtime.css; R8U.md §2).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R8U
export R7B_PREFILL_HEAD_SKIP=1 R7B_CAPACITY_36=1 R7B_SAMPLING=1 R7B_NEW_TOKENS=32 R7H_ID_GUARD=1 R6X_SCROLLBAR_FIX=1 R8U_LAYOUT=1
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 ./compile.sh <out> 36 12
```

Layout (R8U.md §1): title "GPT-2 in CSS" + one muted line (status small at the top right); one row "Prompt [dropdown] or type: [the
unchanged `.tk-root { --draft-prompt: "…"; }` editor] [Run / continue] [Reset]"; token chips under the editor; a quiet native
`<details>` "Options ▸" line with Seed / Sampling / readout; small progress line + 4 px bar; generated text 22 px; footer = practical notes.
DOM of .controls unchanged except one `<details class="r8u-opt">` after Reset; new body child `<header class="r8u-head">` (exempt from the
early-paint lock, styled inline). Offline: model core rules identical in multiset and order (R8U/check_layout_diff.py), witnesses identical,
static no-JS rc 0, pack dry-run resolves every url(). Previous BUILD.md (round 7) follows.

---

# bundles/demo-c32 — the shareable demo, round 7: **capacity 36 → 32 new tokens** (R7B: prefill head skip, "32 new tokens" stop rule, Gumbel-max sampling with seed / temperature controls) + **R7H id guard** (geometry self-check: calibration metric + echo-vs-latched agreement gates) on demo-c32 v6 (R6X: typed prompts N ≤ 4, progress UI, scrollbar fix). The bundle keeps the name `demo-c32` (the one the user knows); the context capacity is 36 = up to 4 prompt tokens + 32 new tokens.

Built by R7X on 2026-10-01 18:06 with `work/2026-09-19/R7X/compile.sh` (= `R7B/compile.sh` + the `R7H_ID_GUARD` / `R6X_SCROLLBAR_FIX` passthroughs; tools copy `work/2026-09-19/R7X/tools` =
`R7B/tools` (= `R6X/tools` v6 + `r7b_features.py` + 8 call sites, `R7B/tools-vs-R6X.diff`) + `R7H/r7h_id_guard.py` + the 2-line hook right after `feedback(capacity)` in `browser_gpt2_runtime.py`
(`R7X/apply_guard_r7x.py` = `R7H/apply_guard.py` pointed at this tools dir; diff vs R7B/tools: `R7X/tools-vs-R7B.diff`, 3 lines). Sizes: index.html 7,445,896 B, runtime.css 53,627,357 B; 286 font faces (271 F4 + 12 R5H dot + 2 tokenizer + 1 Gumbel-noise).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R7X
# demo-c32 v6's exports (previous BUILD.md: bundles/demo-c32.prev/BUILD.md) plus:
export R7B_PREFILL_HEAD_SKIP=1 R7B_CAPACITY_36=1 R7B_SAMPLING=1 R7B_NEW_TOKENS=32
export R7H_ID_GUARD=1 R6X_SCROLLBAR_FIX=1
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 ./compile.sh /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/demo-c32.next 36 12
```

## Behaviour
- Dropdown prompt (N = 0/1): 32 epochs = 32 new tokens, stop at epoch 32 ("Complete • 32 new tokens"). Typed prompt with N ≤ 4 tokens: prefill epochs 1..N−1 skip the vocabulary head (progress text "absorbing prompt token e of N"), the run stops at epoch 31 + N (N = 4 → 35 epochs, always 32 new tokens).
- Sampling: `Seed` select (auto = click-time clock, 1..64 to replay) and `Sampling` select (greedy T = 0 default / T = 0.7 / T = 1.0); the effective seed and temperature are shown after the status. Greedy is bit-identical to demo-c32 v6's head. Browser Reload keeps the checked Run box and restarts the clock from 0 → seed 1 — use Reset, or pick the shown seed to replay.
- Guard (R7H.md §3): `.feedback-metric-cal` (constant id 50256) must decode exactly or `#token-e-ready` is blocked and the red panel "Geometry self-check failed" shows; per slot, `#token-e-ack` waits until the echoed id equals the latched `--saved-token-e`. Zero added frames; +2 elements, +1 timeline, +38 animations (36 slots), ≈+18 KB CSS. Prefill-skip epochs latch −1 and echo −1 → agreement holds; the stop rule's `#token-t-ack{animation:none!important}` and the guard's gates are both suppressions (no conflict).
- Flags: `R7B_PREFILL_HEAD_SKIP`, `R7B_CAPACITY_36` (+ `R7B_NEW_TOKENS`), `R7B_SAMPLING` (R7B.md §1); `R7H_ID_GUARD` (R7H.md §3); `R6X_SCROLLBAR_FIX` (R6X.md §11). Guard off at capacity 36 reproduces `bundles/demo-c36.next` byte for byte; R7B flags off at capacity 32 reproduces `bundles/demo-c32.r7h` byte for byte (R7X.md §2).

## Asset dependencies (relative url() in runtime.css; `R6L/pack_bundle.py … --dry-run`: all 286 resolve, 250,716,836 B)
| faces | path | owner |
|---|---|---|
| 271 | `../../F4/assets/…` and `../../../../experiments/…` (weights, embedding lookup 56.9 MB, head faces) | F4 (via R7X/assets → ../F4/assets) |
| 12 | `../../R5X/assets-r5h/font-vector-operators-r5h/dot-h*-…-f4-r5h.woff2` | R5H dot fonts (via R7X/assets-r5h) |
| 2 | `../../R6P/assets-r6p/gpt2-token-id-{0,1}-full.ttf` | R6P (via R7X/assets-r6p) |
| 1 | `../../R7B/assets-r7b/gumbel-noise.ttf` (8,333,952 B, sha256 7d79b225…, = R7S/noise/gumbel-noise.ttf) | R7B (via R7X/assets-r7b) |

## Verification: R7X.md (offline §2: identity twins, guard diff, static no-JS, witnesses, references; Chrome §3, gated, incl. the mandatory HEADED scrollbars-shown arm). READY is written only after the Chrome set passes. History of the previous live bundle (v1–v6): `bundles/demo-c32.prev/BUILD.md`.

## Verification status (R7X, 2026-10-01 21:17:34) — PASS, swapped in as bundles/demo-c32
Offline R7X.md §2 (all PASS). Chrome R7X.md §3: HEADED 1100×700 with classic scrollbars SHOWN, typed "Shubham was" T = 0 → **35/35** (32 new tokens, position 14 = 17132), guard `--fb-ok` 1 / 36 agreement gates 1 / scroller 524288; HEADED + scrollbars Hello seed 17 T = 1.0 → **32/32** vs the NumPy sampled reference; headless typed "I" → **32/32**; load-paint probe Ready at 2.2 s with the controls painted at 0.5 s and "absorbing prompt token 2 of 4" mid-prefill. All timings on battery or with 4.7–5.7 GB swap: not comparable with R7B's AC numbers (demo-c36 typed Once T = 0: 1,034.9 s / 35 epochs). Known display nit (pre-existing, R6P footer): "at most 36 generated tokens" prints the capacity; the run yields 32 new tokens.
