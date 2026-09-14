# GPT-2 global-q16 final-LayerNorm-bound Chrome probe

## Result

The analytic base, geometry, liveness, CSP, and no-collapse gates passed. Strict exact-candidate global-q16 transport certification with integer fvar user coordinates passed: **false**. The integer-axis page matched 16/16 mathematical q16 bucket winners, including states 493 and 390. Its all-winner decision gate passes, but 712/3072 candidate buckets differ from mathematical q16 by at most 1, so the stricter every-bucket-exact gate remains false. The normalized-axis and half-step baselines remain preserved below.

| Scale | q16 winner | q16 bucket winner | Float winner | Max bucket error vs q16 | Max bucket error vs float | Collapsed rows | Warm median (ms) | Median vs retained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.1 | 14/16 | 14/16 | 14/16 | 15 | 15 | 0 | 3.55 | 0.866× |
| 1/16 | 14/16 | 14/16 | 14/16 | 15 | 15 | 0 | 3.55 | 0.866× |
| 1/16 + half-step | 14/16 | 14/16 | 14/16 | 18 | 18 | 0 | 3.50 | 0.854× |
| 1/16 integer-axis | 16/16 | 16/16 | 16/16 | 1 | 2 | 0 | 3.65 | 0.890× |

The retained 12-glyph q16 page was used only as a latency control (warm median 4.10 ms), never as a correctness oracle. Correctness comparisons use the immutable global-q16 codes and original checkpoint float weights directly.

## Integer-axis acceptance and liveness

The duplicate six-font bank uses fvar min/default/max = -16384/0/+16384 while retaining byte-identical normalized HVAR tables and q16 deltas. CSS supplies `round(nearest, hidden/R*16384, 1)` as an integer user coordinate. Chrome accepted this path: computed settings were non-`normal`, used the `IntegerBound*` families, exposed 768 finite integer axes, matched the nearest-coordinate oracle with maximum coordinate error 0, changed between fixtures (true), and changed intrinsic glyph metrics (true). The remaining one-bucket candidate differences therefore occur after exact coordinate normalization, consistent with per-glyph HVAR advance/layout rounding rather than rejected CSS syntax or a rejected fvar range.

## Analytic reachability bound

For each token row, plane, and 256-axis shard, with y = gamma*z + beta, sum(z) = 0, and ||z||2 <= sqrt(768), the font uses

    bias = c·beta/R
    radius = sqrt(768) ||P(c*gamma padded to 768)||2/R
    base = ceil(radius - bias + 24)

where P(v) = v - mean(v)1. Across all 1,152 bounded glyph rows, the analytic advance interval is 24.000690 to 1516.197860 font units; every lower bound is positive with an explicit 24-unit margin.

The Cauchy advance bound covers the full mean-zero norm ball. Exact HVAR transport is certified only on its intersection with the declared coordinate domain |y_i| <= R = 266.2483969116211. The unconstrained LayerNorm coordinate bound reaches 489.792219 at dimension 496; dimensions 36, 314, 374, 430, 442, 496, 703 can exceed R, so this probe does not claim exact transport outside the unclipped HVAR domain.

The 1,024 stored final-LayerNorm states reconstruct z = (y - beta)/gamma with maximum absolute mean 3.973e-8 and norm 27.712803–27.712822 versus sqrt(768) = 27.712813.

## Chrome geometry

| Scale | Residual unit (layout64) | High unit (layout64) | Analytic high max (px) | Analytic residual max (px) | Browser max (px) | At/above 32768 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.1 | 6.4 | 1638.4 | 3802.812 | 151.620 | 2129.156 | 0 |
| 1/16 | 4 | 1024 | 2376.758 | 94.762 | 1330.734 | 0 |
| 1/16 + half-step | 4 | 1024 | 2376.758 | 94.762 | 1330.734 | 0 |
| 1/16 integer-axis | 4 | 1024 | 2376.758 | 94.762 | 1330.844 | 0 |

Both six-font WOFF2 banks contain only the 192 target rows. At scale 0.1 the analytic high-plane bound is 3802.812 px; at 1/16 it is 2376.758 px, both far below Chrome's 32,768 px adjusted-glyph ceiling. Chrome measured zero collapsed rows.

| Scale | q16 winner mismatches | q16 bucket-winner mismatches | Float-winner mismatches |
| --- | --- | --- | --- |
| 0.1 | 493, 390 | 493, 390 | 493, 390 |
| 1/16 | 493, 390 | 493, 390 | 493, 390 |
| 1/16 + half-step | 493, 474 | 493, 474 | 493, 474 |
| 1/16 integer-axis | none | none | none |

## Runtime contract

All four HTML artifacts have CSP `script-src 'none'`. Raw-source, DOM, event-handler, resource, request, liveness, and geometry audits found no script execution or runtime errors. Browser automation is external to the artifacts. Chrome: 153.0.8010.36.

Raw data: `reference.json` and `results.json`.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_gpt2_global_q16_layernorm_bound_probe.py
    node --check tools/test_gpt2_global_q16_layernorm_bound_probe.mjs
    Q16_LN_BOUND_BENCHMARK_ROUNDS=5 node tools/test_gpt2_global_q16_layernorm_bound_probe.mjs
