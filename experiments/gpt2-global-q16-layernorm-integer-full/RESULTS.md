# Full-vocabulary GPT-2 global-q16 integer-axis output head

## Current decoder-fix verifier

**Failed at the first fixture; no pass is claimed.** State 391 expected q16 token 11 (group 0), and the full width scan still selected token 11. Its expected group wrapper/grid widths were 11,236 / 11,239.8125 px. The direct reducer's `outer-max` anchor computed to 0 px, however, so all 197 match carriers remained nonzero. The carrier maximum was group 0 at 197 px, and the decoder interpreted that width as group 148/local 191, token 38,079.

The exact failure is in `decoder-failure.json`. This run stopped immediately as requested; it did not rerun geometry or the remaining 37 fixtures. The next reducer must replace the failed 197-way outer anchor-size maximum with a bounded reduction tree before another broad verification.

## Preserved exhaustive first run

The full 50,257-row, six-glyph global-q16 bank passed its decision and runtime gates: **false**. Chrome matched 10/38 mathematical q16 winners across the lowest-32 production-margin states plus six production fixtures. The maximum candidate bucket error across every vocabulary row and fixture was 1 versus q16 and 3 versus original checkpoint float.

The fixture suite contains all 20 stored states with raw production-q16 top-two margin <=2 buckets, including all 10 at <=1 bucket. The retained browser bank was not used as a correctness oracle.

| State | Raw q16 margin (buckets) | q16 winner | Float winner | CSS winner | Width-scan winner | Max q16 bucket error | Differing rows |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 391 | 0.147 | 11 | 11 | 50687 | 11 | 1 | 11667 |
| 647 | 0.211 | 1366 | 1366 | 198 | 1366 | 1 | 11709 |
| 382 | 0.266 | 532 | 532 | 50687 | 532 | 1 | 11726 |
| 535 | 0.325 | 541 | 541 | 78 | 541 | 1 | 11673 |
| 82 | 0.526 | 13 | 13 | 50687 | 13 | 1 | 11561 |
| 390 | 0.612 | 12 | 12 | 50687 | 12 | 1 | 11742 |
| 125 | 0.687 | 25 | 25 | 25 | 25 | 1 | 11529 |
| 418 | 0.788 | 338 | 338 | 50687 | 338 | 1 | 11662 |
| 889 | 0.822 | 23 | 23 | 23 | 23 | 1 | 11691 |
| 495 | 0.877 | 11 | 11 | 50687 | 11 | 1 | 11700 |
| 178 | 1.004 | 13 | 13 | 13 | 13 | 1 | 11509 |
| 958 | 1.353 | 257 | 257 | 198 | 257 | 1 | 11595 |
| 621 | 1.360 | 1584 | 1584 | 50687 | 1584 | 1 | 11730 |
| 409 | 1.380 | 464 | 464 | 50687 | 464 | 1 | 11725 |
| 405 | 1.385 | 25 | 25 | 25 | 25 | 1 | 11641 |
| 800 | 1.427 | 290 | 290 | 50687 | 290 | 1 | 11653 |
| 824 | 1.427 | 26954 | 26954 | 3975 | 26954 | 1 | 11692 |
| 629 | 1.552 | 15 | 15 | 15 | 15 | 1 | 11790 |
| 474 | 1.583 | 1146 | 1146 | 396 | 1146 | 1 | 11735 |
| 127 | 1.585 | 13 | 13 | 50687 | 13 | 1 | 11676 |
| 250 | 2.034 | 13 | 13 | 50687 | 13 | 1 | 11562 |
| 940 | 2.037 | 1678 | 1678 | 7 | 1678 | 1 | 11869 |
| 493 | 2.104 | 82 | 82 | 50687 | 82 | 1 | 11383 |
| 547 | 2.208 | 15 | 15 | 15 | 15 | 1 | 11793 |
| 383 | 2.242 | 21955 | 21955 | 50687 | 21955 | 1 | 11579 |
| 442 | 2.364 | 198 | 198 | 50687 | 198 | 1 | 11832 |
| 140 | 2.455 | 13 | 13 | 13 | 13 | 1 | 11616 |
| 450 | 2.794 | 55 | 55 | 50687 | 55 | 1 | 11803 |
| 612 | 3.043 | 13 | 13 | 13 | 13 | 1 | 11883 |
| 505 | 3.048 | 67 | 67 | 50687 | 67 | 1 | 11761 |
| 609 | 3.178 | 19 | 19 | 19 | 19 | 1 | 11684 |
| 88 | 3.187 | 13 | 13 | 50687 | 13 | 1 | 11729 |
| 944 | 38.128 | 1899 | 1899 | 11 | 1899 | 1 | 11731 |
| 270 | 6.622 | 4101 | 4101 | 50687 | 4101 | 1 | 11808 |
| 20 | 65.391 | 1956 | 1956 | 11 | 1956 | 1 | 11625 |
| 7 | 40.965 | 13 | 13 | 13 | 13 | 1 | 11703 |
| 4 | 162.163 | 286 | 286 | 50687 | 286 | 1 | 11628 |
| 0 | 412.398 | 856 | 856 | 273 | 856 | 1 | 11651 |

## Bank and geometry

The bank uses immutable global-q16 codes split exactly into radix-256 high/residual planes over three 256-axis shards. Every fvar axis is -16384/0/+16384 and CSS supplies `round(nearest,h/R*16384,1)`. The six final WOFF2 files occupy 74.78 MiB; no full variable TTF is retained. HTML is 6.30 MiB and CSS is 0.70 MiB.

| Plane | Shard | WOFF2 MiB | Base units | Analytic advance units | Analytic adjusted max px |
| --- | ---: | ---: | ---: | ---: | ---: |
| high | 0 | 9.32 | 64–92 | 24.000–157.588 | 2521.414 |
| residual | 0 | 15.63 | 357–643 | 24.000–1242.497 | 77.656 |
| high | 1 | 9.31 | 77–98 | 24.000–167.760 | 2684.155 |
| residual | 1 | 15.63 | 373–915 | 24.000–1763.455 | 110.216 |
| high | 2 | 9.27 | 45–74 | 24.000–123.014 | 1968.220 |
| residual | 2 | 15.62 | 330–517 | 24.000–1001.919 | 62.620 |

The analytic minimum advance is 24.000004 units and maximum adjusted advance is 2684.155 px, below Chrome's 32,768 px glyph ceiling. Chrome individually measured 301,542 glyphs over all 50,257 rows at state 270: zero collapsed glyphs/rows, zero cap hits, and maximum adjusted width 1335.844 px.

## Browser contract and timing

Computed font settings exposed 768 live integer coordinates with zero error versus the nearest F2DOT14 oracle and changed both settings and intrinsic width between fixtures. The HTML has CSP `script-src 'none'`; source, DOM, request, and resource audits found no runtime JavaScript. Chrome: 153.0.8010.36.

Cold launch-through-first-result: 71908.96 ms (load event 42901.32 ms; fonts-ready wait 28653.72 ms). Warm 114-sample median: 1721.35 ms; p95: 2737.90 ms.

Raw data: `reference.json`, preserved exhaustive `results.json` / `results-first-run.json`, and current `decoder-failure.json`.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_gpt2_global_q16_layernorm_integer_full.py
    node --check tools/test_gpt2_global_q16_layernorm_integer_full.mjs
    Q16_INTEGER_FULL_WARM_ROUNDS=0 node tools/test_gpt2_global_q16_layernorm_integer_full.mjs
