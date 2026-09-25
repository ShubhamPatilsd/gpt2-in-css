# combined3 (heap=1)

Runs: combined3-u1.json, combined3-u2.json, combined3-u3.json; trace summary combined3-t1-summary.json

| run | heap flag | tokens | ids | per-token s (1–8) | median | slope | total s | load ms | RSS peak MB | CDP style % | CDP layout % | recalcs/tok | layouts/tok | reply latency max ms |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| combined3-u1 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 27.4 23.4 24.4 24.6 24.4 24.7 25.5 26.9 | 24.7 | 0.09 | 201.2 | 2838 | 5102 | 41.7 | 20.9 | 136.1 | 87.0 | 398.8999999999942 |
| combined3-u2 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 27.6 24.1 24.2 26.5 25.5 26.5 29.0 26.8 | 26.5 | 0.3 | 210.1 | 33605 | 5403 | 42.0 | 20.0 | 136.0 | 87.0 | 406.8999999999942 |
| combined3-u3 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 25.3 21.4 22.4 22.7 23.6 24.2 25.2 24.7 | 23.9 | 0.25 | 189.5 | 2694 | 5530 | 40.9 | 21.6 | 136.0 | 87.0 | 392.4000000000233 |

Per-token median across untraced runs: 27.4 23.4 24.2 24.6 24.4 24.7 25.5 26.8; median 24.6 s; slope 0.09 s/token/token; RSS peak 5530 MB.

## Light trace (combined3-t1-summary.json)

Complete traced tokens: [1, 2, 3, 4, 5, 6, 7]; style 43.2 % of wall; 132.1 style passes/token; 46.9 frames/token; 1.0 whole-DOM (≥50 % of DOM) passes/token; GC nested total 16309.8 ms over the traced window.

### Style-pass histogram (traced generate window)

| elementCount bucket | passes | per token | summed ms | % of style | mean ms/pass | µs/element |
|---|---:|---:|---:|---:|---:|---:|
| 1-9 | 360 | 51.4 | 5,894 | 5.8 % | 16.4 | 85414.49 |
| 10-99 | 10 | 1.4 | 276 | 0.3 % | 27.6 | 706.14 |
| 100-999 | 295 | 42.1 | 34,106 | 33.8 % | 115.6 | 202.67 |
| 1k-9,999 | 384 | 54.9 | 56,656 | 56.1 % | 147.5 | 42.3 |
| >=50%DOM | 8 | 1.1 | 3,978 | 3.9 % | 497.2 | 9.77 |

Top recurring passes by exact elementCount (n, per token, summed ms, mean ms):

| elementCount | passes | per token | summed ms | mean ms |
|---:|---:|---:|---:|---:|
| 1,553 | 88 | 12.6 | 22,893 | 260.1 |
| 3,089 | 96 | 13.7 | 16,138 | 168.1 |
| 126 | 95 | 13.6 | 14,829 | 156.1 |
| 784 | 96 | 13.7 | 13,825 | 144.0 |
| 2,323 | 81 | 11.6 | 7,198 | 88.9 |
| 0 | 333 | 47.6 | 5,526 | 16.6 |
| 6,919 | 96 | 13.7 | 4,550 | 47.4 |
| 780 | 96 | 13.7 | 4,318 | 45.0 |
| 50,892 | 8 | 1.1 | 3,978 | 497.2 |
| 2,326 | 8 | 1.1 | 2,063 | 257.9 |
| 2,381 | 1 | 0.1 | 2,021 | 2020.9 |
| 2,342 | 7 | 1.0 | 941 | 134.5 |
| 2,334 | 7 | 1.0 | 852 | 121.6 |
| 127 | 1 | 0.1 | 568 | 568.2 |
| 863 | 7 | 1.0 | 566 | 80.8 |
| 1 | 18 | 2.6 | 283 | 15.7 |
| 39 | 9 | 1.3 | 250 | 27.8 |
| 6 | 8 | 1.1 | 80 | 10.0 |
| 40 | 1 | 0.1 | 26 | 25.8 |
| 3 | 1 | 0.1 | 4 | 4.3 |

### Per-token phase split (from the trace)

| token | wall s | style % | layout % | animate % | prepaint % | paint lifecycle % | hit-test % | GC nested % | passes | layouts | frames | whole-DOM passes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 28.2 | 51.4 | 16.3 | 6.5 | 6.1 | 14.9 | 2.1 | 2.7 | 133 | 88 | 52 | 1 |
| 2 | 26.3 | 40.9 | 19.1 | 8.1 | 7.4 | 18.8 | 2.9 | 3.9 | 132 | 87 | 46 | 1 |
| 3 | 29.2 | 40.3 | 21.5 | 7.6 | 6.5 | 18.7 | 2.7 | 6.8 | 132 | 87 | 46 | 1 |
| 4 | 28.6 | 43.2 | 19.7 | 7.8 | 6.7 | 17.0 | 2.8 | 5.6 | 132 | 87 | 46 | 1 |
| 5 | 29.7 | 42.0 | 19.6 | 7.4 | 6.2 | 19.6 | 2.7 | 6.3 | 132 | 87 | 46 | 1 |
| 6 | 29.5 | 43.6 | 21.4 | 6.6 | 6.2 | 17.2 | 2.6 | 8.4 | 132 | 87 | 46 | 1 |
| 7 | 30.8 | 41.2 | 25.7 | 6.5 | 6.0 | 15.8 | 2.5 | 10.0 | 132 | 87 | 46 | 1 |

Notes: config: heap=1, mouseoff (pointer parked off-viewport -50,-50 after the Run click); contended runs: combined3-u1,combined3-u2,combined3-u3
