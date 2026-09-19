### ab-all: per-token phase split (ms; % of window wall)

| phase | token 1 | token 2 | mean |
|---|---:|---:|---:|
| wall | 32,307 | 32,442 | 32,374 |
| main-thread busy | 32,484 (100.5 %) | 32,421 (99.9 %) | 32,452 (100.2 %) |
| idle | -177 (-0.5 %) | 21 (0.1 %) | -78 (-0.2 %) |
| style (UpdateLayoutTree) | 17,037 (52.7 %) | 15,007 (46.3 %) | 16,022 (49.5 %) |
|   of which recalcStyle self (no nested GC) | 14,926 (46.2 %) | 12,239 (37.7 %) | 13,583 (42.0 %) |
| layout | 4,212 (13.0 %) | 4,744 (14.6 %) | 4,478 (13.8 %) |
|   of which text shaping | 1,771 (5.5 %) | 2,092 (6.4 %) | 1,931 (6.0 %) |
| animation servicing (Blink.Animate) | 2,702 (8.4 %) | 3,225 (9.9 %) | 2,964 (9.2 %) |
| pre-paint + compositing inputs | 1,742 (5.4 %) | 1,911 (5.9 %) | 1,826 (5.6 %) |
| paint lifecycle (RunPaintLifecyclePhase) | 4,583 (14.2 %) | 5,274 (16.3 %) | 4,928 (15.2 %) |
|   of which Paint | 13 (0.0 %) | 13 (0.0 %) | 13 (0.0 %) |
| hit-test (fake mousemove) | 738 (2.3 %) | 952 (2.9 %) | 845 (2.6 %) |
| other busy (unattributed) | 1,470 (4.5 %) | 1,309 (4.0 %) | 1,390 (4.3 %) |
| GC (nested inside the above) | 977 (3.0 %) | 1,399 (4.3 %) | 1,188 (3.7 %) |
| style passes / layouts / frames | 172 / 110 / 91 | 171 / 109 / 85 | |
| major GCs | 4 | 4 | |
| token boundary (s after Run) | 32.3 | 64.7 | |
| handshakes (s after Run) | 0.1 run-start; 30.7 token-1-ready; 32.0 token-1-ack | 62.8 token-2-ready; 64.4 token-2-ack | |

### ab-all: style-pass histogram over the traced generate window (2 complete tokens + partial)

| elementCount bucket | passes | per token | summed ms | % of style ms | mean ms/pass | min–max ms | µs per element |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1-9 | 128 | 64.0 | 1,701 | 5.1 % | 13.3 | 0.1–17 | 25394.03 |
| 10-99 | 1 | 0.5 | 64 | 0.2 % | 64.1 | 64.1–64 | 1602.5 |
| 100-999 | 122 | 61.0 | 16,111 | 48.7 % | 132.1 | 25.2–469 | 259.36 |
| 1k-9,999 | 102 | 51.0 | 14,145 | 42.8 % | 138.7 | 25.9–1672 | 38.56 |
| >=50%DOM | 2 | 1.0 | 1,053 | 3.2 % | 526.5 | 469.6–583 | 10.27 |
| **total** | 355 | 178 | 33,074 | 100 % | | | |

Recurring passes by exact elementCount (whole window; n = passes, ms = summed):

| elementCount | passes | per token | summed ms | mean ms | µs/element |
|---:|---:|---:|---:|---:|---:|
| 1,553 | 23 | 11.5 | 4,400 | 191.3 | 123.2 |
| 3,089 | 25 | 12.5 | 4,035 | 161.4 | 52.2 |
| 357 | 21 | 10.5 | 3,546 | 168.8 | 473.0 |
| 784 | 25 | 12.5 | 3,316 | 132.6 | 169.2 |
| 485 | 12 | 6.0 | 2,523 | 210.2 | 433.5 |
| 2,934 | 22 | 11.0 | 2,276 | 103.5 | 35.3 |
| 126 | 24 | 12.0 | 2,271 | 94.6 | 750.9 |
| 484 | 10 | 5.0 | 1,891 | 189.1 | 390.8 |
| 2,957 | 1 | 0.5 | 1,672 | 1672.4 | 565.6 |
| 780 | 25 | 12.5 | 1,297 | 51.9 | 66.5 |
| 51,247 | 2 | 1.0 | 1,053 | 526.5 | 10.3 |
| 0 | 75 | 37.5 | 1,018 | 13.6 | – |
| 6,919 | 25 | 12.5 | 853 | 34.1 | 4.9 |
| 1 | 48 | 24.0 | 628 | 13.1 | 13075.0 |
| 127 | 1 | 0.5 | 469 | 469.2 | 3694.5 |
| 487 | 2 | 1.0 | 438 | 219.1 | 449.8 |
| 2,326 | 2 | 1.0 | 415 | 207.5 | 89.2 |
| 368 | 2 | 1.0 | 360 | 180.2 | 489.8 |
| 2,917 | 2 | 1.0 | 291 | 145.3 | 49.8 |
| 1,438 | 2 | 1.0 | 203 | 101.4 | 70.5 |
| 40 | 1 | 0.5 | 64 | 64.1 | 1602.5 |
| 2 | 2 | 1.0 | 30 | 14.9 | 7450.0 |

Whole-DOM (≥50 % of 72,549 elements) passes per token:

| token | whole-DOM passes | ms | % of token style | biggest pass (ms, elements) |
|---:|---:|---:|---:|---|
| 1 | 1 | 470 | 2.8 % | [1672.4, 2957] |
| 2 | 1 | 583 | 3.9 % | [583.4, 51247] |

GC by name (window): [['V8.GC_MC_INCREMENTAL', 50729], ['V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 50062], ['V8.GC_MC_CLEAR_STRING_TABLE', 69], ['V8.GC_MC_SWEEP', 53], ['V8.GC_MC_MARK_ROOTS', 47], ['V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING', 47], ['V8.GC_MC_MARK_EMBEDDER_TRACING', 36], ['V8.GC_MC_MARK_EMBEDDER_PROLOGUE', 32]], total nested 2,467 ms

### ab-all: renderer RSS (MB, `ps`, 1 Hz)

| interval | min | mean | max |
|---|---:|---:|---:|
| launch→Run (load + idle) | 637 | 1455 | 1832 |
| token 1 (0–32 s) | 1679 | 2942 | 3863 |
| token 2 (32–65 s) | 3886 | 4086 | 4337 |
| after completion (readback) | 4010 | 4092 | 4155 |
| browser process peak | | | 223 |
| GPU process peak | | | 141 |

CDP Performance.getMetrics deltas Run→end (66.6 s wall): RecalcStyleCount +361, RecalcStyleDuration +33.0 s, LayoutCount +226, LayoutDuration +9.2 s, TaskDuration +66.4 s; Nodes 134297, LayoutObjects 141815

Load phase (ab-all): {"wall_ms": 4659.2, "busy_ms": 1754.5, "idle_ms": 2904.7, "frames": 13, "style_ms": 837.8, "style_count": 17, "recalcStyle_ms": 802.6, "recalcStyle_count": 10, "updateStyle_ms": 817.5, "styleInvalidation_ms": 0.3, "layout_ms": 326.7, "layout_count": 14, "of_which_text_shaping_ms": 74.0, "text_shaping_count": 9134, "animate_ms": 36.1, "prepaint_ms": 21.6, "of_which_compositing_inputs_ms": 14.7, "paint_lifecycle_ms": 31.0, "of_which_Paint_ms": 1.5, "hittest_ms": 0.0, "hittest_count": 0, "gc_nested_ms": 44.1, "gc_count": 906, "recalcStyle_self_ms": 801.5, "gc_by_name": [["V8.GC_MC_INCREMENTAL", 11.7], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 11.1], ["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 5.1], ["MajorGC", 4.6], ["V8.GC_MARK_COMPACTOR", 4.4], ["V8.GC_MC_INCREMENTAL_START", 0.8]], "majorGC_count": 4, "other_busy_ms": 501.3, "animation_regex_ms": 53.4, "animation_regex_count": 13227, "paint_prepaint_composite_ms": 63.1}
named: {"ParseAuthorStyleSheet": [1, 50.5], "CSSParserImpl::parseStyleSheet": [3, 50.5], "CSSParserImpl::parseStyleSheet.parse": [3, 50.5], "StyleEngine::updateActiveStyleSheets": [2, 15.9], "RuleSet::addRulesFromSheet": [2, 0.7], "ParseHTML": [10, 159.8]}
big: [[61.3, 89.9, "RunTask", 0], [61.3, 89.8, "ResponseBodyLoader::OnStateChange", 1], [61.3, 89.8, "ResponseBodyLoader::DidFinishLoadingBody", 2], [151.2, 694.2, "RunTask", 0], [151.2, 693.1, "ProxyMain::BeginMainFrame", 1], [151.3, 693.0, "WebFrameWidgetImpl::UpdateLifecycle", 2], [903.1, 33.7, "RunTask", 0], [903.1, 33.7, "ProxyMain::BeginMainFrame", 1], [906.1, 30.1, "WebFrameWidgetImpl::UpdateLifecycle", 2], [957.0, 194.3, "RunTask", 0], [957.0, 194.2, "HTMLDocumentParser::DeferredPumpTokenizerIfPossible", 1], [957.0, 194.2, "HTMLDocumentParser::PumpTokenizerIfPossible", 2]]
nav: {'responseEnd': 48.900000005960464, 'domInteractive': 1047, 'domContentLoadedEventEnd': 1047.0999999940395, 'domComplete': 2192.699999988079, 'loadEventEnd': 2193.5} {'resources': 250, 'resourceBytes': 143759989, 'resourceEncodedBytes': 143759989, 'lastResourceEnd': 1295.9000000059605, 'cssResource': {'startTime': 8.699999988079071, 'responseEnd': 61.29999998211861, 'decodedBodySize': 41667017, 'encodedBodySize': 41667017}, 'fontResources': 249, 'paint': [{'name': 'first-paint', 'startTime': 852}, {'name': 'first-contentful-paint', 'startTime': 852}], 'fontsStatus': 'loaded', 'fontsSize': 283, 'elements': 69522, 'scripts': 0}
timeline: {'tNav0': 571.5, 'tLoad': 2773.6, 'tIdle': 5221.6, 'tRun': 5234.6, 'tEndWait': 69668.8, 'stopReason': 'token-limit', 'traceBytes': 47848692, 'dataLossOccurred': False} finalState: {"headEpoch": 2, "winner": 314} {"--saved-token-1": "11", "--saved-token-2": "314", "tokenState": {"--epoch": "0", "--winner": "0", "--head-output-epoch": "0"}}
