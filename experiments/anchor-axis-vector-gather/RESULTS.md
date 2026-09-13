# Direct anchor geometry to font axes

This probe asks whether 3,072 element widths can feed a real GPT-2
`3,072 → 768` HVAR projection by placing `anchor-size()` expressions directly
inside `font-variation-settings`.

## Result

Rejected. Chrome computes the complete `font-variation-settings` declaration
as `normal`. Both the initial and mutated outputs equal the font's zero-axis
baseline; their RMSE is exactly the RMS of the expected projection. The roughly
20 ms mutation timing therefore measures layout plus a default font render, not
the matrix projection.

`anchor-size()` can drive sizing properties, but it is not accepted as a value
inside `font-variation-settings`. A separate CSS conversion step is still
required before geometry can become a reusable font-axis vector.
