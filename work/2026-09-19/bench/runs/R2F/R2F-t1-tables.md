### R2F-t1: per-token phase split (ms; % of window wall)

| phase | token 1 | token 2 | token 3 | token 4 | token 5 | token 6 | token 7 | mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| wall | 25,310 | 22,900 | 24,189 | 24,388 | 25,129 | 27,060 | 27,625 | 25,229 |
| main-thread busy | 25,477 (100.7 %) | 22,825 (99.7 %) | 24,147 (99.8 %) | 24,310 (99.7 %) | 25,046 (99.7 %) | 26,960 (99.6 %) | 27,521 (99.6 %) | 25,184 (99.8 %) |
| idle | -167 (-0.7 %) | 75 (0.3 %) | 43 (0.2 %) | 78 (0.3 %) | 83 (0.3 %) | 100 (0.4 %) | 104 (0.4 %) | 45 (0.2 %) |
| style (UpdateLayoutTree) | 12,344 (48.8 %) | 9,041 (39.5 %) | 9,581 (39.6 %) | 9,500 (39.0 %) | 10,106 (40.2 %) | 10,613 (39.2 %) | 10,415 (37.7 %) | 10,229 (40.5 %) |
|   of which recalcStyle self (no nested GC) | 10,703 (42.3 %) | 7,134 (31.2 %) | 7,312 (30.2 %) | 7,414 (30.4 %) | 7,491 (29.8 %) | 7,862 (29.1 %) | 7,988 (28.9 %) | 7,986 (31.7 %) |
| layout | 4,254 (16.8 %) | 4,541 (19.8 %) | 4,754 (19.7 %) | 5,028 (20.6 %) | 5,316 (21.2 %) | 5,850 (21.6 %) | 7,041 (25.5 %) | 5,255 (20.8 %) |
|   of which text shaping | 1,797 (7.1 %) | 1,807 (7.9 %) | 1,865 (7.7 %) | 1,867 (7.7 %) | 2,009 (8.0 %) | 2,154 (8.0 %) | 2,216 (8.0 %) | 1,959 (7.8 %) |
| animation servicing (Blink.Animate) | 1,628 (6.4 %) | 1,692 (7.4 %) | 1,746 (7.2 %) | 1,765 (7.2 %) | 1,790 (7.1 %) | 1,852 (6.8 %) | 1,846 (6.7 %) | 1,760 (7.0 %) |
| pre-paint + compositing inputs | 1,694 (6.7 %) | 1,705 (7.4 %) | 1,729 (7.1 %) | 1,715 (7.0 %) | 1,755 (7.0 %) | 1,769 (6.5 %) | 1,787 (6.5 %) | 1,736 (6.9 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 4,149 (16.4 %) | 4,651 (20.3 %) | 5,082 (21.0 %) | 5,074 (20.8 %) | 4,852 (19.3 %) | 5,590 (20.7 %) | 5,128 (18.6 %) | 4,932 (19.6 %) |
|   of which Paint | 8 (0.0 %) | 8 (0.0 %) | 8 (0.0 %) | 8 (0.0 %) | 9 (0.0 %) | 9 (0.0 %) | 9 (0.0 %) | 8 (0.0 %) |
| hit-test (fake mousemove) | 540 (2.1 %) | 604 (2.6 %) | 631 (2.6 %) | 646 (2.6 %) | 664 (2.6 %) | 692 (2.6 %) | 705 (2.6 %) | 640 (2.5 %) |
| other busy (unattributed) | 869 (3.4 %) | 591 (2.6 %) | 624 (2.6 %) | 581 (2.4 %) | 564 (2.2 %) | 595 (2.2 %) | 599 (2.2 %) | 632 (2.5 %) |
| GC (nested inside the above) | 638 (2.5 %) | 887 (3.9 %) | 1,100 (4.5 %) | 901 (3.7 %) | 1,373 (5.5 %) | 1,512 (5.6 %) | 2,137 (7.7 %) | 1,221 (4.8 %) |
| style passes / layouts / frames | 133 / 88 / 52 | 132 / 87 / 46 | 132 / 87 / 46 | 132 / 87 / 46 | 132 / 87 / 46 | 132 / 87 / 46 | 132 / 87 / 46 | |
| major GCs | 3 | 3 | 2 | 2 | 2 | 2 | 2 | |
| token boundary (s after Run) | 25.3 | 48.2 | 72.4 | 96.8 | 121.9 | 149.0 | 176.6 | |
| handshakes (s after Run) | 0.1 run-start; 23.7 token-1-ready; 25.0 token-1-ack | 46.6 token-2-ready; 47.9 token-2-ack | 70.5 token-3-ready; 71.8 token-3-ack | 95.2 token-4-ready; 96.5 token-4-ack | 120.3 token-5-ready; 121.6 token-5-ack | 147.3 token-6-ready; 148.7 token-6-ack | 175.0 token-7-ready; 176.3 token-7-ack | |

### R2F-t1: style-pass histogram over the traced generate window (7 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 360 | 51.4 | 5,073 | 6.2 % | 14.1 | 0.1–20 | 73523.19 |
| 10-99 | 10 | 1.4 | 238 | 0.3 % | 23.8 | 12.4–30 | 609.46 |
| 100-999 | 295 | 42.1 | 27,522 | 33.4 % | 93.3 | 21.5–882 | 163.55 |
| 1k-9,999 | 384 | 54.9 | 46,011 | 55.8 % | 119.8 | 26.1–1639 | 34.35 |
| >=50%DOM | 8 | 1.1 | 3,602 | 4.4 % | 450.2 | 377.8–619 | 8.85 |
| **total** | 1057 | 151 | 82,447 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 1,553 | 88 | 12.6 | 17,596 | 200.0 | 128.8 |
| 3,089 | 96 | 13.7 | 12,700 | 132.3 | 42.8 |
| 126 | 95 | 13.6 | 11,877 | 125.0 | 992.3 |
| 784 | 96 | 13.7 | 10,801 | 112.5 | 143.5 |
| 2,323 | 81 | 11.6 | 6,798 | 83.9 | 36.1 |
| 0 | 333 | 47.6 | 4,754 | 14.3 | – |
| 6,919 | 96 | 13.7 | 4,172 | 43.5 | 6.3 |
| 780 | 96 | 13.7 | 3,612 | 37.6 | 48.2 |
| 50,892 | 8 | 1.1 | 3,602 | 450.2 | 8.8 |
| 2,326 | 8 | 1.1 | 1,656 | 207.0 | 89.0 |
| 2,381 | 1 | 0.1 | 1,639 | 1639.0 | 688.4 |
| 2,342 | 7 | 1.0 | 803 | 114.8 | 49.0 |
| 863 | 7 | 1.0 | 754 | 107.8 | 124.9 |
| 2,334 | 7 | 1.0 | 645 | 92.2 | 39.5 |
| 127 | 1 | 0.1 | 477 | 477.1 | 3756.7 |
| 1 | 18 | 2.6 | 245 | 13.6 | 13605.6 |
| 39 | 9 | 1.3 | 209 | 23.2 | 594.3 |
| 6 | 8 | 1.1 | 70 | 8.8 | 1458.3 |
| 40 | 1 | 0.1 | 30 | 29.7 | 742.5 |
| 3 | 1 | 0.1 | 4 | 4.3 | 1433.3 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 1 | 1 | 378 | 3.1 % | [1639.0, 2381] |
| 2 | 1 | 419 | 4.6 % | [419.1, 50892] |
| 3 | 1 | 445 | 4.6 % | [444.7, 50892] |
| 4 | 1 | 420 | 4.4 % | [419.8, 50892] |
| 5 | 1 | 527 | 5.2 % | [622.3, 2323] |
| 6 | 1 | 619 | 5.8 % | [632.7, 126] |
| 7 | 1 | 382 | 3.7 % | [473.8, 3089] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 142929], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 140710], ['V8.GC_MC_MARK_ROOTS', 69], ['V8.GC_MC_CLEAR_STRING_TABLE', 69], ['V8.GC_MC_SWEEP', 68], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 67], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 49], ['V8.GC_MC_MARK_EMBEDDER_PROLOGUE', 46]], total nested 10,720 ms

### R2F-t1: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 547 | 1432 | 1826 |
| token 1 (0–25 s) | 1682 | 2758 | 3789 |
| token 2 (25–48 s) | 3798 | 4167 | 4552 |
| token 3 (48–72 s) | 4479 | 4659 | 4867 |
| token 4 (72–97 s) | 4956 | 5079 | 5249 |
| token 5 (97–122 s) | 4878 | 5125 | 5388 |
| token 6 (122–149 s) | 4474 | 4771 | 5174 |
| token 7 (149–177 s) | 4247 | 4575 | 4876 |
| rest of run (177–204 s) | 3967 | 4324 | 4596 |
| after completion (readback) | 4630 | 4651 | 4673 |
| browser process peak | | | 224 |
| GPU process peak | | | 141 |

CDP Performance.getMetrics deltas Run→end (206.2 s wall): RecalcStyleCount +1088, RecalcStyleDuration +82.8 s, LayoutCount +696, LayoutDuration +43.2 s, TaskDuration +204.5 s; Nodes 133716, LayoutObjects 141434

Load phase (R2F-t1): {"wall_ms": 4679.8, "busy_ms": 1786.6, "idle_ms": 2893.1, "frames": 16, "style_ms": 816.9, "style_count": 20, "recalcStyle_ms": 779.3, "recalcStyle_count": 11, "updateStyle_ms": 795.2, "styleInvalidation_ms": 0.3, "layout_ms": 349.0, "layout_count": 17, "of_which_text_shaping_ms": 75.3, "text_shaping_count": 12561, "animate_ms": 42.7, "prepaint_ms": 25.4, "of_which_compositing_inputs_ms": 16.3, "paint_lifecycle_ms": 31.8, "of_which_Paint_ms": 1.9, "hittest_ms": 0.0, "hittest_count": 0, "gc_nested_ms": 43.8, "gc_count": 801, "recalcStyle_self_ms": 775.7, "gc_by_name": [["V8.GC_MC_INCREMENTAL", 12.6], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 12.1], ["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 5.0], ["MajorGC", 4.2], ["V8.GC_MARK_COMPACTOR", 4.0], ["V8.GC_MC_INCREMENTAL_START", 0.9]], "majorGC_count": 4, "other_busy_ms": 520.8, "animation_regex_ms": 61.3, "animation_regex_count": 15463, "paint_prepaint_composite_ms": 70.7}
named: {"ParseAuthorStyleSheet": [1, 55.3], "CSSParserImpl::parseStyleSheet": [3, 55.3], "CSSParserImpl::parseStyleSheet.parse": [3, 55.3], "StyleEngine::updateActiveStyleSheets": [2, 16.4], "RuleSet::addRulesFromSheet": [2, 0.8], "ParseHTML": [10, 157.9]}
big: [[62.9, 100.4, "RunTask", 0], [62.9, 100.4, "ResponseBodyLoader::OnStateChange", 1], [62.9, 100.4, "ResponseBodyLoader::DidFinishLoadingBody", 2], [163.4, 743.5, "RunTask", 0], [163.4, 742.3, "ProxyMain::BeginMainFrame", 1], [163.4, 742.1, "WebFrameWidgetImpl::UpdateLifecycle", 2], [939.9, 28.0, "RunTask", 0], [939.9, 28.0, "ProxyMain::BeginMainFrame", 1], [943.3, 24.5, "WebFrameWidgetImpl::UpdateLifecycle", 2], [992.3, 34.5, "RunTask", 0], [992.3, 34.5, "ProxyMain::BeginMainFrame", 1], [995.4, 30.9, "WebFrameWidgetImpl::UpdateLifecycle", 2]]
nav: {'responseEnd': 47.099999994039536, 'domInteractive': 1186.9000000059605, 'domContentLoadedEventEnd': 1187, 'domComplete': 2251.0999999940395, 'loadEventEnd': 2251.7999999821186} {'resources': 250, 'resourceBytes': 144169314, 'resourceEncodedBytes': 144169314, 'lastResourceEnd': 1356.5, 'cssResource': {'startTime': 8.400000005960464, 'responseEnd': 61.79999998211861, 'decodedBodySize': 41611806, 'encodedBodySize': 41611806}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 912}, {'name': 'first-contentful-paint', 'startTime': 912}], 'fontsStatus': 'loaded', 'fontsSize': 283, 'elements': 68947, 'scripts': 0}
timeline: {'tNav0': 547.3, 'tLoad': 2812.1, 'tIdle': 5221.5, 'tRun': 5231.8, 'tEndWait': 209407.6, 'stopReason': 'token-limit', 'traceBytes': 126650205, 'dataLossOccurred': False} finalState: {"headEpoch": 8, "winner": 1101} {"--saved-token-1": "11", "--saved-token-2": "314", "--saved-token-3": "1101", "--saved-token-4": "7926", "--saved-token-5": "11", "--saved-token-6": "475", "--saved-token-7": "314", "--saved-token-8": "1101", "tokenState": {"--epoch": "0", "--winner": "1101", "--head-output-epoch": "8"}}
