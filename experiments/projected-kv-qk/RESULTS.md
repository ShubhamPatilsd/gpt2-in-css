# Projected KV cache attention

## What changed

The earlier feature-selected backend stored each past token's 768-wide normalized
state. Every new attention step then folded the K and V projections into the score
and value computations again.

This experiment stores the projected 64-wide K and V vector for every head, matching
the KV cache used by ordinary autoregressive transformer inference. A small
query-selected HVAR font computes each 64-term Q dot K score. The weighted context is
then reduced directly from cached V values.

The runtime artifacts contain HTML, CSS, SVG, and fonts only. The Playwright files
are external measurement harnesses.

## Font and bundle size

The projected-K score bank is 12 WOFF2 files totaling 168,104 bytes. The preceding
fused-QK bank used 36 files totaling about 19.0 MB. The new score font component is
approximately 113 times smaller because it no longer embeds the 768 to K projection.

Total connected projected-attention bundle sizes are:

| Context | Total bytes | Previous fused backend |
| ---: | ---: | ---: |
| 2 | 4.54 MB | 24.36 MB |
| 8 | 5.14 MB | 26.77 MB |
| 16 | 5.95 MB | 30.09 MB |
| 32 | 7.55 MB | 36.72 MB |

## Browser results

Three-round warm navigation medians:

| Context | Projected KV | Previous fused backend |
| ---: | ---: | ---: |
| 2 | 0.825 s | 1.421 s |
| 8 | 1.081 s | 2.398 s |
| 16 | 1.467 s | 3.860 s |
| 32 | 1.949 s | 6.335 s |

Browser implementation RMSE against the projected-KV numerical reference was
0.00059/0.00084/0.00285/0.00081 at context 2/8/16/32. The independent 5-bit query
approximation relative to the 8-bit-query model remains unchanged.

A controlled context-16 trace measured 1.247 seconds versus 5.893 seconds for the
original per-coordinate backend, a 4.73 times speedup. Layout time fell from 3.533 to
0.961 seconds, shaping calls fell from 37,134 to 9,006, and DOM nodes fell from
53,575 to 9,419.

## Live cache and current-token checks

The nested variable fixture exposes every projected K and V coordinate as live CSS
state. Persistent-page updates, including two animation frames and reading all 768
residual outputs, measured:

| Context | Query update | High-attention cached V update |
| ---: | ---: | ---: |
| 2 | 0.256 s | 0.199 s |
| 8 | 0.250 s | 0.180 s |
| 16 | 0.400 s | 0.215 s |
| 32 | 0.510 s | 0.371 s |

Every output remained finite and changed. Initial navigation of this fully expanded
live-cache fixture is slower because 1,536 custom properties are serialized for each
past token; a production generator should append only each new token's K/V state.

A stricter fixture computes the current token's complete 768 to 2,304 QKV projection
live, uses its K and V in the current attention step, and leaves earlier cache entries
fixed. Warm navigation measured 1.63 seconds at context 16 and 2.60 seconds at context
32. Persistent query-input updates measured 0.435 and 0.467 seconds respectively.
This confirms the speedup survives the required current-token K/V work.

## Current boundary

Projected KV caching is now the preferred attention architecture. Remaining full
inference work is to generate and append one cache entry after each layer, connect the
MLP and residual path for all 12 blocks, and feed the final token choice back into the
next step. The output projection and current-token QKV projection are now the largest
fixed linear stages inside this attention fixture.

The matching real block-0 LN2/MLP is now connected and uses output ranges calibrated
on multi-token states. It reaches 0.0882 RMSE at context 16 and 0.0849 at context 32,
but a warm in-place update takes 2.23 seconds. Attention and MLP separately take only
0.66 and 0.27 seconds; the remaining 1.30 seconds is dependency-graph connection
overhead. Direct inheritance and CSS containment were tested and did not materially
reduce it. See `../multitoken-block0-ranges/RESULTS.md`.
