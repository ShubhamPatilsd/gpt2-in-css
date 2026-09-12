# SVG calibration and RGB group-packing results

This experiment asks two separate questions about the 8-bit SVG full-block
backend:

1. Can systematic quantization error be removed with zero-cost affine bias
   corrections?
2. Can the 32 range groups be evaluated in parallel instead of paying for 32
   separate GELU branches?

The runtime fixtures contain HTML, CSS, and SVG only. The Playwright scripts are
external measurement harnesses.

## Calibration correction is not the solution

`screen_svg_fixed_calibration.py` first looked promising in its simplified
numeric model. On two-fold cross-validation over 64 real GPT-2 token states, an
8-group configuration improved from 51/64 to 55/64 winner matches after fitting
per-affine mean-error corrections.

The real Chromium result contradicted the screen:

| 8 groups, 1.4 headroom | winners | warm mean | final RMSE |
| --- | ---: | ---: | ---: |
| No correction | 10/64 | 621.9 ms | 5.4484 |
| Fitted affine biases | 12/64 | 640.5 ms | 5.5347 |

One fitted block-11 attention correction reached `-26.54`; the simplified
screen was compensating for an error that did not correspond to Chromium's
actual intermediate rounding. This is why offline winner screening cannot be
used as the acceptance test for this backend.

`analyze_svg_browser_correction.py` then fitted corrections to actual Chromium
output vectors and evaluated them on the opposite parity fold. For the 8-group
page, a final bias reduced winner accuracy to 4/64. A clipped per-channel affine
map improved it to 27/64, still far below an acceptable model. For the 32-group
page, the same maps moved 46/64 to only 46/64 and 47/64 respectively. The
remaining error is therefore not a stable offset or scale error at the final
boundary; information is lost in an input-dependent way inside the blocks.

Bias correction remains supported behind `SVG_FILTER_BIAS_CORRECTIONS` for
reproducibility, but it is rejected as the main accuracy strategy.

## RGB-packed GELU is a useful scaling result

The original bucketed GELU emitted one lookup branch and mask for every range
group. The packed path uses the fact that an SVG filter has three independent
color channels:

- copy the same activation code into R, G, and B;
- apply three different GELU lookup tables in one `feComponentTransfer`;
- select three disjoint range groups with one RGB mask;
- sum the selected channels back into the common scalar surface.

This evaluates three range groups per branch while retaining 32 independently
scaled groups. Enable it with `SVG_FILTER_PACKED_GELU=1`.

The 64-case Chromium comparison used the same calibration states, 32 groups,
1.08 headroom, and the same screenshot/readback harness:

| 32-group implementation | winners | warm mean | median | primitives | raw HTML | Brotli q5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Separate GELU branches | 46/64 | 1299.0 ms | 1309.0 ms | 10,767 | 3,706,045 B | 567,662 B |
| Three groups per RGB branch | 44/64 | 714.0 ms | 712.0 ms | 8,871 | 3,252,026 B | 460,789 B |

The packed path is **1.82x faster** and removes 17.6% of filter primitives while
losing two winner matches. In contrast, reducing the model to eight groups was
only modestly faster at 621.9 ms and collapsed accuracy to 10/64. Parallel
channel packing is therefore a materially better scaling direction than
reducing the number of quantization groups.

## Pre-GELU scale-band compression

Stage profiling showed that FC/GELU remained the dominant isolated stage after
RGB packing. It also exposed an important measurement distinction: directly
displaying all 3,072 FC values is much slower than letting the following
projection consume them. The optimization therefore stays inside the SVG
filter chain and does not add a readback boundary.

The new path converts each preactivation from its original 32-group scale into
a smaller set of shared GELU scales. One ratio image and one arithmetic
`feComposite` perform the conversion for the entire 3,072-value vector. RGB
packing then needs only `ceil(G / 3)` lookup passes for `G` GELU bands. The
rest of the model retains 32 range groups. Configure this independently with
`SVG_FILTER_GELU_BUCKETS`; no weights or model layers are removed.

The first sweep used the same 64 calibration states as the earlier packed test:

| GELU bands | RGB passes/block | winners | mean warm time | raw HTML | primitives |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 32 | 11 | 44/64 | 714.0 ms | 3,252,026 B | 8,871 |
| 8 | 3 | 44/64 | 529.9 ms | 2,473,805 B | 8,031 |
| 6 | 2 | 44/64 | 470.0 ms | 2,407,494 B | 7,923 |
| 4 | 2 | 46/64 | 468.9 ms | 2,345,979 B | 7,923 |
| 2 | 1 | 30/64 | 455.9 ms | 2,273,868 B | 7,815 |

Two bands cross the accuracy cliff. Four bands are the best measured point:
they are **1.52x faster than 32-band RGB packing** and **2.77x faster than the
original separate-branch graph**. The higher 46/64 calibration result should
not be interpreted as a more faithful model; quantization noise happened to
repair two top-1 decisions.

The generalization check evaluated 84 additional token states from the same
16-prompt natural-language suite that were not used to set ranges:

| GELU bands | held-out winners | held-out mean RMSE | held-out mean time |
| ---: | ---: | ---: | ---: |
| 32 | 63/84 | 0.7441 | 702.3 ms |
| 6 | 59/84 | 0.6285 | 460.7 ms |
| 4 | 61/84 | 0.7380 | 457.4 ms |

Four bands therefore retain 61 of the control's 63 held-out winners while
being **1.54x faster**. Six bands use the same two-pass structure but do not
improve winner accuracy. This is a general scale-band transformation, not a
special case for selected dimensions or prompts.

## Evidence

- `offline-screen.json`: two-fold simplified numeric screen.
- `corrections-g8-h1.4.json`: exported correction plan.
- `browser-g8-h1.4-baseline-results.json`: real 8-group control.
- `browser-g8-h1.4-results.json`: real 8-group corrected result.
- `browser-g32-h1.08-baseline-results.json`: real 32-group control.
- `browser-g32-h1.08-packed-gelu-direct-results.json`: packed result.
- `browser-g32-gelu{2,4,6,8}-results.json`: GELU-band calibration sweep.
- `browser-g32-gelu{4,6,32}-natural148-results.json`: full 148-token reports
  used to calculate the 84-token held-out comparison.
- `stage-profile-g32-current.json` and `stage-profile-g32-packed.json`:
  cumulative 60-boundary profiles.
- `stage-profile-g32-*-isolated.json`: baseline-subtracted isolated-stage
  profiles and FC matrix/GELU splits.
- `browser-g8-h1.4-final-correction-screen.json` and
  `browser-g32-h1.08-final-correction-screen.json`: held-out browser-output
  correction screens.

The generated 300 MB fixture directories were moved to Trash after measurement;
they are reproducible from `build_svg_filter_full_block.py`. Compact captures,
reports, and correction data remain in this directory.

The later GELU-band sweep likewise retains its compact scored reports and stage
profiles. Its reproducible generated pages, 148-case trace payload, and raw
768-value browser captures were moved to Trash after scoring.

## Next implementation target

Retain 32 groups for transport and use four scale bands only at GELU. The next
useful test is applying the same vector-wide re-encoding idea to other
group-dependent nonlinear tables while keeping head-local live surfaces. The
failed QKV surface merge shows that adding a fan-in/readback boundary is not a
valid way to obtain that packing.
