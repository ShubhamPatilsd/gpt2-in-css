# Dynamic attention with CSS SWAR

Measured in headless Chrome 153 on macOS on September 12, 2026. The runtime
pages contain HTML and CSS only. The external Playwright harness changes the
live query/key inputs, forces layout, and checks every score against the integer
reference.

## Result

Packing two signed six-bit values into each anchor width is bit-exact and cuts
the number of live sources and multiplication terms in half. It is 4–6x faster
than scalar anchor arithmetic at the larger shapes.

| Heads × keys | Pair sources | Pair terms | Scalar query | Pair query | Speedup | Scalar full | Pair full | Speedup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 × 4 | 160 | 128 | 3.32 ms | 2.05 ms | 1.62x | 3.05 ms | 2.22 ms | 1.38x |
| 1 × 16 | 544 | 512 | 7.59 ms | 3.75 ms | 2.02x | 11.20 ms | 5.91 ms | 1.89x |
| 1 × 64 | 2,080 | 2,048 | 220.13 ms | 40.70 ms | 5.41x | 237.78 ms | 47.57 ms | 5.00x |
| 12 × 4 | 1,920 | 1,536 | 149.34 ms | 22.52 ms | 6.63x | 159.05 ms | 27.27 ms | 5.83x |
| 12 × 16 | 6,528 | 6,144 | 2,123.16 ms | 537.09 ms | 3.95x | 2,170.21 ms | 558.66 ms | 3.88x |
| 12 × 64 | 24,960 | 24,576 | 36,841.95 ms | 8,626.53 ms | 4.27x | 37,278.03 ms | 8,862.22 ms | 4.21x |

All scalar and corrected pair trials have zero RMSE and zero maximum error.
`browser-results-same-order-invalid.json` is deliberately retained as a
negative fixture: packing the key pair in the same order as the query computes
cross-products, not the dot product. Reversing the key pair fixes it.

## Decision

Retain the two-lane arithmetic primitive for small live reductions. Reject a
per-coordinate named-anchor key cache for long-context attention: at 12 heads
and 64 keys, the 24,960 live sources and their dependency graph still cost 8.6
seconds for a cached-query update. The arithmetic is no longer the only issue;
the named-anchor graph itself does not scale.

