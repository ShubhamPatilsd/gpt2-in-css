### combined3-t1: per-token phase split (ms; % of window wall)

| phase | token 1 | token 2 | token 3 | token 4 | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| wall | 28,246 | 26,292 | 29,182 | 28,573 | 29,703 | 29,523 | 30,839 | 28,908 |
| main-thread busy | 28,419 (100.6 %) | 26,248 (99.8 %) | 29,124 (99.8 %) | 28,493 (99.7 %) | 29,607 (99.7 %) | 29,435 (99.7 %) | 30,702 (99.6 %) | 28,861 (99.8 %) |
| idle | -173 (-0.6 %) | 44 (0.2 %) | 58 (0.2 %) | 80 (0.3 %) | 95 (0.3 %) | 89 (0.3 %) | 137 (0.4 %) | 47 (0.2 %) |
| style (UpdateLayoutTree) | 14,507 (51.4 %) | 10,756 (40.9 %) | 11,773 (40.3 %) | 12,351 (43.2 %) | 12,488 (42.0 %) | 12,874 (43.6 %) | 12,695 (41.2 %) | 12,492 (43.2 %) |
|   of which recalcStyle self (no nested GC) | 12,691 (44.9 %) | 8,542 (32.5 %) | 9,272 (31.8 %) | 9,246 (32.4 %) | 9,313 (31.4 %) | 9,326 (31.6 %) | 9,778 (31.7 %) | 9,738 (33.7 %) |
| layout | 4,614 (16.3 %) | 5,010 (19.1 %) | 6,273 (21.5 %) | 5,633 (19.7 %) | 5,830 (19.6 %) | 6,312 (21.4 %) | 7,922 (25.7 %) | 5,942 (20.6 %) |
|   of which text shaping | 2,032 (7.2 %) | 2,032 (7.7 %) | 2,300 (7.9 %) | 2,243 (7.9 %) | 2,236 (7.5 %) | 2,281 (7.7 %) | 2,363 (7.7 %) | 2,213 (7.7 %) |
| animation servicing (Blink.Animate) | 1,826 (6.5 %) | 2,118 (8.1 %) | 2,216 (7.6 %) | 2,238 (7.8 %) | 2,187 (7.4 %) | 1,941 (6.6 %) | 1,996 (6.5 %) | 2,075 (7.2 %) |
| pre-paint + compositing inputs | 1,723 (6.1 %) | 1,949 (7.4 %) | 1,883 (6.5 %) | 1,913 (6.7 %) | 1,835 (6.2 %) | 1,840 (6.2 %) | 1,854 (6.0 %) | 1,857 (6.4 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 4,209 (14.9 %) | 4,939 (18.8 %) | 5,446 (18.7 %) | 4,862 (17.0 %) | 5,816 (19.6 %) | 5,075 (17.2 %) | 4,869 (15.8 %) | 5,031 (17.4 %) |
|   of which Paint | 10 (0.0 %) | 9 (0.0 %) | 10 (0.0 %) | 10 (0.0 %) | 10 (0.0 %) | 10 (0.0 %) | 10 (0.0 %) | 10 (0.0 %) |
| hit-test (fake mousemove) | 590 (2.1 %) | 750 (2.9 %) | 795 (2.7 %) | 814 (2.8 %) | 805 (2.7 %) | 754 (2.6 %) | 780 (2.5 %) | 755 (2.6 %) |
| other busy (unattributed) | 950 (3.4 %) | 726 (2.8 %) | 739 (2.5 %) | 682 (2.4 %) | 646 (2.2 %) | 639 (2.2 %) | 587 (1.9 %) | 710 (2.5 %) |
| GC (nested inside the above) | 771 (2.7 %) | 1,036 (3.9 %) | 1,985 (6.8 %) | 1,600 (5.6 %) | 1,868 (6.3 %) | 2,486 (8.4 %) | 3,070 (10.0 %) | 1,831 (6.3 %) |
| style passes / layouts / frames | 133 / 88 / 52 | 132 / 87 / 46 | 132 / 87 / 46 | 132 / 87 / 46 | 132 / 87 / 46 | 132 / 87 / 46 | 132 / 87 / 46 | |
| major GCs | 3 | 3 | 3 | 2 | 2 | 2 | 2 | |
| token boundary (s after Run) | 28.2 | 54.5 | 83.7 | 112.3 | 142.0 | 171.5 | 202.4 | |
| handshakes (s after Run) | 0.0 run-start; 26.7 token-1-ready; 27.9 token-1-ack | 52.6 token-2-ready; 54.1 token-2-ack | 81.9 token-3-ready; 83.3 token-3-ack | 110.5 token-4-ready; 111.9 token-4-ack | 140.2 token-5-ready; 141.6 token-5-ack | 169.8 token-6-ready; 171.1 token-6-ack | 200.6 token-7-ready; 202.0 token-7-ack | |

### combined3-t1: style-pass histogram over the traced generate window (7 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 360 | 51.4 | 5,894 | 5.8 % | 16.4 | 0.1–25 | 85414.49 |
| 10-99 | 10 | 1.4 | 276 | 0.3 % | 27.6 | 12.6–35 | 706.14 |
| 100-999 | 295 | 42.1 | 34,106 | 33.8 % | 115.6 | 23.6–1356 | 202.67 |
| 1k-9,999 | 384 | 54.9 | 56,656 | 56.1 % | 147.5 | 26.3–2021 | 42.3 |
| >=50%DOM | 8 | 1.1 | 3,978 | 3.9 % | 497.2 | 391.3–662 | 9.77 |
| **total** | 1057 | 151 | 100,909 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 1,553 | 88 | 12.6 | 22,893 | 260.1 | 167.5 |
| 3,089 | 96 | 13.7 | 16,138 | 168.1 | 54.4 |
| 126 | 95 | 13.6 | 14,829 | 156.1 | 1238.8 |
| 784 | 96 | 13.7 | 13,825 | 144.0 | 183.7 |
| 2,323 | 81 | 11.6 | 7,198 | 88.9 | 38.3 |
| 0 | 333 | 47.6 | 5,526 | 16.6 | – |
| 6,919 | 96 | 13.7 | 4,550 | 47.4 | 6.9 |
| 780 | 96 | 13.7 | 4,318 | 45.0 | 57.7 |
| 50,892 | 8 | 1.1 | 3,978 | 497.2 | 9.8 |
| 2,326 | 8 | 1.1 | 2,063 | 257.9 | 110.9 |
| 2,381 | 1 | 0.1 | 2,021 | 2020.9 | 848.8 |
| 2,342 | 7 | 1.0 | 941 | 134.5 | 57.4 |
| 2,334 | 7 | 1.0 | 852 | 121.6 | 52.1 |
| 127 | 1 | 0.1 | 568 | 568.2 | 4474.0 |
| 863 | 7 | 1.0 | 566 | 80.8 | 93.7 |
| 1 | 18 | 2.6 | 283 | 15.7 | 15727.8 |
| 39 | 9 | 1.3 | 250 | 27.8 | 713.1 |
| 6 | 8 | 1.1 | 80 | 10.0 | 1664.6 |
| 40 | 1 | 0.1 | 26 | 25.8 | 645.0 |
| 3 | 1 | 0.1 | 4 | 4.3 | 1433.3 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 1 | 1 | 391 | 2.7 % | [2020.9, 2381] |
| 2 | 1 | 487 | 4.5 % | [487.2, 50892] |
| 3 | 1 | 662 | 5.6 % | [661.8, 50892] |
| 4 | 1 | 417 | 3.4 % | [543.2, 3089] |
| 5 | 1 | 431 | 3.5 % | [742.3, 784] |
| 6 | 1 | 468 | 3.6 % | [907.0, 126] |
| 7 | 1 | 523 | 4.1 % | [729.1, 3089] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 141658], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 139829], ['V8.GC_MC_SWEEP', 74], ['V8.GC_MC_CLEAR_STRING_TABLE', 72], ['V8.GC_MC_MARK_ROOTS', 71], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 69], ['V8.GC_MC_MARK_EMBEDDER_PROLOGUE', 48], ['V8.GC_MC_EVACUATE', 48]], total nested 16,310 ms

### combined3-t1: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 346 | 1385 | 1835 |
| token 1 (0–28 s) | 1466 | 2071 | 3195 |
| token 2 (28–55 s) | 3261 | 3494 | 3664 |
| token 3 (55–84 s) | 3109 | 3412 | 3928 |
| token 4 (84–112 s) | 2224 | 3551 | 4328 |
| token 5 (112–142 s) | 3364 | 3707 | 3921 |
| token 6 (142–172 s) | 3127 | 3495 | 3906 |
| token 7 (172–202 s) | 3023 | 3373 | 3697 |
| rest of run (202–235 s) | 2709 | 3305 | 3730 |
| after completion (readback) | 3674 | 3683 | 3692 |
| browser process peak | | | 221 |
| GPU process peak | | | 139 |

CDP Performance.getMetrics deltas Run→end (236.6 s wall): RecalcStyleCount +1088, RecalcStyleDuration +101.3 s, LayoutCount +696, LayoutDuration +48.8 s, TaskDuration +235.3 s; Nodes 133716, LayoutObjects 141434

Load phase (combined3-t1): {"wall_ms": 4686.2, "busy_ms": 1984.4, "idle_ms": 2701.8, "frames": 14, "style_ms": 1024.5, "style_count": 18, "recalcStyle_ms": 979.0, "recalcStyle_count": 10, "updateStyle_ms": 998.6, "styleInvalidation_ms": 0.3, "layout_ms": 345.0, "layout_count": 15, "of_which_text_shaping_ms": 75.0, "text_shaping_count": 10916, "animate_ms": 34.2, "prepaint_ms": 24.8, "of_which_compositing_inputs_ms": 16.4, "paint_lifecycle_ms": 31.6, "of_which_Paint_ms": 1.7, "hittest_ms": 0.0, "hittest_count": 0, "gc_nested_ms": 49.5, "gc_count": 1016, "recalcStyle_self_ms": 974.2, "gc_by_name": [["V8.GC_MC_INCREMENTAL", 14.6], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 13.8], ["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 6.2], ["MajorGC", 4.4], ["V8.GC_MARK_COMPACTOR", 4.2], ["V8.GC_MC_INCREMENTAL_START", 1.2]], "majorGC_count": 4, "other_busy_ms": 524.3, "animation_regex_ms": 48.9, "animation_regex_count": 14181, "paint_prepaint_composite_ms": 69.2}
named: {"ParseAuthorStyleSheet": [1, 61.5], "CSSParserImpl::parseStyleSheet": [3, 61.5], "CSSParserImpl::parseStyleSheet.parse": [3, 61.5], "StyleEngine::updateActiveStyleSheets": [2, 20.9], "RuleSet::addRulesFromSheet": [2, 0.8], "ParseHTML": [10, 158.3]}
big: [[74.1, 108.2, "RunTask", 0], [74.1, 108.2, "ResponseBodyLoader::OnStateChange", 1], [74.2, 108.0, "ResponseBodyLoader::DidFinishLoadingBody", 2], [182.3, 951.0, "RunTask", 0], [182.3, 949.8, "ProxyMain::BeginMainFrame", 1], [182.3, 949.6, "WebFrameWidgetImpl::UpdateLifecycle", 2], [1164.1, 27.5, "RunTask", 0], [1164.1, 27.5, "ProxyMain::BeginMainFrame", 1], [1167.7, 23.8, "WebFrameWidgetImpl::UpdateLifecycle", 2], [1215.9, 37.3, "RunTask", 0], [1215.9, 37.3, "ProxyMain::BeginMainFrame", 1], [1218.9, 33.4, "WebFrameWidgetImpl::UpdateLifecycle", 2]]
nav: {'responseEnd': 48.599999994039536, 'domInteractive': 1355.9000000059605, 'domContentLoadedEventEnd': 1355.9000000059605, 'domComplete': 2489.0999999940395, 'loadEventEnd': 2489.7000000178814} {'resources': 250, 'resourceBytes': 143681372, 'resourceEncodedBytes': 143681372, 'lastResourceEnd': 1587.300000011921, 'cssResource': {'startTime': 10.800000011920929, 'responseEnd': 64.40000000596046, 'decodedBodySize': 40872840, 'encodedBodySize': 40872840}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 1140}, {'name': 'first-contentful-paint', 'startTime': 1140}], 'fontsStatus': 'loaded', 'fontsSize': 283, 'elements': 68947, 'scripts': 0}
timeline: {'tNav0': 540.5, 'tLoad': 3040.3, 'tIdle': 5219.9, 'tRun': 5231.3, 'tEndWait': 239857.5, 'stopReason': 'token-limit', 'traceBytes': 135522586, 'dataLossOccurred': False} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "0", "--winner": "1101", "--head-output-epoch": "8"}}
