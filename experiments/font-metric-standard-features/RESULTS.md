# Standard-feature font-unit multiplexing

## Question

The arbitrary `salt` feature does not affect CSS `ch`/`ic` units. Do browsers
nevertheless honor standardized OpenType substitutions when measuring those
units, allowing one shared HVAR font to expose several selectable row pairs?

## Test

One variable font maps `0` and `水` to different HVAR rows under:

- `salt`
- proportional and tabular numerals (`pnum`, `tnum`)
- slashed zero (`zero`)
- superscript and subscript (`sups`, `subs`)
- stylistic and character variants (`ss01`, `cv01`)
- full/proportional width and traditional/simplified forms
  (`fwid`, `pwid`, `trad`, `smpl`)

For every case the HTML/CSS-only page contains both an explicit rendered glyph
and a box sized with `1ch` or `1ic`. The external harness measures both.

## Result

Chrome applied all twelve substitutions to explicitly rendered glyphs. Their
advances matched the selected HVAR rows within ordinary subpixel layout error.

`1ch` and `1ic` ignored every substitution. Both units continued returning the
unsubstituted base metric for all twelve cases.

This separates two behaviors conclusively:

```text
rendered text shaping: feature-sensitive
CSS font-relative units: base-metric only
```

## Decision

Reject OpenType feature selection as a row-bank selector for direct numeric
font units. It can select many glyph advances inside one text run, but CSS has
no operation that exposes each shaped glyph's advance as a reusable number.
The result therefore returns to the already measured per-glyph geometry path.
