### F5-t1: per-token phase split (ms; % of window wall)

| phase | token 3 | token 4 | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|---:|---:|
| wall | 36,911 | 39,388 | 43,492 | 44,408 | 48,050 | 42,450 |
| main-thread busy | 36,852 (99.8 %) | 39,329 (99.8 %) | 43,418 (99.8 %) | 44,327 (99.8 %) | 47,922 (99.7 %) | 42,369 (99.8 %) |
| idle | 59 (0.2 %) | 59 (0.2 %) | 74 (0.2 %) | 81 (0.2 %) | 128 (0.3 %) | 80 (0.2 %) |
| style (UpdateLayoutTree) | 17,188 (46.6 %) | 18,674 (47.4 %) | 20,723 (47.6 %) | 21,784 (49.1 %) | 23,407 (48.7 %) | 20,355 (48.0 %) |
|   of which recalcStyle self (no nested GC) | 13,901 (37.7 %) | 14,393 (36.5 %) | 15,789 (36.3 %) | 16,756 (37.7 %) | 17,901 (37.3 %) | 15,748 (37.1 %) |
| layout | 5,800 (15.7 %) | 6,296 (16.0 %) | 7,758 (17.8 %) | 7,774 (17.5 %) | 9,670 (20.1 %) | 7,460 (17.6 %) |
|   of which text shaping | 2,263 (6.1 %) | 2,275 (5.8 %) | 2,524 (5.8 %) | 2,420 (5.5 %) | 2,494 (5.2 %) | 2,395 (5.6 %) |
| animation servicing (Blink.Animate) | 3,695 (10.0 %) | 3,794 (9.6 %) | 3,916 (9.0 %) | 4,090 (9.2 %) | 4,119 (8.6 %) | 3,923 (9.2 %) |
| pre-paint + compositing inputs | 2,040 (5.5 %) | 2,018 (5.1 %) | 2,318 (5.3 %) | 2,112 (4.8 %) | 2,093 (4.4 %) | 2,116 (5.0 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 5,669 (15.4 %) | 6,050 (15.4 %) | 6,101 (14.0 %) | 5,955 (13.4 %) | 5,978 (12.4 %) | 5,950 (14.0 %) |
|   of which Paint | 14 (0.0 %) | 14 (0.0 %) | 15 (0.0 %) | 16 (0.0 %) | 16 (0.0 %) | 15 (0.0 %) |
| hit-test (fake mousemove) | 1,082 (2.9 %) | 1,119 (2.8 %) | 1,187 (2.7 %) | 1,257 (2.8 %) | 1,280 (2.7 %) | 1,185 (2.8 %) |
| other busy (unattributed) | 1,378 (3.7 %) | 1,379 (3.5 %) | 1,415 (3.3 %) | 1,354 (3.0 %) | 1,375 (2.9 %) | 1,380 (3.3 %) |
| GC (nested inside the above) | 1,998 (5.4 %) | 3,099 (7.9 %) | 5,067 (11.6 %) | 4,654 (10.5 %) | 6,971 (14.5 %) | 4,358 (10.3 %) |
| style passes / layouts / frames | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | |
| major GCs | 4 | 3 | 4 | 3 | 4 | |
| token boundary (s after Run) | 60.4 | 99.8 | 143.3 | 187.7 | 235.7 | |
| handshakes (s after Run) | 58.2 token-3-ready; 59.9 token-3-ack | 97.7 token-4-ready; 99.4 token-4-ack | 139.9 token-5-ready; 141.9 token-5-ack | 185.4 token-6-ready; 187.2 token-6-ack | 233.5 token-7-ready; 235.3 token-7-ack | |

### F5-t1: style-pass histogram over the traced generate window (5 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 412 | 82.4 | 7,761 | 5.7 % | 18.8 | 7.2–30 | 37133.97 |
| 100-999 | 159 | 31.8 | 17,093 | 12.5 % | 107.5 | 24.5–1408 | 238.39 |
| 1k-9,999 | 557 | 111.4 | 105,620 | 77.2 % | 189.6 | 22.6–1746 | 52.62 |
| >=50%DOM | 7 | 1.4 | 6,427 | 4.7 % | 918.2 | 651.6–1087 | 16.9 |
| **total** | 1135 | 227 | 136,902 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 3,429 | 67 | 13.4 | 21,956 | 327.7 | 95.6 |
| 3,557 | 40 | 8.0 | 13,791 | 344.8 | 96.9 |
| 126 | 79 | 15.8 | 13,282 | 168.1 | 1334.4 |
| 1,553 | 73 | 14.6 | 13,275 | 181.8 | 117.1 |
| 3,856 | 80 | 16.0 | 12,722 | 159.0 | 41.2 |
| 3,089 | 80 | 16.0 | 11,731 | 146.6 | 47.5 |
| 3,556 | 33 | 6.6 | 11,354 | 344.1 | 96.8 |
| 2,934 | 73 | 14.6 | 9,949 | 136.3 | 46.5 |
| 54,319 | 7 | 1.4 | 6,427 | 918.2 | 16.9 |
| 0 | 245 | 49.0 | 4,602 | 18.8 | – |
| 780 | 79 | 15.8 | 3,765 | 47.7 | 61.1 |
| 1 | 153 | 30.6 | 2,930 | 19.2 | 19151.0 |
| 3,440 | 6 | 1.2 | 2,408 | 401.2 | 116.6 |
| 6,919 | 79 | 15.8 | 2,299 | 29.1 | 4.2 |
| 3,559 | 7 | 1.4 | 2,294 | 327.7 | 92.1 |
| 1,438 | 6 | 1.2 | 1,526 | 254.2 | 176.8 |
| 2,326 | 7 | 1.4 | 1,302 | 186.0 | 80.0 |
| 2,917 | 6 | 1.2 | 1,016 | 169.4 | 58.1 |
| 2 | 7 | 1.4 | 160 | 22.8 | 11392.9 |
| 6 | 7 | 1.4 | 69 | 9.9 | 1642.9 |
| 127 | 1 | 0.2 | 45 | 45.4 | 357.5 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 3 | 1 | 652 | 3.8 % | [651.6, 54319] |
| 4 | 1 | 1,087 | 5.8 % | [1086.8, 54319] |
| 5 | 1 | 907 | 4.4 % | [967.9, 1438] |
| 6 | 1 | 862 | 4.0 % | [1241.0, 2934] |
| 7 | 1 | 1,084 | 4.6 % | [1408.2, 126] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 202615], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 199957], ['V8.GC_MC_CLEAR_STRING_TABLE', 76], ['V8.GC_MC_MARK_ROOTS', 74], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 71], ['V8.GC_MC_SWEEP', 70], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 52], ['V8.GC_TIME_TO_SAFEPOINT', 50]], total nested 28,931 ms

### F5-t1: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 1161 | 1525 | 1648 |
| token 1 (0–60 s) | 1663 | 2934 | 3802 |
| token 2 (60–100 s) | 3143 | 3475 | 3861 |
| token 3 (100–143 s) | 2983 | 3355 | 3865 |
| token 4 (143–188 s) | 2698 | 3162 | 3589 |
| token 5 (188–236 s) | 2642 | 3046 | 3449 |
| rest of run (236–329 s) | 2414 | 2986 | 3469 |
| after completion (readback) | 2983 | 3177 | 3376 |
| browser process peak | | | 221 |
| GPU process peak | | | 143 |

CDP Performance.getMetrics deltas Run→end (331.4 s wall): RecalcStyleCount +1400, RecalcStyleDuration +160.8 s, LayoutCount +872, LayoutDuration +54.0 s, TaskDuration +330.2 s; Nodes 139610, LayoutObjects 146358

Load phase (F5-t1): {}
named: null
big: []
nav: {'responseEnd': 52.80000001192093, 'domInteractive': 1351.9000000059605, 'domContentLoadedEventEnd': 1352.0999999940395, 'domComplete': 1813.5, 'loadEventEnd': 1813.9000000059605} {'resources': 250, 'resourceBytes': 138428217, 'resourceEncodedBytes': 138428217, 'lastResourceEnd': 930.4000000059605, 'cssResource': {'startTime': 11.200000017881393, 'responseEnd': 51.599999994039536, 'decodedBodySize': 35607509, 'encodedBodySize': 35607509}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 496}, {'name': 'first-contentful-paint', 'startTime': 496}], 'fontsStatus': 'loaded', 'fontsSize': 261, 'elements': 72549, 'scripts': 0}
timeline: {'tNav0': 557.9, 'tLoad': 2380, 'tIdle': 4641.1, 'tRun': 4647.7, 'tEndWait': 334052, 'stopReason': 'token-limit', 'traceBytes': 152015516, 'dataLossOccurred': True} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "0", "--winner": "1101", "--head-output-epoch": "8"}}
