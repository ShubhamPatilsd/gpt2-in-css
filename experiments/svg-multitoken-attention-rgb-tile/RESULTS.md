# RGB-packed live QKV with raster-staged attention

This experiment packs each head's Q, K, and V projection values into the R,
G, and B channels of one 64-pixel surface. The runtime page is HTML/SVG only
and contains no JavaScript.

## Representation

The retained head-local implementation computes Q, K, and V as three separate
64-output matrix branches. The packed implementation keeps the same reliable
`256 × 64` shard geometry but stores the three output tensors in RGB:

- positive dot-product terms are accumulated in one RGB surface;
- negative terms are accumulated in a second RGB surface;
- two RGB convolutions replace three sign-paired tensor convolutions;
- Q, K, and V are extracted with color matrices after their shared bias and
  two-plane scale correction.

Both scale planes remain centered around `128/255`. This is required because
SVG clamps every intermediate surface; storing signed correction deltas
directly erased negative values.

## QKV accuracy

The packed QKV surface passes the existing browser gate:

| Layout | QKV RMSE | max error | Q RMSE | K RMSE | V RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Existing head-local | 0.024037 | 0.23796 | — | — | — |
| RGB packed | 0.023752 | 0.21878 | 0.02153 | 0.03471 | 0.00487 |

The QKV-only page shrinks from 1,173,381 bytes to 585,289 bytes.

## Why a raster boundary is required

Inside one monolithic filter, the packed Q/K values are readable by color and
composite operations, but the following 64-value attention convolution renders
zero. A stage trace proved the exact boundary:

```text
extracted Q/K → signed Q/K → pixelwise Q×K → scale: valid
64-value score convolution: zero
```

Putting the QKV graph in one SVG filter and attention in a second filter resets
Chromium's internal raster/subregion state. The attention score convolution is
then valid. The probability broadcast must use the ordinary scalar `feTile` in
this fresh stage. Using a second convolution for the broadcast creates another
unsupported chained-convolution boundary and makes the token-1 context zero.

The accepted sequence is therefore:

```text
RGB-packed QKV filter → raster boundary → score convolution → probability tile
```

## Connected result

Two independent nine-round alternating benchmarks were run in the same Chrome
process. Each navigation decoded all QKV and final context values, so an invalid
graph cannot win by demand-driven skipping.

| Trial | existing median | RGB staged median | speedup |
| --- | ---: | ---: | ---: |
| 1 | 1,454.9 ms | 1,259.4 ms | 1.155× |
| 2 | 1,420.3 ms | 1,239.6 ms | 1.146× |

Accuracy improves:

| Layout | context RMSE | max context error | max probability error |
| --- | ---: | ---: | ---: |
| Existing head-local | 0.007654 | 0.12166 | 0.03188 |
| RGB staged | 0.004819 | 0.02216 | 0.01320 |

Connected HTML shrinks from 1,706,770 bytes to 1,118,372 bytes, a 1.53×
reduction.

Rebuild and benchmark with:

```sh
SVG_MULTITOKEN_OUT=experiments/svg-multitoken-attention-rgb-tile \
SVG_QKV_LAYOUT=rgb \
SVG_RGB_ATTENTION_BROADCAST=tile \
  uv run --with numpy --with pillow python tools/build_svg_multitoken_attention.py

SVG_QKV_BENCH_SET=rgbtile SVG_QKV_BENCH_ROUNDS=9 \
  node tools/benchmark_svg_multitoken_qkv_layouts.mjs
```

## Related layout sweeps

### Token-batched QKV

A follow-up placed both input tokens side-by-side in one 128-pixel QKV surface.
It reused each weight image once and reduced QKV convolutions from 144 to 72.
The output is bit-for-bit equivalent at the decoded level, but the wider raster
path is slower:

| QKV token layout | QKV median | connected median | QKV HTML | connected HTML |
| --- | ---: | ---: | ---: | ---: |
| Separate 64-wide tokens | **668.3 ms** | **1,183.1 ms** | 585,289 B | 1,118,372 B |
| Batched 128-wide tokens | 903.6 ms | 1,565.5 ms | **501,567 B** | **1,034,650 B** |

The token-batched path is 1.35x slower for QKV and 1.32x slower end-to-end even
though it has half as many convolutions. This rejects spatial token batching as
a context-length scaling strategy in Chromium: preserving the 64-pixel-wide
fast geometry matters more than reducing primitive count.

Contiguous groups of 2, 3, 4, and 6 heads were all slower than the original
64-wide head-local projection. Their connected median ratios versus the
head-local baseline were 0.72×, 0.51×, 0.70×, and 0.74× respectively. Wider
surfaces reduce markup but do not improve latency.

The QKV reduction-height sweep also found a hard practical boundary:

| shard height | connected median | QKV RMSE | decision |
| ---: | ---: | ---: | --- |
| 128 | 6,638 ms | 0.02449 | valid, much slower |
| 192 | 4,499 ms | 0.02370 | valid, much slower |
| 256 | 1,513 ms | 0.02404 | retained fast path |
| 384 | 1,037 ms | 0.82850 | fast but numerically invalid |

The 384-row result is rejected. Chromium's larger convolution path does not
preserve the dot products even though it paints quickly.

## Decision

Retain 256-row, 64-wide QKV shards with one explicit raster boundary before
attention. The split-positive/negative RGB implementation in this directory is
the valid baseline. It is superseded for speed by the centered-product variant
in `../svg-multitoken-attention-rgb-centered`, which preserves the same geometry
and halves QKV convolutions.

## Attention projection and residual boundary

`connected-attention-residual-staged.html` carries the packed QKV result
through attention, the real `768 → 768` attention projection, and the residual
addition. Its final 1×768 surface is valid in a single render:

- RMSE: 0.03643;
- maximum error: 0.25973;
- nine-run warm median: 2,822.7 ms.

The old head-local page is not a valid one-pass baseline at this boundary. Its
direct twelve-chunk merge renders at 2.0787 RMSE. Reading each chunk in twelve
separate diagnostic renders recovers 0.03859 RMSE but takes 18.2 seconds and is
not an inference latency measurement. The packed staged path therefore proves
a complete reusable projection surface; it does not yet prove a projection
speedup.

The projection/residual boundary slightly improves accuracy relative to the
old per-chunk diagnostic (0.03643 versus 0.03859 RMSE), so the remaining error
is not introduced by RGB QKV.

The follow-up direct mixed-context projection removes the duplicated
`head x source-token` attention work at this boundary. In a nine-round
alternating benchmark it reduced the residual-path median from 2,847.6 ms to
1,531.4 ms, a 1.86x speedup, while improving RMSE from 0.03643 to 0.03343. See
`../svg-staged-mixed-projection/RESULTS.md` for the full result and the rejected
RGB-packed projection variant.
