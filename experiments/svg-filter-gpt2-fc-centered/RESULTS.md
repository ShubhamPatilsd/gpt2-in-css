# Centered-product GPT-2 MLP

This experiment applies midpoint-centered multiplication to GPT-2's real
`768 -> 3072 -> 768` MLP. Runtime pages are HTML/SVG only.

## Variants

The split-sign baseline represents positive and negative terms in R/G. The
centered version represents each normalized operand as `C + value/2` and uses
one arithmetic composite per shard:

```text
P = C + g(X - C)(W - C)
```

The convolution bias removes the accumulated center term. Unlike RGB QKV,
split-sign FC already uses one convolution for both signs, so centering reduces
product surfaces and filter dependencies rather than the convolution count.

## Expansion gain sweep

Standalone FC RMSE improves as gain increases until clipping dominates. The
real selection criterion is the final MLP output after GELU and projection.

| expansion gain | FC RMSE | final MLP RMSE | final max error |
| ---: | ---: | ---: | ---: |
| 2.30 | 0.07416 | 0.40418 | 3.21147 |
| 3.00 | 0.06821 | 0.41171 | 3.21147 |
| 3.50 | 0.06787 | 0.39617 | 3.21147 |
| 4.00 | **0.06715** | 0.37241 | **2.33606** |
| **4.50** | 0.07210 | **0.37222** | **2.33606** |
| 5.00 | 0.07733 | 0.40422 | 4.96227 |

Gain 4.5 is retained because it gives the best measured final output, despite
not having the best intermediate FC RMSE.

## Forced full-MLP recomputation

The benchmark mutates an input image URL before every screenshot, forcing the
browser to reevaluate the filter graph.

| run order | split-sign median | centered expansion median | speedup |
| --- | ---: | ---: | ---: |
| Centered first, 10 rounds | 563.2 ms | 375.1 ms | 1.50x |
| Split-sign first, 10 rounds | 543.4 ms | 328.9 ms | 1.65x |

| path | final RMSE | max error | HTML | primitives |
| --- | ---: | ---: | ---: | ---: |
| Split-sign MLP | 0.41454 | 3.21147 | 38,031 B | 208 |
| Centered expansion + split projection | **0.37222** | **2.33606** | **35,745 B** | **187** |

The hybrid is both faster and more accurate at the final residual.

## Centered projection rejection

Centering both matrices reduced the full page to 27,432 bytes and 116
primitives. It was about 2.1x faster in the smoke comparison, but the best
projection gain tested produced roughly 0.558 final RMSE, worse than both the
0.415 baseline and 0.372 hybrid. Gains above 2.1 rapidly clipped large outputs.

Decision: center the `768 -> 3072` expansion at gain 4.5; retain split-sign
transport for the `3072 -> 768` projection.

Rebuild and benchmark with:

```sh
SVG_FC_OUT=experiments/svg-filter-gpt2-fc-centered \
SVG_FC_CENTERED_DOT=1 \
SVG_CENTERED_DOT_GAIN=4.5 \
  uv run --with numpy --with pillow --with fonttools \
  python tools/build_svg_filter_gpt2_fc.py

SVG_FC_BENCH_STAGE=full SVG_FC_BENCH_ROUNDS=10 \
  node tools/benchmark_svg_fc_centered.mjs
```

