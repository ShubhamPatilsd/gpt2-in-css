### combined-t1: per-token phase split (ms; % of window wall)

| phase | token 3 | token 4 | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|---:|---:|
| wall | 34,079 | 35,416 | 36,325 | 38,530 | 40,648 | 36,999 |
| main-thread busy | 34,035 (99.9 %) | 35,340 (99.8 %) | 36,231 (99.7 %) | 38,439 (99.8 %) | 40,538 (99.7 %) | 36,917 (99.8 %) |
| idle | 44 (0.1 %) | 76 (0.2 %) | 94 (0.3 %) | 91 (0.2 %) | 110 (0.3 %) | 83 (0.2 %) |
| style (UpdateLayoutTree) | 15,605 (45.8 %) | 16,222 (45.8 %) | 16,351 (45.0 %) | 17,864 (46.4 %) | 19,553 (48.1 %) | 17,119 (46.3 %) |
|   of which recalcStyle self (no nested GC) | 12,560 (36.9 %) | 12,997 (36.7 %) | 13,211 (36.4 %) | 13,995 (36.3 %) | 14,917 (36.7 %) | 13,536 (36.6 %) |
| layout | 5,288 (15.5 %) | 5,614 (15.9 %) | 6,220 (17.1 %) | 6,676 (17.3 %) | 6,851 (16.9 %) | 6,130 (16.6 %) |
|   of which text shaping | 1,975 (5.8 %) | 2,092 (5.9 %) | 2,213 (6.1 %) | 2,306 (6.0 %) | 2,359 (5.8 %) | 2,189 (5.9 %) |
| animation servicing (Blink.Animate) | 3,502 (10.3 %) | 3,577 (10.1 %) | 3,604 (9.9 %) | 3,738 (9.7 %) | 3,814 (9.4 %) | 3,647 (9.9 %) |
| pre-paint + compositing inputs | 1,891 (5.6 %) | 1,924 (5.4 %) | 1,969 (5.4 %) | 2,014 (5.2 %) | 1,996 (4.9 %) | 1,959 (5.3 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 5,412 (15.9 %) | 5,648 (15.9 %) | 5,679 (15.6 %) | 5,662 (14.7 %) | 5,780 (14.2 %) | 5,636 (15.2 %) |
|   of which Paint | 13 (0.0 %) | 14 (0.0 %) | 14 (0.0 %) | 14 (0.0 %) | 16 (0.0 %) | 14 (0.0 %) |
| hit-test (fake mousemove) | 1,002 (2.9 %) | 1,034 (2.9 %) | 1,070 (2.9 %) | 1,091 (2.8 %) | 1,109 (2.7 %) | 1,061 (2.9 %) |
| other busy (unattributed) | 1,335 (3.9 %) | 1,320 (3.7 %) | 1,338 (3.7 %) | 1,394 (3.6 %) | 1,436 (3.5 %) | 1,365 (3.7 %) |
| GC (nested inside the above) | 1,593 (4.7 %) | 1,693 (4.8 %) | 1,794 (4.9 %) | 2,645 (6.9 %) | 3,374 (8.3 %) | 2,220 (6.0 %) |
| style passes / layouts / frames | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | 171 / 109 / 85 | |
| major GCs | 3 | 3 | 3 | 3 | 3 | |
| token boundary (s after Run) | 57.6 | 93.0 | 129.3 | 167.9 | 208.5 | |
| handshakes (s after Run) | 55.7 token-3-ready; 57.3 token-3-ack | 91.1 token-4-ready; 92.6 token-4-ack | 127.3 token-5-ready; 128.9 token-5-ack | 165.8 token-6-ready; 167.5 token-6-ack | 206.4 token-7-ready; 208.1 token-7-ack | |

### combined-t1: style-pass histogram over the traced generate window (5 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 416 | 83.2 | 6,903 | 5.9 % | 16.6 | 7.7–26 | 32715.17 |
| 100-999 | 397 | 79.4 | 63,794 | 54.8 % | 160.7 | 22.8–1396 | 316.03 |
| 1k-9,999 | 327 | 65.4 | 41,075 | 35.3 % | 125.6 | 31.0–853 | 34.95 |
| >=50%DOM | 7 | 1.4 | 4,738 | 4.1 % | 676.8 | 578.5–813 | 13.21 |
| **total** | 1147 | 229 | 116,510 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 357 | 68 | 13.6 | 16,940 | 249.1 | 697.8 |
| 1,553 | 74 | 14.8 | 15,924 | 215.2 | 138.6 |
| 784 | 81 | 16.2 | 10,678 | 131.8 | 168.1 |
| 485 | 40 | 8.0 | 10,666 | 266.6 | 549.8 |
| 126 | 80 | 16.0 | 10,533 | 131.7 | 1044.9 |
| 3,089 | 80 | 16.0 | 10,343 | 129.3 | 41.9 |
| 2,934 | 74 | 14.8 | 8,512 | 115.0 | 39.2 |
| 484 | 34 | 6.8 | 8,393 | 246.9 | 510.0 |
| 51,247 | 7 | 1.4 | 4,738 | 676.8 | 13.2 |
| 0 | 247 | 49.4 | 4,100 | 16.6 | – |
| 780 | 80 | 16.0 | 3,394 | 42.4 | 54.4 |
| 6,919 | 80 | 16.0 | 3,224 | 40.3 | 5.8 |
| 1 | 155 | 31.0 | 2,608 | 16.8 | 16828.4 |
| 487 | 7 | 1.4 | 1,755 | 250.7 | 514.8 |
| 2,326 | 7 | 1.4 | 1,498 | 214.0 | 92.0 |
| 368 | 6 | 1.2 | 1,395 | 232.5 | 631.8 |
| 2,917 | 6 | 1.2 | 956 | 159.4 | 54.6 |
| 1,438 | 6 | 1.2 | 617 | 102.9 | 71.6 |
| 2 | 7 | 1.4 | 127 | 18.2 | 9078.6 |
| 6 | 7 | 1.4 | 67 | 9.6 | 1595.2 |
| 127 | 1 | 0.2 | 41 | 40.8 | 321.3 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 3 | 1 | 601 | 3.9 % | [601.0, 51247] |
| 4 | 1 | 813 | 5.0 % | [813.0, 51247] |
| 5 | 1 | 578 | 3.5 % | [578.5, 51247] |
| 6 | 1 | 626 | 3.5 % | [853.4, 1553] |
| 7 | 1 | 696 | 3.6 % | [940.5, 357] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 184595], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 182585], ['V8.GC_MC_MARK_ROOTS', 66], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 65], ['V8.GC_MC_SWEEP', 63], ['V8.GC_MC_CLEAR_STRING_TABLE', 61], ['V8.GC_TIME_TO_SAFEPOINT', 45], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 45]], total nested 17,085 ms

### combined-t1: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 641 | 1456 | 1834 |
| token 1 (0–58 s) | 1679 | 3504 | 4434 |
| token 2 (58–93 s) | 4159 | 4453 | 4602 |
| token 3 (93–129 s) | 4526 | 4716 | 4898 |
| token 4 (129–168 s) | 4289 | 4685 | 4928 |
| token 5 (168–209 s) | 3788 | 4294 | 4879 |
| rest of run (209–292 s) | 3011 | 3676 | 4162 |
| after completion (readback) | 3746 | 3799 | 3853 |
| browser process peak | | | 225 |
| GPU process peak | | | 141 |

CDP Performance.getMetrics deltas Run→end (294.1 s wall): RecalcStyleCount +1400, RecalcStyleDuration +138.0 s, LayoutCount +872, LayoutDuration +47.3 s, TaskDuration +292.7 s; Nodes 134295, LayoutObjects 141817

Load phase (combined-t1): {}
named: null
big: []
nav: {'responseEnd': 48.099999994039536, 'domInteractive': 1107.800000011921, 'domContentLoadedEventEnd': 1107.9000000059605, 'domComplete': 2189.2000000178814, 'loadEventEnd': 2189.800000011921} {'resources': 250, 'resourceBytes': 143513818, 'resourceEncodedBytes': 143513818, 'lastResourceEnd': 1303.300000011921, 'cssResource': {'startTime': 9, 'responseEnd': 61.30000001192093, 'decodedBodySize': 41666858, 'encodedBodySize': 41666858}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 856}, {'name': 'first-contentful-paint', 'startTime': 856}], 'fontsStatus': 'loaded', 'fontsSize': 283, 'elements': 69522, 'scripts': 0}
timeline: {'tNav0': 569.9, 'tLoad': 2774.1, 'tIdle': 5016.5, 'tRun': 5028, 'tEndWait': 297119, 'stopReason': 'token-limit', 'traceBytes': 147621681, 'dataLossOccurred': True} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "0", "--winner": "1101", "--head-output-epoch": "8"}}
