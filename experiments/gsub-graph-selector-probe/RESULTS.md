# GSUB graph selector probe results

Overall: **PASS**

The runtime page contains 0 script elements. It computes registered `--low = mod(node, 255)` and `--high = floor(node / 255)`: `cv01` maps each of 16 slot bases to a slot×low intermediate, then `cv02` maps that intermediate to the final identity glyph. A CSS `if()` chooses one first-hop `anchor-size()`; a size container decodes the half-scale identity advance into `--next-node`; the inherited radix digits drive the second GSUB hop.

## Correctness

| current node | chosen slot | first hop | expected / decoded next | decode | second hop | overall |
|---:|---:|:---:|---:|:---:|:---:|:---:|
| 0 | 0 | PASS | 1 / 1 | PASS | PASS | PASS |
| 1 | 7 | PASS | 33599 / 33599 | PASS | PASS | PASS |
| 32767 | 8 | PASS | 41646 / 41646 | PASS | PASS | PASS |
| 50256 | 15 | PASS | 6071 / 6071 | PASS | PASS | PASS |

All 16 first-hop and all 16 second-hop identity widths are compared exactly for every row. Required boundary indices tested: 0, 1, 32,767, and 50,256.

The radix selector passes every required node and both declarative hops. Its largest numbered values are 255 for `cv01` and 198 for `cv02`; deterministic lookup order is `cv00`, `cv01`, then `cv02`.


## Preserved direct-selector baseline

| current node | requested `cv00` value | low byte | exact result | matches modulo-256 behavior |
|---:|---:|---:|:---:|:---:|
| 0 | 1 | 1 | PASS | yes |
| 1 | 2 | 2 | PASS | yes |
| 32767 | 32768 | 0 | FAIL | yes |
| 50256 | 50257 | 81 | FAIL | yes |

Chromium accepts the CSS syntax for `"cv00" 50257`, and the same font retains all 16 genuine 50,257-entry direct AlternateSets. Direct shaping still reduces the numbered value to its low 8 bits: value 255 passes, value 256 becomes 0/no substitution, and value 257 becomes 1. Thus node 32,767 requests 32,768 and gets no substitution; node 50,256 requests 50,257 and gets 81, selecting node index 80. The radix path bypasses this without shrinking the graph.

## Font and runtime sizes

- TTF: 4,078,960 bytes
- WOFF2: 308,432 bytes
- HTML: 4,531 bytes
- CSS: 4,291 bytes
- Glyphs: 54,354
- Direct baseline: 16 × 50,257-entry AlternateSets
- Radix low: 16 × 255-entry AlternateSets
- Radix high: 4,080 × 198-entry AlternateSets

## Browser and timing

- Browser: 153.0.8010.36
- Cold page/font load: 157.070 ms
- Warm two-hop switch median: 0.300 ms
- Warm two-hop switch p95: 0.400 ms
- Timed switches: 100

The timing covers the passing radix sequence. The direct baseline is measured separately for correctness and does not drive the second hop.

Full machine-readable observations, exact widths, feature boundaries, capabilities, and failures are in `browser-results.json`.
