# R2F (heap=1)

Runs: R2F-u1.json, R2F-u2.json, R2F-u3.json; trace summary R2F-t1-summary.json

| run | heap flag | tokens | ids | per-token s (1–8) | median | slope | total s | load ms | RSS peak MB | CDP style % | CDP layout % | recalcs/tok | layouts/tok | reply latency max ms |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R2F-u1 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 24.5 21.6 22.5 23.8 24.6 24.9 25.9 26.1 | 24.6 | 0.48 | 193.9 | 30813 | 5049 | 40.0 | 21.7 | 136.0 | 87.0 | 380.70000000001164 |
| R2F-u2 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 24.3 21.2 22.2 22.2 22.7 23.3 24.0 23.4 | 23.0 | 0.13 | 183.3 | 2400 | 5941 | 39.4 | 21.6 | 136.1 | 87.0 | 551.9000000000087 |
| R2F-u3 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 24.5 21.5 22.2 23.2 23.4 23.8 24.6 24.1 | 23.6 | 0.21 | 187.4 | 30681 | 5823 | 39.3 | 21.7 | 136.0 | 87.0 | 339.8999999999942 |

Per-token median across untraced runs: 24.5 21.5 22.2 23.2 23.4 23.8 24.6 24.1; median 23.6 s; slope 0.21 s/token/token; RSS peak 5941 MB.

## Light trace (R2F-t1-summary.json)

Complete traced tokens: [1, 2, 3, 4, 5, 6, 7]; style 40.5 % of wall; 132.1 style passes/token; 46.9 frames/token; 1.0 whole-DOM (≥50 % of DOM) passes/token; GC nested total 10720.4 ms over the traced window.

### Style-pass histogram (traced generate window)

| elementCount bucket | passes | per token | summed ms | % of style | mean ms/pass | µs/element |
|---|---:|---:|---:|---:|---:|---:|
| 1-9 | 360 | 51.4 | 5,073 | 6.2 % | 14.1 | 73523.19 |
| 10-99 | 10 | 1.4 | 238 | 0.3 % | 23.8 | 609.46 |
| 100-999 | 295 | 42.1 | 27,522 | 33.4 % | 93.3 | 163.55 |
| 1k-9,999 | 384 | 54.9 | 46,011 | 55.8 % | 119.8 | 34.35 |
| >=50%DOM | 8 | 1.1 | 3,602 | 4.4 % | 450.2 | 8.85 |

Top recurring passes by exact elementCount (n, per token, summed ms, mean ms):

| elementCount | passes | per token | summed ms | mean ms |
|---:|---:|---:|---:|---:|
| 1,553 | 88 | 12.6 | 17,596 | 200.0 |
| 3,089 | 96 | 13.7 | 12,700 | 132.3 |
| 126 | 95 | 13.6 | 11,877 | 125.0 |
| 784 | 96 | 13.7 | 10,801 | 112.5 |
| 2,323 | 81 | 11.6 | 6,798 | 83.9 |
| 0 | 333 | 47.6 | 4,754 | 14.3 |
| 6,919 | 96 | 13.7 | 4,172 | 43.5 |
| 780 | 96 | 13.7 | 3,612 | 37.6 |
| 50,892 | 8 | 1.1 | 3,602 | 450.2 |
| 2,326 | 8 | 1.1 | 1,656 | 207.0 |
| 2,381 | 1 | 0.1 | 1,639 | 1639.0 |
| 2,342 | 7 | 1.0 | 803 | 114.8 |
| 863 | 7 | 1.0 | 754 | 107.8 |
| 2,334 | 7 | 1.0 | 645 | 92.2 |
| 127 | 1 | 0.1 | 477 | 477.1 |
| 1 | 18 | 2.6 | 245 | 13.6 |
| 39 | 9 | 1.3 | 209 | 23.2 |
| 6 | 8 | 1.1 | 70 | 8.8 |
| 40 | 1 | 0.1 | 30 | 29.7 |
| 3 | 1 | 0.1 | 4 | 4.3 |

### Per-token phase split (from the trace)

| token | wall s | style % | layout % | animate % | prepaint % | paint lifecycle % | hit-test % | GC nested % | passes | layouts | frames | whole-DOM passes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 25.3 | 48.8 | 16.8 | 6.4 | 6.7 | 16.4 | 2.1 | 2.5 | 133 | 88 | 52 | 1 |
| 2 | 22.9 | 39.5 | 19.8 | 7.4 | 7.4 | 20.3 | 2.6 | 3.9 | 132 | 87 | 46 | 1 |
| 3 | 24.2 | 39.6 | 19.7 | 7.2 | 7.1 | 21.0 | 2.6 | 4.5 | 132 | 87 | 46 | 1 |
| 4 | 24.4 | 39.0 | 20.6 | 7.2 | 7.0 | 20.8 | 2.6 | 3.7 | 132 | 87 | 46 | 1 |
| 5 | 25.1 | 40.2 | 21.2 | 7.1 | 7.0 | 19.3 | 2.6 | 5.5 | 132 | 87 | 46 | 1 |
| 6 | 27.1 | 39.2 | 21.6 | 6.8 | 6.5 | 20.7 | 2.6 | 5.6 | 132 | 87 | 46 | 1 |
| 7 | 27.6 | 37.7 | 25.5 | 6.7 | 6.5 | 18.6 | 2.6 | 7.7 | 132 | 87 | 46 | 1 |

Notes: config: heap=1, mouseoff (pointer parked off-viewport -50,-50 after the Run click); contended runs: R2F-u1,R2F-u2
