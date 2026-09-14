# Ideal vector carrier: deconfounded result

## Result

The earlier 11.2 ms FC and 5.9 ms projection figures were shaped-result cache
hits, not the cost of processing a new activation vector.

With a never-before-shaped axis vector on every sample, the real HVAR matrices
take:

| Stage | Fixed-axis fresh-page control | Fresh literals | Fresh CSS variables |
|---|---:|---:|---:|
| FC, `768 -> 3072` | 17.3 ms | 38.2 ms | 38.9 ms |
| Projection, `3072 -> 768` | 15.1 ms | 49.8 ms | 52.3 ms |
| Combined | 32.4 ms | 88.0 ms | 91.2 ms |

The CSS-variable carrier remains close to an impossible literal-axis oracle:
only 0.7 ms slower for FC and 2.5 ms slower for projection. The important new
finding is that genuinely new font-axis values cost much more than revisiting
two values Chrome has already shaped.

## Method

Chrome 153.0.8010.36, headless:

- real GPT-2 block-0 FC and projection matrices;
- 9,216 glyphs in each stage;
- 16 distinct activation vectors per variable/literal variant;
- every vector is a unique interpolation between the two real fixture vectors;
- one fresh page graph per timed vector;
- browser, font, and file caches remain warm;
- the default vector is materialized before timing;
- generated rule construction and parsing occur before timing;
- timing begins with the selector change and ends after forced full bank layout.

This prevents exact shaped-output reuse. Separately, the cache-hit measurement
revisits the same two already-shaped vectors in one page.

## Cache hit versus fresh vector

| Stage | Variant | Cached revisit | Fresh vector | Fresh / cached |
|---|---|---:|---:|---:|
| FC | fixed control | 11.6 ms | 17.3 ms | 1.49x |
| FC | literals | 11.6 ms | 38.2 ms | 3.29x |
| FC | variables | 12.0 ms | 38.9 ms | 3.24x |
| Projection | fixed control | 5.6 ms | 15.1 ms | 2.70x |
| Projection | literals | 5.6 ms | 49.8 ms | 8.89x |
| Projection | variables | 5.7 ms | 52.3 ms | 9.18x |

The fixed variant cannot have a fresh axis vector by definition. Its
"fresh-page" column changes selector state while keeping the effective axes
fixed, so it measures graph/style/layout control overhead. Subtracting that
control suggests new-axis shaping contributes roughly 21.6 ms to variable FC
and 37.2 ms to variable projection in this fixture.

## Accuracy

Fresh literal and variable vectors produced identical errors:

- FC: maximum RMSE 0.0396 px, maximum absolute error 0.1479 px.
- Projection: maximum RMSE 0.0680 px, maximum absolute error 0.2575 px.

Expected widths were linearly interpolated from the two offline dot-product
references. The remaining subpixel difference is consistent with font-axis
fixed-point and layout rounding. There is no additional accuracy loss from
CSS variables relative to literal axis values.

## Implication

An ideal CSS vector carrier is still valuable: installing thousands of
variables is almost as fast as supplying literal font axes. But the realistic
fresh-vector floor for these two matrix stages is approximately 91.2 ms per
block, not 16.9 ms. Repeating only that MLP matrix floor across 12 blocks is
about 1.09 seconds per token, or 0.91 token/s, before attention, layer norms,
GELU, residuals, transport, and output readback.

The matrix backend therefore has a substantial input-dependent shaping cost.
Solving vector transport alone does not make HVAR matrix execution free.

## Reproduce

```sh
IDEAL_VECTOR_FRESH_ROUNDS=16 \
IDEAL_VECTOR_CACHE_ROUNDS=24 \
IDEAL_VECTOR_CACHE_WARMUPS=5 \
node tools/test_ideal_vector_carrier_probe.mjs
```

Machine-readable samples are in `benchmark-results.json`.
