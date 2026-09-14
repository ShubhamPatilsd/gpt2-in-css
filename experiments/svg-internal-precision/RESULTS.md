# SVG internal precision by primitive

Measured in headless Chrome 153 on macOS. The runtime page contains no
JavaScript; the external Playwright harness screenshots its output.

## Question

Can a wide-gamut, linear-light, or alpha-backed SVG filter force Chromium to
retain more than eight bits between matrix operations?

Each sample differs from the next by about `1 / 64,512`, far below one 8-bit
code step. A first color matrix creates the sample, a selected filter primitive
passes it onward, and a final color matrix amplifies the tiny differences by
512. If the intermediate survives, all 64 samples become visibly distinct in
the final 8-bit screenshot. If it is rounded first, every sample becomes the
same value.

## Result

| Intermediate primitive | Distinct final levels | Interpretation |
|---|---:|---|
| adjacent color matrix | 64 / 64 | retained or fused |
| named identity color matrix | 64 / 64 | retained or fused |
| zero offset | 64 / 64 | retained or fused |
| one-input merge | 64 / 64 | retained or fused |
| copy-only arithmetic composite | 64 / 64 | optimized copy path |
| zero/small Gaussian blur | 64 / 64 | retained or fused |
| two-input arithmetic addition | 1 / 64 | quantized |
| two-input arithmetic multiplication | 1 / 64 | quantized |
| blend | 1 / 64 | quantized |
| convolution | 1 / 64 | quantized |
| component transfer | 1 / 64 | quantized |

The result is unchanged with `color-interpolation-filters="linearRGB"`,
Display-P3 and Rec.2020 source colors, Chrome forced to a Display-P3 output
profile, or values carried in alpha. `preserveAlpha="true"` on convolution
also does not retain sub-8-bit alpha values.

## Decision

Chromium does retain high precision through simple unary chains that it can
keep internal or fuse. That does not provide a GPT-2 matrix backend. The two
operations the current SVG implementation needs—combining a live activation
with a spatially varying weight image and reducing many products—cross the
quantized boundary. Even two-input addition does so.

Wide-gamut rendering is therefore not the missing precision switch. Further
SVG work should focus only on an algorithm that avoids multi-input compositing,
convolution, and component-transfer boundaries, rather than adding another
color space or storage channel to the current graph.

### HDR AVIF follow-up

A real 12-bit PQ AVIF does select a higher-precision decode path: locally
amplifying the complete ramp recovers about 2,069 levels. All-HDR arithmetic
can retain that lineage across repeated operations. The stronger real-matvec
test still shows no accuracy gain over ordinary 8-bit SDR, however, and adding
a computed SDR correction to an HDR carrier quantizes the correction normally.
HDR therefore improves static source precision without providing a reusable
computed-vector transport. See `../svg-hdr-matvec/RESULTS.md`.

Raw measurements are in `results-srgb.json` and `results-display-p3.json`.

## Reproduce

```sh
make test-svg-internal-precision
```
