# bundles/demo-c36.next — demo-c32 (v6) + R7B: prefill head skip, capacity 36 with the "32 new tokens" stop rule, Gumbel-max sampling (seed / temperature controls)

Built by R7B on 2026-10-01 14:14 (v2 rebuild 14:30: `.pg{display:none!important}` on the stop rule — one display declaration; identity results transfer) with `work/2026-09-19/R7B/compile.sh` (= `R6X/compile.sh` + the R7B flag passthroughs; tools copy `work/2026-09-19/R7B/tools` =
`R6X/tools` (incl. the v6 `R6X_SCROLLBAR_FIX` hunk) + `r7b_features.py` + 8 call sites in `browser_gpt2_runtime.py`; diff `R7B/tools-vs-R6X.diff`). NOT swapped into
bundles/demo-c32 (`.next` is for the merge with R7H). Sizes: index.html 7,445,814 B, runtime.css 53,608,822 B; 286 font faces (271 F4 + 12 R5H dot + 2 tokenizer + 1 noise).

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R7B
# demo-c32's exports (bundles/demo-c32/BUILD.md) plus:
export R7B_PREFILL_HEAD_SKIP=1 R7B_CAPACITY_36=1 R7B_SAMPLING=1 R7B_NEW_TOKENS=32
VALUE_LAYOUT=widths R4S_SMALL_HOPS=0 ./compile.sh /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/demo-c36.next 36 12
```

## Behaviour
- Dropdown prompt (N = 0/1): 32 epochs = 32 new tokens, stop at epoch 32 ("Complete • 32 new tokens"). Typed prompt with N tokens: prefill epochs 1..N−1 skip the head (≈ −2.6 s each), the run stops at epoch 31 + N (N = 4 → 35 epochs, 32 new tokens).
- Sampling: `Seed` select (auto = click-time clock, 1..64 replay) and `Sampling` select (greedy T = 0 default / T = 0.7 / T = 1.0); the effective seed and temperature are shown after the status. Greedy is bit-identical to demo-c32. Browser Reload restores the checked Run box and restarts the clock — use Reset, or pick the shown seed to replay.
- Flags: `R7B_PREFILL_HEAD_SKIP`, `R7B_CAPACITY_36` (+ `R7B_NEW_TOKENS`), `R7B_SAMPLING` (R7B.md §1). All off + capacity 32 reproduces bundles/demo-c32 byte for byte (`R7B/twins/c32-off-v6`).

## Asset dependencies (relative url() in runtime.css)
| faces | path | owner |
|---|---|---|
| 271 | `../../F4/assets/…` | F4 (via R7B/assets → ../F4/assets) |
| 12 | `../../R5X/assets-r5h/…` | R5H dot fonts (via R7B/assets-r5h) |
| 2 | `../../R6P/assets-r6p/gpt2-token-id-{0,1}-full.ttf` | R6P (via R7B/assets-r6p) |
| 1 | `../../R7B/assets-r7b/gumbel-noise.ttf` (8,333,952 B, sha256 7d79b225…, = R7S/noise/gumbel-noise.ttf) | R7B |

## Verification: R7B.md (offline §2, Chrome §3). References: `R7B/reference_*.json`.

## Verification status (R7B, 16:58)
Greedy typed run 35/35 (AC); sampled runs seed 17 T=1.0 and seed 42 T=0.7 both 35/35 (battery, timings not comparable) — R7B.md §3.
