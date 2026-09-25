### combined2-t1: per-token phase split (ms; % of window wall)

| phase | token 1 | token 2 | token 3 | token 4 | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| wall | 36,311 | 36,529 | 36,212 | 37,727 | 38,915 | 41,916 | 44,265 | 38,839 |
| main-thread busy | 36,503 (100.5 %) | 36,475 (99.9 %) | 36,170 (99.9 %) | 37,644 (99.8 %) | 38,830 (99.8 %) | 41,814 (99.8 %) | 44,156 (99.8 %) | 38,799 (99.9 %) |
| idle | -192 (-0.5 %) | 54 (0.1 %) | 41 (0.1 %) | 83 (0.2 %) | 86 (0.2 %) | 102 (0.2 %) | 108 (0.2 %) | 41 (0.1 %) |
| style (UpdateLayoutTree) | 9,298 (25.6 %) | 7,588 (20.8 %) | 7,586 (20.9 %) | 8,130 (21.6 %) | 9,104 (23.4 %) | 10,034 (23.9 %) | 10,215 (23.1 %) | 8,851 (22.8 %) |
|   of which recalcStyle self (no nested GC) | 8,203 (22.6 %) | 6,290 (17.2 %) | 6,194 (17.1 %) | 6,586 (17.5 %) | 6,990 (18.0 %) | 7,547 (18.0 %) | 7,961 (18.0 %) | 7,110 (18.3 %) |
| layout | 19,846 (54.7 %) | 21,186 (58.0 %) | 20,736 (57.3 %) | 21,572 (57.2 %) | 21,872 (56.2 %) | 22,954 (54.8 %) | 25,376 (57.3 %) | 21,934 (56.5 %) |
|   of which text shaping | 1,799 (5.0 %) | 2,061 (5.6 %) | 1,883 (5.2 %) | 2,027 (5.4 %) | 2,147 (5.5 %) | 2,185 (5.2 %) | 2,284 (5.2 %) | 2,055 (5.3 %) |
| animation servicing (Blink.Animate) | 1,348 (3.7 %) | 1,442 (3.9 %) | 1,473 (4.1 %) | 1,567 (4.2 %) | 1,535 (3.9 %) | 1,654 (3.9 %) | 1,700 (3.8 %) | 1,531 (3.9 %) |
| pre-paint + compositing inputs | 1,922 (5.3 %) | 1,991 (5.4 %) | 2,015 (5.6 %) | 2,045 (5.4 %) | 1,986 (5.1 %) | 2,069 (4.9 %) | 2,087 (4.7 %) | 2,016 (5.2 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 2,778 (7.7 %) | 3,225 (8.8 %) | 3,245 (9.0 %) | 3,219 (8.5 %) | 3,255 (8.4 %) | 3,964 (9.5 %) | 3,545 (8.0 %) | 3,319 (8.5 %) |
|   of which Paint | 41 (0.1 %) | 43 (0.1 %) | 42 (0.1 %) | 44 (0.1 %) | 43 (0.1 %) | 45 (0.1 %) | 50 (0.1 %) | 44 (0.1 %) |
| hit-test (fake mousemove) | 451 (1.2 %) | 495 (1.4 %) | 509 (1.4 %) | 541 (1.4 %) | 548 (1.4 %) | 582 (1.4 %) | 607 (1.4 %) | 533 (1.4 %) |
| other busy (unattributed) | 860 (2.4 %) | 548 (1.5 %) | 608 (1.7 %) | 570 (1.5 %) | 529 (1.4 %) | 558 (1.3 %) | 627 (1.4 %) | 614 (1.6 %) |
| GC (nested inside the above) | 1,597 (4.4 %) | 2,092 (5.7 %) | 1,925 (5.3 %) | 2,285 (6.1 %) | 2,738 (7.0 %) | 4,009 (9.6 %) | 4,732 (10.7 %) | 2,768 (7.1 %) |
| style passes / layouts / frames | 137 / 86 / 78 | 135 / 85 / 73 | 135 / 85 / 73 | 135 / 85 / 73 | 135 / 85 / 73 | 135 / 85 / 73 | 135 / 85 / 73 | |
| major GCs | 6 | 6 | 4 | 5 | 4 | 4 | 4 | |
| token boundary (s after Run) | 36.3 | 72.8 | 109.1 | 146.8 | 185.7 | 227.6 | 271.9 | |
| handshakes (s after Run) | 0.1 run-start; 34.5 token-1-ready; 36.0 token-1-ack | 70.9 token-2-ready; 72.5 token-2-ack | 107.1 token-3-ready; 108.7 token-3-ack | 144.8 token-4-ready; 146.4 token-4-ack | 183.4 token-5-ready; 185.4 token-5-ack | 225.6 token-6-ready; 227.3 token-6-ack | 269.8 token-7-ready; 271.5 token-7-ack | |

### combined2-t1: style-pass histogram over the traced generate window (7 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 401 | 57.3 | 3,820 | 5.3 % | 9.5 | 0.1–21 | 15097.63 |
| 10-99 | 1 | 0.1 | 84 | 0.1 % | 84.1 | 84.1–84 | 2102.5 |
| 100-999 | 377 | 53.9 | 40,697 | 56.9 % | 107.9 | 24.8–677 | 249.47 |
| 1k-9,999 | 295 | 42.1 | 22,222 | 31.1 % | 75.3 | 17.3–1718 | 17.74 |
| >=50%DOM | 8 | 1.1 | 4,728 | 6.6 % | 591.0 | 458.0–1116 | 11.53 |
| **total** | 1082 | 155 | 71,550 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 473 | 88 | 12.6 | 13,545 | 153.9 | 325.4 |
| 126 | 95 | 13.6 | 11,545 | 121.5 | 964.5 |
| 2,934 | 88 | 12.6 | 11,426 | 129.8 | 44.3 |
| 347 | 81 | 11.6 | 8,696 | 107.4 | 309.4 |
| 51,235 | 8 | 1.1 | 4,728 | 591.0 | 11.5 |
| 6,919 | 96 | 13.7 | 4,464 | 46.5 | 6.7 |
| 780 | 96 | 13.7 | 3,836 | 40.0 | 51.2 |
| 3,092 | 96 | 13.7 | 2,591 | 27.0 | 8.7 |
| 0 | 198 | 28.3 | 1,860 | 9.4 | – |
| 1 | 186 | 26.6 | 1,776 | 9.6 | 9550.5 |
| 2,957 | 1 | 0.1 | 1,718 | 1718.3 | 581.1 |
| 474 | 8 | 1.1 | 1,698 | 212.3 | 447.9 |
| 2,917 | 7 | 1.0 | 1,141 | 163.0 | 55.9 |
| 1,438 | 7 | 1.0 | 882 | 126.0 | 87.6 |
| 358 | 7 | 1.0 | 833 | 119.0 | 332.3 |
| 127 | 2 | 0.3 | 544 | 271.9 | 2140.9 |
| 2 | 8 | 1.1 | 93 | 11.7 | 5831.2 |
| 6 | 8 | 1.1 | 86 | 10.8 | 1793.8 |
| 40 | 1 | 0.1 | 84 | 84.1 | 2102.5 |
| 3 | 1 | 0.1 | 4 | 4.1 | 1366.7 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 1 | 1 | 458 | 4.9 % | [1718.3, 2957] |
| 2 | 1 | 525 | 6.9 % | [525.1, 51235] |
| 3 | 1 | 461 | 6.1 % | [460.6, 51235] |
| 4 | 1 | 472 | 5.8 % | [471.7, 51235] |
| 5 | 1 | 521 | 5.7 % | [557.4, 474] |
| 6 | 1 | 1,116 | 11.1 % | [1115.9, 51235] |
| 7 | 1 | 583 | 5.7 % | [796.0, 6919] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 312722], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 309400], ['V8.GC_MC_MARK_ROOTS', 126], ['V8.GC_MC_SWEEP', 124], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 120], ['V8.GC_MC_CLEAR_STRING_TABLE', 116], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 98], ['V8.GC_MC_MARK_EMBEDDER_PROLOGUE', 84]], total nested 26,874 ms

### combined2-t1: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 1066 | 1562 | 1732 |
| token 1 (0–36 s) | 1735 | 3309 | 4037 |
| token 2 (36–73 s) | 4061 | 4215 | 4427 |
| token 3 (73–109 s) | 4453 | 4697 | 4946 |
| token 4 (109–147 s) | 4762 | 4971 | 5136 |
| token 5 (147–186 s) | 4713 | 4935 | 5104 |
| token 6 (186–228 s) | 4035 | 4424 | 4933 |
| token 7 (228–272 s) | 4029 | 4326 | 4679 |
| rest of run (272–319 s) | 3607 | 4198 | 4555 |
| after completion (readback) | 4413 | 4517 | 4621 |
| browser process peak | | | 222 |
| GPU process peak | | | 143 |

CDP Performance.getMetrics deltas Run→end (321.0 s wall): RecalcStyleCount +186009, RecalcStyleDuration +109.7 s, LayoutCount +680, LayoutDuration +144.5 s, TaskDuration +319.6 s; Nodes 153132, LayoutObjects 156818

Load phase (combined2-t1): {"wall_ms": 4194.1, "busy_ms": 1916.2, "idle_ms": 2277.9, "frames": 10, "style_ms": 1048.0, "style_count": 15, "recalcStyle_ms": 1003.2, "recalcStyle_count": 12, "updateStyle_ms": 1022.9, "styleInvalidation_ms": 0.4, "layout_ms": 282.0, "layout_count": 10, "of_which_text_shaping_ms": 68.3, "text_shaping_count": 5680, "animate_ms": 21.4, "prepaint_ms": 17.5, "of_which_compositing_inputs_ms": 12.5, "paint_lifecycle_ms": 26.5, "of_which_Paint_ms": 1.2, "hittest_ms": 0.0, "hittest_count": 0, "gc_nested_ms": 163.8, "gc_count": 410, "recalcStyle_self_ms": 1002.9, "gc_by_name": [["MajorGC", 26.8], ["V8.GC_MARK_COMPACTOR", 26.6], ["V8.GC_MC_MARK", 22.1], ["V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL", 21.8], ["V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING", 21.6], ["V8.GC_MC_MARK_EMBEDDER_TRACING", 21.6]], "majorGC_count": 4, "other_busy_ms": 520.8, "animation_regex_ms": 32.4, "animation_regex_count": 10609, "paint_prepaint_composite_ms": 52.3}
named: {"ParseAuthorStyleSheet": [1, 57.5], "CSSParserImpl::parseStyleSheet": [3, 57.5], "CSSParserImpl::parseStyleSheet.parse": [3, 57.5], "StyleEngine::updateActiveStyleSheets": [2, 20.9], "RuleSet::addRulesFromSheet": [2, 2.4], "ParseHTML": [10, 158.7]}
big: [[59.7, 91.9, "RunTask", 0], [59.7, 91.8, "ResponseBodyLoader::OnStateChange", 1], [59.7, 91.8, "ResponseBodyLoader::DidFinishLoadingBody", 2], [151.6, 422.8, "RunTask", 0], [151.6, 421.6, "ProxyMain::BeginMainFrame", 1], [151.7, 421.5, "WebFrameWidgetImpl::UpdateLifecycle", 2], [609.5, 26.6, "RunTask", 0], [609.5, 26.6, "ProxyMain::BeginMainFrame", 1], [611.7, 24.2, "WebFrameWidgetImpl::UpdateLifecycle", 2], [660.1, 459.0, "RunTask", 0], [660.1, 459.0, "ProxyMain::BeginMainFrame", 1], [662.2, 456.4, "WebFrameWidgetImpl::UpdateLifecycle", 2]]
nav: {'responseEnd': 46.599999994039536, 'domInteractive': 1516, 'domContentLoadedEventEnd': 1516.199999988079, 'domComplete': 1902.0999999940395, 'loadEventEnd': 1902.4000000059605} {'resources': 250, 'resourceBytes': 133173705, 'resourceEncodedBytes': 133173705, 'lastResourceEnd': 997.6999999880791, 'cssResource': {'startTime': 8.900000005960464, 'responseEnd': 58.69999998807907, 'decodedBodySize': 31306905, 'encodedBodySize': 31306905}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 580}, {'name': 'first-contentful-paint', 'startTime': 580}], 'fontsStatus': 'loaded', 'fontsSize': 283, 'elements': 79915, 'scripts': 0}
timeline: {'tNav0': 612, 'tLoad': 2523.1, 'tIdle': 4801.5, 'tRun': 4811.7, 'tEndWait': 323764.7, 'stopReason': 'token-limit', 'traceBytes': 121524211, 'dataLossOccurred': False} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "0", "--winner": "1101", "--head-output-epoch": "8"}}
