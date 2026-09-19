
### combined token 5: 85 frames, window wall 36325 ms

| main-thread event | median ms/frame | mean ms/frame | sum ms/token | frames with it | median count/frame |
|---|---:|---:|---:|---:|---:|
| frame dur | 333.3 | 425.6 | 36177 | 85 | 1 |
| animate: WebFrameWidgetImpl::BeginMainFrame incl (=serviceScriptedAnimations+TickAnimations) | 59.5 | 55.0 | 4677 | 85 | 1 |
|   PageAnimator::serviceScriptedAnimations self | 29.8 | 29.8 | 2536 | 85 | 1 |
|   AnimationTimeline::serviceAnimations incl | 24.7 | 25.5 | 2164 | 85 | 19172 |
| UpdateLifecycle self (snapshot validation etc.) | 23.9 | 23.9 | 2029 | 85 | 1 |
| UpdateLayoutTree incl (style) | 224.7 | 192.4 | 16356 | 85 | 2 |
|   UpdateLayoutTree self | 7.5 | 9.0 | 764 | 85 | 2 |
|   Document::recalcStyle self | 195.8 | 155.5 | 13215 | 85 | 2 |
| Layout incl | 38.0 | 73.2 | 6219 | 61 | 2 |
|   ShapeText incl | 0.0 | 26.0 | 2210 | 48 | 3842 |
| Blink.CompositingInputs.UpdateTime | 0.5 | 20.6 | 1753 | 69 | 2 |
| PrePaint incl | 2.0 | 23.2 | 1970 | 85 | 2 |
| RunPaintLifecyclePhase incl | 38.5 | 66.8 | 5678 | 85 | 1 |
|   Paint | 0.2 | 0.2 | 14 | 61 | 2 |
|   PaintArtifactCompositor::Update | 0.0 | 0.0 | 4 | 85 | 1 |
|   Layerize | 0.1 | 0.1 | 4 | 85 | 1 |
|   Commit | 0.1 | 0.3 | 22 | 85 | 1 |
| EventHandler::handleMouseMoveEvent (hover hit-test) | 16.7 | 12.6 | 1072 | 61 | 1 |
| GC nested (V8.GC_*) | 12.3 | 19.5 | 1661 | 77 | 1 |
| gap to previous frame | 1.6 | 1.8 | 153 | 84 | 1 |

serviceAnimations calls by enclosing phase (count/token, ms/token): {'UpdateLayoutTree': (894017, 1122.5), 'PageAnimator::serviceScriptedAnimations': (849051, 1042.1)}

| pass signature (elementCounts) | frames/token | median dur | style | layout | animate | UL self | compInputs | prePaint | paintLC | hover | pending Adds | anim starts/ends | layouts dirty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 23 | 103 | 17 | 0 | 60 | 22 | 0 | 1 | 19 | 18 | 0 | 0/1 |  |
| 2934 126 | 11 | 513 | 235 | 110 | 38 | 25 | 14 | 16 | 81 | 0 | 2331 | 26/0 | 6944 338 |
| 0 6919 780 | 11 | 309 | 99 | 86 | 61 | 25 | 8 | 13 | 39 | 18 | 830 | 0/0 | 8495 2343 |
| 0 3089 784 | 11 | 624 | 253 | 125 | 61 | 26 | 46 | 52 | 124 | 16 | 3842 | 0/0 | 9265 2358 |
| 0 1553 357 | 10 | 719 | 430 | 38 | 63 | 23 | 0 | 2 | 154 | 17 | 2308 | 770/769 | 1599 2 |
| 485 | 6 | 312 | 223 | 8 | 40 | 22 | 0 | 0 | 18 | 0 | 1 | 1/0 | 2 |
| 484 | 5 | 333 | 237 | 8 | 40 | 23 | 0 | 0 | 19 | 0 | 1 | 1/0 | 2 |
| 0 126 6919 | 1 | 456 | 173 | 126 | 64 | 24 | 4 | 7 | 78 | 18 | 2392 | 26/0 | 338 8495 |
| 0 780 3089 | 1 | 406 | 172 | 78 | 58 | 25 | 23 | 28 | 58 | 15 | 1538 | 0/0 | 2343 9265 |
| 0 784 1553 | 1 | 767 | 339 | 95 | 68 | 24 | 17 | 19 | 230 | 17 | 5380 | 769/769 | 2358 1599 |
| 0 368 | 1 | 373 | 224 | 3 | 59 | 23 | 0 | 1 | 77 | 16 | 1540 | 2/0 | 4 |
| 0 2326 51247 | 1 | 3543 | 814 | 1446 | 65 | 28 | 935 | 975 | 222 | 18 | 3078 | 771/771 | 2373 101164 |
| 2 6 | 1 | 117 | 26 | 0 | 62 | 25 | 0 | 1 | 20 | 18 | 1 | 0/2 |  |
| 487 | 1 | 332 | 234 | 10 | 38 | 25 | 0 | 1 | 22 | 0 | 1 | 1/0 | 7 |
| 1438 2917 | 1 | 525 | 263 | 141 | 40 | 27 | 14 | 18 | 32 | 0 | 768 | 2/0 | 1572 6943 |

regression RunPaintLifecyclePhase self = 18.7 ms + 26.7 us*pendingAdds + -18.7 us*transitionStarts + 126.3 us*ends ; R2=0.974
alt regression on (serviceAnim calls, sum elementCount, sum layout dirty): coeffs [-58.5444, 0.006, -0.0086, 0.005] R2=0.532
regression compInputs+PrePaint = -49.7 + 18.76 us*layoutDirty + -4.09 us*styledElements ; R2=0.903
regression animate(BeginMainFrame incl) = 30.7 ms + 1.18 us * serviceAnimations calls ; R2=0.481

### combined token 4: 85 frames, window wall 35415 ms

| main-thread event | median ms/frame | mean ms/frame | sum ms/token | frames with it | median count/frame |
|---|---:|---:|---:|---:|---:|
| frame dur | 317.8 | 415.3 | 35298 | 85 | 1 |
| animate: WebFrameWidgetImpl::BeginMainFrame incl (=serviceScriptedAnimations+TickAnimations) | 59.4 | 54.3 | 4614 | 85 | 1 |
|   PageAnimator::serviceScriptedAnimations self | 30.0 | 29.7 | 2527 | 85 | 1 |
|   AnimationTimeline::serviceAnimations incl | 23.9 | 24.8 | 2107 | 85 | 19291 |
| UpdateLifecycle self (snapshot validation etc.) | 23.4 | 23.4 | 1988 | 85 | 1 |
| UpdateLayoutTree incl (style) | 218.8 | 190.9 | 16226 | 85 | 2 |
|   UpdateLayoutTree self | 7.5 | 8.8 | 747 | 85 | 2 |
|   Document::recalcStyle self | 191.5 | 153.0 | 13001 | 85 | 2 |
| Layout incl | 38.1 | 66.1 | 5621 | 61 | 2 |
|   ShapeText incl | 0.0 | 24.7 | 2098 | 48 | 3074 |
| Blink.CompositingInputs.UpdateTime | 0.5 | 20.1 | 1712 | 68 | 2 |
| PrePaint incl | 1.9 | 22.6 | 1922 | 85 | 2 |
| RunPaintLifecyclePhase incl | 38.7 | 66.4 | 5648 | 85 | 1 |
|   Paint | 0.2 | 0.2 | 14 | 61 | 2 |
|   PaintArtifactCompositor::Update | 0.0 | 0.0 | 4 | 85 | 1 |
|   Layerize | 0.1 | 0.1 | 4 | 85 | 1 |
|   Commit | 0.1 | 0.3 | 22 | 85 | 1 |
| EventHandler::handleMouseMoveEvent (hover hit-test) | 15.9 | 12.2 | 1036 | 61 | 1 |
| GC nested (V8.GC_*) | 12.2 | 18.3 | 1559 | 78 | 1 |
| gap to previous frame | 1.5 | 1.5 | 125 | 84 | 1 |

serviceAnimations calls by enclosing phase (count/token, ms/token): {'UpdateLayoutTree': (889232, 1082.6), 'PageAnimator::serviceScriptedAnimations': (851036, 1024.4)}

| pass signature (elementCounts) | frames/token | median dur | style | layout | animate | UL self | compInputs | prePaint | paintLC | hover | pending Adds | anim starts/ends | layouts dirty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 23 | 101 | 17 | 0 | 61 | 22 | 0 | 1 | 19 | 18 | 0 | 0/1 |  |
| 2934 126 | 11 | 496 | 229 | 101 | 39 | 25 | 14 | 16 | 81 | 0 | 2331 | 26/0 | 6944 338 |
| 0 6919 780 | 11 | 286 | 97 | 72 | 60 | 24 | 8 | 11 | 39 | 17 | 818 | 0/0 | 6959 2343 |
| 0 3089 784 | 11 | 617 | 254 | 115 | 61 | 26 | 45 | 50 | 123 | 17 | 3842 | 0/0 | 9265 2358 |
| 0 1553 357 | 10 | 720 | 421 | 38 | 62 | 23 | 0 | 2 | 158 | 16 | 2308 | 770/769 | 1599 2 |
| 485 | 6 | 316 | 226 | 8 | 40 | 24 | 0 | 0 | 18 | 0 | 1 | 1/0 | 2 |
| 484 | 5 | 314 | 224 | 8 | 39 | 22 | 0 | 0 | 19 | 0 | 1 | 1/0 | 2 |
| 0 126 6919 | 1 | 441 | 172 | 104 | 68 | 24 | 4 | 7 | 82 | 18 | 2380 | 26/0 | 338 6959 |
| 0 780 3089 | 1 | 387 | 167 | 72 | 57 | 24 | 22 | 26 | 55 | 15 | 1537 | 0/0 | 2343 9265 |
| 0 784 1553 | 1 | 759 | 342 | 87 | 65 | 23 | 17 | 19 | 230 | 15 | 5380 | 769/769 | 2358 1599 |
| 0 368 | 1 | 364 | 213 | 3 | 61 | 24 | 0 | 1 | 78 | 16 | 1540 | 2/0 | 4 |
| 0 2326 51247 | 1 | 3726 | 1040 | 1426 | 62 | 27 | 922 | 959 | 218 | 15 | 3078 | 771/771 | 2373 101164 |
| 2 6 | 1 | 118 | 28 | 0 | 64 | 24 | 0 | 1 | 19 | 19 | 1 | 0/2 |  |
| 487 | 1 | 311 | 218 | 9 | 41 | 22 | 1 | 1 | 19 | 0 | 1 | 1/0 | 7 |
| 1438 2917 | 1 | 519 | 258 | 141 | 42 | 26 | 14 | 17 | 34 | 0 | 768 | 2/0 | 1572 6943 |

regression RunPaintLifecyclePhase self = 18.5 ms + 26.4 us*pendingAdds + -0.6 us*transitionStarts + 109.4 us*ends ; R2=0.979
alt regression on (serviceAnim calls, sum elementCount, sum layout dirty): coeffs [-61.2235, 0.0061, -0.0087, 0.0052] R2=0.553
regression compInputs+PrePaint = -46.7 + 18.67 us*layoutDirty + -3.93 us*styledElements ; R2=0.919
regression animate(BeginMainFrame incl) = 30.0 ms + 1.18 us * serviceAnimations calls ; R2=0.483

### F3a token 5: 73 frames, window wall 39142 ms

| main-thread event | median ms/frame | mean ms/frame | sum ms/token | frames with it | median count/frame |
|---|---:|---:|---:|---:|---:|
| frame dur | 417.8 | 534.2 | 38998 | 73 | 1 |
| animate: WebFrameWidgetImpl::BeginMainFrame incl (=serviceScriptedAnimations+TickAnimations) | 34.7 | 31.8 | 2319 | 73 | 1 |
|   PageAnimator::serviceScriptedAnimations self | 14.2 | 14.1 | 1033 | 73 | 1 |
|   AnimationTimeline::serviceAnimations incl | 16.7 | 17.3 | 1266 | 73 | 11014 |
| UpdateLifecycle self (snapshot validation etc.) | 11.9 | 11.7 | 851 | 73 | 1 |
| UpdateLayoutTree incl (style) | 151.3 | 132.2 | 9652 | 73 | 2 |
|   UpdateLayoutTree self | 3.9 | 4.4 | 320 | 73 | 2 |
|   Document::recalcStyle self | 121.0 | 103.7 | 7568 | 73 | 2 |
| Layout incl | 108.4 | 291.4 | 21273 | 49 | 2 |
|   ShapeText incl | 0.1 | 30.4 | 2218 | 37 | 4611 |
| Blink.CompositingInputs.UpdateTime | 1.0 | 23.3 | 1702 | 55 | 2 |
| PrePaint incl | 3.4 | 27.4 | 2003 | 73 | 2 |
| RunPaintLifecyclePhase incl | 25.3 | 45.2 | 3301 | 73 | 1 |
|   Paint | 0.2 | 0.6 | 44 | 49 | 2 |
|   PaintArtifactCompositor::Update | 0.3 | 0.3 | 19 | 73 | 1 |
|   Layerize | 0.3 | 0.3 | 19 | 73 | 1 |
|   Commit | 0.1 | 0.2 | 17 | 73 | 1 |
| EventHandler::handleMouseMoveEvent (hover hit-test) | 11.2 | 8.5 | 622 | 49 | 1 |
| GC nested (V8.GC_*) | 12.8 | 47.4 | 3457 | 72 | 1 |
| gap to previous frame | 0.5 | 1.7 | 122 | 72 | 1 |

serviceAnimations calls by enclosing phase (count/token, ms/token): {'UpdateLayoutTree': (408537, 616.0), 'PageAnimator::serviceScriptedAnimations': (417026, 649.6), 'Layout': (383, 0.4)}

| pass signature (elementCounts) | frames/token | median dur | style | layout | animate | UL self | compInputs | prePaint | paintLC | hover | pending Adds | anim starts/ends | layouts dirty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 23 | 57 | 11 | 0 | 37 | 9 | 0 | 3 | 10 | 14 | 0 | 0/1 |  |
| 473 | 11 | 432 | 166 | 218 | 20 | 11 | 1 | 3 | 12 | 0 | 1 | 1/0 | 16 |
| 2934 126 | 11 | 498 | 258 | 111 | 21 | 14 | 13 | 16 | 72 | 0 | 2353 | 48/0 | 6944 338 |
| 0 6919 780 | 11 | 255 | 73 | 99 | 35 | 12 | 8 | 11 | 31 | 11 | 830 | 0/0 | 8495 2343 |
| 0 3092 347 | 10 | 1493 | 160 | 1085 | 36 | 13 | 45 | 52 | 138 | 11 | 2308 | 770/769 | 8141 16 |
| 0 126 6919 | 1 | 459 | 162 | 174 | 39 | 14 | 4 | 7 | 73 | 11 | 2414 | 48/0 | 338 8495 |
| 0 780 3092 | 1 | 1113 | 70 | 839 | 46 | 14 | 58 | 65 | 79 | 13 | 3076 | 769/769 | 2343 8145 |
| 0 358 | 1 | 887 | 554 | 199 | 42 | 12 | 1 | 3 | 88 | 14 | 2306 | 769/0 | 17 |
| 0 3092 51235 | 1 | 5148 | 691 | 3275 | 36 | 14 | 931 | 986 | 146 | 11 | 3078 | 771/1538 | 8141 101177 |
| 2 6 | 1 | 86 | 27 | 0 | 50 | 13 | 0 | 3 | 12 | 20 | 1 | 0/2 |  |
| 474 | 1 | 472 | 199 | 222 | 20 | 16 | 1 | 3 | 11 | 0 | 1 | 1/0 | 20 |
| 1438 2917 | 1 | 508 | 280 | 146 | 24 | 13 | 14 | 17 | 25 | 0 | 768 | 2/0 | 1572 6943 |

regression RunPaintLifecyclePhase self = 10.9 ms + 23.5 us*pendingAdds + 61.9 us*transitionStarts + 14.5 us*ends ; R2=0.947
alt regression on (serviceAnim calls, sum elementCount, sum layout dirty): coeffs [-42.4926, 0.0079, -0.0228, 0.0119] R2=0.673
regression compInputs+PrePaint = -34.0 + 34.99 us*layoutDirty + -36.97 us*styledElements ; R2=0.947
regression animate(BeginMainFrame incl) = 15.8 ms + 1.42 us * serviceAnimations calls ; R2=0.395
