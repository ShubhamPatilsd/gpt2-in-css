# HVAR-to-SVG QKV raster attention

## Question

Can the HVAR backend expose an entire QKV tensor as one SVG raster and let SVG
attention consume it, avoiding the CSS view-timeline and anchor graph?

All runtime pages contain HTML, CSS, SVG, and fonts only. The external
Playwright harness measures screenshots and is not part of inference.

## Bulk QKV result

Yes for a one-way handoff. Seventy-two filtered groups represent two tokens x
Q/K/V x twelve heads. Each group converts 64 HVAR widths into one raster row.
The combined 64x72 surface contains all 4,608 real QKV values.

Seven warm rounds measured:

- median: 296.2 ms;
- QKV RMSE: 0.005720;
- maximum error: 0.03887;
- three shared QKV fonts: 2.13 MB;
- runtime JavaScript: none.

This is a genuine vector-level HVAR-to-raster operation and is much cheaper
than converting the values through 4,608 CSS timelines.

## Reuse failure

The compact surface does not survive the next arithmetic boundary in the
tested Chrome graph. Feeding the 72 independently filtered rows into the
existing SVG attention filter makes every Q/K score zero. The resulting
probabilities are approximately 0.5, with 0.4958 maximum probability error.

A monolithic alternative laid the bars in eight-column chunks and used
displacement maps to assemble one surface within a single filter. It was worse:

- roughly 657 ms for QKV;
- 0.03248 QKV RMSE and 0.9856 maximum error;
- the following Q/K scores still collapsed.

Finally, fusing the monolithic rasterizer and the complete attention graph into
one SVG filter did not finish after more than three minutes and was terminated.

## Decision

Retain grouped HVAR-to-raster as a fast one-way export primitive. Reject it as
the current reusable attention backend. Chrome can paint the compact raster,
but does not provide a cheap, reliable boundary that lets the next filter use
those foreign-object/filter fragments for signed dot-product reductions.

Reproduce the measured probe with:

```sh
make hvar-raster-qkv-attention
HVAR_RASTER_QKV_FILE=qkv-groups.html \
HVAR_RASTER_QKV_ALLOW_INVALID_CONNECTED=1 \
HVAR_RASTER_QKV_ROUNDS=7 \
node tools/test_hvar_raster_qkv_attention.mjs
```
