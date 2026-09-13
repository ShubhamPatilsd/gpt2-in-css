# TrueType bytecode as an internal numeric backend

## Question

Can a variable font read its variation axes with `GETVARIATION`, perform
fixed-point arithmetic in the TrueType interpreter, and move many outline
points without returning intermediate values to CSS or SVG pixels?

If Chromium exposed this path, it could combine the existing compact HVAR
input representation with reusable arithmetic inside the font rasterizer.

## Probe

The generated font contains three 16-unit-wide rectangle glyphs:

- `plain` has no glyph program;
- `constant` uses `SCFS` to move its right edge to 24 pixels;
- `computed` uses `GETVARIATION`, `DIV`, `MUL`, and `ADD` to map one axis from
  `-1..1` to an 8..24-pixel right edge, then applies the result with `SCFS`.

The font includes `cvt `, `fpgm`, `prep`, and `gasp` tables and requests grid
fitting at every tested size. The page has no runtime JavaScript.

## Browser result

Headless Google Chrome on macOS loaded the font successfully but rendered all
three glyphs identically at 16, 32, and 64px. Neither the constant program nor
the variation-dependent program changed the outline.

| Test | Result |
| --- | --- |
| Font loaded | yes |
| Constant glyph instructions executed | no |
| `GETVARIATION` glyph instructions executed | no |
| Axis-dependent width at 64px | no; always 17 antialiased pixels |

This matches the independent
[FreeType RasterInfo diagnostic](https://freetype.org/freetype2/docs/rasterinfo/rasterinfo.html):
the same Chrome/macOS environment renders `E` for its interpreter fields, the
font's documented signal that TrueType bytecode is inactive.

## Decision

Reject TrueType bytecode as the runtime arithmetic backend for this browser
target. The instruction set is capable on platforms that activate it, but CSS
cannot require a web browser to execute font hinting programs. A backend that
works only under a particular native font scaler would also make the demo
non-portable.

The complex `gvar` vector glyph remains useful because ordinary variable-font
outline interpolation does run. What is unavailable is the programmable font
VM that could have transformed those outline results into reusable internal
state.

## Reproduce

```sh
uv run --with 'fonttools[woff]' python tools/build_truetype_bytecode_probe.py
node tools/test_truetype_bytecode_probe.mjs
```

Machine-readable output is in `browser-results.json`.
