# Browser certification budget

The original browser head chose its ±135.309 font-axis range from ten local
fixtures. Only 70 of the broader 1,024 contextual states fit that range. The
largest saved coordinate is 263.612, so a 1% guard requires ±266.248. At that
range, one F2DOT14 coordinate step is 0.01625 and the worst-case 768-vector
axis-rounding error norm is 0.2252.

The search was rerun against global-int16 target weights at hidden coordinates
rounded to that browser grid. Both coarse and exact scores were then widened
by the same browser-realization allowance.

| Coarse | Allowance per side (buckets) | Groups median / p95 / max | Mean exact rows | Dense reduction |
| --- | ---: | ---: | ---: | ---: |
| Row-wise int10 | 0 | 3 / 15 / 47 | 1,208 | 41.6x |
| Row-wise int10 | 8 | 3 / 16 / 53 | 1,275 | 39.4x |
| Row-wise int10 | 16 | 3 / 17.85 / 56 | 1,345 | 37.4x |
| Row-wise int10 | 24 | 3 / 18 / 61 | 1,407 | 35.7x |
| Row-wise int10 | 32 | 3.5 / 19.85 / 64 | 1,484 | 33.9x |
| Row-wise int11 | 0 | 2 / 5 / 17 | 555 | 90.5x |
| Row-wise int11 | 8 | 2 / 6 / 18 | 577 | 87.1x |
| Row-wise int11 | 16 | 2 / 6 / 20 | 601 | 83.6x |
| Row-wise int11 | 24 | 2 / 6 / 22 | 627 | 80.2x |
| Row-wise int11 | 32 | 2 / 7 / 23 | 661 | 76.1x |

The certified frontier survives a production-sized axis range and useful
realization allowances. Int11 is substantially more robust: even a 24-bucket
allowance keeps p95 at six groups and the maximum at 22, versus 18/61 for
int10. The browser comparison nevertheless favors int10 for one-shot use:
certified int11 takes 104.80 seconds cold versus int10's 36.66 seconds because
it doubles the shaped glyph stream. Int11 remains the warm/recurrent option.

The global-int16 target itself matches dense float GPT-2 on 1,016/1,024
states. Thus this screen is rigorous relative to the browser's int16 target,
not the original float checkpoint. A fully float-exact claim would also need
to certify the int16 residual or refine the final near ties.

## What the allowance can certify

An audit of the generated HVAR arithmetic separates font-axis quantization from
metric/layout realization. Under the observed Chromium model (normalized axes
floor to F2DOT14, each shaped metric may move by at most one 1/64-pixel unit),
the production ±266.248 heads require 19 coarse buckets and 8 fine buckets.
The existing symmetric 24-bucket allowance therefore has five coarse buckets
of conditional headroom and is sufficient for this target:

```text
global-int16 weights at the browser-realized F2DOT14 hidden coordinates
```

It is not a browser-portable proof against the original unrounded hidden
vector. Axis displacement then dominates: the current ±135.309 heads require a
worst-case stop gap above 300 buckets, and the production range requires above
589. A strictly specification-level symmetric F2DOT14 conversion model raises
the production gap above 731 buckets because OpenType leaves post-normalization
instance precision and rounding implementation-dependent.

This distinction should stay explicit. For the current CSS inference pipeline,
the realized-coordinate target is the useful contract because every downstream
font matrix consumes those same realized coordinates. A float-checkpoint-exact
claim would additionally need a residual refinement for both coordinate and
global-int16 weight error; the current target matches the dense float winner on
1,016/1,024 screened states.

The measured cost of the three contracts is:

| Contract | Coarse | Groups median / p95 / max | Mean exact rows | Dense reduction |
| --- | --- | ---: | ---: | ---: |
| Realized-coordinate Chromium model | int10 | 3 / 17 / 55 | 1,322 | 38.0x |
| Realized-coordinate Chromium model | int11 | 2 / 6 / 19 | 592 | 85.0x |
| Unrounded-coordinate Chromium model | int10 | 16 / 117.7 / 194 | 8,216 | 6.1x |
| Unrounded-coordinate Chromium model | int11 | 7.5 / 56.7 / 143 | 3,903 | 12.9x |
| Unrounded-coordinate specification model | int10 | 26 / 161.9 / 197 | 11,776 | 4.3x |
| Unrounded-coordinate specification model | int11 | 12 / 88 / 184 | 6,147 | 8.2x |

The two unrounded-coordinate rows quantify only cross-group stopping. They do
not prove that the browser-selected token is the original winner *inside* an
activated 256-token group; that still requires a near-tie residual stage. This
makes the realized-coordinate contract not just cheaper but qualitatively
simpler.

For the retained production realized-coordinate contract, cumulative coverage
by exact-group budget is:

| Budget | int10 | int11 |
| ---: | ---: | ---: |
| 1 | 13.2% | 35.1% |
| 2 | 33.4% | 73.9% |
| 3 | 54.6% | 86.8% |
| 4 | 67.5% | 91.7% |
| 6 | 79.0% | 96.5% |
| 8 | 84.9% | 97.9% |
| 16 | 94.6% | 99.9% |
| 32 | 99.3% | 100% |
| 61 | 100% | 100% |

This favors a shallow int10 fast path plus an explicit tail strategy. A
six-stage browser page is fastest but covers 79.0%; extending it to 16 stages
raises coverage to 94.6% while increasing the measured cold first result from
49.10 to 86.94 seconds.

```sh
make analyze-gpt2-browser-certification-budget
```
