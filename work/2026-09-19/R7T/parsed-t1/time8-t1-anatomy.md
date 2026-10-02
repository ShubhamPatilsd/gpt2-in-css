# R3A anatomy — R5A/run-combined7/time8-t1-trace.json.gz

main thread 19132/8911204; trace covers 392796.1 s; token bounds (s after trace start): [(6, 392751.4), (7, 392772.2)]

## per-token phase self-time (ms)

| phase | tok 7 | mean |
|---|---:|---:|
| wall | 20,829 | 20,829 |
| frames | 35 | 35.0 |
| style passes | 67 | 67.0 |
| style | 7,836 | 7,836 |
| layout | 7,766 | 7,766 |
| compinputs | 1,627 | 1,627 |
| animate | 1,366 | 1,366 |
| paintLC | 1,102 | 1,102 |
| UL-other | 816 | 816 |
| prepaint | 169 | 169 |
| frame-other | 12 | 12 |
| task | 5 | 5 |

## token 7 — top names by self time within each phase (name, count, self ms)

- **style** 7,836 ms: Document::recalcStyle ×67 6,024.5; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×1 555.4; Document::updateStyle ×67 359.5; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×12190 324.8; AnimationTimeline::serviceAnimations ×233929 296.4; style (self) ×67 186.8; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×1 40.3; V8.GC_MARK_COMPACTOR ×1 22.9; V8.GC_MC_INCREMENTAL ×12263 12.6; V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL ×1 3.1; Document::updateStyleInvalidationIfNeeded ×2 3.0; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×1 2.1; V8.GC_HEAP_EXTERNAL_PROLOGUE ×1 1.1; V8.GC_MC_MARK ×1 0.8
- **layout** 7,766 ms: LocalFrameView::performLayout ×64 4,301.5; InlineNode::ShapeTextIncludingFirstLine ×199452 2,278.2; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×1 809.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×5995 242.3; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×1 62.0; V8.GC_MARK_COMPACTOR ×1 44.8; layout (self) ×64 12.0; V8.GC_MC_INCREMENTAL ×6107 5.9; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×1 3.0; FontCache::GetFontPlatformData ×48 2.7; V8.GC_HEAP_EXTERNAL_PROLOGUE ×1 1.4; V8.GC_MC_MARK ×1 1.0; V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL ×1 0.6; V8.GC_MC_CLEAR_SWEEP_EXTERNAL_POINTER_TABLE ×1 0.2
- **compinputs** 1,627 ms: Blink.CompositingInputs.UpdateTime ×35 1,626.9; compinputs (self) ×35 0.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×2 0.1; LayoutView::commitPendingSelection ×33 0.0; V8.GC_MC_INCREMENTAL ×2 0.0
- **animate** 1,366 ms: PageAnimator::serviceScriptedAnimations ×35 854.9; AnimationTimeline::serviceAnimations ×325866 457.3; LocalFrameView::ScheduleAnimation ×38268 52.0; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×53 1.2; Blink.Animate.UpdateTime ×35 0.2; animate (self) ×35 0.2; V8.GC_MC_INCREMENTAL ×55 0.1; EventDispatch ×2 0.0; AsyncTask Run ×2 0.0; AsyncTask Scheduled ×2 0.0
- **paintLC** 1,102 ms: paintLC (self) ×35 1,084.8; CullRectUpdate ×34 5.5; Paint ×71 5.1; Blink.Paint.UpdateTime ×35 4.3; PaintArtifactCompositor::Update ×35 1.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×20 0.4; LocalFrameView::ScheduleAnimation ×26 0.2; Layerize ×35 0.1; ScrollTree::SetScrollOffset ×75 0.1; PaintController::commitNewDisplayItems ×33 0.1; Blink.CompositingCommit.UpdateTime ×35 0.1; V8.GC_MC_INCREMENTAL ×22 0.1; LocalFrameView::pushPaintArtifactToCompositor ×35 0.0; auto cc::LayerTreeHost::SetNeedsCommit(bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const ×4 0.0
- **UL-other** 816 ms: UL-other (self) ×35 704.5; LocalFrameView::ScheduleAnimation ×77606 84.6; LocalFrameView::UpdateStyleAndLayout ×67 23.5; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×37 1.0; Blink.Layout.UpdateTime ×64 0.8; Blink.Style.UpdateTime ×67 0.4; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×67 0.3; LocalFrameView::layout ×64 0.2; LocalFrameView::performPostLayoutTasks ×64 0.2; LocalFrameView::DidFinishLifecycleUpdate ×35 0.1; PrePaint ×35 0.1; LocalFrameView::NotifyResizeObservers ×35 0.1; ResourceLoadPriorityOptimizer::UpdateImagePrioritiesAndSpeculativeDecodes ×48 0.1; LocalFrameView::WillStartLifecycleUpdate ×35 0.1
- **prepaint** 169 ms: Blink.PrePaint.UpdateTime ×35 168.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×12 0.3; prepaint (self) ×35 0.1; V8.GC_MC_INCREMENTAL ×12 0.0
- **frame-other** 12 ms: HitTest ×26 8.6; frame-other (self) ×35 1.7; MainFrameAborted ×32 0.6; LayerTreeHost::WaitForCommitCompletion ×35 0.2; OverlayInterstitialAdDetector::MaybeFireDetection ×13 0.1; LayerTreeHost::ApplyCompositorChanges ×35 0.1; LocalFrameView::RunAccessibilitySteps ×35 0.1; AnimationHost::TickAnimations ×33 0.1; StickyAdDetector::MaybeFireDetection ×13 0.1; Blink.IntersectionObservation.UpdateTime ×35 0.1; Blink.Accessibility.UpdateTime ×35 0.1; LocalFrameView::UpdateViewportIntersectionsForSubtree ×35 0.1; LayerTreeHost::DoUpdateLayers ×3 0.0; ProxyMain::BeginMainFrame::commit ×3 0.0
- **task** 5 ms: MemoryDumpManager::InvokeOnMemoryDump ×12 2.6; MemoryDumpManager::FinishAsyncProcessDump ×1 1.9; TimerBase::run ×2 0.8; AsyncTask Run ×2 0.0; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1 0.0; EventDispatch ×2 0.0; V8.GC_MC_INCREMENTAL ×1 0.0; AsyncTask Scheduled ×2 0.0

### token 7 — passes by elementCount (n, sum ms, mean ms; mean children self ms per pass)

- ec 163: n 12, sum 2,511, mean 209.2: Document::recalcStyle ×1.0 131.12; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×0.1 46.28; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×186.2 11.79; Document::updateStyle ×1.0 6.08; AnimationTimeline::serviceAnimations ×3833.3 4.73; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 3.36; V8.GC_MARK_COMPACTOR ×0.1 1.91; V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL ×0.1 0.26; V8.GC_MC_INCREMENTAL ×182.2 0.19; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×0.1 0.18 | inst {"AnimationTimeline::serviceAnimations": 5334.1, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.2, "ClearStringTableJob started": 0.2, "Document::updateActiveStyle": 0.2, "V8.GC_HEAP_PROLOGUE_SAFEPOINT": 0.1, "V8.GC_MC_MARK_WEAK_CLOSURE_EPHEMERON_MARKING": 0.1}
- ec 3141: n 12, sum 1,665, mean 138.8: Document::recalcStyle ×1.0 120.87; Document::updateStyle ×1.0 5.66; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×264.8 4.88; AnimationTimeline::serviceAnimations ×3529.9 4.27; V8.GC_MC_INCREMENTAL ×266.7 0.27; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 5637.5, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.9, "Document::updateActiveStyle": 0.2}
- ec 824: n 12, sum 1,583, mean 131.9: Document::recalcStyle ×1.0 113.91; Document::updateStyle ×1.0 5.6; AnimationTimeline::serviceAnimations ×4088.6 5.17; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×239.4 4.01; V8.GC_MC_INCREMENTAL ×240.8 0.25; Document::updateActiveStyle ×0.7 0.0 | inst {"AnimationTimeline::serviceAnimations": 5078.8, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.4, "Document::updateActiveStyle": 0.3}
- ec 2366: n 11, sum 910, mean 82.7: Document::recalcStyle ×1.0 67.88; Document::updateStyle ×1.0 5.47; AnimationTimeline::serviceAnimations ×3127.5 3.92; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×133.3 2.55; V8.GC_MC_INCREMENTAL ×134.4 0.14; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 5264.8, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.1, "Document::updateActiveStyle": 0.2}
- ec 800: n 12, sum 481, mean 40.1: Document::recalcStyle ×1.0 25.95; Document::updateStyle ×1.0 5.45; AnimationTimeline::serviceAnimations ×3459.2 4.63; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×50.0 1.14; V8.GC_MC_INCREMENTAL ×50.1 0.06; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 5708.2, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.1}
- ec 50898: n 1, sum 427, mean 427.0: Document::recalcStyle ×1.0 391.62; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1438.0 28.53; Document::updateStyle ×1.0 5.18; V8.GC_MC_INCREMENTAL ×1440.0 1.44; Document::updateActiveStyle ×1.0 0.0 | inst {"V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 4.0, "V8.GC_MC_INCREMENTAL": 2.0}
- ec 2405: n 1, sum 125, mean 124.6: Document::recalcStyle ×1.0 98.49; AnimationTimeline::serviceAnimations ×7874.0 10.56; Document::updateStyle ×1.0 5.38; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×247.0 4.09; V8.GC_MC_INCREMENTAL ×247.0 0.27 | inst {"AnimationTimeline::serviceAnimations": 10589.0, "Document::updateActiveStyle": 1.0}
- ec 895: n 1, sum 74, mean 73.7: Document::recalcStyle ×1.0 63.57; Document::updateStyle ×1.0 5.57; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×125.0 1.88; Document::updateStyleInvalidationIfNeeded ×1.0 1.32; LocalFrameView::ScheduleAnimation ×598.0 0.67; Document::rebuildLayoutTree ×1.0 0.34; V8.GC_MC_INCREMENTAL ×128.0 0.12; Document::updateActiveStyle ×1.0 0.0 | inst {"LocalFrameView::ScheduleAnimation|Add": 171.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 3.0, "ProxyMain::SetNeedsAnimate": 1.0}
- ec 791: n 1, sum 29, mean 29.0: Document::recalcStyle ×1.0 10.54; AnimationTimeline::serviceAnimations ×6633.0 8.09; Document::updateStyle ×1.0 4.49; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×27.0 0.52; Document::rebuildLayoutTree ×1.0 0.3; V8.GC_MC_INCREMENTAL ×27.0 0.03; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 11830.0}
- ec 39: n 1, sum 17, mean 17.1: Document::recalcStyle ×1.0 10.24; Document::updateStyle ×1.0 5.0; Document::updateStyleInvalidationIfNeeded ×1.0 1.64; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.01; V8.GC_MC_INCREMENTAL ×1.0 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {}
- ec 6: n 1, sum 14, mean 14.3: AnimationTimeline::serviceAnimations ×6087.0 9.0; Document::recalcStyle ×1.0 1.03; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×2.0 0.01; V8.GC_MC_INCREMENTAL ×2.0 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 12376.0}
- ec 1: n 2, sum 0, mean 0.2: Document::recalcStyle ×1.0 0.03; Document::updateStyle ×1.0 0.01; Document::updateActiveStyle ×0.5 0.0 | inst {"Document::updateActiveStyle": 0.5}

### token 7 — instants: {"AnimationTimeline::serviceAnimations": 671074, "Animation": 94682, "LocalFrameView::ScheduleAnimation|Add": 17635, "LocalFrameView::ScheduleAnimation|ScheduleServiceOnNextFrame": 8973, "InlineNode::ShapeTextIncludingFirstLine": 516, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 198, "ScrollTree::SetScrollOffset": 65, "LongTask": 35, "ProxyMain::SetNeedsAnimate": 35, "AnimationFrame::Presentation": 35, "EarlyOut_NoUpdates": 32, "RootScrollerController::PerformRootScrollerSelection": 17}

### token 7 — Animation b/e: {"b/running": 449, "e/": 4}; names: [('--fc-vs-N-N|b', 144), ('--fc-v-N-N|b', 144), ('--fc-ks-N-N|b', 144), ('--fc-k-N|b', 12), ('|e', 4), ('native-handshake|b', 2), ('--saved-token-N|b', 1), ('--head-input-epoch|b', 1), ('--head-fvs|b', 1)]

### token 7 — head frame: 1,318 ms at 15,651 ms; phases {"frame-other": 0.79, "animate": 42.42, "UL-other": 27.85, "style": 894.19, "layout": 287.31, "compinputs": 23.73, "prepaint": 5.44, "paintLC": 36.59}; passes [(2366, 63.19), (163, 831.0)]; layouts [(6995, 52.27), (351, 235.04)]
  top: {"frame-other": [["HitTest", 0.65], ["frame-other (self)", 0.08], ["MainFrameAborted", 0.03], ["LayerTreeHost::WaitForCommitCompletion", 0.01], ["OverlayInterstitialAdDetector::MaybeFireDetection", 0.01], ["StickyAdDetector::MaybeFireDetection", 0.0]], "animate": [["PageAnimator::serviceScriptedAnimations", 24.38], ["AnimationTimeline::serviceAnimations", 17.3], ["LocalFrameView::ScheduleAnimation", 0.73], ["animate (self)", 0.01], ["Blink.Animate.UpdateTime", 0.01]], "UL-other": [["UL-other (self)", 21.94], ["LocalFrameView::ScheduleAnimation", 4.46], ["LocalFrameView::UpdateStyleAndLayout", 1.33], ["Blink.Layout.UpdateTime", 0.03], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.03], ["Blink.Style.UpdateTime", 0.02]], "style": [["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 555.38], ["Document::recalcStyle", 200.72], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 106.81], ["Document::updateStyle", 13.21], ["AnimationTimeline::serviceAnimations", 9.56], ["style (self)", 5.9]], "layout": [["LocalFrameView::performLayout", 236.02], ["InlineNode::ShapeTextIncludingFirstLine", 40.24], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 10.49], ["layout (self)", 0.27], ["V8.GC_MC_INCREMENTAL", 0.22], ["FontCache::GetFontPlatformData", 0.07]], "compinputs": [["Blink.CompositingInputs.UpdateTime", 23.73], ["compinputs (self)", 0.0], ["LayoutView::commitPendingSelection", 0.0]], "prepaint": [["Blink.PrePaint.UpdateTime", 5.44], ["prepaint (self)", 0.0]], "paintLC": [["paintLC (self)", 36.09], ["CullRectUpdate", 0.15], ["Paint", 0.12], ["Blink.Paint.UpdateTime", 0.12], ["PaintArtifactCompositor::Update", 0.09], ["PaintController::commitNewDisplayItems", 0.0]]}

### token 7 — frames

| # | t | dur | passes ec:ms | layouts dirty:ms | style | layout | compinputs | animate | paintLC | UL-other | prepaint | frame-other | task | sa X | anim b/e |
|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 233 | 555 | 163:144 800:47 | 351:229 2416:25 | 191 | 254 | 10 | 38 | 33 | 23 | 4 | 1 | 0 | 16272 | 37/0 |
| 1 | 796 | 568 | 3141:134 824:139 | 9380:60 2471:67 | 273 | 127 | 47 | 49 | 38 | 29 | 4 | 0 | 0 | 17354 | 0/0 |
| 2 | 1,368 | 629 | 2366:73 163:161 | 6995:50 351:216 | 234 | 266 | 23 | 37 | 35 | 27 | 6 | 1 | 0 | 18274 | 37/0 |
| 3 | 2,004 | 410 | 800:36 3141:170 | 2416:25 9380:67 | 205 | 92 | 24 | 39 | 24 | 21 | 5 | 0 | 0 | 15769 | 0/0 |
| 4 | 2,415 | 460 | 824:136 2366:93 | 2471:68 6995:48 | 230 | 116 | 14 | 40 | 36 | 22 | 3 | 0 | 0 | 17069 | 0/0 |
| 5 | 2,877 | 552 | 163:140 800:53 | 351:225 2416:25 | 192 | 250 | 11 | 38 | 34 | 21 | 4 | 1 | 0 | 15565 | 37/0 |
| 6 | 3,434 | 587 | 3141:138 824:146 | 9380:69 2471:76 | 284 | 146 | 48 | 36 | 41 | 27 | 5 | 0 | 0 | 17340 | 0/0 |
| 7 | 4,023 | 778 | 2366:89 163:154 | 6995:59 351:338 | 243 | 397 | 25 | 41 | 37 | 27 | 7 | 1 | 0 | 18461 | 37/0 |
| 8 | 4,808 | 371 | 800:29 3141:139 | 2416:26 9380:60 | 167 | 87 | 24 | 40 | 27 | 23 | 4 | 0 | 0 | 16703 | 0/0 |
| 9 | 5,186 | 471 | 824:103 2366:98 | 2471:76 6995:65 | 201 | 141 | 13 | 45 | 43 | 24 | 4 | 0 | 0 | 18114 | 0/0 |
| 10 | 5,665 | 1,625 | 163:168 800:49 | 351:1273 2416:23 | 217 | 1296 | 11 | 40 | 32 | 24 | 4 | 1 | 0 | 15682 | 37/0 |
| 11 | 7,298 | 542 | 3141:123 824:135 | 9380:63 2471:66 | 258 | 129 | 45 | 40 | 36 | 31 | 4 | 0 | 0 | 17530 | 0/0 |
| 12 | 7,842 | 617 | 2366:70 163:154 | 6995:44 351:220 | 224 | 264 | 25 | 40 | 34 | 26 | 5 | 1 | 0 | 18422 | 37/0 |
| 13 | 8,465 | 362 | 800:32 3141:138 | 2416:22 9380:59 | 170 | 81 | 23 | 38 | 26 | 20 | 4 | 0 | 0 | 16119 | 0/0 |
| 14 | 8,828 | 438 | 824:126 2366:82 | 2471:67 6995:45 | 208 | 112 | 12 | 43 | 37 | 23 | 3 | 0 | 0 | 17704 | 0/0 |
| 15 | 9,268 | 539 | 163:135 800:46 | 351:224 2416:26 | 181 | 250 | 10 | 38 | 34 | 20 | 4 | 1 | 0 | 15380 | 37/0 |
| 16 | 9,813 | 575 | 3141:140 824:147 | 9380:62 2471:72 | 287 | 134 | 45 | 38 | 38 | 28 | 5 | 0 | 0 | 17064 | 0/0 |
| 17 | 10,390 | 634 | 2366:74 163:152 | 6995:46 351:230 | 226 | 276 | 25 | 38 | 34 | 28 | 6 | 1 | 0 | 18391 | 37/0 |
| 18 | 11,030 | 386 | 800:34 3141:151 | 2416:24 9380:62 | 185 | 86 | 23 | 40 | 26 | 20 | 5 | 0 | 0 | 15973 | 0/0 |
| 19 | 11,417 | 459 | 824:128 2366:95 | 2471:69 6995:52 | 223 | 121 | 13 | 45 | 35 | 20 | 3 | 0 | 0 | 17384 | 0/0 |
| 20 | 11,878 | 552 | 163:141 800:47 | 351:226 2416:26 | 188 | 252 | 11 | 39 | 34 | 22 | 4 | 1 | 0 | 16038 | 37/0 |
| 21 | 12,437 | 575 | 3141:140 824:144 | 9380:69 2471:70 | 284 | 139 | 45 | 40 | 36 | 26 | 5 | 0 | 0 | 16743 | 0/0 |
| 22 | 13,014 | 638 | 2366:81 163:141 | 6995:49 351:235 | 223 | 284 | 26 | 37 | 34 | 27 | 6 | 1 | 0 | 18098 | 37/0 |
| 23 | 13,658 | 402 | 800:36 3141:156 | 2416:26 9380:69 | 193 | 95 | 23 | 39 | 26 | 22 | 4 | 0 | 0 | 16323 | 0/0 |
| 24 | 14,061 | 454 | 824:129 2366:92 | 2471:72 6995:45 | 221 | 117 | 13 | 43 | 36 | 22 | 3 | 0 | 0 | 17406 | 0/0 |
| 25 | 14,517 | 584 | 163:189 800:42 | 351:217 2416:26 | 231 | 243 | 11 | 36 | 35 | 23 | 4 | 1 | 0 | 15621 | 37/0 |
| 26 | 15,113 | 530 | 3141:101 824:121 | 9380:61 2471:79 | 222 | 140 | 49 | 42 | 43 | 28 | 6 | 0 | 0 | 17998 | 0/0 |
| 27 | 15,651 | 1,318 | 2366:63 163:831 | 6995:52 351:235 | 894 | 287 | 24 | 42 | 37 | 28 | 5 | 1 | 0 | 18499 | 37/0 |
| 28 | 16,977 | 367 | 800:31 3141:135 | 2416:23 9380:65 | 166 | 88 | 23 | 39 | 25 | 22 | 4 | 0 | 0 | 15651 | 0/0 |
| 29 | 17,344 | 324 | 824:128 791:29 | 2471:69 813:4 | 157 | 73 | 0 | 44 | 27 | 22 | 1 | 0 | 0 | 16945 | 0/0 |
| 30 | 17,670 | 2,744 | 50898:427 6:14 | 101181:1279 | 441 | 1279 | 915 | 37 | 23 | 18 | 31 | 0 | 0 | 14650 | 1/2 |
| 31 | 20,414 | 70 | 1:0 |  | 0 | 0 | 0 | 38 | 15 | 16 | 1 | 0 | 0 | 8559 | 0/1 |
| 32 | 20,485 | 91 | 39:17 | 7:11 | 17 | 11 | 0 | 28 | 16 | 18 | 1 | 0 | 0 | 6161 | 1/0 |
| 33 | 20,576 | 60 | 1:0 |  | 0 | 0 | 0 | 29 | 15 | 14 | 1 | 0 | 0 | 6208 | 0/1 |
| 34 | 20,636 | 439 | 895:74 2405:137 | 1601:87 6997:48 | 211 | 135 | 14 | 32 | 21 | 23 | 4 | 0 | 0 | 13883 | 3/0 |

## inventory (cat, name, ph, count, sum ms) — top 120

- ('blink', 'AnimationTimeline::serviceAnimations', 'I', 1927601, 0.0)
- ('blink', 'AnimationTimeline::serviceAnimations', 'X', 1580376, 2153.09)
- ('blink', 'InlineNode::ShapeTextIncludingFirstLine', 'X', 555103, 7304.34)
- ('cc', 'LocalFrameView::ScheduleAnimation', 'X', 312758, 353.71)
- ('blink.animations,devtools.timeline,benchmark,rail', 'Animation', 'n', 257621, 0.0)
- ('cc', 'LocalFrameView::ScheduleAnimation', 'I', 72466, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL', 's', 49320, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL', 'f', 49320, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL', 'X', 49302, 1535.06)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 'X', 48791, 1485.34)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'PipelineReporter', 'b', 3518, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'BeginImplFrameToSendBeginMainFrame', 'b', 3518, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'BeginImplFrameToSendBeginMainFrame', 'e', 3518, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'PipelineReporter', 'e', 3518, 0.0)
- ('cc', 'auto cc::SchedulerStateMachine::ShouldThrottleSendBeginMainFrame()::(lambda)::operator()(uint32_t) const', 'I', 3512, 0.0)
- ('cc,benchmark', 'Scheduler::BeginFrame', 'X', 3413, 45.03)
- ('cc,benchmark', 'Scheduler::BeginImplFrame', 'X', 3411, 33.46)
- ('cc', 'auto cc::Scheduler::FinishImplFrame()::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 3410, 62.85)
- ('cc', 'auto cc::Scheduler::SendDidNotProduceFrame(const viz::BeginFrameArgs &, FrameSkippedReason)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 3407, 51.92)
- ('cc,benchmark', 'LayerTreeHostImpl::DidNotProduceFrame', 'X', 3402, 44.55)
- ('cc', 'DidNotSubmitInLastFrame', 'X', 3399, 56.86)
- ('cc', 'Scheduler::ScheduleBeginImplFrameDeadline', 'X', 3397, 6.32)
- ('cc,benchmark', 'Scheduler::OnBeginImplFrameDeadline', 'X', 3373, 9.18)
- ('cc', 'AnimationHost::TickAnimations', 'I', 2059, 0.0)
- ('cc', 'AnimationHost::TickAnimations', 'X', 1465, 1.59)
- ('blink', 'InlineNode::ShapeTextIncludingFirstLine', 'I', 1387, 0.0)
- ('blink.animations,devtools.timeline,benchmark,rail', 'Animation', 'b', 1196, 0.0)
- ('disabled-by-default-memory-infra', 'MemoryDumpManager::InvokeOnMemoryDump', 'X', 1013, 270.58)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 'I', 529, 0.0)
- ('devtools.timeline', 'Paint', 'X', 197, 23.48)
- ('cc', 'ScrollTree::SetScrollOffset', 'I', 197, 0.0)
- ('blink', 'LocalFrameView::UpdateStyleAndLayout', 'X', 190, 41957.38)
- ('blink', 'Blink.Style.UpdateTime', 'X', 190, 22522.04)
- ('blink,devtools.timeline', 'UpdateLayoutTree', 'X', 190, 22520.97)
- ('blink,blink_style', 'Document::updateStyle', 'X', 190, 21111.5)
- ('cc', 'ScrollTree::SetScrollOffset', 'X', 187, 0.28)
- ('blink,benchmark', 'LocalFrameView::RunStyleAndLayoutLifecyclePhases', 'X', 185, 41886.57)
- ('blink,blink_style', 'Document::recalcStyle', 'X', 184, 20148.45)
- ('blink', 'Blink.Layout.UpdateTime', 'X', 173, 19448.26)
- ('blink,benchmark', 'LocalFrameView::layout', 'X', 173, 19446.17)
- ('devtools.timeline', 'Layout', 'X', 173, 19445.66)
- ('blink,benchmark,rail,disabled-by-default-blink.debug.layout', 'LocalFrameView::performLayout', 'X', 173, 19412.79)
- ('blink,benchmark', 'LocalFrameView::performPostLayoutTasks', 'X', 173, 0.66)
- ('blink', 'Document::updateActiveStyle', 'X', 158, 0.25)
- ('blink', 'ResourceLoadPriorityOptimizer::UpdateImagePrioritiesAndSpeculativeDecodes', 'X', 138, 0.19)
- ('blink', 'RootScrollerController::PerformRootScrollerSelection', 'X', 136, 0.16)
- ('fonts', 'FontCache::GetFontPlatformData', 'X', 130, 8.06)
- ('__metadata', 'ActiveProcesses', 'I', 124, 0.0)
- ('cc', 'LayerTreeHost::WaitForCommitCompletion', 'X', 102, 0.53)
- ('devtools.timeline,disabled-by-default-v8.gc', 'Sweeper::ConcurrentMajorSweeper Finished', 'I', 101, 0.0)
- ('blink', 'LongTask', 'I', 101, 0.0)
- ('cc', 'LayerTreeHost::ApplyCompositorChanges', 'X', 101, 0.2)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'SendBeginMainFrameToCommit', 'b', 101, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'SendBeginMainFrameToCommit', 'e', 101, 0.0)
- ('devtools.timeline', 'PrePaint', 'X', 100, 5154.36)
- ('blink,benchmark', 'LocalFrameView::RunCompositingInputsLifecyclePhase', 'X', 100, 4676.86)
- ('blink', 'Blink.CompositingInputs.UpdateTime', 'X', 100, 4676.53)
- ('blink,benchmark', 'LocalFrameView::RunPrePaintLifecyclePhase', 'X', 100, 477.1)
- ('blink', 'Blink.PrePaint.UpdateTime', 'X', 100, 476.73)
- ('blink,benchmark', 'LocalFrameView::RunPaintLifecyclePhase', 'X', 100, 3053.93)
- ('blink', 'Blink.Paint.UpdateTime', 'X', 100, 42.27)
- ('blink', 'LocalFrameView::pushPaintArtifactToCompositor', 'X', 100, 5.61)
- ('blink', 'Blink.CompositingCommit.UpdateTime', 'X', 100, 5.49)
- ('devtools.timeline', 'Layerize', 'X', 100, 5.36)
- ('blink', 'LocalFrameView::DidFinishLifecycleUpdate', 'X', 100, 0.39)
- ('blink,benchmark', 'LocalFrameView::RunAccessibilitySteps', 'X', 100, 0.37)
- ('blink,benchmark', 'LocalFrameView::UpdateViewportIntersectionsForSubtree', 'X', 100, 0.3)
- ('devtools.timeline', 'AnimationFrame', 'b', 100, 0.0)
- ('devtools.timeline', 'AnimationFrame::Render', 'b', 100, 0.0)
- ('devtools.timeline', 'AnimationFrame::StyleAndLayout', 'b', 100, 0.0)
- ('devtools.timeline', 'AnimationFrame::StyleAndLayout', 'e', 100, 0.0)
- ('devtools.timeline', 'AnimationFrame::Render', 'e', 100, 0.0)
- ('devtools.timeline', 'AnimationFrame', 'e', 100, 0.0)
- ('blink,benchmark', 'LocalFrameView::NotifyResizeObservers', 'X', 99, 0.24)
- ('blink,benchmark', 'CullRectUpdate', 'X', 99, 15.12)
- ('cc,benchmark', 'ProxyImpl::ScheduledActionSendBeginMainFrame', 'X', 99, 0.57)
- ('cc,benchmark', 'SendBeginMainFrame', 'I', 99, 0.0)
- ('cc,benchmark', 'ProxyMain::BeginMainFrame', 'X', 99, 56125.2)
- ('blink', 'WebFrameWidgetImpl::BeginMainFrame', 'X', 99, 3829.49)
- ('blink', 'Blink.Animate.UpdateTime', 'X', 99, 3828.97)
- ('blink,rail', 'PageAnimator::serviceScriptedAnimations', 'X', 99, 3828.43)
- ('blink', 'WebFrameWidgetImpl::UpdateLifecycle', 'X', 99, 52261.32)
- ('cc,benchmark', 'SendBeginMainFrame', 's', 99, 0.0)
- ('cc,benchmark', 'SendBeginMainFrame', 'f', 99, 0.0)
- ('cc,benchmark', 'ProxyMain::BeginMainFrame', 's', 99, 0.0)
- ('cc,benchmark', 'ProxyMain::BeginMainFrame', 'f', 99, 0.0)
- ('blink', 'Blink.Accessibility.UpdateTime', 'X', 98, 0.18)
- ('blink', 'Blink.IntersectionObservation.UpdateTime', 'X', 98, 0.18)
- ('cc', 'ProxyImpl::SetNeedsCommitOnImplThread', 'X', 98, 2.11)
- ('devtools.timeline', 'AnimationFrame', 's', 98, 0.0)
- ('devtools.timeline', 'AnimationFrame', 'f', 98, 0.0)
- ('devtools.timeline', 'AnimationFrame::Presentation', 'n', 98, 0.0)
- ('cc', 'ProxyMain::SetNeedsAnimate', 'I', 97, 0.0)
- ('cc', 'auto cc::SchedulerStateMachine::SetNeedsBeginMainFrame(bool, bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 97, 0.21)
- ('blink', 'LocalFrameView::WillStartLifecycleUpdate', 'X', 97, 0.16)
- ('blink', 'PaintArtifactCompositor::Update', 'X', 96, 5.0)
- ('blink', 'LayoutView::commitPendingSelection', 'X', 91, 0.12)
- ('blink,benchmark', 'PaintController::commitNewDisplayItems', 'X', 91, 0.24)
- ('cc,raf_investigation', 'EarlyOut_NoUpdates', 'I', 90, 0.0)
- ('cc,benchmark', 'MainFrameAborted', 'X', 90, 2.03)
- ('cc', 'ProxyImpl::BeginMainFrameAbortedOnImplThread', 'X', 90, 9.72)
- ('cc', 'Scheduler::BeginMainFrameAborted', 'X', 90, 1.64)
- ('blink', 'LocalFrameView::UpdateLifecyclePhases - start of lifecycle tasks', 'X', 87, 0.12)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_BACKGROUND_MARKING', 'X', 86, 18.26)
- ('cc', 'Scheduler::NotifyBeginMainFrameStarted', 'X', 83, 0.09)
- ('blink,devtools.timeline', 'HitTest', 'X', 78, 25.66)
- ('devtools.timeline,disabled-by-default-v8.gc', 'ConcurrentMarking::RunMajor Finished', 'X', 74, 0.26)
- ('cc', 'ScrollTree::CollectScrollDeltas', 'X', 72, 0.07)
- ('cc', 'ScheduledTasksState', 'n', 72, 0.0)
- ('disabled-by-default-memory-infra', 'periodic_interval', 'v', 68, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'Sweeper::ConcurrentMajorSweeper Finished', 'X', 64, 0.08)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_CLEAR_STRING_TABLE', 'X', 62, 2.2)
- ('devtools.timeline,disabled-by-default-v8.gc', 'ClearStringTableJob started', 's', 56, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'ClearStringTableJob started', 'f', 56, 0.0)
- ('blink', 'RootScrollerController::PerformRootScrollerSelection', 'I', 50, 0.0)
- ('disabled-by-default-memory-infra', 'MemoryDumpManager::FinishAsyncProcessDump', 'X', 49, 50.81)
- ('disabled-by-default-memory-infra', 'ProcessMemoryDump', 'b', 49, 0.0)
- ('disabled-by-default-memory-infra', 'ProcessMemoryDump', 'e', 49, 0.0)
- ('cc', 'auto cc::(anonymous namespace)::InsertNodeForTask(TaskGraph *, TileTask *, uint16_t, uint16_t, size_t, bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'I', 47, 0.0)
- ('cc', 'TaskSetFinishedTaskImpl::RunOnWorkerThread', 'X', 43, 0.39)