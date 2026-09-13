# Two-lane SWAR anchor matrix multiplication

This experiment asks whether one CSS number can calculate two quantized dot-
product terms at once. Runtime pages contain only HTML and CSS.

## Encoding

Two unsigned 6-bit activations are packed into one anchor width:

```text
P = a0 + 32768*a1
```

Two signed 8-bit weights are packed in reverse order:

```text
Q = w1 + 32768*w0
```

The middle radix coefficient of `P*Q` is exactly `a0*w0 + a1*w1`.
`round()` and centered `mod()` recover that coefficient in CSS. The radix is
large enough to prevent coefficient carry, while the complete product remains
within the exact integer range of a double. One anchor reference and one CSS
multiplication therefore replace two scalar anchor terms.

## Chrome 153 results

All tested results were bit-exact.

| Shape | Backend | Sources | Terms | Raw HTML | Brotli q5 | Warm mutation |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 768→768 | Scalar anchors | 768 | 589,824 | 21.63 MB | 2.46 MB | 1,136.0 ms |
| 768→768 | Two-lane SWAR | 384 | 294,912 | 32.79 MB | 2.14 MB | 650.0 ms |
| 3,072→128 | Scalar anchors | 3,072 | 393,216 | 14.91 MB | 1.69 MB | 3,384.5 ms |
| 3,072→128 | Two-lane SWAR | 1,536 | 196,608 | 22.06 MB | 1.48 MB | 617.1 ms |

The speedups are 1.75x at hidden width and 5.48x for the high-fan-in slice.
Although the packed expression is longer, its repetition compresses better
than the scalar coefficients.

## Decision

Retain this as the fastest exact and directly composable anchor-expression
backend found so far. It materially improves direct CSS matrix math, but it
does not beat the font backend for a dense GPT-2 projection. Six independent
`3,072→128` slices imply roughly 3.7 seconds for `3,072→768` if output cost is
linear, versus about 0.65 seconds for the exact additive-font gather and about
0.1 seconds for a one-way font-to-raster MLP.

The technique is more promising for smaller reductions, attention heads,
sparse matrices, or places where keeping the result as reusable geometry is
worth more than raw dense-matrix speed. A full 768-output page was not emitted:
it would repeat an already-losing path and require roughly 132 MB of raw HTML.

Measurements are in `browser-results.json`.
