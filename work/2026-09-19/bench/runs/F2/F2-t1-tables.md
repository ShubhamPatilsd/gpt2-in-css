### F2-t1: per-token phase split (ms; % of window wall)

| phase | token 3 | token 4 | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|---:|---:|
| wall | 36,217 | 37,553 | 42,780 | 44,963 | 51,195 | 42,542 |
| main-thread busy | 36,154 (99.8 %) | 37,497 (99.9 %) | 42,677 (99.8 %) | 44,878 (99.8 %) | 51,274 (100.2 %) | 42,496 (99.9 %) |
| idle | 63 (0.2 %) | 56 (0.1 %) | 102 (0.2 %) | 85 (0.2 %) | -79 (-0.2 %) | 46 (0.1 %) |
| style (UpdateLayoutTree) | 18,258 (50.4 %) | 18,956 (50.5 %) | 22,730 (53.1 %) | 24,331 (54.1 %) | 28,824 (56.3 %) | 22,620 (53.2 %) |
|   of which recalcStyle self (no nested GC) | 15,169 (41.9 %) | 15,748 (41.9 %) | 18,552 (43.4 %) | 18,940 (42.1 %) | 23,016 (45.0 %) | 18,285 (43.0 %) |
| layout | 5,360 (14.8 %) | 5,818 (15.5 %) | 6,697 (15.7 %) | 6,816 (15.2 %) | 8,566 (16.7 %) | 6,652 (15.6 %) |
|   of which text shaping | 1,977 (5.5 %) | 2,118 (5.6 %) | 2,240 (5.2 %) | 2,276 (5.1 %) | 2,370 (4.6 %) | 2,196 (5.2 %) |
| animation servicing (Blink.Animate) | 3,183 (8.8 %) | 3,267 (8.7 %) | 3,364 (7.9 %) | 3,536 (7.9 %) | 3,610 (7.1 %) | 3,392 (8.0 %) |
| pre-paint + compositing inputs | 1,814 (5.0 %) | 1,881 (5.0 %) | 2,008 (4.7 %) | 1,974 (4.4 %) | 1,977 (3.9 %) | 1,931 (4.5 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 5,403 (14.9 %) | 5,374 (14.3 %) | 5,659 (13.2 %) | 5,866 (13.0 %) | 5,711 (11.2 %) | 5,603 (13.2 %) |
|   of which Paint | 12 (0.0 %) | 13 (0.0 %) | 14 (0.0 %) | 14 (0.0 %) | 16 (0.0 %) | 14 (0.0 %) |
| hit-test (fake mousemove) | 1,167 (3.2 %) | 1,286 (3.4 %) | 1,295 (3.0 %) | 1,430 (3.2 %) | 1,596 (3.1 %) | 1,355 (3.2 %) |
| other busy (unattributed) | 968 (2.7 %) | 915 (2.4 %) | 924 (2.2 %) | 924 (2.1 %) | 990 (1.9 %) | 944 (2.2 %) |
| GC (nested inside the above) | 1,808 (5.0 %) | 1,823 (4.9 %) | 3,169 (7.4 %) | 4,500 (10.0 %) | 6,013 (11.7 %) | 3,462 (8.1 %) |
| style passes / layouts / frames | 171 / 110 / 85 | 171 / 110 / 85 | 171 / 110 / 85 | 171 / 110 / 85 | 171 / 110 / 85 | |
| major GCs | 3 | 3 | 4 | 3 | 3 | |
| token boundary (s after Run) | 60.6 | 98.2 | 140.9 | 185.9 | 237.1 | |
| handshakes (s after Run) | 58.1 token-3-ready; 60.2 token-3-ack | 95.4 token-4-ready; 97.7 token-4-ack | 135.2 token-5-ready; 140.5 token-5-ack | 182.9 token-6-ready; 185.5 token-6-ack | 231.2 token-7-ready; 236.6 token-7-ack | |

### F2-t1: style-pass histogram over the traced generate window (5 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 406 | 81.2 | 6,860 | 4.5 % | 16.9 | 12.6–41 | 41074.85 |
| 100-999 | 321 | 64.2 | 49,552 | 32.5 % | 154.4 | 25.9–1744 | 286.21 |
| 1k-9,999 | 398 | 79.6 | 77,626 | 50.9 % | 195.0 | 19.9–2159 | 42.06 |
| >=50%DOM | 14 | 2.8 | 18,518 | 12.1 % | 1322.7 | 699.3–3703 | 21.73 |
| **total** | 1139 | 228 | 152,556 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 9,200 | 67 | 13.4 | 29,989 | 447.6 | 48.7 |
| 1,553 | 73 | 14.6 | 18,394 | 252.0 | 162.3 |
| 126 | 80 | 16.0 | 12,509 | 156.4 | 1241.0 |
| 473 | 47 | 9.4 | 12,188 | 259.3 | 548.3 |
| 60,872 | 7 | 1.4 | 11,542 | 1648.9 | 27.1 |
| 784 | 80 | 16.0 | 11,151 | 139.4 | 177.8 |
| 472 | 33 | 6.6 | 9,868 | 299.0 | 633.5 |
| 3,089 | 80 | 16.0 | 9,657 | 120.7 | 39.1 |
| 2,935 | 73 | 14.6 | 8,822 | 120.8 | 41.2 |
| 60,859 | 7 | 1.4 | 6,976 | 996.6 | 16.4 |
| 9,211 | 6 | 1.2 | 5,065 | 844.2 | 91.7 |
| 0 | 246 | 49.2 | 4,125 | 16.8 | – |
| 780 | 80 | 16.0 | 3,796 | 47.4 | 60.8 |
| 1 | 153 | 30.6 | 2,595 | 17.0 | 16962.1 |
| 6,919 | 80 | 16.0 | 2,227 | 27.8 | 4.0 |
| 2,326 | 7 | 1.4 | 1,732 | 247.4 | 106.4 |
| 2,917 | 6 | 1.2 | 1,112 | 185.3 | 63.5 |
| 1,958 | 6 | 1.2 | 628 | 104.6 | 53.4 |
| 2 | 7 | 1.4 | 139 | 19.9 | 9935.7 |
| 127 | 1 | 0.2 | 40 | 39.8 | 313.4 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 3 | 2 | 1,531 | 8.4 % | [789.6, 60859] |
| 4 | 2 | 1,576 | 8.3 % | [828.4, 60872] |
| 5 | 2 | 4,417 | 19.4 % | [3536.2, 60872] |
| 6 | 2 | 2,587 | 10.6 % | [1611.5, 60859] |
| 7 | 2 | 4,780 | 16.6 % | [3702.6, 60872] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 219883], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 216912], ['V8.GC_MC_MARK_ROOTS', 71], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 71], ['V8.GC_MC_SWEEP', 65], ['V8.GC_MC_CLEAR_STRING_TABLE', 62], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 51], ['V8.GC_MC_EVACUATE', 48]], total nested 27,082 ms

### F2-t1: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 646 | 1452 | 1823 |
| token 1 (0–61 s) | 1673 | 3370 | 4100 |
| token 2 (61–98 s) | 4173 | 4577 | 4928 |
| token 3 (98–141 s) | 4482 | 4815 | 5005 |
| token 4 (141–186 s) | 3971 | 4529 | 4931 |
| token 5 (186–237 s) | 2696 | 3880 | 4382 |
| rest of run (237–334 s) | 3206 | 3724 | 4323 |
| after completion (readback) | 4231 | 4278 | 4326 |
| browser process peak | | | 221 |
| GPU process peak | | | 139 |

CDP Performance.getMetrics deltas Run→end (336.3 s wall): RecalcStyleCount +1401, RecalcStyleDuration +179.1 s, LayoutCount +880, LayoutDuration +50.7 s, TaskDuration +334.7 s; Nodes 134224, LayoutObjects 141750

Load phase (F2-t1): {}
named: null
big: []
nav: {'responseEnd': 54.70000001788139, 'domInteractive': 1190.800000011921, 'domContentLoadedEventEnd': 1191, 'domComplete': 2200.0999999940395, 'loadEventEnd': 2200.4000000059605} {'resources': 250, 'resourceBytes': 143348994, 'resourceEncodedBytes': 143348994, 'lastResourceEnd': 1306.800000011921, 'cssResource': {'startTime': 10.300000011920929, 'responseEnd': 53.70000001788139, 'decodedBodySize': 41266846, 'encodedBodySize': 41266846}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 860}, {'name': 'first-contentful-paint', 'startTime': 860}], 'fontsStatus': 'loaded', 'fontsSize': 261, 'elements': 69477, 'scripts': 0}
timeline: {'tNav0': 527.8, 'tLoad': 2743.1, 'tIdle': 5177.1, 'tRun': 5189.6, 'tEndWait': 339459.9, 'stopReason': 'token-limit', 'traceBytes': 145340037, 'dataLossOccurred': True} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "8", "--winner": "1101", "--head-output-epoch": "8"}}
