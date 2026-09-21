# R3A anatomy — R3A/runs/R2F-heavy-trace.json.gz

main thread 32851/4560404; trace covers 207746.0 s; token bounds (s after trace start): [(3, 207575.7), (4, 207607.0), (5, 207640.6), (6, 207673.2), (7, 207708.0)]

## per-token phase self-time (ms)

| phase | tok 4 | tok 5 | tok 6 | tok 7 | mean |
|---|---:|---:|---:|---:|---:|
| wall | 31,219 | 33,591 | 32,682 | 34,804 | 33,074 |
| frames | 46 | 46 | 46 | 46 | 46.0 |
| style passes | 132 | 132 | 132 | 132 | 132.0 |
| style | 13,030 | 15,687 | 13,708 | 16,374 | 14,700 |
| layout | 6,914 | 6,699 | 8,083 | 7,308 | 7,251 |
| paintLC | 5,472 | 5,197 | 4,938 | 5,207 | 5,204 |
| animate | 2,244 | 2,264 | 2,306 | 2,257 | 2,268 |
| compinputs | 1,733 | 1,740 | 1,742 | 1,746 | 1,740 |
| UL-other | 1,472 | 1,467 | 1,470 | 1,463 | 1,468 |
| prepaint | 200 | 210 | 216 | 223 | 212 |
| task | 14 | 180 | 29 | 41 | 66 |
| hover | 37 | 39 | 40 | 38 | 39 |
| frame-other | 17 | 19 | 19 | 20 | 19 |

## token 4 — top names by self time within each phase (name, count, self ms)

- **style** 13,030 ms: Document::recalcStyle ×90 9,811.4; AnimationTimeline::serviceAnimations ×738493 945.3; style (self) ×132 657.3; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×1 501.0; Document::updateStyle ×132 487.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×13041 388.9; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×2 136.6; V8.GC_MARK_COMPACTOR ×2 63.1; V8.GC_MC_INCREMENTAL ×13209 15.4; V8.GC_HEAP_EXTERNAL_PROLOGUE ×2 4.8; V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL ×2 3.7; V8.GC_MC_MARK ×2 3.2; Document::updateStyleInvalidationIfNeeded ×2 2.8; Document::rebuildLayoutTree ×2 2.7
- **layout** 6,914 ms: LocalFrameView::performLayout ×87 3,915.1; InlineNode::ShapeTextIncludingFirstLine ×171116 2,319.7; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×1 517.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×4967 135.4; layout (self) ×87 15.9; V8.GC_MC_INCREMENTAL ×5057 5.4; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×1 4.6; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×2 0.4; V8.GC_MC_INCREMENTAL_START ×1 0.1; V8.GC_MC_COMPLETE_SWEEPING ×1 0.0; V8.GC_MC_MARK_ROOTS ×1 0.0; V8.GC_MC_INCREMENTAL_EXTERNAL_EPILOGUE ×1 0.0; Major concurrent marking rescheduled ×3 0.0; V8.GC_TIME_TO_SAFEPOINT ×1 0.0
- **paintLC** 5,472 ms: paintLC (self) ×46 5,441.0; CullRectUpdate ×45 16.0; Paint ×90 5.7; Blink.Paint.UpdateTime ×46 5.4; PaintArtifactCompositor::Update ×46 2.4; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×40 1.1; Layerize ×46 0.2; ScrollTree::SetScrollOffset ×90 0.1; V8.GC_MC_INCREMENTAL ×40 0.1; PaintController::commitNewDisplayItems ×44 0.1; Blink.CompositingCommit.UpdateTime ×46 0.1; LocalFrameView::pushPaintArtifactToCompositor ×46 0.1; LocalFrameView::ScheduleAnimation ×4 0.0; auto cc::LayerTreeHost::SetNeedsCommit(bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const ×5 0.0
- **animate** 2,244 ms: PageAnimator::serviceScriptedAnimations ×46 1,577.4; AnimationTimeline::serviceAnimations ×485864 616.1; LocalFrameView::ScheduleAnimation ×43004 48.3; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×83 1.4; animate (self) ×46 0.5; V8.GC_MC_INCREMENTAL ×85 0.3; Blink.Animate.UpdateTime ×46 0.3; EventDispatch ×2 0.1; EventDispatcher::dispatchEvent ×2 0.0; AsyncTask Run ×2 0.0; AsyncTask Scheduled ×2 0.0; EventDispatcher::dispatch ×2 0.0
- **compinputs** 1,733 ms: Blink.CompositingInputs.UpdateTime ×90 1,733.0; compinputs (self) ×90 0.2; LayoutView::commitPendingSelection ×66 0.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×2 0.1; V8.GC_MC_INCREMENTAL ×2 0.0
- **UL-other** 1,472 ms: UL-other (self) ×46 1,249.8; LocalFrameView::ScheduleAnimation ×111125 118.6; LocalFrameView::UpdateStyleAndLayout ×89 87.7; SelectorStats ×88 8.0; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×115 4.9; Blink.Layout.UpdateTime ×87 1.1; Blink.Style.UpdateTime ×88 0.6; LocalFrameView::layout ×87 0.3; LocalFrameView::performPostLayoutTasks ×87 0.3; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×89 0.3; LocalFrameView::DidFinishLifecycleUpdate ×46 0.2; LocalFrameView::updateStyleAndLayoutIfNeededRecursive ×89 0.2; LocalFrameView::NotifyResizeObservers ×46 0.1; PrePaint ×46 0.1
- **prepaint** 200 ms: Blink.PrePaint.UpdateTime ×90 196.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×14 3.0; prepaint (self) ×90 0.2; V8.GC_MC_INCREMENTAL ×14 0.0
- **hover** 37 ms: LocalFrameView::UpdateStyleAndLayout ×44 22.3; HitTest ×44 6.5; SelectorStats ×44 5.4; hover (self) ×44 1.5; LayoutView::HitTest ×44 0.4; Blink.Style.UpdateTime ×44 0.3; LocalFrameView::updateStyleAndLayoutIfNeededRecursive ×44 0.1; PrePaint ×44 0.1; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×44 0.1; RootScrollerController::PerformRootScrollerSelection ×32 0.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1 0.0; V8.GC_MC_INCREMENTAL ×1 0.0
- **frame-other** 17 ms: HitTest ×40 12.8; Commit ×46 1.9; MainFrameAborted ×43 0.7; frame-other (self) ×46 0.6; LayerTreeHost::WaitForCommitCompletion ×46 0.3; OverlayInterstitialAdDetector::MaybeFireDetection ×20 0.1; StickyAdDetector::MaybeFireDetection ×20 0.1; LocalFrameView::RunAccessibilitySteps ×46 0.1; AnimationHost::TickAnimations ×44 0.1; Blink.IntersectionObservation.UpdateTime ×46 0.1; LayerTreeHost::ApplyCompositorChanges ×46 0.1; Blink.Accessibility.UpdateTime ×46 0.1; LocalFrameView::UpdateViewportIntersectionsForSubtree ×46 0.1; LayerTreeHost::DoUpdateLayers ×3 0.0
- **task** 14 ms: RunTask ×354 12.7; TimerBase::run ×38 1.0; EventDispatch ×3 0.0; AsyncTask Run ×3 0.0; EventDispatcher::dispatchEvent ×3 0.0; EventDispatcher::dispatch ×3 0.0

### token 4 — passes by elementCount (n, sum ms, mean ms; mean children self ms per pass)

- ec 3089: n 12, sum 2,611, mean 217.6: Document::recalcStyle ×1.0 135.31; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×0.1 41.75; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×259.2 17.41; Document::updateStyle ×1.0 5.63; AnimationTimeline::serviceAnimations ×4178.1 5.15; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 5.02; V8.GC_MARK_COMPACTOR ×0.1 2.33; V8.GC_MC_INCREMENTAL ×263.5 0.29; V8.GC_HEAP_EXTERNAL_PROLOGUE ×0.1 0.22; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×0.1 0.18 | inst {"AnimationTimeline::serviceAnimations": 6688.4, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 4.3, "InvalidateLayout": 2.0, "ClearStringTableJob started": 0.5, "Document::updateActiveStyle": 0.3, "V8.GC_MC_INCREMENTAL": 0.1}
- ec 1553: n 11, sum 2,521, mean 229.2: Document::recalcStyle ×1.0 210.45; Document::updateStyle ×1.0 6.84; AnimationTimeline::serviceAnimations ×4710.4 5.74; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×84.5 1.44; V8.GC_MC_INCREMENTAL ×85.4 0.12; LocalFrameView::ScheduleAnimation ×56.0 0.06; Document::rebuildLayoutTree ×0.1 0.06; Document::updateActiveStyle ×0.7 0.0 | inst {"AnimationTimeline::serviceAnimations": 7144.0, "LocalFrameView::ScheduleAnimation|Add": 13.9, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.9, "Document::updateActiveStyle": 0.3}
- ec 784: n 12, sum 1,703, mean 141.9: Document::recalcStyle ×1.0 121.53; AnimationTimeline::serviceAnimations ×4860.0 6.12; Document::updateStyle ×1.0 5.44; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×245.8 4.36; V8.GC_MC_INCREMENTAL ×247.8 0.25; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6006.5, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.0, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.2}
- ec 126: n 12, sum 1,577, mean 131.4: Document::recalcStyle ×1.0 112.52; AnimationTimeline::serviceAnimations ×4696.2 5.97; Document::updateStyle ×1.0 5.26; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×179.9 3.19; V8.GC_MC_INCREMENTAL ×182.4 0.21; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 6170.3, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.5, "InvalidateLayout": 2.0}
- ec 2323: n 10, sum 1,048, mean 104.8: Document::recalcStyle ×1.0 86.63; AnimationTimeline::serviceAnimations ×4340.7 5.57; Document::updateStyle ×1.0 5.35; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×143.9 2.92; V8.GC_MC_INCREMENTAL ×145.6 0.17; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6525.8, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.8, "Document::updateActiveStyle": 0.2, "V8.GC_MC_INCREMENTAL": 0.1}
- ec 50892: n 1, sum 925, mean 924.8: Document::recalcStyle ×1.0 768.83; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×1.0 76.29; V8.GC_MARK_COMPACTOR ×1.0 35.14; AnimationTimeline::serviceAnimations ×9139.0 11.58; Document::updateStyle ×1.0 7.75; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×436.0 6.11; V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL ×1.0 3.66; V8.GC_HEAP_EXTERNAL_PROLOGUE ×1.0 2.1; V8.GC_MC_MARK ×1.0 1.49; V8.GC_MC_CLEAR_JOIN_JOB ×1.0 1.01 | inst {"AnimationTimeline::serviceAnimations": 13363.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 8.0, "ClearStringTableJob started": 6.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL": 1.0, "V8.GC_MC_MARK_EMBEDDER_TRACING": 1.0}
- ec 0: n 42, sum 743, mean 17.7: AnimationTimeline::serviceAnimations ×8169.2 10.78; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.01; V8.GC_MC_INCREMENTAL ×1.1 0.0; Document::updateActiveStyle ×0.9 0.0 | inst {"AnimationTimeline::serviceAnimations": 13563.8, "Document::updateActiveStyle": 0.1, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.0, "AnimationFrame::Presentation": 0.0}
- ec 6919: n 12, sum 719, mean 59.9: Document::recalcStyle ×1.0 44.36; Document::updateStyle ×1.0 5.24; AnimationTimeline::serviceAnimations ×4106.5 4.99; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×62.4 1.14; V8.GC_MC_INCREMENTAL ×62.8 0.09; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6760.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.3, "Document::updateActiveStyle": 0.2}
- ec 780: n 12, sum 519, mean 43.2: Document::recalcStyle ×1.0 27.45; Document::updateStyle ×1.0 5.46; AnimationTimeline::serviceAnimations ×4266.2 5.21; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×48.3 1.04; V8.GC_MC_INCREMENTAL ×49.3 0.06; Document::updateActiveStyle ×0.9 0.0 | inst {"AnimationTimeline::serviceAnimations": 6600.2, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.0, "Document::updateActiveStyle": 0.1}
- ec 2326: n 1, sum 244, mean 243.5: Document::recalcStyle ×1.0 232.97; Document::updateStyle ×1.0 5.9; Document::rebuildLayoutTree ×1.0 2.08; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×113.0 1.75; AnimationTimeline::serviceAnimations ×219.0 0.22; V8.GC_MC_INCREMENTAL ×115.0 0.16; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 550.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.0}
- ec 2342: n 1, sum 138, mean 138.4: Document::recalcStyle ×1.0 112.05; AnimationTimeline::serviceAnimations ×8560.0 9.72; Document::updateStyle ×1.0 5.29; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×219.0 4.41; V8.GC_MC_INCREMENTAL ×222.0 0.28; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13173.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 4.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL": 1.0}
- ec 2334: n 1, sum 119, mean 118.8: Document::recalcStyle ×1.0 108.78; Document::updateStyle ×1.0 5.29; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×210.0 4.03; V8.GC_MC_INCREMENTAL ×214.0 0.21; Document::updateActiveStyle ×1.0 0.0 | inst {"V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 5.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL": 1.0}
- ec 863: n 1, sum 87, mean 87.1: Document::recalcStyle ×1.0 79.0; Document::updateStyle ×1.0 4.7; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×99.0 1.49; Document::updateStyleInvalidationIfNeeded ×1.0 1.47; V8.GC_MC_INCREMENTAL ×101.0 0.12; Document::updateActiveStyle ×1.0 0.0 | inst {"InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.0}
- ec 1: n 2, sum 37, mean 18.4: AnimationTimeline::serviceAnimations ×8481.0 11.46; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.05; Document::recalcStyle ×1.0 0.04; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL ×1.0 0.0; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13252.0, "AnimationFrame::Presentation": 1.0}
- ec 39: n 1, sum 29, mean 28.6: Document::recalcStyle ×1.0 21.98; Document::updateStyle ×1.0 5.01; Document::updateStyleInvalidationIfNeeded ×1.0 1.36; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×2.0 0.03; V8.GC_MC_INCREMENTAL ×2.0 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {"InvalidateLayout": 2.0}
- ec 6: n 1, sum 13, mean 12.7: Document::recalcStyle ×1.0 12.45; Document::updateStyle ×1.0 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {}

### token 4 — instants: {"AnimationTimeline::serviceAnimations": 1667670, "Animation": 123435, "LocalFrameView::ScheduleAnimation|Add": 19363, "LocalFrameView::ScheduleAnimation|ScheduleServiceOnNextFrame": 11881, "InlineNode::ShapeTextIncludingFirstLine": 1252, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 270, "InvalidateLayout": 174, "ScrollTree::SetScrollOffset": 94, "SetLayerTreeId": 90, "ScheduleStyleRecalculation": 88, "BeginCommitCompositorFrame": 46, "LongTask": 46}

### token 4 — Animation b/e: {"b/running": 9545, "e/": 9232}; names: [('|e', 9232), ('--saved-N-N|b', 9228), ('--fc-ks-N-N|b', 144), ('--fc-vs-N-N|b', 144), ('--fc-v-N|b', 12), ('--fc-k-N|b', 12), ('native-handshake|b', 2), ('--saved-token-N|b', 1), ('--head-fvs|b', 1), ('--head-input-epoch|b', 1)]

### token 4 — head frame: 5,054 ms at 25,542 ms; phases {"frame-other": 0.2, "animate": 52.58, "hover": 0.96, "style": 1187.33, "compinputs": 967.01, "prepaint": 43.26, "UL-other": 41.04, "layout": 2532.16, "paintLC": 229.5}; passes [(0, 18.98), (2326, 243.53), (50892, 924.83)]; layouts [(2374, 34.58), (101162, 2497.58)]
  top: {"frame-other": [["Commit", 0.11], ["HitTest", 0.04], ["LayerTreeHost::DoUpdateLayers", 0.02], ["frame-other (self)", 0.02], ["OverlayInterstitialAdDetector::MaybeFireDetection", 0.01], ["ProxyMain::BeginMainFrame::commit", 0.01]], "animate": [["PageAnimator::serviceScriptedAnimations", 36.58], ["AnimationTimeline::serviceAnimations", 15.17], ["LocalFrameView::ScheduleAnimation", 0.77], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.03], ["animate (self)", 0.01], ["Blink.Animate.UpdateTime", 0.01]], "hover": [["LocalFrameView::UpdateStyleAndLayout", 0.64], ["HitTest", 0.15], ["SelectorStats", 0.11], ["hover (self)", 0.03], ["Blink.Style.UpdateTime", 0.01], ["LayoutView::HitTest", 0.01]], "style": [["Document::recalcStyle", 1001.8], ["V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE", 76.29], ["V8.GC_MARK_COMPACTOR", 35.14], ["AnimationTimeline::serviceAnimations", 23.25], ["style (self)", 16.98], ["Document::updateStyle", 13.66]], "compinputs": [["Blink.CompositingInputs.UpdateTime", 966.99], ["compinputs (self)", 0.02], ["LayoutView::commitPendingSelection", 0.0]], "prepaint": [["Blink.PrePaint.UpdateTime", 40.51], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 2.74], ["V8.GC_MC_INCREMENTAL", 0.01], ["prepaint (self)", 0.0]], "UL-other": [["UL-other (self)", 30.24], ["LocalFrameView::UpdateStyleAndLayout", 5.63], ["LocalFrameView::ScheduleAnimation", 4.58], ["SelectorStats", 0.32], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.15], ["Blink.Layout.UpdateTime", 0.05]], "layout": [["InlineNode::ShapeTextIncludingFirstLine", 1027.06], ["LocalFrameView::performLayout", 883.98], ["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 517.65], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 95.45], ["V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE", 4.59], ["V8.GC_MC_INCREMENTAL", 1.51]], "paintLC": [["paintLC (self)", 216.09], ["CullRectUpdate", 10.82], ["Blink.Paint.UpdateTime", 1.89], ["Paint", 0.41], ["PaintArtifactCompositor::Update", 0.23], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.03]]}

### token 4 — frames

| # | t | dur | passes ec:ms | layouts dirty:ms | style | layout | paintLC | animate | compinputs | UL-other | prepaint | task | hover | frame-other | sa X | anim b/e |
|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 271 | 474 | 0:19 126:113 6919:63 | 339:58 6960:50 | 194 | 109 | 85 | 50 | 3 | 28 | 3 | 0 | 1 | 1 | 26315 | 26/0 |
| 1 | 748 | 441 | 0:18 780:34 3089:148 | 2344:22 9266:58 | 201 | 80 | 56 | 48 | 23 | 28 | 4 | 0 | 1 | 0 | 26493 | 0/0 |
| 2 | 1,190 | 869 | 0:14 784:115 1553:237 | 2359:67 1600:34 | 366 | 101 | 297 | 51 | 18 | 32 | 2 | 0 | 1 | 1 | 27910 | 769/769 |
| 3 | 2,061 | 617 | 0:16 2334:119 126:136 | 6944:47 339:59 | 271 | 105 | 140 | 48 | 14 | 34 | 3 | 0 | 1 | 0 | 29344 | 27/0 |
| 4 | 2,681 | 329 | 0:18 6919:53 780:51 | 6960:54 2344:27 | 122 | 80 | 39 | 49 | 8 | 25 | 4 | 0 | 1 | 0 | 26006 | 0/0 |
| 5 | 3,011 | 703 | 0:20 3089:142 784:149 | 9266:62 2359:70 | 311 | 132 | 126 | 46 | 47 | 35 | 5 | 0 | 1 | 1 | 28537 | 0/0 |
| 6 | 3,716 | 726 | 0:19 1553:214 2323:104 | 1600:32 6943:48 | 337 | 80 | 205 | 50 | 15 | 34 | 3 | 0 | 1 | 0 | 28088 | 769/769 |
| 7 | 4,444 | 496 | 0:17 126:118 6919:68 | 339:60 6960:58 | 203 | 118 | 86 | 51 | 4 | 29 | 3 | 0 | 1 | 1 | 26295 | 26/0 |
| 8 | 4,944 | 457 | 0:18 780:32 3089:151 | 2344:27 9266:62 | 201 | 89 | 59 | 50 | 24 | 28 | 6 | 0 | 1 | 0 | 26111 | 0/0 |
| 9 | 5,401 | 897 | 0:17 784:125 1553:237 | 2359:70 1600:32 | 379 | 101 | 304 | 55 | 17 | 36 | 2 | 0 | 1 | 1 | 28355 | 769/769 |
| 10 | 6,300 | 591 | 0:16 2323:91 126:136 | 6943:52 339:59 | 243 | 111 | 145 | 41 | 14 | 32 | 3 | 0 | 1 | 0 | 28118 | 26/0 |
| 11 | 6,894 | 332 | 0:18 6919:50 780:52 | 6960:55 2344:28 | 120 | 83 | 41 | 47 | 9 | 28 | 4 | 0 | 1 | 0 | 26762 | 0/0 |
| 12 | 7,227 | 715 | 0:16 3089:144 784:143 | 9266:71 2359:72 | 304 | 143 | 127 | 46 | 50 | 37 | 6 | 0 | 1 | 1 | 27814 | 0/0 |
| 13 | 7,944 | 765 | 0:18 1553:216 2323:128 | 1600:32 6943:49 | 362 | 81 | 215 | 51 | 14 | 37 | 4 | 0 | 1 | 0 | 28710 | 769/769 |
| 14 | 8,711 | 498 | 0:19 126:124 6919:69 | 339:60 6960:54 | 212 | 114 | 85 | 52 | 4 | 27 | 3 | 0 | 1 | 1 | 26492 | 26/0 |
| 15 | 9,212 | 483 | 0:19 780:35 3089:169 | 2344:26 9266:67 | 222 | 93 | 58 | 51 | 23 | 30 | 5 | 0 | 1 | 0 | 26738 | 0/0 |
| 16 | 9,696 | 922 | 0:16 784:136 1553:241 | 2359:72 1600:31 | 393 | 103 | 316 | 52 | 18 | 36 | 2 | 0 | 1 | 1 | 28816 | 769/769 |
| 17 | 10,621 | 645 | 0:20 2323:107 126:167 | 6943:54 339:60 | 294 | 114 | 137 | 50 | 13 | 32 | 3 | 0 | 1 | 0 | 30095 | 26/0 |
| 18 | 11,269 | 323 | 0:16 6919:52 780:51 | 6960:58 2344:25 | 120 | 83 | 41 | 41 | 8 | 26 | 4 | 0 | 1 | 0 | 25884 | 0/0 |
| 19 | 11,593 | 766 | 0:19 3089:229 784:119 | 9266:61 2359:73 | 366 | 135 | 131 | 48 | 46 | 33 | 5 | 0 | 1 | 1 | 28184 | 0/0 |
| 20 | 12,362 | 712 | 0:17 1553:236 2323:109 | 1600:36 6943:52 | 361 | 88 | 151 | 48 | 16 | 42 | 3 | 0 | 1 | 0 | 29959 | 769/769 |
| 21 | 13,081 | 465 | 0:18 126:107 6919:65 | 339:61 6960:49 | 190 | 110 | 81 | 50 | 4 | 26 | 3 | 0 | 1 | 1 | 27233 | 26/0 |
| 22 | 13,550 | 1,126 | 0:17 780:30 3089:824 | 2344:23 9266:67 | 870 | 90 | 57 | 49 | 22 | 30 | 5 | 0 | 1 | 1 | 27103 | 0/0 |
| 23 | 14,677 | 788 | 0:17 784:126 1553:231 | 2359:71 1600:31 | 375 | 102 | 197 | 56 | 17 | 38 | 2 | 0 | 1 | 0 | 28416 | 769/769 |
| 24 | 15,467 | 597 | 0:17 2323:92 126:138 | 6943:50 339:61 | 247 | 111 | 139 | 50 | 13 | 32 | 3 | 0 | 1 | 1 | 29161 | 26/0 |
| 25 | 16,067 | 319 | 0:15 6919:51 780:54 | 6960:52 2344:22 | 121 | 75 | 41 | 39 | 9 | 29 | 4 | 0 | 1 | 0 | 26158 | 0/0 |
| 26 | 16,387 | 725 | 0:18 3089:153 784:162 | 9266:63 2359:71 | 332 | 134 | 123 | 49 | 45 | 35 | 4 | 0 | 1 | 1 | 28179 | 0/0 |
| 27 | 17,114 | 706 | 0:19 1553:218 2323:115 | 1600:33 6943:56 | 352 | 88 | 159 | 52 | 15 | 36 | 3 | 0 | 1 | 0 | 28710 | 769/769 |
| 28 | 17,821 | 502 | 0:19 126:129 6919:68 | 339:64 6960:53 | 216 | 117 | 85 | 51 | 3 | 24 | 3 | 0 | 1 | 1 | 26083 | 26/0 |
| 29 | 18,327 | 458 | 0:16 780:33 3089:165 | 2344:24 9266:60 | 214 | 84 | 58 | 45 | 23 | 30 | 4 | 0 | 1 | 0 | 25091 | 0/0 |
| 30 | 18,786 | 810 | 0:18 784:137 1553:229 | 2359:74 1600:31 | 384 | 105 | 208 | 57 | 17 | 34 | 3 | 0 | 1 | 1 | 28334 | 769/769 |
| 31 | 19,598 | 603 | 0:19 2323:89 126:140 | 6943:49 339:66 | 248 | 115 | 142 | 48 | 14 | 33 | 3 | 0 | 1 | 0 | 29897 | 26/0 |
| 32 | 20,204 | 317 | 0:18 6919:49 780:50 | 6960:51 2344:22 | 117 | 73 | 40 | 47 | 8 | 28 | 4 | 0 | 1 | 0 | 26231 | 0/0 |
| 33 | 20,523 | 699 | 0:18 3089:140 784:152 | 9266:68 2359:66 | 310 | 134 | 122 | 47 | 44 | 36 | 4 | 0 | 1 | 1 | 28774 | 0/0 |
| 34 | 21,224 | 710 | 0:14 1553:217 2323:112 | 1600:31 6943:51 | 343 | 82 | 181 | 47 | 15 | 38 | 3 | 0 | 1 | 0 | 27304 | 769/769 |
| 35 | 21,936 | 502 | 0:18 126:120 6919:66 | 339:65 6960:61 | 204 | 126 | 86 | 51 | 3 | 27 | 3 | 0 | 1 | 1 | 25668 | 26/0 |
| 36 | 22,440 | 477 | 0:20 780:35 3089:169 | 2344:27 9266:62 | 224 | 89 | 59 | 45 | 22 | 32 | 5 | 0 | 1 | 0 | 26369 | 0/0 |
| 37 | 22,919 | 833 | 0:18 784:131 1553:245 | 2359:72 1600:31 | 394 | 103 | 221 | 53 | 18 | 40 | 2 | 0 | 1 | 1 | 28626 | 769/769 |
| 38 | 23,754 | 623 | 0:17 2323:101 126:149 | 6943:56 339:57 | 266 | 112 | 140 | 52 | 14 | 35 | 3 | 0 | 1 | 0 | 28413 | 26/0 |
| 39 | 24,380 | 369 | 0:20 6919:66 780:60 | 6960:64 2344:29 | 145 | 93 | 41 | 47 | 9 | 28 | 4 | 0 | 1 | 0 | 27253 | 0/0 |
| 40 | 24,750 | 791 | 0:17 3089:178 784:208 | 9266:68 2359:72 | 403 | 139 | 113 | 46 | 46 | 35 | 5 | 0 | 1 | 1 | 27689 | 0/0 |
| 41 | 25,542 | 5,054 | 0:19 2326:244 50892:925 | 2374:35 101162:2498 | 1187 | 2532 | 230 | 53 | 967 | 41 | 43 | 0 | 1 | 0 | 29500 | 770/771 |
| 42 | 30,599 | 135 | 1:21 6:13 |  | 33 | 0 | 22 | 49 | 0 | 28 | 1 | 0 | 2 | 0 | 18732 | 0/1 |
| 43 | 30,735 | 141 | 39:29 | 7:13 | 29 | 13 | 24 | 45 | 1 | 29 | 1 | 0 | 0 | 0 | 9361 | 1/0 |
| 44 | 30,876 | 117 | 1:16 |  | 16 | 0 | 22 | 48 | 0 | 28 | 1 | 0 | 1 | 0 | 17057 | 0/1 |
| 45 | 30,994 | 506 | 863:87 2342:147 | 1571:95 6944:54 | 234 | 149 | 35 | 42 | 14 | 29 | 3 | 0 | 0 | 0 | 17909 | 2/0 |

## token 5 — top names by self time within each phase (name, count, self ms)

- **style** 15,687 ms: Document::recalcStyle ×90 10,302.6; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×2 2,195.2; AnimationTimeline::serviceAnimations ×749829 975.9; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×13275 733.3; style (self) ×132 665.7; Document::updateStyle ×132 441.4; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×2 198.7; V8.GC_MARK_COMPACTOR ×2 116.4; V8.GC_MC_INCREMENTAL ×13402 16.5; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×2 13.3; V8.GC_MC_MARK ×2 6.1; V8.GC_HEAP_EXTERNAL_PROLOGUE ×2 4.7; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×4 4.5; Document::updateStyleInvalidationIfNeeded ×2 4.0
- **layout** 6,699 ms: LocalFrameView::performLayout ×87 4,219.2; InlineNode::ShapeTextIncludingFirstLine ×181250 2,410.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×5185 48.1; layout (self) ×87 15.7; V8.GC_MC_INCREMENTAL ×5297 5.8
- **paintLC** 5,197 ms: paintLC (self) ×46 5,164.7; CullRectUpdate ×46 15.4; Paint ×90 6.6; Blink.Paint.UpdateTime ×46 5.8; PaintArtifactCompositor::Update ×46 2.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×39 0.9; Layerize ×46 0.2; ScrollTree::SetScrollOffset ×86 0.1; PaintController::commitNewDisplayItems ×44 0.1; V8.GC_MC_INCREMENTAL ×39 0.1; Blink.CompositingCommit.UpdateTime ×46 0.1; LocalFrameView::pushPaintArtifactToCompositor ×46 0.1; LocalFrameView::ScheduleAnimation ×4 0.1; auto cc::LayerTreeHost::SetNeedsCommit(bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const ×5 0.0
- **animate** 2,264 ms: PageAnimator::serviceScriptedAnimations ×46 1,581.6; AnimationTimeline::serviceAnimations ×493348 630.9; LocalFrameView::ScheduleAnimation ×43340 49.5; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×77 1.3; animate (self) ×46 0.5; Blink.Animate.UpdateTime ×46 0.3; V8.GC_MC_INCREMENTAL ×77 0.2; EventDispatch ×2 0.0; EventDispatcher::dispatch ×2 0.0; EventDispatcher::dispatchEvent ×2 0.0; AsyncTask Scheduled ×2 0.0; AsyncTask Run ×2 0.0
- **compinputs** 1,740 ms: Blink.CompositingInputs.UpdateTime ×90 1,739.5; compinputs (self) ×90 0.2; LayoutView::commitPendingSelection ×58 0.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×3 0.1; V8.GC_MC_INCREMENTAL ×3 0.0
- **UL-other** 1,467 ms: UL-other (self) ×46 1,242.7; LocalFrameView::ScheduleAnimation ×112279 120.5; LocalFrameView::UpdateStyleAndLayout ×89 88.4; SelectorStats ×88 8.2; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×118 3.4; Blink.Layout.UpdateTime ×87 1.1; Blink.Style.UpdateTime ×88 0.5; LocalFrameView::layout ×87 0.3; LocalFrameView::performPostLayoutTasks ×87 0.3; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×89 0.3; LocalFrameView::DidFinishLifecycleUpdate ×46 0.2; LocalFrameView::updateStyleAndLayoutIfNeededRecursive ×89 0.2; V8.GC_MC_INCREMENTAL ×119 0.2; ResourceLoadPriorityOptimizer::UpdateImagePrioritiesAndSpeculativeDecodes ×73 0.1
- **prepaint** 210 ms: Blink.PrePaint.UpdateTime ×90 209.0; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×13 0.3; prepaint (self) ×90 0.2; V8.GC_MC_INCREMENTAL ×13 0.0
- **task** 180 ms: V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×1 83.9; V8.GC_MARK_COMPACTOR ×1 51.8; RunTask ×363 39.9; V8.GC_HEAP_EXTERNAL_PROLOGUE ×1 1.9; TimerBase::run ×37 1.1; V8.GC_MC_MARK ×1 0.6; V8.GC_MC_CLEAR_SWEEP_EXTERNAL_POINTER_TABLE ×1 0.2; V8.GC_MC_CLEAR_JOIN_JOB ×1 0.1; V8.GC_MC_EVACUATE_UPDATE_POINTERS_POINTER_TABLES ×1 0.1; V8.GC_MC_MARK_ROOTS ×2 0.1; V8.GC_MC_EVACUATE_UPDATE_POINTERS_TO_NEW_ROOTS ×1 0.0; MajorGC ×1 0.0; V8.GC_MC_CLEAR_SWEEP_JS_DISPATCH_TABLE ×1 0.0; V8.GC_MC_CLEAR_SWEEP_TRUSTED_POINTER_TABLE ×1 0.0
- **hover** 39 ms: LocalFrameView::UpdateStyleAndLayout ×44 24.0; HitTest ×44 7.1; SelectorStats ×44 5.5; hover (self) ×44 1.6; LayoutView::HitTest ×44 0.4; Blink.Style.UpdateTime ×44 0.3; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×44 0.1; LocalFrameView::updateStyleAndLayoutIfNeededRecursive ×44 0.1; PrePaint ×44 0.1; RootScrollerController::PerformRootScrollerSelection ×34 0.0
- **frame-other** 19 ms: HitTest ×44 14.6; Commit ×46 2.0; MainFrameAborted ×43 0.8; frame-other (self) ×46 0.6; LayerTreeHost::WaitForCommitCompletion ×46 0.2; OverlayInterstitialAdDetector::MaybeFireDetection ×22 0.2; StickyAdDetector::MaybeFireDetection ×22 0.1; AnimationHost::TickAnimations ×46 0.1; LocalFrameView::RunAccessibilitySteps ×46 0.1; LayerTreeHost::ApplyCompositorChanges ×46 0.1; Blink.IntersectionObservation.UpdateTime ×46 0.1; Blink.Accessibility.UpdateTime ×46 0.1; LocalFrameView::UpdateViewportIntersectionsForSubtree ×46 0.1; LayerTreeHost::DoUpdateLayers ×3 0.0

### token 5 — passes by elementCount (n, sum ms, mean ms; mean children self ms per pass)

- ec 3089: n 12, sum 3,945, mean 328.8: Document::recalcStyle ×1.0 147.32; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×0.1 121.04; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×243.3 29.48; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 8.37; Document::updateStyle ×1.0 5.6; V8.GC_MARK_COMPACTOR ×0.1 5.58; AnimationTimeline::serviceAnimations ×4272.8 5.26; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×0.1 0.65; V8.GC_MC_MARK ×0.1 0.39; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×0.2 0.3 | inst {"AnimationTimeline::serviceAnimations": 6593.8, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.8, "InvalidateLayout": 2.0, "ClearStringTableJob started": 0.4, "Document::updateActiveStyle": 0.2, "Major concurrent marking rescheduled": 0.2}
- ec 1553: n 11, sum 2,543, mean 231.2: Document::recalcStyle ×1.0 213.98; AnimationTimeline::serviceAnimations ×4774.7 5.9; Document::updateStyle ×1.0 5.05; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×86.9 1.5; V8.GC_MC_INCREMENTAL ×87.3 0.12; Document::rebuildLayoutTree ×0.1 0.08; LocalFrameView::ScheduleAnimation ×54.1 0.06; Document::updateActiveStyle ×0.6 0.0 | inst {"AnimationTimeline::serviceAnimations": 7079.6, "LocalFrameView::ScheduleAnimation|Add": 15.8, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.4, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.4}
- ec 126: n 12, sum 1,926, mean 160.5: Document::recalcStyle ×1.0 129.13; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 8.18; AnimationTimeline::serviceAnimations ×4728.7 5.94; Document::updateStyle ×1.0 4.83; V8.GC_MARK_COMPACTOR ×0.1 4.12; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×194.4 3.72; V8.GC_MC_INCREMENTAL ×196.8 0.24; V8.GC_HEAP_EXTERNAL_PROLOGUE ×0.1 0.2; V8.GC_MC_MARK ×0.1 0.12; V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL ×0.1 0.02 | inst {"AnimationTimeline::serviceAnimations": 6137.8, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.3, "InvalidateLayout": 2.0, "ClearStringTableJob started": 0.7, "Document::updateActiveStyle": 0.2, "Major concurrent marking rescheduled": 0.1}
- ec 784: n 12, sum 1,762, mean 146.8: Document::recalcStyle ×1.0 127.1; AnimationTimeline::serviceAnimations ×4898.4 6.18; Document::updateStyle ×1.0 5.46; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×225.7 3.84; V8.GC_MC_INCREMENTAL ×227.2 0.24; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 5904.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.5, "Document::updateActiveStyle": 0.2}
- ec 50892: n 1, sum 1,659, mean 1658.7: V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×1.0 742.76; Document::recalcStyle ×1.0 673.03; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1157.0 209.49; AnimationTimeline::serviceAnimations ×8788.0 11.53; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×1.0 5.44; Document::updateStyle ×1.0 5.4; V8.GC_MC_INCREMENTAL ×1164.0 1.68; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×2.0 0.86; V8.GC_MC_INCREMENTAL_START ×1.0 0.12; V8.GC_MC_MARK_ROOTS ×1.0 0.03 | inst {"AnimationTimeline::serviceAnimations": 12945.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 7.0, "Layer:deleted": 3.0, "InvalidateLayout": 2.0, "UpdateCounters": 1.0}
- ec 2323: n 10, sum 1,118, mean 111.8: Document::recalcStyle ×1.0 93.53; AnimationTimeline::serviceAnimations ×4326.1 5.53; Document::updateStyle ×1.0 5.28; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×148.5 3.06; V8.GC_MC_INCREMENTAL ×150.2 0.18; Document::updateActiveStyle ×0.9 0.0 | inst {"AnimationTimeline::serviceAnimations": 6540.4, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.8, "V8.GC_MC_INCREMENTAL": 0.1, "Document::updateActiveStyle": 0.1}
- ec 0: n 42, sum 780, mean 18.6: AnimationTimeline::serviceAnimations ×8325.2 11.35; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.0; V8.GC_MC_INCREMENTAL ×1.0 0.0; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13352.8, "Document::updateActiveStyle": 0.0, "AnimationFrame::Presentation": 0.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.0}
- ec 6919: n 12, sum 737, mean 61.4: Document::recalcStyle ×1.0 46.66; AnimationTimeline::serviceAnimations ×4144.8 5.0; Document::updateStyle ×1.0 4.63; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×58.8 1.05; V8.GC_MC_INCREMENTAL ×59.2 0.09; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6721.8, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.5, "Document::updateActiveStyle": 0.2}
- ec 780: n 12, sum 527, mean 43.9: Document::recalcStyle ×1.0 28.71; AnimationTimeline::serviceAnimations ×4345.3 5.3; Document::updateStyle ×1.0 4.64; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×45.1 1.03; V8.GC_MC_INCREMENTAL ×45.5 0.06; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6457.1, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.4, "Document::updateActiveStyle": 0.2}
- ec 2326: n 1, sum 246, mean 246.5: Document::recalcStyle ×1.0 239.61; Document::updateStyle ×1.0 4.79; Document::rebuildLayoutTree ×1.0 1.29; AnimationTimeline::serviceAnimations ×224.0 0.24; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 545.0, "InvalidateLayout": 2.0}
- ec 2342: n 1, sum 147, mean 146.9: Document::recalcStyle ×1.0 121.11; AnimationTimeline::serviceAnimations ×8480.0 9.89; Document::updateStyle ×1.0 5.33; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×204.0 3.63; V8.GC_MC_INCREMENTAL ×208.0 0.24; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13253.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 4.0, "InvalidateLayout": 2.0}
- ec 2334: n 1, sum 131, mean 130.7: Document::recalcStyle ×1.0 121.38; Document::updateStyle ×1.0 5.22; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×224.0 3.56; V8.GC_MC_INCREMENTAL ×228.0 0.25 | inst {"V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 4.0, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 1.0}
- ec 863: n 1, sum 88, mean 87.7: Document::recalcStyle ×1.0 79.97; Document::updateStyle ×1.0 4.83; Document::updateStyleInvalidationIfNeeded ×1.0 2.64; Document::updateActiveStyle ×1.0 0.0 | inst {"InvalidateLayout": 2.0}
- ec 1: n 2, sum 40, mean 20.1: AnimationTimeline::serviceAnimations ×9107.5 12.64; Document::recalcStyle ×1.0 0.06; Document::updateStyle ×1.0 0.01; Document::updateActiveStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL ×0.5 0.0; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×0.5 0.0 | inst {"AnimationTimeline::serviceAnimations": 12625.5, "AnimationFrame::Presentation": 0.5}
- ec 39: n 1, sum 26, mean 26.5: Document::recalcStyle ×1.0 19.99; Document::updateStyle ×1.0 4.77; Document::updateStyleInvalidationIfNeeded ×1.0 1.37; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.01; V8.GC_MC_INCREMENTAL ×1.0 0.0 | inst {"InvalidateLayout": 2.0, "Document::updateActiveStyle": 1.0}
- ec 6: n 1, sum 12, mean 11.5: Document::recalcStyle ×1.0 11.25; Document::updateStyle ×1.0 0.01 | inst {"Document::updateActiveStyle": 1.0}

### token 5 — instants: {"AnimationTimeline::serviceAnimations": 1641929, "Animation": 123581, "LocalFrameView::ScheduleAnimation|Add": 18503, "LocalFrameView::ScheduleAnimation|ScheduleServiceOnNextFrame": 11491, "InlineNode::ShapeTextIncludingFirstLine": 334, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 243, "InvalidateLayout": 174, "ScrollTree::SetScrollOffset": 98, "SetLayerTreeId": 90, "ScheduleStyleRecalculation": 88, "LongTask": 47, "BeginCommitCompositorFrame": 46}

### token 5 — Animation b/e: {"b/running": 9544, "e/": 9232}; names: [('|e', 9232), ('--saved-N-N|b', 9228), ('--fc-vs-N-N|b', 144), ('--fc-ks-N-N|b', 144), ('--fc-k-N|b', 12), ('--fc-v-N|b', 12), ('native-handshake|b', 2), ('--saved-token-N|b', 1), ('--head-fvs|b', 1)]

### token 5 — head frame: 2,469 ms at 12,286 ms; phases {"frame-other": 0.85, "animate": 43.83, "hover": 0.91, "style": 2062.25, "compinputs": 51.7, "prepaint": 4.57, "UL-other": 37.53, "layout": 137.31, "paintLC": 129.82}; passes [(0, 17.94), (3089, 1901.17), (784, 143.14)]; layouts [(9266, 62.76), (2359, 74.55)]
  top: {"frame-other": [["HitTest", 0.66], ["Commit", 0.1], ["MainFrameAborted", 0.04], ["frame-other (self)", 0.02], ["StickyAdDetector::MaybeFireDetection", 0.01], ["OverlayInterstitialAdDetector::MaybeFireDetection", 0.01]], "animate": [["PageAnimator::serviceScriptedAnimations", 30.9], ["AnimationTimeline::serviceAnimations", 12.15], ["LocalFrameView::ScheduleAnimation", 0.76], ["animate (self)", 0.01], ["Blink.Animate.UpdateTime", 0.01]], "hover": [["LocalFrameView::UpdateStyleAndLayout", 0.6], ["HitTest", 0.13], ["SelectorStats", 0.12], ["hover (self)", 0.03], ["LayoutView::HitTest", 0.01], ["Blink.Style.UpdateTime", 0.01]], "style": [["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 1452.42], ["Document::recalcStyle", 302.21], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 249.0], ["AnimationTimeline::serviceAnimations", 22.89], ["style (self)", 14.99], ["Document::updateStyle", 8.54]], "compinputs": [["Blink.CompositingInputs.UpdateTime", 51.7], ["compinputs (self)", 0.0], ["LayoutView::commitPendingSelection", 0.0]], "prepaint": [["Blink.PrePaint.UpdateTime", 4.57], ["prepaint (self)", 0.0]], "UL-other": [["UL-other (self)", 29.75], ["LocalFrameView::ScheduleAnimation", 6.54], ["LocalFrameView::UpdateStyleAndLayout", 0.82], ["SelectorStats", 0.26], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.07], ["Blink.Layout.UpdateTime", 0.03]], "layout": [["LocalFrameView::performLayout", 70.48], ["InlineNode::ShapeTextIncludingFirstLine", 65.05], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 1.23], ["layout (self)", 0.43], ["V8.GC_MC_INCREMENTAL", 0.12]], "paintLC": [["paintLC (self)", 129.21], ["CullRectUpdate", 0.19], ["Blink.Paint.UpdateTime", 0.15], ["Paint", 0.12], ["PaintArtifactCompositor::Update", 0.1], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.04]]}

### token 5 — frames

| # | t | dur | passes ec:ms | layouts dirty:ms | style | layout | paintLC | animate | compinputs | UL-other | prepaint | task | hover | frame-other | sa X | anim b/e |
|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 282 | 558 | 0:18 126:139 6919:70 | 339:73 8496:77 | 227 | 150 | 87 | 55 | 5 | 29 | 3 | 0 | 1 | 1 | 26930 | 26/0 |
| 1 | 844 | 494 | 0:22 780:40 3089:177 | 2344:28 9266:64 | 239 | 91 | 59 | 45 | 23 | 32 | 5 | 0 | 1 | 0 | 27727 | 0/0 |
| 2 | 1,339 | 850 | 0:17 784:144 1553:242 | 2359:69 1600:31 | 403 | 100 | 232 | 58 | 18 | 35 | 3 | 0 | 1 | 1 | 27969 | 769/769 |
| 3 | 2,190 | 672 | 0:19 2334:131 126:155 | 6944:56 339:67 | 305 | 122 | 143 | 53 | 13 | 32 | 3 | 0 | 1 | 0 | 29589 | 27/0 |
| 4 | 2,865 | 345 | 0:17 6919:52 780:51 | 8496:71 2344:26 | 120 | 97 | 38 | 45 | 9 | 29 | 4 | 0 | 1 | 1 | 26686 | 0/0 |
| 5 | 3,211 | 739 | 0:18 3089:163 784:165 | 9266:65 2359:72 | 346 | 137 | 124 | 46 | 46 | 35 | 5 | 0 | 1 | 0 | 27084 | 0/0 |
| 6 | 3,952 | 740 | 0:19 1553:216 2323:115 | 1600:31 6943:55 | 350 | 86 | 199 | 51 | 15 | 35 | 3 | 0 | 1 | 1 | 28539 | 769/769 |
| 7 | 4,694 | 525 | 0:19 126:122 6919:67 | 339:66 8496:79 | 208 | 145 | 81 | 52 | 5 | 29 | 4 | 0 | 1 | 0 | 26497 | 26/0 |
| 8 | 5,223 | 548 | 0:16 780:33 3089:232 | 2344:27 9266:72 | 282 | 99 | 59 | 50 | 23 | 28 | 5 | 0 | 1 | 1 | 26539 | 0/0 |
| 9 | 5,772 | 850 | 0:19 784:137 1553:239 | 2359:76 1600:31 | 395 | 107 | 237 | 55 | 17 | 36 | 2 | 0 | 1 | 0 | 28326 | 769/769 |
| 10 | 6,624 | 623 | 0:20 2323:93 126:147 | 6943:54 339:69 | 260 | 123 | 141 | 49 | 15 | 30 | 4 | 0 | 1 | 1 | 29621 | 26/0 |
| 11 | 7,251 | 387 | 0:19 6919:53 780:56 | 8496:97 2344:29 | 128 | 126 | 40 | 48 | 11 | 30 | 4 | 0 | 1 | 0 | 26940 | 0/0 |
| 12 | 7,639 | 779 | 0:18 3089:172 784:175 | 9266:69 2359:71 | 366 | 140 | 128 | 52 | 49 | 38 | 6 | 0 | 1 | 1 | 28228 | 0/0 |
| 13 | 8,420 | 774 | 0:19 1553:235 2323:124 | 1600:32 6943:51 | 378 | 83 | 209 | 52 | 15 | 34 | 3 | 0 | 1 | 0 | 28792 | 769/769 |
| 14 | 9,195 | 581 | 0:19 126:160 6919:88 | 339:69 8496:72 | 267 | 142 | 84 | 53 | 5 | 25 | 4 | 0 | 1 | 1 | 26393 | 26/0 |
| 15 | 9,781 | 669 | 0:20 780:49 3089:338 | 2344:29 9266:69 | 407 | 98 | 59 | 49 | 23 | 27 | 5 | 0 | 1 | 0 | 27136 | 0/0 |
| 16 | 10,451 | 771 | 0:16 784:108 1553:248 | 2359:73 1600:34 | 371 | 107 | 186 | 49 | 20 | 33 | 4 | 0 | 1 | 1 | 29263 | 769/769 |
| 17 | 11,231 | 699 | 0:19 2323:134 126:147 | 6943:65 339:89 | 300 | 154 | 139 | 54 | 13 | 34 | 3 | 0 | 1 | 0 | 30688 | 26/0 |
| 18 | 11,938 | 341 | 0:18 6919:50 780:48 | 8496:71 2344:24 | 115 | 96 | 42 | 45 | 8 | 29 | 4 | 0 | 1 | 1 | 26775 | 0/0 |
| 19 | 12,286 | 2,469 | 0:18 3089:1901 784:143 | 9266:63 2359:75 | 2062 | 137 | 130 | 44 | 52 | 38 | 5 | 0 | 1 | 1 | 28641 | 0/0 |
| 20 | 14,757 | 669 | 0:19 1553:212 2323:105 | 1600:32 6943:50 | 336 | 82 | 148 | 48 | 14 | 37 | 3 | 0 | 1 | 0 | 28390 | 769/769 |
| 21 | 15,427 | 521 | 0:17 126:124 6919:65 | 339:73 8496:71 | 206 | 144 | 82 | 53 | 5 | 26 | 3 | 0 | 1 | 1 | 27061 | 26/0 |
| 22 | 15,952 | 437 | 0:19 780:32 3089:146 | 2344:24 9266:58 | 196 | 82 | 59 | 43 | 24 | 28 | 4 | 0 | 1 | 0 | 26561 | 0/0 |
| 23 | 16,390 | 748 | 0:18 784:117 1553:226 | 2359:68 1600:30 | 360 | 98 | 182 | 53 | 18 | 32 | 2 | 0 | 1 | 1 | 28155 | 769/769 |
| 24 | 17,141 | 638 | 0:16 2323:89 126:170 | 6943:48 339:70 | 275 | 118 | 141 | 50 | 14 | 36 | 3 | 0 | 1 | 0 | 28765 | 26/0 |
| 25 | 17,782 | 343 | 0:18 6919:51 780:50 | 8496:72 2344:25 | 118 | 97 | 39 | 46 | 9 | 28 | 4 | 0 | 1 | 0 | 26749 | 0/0 |
| 26 | 18,126 | 729 | 0:16 3089:147 784:162 | 9266:65 2359:71 | 325 | 136 | 126 | 49 | 48 | 38 | 5 | 0 | 1 | 1 | 27569 | 0/0 |
| 27 | 18,857 | 695 | 0:19 1553:218 2323:118 | 1600:31 6943:57 | 355 | 88 | 154 | 47 | 14 | 32 | 3 | 0 | 1 | 0 | 28553 | 769/769 |
| 28 | 19,554 | 541 | 0:20 126:138 6919:72 | 339:71 8496:70 | 230 | 141 | 83 | 50 | 6 | 27 | 3 | 0 | 1 | 1 | 26362 | 26/0 |
| 29 | 20,099 | 474 | 0:18 780:34 3089:175 | 2344:25 9266:67 | 227 | 92 | 58 | 42 | 22 | 29 | 4 | 0 | 1 | 0 | 26820 | 0/0 |
| 30 | 20,574 | 806 | 0:17 784:130 1553:234 | 2359:71 1600:32 | 381 | 103 | 208 | 55 | 17 | 38 | 3 | 0 | 1 | 1 | 28408 | 769/769 |
| 31 | 21,383 | 638 | 0:20 2323:91 126:156 | 6943:56 339:72 | 267 | 128 | 140 | 53 | 13 | 32 | 3 | 0 | 1 | 0 | 30821 | 26/0 |
| 32 | 22,025 | 358 | 0:19 6919:51 780:51 | 8496:76 2344:26 | 120 | 102 | 43 | 47 | 9 | 31 | 4 | 0 | 1 | 1 | 27225 | 0/0 |
| 33 | 22,384 | 751 | 0:20 3089:164 784:160 | 9266:72 2359:70 | 344 | 142 | 128 | 46 | 49 | 36 | 5 | 0 | 1 | 0 | 28588 | 0/0 |
| 34 | 23,137 | 742 | 0:21 1553:216 2323:125 | 1600:32 6943:65 | 362 | 97 | 179 | 52 | 15 | 33 | 3 | 0 | 1 | 1 | 28720 | 769/769 |
| 35 | 23,881 | 565 | 0:18 126:149 6919:71 | 339:71 8496:84 | 238 | 155 | 85 | 49 | 5 | 28 | 4 | 0 | 1 | 0 | 26318 | 26/0 |
| 36 | 24,451 | 549 | 0:19 780:39 3089:200 | 2344:34 9266:91 | 258 | 124 | 59 | 48 | 23 | 30 | 5 | 0 | 1 | 1 | 27816 | 0/0 |
| 37 | 25,000 | 908 | 0:20 784:184 1553:258 | 2359:77 1600:38 | 462 | 115 | 218 | 55 | 17 | 36 | 3 | 0 | 1 | 0 | 29334 | 769/769 |
| 38 | 25,910 | 858 | 0:18 2323:124 126:320 | 6943:68 339:77 | 461 | 144 | 145 | 49 | 18 | 35 | 5 | 0 | 1 | 1 | 29419 | 26/0 |
| 39 | 26,773 | 340 | 0:18 6919:47 780:46 | 8496:65 2344:29 | 111 | 94 | 44 | 47 | 9 | 29 | 5 | 0 | 1 | 0 | 27825 | 0/0 |
| 40 | 27,120 | 706 | 0:18 3089:129 784:137 | 9266:69 2359:88 | 284 | 157 | 125 | 46 | 49 | 38 | 5 | 0 | 1 | 1 | 29354 | 0/0 |
| 41 | 27,835 | 4,983 | 0:23 2326:246 50892:1659 | 2374:33 101162:1709 | 1928 | 1742 | 232 | 50 | 946 | 38 | 46 | 0 | 1 | 0 | 29716 | 770/771 |
| 42 | 32,821 | 126 | 1:22 6:12 |  | 34 | 0 | 18 | 46 | 0 | 26 | 1 | 0 | 1 | 0 | 18964 | 0/1 |
| 43 | 32,949 | 138 | 39:26 | 7:12 | 26 | 12 | 24 | 46 | 0 | 28 | 1 | 0 | 0 | 0 | 9956 | 1/0 |
| 44 | 33,225 | 113 | 1:18 |  | 18 | 0 | 23 | 45 | 0 | 25 | 1 | 0 | 1 | 0 | 19075 | 0/1 |
| 45 | 33,344 | 617 | 863:88 2342:224 | 1571:113 6944:59 | 312 | 172 | 34 | 45 | 16 | 32 | 5 | 0 | 0 | 1 | 19091 | 2/0 |

## token 6 — top names by self time within each phase (name, count, self ms)

- **style** 13,708 ms: Document::recalcStyle ×90 9,798.6; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×2 1,016.9; AnimationTimeline::serviceAnimations ×748014 990.1; style (self) ×132 666.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×12157 553.0; Document::updateStyle ×132 406.3; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×2 175.5; V8.GC_MARK_COMPACTOR ×2 50.0; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×2 15.0; V8.GC_MC_INCREMENTAL ×12251 14.9; V8.GC_MC_MARK ×2 6.7; V8.GC_HEAP_EXTERNAL_PROLOGUE ×2 3.5; Document::updateStyleInvalidationIfNeeded ×2 2.7; Document::rebuildLayoutTree ×2 2.6
- **layout** 8,083 ms: LocalFrameView::performLayout ×87 4,361.7; InlineNode::ShapeTextIncludingFirstLine ×190699 2,384.9; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×1 1,205.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×5095 99.2; layout (self) ×87 16.1; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×1 8.9; V8.GC_MC_INCREMENTAL ×5217 5.7; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×2 0.5; V8.GC_MC_INCREMENTAL_START ×1 0.1; V8.GC_MC_MARK_ROOTS ×1 0.0; V8.GC_MC_INCREMENTAL_EXTERNAL_EPILOGUE ×1 0.0; V8.GC_MC_COMPLETE_SWEEPING ×1 0.0; V8.GC_TIME_TO_SAFEPOINT ×1 0.0; Major concurrent marking rescheduled ×1 0.0
- **paintLC** 4,938 ms: paintLC (self) ×46 4,906.1; CullRectUpdate ×46 15.2; Blink.Paint.UpdateTime ×46 6.5; Paint ×90 6.2; PaintArtifactCompositor::Update ×46 2.9; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×38 0.9; ScrollTree::SetScrollOffset ×91 0.2; Layerize ×46 0.2; V8.GC_MC_INCREMENTAL ×38 0.1; PaintController::commitNewDisplayItems ×44 0.1; LocalFrameView::pushPaintArtifactToCompositor ×46 0.1; Blink.CompositingCommit.UpdateTime ×46 0.1; LocalFrameView::ScheduleAnimation ×4 0.0; auto cc::LayerTreeHost::SetNeedsCommit(bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const ×6 0.0
- **animate** 2,306 ms: PageAnimator::serviceScriptedAnimations ×46 1,597.0; AnimationTimeline::serviceAnimations ×485351 636.5; LocalFrameView::ScheduleAnimation ×43670 63.3; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×82 8.2; animate (self) ×46 0.5; Blink.Animate.UpdateTime ×46 0.3; V8.GC_MC_INCREMENTAL ×82 0.2; EventDispatch ×2 0.0; EventDispatcher::dispatchEvent ×2 0.0; EventDispatcher::dispatch ×2 0.0; AsyncTask Run ×2 0.0; AsyncTask Scheduled ×2 0.0
- **compinputs** 1,742 ms: Blink.CompositingInputs.UpdateTime ×90 1,741.6; compinputs (self) ×90 0.3; LayoutView::commitPendingSelection ×64 0.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×4 0.1; V8.GC_MC_INCREMENTAL ×4 0.0
- **UL-other** 1,470 ms: UL-other (self) ×46 1,242.8; LocalFrameView::ScheduleAnimation ×112194 122.3; LocalFrameView::UpdateStyleAndLayout ×89 86.0; SelectorStats ×88 8.4; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×119 6.6; Blink.Layout.UpdateTime ×87 1.1; Blink.Style.UpdateTime ×88 0.5; LocalFrameView::layout ×87 0.3; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×89 0.3; LocalFrameView::performPostLayoutTasks ×87 0.2; LocalFrameView::updateStyleAndLayoutIfNeededRecursive ×89 0.2; LocalFrameView::DidFinishLifecycleUpdate ×46 0.2; V8.GC_MC_INCREMENTAL ×119 0.2; ResourceLoadPriorityOptimizer::UpdateImagePrioritiesAndSpeculativeDecodes ×74 0.1
- **prepaint** 216 ms: Blink.PrePaint.UpdateTime ×90 215.9; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×11 0.3; prepaint (self) ×90 0.2; V8.GC_MC_INCREMENTAL ×11 0.0
- **hover** 40 ms: LocalFrameView::UpdateStyleAndLayout ×44 23.5; SelectorStats ×44 8.1; HitTest ×44 6.3; hover (self) ×44 1.6; LayoutView::HitTest ×44 0.4; Blink.Style.UpdateTime ×44 0.3; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×44 0.1; LocalFrameView::updateStyleAndLayoutIfNeededRecursive ×44 0.1; PrePaint ×44 0.1; RootScrollerController::PerformRootScrollerSelection ×31 0.0
- **task** 29 ms: RunTask ×365 28.2; TimerBase::run ×34 0.9; AsyncTask Run ×2 0.0; EventDispatcher::dispatchEvent ×2 0.0; EventDispatch ×2 0.0; EventDispatcher::dispatch ×2 0.0; AsyncTask Scheduled ×1 0.0
- **frame-other** 19 ms: HitTest ×44 14.0; Commit ×46 2.1; MainFrameAborted ×43 0.8; frame-other (self) ×46 0.6; LayerTreeHost::WaitForCommitCompletion ×46 0.3; OverlayInterstitialAdDetector::MaybeFireDetection ×22 0.1; AnimationHost::TickAnimations ×44 0.1; StickyAdDetector::MaybeFireDetection ×22 0.1; LayerTreeHost::ApplyCompositorChanges ×46 0.1; LocalFrameView::RunAccessibilitySteps ×46 0.1; Blink.Accessibility.UpdateTime ×46 0.1; Blink.IntersectionObservation.UpdateTime ×45 0.1; LocalFrameView::UpdateViewportIntersectionsForSubtree ×46 0.1; LayerTreeHost::DoUpdateLayers ×3 0.0

### token 6 — passes by elementCount (n, sum ms, mean ms; mean children self ms per pass)

- ec 1553: n 11, sum 2,505, mean 227.7: Document::recalcStyle ×1.0 210.78; AnimationTimeline::serviceAnimations ×4611.7 5.76; Document::updateStyle ×1.0 5.09; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×83.2 1.41; V8.GC_MC_INCREMENTAL ×83.5 0.12; LocalFrameView::ScheduleAnimation ×53.5 0.06; Document::rebuildLayoutTree ×0.1 0.05; Document::updateActiveStyle ×0.6 0.0 | inst {"AnimationTimeline::serviceAnimations": 7242.6, "LocalFrameView::ScheduleAnimation|Add": 16.5, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.4, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.3}
- ec 126: n 12, sum 1,818, mean 151.5: Document::recalcStyle ×1.0 133.95; AnimationTimeline::serviceAnimations ×4679.6 5.85; Document::updateStyle ×1.0 4.49; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×190.7 2.96; V8.GC_MC_INCREMENTAL ×192.5 0.23; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6186.9, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.8, "Document::updateActiveStyle": 0.2}
- ec 3089: n 12, sum 1,793, mean 149.4: Document::recalcStyle ×1.0 130.72; AnimationTimeline::serviceAnimations ×4247.5 5.49; Document::updateStyle ×1.0 4.43; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×237.9 4.27; V8.GC_MC_INCREMENTAL ×240.1 0.26; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6619.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.2, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.2}
- ec 784: n 12, sum 1,740, mean 145.0: Document::recalcStyle ×1.0 113.17; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 8.82; AnimationTimeline::serviceAnimations ×4935.1 6.44; Document::updateStyle ×1.0 4.58; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×218.3 3.73; V8.GC_MARK_COMPACTOR ×0.1 3.07; V8.GC_MC_MARK ×0.1 0.46; V8.GC_MC_INCREMENTAL ×217.9 0.24; V8.GC_HEAP_EXTERNAL_PROLOGUE ×0.1 0.19; V8.GC_MC_CLEAR_SWEEP_EXTERNAL_POINTER_TABLE ×0.1 0.01 | inst {"AnimationTimeline::serviceAnimations": 5931.4, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.2, "ClearStringTableJob started": 0.6, "Document::updateActiveStyle": 0.2, "V8.GC_TIME_TO_SAFEPOINT": 0.1}
- ec 50892: n 1, sum 1,398, mean 1398.3: Document::recalcStyle ×1.0 586.12; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×1.0 497.95; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×475.0 278.21; AnimationTimeline::serviceAnimations ×8846.0 11.46; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×1.0 10.36; Document::updateStyle ×1.0 5.45; V8.GC_MC_INCREMENTAL ×477.0 0.91; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×2.0 0.23; V8.GC_MC_INCREMENTAL_START ×1.0 0.13; V8.GC_MC_INCREMENTAL_EXTERNAL_EPILOGUE ×1.0 0.06 | inst {"AnimationTimeline::serviceAnimations": 12887.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.0, "UpdateCounters": 1.0, "Major concurrent marking rescheduled": 1.0}
- ec 6919: n 12, sum 1,391, mean 115.9: Document::recalcStyle ×1.0 45.16; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×0.1 43.25; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×59.3 6.2; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 5.81; AnimationTimeline::serviceAnimations ×4182.3 5.01; Document::updateStyle ×1.0 4.7; V8.GC_MARK_COMPACTOR ×0.1 1.11; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×0.1 0.38; V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL ×0.1 0.16; V8.GC_HEAP_EXTERNAL_PROLOGUE ×0.1 0.1 | inst {"AnimationTimeline::serviceAnimations": 6684.2, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.4, "ClearStringTableJob started": 0.3, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.2, "V8.GC_HEAP_PROLOGUE_SAFEPOINT": 0.1}
- ec 2323: n 10, sum 1,016, mean 101.6: Document::recalcStyle ×1.0 85.01; AnimationTimeline::serviceAnimations ×4342.0 5.58; Document::updateStyle ×1.0 4.34; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×143.9 2.54; V8.GC_MC_INCREMENTAL ×145.5 0.17; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 6524.5, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.8, "V8.GC_MC_INCREMENTAL": 0.2}
- ec 0: n 42, sum 796, mean 19.0: AnimationTimeline::serviceAnimations ×8350.7 11.46; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.26; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL ×1.0 0.0; Document::updateActiveStyle ×1.0 0.0; Major concurrent marking rescheduled ×0.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13364.0, "Document::updateActiveStyle": 0.0}
- ec 780: n 12, sum 491, mean 40.9: Document::recalcStyle ×1.0 26.11; AnimationTimeline::serviceAnimations ×4272.4 5.39; Document::updateStyle ×1.0 4.3; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×43.5 0.93; V8.GC_MC_INCREMENTAL ×43.8 0.05; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6594.1, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.3, "Document::updateActiveStyle": 0.2}
- ec 2326: n 1, sum 243, mean 243.2: Document::recalcStyle ×1.0 229.97; Document::updateStyle ×1.0 10.74; Document::rebuildLayoutTree ×1.0 1.98; AnimationTimeline::serviceAnimations ×255.0 0.26; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 514.0, "InvalidateLayout": 2.0}
- ec 2342: n 1, sum 224, mean 224.4: Document::recalcStyle ×1.0 200.48; AnimationTimeline::serviceAnimations ×9281.0 10.58; Document::updateStyle ×1.0 6.14; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 12452.0, "InvalidateLayout": 2.0}
- ec 2334: n 1, sum 116, mean 116.0: Document::recalcStyle ×1.0 107.66; Document::updateStyle ×1.0 4.06; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×184.0 3.8; V8.GC_MC_INCREMENTAL ×187.0 0.22; Document::updateActiveStyle ×1.0 0.0 | inst {"V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 3.0, "InvalidateLayout": 2.0}
- ec 863: n 1, sum 93, mean 93.3: Document::recalcStyle ×1.0 84.97; Document::updateStyle ×1.0 4.77; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×99.0 1.7; Document::updateStyleInvalidationIfNeeded ×1.0 1.43; V8.GC_MC_INCREMENTAL ×100.0 0.15; Document::updateActiveStyle ×1.0 0.0 | inst {"InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.0}
- ec 1: n 2, sum 44, mean 22.0: AnimationTimeline::serviceAnimations ×8475.5 14.68; Document::recalcStyle ×1.0 0.04; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL ×1.5 0.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.5 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13257.5, "AnimationFrame::Presentation": 0.5}
- ec 39: n 1, sum 27, mean 27.0: Document::recalcStyle ×1.0 20.16; Document::updateStyle ×1.0 5.04; Document::updateStyleInvalidationIfNeeded ×1.0 1.31; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.03; V8.GC_MC_INCREMENTAL ×1.0 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {"InvalidateLayout": 2.0}
- ec 6: n 1, sum 12, mean 11.9: Document::recalcStyle ×1.0 11.27; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.08; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL ×1.0 0.0; Document::updateActiveStyle ×1.0 0.0 | inst {}

### token 6 — instants: {"AnimationTimeline::serviceAnimations": 1656355, "Animation": 123724, "LocalFrameView::ScheduleAnimation|Add": 18527, "LocalFrameView::ScheduleAnimation|ScheduleServiceOnNextFrame": 11448, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 220, "InvalidateLayout": 174, "InlineNode::ShapeTextIncludingFirstLine": 101, "ScrollTree::SetScrollOffset": 93, "SetLayerTreeId": 90, "ScheduleStyleRecalculation": 88, "BeginCommitCompositorFrame": 46, "LongTask": 46}

### token 6 — Animation b/e: {"b/running": 9546, "e/": 9232}; names: [('|e', 9232), ('--saved-N-N|b', 9228), ('--fc-vs-N-N|b', 144), ('--fc-ks-N-N|b', 144), ('--fc-k-N|b', 12), ('--fc-v-N|b', 12), ('--head-input-epoch|b', 2), ('native-handshake|b', 2), ('--saved-token-N|b', 1), ('--head-fvs|b', 1)]

### token 6 — head frame: 4,647 ms at 27,391 ms; phases {"task": 0.1, "frame-other": 0.21, "animate": 46.51, "hover": 0.89, "style": 1664.07, "compinputs": 941.86, "prepaint": 49.83, "UL-other": 37.2, "layout": 1673.48, "paintLC": 233.39}; passes [(0, 22.58), (2326, 243.22), (50892, 1398.27)]; layouts [(2374, 35.57), (101162, 1637.9)]
  top: {"task": [["RunTask", 0.1]], "frame-other": [["Commit", 0.11], ["HitTest", 0.04], ["frame-other (self)", 0.02], ["OverlayInterstitialAdDetector::MaybeFireDetection", 0.01], ["LayerTreeHost::DoUpdateLayers", 0.01], ["ProxyMain::BeginMainFrame::commit", 0.01]], "animate": [["PageAnimator::serviceScriptedAnimations", 31.55], ["AnimationTimeline::serviceAnimations", 14.17], ["LocalFrameView::ScheduleAnimation", 0.76], ["animate (self)", 0.01], ["Blink.Animate.UpdateTime", 0.01]], "hover": [["LocalFrameView::UpdateStyleAndLayout", 0.57], ["HitTest", 0.14], ["SelectorStats", 0.11], ["hover (self)", 0.05], ["LayoutView::HitTest", 0.01], ["Blink.Style.UpdateTime", 0.01]], "style": [["Document::recalcStyle", 816.08], ["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 497.95], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 278.21], ["AnimationTimeline::serviceAnimations", 26.85], ["Document::updateStyle", 16.21], ["style (self)", 15.0]], "compinputs": [["Blink.CompositingInputs.UpdateTime", 941.83], ["compinputs (self)", 0.02], ["LayoutView::commitPendingSelection", 0.01]], "prepaint": [["Blink.PrePaint.UpdateTime", 49.76], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.05], ["V8.GC_MC_INCREMENTAL", 0.01], ["prepaint (self)", 0.0]], "UL-other": [["UL-other (self)", 26.08], ["LocalFrameView::UpdateStyleAndLayout", 5.29], ["LocalFrameView::ScheduleAnimation", 5.18], ["SelectorStats", 0.53], ["Blink.Layout.UpdateTime", 0.04], ["Blink.Style.UpdateTime", 0.02]], "layout": [["InlineNode::ShapeTextIncludingFirstLine", 1005.43], ["LocalFrameView::performLayout", 651.94], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 13.42], ["V8.GC_MC_INCREMENTAL", 1.49], ["layout (self)", 1.2]], "paintLC": [["paintLC (self)", 220.19], ["CullRectUpdate", 9.85], ["Blink.Paint.UpdateTime", 2.37], ["Paint", 0.45], ["PaintArtifactCompositor::Update", 0.45], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.03]]}

### token 6 — frames

| # | t | dur | passes ec:ms | layouts dirty:ms | style | layout | paintLC | animate | compinputs | UL-other | prepaint | task | hover | frame-other | sa X | anim b/e |
|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 371 | 600 | 0:18 126:144 6919:68 | 339:97 10032:90 | 231 | 187 | 91 | 51 | 5 | 32 | 4 | 0 | 1 | 0 | 28267 | 26/0 |
| 1 | 982 | 1,791 | 0:20 780:27 3089:145 | 2344:24 9266:1341 | 192 | 1365 | 105 | 54 | 37 | 30 | 6 | 0 | 1 | 1 | 27126 | 0/0 |
| 2 | 2,778 | 795 | 0:35 784:122 1553:229 | 2359:67 1600:30 | 386 | 97 | 155 | 93 | 18 | 41 | 2 | 0 | 4 | 0 | 30659 | 769/769 |
| 3 | 3,575 | 664 | 0:19 2334:116 126:153 | 6944:50 339:83 | 288 | 133 | 143 | 50 | 13 | 32 | 3 | 0 | 1 | 1 | 29895 | 27/0 |
| 4 | 4,243 | 347 | 0:17 6919:47 780:50 | 10032:81 2344:25 | 114 | 106 | 42 | 44 | 8 | 29 | 4 | 0 | 1 | 0 | 25697 | 0/0 |
| 5 | 4,592 | 682 | 0:18 3089:131 784:139 | 9266:63 2359:69 | 288 | 132 | 124 | 49 | 47 | 36 | 5 | 0 | 1 | 1 | 27714 | 0/0 |
| 6 | 5,276 | 641 | 0:18 1553:216 2323:105 | 1600:30 6943:51 | 339 | 82 | 121 | 49 | 13 | 34 | 3 | 0 | 1 | 0 | 27986 | 769/769 |
| 7 | 5,919 | 544 | 0:18 126:133 6919:64 | 339:81 10032:78 | 216 | 158 | 80 | 53 | 5 | 27 | 3 | 0 | 1 | 1 | 26809 | 26/0 |
| 8 | 6,467 | 455 | 0:16 780:32 3089:161 | 2344:24 9266:64 | 209 | 87 | 57 | 40 | 25 | 30 | 5 | 0 | 1 | 0 | 26284 | 0/0 |
| 9 | 6,923 | 758 | 0:19 784:122 1553:240 | 2359:69 1600:32 | 380 | 101 | 164 | 54 | 18 | 36 | 3 | 0 | 1 | 1 | 28076 | 769/769 |
| 10 | 7,683 | 635 | 0:18 2323:85 126:152 | 6943:53 339:82 | 255 | 135 | 143 | 50 | 14 | 34 | 3 | 0 | 1 | 0 | 28567 | 26/0 |
| 11 | 8,322 | 346 | 0:19 6919:48 780:49 | 10032:81 2344:25 | 115 | 106 | 40 | 42 | 9 | 29 | 5 | 0 | 1 | 0 | 25906 | 0/0 |
| 12 | 8,670 | 711 | 0:20 3089:138 784:156 | 9266:65 2359:70 | 314 | 135 | 122 | 50 | 47 | 36 | 5 | 0 | 1 | 1 | 28244 | 0/0 |
| 13 | 9,383 | 665 | 0:17 1553:218 2323:105 | 1600:31 6943:51 | 340 | 82 | 139 | 51 | 14 | 35 | 3 | 0 | 1 | 0 | 27780 | 769/769 |
| 14 | 10,050 | 556 | 0:20 126:134 6919:62 | 339:81 10032:85 | 217 | 166 | 86 | 52 | 5 | 26 | 3 | 0 | 1 | 1 | 26928 | 26/0 |
| 15 | 10,611 | 474 | 0:20 780:31 3089:169 | 2344:26 9266:63 | 219 | 89 | 58 | 51 | 23 | 29 | 4 | 0 | 1 | 0 | 27150 | 0/0 |
| 16 | 11,104 | 764 | 0:18 784:125 1553:235 | 2359:69 1600:31 | 378 | 100 | 178 | 55 | 16 | 33 | 2 | 0 | 1 | 1 | 28291 | 769/769 |
| 17 | 11,870 | 644 | 0:19 2323:93 126:161 | 6943:54 339:79 | 273 | 134 | 138 | 52 | 13 | 31 | 3 | 0 | 1 | 0 | 30279 | 26/0 |
| 18 | 12,518 | 422 | 0:19 6919:135 780:42 | 10032:77 2344:22 | 197 | 99 | 40 | 46 | 9 | 27 | 4 | 0 | 1 | 1 | 26827 | 0/0 |
| 19 | 12,943 | 673 | 0:15 3089:119 784:123 | 9266:59 2359:84 | 257 | 143 | 135 | 46 | 48 | 36 | 6 | 0 | 1 | 0 | 28296 | 0/0 |
| 20 | 13,625 | 730 | 0:20 1553:240 2323:117 | 1600:38 6943:59 | 376 | 97 | 151 | 46 | 16 | 40 | 3 | 0 | 1 | 1 | 30118 | 769/769 |
| 21 | 14,362 | 1,197 | 0:21 126:133 6919:668 | 339:85 10032:122 | 821 | 207 | 82 | 50 | 6 | 26 | 4 | 0 | 1 | 1 | 26311 | 26/0 |
| 22 | 15,569 | 434 | 0:16 780:31 3089:143 | 2344:24 9266:58 | 190 | 82 | 58 | 46 | 24 | 28 | 5 | 0 | 1 | 0 | 26832 | 0/0 |
| 23 | 16,004 | 742 | 0:16 784:110 1553:221 | 2359:69 1600:31 | 346 | 99 | 186 | 52 | 18 | 36 | 2 | 0 | 1 | 1 | 27534 | 769/769 |
| 24 | 16,748 | 623 | 0:17 2323:81 126:154 | 6943:49 339:83 | 251 | 131 | 139 | 49 | 14 | 34 | 3 | 0 | 1 | 0 | 28570 | 26/0 |
| 25 | 17,375 | 351 | 0:18 6919:50 780:50 | 10032:82 2344:25 | 117 | 107 | 41 | 43 | 8 | 30 | 4 | 0 | 1 | 0 | 25999 | 0/0 |
| 26 | 17,728 | 712 | 0:18 3089:141 784:151 | 9266:60 2359:72 | 310 | 133 | 128 | 52 | 46 | 37 | 5 | 0 | 1 | 1 | 27661 | 0/0 |
| 27 | 18,442 | 675 | 0:19 1553:209 2323:105 | 1600:33 6943:53 | 333 | 86 | 155 | 49 | 14 | 34 | 3 | 0 | 1 | 0 | 27801 | 769/769 |
| 28 | 19,119 | 589 | 0:19 126:148 6919:73 | 339:91 10032:84 | 240 | 175 | 86 | 51 | 5 | 28 | 4 | 0 | 1 | 1 | 26815 | 26/0 |
| 29 | 19,714 | 466 | 0:18 780:32 3089:164 | 2344:25 9266:65 | 213 | 90 | 58 | 46 | 23 | 30 | 5 | 0 | 1 | 0 | 27214 | 0/0 |
| 30 | 20,181 | 790 | 0:17 784:121 1553:230 | 2359:68 1600:32 | 369 | 100 | 209 | 55 | 18 | 36 | 2 | 0 | 1 | 1 | 27947 | 769/769 |
| 31 | 20,973 | 656 | 0:19 2323:87 126:173 | 6943:56 339:78 | 279 | 134 | 141 | 52 | 13 | 33 | 3 | 0 | 1 | 0 | 29501 | 26/0 |
| 32 | 21,633 | 375 | 0:18 6919:48 780:53 | 10032:99 2344:23 | 120 | 122 | 40 | 47 | 10 | 29 | 4 | 0 | 1 | 1 | 26615 | 0/0 |
| 33 | 22,011 | 709 | 0:19 3089:144 784:146 | 9266:69 2359:69 | 309 | 138 | 127 | 48 | 48 | 33 | 5 | 0 | 1 | 0 | 27965 | 0/0 |
| 34 | 22,722 | 726 | 0:21 1553:213 2323:121 | 1600:34 6943:55 | 355 | 89 | 176 | 50 | 15 | 36 | 3 | 0 | 1 | 1 | 28849 | 769/769 |
| 35 | 23,450 | 579 | 0:20 126:142 6919:70 | 339:80 10032:96 | 232 | 176 | 84 | 51 | 5 | 26 | 3 | 0 | 1 | 0 | 26508 | 26/0 |
| 36 | 24,034 | 492 | 0:19 780:40 3089:168 | 2344:29 9266:70 | 227 | 99 | 59 | 49 | 24 | 29 | 5 | 0 | 1 | 1 | 26528 | 0/0 |
| 37 | 24,527 | 865 | 0:19 784:143 1553:256 | 2359:76 1600:32 | 418 | 108 | 222 | 59 | 18 | 36 | 3 | 0 | 1 | 0 | 28800 | 769/769 |
| 38 | 25,394 | 719 | 0:17 2323:117 126:190 | 6943:64 339:83 | 324 | 147 | 144 | 51 | 14 | 34 | 4 | 0 | 1 | 1 | 28770 | 26/0 |
| 39 | 26,117 | 370 | 0:20 6919:59 780:55 | 10032:86 2344:25 | 134 | 111 | 39 | 45 | 9 | 26 | 4 | 0 | 1 | 0 | 26704 | 0/0 |
| 40 | 26,489 | 898 | 0:17 3089:172 784:283 | 9266:82 2359:75 | 472 | 157 | 122 | 47 | 49 | 40 | 9 | 0 | 1 | 1 | 28279 | 0/0 |
| 41 | 27,391 | 4,647 | 0:23 2326:243 50892:1398 | 2374:36 101162:1638 | 1664 | 1673 | 233 | 47 | 942 | 37 | 50 | 0 | 1 | 0 | 30454 | 770/771 |
| 42 | 32,043 | 138 | 1:26 6:12 |  | 38 | 0 | 21 | 51 | 0 | 26 | 1 | 0 | 1 | 0 | 19370 | 0/1 |
| 43 | 32,182 | 139 | 39:27 | 7:13 | 27 | 13 | 22 | 49 | 0 | 27 | 1 | 0 | 0 | 0 | 9536 | 1/0 |
| 44 | 32,321 | 111 | 1:18 |  | 18 | 0 | 21 | 47 | 0 | 24 | 1 | 0 | 1 | 0 | 17157 | 0/1 |
| 45 | 32,433 | 544 | 863:93 2342:152 | 1571:111 6944:58 | 246 | 169 | 34 | 44 | 15 | 32 | 3 | 0 | 0 | 0 | 18082 | 2/0 |

## token 7 — top names by self time within each phase (name, count, self ms)

- **style** 16,374 ms: Document::recalcStyle ×90 10,923.9; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×2 2,247.0; AnimationTimeline::serviceAnimations ×745007 1,015.4; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×13701 707.7; style (self) ×132 655.3; Document::updateStyle ×132 419.3; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×2 194.6; V8.GC_MARK_COMPACTOR ×2 157.1; V8.GC_MC_INCREMENTAL ×13799 17.0; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×2 14.0; V8.GC_MC_MARK ×2 4.6; V8.GC_HEAP_EXTERNAL_PROLOGUE ×2 4.5; Document::updateStyleInvalidationIfNeeded ×2 2.7; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×4 1.9
- **layout** 7,308 ms: LocalFrameView::performLayout ×87 4,795.9; InlineNode::ShapeTextIncludingFirstLine ×199516 2,437.4; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×5394 52.9; layout (self) ×87 15.6; V8.GC_MC_INCREMENTAL ×5501 5.8
- **paintLC** 5,207 ms: paintLC (self) ×46 5,170.7; CullRectUpdate ×46 14.8; Blink.Paint.UpdateTime ×46 10.9; Paint ×90 6.7; PaintArtifactCompositor::Update ×46 2.6; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×39 0.8; ScrollTree::SetScrollOffset ×91 0.2; Layerize ×46 0.1; V8.GC_MC_INCREMENTAL ×39 0.1; PaintController::commitNewDisplayItems ×44 0.1; LocalFrameView::pushPaintArtifactToCompositor ×46 0.1; Blink.CompositingCommit.UpdateTime ×46 0.1; LocalFrameView::ScheduleAnimation ×4 0.1; auto cc::LayerTreeHost::SetNeedsCommit(bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const ×3 0.0
- **animate** 2,257 ms: PageAnimator::serviceScriptedAnimations ×46 1,554.1; AnimationTimeline::serviceAnimations ×489495 650.1; LocalFrameView::ScheduleAnimation ×43799 50.0; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×76 1.2; animate (self) ×46 0.5; Blink.Animate.UpdateTime ×46 0.5; V8.GC_MC_INCREMENTAL ×77 0.2; EventDispatch ×2 0.0; EventDispatcher::dispatchEvent ×2 0.0; EventDispatcher::dispatch ×2 0.0; AsyncTask Scheduled ×2 0.0; AsyncTask Run ×2 0.0
- **compinputs** 1,746 ms: Blink.CompositingInputs.UpdateTime ×90 1,746.0; compinputs (self) ×90 0.2; LayoutView::commitPendingSelection ×67 0.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1 0.1; V8.GC_MC_INCREMENTAL ×1 0.0
- **UL-other** 1,463 ms: UL-other (self) ×46 1,229.2; LocalFrameView::ScheduleAnimation ×112142 124.8; LocalFrameView::UpdateStyleAndLayout ×89 92.9; SelectorStats ×88 8.8; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×112 3.2; Blink.Layout.UpdateTime ×87 1.2; Blink.Style.UpdateTime ×88 0.5; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×89 0.3; LocalFrameView::performPostLayoutTasks ×87 0.3; LocalFrameView::layout ×87 0.3; LocalFrameView::updateStyleAndLayoutIfNeededRecursive ×89 0.2; LocalFrameView::DidFinishLifecycleUpdate ×46 0.2; V8.GC_MC_INCREMENTAL ×112 0.1; ResourceLoadPriorityOptimizer::UpdateImagePrioritiesAndSpeculativeDecodes ×78 0.1
- **prepaint** 223 ms: Blink.PrePaint.UpdateTime ×90 222.9; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×10 0.3; prepaint (self) ×90 0.2; V8.GC_MC_INCREMENTAL ×10 0.0
- **task** 41 ms: RunTask ×360 39.8; TimerBase::run ×40 1.1; AsyncTask Run ×2 0.0; EventDispatcher::dispatchEvent ×2 0.0; EventDispatch ×2 0.0; EventDispatcher::dispatch ×2 0.0; AsyncTask Scheduled ×1 0.0
- **hover** 38 ms: LocalFrameView::UpdateStyleAndLayout ×44 23.4; HitTest ×44 6.7; SelectorStats ×44 5.7; hover (self) ×44 1.5; LayoutView::HitTest ×44 0.4; Blink.Style.UpdateTime ×44 0.2; LocalFrameView::updateStyleAndLayoutIfNeededRecursive ×44 0.1; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×44 0.1; PrePaint ×44 0.1; RootScrollerController::PerformRootScrollerSelection ×32 0.1; V8.GC_MC_INCREMENTAL ×1 0.0; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1 0.0
- **frame-other** 20 ms: HitTest ×46 15.4; Commit ×46 2.4; MainFrameAborted ×43 0.9; frame-other (self) ×46 0.6; LayerTreeHost::WaitForCommitCompletion ×46 0.2; OverlayInterstitialAdDetector::MaybeFireDetection ×23 0.2; StickyAdDetector::MaybeFireDetection ×23 0.1; AnimationHost::TickAnimations ×44 0.1; LocalFrameView::UpdateViewportIntersectionsForSubtree ×46 0.1; LayerTreeHost::ApplyCompositorChanges ×46 0.1; LocalFrameView::RunAccessibilitySteps ×46 0.1; Blink.IntersectionObservation.UpdateTime ×46 0.1; Blink.Accessibility.UpdateTime ×46 0.1; LayerTreeHost::DoUpdateLayers ×3 0.0

### token 7 — passes by elementCount (n, sum ms, mean ms; mean children self ms per pass)

- ec 784: n 12, sum 3,147, mean 262.3: Document::recalcStyle ×1.0 135.91; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×0.1 76.98; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×219.7 21.04; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 8.16; AnimationTimeline::serviceAnimations ×4817.0 6.41; Document::updateStyle ×1.0 4.44; V8.GC_MARK_COMPACTOR ×0.1 3.96; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×0.1 0.47; V8.GC_MC_INCREMENTAL ×220.7 0.25; V8.GC_HEAP_EXTERNAL_PROLOGUE ×0.1 0.19 | inst {"AnimationTimeline::serviceAnimations": 5985.4, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.0, "ClearStringTableJob started": 0.6, "Document::updateActiveStyle": 0.2, "V8.GC_TIME_TO_SAFEPOINT": 0.1}
- ec 2323: n 10, sum 2,937, mean 293.7: V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×0.1 132.33; Document::recalcStyle ×1.0 96.97; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×124.8 27.02; V8.GC_MARK_COMPACTOR ×0.1 10.95; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 9.67; AnimationTimeline::serviceAnimations ×4271.6 5.79; Document::updateStyle ×1.0 5.28; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×0.1 0.83; V8.GC_MC_MARK ×0.1 0.29; V8.GC_HEAP_EXTERNAL_PROLOGUE ×0.1 0.22 | inst {"AnimationTimeline::serviceAnimations": 6594.9, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.5, "ClearStringTableJob started": 0.6, "Document::updateActiveStyle": 0.5, "V8.GC_HEAP_PROLOGUE_SAFEPOINT": 0.1}
- ec 1553: n 11, sum 2,552, mean 232.0: Document::recalcStyle ×1.0 216.13; AnimationTimeline::serviceAnimations ×4589.6 5.83; Document::updateStyle ×1.0 4.19; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×77.0 1.33; V8.GC_MC_INCREMENTAL ×77.5 0.11; Document::rebuildLayoutTree ×0.1 0.08; LocalFrameView::ScheduleAnimation ×55.6 0.06; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 7194.8, "LocalFrameView::ScheduleAnimation|Add": 14.3, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.5}
- ec 126: n 12, sum 2,188, mean 182.3: Document::recalcStyle ×1.0 161.94; Document::updateStyle ×1.0 6.71; AnimationTimeline::serviceAnimations ×4749.5 6.18; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×203.4 3.23; V8.GC_MC_INCREMENTAL ×204.8 0.25; Document::updateActiveStyle ×0.9 0.0 | inst {"AnimationTimeline::serviceAnimations": 6052.9, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.4, "Document::updateActiveStyle": 0.1}
- ec 3089: n 12, sum 2,126, mean 177.1: Document::recalcStyle ×1.0 158.67; AnimationTimeline::serviceAnimations ×4270.7 5.43; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×248.2 4.48; Document::updateStyle ×1.0 4.39; V8.GC_MC_INCREMENTAL ×250.3 0.29; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6595.8, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.2, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.2}
- ec 0: n 42, sum 805, mean 19.2: AnimationTimeline::serviceAnimations ×8359.5 11.97; Document::updateStyle ×1.0 0.01; Document::updateActiveStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.0; V8.GC_MC_INCREMENTAL ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13300.3, "Document::updateActiveStyle": 0.0, "AnimationFrame::Presentation": 0.0}
- ec 6919: n 12, sum 786, mean 65.5: Document::recalcStyle ×1.0 50.48; AnimationTimeline::serviceAnimations ×4130.8 5.4; Document::updateStyle ×1.0 4.45; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×61.4 1.14; V8.GC_MC_INCREMENTAL ×61.7 0.09; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6735.7, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.2, "Document::updateActiveStyle": 0.2}
- ec 50892: n 1, sum 594, mean 594.0: Document::recalcStyle ×1.0 542.46; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1555.0 25.62; AnimationTimeline::serviceAnimations ×9013.0 11.79; Document::updateStyle ×1.0 4.97; V8.GC_MC_INCREMENTAL ×1562.0 1.9; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 12720.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 7.0, "InvalidateLayout": 2.0}
- ec 780: n 12, sum 560, mean 46.7: Document::recalcStyle ×1.0 31.61; AnimationTimeline::serviceAnimations ×4245.8 5.43; Document::updateStyle ×1.0 4.49; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×45.3 0.91; V8.GC_MC_INCREMENTAL ×45.6 0.06; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6556.6, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.2, "Document::updateActiveStyle": 0.2}
- ec 2326: n 1, sum 238, mean 238.0: Document::recalcStyle ×1.0 230.07; Document::updateStyle ×1.0 4.28; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×94.0 1.86; Document::rebuildLayoutTree ×1.0 1.04; AnimationTimeline::serviceAnimations ×241.0 0.27; V8.GC_MC_INCREMENTAL ×96.0 0.14 | inst {"AnimationTimeline::serviceAnimations": 528.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.0, "Document::updateActiveStyle": 1.0}
- ec 2342: n 1, sum 152, mean 152.4: Document::recalcStyle ×1.0 125.47; AnimationTimeline::serviceAnimations ×8617.0 10.48; Document::updateStyle ×1.0 4.27; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×232.0 4.03; V8.GC_MC_INCREMENTAL ×234.0 0.3; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13116.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.0}
- ec 2334: n 1, sum 139, mean 139.0: Document::recalcStyle ×1.0 114.4; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×218.0 19.89; Document::updateStyle ×1.0 4.17; V8.GC_MC_INCREMENTAL ×220.0 0.23; Document::updateActiveStyle ×1.0 0.0 | inst {"V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.0, "InvalidateLayout": 2.0}
- ec 863: n 1, sum 82, mean 82.3: Document::recalcStyle ×1.0 74.8; Document::updateStyle ×1.0 4.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×123.0 1.67; Document::updateStyleInvalidationIfNeeded ×1.0 1.41; V8.GC_MC_INCREMENTAL ×127.0 0.14; Document::updateActiveStyle ×1.0 0.0 | inst {"V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 4.0, "InvalidateLayout": 2.0}
- ec 1: n 2, sum 36, mean 17.8: AnimationTimeline::serviceAnimations ×8134.5 10.88; Document::recalcStyle ×1.0 0.04; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.5 0.01; V8.GC_MC_INCREMENTAL ×1.5 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13598.5, "AnimationFrame::Presentation": 1.0}
- ec 39: n 1, sum 24, mean 24.5: Document::recalcStyle ×1.0 18.72; Document::updateStyle ×1.0 4.21; Document::updateStyleInvalidationIfNeeded ×1.0 1.29; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.02; V8.GC_MC_INCREMENTAL ×1.0 0.0; Document::updateActiveStyle ×1.0 0.0 | inst {"InvalidateLayout": 2.0}
- ec 6: n 1, sum 8, mean 7.7: Document::recalcStyle ×1.0 7.31; Document::updateStyle ×1.0 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {}

### token 7 — instants: {"AnimationTimeline::serviceAnimations": 1647528, "Animation": 123871, "LocalFrameView::ScheduleAnimation|Add": 18491, "LocalFrameView::ScheduleAnimation|ScheduleServiceOnNextFrame": 11599, "InlineNode::ShapeTextIncludingFirstLine": 500, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 210, "InvalidateLayout": 174, "ScrollTree::SetScrollOffset": 93, "SetLayerTreeId": 90, "ScheduleStyleRecalculation": 88, "BeginCommitCompositorFrame": 46, "LongTask": 46}

### token 7 — Animation b/e: {"b/running": 9545, "e/": 9232}; names: [('|e', 9232), ('--saved-N-N|b', 9228), ('--fc-vs-N-N|b', 144), ('--fc-ks-N-N|b', 144), ('--fc-k-N|b', 12), ('--fc-v-N|b', 12), ('native-handshake|b', 2), ('--saved-token-N|b', 1), ('--head-fvs|b', 1), ('--head-input-epoch|b', 1)]

### token 7 — head frame: 2,291 ms at 11,693 ms; phases {"frame-other": 0.82, "animate": 49.52, "hover": 0.81, "style": 1890.96, "compinputs": 14.57, "prepaint": 2.82, "UL-other": 33.74, "layout": 154.9, "paintLC": 142.82}; passes [(0, 17.93), (2323, 1716.45), (126, 156.58)]; layouts [(6943, 55.02), (339, 99.88)]
  top: {"frame-other": [["HitTest", 0.64], ["Commit", 0.1], ["MainFrameAborted", 0.03], ["frame-other (self)", 0.02], ["LayerTreeHost::WaitForCommitCompletion", 0.01], ["OverlayInterstitialAdDetector::MaybeFireDetection", 0.01]], "animate": [["PageAnimator::serviceScriptedAnimations", 31.45], ["AnimationTimeline::serviceAnimations", 17.34], ["LocalFrameView::ScheduleAnimation", 0.71], ["animate (self)", 0.01], ["Blink.Animate.UpdateTime", 0.01]], "hover": [["LocalFrameView::UpdateStyleAndLayout", 0.51], ["HitTest", 0.13], ["SelectorStats", 0.11], ["hover (self)", 0.04], ["LayoutView::HitTest", 0.01], ["Blink.Style.UpdateTime", 0.01]], "style": [["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 1323.32], ["Document::recalcStyle", 258.05], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 252.6], ["AnimationTimeline::serviceAnimations", 23.52], ["style (self)", 14.57], ["Document::updateStyle", 8.55]], "compinputs": [["Blink.CompositingInputs.UpdateTime", 14.57], ["compinputs (self)", 0.0], ["LayoutView::commitPendingSelection", 0.0]], "prepaint": [["Blink.PrePaint.UpdateTime", 2.82], ["prepaint (self)", 0.01]], "UL-other": [["UL-other (self)", 26.85], ["LocalFrameView::ScheduleAnimation", 4.95], ["LocalFrameView::UpdateStyleAndLayout", 1.08], ["SelectorStats", 0.76], ["Blink.Style.UpdateTime", 0.03], ["Blink.Layout.UpdateTime", 0.03]], "layout": [["LocalFrameView::performLayout", 127.3], ["InlineNode::ShapeTextIncludingFirstLine", 26.27], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 1.04], ["layout (self)", 0.15], ["V8.GC_MC_INCREMENTAL", 0.14]], "paintLC": [["paintLC (self)", 142.41], ["Paint", 0.11], ["PaintArtifactCompositor::Update", 0.1], ["Blink.Paint.UpdateTime", 0.1], ["CullRectUpdate", 0.09], ["PaintController::commitNewDisplayItems", 0.01]]}

### token 7 — frames

| # | t | dur | passes ec:ms | layouts dirty:ms | style | layout | paintLC | animate | compinputs | UL-other | prepaint | task | hover | frame-other | sa X | anim b/e |
|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 295 | 617 | 0:19 126:162 6919:71 | 339:96 11568:93 | 252 | 190 | 85 | 51 | 5 | 30 | 3 | 0 | 1 | 1 | 27047 | 26/0 |
| 1 | 918 | 480 | 0:18 780:34 3089:167 | 2344:25 9266:69 | 219 | 94 | 58 | 51 | 22 | 30 | 5 | 0 | 1 | 0 | 26711 | 0/0 |
| 2 | 1,399 | 837 | 0:20 784:133 1553:234 | 2359:71 1600:31 | 387 | 103 | 234 | 56 | 18 | 36 | 3 | 0 | 1 | 1 | 28992 | 769/769 |
| 3 | 2,239 | 720 | 0:17 2334:139 126:169 | 6944:57 339:90 | 326 | 147 | 142 | 54 | 14 | 34 | 3 | 0 | 1 | 0 | 29396 | 27/0 |
| 4 | 2,963 | 371 | 0:19 6919:57 780:51 | 11568:91 2344:24 | 126 | 115 | 41 | 43 | 10 | 30 | 4 | 0 | 1 | 1 | 25762 | 0/0 |
| 5 | 3,337 | 766 | 0:20 3089:168 784:167 | 9266:68 2359:77 | 354 | 145 | 129 | 50 | 47 | 34 | 5 | 0 | 1 | 0 | 28101 | 0/0 |
| 6 | 4,104 | 780 | 0:19 1553:231 2323:125 | 1600:31 6943:59 | 375 | 91 | 202 | 52 | 14 | 39 | 4 | 0 | 1 | 1 | 27922 | 769/769 |
| 7 | 4,887 | 628 | 0:18 126:166 6919:82 | 339:93 11568:95 | 266 | 188 | 82 | 53 | 5 | 29 | 4 | 0 | 1 | 0 | 26302 | 26/0 |
| 8 | 5,520 | 534 | 0:21 780:33 3089:210 | 2344:32 9266:73 | 264 | 106 | 58 | 46 | 24 | 29 | 5 | 0 | 1 | 1 | 26292 | 0/0 |
| 9 | 6,056 | 884 | 0:21 784:160 1553:238 | 2359:79 1600:32 | 419 | 110 | 241 | 57 | 19 | 35 | 2 | 0 | 1 | 0 | 28443 | 769/769 |
| 10 | 6,942 | 714 | 0:19 2323:112 126:185 | 6943:59 339:92 | 315 | 151 | 143 | 52 | 14 | 34 | 4 | 0 | 1 | 1 | 28602 | 26/0 |
| 11 | 7,660 | 377 | 0:19 6919:57 780:53 | 11568:91 2344:25 | 129 | 116 | 41 | 46 | 10 | 30 | 4 | 0 | 1 | 0 | 26536 | 0/0 |
| 12 | 8,039 | 809 | 0:20 3089:203 784:181 | 9266:68 2359:70 | 404 | 138 | 128 | 47 | 49 | 37 | 5 | 0 | 1 | 1 | 28360 | 0/0 |
| 13 | 8,850 | 903 | 0:19 1553:226 2323:325 | 1600:32 6943:52 | 570 | 84 | 149 | 49 | 15 | 32 | 4 | 0 | 1 | 0 | 28099 | 769/769 |
| 14 | 9,757 | 633 | 0:23 126:178 6919:63 | 339:99 11568:94 | 264 | 193 | 88 | 51 | 6 | 25 | 4 | 0 | 1 | 1 | 27339 | 26/0 |
| 15 | 10,405 | 518 | 0:19 780:38 3089:182 | 2344:25 9266:80 | 239 | 104 | 70 | 47 | 21 | 29 | 7 | 0 | 1 | 0 | 28273 | 0/0 |
| 16 | 10,930 | 755 | 0:19 784:117 1553:232 | 2359:70 1600:36 | 368 | 106 | 175 | 52 | 16 | 33 | 3 | 0 | 1 | 1 | 29308 | 769/769 |
| 17 | 11,693 | 2,291 | 0:18 2323:1716 126:157 | 6943:55 339:100 | 1891 | 155 | 143 | 50 | 15 | 34 | 3 | 0 | 1 | 1 | 29761 | 26/0 |
| 18 | 13,989 | 367 | 0:18 6919:48 780:50 | 11568:95 2344:24 | 117 | 119 | 43 | 44 | 13 | 25 | 4 | 0 | 1 | 0 | 26248 | 0/0 |
| 19 | 14,358 | 692 | 0:19 3089:135 784:140 | 9266:63 2359:68 | 295 | 131 | 128 | 48 | 48 | 38 | 4 | 0 | 1 | 1 | 27520 | 0/0 |
| 20 | 15,052 | 683 | 0:19 1553:216 2323:103 | 1600:32 6943:54 | 339 | 86 | 150 | 52 | 14 | 39 | 3 | 0 | 1 | 0 | 28600 | 769/769 |
| 21 | 15,737 | 605 | 0:19 126:152 6919:68 | 339:102 11568:95 | 238 | 197 | 84 | 48 | 6 | 28 | 3 | 0 | 1 | 1 | 25787 | 26/0 |
| 22 | 16,349 | 471 | 0:19 780:33 3089:162 | 2344:27 9266:66 | 214 | 94 | 56 | 50 | 23 | 29 | 5 | 0 | 1 | 0 | 27554 | 0/0 |
| 23 | 16,821 | 783 | 0:19 784:127 1553:234 | 2359:72 1600:32 | 379 | 104 | 188 | 56 | 18 | 34 | 3 | 0 | 1 | 1 | 28226 | 769/769 |
| 24 | 17,606 | 680 | 0:19 2323:95 126:177 | 6943:48 339:95 | 291 | 143 | 140 | 51 | 15 | 35 | 3 | 0 | 1 | 0 | 29185 | 26/0 |
| 25 | 18,291 | 402 | 0:20 6919:64 780:55 | 11568:105 2344:25 | 140 | 130 | 40 | 47 | 10 | 29 | 5 | 0 | 1 | 1 | 26901 | 0/0 |
| 26 | 18,695 | 742 | 0:21 3089:165 784:150 | 9266:70 2359:70 | 335 | 140 | 130 | 49 | 47 | 36 | 5 | 0 | 1 | 0 | 28172 | 0/0 |
| 27 | 19,439 | 684 | 0:19 1553:214 2323:109 | 1600:32 6943:53 | 341 | 85 | 157 | 49 | 14 | 33 | 3 | 0 | 1 | 1 | 28381 | 769/769 |
| 28 | 20,126 | 619 | 0:20 126:162 6919:74 | 339:92 11568:101 | 256 | 192 | 84 | 49 | 7 | 25 | 3 | 0 | 1 | 0 | 26792 | 26/0 |
| 29 | 20,751 | 491 | 0:17 780:36 3089:177 | 2344:25 9266:79 | 230 | 105 | 56 | 43 | 22 | 28 | 5 | 0 | 1 | 1 | 25418 | 0/0 |
| 30 | 21,243 | 826 | 0:17 784:142 1553:238 | 2359:75 1600:33 | 396 | 108 | 216 | 51 | 17 | 36 | 2 | 0 | 1 | 0 | 28917 | 769/769 |
| 31 | 22,071 | 911 | 0:18 2323:99 126:322 | 6943:81 339:104 | 439 | 186 | 164 | 47 | 21 | 40 | 12 | 0 | 1 | 1 | 30711 | 26/0 |
| 32 | 22,987 | 423 | 0:22 6919:60 780:62 | 11568:111 2344:36 | 145 | 147 | 41 | 45 | 12 | 28 | 5 | 0 | 1 | 0 | 27638 | 0/0 |
| 33 | 23,413 | 869 | 0:20 3089:211 784:209 | 9266:83 2359:83 | 440 | 166 | 128 | 47 | 47 | 33 | 6 | 0 | 1 | 1 | 27873 | 0/0 |
| 34 | 24,285 | 798 | 0:19 1553:247 2323:150 | 1600:34 6943:65 | 416 | 99 | 182 | 49 | 14 | 33 | 3 | 0 | 1 | 0 | 28811 | 769/769 |
| 35 | 25,085 | 663 | 0:20 126:179 6919:79 | 339:97 11568:107 | 278 | 204 | 87 | 55 | 7 | 27 | 4 | 0 | 1 | 1 | 26721 | 26/0 |
| 36 | 25,754 | 557 | 0:19 780:56 3089:215 | 2344:34 9266:76 | 289 | 110 | 56 | 46 | 24 | 26 | 5 | 0 | 1 | 0 | 27240 | 0/0 |
| 37 | 26,312 | 1,002 | 0:19 784:293 1553:243 | 2359:76 1600:34 | 555 | 110 | 227 | 54 | 18 | 34 | 3 | 0 | 1 | 1 | 28877 | 769/769 |
| 38 | 27,317 | 732 | 0:19 2323:102 126:181 | 6943:58 339:116 | 302 | 174 | 150 | 49 | 17 | 35 | 3 | 0 | 1 | 0 | 29785 | 26/0 |
| 39 | 28,060 | 414 | 0:17 6919:63 780:57 | 11568:103 2344:32 | 138 | 135 | 46 | 44 | 9 | 34 | 7 | 0 | 1 | 1 | 26986 | 0/0 |
| 40 | 28,484 | 1,894 | 0:18 3089:131 784:1328 | 9266:77 2359:83 | 1477 | 160 | 117 | 49 | 49 | 36 | 5 | 0 | 1 | 1 | 27918 | 0/0 |
| 41 | 30,381 | 3,825 | 0:19 2326:238 50892:594 | 2374:36 101162:1646 | 851 | 1682 | 225 | 48 | 935 | 41 | 42 | 0 | 1 | 0 | 29168 | 770/771 |
| 42 | 34,207 | 123 | 1:18 6:8 |  | 26 | 0 | 22 | 48 | 0 | 25 | 1 | 0 | 1 | 0 | 18615 | 0/1 |
| 43 | 34,331 | 132 | 39:25 | 7:11 | 25 | 11 | 25 | 45 | 0 | 26 | 1 | 0 | 0 | 0 | 9690 | 1/0 |
| 44 | 34,462 | 112 | 1:18 |  | 18 | 0 | 23 | 45 | 0 | 24 | 1 | 0 | 1 | 0 | 17306 | 0/1 |
| 45 | 34,575 | 506 | 863:82 2342:149 | 1571:101 6944:51 | 231 | 151 | 32 | 45 | 15 | 27 | 4 | 0 | 0 | 0 | 18728 | 2/0 |

## inventory (cat, name, ph, count, sum ms) — top 120

- ('blink', 'AnimationTimeline::serviceAnimations', 'I', 9979020, 0.0)
- ('blink', 'AnimationTimeline::serviceAnimations', 'X', 7406812, 9743.4)
- ('blink', 'InlineNode::ShapeTextIncludingFirstLine', 'X', 1104882, 14507.86)
- ('cc', 'LocalFrameView::ScheduleAnimation', 'X', 929598, 1036.69)
- ('blink.animations,devtools.timeline,benchmark,rail', 'Animation', 'n', 737217, 0.0)
- ('disabled-by-default-devtools.timeline', 'RunTask', 'X', 527738, 198351.23)
- ('disabled-by-default-devtools.timeline', 'RunTask', 'I', 222621, 0.0)
- ('cc', 'LocalFrameView::ScheduleAnimation', 'I', 182058, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL', 's', 110797, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL', 'f', 110797, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL', 'X', 110769, 4141.03)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 'X', 109423, 4009.63)
- ('blink.animations,devtools.timeline,benchmark,rail', 'Animation', 'b', 57242, 0.0)
- ('blink.animations,devtools.timeline,benchmark,rail', 'Animation', 'e', 54622, 0.0)
- ('cc', 'auto cc::SchedulerStateMachine::ShouldThrottleSendBeginMainFrame()::(lambda)::operator()(uint32_t) const', 'I', 12066, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'PipelineReporter', 'b', 12062, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'BeginImplFrameToSendBeginMainFrame', 'b', 12062, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'BeginImplFrameToSendBeginMainFrame', 'e', 12062, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'PipelineReporter', 'e', 12062, 0.0)
- ('cc,benchmark', 'Scheduler::BeginFrame', 'X', 11791, 157.71)
- ('cc,benchmark', 'Scheduler::BeginImplFrame', 'X', 11789, 112.71)
- ('cc', 'auto cc::Scheduler::FinishImplFrame()::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 11784, 202.64)
- ('cc', 'auto cc::Scheduler::SendDidNotProduceFrame(const viz::BeginFrameArgs &, FrameSkippedReason)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 11777, 161.28)
- ('cc,benchmark', 'LayerTreeHostImpl::DidNotProduceFrame', 'X', 11771, 133.49)
- ('cc', 'DidNotSubmitInLastFrame', 'X', 11767, 180.77)
- ('cc', 'Scheduler::ScheduleBeginImplFrameDeadline', 'X', 11735, 25.54)
- ('cc,benchmark', 'Scheduler::OnBeginImplFrameDeadline', 'X', 10959, 18.06)
- ('cc', 'AnimationHost::TickAnimations', 'I', 7218, 0.0)
- ('cc', 'AnimationHost::TickAnimations', 'X', 4870, 5.67)
- ('blink', 'InlineNode::ShapeTextIncludingFirstLine', 'I', 2952, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 'I', 1374, 0.0)
- ('disabled-by-default-devtools.timeline', 'InvalidateLayout', 'I', 1032, 0.0)
- ('cc,benchmark', 'Scheduler::OnBeginImplFrameDeadline', 'I', 829, 0.0)
- ('blink', 'LocalFrameView::UpdateStyleAndLayout', 'X', 799, 129768.1)
- ('blink,blink_style', 'Document::updateStyle', 'X', 794, 74495.13)
- ('disabled-by-default-blink.debug', 'SelectorStats', 'X', 794, 84.32)
- ('blink,benchmark', 'LocalFrameView::RunStyleAndLayoutLifecyclePhases', 'X', 793, 129692.37)
- ('disabled-by-default-blink.debug', 'LocalFrameView::updateStyleAndLayoutIfNeededRecursive', 'X', 793, 129689.17)
- ('blink', 'Blink.Style.UpdateTime', 'X', 793, 84449.22)
- ('blink,devtools.timeline', 'UpdateLayoutTree', 'X', 793, 84360.15)
- ('blink', 'Document::updateActiveStyle', 'X', 680, 1.37)
- ('blink', 'RootScrollerController::PerformRootScrollerSelection', 'X', 607, 0.79)
- ('cc', 'ScrollTree::SetScrollOffset', 'X', 546, 0.96)
- ('cc', 'ScrollTree::SetScrollOffset', 'I', 546, 0.0)
- ('disabled-by-default-devtools.timeline', 'SetLayerTreeId', 'I', 539, 0.0)
- ('devtools.timeline', 'PrePaint', 'X', 539, 11732.38)
- ('blink,benchmark', 'LocalFrameView::RunCompositingInputsLifecyclePhase', 'X', 539, 10434.42)
- ('blink', 'Blink.CompositingInputs.UpdateTime', 'X', 539, 10433.16)
- ('blink,benchmark', 'LocalFrameView::RunPrePaintLifecyclePhase', 'X', 539, 1296.63)
- ('blink', 'Blink.PrePaint.UpdateTime', 'X', 539, 1295.27)
- ('blink,blink_style', 'Document::recalcStyle', 'X', 537, 71976.89)
- ('devtools.timeline', 'Paint', 'X', 536, 64.05)
- ('disabled-by-default-devtools.timeline', 'ScheduleStyleRecalculation', 'I', 525, 0.0)
- ('blink,devtools.timeline', 'HitTest', 'X', 518, 122.92)
- ('blink', 'Blink.Layout.UpdateTime', 'X', 516, 44511.25)
- ('blink,benchmark', 'LocalFrameView::layout', 'X', 516, 44504.71)
- ('devtools.timeline', 'Layout', 'X', 516, 44503.08)
- ('blink,benchmark,rail,disabled-by-default-blink.debug.layout', 'LocalFrameView::performLayout', 'X', 516, 44408.87)
- ('blink,benchmark', 'LocalFrameView::performPostLayoutTasks', 'X', 516, 2.37)
- ('blink', 'ResourceLoadPriorityOptimizer::UpdateImagePrioritiesAndSpeculativeDecodes', 'X', 444, 0.77)
- ('__metadata', 'ActiveProcesses', 'I', 399, 0.0)
- ('blink', 'LayoutView::commitPendingSelection', 'X', 390, 0.52)
- ('disabled-by-default-devtools.timeline', 'Commit', 'X', 279, 105.48)
- ('cc', 'LayerTreeHost::WaitForCommitCompletion', 'X', 279, 1.52)
- ('blink', 'LongTask', 'I', 279, 0.0)
- ('cc', 'LayerTreeHost::ApplyCompositorChanges', 'X', 278, 0.51)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'SendBeginMainFrameToCommit', 'b', 278, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'SendBeginMainFrameToCommit', 'e', 278, 0.0)
- ('blink', 'Blink.Animate.UpdateTime', 'X', 277, 13698.41)
- ('blink,rail', 'PageAnimator::serviceScriptedAnimations', 'X', 277, 13696.59)
- ('cc', 'auto cc::SchedulerStateMachine::SetNeedsBeginMainFrame(bool, bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 277, 0.64)
- ('blink', 'WebFrameWidgetImpl::UpdateLifecycle', 'X', 277, 176407.64)
- ('blink', 'LocalFrameView::WillStartLifecycleUpdate', 'X', 277, 0.45)
- ('blink,benchmark', 'LocalFrameView::NotifyResizeObservers', 'X', 277, 0.74)
- ('blink,benchmark', 'LocalFrameView::RunPaintLifecyclePhase', 'X', 277, 32060.38)
- ('blink', 'Blink.Paint.UpdateTime', 'X', 277, 169.98)
- ('blink', 'LocalFrameView::pushPaintArtifactToCompositor', 'X', 277, 17.49)
- ('blink', 'Blink.CompositingCommit.UpdateTime', 'X', 277, 17.08)
- ('devtools.timeline', 'Layerize', 'X', 277, 16.65)
- ('blink', 'LocalFrameView::DidFinishLifecycleUpdate', 'X', 277, 1.37)
- ('disabled-by-default-devtools.timeline', 'BeginCommitCompositorFrame', 'I', 277, 0.0)
- ('blink,benchmark', 'LocalFrameView::RunAccessibilitySteps', 'X', 277, 0.99)
- ('blink', 'Blink.Accessibility.UpdateTime', 'X', 277, 0.42)
- ('blink,benchmark', 'LocalFrameView::UpdateViewportIntersectionsForSubtree', 'X', 277, 0.85)
- ('devtools.timeline', 'AnimationFrame', 'b', 277, 0.0)
- ('devtools.timeline', 'AnimationFrame::Render', 'b', 277, 0.0)
- ('devtools.timeline', 'AnimationFrame::StyleAndLayout', 'b', 277, 0.0)
- ('devtools.timeline', 'AnimationFrame::StyleAndLayout', 'e', 277, 0.0)
- ('devtools.timeline', 'AnimationFrame::Render', 'e', 277, 0.0)
- ('devtools.timeline', 'AnimationFrame', 'e', 277, 0.0)
- ('cc', 'ProxyImpl::SetNeedsCommitOnImplThread', 'X', 276, 1.55)
- ('blink,benchmark', 'CullRectUpdate', 'X', 276, 92.97)
- ('cc,benchmark', 'ProxyImpl::ScheduledActionSendBeginMainFrame', 'X', 276, 2.19)
- ('cc,benchmark', 'SendBeginMainFrame', 'I', 276, 0.0)
- ('cc,benchmark', 'ProxyMain::BeginMainFrame', 'X', 276, 194431.97)
- ('blink', 'WebFrameWidgetImpl::BeginMainFrame', 'X', 276, 18783.96)
- ('cc,benchmark', 'SendBeginMainFrame', 's', 276, 0.0)
- ('cc,benchmark', 'SendBeginMainFrame', 'f', 276, 0.0)
- ('cc,benchmark', 'ProxyMain::BeginMainFrame', 's', 276, 0.0)
- ('cc,benchmark', 'ProxyMain::BeginMainFrame', 'f', 276, 0.0)
- ('devtools.timeline', 'AnimationFrame', 's', 276, 0.0)
- ('devtools.timeline', 'AnimationFrame', 'f', 276, 0.0)
- ('devtools.timeline', 'AnimationFrame::Presentation', 'n', 276, 0.0)
- ('cc', 'ProxyMain::SetNeedsAnimate', 'I', 275, 0.0)
- ('blink', 'Blink.IntersectionObservation.UpdateTime', 'X', 275, 0.46)
- ('blink', 'PaintArtifactCompositor::Update', 'X', 273, 15.7)
- ('blink,benchmark', 'PaintController::commitNewDisplayItems', 'X', 262, 0.71)
- ('blink', 'EventHandler::handleMouseMoveEvent', 'X', 261, 5138.26)
- ('blink', 'LayoutView::HitTest', 'X', 261, 5129.24)
- ('cc,raf_investigation', 'EarlyOut_NoUpdates', 'I', 258, 0.0)
- ('cc,benchmark', 'MainFrameAborted', 'X', 258, 5.93)
- ('cc', 'ProxyImpl::BeginMainFrameAbortedOnImplThread', 'X', 258, 35.9)
- ('cc', 'Scheduler::BeginMainFrameAborted', 'X', 258, 5.88)
- ('cc', 'Scheduler::NotifyBeginMainFrameStarted', 'X', 233, 0.31)
- ('blink', 'TimerBase::run', 'X', 230, 6.4)
- ('blink', 'LocalFrameView::UpdateLifecyclePhases - start of lifecycle tasks', 'X', 220, 0.28)
- ('cc', 'ScrollTree::CollectScrollDeltas', 'X', 220, 0.26)
- ('devtools.timeline,disabled-by-default-v8.gc', 'Sweeper::ConcurrentMajorSweeper Finished', 'I', 196, 0.0)
- ('blink', 'RootScrollerController::PerformRootScrollerSelection', 'I', 187, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_BACKGROUND_MARKING', 'X', 171, 38.72)