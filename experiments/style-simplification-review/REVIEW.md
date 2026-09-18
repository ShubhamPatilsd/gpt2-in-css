# Removing work from the current CSS calculation path

Original read-only investigation and proposals, 2026-09-17 America/Los_Angeles.
The user subsequently authorized these experiments; their execution is recorded
in the [experiment index](README.md) and [combined results](RESULTS.md).
The MLP comparison belongs to another task; this review does not run or change it.

## What the review rules out as new discoveries

| Approach | Existing evidence | Consequence |
| --- | --- | --- |
| Restrict inherited input values | [Dense report](../browser-gpt2-integration/dense-report.md): normalized-input privacy preserves outputs but small timing differences are inconsistent. [Cache report](../browser-gpt2-scaling/RESULTS.md): explicit forwarding and broad resets can regress. | Do not infer less elapsed time from fewer inherited variables. |
| Pack several values in one width/height | [Preactivation transport](../preactivation-packet-transport/REPORT.md): real MLP works; carrier reduction is not a proportional speedup, and precision trades against packing. | Another radix arrangement alone is unlikely to remove the main cost. |
| Pass outputs directly between fonts | [Metric chaining](../font-metric-chain-probe/RESULTS.md): a few channels work, but the 768-output bank creates a large font/memory cost. [Cross-shard composition](../cross-shard-font-composition/RESULTS.md): HVAR output does not become another face's input axes directly. | There is no established broad-vector font-to-font bypass. |
| Keep arithmetic inside digit substitutions | [Partitioned digits](../gsub-partitioned-digits/RESULTS.md): wider correctness repaired, but the 256-input program loses badly to variable fonts. | Do not prioritize another digit compiler here. |
| Fold LayerNorm into new matrix coefficients | [HVAR fusion](../hvar-layernorm-fusion/RESULTS.md): exact algebra, worse coefficient-quantization error. SVG version also failed accuracy. | A different numerical representation is needed before retrying the same fusion. |
| Delay downstream work by a fixed timer or use broad containment | [Lifecycle study](../numeric-backend-decision/RESULTS.md), [connected MLP](../avar2-gelu-linear-hvar-full-mlp/CONNECTED_RESULTS.md): rearming/delay and containment did not supply the desired gain. | Do not replace a freshness dependency with a guessed delay. |

These findings concern the named implementations. A repository search is not a
proof that every historical branch or mathematical rearrangement was tested.

## First bounded test: read only the required feedback vector

The current loop stores alternating results in two banks. One supplies the
previous layer's 768 values while the other receives the current layer's result.
The default reader attaches animations to both full vectors plus both stamps:
`2*(768+1) = 1,538` animated channels. It only needs the previous vector, its
stamp, and the current bank's acknowledgement stamp: `768+2 = 770` channels.

The selective branch already exists in
[loop_parts](../../tools/probe_native_reused_loop.py), and the independent
`loop-selective` switch exists in
[dense_compile_variant](../../tools/browser_gpt2_dense_locality.py).
The [source review](../browser-gpt2-integration/profiling/source-review.md)
identifies browser validation as pending. This is an unmeasured existing option,
not a new invention or a claim of halving token time.

Test the actual 768-wide native loop at multiple consecutive passes with both
variants, the same arithmetic, alternating/revisited inputs, and current stamps.
Retain both readiness and acknowledgement checks. Verify every retained vector
and no stale or mixed-generation input before timing. Measure complete handoff
latency and renderer work in fresh AB/BA processes. Switching animation lists
could erase the benefit or alter lifecycle behavior; that is a reason to test.
Stop if either direction loses correctness or no repeatable saving appears.

## Related bounded test: keep invariant stage rules outside layer selection

The compiler wraps structural timeline/animation/container declarations inside
each layer's conditional rule alongside actual layer-dependent values. The
existing `layer-hoist` option extracts only declarations whose values are
verified identical across layers. This can simplify layer selection without
changing weights or numerical expressions. It is also unmeasured in the reviewed
report. Test it independently from selective reads. Chrome may already avoid
much of the apparent duplicated work; a smaller stylesheet is not sufficient.

## Different algebraic proposal: keep the matrix weights unchanged

Target the explicit normalized 768-value intermediate, not the matrix product.
Let `Q` be the exact reconstructed quantized matrix currently represented by the
existing fonts. For a residual vector `x`, LayerNorm uses fixed coordinate gains
`gamma` and offsets `beta`, the live mean `mu`, and
`sigma = sqrt(mean((x-mu)^2)+epsilon)`.

The current mathematical target is:

```
normalized = gamma * (x-mu) / sigma + beta
y = Q @ normalized + b
```

An equivalent arrangement is:

```
z = gamma * x                 # per-input scaling in font-axis expressions
C = Q @ gamma                # constant, calculated offline
D = Q @ beta + b             # constant, calculated offline
y = (Q @ z - mu*C) / sigma + D
```

Every multiplication with `gamma` is coordinate-wise except the explicitly
written matrix products. `C` and `D` are fixed output-coordinate constants;
there is no runtime second matrix product. The same font bank can evaluate
`Q @ z`. Its existing output-decode expression can incorporate the centering,
division, and offset. The live range factor can be combined with `1/sigma`
once as a shared scalar.

This does not construct or requantize `Q diag(gamma)` or centered matrix rows,
which is where the earlier fusion changed the weight representation. It still
needs 768 axis values and the mean/variance reductions. The prospective saving
is eliminating the 768 separately published normalized properties and their
mean/variance-dependent expressions. Some scalar arithmetic moves to the
2,304 QKV or 3,072 FC output expressions, so less work is NOT guaranteed.

This is an existing kind of algebraic rearrangement, not new mathematics.
Related normalization/weight rearrangements are studied in
[Outlier Suppression](https://arxiv.org/abs/2209.13325); that paper is not evidence
that this particular CSS representation is faster or accurate. I did not find
a measured preserved-weight form in the reviewed reports and source search.

### Precision is the first rejection gate

Keeping weight codes fixed does not keep browser numerics identical. The new
axis vector has a different range and is rounded at different points. Subtracting
`mu*C` after the dot product may cause severe cancellation. Large common offsets
and small variance are especially important stress cases: ideal LayerNorm is
shift invariant, while finite-precision `Q @ z - mu*C` need not be.

Before building any page, emulate the existing HVAR coordinate rounding and
output scaling on saved real states from early, middle and late layers. Compare
with both the current quantized path and the full-precision reference. Include
shifted copies and small-variance inputs within the declared supported domain;
record clipping and maximum errors, not only mean error. Use the actual backend
range behavior. Stop if the rearrangement worsens the accepted numerical budget.

If it passes, build only one real LN-to-QKV or LN-to-FC comparison with the
existing font assets and the same output consumer. Include all corrected outputs
in the demand, changing inputs, native freshness, separate correctness/timing,
and repeated matched processes. Require complete-boundary latency improvement;
fewer properties alone does not qualify. Do not run twelve layers to decide
whether the first stage wins.

## Priority

First test the selective feedback reader: its removable work is concrete, its
implementation exists, and it changes no numerical representation. Independently
screen the preserved-weight normalization algebra offline. Consider the layer
invariant-rule test as another small existing option. No full-model speedup is
predicted. This paragraph records the proposal before execution; follow the
experiment index above for the subsequent results.
