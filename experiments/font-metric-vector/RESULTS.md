# Four-output font-metric transport

## Question

Can one variable-font instance expose several independent matrix outputs directly
as CSS numbers, avoiding one geometry/timeline readback per output?

## Result

Yes for four outputs, but the approach scales in the wrong direction.

Chromium exposes four independent font measurements:

- `ex`: the varied height of the `x` glyph
- `cap`: the varied cap-height metric
- `ch`: the varied advance of `0`
- `ic`: the varied advance of `水`

The 64-input proof returned `[-67, -76, -84.5, 58.5001]` for expected
`[-67, -75.5, -84.5, 58.5]`. Cap height rounds to one whole font unit; the
other channels preserve fractional interpolation.

The scaled test used the exact same 256×256 integer matrix and input vector as
`matrix-scaling/256`. It split the 256 result rows across 64 fonts, four rows per
font, and inherited all 256 registered output properties into one final element.
The HTML contains no JavaScript.

| Transport | Max error | RMSE | Warm median |
| --- | ---: | ---: | ---: |
| Four font metrics, 64 fonts | 0.5004 | 0.1593 | 199 ms |
| Existing HVAR/container transport, one font | 0.2420 | 0.1522 | 69 ms |

Timings are nine alternating same-browser warm navigations through reading all
256 values. The font-metric route was **2.88× slower**, not faster.

## Delivery cost

The 64 test fonts total 60,360,368 bytes as TTF. FontTools compresses them to
365,616 bytes of WOFF2, but Chromium rejects those unusually sparse,
high-compression-ratio WOFF2 files during conversion to SFNT. The working page
therefore uses TTF files so that the computation can be measured honestly.

## Scaling consequence

Four outputs per font still means one distinct font face per four rows. A
256-input shard of GPT-2's `768 → 3,072` FC matrix would require 768 font faces.
Because the 768 inputs require three 256-axis shards, the full FC would require
2,304 faces plus a merger for the three partial vectors.

The experiment is therefore a useful capability proof and a rejected scaling
backend. It removes geometry readback but replaces it with much more expensive
font-face instantiation. The next viable direction must expose tens or hundreds
of outputs from one browser object, not four.
