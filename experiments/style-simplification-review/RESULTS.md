# Three CSS simplification experiments: results

**None of these three changes earned a replacement of the current path.**
Reading fewer saved values made the tested native handoff slower. Moving
unchanging rules outside layer selection preserved the answers but did not
produce repeatable savings. Rearranging normalization while keeping the weights
unchanged passed ordinary test inputs, but failed its numerical robustness gate.

The experiments are complete, including the planned stop before browser
implementation when the normalization screen failed. No production default
changed and no hour-long token run was launched. The completed connected MLP
experiment belongs to the other task and is documented
[separately](../native-mlp-integration/RESULTS.md).

| Proposed simplification | Numerical result | Time result | Decision |
| --- | --- | --- | --- |
| Read one saved 768-number vector instead of both | All checked values identical to baseline; 61,440 oracle coordinate checks pass | Four pairs slower; median +28.7% from first capture through the remaining 23 handoffs | Do not promote `loop-selective` |
| Move identical stage rules outside layer selection | 110,592 oracle coordinate checks pass; all 55,296 matched comparisons exactly equal | Fresh QKV approximately unchanged; fresh MLP +0.8–1.0%; aggregate style differences reverse between pairs | Do not promote `layer-hoist` |
| Remove the separately published normalized vector, retaining the exact matrix weights | All 44 natural cases pass the primary numerical model; 189 of 264 stress cases fail the relative-error gate | No browser timing: precision gate failed first | Do not implement this formula as a general replacement |

## 1. Reading fewer values did not mean doing less browser work

The default loop keeps two saved answers and reads 1,538 animated channels.
The selective version reads 770: the previous answer's 768 coordinates and two
pass stamps. But it also changes the active animation list every pass.

In four fresh-process pairs, the baseline completes the 24-pass test in
9.62–9.91 seconds. The selective version takes 11.79–13.44 seconds. Removing
startup from the comparison does not rescue it: the remaining 23 captures are
21.7–42.5% slower, with a median paired increase of 28.7%.

Both versions perform 119 style recalculations and 71 layouts over the complete
run in every pair. The selective version spends more time recalculating styles
in every pair. Its smaller active reader list therefore does not remove an
update cycle. Animation-list changes are a plausible source of extra work, but
we have not traced which internal operation accounts for the slowdown.

This uses the actual native two-bank mechanism at the model's 768-number width,
with a simple recurrent calculation. It is deliberately a handoff test, not a
matrix calculation or a complete model. The result rejects this particular
implementation; it does not prove that all selective reading must lose.

[Full handoff protocol, measurements and evidence](selective-loop/RESULTS.md).

## 2. Fewer conditional rules did not remove update cycles

The layer-rule test uses real QKV and MLP calculations for layers 0 and 11.
Only structural declarations verified identical across layers move out of the
layer conditions. Weights, numerical expressions and freshness checks retain
their original conditions. Stylesheets shrink by 3.3–4.0%.

Every candidate output equals its baseline. Fresh-input QKV medians change
from 335.55 to 334.51 ms in one process order and from 330.40 to 331.14 ms in
the other. MLP changes from 763.98 to 771.80 ms and from 760.61 to 766.37 ms.
Small aggregate reductions in style work in the first pair reverse in the
second. Style/layout update counts remain the same.

These short component tests include real matrix fonts, normalization, demand
on all outputs and generation checks. They exclude complete token generation.
Their polling floor and complete measurement boundary are recorded in the
[layer-rule report](layer-hoist/RESULTS.md). There is no observed saving that
justifies a longer integration trial for this rewrite.

## 3. Exact algebra still meets finite-precision limits

The proposed normalization change keeps the existing quantized matrix `Q`:

```
current:  Q @ (gamma * (x - mean) / sigma + beta) + bias
proposal: (Q @ (gamma*x) - mean * (Q @ gamma)) / sigma
          + Q @ beta + bias
```

Here `gamma` and `beta` are fixed per-coordinate normalization parameters;
`mean` and `sigma` come from the current input. Products with `gamma*x` are
coordinate-wise. `Q @ gamma` and `Q @ beta` can be calculated beforehand, so
the proposal still needs only one live matrix product. The intended saving is
removing a separately published 768-number normalized intermediate.

The identity is mathematically valid, and the implementation's exact and
float64 checks pass. Eighteen existing font assets were checked against the
same weight codes, axes and base widths. Requantizing the weights is not the
problem this time.

The problem is **when rounding happens**. The current path first subtracts the
mean and divides by the spread, then sends those values into the font. The
proposal sends the uncentered scaled input first. A large common offset makes
its font input range large even when the differences that matter are small.
Rounding can lose those differences before the later subtraction and division
try to recover them.

All 44 ordinary reference-derived inputs pass the primary font-coordinate
rounding model. On the 264 deliberately shifted or low-variance versions,
189 fail the relative-error gate and 40 exceed the additional 0.05 RMSE ceiling.
The worst candidate RMSE against the ideal unchanged-weight calculation is
1.68533. Alternative rounding models also expose failures; one natural input
fails only the conservative per-shard width-rounding sensitivity model.

These are **offline numerical results**, not observed browser errors. The stress
inputs are not claimed to occur in ordinary prompts. The conclusion is narrow:
this formula does not meet the predeclared robustness requirements for a general
replacement. A narrower supported domain or a precision repair would be a new
proposal, not a reinterpretation of this failed gate.

[Protocol](normalization/PROTOCOL.md) · [Detailed numerical report](normalization/RESULTS.md).

## What this changes about our direction

These experiments reduce uncertainty; they do not reduce the current measured
model time. The last saved complete 32-token run remains **3,177.132 seconds
(52.95 minutes)**. The other task's MLP report also rejects its tested replacement
and explains why a standalone segment cannot supply a new full-run forecast.

The concrete lesson from the two browser tests is that smaller CSS descriptions
do not necessarily remove browser update cycles. A further handoff experiment
should identify an entire receipt/capture/advance cycle it can eliminate while
preserving the saved values and their generation checks, or hold reader state
fixed instead of replacing it each pass. That is a research direction, not a
tested speedup. Another reduction in declaration or animation count alone is a
poor reason to launch a long benchmark.

The three new tools, source snapshots, fixture hashes, raw vectors, timing
observations, numerical rejection cases and reproduction commands are indexed
in [README.md](README.md). The normalization report preserves its dependency
and font-discovery failures. No rejected measurement was silently converted
into a passing result.
