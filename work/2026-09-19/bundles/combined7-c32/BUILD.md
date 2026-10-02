# bundles/combined7-c32 — combined4-c32c + R4T consumer re-chunk (capacity 32, `--value-layout widths`, R4D flags, **R4S_SMALL_HOPS=0**)

REBUILT by R4M on 2026-09-21 01:58 (`R4S_SMALL_HOPS=0 R4T_CONSUMER_CHUNK=64 VALUE_LAYOUT=widths work/2026-09-19/R4M/compile.sh tools7 bundles/combined7-c32 32`) **without R4S**
(coordinator 01:5x: combined6-c32's run 1 showed R4S's interleaved container recalcs scaling with the filled positions at capacity 32 — RecalcStyleCount/token 126.6 + 70.8·k, total 872.7 s vs
c32c's 758.7 s; `R4M.md` §4.1). The first build (with R4S, 01:44) is kept as `R4M/scratch/combined7-c32-withR4S/` for the record. Same tools copy as `bundles/combined7/BUILD.md`;
`--capacity 32`, `--value-layout widths` and `R4S_SMALL_HOPS=0` differ (same caveat as `bundles/combined6-c32/BUILD.md`: widths numerics are not bit-identical;
ids are the acceptance). R4T's capacity-32 warning (every consumer ≤ 64 animations; any other `inherits:false` number forwarded one level) is checked in `R4M.md` §6.

```sh
cd /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/R4M
# combined6's exports (bundles/combined6/BUILD.md) plus:
export R4T_CONSUMER_CHUNK=64 R4S_SMALL_HOPS=0
# i.e. R4S_SMALL_HOPS=0 R4T_CONSUMER_CHUNK=64 VALUE_LAYOUT=widths ./compile.sh tools7 bundles/combined7-c32 32
uv run --with numpy --with fonttools --with pillow --with brotli \
  python tools7/browser_gpt2_runtime.py \
  --blocks 12 --capacity 32 --reuse-core --cache-codec font-vector \
  --cache-layout flat --scoped-state --isolate-head --detached-output \
  --value-layout widths --font-backend original \
  --output /Users/shubhampatil/Documents/programming/gpt2-css/work/2026-09-19/bundles/combined7-c32
```

Flags, merge and the tools diff: see `bundles/combined7/BUILD.md` (`R4M/tools7-vs-R3M.diff`).

## Offline verification

- **`R4T_CONSUMER_CHUNK=0` (`R4M/scratch/p7-32w-noR4S-noR4T`) reproduces `bundles/combined4-c32c` byte-for-byte** (index.html; runtime.css URL-normalised; manifest +`r4sSmallHops:false`, `r4tConsumerChunk:0`).
- `R4T/offline_check_r4t.py bundles/combined7-c32 bundles/combined4-c32c` → `R4M/offline_check_r4t-combined7-c32-noR4S.log`: vs `bundles/combined4-c32c` all substantive checks pass (max 64 animations/element — `.fvs-score-reader` 384 is the untouched R4S-less score reader; loop-reader forwards 4,224; consumer elements 1,200 vs 164; elements +124; non-consumer CSS identical; HTML identical modulo wrappers; witnesses 283/283) and the only FAIL line is the manifest carrying the extra key `r4sSmallHops:false` (the merged tools include the R4S module; c32c's manifest has no such key). Re-run against the flag-off twin `R4M/scratch/p7-32w-noR4S-noR4T` (manifest with the key): manifest check passes and the only FAIL is the checker's raw (non-URL-normalised) CSS compare tripping on the scratch dir's one-level-deeper `url("../../../../…")` font paths — a path-depth artefact, not content (`compare_bundles.py` shows the twin identical to c32c after URL normalisation). Net: R4T's structural checks pass for combined7-c32 (`R4M/offline_check_r4t-combined7-c32-noR4S.log`, `…-vs-flagoff.log`) (the earlier R4S build's check vs combined6-c32 passed: `R4M/offline_check_r4t-combined7-c32.log`).
- Witnesses 283/283 identical to combined4-c32c; `launch_browser_gpt2.py --check`: 285 static files, `runtimeJavaScript: false`.
- Sizes: runtime.css 51329116 B, index.html 7202616 B.

## Chrome runs (via `R4M/run_chain7.sh`, ONE passive 32-token run each: run A = prompt 40 "I" (`B0_PROMPT_TOKEN=40`) vs `R4P/reference_ids_32_40.json` — the demo, READY gate; run B = Hello vs `R4C/reference_ids_32.json` for comparability with c32c / combined6-c32)

Protocol as §4 (`R4M/run_c32.sh`, ONE passive run each, keyboard trigger, heap flag ON). **Caveat: the machine was in active user use from ≈ 02:15 (load 8–30 at run A's start, `{ 8.35 18.17 14.11 }`;
run B started at `{ 7.56 6.50 8.0 }`) — absolute times from runs A/B/C are inflated relative to the 01:38–02:09 combined6-c32 runs (load 5–7) and R4D's c32c run (load 6–8).** RecalcStyleCount per token is
load-independent and flat at 84 for all no-R4S bundles (c32c, combined7-c32); style/layout durations are CDP main-thread times (contention-sensitive but not idle-inflated).

| run | bundle (capacity 32, widths) | R4S | R4T | prompt | ids | total s | k=1 / 8 / 16 / 24 / 32 s | fit tokens 2..32 | style s/token | layout s/token | RecalcStyle/token | RSS peak MB |
|---|---|---|---|---|---|---:|---|---|---|---|---|---:|
| R4D c32c-run1 (01:0x) | `combined4-c32c` | – | – | Hello | 32/32 | **758.7** | 22.0 / 17.7 / 21.3 / 26.9 / 35.2 | 12.8 + 0.65·k | 4.46 + 0.30·k | 2.66 + 0.27·k | 84 flat | 7,226 |
| R4M.md §4.1 run 1 (01:38) | `combined6-c32` | on | – | Hello | 32/32 | 872.7 | 20.1 / 18.3 / 23.2 / 33.4 / 43.6 | 11.65 + 0.93·k | 3.87 + 0.38·k | 2.59 + 0.44·k | 126.6 + 70.8·k | 6,246 |
| R4M.md §4.2 run 2 (01:53) | `combined6-c32` | on | – | 40 "I" | 32/32 | 936.6 | 20.0 / 18.3 / 25.3 / 36.1 / 46.1 | 11.69 + 1.05·k | 2.94 + 0.52·k | 3.30 + 0.41·k | 126.4 + 70.8·k | 6,212 |
| **run A** (02:30) | `combined7-c32` | off | 64 | 40 "I" | 32/32 | 1,050.1 | 22.3 / 24.7 / 33.1 / 37.9 / 49.7 | 15.8 + 1.02·k | **8.07** + 0.44·k | 3.11 + 0.47·k | 84 flat | 3,878 |
| **run B** (02:46) | `combined7-c32` | off | 64 | Hello | 32/32 | 929.7 | 21.7 / 19.1 / 30.9 / 35.3 / 47.4 | 11.1 + 1.07·k | 4.00 + 0.56·k | 3.21 + 0.38·k | 84 flat | 5,253 |
| **run C** (chain C) | `combined4-c32c` | – | – | 40 "I" | PENDING-RUNC-IDS | PENDING-RUNC-TOTAL | PENDING-RUNC-CURVE | PENDING-RUNC-FIT | PENDING-RUNC-STYLE | PENDING-RUNC-LAYOUT | 84 flat | PENDING-RUNC-RSS |

- **R4T (consumer re-chunk) is a regression at 12 layers**: with R4S off and everything else equal to c32c, run B (Hello) took 929.7 s vs c32c's 758.7 s (+23 %) and run A (prompt 40) 1,050 s; the
  style intercept doubles on run A (8.07 vs 4.46 s/token — 1,200 consumer elements instead of 164, each a style-recalc root with its own animation set, plus 4,224 `--lp-*:inherit` forwards
  per pass) and the style slope rises (0.44–0.56 vs 0.30). This matches B5's first paired R4T row (+2.3 s/token at capacity 8). Part of the absolute gap is the load caveat, but the style-time
  structure (flat RecalcStyleCount, higher style duration per pass) is not load-shaped. `bundles/combined7-c32/READY` exists (32/32 on both prompts) but **combined7-c32 is not the demo**.
- **combined6-c32 vs combined7-c32**: both slower than c32c for opposite reasons — R4S's position-dependent interleaved recalcs (§4.1) vs R4T's per-pass style cost.
- **Fastest verified prompt-40 demo: PENDING-DEMO-VERDICT**

**Run A per-token table (combined7-c32, prompt 40):**

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 22.3 | 22 | 13 | Y | 87 | 79 | 9.7 | 4.3 | 19.4 | 3675 | 3675 |
| 2 | 16.2 | 38 | 198 | Y | 84 | 76 | 6.9 | 4.2 | 16.1 | 3878 | 3850 |
| 3 | 17.5 | 56 | 198 | Y | 84 | 76 | 7.9 | 4.5 | 17.5 | 3805 | 3673 |
| 4 | 18.2 | 74 | 464 | Y | 82 | 74 | 8.1 | 5.2 | 18.3 | 3625 | 3470 |
| 5 | 21.2 | 95 | 717 | Y | 84 | 76 | 10.0 | 5.5 | 20.7 | 3554 | 3453 |
| 6 | 21.9 | 117 | 1517 | Y | 84 | 76 | 10.8 | 5.8 | 21.9 | 3446 | 3287 |
| 7 | 22.7 | 140 | 314 | Y | 84 | 76 | 11.0 | 6.3 | 22.6 | 3493 | 2874 |
| 8 | 24.7 | 165 | 750 | Y | 84 | 76 | 12.8 | 6.5 | 24.7 | 3579 | 2494 |
| 9 | 25.2 | 190 | 373 | Y | 82 | 74 | 11.5 | 8.0 | 24.9 | 3548 | 2428 |
| 10 | 27.5 | 217 | 284 | Y | 86 | 78 | 14.4 | 9.1 | 29.6 | 3480 | 3155 |
| 11 | 28.7 | 246 | 467 | Y | 82 | 74 | 9.8 | 10.0 | 25.6 | 3543 | 3477 |
| 12 | 27.1 | 273 | 284 | Y | 86 | 78 | 15.9 | 8.0 | 30.2 | 3502 | 2865 |
| 13 | 29.4 | 302 | 262 | Y | 84 | 76 | 15.6 | 8.1 | 30.1 | 3545 | 3003 |
| 14 | 31.1 | 334 | 1957 | Y | 84 | 76 | 12.7 | 8.4 | 27.7 | 3668 | 2959 |
| 15 | 32.4 | 366 | 16918 | Y | 84 | 76 | 16.7 | 9.0 | 32.3 | 3393 | 2928 |
| 16 | 33.1 | 399 | 3650 | Y | 84 | 76 | 18.1 | 9.2 | 33.5 | 3324 | 2272 |
| 17 | 34.0 | 433 | 290 | Y | 84 | 76 | 15.4 | 12.3 | 33.9 | 3493 | 2155 |
| 18 | 35.9 | 469 | 2822 | Y | 84 | 76 | 16.7 | 12.3 | 35.5 | 3207 | 2509 |
| 19 | 37.8 | 507 | 257 | Y | 84 | 76 | 15.3 | 15.3 | 37.1 | 3744 | 3063 |
| 20 | 35.1 | 542 | 6131 | Y | 84 | 76 | 14.7 | 13.5 | 34.6 | 3567 | 2956 |
| 21 | 37.7 | 579 | 286 | Y | 84 | 76 | 20.5 | 10.8 | 37.7 | 3454 | 3219 |
| 22 | 40.1 | 620 | 12912 | Y | 82 | 74 | 17.5 | 13.7 | 38.5 | 3498 | 3498 |
| 23 | 34.2 | 654 | 32132 | Y | 86 | 78 | 14.5 | 14.7 | 35.9 | 3346 | 2309 |
| 24 | 37.9 | 692 | 13 | Y | 84 | 76 | 21.4 | 9.8 | 37.6 | 3666 | 2537 |
| 25 | 40.4 | 732 | 314 | Y | 84 | 76 | 18.4 | 14.4 | 40.0 | 3693 | 2689 |
| 26 | 42.5 | 774 | 373 | Y | 84 | 76 | 21.7 | 12.8 | 41.6 | 3370 | 2619 |
| 27 | 43.2 | 818 | 523 | Y | 84 | 76 | 22.8 | 13.0 | 42.9 | 3682 | 2583 |
| 28 | 44.5 | 862 | 6568 | Y | 84 | 76 | 19.9 | 17.1 | 44.1 | 3546 | 2765 |
| 29 | 46.4 | 909 | 284 | Y | 84 | 76 | 21.4 | 17.3 | 46.1 | 3508 | 2079 |
| 30 | 46.5 | 955 | 1949 | Y | 84 | 76 | 20.1 | 18.2 | 45.9 | 3412 | 2838 |
| 31 | 45.4 | 1000 | 340 | Y | 84 | 76 | 23.1 | 16.1 | 46.8 | 3567 | 2596 |
| 32 | 49.7 | 1050 | 13 | Y | 80 | 72 | 14.8 | 22.8 | 46.4 | 3705 | 2475 |

**Run B per-token table (combined7-c32, Hello):**

| k | s/token | cum s | id | ok | ΔRecalcStyle | ΔLayout | Δstyle s | Δlayout s | Δtask s | RSS max MB (interval) | RSS at capture |
|---:|---:|---:|---:|:--:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 21.7 | 22 | 11 | Y | 87 | 79 | 9.5 | 4.0 | 18.9 | 3884 | 3825 |
| 2 | 15.9 | 38 | 314 | Y | 84 | 76 | 6.8 | 4.1 | 15.9 | 4279 | 4279 |
| 3 | 16.6 | 54 | 1101 | Y | 84 | 76 | 7.1 | 4.4 | 16.6 | 4624 | 4602 |
| 4 | 17.0 | 71 | 7926 | Y | 84 | 76 | 7.5 | 4.6 | 16.8 | 4619 | 4430 |
| 5 | 16.2 | 87 | 11 | Y | 82 | 74 | 7.1 | 4.5 | 15.9 | 5170 | 4989 |
| 6 | 17.2 | 105 | 475 | Y | 84 | 76 | 7.4 | 5.1 | 17.1 | 5253 | 4881 |
| 7 | 17.9 | 122 | 314 | Y | 84 | 76 | 7.8 | 5.4 | 18.0 | 5167 | 4782 |
| 8 | 19.1 | 142 | 1101 | Y | 84 | 76 | 8.3 | 5.7 | 19.0 | 5049 | 4715 |
| 9 | 20.5 | 162 | 407 | Y | 84 | 76 | 8.6 | 7.0 | 20.4 | 4875 | 4775 |
| 10 | 19.9 | 182 | 1654 | Y | 84 | 76 | 8.5 | 6.7 | 20.1 | 5063 | 4739 |
| 11 | 22.5 | 204 | 611 | Y | 84 | 76 | 9.6 | 7.3 | 22.1 | 4888 | 4852 |
| 12 | 23.9 | 228 | 345 | Y | 84 | 76 | 9.2 | 9.0 | 23.8 | 4719 | 4593 |
| 13 | 25.6 | 254 | 821 | Y | 84 | 76 | 12.5 | 7.5 | 25.5 | 4650 | 4520 |
| 14 | 28.3 | 282 | 3910 | Y | 84 | 76 | 14.2 | 8.2 | 28.1 | 4588 | 3098 |
| 15 | 27.6 | 310 | 286 | Y | 84 | 76 | 13.9 | 7.9 | 27.4 | 4253 | 3470 |
| 16 | 30.9 | 341 | 428 | Y | 84 | 76 | 12.3 | 12.5 | 30.7 | 4835 | 4724 |
| 17 | 27.6 | 368 | 13 | Y | 84 | 76 | 11.4 | 10.6 | 27.5 | 5052 | 4941 |
| 18 | 27.9 | 396 | 314 | Y | 84 | 76 | 13.7 | 8.4 | 27.7 | 4912 | 4520 |
| 19 | 30.0 | 426 | 1101 | Y | 84 | 76 | 15.3 | 9.1 | 30.1 | 4850 | 4639 |
| 20 | 29.3 | 456 | 407 | Y | 84 | 76 | 10.6 | 12.6 | 28.9 | 4769 | 4347 |
| 21 | 31.0 | 487 | 1654 | Y | 84 | 76 | 13.4 | 11.7 | 31.0 | 4637 | 4346 |
| 22 | 29.9 | 516 | 611 | Y | 84 | 76 | 13.3 | 12.3 | 31.9 | 4727 | 4159 |
| 23 | 33.1 | 550 | 345 | Y | 84 | 76 | 14.9 | 10.2 | 31.1 | 4366 | 2937 |
| 24 | 35.3 | 585 | 821 | Y | 84 | 76 | 14.3 | 14.9 | 35.7 | 4336 | 3017 |
| 25 | 40.4 | 625 | 3910 | Y | 84 | 76 | 17.4 | 15.5 | 39.5 | 3820 | 2758 |
| 26 | 37.9 | 663 | 286 | Y | 84 | 76 | 19.5 | 11.7 | 37.9 | 3853 | 2731 |
| 27 | 43.7 | 707 | 428 | Y | 84 | 76 | 19.2 | 16.4 | 42.7 | 3856 | 2834 |
| 28 | 40.5 | 747 | 13 | Y | 84 | 76 | 21.4 | 12.0 | 40.2 | 3740 | 2945 |
| 29 | 44.8 | 792 | 314 | Y | 84 | 76 | 21.4 | 15.3 | 44.1 | 3608 | 2776 |
| 30 | 44.8 | 837 | 1101 | Y | 84 | 76 | 22.5 | 14.5 | 44.5 | 3619 | 2746 |
| 31 | 45.4 | 882 | 407 | Y | 84 | 76 | 24.3 | 13.9 | 45.6 | 3623 | 2771 |
| 32 | 47.4 | 930 | 1654 | Y | 80 | 72 | 22.7 | 12.9 | 45.4 | 3432 | 2558 |

PENDING-RUNC-TABLE
