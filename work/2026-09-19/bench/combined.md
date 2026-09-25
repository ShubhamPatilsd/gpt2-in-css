# combined (heap=1)

Runs: combined-u1.json, combined-u2.json, combined-u3.json; trace summary combined-t1-summary.json

| run | heap flag | tokens | ids | per-token s (1–8) | median | slope | total s | load ms | RSS peak MB | CDP style % | CDP layout % | recalcs/tok | layouts/tok | reply latency max ms |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| combined-u1 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 30.1 28.5 29.8 29.7 30.3 31.2 31.5 32.7 | 30.2 | 0.45 | 243.7 | 2268 | 5830 | 46.3 | 16.9 | 175.0 | 109.0 | 220.09999999997672 |
| combined-u2 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 30.2 30.5 31.3 30.0 30.6 31.4 32.4 32.1 | 30.9 | 0.28 | 248.5 | 2248 | 5806 | 46.5 | 16.7 | 175.0 | 109.0 | 485.8999999999942 |
| combined-u3 | True | 8 | 8/8 [11, 314, 1101, 7926, 11, 475, 314, 1101] | 30.5 28.3 29.8 29.7 30.4 31.3 32.4 32.5 | 30.4 | 0.47 | 244.9 | 2192 | 5852 | 46.4 | 17.1 | 175.1 | 109.0 | 155.60000000000582 |

Per-token median across untraced runs: 30.2 28.5 29.8 29.7 30.4 31.3 32.4 32.5; median 30.3 s; slope 0.49 s/token/token; RSS peak 5852 MB.

## Light trace (combined-t1-summary.json)

Complete traced tokens: [3, 4, 5, 6, 7]; style 46.3 % of wall; 171.0 style passes/token; 85.0 frames/token; 1.0 whole-DOM (≥50 % of DOM) passes/token; GC nested total 17085.2 ms over the traced window.

### Style-pass histogram (traced generate window)

| elementCount bucket | passes | per token | summed ms | % of style | mean ms/pass | µs/element |
|---|---:|---:|---:|---:|---:|---:|
| 1-9 | 416 | 83.2 | 6,903 | 5.9 % | 16.6 | 32715.17 |
| 100-999 | 397 | 79.4 | 63,794 | 54.8 % | 160.7 | 316.03 |
| 1k-9,999 | 327 | 65.4 | 41,075 | 35.3 % | 125.6 | 34.95 |
| >=50%DOM | 7 | 1.4 | 4,738 | 4.1 % | 676.8 | 13.21 |

Top recurring passes by exact elementCount (n, per token, summed ms, mean ms):

| elementCount | passes | per token | summed ms | mean ms |
|---:|---:|---:|---:|---:|
| 357 | 68 | 13.6 | 16,940 | 249.1 |
| 1,553 | 74 | 14.8 | 15,924 | 215.2 |
| 784 | 81 | 16.2 | 10,678 | 131.8 |
| 485 | 40 | 8.0 | 10,666 | 266.6 |
| 126 | 80 | 16.0 | 10,533 | 131.7 |
| 3,089 | 80 | 16.0 | 10,343 | 129.3 |
| 2,934 | 74 | 14.8 | 8,512 | 115.0 |
| 484 | 34 | 6.8 | 8,393 | 246.9 |
| 51,247 | 7 | 1.4 | 4,738 | 676.8 |
| 0 | 247 | 49.4 | 4,100 | 16.6 |
| 780 | 80 | 16.0 | 3,394 | 42.4 |
| 6,919 | 80 | 16.0 | 3,224 | 40.3 |
| 1 | 155 | 31.0 | 2,608 | 16.8 |
| 487 | 7 | 1.4 | 1,755 | 250.7 |
| 2,326 | 7 | 1.4 | 1,498 | 214.0 |
| 368 | 6 | 1.2 | 1,395 | 232.5 |
| 2,917 | 6 | 1.2 | 956 | 159.4 |
| 1,438 | 6 | 1.2 | 617 | 102.9 |
| 2 | 7 | 1.4 | 127 | 18.2 |
| 6 | 7 | 1.4 | 67 | 9.6 |

### Per-token phase split (from the trace)

| token | wall s | style % | layout % | animate % | prepaint % | paint lifecycle % | hit-test % | GC nested % | passes | layouts | frames | whole-DOM passes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 34.1 | 45.8 | 15.5 | 10.3 | 5.6 | 15.9 | 2.9 | 4.7 | 171 | 109 | 85 | 1 |
| 4 | 35.4 | 45.8 | 15.9 | 10.1 | 5.4 | 15.9 | 2.9 | 4.8 | 171 | 109 | 85 | 1 |
| 5 | 36.3 | 45.0 | 17.1 | 9.9 | 5.4 | 15.6 | 2.9 | 4.9 | 171 | 109 | 85 | 1 |
| 6 | 38.5 | 46.4 | 17.3 | 9.7 | 5.2 | 14.7 | 2.8 | 6.9 | 171 | 109 | 85 | 1 |
| 7 | 40.6 | 48.1 | 16.9 | 9.4 | 4.9 | 14.2 | 2.7 | 8.3 | 171 | 109 | 85 | 1 |
