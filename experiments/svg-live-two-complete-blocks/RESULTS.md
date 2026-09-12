# Two complete live GPT-2 blocks

This page connects every operation and both residual paths in blocks 0 and 1.
Block 1 uses a fixed first-token cache entry and block 0's live newest-token
output. It contains no JavaScript.

Retained block-1 centered expansion gain: 4.5.

Measured behavior across repeated forced recomputations:

- stable alternating-resource samples: approximately 1,900–2,050 ms
- 15-run stable median after warmup: 1,989 ms
- raw block-1 output RMSE: 0.47588
- raw maximum error: 8.16796
- RMSE after block 2 LN1: 0.06078
- maximum error after block 2 LN1: 1.25006
- clipped output channels: 0
- generated HTML: 4,203,342 bytes

The old benchmark generated a new image URL on every round and occasionally
triggered a doubled cold-resource pass. Alternating two preloaded URLs and
mutating an arithmetic coefficient show that normal filter execution is stable
around two seconds. The screenshot/raster stage dominates; layout and
main-thread script work are only tens of milliseconds.

The layer-normalization and block-1-input filter regions are now restricted to
their actual 64- and 256-column extents. This preserves accuracy but does not
change runtime because primitive subregions already constrained raster work.
See `../svg-reduction-alternatives/RESULTS.md` for rejected and candidate
reduction backends.
