# Packed HVAR transport scaling

Measured in headless Chrome 153 on macOS on September 13, 2026. Runtime pages
contain HTML, CSS, and fonts only. The external harness switches between two
HVAR-produced input vectors and forces 64 outputs from a following dense HVAR
matrix.

## Compared transports

Both transports encode four 12-bit coordinates in one container: four low
six-bit digits in its width and four high six-bit digits in its height.

- **Additive animations:** each decoded coordinate interpolates a complete
  one-hot `font-variation-settings` vector. This was the previous working
  gather.
- **Registered inheritance:** each nested decoder freezes four local `cqi` /
  `cqb` results into registered numeric properties. Those numbers inherit to
  the final element, which constructs the complete axis list once.

Both produce the same matrix outputs and therefore the same numeric error.

## Scaling result

| Live input width | Animation transport | Registered transport | Speedup | Animation CSS | Registered CSS |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | 10.3 ms | 6.0 ms | 1.7x | 62 KB | 24 KB |
| 128 | 21.1 ms | 9.2 ms | 2.3x | 197 KB | 47 KB |
| 256 | 58.2 ms | 14.1 ms | 4.1x | 689 KB | 93 KB |
| 512 | 189.9 ms | 25.7 ms | 7.4x | 2.56 MB | 186 KB |
| 768 | 401.0 ms | 41.8 ms | 9.6x | 5.60 MB | 278 KB |

The width-768 numbers are medians of three independent nine-round processes.
Registered transport also reduced warm load from about 1.21 seconds to 164 ms.
Its stylesheet grows linearly rather than quadratically. Brotli q5 compresses
the 278 KB registered stylesheet to 6.1 KB; raw size remains the relevant
parser and style-engine input.

The largest width-768 output RMSE was 0.161 font units on values centered near
60,000 font units. The animation and registered paths were identical, so this
error comes from variable-font interpolation and multi-font shaping rather than
the new property transport.

## Rejected sparse-animation shortcut

An animation per axis with a one-entry variation list does not union the axes.
Chrome retained only the final animation's `"X003" 0.5`. Additive animations
therefore require matching complete lists, which explains their quadratic
growth.

## Decision

Use registered numeric inheritance for vector gathers. At GPT-2 width 768 it
turns the previously dominant gather into a roughly 42 ms operation while
preserving the same result. The remaining scaling costs are now the number of
dense output glyphs, repeated gathers across a full block, and nonlinear
reductions—not the basic conversion of 768 glyph widths into 768 reusable font
axes.

## Reproduce

```sh
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_packed_hvar_transport_scaling.py
PACKED_HVAR_MODE=animation node tools/test_packed_hvar_transport_scaling.mjs
PACKED_HVAR_MODE=registered node tools/test_packed_hvar_transport_scaling.mjs
```
