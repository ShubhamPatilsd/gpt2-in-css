# TTC metric-bank probe

## Question

Can many CSS font faces select different output rows while a TrueType Collection
stores the shared HVAR matrix only once?

CSS Fonts 4 specifies collection-member selection with an exact PostScript-name
fragment, such as `url(collection.ttc#FaceName)`. OpenType collections can also
share identical table data between faces, so this would be an unusually compact
way to expose many matrix rows if Chrome implemented the selector.

## Fixtures

- `metric-bank.ttc`: 64 variable faces with distinct names and cmaps, sharing the
  HVAR/fvar/glyf data. Each face should expose a different pair of HVAR dot
  products through `1ch` and `1ic`.
- `static-bank.ttc`: a non-variable control with 64 faces. Each face maps `0` and
  `水` to glyphs with unmistakably different fixed advances.
- `index.html` and `static.html`: HTML/CSS-only consumers.
- `tools/test_ttc_metric_bank.mjs`: external browser measurement harness.

## Results in Chrome

The variable collection returned the face-0 pair for all 64 requested faces:

- RMSE: `109.006`
- max error: `250.75`
- first eight recovered values:
  `134.5, 1.75, 134.5, 1.75, 134.5, 1.75, 134.5, 1.75`

The static control failed in exactly the same way. Expected advances began with
`700, 1100, 703, 1105, 706, 1110, 709, 1115`, but Chrome returned
`700, 1100` for every face.

An independent check using WPT's two-face `ahem.ttc` also rendered the first
face for every PostScript-name and numeric fragment, including in fresh browser
contexts. The existing WPT collection test exercises unfragmented face-0 loading;
it does not verify member selection.

## Decision

Reject this transport for current Chrome. FontTools does physically deduplicate
the shared tables, and the file is only 143,628 bytes for 64 variable faces, but
the browser cannot select any face after the first one. The failure happens before
HVAR accuracy or scaling becomes relevant.

Revisit only if Chrome implements collection URL fragments. A future smoke test
should use the static control first.

## References

- CSS Fonts 4 collection fragments:
  https://www.w3.org/TR/css-fonts-4/#font-face-src-loading
- OpenType Font Collections:
  https://learn.microsoft.com/en-us/typography/opentype/spec/otff
- Matching Chrome support report:
  https://github.com/Fyrd/caniuse/issues/6566
