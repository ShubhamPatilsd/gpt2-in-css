# R2C (heap=1)

Runs: R2C-u1.json, R2C-u2.json, R2C-u3.json; trace summary R2C-t1-summary.json

| run | heap flag | tokens | ids | per-token s (1–8) | median | slope | total s | load ms | RSS peak MB | CDP style % | CDP layout % | recalcs/tok | layouts/tok | reply latency max ms |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R2C-u1 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 32.4 32.8 48.8 37.3 31.3 31.5 32.2 32.2 | 32.3 | -0.74 | 278.5 | 2772 | 6136 | 48.5 | 17.3 | 175.0 | 109.0 | 1776.300000000003 |
| R2C-u2 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 31.9 31.6 32.7 33.3 35.3 35.5 36.9 36.7 | 34.3 | 0.84 | 273.9 | 2577 | 5587 | 47.6 | 15.9 | 175.0 | 109.0 | 234.79999999998836 |
| R2C-u3 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 32.2 30.5 34.1 33.3 31.8 32.9 33.6 36.1 | 33.1 | 0.44 | 264.6 | 2353 | 5703 | 47.7 | 16.5 | 175.0 | 109.0 | 195.79999999998836 |

Per-token median across untraced runs: 32.2 31.6 34.1 33.3 31.8 32.9 33.6 36.1; median 33.1 s; slope 0.38 s/token/token; RSS peak 6136 MB.

## Light trace (R2C-t1-summary.json)

Complete traced tokens: [3, 4, 5, 6, 7]; style 47.9 % of wall; 171.0 style passes/token; 85.0 frames/token; 1.0 whole-DOM (≥50 % of DOM) passes/token; GC nested total 20863.9 ms over the traced window.

### Style-pass histogram (traced generate window)

| elementCount bucket | passes | per token | summed ms | % of style | mean ms/pass | µs/element |
|---|---:|---:|---:|---:|---:|---:|
| 1-9 | 420 | 84.0 | 6,562 | 5.3 % | 15.6 | 30806.1 |
| 100-999 | 400 | 80.0 | 68,383 | 55.4 % | 171.0 | 336.45 |
| 1k-9,999 | 330 | 66.0 | 43,745 | 35.4 % | 132.6 | 36.82 |
| >=50%DOM | 7 | 1.4 | 4,848 | 3.9 % | 692.5 | 13.51 |

Top recurring passes by exact elementCount (n, per token, summed ms, mean ms):

| elementCount | passes | per token | summed ms | mean ms |
|---:|---:|---:|---:|---:|
| 1,553 | 74 | 14.8 | 18,701 | 252.7 |
| 357 | 68 | 13.6 | 17,047 | 250.7 |
| 126 | 81 | 16.2 | 12,678 | 156.5 |
| 784 | 81 | 16.2 | 11,983 | 147.9 |
| 3,089 | 81 | 16.2 | 10,131 | 125.1 |
| 485 | 41 | 8.2 | 10,057 | 245.3 |
| 484 | 34 | 6.8 | 8,597 | 252.9 |
| 2,934 | 75 | 15.0 | 8,163 | 108.8 |
| 51,247 | 7 | 1.4 | 4,848 | 692.5 |
| 0 | 249 | 49.8 | 3,885 | 15.6 |
| 780 | 81 | 16.2 | 3,531 | 43.6 |
| 6,919 | 81 | 16.2 | 3,311 | 40.9 |
| 368 | 6 | 1.2 | 2,616 | 436.0 |
| 1 | 157 | 31.4 | 2,479 | 15.8 |
| 487 | 7 | 1.4 | 1,834 | 262.0 |
| 2,326 | 7 | 1.4 | 1,723 | 246.1 |
| 2,917 | 6 | 1.2 | 1,068 | 177.9 |
| 1,438 | 6 | 1.2 | 649 | 108.2 |
| 2 | 7 | 1.4 | 131 | 18.8 |
| 6 | 7 | 1.4 | 67 | 9.6 |

### Per-token phase split (from the trace)

| token | wall s | style % | layout % | animate % | prepaint % | paint lifecycle % | hit-test % | GC nested % | passes | layouts | frames | whole-DOM passes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 34.0 | 46.7 | 15.2 | 9.7 | 5.4 | 16.1 | 2.8 | 4.6 | 171 | 109 | 85 | 1 |
| 4 | 36.9 | 45.7 | 16.5 | 9.2 | 5.0 | 17.1 | 2.7 | 6.0 | 171 | 109 | 85 | 1 |
| 5 | 37.9 | 48.6 | 16.2 | 9.1 | 5.0 | 14.6 | 2.7 | 7.6 | 171 | 109 | 85 | 1 |
| 6 | 39.1 | 47.4 | 18.6 | 8.7 | 4.9 | 14.0 | 2.6 | 9.0 | 171 | 109 | 85 | 1 |
| 7 | 42.0 | 50.8 | 16.7 | 8.4 | 4.6 | 13.5 | 2.6 | 10.8 | 171 | 109 | 85 | 1 |

Notes: config: heap=1, mouseoff (pointer parked off-viewport -50,-50 after the Run click)
