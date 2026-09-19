### ab-lock: per-token phase split (ms; % of window wall)

| phase | token 1 | token 2 | mean |
|---|---:|---:|---:|
| wall | 32,759 | 32,221 | 32,490 |
| main-thread busy | 32,947 (100.6 %) | 32,181 (99.9 %) | 32,564 (100.2 %) |
| idle | -188 (-0.6 %) | 41 (0.1 %) | -74 (-0.2 %) |
| style (UpdateLayoutTree) | 17,058 (52.1 %) | 14,640 (45.4 %) | 15,849 (48.8 %) |
|   of which recalcStyle self (no nested GC) | 14,927 (45.6 %) | 11,984 (37.2 %) | 13,455 (41.4 %) |
| layout | 4,455 (13.6 %) | 5,030 (15.6 %) | 4,742 (14.6 %) |
|   of which text shaping | 1,863 (5.7 %) | 1,942 (6.0 %) | 1,902 (5.9 %) |
| animation servicing (Blink.Animate) | 2,790 (8.5 %) | 3,200 (9.9 %) | 2,995 (9.2 %) |
| pre-paint + compositing inputs | 1,815 (5.5 %) | 1,898 (5.9 %) | 1,857 (5.7 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 4,599 (14.0 %) | 5,211 (16.2 %) | 4,905 (15.1 %) |
|   of which Paint | 12 (0.0 %) | 12 (0.0 %) | 12 (0.0 %) |
| hit-test (fake mousemove) | 730 (2.2 %) | 912 (2.8 %) | 821 (2.5 %) |
| other busy (unattributed) | 1,500 (4.6 %) | 1,290 (4.0 %) | 1,395 (4.3 %) |
| GC (nested inside the above) | 958 (2.9 %) | 1,410 (4.4 %) | 1,184 (3.6 %) |
| style passes / layouts / frames | 172 / 110 / 91 | 171 / 109 / 85 | |
| major GCs | 4 | 4 | |
| token boundary (s after Run) | 32.8 | 65.0 | |
| handshakes (s after Run) | 0.1 run-start; 31.0 token-1-ready; 32.4 token-1-ack | 63.1 token-2-ready; 64.6 token-2-ack | |

### ab-lock: style-pass histogram over the traced generate window (2 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 128 | 64.0 | 1,670 | 5.1 % | 13.0 | 0.1–17 | 24920.9 |
| 10-99 | 1 | 0.5 | 57 | 0.2 % | 57.4 | 57.4–57 | 1435.0 |
| 100-999 | 122 | 61.0 | 15,882 | 48.5 % | 130.2 | 25.1–486 | 255.67 |
| 1k-9,999 | 102 | 51.0 | 14,071 | 43.0 % | 137.9 | 26.9–1695 | 38.36 |
| >=50%DOM | 2 | 1.0 | 1,056 | 3.2 % | 528.2 | 475.1–581 | 10.31 |
| **total** | 355 | 178 | 32,736 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 1,553 | 23 | 11.5 | 4,392 | 191.0 | 123.0 |
| 3,089 | 25 | 12.5 | 3,960 | 158.4 | 51.3 |
| 357 | 21 | 10.5 | 3,471 | 165.3 | 462.9 |
| 784 | 25 | 12.5 | 3,182 | 127.3 | 162.3 |
| 485 | 12 | 6.0 | 2,506 | 208.8 | 430.6 |
| 126 | 24 | 12.0 | 2,257 | 94.1 | 746.5 |
| 2,934 | 22 | 11.0 | 2,247 | 102.1 | 34.8 |
| 484 | 10 | 5.0 | 1,887 | 188.7 | 389.9 |
| 2,957 | 1 | 0.5 | 1,695 | 1694.8 | 573.1 |
| 780 | 25 | 12.5 | 1,291 | 51.6 | 66.2 |
| 51,247 | 2 | 1.0 | 1,056 | 528.2 | 10.3 |
| 0 | 75 | 37.5 | 996 | 13.3 | – |
| 6,919 | 25 | 12.5 | 850 | 34.0 | 4.9 |
| 1 | 48 | 24.0 | 616 | 12.8 | 12839.6 |
| 127 | 1 | 0.5 | 486 | 485.8 | 3825.2 |
| 487 | 2 | 1.0 | 447 | 223.6 | 459.0 |
| 2,326 | 2 | 1.0 | 418 | 209.1 | 89.9 |
| 368 | 2 | 1.0 | 355 | 177.6 | 482.5 |
| 2,917 | 2 | 1.0 | 302 | 151.1 | 51.8 |
| 1,438 | 2 | 1.0 | 207 | 103.3 | 71.9 |
| 40 | 1 | 0.5 | 57 | 57.4 | 1435.0 |
| 2 | 2 | 1.0 | 30 | 15.1 | 7550.0 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 1 | 1 | 475 | 2.8 % | [1694.8, 2957] |
| 2 | 1 | 581 | 4.0 % | [581.3, 51247] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 50476], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 49759], ['V8.GC_MC_CLEAR_STRING_TABLE', 64], ['V8.GC_MC_SWEEP', 52], ['V8.GC_MC_MARK_ROOTS', 48], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 46], ['V8.GC_MC_MARK_EMBEDDER_PROLOGUE', 32], ['V8.GC_MC_EVACUATE', 32]], total nested 2,459 ms

### ab-lock: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 529 | 1430 | 1835 |
| token 1 (0–33 s) | 1682 | 2935 | 3727 |
| token 2 (33–65 s) | 3507 | 3959 | 4334 |
| after completion (readback) | 4347 | 4375 | 4394 |
| browser process peak | | | 222 |
| GPU process peak | | | 140 |

CDP Performance.getMetrics deltas Run→end (66.8 s wall): RecalcStyleCount +361, RecalcStyleDuration +32.6 s, LayoutCount +226, LayoutDuration +9.7 s, TaskDuration +66.7 s; Nodes 134297, LayoutObjects 141815

Load phase (ab-lock): {"wall_ms": 4685.6, "busy_ms": 1833.8, "idle_ms": 2851.8, "frames": 13, "style_ms": 909.6, "style_count": 17, "recalcStyle_ms": 866.0, "recalcStyle_count": 12, "updateStyle_ms": 886.8, "styleInvalidation_ms": 0.4, "layout_ms": 325.2, "layout_count": 14, "of_which_text_shaping_ms": 74.1, "text_shaping_count": 9332, "animate_ms": 31.9, "prepaint_ms": 21.8, "of_which_compositing_inputs_ms": 14.7, "paint_lifecycle_ms": 29.8, "of_which_Paint_ms": 1.5, "hittest_ms": 0.0, "hittest_count": 0, "gc_nested_ms": 42.8, "gc_count": 627, "recalcStyle_self_ms": 863.1, "gc_by_name": [["V8.GC_MC_INCREMENTAL", 11.8], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 11.5], ["MajorGC", 4.5], ["V8.GC_MARK_COMPACTOR", 4.3], ["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 4.2], ["V8.GC_MC_INCREMENTAL_START", 0.9]], "majorGC_count": 4, "other_busy_ms": 515.5, "animation_regex_ms": 45.8, "animation_regex_count": 13280, "paint_prepaint_composite_ms": 62.7}
named: {"ParseAuthorStyleSheet": [1, 57.9], "CSSParserImpl::parseStyleSheet": [3, 57.9], "CSSParserImpl::parseStyleSheet.parse": [3, 57.9], "StyleEngine::updateActiveStyleSheets": [2, 18.3], "RuleSet::addRulesFromSheet": [2, 0.8], "ParseHTML": [10, 152.1]}
big: [[52.1, 106.6, "RunTask", 0], [52.1, 106.6, "ResponseBodyLoader::OnStateChange", 1], [52.1, 106.6, "ResponseBodyLoader::DidFinishLoadingBody", 2], [158.7, 750.5, "RunTask", 0], [158.7, 749.3, "ProxyMain::BeginMainFrame", 1], [158.7, 749.2, "WebFrameWidgetImpl::UpdateLifecycle", 2], [973.2, 36.3, "RunTask", 0], [973.2, 36.3, "ProxyMain::BeginMainFrame", 1], [976.3, 32.5, "WebFrameWidgetImpl::UpdateLifecycle", 2], [1038.5, 43.2, "RunTask", 0], [1038.5, 43.1, "ProxyMain::BeginMainFrame", 1], [1041.4, 40.1, "WebFrameWidgetImpl::UpdateLifecycle", 2]]
nav: {'responseEnd': 52.30000001192093, 'domInteractive': 1245.1000000238419, 'domContentLoadedEventEnd': 1245.1000000238419, 'domComplete': 2236.300000011921, 'loadEventEnd': 2236.7000000178814} {'resources': 250, 'resourceBytes': 144715259, 'resourceEncodedBytes': 144715259, 'lastResourceEnd': 1334.7000000178814, 'cssResource': {'startTime': 10, 'responseEnd': 51.10000002384186, 'decodedBodySize': 41666851, 'encodedBodySize': 41666851}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 916}, {'name': 'first-contentful-paint', 'startTime': 916}], 'fontsStatus': 'loaded', 'fontsSize': 283, 'elements': 69522, 'scripts': 0}
timeline: {'tNav0': 431.4, 'tLoad': 2680.7, 'tIdle': 5114.1, 'tRun': 5121.6, 'tEndWait': 69787.3, 'stopReason': 'token-limit', 'traceBytes': 48075737, 'dataLossOccurred': False} finalState: {"headEpoch": 2, "winner": 314} {"--saved-token-1": "11", "--saved-token-2": "314", "tokenState": {"--epoch": "0", "--winner": "0", "--head-output-epoch": "0"}}
