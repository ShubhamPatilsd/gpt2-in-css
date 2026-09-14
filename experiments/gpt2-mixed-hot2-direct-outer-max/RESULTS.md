# Mixed hot-2 direct outer maximum

Decision: **retain as the flat baseline; superseded by fan-in-16 hierarchy**.

The retained mixed-hot2 page reconstructs every group score through a
view-timeline inversion and lets the model's intrinsic width expose the global
bucket. This variant leaves all score rows, hot exact rows, fonts, and
downstream best-first decoders unchanged, but replaces those 197 inversions
with one fixed node:

```css
width: max(anchor-size(--score-group-0 width), ...);
```

The ordinary outer reader consumes that node directly. This is an exact
transport replacement, not a different score approximation.

## Browser results

Against the retained mixed-hot2 page, three alternating rounds over all ten
fixtures pass **30/30** route, bucket, final-token, and dense-oracle checks.

| Metric | Direct maximum | Retained mixed-hot2 | Ratio |
|---|---:|---:|---:|
| Mean, 30 samples | 3,234.0 ms | 4,189.0 ms | **0.772x** |
| Median | 3,110.5 ms | 3,912.6 ms | **0.795x** |
| p90 | 4,956.0 ms | 7,145.9 ms | **0.694x** |
| Maximum | 5,265.5 ms | 7,783.6 ms | 0.676x |

Warm mean improves 22.8%, median 20.5%, and p90 30.6%. Cold load in that run
is 58.49 versus 54.41 seconds, a 7.5% regression.

A separate 30-pair head-to-head against the reused-upper contiguous B=4 gate
also passes every check. Direct-max/full-grid is faster by 5.8% mean and 5.2%
median, with lower p90 and maximum. The direct maximum therefore explains most
of the earlier B=4 win; gate/container arithmetic costs more than suppressing
the hot-row shapes saves.

Generated size is 8,247,860 bytes of HTML and 712,267 bytes of topology CSS;
all fonts are reused. Chrome: 153.0.8010.36. Raw results are in
`ab-results.json` and `ab-vs-b4.json`.

A later two-level reduction keeps the same 197 inputs and exact decoder but
materializes 13 maxima of at most 16 terms before the root. Against pruned flat
direct-max it improves mean 2.5%, median 1.0%, p90 10.6%, and maximum 12.5% over
30 exact pairs. See `../gpt2-mixed-hot2-hierarchical-outer-max16/RESULTS.md`.
