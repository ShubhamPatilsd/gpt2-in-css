# Unconventional execution experiments

Date: 2026-09-17. Follow-up to [the research shortlist](UNCONVENTIONAL_OPTIONS.md).
These are measured feasibility gates, not a new full-model throughput result.
The existing full-model compiler is not changed by these probes. Three browser
implementations were built, including a successful glyph arithmetic circuit;
offline learned-code and standalone-Skia tests assess the two directions that
change the model or browser.

The clearest speed result is a small glyph circuit at **sixteen connected steps**:
7.0 ms versus 10.2 ms for direct CSS with unique text, about **31% less elapsed
time**, including native input encoding and required numeric output readback.
An independent audit rejected an earlier apparent eight-step win against a CSS
control with an avoidable geometry round trip; the final comparison removes it.
This is a two-coordinate discrete-state circuit, not a GPT-2 layer.
Fused attention loses, alpha circuits fail to scale, and the
tested learned codes fail their accuracy gate. Higher-precision Skia establishes
numerical prerequisites but has no Chromium/token-speed result.

## Experimental contract

- Test changing inputs through useful downstream consumers, including required
  publication and final readback. An isolated font or filter timing is not token speed.
- Browser pages contain no inference JavaScript. External harnesses can supply
  inputs, observe widths/pixels, time the operation and compare with an oracle.
- Numerical tests precede performance claims. Font rejection, fallback rendering,
  clipping, missing outputs and timeouts remain failures, even if fast.
- Browser runs and large builds cooperate on a single advisory lock through
  `tools/run_unconventional_isolated.py`. This prevents these experiments from
  competing with each other, but does not remove normal machine activity.
- Three agents independently implement attention fusion, glyph arithmetic and
  alpha-pixel circuits. The coordinating agent tests learned activation codes and
  the Skia precision premise, then reviews their scope and evidence.
- Model and browser changes are confined to separate feasibility tests. No new
  checkpoint or custom browser becomes the default pipeline.

## Evidence by direction

### Fused attention inside a font

[Full report](../fused-attention-font-probe/RESULTS.md).
One 64-dimensional head with four cached tokens returns all final normalized
outputs. Real held-out inputs and explicit range failures are included.

| Exponential approximation | Fused query update | Matched complete CSS | Outcome |
|---|---:|---:|---|
| 64 segments | 9.594 ms | 1.825 ms | 5.26× slower |
| 16 segments | 7.721 ms | 1.953 ms | 3.95× slower |

Reducing HVAR regions from 8,384 to 2,192 improves performance but does not win.
The smaller font's supported cases have maximum coordinate error 0.00456;
its fresh changes average 2.08 ms of style work and 4.50 ms of layout. A real
layer-11 sample clips under layer-0 calibration and reaches 0.64025 maximum
error. Each layer would need separate range validation. Seven measured rounds
follow a warmup, with CSS/fused order alternating.

**Decision:** stop this implementation before integration. Removing intermediate
scores added more font/layout work than the CSS calculations it replaced. Failed
font loads and broken readers are retained and excluded from valid timings.

### Arithmetic through glyph substitutions

[Full report](../gsub-arithmetic-probe/RESULTS.md).
Both direct text and native CSS counters pass all 65,536 byte additions, all
65,536 addition-plus-nonlinearity cases and all 256 small-network inputs exactly.
An actual native numeric output receiver also passes. The font is 7,508 WOFF2
bytes with 1,635 glyphs and 13 lookups.

For 256 independent changing outputs, including CSS input encoding and native
numeric output readback:

| Operation | GSUB | Matched CSS with same output boundary |
|---|---:|---:|
| Addition | 5.0 ms | 2.5 ms |
| Addition + nonlinear | 4.9 ms | 2.7 ms |
| Tiny two-layer network | 3.4 ms | 3.1 ms |

Prepared-character timings were better, but omit the input-encoding cost. The
complete paths above do not show a speedup. Intermediate glyph identities do
remain within shaping, so a bounded depth-amortization follow-up is justified.
The tiny network has two inputs per neuron and uses joint-state lookup tables;
it is not a general dense-neural circuit compiler.

The [completed depth follow-up](../gsub-arithmetic-depth-probe/RESULTS.md) keeps
two coordinate glyphs between successive reversible nonlinear cells. Each layer
performs its own pair substitution and expansion; disabling any layer prevents
final readout. Reversibility keeps all 256 input states distinct, avoiding an
apparent win from saturating all outputs to a constant.

The **initial matched-reader sweep** measured milliseconds for 256 changing
outputs with the same geometry reader on both backends:

| Connected steps | GSUB, repeated state | CSS, repeated state | GSUB, unique text | CSS, unique text |
|---|---:|---:|---:|---:|
| 1 | 5.7 | 4.5 | 5.9 | 4.8 |
| 2 | 5.7 | 5.3 | 6.0 | 5.3 |
| 4 | 5.8 | 6.5 | 6.1 | 6.3 |
| 8 | 6.2 | 8.2 | 6.3 | 8.5 |

Every depth passes all 256 states, and all 163,840 timed outputs are exact.
The unique-text diagnostic changes a zero-advance nonce to prevent simply
reusing an identical whole text string. It is not instrumentation of every
internal shaping cache. At depth eight the font has 2,658 glyphs, 17 lookups and
8,656 WOFF2 bytes. Thirty-five samples follow five warmups; backend order
alternates. This is one bounded sweep, not an across-machine repeatability claim.

**Independent review qualification:** the numeric CSS control has its final
coordinates available before being forced through width→anchor→container→number.
That return path is necessary for glyph computation and avoidable for CSS.
The table above is valid for the stated matched reader; it does not establish
that GSUB beats direct CSS. The original artifacts are archived, and the corrected
control consumes its final CSS numbers directly.

**Corrected direct-CSS results**, including each backend's necessary transfers:

| Connected steps | GSUB, repeated state | Direct CSS, repeated state | GSUB, unique text | Direct CSS, unique phase |
|---|---:|---:|---:|---:|
| 1 | 5.6 ms | 2.5 ms | 5.9 ms | 2.6 ms |
| 2 | 5.9 ms | 3.1 ms | 6.2 ms | 3.1 ms |
| 4 | 6.0 ms | 4.2 ms | 6.3 ms | 4.3 ms |
| 8 | 6.1 ms | 6.2 ms | 6.8 ms | 6.3 ms |
| 16 | 6.5 ms | 10.2 ms | 7.0 ms | 10.2 ms |

Eight steps have no reliable advantage: repeated-state results tie and unique
text is slower. Because GSUB's depth cost grows more slowly, a single final
extension tests sixteen steps in a separate fresh browser. It passes all 256
states, all sixteen disabled-layer controls and all 61,440 timed output checks.
The direct-CSS comparison now favors GSUB in both phases (31–36% less elapsed
time). The font has 4,962 glyphs, 33 lookups and 13,868 WOFF2 bytes. See the
[sixteen-step measurement](../gsub-arithmetic-depth-probe/depth16/results.json).
These are bounded within-run medians, not cross-run confidence intervals.

**Decision:** retain glyph execution as the most promising unmodified-browser
mechanism from this batch. Depth can amortize its conversion cost, including
against a direct numeric CSS control. The next gate is widening the computation
with reusable arithmetic circuits; joint-state tables over hundreds of inputs
would grow exponentially. This control uses a reversible digital cell, not
actual GPT-2 matmuls or GELU, and does not speed up the current model by itself.

### Alpha-pixel digital circuits

[Full report](../svg-alpha-circuit-probe/RESULTS.md).
Thirty-four changing-input arithmetic trials pass exactly, with zero measured
style recalculations. Eight parallel addition/cancellation cases scale as follows:

| Word width | Changed-input plus screenshot median |
|---|---:|
| 8 bits | 82.3 ms |
| 16 bits | 414.8 ms |
| 32 bits | 2,755.9 ms |

Cached capture overhead is about 67 ms and is not subtracted as an estimate of
pure computation. A parallel-prefix carry variant is slower at 8/16 bits and
times out at 32. The four-wide matvec→ReLU→matvec times out; the two-wide version
paints no valid output. Independent graph interpretation passes, so the browser
failure remains unresolved rather than being labeled a mathematical impossibility.

**Decision:** stop this generated architecture before scaling. This directly
demonstrates that eliminating measured style work does not ensure fast execution.

### Learned glyph-code interfaces

Completed [centroid screen](../learned-glyph-code-screen/RESULTS.md) learns six
configurations on isolated real GPT-2 block-0 contextual activations. The target
is the full 768→3072 FC, GELU and 3072→768 projection. It evaluates local-text and
random-token contexts separately as well as together. The best candidate selected
on validation data has 36.21% relative RMS error at the held-out MLP output.
[Supervised table distillation](../learned-glyph-code-screen/DISTILLATION.md)
improves that only to 35.82%, far above the declared 5% screening threshold.
Train/validation/test context hashes and local-text sources are isolated.

**Decision:** these modest learned codes are not ready for browser compilation.
This rejects the tested configurations, not larger-scale end-to-end training or
models that directly emit codes. Browser encoding and lookup costs are unmeasured.
There are no next-token quality or model-speed results from this screen.

### Higher-precision filter storage

The [standalone Skia probe](../skia-f16-materialization-probe/RESULTS.md) tests the numerical
premise directly using explicitly materialized raster surfaces. It is not a
Chromium patch, SVG integration or GPU performance measurement. RGBA8, RGBA16F
and RGBA32F are compared, including independent byte-table and single-RGBA8
barriers. Full intermediate format/value observations are required; a later
residual can restore distinctions that an earlier computation lost.

The ramp fixture carries 64 distinguishable near-zero values through every stage
with F16; RGBA8 collapses them to one. The same spacing around 0.5 collapses to
three F16 levels. F32 retains all 64 at both offsets. A single byte table or
RGBA8 surface destroys precision in the main branch. Permuted inputs additionally
test a nontrivial spatial reduction; the F32 oracle assertion passes throughout.

**Decision:** a useful precision prerequisite passed, with clear numeric limits.
It does not prove that requesting F16 in Chromium fixes its entire filter path.
These CPU timings include fixture/oracle work and are not browser performance
evidence.

The [real-weight follow-up](../skia-f16-real-matvec/RESULTS.md) then executes a
16→16→16 FC→ReLU→projection slice through actual Skia filters. The matrices and
inputs come from GPT-2, but ReLU replaces GELU for this structural precision
test. Intermediate geometry feeds the next operation without NumPy calculating
its inputs. Conservative ranges initially cause large F16 error. A single tighter
fixed range, calibrated on two inputs, substantially improves it.

For a third real input not used to set that range, with zero clipping:

| Materialized format | Final output RMSE |
|---|---:|
| RGBA8 | 0.0347972 |
| RGBA16F | 0.00170061 |
| RGBA32F | 0.00000045445 |

F16 reduces this error about 20.5× versus RGBA8, but still has 2.46% relative
RMS error. These are precision results, not a 20.5× speedup. The fixed range has
only one held-out input check. Neither original GPT-2 decision quality nor GPU
execution is established. Width scaling stops at this gate; sixteen dimensions
do not predict full 768/3072-wide errors or costs.

**Updated decision:** retain a carefully encoded floating-point filter backend
as the most promising custom-browser direction. Precision and range handling
must be designed together; F16 alone is not an accuracy guarantee.

## What to carry forward

1. **Stock-browser track:** widen the successful glyph circuit using composable
   arithmetic while retaining its internal state and complete boundary costs.
   Depth has a measured crossover at sixteen steps versus direct CSS; large
   fan-in does not yet have a solution.
2. **Custom-browser track:** instrument actual filter intermediate formats and
   preserve the real-weight slice's numeric behavior through Chromium's SVG path.
   Standalone Skia does not establish that integration. Validate real GELU,
   normalization, larger reductions and native token feedback before token claims.
3. Stop the present fused-attention and alpha-bit backends, and the tested small
   activation-code configurations. Their observed failures are recorded above;
   they are not promoted simply because they remove CSS intermediates.

## Full-model interpretation

No token throughput number can be inferred by adding or dividing these small
component timings. Any eventual integration must preserve native feedback and
generation correctness, then repeat a matched full 12-layer run. The prior
valid two-token 12-layer owned-attention measurement remains 99.487 seconds;
these probes do not update it.
