# Browser-native compute probes

Measured in Google Chrome 153.0.8010.48 on macOS. Every runtime fixture is
HTML/CSS/images only. The Python harness uses Chromium screenshot mode and CDP
DOM/style inspection; it never evaluates or injects JavaScript.

## Result

No tested primitive replaces HVAR for an arbitrary dense 768x768 matrix.
However, two previously untested paths are useful:

1. Computed CSS colors are a real floating-point carrier. Relative colors and
   balanced `color-mix()` trees can pack three signed reductions in RGB and
   chain through nonlinear channel math without an RGBA8 intermediate.
2. Flex distribution plus `anchor-size()` implements an accurate geometric
   softmax and probability-weighted reduction. This is a credible shortcut for
   short-context attention, where the reduction is narrow rather than 768x768.

Additive transform animations and native resampling were also tested. Neither
is a general compute win, although shear transforms expose one unusual
timeline-to-geometry fusion described below.

## 1. Computed colors as RGB float SIMD

CSS Color 5 says relative-color channels are retained outside their reference
ranges until the color is finally resolved for display. Chrome stores a typed
`<color>` custom property as a computed color rather than as an image pixel.
That gives a numeric graph which does not pass through SVG's RGBA8 surfaces.

The precision probe placed values only 1/65,536 apart in the red channel,
passed them through 0, 32, or 128 registered `<color>` properties, then
amplified the difference 4,096 times at final paint. All 17 levels survived at
every depth. The direct row had zero byte error and the 32/128-stage rows had a
maximum final paint error of one byte.

A balanced `color-mix()` is an average. Each input scalar can first be expanded
to a signed three-channel contribution:

```css
color(srgb
  calc(var(--x17) * w-row0-17)
  calc(var(--x17) * w-row1-17)
  calc(var(--x17) * w-row2-17))
```

Mixing all input contributions and multiplying by the term count produces
three output rows at once. Negative and out-of-gamut intermediate channels
survived. Every tested dense result matched the expected final RGB bytes:

| Matrix | Weights | Runtime HTML | First unseen input state | Max channel error |
| ---: | ---: | ---: | ---: | ---: |
| 96x96 | 9,216 | 0.47 MB | 20.7 ms | 0 |
| 192x192 | 36,864 | 1.89 MB | 39.8 ms | 0 |
| 384x384 | 147,456 | 7.58 MB | 159.9 ms | 0 |
| 768x768 | 589,824 | 30.34 MB | 660.9 ms | 0 |

Repeated toggles of the same two inputs become much faster because Blink
reuses computed styles; those cache hits are not representative of inference.
The table reports the first previously unseen state.

A separate 24-wide `matmul -> approximate GELU -> matmul` graph also matched
all 24 expected output channels exactly at final paint. This proves that colors
are composable across a nonlinear boundary, not just a terminal dot-product
trick.

Decision: retain this as an exact reference backend and for small terminal or
sensitivity-critical arithmetic. Reject it for every GPT-2 dense layer: one
768x768 operation is roughly ten times the existing 64.2 ms HVAR projection
oracle and expands to 30 MB before GELU or another matrix.

## 2. Flexbox as softmax, anchors as the weighted reduction

With zero flex bases, flexbox assigns widths in proportion to `flex-grow`.
Chrome accepts the CSS `exp()` function in that numeric property:

```css
.token { flex: exp(var(--score)) 1 0; }
```

Therefore each token width is directly proportional to
`exp(score) / sum(exp(score))`; no explicit reciprocal is needed. Three score
sets, including a large `[-7, 3]` range and a nearly tied set, matched expected
4,096-pixel softmax boundaries within 0.48 px.

Each probability box was then named as an anchor. A later positioned box used
one short reduction:

```css
width: calc(
  (C + var(--v0)) * anchor-size(--p0 width) +
  (C + var(--v1)) * anchor-size(--p1 width) +
  ...);
```

The positive offset `C` permits signed values and subtracts back out after
readback because the probabilities sum to one. All three cases matched within
0.315 px at a 2,048 px encoding scale, or less than 0.000154 decoded error.

Decision: this is the best integration candidate from this pass. It does not
replace dense HVAR projections, but it can collapse exponentiation,
normalization, and the short token-axis value reduction into one flex layout
plus one anchor expression per context coordinate. Test it next on the real
two-token/short-context attention fixture against the current CSS arithmetic
path.

## 3. Additive transform matrices

Paused animations can encode an input as progress, while a keyframe endpoint
encodes a weight. `animation-composition: add` concatenates translations, and
translations sum. A nine-keyframe integer-weight codebook produced exact
matrix positions through 384x384:

| Matrix | Animation effects | HTML | Cold screenshot including Chrome startup |
| ---: | ---: | ---: | ---: |
| 32x32 | 1,024 | 7.3 KB | 0.91 s |
| 64x64 | 4,096 | 19.7 KB | 0.92 s |
| 128x128 | 16,384 | 63.0 KB | 1.10 s |
| 256x256 | 65,536 | 223 KB | 1.95 s |
| 384x384 | 147,456 | 482 KB | 3.22 s |
| 768x768 | 589,824 | 1.8 MB | did not render within 45 s |

The source representation is compact, but Chromium's animation-effect count
is the wall. Reject this for dense matrices.

The dynamic version is more interesting: animation progress supplied Q and a
custom-property endpoint supplied K. Twenty-four independent 64-term Q dot K
scores were exact and a new shared query took about 14-16 ms. A direct CSS
`calc()` control performed the same 1,536 multiplies in about 1-2 ms, so the
animation route is not intrinsically faster.

One unusual handoff did work. Replacing translations with upper-triangular
shear matrices makes their additive dot product change the transformed
bounding-box width. Chrome's `anchor-size()` observed that transformed width;
eight 16-term dynamic dots were recovered with zero pixel error. This can fuse
a timeline-progress read with a small reduction when the progress has not yet
been materialized as a CSS number. Otherwise direct `calc()` is preferable.

## 4. Native resampling

Static PNG downscaling averaged alternating and half-black/half-white patterns
to 128, but mapped a one-pixel impulse to 0 rather than the expected 3.98.
Live HTML transform and inline-SVG downscaling were strongly biased (for
example 185 and 192 instead of 127.5). The image decoder can make a pleasant
thumbnail, but none of these paths is an accurate reusable reducer for dynamic
activations.

## Recommendation

Keep HVAR as the measured dense backend. The next experiment should replace
only the softmax/value-reduction portion of the real attention fixture with
the flex/anchor construction. In parallel, retain the RGB computed-color
backend as a precision oracle and consider it only for reductions small enough
that expanded O(weights) style work stays below the HVAR/timeline cost.

The transform/shear route is a third-choice specialization for consuming
timeline progress directly; the direct CSS control shows it should not be used
once values already exist as registered numbers.

## Reproduce

```sh
python3 tools/probe_browser_native_compute.py
```

Set `CHROME_BIN` to select another Chromium executable. Raw measurements and
generated fixtures are in `results.json` and this directory.

Relevant platform definitions:

- [CSS Color 5 relative colors](https://www.w3.org/TR/css-color-5/#relative-colors)
- [CSS exponential functions](https://www.w3.org/TR/css-values-4/#exponent-funcs)
- [Flex distribution algorithm](https://www.w3.org/TR/css-flexbox-1/#resolve-flexible-lengths)
- [CSS animation composition](https://www.w3.org/TR/css-animations-2/#animation-composition)
- [Anchor sizing](https://www.w3.org/TR/css-anchor-position-1/#anchor-size)
