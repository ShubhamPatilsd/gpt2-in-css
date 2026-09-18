### fullring: per-token phase split (ms; % of window wall)

| phase | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|
| wall | 48,140 | 50,636 | 54,391 | 51,056 |
| main-thread busy | 48,091 (99.9 %) | 50,461 (99.7 %) | 54,337 (99.9 %) | 50,963 (99.8 %) |
| idle | 49 (0.1 %) | 175 (0.3 %) | 53 (0.1 %) | 93 (0.2 %) |
| style (UpdateLayoutTree) | 25,651 (53.3 %) | 27,755 (54.8 %) | 30,624 (56.3 %) | 28,010 (54.9 %) |
|   of which recalcStyle self (no nested GC) | 21,078 (43.8 %) | 21,402 (42.3 %) | 23,092 (42.5 %) | 21,857 (42.8 %) |
| layout | 7,760 (16.1 %) | 8,242 (16.3 %) | 8,490 (15.6 %) | 8,164 (16.0 %) |
|   of which text shaping | 2,296 (4.8 %) | 2,383 (4.7 %) | 2,346 (4.3 %) | 2,342 (4.6 %) |
| animation servicing (Blink.Animate) | 3,934 (8.2 %) | 3,899 (7.7 %) | 4,040 (7.4 %) | 3,958 (7.8 %) |
| pre-paint + compositing inputs | 2,062 (4.3 %) | 2,084 (4.1 %) | 2,051 (3.8 %) | 2,066 (4.0 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 5,982 (12.4 %) | 5,898 (11.6 %) | 5,979 (11.0 %) | 5,953 (11.7 %) |
|   of which Paint | 16 (0.0 %) | 16 (0.0 %) | 17 (0.0 %) | 16 (0.0 %) |
| hit-test (fake mousemove) | 1,572 (3.3 %) | 1,511 (3.0 %) | 1,576 (2.9 %) | 1,553 (3.0 %) |
| other busy (unattributed) | 1,132 (2.4 %) | 1,071 (2.1 %) | 1,576 (2.9 %) | 1,260 (2.5 %) |
| GC (nested inside the above) | 4,801 (10.0 %) | 7,104 (14.0 %) | 9,294 (17.1 %) | 7,066 (13.8 %) |
| style passes / layouts / frames | 171 / 110 / 85 | 171 / 110 / 85 | 171 / 110 / 85 | |
| major GCs | 3 | 4 | 4 | |
| token boundary (s after Run) | 51.5 | 102.1 | 156.5 | |
| handshakes (s after Run) | 47.9 token-5-ready; 51.0 token-5-ack | 99.0 token-6-ready; 101.7 token-6-ack | 152.9 token-7-ready; 156.0 token-7-ack | |

### fullring: style-pass histogram over the traced generate window (3 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 245 | 81.7 | 4,715 | 4.0 % | 19.2 | 16.0–42 | 46683.17 |
| 100-999 | 97 | 32.3 | 13,192 | 11.3 % | 136.0 | 30.2–1824 | 302.47 |
| 1k-9,999 | 293 | 97.7 | 60,782 | 51.9 % | 207.4 | 38.5–1725 | 57.05 |
| 10k-<50%DOM | 44 | 14.7 | 26,694 | 22.8 % | 606.7 | 428.3–2377 | 49.42 |
| >=50%DOM | 9 | 3.0 | 11,695 | 10.0 % | 1299.4 | 956.3–1919 | 20.32 |
| **total** | 688 | 229 | 117,078 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 12,274 | 40 | 13.3 | 23,409 | 585.2 | 47.7 |
| 3,545 | 29 | 9.7 | 12,763 | 440.1 | 124.1 |
| 1,553 | 44 | 14.7 | 11,646 | 264.7 | 170.4 |
| 126 | 48 | 16.0 | 9,959 | 207.5 | 1646.6 |
| 3,856 | 48 | 16.0 | 9,567 | 199.3 | 51.7 |
| 3,544 | 20 | 6.7 | 7,949 | 397.5 | 112.2 |
| 3,089 | 48 | 16.0 | 7,919 | 165.0 | 53.4 |
| 63,946 | 5 | 1.7 | 6,221 | 1244.2 | 19.5 |
| 2,935 | 44 | 14.7 | 6,212 | 141.2 | 48.1 |
| 63,933 | 4 | 1.3 | 5,474 | 1368.5 | 21.4 |
| 12,285 | 4 | 1.3 | 3,285 | 821.2 | 66.8 |
| 780 | 48 | 16.0 | 3,186 | 66.4 | 85.1 |
| 0 | 148 | 49.3 | 2,829 | 19.1 | – |
| 6,919 | 48 | 16.0 | 2,384 | 49.7 | 7.2 |
| 1 | 93 | 31.0 | 1,796 | 19.3 | 19317.2 |
| 2,326 | 4 | 1.3 | 1,033 | 258.2 | 111.0 |
| 2,917 | 4 | 1.3 | 817 | 204.2 | 70.0 |
| 1,958 | 4 | 1.3 | 492 | 123.0 | 62.8 |
| 2 | 4 | 1.3 | 90 | 22.5 | 11237.5 |
| 127 | 1 | 0.3 | 48 | 47.6 | 374.8 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 5 | 2 | 2,472 | 9.6 % | [1293.1, 63946] |
| 6 | 2 | 2,311 | 8.3 % | [1484.8, 3545] |
| 7 | 2 | 2,565 | 8.4 % | [1824.4, 126] |

### fullring: invalidation tracking (traced window)

| event | reason | count | per token |
|---|---|---:|---:|

StyleInvalidator / ScheduleStyleInvalidation by selector part (per token ≈ count/4):

| event | reason | part | count |
|---|---|---|---:|

GC by name (window): [['V8.GC_MC_INCREMENTAL', 146476], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 144728], ['V8.GC_MC_MARK_ROOTS', 50], ['V8.GC_MC_SWEEP', 50], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 48], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 38], ['V8.GC_TIME_TO_SAFEPOINT', 34], ['V8.GC_MC_EVACUATE', 34]], total nested 31,907 ms

### fullring: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 560 | 1429 | 1823 |
| token 1 (0–51 s) | 1670 | 2714 | 3509 |
| token 2 (51–102 s) | 2734 | 3229 | 3722 |
| token 3 (102–157 s) | 2938 | 3437 | 3898 |
| rest of run (157–378 s) | 1492 | 3067 | 4249 |
| after completion (readback) | 3843 | 3982 | 4122 |
| browser process peak | | | 225 |
| GPU process peak | | | 139 |

CDP Performance.getMetrics deltas Run→end (379.9 s wall): RecalcStyleCount +1401, RecalcStyleDuration +206.3 s, LayoutCount +880, LayoutDuration +55.6 s, TaskDuration +378.5 s; Nodes 139600, LayoutObjects 146358

Load phase (fullring): {}
named: null
big: []
nav: {'responseEnd': 49.80000001192093, 'domInteractive': 994.3000000119209, 'domContentLoadedEventEnd': 994.4000000059605, 'domComplete': 2374, 'loadEventEnd': 2374.5} {'resources': 250, 'resourceBytes': 148357698, 'resourceEncodedBytes': 148357698, 'lastResourceEnd': 1364.4000000059605, 'cssResource': {'startTime': 12.700000002980232, 'responseEnd': 96.6000000089407, 'decodedBodySize': 45783674, 'encodedBodySize': 45783674}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 876}, {'name': 'first-contentful-paint', 'startTime': 876}], 'fontsStatus': 'loaded', 'fontsSize': 261, 'elements': 72549, 'scripts': 0}
timeline: {'tNav0': 706.4, 'tLoad': 3099, 'tIdle': 5350.4, 'tRun': 5356.6, 'tEndWait': 383253.6, 'stopReason': 'token-limit', 'traceBytes': 151132441, 'dataLossOccurred': True} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "8", "--winner": "1101", "--head-output-epoch": "8"}}
