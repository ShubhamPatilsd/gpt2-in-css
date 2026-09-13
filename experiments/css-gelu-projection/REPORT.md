# CSS GELU before pure HVAR projection

## Result

Computing all 3,072 GELU values once on an ancestor as registered, inherited
CSS numbers is viable and materially faster than applying `avar2` GELU inside
each of the 768 projection outputs.

Chrome 153, warm browser/font/HTTP caches, fresh page graph and a distinct
never-before-shaped vector for every timed sample:

| Variant | Fresh vectors | Median | p10-p90 | Max output RMSE | Max abs error |
|---|---:|---:|---:|---:|---:|
| Existing avar2 projection oracle | 16 | 463.7 ms | 454.4-474.1 ms | 0.05203 | 0.97035 |
| Exact CSS `exp`/`pow` GELU, inherited | 16 | **111.4 ms** | 107.7-114.5 ms | **0.01802** | **0.05148** |
| 8-knot hinge GELU, inherited | 16 | 123.0 ms | 120.2-125.5 ms | 1.20477 | 21.90333 |
| 16-knot hinge GELU, inherited | 16 | 261.0 ms | 259.1-266.5 ms | 0.14618 | 2.80932 |
| 32-knot hinge GELU, inherited | 16 | 324.6 ms | 317.2-328.5 ms | 0.03731 | 0.62597 |
| Ideal exact post-GELU vector | 16 | **86.8 ms** | 84.6-87.5 ms | 0.01802 | 0.05148 |
| Exact GELU repeated on every output (control) | 1 | 20,142.6 ms | - | 0.01759 | 0.04364 |

The exact inherited path is **4.16x faster** than the current avar2 projection
oracle. It is only 24.6 ms slower than supplying the exact post-GELU vector,
so the 3,072 exact CSS GELU evaluations are not the dominant remaining cost.
The pure 3,072 -> 768 HVAR projection itself accounts for most of the 86.8 ms
ideal floor.

The hinge approximations are not useful here. Eight knots are slightly slower
than exact CSS GELU and much less accurate. More knots improve accuracy but
rapidly increase CSS math cost; even 32 knots remain less accurate and nearly
3x slower than exact GELU.

## Why this demonstrates compute-once behavior

In `exact-inherited.html`, `--g-0000` through `--g-3071` are declared on
`#state`. CSS Typed OM reports each sampled value as a `CSSUnitValue` on that
element, and the exact same typed value is inherited by `#bank` and its output
children. The bank exposes all 3,072 axes.

In the control page, `#state` and `#bank` retain the registered initial value
zero; each output owns and computes the GELU values and its own 3,072-axis
list. It produces the same numeric result but is **180.8x slower** than the
ancestor topology. That makes the sharing result decisive rather than an
assumption about lazy custom-property evaluation.

## Methodology and correctness

- Inputs are sixteen unique interpolations of the four real Chrome-captured
  block-1 preactivation and residual vectors in
  `../hvar-vector-oracle/captured-boundaries.json`.
- Every sample uses a fresh page/layout graph. Browser, font, and HTTP caches
  remain warm. The injected test vector is installed before timing.
- Timing begins at the selector mutation and ends after forcing all 768 output
  widths, not only one glyph.
- Runtime pages contain no JavaScript. The Playwright harness is external.
- The generated pages isolate GELU plus the pure projection. The harness adds
  the captured residual and real block-1 projection bias after reading the
  intrinsic projection widths, then scores the resulting full output against
  float GPT-2 block-1 math.
- The ideal and exact variants have the same error floor, showing that their
  remaining ~0.018 RMSE is HVAR endpoint/layout quantization, not CSS GELU.

## Practical conclusion

Use the exact inherited CSS GELU topology. Do not use the hinge variants, and
do not keep GELU in `avar2` on every output font. The next optimization target
is the still-real pure HVAR projection/shaping floor (~87 ms in this isolated
stage), not GELU approximation.

Rebuild:

```sh
PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools --with brotli \
  python tools/build_css_gelu_projection.py
```

Benchmark (expects the workspace server on port 4178):

```sh
node tools/test_css_gelu_projection.mjs
```
