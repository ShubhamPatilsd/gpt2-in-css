# Direct mixed-context attention projection

This experiment removes duplicated attention work from GPT-2's attention
projection. The runtime pages are HTML/SVG only and contain no JavaScript.

## What changed

The older connected page computes the two-token attention mixture separately
inside every `(head, source token)` projection branch. That creates 24
projection inputs and repeats work that the attention stage has already done.

The direct path inserts a raster boundary after attention and feeds the
resulting 768-value mixed-context vector directly into `c_proj`. Projection now
uses 12 head slices, one per head, without reconstructing attention weights.

```text
old: QKV -> attention -> recompute 12 heads x 2 source tokens -> c_proj
new: QKV -> attention -> 768 mixed-context values -> c_proj
```

## Nine-round alternating benchmark

Each variant was warmed once and then measured nine times in alternating order
inside the same Chrome process. Every measurement screenshots and decodes all
768 residual outputs.

| Path | median | RMSE | max error | HTML | all primitives | projection primitives |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Recomputed projection | 2,847.6 ms | 0.03643 | 0.25973 | 2,905,222 B | 13,326 | 10,142 |
| Direct mixed context | **1,531.4 ms** | **0.03343** | 0.36910 | 2,127,615 B | 8,471 | 5,287 |
| RGB-packed direct projection | 2,897.5 ms | 0.05838 | 0.67096 | 1,991,570 B | 7,758 | 4,574 |

The direct mixed-context path is **1.86x faster** than the recomputed path. It
also removes 49% of the projection stage, 36% of all filter primitives, and
777,607 bytes of HTML. The QKV and attention stages contribute the shared 3,184
primitives in each staged page.

## RGB projection result

Packing three head dot products into RGB initially failed at 1.14 RMSE. The
failure was not ordinary clipping headroom: arithmetic subtraction produced an
alpha of `128/255`, which clipped every positive channel value at the encoding
center.

Keeping positive and negative sums in separate R/G channels until the final
collapse fixes that structural error. A headroom sweep found 2x to be the best
tested point:

| headroom | RMSE | max error |
| ---: | ---: | ---: |
| 1.10x | 0.08069 | 1.69049 |
| 1.25x | 0.07315 | 1.57775 |
| 1.50x | 0.07306 | 1.49722 |
| **2.00x** | **0.05838** | **0.67096** |
| 2.50x | 0.06471 | 0.58023 |
| 3.00x | 0.11701 | 1.85755 |
| 4.00x | 0.11773 | 1.22168 |

The corrected RGB path is numerically usable, but it is 1.89x slower than the
separate-channel direct path and less accurate. Fewer SVG primitives do not
guarantee less raster work; the extra channel routing and packed surfaces cost
more than the removed convolutions save.

## Decision

Retain the separate-channel direct mixed-context projection and reject RGB
packing for `c_proj`. The later centered-product experiment improves the QKV
front of this same path without changing this projection decision.

## Current stage costs

A separate nine-round run measured the accepted RGB QKV/attention path:

| demanded output | median |
| --- | ---: |
| QKV debug surface | 662.7 ms |
| QKV plus attention context | 1,140.5 ms |
| QKV plus attention plus direct projection/residual | 1,531.4 ms |

These pages expose different output geometries, so the differences are a
profiling estimate rather than perfectly isolated stage timings. They indicate
roughly 0.48 seconds beyond QKV for attention and 0.39 seconds beyond attention
for direct `c_proj` plus the residual. QKV is now the largest individual target;
projection is no longer the dominant stage.

## Centered-QKV follow-up

Replacing split positive/negative QKV with one midpoint-centered convolution
per shard reduces forced full residual recomputation from 1,154–1,158 ms to
563–584 ms, a repeatable 1.98–2.05x speedup. Full residual RMSE changes only
from 0.03343 to 0.03490, and maximum error remains 0.36910.

The current best connected boundary is therefore:

```text
centered RGB QKV -> raster boundary -> attention -> raster boundary
-> separate-channel direct c_proj -> residual
```

See `../svg-multitoken-attention-rgb-centered/RESULTS.md`.

Rebuild and benchmark with:

```sh
python3 tools/build_svg_staged_mixed_projection.py

SVG_MIXED_CPROJ_PACK=rgb \
SVG_MIXED_CPROJ_HEADROOM=2 \
SVG_MIXED_PROJECTION_OUT=experiments/svg-staged-mixed-projection-rgb \
  python3 tools/build_svg_staged_mixed_projection.py

SVG_RESIDUAL_BENCH_SET=mixed SVG_RESIDUAL_BENCH_ROUNDS=9 \
  node tools/benchmark_svg_attention_residual_paths.mjs
```
