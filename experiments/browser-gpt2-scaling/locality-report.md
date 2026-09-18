# Structural locality experiment: let one changed head update one subtree

Measured September 17, 2026 on the local macOS host, Chromium `153.0.8010.48`.

## Finding

This experiment establishes a concrete local scaling result: moving head 0's
changing query and readiness tick from `body` to the head's own subtree kept its
style recalculation cost nearly flat as unchanged heads were added. The same
change reduced Chromium's first `UpdateLayoutTree` event from **923 elements to
77 elements at 12 heads**. Both versions still computed the correct answers.

With eight populated positions and no artificial spectator elements, mean style
time at 12 heads fell from **16.431 ms to 2.662 ms**, a 6.17× reduction in that
metric. It was 2.670 ms at one head and 2.761 ms at four heads in the local case.
The benchmark's median observed mutation latency fell only from **125.402 ms to
112.914 ms**, because it includes other work and a substantial polling floor.

This is a structural attention diagnostic with immutable K/V fixtures, real
bilinear-font QK computation, and CSS softmax/weighted-V arithmetic. It is **not
the production KV cache**, a complete GPT-2 layer, or an autonomous token run.
The measured reduction must not be multiplied by the previous full-model style
percentage to predict an end-to-end speedup.

## Question and controlled comparison

The question was whether unrelated, unchanged state can make the same active
attention head increasingly expensive to update, and whether a narrower owner
removes that extra work.

Each head is an independent subtree containing:

1. Eight immutable 64-dimensional K vectors, supplied as literal font-axis
   settings, and one changing 64-dimensional Q vector supplied as CSS properties.
2. Real bilinear variable-font QK operators, producing geometry for the scaled
   dot products. View timelines transport that geometry to a head-local reader.
3. Registered, non-inherited scratch properties for scores, maximum, exponentials,
   denominator, and the readiness receipt. These were already private in both
   comparison arms; this experiment does not isolate `inherits:false` as a change.
4. Eight immutable V vectors embedded into CSS arithmetic. The reader calculates
   softmax and its 64 weighted sums, and publishes those sums to 64 width elements.
5. A local `timeline-scope` and a readiness tick transported through a separate
   geometry measurement.

In `broadcast` mode, head 0's 64 query properties and tick are defined and mutated
on `body`. They can inherit into every head. In `local` mode, those same properties
are defined and mutated on `#head-0`. Other heads receive their own distinct,
unchanged queries locally in both modes. Page topology and calculations are
otherwise identical within a matched pair.

The head-count axis is **1, 4, 12**. Every head has eight fully populated positions.
The spectator axis is **0 or 1,024** inert descendants per head. Spectators are
simple fixed-size elements, not neural calculations or working cache banks. They
amplify descendant overhead separately from the cost of real, unchanged heads.

An important fixture correction was made before measurement: each head now has
its own deterministic RNG seed. The original sequential RNG allocation changed
head 0's K/V when the number of heads changed. All 24 measured cases now have the
same head-0 Q/K/V input hash, so the active calculation is held constant across
both head counts and spectator counts.

## Protocol and checks

- Each configuration ran in two fresh browser processes, with four query updates
  per process: **24 benchmark processes and 96 timed mutations**. Mode order was
  reversed for the second repeat. This is a small repeated diagnostic, not a
  statistical confidence interval or a population-level performance estimate.
- All heads were initialized and checked before timing began. This prevents late
  initialization of unrelated heads from contaminating the first mutation.
- Only head 0's query and tick changed after initialization. Its query alternated
  between `-0.7 × original` and `0.8 × original`. K and V remained immutable.
- A completed sample required a matching native readiness receipt, the requested
  input tick, finite output, and three unchanged subsequent reads. This adds at
  least 75 ms of explicit polling delay. The wall time also includes CDP reads and
  writes, and larger pages expose more registered properties through computed
  style. The primary locality measures are renderer style time and trace counts.
- After each timed sample, every unrelated head was checked outside the timed
  region against both its initialized output and the NumPy attention oracle.
- The numerical acceptance threshold was RMSE below 0.005 for the active head,
  every initial head, and every unrelated head after every mutation. Unrelated
  output changes also had to remain below `1e-7`.
- Actual maximum RMSE across these checks was **0.000037353**; maximum absolute
  error was **0.000103044**. Active mutations' maximum absolute error was
  **0.0000700892**. All unrelated-head output differences were exactly zero at the
  precision of the CSS computed-style numbers read by the harness.
- Page JavaScript is prohibited by CSP and the browser harness. The Python/CDP
  harness supplies input mutations and reads outputs; it does not copy computed
  values back into the page. The native ready tick is a diagnostic completion
  mechanism, not a demonstrated autonomous scheduler.
- Source and generated-page SHA-256 hashes, input hash, browser version, renderer
  metrics, numerical errors, DOM counters, and sampled renderer RSS are retained
  in each `results.json`.

One process failed during browser startup, before `Browser.getVersion` and before
any mutation, with `list index out of range`. Its original report is retained as
[`initial-launch-failure.json`](locality/broadcast-h12-s8-n0-r0/initial-launch-failure.json).
The same configuration succeeded on retry. The exception was not localized
further, so it is recorded as a harness/startup failure rather than an arithmetic
failure or silently counted as a passing attempt.

## Untraced timings

Each row pools eight updates across two processes. Style and layout are means of
renderer metric deltas; wall time is the median observed update duration.

| Inert elements/head | Heads | Owner | Style ms | Layout ms | Wall ms |
| ---: | ---: | --- | ---: | ---: | ---: |
| 0 | 1 | body | 2.575 | 3.879 | 102.237 |
| 0 | 1 | head | 2.670 | 3.992 | 103.881 |
| 0 | 4 | body | 6.937 | 4.264 | 108.520 |
| 0 | 4 | head | 2.761 | 4.602 | 104.731 |
| 0 | 12 | body | 16.431 | 3.820 | 125.402 |
| 0 | 12 | head | 2.662 | 4.862 | 112.914 |
| 1,024 | 1 | body | 3.321 | 4.017 | 102.439 |
| 1,024 | 1 | head | 3.226 | 4.018 | 103.072 |
| 1,024 | 4 | body | 9.268 | 4.764 | 112.035 |
| 1,024 | 4 | head | 3.441 | 4.971 | 107.384 |
| 1,024 | 12 | body | 21.950 | 4.327 | 129.353 |
| 1,024 | 12 | head | 3.102 | 5.019 | 112.526 |

At 12 heads with spectators, the two independent broadcast style means were
21.728 and 22.173 ms; local means were 3.177 and 3.027 ms. Without spectators,
broadcast means were 16.518 and 16.344 ms; local means were 2.723 and 2.602 ms.
The separation is visible in both repeats and is not driven by one unusually
slow sample. Conversely, there is no clear benefit at one head, as expected when
there are no unrelated heads to exclude.

Local ownership did **not** produce a demonstrated layout improvement. In these
small runs its layout means were sometimes higher. Nor did it make observed wall
latency perfectly flat; the local median rose from about 104 to 113 ms with no
spectators as the page grew. The conclusion is narrower: the active mutation's
style work and first style-event element count stayed nearly independent of the
number of unrelated heads.

## Independent traces: what actually stopped repeating

Twelve additional fresh processes traced one post-initialization mutation in each
configuration. Every traced mutation passed correctness and unrelated-output
checks. Trace durations are excluded from the timing table above.

| Heads | Body: first style event elements | Head: first style event elements | Second event elements, either owner |
| ---: | ---: | ---: | ---: |
| 1 | 76 | 77 | 65 |
| 4 | 307 | 77 | 65 |
| 12 | 923 | 77 | 65 |

These exact `UpdateLayoutTree.args.elementCount` values occurred both with zero
spectators and with 1,024 spectators per head. They are Chromium's event counts,
not an assertion that every visited DOM node or every property-map operation is
counted. In particular, inert spectators increase style time without appearing in
this count. That does not establish physical copying of every inherited property.

All twelve traces contained **nine text-shaping events** and two layout events
with **19 and 67 dirty objects**. The number of font-shaping events did not grow
with unchanged heads even in broadcast mode. Therefore the browser was already
avoiding at least that redundant work here. The demonstrated gain is preventing
collateral **style recalculation**, not evidence that all unchanged fonts used to
be reshaped or every head's arithmetic used to be executed afresh.

This distinction matters for the production plan: invalidation scope, font reuse,
and numeric reuse are different mechanisms and need separate measurements.

## Memory and capacity

With no spectators, mean sampled peak renderer RSS was approximately 498–505 MiB
at one head, 658–661 MiB at four heads, and 688–699 MiB at twelve heads. With
spectators, it was approximately 575–584, 660–663, and 696–703 MiB respectively.
The corresponding DOM-counter node counts were 105/363/1,051 without spectators
and 1,129/4,459/13,339 with spectators.

These are coarse 0.5-second sampled process RSS measurements. They are not macOS
physical footprint, may miss short peaks, and are not a controlled memory-reuse
ablation. No memory reduction is claimed from this experiment. In particular,
instantiating more persistent per-layer font geometry in the real model could
consume substantially more memory than these fixtures. The locality artifacts
were small enough that no disk cleanup was needed for this experiment.

## What the result supports, and what remains open

The result supports a production experiment in which each attention head receives
only its own changing query, has local scratch and completion state, and exports
only its finished 64 outputs. A persistent cache owner should similarly avoid
publishing unrelated cache fields throughout a shared subtree. This is an
implementation hypothesis informed by a controlled diagnostic, not a measured
production-cache optimization.

The following were intentionally held out of this test:

- **Layer switching and native KV retention.** K/V were static fixture literals;
  no browser latch or 12-layer cache-bank selector was used. This cannot establish
  that old font representations survive switching among real layers.
- **Static V-width reuse.** Weighted V is a CSS sum of literal values here. There
  is no font-rendered V-width baseline or comparison arm in this diagnostic.
- **Empty slots.** All eight positions are populated. The spectator elements are
  not empty-slot calculations, and this cannot estimate an early-token gating win.
- **Stage fusion and containment.** Both arms use the same operations and the
  same fixed, contained measurement wrappers. Neither fusion nor containment was
  independently changed.
- **Full-model updates.** Real new-token inference generally changes all queries
  and activations. The test changes one query head specifically to measure
  collateral updates. It does not imply that other heads can be skipped when
  their real inputs change.
- **Long context and model quality.** Eight static positions do not characterize
  32/128/1,024-position scaling, generation quality, or token throughput.

The next decisive production test is to repeat the one-head-query mutation on the
native retained KV cache with 1 and 12 layers, while checking unchanged cache
contents and unchanged head outputs. Trace the active style event and count font
shaping separately. Then test whole-token layer traversal, because all-head work
and layer selection may dominate even after one-head locality is fixed.

## Native commit design addendum: the current reused core

This section is a source-based design assessment, not another measured result.
It identifies what would be required to make the diagnostic's local mutations
originate from the existing script-free pipeline.

### Existing control and data ancestry

[`compile_reused_runtime_core`](../../tools/browser_gpt2_reused_adapter.py) already
moves layer control into `.core-controller`, a sibling of the vocabulary-head
receiver. `--pass`, `--layer`, `--loop-phase`, `--loop-captured-pass`, and
`--loop-held` are private registered properties. Container rules publish
`--native-pass` into `.core-block`, and `.reused-input` turns it into the finer
`--epoch` used by matrix receipts. This existing outer boundary prevents a layer
change from directly carrying layer-control properties into the 50k-row head.
It does not make the stages within the reusable core independent.

[`compile_reused`](../../tools/browser_gpt2_reused_core.py) nests the shared stages
in order: LN1 → QKV → attention/mix → attention projection → LN2 → FC → projection.
The current stage output is therefore an ancestor input to subsequent stages.
The attention/mix source is a sibling of the context bridge's receiver, but both
remain inside the upstream QKV stage's numeric ancestry. Resetting private metric
scratch is useful; it does not by itself stop changes to the inherited activation
vectors or the stage/layer containers from reaching descendants.

Inside [`font_attention`](../../tools/browser_gpt2_font_vector_cache.py),
`.fvs-query` computes query axes and live K/V settings for every head. The
non-inherited `--fc-*` fields reside on twelve nested `.fvs-bank-*` elements.
The selected layer publishes inherited `--fr-*` aliases for **all slots and
heads**, and the common score source, common score reader, and value subtree sit
inside those nested banks. A single `.fvs-score-receipt` gates the whole value
stage. Score timelines are exposed through an `html` scope. These are the exact
shared owners a per-head rewrite would have to split.

Changing `--fr-*` to non-inherited cannot complete that rewrite by itself: the
score glyphs and value rows currently depend on those aliases. Nor can a local
`--query-h` alias alone isolate a head while the original 2,304 `--qkv-*` inputs
continue to inherit through it. The desired head boundary must export its
materialized query settings/scales and selected cache inputs, while keeping raw
upstream vectors and unrelated aliases out of its compute descendants.

### Native components that can be reused

[`loop_parts`](../../tools/probe_native_reused_loop.py) already implements the
essential storage primitive: two banks of numeric fields plus a generation tag,
delayed transitions to hold a captured vector, geometry/timeline reads, and a
capture-then-advance handshake driven by CSS animation completion and SVG SMIL.
The producer writes one bank while the consumer reads the other. The current
implementation uses generic property names and a shared controller; per-head or
per-stage use would require namespacing and local container/timeline scopes.

[`matvec`](../../tools/build_hybrid_twelve_block.py) already transports a generation
marker alongside glyph geometry and gates its consumer on a matching receipt.
[`bridge`](../../tools/build_hybrid_twelve_block.py) already carries a vector and
generation between sibling subtrees. These provide concrete building blocks for
a stage input register and a local completion signal. Existing font-bank retention
likewise demonstrates delayed storage of whole font-axis lists and scales, but
does not demonstrate that a sibling head can acquire those lists without a broad
ancestor publication.

### Handoff and barrier issues that still need an experiment

1. **Reading siblings without restoring shared inheritance.** A head cannot read
   an arbitrary custom property from a sibling directly. Either its parent must
   expose a narrow, materialized input and shadow other fields at the boundary,
   or a geometry/timeline bridge must deliver those inputs. The first path may
   still invalidate all input-owner wrappers; the second adds operators and
   layout work. Their costs must be measured rather than assumed away.
2. **Coherent capture.** The query, query scale, selected K/V fields, write slot,
   layer identity, and pass receipt must refer to the same calculation. A tick
   that arrives first must not bless old Q or old cache data. A copied stage
   receipt is useful only if its geometry is coupled to the data it claims to
   certify; it is not a universal browser transaction barrier.
3. **Freeze before reuse.** When the shared QKV stage selects the next layer, a
   downstream head input bank must already be held. The existing loop uses a
   captured acknowledgement before advancing. A head/stage register must keep
   this ordering and prove that changing or poisoning the producer after capture
   does not alter the retained input or the completed output.
4. **Join all heads before the projection.** Twelve independently published
   64-value outputs need twelve matching pass tags before the combined 768-vector
   can be consumed. The current one-score-stamp and one-context-stamp arrangement
   does not implement this fan-in. A join can compare every received tag against
   the requested pass, but must reject mixed old/new head outputs and preserve
   the residual input until projection finishes.
5. **Keep control local too.** Global `@container corestate style(--layer:...)`
   selectors and the inherited pass can still invalidate a local head. A retained
   input with a root-driven layer selector is not the same experiment as changing
   only one owning subtree. Destination weight selection, cache selection, and
   completion metadata must be evaluated at the intended local boundary.
6. **Separate input change from completion metadata.** The global pass changes
   even when a fixture leaves some head's numeric input unchanged. Updating an
   otherwise dormant head's pass still has a cost. A test must distinguish a
   stable numeric input from a newly certified output for a new pass. Actual
   inference usually changes every query; the win then concerns unrelated state
   and intermediate propagation, not permission to skip necessary heads.
7. **Preserve measurement sources.** Closing a consumer gate must not remove a
   source whose timeline is needed to complete the handshake. Moving the current
   display/content-visibility boundaries without preserving live measurement
   geometry can create a deadlock or a falsely stable stale result.

### Smallest next executable test

Before rewriting all twelve heads, adapt this locality fixture into a **two-head,
three-commit native handoff probe**. Keep eight static K/V positions initially so
the new variable is native input delivery, not cache retention at the same time.

- Place a shared upstream query producer outside the head compute subtrees. It
  owns the original Q fixture and generates the same two changed Q vectors using
  CSS arithmetic. Fixture inputs appear only at this producer; destination banks
  receive their values through actual native geometry reads.
- Give head 0 a namespaced version of the existing two-bank register carrying 64
  query values and a pass tag. Scope its reader, controller, timeline names, and
  capture signals locally. Head 1 is a real, initialized attention head with
  unchanged input. Use private scratch and the same containment in both arms.
- Run three commits entirely through the existing CSS-receipt/SMIL pattern:
  capture A, capture B, then A again. After each capture, a native signal changes
  the source to a deliberately different query while the destination is held.
  Only after output capture may the next commit open the other input bank.
  This tests reuse and retention, rather than merely one successful initial load.
- Produce distinct input-captured and output-complete tags. Reject a completion
  tag if the numeric output is from an earlier commit. Check A/B/A against NumPy,
  check the poisoned-source interval against the retained output, and verify
  unchanged head-1 output and cache fixtures. Harness reads are permitted for
  validation; no writes occur after navigation.
- Compare broad publication with the native local register under the same source
  sequence. Trace input handoff and head computation separately: the local
  compute event should remain near its current 77/65 element counts, but the
  total includes the new register/bridge cost. Count extra layout and shaping
  work rather than judging only the downstream event.

The pass condition is correct capture/freeze/reuse with no external input writes
and no collateral head-1 compute update, at a measured total cost worth the
extra register. After that passes, replace the static cache with two native layer
banks, run layer A → B → A with distinct K/V, and prove that layer A's retained
values and reused font representation survive. Only then expand to twelve heads,
their completion join, and the shared attention projection. None of these native
commit extensions was implemented or benchmarked in the present locality study.

Follow-up: the smallest native input-delivery step has now been implemented and
validated separately in the [native local commits report](native-local-commits.md).
It completed A → B → A around two real attention heads, retained each input while
the upstream source was poisoned, and passed an initially unobserved run with no
post-navigation writes. It uses a serialized single reusable bank; native
per-layer KV acquisition, twelve-head fan-in, and an end-to-end speedup remain open.

## Reproduce and inspect

From the repository root:

```sh
uv run tools/probe_browser_gpt2_state_locality.py --heads 1 4 12 --slots 8 --spectators 1024 --repeats 2
uv run tools/probe_browser_gpt2_state_locality.py --heads 1 4 12 --slots 8 --spectators 0 --repeats 2
uv run experiments/browser-gpt2-scaling/locality/trace_locality.py
python3 experiments/browser-gpt2-scaling/locality/summarize_locality.py
```

The benchmark reuses an already passing result only when its source/generated
artifact hashes match; delete or relocate selected result directories to request
fresh measurements. Run browser benchmarks serially: simultaneous browser
experiments would confound timing and sampled memory. Parallel agents can still
build fixtures, review code, and write reports while one browser suite runs.

Entry points and evidence:

- [Benchmark source](../../tools/probe_browser_gpt2_state_locality.py).
- [Machine-readable summary](locality/summary.json), including per-process style
  means, pooled timing statistics, error maxima, and trace event counts.
- [Trace runner](locality/trace_locality.py) and
  [summary rebuild script](locality/summarize_locality.py).
- Representative 12-head, no-spectator
  [broadcast result](locality/broadcast-h12-s8-n0-r0/results.json) and
  [local result](locality/local-h12-s8-n0-r0/results.json).
- Representative
  [broadcast trace](locality/trace-broadcast-h12-s8-n0/trace.json) and
  [local trace](locality/trace-local-h12-s8-n0/trace.json).

Each case directory contains a script-free `index.html` and its generated CSS.
The font URL uses the local absolute URI of the repository's existing dot font;
regenerate pages after moving the checkout.

Post-measurement lint cleanup made the probe executable, sorted its imports, and
documented its intentional broad experiment-boundary exception catch with a
targeted `BLE001` suppression. Ruff passes. No computation or browser behavior
was changed, and no browser measurements were rerun for this cleanup. The exact
[source before final lint](source-before-final-lint/probe_browser_gpt2_state_locality.py)
and [SHA manifest](source-before-final-lint/manifest.json) preserve the bytes used
for the recorded measurements; current source hashes consequently differ.

The subsequent [twelve-head owned-attention integration](../browser-gpt2-integration/attention-report.md)
replaces the static-KV fixture with head-owned native input registers, real
layer/slot KV retention, all 768 context outputs, and a generation-aware join.
Its separate component and native results do not retroactively change the scope
of the locality timings above.
