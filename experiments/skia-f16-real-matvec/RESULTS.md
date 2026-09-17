# Real GPT-2 weight slices on explicit Skia float surfaces

## Finding

Real dense arithmetic can remain inside Skia filters through a nonlinear stage
and a second dense matrix. The RGBA32F control agrees with the independent
float64 oracle. RGBA16F improves precision substantially over RGBA8, but **the
signed encoding and fixed numerical ranges still matter**. Changing the surface
format alone is not a demonstrated solution to faithful GPT-2 generation.

This is a standalone **CPU Skia** prerequisite experiment. It does not modify
Chromium, exercise Blink or SVG GPU rendering, or measure token speed. The chain
uses 16-dimensional slices of real GPT-2 weights and ReLU in place of GELU; it
is not equivalent to a GPT-2 MLP or block. No larger dimensions were attempted.

## Actual computation and inputs

The two dense matrices are the top-left `16 x 16` slices of
`h.0.mlp.c_fc.weight` and `h.0.mlp.c_proj.weight`, with their corresponding
original biases. NumPy prepares real block-0 LN2 input vectors for one-token
prompts from the checkpoint, then an independent float64 oracle evaluates

```
first 16 LN2 coordinates -> real FC slice + bias -> ReLU
                         -> real projection slice + bias -> 16 outputs
```

The first two input token IDs are 15496 and 464. Token 11 is added only in the
range-control follow-up and is excluded from calibration. The exact input and
output vectors are saved in each case's `oracle` field; real weights, observed
quantized weights and errors are also recorded. Slice/bias hashes are included
in the follow-up. The checkpoint and source paths/hashes are recorded.

At runtime, each matrix stage uses these actual Skia operations:

1. Draw the live input vector repeatedly into one image band and the static
   weight matrix into a second band. All copies use explicit raster surfaces.
2. Use source-relative `Offset` and `Arithmetic` filters to multiply the input
   samples by their corresponding weight samples, retaining a signed centered
   product representation.
3. Apply an all-ones `MatrixConvolution` reduction. Extract the column whose
   support contains all 16 input products, avoiding truncated edge reductions.
4. Pack the actual reduction image with the bias image; an arithmetic filter
   applies the normalization gain and adds bias.
5. Apply an affine color matrix with clamping to calculate ReLU.
6. Rotate/copy the actual resulting image into the second matrix's source band.

Python schedules fixed draws, but it never reads a vector back and uses those
numbers as the next stage's inputs. Optional intermediate readbacks produce
diagnostics only; the next stage receives the existing Skia snapshot. The
geometry handoff from ReLU into the second matrix was numerically exact in all
15 format/input cases.

No `ImageFilters.Image` children are used: skia-python's embedded-image cloning
previously destroyed float precision in the separate materialization probe.
The new graph uses actual source images and source-relative offset children.

## Surface format comparison

The baseline uses a fixed input range of `[-8,8]`, then conservative matrix L1
bounds for later outputs. Those bounds are `18.2283` after FC and `26.6038`
after projection. The true input RMS is about `0.11`, so this deliberately broad
range wastes many representable levels.

| Input token | RGBA8 final RMSE | RGBA16F final RMSE | RGBA32F final RMSE | Oracle output RMS |
| --- | ---: | ---: | ---: | ---: |
| 15496 | 0.635816 | 0.031030 | 0.000006303 | 0.066675 |
| 464 | 0.635163 | 0.028255 | 0.000009337 | 0.065509 |

In the first case, F16's first-matrix RMSE is `0.017142`. Recomputing the oracle
using the **measured input and weight values** changes that to `0.017141`.
Thus the observed source quantization does not explain most of the error:
product/reduction/bias materialization with centered values introduces more.
This comparison still includes bias representation error; it is not a pure
reduction-only attribution.

The F32 final maximum absolute errors are `1.04e-5` and `2.20e-5`. All observed
F32 FC, ReLU and final stages pass the `0.0002` control gate. That gate checks
the experimental computation against its oracle; it is not a GPT-2 quality
acceptance threshold. [Baseline JSON](n16-r0/results.json)

## One fixed-range control, with a held-out input

The follow-up chooses its input bound as `1.25 * max(abs(input))` across only
the first two input vectors. It then freezes that bound and uses the same
conservative matrix L1 formulas for output ranges. No output oracle values set
the ranges. The resulting bounds are `0.322078`, `0.911155`, and `1.455344`.

| Input token | Calibration role | RGBA8 final RMSE | RGBA16F final RMSE | RGBA32F final RMSE | Clipped input coordinates |
| --- | --- | ---: | ---: | ---: | ---: |
| 15496 | Calibration | 0.034799 | 0.002010 | 4.11e-7 | 0 |
| 464 | Calibration | 0.031648 | 0.001676 | 4.13e-7 | 0 |
| 11 | Held out | 0.034797 | 0.001701 | 4.54e-7 | 0 |

On the held-out slice, F16 has about **20.5 times lower RMSE** than RGBA8, with
maximum absolute error `0.003801`. Its RMSE is still **2.46% of the oracle output
RMS**. One held-out input does not establish generalization or token agreement.
All F32 controls pass; no input clips. The first-matrix, activation and final
errors remain separately visible in the [range-control JSON](n16-calibrated-r1/results.json).

## Costs and precision limits

Each chain allocates 13 explicit application-visible raster surfaces and
performs 47 static draw calls. The sum of their minimum storage is 8,768 bytes
for RGBA8, 17,536 bytes for RGBA16F, and 35,072 bytes for RGBA32F. This is **not
peak memory**: it excludes Skia's internal temporary surfaces, image caches,
Python/NumPy arrays and source-image allocations. Actual surface and snapshot
color types are recorded rather than inferred from a screenshot.

Three timing samples follow one warmup for each case. The full tiny CPU chain
took roughly `0.46-0.72 ms`. It includes construction of input/weight/bias
images, filter creation, all explicit allocation and geometry copies, final
float readback, Python dispatch and final error-summary arithmetic. NumPy's
model input preparation and precomputed matrix oracle are outside the timed
interval. These are diagnostic costs, not browser latency, pure matrix time,
or evidence of a full-model speedup. The tiny repeat count also does not support
a meaningful performance ranking of surface formats.

F16 precision is relative to magnitude. Encoding small signed values around
`0.5` loses detail, especially when reductions need to recover a small signed
sum. Tighter fixed scales helped this slice substantially. Positive/negative
rails might avoid the offset but were not implemented; they would add filter
work and need their own numerical audit.

ReLU here uses native clamping. GPT-2's GELU requires another implementation;
the existing byte-table route would reintroduce an eight-bit boundary. Full
normalization, attention, twelve-layer accumulation, vocabulary decisions,
autonomous token feedback and GPU/browser surface selection remain untested.

## Recommendation and reproduction

This is positive evidence for a **carefully encoded high-precision filter
backend**, with F32 validating the actual dense computation. It is not evidence
that forcing F16 alone solves the earlier SVG accuracy failures. A custom
browser experiment would still need to preserve precision at every primitive,
implement suitable nonlinear operations, freeze ranges from an independent
calibration set, and test held-out full-model decisions. Width scaling and a
Chromium build were deliberately left outside this bounded probe.

Both immutable attempts preserve their exact source and all 15 numerical cases.

```sh
python3 tools/run_unconventional_isolated.py --label skia-real-matvec -- uv run --python 3.12 --with skia-python==144.0.post2 --with numpy python tools/probe_skia_f16_real_matvec.py --label n16-r0 --sizes 16 --rounds 3
python3 tools/run_unconventional_isolated.py --label skia-real-matvec -- uv run --python 3.12 --with skia-python==144.0.post2 --with numpy python tools/probe_skia_f16_real_matvec.py --label n16-calibrated-r1 --sizes 16 --rounds 3 --calibrated-range
```

Use new labels to repeat. Both runs used the shared experiment lock. The normal
browser/model and the earlier materialization probe were unchanged.
