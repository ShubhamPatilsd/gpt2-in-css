# Real GPT-2 HVAR to SWAR MLP slice

This no-JavaScript fixture connects the real first-block GPT-2-small
`768→3,072` FC font to GELU, 6-bit activation packing, and a real signed 8-bit
`3,072→128` projection slice using two-lane SWAR anchor dot products.

## Variants

| Variant | FC/GELU handoff | Warm mutation | Browser RMSE vs quantized transport |
| --- | --- | ---: | ---: |
| Baseline | 1,536 packet elements decode two HVAR widths each | 1,701.0 ms | 0.014–0.030 |
| Fused | Each HVAR source uses `calc-size()` to emit its GELU/6-bit code | 1,489.4 ms | 0.014–0.030 |
| Fused fast | Same fusion with the sigmoid GELU approximation | 1,404.4 ms | 0.013–0.026 |

The exact fusion is 1.14x faster than the separate handoff. The approximate
GELU reaches 1.21x. A CSS `@function --gelu()` attempt was invalid at computed
value time in this Chrome build, so the working baseline and fused pages inline
the nonlinear expression.

One activation in the sampled input crossed into the adjacent 6-bit bucket
because the real HVAR glyph width is layout-quantized. This explains the small
browser-versus-transport error; the SWAR integer dot-product itself remained
exact. End-to-end RMSE against the unquantized 128-output reference was about
0.14–0.18, dominated by activation and effective-weight quantization.

The best page contains 4,743 elements, 23.40 MB raw CSS, 0.55 MB raw HTML, and
2.81 MB of reused WOFF2 fonts. Brotli q5 reduces its CSS to 1.26 MB and HTML to
0.10 MB. Cold load plus first evaluation was roughly 13 seconds.

## Decision

Do not scale this to the full dense projection. The isolated SWAR
`3,072→128` calculation takes about 0.62 seconds; the real FC/GELU/packing
front-end raises one slice to 1.40 seconds. Reusing the front-end and adding
six projection slices gives an optimistic estimate near 4.5 seconds for one
complete MLP. The existing real two-dimensional additive MLP is about 2.27
seconds, and the loaded flat-timeline MLP is about 0.34 seconds.

SWAR remains valuable for smaller composable reductions, sparse paths, and
attention-head-sized calculations. It is not the dense GPT-2 backend.

Raw measurements are in `browser-results-baseline.json`,
`browser-results-fused.json`, and `browser-results-fused-fast.json`.
