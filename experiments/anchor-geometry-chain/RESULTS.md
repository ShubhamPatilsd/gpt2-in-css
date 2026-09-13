# Geometry-native dense matrix chain

## Question

Can matrix outputs remain as element widths and feed the next matrix directly
through `anchor-size()`, avoiding view timelines and registered numeric CSS
properties entirely?

The generated pages contain HTML and CSS only. JavaScript exists only in the
external Playwright measurement harnesses.

## Working representation

Every scalar `x` is represented by one positive width:

```text
width = 2000px + 64px * x
```

For an affine output `y = W*x + b`, the next width is compiled as:

```text
2000px * (1 - sum(W)) + 64px * b
  + W0 * anchor-size(--x0 width)
  + W1 * anchor-size(--x1 width)
  + ...
```

The result is another named anchor with exactly the same encoding. A following
matrix can consume it directly. No coordinate is converted into a custom
property, timeline progress, font axis, color, or script value between layers.

## Chromium expression limit and fix

A conventional left-to-right sum works through 98 anchor terms. At 99 terms,
Chrome begins resolving output widths to zero. Splitting the dot product into
96-term geometry nodes restores correctness, but creates thousands of extra
anchors and is extremely slow: a 768x768 matrix took 28.4 seconds.

The useful discovery is to emit a balanced calculation tree:

```text
((a + b) + (c + d)) + ((e + f) + (g + h))
```

instead of:

```text
(((((((a + b) + c) + d) + e) + f) + g) + h)
```

This keeps expression depth logarithmic. The 768-input calculation then works
with only the 768 source anchors and 768 output anchors, and is about 6.1x
faster than the intermediate-geometry tree.

## Scaling result

Chrome 153, three rotated navigations, with all output widths forced:

| Dense matrix | Terms | Raw HTML | Brotli q5 | Warm navigation | RMSE |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 384x384 | 147,456 | 7.20 MB | 1.27 MB | 888.6 ms | 0.000154 |
| 512x512 | 262,144 | 12.80 MB | 2.25 MB | 1,708.8 ms | 0.000150 |
| 768x768 | 589,824 | 28.83 MB | 5.11 MB | 4,683.5 ms | 0.000153 |

To separate parsing from calculation, a second harness loads each page once,
changes every input width, and forces all outputs seven times:

| Dense matrix | Warm input mutation + evaluation |
| ---: | ---: |
| 384x384 | 184.7 ms |
| 512x512 | 391.8 ms |
| 768x768 | 1,250.5 ms |

The largest maximum absolute error was 0.000412. The backend is therefore
accurate and genuinely composable, but its work and source both grow with the
number of matrix coefficients. GPT-2's 768-to-3,072 FC matrix alone would
contain 2,359,296 anchor terms before its GELU or projection.

## Decision

Reject expanded anchor geometry as the dense GPT-2 matrix backend. It removes
the transport boundary, but a single loaded 768x768 evaluation is already
about 1.25 seconds and the page carries 28.8 MB of CSS source. HVAR performs the
dense multiplication much more compactly; its remaining problem is exposing
the resulting vector.

Retain balanced `anchor-size()` sums as a general CSS compiler optimization.
They remove a real Chromium expression-depth failure and may be useful for
small reductions, sparse routing, or merging a modest number of geometric
partials.

Artifacts:

- `n384-l1-balanced.html`, `n512-l1-balanced.html`, `n768-l1-balanced.html`
- `results.json`: rotated-navigation benchmark
- `mutation-results.json`: same-page input-mutation benchmark
- `../../tools/build_anchor_geometry_chain.py`
- `../../tools/test_anchor_geometry_chain.mjs`
- `../../tools/test_anchor_geometry_mutation.mjs`
