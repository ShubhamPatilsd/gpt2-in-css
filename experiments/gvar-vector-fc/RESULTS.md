# One-glyph vector matvec

This experiment puts every matrix-output bar into one complex TrueType variable
glyph. The glyph outline contains one rectangle per output, and `gvar` moves
each rectangle endpoint from the 256 live axis values. The runtime page contains
no JavaScript.

## Structural scaling probe

| Outputs in one glyph | WOFF2 size | Warm mutation median | Live elements |
| ---: | ---: | ---: | ---: |
| 256 | 190,640 bytes | 81.69 ms | 12 |
| 3,072 | 2,024,288 bytes | 84.69 ms | 12 |

Increasing the number of output rectangles by 12× barely changed warm runtime.
This is the first tested font representation whose browser object count and
mutation time do not grow with the FC output width.

## Real GPT-2 FC + GELU

The real page uses three complex glyphs, one for each 256-axis input shard.
Their 3,072 partial-result rectangles are reduced into one column, added,
rescaled to FC preactivation units, and passed through the GELU transfer table.

| Metric | Result |
| --- | ---: |
| Warm mutation median | 116.19 ms |
| Load and first paint | 212.61 ms |
| Calibration mean RMSE | 0.02753 |
| Held-out mean RMSE | 0.02791 |
| Worst held-out error | 0.18514 |
| WOFF2 assets | 9,612,544 bytes |
| HTML | 26,966 bytes |
| Live elements | 30 |

The first build used a 28,000-unit base and allowed varied outline endpoints to
reach approximately 53,000 units. FontTools evaluated those coordinates
correctly, but Chromium wrapped/clamped them at rasterization because TrueType
outline coordinates are signed 16-bit. Keeping the base near 14,500 and every
calibrated endpoint below 30,000 removed the catastrophic errors.

## Meaning

This replaces the ordinary HVAR raster page's 3,072 bar elements and 9,216
shaped glyphs with three shaped glyphs. Its RMSE is close to the ordinary bar
transport's 0.02344 while using 30 elements instead of 3,090. It is still a
one-way geometry-to-raster transport: the resulting pixel vector cannot become
the next variable font's axes without another readback mechanism.

## Reproduce

```sh
uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors \
  python tools/build_gvar_vector_glyph_probe.py
GVAR_VECTOR_OUTPUTS=3072 \
uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors \
  python tools/build_gvar_vector_glyph_probe.py
GVAR_VECTOR_OUTPUTS=3072 node tools/test_gvar_vector_glyph_probe.mjs

uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors \
  python tools/build_gvar_vector_fc_probe.py
node tools/test_gvar_vector_fc_probe.mjs
```
