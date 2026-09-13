# Real-HVAR anchor packing

This fixture replaces the four synthetic source widths with real variable-font
HVAR dot products. Their glyph widths are rounded and packed with
`anchor-size()`, decoded through `cqi`, and accumulated into a four-axis vector.

Both tested input vectors matched the offline reference to approximately
`1e-6`. This proves the full local bridge:

`HVAR matrix output → glyph width → packed CSS carrier → reusable vector`.

The full GPT-2 probe additionally applies bias, per-channel quantization and
GELU in CSS before the additive projection.
