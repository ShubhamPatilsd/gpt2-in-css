# Preserved-weight normalization: numerical rejection screen

Declared before calculating candidate results on 2026-09-18 UTC. This is an
offline rejection gate, not a browser benchmark or a model-quality certificate.

## Question and unchanged contract

With exactly the existing row-q9 matrix `Q`, compare:

```
baseline:  Q @ (gamma * (x - mean(x)) / sigma + beta) + bias
candidate: (Q @ (gamma*x) - mean(x) * (Q @ gamma)) / sigma
           + Q @ beta + bias
sigma = sqrt(mean((x-mean(x))**2) + 1e-5)
```

The candidate never requantizes `Q`, alters its codes, or builds a font. Record
hashes of the codes/scales/reconstructed weights and the actual existing font
assets where available. First verify equality in float64 before imposing font
precision. Floating-point agreement is a check of this implementation, not a
proof of exact algebra (the displayed identity follows by distributivity).

## Cases fixed before execution

- Saved existing real reference-derived dense-stage inputs for layers 0 and 11,
  token positions 0 and 1 of token sequence `[15496, 11]`, for LN1→QKV and LN2→FC.
- Save additional reference-derived activations from the existing quantized
  twelve-layer model for prompts `The quick brown fox`,
  `Paris is the capital of`, and `CSS can perform matrix multiplication`.
  Retain positions 0 and the final prompt position at layers 0, 5, 11 for both
  boundaries. These are genuine checkpoint computations but are not captured
  native-browser vectors.
- For every distinct base vector, retain the natural input, add common offsets
  of ±8 and ±64 times its original standard deviation, and test low-variance
  inputs `mean(x) + .001*(x-mean(x))`, with and without a further common shift of
  eight original standard deviations. These synthetic stress cases exercise
  LayerNorm's shift invariance and low-variance behavior; they are not claimed
  to occur in ordinary prompts.
- All finite inputs use the current dynamic range:
  `R = 1.001 * max(1e-6, max(abs(font_input)))`; no clipping is intended.

## Numeric models and limitations

Use row codes and row scales from `quantize_float_rows(..., bits=9)`, 256-input
shards, current 512 px font size / 1,000 units per em, and CSS constants rounded
to the same nine-decimal format. Compare both paths with the same original
float-weight stage target and the unchanged ideal-q9 stage target.

The primary coordinate model floors normalized values to the F2DOT14 grid,
consistent with the repository's existing Chrome coordinate-dither study.
Also report nearest-grid sensitivity; it is not permission to choose whichever
rounding mode makes the candidate look best. Report both coordinate-only sums
and additional nearest/floor 1/64-pixel per-shard advance quantization. Those
advance variants are sensitivity models, **not a claim that every native font
advance and timeline operation has been reproduced exactly**. CSS internal
float conversion, timeline sampling/reciprocal decoding, and browser-specific
glyph rounding remain unmodeled. A pass would still require native validation.

## Predeclared rejection conditions

1. Float64 identity must have maximum error ≤1e-9 on every finite case. No code
   or matrix hash may change between paths; no axis may clip.
2. Under the primary coordinate-only model, on **each** natural and stress
   vector, candidate error against the original float-weight stage must not
   exceed `1.10 * baseline_error + 1e-5` for either RMSE or maximum error.
   Ten percent is this screen's conservative allowance; it is not a previously
   established full-model quality budget.
3. Candidate error versus the ideal-q9 stage must have RMSE <0.05. This ceiling
   is the existing native dense-stage QKV gate; extending it to FC preactivations
   here is an additional rejection safeguard, not an established FC budget.
4. A sensitivity-model failure prevents claiming robust eligibility for a
   browser implementation. Separate natural versus synthetic failures, and do
   not label sensitivity output as a browser observation.

Failure stops this candidate before browser implementation. Passing all gates
only authorizes proposing one connected native boundary test; it predicts no
speedup. Preserve the protocol, source snapshot, every case result, and saved
inputs. Serialize heavy calculations using the repository's common experiment
lock and single-thread BLAS settings. No token generation or large font build.
