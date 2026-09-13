# Grid/subgrid vector transport

Measured in headless Chrome on macOS on September 12, 2026. The runtime page
contains only HTML and CSS; the external Playwright harness changes inputs and
reads results.

## Result

A parent Grid can retain 256 independently sized HVAR glyph advances as 256
track widths. A spanning subgrid gives each coordinate a local container, so
the same declaration converts every track to a registered CSS number:

```css
--v: calc(100cqi / 1px * 1000 / 32 - 8000);
```

No view timelines, named animations, per-output property names, or nested
container-query chain are required. A coordinatewise GELU approximation also
runs locally using CSS `exp()`.

| 256x256 HVAR output transport | Unique-input warm median | Output RMSE |
| --- | ---: | ---: |
| nested container chain | 28.2 ms | 0.2802-0.2848 |
| Grid/subgrid vector | 14.8 ms | 0.2802-0.2848 |

The Grid form is about 1.9x faster while preserving exactly the same decoded
matrix values. Its first changed input takes about 30-36 ms; subsequent unique
inputs take about 13-17 ms.

## What this establishes

Grid is a useful vector carrier for coordinatewise work. It can hold hundreds
of live scalar results in one layout structure and apply the same CSS formula
to all of them without serial inheritance depth.

It does not yet solve dense chaining. Each recovered number is local to one
subgrid cell. CSS has no operation that gathers all 256 sibling-local numbers
into one `font-variation-settings` list for the next HVAR matrix. Expanding the
next matrix directly over these cells would reintroduce a quadratic dependency
graph. Therefore this is a real constant-factor transport improvement, not yet
the missing vector register for a complete GPT-2 block.

A direct anchor gather was tested separately. Supplying
`calc(anchor-size(--source width) / 100px)` as a variation-axis value makes
Chrome compute `font-variation-settings: normal`; the matching static `0.5`
axis works. Anchor geometry therefore cannot bypass this gather boundary.

## Reproduce

```sh
uv run --with numpy --with brotli --with fonttools --with pillow \
  python tools/build_grid_subgrid_vector_probe.py
GRID_VECTOR_MODE=grid node tools/test_grid_subgrid_vector.mjs
GRID_VECTOR_MODE=direct node tools/test_grid_subgrid_vector.mjs
```
