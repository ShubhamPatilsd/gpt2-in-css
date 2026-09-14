# Direct-target groupwise Cauchy block-flow cascade

## Decision

**Retain as the best verified fixture-range output head.** This is the first
full integration in this branch that combines the retained row transport,
zero-height block-flow group maxima, fan-in-16 outer reducer, live groupwise
certificate, dynamic exact-group scoring, stopping, and final token selection.

The certificate is built directly for the existing exact browser target:

```text
global-int16 target row - row-wise int10 coarse row
```

It does not change GPT-2-small's architecture or checkpoint. The strict page
contains no JavaScript.

## Browser proof

Chrome 153.0.8010.36 passed all 10 fixtures:

- 10/10 live routes matched a no-bound coarse control plus independently
  predicted group bounds;
- every selected group matched a forced global-int16 exact-score shadow;
- every incumbent merge, next upper, strict 48-bucket stop, and final token
  matched its independent oracle;
- every fixture certified within six stages, with active-stage counts
  `1,3,1,1,1,1,2,1,1,1`;
- all 96 block norms and font axes changed, and all 195 non-hot group glyphs
  changed;
- 1,942/1,950 sampled bounds hit the predicted 4 px bucket exactly and eight
  landed one bucket farther outward; none rounded inward;
- a JavaScript-disabled context loaded the page and result graph.

The hot exact groups 0 and 1 retain their existing 24-bucket upper allowance
and do not receive a redundant residual glyph. Ordinary coarse candidates no
longer include the inherited scalar per-row Cauchy term; adding that term was
the double-bound defect in the first discarded build.

## Paired loaded timing

Four fixtures were alternated against the previously retained shard256
block-flow head after correctness passed.

| Page | Mean | Median | Minimum | Maximum |
|---|---:|---:|---:|---:|
| Direct-target groupwise cascade | 1,979.2 ms | 2,680.9 ms | 1,021.6 ms | 2,909.1 ms |
| Retained scalar-bound head | 2,857.9 ms | 2,969.5 ms | 1,974.2 ms | 3,613.3 ms |

The candidate is 0.693x by mean and 0.903x by median. Four samples establish a
strong direction, not a final broad benchmark. Candidate cold load was
45.12 s versus 49.28 s for retained in the same browser process.

## Production-range scaling screen

The 1,024 saved states were independently rescored at the production
F2DOT14 range (±266.248). The global-int16 target matched the float winner on
1,024/1,024 states, and every target group was certified.

With the conservative live 48-bucket stop margin:

- overall exact work is 1.996 groups mean, 1 median, 6 p95, and 22 maximum;
- test exact work is 2.031 groups / 520 rows mean, 1 group / 256 rows median,
  6 groups / 1,536 rows p95, and 14 groups / 3,584 rows maximum;
- 984/1,024 states stop within six stages and 1,018/1,024 within twelve.

For the 40 six-stage fallbacks, a one-wave exact closure would need 4.525
additional competitive groups on average, 3 median, 16 p95, and 21 maximum;
total exact work on those fallback states would average 2,694 rows and max at
6,912. This favors extending the small dynamic-group unroll over adding a
50,257-row dense fallback, though neither is yet a browser result.

The production bound font is structurally feasible: maximum coefficient 367
and maximum pre-zero-base advance 28,378 fit OpenType's integer limits.

This production screen is not yet a production browser claim. The integrated
page still reuses ±135.309 fixture-range score fonts, and six stages cannot
close 40/1,024 production states. A production artifact needs rebuilt
±266.248 score/bound fonts plus a conditional exact tail or a longer unroll.

Raw browser evidence is in `browser-results.json`; the production screen is in
`offline-results.json`. Nothing was committed or pushed.
