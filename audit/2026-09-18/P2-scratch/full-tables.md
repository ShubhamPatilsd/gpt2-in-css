### full: per-token phase split (ms; % of window wall)

| phase | token 1 | token 2 | token 3 | token 4 | mean |
|---|---:|---:|---:|---:|---:|
| wall | 38,744 | 40,320 | 45,143 | 51,770 | 43,994 |
| main-thread busy | 38,984 (100.6 %) | 40,280 (99.9 %) | 45,099 (99.9 %) | 51,702 (99.9 %) | 44,016 (100.0 %) |
| idle | -240 (-0.6 %) | 40 (0.1 %) | 44 (0.1 %) | 68 (0.1 %) | -22 (-0.0 %) |
| style (UpdateLayoutTree) | 21,780 (56.2 %) | 21,727 (53.9 %) | 25,467 (56.4 %) | 28,804 (55.6 %) | 24,444 (55.6 %) |
|   of which recalcStyle self (no nested GC) | 19,155 (49.4 %) | 18,062 (44.8 %) | 19,772 (43.8 %) | 21,889 (42.3 %) | 19,719 (44.8 %) |
| layout | 4,568 (11.8 %) | 5,246 (13.0 %) | 5,790 (12.8 %) | 8,350 (16.1 %) | 5,988 (13.6 %) |
|   of which text shaping | 2,021 (5.2 %) | 2,138 (5.3 %) | 2,186 (4.8 %) | 2,415 (4.7 %) | 2,190 (5.0 %) |
| animation servicing (Blink.Animate) | 3,170 (8.2 %) | 3,523 (8.7 %) | 3,617 (8.0 %) | 3,737 (7.2 %) | 3,512 (8.0 %) |
| pre-paint + compositing inputs | 1,884 (4.9 %) | 1,946 (4.8 %) | 1,993 (4.4 %) | 2,356 (4.6 %) | 2,045 (4.6 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 4,993 (12.9 %) | 5,296 (13.1 %) | 5,709 (12.6 %) | 5,832 (11.3 %) | 5,458 (12.4 %) |
|   of which Paint | 13 (0.0 %) | 14 (0.0 %) | 18 (0.0 %) | 17 (0.0 %) | 15 (0.0 %) |
| hit-test (fake mousemove) | 1,067 (2.8 %) | 1,306 (3.2 %) | 1,374 (3.0 %) | 1,483 (2.9 %) | 1,307 (3.0 %) |
| other busy (unattributed) | 1,524 (3.9 %) | 1,236 (3.1 %) | 1,149 (2.5 %) | 1,140 (2.2 %) | 1,262 (2.9 %) |
| GC (nested inside the above) | 1,362 (3.5 %) | 2,465 (6.1 %) | 4,961 (11.0 %) | 8,378 (16.2 %) | 4,292 (9.8 %) |
| style passes / layouts / frames | 172 / 111 / 91 | 171 / 110 / 85 | 171 / 110 / 85 | 171 / 110 / 85 | |
| major GCs | 5 | 6 | 4 | 4 | |
| token boundary (s after Run) | 38.7 | 79.1 | 124.2 | 176.0 | |
| handshakes (s after Run) | 0.1 run-start; 35.9 token-1-ready; 38.3 token-1-ack | 75.5 token-2-ready; 78.6 token-2-ack | 120.9 token-3-ready; 123.7 token-3-ack | 170.5 token-4-ready; 175.5 token-4-ack | |

### full: style-pass histogram over the traced generate window (4 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 257 | 64.2 | 4,005 | 3.8 % | 15.6 | 0.1–23 | 36743.12 |
| 10-99 | 1 | 0.2 | 63 | 0.1 % | 63.2 | 63.2–63 | 1620.51 |
| 100-999 | 102 | 25.5 | 9,831 | 9.4 % | 96.4 | 31.3–831 | 212.75 |
| 1k-9,999 | 307 | 76.8 | 55,944 | 53.4 % | 182.2 | 26.9–1598 | 50.01 |
| 10k-<50%DOM | 46 | 11.5 | 22,615 | 21.6 % | 491.6 | 308.2–1591 | 40.05 |
| >=50%DOM | 8 | 2.0 | 12,361 | 11.8 % | 1545.1 | 880.1–2915 | 24.16 |
| **total** | 721 | 180 | 104,818 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 12,274 | 31 | 7.8 | 16,431 | 530.0 | 43.2 |
| 1,553 | 46 | 11.5 | 10,903 | 237.0 | 152.6 |
| 3,089 | 51 | 12.8 | 10,483 | 205.6 | 66.5 |
| 3,545 | 29 | 7.2 | 8,960 | 309.0 | 87.2 |
| 3,856 | 50 | 12.5 | 7,772 | 155.4 | 40.3 |
| 2,935 | 46 | 11.5 | 6,496 | 141.2 | 48.1 |
| 63,946 | 4 | 1.0 | 6,441 | 1610.2 | 25.2 |
| 63,933 | 4 | 1.0 | 5,920 | 1479.9 | 23.1 |
| 126 | 50 | 12.5 | 5,876 | 117.5 | 932.8 |
| 3,544 | 21 | 5.2 | 5,440 | 259.1 | 73.1 |
| 12,273 | 10 | 2.5 | 3,522 | 352.2 | 28.7 |
| 780 | 51 | 12.8 | 3,455 | 67.8 | 86.9 |
| 0 | 154 | 38.5 | 2,399 | 15.6 | – |
| 12,285 | 4 | 1.0 | 2,353 | 588.2 | 47.9 |
| 6,919 | 51 | 12.8 | 2,014 | 39.5 | 5.7 |
| 2,957 | 1 | 0.2 | 1,598 | 1598.4 | 540.5 |
| 1 | 98 | 24.5 | 1,528 | 15.6 | 15587.8 |
| 2,326 | 4 | 1.0 | 1,026 | 256.4 | 110.2 |
| 2,917 | 4 | 1.0 | 746 | 186.5 | 63.9 |
| 1,958 | 4 | 1.0 | 505 | 126.2 | 64.5 |
| 127 | 1 | 0.2 | 499 | 499.0 | 3929.1 |
| 12,272 | 1 | 0.2 | 309 | 308.8 | 25.2 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 1 | 2 | 1,833 | 8.4 % | [1598.4, 2957] |
| 2 | 2 | 2,932 | 13.5 % | [1518.5, 63946] |
| 3 | 2 | 3,274 | 12.9 % | [2146.5, 63933] |
| 4 | 2 | 4,322 | 15.0 % | [2914.8, 63946] |

### full: invalidation tracking (traced window)

| event | reason | count | per token |
|---|---|---:|---:|
| LayoutInvalidationTracking | Style changed | 1,913,356 | 478,339 |
| StyleRecalcInvalidationTracking | ScrollTimeline | 442,107 | 110,527 |
| LayoutInvalidationTracking | Added to layout | 147,753 | 36,938 |
| LayoutInvalidationTracking | Anchor positioning | 107,344 | 26,836 |
| StyleRecalcInvalidationTracking | Related style rule | 12,272 | 3,068 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | 10,738 | 2,684 |
| LayoutInvalidationTracking | Removed from layout | 3,105 | 776 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched class | 1,326 | 332 |
| ScheduleStyleInvalidationTracking | (none) | 203 | 51 |
| StyleRecalcInvalidationTracking | Affected by :has() | 202 | 50 |
| StyleInvalidatorInvalidationTracking | Element has pending invalidation list | 198 | 50 |
| StyleInvalidatorInvalidationTracking | Invalidation set invalidates self | 106 | 26 |
| StyleRecalcInvalidationTracking | Animation | 105 | 26 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched tagName | 102 | 26 |
| LayoutInvalidationTracking | Text changed | 4 | 1 |
| StyleRecalcInvalidationTracking | PseudoClass | 2 | 0 |

StyleInvalidator / ScheduleStyleInvalidation by selector part (per token ≈ count/4):

| event | reason | part | count |
|---|---|---|---:|
| ScheduleStyleInvalidationTracking | (none) | `has` | 202 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched tagName | `select` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched class | `status` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `run-start` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched class | `feedback-reader` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched class | `visible-output` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched class | `core-controller` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched class | `core-block` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `eos-ready` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-1-ready` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-1-ack` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-2-ready` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-2-ack` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-3-ready` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-3-ack` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-4-ready` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-4-ack` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-5-ready` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-5-ack` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-6-ready` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-6-ack` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-7-ready` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-7-ack` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-8-ready` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `token-8-ack` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `capture-epoch-observer` | 102 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched id | `loop-ack-N` (all N, summed) | 7600 |
| StyleInvalidatorInvalidationTracking | Invalidation set matched class | `token-slot-N` (all N, summed) | 816 |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 128536], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 126680], ['V8.GC_MC_CLEAR_STRING_TABLE', 104], ['V8.GC_MC_SWEEP', 80], ['V8.GC_MC_MARK_ROOTS', 79], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 74], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 60], ['V8.GC_MC_MARK_EMBEDDER_PROLOGUE', 54]], total nested 21,358 ms

### full: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 567 | 1436 | 1838 |
| token 1 (0–39 s) | 1674 | 2468 | 2994 |
| token 2 (39–79 s) | 1695 | 2582 | 2931 |
| token 3 (79–124 s) | 2171 | 2737 | 3257 |
| token 4 (124–176 s) | 1919 | 2484 | 3159 |
| rest of run (176–395 s) | 1388 | 2709 | 3580 |
| after completion (readback) | 2821 | 2913 | 3005 |
| browser process peak | | | 224 |
| GPU process peak | | | 139 |

CDP Performance.getMetrics deltas Run→end (397.1 s wall): RecalcStyleCount +1400, RecalcStyleDuration +223.9 s, LayoutCount +880, LayoutDuration +58.1 s, TaskDuration +395.4 s; Nodes 139602, LayoutObjects 146358

Load phase (full): {"wall_ms": 4632.9, "busy_ms": 1836.8, "idle_ms": 2796.1, "frames": 12, "style_ms": 905.4, "style_count": 16, "recalcStyle_ms": 848.4, "recalcStyle_count": 8, "updateStyle_ms": 862.9, "styleInvalidation_ms": 0.7, "layout_ms": 305.3, "layout_count": 13, "of_which_text_shaping_ms": 71.5, "text_shaping_count": 7876, "animate_ms": 31.0, "prepaint_ms": 20.5, "of_which_compositing_inputs_ms": 14.0, "paint_lifecycle_ms": 29.0, "of_which_Paint_ms": 1.3, "hittest_ms": 0.0, "hittest_count": 0, "gc_nested_ms": 146.3, "gc_count": 882, "recalcStyle_self_ms": 845.9, "gc_by_name": [["MajorGC", 24.9], ["V8.GC_MARK_COMPACTOR", 24.7], ["V8.GC_MC_MARK", 20.1], ["V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL", 13.9], ["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 13.6], ["V8.GC_MC_INCREMENTAL", 9.4]], "majorGC_count": 5, "other_busy_ms": 545.6, "animation_regex_ms": 44.2, "animation_regex_count": 12934, "paint_prepaint_composite_ms": 59.4}
named: {"ParseAuthorStyleSheet": [1, 52.7], "CSSParserImpl::parseStyleSheet": [3, 52.7], "CSSParserImpl::parseStyleSheet.parse": [3, 52.7], "StyleEngine::updateActiveStyleSheets": [2, 29.9], "RuleSet::addRulesFromSheet": [2, 1.4], "ParseHTML": [10, 155.9]}
big: [[106.6, 104.1, "RunTask", 0], [106.6, 104.0, "ResponseBodyLoader::OnStateChange", 1], [106.6, 104.0, "ResponseBodyLoader::DidFinishLoadingBody", 2], [210.7, 659.5, "RunTask", 0], [210.7, 658.3, "ProxyMain::BeginMainFrame", 1], [210.8, 658.1, "WebFrameWidgetImpl::UpdateLifecycle", 2], [872.4, 184.8, "RunTask", 0], [872.4, 184.8, "HTMLDocumentParser::DeferredPumpTokenizerIfPossible", 1], [872.4, 184.8, "HTMLDocumentParser::PumpTokenizerIfPossible", 2], [1112.5, 169.9, "RunTask", 0], [1112.5, 169.9, "ProxyMain::BeginMainFrame", 1], [1115.9, 166.5, "WebFrameWidgetImpl::UpdateLifecycle", 2]]
nav: {'responseEnd': 48, 'domInteractive': 958, 'domContentLoadedEventEnd': 958.0999999940395, 'domComplete': 2356.5999999940395, 'loadEventEnd': 2357.2000000029802} {'resources': 250, 'resourceBytes': 148361882, 'resourceEncodedBytes': 148361882, 'lastResourceEnd': 1339.9000000059605, 'cssResource': {'startTime': 11.299999997019768, 'responseEnd': 96.20000000298023, 'decodedBodySize': 45783674, 'encodedBodySize': 45783674}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 876}, {'name': 'first-contentful-paint', 'startTime': 876}], 'fontsStatus': 'loaded', 'fontsSize': 261, 'elements': 72549, 'scripts': 0}
timeline: {'tNav0': 677.5, 'tLoad': 3051.1, 'tIdle': 5307.8, 'tRun': 5316.5, 'tEndWait': 400369.4, 'stopReason': 'token-limit', 'traceBytes': 146814867, 'dataLossOccurred': True} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "8", "--winner": "1101", "--head-output-epoch": "8"}}
