# SVG reduction alternatives

These experiments test whether large `feConvolveMatrix` reductions can be
replaced by cheaper native SVG operations. Runtime fixtures contain no
JavaScript; Playwright is used only by the external measurement harnesses.

## Stable recomputation measurement

`tools/profile_svg_recompute_variance.mjs` now supports three invalidation
modes. Alternating two preloaded input URLs and toggling one arithmetic
coefficient both produce real recomputation without continually allocating new
image resources. A 15-round unique-URL run contained one doubled second sample
and then 13 stable samples. Ten alternating-URL samples stayed between 1.84 and
2.07 seconds. The normal two-block GPU-filter cost is therefore real, while the
occasional doubled sample is an invalidation/cold-resource artifact rather than
a periodic compute cost.

Shrinking the live layer-normalization filter from 3,072 columns to its actual
64-column extent, and block-1 LN1 from 3,072 to 256 columns, preserves output
but does not measurably change timing. Primitive subregions were already
restricting the demanded raster area.

## Layer-normalization reductions

| reducer | local RMSE | local max error | result |
| --- | ---: | ---: | --- |
| three 256-tap box reductions | 0.08234 | 0.19939 | retained baseline |
| six 128-tap reductions | 0.08234 | 0.19939 | accurate, no speed gain |
| four 192-tap reductions | 0.04525 | 0.14384 | more accurate, about 5% slower than 256 |
| two 384-tap reductions | 0.66655 | 1.22985 | rejected |
| one 768-tap reduction | 0.77285 | 1.37366 | rejected |
| parallel `E[x²] - E[x]²` | 0.15075 | 0.91860 | rejected: slower and less accurate |
| tiled Gaussian, 3 copies, sigma 384 | 0.06123 | 0.26072 | accurate candidate, modest speed only |
| hierarchical 4×4×4×4 | 0.08234 | 0.19939 | exact locally, 13.4% faster locally |
| hierarchical 16×16 | 0.13214 | 0.26494 | rejected |

The tiled Gaussian uses `feTile` to repeat the 768-row vector and samples a
wide blur from the center copy. A same-browser paired two-block test measured a
2.016-second median versus 2.145 seconds for the baseline (6.4% median gain),
but the Gaussian page also produced two doubled frames under side-by-side
pressure. A 12-stage normalization-only chain measured 1.049 seconds versus
1.083 seconds (3.1%). This is an accuracy option and a small normal-case win,
not an order-of-magnitude scaling change.

The hierarchical 4-tap reduction avoids Skia's large-kernel texture path. In a
14-round paired isolated-LN test it measured 828 ms versus 940 ms, a 13.4%
speedup with identical local output. Block-1 LN1 measured a smaller 5.1%
cumulative speedup, with RMSE changing from 0.0675 to 0.0725. However, replacing
all three connected normalizations caused two-block post-next-LN RMSE to rise
from 0.0608 to 0.1110 and did not improve full-chain latency. It is therefore
not retained as a general transformer reduction.

## Native resampling probes

- `feImage href="#element"` returned transparent black for both referenced
  `<svg>` and `<g>` fragments in the tested Chrome filter context.
- Geometrically compressing a filtered eight-row group selected its center
  value (`128`) rather than its mean (`112`).
- An untiled Gaussian could be calibrated on eight rows, but Chrome clamps the
  useful radius around sigma 500 for a 768-row 1:1 surface. It remained too
  nonuniform and produced 0.409 local LN RMSE.
- Cropping a cell, repeating it with `feTile`, and then blurring recovered the
  exact eight-row fixture mean. It remained only modestly faster at transformer
  scale because the taller blur surface adds raster work.

## QKV reductions

Replacing each centered 256-tap QKV reduction with tiled Gaussian blur was both
slower and invalid (about 1.51 seconds for isolated QKV, RMSE 1.39). A plain
4×4×4×4 hierarchy measured about 1.03 seconds with RMSE 1.35. Distributing the
required gain across the four hierarchy stages improved this only to 0.88
seconds and RMSE 1.08. The retained large convolution is about 0.72 seconds and
0.026 RMSE on the same fixture.

The failure mode is signed cancellation. Layer-normalization means are already
large 8-bit values, so staged averaging can preserve them. QKV dot products are
small deviations around the encoding center; every added 8-bit materialization
rounds or clips partial sums before positive and negative terms cancel.

## Decision

Keep centered QKV with the existing 256-tap reduction and keep the sharded
normalization path as the robust connected baseline. Tiled Gaussian and
hierarchical reductions remain useful experimental options, but neither is a
general full-GPT replacement. The next scalable backend must either preserve
higher precision across staged reductions or perform signed reduction in one
browser operation without Skia's large-kernel cost.
