# Independent audit of the width follow-ups

Status: complete. Source preflight, all completed measurements, the width-256
failure diagnosis, and the combined results synthesis have been reviewed.

This audit covers three follow-ups to the connected weighted-sum experiment:
the cost of exposing a font's answer to native CSS, a matrix workload in which
several outputs share one input vector, and a representation that reuses digit
glyphs across positions or stages. It does not run additional browser work or
change the implementation while other agents measure it.

## Reader isolation

The source-only and complete-reader variants should run on separate pages with
the same raw input vectors, nonce values, write calls, output count, warmup, and
number of observations. The source-only version observes the font's width. The
complete version additionally converts that width into a native CSS number and
uses it in a dependent width calculation. Expected observations differ by that
documented final transformation; both need exact checks.

The difference between those variants estimates the cost of adding the reader,
including its extra DOM nodes and dependencies. It does not isolate a single
CSS instruction. Hidden reader nodes left in the source-only page could still
incur work, which is why the source-only page should actually omit them.

The simple-font control may receive an externally precomputed answer. That is
an explicitly diagnostic exception, not native arithmetic. Expected-answer
preparation belongs outside the timed interval. Both of that control's variants
must still receive identical otherwise-unused raw input writes, identical answer
writes, and identical nonce changes. Its own source-only versus full-reader
comparison can measure boundary cost with little arithmetic in the font.

Do not subtract the simple-font total from the arithmetic-font total and call
the difference an exact arithmetic cost. The input dependencies and font programs
differ, and browser costs need not be additive. It is reasonable to report both
paired differences and the practical limits of the inference.

## Shared-vector matrix workload

One input vector must genuinely be written once and inherited or otherwise
shared by all output rows. A setup that performs N writes separately for each
of M rows still repeats N*M writes and does not test the intended change.

The variable-font control should use one N-axis font with M distinct output
glyphs and shared parent font settings. Each output glyph represents its own
matrix row. The digit-font implementation may require a distinct font or shaping
run per row; those costs are part of the comparison, not something to exclude.
Direct CSS should compute and consume each row's result directly without being
forced through the font-specific geometry reader.

All implementations need the same signed matrix, input vectors, number of
vectors and rows, final native numeric consumption, and observation count. Any
affine continuation retained from the earlier experiment should be consistent
across implementations; legally folding it into fixed weights is allowed.

Include a non-square shape to expose transposition/indexing errors. Check each
row identity independently with single-coordinate probes, extrema, zero and
cancellation cases, and deterministic random inputs. Avoid accidental duplicate
rows or all-zero columns that make nominal dimensions misleading. If a matrix
uses repeated or rotated weight patterns, report that structure; it is not a
generic checkpoint matrix.

## Reusable digit representation

Keep the old arithmetic contract and final numeric reader unchanged where
possible. A new representation must not also quietly change precision, overflow
semantics, or the measured boundary. Signed integers must retain their meaning;
modulo wrapping is a different contract.

Reusing glyph identities creates a new risk: a lookup may match a value at the
wrong position or stage. The compiler needs explicit invariants for separators,
stage markers, or routing state. Controls that disable or change those markers
should break a case requiring them. Intermediate arithmetic glyphs must retain
zero advance, and later arithmetic must consume their glyph state.

Count glyphs, rule entries, top-level and nested lookup calls, context lengths,
and peak glyph-buffer size. Smaller files or fewer glyphs alone are not evidence
of faster execution. Compare exact outputs before measuring speed. Exhaustive
four-input testing remains feasible; wider cases should include extremes,
carries, cancellation, and every individual coordinate. A wider test crossing
an old size boundary is valuable only after those small correctness gates pass
and the new numerical range is checked.

## Repetitions and measurement controls

Three fresh browser repetitions should use distinct deterministic input seeds.
Within a repetition, implementations being compared need the same vectors. Use
balanced backend and configuration order so a backend is not always measured
first or last. Preserve each repetition's results as well as any aggregate.

Preparation, expected arithmetic, and protocol transport stay outside the timed
region. Include the actual native input writes, encoding, required font/CSS work,
required output reader, and forced final observations. Warmup must be stated.
Check every timed output. Hash the exact font bytes and record browser version,
machine, input seed, backend order, and the correctness gate used by the run.

All browser timings should remain serialized under the shared lock. Font builds
and CPU-heavy auxiliary checks should not compete with measured runs. Ordinary
machine activity remains a limitation unless separately controlled.

Three repetitions can establish repeatability on the tested browser and machine.
They cannot establish a universal scaling law or a GPT-2 token speedup. Each
conclusion should identify which cost or representation choice the experiment
actually changes, and preserve failures rather than changing the target until
a favorable result appears.

## Implementation and result review

### Reader source preflight

The diagnostic [font builder](../../tools/build_gsub_reader_control.py) covers
every odd final answer in `[-2751,2529]`, using advance `8192+answer`. This exactly
covers the retained 64-input contract, and all source widths remain positive.
The [reader harness](../../tools/test_gsub_reader_isolation.mjs) creates separate
source-only and full-reader contexts with matched writes and one timed geometry
observation per output. Both precomputed-answer controls additionally receive
the same unused raw-input updates. Correctness separately checks source width,
decoded CSS number, and consumer width for full-reader fixtures.

The first preflight caught unequal cache preparation across repetitions:
repetition zero performed exhaustive four-input correctness in the same browser
before timing, while later repetitions checked only a small subset. That could
warm a much larger set of HVAR font instances in the first repetition. The root
agent changed the design to run exhaustive validation in a separate browser
before all timed repetitions, with the same small precheck in each fresh timed
browser. Width order now rotates across repetitions, and the six backend blocks
rotate by two positions rather than one. Source/full order alternates each round.

No arithmetic or output-offset issue was found in the reader preflight. The
interpretation remains the incremental cost of the reader fixtures, including
their DOM and style dependencies; it is not a pure font execution measurement.

### Reusable-symbol source preflight

The [reusable compiler](../../tools/build_gsub_reusable_digits.py) keeps one
`acc` marker followed by the four-digit running total. Each remaining operand
has its own marker and four product digits. Digit contexts require the unique
accumulator marker and the immediately following operand word. They retain each
temporary carry until all four digits have been processed. Cleanup absorbs the
old accumulator word and operand marker, and normalization restores one `acc`
followed by the new four digits.

The first input uses a dedicated alphabet to seed the accumulator; subsequent
inputs reuse one alphabet per repeated weight. Those alphabet mappings preserve
the old `[3,-2,5,1]` arithmetic. Intermediate advances remain zero. The final
dependent operation and native reader use the same signed contract as before.

Source-derived counts are 262 glyphs, `7*N` top-level lookup calls,
`7*N+25` total lookups, and `115*N+454` rule statements. The maximum contextual
backtrack is nine glyphs and the peak buffer is `5*N+1`. These are structural
counts, not runtime predictions. Every repeated pass needs its own lookup index;
the actual compiled lookup count and browser correctness must confirm that the
compiler/shaper has not collapsed necessary repeated applications.

The marker control replaces the first input's accumulator-producing alphabet
with an ordinary operand alphabet for the same value and weight. That preserves
the mathematical product while removing the marker needed to execute and publish
the result. Splitting input characters across atomic inline blocks can publish
the first partial result here, so the control appropriately requires a wrong
answer rather than universally requiring zero width.

The new representation removes glyph growth, but still has sequential passes
and a growing glyph buffer. A partially executed circuit could publish a partial
answer if an engine work limit intervenes. Exact full-result checks, extrema,
and individual-coordinate probes remain required at every wider size.

### Shared-matrix preflight

The matrix worker's agreed design covers input counts 4, 16, and 64 and output
counts 1, 4, and 16, including non-square cases. Rows use distinct deterministic
synthetic coefficients from `{-3,-2,-1,1,2,3}`. Every backend receives one parent
write per input coordinate plus the nonce. The retained digit implementation
uses separate row fonts; the variable implementation shares one multi-glyph font
and parent variation settings. Both fixed-total-output and one-vector workload
views are planned, with their input and output counts recorded separately.

Completed source and result review remains pending.

The [matrix compiler](../../tools/build_gsub_shared_matrix_probe.py) and
[harness](../../tools/test_gsub_shared_matrix_probe.mjs) now implement that
design. The compiler records the synthetic matrices and hashes all row fonts.
The harness checks that every coefficient is nonzero and every row is distinct.
It updates only vector-parent properties, independently observes each row, and
requires a passing separate correctness report for the exact font bytes before
timing. Configurations rotate across fresh browser repetitions, and backend
orders use all six permutations.

Each HVAR font contains all sixteen result glyphs even when a configuration
activates only one or four output rows. The active-row count is therefore a
subset of the same font, not a newly rebuilt font of that smaller size. This
should stay explicit when interpreting memory or cache effects.

The fixed-output view uses `256/M` vectors, so increasing output count reduces
the number of raw input writes while preserving 256 observed outputs. The
one-vector view preserves one set of input writes while increasing observed
outputs. Both views are relevant, but neither permits attributing every change
in elapsed time solely to arithmetic reuse. Raw batch times, vector counts,
output counts, and normalized values must remain available together.

One-vector cases can fall below the browser clock's useful resolution. A zero
or sub-millisecond sample is not zero-cost execution. If small differences are
not stable across repetitions or are comparable to timestamp quantization,
their ordering is inconclusive; precise speedup ratios would be misleading.

The matrix harness subsequently addressed that risk by timing 32 different
one-vector updates per sample. It forces all outputs at every update, retains
every observation for checking afterward, stores the raw aggregate duration,
and divides by 32 to report average update cost. I reviewed that change: it does
not skip intermediate reads or measure only the final update. The resulting
statistic is a median of 32-update averages, not a distribution of isolated
single-update latencies.

The nonce cycles through 65 glyphs during these longer samples. It changes on
every update but cannot guarantee globally unique text. In HVAR the row character
is fixed and inherited axes also form part of the changing font state. The
harness now explicitly records the number of unique input-plus-nonce states
and describes the cycle rather than claiming that all text or font caches are
disabled.

The completed matrix result review appears below.

### Input sharing already exists in the model

The shared-vector comparison must not be presented as a new optimization to
the current GPT-2 implementation. Its matmul stages already reuse a source
vector's font settings across output-row glyphs. The current core calls
`hybrid.matvec` with `compact=True` for QKV, attention projection, the first MLP
projection, and the second MLP projection
([call site](../../tools/browser_gpt2_core.py#L313)).

The implementation derives the axis settings from the source vector, applies
them to a common stage selector when one pack suffices, and creates each
output's text from that output row's characters
([settings and output construction](../../tools/build_hybrid_twelve_block.py#L131)).
Each input-shard font contains all output rows
([font construction](../../tools/build_gpt2_block_css.py#L149)). The 768-input
stages use one common ancestor setting; the 3,072-input projection uses four
packs whose classes share the corresponding input settings across outputs.

The new matrix fixture therefore measures an existing mechanism under a
many-output workload. Its value is establishing a fairer comparison and
understanding the effect of input reuse, not demonstrating that the model
previously performed one independent input-setting update per output.

### Completed reader results

I independently read the completed
[reader results](../gsub-reader-isolation/results.json). The report passes with
no errors. All 99 timing rows, all correctness rows, and every profile pass.
The dedicated validation browser exhaustively checks all 65,536 four-input
vectors for every condition. The wider validation sets contain 2,315 vectors
at width 16 and 3,083 at width 64. Each timed repetition then uses the same
128-case precheck in a fresh browser.

At width 64, the per-repetition medians for a batch of 256 outputs are below.
The last column is the median of matching within-round full-minus-source
differences, not subtraction of the two separately computed medians. I
independently recomputed every paired median in `summary.json` from the raw
samples; all agree.

| Method | Repetition | Source only | Complete reader | Median paired increase |
| --- | ---: | ---: | ---: | ---: |
| Running-total GSUB | 0 | 73.0 ms | 76.6 ms | +3.10 ms |
| Running-total GSUB | 1 | 72.3 ms | 76.0 ms | +3.25 ms |
| Running-total GSUB | 2 | 74.6 ms | 77.5 ms | +4.20 ms |
| Tree GSUB | 0 | 131.1 ms | 136.0 ms | +5.10 ms |
| Tree GSUB | 1 | 127.7 ms | 130.6 ms | +3.30 ms |
| Tree GSUB | 2 | 130.8 ms | 135.3 ms | +4.40 ms |
| HVAR | 0 | 214.1 ms | 206.1 ms | -6.35 ms |
| HVAR | 1 | 198.6 ms | 208.7 ms | +3.90 ms |
| HVAR | 2 | 212.0 ms | 206.6 ms | -3.05 ms |

The HVAR sign reversal means that its small incremental reader cost is
unresolved by this experiment. It is not evidence of a negative reader cost.
Nevertheless, approximately all of its large total remains when the reader is
removed. The GSUB increments are consistently positive and small relative to
the source path. These interventions reject the hypothesis that the final
reader dominates the measured width-64 font calculations.

The precomputed-font diagnostic adds 2.60–3.05 ms for its reader at width 64; the
precomputed-CSS diagnostic adds 2.20–2.60 ms. Those paired controls corroborate a
small boundary cost in these fixtures. They do not permit an exact subtraction
of arithmetic cost from the real-font totals. At smaller, cheaper calculations
the reader is a larger fraction of total time, so the width-64 conclusion should
not be generalized to all programs.

The separate profiles retain the tree-versus-running-total difference with no
reader: source-only layout totals are about 1,040.8 ms versus 460.5 ms over ten
batches. The final reader raises recorded style events from 10 to 2,567 in these
profiles, despite the small elapsed-time increment. That illustrates why event
counts alone do not identify the dominant cost.

The remaining source path includes raw property writes, native input encoding,
style resolution, font shaping, and measuring the source geometry. It is not a
direct measurement of GSUB CPU time. These separate-page totals also should not
be subtracted from the older combined-page benchmark as if they were a single
cost decomposition.

The reader report's tables, exact-check totals, profile values, and bounded
conclusions agree with the reviewed data. No substantive reporting issue was
found in that report.

### Completed matrix results

I independently read the final [correctness results](../gsub-shared-matrix-probe/results-correctness.json)
and [timing results](../gsub-shared-matrix-probe/results-timing.json). Both pass
with empty error lists. The full gate checks 3,263,232 output numbers: every
four-input vector and all sixteen rows in all three methods, then 1,128
sixteen-input and 1,320 sixty-four-input vectors. Every one of the 192 recorded
GSUB stage ablations changes the intact answer. These checks support the stated
exact finite-domain result; wider domains remain sampled.

The timing report contains 162 rows, each with 25 raw samples, of which the
first five are warmups. Every aggregate-to-update normalization is correct,
and all 972,000 observed outputs match the oracle. There are 54 distinct
configuration/repetition input seeds. I recomputed each timing row's statistic
from its raw samples and each of the 54 cross-repetition summaries; all agree.
The per-run statistic selects the upper middle of twenty measured samples.

At 64 inputs and sixteen outputs per vector, the median fixed-output batch
times are 9.2 ms for direct CSS, 72.2 ms for GSUB, and 24.8 ms for HVAR. The
corresponding one-vector repeated-update measurements are 0.5625, 4.48125,
and 1.4625 ms. HVAR's advantage over this GSUB implementation is consistent
across all three repetitions in both workload views. Direct CSS is fastest
in every tested configuration. The near tie between the two font methods at
four inputs and sixteen outputs is too close to motivate a general ranking.

The change from one to sixteen outputs per vector preserves 256 total outputs
in the fixed-output view but removes most input writes and independent font
states. The one-vector view confirms that producing additional HVAR output
glyphs is relatively cheap when they inherit an existing vector's settings.
These observations correct the earlier one-output comparison without isolating
arithmetic reuse from all other source-path work. They also do not introduce
sharing to GPT-2: that mechanism already exists in the implementation described
above.

The report's tables and counts agree with the reviewed raw data. Its limits
are appropriate: synthetic small integer weights, full affine simplification
allowed to competitors, font loading excluded, one sixteen-row HVAR font at
every active-row count, separate GSUB row fonts, and no claimed whole-model
speedup. No substantive correctness or timing-report issue was found.

### Reusable digits: current correctness, failure, and source evidence

The completed four-input gate checks all 65,536 vectors for both the new and
retained fonts and their direct-CSS controls. The wider gate checks 4,373
sixteen-input and 5,147 sixty-four-input cases per implementation. All pass,
including the recorded stage, atomic-run, and accumulator-marker controls.

The [256-input smoke attempt](../gsub-reusable-digits/smoke-w256.json) fails.
All first eight GSUB cases have a source width of zero, while direct CSS matches
all eight. The external reader faithfully decodes that zero into the same wrong
number for every case. Even the minimum-product vector fails: its expected
source width is only 65. This is not an overflow at the numerical boundary:
the maximum shifted sum is 10,560 and the maximum internally doubled value is
21,121, both within the four-digit representation. No failed font request or
browser console error is recorded. The current evidence establishes a failure
before final numerical readback; it does not alone distinguish input encoding,
font processing, or a shaping limit. A successful font build is not a successful
256-input browser computation. Width 64 is validated; this failed attempt does
not establish the first failing width between 64 and 256.

The source explains why storage reduction is not a promise of speed. The
[retained compiler](../../tools/build_gsub_weighted_sum_probe.py#L129) names each
node and digit position separately. Its contextual addition targets the class
for the particular right-hand digit being updated
([target](../../tools/build_gsub_weighted_sum_probe.py#L192)). In the
[reusable compiler](../../tools/build_gsub_reusable_digits.py#L53), every
ordinary digit position uses the same sixteen glyphs. Each repeated addition
targets that common class and checks surrounding accumulator/operand markers
to identify the intended position
([contextual rules](../../tools/build_gsub_reusable_digits.py#L87)). Many more
positions are therefore eligible at the target-class level, even though most
must fail the full context. The new representation also uses seven top-level
steps per merge instead of six. These are concrete structural differences,
not a measured attribution of browser CPU time to failed matches or scans.

The completed [width-64 coarse profile](../gsub-reusable-digits/profile-w64.json)
passes every output check. Across three measured batches of 256 outputs,
reusable digits spend 14.166 seconds in the browser's layout category versus
0.2016 seconds for the retained representation. Both record 769 style events.
Their elapsed totals are 14.318 and 0.318 seconds, respectively. This locates
most of the measured difference in a broad category containing the font source
work; it does not isolate font execution from the rest of layout. The profile
uses one warmup and three measured batches and is separate from the repeated
timing experiment.

All three completed timing repetitions show a large slowdown despite the
constant 262-glyph font. I independently checked every timing median against
its twenty measured raw samples, each font hash against the current artifact,
and the shared input seed within each comparison. All agree. Across the three
runs, 307,200 timed outputs pass, including the additional stable-nonce phase
in the first run. The common changing-nonce phase accounts for 230,400 outputs.
The first run measured that phase after a stable-nonce phase; later runs
measured only the changing-nonce phase. The report should retain that difference
in preparation rather than describe all three runs as identical procedures.

| Inputs | Reusable batch medians, runs 1 / 2 / 3 | Retained batch medians, runs 1 / 2 / 3 |
| ---: | ---: | ---: |
| 4 | 19.3 / 26.6 / 27.0 ms | 13.5 / 9.8 / 10.6 ms |
| 16 | 219.5 / 311.0 / 310.7 ms | 31.2 / 27.6 / 26.5 ms |
| 64 | 3,395.0 / 4,743.2 / 4,767.3 ms | 122.9 / 127.7 / 106.2 ms |

These are 256-output batches, with five warmups excluded. Variation is visible,
but the slowdown's direction and practical size are not ambiguous. At width
64 the ratios within individual repetitions range from about 27.6 to 44.9.
No claim of a precise universal slowdown factor is justified.

### Narrowing the 256-input failure

The [follow-up diagnosis](../gsub-reusable-digits/diagnosis-w256.json) shows that
the font loads and the counter-based CSS has content and counter-reset values.
Literal input text produces the same zero width, including with the reduction
feature disabled. Additional zero-width input characters do not rescue it.
The separate HarfBuzz 14.2.1 CLI retains all original input glyphs unchanged:
even the product substitutions have not run. This supports rejection of the
GSUB table before arithmetic, rather than a reduction stopping halfway or a
CSS input/readback failure.

The exact CLI release's [sanitizer source](https://github.com/harfbuzz/harfbuzz/blob/14.2.1/src/hb-sanitize.hh#L213-L227)
initializes a bounded checking allowance from table byte length times 64.
Range checks consume that allowance, and a rejected table is replaced with an
empty table. That makes additional unused table bytes a useful discriminator
for this hypothesis; the experiment must preserve the original failed font
and identify any padded font as a distinct diagnostic artifact. This source
is not verification of the precise library revision or compile options inside
the tested Chrome binary.

Independent parsing of the original TTF lookup arrays finds 379, 1,759, 7,279,
and 29,359 referenced subtables at widths 4, 16, 64, and 256. Their actual GSUB
table lengths are 12,464, 12,800, 14,144, and 19,520 bytes. Shared binary bodies
save storage but do not remove these repeated references.

There is also a separate [cumulative subtable limit](https://github.com/harfbuzz/harfbuzz/blob/14.2.1/src/hb-sanitize.hh#L114-L143)
of fewer than 16,384 references. The [lookup sanitizer](https://github.com/harfbuzz/harfbuzz/blob/14.2.1/src/hb-ot-layout-common.hh#L1380-L1396)
charges each lookup's subtable count against it. Width 256 exceeds this limit
regardless of additional table bytes. The emitted count follows `115*N - 81`;
width 144 is the first supported multiple-of-four width exceeding this
particular limit. Width 140 would be below the count limit, but that is not a
correctness result or proof that another limit would permit it. The largest
width validated by the full browser gate remains 64.

The completed [HarfBuzz table diagnostic](../gsub-reusable-digits/diagnosis-subtables.json)
and [browser threshold diagnostic](../gsub-reusable-digits/diagnosis-browser-subtables.json)
directly corroborate this limit. I reviewed both scripts and independently
checked all ten TTF hashes, lookup counts, and summed subtable counts. The
full-program padded GSUB tables contain the original bytes unchanged followed
only by zeros. Neither padding amount rescues the full program. The installed
HarfBuzz library reports no validated GSUB lookups for the original despite
the raw table containing 1,817.

In deliberately pruned diagnostic fonts with the same 1,817 lookup entries,
HarfBuzz accepts 16,383 subtable references and rejects 16,384. Both have ample
unused byte padding. Chrome shows the same boundary using only one seed glyph,
with reduction and dependent arithmetic disabled: Products followed by Publish
gives width 64 at 16,383 references and width zero at 16,384. Thus the rejection
does not require a long input or execution of the arithmetic program. This
matched boundary, the independent binary counts, and the primary source
provide strong evidence for the stated validation limit in these artifacts.

The pruned fonts deliberately omit arithmetic rules. Their acceptance is not
a repair of the original 256-input calculation, and they are not included in
the numerical success results. The original failed font remains unchanged.

### Final synthesis review

The combined [results](RESULTS.md) agree with the reviewed source and data.
They distinguish the reader intervention from total font-source cost, interpret
matrix sharing as an existing model mechanism, and separate compact storage
from execution speed. The reported file sizes match the actual files. Timing
tables preserve repeated-run variation instead of selecting favorable samples.

The width conclusion is properly bounded: the full browser gate validates 64,
the complete 256-input font fails, and the predicted 144-input count-limit
crossing is a source-derived constraint, not a newly tested numerical boundary.
The diagnostic rule-pruned fonts remain separate from working arithmetic.
No full-model speedup or precision claim follows from these experiments.
Two small reporting clarifications were requested: attribute the
reduction-disabled literal-text observation to Chrome, and document the first
timing repetition's additional stable-nonce phase. Neither changes the result.
No additional measurement is required by this audit.
