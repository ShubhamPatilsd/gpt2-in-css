# Single-glyph vector raster

## Result

COLRv1 can encode a dense linear vector in one variable color glyph.  Each
output is a `PaintVarScale` layer whose horizontal scale has its own delta row
over the live variation axes.  The page shapes one text glyph; no output is a
DOM element.

The glyph's painted bars can be consumed directly inside one SVG filter graph.
The retained page performs three operations without CSS numeric readback:

1. a horizontal convolution turns each bar width into one raster value;
2. `feComponentTransfer` applies a piecewise nonlinear map to the whole vector;
3. a second convolution averages the first 256 mapped values and places that
   scalar next to the vector.

This is genuine raster reuse.  It is limited to the same SVG filter graph; it
does not expose CSS numbers or variation axes for another font.

## Chrome 153 measurements

The runtime pages contain HTML, CSS, SVG, and fonts only.  Playwright exists
only in the external mutation/screenshot harness.

| Live axes | Vector outputs | COLRv1 layers | WOFF2 | Live elements | Warm mutation + raster read | Vector RMSE | Max error |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | 64 | 64 | 6,932 B | 22 | 66.67 ms | 0.00236 | 0.00535 |
| 256 | 256 | 256 | 69,844 B | 22 | 67.19 ms | 0.00263 | 0.00627 |
| 256 | 3,072 | 3,072 | 722,788 B | 22 | 366.43 ms | 0.00249 | 0.00687 |

The downstream mean's maximum absolute error was 0.00123, 0.00181, and
0.00229 respectively.  On the 3,072-output page, an alternate axis vector
changed 2,375 raster pixels and the measured-versus-expected change correlation
was 0.9782.  The other changes were smaller than one 8-bit raster step.

Element count stays constant because the 3,072 output objects are inside the
font's COLR paint graph.  Runtime does not stay constant: Chromium still walks
and paints all 3,072 `PaintVarScale` layers.

A cached screenshot of the settled 3,072-row surface takes 82.05 ms.  The
matched mutation plus screenshot takes 366.43 ms, leaving roughly 284.38 ms of
additional variation/paint/filter work.  At 64 and 256 outputs the cached-read
and mutation-read medians are both about 67 ms, so screenshot synchronization
is the measurement floor there.

## Comparison with the existing gvar glyph

The existing `gvar-vector-glyph` already puts 3,072 output rectangles in one
ordinary variable outline.  Its saved result is:

| 3,072-output representation | WOFF2 | Live elements | Warm mutation + raster read |
| --- | ---: | ---: | ---: |
| complex `gvar` outline | 2,024,288 B | 12 | 84.69 ms |
| COLRv1 variable paint layers | 722,788 B | 22 | 366.43 ms |

COLRv1 is 64.3% smaller on disk but **4.33x slower** at 3,072 outputs.  The
extra ten live elements in this page are the second-stage filter proof, not
output carriers.  The important scaling difference is internal: the gvar
outline is rasterized as one varied path, while COLRv1 retains one paint node
per output.

Therefore the existing gvar glyph remains the preferred one-object vector
export.  COLRv1 is useful evidence that paint graphs can hold independent
linear output rows, but it does not improve the scaling bottleneck.

## Reuse boundary

Raster results are reusable for elementwise maps, channel arithmetic,
compositing, and spatially shared convolutions inside the active filter.
They are not a general dense-vector backend:

- `feConvolveMatrix` applies one spatially invariant kernel.  An arbitrary
  matrix needs a different weight row for every output.
- The existing direct-projection probe works through 256 kernel inputs, then
  Chrome returns clamped or invalid results at 512 and above.  A real
  3,072-to-768 projection would need 9,216 separate 256-input convolutions.
- Filter results are scoped image buffers.  SVG provides no operation that
  turns all pixels into a CSS numeric vector or another font's variation axes.
- Each filter boundary stores ordinary color samples, so deep chains retain the
  already-measured 8-bit quantization problem.

The answer is consequently split:

- **Yes:** one glyph can emit a large independent vector, and subsequent SVG
  primitives can consume it immediately.
- **No:** that raster cannot become a cheap, precise, generally reusable vector
  across arbitrary dense matrices or return to the font backend.

## Reproduce

```sh
uv run --with numpy --with fonttools --with brotli \
  python tools/build_single_glyph_vector_raster.py
node tools/test_single_glyph_vector_raster.mjs

SINGLE_GLYPH_INPUTS=256 SINGLE_GLYPH_OUTPUTS=256 \
  uv run --with numpy --with fonttools --with brotli \
  python tools/build_single_glyph_vector_raster.py
SINGLE_GLYPH_INPUTS=256 SINGLE_GLYPH_OUTPUTS=256 \
  node tools/test_single_glyph_vector_raster.mjs

SINGLE_GLYPH_INPUTS=256 SINGLE_GLYPH_OUTPUTS=3072 \
  uv run --with numpy --with fonttools --with brotli \
  python tools/build_single_glyph_vector_raster.py
SINGLE_GLYPH_INPUTS=256 SINGLE_GLYPH_OUTPUTS=3072 \
  node tools/test_single_glyph_vector_raster.mjs
```
