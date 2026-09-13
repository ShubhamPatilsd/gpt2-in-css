# Packed font-metric transport

## Question

Can arithmetic/radix coding put several HVAR dot products into one font metric,
then let CSS `round()` and `mod()` recover them?

## Exact integer proof

`index.html` packs two signed 8-bit dot products into `1ch` and two more into
`1ic`. The font computes

```text
packed = (output 0 + 128) + 256 × (output 1 + 128)
```

and CSS extracts the two base-256 digits. Across 400 changing 16-value inputs,
Chrome recovered all four outputs exactly:

- RMSE: `0`
- maximum error: `0`
- generated font: `5,500` bytes
- runtime page: HTML/CSS only

This is a real transport primitive for integer-valued dot products.

## Equal-output scale comparison

The scale fixtures force 1,024 numeric outputs under otherwise identical
conditions:

| Fixture | Producer nodes | Values per node | Warm median | Mutation median |
| --- | ---: | ---: | ---: | ---: |
| unpacked | 512 | 2 | 116.6 ms | 0.9 ms |
| packed | 256 | 4 | 84.3 ms | 0.4 ms |

Packing was `1.38×` faster on warm loading and `2.25×` faster on a forced
recalculation. It reduces real browser work, not only source size.

## Real GPT-2 feasibility

The exact proof uses integer axes and deliberately tiny coefficients. Actual
GPT-2 HVAR inputs are continuous normalized values. Two arbitrary real dot
products cannot be recovered from one linear scalar. Making the method exact
requires quantizing activations to integers before the font calculation.

`real-feasibility.json` applies that requirement to the actual block-0 matrices
with the project's 9-bit weight rows. One OpenType advance has a 16-bit range.
At 8-bit activation precision, the median adjacent pair needs:

| Matrix | Median bits for two raw results | Pairs fitting 16 bits |
| --- | ---: | ---: |
| value projection | 31 | 0% |
| attention projection | 31 | 0% |
| FC | 32 | 0% |
| MLP projection | 27 | 0% |

Even at only 4-bit activation precision, median pairs need 18–23 bits. The
fraction fitting one metric is 1.2–2.3% for the first three matrices and 23.7%
for the MLP projection. That is before measuring the accuracy loss caused by
4-bit activations.

## Decision

Keep radix packing **after** a value has already been quantized; the existing
packed timeline transport legitimately benefits from it. Do not use direct
packed HVAR coefficients as the general matrix-output transport. The font's
16-bit advance is already mostly occupied by one real GPT-2 dot product, and
HVAR has no per-output rounding operation that could create smaller digits
before combining rows.

The experiment explains why the toy is fast and exact without mistaking it for
a full-model solution.
