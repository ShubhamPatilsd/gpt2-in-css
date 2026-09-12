# Centered single-convolution QKV

This experiment halves QKV reductions while preserving the reliable 64-pixel
surface width. The runtime is HTML/SVG only and contains no JavaScript.

## Method

The previous RGB QKV path stores positive and negative products separately and
runs two convolutions per `(token, head, shard)`. The centered path offset-encodes
both operands around `C = 128/255` and computes their signed product with one
arithmetic composite.

For normalized values `x` and `w`:

```text
X = C + x/2
W = C + w/2
P = C + g(X - C)(W - C) = C + g*x*w/4
```

One `feConvolveMatrix` then sums `P`. Its divisor and bias remove the accumulated
center term and return `C + dot(x,w)/(2D)`, the same representation expected by
the existing shard, bias, and scale stages.

This changes QKV from 144 convolutions to 72 without widening the raster.

## Gain sweep

`g` controls how much of the 8-bit range each product uses. Too little wastes
precision; `g = 2` occasionally clips a large key value. The retained value is
`1.9`.

| gain | QKV RMSE | QKV max error | context RMSE | probability max error |
| ---: | ---: | ---: | ---: | ---: |
| 1.00 | 0.03582 | 0.30959 | — | — |
| 1.25 | 0.03259 | 0.39516 | — | — |
| 1.50 | 0.02949 | 0.40554 | — | — |
| 1.75 | 0.02566 | **0.21342** | 0.00631 | 0.07109 |
| **1.90** | 0.02565 | 0.24498 | **0.00526** | **0.02209** |
| 2.00 | **0.02549** | 0.40554 | 0.00582 | 0.03778 |

## Nine-round connected benchmark

| QKV method | QKV median | connected median | QKV RMSE | context RMSE | QKV HTML | connected HTML |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Split positive/negative | 723.1 ms | 1,039.8 ms | **0.02375** | **0.00482** | 585,289 B | 1,118,372 B |
| Centered, gain 1.9 | **300.6 ms** | **465.4 ms** | 0.02565 | 0.00526 | **440,451 B** | **973,534 B** |

The centered path is 2.41x faster for QKV and 2.23x faster through attention.
It also removes 25% of QKV HTML. The accuracy loss is small and remains well
inside the current browser validity gate.

## Full residual recomputation

The centered QKV stage was connected to the retained direct mixed-context
attention projection. A dedicated benchmark changes the input image URL before
every screenshot, forcing Chrome to recompute the filter instead of reusing a
raster cache.

| order | split-sign median | centered median | speedup |
| --- | ---: | ---: | ---: |
| Split-sign first, 8 rounds | 1,154.0 ms | 563.2 ms | 2.05x |
| Centered first, 10 rounds | 1,158.1 ms | 583.5 ms | 1.98x |

Full residual RMSE changes from 0.03343 to 0.03490. Maximum error remains
0.36910. The approximately 2x improvement therefore survives attention,
projection, the residual addition, and explicit input invalidation.

## Decision

Retain centered QKV with gain 1.9. Unlike spatial token batching, it reduces
work while keeping Chromium's 64-pixel fast geometry.

Rebuild and benchmark with:

```sh
SVG_MULTITOKEN_OUT=experiments/svg-multitoken-attention-rgb-centered \
SVG_QKV_LAYOUT=rgb \
SVG_RGB_QKV_CENTERED_DOT=1 \
SVG_RGB_QKV_CENTERED_GAIN=1.9 \
SVG_RGB_ATTENTION_BROADCAST=tile \
  python3 tools/build_svg_multitoken_attention.py

SVG_QKV_BENCH_SET=rgbcentered SVG_QKV_BENCH_ROUNDS=9 \
  node tools/benchmark_svg_multitoken_qkv_layouts.mjs

SVG_RECOMPUTE_ROUNDS=10 SVG_RECOMPUTE_ORDER=centered-first \
  node tools/benchmark_svg_residual_recompute.mjs
```

