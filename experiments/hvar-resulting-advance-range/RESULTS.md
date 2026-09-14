# HVAR resulting-advance range probe

## Result

**Chrome 153 preserves signed, out-of-uint16 HVAR results while shaping a
positive-width glyph run.** Neither the individual glyph nor the complete run
is clamped to `[0, 65535]`, and there is no uint16 wrap.

At the `TEST=1` endpoint:

| Case | Base | HVAR delta | Resulting target | Compensator | Expected run | Chrome run |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Negative, mild | 1,000 | -2,000 | -1,000 | 5,000 | 4,001 | 4,001.22 |
| Negative, large | 1,000 | -11,000 | -10,000 | 15,000 | 5,001 | 5,001.22 |
| Above 65,535, mild | 65,000 | +2,000 | 67,000 | 1,000 | 68,001 | 68,001.22 |
| Above 65,535, large | 65,000 | +30,000 | 95,000 | 1,000 | 96,001 | 96,001.22 |

The 0.22-design-unit differences are normal 1/64-CSS-pixel layout rounding at
`font-size:64px`; they are below the one-design-unit gate and are thousands of
units away from the competing clamp/wrap hypotheses.

All six width APIs agreed: HTML intrinsic and Range widths plus SVG computed
text lengths, each with target-before-compensator and compensator-before-target
order. The `TEST=-1` and default endpoints, three in-range controls, and all
order reversals also passed. Serialized font inspection confirms uint16 base
advances and signed-int16 HVAR deltas.

An isolated negative-advance glyph reports a zero HTML/SVG width because those
geometry APIs cannot return a negative box width. That is not a per-glyph
shaping clamp: inside the compensated run, the same glyph subtracts exactly
1,000 or 10,000 design units. SVG character positions independently expose the
negative displacement.

## One-plane global-int16 consequence

This result permits a corpus-domain one-plane scorer under these exact
conditions:

1. Encode each candidate as one varying score glyph plus a fixed positive
   compensator in the **same shaped run**, and consume the run width rather
   than the isolated score-glyph width.
2. Use one candidate-independent compensator `C`, so adding it preserves the
   argmax. Across every reachable corpus state and candidate, require
   `C + score(state, candidate) >= 0`; keeping only the total run nonnegative is
   sufficient in this Chrome build.
3. Keep each stored HVAR variation delta in `[-32768, 32767]` and each static
   `hmtx` advance in `[0, 65535]`. The *resulting* score-glyph advance may be
   negative or exceed 65,535.
4. If the corpus lower bound needs more than 65,535 units of compensation, use
   multiple constant glyphs (each with a legal uint16 base). Account for that
   extra glyph topology when comparing against the existing planes.
5. Sweep the real corpus coordinates and validate the 128-axis/multi-region
   accumulated result. This probe proves endpoint arithmetic for one axis and
   two regions; it does not by itself certify the production font's aggregate
   range or browser portability.

Thus the signed-result path is **not rejected**. Its next scaling gate is a
corpus-real one-plane font: calculate the minimum shared compensator, confirm
all individual int16 region rows serialize, then compare its glyph/font/layout
cost with the retained scorer.

Raw measurements and every hypothesis error are in
[`browser-results.json`](browser-results.json); generated inputs and serialized
HVAR rows are in [`reference.json`](reference.json).

## Reproduce

```sh
uv run --with fonttools --with brotli \
  python tools/build_hvar_resulting_advance_range_probe.py
node tools/test_hvar_resulting_advance_range_probe.mjs
```
