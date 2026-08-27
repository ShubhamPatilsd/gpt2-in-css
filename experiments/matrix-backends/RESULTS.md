# HTML/CSS-only 64×64 matrix backend results

Measured in Chromium on August 26, 2026. Neither page contains JavaScript.

## Result

| Backend | Arithmetic | Browser result | Runtime bundle (raw / Brotli) | Verdict |
| --- | --- | --- | ---: | --- |
| Variable font + HVAR | 4,096 signed integer weights; 64 continuous inputs | All 64 outputs; max absolute error `0.2383`, mean `0.1168` | `38,434 B` / `10,930 B` | Works and can return numeric results to CSS |
| Direct-compiled HVAR | Same matrix and inputs | Identical 64 outputs and error | `34,253 B` / `6,754 B` | Same computation without redundant glyph-variation data |
| SVG filters + PNG tensor | 4-bit unsigned weights; 3-bit inputs; 8-bit output | 63 non-edge pixels were within roughly one 8-bit level according to the browser-computed 16× difference strip | `25,485 B` / `7,132 B` | Performs the matvec, but the result remains pixels and is resolution-sensitive |

Warm reload-to-screenshot medians were `101 ms` for the font page and `102 ms` for the SVG page over nine cached runs. This is an end-to-end browser measurement dominated by reload, layout, and screenshot overhead. It does **not** isolate the time spent on 4,096 multiply-accumulates.

## What each experiment does

### Variable font

- Each input vector coordinate is one variable-font axis.
- Each output row is one glyph.
- The glyph's horizontal advance is the base width plus that row's dot product.
- Anchor sizing, inline-size container queries, and registered custom properties turn each rendered advance back into a CSS number.
- WOFF2 reduces the matrix font from `81,188 B` to `8,868 B`.
- Writing `fvar` and `HVAR` directly reduces it further to `4,680 B` WOFF2.
- Chromium rejected the first WOFF2 because every glyph was contourless. Giving each glyph a one-font-unit square fixed browser loading without changing its advance.

This path has the important property the SVG path lacks: the result is a number that another CSS calculation can consume.

### SVG filters

- A `64×64` PNG stores the matrix.
- Sixty-four one-pixel rows encode the input vector.
- Arithmetic `feComposite` multiplies the input and weights component-wise.
- A `1×64` `feConvolveMatrix` reduction sums each column.
- The PNG is transposed because raster columns represent output neurons while raster rows represent input features.

The filter kernel is applied in layer-space pixels in Chromium's Skia backend. Enlarging the SVG before filtering changed which input rows the 64-pixel kernel covered and therefore changed the answer. The working page computes at native vertical resolution and only repeats the finished rows for visibility. Skia also stores larger convolution kernels in an 8-bit texture and explicitly notes that kernels larger than `5×5` quickly exceed realtime capability. See the [Skia matrix-convolution implementation](https://chromium.googlesource.com/experimental/external/gob/skia/skia/+/fc46d066b5b61503e660c9a25a8689f094ee9b04/src/effects/imagefilters/SkMatrixConvolutionImageFilter.cpp#181) and the [Filter Effects specification](https://www.w3.org/TR/filter-effects-1/#feConvolveMatrixElement).

## What this means for GPT-2

The variable-font path is worth scaling. It compresses weights unusually well and exposes its output to CSS. The follow-up tests at `128`, `256`, and `768` dimensions are documented in [the scaling results](../matrix-scaling/RESULTS.md).

The SVG path is not a good foundation for a multi-layer transformer. Signed weights require at least a positive/negative split, intermediate values are quantized pixels, rendering scale changes the operation, and there is no clean CSS-only conversion from 64 output pixels back into 64 numeric custom properties for the next layer. It remains useful as a compact proof that the browser's image-filter backend can execute a packed dot-product reduction.

## Reproduce

```sh
make test-matrix-backends
python3 -m http.server 4177
```

Open:

- `http://127.0.0.1:4177/experiments/matrix-backends/variable-font.html`
- `http://127.0.0.1:4177/experiments/matrix-backends/svg-pixel.html`
