# HVAR shaping versus CSS exposure

Measured in Chrome 153 on September 12, 2026. Every fixture renders the same
9,216 glyphs for the real GPT-2-small 768→3,072 FC matrix. Runtime pages contain
no JavaScript. The external harness performs eight rotated navigations, waits
for fonts and two animation frames, and forces every exposed result.

| Fixture | Layout objects | Timelines | Warm median | Forced read |
| --- | ---: | ---: | ---: | ---: |
| three continuous font runs | 3 | 0 | 136.3 ms | 0.85 ms |
| 3,072 spans in one container | 3,072 | 0 | 111.3 ms | 2.88 ms |
| separate output containers | 9,216 | 0 | 134.8 ms | 2.95 ms |
| expose every result through a timeline | 9,216 | 3,072 | 588.5 ms | 163.7 ms |
| timeline exposure plus CSS decode/GELU | 3,072 | 3,072 | 1,074.3 ms | 163.0 ms |

The font calculation itself is not the dominant cost. Changing from three
continuous runs to thousands of plain output objects stays in the same
100–135 ms band. Adding named timelines costs roughly another 477 ms, and
turning their values into reusable CSS numbers and GELU outputs costs roughly
another 486 ms. The complete exposed stage is about 9.7× the shared-span
shaping control.

Therefore reducing glyph count or consolidating text runs cannot deliver the
required order-of-magnitude improvement. The missing primitive is a way to
read many HVAR advances as reusable numeric state without one timeline/property
pipeline per output.

Artifacts:

- `view-timeline-fc-font-three-runs.html`
- `view-timeline-fc-font-shared-spans.html`
- `hvar-shaping-exposure-results.json`
- `../../tools/test_hvar_shaping_exposure.mjs`

