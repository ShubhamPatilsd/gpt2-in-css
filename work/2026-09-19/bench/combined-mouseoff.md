# combined (mouseoff)

Runs: combined-mouseoff-u1.json, combined-mouseoff-u2.json, combined-mouseoff-u3.json; trace summary combined-mouseoff-t1-summary.json

| run | heap flag | tokens | ids | per-token s (1–8) | median | slope | total s | load ms | RSS peak MB | CDP style % | CDP layout % | recalcs/tok | layouts/tok | reply latency max ms |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| combined-mouseoff-u1 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 33.0 31.6 33.3 34.6 35.6 36.5 38.2 39.9 | 35.1 | 1.1 | 282.8 | 2703 | 4320 | 47.6 | 16.9 | 175.1 | 109.0 | 214.29999999998836 |
| combined-mouseoff-u2 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 35.4 34.1 36.8 42.3 40.6 40.4 42.6 41.8 | 40.5 | 1.14 | 314.1 | 31585 | 4050 | 48.4 | 17.9 | 175.0 | 109.0 | 894.2000000000116 |
| combined-mouseoff-u3 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 31.4 29.4 30.2 30.5 31.3 31.9 33.1 33.7 | 31.3 | 0.48 | 251.5 | 31087 | 5575 | 46.8 | 16.5 | 174.9 | 109.0 | 271 |

Per-token median across untraced runs: 33.0 31.6 33.3 34.6 35.6 36.5 38.2 39.9; median 35.1 s; slope 1.09 s/token/token; RSS peak 5575 MB.

## Light trace (combined-mouseoff-t1-summary.json)

Complete traced tokens: [3, 4, 5, 6, 7]; style 47.3 % of wall; 171.0 style passes/token; 85.0 frames/token; 1.0 whole-DOM (≥50 % of DOM) passes/token; GC nested total 19356.6 ms over the traced window.

### Style-pass histogram (traced generate window)

| elementCount bucket | passes | per token | summed ms | % of style | mean ms/pass | µs/element |
|---|---:|---:|---:|---:|---:|---:|
| 1-9 | 420 | 84.0 | 6,251 | 5.4 % | 14.9 | 29348.83 |
| 100-999 | 400 | 80.0 | 63,425 | 55.2 % | 158.6 | 312.05 |
| 1k-9,999 | 330 | 66.0 | 40,448 | 35.2 % | 122.6 | 34.05 |
| >=50%DOM | 7 | 1.4 | 4,718 | 4.1 % | 674.0 | 13.15 |

Top recurring passes by exact elementCount (n, per token, summed ms, mean ms):

| elementCount | passes | per token | summed ms | mean ms |
|---:|---:|---:|---:|---:|
| 1,553 | 74 | 14.8 | 14,960 | 202.2 |
| 357 | 68 | 13.6 | 14,707 | 216.3 |
| 784 | 81 | 16.2 | 11,262 | 139.0 |
| 126 | 81 | 16.2 | 11,241 | 138.8 |
| 3,089 | 81 | 16.2 | 11,016 | 136.0 |
| 485 | 41 | 8.2 | 10,976 | 267.7 |
| 484 | 34 | 6.8 | 8,485 | 249.6 |
| 2,934 | 75 | 15.0 | 7,797 | 104.0 |
| 51,247 | 7 | 1.4 | 4,718 | 674.0 |
| 0 | 249 | 49.8 | 3,689 | 14.8 |
| 6,919 | 81 | 16.2 | 3,680 | 45.4 |
| 780 | 81 | 16.2 | 3,343 | 41.3 |
| 1 | 157 | 31.4 | 2,381 | 15.2 |
| 487 | 7 | 1.4 | 2,038 | 291.1 |
| 2,326 | 7 | 1.4 | 1,463 | 209.1 |
| 368 | 6 | 1.2 | 1,331 | 221.8 |
| 2,917 | 6 | 1.2 | 920 | 153.3 |
| 1,438 | 6 | 1.2 | 613 | 102.1 |
| 2 | 7 | 1.4 | 120 | 17.2 |
| 6 | 7 | 1.4 | 61 | 8.7 |

### Per-token phase split (from the trace)

| token | wall s | style % | layout % | animate % | prepaint % | paint lifecycle % | hit-test % | GC nested % | passes | layouts | frames | whole-DOM passes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 32.7 | 45.6 | 16.4 | 9.3 | 5.6 | 16.3 | 2.8 | 4.9 | 171 | 109 | 85 | 1 |
| 4 | 33.9 | 46.7 | 16.5 | 9.0 | 5.4 | 15.8 | 2.7 | 5.7 | 171 | 109 | 85 | 1 |
| 5 | 35.8 | 46.5 | 17.7 | 9.0 | 5.2 | 15.1 | 2.7 | 7.9 | 171 | 109 | 85 | 1 |
| 6 | 37.0 | 47.9 | 17.1 | 8.7 | 5.1 | 14.8 | 2.7 | 7.4 | 171 | 109 | 85 | 1 |
| 7 | 39.8 | 49.4 | 17.3 | 8.7 | 4.8 | 13.7 | 2.6 | 10.4 | 171 | 109 | 85 | 1 |

Notes: config: heap=1, mouseoff (pointer parked off-viewport -50,-50 after the Run click)
