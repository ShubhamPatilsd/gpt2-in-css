# Feature-indexed font metric readback

## Question

Can one variable font store many output rows as GSUB `salt` alternates, select a
row with `font-feature-settings: "salt" N`, and expose its HVAR advance directly
through `1ch` or `1ic`?

If this worked, one font face plus 64 nested CSS nodes would return 128
independent matrix outputs without creating output glyph geometry.

## Result: rejected

Chrome honors the numbered `salt` selection during ordinary text shaping, but
does **not** apply it when resolving the `ch` and `ic` CSS units.

The test font contains 64 alternates for `0` and 64 alternates for `水`. Each
alternate has an independent 32-input HVAR dot product. The page selects
alternate `N` with `font-feature-settings: "salt" N`.

| Readback path | Outputs | RMSE | Max error | Warm median |
| --- | ---: | ---: | ---: | ---: |
| `calc(1ch)` / `calc(1ic)` | 128 zeros | 51.5736 | 134.5 | 45.4 ms |
| Shaped glyph geometry | 128 correct | 0.01651 | 0.03027 | 67.1 ms |

The correct geometry result proves that the GSUB indices and per-alternate HVAR
rows work. The all-zero metric result proves that CSS resolves `ch` and `ic`
from the default character metrics rather than from the GSUB-substituted glyph.
Changing the numbered feature therefore cannot multiplex those units.

The metric page is faster only because it never evaluates the selected
alternate rows; its output is invalid.

## Artifacts

- `index.html`: HTML/CSS-only attempted metric transport
- `geometry.html`: HTML/CSS-only shaped-glyph control
- `feature-rows.ttf`: one font face containing all 128 output rows
- `reference.json`: matrix/input/reference data

Both runtime pages contain no JavaScript. The external Playwright harness only
measures browser output.

## Reproduce

```sh
/usr/bin/python3 tools/build_feature_metric_readback.py
node tools/test_feature_metric_readback.mjs
```
