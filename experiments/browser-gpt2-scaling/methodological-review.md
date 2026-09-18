# Measurement and interpretation review

This review covers the opt-in attention ablations and their observation harness.
It is based on the generator and driver code, not an inference about Chromium's
unobserved internal caches. The measurements are in
[MEASUREMENTS.md](MEASUREMENTS.md); the reproducible aggregation code is
[summarize_browser_gpt2_scaling_investigation.py](../../tools/summarize_browser_gpt2_scaling_investigation.py).

## Evidence levels

| Level | What is established | What is still required |
| --- | --- | --- |
| Generated source inspection | Requested CSS/HTML rewrite exists and keeps the intended graph shape | A browser may resolve or invalidate that shape differently than expected |
| Deterministic component correctness | Given externally supplied QKV and controls, attention agrees with a numerical oracle on this fixture | Other magnitudes, inputs, longer histories, layer schedules and native scheduling |
| Repeated component measurements | The variant changes observed update cost for the recorded design and browser | Broad statistical confidence and a full-model speedup |
| Structural locality prototype | Ownership can be tested while adding unrelated elements and heads | Equivalent native KV storage, transport and all-head completion in the production graph |
| Native transformer feedback | A candidate survives the real reused core and feedback machinery | Full 12-layer, full-vocabulary generation with retained correctness and useful throughput |

No single level substitutes for the next. In particular, reducing style time in
an externally driven attention fixture does not establish a reduction in the
previous 32-token autonomous run.

## What the current measurements include

The [driver](../../tools/investigate_browser_gpt2_scaling.py) starts a fresh
headless browser for each variant/configuration/repeat. It compiles deterministic
synthetic QKV, uses distinct affine modifications for each layer, appends values
to that layer's cache and compares all 768 context coordinates against NumPy
softmax and weighted-V reduction. Stored values are retained natively; the
reference context is never supplied to the page.

The first sample is checked but excluded from warm timing summaries. Navigation
and initial font loading happen before this sample's timer, so this is **not a
cold-start measurement**. With more than one layer, only the first sample for
layer 0 is excluded; first visits to other layers remain in the append summary.
For full-context analysis, use final-position rows, not the average over a
growing prefix. Appending each layer is one component update, not a token.

Every measured mutation replaces the body's inline style with a generation
marker, position, selected layer and all 2,304 QKV declarations. The readiness
protocol requires a matching generation receipt, a finite context and three
unchanged comparisons after the first observation. A single iteration reads the
receipt and output with separate `CSS.getComputedStyleForNode` requests. At least
three 25 ms sleeps are therefore inside each measured duration; CDP request
latency and any work forced by computed-style reads are also included.

`Performance.getMetrics` supplies before/after style, layout and task duration
counters. Style/layout counts are the number of recalculation/layout events,
not affected-element counts. Their presence in the saved report does not prove
that only a particular subtree was updated. Nested trace events have inclusive
durations; summing them would double-count work. The optional trace uses a
separate update after the timed samples, which is the right separation for
avoiding instrumentation overhead in the principal timing table.

RSS comes from [MemorySampler](../../tools/benchmark_browser_gpt2_memory.py),
which samples the browser process tree through `ps` every 0.5 seconds. The recorded peak
spans startup through the timed samples and their validation, before any optional
separate trace. This is a sampled
resident-set sum, not a measured peak for each particular update, and not macOS
physical footprint. Short peaks may be missed; shared resident pages may be
counted more than once. It is useful for comparing gross memory cost under the
same conditions, not estimating exact memory allocation savings.

## Actionable issues and controls

### 1. Query changes and layer selection are separate experiments

For one layer, the query probe keeps position/K/V fixed and changes query
coordinates 0–63. Other heads' reference contexts remain unchanged. For multiple
layers, the loop revisits each layer in turn; selecting a different layer changes
the active exported K/V even though each stored history is immutable.

The driver now calls this second case `query+layer-switch`. Older reports with
multiple layers and `query-only` must be interpreted the same way. The
summarizer supports both labels and keeps their statistics separate.

A future direct test of persistent font representation should include three
phases: repeated query changes on the same layer, selection changes between
populated layers, and repeated queries after each selected layer has settled.
The current multi-layer revisits exercise retention correctness and switching
cost, but do not measure a long same-layer query phase for every stored layer.

### 2. The component query probe is not a localized mutation probe

Changing 64 numbers semantically does not mean only 64 declarations are written
or one head receives invalidation. The driver rewrites the full body style and
increments a global generation marker. Other declarations retain their numeric
values, but the mutation site and freshness-control machinery remain broad.

The separate [head-locality diagnostic](../../tools/probe_browser_gpt2_state_locality.py)
addresses a narrower question by changing the mutation owner from the body to
head 0 while adding unrelated heads and spectator elements. Its immutable KV
fixtures and CSS weighted-value arithmetic are intentionally simpler than the
production retained-font graph. It can demonstrate a mechanism worth porting;
it is not a replacement native-cache benchmark.

For stronger attribution, add an unchanged-value style rewrite, a generation-only
rewrite, and a query rewrite as separate controls. Record affected-element
counts for an untimed diagnostic update. This would distinguish style-attribute
processing, the completion signal and actual query dependencies. The current
driver cannot apportion these causes from duration counters alone.

### 3. Replication and pairing must match the actual experiment

The runs reverse variant order on alternating repeats, which reduces simple
order confounding. They are not randomized trials, and the existing one- or
two-process samples do not support narrow confidence intervals. Thermal state,
browser startup, background host activity, parsing and font-cache behavior can
still vary. Do not run another browser workload concurrently while collecting a
case intended for comparison.

There was one actual host-contention exception during the later native
twelve-layer/four-position follow-up: a separate source-analysis regular
expression consumed approximately one CPU for about 40 seconds while
`baseline-b12-c4-r0` was running. This is **not a browser or arithmetic failure**.
Its numerical evidence is retained, but its timings are excluded from candidate
comparisons. The native follow-up uses clean repeat-2 baseline/widths and
repeat-1 widths/baseline pairs to replace that timing evidence. See the
[native report](native-report.md) for the recorded exclusion and completed checks.

Running only one browser benchmark is therefore insufficient by itself to
prevent contention: expensive analysis, compilation and dependency installation
on the same host can also affect it. Plotting dependency installation/rendering
is kept outside the active native benchmark slot. Cheap bounded reads and report
preparation continue in parallel.

The summarizer uses one browser process as the unit of replication. It reports
the median of process medians and their range, and pairs a variant only with the
baseline of the same capacity, population, layers, requested/inferred query
count, recorded source revision, browser arguments/version and repeat ID. Update
samples from one process are not treated as independent experiments. Failed and
incomplete cases remain visible; they do not supply optimistic timing estimates.

The locality sweep also preserves one browser-startup failure as
[`initial-launch-failure.json`](locality/broadcast-h12-s8-n0-r0/initial-launch-failure.json),
separately from the successful retry's `results.json`. Thus 24 successful timing
configurations plus 12 successful traced configurations do not mean every launch
attempt passed. The main evidence inventory records the failed attempt explicitly;
it had zero measured samples and does not affect the timing aggregates.

The two-layer component suite uses capacity eight, while the twelve-layer suite
uses capacity four. Matched variants within each suite are comparable, but the
difference between suites is not a controlled layer-count effect: capacity,
population, repetition count and query schedule also differ. A pure layer-count
scaling curve would hold those other axes fixed. These suites instead test
specific layer-revisit configurations and expose whether candidate improvements
survive those configurations.

The initial capacity-4 screen has two query probes, while the early capacity-32
screen has three. Their variant-module SHA-256 also differs: the addition of
`lean` changed the module hash even though earlier variant behaviors were
unchanged. These screens remain separate in the generated report. Within the
capacity-32 paired screen, both repetitions used the same recorded sources.
Subsequent changes to labels/formatting may create further source groups without
necessarily changing a variant's rendered page. The exact generated CSS hash is
retained to make that distinction inspectable.

### 4. Hashes should eventually cover the full build and measurement closure

The initial driver recorded itself, the ablation module, the main attention
compiler and generated attention CSS. This is valuable but incomplete:
`compile_fixture`, the bridge generator, imported metrics/CDP/settling helpers,
font files and generated HTML also affect the experiment. The current revision
key means **matching recorded sources**, not a reproducible byte-for-byte closure.

A future manifest should record these dependencies, Python/package versions,
OS/architecture, browser launch arguments and fixture seed explicitly. Generated
HTML/CSS are already retained. Existing result hashes must never be backfilled
from today's source files as though those files were known to have been used.
The summarizer separately hashes each result file it actually reads.

Subsequent driver revisions additionally hash the fixture compiler, bridge
generator, profiling/DOM/memory/font-wait helpers and generated HTML, and
preserve copies of hashed Python sources under each run's `sources/` directory.
They record Python version, OS/platform, NumPy/fonttools/brotli/Pillow versions,
the fixture seed and UTC start time. This improves repeatability for those new
runs. It does not retroactively supply missing source snapshots for the initial
screen or hash every transitive dependency and font asset.

### 5. Correctness checks are necessary but not comprehensive

The driver checks finite coordinates and RMSE < 0.005 for every settled context.
It also records maximum absolute error and the other eleven heads' maximum
reference error. This is a useful independent oracle for the synthetic fixture.
The named `unchangedHeadsMaximumError` field compares those heads against the
oracle; it is not a count of unchanged DOM nodes or a direct measure of skipped
browser work. A global RMSE threshold can also hide a larger localized error,
which is why the maximum error remains visible.

The tests currently cover affine variants of one deterministic random sequence.
Before promotion, include realistic model activations, near-tied attention
scores, extreme value scales, one-slot boundaries, full cache occupancy and
distinct multi-layer histories. Native feedback and full-model quality are
separate checks. Stable reads plus a generation receipt guard this experiment
against stale observations; they are not a proof of every possible timing or
generation-wrap scenario.

### 6. Short native sequences include a terminal-token effect

The [native two-layer experiment](native-report.md) observed a shorter final
token interval for all four variants. The terminal token has no continuing
next-token feedback, unlike earlier tokens. Its intervals therefore mix
continuing and terminal execution rather than sampling one steady-state rate.
This is material when there are only three warm intervals: the median and total
run time answer different questions, and neither establishes long-run scaling.

The 12-layer/two-token comparison has only one post-first-token interval, which
is terminal. Treat it as a correctness/integration test and a total latency for
that exact short task. It cannot estimate steady-state full-model throughput.
Increasing repetitions of the same two-token task would reduce run-to-run
uncertainty but would not remove this structural limitation. A longer native
sequence is needed, with continuing and terminal intervals labeled separately.

In the measured pair, `lean` took 91.97 seconds versus 82.73 seconds for baseline,
an 11.2% increase in total latency. Its sole warm/final interval was also longer
(47.43 versus 37.91 seconds), while sampled renderer peak RSS was lower. This
single short pair does not establish a repeatable slowdown curve, but it
prevents treating the earlier component or truncated-model improvements as an
already demonstrated full-model optimization.

The two-layer coarse stage observer also omitted or rejected different terminal
epochs across variants. Stage-share percentages from unequal accepted epoch
sets should not be compared as if they were measurements of the same workload.
Full renderer counter totals and exact token intervals remain separately saved.

The later clean twelve-layer/four-token repetitions also show why terminal
classification is not a fixed timing correction: those terminal intervals are
not consistently shorter than continuing intervals. In the baseline-then-widths
pair, width reuse reduced total time by 6.3%; in the reversed-order pair, it
increased total time by 13.7%. The mean continuing-interval comparison also
reversed (8.1% lower versus 20.4% higher), as did the RSS comparison. Thus the
inconclusive native result cannot be dismissed as only a terminal-token artifact,
and pooling both pairs into one headline percentage would conceal the reversal.

The compiled artifacts remained identical between repetitions of a variant.
Similar style/layout counts with changing durations locate variability in the
measured browser execution but do not establish its allocator, scheduler or host
cause. Four matching token IDs also do not mean exact numeric agreement: the
widths final residual maximum absolute error was 0.252111 versus 0.118800 for
baseline, even though all token/reference checks passed. Those residual errors
belong to the native model test and must not be pooled with component context
errors or local-register errors.

## Driver issues corrected during the investigation

The review identified the following measurement/reporting defects. Later
driver revisions address them; saved earlier measurements are preserved rather
than rewritten with information they did not record.

| Finding | Implemented correction | Remaining interpretation limit |
| --- | --- | --- |
| Compilation and report-construction errors occurred outside the case's exception handler | The CLI catches them, saves a failed result with configuration/failure phase and continues to retain the sweep's evidence | Failures before source/environment collection cannot include those missing fields |
| A trace could fail numerical validation or completion while timed samples still passed | A separate `tracePassed` requires completion and numerical RMSE below the component threshold; both fresh and preserved failed traces count toward CLI failure | Timed-sample pass status remains intentionally distinct from trace pass status |
| A multi-layer case's trace did not exercise the same operation as its query-plus-switch samples | `traceKind` explicitly records that it changes the query on the same selected layer as the final sample | The trace cannot diagnose active-layer switching cost |
| Query count and tracing were absent from the directory identity | Requested `queryUpdates`/`traceRequested` are recorded; existing cases with differing settings are rejected rather than silently reused | The user must archive/preserve an existing case or use a distinct repetition/configuration to rerun it |
| Explicit `--positions 0` silently meant full capacity; nonpositive repeats and negative query counts silently did nothing | Explicit `None` handling and range validation reject these arguments; zero query probes remain allowed | A zero-query run intentionally supplies no query-only evidence |
| Failed/incomplete cases did not identify how many samples had been planned | Requested query count is recorded, and the summarizer reports observed/planned samples | Earlier incomplete files without that field have an unknown planned query count |

The summarizer preserves `traceValidation`, `tracePassed`, `traceComplete`,
`traceKind` and failure phase when available. It keeps a passing timed case
visible even if its separate diagnostic trace fails, so the report cannot
silently relabel the entire experiment as a validated trace.

## Native local-commit evidence is a separate mechanism test

The [local-commit probe](native-local-commits.md) has three passing cases and nine
audited commits: a local query register receives A, B, then A through a native
geometry bridge, retains each value when its upstream source is poisoned, and
computes the expected attention output. The two heads use static eight-position
K/V. This establishes coherent local capture/hold/reuse for the tested sequence;
it does not establish native per-layer KV acquisition, twelve-head completion,
or a useful reduction in total work compared with a broadcast implementation.

All cases report zero post-navigation writes. Two delay observation by two
seconds. The stronger delayed case reads a DOM completion marker before its
first computed-style read and records that the three-commit sequence had already
completed. That rules out computed-style polling as a requirement for progress
in this particular run. The earlier delayed case lacks that stronger recorded
marker check and should not be silently upgraded to the same evidence level.

Audit records preserve each held vector, output, poisoned source and signed tags,
so the head-0 correctness check covers all three commits even when the observer
arrives after completion. Head 1's reported unchanged-output differences are
based on its observed valid samples; the delayed cases have just one such sample.
A zero difference for one sample does not prove continuous invariance throughout
the unobserved interval. Its final output does match the independent reference.

These 64-coordinate context errors are reported separately from the attention
suite's 768-coordinate errors and the native model's final residual errors.
Observed completion times, especially after a deliberate wait, are not pooled
into performance averages and are not evidence of a speedup. The main inventory
links all three cases and distinguishes the marker instrumentation revision.

## Review of the concrete rewrites

| Variant | What the source actually changes | Claim supported by a passing measurement | Claim it cannot support on its own |
| --- | --- | --- | --- |
| `widths` | Fixes V's `P000` font axis at 1; uses `calc-size` to multiply intrinsic width by the varying scalar | Reduced update work with numerically correct weighted V under this schedule | Every previous V is permanently shaped across all layer switches, or a 27% full-model gain |
| `fields` | Registers exported `--fr-*` aliases as non-inheriting, explicitly forwards them through shared carrier elements and into relevant leaves | The measured cost of this particular selective-forwarding layout | Independent head ownership, or that inheritance physically copied every old field beforehand |
| `empty` | Uses style queries to hide unused score/value glyphs and removes their positive base widths from the final subtraction | Early-prefix work reduction while preserving the sum | Removal of their DOM/CSS or a reduction once all slots are active |
| `materialize` | Clears raw `--qkv-*` coordinates at the first cache bank after axis lists/scales resolve upstream | Whether terminating raw-input propagation at that point changes cost | Removal of a geometry-to-number bridge, new algebraic fusion or a new transformer operator |
| `timelines` | Moves attention-internal score timeline scope from `html` to `.fvs-query` | Effect of narrowing that timeline scope | A new per-stage version protocol, or an independent all-head completion barrier |
| `contain-layout` | Changes attention scrollers from strict containment to `size layout` | Effect of this exact containment configuration | Universal benefit from adding containment; this experiment actually removes part of the original containment |
| `contain-none` | Removes containment from those attention scrollers | Effect of the same geometry without containment | A safe general default for the rest of the runtime |
| `combined` | Combines width reuse, empty-slot hiding, selective forwarding, input materialization and local timeline scope | Interaction of the complete bundle | Additive gains from the individual changes |
| `lean` | Uses the same bundle without selective forwarding | Whether the forwarding regression can be avoided | Which of the remaining changes causes a measured gain without matched ablations |

The selective-forwarding implementation still relays all exported fields across
several spine elements, resolves selected-layer aliases on nested banks and
creates many explicit forwarding declarations. Its theoretical reduction in
irrelevant leaf fields can be outweighed by this cost. A measured regression is
informative: it rejects this particular implementation under the tested design,
not all forms of non-inheriting properties or structural head ownership.

The baseline already resolves score progress and softmax scratch fields on one
reader with non-inheriting registrations. It already retains KV privately and
uses readiness gates. These existing mechanisms should not be reported as newly
implemented by this investigation. A future fusion or local-completion result
must identify an actual removed transfer, narrower dependency or preserved
correctness barrier, then measure it in the appropriate native graph.

The later [raw-QKV source audit](materialization-notes.md) makes the
`materialize` label particularly important to qualify: baseline and candidate
HTML are identical, and the only CSS addition is a 42,797-byte rule resetting
2,304 raw QKV declarations at the first attention bank. Baseline already derives
the axis lists and scales. The reset leaves those derived dependencies, layer
selection and completion control in place, and does not clear the sibling dense
stage ancestry. It is a raw-input lifetime/reset ablation, not a newly added
materialization operation or a native input-commit boundary.

## Decision boundary

The best next candidate is whichever maintains correctness and reduces renderer
work under full occupancy and layer selection, not simply the smallest number
in an early-prefix wall-time table. Preserve negative results, inspect the
per-position curve, and compare native system behavior before changing defaults.
The hour-long run remains the end-to-end problem until an autonomous run at
comparable model, vocabulary, context and correctness demonstrates improvement.
