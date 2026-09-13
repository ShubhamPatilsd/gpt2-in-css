# HDR SVG precision and real matvec

These runtime fixtures contain no JavaScript. An external Playwright harness
captures the pixels and compares them with the real GPT-2 tensor result.

## What was tested

The experiment asks whether a 12-bit PQ AVIF can force Chromium's SVG filter
graph to keep more than eight bits through the operations needed by a matrix
multiply.

Four supporting probes isolate the possible mechanisms:

1. `svg-avif-precision` passes adjacent 12-bit codes through individual SVG
   primitives.
2. `svg-hdr-carrier-transport` adds a newly computed sub-8-bit correction to a
   live HDR pixel.
3. `svg-hdr-compute-chain` repeats two-input arithmetic and convolution while
   every source remains HDR-derived.
4. `svg-hdr-codebook` locally amplifies all 4,096 PQ codes to recover the
   browser's usable numeric codebook.

The final page performs a real GPT-2 block-0 `64x64` projection tile three
ways: ordinary 8-bit SDR operands, 12-bit HDR activation and weight images,
and HDR activation with full-precision weights embedded directly in 64
convolution kernels.

## Findings

- The full PQ ramp exposes 2,069 recovered levels overall and about 970 usable
  levels in the selected `[0.05, 0.95]` filter range.
- Adding an SDR-computed correction to an HDR carrier does not promote it. The
  HDR and SDR cases retain the same number of levels.
- A chain whose operands are all HDR-derived retains 32 narrow-ramp levels
  through twelve arithmetic/convolution stages with scRGB/HDR output and 22
  levels with the default sRGB output. The lineage matters.
- That lineage does not improve the real matrix result. The arithmetic product
  and reduction still dominate the error.

Default sRGB Chrome result:

| 64x64 path | RMSE vs float | compute-only RMSE |
| --- | ---: | ---: |
| ordinary 8-bit SDR product image | **0.02158** | **0.01933** |
| 12-bit PQ HDR product image | 0.02212 | 0.02148 |
| HDR activation, float convolution kernels | 0.02692 | 0.02665 |

The combined three-path page takes about 66-68 ms per warm screenshot. That
number is useful only as a probe cost; it is not a standalone per-path latency.

## Decision

Reject HDR AVIF as the missing general SVG numerical backend. Chromium can
retain extra precision already present in an HDR-decoded image, but a real
matrix multiply is no more accurate than the ordinary 8-bit representation.
An HDR carrier also cannot preserve a newly created low-order correction.

Embedding weights directly in convolution attributes avoids the weight-image
product but needs one large kernel primitive per output and is less accurate on
this fixture. It therefore does not solve either accuracy or full-model scale.

Raw measurements are in `results.json`; the recovered PQ map is in
`../svg-hdr-codebook/codebook-srgb.json`.

## Reproduce

```sh
make test-svg-hdr-matvec
```
