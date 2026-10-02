# bundles/combined6-c32 — combined6's emitter at capacity 32 with `--value-layout widths` (the 32-token demo candidate)

Built by R4M on 2026-09-21 00:47 (`VALUE_LAYOUT=widths work/2026-09-19/R4M/compile.sh tools bundles/combined6-c32 32`, 8 s). Same tools copy
`work/2026-09-19/R4M/tools` and flags as `bundles/combined6/BUILD.md`; only `--capacity 32` and `--value-layout widths` differ (coordinator 00:46:
combined6-c32 = combined4 + R4S + R4D + widths, the fastest verified 32-token configuration — `bundles/combined4-c32c` 758.7 s vs c32b 905.9 s vs
combined4-c32 1,132.9 s). **Caveat inherited from combined4-c32c (`R4D.md` §4.3)**: the widths layout is NOT bit-identical numerically to the runs layout
(constant font instance per filled slot, weight carried in the `calc-size` width: `P000` 1/16384 quantisation replaced by ≤ 0.03 px LayoutUnit snapping);
ids were verified in Chrome on the Hello trajectory (c32c) and are verified here on both the Hello and the "I" (token 40) trajectories — see the Chrome section.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4M
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export F4_PACKED_BANKS=1 F4_PACKED_HEAD=1 F4_NUMERIC_LISTS=1
export R2C_HOIST_FVS=1 R2C_HOIST_STAGES=1 R2C_HOIST_QUERY=1 R2C_HOIST_EMBEDDING=1
export R2F_LEAN_HANDSHAKE=1
export R2D_HEAD_LOCK=1 R2D_OVERFLOW_CLIP=1 R2D_POINTER_EVENTS=0 R2D_CONTAIN_PAINT=1
export R2G_SCOPED_HAS=1 R3R_FOLD_HOP=1 R3H_BLOCKFLOW_MAX=1
export R4S_SMALL_HOPS=1
export R4D_EMPTY_UNFILLED=1 R4D_LEAN_LATCH=1 R4D_UNPACK_V=1 R4D_HIDE_UNFILLED=1 R4D_GATE_SCORES=0
# (R4T_CONSUMER_CHUNK not set: R4T is not part of this bundle)
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools/browser_gpt2_runtime.py \
  --blocks 12 --capacity 32 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout widths --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined6-c32
```

Flags, merge and the tools diff: identical to `bundles/combined6/BUILD.md` (same tools copy; `R4M/tools-vs-R3M.diff`).

## Offline verification (reference builds in `work/2026-09-19/R4M/scratch/` from the same tools; `runtime.css` compared after normalising the relative `url("../…")` depth; `index.html` byte-for-byte; `R4M/compare_bundles.py`)

- **All new flags OFF (`scratch/p32-alloff`) vs `bundles/combined4-c32`: index.html byte-identical, runtime.css identical (URL-normalised), manifest differs only by the 6 new keys (false/null).**
- Union checks: only-R4S (`scratch/p32-noR4D`, R4D off) reproduces `bundles/— (no R4S c32 bundle exists; only-R4S checked by R4S's checker below)`; only-R4D (`scratch/p32w-noR4S`, R4S off) reproduces `bundles/combined4-c32c` (css + index.html identical, manifest +1/+5 keys). This bundle is the URL-normalised twin of `R4M/scratch/p32w` (0 manifest differences).
- R4S: `R4S/offline_check.py p32w p32w-noR4S 32` → `RESULT: PASS` — +384 `--fs` registrations inherits:true / −384 inherits:false, −386 progress/stamp/ready registrations, −770 score keyframes, −scroller/−reader animations/−receipt/−gate, +4 structure, +192 container-size rules, +192 publishers; elements 86,503 vs 86,315 (+188), **max depth 238 (reader 233; parser cap 512; chain 192 ≤ 250)** — also PASS on the `runs` twin (`scratch/p32` vs `p32-noR4S`). Widths vs runs (`scratch/p32w` vs `p32`): index.html identical, css differs only in the 384 `.fvs-v-H-S` leaf rules (R4D's c32c ↔ c32b finding).
- R4D: `R4D/rule_diff.py` (flag-off reference vs bundle): differing leaf-rule families = exactly R4D's BUILD.md list (KV `@property` initials, `--fc/--fr-v-S-H` registrations, `.fvs-v-H-S` leaves, bank write rules, per-write-slot `.fvs-bank` lists, `.fvs-query` lists + `--fvq-S` flags, 32 `display:none` container rules, `@property --fvs-nbase`, `.head-isolation` wall). Interaction grep: 32 fvq rules, 0 `.fvs-score-source`, 768 `var(--fvs-nbase)` rows, 192 chain containers / 384 anchors, manifest `r4dGateScores:false`.
- `font-witnesses.json`: 283/283 identical to combined4 / R4S / combined5 / combined4-c32 / c32b / c32c (keys modulo tools dir). `launch_browser_gpt2.py --check`: 285 static files, `runtimeJavaScript: false`.
- NumPy reference ids with the merged tools (`R4M/reference_ids.log`): 8-token `[11, 314, 1101, 7926, 11, 475, 314, 1101]` = expected; 32-token teacher-forced (kv_window None / 32) and free-running == the saved ctx32 ids (`R4M/reference_ids_32.json` == `R4C/reference_ids_32.json`).
- Sizes: runtime.css 51102156 B, index.html 7198372 B.

## Chrome runs (ONE passive 32-token run each, `R4M/run_c32.sh` = R4C's pattern with the R4M harness copy `R4M/bench_native.mjs`: B0/bench_native.mjs + `B0_PROMPT_TOKEN`)

### Run 1 Run 1 — default prompt "Hello" (15496) vs `R4C/reference_ids_32.json` — **32/32 ids, 872.7 s** (`R4M/run-combined6-c32/c32-run1.summary.md`)

ONE passive run, `R4M/run_c32.sh combined6-c32 c32-run1` (R4C's pattern: `R4M/bench_native.mjs` = B0's + prompt knob, keyboard trigger, heap flag ON, trace OFF, 1 Hz `#token-k-captured.done`
poll, RSS via `ps` at 1 Hz), 01:38:05–01:53:20 under `CHROME.lock` (waited 1,110 s; AC; load 6.6 at start — other agents' Chrome/compiles, comparable to c32c's 6–8).

- ids **32/32** = `R4C/reference_ids_32.json` (text "Hello, I'm sorry, but I'm not sure if you're aware of this. I'm not sure if you're aware of this. I'm not sure"); `bundles/combined6-c32/READY` created 01:53.
- **Curve** (s/token): k=1 **20.1**, 8 **18.3**, 16 **23.2**, 24 **33.4**, 32 **43.6**; total **872.7 s**; median 24.4; min 16.0 (k=2); max 45.9 (k=30). Fit tokens 2..32: **11.65 + 0.933·k** (rmse 3.0);
  style 3.9 + 0.38·k, layout 2.6 + 0.44·k, other ≈ 5.3 + 0.11·k. RSS renderer peak **6,246 MB** (before run 1,916; at end 4,692); LayoutCount 64/token flat.
- **vs the references**: combined4-c32 (R4C) 1,132.9 s (16.3 + 1.14·k); combined4-c32b (R4D flags) 905.9 s (13.4 + 0.89·k); **combined4-c32c (R4D + widths) 758.7 s (12.8 + 0.65·k, layout 2.66 + 0.27·k, RecalcStyleCount 84/token flat)**.
  combined6-c32 = c32c + R4S: faster for the first ~10 tokens (k=2–4: 16.0–16.9 vs c32c 17.7–18.4; c32c's k=8 was 21.6) but **slower overall: 872.7 vs 758.7 s (+15 %)**, the slope 0.93 vs 0.65 s/token/position.

**Finding — R4S at capacity 32 is a position-dependent loss (coordinator 01:5x; evidence = the per-token counters, no fixture needed):**
`RecalcStyleCount` per token = **126.6 + 70.8·k** (c32c: 84.3 − 0.03·k, flat; combined6 at capacity 8: 3,752 for 8 tokens ≈ 470/token, R4S alone 3,759). With R4S the 192-deep
`position:fixed; container-type:size` score chain (depth 238) resolves inside the qkv pass's layout by interleaved container recalcs, and Blink counts each one; the count grows by ≈ 71 per
filled position per token ≈ 12 layers × 6 containers per position (each position adds 12 score carriers = 6 containers whose sizes change once a slot is filled), so the interleaved recalcs
— and the layout work they trigger below the chain (768 V rows × (1+p) glyphs restyled at the container's layout) — scale with the filled positions. Layout duration slope 0.44 vs c32c's 0.27
s/token/position and style 0.38 vs 0.35 carry the difference: at k ≥ 12 the added interleaved work outweighs the removed score-readback pass (−12 passes, −6 frames/token — the −0.6 s that R4S
wins at capacity 8, where the chain is 48 deep and p ≤ 8). Consequence: **combined7-c32 is rebuilt WITHOUT R4S** (= combined4-c32c + R4T) and combined7 (capacity 8) keeps R4S for B5's bench;
a capacity-32 R4S would need a chain whose cost does not grow with p (e.g. containers only for filled slots, or the V rows outside the chain's subtree).

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20.1 | 20 | 11 | Y | 217 | 65 | 7.5 | 4.6 | 17.6 | 3927 | 3927 |
| 2 | 16.0 | 36 | 314 | Y | 228 | 64 | 5.7 | 4.7 | 16.0 | 4322 | 4050 |
| 3 | 16.6 | 53 | 1101 | Y | 360 | 64 | 5.8 | 5.0 | 16.6 | 4571 | 4567 |
| 4 | 16.9 | 70 | 7926 | Y | 372 | 64 | 5.7 | 5.4 | 17.0 | 4891 | 4424 |
| 5 | 23.6 | 93 | 11 | Y | 504 | 64 | 10.3 | 6.7 | 23.5 | 3913 | 1987 |
| 6 | 22.5 | 116 | 475 | Y | 516 | 64 | 8.8 | 7.2 | 22.4 | 4488 | 4488 |
| 7 | 18.2 | 134 | 314 | Y | 648 | 64 | 6.0 | 6.2 | 18.1 | 5526 | 5526 |
| 8 | 18.3 | 152 | 1101 | Y | 660 | 64 | 6.3 | 6.1 | 18.2 | 5770 | 5770 |
| 9 | 19.0 | 171 | 407 | Y | 792 | 64 | 6.1 | 7.0 | 19.1 | 5916 | 5916 |
| 10 | 18.9 | 190 | 1654 | Y | 804 | 64 | 6.2 | 6.5 | 18.6 | 6149 | 6144 |
| 11 | 18.7 | 209 | 611 | Y | 936 | 64 | 6.7 | 6.4 | 19.0 | 6116 | 5935 |
| 12 | 20.2 | 229 | 345 | Y | 948 | 64 | 6.7 | 7.6 | 20.5 | 6246 | 5844 |
| 13 | 21.5 | 251 | 821 | Y | 1080 | 64 | 7.0 | 7.4 | 20.8 | 6071 | 5595 |
| 14 | 23.3 | 274 | 3910 | Y | 1092 | 64 | 8.9 | 7.9 | 23.3 | 6036 | 5161 |
| 15 | 22.6 | 297 | 286 | Y | 1224 | 64 | 8.2 | 7.8 | 22.4 | 5734 | 5476 |
| 16 | 23.2 | 320 | 428 | Y | 1236 | 64 | 8.2 | 8.4 | 23.0 | 6052 | 5303 |
| 17 | 25.2 | 345 | 13 | Y | 1368 | 64 | 9.3 | 9.2 | 25.1 | 5810 | 5472 |
| 18 | 25.7 | 371 | 314 | Y | 1380 | 64 | 9.8 | 9.0 | 25.5 | 5549 | 5403 |
| 19 | 29.1 | 400 | 1101 | Y | 1512 | 64 | 12.4 | 9.7 | 29.0 | 6020 | 5920 |
| 20 | 27.3 | 427 | 407 | Y | 1524 | 64 | 10.7 | 9.4 | 26.9 | 5900 | 5826 |
| 21 | 29.3 | 456 | 1654 | Y | 1656 | 64 | 13.0 | 9.4 | 29.4 | 5852 | 5852 |
| 22 | 28.4 | 485 | 611 | Y | 1668 | 64 | 11.1 | 9.9 | 28.0 | 5751 | 4920 |
| 23 | 30.7 | 515 | 345 | Y | 1800 | 64 | 12.9 | 10.6 | 30.5 | 5521 | 4731 |
| 24 | 33.4 | 549 | 821 | Y | 1812 | 64 | 13.3 | 13.2 | 34.1 | 5572 | 5256 |
| 25 | 39.1 | 588 | 3910 | Y | 1786 | 62 | 11.5 | 17.2 | 36.6 | 5755 | 3022 |
| 26 | 38.4 | 626 | 286 | Y | 2114 | 66 | 17.6 | 13.7 | 39.5 | 4305 | 2420 |
| 27 | 36.4 | 663 | 428 | Y | 2088 | 64 | 14.3 | 14.3 | 36.1 | 5070 | 4278 |
| 28 | 39.5 | 702 | 13 | Y | 2100 | 64 | 14.9 | 16.9 | 39.4 | 4645 | 4579 |
| 29 | 40.4 | 742 | 314 | Y | 2232 | 64 | 14.1 | 17.8 | 39.7 | 4942 | 4826 |
| 30 | 45.9 | 788 | 1101 | Y | 2244 | 64 | 13.9 | 22.9 | 45.7 | 4791 | 3263 |
| 31 | 40.8 | 829 | 407 | Y | 2376 | 64 | 15.5 | 17.0 | 40.3 | 4901 | 4806 |
| 32 | 43.6 | 873 | 1654 | Y | 2180 | 60 | 20.2 | 13.4 | 41.9 | 4850 | 4692 |

### Run 2 Run 2 — prompt token 40 ("I") via `B0_PROMPT_TOKEN=40` vs `R4P/reference_ids_32_40.json`

ONE passive run, `B0_PROMPT_TOKEN=40 REF_JSON=R4P/reference_ids_32_40.json R4M/run_c32.sh combined6-c32 c32-run2-p40`, 01:53:22–02:09:42 under `CHROME.lock` (AC; load 4.9–6.1).
The harness picked `<option value="40">` ("I") with Playwright `selectOption` before Run and verified `select.value = "40"` and body `--prompt-token = 40` (`prompt-selected` event); the page stays JS-free.

- ids **32/32** = `R4P/reference_ids_32_40.json` (free-running == teacher-forced reference); decoded text (`R4M/decode_ids.py`):
  **"I.\n\nThe first thing I did was to go to the local grocery store and buy a bag of frozen yogurt. I was so excited to try it."** — the non-looping demo text. No mismatch → no margin analysis needed
  (R4P's smallest margin on this trajectory is 9 at positions 20 and 26, `R4P/margins.json["40"]`). Appended to `bundles/combined6-c32/READY`.
- **Curve** (s/token): k=1 **20.0**, 8 **18.3**, 16 **25.3**, 24 **36.1**, 32 **46.1**; total **936.6 s**; median 27.6; min 15.9 (k=2); max 46.2. Fit tokens 2..32: **11.69 + 1.051·k** (rmse 2.3);
  style 2.9 + 0.52·k, layout 3.3 + 0.41·k. RSS renderer peak **6,212 MB**. RecalcStyleCount/token **126.4 + 70.8·k** — identical to run 1's fit (the R4S term does not depend on the prompt),
  LayoutCount 64/token flat.
- vs run 1 (Hello, 872.7 s, 0.93·k): +64 s / +7 %, the slope 1.05 vs 0.93 s/token/position with the same intercept — the "I" trajectory's tokens are costlier per position (style +0.14·k), consistent
  with a content-dependent term (distinct ids → more distinct V-glyph font instances / head work) on top of the R4S position term; same 32/32 correctness.

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20.0 | 20 | 13 | Y | 219 | 67 | 7.7 | 4.6 | 18.0 | 3898 | 3898 |
| 2 | 15.9 | 36 | 198 | Y | 226 | 62 | 5.4 | 4.6 | 15.4 | 4623 | 4623 |
| 3 | 16.8 | 53 | 198 | Y | 360 | 64 | 6.1 | 4.9 | 16.9 | 5117 | 4215 |
| 4 | 21.8 | 75 | 464 | Y | 372 | 64 | 8.6 | 6.7 | 22.2 | 4433 | 967 |
| 5 | 21.2 | 96 | 717 | Y | 504 | 64 | 7.2 | 7.0 | 20.5 | 4259 | 4253 |
| 6 | 17.6 | 113 | 1517 | Y | 516 | 64 | 6.2 | 5.4 | 17.5 | 5187 | 5187 |
| 7 | 18.0 | 131 | 314 | Y | 648 | 64 | 6.5 | 5.6 | 18.0 | 5566 | 5561 |
| 8 | 18.3 | 150 | 750 | Y | 660 | 64 | 6.4 | 5.8 | 18.2 | 5679 | 5667 |
| 9 | 19.1 | 169 | 373 | Y | 792 | 64 | 7.0 | 6.3 | 19.5 | 6068 | 6016 |
| 10 | 21.9 | 191 | 284 | Y | 804 | 64 | 7.1 | 7.7 | 21.3 | 5879 | 5278 |
| 11 | 21.7 | 212 | 467 | Y | 936 | 64 | 8.0 | 7.1 | 21.6 | 5804 | 5770 |
| 12 | 21.8 | 234 | 284 | Y | 948 | 64 | 7.6 | 7.5 | 21.8 | 5872 | 5872 |
| 13 | 23.3 | 257 | 262 | Y | 1080 | 64 | 8.4 | 8.3 | 23.6 | 6073 | 6009 |
| 14 | 24.2 | 282 | 1957 | Y | 1092 | 64 | 8.1 | 8.7 | 24.0 | 6110 | 5783 |
| 15 | 25.4 | 307 | 16918 | Y | 1224 | 64 | 10.0 | 8.3 | 25.4 | 5984 | 5686 |
| 16 | 25.3 | 332 | 3650 | Y | 1236 | 64 | 8.1 | 9.8 | 25.1 | 6212 | 4962 |
| 17 | 30.5 | 363 | 290 | Y | 1368 | 64 | 10.5 | 12.1 | 30.0 | 5363 | 4065 |
| 18 | 30.3 | 393 | 2822 | Y | 1380 | 64 | 12.8 | 10.0 | 30.1 | 5179 | 4191 |
| 19 | 29.7 | 423 | 257 | Y | 1512 | 64 | 11.0 | 11.3 | 29.4 | 4905 | 4781 |
| 20 | 30.3 | 453 | 6131 | Y | 1524 | 64 | 16.1 | 10.2 | 33.7 | 4743 | 4560 |
| 21 | 33.9 | 487 | 286 | Y | 1656 | 64 | 12.2 | 10.8 | 30.3 | 4539 | 3126 |
| 22 | 36.5 | 524 | 12912 | Y | 1668 | 64 | 15.4 | 13.1 | 36.3 | 4774 | 3360 |
| 23 | 35.3 | 559 | 32132 | Y | 1654 | 62 | 15.9 | 10.7 | 34.3 | 4802 | 3830 |
| 24 | 36.1 | 595 | 13 | Y | 1958 | 66 | 16.2 | 12.9 | 37.3 | 5299 | 4291 |
| 25 | 35.4 | 630 | 314 | Y | 1944 | 64 | 15.2 | 11.6 | 34.6 | 4856 | 3067 |
| 26 | 40.2 | 671 | 373 | Y | 1956 | 64 | 15.3 | 16.3 | 39.7 | 4683 | 4109 |
| 27 | 43.5 | 714 | 523 | Y | 2088 | 64 | 20.8 | 14.5 | 43.7 | 4549 | 4154 |
| 28 | 43.7 | 758 | 6568 | Y | 2100 | 64 | 21.2 | 13.6 | 42.9 | 4342 | 4030 |
| 29 | 43.3 | 801 | 284 | Y | 2232 | 64 | 15.0 | 19.7 | 43.0 | 4288 | 3836 |
| 30 | 43.2 | 844 | 1949 | Y | 2244 | 64 | 15.1 | 19.3 | 42.9 | 4326 | 4155 |
| 31 | 46.2 | 890 | 340 | Y | 2376 | 64 | 22.4 | 14.8 | 45.8 | 4315 | 3913 |
| 32 | 46.1 | 937 | 13 | Y | 2180 | 60 | 21.8 | 14.0 | 44.6 | 4224 | 3680 |


