### F3a-t1: per-token phase split (ms; % of window wall)

| phase | token 1 | token 2 | token 3 | token 4 | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| wall | 33,325 | 34,014 | 35,190 | 37,494 | 39,142 | 41,154 | 44,580 | 37,843 |
| main-thread busy | 33,532 (100.6 %) | 33,966 (99.9 %) | 35,126 (99.8 %) | 37,437 (99.8 %) | 39,020 (99.7 %) | 41,056 (99.8 %) | 44,463 (99.7 %) | 37,800 (99.9 %) |
| idle | -207 (-0.6 %) | 48 (0.1 %) | 63 (0.2 %) | 57 (0.2 %) | 122 (0.3 %) | 98 (0.2 %) | 118 (0.3 %) | 43 (0.1 %) |
| style (UpdateLayoutTree) | 8,643 (25.9 %) | 7,734 (22.7 %) | 7,713 (21.9 %) | 8,690 (23.2 %) | 9,667 (24.7 %) | 11,036 (26.8 %) | 12,501 (28.0 %) | 9,426 (24.9 %) |
|   of which recalcStyle self (no nested GC) | 7,474 (22.4 %) | 6,158 (18.1 %) | 6,337 (18.0 %) | 6,928 (18.5 %) | 7,583 (19.4 %) | 8,151 (19.8 %) | 8,996 (20.2 %) | 7,375 (19.5 %) |
| layout | 17,583 (52.8 %) | 18,520 (54.4 %) | 19,293 (54.8 %) | 19,894 (53.1 %) | 21,276 (54.4 %) | 21,023 (51.1 %) | 23,432 (52.6 %) | 20,146 (53.2 %) |
|   of which text shaping | 1,783 (5.4 %) | 1,894 (5.6 %) | 1,966 (5.6 %) | 2,136 (5.7 %) | 2,218 (5.7 %) | 2,220 (5.4 %) | 2,292 (5.1 %) | 2,073 (5.5 %) |
| animation servicing (Blink.Animate) | 1,354 (4.1 %) | 1,471 (4.3 %) | 1,578 (4.5 %) | 1,657 (4.4 %) | 1,696 (4.3 %) | 1,788 (4.3 %) | 1,810 (4.1 %) | 1,622 (4.3 %) |
| pre-paint + compositing inputs | 1,928 (5.8 %) | 1,971 (5.8 %) | 2,033 (5.8 %) | 2,024 (5.4 %) | 2,004 (5.1 %) | 2,649 (6.4 %) | 2,110 (4.7 %) | 2,103 (5.6 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 2,746 (8.2 %) | 3,225 (9.5 %) | 3,415 (9.7 %) | 4,039 (10.8 %) | 3,301 (8.4 %) | 3,389 (8.2 %) | 3,386 (7.6 %) | 3,357 (8.9 %) |
|   of which Paint | 40 (0.1 %) | 41 (0.1 %) | 42 (0.1 %) | 44 (0.1 %) | 44 (0.1 %) | 52 (0.1 %) | 60 (0.1 %) | 46 (0.1 %) |
| hit-test (fake mousemove) | 455 (1.4 %) | 527 (1.5 %) | 564 (1.6 %) | 597 (1.6 %) | 620 (1.6 %) | 695 (1.7 %) | 699 (1.6 %) | 594 (1.6 %) |
| other busy (unattributed) | 824 (2.5 %) | 518 (1.5 %) | 532 (1.5 %) | 536 (1.4 %) | 456 (1.2 %) | 476 (1.2 %) | 525 (1.2 %) | 552 (1.5 %) |
| GC (nested inside the above) | 1,602 (4.8 %) | 2,024 (6.0 %) | 2,126 (6.0 %) | 2,585 (6.9 %) | 3,823 (9.8 %) | 4,336 (10.5 %) | 6,008 (13.5 %) | 3,215 (8.5 %) |
| style passes / layouts / frames | 138 / 86 / 78 | 135 / 85 / 73 | 135 / 85 / 73 | 135 / 85 / 73 | 135 / 85 / 73 | 135 / 85 / 73 | 135 / 85 / 73 | |
| major GCs | 6 | 5 | 4 | 4 | 5 | 4 | 4 | |
| token boundary (s after Run) | 33.3 | 67.3 | 102.5 | 140.0 | 179.2 | 220.3 | 264.9 | |
| handshakes (s after Run) | 0.1 run-start; 31.4 token-1-ready; 33.0 token-1-ack | 65.4 token-2-ready; 67.0 token-2-ack | 100.5 token-3-ready; 102.2 token-3-ack | 137.9 token-4-ready; 139.7 token-4-ack | 177.2 token-5-ready; 178.8 token-5-ack | 218.2 token-6-ready; 220.0 token-6-ack | 262.8 token-7-ready; 264.6 token-7-ack | |

### F3a-t1: style-pass histogram over the traced generate window (7 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 402 | 57.4 | 4,319 | 5.5 % | 10.7 | 0.1–38 | 17005.51 |
| 10-99 | 1 | 0.1 | 74 | 0.1 % | 73.5 | 73.5–74 | 1837.5 |
| 100-999 | 377 | 53.9 | 49,172 | 62.6 % | 130.4 | 25.4–1228 | 301.43 |
| 1k-9,999 | 295 | 42.1 | 19,903 | 25.3 % | 67.5 | 16.9–1514 | 15.89 |
| >=50%DOM | 8 | 1.1 | 5,114 | 6.5 % | 639.2 | 477.7–1077 | 12.48 |
| **total** | 1083 | 155 | 78,582 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 473 | 88 | 12.6 | 16,929 | 192.4 | 406.7 |
| 126 | 95 | 13.6 | 12,739 | 134.1 | 1064.3 |
| 347 | 81 | 11.6 | 11,429 | 141.1 | 406.6 |
| 2,934 | 88 | 12.6 | 11,258 | 127.9 | 43.6 |
| 51,235 | 8 | 1.1 | 5,114 | 639.2 | 12.5 |
| 780 | 96 | 13.7 | 3,777 | 39.3 | 50.4 |
| 6,919 | 96 | 13.7 | 2,548 | 26.5 | 3.8 |
| 3,092 | 96 | 13.7 | 2,523 | 26.3 | 8.5 |
| 358 | 7 | 1.0 | 2,374 | 339.2 | 947.4 |
| 0 | 198 | 28.3 | 2,100 | 10.6 | – |
| 1 | 187 | 26.7 | 2,014 | 10.8 | 10771.1 |
| 2,957 | 1 | 0.1 | 1,514 | 1514.3 | 512.1 |
| 474 | 8 | 1.1 | 1,459 | 182.3 | 384.7 |
| 2,917 | 7 | 1.0 | 1,183 | 169.0 | 57.9 |
| 1,438 | 7 | 1.0 | 877 | 125.3 | 87.1 |
| 127 | 2 | 0.3 | 465 | 232.6 | 1831.5 |
| 2 | 8 | 1.1 | 110 | 13.8 | 6906.2 |
| 6 | 8 | 1.1 | 90 | 11.2 | 1872.9 |
| 40 | 1 | 0.1 | 74 | 73.5 | 1837.5 |
| 3 | 1 | 0.1 | 4 | 4.3 | 1433.3 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 1 | 1 | 478 | 5.5 % | [1514.3, 2957] |
| 2 | 1 | 570 | 7.4 % | [569.6, 51235] |
| 3 | 1 | 484 | 6.3 % | [483.5, 51235] |
| 4 | 1 | 556 | 6.4 % | [555.7, 51235] |
| 5 | 1 | 655 | 6.8 % | [654.7, 51235] |
| 6 | 1 | 1,077 | 9.8 % | [1076.7, 51235] |
| 7 | 1 | 612 | 4.9 % | [1227.7, 473] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 325021], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 321082], ['V8.GC_MC_MARK_ROOTS', 123], ['V8.GC_MC_SWEEP', 119], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 118], ['V8.GC_MC_CLEAR_STRING_TABLE', 118], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 95], ['V8.GC_MC_MARK_EMBEDDER_PROLOGUE', 82]], total nested 29,407 ms

### F3a-t1: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 1651 | 1691 | 1807 |
| token 1 (0–33 s) | 1669 | 3234 | 3932 |
| token 2 (33–67 s) | 3959 | 4192 | 4394 |
| token 3 (67–103 s) | 4395 | 4810 | 5057 |
| token 4 (103–140 s) | 4441 | 4724 | 4986 |
| token 5 (140–179 s) | 4141 | 4497 | 4952 |
| token 6 (179–220 s) | 4033 | 4335 | 4834 |
| token 7 (220–265 s) | 3644 | 4199 | 4524 |
| rest of run (265–311 s) | 3566 | 4066 | 4489 |
| after completion (readback) | 4095 | 4172 | 4250 |
| browser process peak | | | 224 |
| GPU process peak | | | 140 |

CDP Performance.getMetrics deltas Run→end (312.6 s wall): RecalcStyleCount +186010, RecalcStyleDuration +108.7 s, LayoutCount +680, LayoutDuration +135.1 s, TaskDuration +311.4 s; Nodes 153067, LayoutObjects 156751

Load phase (F3a-t1): {"wall_ms": 4070.5, "busy_ms": 1685.4, "idle_ms": 2385.1, "frames": 10, "style_ms": 810.2, "style_count": 15, "recalcStyle_ms": 775.8, "recalcStyle_count": 13, "updateStyle_ms": 789.4, "styleInvalidation_ms": 0.3, "layout_ms": 282.4, "layout_count": 11, "of_which_text_shaping_ms": 67.8, "text_shaping_count": 6353, "animate_ms": 22.2, "prepaint_ms": 17.3, "of_which_compositing_inputs_ms": 12.4, "paint_lifecycle_ms": 26.5, "of_which_Paint_ms": 1.1, "hittest_ms": 0.0, "hittest_count": 0, "gc_nested_ms": 172.8, "gc_count": 893, "recalcStyle_self_ms": 775.5, "gc_by_name": [["MajorGC", 27.2], ["V8.GC_MARK_COMPACTOR", 27.0], ["V8.GC_MC_MARK", 23.2], ["V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL", 22.9], ["V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING", 22.6], ["V8.GC_MC_MARK_EMBEDDER_TRACING", 22.6]], "majorGC_count": 4, "other_busy_ms": 526.8, "animation_regex_ms": 33.9, "animation_regex_count": 11196, "paint_prepaint_composite_ms": 51.9}
named: {"ParseAuthorStyleSheet": [1, 45.9], "CSSParserImpl::parseStyleSheet": [3, 45.9], "CSSParserImpl::parseStyleSheet.parse": [3, 45.9], "StyleEngine::updateActiveStyleSheets": [2, 15.1], "RuleSet::addRulesFromSheet": [2, 2.3], "ParseHTML": [10, 180.5]}
big: [[49.8, 74.5, "RunTask", 0], [49.9, 74.4, "ResponseBodyLoader::OnStateChange", 1], [49.9, 74.4, "ResponseBodyLoader::DidFinishLoadingBody", 2], [124.3, 322.4, "RunTask", 0], [124.3, 321.2, "ProxyMain::BeginMainFrame", 1], [124.3, 321.0, "WebFrameWidgetImpl::UpdateLifecycle", 2], [504.4, 32.9, "RunTask", 0], [504.4, 32.9, "ProxyMain::BeginMainFrame", 1], [508.5, 28.4, "WebFrameWidgetImpl::UpdateLifecycle", 2], [562.4, 318.8, "RunTask", 0], [562.4, 318.8, "ProxyMain::BeginMainFrame", 1], [564.5, 316.7, "WebFrameWidgetImpl::UpdateLifecycle", 2]]
nav: {'responseEnd': 50.10000002384186, 'domInteractive': 1230.7000000178814, 'domContentLoadedEventEnd': 1230.7000000178814, 'domComplete': 1778.5, 'loadEventEnd': 1778.9000000059605} {'resources': 250, 'resourceBytes': 134917516, 'resourceEncodedBytes': 134917516, 'lastResourceEnd': 864.9000000059605, 'cssResource': {'startTime': 9.100000023841858, 'responseEnd': 48.900000005960464, 'decodedBodySize': 32083076, 'encodedBodySize': 32083076}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 452}, {'name': 'first-contentful-paint', 'startTime': 452}], 'fontsStatus': 'loaded', 'fontsSize': 261, 'elements': 79870, 'scripts': 0}
timeline: {'tNav0': 559.4, 'tLoad': 2347, 'tIdle': 4626.1, 'tRun': 4634.5, 'tEndWait': 315251, 'stopReason': 'token-limit', 'traceBytes': 121288594, 'dataLossOccurred': False} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "0", "--winner": "1101", "--head-output-epoch": "8"}}
