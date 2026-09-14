# GPT-2 16-group Cauchy block-flow composition gate

## Decision

**Pass the narrow composition gate.** The 16-group candidate preserves the
retained zero-height block-flow group reducer and one fan-in-16 outer maximum,
then appends one zero-base 96-axis Cauchy bound glyph to each group upper. It
does not change GPT-2-small's architecture or checkpoint.

All six hidden-vector fixtures passed in Chrome 153.0.8010.36. For every
fixture and group, the candidate width equaled the live no-bound control width
plus the measured bound-glyph width. Selected groups matched the composition
oracle (`live control + independently predicted bound`) and exercised three
distinct winners: groups 0, 1, and 3. The fan-in-16 chunk and final outer
maximum both equaled the same oracle maximum.

## Carrier and correctness

- All 96 registered block norms changed across the liveness pair.
- All 96 computed font axes changed.
- All 16 group-bound glyph widths changed.
- All 96 fixture-by-group measured bounds were outward-safe and exactly
  matched the F2DOT14-realized prediction: 96 exact, 0 within one 4 px bucket,
  and 0 beyond one bucket. The acceptance contract conservatively permits one
  bucket while still requiring outward safety.
- The all-zero fixture uses the browser's zero-base result: its sub-font-unit
  positive pad rounds away and the CSS outward floor contributes 4 px. Its
  certified radius is zero, so this remains conservative.
- Both generated pages contain zero `script` elements. A separate context with
  page JavaScript disabled loaded the candidate and its outer reducer.

The direct NumPy coarse-width reconstruction is retained only as a diagnostic.
It does not model the retained score fonts' per-run snapping and therefore
differs by whole score buckets on many rows. Composition correctness instead
uses the otherwise identical live control page for the coarse term, while the
bound term remains independently predicted from the saved Cauchy coefficients.

## Loaded mutation timing

Five alternating loaded mutations were measured only after correctness and
liveness passed.

| Page | Mean | Median |
|---|---:|---:|
| Identical 16-group topology without bounds | 85.66 ms | 77.10 ms |
| 16-group topology with one bound per group | 49.58 ms | 48.80 ms |

The candidate/control ratios were 0.579x by mean and 0.633x by median. This is
not treated as a speedup claim, but it clearly does not meet the predefined
decisive-penalty rule (both mean and median at least 1.5x and 50 ms slower).

Raw fixture geometry, NumPy coarse diagnostics, liveness counts, timing
samples, and the final decision are in `browser-results.json`. Generated inputs
and the oracle contract are in `reference.json`.

Nothing was committed or pushed.
