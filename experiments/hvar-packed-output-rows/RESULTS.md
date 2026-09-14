# Packing multiple HVAR output rows into one advance

## Result

This does reduce browser work, but it cannot preserve independent continuous
dot products. It is not a viable general vector carrier.

| Encoding | Carriers | Glyphs | DOM elements | Warm median | FC RMSE | Lane RMSE |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| One output per advance | 3,072 | 9,216 | 9,223 | 61.5 ms | 0.0003 | 0.0003 |
| Two outputs, radix 256 | 1,536 | 4,608 | 4,615 | 33.5 ms | 60.01 | 84.87, 1.02 |
| Four outputs, radix 16 | 768 | 2,304 | 2,311 | 18.8 ms | 24.63 | 22.69, 22.73, 37.31, 1.81 |

The 16 real GPT-2 test vectors have FC preactivations from -7.19 to 11.63 and
an overall RMS magnitude of 1.74. Errors of 24-60 are therefore catastrophic.
The packed variants select the wrong quantized digit for 77.7% and 75.9% of
outputs respectively.

The runtime pages contain only HTML, CSS, and fonts. Chrome 153 was driven by
the external Playwright harness for measurement.

## Why the radix digits contaminate one another

For two intended values, the font can form one continuous advance:

```
packed = low + radix * high
```

HVAR is linear. Both `low` and `high` are fractional dot products. It cannot
round `high` before adding it. Consequently, the fractional part of `high`,
multiplied by the radix, occupies the same part of the number that was supposed
to contain `low`.

CSS receives only the final combined advance. `round()` and `mod()` at that
point cannot distinguish the intended low value from the higher lane's
fractional contribution. The highest lane is the only one that avoids this
specific contamination, which is exactly the lane-error pattern in the table.

The offline implementation of the same combined-row arithmetic produces the
same catastrophic model error. Chromium adds only normal font-axis and layout
rounding, plus rare one-unit boundary changes that can themselves cause a
radix wrap. This is therefore not primarily a browser implementation bug.

## Font and geometry limits

- A TrueType advance is an unsigned 16-bit value: 0 through 65,535 design
  units per glyph.
- An HVAR region delta is signed 16-bit.
- Because the base advance must cover the maximum negative excursion and the
  positive excursion must remain below 65,535, these rows are limited to about
  32,751 total absolute coefficient units per 256-axis shard.
- The current reliable backend has 256 axes per font. A real 768-input FC row
  therefore remains a three-glyph fallback run even when several output rows
  are packed into that run.

To fit those limits, the two-lane probe needs a very wide nominal range of
plus/minus 128 per lane. The four-lane probe needs plus/minus 32. Tighter,
more accurate scaling makes the radix-weighted coefficients exceed the glyph
advance range before the browser even loads the font.

## Interpretation

The timing improvement is real and roughly follows the reduction in carriers,
glyphs, and elements: 1.84x for two lanes and 3.27x for four. But radix packing
requires a nonlinear quantization boundary **before** the lane values are
summed. HVAR supplies no such boundary. CSS supplies it only after layout,
which is too late.

This route would work for values that were already integers before entering
the font. Making GPT-2 activations integer-valued at that point would require a
separate per-output quantization mechanism and would reintroduce the carrier
boundary this experiment was meant to remove.

## Reproduce

```sh
uv run --with numpy --with fonttools --with brotli --with safetensors --with pillow \
  python tools/build_hvar_packed_output_rows.py
HVAR_PACKED_ROUNDS=24 HVAR_PACKED_WARMUPS=5 \
  node tools/test_hvar_packed_output_rows.mjs
```

Full measurements are in `browser-results.json`; inputs, reference outputs,
and the matching offline packed arithmetic are in `reference.json`.
