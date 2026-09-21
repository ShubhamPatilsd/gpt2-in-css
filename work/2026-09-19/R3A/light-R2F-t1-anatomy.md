# R3A anatomy — bench/runs/R2F/R2F-t1-trace.json.gz

main thread 91980/4194530; trace covers 192888.3 s; token bounds (s after trace start): [(1, 192707.0), (2, 192729.9), (3, 192754.1), (4, 192778.4), (5, 192803.6), (6, 192830.6), (7, 192858.3)]

## per-token phase self-time (ms)

| phase | tok 5 | tok 6 | mean |
|---|---:|---:|---:|
| wall | 25,129 | 27,060 | 26,094 |
| frames | 46 | 46 | 46.0 |
| style passes | 132 | 132 | 132.0 |
| style | 10,106 | 10,613 | 10,359 |
| layout | 5,315 | 5,850 | 5,583 |
| paintLC | 4,852 | 5,590 | 5,221 |
| animate | 1,790 | 1,853 | 1,821 |
| compinputs | 1,577 | 1,590 | 1,584 |
| UL-other | 1,177 | 1,215 | 1,196 |
| prepaint | 178 | 179 | 178 |
| task | 16 | 32 | 24 |
| hover | 18 | 19 | 18 |
| frame-other | 16 | 16 | 16 |

## token 5 — top names by self time within each phase (name, count, self ms)

- **style** 10,106 ms: Document::recalcStyle ×90 7,490.6; AnimationTimeline::serviceAnimations ×658499 772.9; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×2 666.5; style (self) ×132 528.1; Document::updateStyle ×132 384.2; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×12984 217.6; V8.GC_MC_INCREMENTAL ×13185 13.5; V8.GC_MARK_COMPACTOR ×1 10.5; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×1 9.8; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×2 3.4; Document::updateStyleInvalidationIfNeeded ×2 3.1; V8.GC_HEAP_EXTERNAL_PROLOGUE ×1 1.8; Document::rebuildLayoutTree ×2 1.2; LocalFrameView::ScheduleAnimation ×605 0.6
- **layout** 5,315 ms: LocalFrameView::performLayout ×87 3,209.7; InlineNode::ShapeTextIncludingFirstLine ×181060 2,004.0; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×5223 48.1; V8.GC_MARK_COMPACTOR ×1 18.6; layout (self) ×87 14.9; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×1 11.4; V8.GC_MC_INCREMENTAL ×5332 4.7; V8.GC_HEAP_EXTERNAL_PROLOGUE ×1 2.0; V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL ×1 0.9; V8.GC_MC_MARK ×1 0.6; V8.GC_MC_CLEAR_SWEEP_EXTERNAL_POINTER_TABLE ×1 0.1; V8.GC_MC_CLEAR_JOIN_JOB ×1 0.1; V8.GC_MC_MARK_EMBEDDER_TRACING ×3 0.1; V8.GC_MC_EVACUATE_UPDATE_POINTERS_POINTER_TABLES ×1 0.0
- **paintLC** 4,852 ms: paintLC (self) ×46 4,825.4; CullRectUpdate ×46 13.7; Paint ×90 5.0; Blink.Paint.UpdateTime ×46 4.7; PaintArtifactCompositor::Update ×46 1.8; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×38 0.6; Layerize ×46 0.1; ScrollTree::SetScrollOffset ×90 0.1; V8.GC_MC_INCREMENTAL ×39 0.1; PaintController::commitNewDisplayItems ×44 0.1; LocalFrameView::pushPaintArtifactToCompositor ×46 0.1; Blink.CompositingCommit.UpdateTime ×46 0.1; LocalFrameView::ScheduleAnimation ×4 0.0; auto cc::LayerTreeHost::SetNeedsCommit(bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const ×3 0.0
- **animate** 1,790 ms: PageAnimator::serviceScriptedAnimations ×46 1,210.2; AnimationTimeline::serviceAnimations ×457433 532.5; LocalFrameView::ScheduleAnimation ×42641 45.3; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×84 1.3; animate (self) ×46 0.5; V8.GC_MC_INCREMENTAL ×87 0.2; Blink.Animate.UpdateTime ×46 0.2; AsyncTask Run ×2 0.0; EventDispatch ×2 0.0; AsyncTask Scheduled ×2 0.0
- **compinputs** 1,577 ms: Blink.CompositingInputs.UpdateTime ×90 1,576.8; compinputs (self) ×90 0.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×3 0.1; LayoutView::commitPendingSelection ×65 0.1; V8.GC_MC_INCREMENTAL ×3 0.0
- **UL-other** 1,177 ms: UL-other (self) ×46 990.1; LocalFrameView::ScheduleAnimation ×108615 112.6; LocalFrameView::UpdateStyleAndLayout ×89 67.8; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×110 3.4; Blink.Layout.UpdateTime ×87 0.9; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×89 0.4; Blink.Style.UpdateTime ×88 0.4; LocalFrameView::layout ×87 0.2; LocalFrameView::performPostLayoutTasks ×87 0.2; LocalFrameView::DidFinishLifecycleUpdate ×46 0.2; V8.GC_MC_INCREMENTAL ×111 0.1; PrePaint ×46 0.1; LocalFrameView::NotifyResizeObservers ×44 0.1; ResourceLoadPriorityOptimizer::UpdateImagePrioritiesAndSpeculativeDecodes ×68 0.1
- **prepaint** 178 ms: Blink.PrePaint.UpdateTime ×90 177.3; prepaint (self) ×90 0.2; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×11 0.2; V8.GC_MC_INCREMENTAL ×11 0.0
- **hover** 18 ms: LocalFrameView::UpdateStyleAndLayout ×44 9.8; HitTest ×44 6.2; hover (self) ×44 1.2; LayoutView::HitTest ×44 0.3; Blink.Style.UpdateTime ×44 0.2; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×44 0.1; PrePaint ×44 0.1; RootScrollerController::PerformRootScrollerSelection ×26 0.0
- **task** 16 ms: RunTask ×343 15.2; TimerBase::run ×31 0.5; PageTimingMetricsSender::SendNow ×15 0.3; AsyncTask Run ×2 0.0; EventDispatch ×2 0.0
- **frame-other** 16 ms: HitTest ×38 11.7; Commit ×46 1.7; MainFrameAborted ×43 0.8; frame-other (self) ×46 0.5; LayerTreeHost::WaitForCommitCompletion ×46 0.3; OverlayInterstitialAdDetector::MaybeFireDetection ×19 0.1; AnimationHost::TickAnimations ×44 0.1; LayerTreeHost::ApplyCompositorChanges ×45 0.1; StickyAdDetector::MaybeFireDetection ×19 0.1; Blink.Accessibility.UpdateTime ×46 0.1; Blink.IntersectionObservation.UpdateTime ×45 0.1; LocalFrameView::RunAccessibilitySteps ×46 0.1; LocalFrameView::UpdateViewportIntersectionsForSubtree ×46 0.1; LayerTreeHost::DoUpdateLayers ×3 0.0

### token 5 — passes by elementCount (n, sum ms, mean ms; mean children self ms per pass)

- ec 1553: n 11, sum 2,198, mean 199.8: Document::recalcStyle ×1.0 185.9; AnimationTimeline::serviceAnimations ×4213.9 4.78; Document::updateStyle ×1.0 4.4; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×79.9 1.18; V8.GC_MC_INCREMENTAL ×80.7 0.11; LocalFrameView::ScheduleAnimation ×55.0 0.06; Document::rebuildLayoutTree ×0.1 0.04; Document::updateActiveStyle ×0.9 0.0 | inst {"AnimationTimeline::serviceAnimations": 7640.5, "LocalFrameView::ScheduleAnimation|Add": 14.9, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.8, "Document::updateActiveStyle": 0.1}
- ec 126: n 12, sum 1,389, mean 115.8: Document::recalcStyle ×1.0 100.05; AnimationTimeline::serviceAnimations ×4345.7 4.99; Document::updateStyle ×1.0 4.41; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×196.6 2.69; V8.GC_MC_INCREMENTAL ×199.5 0.2; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6520.8, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.9, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.2}
- ec 3089: n 12, sum 1,342, mean 111.8: Document::recalcStyle ×1.0 96.12; AnimationTimeline::serviceAnimations ×3847.8 4.37; Document::updateStyle ×1.0 4.36; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×269.8 3.5; V8.GC_MC_INCREMENTAL ×273.5 0.25; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 7018.7, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 3.8, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.2}
- ec 2323: n 10, sum 1,304, mean 130.4: Document::recalcStyle ×1.0 63.49; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×0.1 50.59; Document::updateStyle ×1.0 4.43; AnimationTimeline::serviceAnimations ×3760.3 4.31; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×140.2 4.05; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×0.1 0.17; V8.GC_MC_INCREMENTAL ×142.3 0.16; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×0.2 0.01; V8.GC_MC_INCREMENTAL_START ×0.1 0.01; V8.GC_MC_MARK_ROOTS ×0.1 0.0 | inst {"AnimationTimeline::serviceAnimations": 7106.2, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.3, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL": 0.2, "Document::updateActiveStyle": 0.1, "UpdateCounters": 0.1}
- ec 784: n 12, sum 1,285, mean 107.1: Document::recalcStyle ×1.0 88.82; AnimationTimeline::serviceAnimations ×4478.8 5.17; Document::updateStyle ×1.0 4.49; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×233.8 3.2; V8.GC_MARK_COMPACTOR ×0.1 0.87; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 0.81; V8.GC_MC_INCREMENTAL ×237.2 0.21; V8.GC_HEAP_EXTERNAL_PROLOGUE ×0.1 0.15; V8.GC_MC_MARK ×0.1 0.05; V8.GC_MC_MARK_EMBEDDER_TRACING ×0.1 0.01 | inst {"AnimationTimeline::serviceAnimations": 6387.7, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 3.3, "InvalidateLayout": 2.0, "ClearStringTableJob started": 0.5, "Document::updateActiveStyle": 0.3, "V8.GC_MC_MARK_EMBEDDER_TRACING": 0.2}
- ec 0: n 42, sum 605, mean 14.4: AnimationTimeline::serviceAnimations ×7167.5 8.67; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.0; V8.GC_MC_INCREMENTAL ×1.0 0.0; Document::updateActiveStyle ×0.9 0.0 | inst {"AnimationTimeline::serviceAnimations": 14547.2, "Document::updateActiveStyle": 0.1, "AnimationFrame::Presentation": 0.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.0}
- ec 50892: n 1, sum 527, mean 527.4: Document::recalcStyle ×1.0 321.31; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×1.0 160.53; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×417.0 22.06; AnimationTimeline::serviceAnimations ×8776.0 9.86; Document::updateStyle ×1.0 4.41; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×1.0 1.76; V8.GC_MC_INCREMENTAL ×444.0 0.68; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×2.0 0.05; V8.GC_MC_INCREMENTAL_START ×1.0 0.03; V8.GC_MC_MARK_ROOTS ×1.0 0.02 | inst {"AnimationTimeline::serviceAnimations": 12957.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 27.0, "Layer:deleted": 3.0, "InvalidateLayout": 2.0, "UpdateCounters": 1.0}
- ec 6919: n 12, sum 523, mean 43.6: Document::recalcStyle ×1.0 31.05; Document::updateStyle ×1.0 4.32; AnimationTimeline::serviceAnimations ×3600.1 4.06; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×58.4 0.95; V8.GC_MC_INCREMENTAL ×58.8 0.07; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 7266.4, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.4, "Document::updateActiveStyle": 0.2}
- ec 780: n 12, sum 392, mean 32.6: Document::recalcStyle ×1.0 19.79; Document::updateStyle ×1.0 4.45; AnimationTimeline::serviceAnimations ×3847.9 4.32; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×47.8 0.86; V8.GC_MC_INCREMENTAL ×48.8 0.05; Document::updateActiveStyle ×0.9 0.0 | inst {"AnimationTimeline::serviceAnimations": 7018.6, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.0, "Document::updateActiveStyle": 0.1}
- ec 2326: n 1, sum 205, mean 204.9: Document::recalcStyle ×1.0 198.4; Document::updateStyle ×1.0 5.26; Document::rebuildLayoutTree ×1.0 0.7; AnimationTimeline::serviceAnimations ×234.0 0.29; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 535.0, "InvalidateLayout": 2.0}
- ec 2342: n 1, sum 115, mean 114.9: Document::recalcStyle ×1.0 92.48; AnimationTimeline::serviceAnimations ×7698.0 8.61; Document::updateStyle ×1.0 4.44; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×212.0 3.25; V8.GC_MC_INCREMENTAL ×215.0 0.23 | inst {"AnimationTimeline::serviceAnimations": 14035.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 3.0, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 1.0}
- ec 2334: n 1, sum 92, mean 92.3: Document::recalcStyle ×1.0 84.69; Document::updateStyle ×1.0 4.28; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×229.0 2.87; V8.GC_MC_INCREMENTAL ×231.0 0.24 | inst {"V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.0, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 1.0}
- ec 863: n 1, sum 64, mean 64.3: Document::recalcStyle ×1.0 57.0; Document::updateStyle ×1.0 4.07; Document::updateStyleInvalidationIfNeeded ×1.0 1.56; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×124.0 1.29; V8.GC_MC_INCREMENTAL ×125.0 0.11; Document::updateActiveStyle ×1.0 0.0 | inst {"InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.0}
- ec 1: n 2, sum 32, mean 16.0: AnimationTimeline::serviceAnimations ×7677.5 9.78; Document::recalcStyle ×1.0 0.03; Document::updateStyle ×1.0 0.01; Document::updateActiveStyle ×0.5 0.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.01; V8.GC_MC_INCREMENTAL ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 14055.5, "AnimationFrame::Presentation": 1.0, "Document::updateActiveStyle": 0.5}
- ec 39: n 1, sum 24, mean 24.5: Document::recalcStyle ×1.0 18.52; Document::updateStyle ×1.0 4.09; Document::updateStyleInvalidationIfNeeded ×1.0 1.57; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×2.0 0.03; V8.GC_MC_INCREMENTAL ×2.0 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {"InvalidateLayout": 2.0}
- ec 6: n 1, sum 9, mean 8.6: Document::recalcStyle ×1.0 8.34; Document::updateStyle ×1.0 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {}

### token 5 — instants: {"AnimationTimeline::serviceAnimations": 1773788, "Animation": 123581, "LocalFrameView::ScheduleAnimation|Add": 20604, "LocalFrameView::ScheduleAnimation|ScheduleServiceOnNextFrame": 13745, "InlineNode::ShapeTextIncludingFirstLine": 524, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 322, "InvalidateLayout": 174, "ScrollTree::SetScrollOffset": 94, "SetLayerTreeId": 90, "ScheduleStyleRecalculation": 88, "BeginCommitCompositorFrame": 46, "LongTask": 46}

### token 5 — Animation b/e: {"b/running": 9545, "e/": 9232}; names: [('|e', 9232), ('--saved-N-N|b', 9228), ('--fc-vs-N-N|b', 144), ('--fc-ks-N-N|b', 144), ('--fc-k-N|b', 12), ('--fc-v-N|b', 12), ('native-handshake|b', 2), ('--saved-token-N|b', 1), ('--head-fvs|b', 1), ('--head-input-epoch|b', 1)]

### token 5 — head frame: 1,133 ms at 10,267 ms; phases {"frame-other": 0.69, "animate": 37.51, "hover": 0.38, "style": 822.66, "compinputs": 13.69, "prepaint": 2.6, "UL-other": 30.36, "layout": 81.21, "paintLC": 144.13}; passes [(0, 14.34), (1553, 186.0), (2323, 622.32)]; layouts [(1600, 30.61), (6943, 50.6)]
  top: {"frame-other": [["HitTest", 0.6], ["Commit", 0.04], ["MainFrameAborted", 0.02], ["frame-other (self)", 0.01], ["LayerTreeHost::WaitForCommitCompletion", 0.01], ["OverlayInterstitialAdDetector::MaybeFireDetection", 0.01]], "animate": [["PageAnimator::serviceScriptedAnimations", 24.98], ["AnimationTimeline::serviceAnimations", 11.79], ["LocalFrameView::ScheduleAnimation", 0.72], ["animate (self)", 0.01], ["Blink.Animate.UpdateTime", 0.0]], "hover": [["LocalFrameView::UpdateStyleAndLayout", 0.23], ["HitTest", 0.11], ["hover (self)", 0.03], ["LayoutView::HitTest", 0.01], ["LocalFrameView::RunStyleAndLayoutLifecyclePhases", 0.0], ["Blink.Style.UpdateTime", 0.0]], "style": [["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 505.93], ["Document::recalcStyle", 253.04], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 22.46], ["AnimationTimeline::serviceAnimations", 17.12], ["style (self)", 12.31], ["Document::updateStyle", 9.7]], "compinputs": [["Blink.CompositingInputs.UpdateTime", 13.68], ["compinputs (self)", 0.0], ["LayoutView::commitPendingSelection", 0.0]], "prepaint": [["Blink.PrePaint.UpdateTime", 2.6], ["prepaint (self)", 0.0]], "UL-other": [["UL-other (self)", 22.51], ["LocalFrameView::UpdateStyleAndLayout", 4.52], ["LocalFrameView::ScheduleAnimation", 3.25], ["Blink.Layout.UpdateTime", 0.03], ["LocalFrameView::RunStyleAndLayoutLifecyclePhases", 0.01], ["Blink.Style.UpdateTime", 0.01]], "layout": [["LocalFrameView::performLayout", 54.55], ["InlineNode::ShapeTextIncludingFirstLine", 21.15], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 5.05], ["layout (self)", 0.37], ["V8.GC_MC_INCREMENTAL", 0.08]], "paintLC": [["paintLC (self)", 143.8], ["Paint", 0.09], ["CullRectUpdate", 0.07], ["Blink.Paint.UpdateTime", 0.07], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.05], ["PaintArtifactCompositor::Update", 0.04]]}

### token 5 — frames

| # | t | dur | passes ec:ms | layouts dirty:ms | style | layout | paintLC | animate | compinputs | UL-other | prepaint | task | hover | frame-other | sa X | anim b/e |
|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 228 | 430 | 0:14 126:100 6919:49 | 339:62 8496:58 | 162 | 119 | 79 | 40 | 4 | 21 | 3 | 0 | 0 | 1 | 23438 | 26/0 |
| 1 | 662 | 357 | 0:14 780:25 3089:114 | 2344:19 9266:49 | 153 | 68 | 53 | 36 | 20 | 23 | 4 | 0 | 0 | 0 | 23189 | 0/0 |
| 2 | 1,020 | 697 | 0:14 784:93 1553:205 | 2359:56 1600:28 | 312 | 83 | 212 | 42 | 16 | 28 | 2 | 0 | 0 | 1 | 26013 | 769/769 |
| 3 | 1,719 | 549 | 0:14 2334:92 126:123 | 6944:40 339:63 | 230 | 103 | 135 | 40 | 13 | 25 | 3 | 0 | 0 | 0 | 26584 | 27/0 |
| 4 | 2,271 | 281 | 0:15 6919:37 780:40 | 8496:60 2344:19 | 92 | 79 | 36 | 37 | 8 | 24 | 4 | 0 | 0 | 0 | 24819 | 0/0 |
| 5 | 2,553 | 569 | 0:15 3089:105 784:110 | 9266:50 2359:56 | 230 | 106 | 118 | 39 | 43 | 27 | 4 | 0 | 0 | 1 | 25798 | 0/0 |
| 6 | 3,124 | 623 | 0:14 1553:189 2323:81 | 1600:29 6943:40 | 283 | 68 | 191 | 38 | 13 | 27 | 3 | 0 | 0 | 0 | 24632 | 769/769 |
| 7 | 3,749 | 432 | 0:14 126:104 6919:50 | 339:62 8496:57 | 168 | 120 | 78 | 37 | 4 | 21 | 3 | 0 | 0 | 1 | 22677 | 26/0 |
| 8 | 4,184 | 358 | 0:14 780:25 3089:116 | 2344:19 9266:50 | 155 | 69 | 52 | 35 | 20 | 22 | 4 | 0 | 0 | 0 | 22700 | 0/0 |
| 9 | 4,544 | 710 | 0:14 784:99 1553:204 | 2359:58 1600:28 | 317 | 86 | 217 | 44 | 16 | 27 | 2 | 0 | 0 | 1 | 25733 | 769/769 |
| 10 | 5,256 | 518 | 0:13 2323:68 126:120 | 6943:40 339:62 | 201 | 102 | 134 | 38 | 13 | 26 | 3 | 0 | 0 | 0 | 25549 | 26/0 |
| 11 | 5,777 | 276 | 0:14 6919:37 780:40 | 8496:59 2344:21 | 91 | 80 | 38 | 33 | 8 | 23 | 4 | 0 | 0 | 0 | 23370 | 0/0 |
| 12 | 6,054 | 610 | 0:18 3089:109 784:122 | 9266:55 2359:65 | 250 | 120 | 119 | 38 | 48 | 29 | 5 | 0 | 0 | 1 | 26852 | 0/0 |
| 13 | 6,666 | 681 | 0:15 1553:199 2323:92 | 1600:29 6943:45 | 307 | 75 | 206 | 46 | 13 | 32 | 3 | 0 | 0 | 0 | 27090 | 769/769 |
| 14 | 7,349 | 464 | 0:15 126:117 6919:55 | 339:64 8496:62 | 187 | 126 | 78 | 43 | 4 | 22 | 3 | 0 | 0 | 1 | 24042 | 26/0 |
| 15 | 7,817 | 375 | 0:14 780:28 3089:126 | 2344:20 9266:53 | 168 | 73 | 51 | 35 | 21 | 22 | 4 | 0 | 0 | 0 | 23770 | 0/0 |
| 16 | 8,193 | 717 | 0:14 784:103 1553:214 | 2359:58 1600:64 | 332 | 122 | 168 | 43 | 19 | 30 | 2 | 0 | 0 | 1 | 26148 | 769/769 |
| 17 | 8,911 | 537 | 0:15 2323:69 126:119 | 6943:41 339:67 | 203 | 107 | 133 | 47 | 13 | 29 | 3 | 0 | 0 | 0 | 28833 | 26/0 |
| 18 | 9,456 | 270 | 0:16 6919:33 780:37 | 8496:57 2344:17 | 85 | 74 | 38 | 36 | 8 | 24 | 4 | 0 | 1 | 0 | 24911 | 0/0 |
| 19 | 9,728 | 533 | 0:13 3089:89 784:99 | 9266:46 2359:54 | 201 | 100 | 119 | 36 | 43 | 28 | 4 | 0 | 0 | 1 | 24690 | 0/0 |
| 20 | 10,267 | 1,133 | 0:14 1553:186 2323:622 | 1600:31 6943:51 | 823 | 81 | 144 | 38 | 14 | 30 | 3 | 0 | 0 | 1 | 25445 | 769/769 |
| 21 | 11,402 | 441 | 0:16 126:104 6919:51 | 339:65 8496:57 | 171 | 122 | 77 | 42 | 4 | 22 | 3 | 0 | 0 | 0 | 24930 | 26/0 |
| 22 | 11,848 | 363 | 0:16 780:26 3089:116 | 2344:19 9266:50 | 158 | 69 | 52 | 37 | 20 | 23 | 4 | 0 | 0 | 0 | 24756 | 0/0 |
| 23 | 12,211 | 654 | 0:13 784:95 1553:202 | 2359:55 1600:27 | 310 | 83 | 173 | 43 | 16 | 27 | 2 | 0 | 0 | 1 | 25266 | 769/769 |
| 24 | 12,868 | 526 | 0:13 2323:66 126:127 | 6943:41 339:62 | 206 | 103 | 134 | 39 | 12 | 28 | 3 | 0 | 0 | 0 | 26447 | 26/0 |
| 25 | 13,397 | 273 | 0:13 6919:35 780:39 | 8496:61 2344:19 | 88 | 80 | 35 | 33 | 8 | 24 | 4 | 0 | 0 | 0 | 22568 | 0/0 |
| 26 | 13,671 | 580 | 0:15 3089:105 784:114 | 9266:51 2359:58 | 233 | 109 | 119 | 41 | 44 | 29 | 4 | 0 | 0 | 1 | 26494 | 0/0 |
| 27 | 14,253 | 584 | 0:14 1553:188 2323:81 | 1600:28 6943:40 | 283 | 69 | 147 | 41 | 12 | 30 | 3 | 0 | 0 | 0 | 25530 | 769/769 |
| 28 | 14,839 | 440 | 0:14 126:108 6919:51 | 339:64 8496:57 | 173 | 120 | 78 | 38 | 4 | 23 | 3 | 0 | 0 | 1 | 23899 | 26/0 |
| 29 | 15,284 | 370 | 0:15 780:25 3089:119 | 2344:20 9266:51 | 160 | 71 | 54 | 37 | 22 | 22 | 4 | 0 | 0 | 0 | 25285 | 0/0 |
| 30 | 15,655 | 698 | 0:14 784:97 1553:207 | 2359:62 1600:28 | 317 | 91 | 196 | 46 | 16 | 29 | 2 | 0 | 0 | 1 | 25895 | 769/769 |
| 31 | 16,356 | 533 | 0:14 2323:66 126:128 | 6943:45 339:63 | 208 | 108 | 135 | 38 | 13 | 28 | 3 | 0 | 0 | 0 | 26302 | 26/0 |
| 32 | 16,892 | 267 | 0:13 6919:36 780:39 | 8496:53 2344:20 | 88 | 74 | 38 | 35 | 7 | 21 | 4 | 0 | 0 | 0 | 22635 | 0/0 |
| 33 | 17,161 | 589 | 0:15 3089:105 784:115 | 9266:54 2359:60 | 235 | 114 | 120 | 40 | 44 | 30 | 4 | 0 | 0 | 1 | 26188 | 0/0 |
| 34 | 17,752 | 627 | 0:14 1553:195 2323:85 | 1600:29 6943:41 | 294 | 71 | 176 | 41 | 13 | 29 | 3 | 0 | 0 | 0 | 26121 | 769/769 |
| 35 | 18,381 | 441 | 0:14 126:113 6919:50 | 339:62 8496:56 | 177 | 118 | 77 | 41 | 3 | 21 | 3 | 0 | 0 | 1 | 23856 | 26/0 |
| 36 | 18,826 | 374 | 0:14 780:25 3089:121 | 2344:20 9266:55 | 161 | 76 | 54 | 35 | 21 | 24 | 4 | 0 | 0 | 0 | 24032 | 0/0 |
| 37 | 19,200 | 724 | 0:15 784:100 1553:208 | 2359:68 1600:30 | 323 | 98 | 211 | 43 | 17 | 29 | 2 | 0 | 0 | 1 | 25994 | 769/769 |
| 38 | 19,926 | 541 | 0:15 2323:73 126:127 | 6943:43 339:63 | 215 | 106 | 135 | 40 | 13 | 29 | 4 | 0 | 0 | 0 | 27304 | 26/0 |
| 39 | 20,470 | 284 | 0:15 6919:38 780:42 | 8496:58 2344:24 | 96 | 82 | 36 | 36 | 8 | 22 | 4 | 0 | 0 | 0 | 24574 | 0/0 |
| 40 | 20,756 | 624 | 0:14 3089:115 784:138 | 9266:62 2359:62 | 267 | 124 | 110 | 41 | 46 | 30 | 6 | 0 | 0 | 1 | 25202 | 0/0 |
| 41 | 21,382 | 3,273 | 0:16 2326:205 50892:527 | 2374:29 101162:1309 | 748 | 1338 | 212 | 45 | 861 | 32 | 37 | 0 | 0 | 0 | 29129 | 770/771 |
| 42 | 24,657 | 103 | 1:18 6:9 |  | 27 | 0 | 18 | 37 | 0 | 20 | 1 | 0 | 1 | 0 | 17544 | 0/1 |
| 43 | 24,761 | 104 | 39:24 | 7:9 | 24 | 9 | 18 | 33 | 0 | 20 | 1 | 0 | 0 | 0 | 8101 | 1/0 |
| 44 | 24,865 | 83 | 1:14 |  | 14 | 0 | 16 | 33 | 0 | 19 | 1 | 0 | 0 | 0 | 15262 | 0/1 |
| 45 | 24,949 | 409 | 863:64 2342:116 | 1571:80 6944:40 | 180 | 120 | 32 | 36 | 13 | 25 | 3 | 0 | 0 | 0 | 17121 | 2/0 |

## token 6 — top names by self time within each phase (name, count, self ms)

- **style** 10,613 ms: Document::recalcStyle ×90 7,862.0; AnimationTimeline::serviceAnimations ×677377 814.5; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×2 679.2; style (self) ×132 545.5; Document::updateStyle ×132 360.2; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×13443 220.1; V8.GC_MARK_COMPACTOR ×2 51.6; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×2 46.4; V8.GC_MC_INCREMENTAL ×13641 14.0; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×2 5.5; V8.GC_HEAP_EXTERNAL_PROLOGUE ×2 4.4; Document::updateStyleInvalidationIfNeeded ×2 3.1; V8.GC_MC_MARK ×2 1.6; V8.GC_MC_MARK_FULL_CLOSURE_PARALLEL ×2 1.2
- **layout** 5,850 ms: LocalFrameView::performLayout ×87 3,638.7; InlineNode::ShapeTextIncludingFirstLine ×190380 2,149.9; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×5181 41.1; layout (self) ×87 15.2; V8.GC_MC_INCREMENTAL ×5305 4.7
- **paintLC** 5,590 ms: paintLC (self) ×46 5,562.8; CullRectUpdate ×46 13.4; Paint ×90 5.0; Blink.Paint.UpdateTime ×46 4.9; PaintArtifactCompositor::Update ×46 1.9; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×36 0.8; Layerize ×46 0.1; ScrollTree::SetScrollOffset ×98 0.1; V8.GC_MC_INCREMENTAL ×36 0.1; PaintController::commitNewDisplayItems ×44 0.1; Blink.CompositingCommit.UpdateTime ×46 0.1; LocalFrameView::pushPaintArtifactToCompositor ×46 0.1; LocalFrameView::ScheduleAnimation ×4 0.0; auto cc::LayerTreeHost::SetNeedsCommit(bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const ×7 0.0
- **animate** 1,853 ms: PageAnimator::serviceScriptedAnimations ×46 1,258.1; AnimationTimeline::serviceAnimations ×460278 546.1; LocalFrameView::ScheduleAnimation ×42881 46.4; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×82 1.2; animate (self) ×46 0.5; Blink.Animate.UpdateTime ×46 0.3; V8.GC_MC_INCREMENTAL ×86 0.2; AsyncTask Run ×2 0.0; EventDispatch ×2 0.0; AsyncTask Scheduled ×2 0.0
- **compinputs** 1,590 ms: Blink.CompositingInputs.UpdateTime ×90 1,589.7; compinputs (self) ×90 0.2; LayoutView::commitPendingSelection ×54 0.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1 0.0; V8.GC_MC_INCREMENTAL ×1 0.0
- **UL-other** 1,215 ms: UL-other (self) ×46 1,016.1; LocalFrameView::ScheduleAnimation ×108852 114.2; LocalFrameView::UpdateStyleAndLayout ×89 74.8; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×106 7.2; Blink.Layout.UpdateTime ×87 1.0; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×89 0.4; Blink.Style.UpdateTime ×88 0.4; LocalFrameView::layout ×87 0.3; LocalFrameView::performPostLayoutTasks ×87 0.2; LocalFrameView::DidFinishLifecycleUpdate ×46 0.2; PrePaint ×46 0.1; V8.GC_MC_INCREMENTAL ×107 0.1; LocalFrameView::NotifyResizeObservers ×46 0.1; ResourceLoadPriorityOptimizer::UpdateImagePrioritiesAndSpeculativeDecodes ×74 0.1
- **prepaint** 179 ms: Blink.PrePaint.UpdateTime ×90 178.1; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×16 0.4; prepaint (self) ×90 0.2; V8.GC_MC_INCREMENTAL ×16 0.0
- **task** 32 ms: RunTask ×343 30.7; TimerBase::run ×34 0.5; PageTimingMetricsSender::SendNow ×15 0.4; AsyncTask Run ×2 0.0; EventDispatch ×2 0.0; AsyncTask Scheduled ×1 0.0
- **hover** 19 ms: LocalFrameView::UpdateStyleAndLayout ×44 10.1; HitTest ×44 6.6; hover (self) ×44 1.3; LayoutView::HitTest ×44 0.3; Blink.Style.UpdateTime ×44 0.2; LocalFrameView::RunStyleAndLayoutLifecyclePhases ×44 0.2; PrePaint ×44 0.1; RootScrollerController::PerformRootScrollerSelection ×31 0.0
- **frame-other** 16 ms: HitTest ×38 11.6; Commit ×46 1.8; MainFrameAborted ×43 0.7; frame-other (self) ×46 0.5; LayerTreeHost::WaitForCommitCompletion ×46 0.3; OverlayInterstitialAdDetector::MaybeFireDetection ×19 0.1; AnimationHost::TickAnimations ×42 0.1; StickyAdDetector::MaybeFireDetection ×19 0.1; LayerTreeHost::ApplyCompositorChanges ×46 0.1; Blink.IntersectionObservation.UpdateTime ×46 0.1; LocalFrameView::RunAccessibilitySteps ×46 0.1; LocalFrameView::UpdateViewportIntersectionsForSubtree ×46 0.1; Blink.Accessibility.UpdateTime ×45 0.1; LayerTreeHost::DoUpdateLayers ×3 0.0

### token 6 — passes by elementCount (n, sum ms, mean ms; mean children self ms per pass)

- ec 1553: n 11, sum 2,240, mean 203.7: Document::recalcStyle ×1.0 189.65; AnimationTimeline::serviceAnimations ×4389.7 5.02; Document::updateStyle ×1.0 4.03; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×80.2 1.21; V8.GC_MC_INCREMENTAL ×81.4 0.1; LocalFrameView::ScheduleAnimation ×54.5 0.06; Document::rebuildLayoutTree ×0.1 0.03; Document::updateActiveStyle ×0.5 0.0 | inst {"AnimationTimeline::serviceAnimations": 7464.6, "LocalFrameView::ScheduleAnimation|Add": 15.5, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 1.2, "Document::updateActiveStyle": 0.5}
- ec 126: n 12, sum 2,087, mean 173.9: Document::recalcStyle ×1.0 113.01; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×0.1 38.85; AnimationTimeline::serviceAnimations ×4442.1 5.17; Document::updateStyle ×1.0 4.35; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×185.8 3.99; V8.GC_MARK_COMPACTOR ×0.1 2.69; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 1.69; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×0.1 0.23; V8.GC_MC_INCREMENTAL ×187.1 0.2; V8.GC_HEAP_EXTERNAL_PROLOGUE ×0.1 0.18 | inst {"AnimationTimeline::serviceAnimations": 6360.3, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 3.1, "InvalidateLayout": 2.0, "ClearStringTableJob started": 0.7, "Document::updateActiveStyle": 0.2, "Major concurrent marking rescheduled": 0.1}
- ec 3089: n 12, sum 1,387, mean 115.6: Document::recalcStyle ×1.0 100.17; AnimationTimeline::serviceAnimations ×3917.8 4.57; Document::updateStyle ×1.0 4.03; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×243.8 3.33; V8.GC_MC_INCREMENTAL ×247.2 0.22; Blink.Style.UpdateTime ×0.1 0.0; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6948.7, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 3.4, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.2}
- ec 784: n 12, sum 1,300, mean 108.3: Document::recalcStyle ×1.0 92.46; AnimationTimeline::serviceAnimations ×4536.7 5.36; Document::updateStyle ×1.0 4.0; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×226.3 2.96; V8.GC_MC_INCREMENTAL ×228.3 0.2; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6265.8, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.0, "InvalidateLayout": 2.0, "Document::updateActiveStyle": 0.2}
- ec 2323: n 10, sum 840, mean 84.0: Document::recalcStyle ×1.0 64.85; AnimationTimeline::serviceAnimations ×3896.6 4.58; Document::updateStyle ×1.0 4.02; V8.GC_HEAP_EMBEDDER_TRACING_EPILOGUE ×0.1 2.62; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×140.2 2.25; V8.GC_MARK_COMPACTOR ×0.1 1.93; V8.GC_HEAP_EXTERNAL_PROLOGUE ×0.1 0.22; V8.GC_MC_INCREMENTAL ×142.7 0.14; V8.GC_MC_MARK ×0.1 0.08; V8.GC_MC_CLEAR_SWEEP_EXTERNAL_POINTER_TABLE ×0.1 0.01 | inst {"AnimationTimeline::serviceAnimations": 6969.9, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 2.7, "InvalidateLayout": 2.0, "ClearStringTableJob started": 0.5, "V8.GC_MC_INCREMENTAL": 0.2, "Document::updateActiveStyle": 0.2}
- ec 0: n 42, sum 635, mean 15.1: AnimationTimeline::serviceAnimations ×7409.1 9.17; Document::updateStyle ×1.0 0.01; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.0; V8.GC_MC_INCREMENTAL ×1.0 0.0; Document::updateActiveStyle ×0.9 0.0 | inst {"AnimationTimeline::serviceAnimations": 14269.0, "Document::updateActiveStyle": 0.1, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.0, "AnimationFrame::Presentation": 0.0}
- ec 50892: n 1, sum 619, mean 619.2: Document::recalcStyle ×1.0 349.79; V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED ×1.0 213.05; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1447.0 30.78; AnimationTimeline::serviceAnimations ×8526.0 10.1; Document::updateStyle ×1.0 4.02; V8.GC_MC_INCREMENTAL_EXTERNAL_PROLOGUE ×1.0 2.75; V8.GC_MC_INCREMENTAL ×1481.0 1.87; V8.GC_MC_MARK_EMBEDDER_PROLOGUE ×2.0 0.11; V8.GC_MC_INCREMENTAL_START ×1.0 0.09; V8.GC_MC_COMPLETE_SWEEPING ×1.0 0.02 | inst {"AnimationTimeline::serviceAnimations": 13207.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 34.0, "InvalidateLayout": 2.0, "V8.GC_MC_SWEEP": 1.0, "Layer:deleted": 1.0, "UpdateCounters": 1.0}
- ec 6919: n 12, sum 552, mean 46.0: Document::recalcStyle ×1.0 32.64; AnimationTimeline::serviceAnimations ×3869.4 4.47; Document::updateStyle ×1.0 4.47; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×55.3 0.93; V8.GC_MC_INCREMENTAL ×55.5 0.07; Document::updateActiveStyle ×0.8 0.0 | inst {"AnimationTimeline::serviceAnimations": 6997.1, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.2, "Document::updateActiveStyle": 0.2}
- ec 780: n 12, sum 418, mean 34.8: Document::recalcStyle ×1.0 21.89; AnimationTimeline::serviceAnimations ×3902.9 4.7; Document::updateStyle ×1.0 4.06; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×44.0 0.79; V8.GC_MC_INCREMENTAL ×44.5 0.04; Document::updateActiveStyle ×0.6 0.0 | inst {"AnimationTimeline::serviceAnimations": 6899.5, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 0.5, "Document::updateActiveStyle": 0.4}
- ec 2326: n 1, sum 206, mean 205.6: Document::recalcStyle ×1.0 200.6; Document::updateStyle ×1.0 3.73; Document::rebuildLayoutTree ×1.0 0.79; AnimationTimeline::serviceAnimations ×203.0 0.21; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 566.0, "InvalidateLayout": 2.0}
- ec 2342: n 1, sum 116, mean 115.6: Document::recalcStyle ×1.0 91.08; AnimationTimeline::serviceAnimations ×8484.0 9.56; Document::updateStyle ×1.0 4.83; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×254.0 3.16; V8.GC_MC_INCREMENTAL ×260.0 0.24; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 13249.0, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 6.0, "InvalidateLayout": 2.0}
- ec 2334: n 1, sum 93, mean 92.9: Document::recalcStyle ×1.0 83.72; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×224.0 4.6; Document::updateStyle ×1.0 3.92; V8.GC_MC_INCREMENTAL ×229.0 0.25; Document::updateActiveStyle ×1.0 0.0 | inst {"V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 5.0, "InvalidateLayout": 2.0}
- ec 863: n 1, sum 64, mean 63.8: Document::recalcStyle ×1.0 56.19; Document::updateStyle ×1.0 4.02; Document::updateStyleInvalidationIfNeeded ×1.0 1.58; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×126.0 1.5; V8.GC_MC_INCREMENTAL ×129.0 0.17; Document::updateActiveStyle ×1.0 0.0 | inst {"V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 4.0, "InvalidateLayout": 2.0, "V8.GC_MC_INCREMENTAL": 1.0}
- ec 1: n 2, sum 28, mean 14.2: AnimationTimeline::serviceAnimations ×6850.5 8.57; Document::recalcStyle ×1.0 0.03; Document::updateStyle ×1.0 0.03; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.5 0.01; V8.GC_MC_INCREMENTAL ×1.5 0.0; Document::updateActiveStyle ×1.0 0.0 | inst {"AnimationTimeline::serviceAnimations": 14882.5, "AnimationFrame::Presentation": 1.0}
- ec 39: n 1, sum 22, mean 21.8: Document::recalcStyle ×1.0 16.33; Document::updateStyle ×1.0 3.74; Document::updateStyleInvalidationIfNeeded ×1.0 1.52; V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING ×1.0 0.01; V8.GC_MC_INCREMENTAL ×1.0 0.01 | inst {"InvalidateLayout": 2.0, "Document::updateActiveStyle": 1.0}
- ec 6: n 1, sum 8, mean 7.7: Document::recalcStyle ×1.0 7.47; Document::updateStyle ×1.0 0.01; Document::updateActiveStyle ×1.0 0.0 | inst {}

### token 6 — instants: {"AnimationTimeline::serviceAnimations": 1746682, "Animation": 123724, "LocalFrameView::ScheduleAnimation|Add": 20488, "LocalFrameView::ScheduleAnimation|ScheduleServiceOnNextFrame": 13605, "InlineNode::ShapeTextIncludingFirstLine": 420, "V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING": 338, "InvalidateLayout": 174, "SetLayerTreeId": 90, "ScheduleStyleRecalculation": 88, "ScrollTree::SetScrollOffset": 86, "BeginCommitCompositorFrame": 46, "LongTask": 46}

### token 6 — Animation b/e: {"b/running": 9545, "e/": 9232}; names: [('|e', 9232), ('--saved-N-N|b', 9228), ('--fc-vs-N-N|b', 144), ('--fc-ks-N-N|b', 144), ('--fc-k-N|b', 12), ('--fc-v-N|b', 12), ('native-handshake|b', 2), ('--saved-token-N|b', 1), ('--head-fvs|b', 1), ('--head-input-epoch|b', 1)]

### token 6 — head frame: 1,046 ms at 9,510 ms; phases {"frame-other": 0.73, "animate": 38.44, "hover": 0.41, "style": 710.18, "compinputs": 12.35, "prepaint": 2.74, "UL-other": 27.22, "layout": 118.91, "paintLC": 135.19}; passes [(0, 14.07), (2323, 63.38), (126, 632.73)]; layouts [(6943, 46.78), (339, 72.13)]
  top: {"frame-other": [["HitTest", 0.62], ["Commit", 0.06], ["MainFrameAborted", 0.02], ["frame-other (self)", 0.02], ["StickyAdDetector::MaybeFireDetection", 0.01], ["LayerTreeHost::WaitForCommitCompletion", 0.01]], "animate": [["PageAnimator::serviceScriptedAnimations", 25.27], ["AnimationTimeline::serviceAnimations", 12.44], ["LocalFrameView::ScheduleAnimation", 0.7], ["animate (self)", 0.01], ["Blink.Animate.UpdateTime", 0.0]], "hover": [["LocalFrameView::UpdateStyleAndLayout", 0.21], ["HitTest", 0.14], ["hover (self)", 0.03], ["LayoutView::HitTest", 0.01], ["LocalFrameView::RunStyleAndLayoutLifecyclePhases", 0.0], ["Blink.Style.UpdateTime", 0.0]], "style": [["V8.GC_HEAP_ENSURE_SWEEPING_COMPLETED", 466.18], ["Document::recalcStyle", 183.04], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 19.74], ["AnimationTimeline::serviceAnimations", 18.23], ["style (self)", 11.78], ["Document::updateStyle", 7.92]], "compinputs": [["Blink.CompositingInputs.UpdateTime", 12.35], ["compinputs (self)", 0.0], ["LayoutView::commitPendingSelection", 0.0]], "prepaint": [["Blink.PrePaint.UpdateTime", 2.73], ["prepaint (self)", 0.0]], "UL-other": [["UL-other (self)", 22.47], ["LocalFrameView::ScheduleAnimation", 3.97], ["LocalFrameView::UpdateStyleAndLayout", 0.71], ["Blink.Layout.UpdateTime", 0.02], ["LocalFrameView::layout", 0.01], ["LocalFrameView::RunStyleAndLayoutLifecyclePhases", 0.01]], "layout": [["LocalFrameView::performLayout", 96.96], ["InlineNode::ShapeTextIncludingFirstLine", 21.68], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.13], ["layout (self)", 0.13], ["V8.GC_MC_INCREMENTAL", 0.01]], "paintLC": [["paintLC (self)", 134.64], ["V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING", 0.26], ["Paint", 0.09], ["CullRectUpdate", 0.08], ["Blink.Paint.UpdateTime", 0.07], ["PaintArtifactCompositor::Update", 0.04]]}

### token 6 — frames

| # | t | dur | passes ec:ms | layouts dirty:ms | style | layout | paintLC | animate | compinputs | UL-other | prepaint | task | hover | frame-other | sa X | anim b/e |
|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 229 | 475 | 0:14 126:112 6919:52 | 339:74 10032:71 | 178 | 145 | 79 | 41 | 4 | 23 | 3 | 0 | 0 | 1 | 24489 | 26/0 |
| 1 | 708 | 371 | 0:15 780:25 3089:118 | 2344:20 9266:52 | 158 | 73 | 54 | 38 | 21 | 23 | 4 | 0 | 0 | 0 | 23861 | 0/0 |
| 2 | 1,080 | 733 | 0:15 784:96 1553:209 | 2359:63 1600:29 | 320 | 92 | 226 | 46 | 16 | 30 | 2 | 0 | 0 | 1 | 26543 | 769/769 |
| 3 | 1,816 | 576 | 0:16 2334:93 126:132 | 6944:43 339:72 | 241 | 115 | 134 | 42 | 13 | 27 | 3 | 0 | 0 | 0 | 28773 | 27/0 |
| 4 | 2,395 | 284 | 0:14 6919:37 780:40 | 10032:65 2344:21 | 90 | 86 | 37 | 37 | 8 | 22 | 4 | 0 | 0 | 0 | 22940 | 0/0 |
| 5 | 2,681 | 596 | 0:17 3089:105 784:112 | 9266:57 2359:67 | 234 | 123 | 121 | 38 | 45 | 28 | 4 | 0 | 0 | 1 | 25934 | 0/0 |
| 6 | 3,279 | 653 | 0:14 1553:197 2323:85 | 1600:30 6943:46 | 296 | 76 | 194 | 41 | 13 | 30 | 3 | 0 | 0 | 0 | 26051 | 769/769 |
| 7 | 3,934 | 486 | 0:14 126:117 6919:54 | 339:75 10032:72 | 185 | 148 | 82 | 39 | 5 | 23 | 3 | 0 | 0 | 1 | 23698 | 26/0 |
| 8 | 4,424 | 395 | 0:15 780:27 3089:127 | 2344:24 9266:57 | 169 | 81 | 53 | 42 | 21 | 23 | 4 | 0 | 0 | 0 | 23862 | 0/0 |
| 9 | 4,820 | 743 | 0:17 784:102 1553:208 | 2359:64 1600:29 | 326 | 93 | 227 | 48 | 16 | 30 | 2 | 0 | 0 | 1 | 27521 | 769/769 |
| 10 | 5,566 | 575 | 0:14 2323:69 126:138 | 6943:50 339:85 | 221 | 135 | 135 | 40 | 13 | 28 | 3 | 0 | 0 | 0 | 26539 | 26/0 |
| 11 | 6,145 | 307 | 0:15 6919:39 780:42 | 10032:74 2344:25 | 97 | 99 | 37 | 38 | 9 | 23 | 4 | 0 | 0 | 0 | 24583 | 0/0 |
| 12 | 6,454 | 615 | 0:14 3089:114 784:123 | 9266:61 2359:65 | 250 | 126 | 119 | 39 | 46 | 30 | 5 | 0 | 0 | 1 | 25904 | 0/0 |
| 13 | 7,071 | 678 | 0:15 1553:199 2323:92 | 1600:30 6943:45 | 306 | 75 | 205 | 41 | 13 | 35 | 3 | 0 | 0 | 0 | 26400 | 769/769 |
| 14 | 7,751 | 596 | 0:16 126:176 6919:61 | 339:90 10032:80 | 254 | 170 | 93 | 41 | 6 | 27 | 4 | 0 | 0 | 1 | 25720 | 26/0 |
| 15 | 8,357 | 410 | 0:19 780:32 3089:121 | 2344:26 9266:61 | 172 | 86 | 55 | 45 | 21 | 25 | 4 | 0 | 1 | 0 | 28226 | 0/0 |
| 16 | 8,773 | 730 | 0:14 784:87 1553:206 | 2359:64 1600:29 | 307 | 94 | 238 | 44 | 17 | 29 | 2 | 0 | 0 | 1 | 26461 | 769/769 |
| 17 | 9,510 | 1,046 | 0:14 2323:63 126:633 | 6943:47 339:72 | 710 | 119 | 135 | 38 | 12 | 27 | 3 | 0 | 0 | 1 | 26196 | 26/0 |
| 18 | 10,560 | 292 | 0:13 6919:36 780:42 | 10032:68 2344:23 | 91 | 91 | 37 | 35 | 8 | 26 | 4 | 0 | 0 | 0 | 23298 | 0/0 |
| 19 | 10,855 | 592 | 0:16 3089:104 784:114 | 9266:57 2359:63 | 234 | 120 | 121 | 39 | 44 | 30 | 4 | 0 | 0 | 0 | 26109 | 0/0 |
| 20 | 11,449 | 670 | 0:15 1553:195 2323:81 | 1600:29 6943:47 | 291 | 76 | 209 | 45 | 13 | 32 | 3 | 0 | 0 | 1 | 25841 | 769/769 |
| 21 | 12,121 | 473 | 0:14 126:117 6919:52 | 339:74 10032:68 | 183 | 143 | 80 | 39 | 4 | 21 | 3 | 0 | 0 | 0 | 24035 | 26/0 |
| 22 | 12,599 | 381 | 0:15 780:26 3089:122 | 2344:21 9266:53 | 162 | 74 | 54 | 41 | 21 | 24 | 4 | 0 | 0 | 0 | 24898 | 0/0 |
| 23 | 12,981 | 782 | 0:14 784:97 1553:212 | 2359:68 1600:28 | 323 | 96 | 270 | 45 | 16 | 27 | 2 | 0 | 0 | 1 | 26720 | 769/769 |
| 24 | 13,765 | 555 | 0:16 2323:71 126:132 | 6943:45 339:73 | 218 | 118 | 134 | 41 | 13 | 28 | 3 | 0 | 0 | 0 | 27455 | 26/0 |
| 25 | 14,325 | 296 | 0:14 6919:41 780:41 | 10032:69 2344:20 | 97 | 89 | 38 | 35 | 8 | 25 | 4 | 0 | 0 | 0 | 23860 | 0/0 |
| 26 | 14,624 | 616 | 0:15 3089:108 784:121 | 9266:70 2359:63 | 243 | 133 | 120 | 40 | 45 | 30 | 4 | 0 | 0 | 1 | 26749 | 0/0 |
| 27 | 15,242 | 696 | 0:14 1553:194 2323:85 | 1600:30 6943:43 | 294 | 73 | 243 | 42 | 13 | 29 | 3 | 0 | 0 | 0 | 26628 | 769/769 |
| 28 | 15,940 | 485 | 0:16 126:121 6919:52 | 339:75 10032:70 | 190 | 145 | 79 | 42 | 4 | 20 | 3 | 0 | 0 | 1 | 25158 | 26/0 |
| 29 | 16,430 | 380 | 0:15 780:26 3089:124 | 2344:22 9266:55 | 165 | 76 | 53 | 38 | 21 | 23 | 4 | 0 | 0 | 0 | 24974 | 0/0 |
| 30 | 16,811 | 793 | 0:15 784:101 1553:209 | 2359:63 1600:30 | 326 | 92 | 281 | 46 | 16 | 28 | 2 | 0 | 0 | 1 | 26847 | 769/769 |
| 31 | 17,607 | 573 | 0:15 2323:70 126:146 | 6943:47 339:76 | 230 | 123 | 134 | 41 | 13 | 28 | 3 | 0 | 0 | 0 | 27378 | 26/0 |
| 32 | 18,184 | 298 | 0:15 6919:39 780:40 | 10032:74 2344:23 | 94 | 96 | 39 | 35 | 9 | 21 | 4 | 0 | 0 | 0 | 23338 | 0/0 |
| 33 | 18,484 | 612 | 0:15 3089:114 784:121 | 9266:57 2359:65 | 250 | 122 | 119 | 40 | 45 | 30 | 4 | 0 | 0 | 1 | 26033 | 0/0 |
| 34 | 19,098 | 721 | 0:14 1553:195 2323:93 | 1600:30 6943:46 | 302 | 76 | 257 | 39 | 13 | 30 | 3 | 0 | 0 | 0 | 25509 | 769/769 |
| 35 | 19,821 | 503 | 0:14 126:129 6919:53 | 339:76 10032:76 | 196 | 153 | 79 | 43 | 5 | 23 | 3 | 0 | 0 | 1 | 23492 | 26/0 |
| 36 | 20,328 | 405 | 0:15 780:28 3089:132 | 2344:23 9266:63 | 175 | 86 | 55 | 38 | 21 | 24 | 4 | 0 | 0 | 0 | 24043 | 0/0 |
| 37 | 20,734 | 831 | 0:15 784:117 1553:216 | 2359:64 1600:30 | 348 | 94 | 294 | 43 | 17 | 31 | 2 | 0 | 0 | 1 | 26318 | 769/769 |
| 38 | 21,568 | 647 | 0:16 2323:129 126:135 | 6943:48 339:87 | 280 | 135 | 143 | 44 | 14 | 27 | 4 | 0 | 0 | 0 | 28332 | 26/0 |
| 39 | 22,220 | 325 | 0:16 6919:35 780:49 | 10032:81 2344:22 | 101 | 103 | 39 | 41 | 9 | 27 | 4 | 0 | 1 | 0 | 26086 | 0/0 |
| 40 | 22,552 | 568 | 0:17 3089:98 784:111 | 9266:51 2359:64 | 226 | 115 | 109 | 41 | 44 | 27 | 4 | 0 | 0 | 1 | 26677 | 0/0 |
| 41 | 23,127 | 3,455 | 0:16 2326:206 50892:619 | 2374:30 101162:1320 | 841 | 1350 | 293 | 39 | 859 | 35 | 37 | 0 | 0 | 0 | 27758 | 770/771 |
| 42 | 26,584 | 98 | 1:15 6:8 |  | 23 | 0 | 15 | 37 | 0 | 21 | 1 | 0 | 1 | 0 | 15851 | 0/1 |
| 43 | 26,682 | 102 | 39:22 | 7:8 | 22 | 8 | 16 | 34 | 1 | 21 | 1 | 0 | 0 | 0 | 8574 | 1/0 |
| 44 | 26,784 | 87 | 1:13 |  | 13 | 0 | 19 | 35 | 0 | 18 | 1 | 0 | 0 | 0 | 14685 | 0/1 |
| 45 | 26,871 | 422 | 863:64 2342:115 | 1571:88 6944:45 | 179 | 133 | 33 | 36 | 14 | 25 | 3 | 0 | 0 | 0 | 16972 | 2/0 |

## inventory (cat, name, ph, count, sum ms) — top 120

- ('blink', 'AnimationTimeline::serviceAnimations', 'I', 14162752, 0.0)
- ('blink', 'AnimationTimeline::serviceAnimations', 'X', 8974644, 10443.88)
- ('blink', 'InlineNode::ShapeTextIncludingFirstLine', 'X', 1426223, 15938.71)
- ('cc', 'LocalFrameView::ScheduleAnimation', 'X', 1221885, 1280.49)
- ('blink.animations,devtools.timeline,benchmark,rail', 'Animation', 'n', 998220, 0.0)
- ('cc', 'LocalFrameView::ScheduleAnimation', 'I', 278750, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL', 's', 143054, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL', 'f', 143054, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL', 'X', 142974, 2390.57)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 'X', 140741, 2246.88)
- ('disabled-by-default-devtools.timeline', 'RunTask', 'X', 127428, 209061.8)
- ('blink.animations,devtools.timeline,benchmark,rail', 'Animation', 'b', 86432, 0.0)
- ('blink.animations,devtools.timeline,benchmark,rail', 'Animation', 'e', 72318, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'PipelineReporter', 'b', 13174, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'BeginImplFrameToSendBeginMainFrame', 'b', 13174, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'BeginImplFrameToSendBeginMainFrame', 'e', 13174, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'PipelineReporter', 'e', 13174, 0.0)
- ('cc', 'auto cc::SchedulerStateMachine::ShouldThrottleSendBeginMainFrame()::(lambda)::operator()(uint32_t) const', 'I', 13028, 0.0)
- ('cc,benchmark', 'Scheduler::BeginFrame', 'X', 12559, 142.29)
- ('cc,benchmark', 'Scheduler::BeginImplFrame', 'X', 12530, 102.43)
- ('cc', 'auto cc::Scheduler::SendDidNotProduceFrame(const viz::BeginFrameArgs &, FrameSkippedReason)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 12511, 143.05)
- ('cc', 'auto cc::Scheduler::FinishImplFrame()::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 12502, 174.89)
- ('cc,benchmark', 'LayerTreeHostImpl::DidNotProduceFrame', 'X', 12453, 119.4)
- ('cc', 'DidNotSubmitInLastFrame', 'X', 12390, 154.93)
- ('cc', 'Scheduler::ScheduleBeginImplFrameDeadline', 'X', 12371, 22.04)
- ('disabled-by-default-devtools.timeline', 'RunTask', 'I', 11480, 0.0)
- ('cc,benchmark', 'Scheduler::OnBeginImplFrameDeadline', 'X', 10612, 14.85)
- ('cc', 'AnimationHost::TickAnimations', 'I', 7906, 0.0)
- ('blink', 'InlineNode::ShapeTextIncludingFirstLine', 'I', 6817, 0.0)
- ('cc', 'AnimationHost::TickAnimations', 'X', 5266, 6.1)
- ('devtools.timeline', 'ResourceReceivedData', 'I', 3220, 0.0)
- ('devtools.timeline,disabled-by-default-v8.gc', 'V8.GC_MC_INCREMENTAL_EMBEDDER_TRACING', 'I', 2313, 0.0)
- ('cc,benchmark', 'Scheduler::OnBeginImplFrameDeadline', 'I', 1918, 0.0)
- ('disabled-by-default-devtools.timeline', 'InvalidateLayout', 'I', 1430, 0.0)
- ('blink', 'LocalFrameView::UpdateStyleAndLayout', 'X', 1173, 128065.32)
- ('blink,benchmark', 'LocalFrameView::RunStyleAndLayoutLifecyclePhases', 'X', 1109, 127886.7)
- ('blink,blink_style', 'Document::updateStyle', 'X', 1097, 72915.11)
- ('blink', 'Blink.Style.UpdateTime', 'X', 1096, 83390.31)
- ('blink,devtools.timeline', 'UpdateLayoutTree', 'X', 1096, 83385.71)
- ('blink', 'Document::updateActiveStyle', 'X', 859, 18.05)
- ('cc', 'ScrollTree::SetScrollOffset', 'X', 789, 1.05)
- ('disabled-by-default-devtools.timeline', 'SetLayerTreeId', 'I', 763, 0.0)
- ('devtools.timeline', 'PrePaint', 'X', 763, 13963.29)
- ('blink,benchmark', 'LocalFrameView::RunCompositingInputsLifecyclePhase', 'X', 763, 12536.61)
- ('blink', 'Blink.CompositingInputs.UpdateTime', 'X', 763, 12535.29)
- ('blink,benchmark', 'LocalFrameView::RunPrePaintLifecyclePhase', 'X', 763, 1425.0)
- ('blink', 'Blink.PrePaint.UpdateTime', 'X', 763, 1423.37)
- ('blink', 'RootScrollerController::PerformRootScrollerSelection', 'X', 755, 0.83)
- ('devtools.timeline', 'Paint', 'X', 754, 70.63)
- ('cc', 'ScrollTree::SetScrollOffset', 'I', 752, 0.0)
- ('blink,blink_style', 'Document::recalcStyle', 'X', 747, 70085.27)
- ('disabled-by-default-devtools.timeline', 'ScheduleStyleRecalculation', 'I', 739, 0.0)
- ('blink', 'Blink.Layout.UpdateTime', 'X', 718, 43864.13)
- ('blink,benchmark', 'LocalFrameView::layout', 'X', 718, 43856.43)
- ('devtools.timeline', 'Layout', 'X', 718, 43854.58)
- ('blink,benchmark,rail,disabled-by-default-blink.debug.layout', 'LocalFrameView::performLayout', 'X', 718, 43735.31)
- ('blink,benchmark', 'LocalFrameView::performPostLayoutTasks', 'X', 718, 2.41)
- ('blink,devtools.timeline', 'HitTest', 'X', 664, 140.28)
- ('cc', 'ScheduledTasksState', 'n', 660, 0.0)
- ('blink', 'ResourceLoadPriorityOptimizer::UpdateImagePrioritiesAndSpeculativeDecodes', 'X', 592, 0.7)
- ('loading', 'CorsURLLoader::HandleComplete', 'X', 582, 17.53)
- ('loading', 'CorsURLLoader::~CorsURLLoader', 'X', 582, 2.62)
- ('loading', 'CorsURLLoader::HandleComplete', 's', 582, 0.0)
- ('loading', 'CorsURLLoader::HandleComplete', 'f', 582, 0.0)
- ('loading', 'CorsURLLoader::~CorsURLLoader', 's', 582, 0.0)
- ('loading', 'CorsURLLoader::~CorsURLLoader', 'f', 582, 0.0)
- ('loading', 'CorsURLLoaderFactory::CreateLoaderAndStart', 'X', 579, 37.81)
- ('loading', 'CorsURLLoader::Start', 'X', 579, 28.79)
- ('loading', 'CorsURLLoader::StartRequest', 'X', 579, 28.48)
- ('loading', 'CorsURLLoader::StartNetworkRequest', 'X', 579, 27.78)
- ('loading', 'URLLoader::URLLoader', 'X', 579, 21.12)
- ('loading', 'URLLoader::ScheduleStart', 'X', 579, 16.48)
- ('loading', 'CorsURLLoader::CorsURLLoader', 's', 579, 0.0)
- ('loading', 'CorsURLLoader::CorsURLLoader', 'f', 579, 0.0)
- ('loading', 'CorsURLLoader::Start', 's', 579, 0.0)
- ('loading', 'CorsURLLoader::Start', 'f', 579, 0.0)
- ('loading', 'CorsURLLoader::StartRequest', 's', 579, 0.0)
- ('loading', 'CorsURLLoader::StartRequest', 'f', 579, 0.0)
- ('loading', 'CorsURLLoader::StartNetworkRequest', 's', 579, 0.0)
- ('loading', 'CorsURLLoader::StartNetworkRequest', 'f', 579, 0.0)
- ('loading', 'URLLoader::URLLoader', 's', 579, 0.0)
- ('loading', 'URLLoader::URLLoader', 'f', 579, 0.0)
- ('loading', 'URLLoader::ScheduleStart', 's', 579, 0.0)
- ('loading', 'URLLoader::ScheduleStart', 'f', 579, 0.0)
- ('loading', 'CorsURLLoaderFactory::CreateLoaderAndStart', 's', 575, 0.0)
- ('loading', 'CorsURLLoaderFactory::CreateLoaderAndStart', 'f', 575, 0.0)
- ('loading', 'ResourceRequestSender::OnRequestComplete', 'X', 569, 3.46)
- ('loading', 'ThrottlingURLLoader::Start', 'X', 569, 7.22)
- ('loading', 'ThrottlingURLLoader::StartNow', 'X', 569, 5.54)
- ('loading', 'CorsURLLoaderFactory::GetDevToolsObserver', 'X', 569, 3.05)
- ('loading', 'ThrottlingURLLoader::ThrottlingURLLoader', 's', 569, 0.0)
- ('loading', 'ThrottlingURLLoader::ThrottlingURLLoader', 'f', 569, 0.0)
- ('loading', 'ThrottlingURLLoader::Start', 's', 569, 0.0)
- ('loading', 'ThrottlingURLLoader::Start', 'f', 569, 0.0)
- ('loading', 'ThrottlingURLLoader::StartNow', 's', 569, 0.0)
- ('loading', 'ThrottlingURLLoader::StartNow', 'f', 569, 0.0)
- ('blink', 'Resource::appendData', 'X', 560, 5.21)
- ('blink', 'ResponseBodyLoader::OnStateChange', 'X', 531, 113.9)
- ('cc', 'LayerTreeHost::WaitForCommitCompletion', 'X', 502, 2.81)
- ('disabled-by-default-devtools.timeline', 'Commit', 'X', 500, 127.95)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'SendBeginMainFrameToCommit', 'b', 497, 0.0)
- ('cc,benchmark,disabled-by-default-devtools.timeline.frame', 'SendBeginMainFrameToCommit', 'e', 497, 0.0)
- ('blink', 'LayoutView::commitPendingSelection', 'X', 496, 0.54)
- ('cc', 'auto cc::SchedulerStateMachine::SetNeedsBeginMainFrame(bool, bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 469, 1.1)
- ('cc', 'LayerTreeHost::ApplyCompositorChanges', 'X', 439, 0.73)
- ('cc', 'auto cc::(anonymous namespace)::InsertNodeForTask(TaskGraph *, TileTask *, uint16_t, uint16_t, size_t, bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'X', 433, 0.49)
- ('__metadata', 'ActiveProcesses', 'I', 424, 0.0)
- ('loading', 'CorsURLLoader::CorsURLLoader', 'X', 413, 0.91)
- ('disabled-by-default-devtools.timeline', 'GPUTask', 'X', 411, 85.25)
- ('disabled-by-default-devtools.timeline', 'UpdateLayer', 'X', 410, 5.89)
- ('cc', 'TaskSetFinishedTaskImpl::RunOnWorkerThread', 'X', 404, 2.18)
- ('cc', 'ProxyImpl::SetNeedsCommitOnImplThread', 'X', 404, 1.86)
- ('disabled-by-default-devtools.timeline', 'UpdateLayer', 'I', 403, 0.0)
- ('cc', 'auto cc::LayerTreeHost::SetNeedsCommit(bool)::(lambda)::operator()()::(lambda)::operator()(uint32_t) const', 'I', 401, 0.0)
- ('blink', 'WebFrameWidgetImpl::BeginMainFrame', 'X', 401, 19613.28)
- ('blink', 'Blink.Animate.UpdateTime', 'X', 401, 14372.63)
- ('blink,rail', 'PageAnimator::serviceScriptedAnimations', 'X', 401, 14370.62)
- ('blink', 'WebFrameWidgetImpl::UpdateLifecycle', 'X', 401, 184861.99)
- ('blink,benchmark', 'LocalFrameView::RunPaintLifecyclePhase', 'X', 401, 39479.96)
- ('blink', 'Blink.Paint.UpdateTime', 'X', 401, 188.44)