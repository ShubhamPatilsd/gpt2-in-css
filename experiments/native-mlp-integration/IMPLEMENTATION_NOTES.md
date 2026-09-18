# What this fixture connects

`tools/build_native_mlp_integration.py` builds four pages: the current native
MLP and the avar2 MLP, each for GPT-2 layers 0 and 1. No production core file is
modified. Every page calculates this complete segment in the browser:

```text
768 post-attention residual coordinates
  → the layer's real LN2
  → 768 → 3,072 FC
  → GELU
  → 3,072 → 768 projection
  → projection bias + the input residual
  → the next layer's real LN1
  → a scalar that depends on all 768 normalized coordinates
```

The external harness selects a raw residual fixture and advances the generation.
It supplies no normalized inputs, hidden activations, matrix products, block
outputs, or next-layer outputs to the page. Those arrays exist in the manifest
only as independent numerical oracles. Author scripts are prohibited by CSP and
the browser context disables author JavaScript.

## Inputs and arithmetic

The four inputs are post-attention residuals from tokens `[15496, 995, 11, 314]`
at positions 0–3 of one quantized GPT-2 trajectory. The builder calculates real
causal multi-token attention to obtain these boundary fixtures. Attention itself
is **outside** the browser segment being timed. Layer 1 fixtures come from the
baseline mathematical trajectory; they are not produced by the candidate page.

Both backends use the same signed 9-bit row-quantized FC weights, the same LN2
coefficients, residual inputs, projection biases, and next-layer LN1 coefficients.
They use the same dynamic FC input range as the current core:
`1.001 × max(0.000001, maximum absolute input coordinate)`.

Their later arithmetic differs. The baseline computes the exact GELU expression
in CSS and uses signed 9-bit row-quantized projection weights. The candidate uses
the existing piecewise GELU map in avar2 and the existing linear HVAR projection
fonts. Therefore each backend has its own mathematical oracle. A third target
uses the shared quantized FC, exact GELU, and float projection, making their
different approximation errors visible. This common target is not a full
unquantized GPT-2 oracle.

The candidate reuses 13 existing projection groups: two groups of 238 hidden
coordinates and eleven of 236. Layer 0's preactivation scale is 12.5; layer 1's
is 19. These are existing font limits, not an input-independent guarantee for
arbitrary prompts. The builder rejects these fixtures if a preactivation exceeds
the corresponding limit.

## How closely the baseline matches the native core

Both baseline stages call the same `build_hybrid_twelve_block.matvec` function
as `browser_gpt2_reused_core.compile_reused`, with `compact=True`, `gated=True`,
`dynamic_range=True`, and chunk size 512. The same native view timelines carry
the numerical results, and the same generation markers control the FC and
projection gates. LayerNorm uses the same `norm_declarations` function.

The fixture is still a **segment replay**. It does not contain layer selection,
all twelve layers' styles, K/V banks, attention, the vocabulary head, embedding,
or token feedback. It also exposes extra final diagnostic widths. Resident
memory and invalidation scope therefore differ from the full reused core.

## The candidate's boundary

The candidate uses the current row-base FC font assets, with geometry decoding
instead of the baseline's FC view-timeline decoding. Each projection group
receives the FC preactivations through paired width/height containers. The
projection fonts apply avar2 GELU and produce 768 group contributions. Anchors
sum all thirteen contributions and add the residual and projection bias.

A 384-level paired-container chain turns all 768 completed widths back into
typed `--out-*` CSS numbers. The next real LayerNorm consumes those numbers.
This final consumer is essential: simply reading the MLP's rendered widths would
omit the numerical handoff needed by the model.

The group trees and final state-capture tree are siblings, keeping the maximum
DOM depth within the previously established browser limit.

## Completion and startup

The baseline terminal sits inside both native generation gates. Its height is
`64 × epoch`, and its width is a weighted sum of all next-LayerNorm coordinates.
The candidate has no timeline stage gates: its geometry dependency graph is
synchronous, so forcing the terminal width also forces its upstream calculations.
Its terminal height alone is not proof that the arithmetic is fresh.

For both pages, the harness checks all 768 state coordinates and all 768
next-LayerNorm coordinates after the timed terminal read. It then checks that the
terminal did not change while those coordinates were read. Changing inputs and
revisiting earlier cases test freshness. The final scalar also depends on all
coordinates through LayerNorm's mean and variance.

The production runtime has a native font-loading barrier. This fixture instead
uses external font preloading and verification during harness setup, before
timed mutations. Navigation, font setup, and warm updates are recorded separately.
This difference must not be hidden in a cold-start comparison.

The first smoke observer waited for `requestAnimationFrame` inside a context with
author JavaScript disabled and did not return. The corrected observer polls
externally, leaving the page's calculations native. Both attempts are retained.

## What existed before this work

`avar2-gelu-linear-hvar-full-mlp/CONNECTED_RESULTS.md` already documented live
LayerNorm, residual, next-LayerNorm, and two-block avar2 connections. This work
does not newly prove those capabilities. It adds a controlled replay comparison
against the **current native core's own MLP stages**, using identical boundary
inputs, repeated generations, current completion semantics, and separate
mathematical oracles.

Passing this segment test cannot establish a new twelve-layer token time or
prove that these early layers represent later layers. Full-token estimates must
keep unmeasured work explicit and be labeled conditional.

## Numerical gate revision

The first strict gate required maximum state error at most 0.1 and maximum
next-LayerNorm error at most 0.01. Layer 1 failed the state condition in both
backends, despite passing the downstream condition. Those failures remain in
the raw reports. We have not fixed or fully explained the absolute discrepancy.
An independent simulation of normalized font-axis rounding alone did not
account for it.

For the bounded diagnostic timing comparison, policy v2 uses the existing native
core's independent acceptance criterion: finite state coordinates and state RMSE
strictly below 0.05, as in `tools/test_browser_gpt2_reused_core.py`. It also retains
the maximum next-LayerNorm error condition of 0.01. All maximum errors remain
reported. The original 0.1 absolute condition is not presented as passing.

`manifest-strict-absolute-v1.json` preserves the prior policy. Comparing it with
the amended manifest verified that all HTML hashes, font hashes, raw inputs,
oracle arrays, cases and readouts were unchanged. Only the gate policy and
builder source hash changed. The revised gate is sufficient for a diagnostic
comparison under the existing native tolerance, not proof of full-model quality.
