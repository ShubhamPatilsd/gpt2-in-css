# GPT-2 global-q15 contender browser probe

## Result

The best calibrated-q15 display scale is **1/16**: it matches the production q16 bucket winner on 14/16 fixtures, with mismatches at 493, 390. Live grid verification passed: **true**.

At state 519, the production target is token 37848; q15 at 0.1 chooses 37848, 1/16 chooses 37848, 1/32 chooses 37848, while the retained q16 control chooses 2032.

At state 493, production-calibrated q15 and q16 buckets both choose token 82; q15 at 0.1 chooses 17, 1/16 chooses 17, 1/32 chooses 17, while q16 chooses 17.

| q15 display scale | Production bucket matches | Mismatch states | Zero-width tokens | Max bucket error |
| ---: | ---: | --- | ---: | ---: |
| 0.1 | 12/16 | 493, 621, 390, 474 | 2 | 11 |
| 1/16 | 14/16 | 493, 390 | 0 | 11 |
| 1/32 | 14/16 | 493, 474 | 0 | 11 |

The nearest-q15 1,024-state screen has exactly one unbucketed mismatch, state 547 (float token 15 versus q15 token 405). Production calibration makes two residual-only moves: token 15 dimension 496 changes -1887 to -1886, and token 82 dimension 36 changes -2913 to -2912. It reaches 1,024/1,024 original-float winner agreement and 1,024/1,024 global-q16 production-bucket agreement; q16 has zero mathematical mismatches. The live Chrome q15 fonts contain both moves without changing the six-glyph topology. The browser fixture set covers 256/256 requested top-16 float slots with 192 unique contenders.

| State | Selection role | Float | nearest q15 | calibrated q15 | Production bucket | q15 Chrome 0.1 | q15 Chrome 1/16 | q15 Chrome 1/32 | q16 Chrome | Float margin |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 519 | known-q16-browser-flip | 37848 | 37848 | 37848 | 37848 | 37848 | 37848 | 37848 | 2032 | 0.061566 |
| 547 | sole-nearest-q15-mismatch | 15 | 405 | 15 | 15 | 15 | 15 | 15 | 15 | 0.013065 |
| 493 | lowest-float-margin | 82 | 82 | 82 | 82 | 17 | 17 | 17 | 17 | 0.001498 |
| 621 | lowest-float-margin | 1584 | 1584 | 1584 | 1584 | 1853 | 1584 | 1584 | 1584 | 0.001639 |
| 889 | lowest-float-margin | 23 | 23 | 23 | 23 | 23 | 23 | 23 | 23 | 0.002141 |
| 391 | lowest-float-margin | 11 | 11 | 11 | 11 | 11 | 11 | 11 | 11 | 0.004754 |
| 390 | lowest-float-margin | 12 | 12 | 12 | 12 | 338 | 338 | 12 | 338 | 0.006356 |
| 824 | lowest-float-margin | 26954 | 26954 | 26954 | 26954 | 26954 | 26954 | 26954 | 26954 | 0.006655 |
| 423 | lowest-float-margin | 3099 | 3099 | 3099 | 3099 | 3099 | 3099 | 3099 | 3099 | 0.009691 |
| 474 | lowest-float-margin | 1146 | 1146 | 1146 | 1146 | 873 | 1146 | 873 | 1146 | 0.010227 |
| 944 | production-fixture | 1899 | 1899 | 1899 | 1899 | 1899 | 1899 | 1899 | 1899 | 0.308267 |
| 270 | production-fixture | 4101 | 4101 | 4101 | 4101 | 4101 | 4101 | 4101 | 4101 | 0.053594 |
| 20 | production-fixture | 1956 | 1956 | 1956 | 1956 | 1956 | 1956 | 1956 | 1956 | 0.498161 |
| 7 | production-fixture | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 13 | 0.323222 |
| 4 | production-fixture | 286 | 286 | 286 | 286 | 286 | 286 | 286 | 286 | 1.255805 |
| 0 | production-fixture | 856 | 856 | 856 | 856 | 856 | 856 | 856 | 856 | 3.157015 |

## Latency

| Transport | Glyphs/row | Median (ms) | Mean (ms) | p95 (ms) | Mean/q16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| q15 0.1 | 6 | 123.45 | 125.15 | 132.50 | 1.012× |
| q15 1/16 | 6 | 121.40 | 124.28 | 132.20 | 1.005× |
| q15 1/32 | 6 | 123.15 | 125.33 | 132.10 | 1.014× |
| retained global q16 | 12 | 122.35 | 123.62 | 131.50 | 1.000× |

The retained q16 control matches 13/16 production bucket targets, collapses 5 tokens somewhere in the fixture suite, and has maximum bucket error 10. Its state-519 float-winner row does collapse to zero width.

This probe uses production-range homogeneous coordinates, real 768-axis rows,
and no runtime JavaScript. GPT-2's architecture and source checkpoint are
unchanged; the tested q15 approximation contains the two declared residual-code
calibrations above. Only 192 q15 rows were generated; this is not a full q15
font bank.

Chrome: 153.0.8010.36. Timings use one unmeasured all-fixture warmup followed by 3 warm rounds. Raw data: results.json. The completed nearest, single-move, and two-move-0.1 runs are preserved under nearest-*, single-move-*, and two-move-s10-* filenames.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_gpt2_global_q15_contender_probe.py
    node --check tools/test_gpt2_global_q15_contender_probe.mjs
    Q15_CONTENDER_BENCHMARK_ROUNDS=3 node tools/test_gpt2_global_q15_contender_probe.mjs
