# Anchor geometry numeric backend

This experiment replaces SVG pixels with element widths. Every scalar is
encoded as a large positive CSS length. `anchor-size()` reads those lengths,
ordinary `calc()` performs weighted sums, and each result width becomes an
anchor for the next dense layer. The pages contain no JavaScript.

## Flat expressions

Two dense layers remain accurate through width 64, with approximately
`6e-7` RMSE. Chrome 153 accepts at most 99 arithmetic terms in one tested
width expression; 100 terms are rejected. Consequently, flat 128-, 256-, and
768-input expressions compute as zero.

## Hierarchical reduction

Splitting each dot product into groups of at most 96 terms bypasses the parser
limit.

| Width | Weighted terms | Browser boxes | HTML | Final RMSE | Total load + measurement |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 128 | 32,768 | 896 | 1.91 MB | `1.44e-6` | 125 ms |
| 256 | 131,072 | 2,304 | 7.59 MB | `1.91e-6` | 468 ms |
| 768 | 1,179,648 | 14,592 | 68.34 MB | `3.85e-6` | 31.47 s |

The 768 test is numerically successful: it evaluates both dense layers with
less than `9e-6` maximum error. It is not a viable GPT-2 backend. A single
transformer block contains several matrices at least this large, and this page
already needs 68 MB and 31 seconds for only two square matrices.

## Decision

Anchor geometry proves that HTML/CSS has a high-precision numerical domain,
but dense textual `calc()` graphs scale worse than the existing font and SVG
backends. Keep this as a correctness/reference backend, not the primary
inference engine.

Raw measurements are in `results.json` and `chunked-results.json`.
