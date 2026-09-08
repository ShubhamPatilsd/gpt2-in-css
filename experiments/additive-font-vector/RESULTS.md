# Geometry-to-vector transport results

## Result

Registered numeric custom properties are the first tested transport that converts an entire geometry vector into reusable CSS numeric state without a 2–4 component packing limit.

The working pipeline is:

1. An HVAR font renders each matrix output as one glyph width.
2. Each glyph owns a named view timeline.
3. A scroll-driven animation writes that timeline's progress into a distinct registered `<number>` custom property.
4. One shared CSS function recovers the original signed value exactly with the reciprocal timeline formula.
5. Downstream variable-font matrix shards consume 256 values at a time through `font-variation-settings`.

The vector is represented as `--v0` through `--vN`. It is one CSS numeric state, not a sequence of container-query readbacks. A consumer can reuse any coordinate with `var(--vN)` or a derived property such as `--hN`.

## Why the reciprocal decoder works

For viewport width `V` and measured geometry width `W`, the cover progress is:

```text
p = V / (V + W)
```

Therefore:

```text
W = V / p - V
```

The font's scale and base width are then removed with ordinary CSS arithmetic. This avoids one sampled `linear()` easing per output.

## Measurements

All pages contain no JavaScript. Browser timings are cold page-creation wall times in the local in-app Chromium browser, so use them as architectural comparisons rather than production benchmarks.

| Probe | Result |
| --- | --- |
| 768 geometry values → 768 registered numbers | all 768 recovered |
| Maximum decoded-axis error | `0.000002` |
| Downstream three-font HVAR sum | `780.5391px` rendered vs `780.5200px` expected |
| 768 registered-property page | 223,958 bytes raw; 9,464 bytes Brotli |
| 768 registered-property load | about 0.60 s |
| Old additive full-list page | 10,803,732 bytes raw; 13,646 bytes Brotli |

The small rendered-width difference is font/layout subpixel quantization. It is not a missing vector coordinate.

## Real GPT-2 MLP chain

`../gpt2-block-css/additive-vector-mlp.html` runs the quantized GPT-2-small block-0 MLP path:

```text
768 input
  → HVAR FC 768×3072
  → 3,072 registered progress numbers
  → exact CSS reciprocal + GELU
  → twelve parallel 256-axis HVAR projection shards
  → 768 reduced geometry outputs
```

All 3,072 registered values and all 768 projection outputs are nonzero and reusable. Compared with the NumPy reference:

| Measurement | Result |
| --- | --- |
| Mean relative projection error | `0.000100%` |
| Maximum relative projection error | `0.00205%` |
| HTML + CSS | 2,116,005 bytes raw; about 115 KB Brotli |
| 3,072-value transport-only load | about 2.83 s |
| Transport + 3,072→768 projection load | about 10.49 s |

The remaining roughly 7.7 seconds in the in-app browser measurement was downstream projection fan-out: twelve fonts rendered 9,216 partial glyph outputs, then anchor geometry reduced them. It was no longer geometry-to-number conversion or stylesheet size.

## Packed fallback-run projection

`../gpt2-block-css/additive-vector-mlp-packed.html` removes the per-shard
projection boxes. Each of the 768 output elements contains a twelve-character
text run. Disjoint `unicode-range` coverage sends each character to one of the
twelve 256-axis fonts, and the run's ordinary text width sums those twelve
matrix contributions. A single inherited `font-variation-settings` list holds
all 3,072 uniquely tagged hidden values; each fallback font consumes its own
256-tag slice and ignores the rest.

The matrix, quantization, FC transport, GELU, and number of shaped projection
glyphs are unchanged. Only the browser-object graph changes.

| Measurement | Original anchor fan-out | Packed fallback run |
| --- | ---: | ---: |
| Partial projection elements | 9,216 | 768 |
| Total DOM elements | 15,400 | 3,855 |
| Projection glyphs shaped | 9,216 | 9,216 |
| HTML bytes | 1,390,009 | 409,318 |
| CSS bytes | 725,996 | 725,419 |
| Fresh headless-Chromium process mean, 3 runs | 2.661 s | 2.027 s |

That is a 12× reduction in partial projection elements, a 75% reduction in all
DOM elements, and a measured 1.31× end-to-end speedup (24% less latency). All
768 output widths are nonzero. Browser comparison against the stored reference
gave `0.000061%` mean relative error and `0.000472%` maximum relative error.

The gap between the 12× object reduction and 1.31× speedup is important: font
shaping still evaluates 9,216 glyphs against 3,072 variation-axis values. DOM
and anchor reduction was a real secondary cost, but the remaining primary cost
is glyph/variation processing plus the 3,072-value FC transport.

### Projection cost ablation

Seven rotated navigations in one warmed headless Chromium process isolate the
page work from browser startup and font download. Every case parses the same
stylesheet and performs the same 3,072-value FC timeline transport.

| Case | Projection glyphs | Live variation values | Median |
| --- | ---: | ---: | ---: |
| Transport only | 0 | 0 | 1.487 s |
| Twelve fixed-axis shards | 9,216 | 0 | 1.576 s |
| One live shard | 768 | 256 | 1.547 s |
| Two live shards | 1,536 | 512 | 1.558 s |
| Four live shards | 3,072 | 1,024 | 1.574 s |
| Eight live shards | 6,144 | 2,048 | 1.626 s |
| Twelve live shards | 9,216 | 3,072 | 1.663 s |

The complete packed projection adds about 176 ms over transport-only. Holding
all 9,216 glyphs but disabling variation adds about 89 ms; enabling all 3,072
live axes adds a further 87 ms. Roughly 89% of the packed page's median time is
therefore before projection, in the 3,072-output FC geometry-to-number
transport. Exact run data is in
`../gpt2-block-css/additive-vector-mlp-scaling-results.json`.

### Two outputs from one view timeline

`../gpt2-block-css/additive-vector-mlp-paired.html` uses both independent
geometric inputs to a view timeline. The first HVAR result becomes the inline
position of the subject and the second becomes its width. At the initial scroll
position, the same timeline is sampled at its `cover` and `entry` ranges.

For scrollport width `V`, subject position `L`, subject width `W`, cover
progress `p`, and entry progress `q`:

```text
p = (V - L) / (V + W)
q = (V - L) / W
W = pV / (q - p)
L = V - qW
```

One range-aware `@keyframes` rule writes both progress values. This matters:
the first paired probe used two animations per timeline and saved little.
Absolute `cover` and `entry` keyframes let one animation recover both numbers,
halving subjects, timelines, and animations together without packing two
integers into one imprecise layout length.

Fifteen alternating warm navigations in Chrome 152 gave:

| Case | FC subjects | Timelines | Animations | Median |
| --- | ---: | ---: | ---: | ---: |
| Original FC transport | 3,072 | 3,072 | 3,072 | 1,004.2 ms |
| Paired FC transport | 1,536 | 1,536 | 1,536 | 621.3 ms |
| Original complete MLP | 3,072 | 3,072 | 3,072 | 1,014.9 ms |
| Paired complete MLP | 1,536 | 1,536 | 1,536 | 694.4 ms |

The paired transport is 38.1% faster in isolation and the complete MLP is
31.6% faster. All 3,072 hidden values and all 768 projection widths are finite.
The paired hidden vector differs from the original transport by `0.0003034`
maximum absolute error. Against the stored projection reference, the paired
page's maximum relative width error was `0.000589%`, the same maximum relative
error observed for the original page in that run.

A fixed-width ablation kept the original 3,072 timelines and animations but
removed HVAR computation. Its median was 947.6 ms versus 1,006.3 ms for the real
font FC in the same eleven-run comparison. About 94% of that boundary was
therefore transport/state machinery, not font shaping. The paired design
attacks the measured bottleneck directly.

Two apparent shortcuts remain unavailable in the tested browser. Direct
`anchor-size()` cannot resolve inside a registered numeric property or
`font-variation-settings`, and Chrome 152 rejects the newer
`timeline-scope: all` value. Explicit timeline names are still required.

## Limits

- Chromium/OpenType accepts at most 256 axes in one tested variable font. A 3,072-value state therefore feeds twelve parallel font shards. This is a font-consumer limit, not a CSS-vector limit.
- One animation/timeline is still required per geometry coordinate. The representation scales linearly rather than being capped at four, but 3,072 simultaneous scroll-driven animations cost about 2.8 seconds in the current construction.
- A subsequent font matrix emits geometry again. Another numeric transport boundary is required after each non-composable nonlinear stage. Consecutive linear matrices should still be multiplied together offline.
- `font-variation-settings` animations require matching axis lists for additive composition. Sparse one-axis animation lists do not union, which is why the original additive prototype had quadratic uncompressed CSS.

## Other backend considered

SVG filter buffers can hold many pixels and chain operations without CSS readback. They are not a good numeric-state backend for this model: filter primitives expose image buffers rather than reusable CSS numbers, dense arbitrary matrices do not map directly to `feConvolveMatrix`, and primitive results are clamped to the permitted color range. They remain useful only if a later design can keep the entire remaining network inside the image backend.

## Relevant standards

- CSS Properties and Values API: https://drafts.css-houdini.org/css-properties-values-api/
- CSS Scroll-driven Animations: https://drafts.csswg.org/scroll-animations-1/
- CSS Values custom functions: https://drafts.csswg.org/css-mixins-1/#function-rule
- CSS Fonts `font-variation-settings`: https://drafts.csswg.org/css-fonts-4/#font-variation-settings-def
- Filter Effects: https://www.w3.org/TR/filter-effects-1/

## Next work

The per-shard projection fan-out is solved, and paired range transport reduces
the FC boundary to 1,536 timelines and animations. This is a real constant-factor
improvement, not the missing vector primitive: one timeline still exposes at
most the two independent numbers in a box's position and extent. Reaching the
130 ms/block target still requires a browser operation that exposes many
results at once, or a backend that applies GELU and continues to projection
without converting every FC coordinate into separate CSS state.
