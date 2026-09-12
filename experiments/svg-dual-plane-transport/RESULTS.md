# General higher-precision SVG transport

This experiment tests two representations in actual Chromium SVG filters. The
page contains no JavaScript; `tools/test_svg_dual_plane_transport.mjs` only
screenshots and measures its pixels.

## 1. Persistent coarse + fine planes

Each scalar is stored as:

```text
value = coarse_byte + fine_byte
```

Both bytes are propagated independently through the same 12-stage affine
recurrence. No prompt, coordinate, or outlier receives special handling.

| Calculated stages | One-plane RMSE | Two-plane RMSE |
| ---: | ---: | ---: |
| 0 | 0.004513 | 0.0000175 |
| 1 | 0.005669 | 0.004472 |
| 2 | 0.005677 | 0.004353 |
| 4 | 0.005627 | 0.004692 |
| 8 | 0.004926 | 0.004476 |
| 12 | 0.004683 | 0.004482 |

The two-plane input really does start about 258 times more accurate. After one
calculated boundary, however, it is already back at the 8-bit error scale.
The fine plane preserves the original input correction, but Chromium creates a
new rounding error when the newly calculated coarse plane is materialized. No
SVG primitive exposes that discarded remainder, so it cannot be copied into
the fine plane.

Conclusion: a conventional fixed coarse/fine encoding is high-precision
storage, but it is not a reusable high-precision compute transport in SVG.

## 2. Exact radix digits and carry

The second probe stores base-16 digits in color channels and uses a discrete
component-transfer table to calculate the low digit and carry. All 256 random
additions pass exactly in Chromium.

This proves that exact multi-byte arithmetic can be constructed if every
operation is decomposed into explicit digit operations. It is not compact for
GPT-2 dot products. A lower bound for unsigned 16-bit activations multiplied by
8-bit weights, before sign handling, final carry propagation, nonlinearities,
or storage, is:

| Dot length | Radix | Partial reduction groups |
| ---: | ---: | ---: |
| 768 | 2 | 512 |
| 768 | 4 | 896 |
| 768 | 16 | 6,144 |
| 3,072 | 2 | 1,664 |
| 3,072 | 4 | 3,520 |
| 3,072 | 16 | 24,576 |

Radix 2 is the least-bad case because each byte can accumulate up to 255
one-bit products before a carry. It still expands one matrix calculation into
hundreds or thousands of plane reductions. Exact radix arithmetic is therefore
a correctness fallback, not a plausible full-GPT-2 transport.

## Result

There is no fixed two-channel encoding that both:

1. preserves the discarded part of every newly computed SVG result, and
2. remains two channels after arbitrary chained computation.

The missing capability is not encoding capacity. Two bytes can store 65,536
states. The missing capability is a primitive that returns both the rounded
result and its rounding remainder, or a browser surface whose filter
intermediates are actually higher precision.

Generated measurements are in `results.json`; the exact inputs and cost model
are in `reference.json`.
