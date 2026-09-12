# Spatially batched GPT-2 attention heads

This experiment asks whether the twelve independent GPT-2 attention heads
should be expressed as twelve copies of an SVG graph or as lanes inside shared
image operations. The generated runtime is HTML/SVG only and contains no
JavaScript.

The retained page performs real two-token, twelve-head causal attention:

- Q/K products for both source tokens;
- fused score subtraction;
- twelve 64-value reductions;
- sigmoid form of the two-item softmax;
- weighted mixing of both V vectors.

It uses exact precomputed Q/K/V input surfaces so the measurement isolates the
attention mixer, matching the existing `svg-multitoken-attention/index.html`
baseline.

## Retained layout

Q, K, and V values are stored as twelve contiguous 64-value head segments in a
single 768-pixel row. Pixelwise Q×K work is shared across the complete row. The
two scores are subtracted before reduction, halving the number of dot-product
reductions. Each head retains its own scale normalization and convolution
divisor, which is essential because a single global coefficient causes smaller
heads to disappear in 8-bit scale images.

Direct 64-tap reductions are reliable in this fused layout. The resulting
probabilities are tiled over the corresponding 64-value V segment and all
heads are mixed in the same value surface.

## Chromium A/B result

Both pages were measured for nine navigations and screenshots in the same
Chrome process; the first run was excluded from the warm mean.

| Attention core | warm mean | context RMSE | max context error | max probability error |
| --- | ---: | ---: | ---: | ---: |
| Original head-by-head graph | 139.0 ms | 0.001053 | 0.00689 | 0.00845 |
| Spatially batched graph | 140.5 ms | 0.001947 | 0.01968 | 0.03087 |

The speed ratio is 0.989×: effectively no latency improvement. The graph and
bundle reductions are nevertheless large:

| Attention core | top-level primitives | HTML | referenced assets | runtime total | Brotli q5 HTML |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original | 615 | 527,666 B | 12,625 B | 540,291 B | 21,108 B |
| Spatially batched | 116 | 47,430 B | 5,525 B | 52,955 B | 3,774 B |

This is a **5.3× graph reduction** and a **10.2× runtime-bundle reduction** at
roughly equal latency. It proves that repeated SVG markup and object count were
not the main cost of this small attention mixer; convolution and raster work
dominate. The layout is still useful for preventing bundle explosion when
multi-token attention is repeated through twelve blocks.

## Rejected layouts

- Putting heads in separate rows under one `feConvolveMatrix` was fast but
  Chromium produced valid reductions for only a subset of rows.
- Padding all heads into one 3,072-pixel surface was accurate, but the extra
  pixel area erased the savings from fewer primitives.
- Computing densely and relocating terms into padded lanes with `feOffset`
  corrupted the signed surface and was slower.
- A shared scale maximum destroyed small per-head coefficients. Per-head scale
  normalization plus a post-reduction magnitude restore fixed it.

Intermediate reports are retained as `results-horizontal.json`,
`results-lane-reductions.json`, `results-lane-scaled.json`,
`results-lane-divisors.json`, and `results-dense-scatter.json`. The authoritative
retained result is `results.json`.

## Decision

Use spatial head batching to shrink generated pages and graph size, not as a
claimed speed optimization. For latency, prioritize operations like the
32-group GELU where RGB packing actually reduced warm time by 1.82×. Full
inference should combine both techniques: spatial batching for repeated linear
head structure and RGB packing for independent nonlinear/range branches.

A subsequent attempt to merge the existing 72 live QKV result surfaces into
the required six compact inputs failed: all probabilities rendered as zero and
warm latency rose from 1.44 to 2.38 seconds. Spatial batching therefore cannot
currently cross that live SVG result boundary. See
`../svg-connected-batched-attention/RESULTS.md`.

## Contiguous live-input follow-up

The later `../svg-contiguous-qkv-batched-native-convolve/` experiment removed
that merge boundary by producing six contiguous 768-value Q/K/V surfaces
directly. It also replaced the live-result-incompatible probability tiling with
a repeated-sum convolution and kept attention at the QKV surface's native
coordinate. This path is accurate and shrinks connected HTML from 1.71 MB to
120 KB, but a controlled current-context benchmark measured 1,103 ms versus
925 ms for head-local attention. Retain head-local surfaces for latency; test
smaller contiguous head groups only as a bundle/runtime compromise.

That proposed intermediate-width sweep was subsequently completed. Groups of
2, 3, 4, and 6 heads were all slower than the 64-wide head-local layout, so no
width compromise was retained. The successful follow-up instead packs each
head's Q, K, and V into RGB while preserving the 64-wide geometry. With one
explicit raster boundary before attention, `../svg-multitoken-attention-rgb-tile/`
is accurate and improves connected median latency by 1.15× while reducing HTML
by 1.53×.
