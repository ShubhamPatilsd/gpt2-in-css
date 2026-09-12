# Linear fusion scaling probe

This no-script SVG experiment compares three mathematically related paths in
actual Chromium:

1. `chain`: 1–64 consecutive `feColorMatrix` additions.
2. `bounded`: the same additions with a no-op `feConvolveMatrix` after each.
3. `fused`: all additions algebraically combined into one `feColorMatrix`.

Each stage adds `0.001` to every scalar. The source is already decoded from its
8-bit PNG so the measurement counts only errors introduced after input.

## Stage scaling at 768 values

| Stages | Fuseable chain RMSE | Convolution-bounded RMSE | One fused operation RMSE |
| ---: | ---: | ---: | ---: |
| 1 | 0.001000 | 0.001000 | 0.001000 |
| 2 | 0.002000 | 0.002000 | 0.002000 |
| 4 | 0.003843 | 0.004000 | 0.003843 |
| 8 | 0.000157 | 0.008000 | 0.000157 |
| 16 | 0.000314 | 0.016000 | 0.000314 |
| 32 | 0.000627 | 0.032000 | 0.000627 |
| 64 | 0.001255 | 0.064000 | 0.001255 |

The ordinary chain and manually fused operation are pixel-for-pixel identical
through all 64 stages. Chromium therefore preserves this compatible sequence
as though it were fused, whether through optimizer fusion or deferred
materialization. Their non-monotonic error is the expected rounding of one
final 8-bit output.

The no-op convolution prevents that fusion. Its output is materialized after
every update, each sub-byte update disappears, and error grows exactly with the
number of boundaries. At 64 stages it has 51 times the fused path's RMSE.

## Vector-width scaling at 64 stages

| Values | Fuseable chain RMSE | Convolution-bounded RMSE | One fused operation RMSE |
| ---: | ---: | ---: | ---: |
| 64 | 0.001255 | 0.064000 | 0.001255 |
| 256 | 0.001255 | 0.064000 | 0.001255 |
| 768 | 0.001255 | 0.064000 | 0.001255 |
| 3,072 | 0.001255 | 0.064000 | 0.001255 |

The precision result is independent of width through the full 3,072-value GPT-2
MLP width. The combined three-path pages took roughly 100 ms for navigation and
capture in the retained warm runs, but that number includes browser/page and
screenshot overhead and is not an inference benchmark.

## Decision

Algebraic fusion scales for consecutive linear operations that can be expressed
as one compatible primitive. It is worth doing everywhere it applies.

It is not a general transformer transport solution. GPT-2's matrix reductions
require convolution-like primitives, and its layer normalization, softmax, and
GELU separate the linear regions. Those boundaries materialize 8-bit images and
cannot all be removed by placing the primitives in one `<filter>`.

The useful implementation rule is therefore:

- pre-compose consecutive affine maps at build time;
- fold biases and constant scales into the consuming primitive;
- do not expect SVG to preserve floating-point state across a convolution or
  nonlinear boundary.

Raw measurements are in `results.json`; generated fixtures and exact expected
values are in `reference.json`.
