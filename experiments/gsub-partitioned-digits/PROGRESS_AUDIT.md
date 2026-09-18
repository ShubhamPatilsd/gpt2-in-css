# Progress audit: what improved, what stalled, and what the next test can establish

This is an independent read-only review of the saved experiments, not a new
browser measurement. The audit owns this document only. The partitioned-digit
experiment's source, protocol, native gates and all three timing repetitions
are independently reviewed below. The audit is complete.

The evidence does **not** establish a fundamental speed plateau. It does show
that recent local-update and glyph-arithmetic work has not produced a repeatable
improvement in autonomous GPT-2 token generation. There was earlier system-level
progress, and several useful mechanisms now work. The current stall is converting
those mechanisms into a faster, accurate, connected model at its real dimensions.

## The target and the actual baseline

The relevant target is a browser-owned calculation: one prompt selection, all
twelve transformer layers, retained K/V for prior positions, the full 50,257-token
vocabulary decision, and native token feedback. The page must not use inference
JavaScript or receive externally calculated intermediate vectors. Offline font
construction and independent numerical verification are allowed. Component
drivers may supply raw inputs, but that does not make them autonomous inference.

The implementation is already quantized: core matrix weights use the established
row-q9 representation and the full head uses q16. Matching the original checkpoint's
winning tokens on a short trajectory is valuable evidence, not exact float32
equivalence or broad model-quality certification. The current prompt interface
is a fixed one-token picker; arbitrary text tokenization and long-context quality
are separate tasks.

These are the most relevant retained whole-model measurements. Different
capacities and generations must not be merged into one speedup series.

| Saved implementation | Scope and repetitions | First result | Continuing/result intervals | Complete run |
| --- | --- | --- | --- | --- |
| Original scalar-cache demo | 12 layers, capacity 8, eight generated tokens; one retained run | 110.819 s from navigation; 73.611 s from Run | Seven post-first intervals, median 77.956 s, range 62.301–91.287 s; last interval is terminal | 662.495 s |
| Reused integer10 core | Same 12-layer/eight-token size; one retained run | 81.967 s navigation; 50.969 s Run | Post-first median 54.461 s, range 41.165–63.855 s | 458.206 s |
| Whole-head font-vector cache | 12 layers, capacity 8, eight generated tokens; one retained run | 45.058 s navigation; 39.772 s Run | Post-first median 51.310 s, range 43.967–58.518 s | 402.672 s |
| Whole-head font-vector cache at longer context | 12 layers, capacity 32, 32 generated tokens; one retained trajectory | 97.566 s navigation; 66.297 s Run | Post-first median 97.694 s, range 57.176–143.320 s; history grows through the run | 3,177.132 s |
| Baseline in the later width-reuse comparison | 12 layers, capacity 4, four generated tokens; two clean fresh processes | 41.201 and 42.557 s | Nonterminal intervals 36.337/40.554 s and 32.937/33.648 s | 162.127 and 144.100 s |
| All-head owned attention | 12 layers, capacity 2, two generated tokens; one completed run | 52.116 s from navigation | One 47.370 s **terminal** interval; no continuing interval | 99.487 s |

Sources: [original demo report](../browser-gpt2/RESULTS.md),
[integer10 raw summary](../browser-gpt2/demo-reused-twelve/scaling-summary.json),
[eight-token font-vector summary](../browser-gpt2/demo-font-vector-twelve/scaling-summary.json),
[32-token raw summary](../browser-gpt2/demo-font-vector-context32/scaling-summary.json),
[clean four-token comparison](../browser-gpt2-scaling/native/capacity4-comparison.json),
and [owned-attention summary](../browser-gpt2-integration/native/owned-b12c2-r1/integration-summary.json).
The raw summaries, rather than older prose calling 78 s/token the only result,
determine the current evidence.

The first three saved runs show substantial engineering progress: 662.495 to
402.672 seconds is about 39.2% less total time at the same nominal eight-token
size. They were not a randomized contemporaneous comparison, so that percentage
is a historical system-level difference, not an isolated treatment effect.
All eight decisions in the latter two runs match both the independent quantized
reference and the original floating-point winners. The font-vector run's final
residual RMSE is 0.018902; peak sampled renderer RSS is 3,863.4 MiB.

The longer run matches all 32 reference and original-float winners on its one
trajectory. Its final residual RMSE is 0.018007 and sampled renderer peak is
5,215.7 MiB. Its first post-first interval is 57.176 seconds; several late
intervals exceed 130 seconds. This documents a scaling problem within the run,
not an identical fixed workload becoming slower. Its one initial Run action is
recorded as an external write; later numerical intermediates are browser-owned.
The newer autostart experiments instead record zero post-navigation writes.

The isolated 70.09-second width-reuse result for two tokens is a real passing
short screen, but it is not the best established throughput: its comparator was
earlier, it contains no continuing interval, and later four-token repetitions
reverse the apparent gain. The latest owned-attention result is also a correct
integration, not a faster model. No recent 32-token result supersedes the
3,177.132-second measurement.

## Where time is known to go

Within each layer the native path performs normalization, QKV projection,
K/V retention and attention, attention-output projection plus residual,
normalization, MLP expansion plus GELU, and MLP projection plus residual. The
next layer consumes that residual. After twelve passes, final normalization and
full-vocabulary selection feed the next token back into embedding lookup.
Each boundary must preserve values and identify the current generation.

In the 32-token run, renderer task accounting attributes 67.97% of warm task
time to style recalculation, 15.10% to layout, and 16.88% to other tasks. These
are renderer-task shares, not exclusive wall-clock percentages or mathematical
operator shares. Only 14 of 31 post-first epochs have a usable monotonic coarse
boundary sequence. Those observed spans put 88.87% between embedding and core/KV
completion, but cannot split it into pure matrix arithmetic, retention and
transport. [Raw evidence](../browser-gpt2/demo-font-vector-context32/scaling-summary.json).

The later native receipt diagnostic caught **zero of 24 passes with all six
stage witnesses**. Its reads can wait for or flush browser work; the longest
read lasted 5.685 seconds. Therefore the repository still cannot honestly answer
“exactly what percentage of token time is just the matmuls.” A small observed
vocabulary tail also does not prove the whole vocabulary computation is cheap.
[Stage-cost report](../browser-gpt2-integration/stage-costs.md).

An older, different fixed-prefix twelve-block experiment gives a useful
prioritization clue. Across 84 isolated stage fixtures, sums of per-layer median
browser-task costs were 4.151 seconds for FC/GELU, 2.127 for QKV, 1.508 for MLP
projection, 0.760 for attention projection, 0.328 for attention mixing, and
0.285 for both normalizations. They total 9.158 seconds, while the connected
graph used about 39.6 seconds of browser work. The isolated dense stages account
for 93.3% of that **isolated-stage** work, not 93.3% of token time. The gap cannot
be booked as an independently measured “transport stage.” This experiment
excludes prefix prefill, final vocabulary work, KV append and token feedback.
[Full scope and results](../hybrid-12block-profile/RESULTS.md).

There are also directly measured costs of exposing many model coordinates.
An old real 768→3,072 FC fixture shapes the same 9,216 glyphs in every condition.
Plain output spans took 111.3 ms; exposing 3,072 timelines took 588.5 ms; exposing
and decoding/GELU took 1,074.3 ms over rotated warm navigations. This is evidence
about that large intermediate boundary, not an operation profiler for today's
runtime. [Source report](../gpt2-block-css/HVAR_SHAPING_EXPOSURE.md).

The newest GSUB reader test asks a different question: removing **one final
reader** from a 64-input integer sum leaves most of its time intact. Its few-ms
reader increment does not contradict the cost of thousands of internal FC
carriers. Neither result should be generalized outside its boundary and workload.
[Reader experiment](../gsub-reader-isolation/RESULTS.md).

## Which local wins did not become model wins

| Finding | What actually passed | Why it does not establish faster token generation |
| --- | --- | --- |
| About 6.17× less style work | One query head changes, eleven heads and literal K/V stay fixed; style 16.431→2.662 ms | Every real layer changes all queries and requires live cache ownership, native input transport and completion joining. Measured wall latency only changed 125.402→112.914 ms in a fixture with a polling floor. |
| Rendered old V reused | Earlier isolated 32-position attention about 1.35→0.98 seconds | Layer switches replace the active layer's values. Later twelve-layer component switching medians were nearly unchanged; two clean four-token native pairs disagree. |
| All twelve heads own inputs/cache | Correct autonomous two-token run through twelve layers, all retained vectors checked | Added native transfers/barriers and state; 99.487 seconds versus an earlier unmatched baseline's 82.73 seconds. No speed gain or long-context scaling established. |
| Faster isolated FC/GELU | Older easing experiment cut local FC task work about 37% | Connected fixed-prefix twelve-block medians 39.7→39.3 seconds do not resolve a meaningful improvement; not full token generation. |
| GSUB depth amortization | Two-coordinate reversible circuit at sixteen steps: 7.0 versus 10.2 ms for direct CSS, exact finite-domain checks | Small discrete state with joint-state tables is not hundreds of interacting real-valued coordinates. Wider weighted sums did not inherit the speedup. |
| Shared HVAR matrix inputs | At 64 inputs and sixteen outputs, 24.8 ms versus 72.2 ms for separate GSUB row fonts per 256 outputs | Synthetic four-bit integer arithmetic; direct CSS is still 9.2 ms. Current GPT-2 already shares input settings across output glyphs. |
| Global reuse of digit symbols | Constant 262 glyphs and 2,664 WOFF2 bytes at width 64; exact sampled arithmetic | It is roughly 28–45× slower than retained position-specific digits in matched runs. Width 256 is rejected before arithmetic because of 29,359 subtable references. |

Evidence: [locality report](../browser-gpt2-scaling/locality-report.md),
[native scaling results](../browser-gpt2-scaling/RESULTS.md),
[all-head integration](../browser-gpt2-integration/RESULTS.md),
[older twelve-block profile](../hybrid-12block-profile/RESULTS.md),
[unconventional probes](../browser-gpt2-integration/UNCONVENTIONAL_EXPERIMENTS.md),
and [latest three-experiment synthesis](../gsub-width-followups/RESULTS.md).

The clean four-token width-reuse pairs are especially informative. With baseline
first, total time improved 162.127→151.950 seconds; with order reversed, it
regressed 144.100→163.906 seconds. Nonterminal interval means move in opposite
directions too. All four runs pass their token/cache checks. Averaging those
different directions into a single favorable headline would manufacture progress.

## What is obstructing useful progress

1. **Too much distance between the proof and the target.** A two-coordinate
   circuit, a 64-input small-integer sum, a single immutable attention head and
   a real 768→3,072→768 MLP test different problems. Each can answer its local
   question; none substitutes for native model integration. New mechanisms need
   explicit width, precision, multi-output and connected-stage gates before
   more effort is spent optimizing them.
2. **State transport and retained scheduling are part of the computation.** A
   cached number is not automatically a cached browser representation. Native
   ownership/latches add dependencies and generation handling. Smaller property,
   DOM, glyph or file counts have repeatedly moved costs instead of removing
   them. Old frozen-cache controls were diagnostic external writes, not usable
   no-JavaScript inference. [Retention study](../browser-gpt2/MEMORY_AND_SPEED.md).
3. **Fair comparison had to be repaired in several probes.** The early GSUB depth
   control unnecessarily forced CSS through a font-style geometry return trip;
   removing it eliminated the apparent eight-step advantage. A later HVAR timing
   phase replayed inputs and confounded its cache comparison. One-output HVAR
   fixtures understated multi-output sharing. These are documented corrected
   experiments, not valid evidence to keep in a speedup narrative.
4. **Precision rules eliminate attractive shortcuts.** A fast wrong output is
   not inference. The old connected twelve-block page's 8.442-second result had
   residual RMSE 10.359. Its 9.388-second staged counterpart externally transferred
   vectors and omitted the head. Neither is autonomous token speed.
   [Retained invalid/staged results](../gpt2-flat-12block-chain/RESULTS.md).
5. **Several ostensibly new optimizations already exist.** Input-sharing font
   settings, the K/V cache, a reused transformer graph, local controls and some
   private scratch state are baseline mechanisms. Naming them again is not an
   implementation change. Conversely, many previously measured local gains have
   not passed a matched continuing-token integration gate.
6. **Attribution remains incomplete.** The current full-token stage witnesses
   miss boundaries; broad style/layout counters do not identify pure arithmetic
   time. Capacity-two runs contain only a terminal interval. Small repetition
   counts, power state and host variation matter. One four-token baseline was
   correctly excluded for overlapping source-analysis CPU work; retained failed
   and contaminated records must remain visible.

These are reasons to change experiment selection and promotion criteria. They
are not proof that the browser has no faster valid implementation. Negative
results have narrowed several architectures, while the historical eight-token
improvement demonstrates that system-level changes can matter.

## Four new or still-unmeasured stock-browser attacks

| Attack | Existing evidence and status | Next decisive gate | Constraints |
| --- | --- | --- | --- |
| Change both candidate identity and compiled rule organization, as independent controls | Globally shared digits made rule matching broad and hit a validation limit; position-specific digits were faster but larger. Slot-partitioned digits and lossless class-rule packing are genuinely new tests. One changes which positions qualify for a rule; the other changes table storage/dispatch while preserving arithmetic. | Exact four-input gate, sampled wider carry/routing checks, then matched full-boundary timing at width 64 and a valid width-256 program. Include the old global alphabet in the same fixture before claiming the identity change caused a gain. Count binary references separately from rule statements. | Stock browser, unchanged integer contract; still far from GPT-2 precision and width. |
| Start arithmetic at the unique accumulator marker instead of selecting every digit | The new compiler still uses seven top-level lookups per merge. An unimplemented alternative uses a marker-anchored outer context and a flat sequence of nested local actions. It changes execution dispatch, independently of glyph alphabet and table compression. | A two-addition fixture must prove that later actions still target the right location after word absorption. Then exact four-input checks and matched width-16/64 timing. Context bookkeeping could still scale poorly; fewer visible passes is not proof of linear execution. | Stock browser hypothesis; no change to engine limits. [Compiler proposal](COMPILER_NOTES.md) is explicit about unresolved semantics and costs. |
| Preserve rendered V separately for each layer, rather than preserve only selected-layer values | Numeric K/V retention and active-layer width reuse already exist. The documented missing question is whether rendered representations can survive all twelve layer selections cheaply. The prior width-reuse component did not show a layer-switch benefit, and native repeats disagreed. This is an outstanding physical representation/lifetime test, not a new cache idea. | Same populated capacity and queries at 1, 2 and 12 layers; append, query-only and layer-switch cases. Measure peak resident memory as well as latency, then continuing native tokens. Reject a speed result purchased by an unbounded rendered graph. | Stock browser, same checkpoint and attention mask. Per-layer rendered banks are a hypothesis, not a demonstrated fix. |
| Use static per-input glyph advances as an exact affine baseline | For the current small discrete input domain, each fixed-weight contribution can be tabulated independently and selected with native counters; text layout can sum advances. No learned code assignment or repeated GSUB reduction is required. This control is now implemented in the current experiment and passes the native gates below. The old CSS-counter matrix accumulated weighted counters instead. | Measure raw-input encoding, every output and final CSS consumption. Then test distinct rows, table/glyph growth and geometric precision. Do not call width summation internal glyph-state arithmetic. | Stock browser for the finite integer probe. Continuous model activations require a separately validated quantization/encoding contract; this is not a demonstrated multilayer replacement. |

The [per-layer representation gap](../browser-gpt2-scaling/RESULTS.md) and
[old weighted-counter implementation](../counter-matrix/RESULTS.md) delimit the
third and fourth proposals. A review cannot prove an idea absent from every
historical branch; “not established” here refers to the inspected source and
saved reports. These proposals are intentionally bounded tests, not predictions
of a token speedup, and do not expand the active experiment automatically.

There is also an integration backlog before inventing another execution engine.
Sparse avar2 GELU followed by linear HVAR already computes a real block-0
768→3,072→768 MLP at a reported 251 ms component median, retaining a 3,072-value
preactivation boundary. Native real-layer/generation integration would be new
work; the mechanism itself is not new. Selective dense-stage ownership,
projection-setting, head-input and feedback-reader variants also remain listed
as unmeasured. See the [avar2 MLP report](../avar2-gelu-linear-hvar-full-mlp/RESULTS.md)
and [integration backlog](../browser-gpt2-integration/RESULTS.md).

Two previously proposed directions change the target and should not be
reintroduced as fresh discoveries. A custom floating-point SVG backend needs
actual Chromium integration: the standalone real 16→16→16 Skia slice reduced
held-out RMSE from 0.0347972 to 0.00170061 with F16, but substituted ReLU for
GELU and established no browser speed. Learned glyph-code interfaces change
the model: tested held-out relative error was 36.21%, improving only to 35.82%
after table fitting, against a declared 5% screening gate. Jointly trained models
that emit codes remain untested. These are [precision](../skia-f16-real-matvec/RESULTS.md)
and [model](../learned-glyph-code-screen/DISTILLATION.md) tracks, not drop-in
optimizations of the current stock-browser GPT-2 implementation.

The root [next-directions document](NEXT_DIRECTIONS.md) makes the same useful
distinction between a new dispatch hypothesis, integration of an existing MLP
mechanism, and persistent rendered-value storage. I found no claim of false
novelty in that ordering. Twelve private numeric/font-setting K/V banks already
exist; they are not twelve independently retained rendered V surfaces. The
[materialization review](../browser-gpt2-scaling/materialization-notes.md)
explicitly describes the shared attention graph beneath all twelve banks and
the layer-dependent aliases that change on selection. A persistence comparison
should replay the same per-layer queries and K/V history between designs;
identical queries across different layers would be a restricted diagnostic.

Fused attention and alpha-bit circuits do not currently justify further scaling:
the tested fused attention was 3.95–5.26× slower than matched CSS, with a real
layer-11 range failure; alpha circuits became very slow and the wider connected
matvec tests failed. Their [completed results](../browser-gpt2-integration/UNCONVENTIONAL_EXPERIMENTS.md)
are reasons to stop those particular implementations, not reasons to infer that
all nontraditional execution mechanisms are impossible.

## Gate for the new partitioned-digit experiment

Source, protocol, native correctness and all timing review are complete.
Acceptance must
preserve the same signed weighted-sum and internal continuation, native raw-input
encoding, necessary final numerical reader, and exact output oracle. Grouping
must not split the problem into externally summed answers or receive precomputed
products. It must count glyphs, binary subtable references, active rule targets,
font bytes and complete update time separately. A font that loads or builds is
not a correct arithmetic implementation; a compact arithmetic implementation is
not yet a faster model.

Promotion beyond this experiment should require a real, connected tensor
workload and then an unchanged-context full-model comparison with several
nonterminal intervals, repeated fresh-browser runs and the same independent
token/cache/head checks. A useful outcome can also be a decisive rejection that
stops further investment in this representation.

### Completed source and structure review

The [compiler](../../tools/build_gsub_partitioned_digits.py) introduces one
ordinary and temporary digit alphabet per base-16 position. The two new layouts
have byte-identical arithmetic FEA. The control explicitly forces Format 3
coverage-context tables; the packed version converts them into Format 2 class
contexts without pruning or expanding rules. For each lookup and context side,
coverage sets must be identical or disjoint. The conversion retains matching
sets, context order, nested action records, lookup identities and feature order.
Grouping by the first input class preserves order among rules that can match
the same target. The first-glyph coverage still excludes nonmatching classes.
I found no source-level semantic discrepancy in this conversion.

I independently checked all seven built variants' file hashes, raw TTF lookup
counts, raw subtable counts and formulas. All contain 406 glyphs, `7N+82`
lookups and `115N+1510` emitted FEA statements. The coverage layout references
`115N-23` subtables; the packed layout references `7N+82`. At 256 inputs the
packed font has 1,874 references and is 4,220 WOFF2 bytes. Both four-input
variants pass all 65,536 inputs in standalone HarfBuzz; wider builds pass only
sixteen initial offline probes at this stage. TTF and WOFF2 GSUB, cmap, glyph
order and metrics agree. None of these facts substitutes for browser correctness.

Three preflight issues were identified and corrected before the full timings:
the harness now requires the entire exact-font correctness report to pass;
the old global-digit font is included under the same fixture for the causal
partitioning comparison; and reachable shifted-sum carry boundaries are
explicitly constructed. The many-output fixture uses sixteen identical rows
and row-shifted nonce text. That is declared as a controlled repetition test,
not a general matrix with distinct outputs.

The first 512-vector shared-row gate exceeded its declared 180-second budget
without a numerical mismatch. It is preserved as a failed attempt, not reused
as an accepted gate. Before rerunning, the harness declared a 64-vector subset:
all twenty width-64 extrema/cancellation/carry cases, twelve distributed
coordinate probes, and thirty-two deterministic random cases. The complete
width-4/16/64 single-row arithmetic gates remain unchanged, and every later timed output is
checked. This narrower shared-row gate still tests repeated row delivery and
readback without representing it as an exhaustive matrix check. The complete
timing configuration has a declared 90-second evaluation deadline; correctness
evaluations retain their 45-second deadline and 180-second configuration budget.

A separate 2,071-vector width-256 attempt reached 2,048 exact vectors on every
backend before its 180-second budget expired. It is also preserved as a failed
attempt. The declared rerun retains all twenty-three edge/carry/cancellation
cases, both signed extrema at each of 256 coordinates, and 128 deterministic
random vectors: 663 cases total. This is a sampled gate, not exhaustive
width-256 validation. Timing batches were reduced equally across backends to
32 outputs for the main comparisons and 16 outputs at width 256 before timing;
the final report must compare within those batch sizes and report all three
fresh-browser repetitions.

The new [static-advance control](../../tools/build_static_advance_sum.py) is
mathematically correct for the same affine result: each selected input glyph
has advance `2*(w*x-minimum)`, and the nonce has constant advance 65. Subtracting
`64+2*sumOffset` gives `2*S+1`. Independent TTF parsing confirms all 64 product
metrics, all 65 nonce metrics, 130 glyphs and the absence of GSUB/HVAR tables.
The hashes match the manifest. Its state is geometric width summation, not an
internally reusable glyph sum, and the report must preserve that distinction.
This implemented control passes the native gates described below.

The original HVAR-256 WOFF2 control failed to load. Its TTF counterpart loaded
and returned the expected default-axis width, so the fixture now uses that TTF
with the failed attempt preserved. Timing excludes font loading. The default
load check alone was not a changing-input arithmetic gate; the completed native
gate below now supplies that evidence. [Packaging diagnostic](diagnosis-hvar256.json).

The separate [AAT support screen](../aat-support-probe/RESULTS.md) appropriately
stops before arithmetic compilation. In the tested Chrome, both downloaded
TTF and WOFF2 fonts load, but the AAT substitution leaves width 100 while the
equivalent GSUB control returns 700. Standalone HarfBuzz executes the AAT rule.
This is a support/deployment rejection for these web fonts, not a speed result
or a claim about every browser or locally installed font. The initial
empty-outline WOFF2 failures affected every control and were correctly kept
separate from the repaired final fixture.

### Native gate review

The completed [main correctness gate](results-correctness-main.json) passes
all 28 backend/configuration records with zero mismatches or browser errors.
Every one of seven backends checks all 65,536 four-input vectors, 1,108
width-16 vectors, 1,300 width-64 vectors, and 64 width-64 vectors through all
sixteen repeated output rows. This totals 482,776 exact output checks, each
checking the source width, decoded CSS number and following consumer where
applicable. All 64 GSUB stage-disable controls change the result as required.

I independently matched all eighteen loaded font hashes to the intended
files and matched the saved main harness to its recorded hash. The final frozen
harness differs from that snapshot only in the separately declared width-256
correctness subset and its description. The main gate therefore remains
applicable to the unchanged main fixtures.

The completed [width-256 gate](results-correctness-256.json) passes all 663
declared vectors for packed GSUB, static advances, HVAR and CSS, with zero
mismatches or browser errors. All four GSUB stage-disable controls discriminate;
the full result is width 21,185 while disabled stages produce 0, 155, 64 and 0.
The final frozen harness hash and all three loaded font hashes match. In
particular, HVAR's TTF control now has changing-input checks, rather than only
a successful default-axis load. Across the two accepted gates there are
485,428 exact output checks.

The packed program therefore repairs the demonstrated browser capacity failure
at 256 inputs on this declared sample, without pruning arithmetic or changing
engine limits. Its wider validation is sampled, and it is still a four-bit
integer affine circuit with an internal continuation. This is not evidence of
a correct full-precision transformer or a model speed improvement.

### Main timing review

The [main timing report](results-timing-main.json) passes all three fresh-browser
repetitions with 84 backend/configuration records and 67,200 checked outputs.
There are no mismatches or browser errors. I independently recomputed every
within-repetition upper median from its twenty measured samples, checked the
final source hash, and matched every font hash to the passed gate. All twelve
repetition/configuration seeds differ; backends in a configuration receive the
same stimulus stream.

The audited median-of-three times below are milliseconds per **32 outputs**.
The first column publishes 32 independent vectors; the second publishes two
vectors with sixteen repeated rows each. This changes both sharing and the
number of input publications, so the cross-column ratio is a workload-level
comparison, not an isolated shaping-cost estimate.

| Backend | Width 64, one output/vector | Width 64, sixteen outputs/vector |
| --- | ---: | ---: |
| Global reusable digits | 594.5 | 593.9 |
| Slot digits, coverage contexts | 179.9 | 178.8 |
| Slot digits, packed class contexts | 194.4 | 193.8 |
| Retained position-specific digits | 17.4 | 15.7 |
| Static glyph advances | 10.2 | 8.6 |
| Shared HVAR | 41.2 | 8.0 |
| Direct CSS | 3.1 | 0.5 |

The conclusion follows from matched comparisons: slot partitioning improves the
poor global-alphabet implementation by about 3.3×, but remains roughly ten times
slower than retained position-specific glyphs. Packing the same slot arithmetic
does not improve time here; it is slightly slower. Its successful capacity
repair is a separate result. Static advances improve this small-domain affine
work over GSUB, but at sixteen outputs the HVAR control is faster, and direct
CSS remains the fastest tested backend. No result supports promoting the compact
GSUB program as the current model's matrix replacement.

The results do not isolate which internal engine operation costs time. In
particular, the symbolic rule-eligibility count in the compiler notes is a
plausible design concern, not a measured number of rule visits or a proven
explanation for a particular runtime ratio.

### Width-256 timing and final report review

The [width-256 timing report](results-timing-256.json) also passes all three
fresh-browser repetitions, with twelve backend/repetition records and 4,800
checked outputs. Every recorded answer is exact; no browser errors occurred.
All within-run medians recompute from their raw samples, the final harness hash
matches, and all font hashes match the accepted width-256 gate. The three
repetitions use different seeds and each backend receives the same inputs
within a repetition.

These times are milliseconds per **16 outputs**, a different batch size from
the main table:

| Backend | Three run medians | Median of run medians |
| --- | --- | ---: |
| Packed slot digits | 1,475.6 / 1,473.1 / 1,445.1 | 1,473.1 |
| Static advances | 14.5 / 14.7 / 13.8 | 14.5 |
| HVAR | 39.6 / 38.7 / 37.2 | 38.7 |
| Direct CSS | 5.8 / 5.8 / 5.7 | 5.8 |

The wider program is valid on the declared checks but remains far too slow to
promote on this comparison. Packing removes the known validation obstacle; it
does not remove the execution cost. Dividing by sixteen describes this batch's
per-output cost, not measured isolated-vector latency or an asymptotic bound.

Across the two timing reports there are 72,000 exact checked outputs, including
warmups. I independently verified all 32 configurations in
[results-summary.json](results-summary.json): the three constituent medians,
their median and range, per-output/per-vector divisions, and hashes of the four
raw source reports all agree. The complete [results report](RESULTS.md)
correctly separates capacity, representation, component speed and model speed;
its main table and substantive interpretation match the raw evidence. No
additional experiment is required to support its bounded conclusions.
