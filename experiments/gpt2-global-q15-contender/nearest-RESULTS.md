# GPT-2 global-q15 contender browser probe

## Result

The contender-only q15 transport is **1.015× faster by mean** than the retained q16 transport (126.75 ms versus 128.59 ms). Live grid verification passed: **true**.

At state 519, float/q15/q16 mathematics all choose token 37848; Chrome q15 chooses 37848 and Chrome q16 chooses 2032. This reproduces the known q16 browser flip to token 2032.

Chrome collapses 2 q15 contender rows and 5 q16 contender rows to zero width somewhere in the fixture set. The q16 row for state 519's float winner 37848 does collapse, directly explaining that flip.

The 1,024-state mathematical screen has exactly one q15 mismatch, state 547 (float token 15 versus q15 token 405), and zero q16 mismatches. The browser fixture set covers 256/256 requested top-16 float slots with 192 unique contenders.

| State | Selection role | Float winner | q15 math | q16 math | q15 Chrome | q16 Chrome | Float margin |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 519 | known-q16-browser-flip | 37848 | 37848 | 37848 | 37848 | 2032 | 0.061566 |
| 547 | sole-mathematical-q15-mismatch | 15 | 405 | 15 | 405 | 15 | 0.013065 |
| 493 | lowest-float-margin | 82 | 82 | 82 | 17 | 17 | 0.001498 |
| 621 | lowest-float-margin | 1584 | 1584 | 1584 | 1853 | 1584 | 0.001639 |
| 889 | lowest-float-margin | 23 | 23 | 23 | 23 | 23 | 0.002141 |
| 391 | lowest-float-margin | 11 | 11 | 11 | 11 | 11 | 0.004754 |
| 390 | lowest-float-margin | 12 | 12 | 12 | 338 | 338 | 0.006356 |
| 824 | lowest-float-margin | 26954 | 26954 | 26954 | 26954 | 26954 | 0.006655 |
| 423 | lowest-float-margin | 3099 | 3099 | 3099 | 3099 | 3099 | 0.009691 |
| 474 | lowest-float-margin | 1146 | 1146 | 1146 | 873 | 1146 | 0.010227 |
| 944 | production-fixture | 1899 | 1899 | 1899 | 1899 | 1899 | 0.308267 |
| 270 | production-fixture | 4101 | 4101 | 4101 | 4101 | 4101 | 0.053594 |
| 20 | production-fixture | 1956 | 1956 | 1956 | 1956 | 1956 | 0.498161 |
| 7 | production-fixture | 13 | 13 | 13 | 13 | 13 | 0.323222 |
| 4 | production-fixture | 286 | 286 | 286 | 286 | 286 | 1.255805 |
| 0 | production-fixture | 856 | 856 | 856 | 856 | 856 | 3.157015 |

## Latency

| Transport | Glyphs/row | Median (ms) | Mean (ms) | p95 (ms) |
| --- | ---: | ---: | ---: | ---: |
| global q15 radix-128 | 6 | 125.60 | 126.75 | 134.20 |
| retained global q16 radix-256 | 12 | 127.45 | 128.59 | 138.00 |

The maximum absolute browser bucket error for the browser-selected row is 11 buckets for q15 and 10 buckets for q16. Browser winners match their mathematical unbucketed targets on 12/16 q15 fixtures and 13/16 q16 fixtures.

This probe uses production-range homogeneous coordinates, real 768-axis rows, and no runtime JavaScript. GPT-2 architecture, checkpoint, and weights are unchanged. Only 192 q15 rows were generated; this is not a full q15 font bank.

Chrome: 153.0.8010.36. Timings use one unmeasured all-fixture warmup followed by 5 warm rounds. Raw data: results.json.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_gpt2_global_q15_contender_probe.py
    node --check tools/test_gpt2_global_q15_contender_probe.mjs
    Q15_CONTENDER_BENCHMARK_ROUNDS=5 node tools/test_gpt2_global_q15_contender_probe.mjs
