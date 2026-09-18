# Keeping the weights unchanged did not make delayed normalization robust

**Stop before building a browser version of this proposal.** All 44 ordinary
reference-derived inputs passed the primary numerical screen. However, the
proposal failed the predeclared common-offset and low-variance checks, even
before adding timeline or layout error. This is an offline rejection of a
general replacement, **not a claim that the tested ordinary inputs failed**.

No production code, model weight, font, or browser page was changed. No timing
benefit is measured or inferred. The complete screen took 14.3 seconds after
acquiring the shared experiment lock; that duration is Python analysis time.

## What was tested

The existing path first centers and normalizes each input, then lets the font
calculate a weighted sum. The proposed path sends the less-processed inputs to
the same font and corrects its answer afterward:

```
existing:   Q @ (gamma * (x - mean) / sigma + beta) + bias
proposed:   (Q @ (gamma*x) - mean * (Q @ gamma)) / sigma
            + Q @ beta + bias
```

`Q @ gamma` and `Q @ beta + bias` are constants calculated beforehand. `Q`
is the existing 9-bit-per-row reconstructed matrix, not a newly rounded matrix.
In exact arithmetic, the two expressions are equal.

The exact rational-arithmetic check returned identical fractions in both
paths. Across all 308 real and synthetic cases, the float64 identity's largest
difference was **4.11e-10**, below the predeclared 1e-9 threshold. All six matrices
retained identical codes/scales/weight hashes. The analyzer opened **18 existing
WOFF2 files** and checked their HVAR deltas, signed axes, and row bases against
those codes, rather than merely assuming the font files represented them.

The 44 base inputs cover both LN1→QKV and LN2→FC at layers **0, 5, and 11**:

- Eight saved inputs from the existing dense-stage fixtures at positions 0 and
  1 of `[15496, 11]` (`Hello,`), layers 0 and 11.
- Thirty-six newly saved reference-derived inputs from `The quick brown fox`,
  `Paris is the capital of`, and `CSS can perform matrix multiplication`, at
  the first/final prompt positions and all three selected layers.

These use the genuine local GPT-2 checkpoint and its current row-q9 reference
trajectory. They are **not native browser captures**. The original-float target
below applies the original float matrix to the same input; it is not a separate
full-float model trajectory or a token-quality evaluation.

## Numerical contract and gate

The [protocol](PROTOCOL.md) was written before candidate results. The analyzer
uses current dynamic ranges `1.001*max(1e-6,max(abs(input)))`, 256-coordinate
shards, 512 px font size, 1,000 font units per em, and nine-decimal CSS constants.
No input clipped the signed font-axis range.

The primary model floors normalized coordinates to F2DOT14, following the
repository's [Chrome coordinate-dither evidence](../../gpt2-hvar-coordinate-dither/browser-results.json)
and [implementation](../../../tools/build_gpt2_hvar_coordinate_dither_probe.py).
It leaves advances continuous, to isolate the coordinate error. Nearest-grid
coordinates and two 1/64-pixel per-shard rounding modes are separate sensitivity
models. **None reproduces all native glyph, internal CSS float, and timeline
decoding behavior.** A passing offline screen would still require a browser
correctness gate.

Every case had to keep RMSE and maximum error against the original float stage
within `1.10*baseline_error + 1e-5`, and keep RMSE against the unchanged ideal-q9
stage below 0.05. The 10% allowance is a conservative criterion for this screen,
not a known full-model error budget. The 0.05 ceiling comes from the existing
dense QKV gate; applying it to FC preactivations here is an additional safeguard,
not an established FC-quality budget.

## Ordinary inputs passed the primary screen

Each table value is the largest **per-input RMSE** among the indicated ordinary
cases. Baseline and proposed maxima can belong to different inputs. No pooling
of synthetic cases makes this table look worse or better.

| Layer | Boundary | Cases | Existing vs original float | Proposed vs original float | Proposed vs ideal q9 |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | LN1→QKV | 8 | 0.003257 | 0.003256 | 0.000187 |
| 0 | LN2→FC | 8 | 0.004096 | 0.004103 | 0.000320 |
| 5 | LN1→QKV | 6 | 0.005728 | 0.005758 | 0.001197 |
| 5 | LN2→FC | 6 | 0.005982 | 0.005881 | 0.001633 |
| 11 | LN1→QKV | 8 | 0.004843 | 0.004849 | 0.000844 |
| 11 | LN2→FC | 8 | 0.002991 | 0.002993 | 0.000326 |

All **44/44** pass both criteria. Nearest-coordinate and nearest-1/64-pixel
sensitivity also pass all ordinary cases. The floor-coordinate plus
floor-1/64-pixel sensitivity fails the maximum-error-relative criterion for
one case: original error 0.010378 versus proposed 0.011556. Its proposed q9 RMSE
is only 0.000293. That isolated conservative-model result is **not an observed
browser failure**, and is not the main reason to stop.

## Common offsets and low variance expose the problem

For each base vector, the fixed stress set adds a shared offset in units of its
original standard deviation, or shrinks its deviations from the mean by 1,000×.
These finite inputs fit the current dynamic-axis contract, but are deliberately
synthetic; this report does not assert GPT-2 naturally produces them.

| Variant, applied to each base vector | Pass / 44 | Exceed q9 RMSE 0.05 | Worst proposed q9 RMSE |
| --- | ---: | ---: | ---: |
| Subtract 8 original standard deviations | 31 | 0 | 0.002360 |
| Add 8 original standard deviations | 22 | 0 | 0.003635 |
| Subtract 64 original standard deviations | 0 | 0 | 0.014211 |
| Add 64 original standard deviations | 0 | 0 | 0.015577 |
| Shrink deviations by 1,000× | 22 | 0 | 0.011553 |
| Shrink deviations, then add 8 original standard deviations | 0 | 40 | 1.685330 |

Overall **189/264 synthetic cases fail** the primary relative-error criterion;
40 also cross the 0.05 q9 ceiling. The answer does not depend on choosing floor
rounding: the nearest-coordinate model still fails 153/264 stress cases, with
36 crossing the absolute ceiling and worst q9 RMSE 0.715837.

The largest primary error occurs at layer 5's FC input, derived from the first
token of `CSS can perform matrix multiplication`, after the low-variance plus
offset transformation:

| Same stressed input | Existing path | Proposed path |
| --- | ---: | ---: |
| Error vs ideal q9, RMSE | 0.001542 | **1.685330** |
| Error vs ideal q9, maximum coordinate | 0.010204 | **11.631052** |
| Font input range before F2DOT14 rounding | 11.002 | 1,193.941 |

Its standard-deviation denominator including epsilon is 0.104539. The proposal
rounds values using a range of roughly 1,194, then divides the resulting error
by roughly 0.105. Subtracting the mean afterward removes the ideal common
offset; it cannot remove the rounding error already introduced.

More generally, candidate coordinate error scales with approximately
`range(gamma*x) / (16384*sigma)` before multiplication by matrix coefficients.
The existing path centers first, so a large shared offset does not consume its
coordinate precision. This explains the failure without changing the weights
or appealing to unspecified browser overhead.

## Decision and limits

The specific delayed-centering proposal does not meet its declared supported
input contract and is **not advanced to browser implementation or timing**.
The result does not disprove a narrower, guarded domain, and it does not prove
that all normalization rearrangements are inaccurate. It does establish that
unchanged weights and exact algebra alone are insufficient for this proposal.

There is no new token-time estimate from this experiment. A different proposal
would need a new predeclared contract and gate; this run does not silently try
additional variants after observing failures.

## Reproduction and retained evidence

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  uv run --python 3.11 --with numpy --with fonttools --with brotli --with pillow \
  python tools/run_unconventional_isolated.py \
  --label preserved-weight-normalization-screen -- \
  uv run --python 3.11 --with numpy --with fonttools --with brotli --with pillow \
  python tools/analyze_preserved_weight_normalization.py \
  --output experiments/style-simplification-review/normalization/reproduction
```

- [Analyzer](../../../tools/analyze_preserved_weight_normalization.py) and
  [executed source snapshot](analyzer-snapshot.py).
- [Complete raw results](results.json): every case/model metric, matrix and
  font hashes, source hashes, gates, and limitations.
- [Case identities and provenance](inputs.json), [all input vectors](inputs.npz),
  and [primary output arrays](primary-outputs.npz). Each matrix records its
  output-array case order in `results.json`.
- `results-incomplete.json` is the retained checkpoint before final summary;
  it is not a separate experiment or a passing gate.
- [First environment failure](attempt-missing-brotli/ATTEMPT.md) and
  [asset-location failure](attempt-missing-fc-asset/ATTEMPT.md), each with exact
  source/input snapshots. Neither produced a complete result. Repairs changed
  dependencies/asset discovery, not cases, formulas, or thresholds.

Only this offline analyzer and experiment artifacts were added. The existing
normalization compiler and fonts remain unchanged.
