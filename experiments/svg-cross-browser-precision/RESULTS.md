# Cross-browser vector-backend gate

Decision: **reject Firefox as a bulk-vector escape hatch**.

The runtime fixtures contain only HTML, CSS, SVG, and fonts. Playwright is an external verifier. No GPT-2 architecture, checkpoint tensor, or inference rule was changed.

## SVG filter intermediate precision

The gate creates 64 inputs separated by roughly `1/64,512`, passes them through a selected SVG filter boundary, then amplifies the surviving difference by 512 using four moderate color-matrix stages. An unfiltered row and a single-matrix row prove that both engines paint the fixture. The browser-neutral page uses `linearRGB`, object-bounding-box filter regions, and coefficients small enough to avoid Firefox's large-matrix-coefficient behavior.

| Boundary | Chrome 153 distinct levels | Firefox 153 distinct levels |
|---|---:|---:|
| Adjacent color matrices | 64 | 1 |
| Named identity color matrix | 1 | 1 |
| Two-input arithmetic add | 2 | 2 |
| Two-input arithmetic multiply | 1 | 1 |
| 1×1 convolution | 1 | 1 |
| Identity component transfer | 1 | 1 |

Firefox does not preserve the sub-eight-bit signal through any tested reusable boundary. It also loses the signal between adjacent color matrices, where Chrome can retain or fuse all 64 values. Switching engines therefore cannot supply the reusable floating-point raster needed by the SVG GPT-2 path.

Raw measurements are in `chromium.json` and `firefox.json`.

## Variable-font axis ceiling

The existing real matrix fixtures provide otherwise equivalent 256- and 257-axis HVAR fonts. Firefox renders the first 256-axis result at 255.4167 px versus 255.408 px expected. The 257-axis page renders a 18.4667 px fallback glyph instead of the expected matrix result, although `document.fonts.status` settles to `loaded`.

Firefox therefore has the same practical cutoff observed in Chrome: 256 axes work and 257 axes do not. It cannot run the full 768- or 3,072-coordinate stage inside one variable font.

The axis measurement is recorded in `axis-limit-firefox.json`.

## Reproduce

```sh
python3 tools/build_svg_cross_browser_precision.py
SVG_PRECISION_BROWSER=chromium node tools/test_svg_cross_browser_precision.mjs
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpt2-css-playwright-browsers \
  SVG_PRECISION_BROWSER=firefox node tools/test_svg_cross_browser_precision.mjs
```
