# Variable-font multimetric probe

## Result

One variable-font instance can expose **five independent dot products** as
native CSS numbers without glyph-width containers, view timelines, or
JavaScript:

| CSS value | OpenType source | Expected | Chrome | Error |
| --- | --- | ---: | ---: | ---: |
| `1ex` | x-height outline / MVAR `xhgt` | -14.75 | -14.75 | 0 |
| `1cap` | cap-height outline / MVAR `cpht` | -51.25 | -51.00 | 0.25 |
| `1ch` | HVAR advance of `0` | -50.50 | -50.50 | 0 |
| `1ic` | HVAR advance of `水` | -22.50 | -22.50 | 0 |
| `1lh` | MVAR `hasc`, with `USE_TYPO_METRICS` | -40.50 | -41.0156 | -0.5156 |

The successful-channel RMSE is 0.2562 font units and max error is 0.5156.
Across 200 axis mutations, the worst error of those five channels was 0.9844
font units. `cap` rounds to whole font units. `lh` is serialized on Chrome's
CSS subpixel grid, so it is coarser; increasing the probe's font size can
reduce that decoded error.

## VVAR / writing-mode result

Vertical writing does **not** create two more numeric channels:

- With mixed text orientation, `ch` and `ic` still returned the horizontal
  HVAR values (-50.5 and -22.5).
- With upright orientation, they returned `1em` (decoded delta 0).
- The font's VVAR rows evaluate offline to 40.75 and -12.5, but Chromium did
  not expose those variations through `ch`, `ic`, or measured glyph advance in
  this probe.

Therefore the directly reusable capacity found here is five numbers per font
instance, not seven.

## Performance

On the local Chrome run:

- Warm navigation + font readiness + style read: about 50 ms median.
- Forced axis changes and five-number reads: 5.1 ms per median batch of 200,
  or 0.0255 ms per update.

The second number is the relevant transport cost once the font is loaded. It
shows that reading MVAR/HVAR metrics as CSS units is much cheaper than creating
layout geometry. The scaling problem remains: GPT-2 needs 768 or 3,072 outputs,
so five channels would still require many separately parameterized font
instances unless the same instance can expose more metric families.

## Reproduce

```sh
/usr/bin/python3 tools/build_font_multimetric_probe.py
node tools/test_font_multimetric_probe.mjs
```

The generated runtime page contains no JavaScript.
