# Production groupwise cascade with six-font q16 transport

**FAIL: reject-sixfont-production-integration.** Chrome was checked directly against the immutable mathematical global-q16 approximation and original checkpoint float; the retained browser page was used only for paired timing.

| State | Active stages | Routed groups | q16 | Float | Chrome | Pass |
| ---: | ---: | :--- | ---: | ---: | ---: | :---: |
| 944 | 23 | 4,7,3,26,9,8,5,12,21,22,14,15,6,11,10,16,23,13,25,18,19,20,17 | 1899 | 1899 | 1023 | no |
| 270 | 23 | 16,3,2,39,29,33,37,7,13,17,25,4,28,38,15,8,6,14,21,22,5,45,20 | 4101 | 4101 | 767 | no |
| 20 | 23 | 7,4,17,18,12,15,62,193,2,33,52,168,41,38,56,36,8,16,21,30,27,6,11 | 1956 | 1956 | 767 | no |
| 7 | 23 | 3,2,4,28,5,8,7,6,11,196,26,9,13,21,10,15,23,14,12,24,17,37,41 | 13 | 13 | 767 | no |
| 4 | 23 | 2,9,5,3,41,11,28,13,8,4,196,6,7,10,19,32,14,77,15,12,22,21,37 | 286 | 286 | 767 | no |
| 0 | 23 | 3,2,12,7,5,41,11,4,18,42,8,13,82,6,10,147,19,28,15,135,79,31,103 | 856 | 856 | 767 | no |

State 519 is not one of the retained six production fixtures. Its separate forced-group integration check selected token 37887 in group 147 (q16 target 37848; legacy browser comparison token 2032; fail).

Dynamic selected-group q16 bucket deltas: -5470..-2781 across 138 stages. Hot-group deltas: null..null across 0 stages. The retained stop threshold remains 49 buckets. A selected-candidate -1 delta would spend one bucket of that separation; observed negative count was 138.

Integer-axis liveness: pass; 768 computed dynamic axes, 768 hot axes, zero-coordinate errors 0. Sampled 330 glyphs with 6 collapses and 0 cap hits; analytic maximum is 2684.155 px. Group 196 exposed 81/256 rows.

Runtime/CSP: pass; six q16 fonts requested 6/6, old q16 fonts requested 0, script requests 0, JavaScript-disabled load true. Source has CSP `script-src 'none'` and no script elements.

Cold load: six-font 50760.97 ms, retained 80919.60 ms (0.627×). Warm paired median over 6 samples each: six-font 24808.38 ms, retained 8052.82 ms (3.081×).

Raw results: `browser-results.json`. The six WOFF2 files are referenced from the completed bank and are not copied.
