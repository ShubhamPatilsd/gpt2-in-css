### combined-mouseoff-t1: per-token phase split (ms; % of window wall)

| phase | token 3 | token 4 | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|---:|---:|
| wall | 32,715 | 33,913 | 35,850 | 36,966 | 39,838 | 35,857 |
| main-thread busy | 32,663 (99.8 %) | 33,831 (99.8 %) | 35,758 (99.7 %) | 36,886 (99.8 %) | 39,700 (99.7 %) | 35,768 (99.8 %) |
| idle | 53 (0.2 %) | 82 (0.2 %) | 92 (0.3 %) | 80 (0.2 %) | 138 (0.3 %) | 89 (0.2 %) |
| style (UpdateLayoutTree) | 14,902 (45.6 %) | 15,823 (46.7 %) | 16,676 (46.5 %) | 17,707 (47.9 %) | 19,679 (49.4 %) | 16,957 (47.3 %) |
|   of which recalcStyle self (no nested GC) | 12,009 (36.7 %) | 12,490 (36.8 %) | 12,942 (36.1 %) | 13,657 (36.9 %) | 14,709 (36.9 %) | 13,161 (36.7 %) |
| layout | 5,357 (16.4 %) | 5,586 (16.5 %) | 6,363 (17.7 %) | 6,336 (17.1 %) | 6,889 (17.3 %) | 6,106 (17.0 %) |
|   of which text shaping | 2,047 (6.3 %) | 2,133 (6.3 %) | 2,488 (6.9 %) | 2,206 (6.0 %) | 2,296 (5.8 %) | 2,234 (6.2 %) |
| animation servicing (Blink.Animate) | 3,051 (9.3 %) | 3,064 (9.0 %) | 3,220 (9.0 %) | 3,214 (8.7 %) | 3,451 (8.7 %) | 3,200 (8.9 %) |
| pre-paint + compositing inputs | 1,818 (5.6 %) | 1,832 (5.4 %) | 1,848 (5.2 %) | 1,876 (5.1 %) | 1,909 (4.8 %) | 1,856 (5.2 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 5,327 (16.3 %) | 5,364 (15.8 %) | 5,405 (15.1 %) | 5,475 (14.8 %) | 5,476 (13.7 %) | 5,409 (15.1 %) |
|   of which Paint | 13 (0.0 %) | 13 (0.0 %) | 14 (0.0 %) | 14 (0.0 %) | 15 (0.0 %) | 14 (0.0 %) |
| hit-test (fake mousemove) | 909 (2.8 %) | 917 (2.7 %) | 983 (2.7 %) | 996 (2.7 %) | 1,031 (2.6 %) | 967 (2.7 %) |
| other busy (unattributed) | 1,299 (4.0 %) | 1,246 (3.7 %) | 1,263 (3.5 %) | 1,283 (3.5 %) | 1,265 (3.2 %) | 1,271 (3.5 %) |
| GC (nested inside the above) | 1,592 (4.9 %) | 1,938 (5.7 %) | 2,849 (7.9 %) | 2,752 (7.4 %) | 4,125 (10.4 %) | 2,651 (7.4 %) |
| style passes / layouts / frames | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | |
| major GCs | 3 | 3 | 3 | 3 | 4 | |
| token boundary (s after Run) | 57.1 | 91.0 | 126.9 | 163.9 | 203.7 | |
| handshakes (s after Run) | 55.3 token-3-ready; 56.8 token-3-ack | 89.2 token-4-ready; 90.7 token-4-ack | 125.0 token-5-ready; 126.5 token-5-ack | 161.9 token-6-ready; 163.5 token-6-ack | 201.5 token-7-ready; 203.2 token-7-ack | |

### combined-mouseoff-t1: style-pass histogram over the traced generate window (5 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 420 | 84.0 | 6,251 | 5.4 % | 14.9 | 6.5–24 | 29348.83 |
| 100-999 | 400 | 80.0 | 63,425 | 55.2 % | 158.6 | 23.1–1071 | 312.05 |
| 1k-9,999 | 330 | 66.0 | 40,448 | 35.2 % | 122.6 | 29.0–1186 | 34.05 |
| >=50%DOM | 7 | 1.4 | 4,718 | 4.1 % | 674.0 | 543.0–847 | 13.15 |
| **total** | 1157 | 231 | 114,842 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 1,553 | 74 | 14.8 | 14,960 | 202.2 | 130.2 |
| 357 | 68 | 13.6 | 14,707 | 216.3 | 605.8 |
| 784 | 81 | 16.2 | 11,262 | 139.0 | 177.3 |
| 126 | 81 | 16.2 | 11,241 | 138.8 | 1101.4 |
| 3,089 | 81 | 16.2 | 11,016 | 136.0 | 44.0 |
| 485 | 41 | 8.2 | 10,976 | 267.7 | 552.0 |
| 484 | 34 | 6.8 | 8,485 | 249.6 | 515.6 |
| 2,934 | 75 | 15.0 | 7,797 | 104.0 | 35.4 |
| 51,247 | 7 | 1.4 | 4,718 | 674.0 | 13.2 |
| 0 | 249 | 49.8 | 3,689 | 14.8 | – |
| 6,919 | 81 | 16.2 | 3,680 | 45.4 | 6.6 |
| 780 | 81 | 16.2 | 3,343 | 41.3 | 52.9 |
| 1 | 157 | 31.4 | 2,381 | 15.2 | 15166.9 |
| 487 | 7 | 1.4 | 2,038 | 291.1 | 597.8 |
| 2,326 | 7 | 1.4 | 1,463 | 209.1 | 89.9 |
| 368 | 6 | 1.2 | 1,331 | 221.8 | 602.9 |
| 2,917 | 6 | 1.2 | 920 | 153.3 | 52.5 |
| 1,438 | 6 | 1.2 | 613 | 102.1 | 71.0 |
| 2 | 7 | 1.4 | 120 | 17.2 | 8600.0 |
| 6 | 7 | 1.4 | 61 | 8.7 | 1445.2 |
| 127 | 1 | 0.2 | 42 | 42.1 | 331.5 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 3 | 1 | 847 | 5.7 % | [846.9, 51247] |
| 4 | 1 | 558 | 3.5 % | [557.8, 51247] |
| 5 | 1 | 581 | 3.5 % | [829.9, 784] |
| 6 | 1 | 658 | 3.7 % | [819.4, 357] |
| 7 | 1 | 797 | 4.1 % | [1071.5, 485] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 186223], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 183953], ['V8.GC_MC_CLEAR_STRING_TABLE', 75], ['V8.GC_MC_MARK_ROOTS', 65], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 64], ['V8.GC_MC_SWEEP', 62], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 48], ['V8.GC_MC_EVACUATE', 44]], total nested 19,357 ms

### combined-mouseoff-t1: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 370 | 1379 | 1829 |
| token 1 (0–57 s) | 1663 | 3084 | 4126 |
| token 2 (57–91 s) | 3919 | 4143 | 4450 |
| token 3 (91–127 s) | 3907 | 4162 | 4388 |
| token 4 (127–164 s) | 3497 | 3907 | 4247 |
| token 5 (164–204 s) | 3476 | 3783 | 4112 |
| rest of run (204–284 s) | 3225 | 3618 | 4061 |
| after completion (readback) | 3514 | 3748 | 3893 |
| browser process peak | | | 221 |
| GPU process peak | | | 145 |

CDP Performance.getMetrics deltas Run→end (286.2 s wall): RecalcStyleCount +1399, RecalcStyleDuration +135.8 s, LayoutCount +872, LayoutDuration +47.7 s, TaskDuration +284.9 s; Nodes 134295, LayoutObjects 141817

Load phase (combined-mouseoff-t1): {}
named: null
big: []
nav: {'responseEnd': 59.69999998807907, 'domInteractive': 1188.699999988079, 'domContentLoadedEventEnd': 1188.699999988079, 'domComplete': 2518.4000000059605, 'loadEventEnd': 2519.5999999940395} {'resources': 250, 'resourceBytes': 144209406, 'resourceEncodedBytes': 144209406, 'lastResourceEnd': 1525.9000000059605, 'cssResource': {'startTime': 19.5, 'responseEnd': 86.7999999821186, 'decodedBodySize': 41666858, 'encodedBodySize': 41666858}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 1012}, {'name': 'first-contentful-paint', 'startTime': 1012}], 'fontsStatus': 'loaded', 'fontsSize': 283, 'elements': 69522, 'scripts': 0}
timeline: {'tNav0': 1025.7, 'tLoad': 3551.5, 'tIdle': 5803, 'tRun': 5813.4, 'tEndWait': 290026.4, 'stopReason': 'token-limit', 'traceBytes': 142588363, 'dataLossOccurred': True} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "0", "--winner": "1101", "--head-output-epoch": "8"}}
