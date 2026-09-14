# Production groupwise cascade with six-font q16 transport

**PASS: accept-sixfont-production-integration.** Chrome was checked directly against the immutable mathematical global-q16 approximation and original checkpoint float; the retained browser page was used only for paired timing.

| State | Active stages | Routed groups | q16 | Float | Chrome | Pass |
| ---: | ---: | :--- | ---: | ---: | ---: | :---: |
| 944 | 23 | 4,7,3,26,9,8,5,12,21,22,14,15,6,11,10,16,23,13,25,18,19,20,0 | 1899 | 1899 | 1899 | yes |
| 270 | 11 | 16,3,2,39,0,29,33,37,7,1,13 | 4101 | 4101 | 4101 | yes |
| 20 | 7 | 7,4,17,18,12,15,62 | 1956 | 1956 | 1956 | yes |
| 7 | 1 | 0 | 13 | 13 | 13 | yes |
| 4 | 1 | 1 | 286 | 286 | 286 | yes |
| 0 | 1 | 3 | 856 | 856 | 856 | yes |

State 519 is not one of the retained six production fixtures. Its separate forced-group integration check selected token 37848 in group 147 (q16 target 37848; legacy browser comparison token 2032; pass).

Dynamic selected-group q16 bucket deltas: 0..1 across 39 stages. Hot-group deltas: 0..1 across 5 stages. The retained stop threshold remains 49 buckets. A selected-candidate -1 delta would spend one bucket of that separation; observed negative count was 0.

Integer-axis liveness: pass; 768 computed dynamic axes, 768 hot axes, zero-coordinate errors 0. Sampled 288 glyphs with 0 collapses and 0 cap hits; analytic maximum is 2684.155 px. Group 196 exposed 81/256 rows.

Runtime/CSP: pass; six q16 fonts requested 6/6, old q16 fonts requested 0, script requests 0, JavaScript-disabled load true. Source has CSP `script-src 'none'` and no script elements.

Cold load: six-font 73015.46 ms; retained comparison not run ms. Warm paired benchmark: deferred.

Raw results: `browser-results.json`. The six WOFF2 files are referenced from the completed bank and are not copied.
