### R2C-t1: per-token phase split (ms; % of window wall)

| phase | token 3 | token 4 | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|---:|---:|
| wall | 33,980 | 36,869 | 37,939 | 39,095 | 42,028 | 37,982 |
| main-thread busy | 33,906 (99.8 %) | 36,802 (99.8 %) | 37,844 (99.7 %) | 39,002 (99.8 %) | 42,017 (100.0 %) | 37,914 (99.8 %) |
| idle | 74 (0.2 %) | 67 (0.2 %) | 95 (0.3 %) | 93 (0.2 %) | 11 (0.0 %) | 68 (0.2 %) |
| style (UpdateLayoutTree) | 15,878 (46.7 %) | 16,840 (45.7 %) | 18,436 (48.6 %) | 18,542 (47.4 %) | 21,339 (50.8 %) | 18,207 (47.9 %) |
|   of which recalcStyle self (no nested GC) | 12,816 (37.7 %) | 13,619 (36.9 %) | 14,257 (37.6 %) | 14,655 (37.5 %) | 15,867 (37.8 %) | 14,243 (37.5 %) |
| layout | 5,166 (15.2 %) | 6,074 (16.5 %) | 6,145 (16.2 %) | 7,278 (18.6 %) | 7,037 (16.7 %) | 6,340 (16.7 %) |
|   of which text shaping | 2,019 (5.9 %) | 2,174 (5.9 %) | 2,174 (5.7 %) | 2,232 (5.7 %) | 2,332 (5.5 %) | 2,186 (5.8 %) |
| animation servicing (Blink.Animate) | 3,310 (9.7 %) | 3,392 (9.2 %) | 3,444 (9.1 %) | 3,418 (8.7 %) | 3,534 (8.4 %) | 3,419 (9.0 %) |
| pre-paint + compositing inputs | 1,840 (5.4 %) | 1,853 (5.0 %) | 1,902 (5.0 %) | 1,917 (4.9 %) | 1,949 (4.6 %) | 1,892 (5.0 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 5,480 (16.1 %) | 6,291 (17.1 %) | 5,555 (14.6 %) | 5,492 (14.0 %) | 5,679 (13.5 %) | 5,699 (15.0 %) |
|   of which Paint | 14 (0.0 %) | 14 (0.0 %) | 15 (0.0 %) | 15 (0.0 %) | 15 (0.0 %) | 15 (0.0 %) |
| hit-test (fake mousemove) | 946 (2.8 %) | 978 (2.7 %) | 1,013 (2.7 %) | 1,022 (2.6 %) | 1,073 (2.6 %) | 1,007 (2.6 %) |
| other busy (unattributed) | 1,286 (3.8 %) | 1,373 (3.7 %) | 1,350 (3.6 %) | 1,333 (3.4 %) | 1,406 (3.3 %) | 1,350 (3.6 %) |
| GC (nested inside the above) | 1,550 (4.6 %) | 2,224 (6.0 %) | 2,889 (7.6 %) | 3,521 (9.0 %) | 4,528 (10.8 %) | 2,943 (7.7 %) |
| style passes / layouts / frames | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | |
| major GCs | 3 | 3 | 3 | 3 | 3 | |
| token boundary (s after Run) | 59.7 | 96.6 | 134.5 | 173.6 | 215.6 | |
| handshakes (s after Run) | 57.8 token-3-ready; 59.3 token-3-ack | 94.6 token-4-ready; 96.2 token-4-ack | 132.5 token-5-ready; 134.1 token-5-ack | 171.6 token-6-ready; 173.2 token-6-ack | 213.6 token-7-ready; 215.2 token-7-ack | |

### R2C-t1: style-pass histogram over the traced generate window (5 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 420 | 84.0 | 6,562 | 5.3 % | 15.6 | 7.3–25 | 30806.1 |
| 100-999 | 400 | 80.0 | 68,383 | 55.4 % | 171.0 | 26.7–1470 | 336.45 |
| 1k-9,999 | 330 | 66.0 | 43,745 | 35.4 % | 132.6 | 29.7–1260 | 36.82 |
| >=50%DOM | 7 | 1.4 | 4,848 | 3.9 % | 692.5 | 573.1–815 | 13.51 |
| **total** | 1157 | 231 | 123,538 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 1,553 | 74 | 14.8 | 18,701 | 252.7 | 162.7 |
| 357 | 68 | 13.6 | 17,047 | 250.7 | 702.2 |
| 126 | 81 | 16.2 | 12,678 | 156.5 | 1242.2 |
| 784 | 81 | 16.2 | 11,983 | 147.9 | 188.7 |
| 3,089 | 81 | 16.2 | 10,131 | 125.1 | 40.5 |
| 485 | 41 | 8.2 | 10,057 | 245.3 | 505.8 |
| 484 | 34 | 6.8 | 8,597 | 252.9 | 522.4 |
| 2,934 | 75 | 15.0 | 8,163 | 108.8 | 37.1 |
| 51,247 | 7 | 1.4 | 4,848 | 692.5 | 13.5 |
| 0 | 249 | 49.8 | 3,885 | 15.6 | – |
| 780 | 81 | 16.2 | 3,531 | 43.6 | 55.9 |
| 6,919 | 81 | 16.2 | 3,311 | 40.9 | 5.9 |
| 368 | 6 | 1.2 | 2,616 | 436.0 | 1184.8 |
| 1 | 157 | 31.4 | 2,479 | 15.8 | 15789.8 |
| 487 | 7 | 1.4 | 1,834 | 262.0 | 538.0 |
| 2,326 | 7 | 1.4 | 1,723 | 246.1 | 105.8 |
| 2,917 | 6 | 1.2 | 1,068 | 177.9 | 61.0 |
| 1,438 | 6 | 1.2 | 649 | 108.2 | 75.2 |
| 2 | 7 | 1.4 | 131 | 18.8 | 9378.6 |
| 6 | 7 | 1.4 | 67 | 9.6 | 1592.9 |
| 127 | 1 | 0.2 | 40 | 39.7 | 312.6 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 3 | 1 | 815 | 5.1 % | [814.8, 51247] |
| 4 | 1 | 573 | 3.4 % | [573.1, 51247] |
| 5 | 1 | 604 | 3.3 % | [835.0, 126] |
| 6 | 1 | 701 | 3.8 % | [991.0, 357] |
| 7 | 1 | 772 | 3.6 % | [1144.3, 126] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 187383], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 185236], ['V8.GC_MC_MARK_ROOTS', 65], ['V8.GC_MC_SWEEP', 63], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 61], ['V8.GC_MC_CLEAR_STRING_TABLE', 51], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 50], ['V8.GC_MC_EVACUATE', 44]], total nested 20,864 ms

### R2C-t1: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 349 | 1405 | 1902 |
| token 1 (0–60 s) | 1632 | 2936 | 4146 |
| token 2 (60–97 s) | 4124 | 4293 | 4487 |
| token 3 (97–134 s) | 2837 | 4106 | 4716 |
| token 4 (134–174 s) | 3058 | 3694 | 4119 |
| token 5 (174–216 s) | 3403 | 3717 | 4103 |
| rest of run (216–303 s) | 3016 | 3573 | 3986 |
| after completion (readback) | 3832 | 3832 | 3833 |
| browser process peak | | | 222 |
| GPU process peak | | | 138 |

CDP Performance.getMetrics deltas Run→end (304.5 s wall): RecalcStyleCount +1400, RecalcStyleDuration +147.8 s, LayoutCount +872, LayoutDuration +48.7 s, TaskDuration +303.3 s; Nodes 134296, LayoutObjects 141817

Load phase (R2C-t1): {}
named: null
big: []
nav: {'responseEnd': 51.30000001192093, 'domInteractive': 1376.2000000178814, 'domContentLoadedEventEnd': 1376.300000011921, 'domComplete': 2620.5, 'loadEventEnd': 2621.5999999940395} {'resources': 250, 'resourceBytes': 143716091, 'resourceEncodedBytes': 143716091, 'lastResourceEnd': 1663.7000000178814, 'cssResource': {'startTime': 13.5, 'responseEnd': 76.7000000178814, 'decodedBodySize': 40927799, 'encodedBodySize': 40927799}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 1204}, {'name': 'first-contentful-paint', 'startTime': 1204}], 'fontsStatus': 'loaded', 'fontsSize': 283, 'elements': 69522, 'scripts': 0}
timeline: {'tNav0': 560.5, 'tLoad': 3197.3, 'tIdle': 5449.2, 'tRun': 5460.2, 'tEndWait': 307969.9, 'stopReason': 'token-limit', 'traceBytes': 145561737, 'dataLossOccurred': True} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "0", "--winner": "1101", "--head-output-epoch": "8"}}
