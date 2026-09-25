# combined2 (heap=1)

Runs: combined2-u1.json, combined2-u2.json, combined2-u3.json; trace summary combined2-t1-summary.json

| run | heap flag | tokens | ids | per-token s (1–8) | median | slope | total s | load ms | RSS peak MB | CDP style % | CDP layout % | recalcs/tok | layouts/tok | reply latency max ms |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| combined2-u1 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 35.3 34.7 35.7 36.3 37.1 38.9 39.8 36.7 | 36.5 | 0.54 | 294.5 | 2508 | 6667 | 34.9 | 44.8 | 23251.0 | 85.0 | 335 |
| combined2-u2 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 34.5 34.3 36.3 36.9 37.5 38.0 38.9 38.6 | 37.2 | 0.69 | 294.9 | 2285 | 6518 | 34.7 | 44.6 | 23251.2 | 85.0 | 339 |
| combined2-u3 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 34.8 34.4 34.4 35.7 37.6 38.4 39.2 41.2 | 36.6 | 0.98 | 295.7 | 2217 | 6021 | 34.8 | 44.7 | 23251.2 | 85.0 | 309.29999999998836 |

Per-token median across untraced runs: 34.8 34.4 35.7 36.3 37.5 38.4 39.2 38.6; median 36.9 s; slope 0.71 s/token/token; RSS peak 6667 MB.

## Light trace (combined2-t1-summary.json)

Complete traced tokens: [1, 2, 3, 4, 5, 6, 7]; style 22.8 % of wall; 135.3 style passes/token; 73.7 frames/token; 1.0 whole-DOM (≥50 % of DOM) passes/token; GC nested total 26873.7 ms over the traced window.

### Style-pass histogram (traced generate window)

| elementCount bucket | passes | per token | summed ms | % of style | mean ms/pass | µs/element |
|---|---:|---:|---:|---:|---:|---:|
| 1-9 | 401 | 57.3 | 3,820 | 5.3 % | 9.5 | 15097.63 |
| 10-99 | 1 | 0.1 | 84 | 0.1 % | 84.1 | 2102.5 |
| 100-999 | 377 | 53.9 | 40,697 | 56.9 % | 107.9 | 249.47 |
| 1k-9,999 | 295 | 42.1 | 22,222 | 31.1 % | 75.3 | 17.74 |
| >=50%DOM | 8 | 1.1 | 4,728 | 6.6 % | 591.0 | 11.53 |

Top recurring passes by exact elementCount (n, per token, summed ms, mean ms):

| elementCount | passes | per token | summed ms | mean ms |
|---:|---:|---:|---:|---:|
| 473 | 88 | 12.6 | 13,545 | 153.9 |
| 126 | 95 | 13.6 | 11,545 | 121.5 |
| 2,934 | 88 | 12.6 | 11,426 | 129.8 |
| 347 | 81 | 11.6 | 8,696 | 107.4 |
| 51,235 | 8 | 1.1 | 4,728 | 591.0 |
| 6,919 | 96 | 13.7 | 4,464 | 46.5 |
| 780 | 96 | 13.7 | 3,836 | 40.0 |
| 3,092 | 96 | 13.7 | 2,591 | 27.0 |
| 0 | 198 | 28.3 | 1,860 | 9.4 |
| 1 | 186 | 26.6 | 1,776 | 9.6 |
| 2,957 | 1 | 0.1 | 1,718 | 1718.3 |
| 474 | 8 | 1.1 | 1,698 | 212.3 |
| 2,917 | 7 | 1.0 | 1,141 | 163.0 |
| 1,438 | 7 | 1.0 | 882 | 126.0 |
| 358 | 7 | 1.0 | 833 | 119.0 |
| 127 | 2 | 0.3 | 544 | 271.9 |
| 2 | 8 | 1.1 | 93 | 11.7 |
| 6 | 8 | 1.1 | 86 | 10.8 |
| 40 | 1 | 0.1 | 84 | 84.1 |
| 3 | 1 | 0.1 | 4 | 4.1 |

### Per-token phase split (from the trace)

| token | wall s | style % | layout % | animate % | prepaint % | paint lifecycle % | hit-test % | GC nested % | passes | layouts | frames | whole-DOM passes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 36.3 | 25.6 | 54.7 | 3.7 | 5.3 | 7.7 | 1.2 | 4.4 | 137 | 86 | 78 | 1 |
| 2 | 36.5 | 20.8 | 58.0 | 3.9 | 5.4 | 8.8 | 1.4 | 5.7 | 135 | 85 | 73 | 1 |
| 3 | 36.2 | 20.9 | 57.3 | 4.1 | 5.6 | 9.0 | 1.4 | 5.3 | 135 | 85 | 73 | 1 |
| 4 | 37.7 | 21.6 | 57.2 | 4.2 | 5.4 | 8.5 | 1.4 | 6.1 | 135 | 85 | 73 | 1 |
| 5 | 38.9 | 23.4 | 56.2 | 3.9 | 5.1 | 8.4 | 1.4 | 7.0 | 135 | 85 | 73 | 1 |
| 6 | 41.9 | 23.9 | 54.8 | 3.9 | 4.9 | 9.5 | 1.4 | 9.6 | 135 | 85 | 73 | 1 |
| 7 | 44.3 | 23.1 | 57.3 | 3.8 | 4.7 | 8.0 | 1.4 | 10.7 | 135 | 85 | 73 | 1 |

Notes: contended runs: combined2-u1
