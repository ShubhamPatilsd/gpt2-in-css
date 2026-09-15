# Direct two-dimensional packet capacity

## Result

A direct size container carries exactly 24 integer bits in its width and 24 in
its height. CSS can therefore recover a 48-bit packet without a view timeline.

Chrome 153 decoded 1,024 randomized packets for each format:

| Bits per value | Values per carrier | Decoded values | Failures |
| ---: | ---: | ---: | ---: |
| 6 | 8 | 8,192 | 0 |
| 7 | 6 | 6,144 | 0 |
| 8 | 6 | 6,144 | 0 |
| 9 | 5 | 5,120 | 0 |
| 10 | 4 | 4,096 | 0 |
| 11 | 4 | 4,096 | 0 |
| 12 | 4 | 4,096 | 0 |
| 16 | 3 | 3,072 | 0 |

All 1,024 arbitrary 24-bit geometry words survived exactly. At 25 bits,
510/1,024 failed; the first failure was `16,777,217 -> 16,777,216`. Thus the
48-bit total is a measured hard capacity, not merely the largest tested packet.

The real nested MLP pages were also checked after injecting their quantized
codes directly into every carrier. The 8-, 9-, 10-, and 12-bit variants had
zero transport failures across 24,576 decoded values.

## Decoder bug found

The old MLP decoder rounded the packed container size only for the lowest
digit. Higher digits divided the raw `cqi`/`cqb` value and rounded downward.
A value serialized infinitesimally below an integer could therefore borrow
from the next digit. The geometry was exact, but the decoder was not.

The builder now rounds each packed 24-bit word once before any division or
modulo. This makes the full nested packet transport exact.

## New 9-bit packet

The previous builder split every code evenly across width and height, which
only supported even bit widths. A generic 48-bit stream now supports five
9-bit values per carrier. The last MLP group is padded because 3,072 is not
divisible by five; the model dimensions and operations are unchanged.

An eight-round alternating real-MLP comparison measured:

| Format | Values/carrier | Carriers | Warm median | Worst RMSE vs full-precision preactivation path |
| --- | ---: | ---: | ---: | ---: |
| 8-bit | 6 | 512 | 1,027.5 ms | 0.006995 |
| 9-bit | 5 | 615 | 985.8 ms | 0.006459 |
| 10-bit | 4 | 768 | 1,109.5 ms | 0.005810 |
| 12-bit | 4 | 768 | 1,063.7 ms | 0.005665 |

The timing differences are small relative to run variance. Packing no longer
dominates this path: all variants still shape 3,072 FC glyphs and 768
projection glyphs, and the HVAR projection contributes roughly a 0.0045-0.0057
RMSE floor in this fixture.

## Precision statement

“Exact” here means that every already-quantized integer code survives the
transport unchanged. Quantizing an arbitrary floating-point activation to
8, 9, 10, or 12 bits is still a model-value approximation. Multiple arbitrary
full-precision values cannot be losslessly compressed into a 48-bit carrier.
Without activation quantization, width and height can carry only two independent
continuous values.

The guarded view-timeline sweep is a negative control. Scaling packed values
with guard bits did not restore lost payload because the progress error scales
with the geometry. Across 64 timeline geometries, only one layout transported
15 bits per coordinate exactly; no 16-bit layout was exact. Direct container
units avoid this lossy geometry-to-progress inversion.

## Reproduction

```sh
node tools/test_direct_2d_packet_capacity.mjs
ANCHOR_PACKED_CODE_BITS=8,9,10,12 node tools/test_anchor_packed_code_exactness.mjs
PREACTIVATION_PACKET_BITS=8,9,10,12 PREACTIVATION_PACKET_ROUNDS=8 \
  node tools/compare_preactivation_packet_transports.mjs
```

Raw results are in `browser-results.json`, `real-mlp-code-results.json`, and
`../preactivation-packet-transport/real-mlp-results.json`.
