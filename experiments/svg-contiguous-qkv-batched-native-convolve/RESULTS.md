# Contiguous live QKV into native-position batched attention

This experiment tests whether live GPT-2 Q/K/V vectors should be born as
contiguous matrices and consumed by a spatially batched attention core. The
runtime is HTML/SVG only and contains no JavaScript.

## Compared layouts

The existing connected implementation computes 72 head-local surfaces:

- two tokens;
- Q, K, and V;
- twelve 64-value heads.

Two alternatives were generated from the same block-0 weights and inputs:

- six 768-value surfaces, one Q/K/V surface per token;
- two 2,304-value QKV surfaces, one per token.

The original batched-attention adapter was not reused. It relocated and merged
live head surfaces after the matrix calculation, which Chromium rendered as
zero. Here the vectors are produced contiguously by the matrix itself.

## Contiguous QKV alone

Five alternating warm trials in one Chrome process gave:

| Layout | connected median | context RMSE | HTML |
| --- | ---: | ---: | ---: |
| 72 head-local surfaces | 1,506.8 ms | 0.007654 | 1,706,770 B |
| six part-contiguous surfaces | 2,090.8 ms | 0.005413 | 637,630 B |
| two vector-born surfaces | 2,036.5 ms | 0.005516 | 592,316 B |

The contiguous matrices reduce HTML by 2.7–2.9× but are 35–39% slower once
their results are split back into heads. A shared wide surface is therefore
not a latency optimization when it fans back out to many consumers.

The comparison is reproducible with:

```sh
node tools/benchmark_svg_multitoken_qkv_layouts.mjs
```

## Direct batched consumer

Connecting the six part-contiguous surfaces directly to the compact attention
core removed the head fan-out. The first version appeared to run in about 430
ms, but it was invalid: `feOffset` plus `feTile` turned the live per-head
probabilities into zero, so Chromium skipped the value mixture.

A stage trace located the first invalid result precisely:

```text
live Q/K → signed Q/K → products → score reduction → sigmoid: valid
per-head probability feOffset → feTile: zero
weighted V → context: zero
```

The retained version replaces the failing scalar tile with a 127-tap
convolution. Each head's 64 score terms are cropped without relocation, and
the convolution emits the same reduced score over all 64 positions. Attention
then remains at the live QKV surface's native `y=255` coordinate.

With exact precomputed Q/K/V inputs, this broadcast method is valid and is
slightly faster than the original compact mixer:

| Mixer | warm mean | context RMSE | probability max error |
| --- | ---: | ---: | ---: |
| Original scalar tile | 138.3 ms | 0.001053 | 0.00845 |
| Repeated-sum convolution | 126.1 ms | 0.001947 | 0.03087 |

## Authoritative connected result

Seven alternating warm trials exposed only the current token's actual
768-value context, preventing demand-driven skipping:

| Connected implementation | median | context RMSE | max error |
| --- | ---: | ---: | ---: |
| Existing head-local | 924.9 ms | 0.006342 | 0.06737 |
| Contiguous native-position | 1,103.2 ms | 0.005567 | 0.02891 |

The contiguous path's maximum attention-probability error is 0.03087. It is
accurate, but its latency ratio is 0.838×: about 19% slower than preserving
head-local QKV surfaces.

The graph-size reduction is substantial:

| Connected implementation | HTML | `<fe*>` nodes |
| --- | ---: | ---: |
| Existing head-local | 1,706,770 B | 5,388 |
| Contiguous native-position | 120,381 B | 435 |

That is a 14.2× HTML reduction and a 12.4× filter-node reduction.

The stage trace is reproducible with:

```sh
SVG_CONTIGUOUS_TRACE_URL=http://127.0.0.1:4178/experiments/svg-contiguous-qkv-batched-native-convolve/index.html \
  node tools/trace_svg_contiguous_qkv_attention.mjs
```

The controlled comparison is reproducible with:

```sh
node tools/benchmark_svg_connected_native_attention.mjs
```

## Decision

Do not replace the current head-local connected attention for latency. Do use
contiguous grouping as a bundle-size technique if generated graph size becomes
the limiting constraint.

The next latency experiment should test intermediate groups of two, three, or
four heads. The results establish the endpoints: 64-wide head-local surfaces
are fastest, while 768-wide part surfaces are far smaller. A grouped layout can
search for the point that retains most of the 12.4× graph reduction without
paying the full 19% runtime penalty. Groups must be born contiguous and consumed
at their native coordinates; post-matrix relocation and scalar tiling are both
known-invalid boundaries.
