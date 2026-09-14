# Chromium F16 SVG-filter moonshot audit

## Decision

**Technically plausible, but not runnable on this workstation yet.** A narrow
Chromium/Skia patch can force image-filter save layers and their materialized
intermediates to RGBA16F without changing GPT-2-small's architecture or
checkpoint. This is the only audited route with credible order-of-magnitude
potential because it preserves the already-fast dense SVG execution shape
while attacking its observed 8-bit intermediate-surface failure directly.

The current machine has no Chromium checkout and only 4.9 GiB free. Chromium's
official build instructions require at least 100 GB free, so checkout/build is
blocked by local storage rather than by an unresolved source path. No Chromium
or browser files were modified.

## Source path and scoped patch

Audit baseline: Chromium `6d39329f...`, which pins Skia `7a6fd7ff...` in
[DEPS](https://chromium.googlesource.com/chromium/src/+/6d39329fd7eed40e155125fba10835d5c96cb798/DEPS#344).

Blink converts SVG primitives into backend-independent paint filters:

- [`feColorMatrix`](https://chromium.googlesource.com/chromium/src/+/6d39329fd7eed40e155125fba10835d5c96cb798/third_party/blink/renderer/platform/graphics/filters/fe_color_matrix.cc#152)
- [`feComponentTransfer`](https://chromium.googlesource.com/chromium/src/+/6d39329fd7eed40e155125fba10835d5c96cb798/third_party/blink/renderer/platform/graphics/filters/fe_component_transfer.cc#134)
- [`feComposite`](https://chromium.googlesource.com/chromium/src/+/6d39329fd7eed40e155125fba10835d5c96cb798/third_party/blink/renderer/platform/graphics/filters/fe_composite.cc#171)
- [`feConvolveMatrix`](https://chromium.googlesource.com/chromium/src/+/6d39329fd7eed40e155125fba10835d5c96cb798/third_party/blink/renderer/platform/graphics/filters/fe_convolve_matrix.cc#138)
- [`feOffset`](https://chromium.googlesource.com/chromium/src/+/6d39329fd7eed40e155125fba10835d5c96cb798/third_party/blink/renderer/platform/graphics/filters/fe_offset.cc#60)

The format is selected later. [`SkCanvas::image_filter_color_type()`](https://skia.googlesource.com/skia/+/7a6fd7ff72d5d2d2ecf08b0a98823583888042b3/src/core/SkCanvas.cpp#671)
normally inherits the destination color type. `SkDevice::drawFilteredImage()`
places that type in the filter context, and every materialized intermediate
device inherits it through [`SkImageFilterTypes.cpp`](https://skia.googlesource.com/skia/+/7a6fd7ff72d5d2d2ecf08b0a98823583888042b3/src/core/SkImageFilterTypes.cpp#186).
Ordinary SDR web tiles are therefore N32/RGBA8 even though Skia supports F16.

The smallest scoped proof patch is at the two raster playback sites in
[`cc/paint/paint_op.cc`](https://chromium.googlesource.com/chromium/src/+/6d39329fd7eed40e155125fba10835d5c96cb798/cc/paint/paint_op.cc#1849):

1. In `SaveLayerOp::RasterWithFlags`, use `SkCanvas::SaveLayerRec` and request
   `kF16ColorType` when the paint contains an image filter.
2. In `SaveLayerFiltersOp::RasterWithFlags`, request `kF16ColorType` when its
   filter list or backdrop filter is nonempty.

This should propagate F16 through both the source layer and all materialized
Skia image-filter surfaces. Instrumentation must assert the actual source and
`AutoSurface` color types; format inference from screenshots is insufficient.

## Separate precision limits

F16 surfaces do not solve every primitive automatically.

- `feComponentTransfer` is compiled to four 256-byte lookup tables. The CPU
  pipeline converts to an 8-bit index and returns an 8-bit table value in
  [`byte_tables`](https://skia.googlesource.com/skia/+/7a6fd7ff72d5d2d2ecf08b0a98823583888042b3/src/opts/SkRasterPipeline_opts.h#2983).
  A minimal probe patch should bypass the LUT for semantic identity functions;
  general high-precision transfer needs a float representation across Blink,
  cc serialization, and Skia.
- Large `feConvolveMatrix` kernels are stored in an A8 coefficient texture by
  [`create_kernel_bitmap()`](https://skia.googlesource.com/skia/+/7a6fd7ff72d5d2d2ecf08b0a98823583888042b3/src/effects/imagefilters/SkMatrixConvolutionImageFilter.cpp#165).
  The repo's all-ones reductions are exactly representable, but arbitrary GPT
  weight kernels would need another representation.

There is no reliable stock flag for ordinary SDR filters. Chromium exposes
`--force-raster-color-profile=scrgb-linear`, but tile allocation selects F16
only when both the target and recorded content are HDR. The existing HDR
experiments already show why this is not a general escape: HDR source lineage
can retain precision while newly computed SDR corrections quantize.

## First falsifiable build gate

Use 64 opaque samples `v_i = i / 65535` near zero, pass them through each
primitive and a combined chain, then multiply by 1024 before ordinary 8-bit
readback. Test identity color matrix, 1x1 convolution, identity component
transfer, non-copy arithmetic composite, and offset followed by a forced
materialization barrier.

Success requires:

- 64 distinct monotonic levels after every primitive and the combined chain;
- instrumented F16 source and intermediate devices on GPU and raster paths;
- unchanged-checkpoint SVG screens reaching 64/64 teacher-forced and 48/48
  generation decisions;
- less than 2.2x peak filter memory and less than 2x warm runtime.

Kill the branch if any materialization collapses below 64 levels, identity
component transfer still quantizes, either backend silently falls to N32, or
the microprobe passes without materially improving the full GPT-2 screens.

Official Chromium guidance documents the 100 GB free-space minimum in the
[build instructions](https://chromium.googlesource.com/chromium/src/+/main/docs/linux/build_instructions.md).
