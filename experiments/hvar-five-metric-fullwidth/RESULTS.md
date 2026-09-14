# Full-width five-metric HVAR/MVAR transport

## Question

Can a variable font expose several independent dense-matrix rows directly as
reusable CSS numbers, without one glyph/timeline per result and without the
rejected `ROW`-axis cross-product?

## Construction

The runtime page contains no JavaScript. A font instance receives live inputs
through variation axes and exposes five independently weighted dot products:

| CSS unit | Font source |
| --- | --- |
| `ex` | varied `x` outline in `gvar` |
| `cap` | MVAR cap height (`cpht`) |
| `ch` | HVAR advance of `0` |
| `ic` | HVAR advance of `水` |
| `lh` | MVAR horizontal ascender (`hasc`) |

Each unit is converted directly into an inherited registered `<number>` custom
property. There is no geometry readback, view timeline, animation, row-selector
axis, or output glyph in this path.

Chrome accepts at most 256 variation axes, while `gvar`'s 16-bit per-glyph tuple
offset prevents the outline-backed `ex` channel from reaching that ceiling in
this representation. The retained full-width proof therefore uses six
128-input font shards. Inputs are shifted from `[-1,1]` to `[0,1]`, font deltas
are scaled by 16, and a fixed row sum is subtracted in CSS. These are algebraic
transformations, not an approximation. The six partial results for each metric
are summed on one final DOM node.

## Chrome 153 result

Thirty-two random 768-value vectors produced the following error against direct
floating-point matrix multiplication:

| Output | RMSE | Maximum absolute error |
| --- | ---: | ---: |
| `ex` | 0.00592 | 0.01257 |
| `cap` | 0.04035 | 0.07485 |
| `ch` | 0.00524 | 0.01435 |
| `ic` | 0.00559 | 0.01298 |
| `lh` | 0.09733 | 0.26882 |

The larger `cap` and `lh` errors come from integer font-metric rounding. Scaling
the stored deltas by 16 makes that error sixteen times smaller before CSS
decodes the result. HVAR advances and the outline-backed metrics retain finer
sub-unit interpolation.

Performance in one warmed headless Chrome process:

| Measurement | Result |
| --- | ---: |
| Warm navigation/font load median | 35.63 ms |
| Change one axis, force and read all five outputs | 0.056 ms |
| Replace all 768 CSS inputs, force and read all five outputs | 6.68 ms |
| Six WOFF files | 38,296 bytes |
| Expanded SFNT data | 1,456,984 bytes |
| HTML | 47,586 bytes |

The full-vector mutation number includes constructing and parsing 768 inline
custom-property declarations in the external harness, so it is an upper bound
for the font calculation alone.

## Decision

This is a useful direct transport primitive. One font instance can perform five
arbitrary dense rows and expose all five as CSS numeric state; multiple input
shards can be accumulated on one descendant without timelines.

It is not a general vector-output primitive. CSS exposes only these five useful
font-relative scalar metrics. Additional glyphs, GSUB feature alternates,
language changes, named instances, and vertical metrics do not create new
numeric CSS units. Packing multiple low-precision integers into one metric is
possible, but arbitrary real dot products cannot be separated after they have
already been summed into one scalar.

Consequently, producing 768 arbitrary output rows still needs 154 five-row
font instances (and input-axis sharding inside each), or another backend. That
linear output multiplicity—not the accuracy or speed of this five-row probe—is
the remaining limit.

## Reproduce

```sh
/usr/bin/python3 tools/build_hvar_five_metric_fullwidth.py
node tools/test_hvar_five_metric_fullwidth.mjs
```
