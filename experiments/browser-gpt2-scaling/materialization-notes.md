# What the QKV “materialize” ablation changes—and leaves connected

This is a bounded source inspection of the existing generated native baseline
and materialize pages, informed by their saved measurements. No new browser run
or native trace was performed for this note. Chromium explanations below are
hypotheses, not trace findings.

The main finding is that **the ablation does not add a new materialization step**.
The baseline already computes the query and live K/V axis lists and their scales
on `.fvs-query`. The ablation adds one rule that resets the 2,304 raw QKV custom
properties on the first bank below that element. It narrows the lifetime of those
raw values in one branch, but it does not turn that branch into an independently
committed computation.

## Exact generated-page difference

Compared the existing artifacts:

- [Native baseline, 12 layers / 2 tokens](native/baseline-b12-c2-r0/runtime.css).
- [Native materialize, 12 layers / 2 tokens](native/materialize-b12-c2-r0/runtime.css).

Their `index.html` files are byte-identical. Both have SHA-256
`453ca3ca0ee314df3f7efecfc9fe6690e5f84a3eb156e888615a73995567b253`.
Their CSS becomes identical after deleting the materialize page's single
**42,797-byte rule**, containing exactly **2,304 reset declarations**:

```css
.fvs-query > .fvs-bank {
  --qkv-000: initial;
  --qkv-001: initial;
  /* … every raw Q, K, and V coordinate … */
  --qkv-2303: initial;
}
```

The actual emitted rule is minified. Its selector matches only the first of the
twelve nested font banks: `.fvs-bank-0`. Descendants inherit its reset values.
The existing raw QKV registrations remain inherited numeric properties with
`initial-value:0`; no registration is removed or made private by this ablation.
Replacing a value with zero does not establish that its property entry or any
particular allocation has been removed from Chromium's internal style state.

The transformation is defined in
[`browser_gpt2_scaling_variants.py`](../../tools/browser_gpt2_scaling_variants.py).
There are no extra head wrappers, no removed nodes, no new registers, no changed
receipt or timeline scopes, and no changed font-axis formulas. Accordingly, this
test should be described as **resetting raw QKV at the first attention bank**,
not as newly computing the axis lists once or adding stage fusion.

## Does the 2,304-field lifetime boundary actually end dependencies?

There are three different questions here.

**Raw numeric values inside the bank branch:** the emitted CSS resets them to
their registered initial values. In the inspected 268,549-character attention
CSS region before the reset rule, all **4,608 `var(--qkv-…)` references** occur in
declarations on `.fvs-query`, before the reset. They feed per-head maxima/scales
and normalized axis lists. No raw-QKV consumer was found inside the subsequent
font-bank/score/value region. The passing numerical checks support that this
boundary preserves the attention inputs on the measured sequence.

**Mathematical dependence on new QKV:** that remains. Twelve query axis lists,
twelve query scales, twenty-four live K/V axis lists, and twenty-four live K/V
scales—72 derived properties—are still produced upstream and made available to
the banks and score/value consumers. New queries must change scores; active-slot
K/V writes must change storage. Moving the source information into fewer,
structured properties does not make these inputs constant.

**Browser invalidation dependencies:** the source reset does not establish their
absence. The `.fvs-query` ancestor still changes; derived properties still change;
bank selection still depends on the current layer; source and receipt stamps still
depend on the pass; the common score reader still serves every head. Whether
Chromium can skip descendants after a particular inherited value is shadowed is
an engine behavior to measure. We cannot infer zero style work from the reset or
infer physical copying of all 2,304 values from inheritance alone.

The original nested bank structure is unchanged:

```text
shared QKV numeric consumers / QKV receipt / QKV gate
├─ fvs-query                         raw QKV → existing axis lists/scales
│  └─ bank 0                         only new reset rule
│     └─ bank 1 … bank 11
│        ├─ shared score source
│        └─ shared score reader / receipt / gate / softmax / value source
└─ context bridge receiver / gate
   └─ attention projection / LN2 / FC / projection
```

This sibling layout follows
[`compile_reused`](../../tools/browser_gpt2_reused_core.py), where the mix layout
is `mix_source + ctx_receiver`, and is visible in both generated HTML files.
The reset is inside the font-bank branch. It does **not** clear raw QKV along the
sibling context receiver and subsequent dense-stage ancestry. The native manifest
also has `liveness:false`; this is not the separate general dead-vector cleanup.

## Why a native layer loop is a different workload

At the start of this review, the available materialize component comparisons used
**one layer**: capacity 4 with four populated positions, and capacity 32 with four
populated positions. The absence of a matched twelve-layer materialize component
motivated the follow-up reported below. That follow-up has now passed and remained
nearly neutral under layer switching; it does not reproduce the native regression.

Component inputs are delivered as one externally supplied QKV vector through
the harness. The native graph instead computes its 2,304 QKV coordinates through
five nested `.shared-qkv-c0` … `.shared-qkv-c4` numeric-consumer elements, followed
by a QKV receipt and gate. Each native layer also selects different dense font
weights and normalization constants. The enclosing controller and pass machinery
remain present inside the same reused core.

The font-cache selection code is also unchanged: each selected layer exposes
inherited `--fr-*` aliases from its private `--fc-*` bank, and the entire attention
graph remains nested below all twelve banks. Clearing raw QKV does not prevent
these layer-dependent aliases from changing when the selected layer changes. It
does not preserve one layer's rendered V geometry across use of another layer.

Verified structural differences between the two workloads therefore include
upstream dense computation and its numeric-consumer ancestry, receipt/gate
transitions, repeated layer selection, and the rest of the dense model. Possible
differences in the number of intermediate style/layout updates are unmeasured.
In particular, this inspection does not show that the native graph exposes
partial QKV vectors or violates its receipt protocol.

## What the existing numbers say

These native runs are one short sequence per variant, with two generated tokens.
The second-token interval is not an exclusive attention or layer-switch timing.

| Native variant | Total seconds | Second-token interval seconds |
| --- | ---: | ---: |
| Baseline | 82.729 | 37.907 |
| Materialize | 87.239 | 46.183 |
| Width reuse | 70.09 | 31.43 |
| Lean combination | 91.97 | 47.43 |

Materialize took about 4.51 seconds more overall and 8.28 seconds more in the
second-token interval. Its first observed token was earlier: 41.047 versus
44.813 seconds. That mixed result reinforces the need to separate startup and
steady computation and to repeat a matched comparison before assigning a stable
regression magnitude.

Saved warm renderer-task proportions were 50.99% style and 14.99% layout for
baseline, versus 60.05% style and 11.46% layout for materialize. Proportions alone
are not absolute durations and do not localize the work to the reset rule.
Sampled peak renderer RSS was approximately 3,421 versus 3,228 MiB. This single
comparison is consistent with a possible memory/time tradeoff, but does not prove
one or identify its mechanism.

The capacity-32, one-layer sparse component's per-run mean append style times
were 104.656/101.959 ms for baseline and 103.430/104.558 ms for materialize.
Query-only mean style times were 109.564/104.664 versus 106.424/105.837 ms.
Those are nearly neutral in renderer style work. Their wall times include
completion polling and should not be used alone to claim an equivalent change in
engine work. These inputs also populate only four of the allocated 32 slots.

The combined lean result cannot isolate materialization: it also changes V-width
reuse, empty-slot work, and internal timeline scope. Its slowdown does not prove
that this reset rule caused the whole combination to regress.

## Unmeasured explanations worth distinguishing

1. **Extra reset/cascade work without enough downstream savings.** Explicitly
   applying 2,304 declarations may cost more than the raw inherited values cost
   when existing engine optimizations share or skip them. A source rule cannot
   reveal that balance. The hypothesis predicts a relationship between reset
   count and style cost, even with unchanged materialized inputs.
2. **The real changing inputs still invalidate the same shared branch.** Derived
   query/cache aliases and pass/layer controls remain. If those already cause the
   relevant descendants to update, removing the raw names may save little
   additional work. The hypothesis predicts little reduction in affected-element
   counts despite lower raw-value exposure.
3. **Interaction with native stage/gate lifetimes.** Repeated upstream stage
   activation or layer-specific styles could make the boundary more expensive in
   a reused native core than in a flat one-layer fixture. More frequent rebuilding
   of style state is one possible explanation, but no native trace here proves
   it. A layer-switch-only test and a whole-core trace can separate this from
   straightforward declaration count.
4. **One-run variability or memory pressure.** Startup differs in the opposite
   direction, RSS differs, and the native sample is small. A stable regression
   cannot be established from these two timings alone. Repeat ordering must be
   counterbalanced and host workloads excluded.

## Smallest useful falsification experiments

**Completed follow-up: the matched layer-switch comparison.** The proposed test
was to run baseline and
materialize attention components with twelve native banks, capacity 4, four
positions, and one query-update round across all twelve layers: 48 append samples
followed by 12 query-plus-layer-switch samples. This matches the existing baseline
component case. Hold the fixture sequence identical,
alternate run order, validate every layer's retained K/V, and collect style/layout
metrics. Compare that with an otherwise matched one-layer case. A regression
already present in the twelve-bank component would narrow the issue before
involving the dense QKV producer or vocabulary head.

That matching follow-up is now complete:
[`materialize-c4-l12-p4-r0`](runs/materialize-c4-l12-p4-r0/results.json). All nine
relevant source hashes matched the baseline before execution, as recorded in its
[source preflight](runs/materialize-c4-l12-p4-r0/source-preflight.json). All 60
context checks and the separate trace passed. Append median latency was 350.81 ms
versus baseline 356.95 ms; query-plus-layer-switch median was 376.69 versus
381.10 ms. Mean append style time was 57.30 versus 58.40 ms, and mean switch style
time was 68.59 versus 68.24 ms.

This later component run was nearly neutral: **the twelve-bank fixture did not
reproduce the native regression**. It narrows the evidence, but does not identify
upstream dense computation, gates, or any other unmeasured native mechanism as
the cause. This is one later matching run, without counterbalanced repetitions;
it does not establish a precise effect size. It also cannot distinguish an
interaction with the complete native graph or scheduler from variability in the
single native run per variant.

**Second, split data changes from layer selection.** At a fixed populated
position, compare a constant-QKV layer A → B → A selection sequence with changes
to QKV while the selected layer stays fixed. Use distinct stored K/V per layer,
verify outputs, and trace affected style elements and font-shaping events
separately. This distinguishes cache-alias/selector churn from the raw input
boundary. It still does not substitute for the final all-layer token run.

**Third, vary the amount of resetting without changing arithmetic.** Use reset
counts 0, 192, 768, and 2,304 at the same first-bank boundary; all raw consumers
already precede it. The 192-field case can cover one head's Q/K/V coordinates.
Keep page structure and aliases fixed, and verify numerical identity. Add a
control that resets the same number of registered, unused properties already
held at their initial values. If both slopes match, explicit style-state handling
is a stronger suspect; if only live-field resets differ, inherited-value
invalidation is more likely involved. Neither outcome by itself identifies a
specific internal Chromium cache algorithm.

**Finally, compare an actual native commit boundary.** The
[native local input-register probe](native-local-commits.md) proves that a
receiver can keep the correct query while its upstream source changes. It does
not measure the total cost of that isolation. Use that mechanism as a separate
ablation which freezes only the head inputs after their QKV receipt, and include
the new bridge/register cost. Resetting names and committing finished inputs are
different interventions; a performance result for one should not be attributed
to the other.

No production change is recommended from the current materialize result alone.
The matched twelve-bank component has now remained nearly neutral. The next
useful distinction is between reset-count overhead and interactions present only
in the complete native graph, using controlled experiments rather than assigning
the native cost to an upstream stage from these timings alone.

## Host-workload contamination incident during this source review

A broad source-analysis regex unexpectedly occupied approximately one CPU core
for about 40 seconds. It was terminated with SIGTERM (Python PID 74321). No
browser was launched by this analysis. Exact wall-clock start/end were not
recorded; the conservative affected interval is **2026-09-17 08:25:00–08:27:37 UTC**.

The concurrently running native twelve-layer/capacity-4 baseline repeat 0 began
at approximately 08:25:12 UTC and overlapped that interval. Root and the native
pipeline agent were informed to exclude or replace its timing. This is a host
workload contamination incident, not a browser failure, and it does not affect
the earlier twelve-layer/capacity-2 numbers discussed above. Subsequent source
inspection used small bounded substrings and completed in under a second.
