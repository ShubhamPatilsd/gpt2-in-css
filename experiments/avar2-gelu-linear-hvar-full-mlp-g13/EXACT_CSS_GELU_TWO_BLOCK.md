# Exact ancestor CSS GELU in the two-block HVAR path

This comparison replaces the projection fonts' repeated `avar2` GELU mapping with exact GPT-2 GELU values computed once as inherited typed CSS numbers. Everything else in the two-block path remains unchanged: attention, FC matvecs, residuals, vector transport, and final output extraction.

Runtime artifacts contain HTML, CSS, and fonts only. Both pages contain zero script elements.

## Controlled warm benchmark

Chrome 153.0.8010.36; HTTP, browser, and font caches warm; a fresh page/layout graph for every mutation; six rounds over three distinct real cases; all 768 final widths forced inside each timing.

| Variant | Median | Range | Elements | Max RMSE vs exact float |
| --- | ---: | ---: | ---: | ---: |
| Existing per-output `avar2` GELU | 2410.6 ms | 2379.3–2504.8 ms | 23,528 | 0.05113 |
| Exact inherited CSS GELU, computed once | 1810.8 ms | 1659.8–1900.5 ms | 23,528 | 0.03792 |

The integrated speedup is **1.33×**, or about **600 ms / 24.9% less latency**. The exact variant is closer to the exact float reference for every one of the four validation cases. It intentionally does not match the old “represented” reference, because that reference includes the old piecewise `avar2` approximation.

## Load size

| Variant | Total | HTML | CSS | WOFF2 |
| --- | ---: | ---: | ---: | ---: |
| Existing `avar2` | 19.403 MB | 2.938 MB | 2.472 MB | 13.993 MB |
| Exact compute-once | 19.819 MB | 3.172 MB | 2.814 MB | 13.833 MB |

The exact variant adds 0.416 MB (+2.15%) overall. Its pure linear projection fonts are 0.160 MB smaller; registered-property and GELU-function declarations account for the net increase.

## Interpretation

Computing GELU once before projection is a validated improvement for the real two-block graph. The isolated projection probe improved by 4.16×, while the full graph improves by 1.33× because attention, FC computation, transport, residual work, and output extraction still dominate the remaining time.

Artifacts:

- `connected-two-block-exact-css-gelu-layoutless.html`
- `exact-css-gelu-two-block-results.json`
- `../../tools/build_exact_css_gelu_two_block.py`
- `../../tools/benchmark_exact_css_gelu_two_block.mjs`
