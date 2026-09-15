# Packed preactivation transport

## Question

Can one layout carrier hold several independent GPT-2 MLP preactivations, let CSS unpack them, apply GELU independently, and feed the results into the `3072 -> 768` projection?

## Result

Yes. Chrome can do this exactly at the transport layer. The practical limit is the amount of exact integer payload available in geometry, not CSS's ability to decode or apply GELU.

The small HTML/CSS-only proof stores eight 6-bit codes in one element: four base-64 digits in its width and four in its height. CSS recovers every digit with `round()`, `mod()`, and container units, converts each code back to a signed preactivation, then evaluates GELU independently. Both test packets decode exactly in Chrome 153.0.8010.36. Maximum observed GELU error is `5.29e-6`, attributable to computed-style decimal serialization rather than a wrong decoded code.

The repository already contained a stronger real-weight implementation in the `anchor-packed-full-mlp-local-2d-*` pages. Those pages use the actual GPT-2 block-0 `768 -> 3072` FC font computation, pack the resulting **preactivation** codes into two-dimensional layout carriers, decode them in CSS, apply GELU, and consume all 3,072 activations in the real `3072 -> 768` projection. This is distinct from the older post-GELU timeline-packet experiments.

## Real GPT-2 MLP comparison

The external Playwright harness alternated two built-in real inputs across all variants in one Chrome context. The first two samples were treated as warm-up. Times cover a live input toggle through completion of the projected 768-vector.

| Encoding | Values / carrier | Packed carriers | Median warm | Worst RMSE vs full-precision preactivation path | Worst absolute error |
|---|---:|---:|---:|---:|---:|
| 3-bit | 16 | 192 | 862.7 ms | 0.240916 | 0.864951 |
| 4-bit | 12 | 256 | 813.6 ms | 0.063659 | 0.272171 |
| 6-bit | 8 | 384 | 961.5 ms | 0.015462 | 0.064495 |
| 8-bit | 6 | 512 | 1,124.4 ms | 0.004554 | 0.015704 |
| 10-bit | 4 | 768 | 1,183.0 ms | 0.002762 | 0.012159 |

Every variant still shapes 3,072 FC source glyphs and 768 projection glyphs. Packing reduces only the intermediate layout-dependent carriers: 16x at 3-bit, 12x at 4-bit, 8x at 6-bit, 6x at 8-bit, or 4x at 10-bit. Consequently, carrier count does not translate into proportional end-to-end speedup.

## Geometry limit

The tested exact packet uses at most 24 integer payload bits in each of width and height, or about 48 bits total per two-dimensional carrier. That yields the basic capacity bound:

`values per carrier <= floor(48 / bits per value)`

The existing 8- and 10-bit real pages achieve this by splitting each code into low/high planes across the two dimensions. Crossing the exact-integer range cannot preserve every adjacent integer in one layout number, so adding more values requires another dimension, carrier, or representation.

A later capacity audit tested 40,960 randomized decoded values and confirmed
the 48-bit boundary: 24-bit words were exact, while 510/1,024 sampled 25-bit
words failed. It also found and fixed a decoder bug: packed `cqi`/`cqb` must be
rounded to an integer before extracting every digit, not only the low digit.
After the fix, the nested real MLP carrier chain decoded 24,576 injected 8-,
9-, 10-, and 12-bit codes with zero transport failures.

The builder now also supports a generic five-value 9-bit packet. See
`../direct-2d-packet-capacity/RESULTS.md` for the capacity proof and current
8/9/10/12-bit comparison.

## Verdict

Packed preactivation transport is viable and useful, but it is not the missing order-of-magnitude scaling breakthrough. Six bits is the best measured speed/accuracy compromise here; eight or ten bits approach the quantized-HVAR error floor at approximately 1.1-1.2 seconds for this isolated MLP path.

Two limitations remain:

1. The fixed cost is still dominated by thousands of source/projection glyph operations, which packing does not remove.
2. The real pages calibrate per-channel preactivation ranges from only their two fixture inputs. The results prove the mechanism, not accuracy over arbitrary prompts; wider general-purpose ranges would spend precision or require more bits.

The next useful direction is therefore to reduce or reuse source/projection shaping work, or find a carrier with more than roughly 48 exact reusable payload bits. Further radix packing within width/height alone has reached its useful limit.

## Reproduction

```sh
node tools/test_preactivation_packet_exact.mjs
PREACTIVATION_PACKET_ROUNDS=8 node tools/compare_preactivation_packet_transports.mjs
```

Raw results are in `exact-proof-results.json` and `real-mlp-results.json`.
