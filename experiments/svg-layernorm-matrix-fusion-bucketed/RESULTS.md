# LayerNorm-to-matrix fusion A/B

This experiment tests a real block-0 GPT-2-small LayerNorm consumer in actual
Chromium. The generated pages contain no JavaScript. The external Playwright
harness only captures and decodes their pixels.

The ordinary path is:

```text
bucketed residual x
→ calculate LayerNorm(x)
→ materialize 768 normalized values
→ composed attention matrix
→ 768 outputs
```

The fused-consumer identity is:

```text
A[j,i] = W[j,i] × gamma[i]
B[j,i] = A[j,i] - mean(A[j,:])
c[j]   = W[j,:] × beta + bias[j]

W × LayerNorm(x) + bias = gain(x) × (B × x) + c
```

The right side needs only the live inverse standard deviation after the matrix;
the mean is eliminated algebraically. Across both fixtures, the dense NumPy
forms differ by at most `3.11e-15`.

## Chromium result

The retained fused variant materializes a bucketed `x - mean(x)` surface before
the matrix because the completely centered-weight form was even less accurate.

| Path | Original RMSE | Alternate RMSE | Original max error | Alternate max error |
| --- | ---: | ---: | ---: | ---: |
| Materialized LayerNorm | 0.06037 | 0.06774 | 1.26479 | 0.87300 |
| Fused consumer | 0.52925 | 0.52945 | 5.51888 | 5.62711 |

The centered/diff matrix before its gain and constant already has `0.20209`
RMSE and `2.11473` maximum error. The fused consumer therefore fails at the
matrix boundary, not because its algebra is approximate.

## Size and timing

| Path | Filter primitives | HTML bytes | Retained warm navigation + capture median |
| --- | ---: | ---: | ---: |
| Materialized LayerNorm | 156 | 55,167 | 482.9 ms |
| Fused consumer | 152 | 56,187 | 115.2 ms |

The timing includes navigation and screenshot capture, varied substantially
between runs, and is not a token-rate measurement. The fused dependency path
was consistently cheaper to render, but its approximately eight-times-larger
RMSE makes the speed result unusable.

## Why it fails

Fusion changes where quantization occurs:

- The ordinary path applies learned `gamma` coordinate-by-coordinate before
  the matrix, then encodes the normalized vector in 32 scale buckets.
- The fused path folds `gamma` into every matrix column. Those transformed
  weights and their partial sums must pass through the 8-bit product and
  accumulator surfaces.
- Centering the matrix rows creates cancellation across the 768-term reduction.
  Keeping an explicit centered activation avoids some of that cancellation but
  recreates nearly the entire LayerNorm transport graph.

Thus the model-level algebra is exact while the SVG execution is not
numerically equivalent.

## Decision

Reject full LayerNorm-consumer fusion for the current 8-bit SVG backend.

It demonstrates that removing a transport boundary can make the browser graph
faster, but moving the same work into a worse-quantized matrix is not a useful
trade. The next transport work should preserve the existing coordinate-wise
LayerNorm affine and instead reduce precision loss inside the unavoidable
normalization statistics/output boundaries.

Rebuild with `tools/build_svg_layernorm_matrix_fusion.py` and validate with
`tools/test_svg_layernorm_matrix_fusion.mjs`. Raw measurements are in
`results.json`.
