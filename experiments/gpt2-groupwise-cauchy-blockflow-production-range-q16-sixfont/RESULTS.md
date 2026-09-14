# Production groupwise cascade with six-font q16 transport

**PASS: certify-sixfont-accuracy-cold-profile-retain-q16-warm-default.** Accept and certify the six-font integration as the accuracy + cold-start profile; it repairs state519. Reject it as the loaded-throughput default and retain the existing q16 backend for warm use. Chrome was checked directly against the immutable mathematical global-q16 approximation and original checkpoint float; the retained browser page was used only for paired timing.

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

Four live upper-bucket reads are one below a JavaScript reconstruction:

| State | Stage | Next group | Source/reader width px | Width / 4 | JS expected | CSS observed |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 270 | 4 | 29 | 14420 | 3605 | 3605 | 3604 |
| 270 | 7 | 7 | 14320 | 3580 | 3580 | 3579 |
| 270 | 8 | 1 | 14264 | 3566 | 3566 | 3565 |
| 4 | 0 | 0 | 14320 | 3580 | 3580 | 3579 |

Both `getBoundingClientRect().width` and computed reader width are the exact integral values shown, so this is not `Math.floor` acting on a visible subpixel remainder. Chrome's internal `100cqi/4px` evaluation at an exact boundary makes `round(down)` one bucket conservative. The unchanged retained verifier allowance of one upper-transport bucket covers exactly these cases; measured routing, gap arithmetic, and the 49-bucket done gate still match live CSS.

Integer-axis liveness: pass; 768 computed dynamic axes, 768 hot axes, zero-coordinate errors 0. Sampled 288 glyphs with 0 collapses and 0 cap hits; analytic maximum is 2684.155 px. Group 196 exposed 81/256 rows.

Runtime/CSP: pass; six q16 fonts requested 6/6, old q16 fonts requested 0, script requests 0, JavaScript-disabled load true. Source has CSP `script-src 'none'` and no script elements.

Cold load: six-font 75612.62 ms; retained comparison 87491.10 ms (0.864×, 13.6% faster). Warm paired benchmark:

| State | Active stages | Order | Six-font ms | Retained ms | Ratio |
| ---: | ---: | :--- | ---: | ---: | ---: |
| 944 | 23 | candidate then retained | 17716.43 | 18368.25 | 0.965× |
| 270 | 11 | retained then candidate | 11255.31 | 11405.73 | 0.987× |
| 20 | 7 | candidate then retained | 8951.53 | 6957.12 | 1.287× |
| 7 | 1 | retained then candidate | 2652.95 | 1825.79 | 1.453× |
| 4 | 1 | candidate then retained | 2457.73 | 2261.22 | 1.087× |
| 0 | 1 | retained then candidate | 4005.69 | 2868.67 | 1.396× |

Warm mean is 7839.94 ms versus 7281.13 ms (1.077×, 7.7% slower); warm median is 8951.53 ms versus 6957.12 ms (1.287×, 28.7% slower). The hard 23- and 11-stage fixtures are slightly faster, while the 7- and 1-stage fixtures regress. This supports the accuracy/cold-start profile verdict, not promotion to the loaded-throughput default.

Raw results: `browser-results.json`. The six WOFF2 files are referenced from the completed bank and are not copied.
