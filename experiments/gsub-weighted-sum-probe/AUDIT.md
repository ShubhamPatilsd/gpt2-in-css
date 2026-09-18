# Independent audit of the digit-composed weighted-sum experiment

Status: source, correctness, internal channels, corrected timings, and coarse profiles reviewed.

The question is whether a single browser text-shaping operation can combine many
independent input values using small arithmetic rules, retain the answer as glyph
state, and use it in a later arithmetic operation before publishing a CSS number.
Success would establish a connected arithmetic building block. It would not yet
establish a GPT-2 compiler, adequate model precision, or a model speedup.

## Numerical contract

For four inputs, each an integer in `[-8, 7]`, the requested operation is

```
S = 3*a - 2*b + 5*c + d
```

Its exact minimum is `-86`, attained at `[-8, 7, -8, -8]`; its exact maximum is
`79`, attained at `[7, -8, 7, 7]`. The subtraction and negative values must retain
their ordinary signed-integer meaning. A modulo result is a different contract.

If the four weights repeat, the bounds for the planned widths are:

| Inputs | Signed sum range | Shifted sum range | Minimum unsigned bits |
| ---: | ---: | ---: | ---: |
| 4 | -86 to 79 | 0 to 165 | 8 |
| 8 | -172 to 158 | 0 to 330 | 9 |
| 16 | -344 to 316 | 0 to 660 | 10 |
| 64 | -1376 to 1264 | 0 to 2640 | 12 |

A useful representation is to shift each product by its smallest possible value.
For example, `3*a` becomes `3*a + 24`, while `-2*b` becomes `-2*b + 14`. Each
shifted product is nonnegative. Their sum is `P = S + 86` at width four. The final
consumer subtracts the documented offset to recover `S`. This is an exact
representation of signed arithmetic; no signed result has been discarded.

The four input multiplication tables need only 16 entries each. The addition,
carry, routing, dependent operation, and final readout rules are additional and
must be counted. The proof against a full-vector lookup is in the generated
program, not just in the multiplication-table count.

An affine operation following the sum is a useful test of passing an internal
result to another operation. It must be described as an affine dependency test,
not a nonlinear activation or an MLP. Its exact range and required accumulator
bits must be derived separately. If the intended operation is, for example,
`2*S + 7`, its width-four range is `[-165, 165]`, wider than the sum itself.

The agreed first dependent operation is `F = 2*S + 1`, implemented internally as
`Q = 2*P + 1` and decoded as `F = Q - 2*offset`. Its width-four range is
`[-171, 159]`; the width-64 range is `[-2751, 2529]`. Four little-endian nibbles
are sufficient for every planned unsigned intermediate (`Q <= 5281`).

## What the old primitive already proves

The existing [arithmetic compiler](../../tools/build_gsub_arithmetic_probe.py)
enumerates 256 low-digit pairs and 256 high-digit pairs, carries from the low sum,
then packs a nine-bit answer. It does not enumerate every full pair of eight-bit
inputs. Its [report](../gsub-arithmetic-probe/RESULTS.md) records exhaustive native
CSS-counter input checks and exact final numeric readback.

That primitive starts with already interleaved digits:
`[a-low, b-low, a-high, b-high]`. A product lookup naturally emits grouped digits:
`[a-low, a-high, b-low, b-high]`. The new implementation must actually solve that
routing problem. Interleaving precomputed weighted products in JavaScript or CSS
would move part of the requested operation out of the font. Position-tagged
contextual rules or explicit local permutations are legitimate solutions, but
their costs belong to the font's size and execution measurements.

There is a standards trap in deleting the consumed left word: the OpenType
[multiple-substitution format](https://learn.microsoft.com/en-us/typography/opentype/spec/gsub#lookup-type-2-subtable-multiple-substitution)
requires a nonempty output sequence. `sub glyph by NULL` should therefore not be
assumed to be portable. One standard construction is to map the consumed digits
to a zero-width trash glyph, then use a ligature to absorb those trash glyphs
along with the first surviving digit, producing that same surviving digit.
Those cleanup rules belong in the implementation's cost accounting.

## Conditions for a genuine connected result

1. CSS supplies only the input integers, an optional test nonce, and documented
   encoding such as an offset. It must not supply weighted products or the sum.
2. Each input's fixed multiplication takes place through the font program.
3. Intermediate product and accumulator glyphs have zero advance. A line whose
   independent product glyph advances simply add up is a useful different
   mechanism, but does not establish connected digit arithmetic inside GSUB.
4. The dependent operation consumes the accumulated digit glyphs. It must not
   receive the result from CSS, external JavaScript, or a precomputed answer.
5. The final answer becomes a native CSS number through the actual geometry
   reader, and a dependent CSS width consumes that number. External readback
   alone is insufficient to show that the next native stage can use the answer.
6. The browser page has no runtime inference script. External automation may
   prepare inputs, create fixtures, time the operation, and check observations.
7. Glyph names, stage tags, lookup ordering, and readout rules make the dependency
   visible in generated source. Disabling multiplication, a reduction stage,
   carry processing, or the dependent operation must be able to break a chosen
   case that exercises that stage.

Disabling all arithmetic and splitting required input text across atomic
inline-blocks are additional useful negative controls. The existing experiment
already showed that glyph-state computation cannot cross those shaping boundaries.

## Correctness and timing checks

The width-four domain contains `16^4 = 65,536` vectors and is small enough to test
exhaustively. Larger widths should include independently constructed extrema,
all-zero and uniform inputs, cancellation, transitions across digit carries, and
deterministically seeded random vectors. The reference should evaluate ordinary
signed arithmetic independently of the font's offset/digit representation.

Every timed final output should also be checked. Compare exact integer geometry
and decoded signed CSS numbers; do not round observations to hide failed carries
or fractional font-metric errors. Keep the successful power-of-two units-per-em
and font-size convention from the earlier primitive unless a change is separately
validated. Input changes need not force different answers: distinct vectors can
have the same weighted sum, so record changed input coverage separately.

The strongest direct CSS baseline can consume its computed number directly. It
must not be forced through a font-specific geometry-to-number roundtrip that
GSUB needs but CSS does not. A matched-reader control is supplementary, not the
primary speed claim. Both primary paths should end at equivalent native numeric
consumption, and timing should include native input writes, encoding, shaping or
CSS arithmetic, required readout, and the final forced width observation.

Record full sample distributions, a stated warmup exclusion, alternating or
balanced execution order, and exact browser/hardware versions. Changing nonce
text prevents identical complete-string reuse but does not disable all browser
font caches. One shared browser benchmark at a time avoids competition among
agents. Compiling fonts should likewise not overlap benchmark timing.

Useful independent carry controls at width four are `[7, -8, 7, 7]`, which yields
shifted products `[45, 30, 75, 15]`, `P=165`, `Q=331`, and `F=159`; and four
copies of `-8`, which yield `P=30`, `Q=61`, and `F=-111`. Together they exercise
low-digit carries in reduction and carries at different digits in the dependent
doubling operation. A disabled phase must produce an incorrect result on a case
that uses it; it need not always produce zero width. No planned value requires
a carry out of the fourth nibble.

## Limits that must stay visible

Small pairwise tables can avoid exponential enumeration of a whole vector. They
still incur more digits, carry work, routing lookups, and intermediate glyphs.
A balanced reduction can shorten the arithmetic dependency chain while adding
routing complexity; the browser result must decide which is cheaper.

A tree's arithmetic depth and the actual font lookup count must be distinguished.
If every addition node gets its own ordered lookup group, both schedules still
execute a linear number of lookup groups. A logarithmic arithmetic tree does not
by itself establish logarithmic shaping passes. Sharing the same lookups among
independent nodes at each tree level would be an additional construction.

Ordinary OpenType glyph IDs and lookup indexing are finite, and text-shaping
engines have operation and expansion limits. A font successfully saved to disk
does not prove that the browser will execute the entire program. Validate each
width before timing and preserve the first failing artifact if a budget is hit.
The current [HarfBuzz limits source](https://raw.githubusercontent.com/harfbuzz/harfbuzz/main/src/hb-limits.hh)
documents such guardrails, but its current values are not proof of the exact
limits in the tested Chrome binary.

The four planned widths also differ from GPT-2 in precision and connectivity.
The inputs here have 16 values. Actual GPT-2 activations are not established to
fit that domain. One successful output does not demonstrate input reuse across
3,072 outputs or a whole following layer. Those are later gates.

## Implementation review

The first [compiler](../../tools/build_gsub_weighted_sum_probe.py) implements the
offset contract and four-digit representation described above. Its product
lookup has one entry for each of 16 values of each input. Shared nested
constant-addition lookups map a right digit to its sum with one left digit plus
carry. The routing contexts inspect the adjacent words; they retain each lower
temporary digit, including its carry, until all four digits have been processed.
Normalization then reduces temporary digits modulo 16, and standard ligatures
absorb the consumed left word. No weighted product is supplied by the harness.

The implementation batches independent tree nodes at a common level. Each level
uses four digit lookups, one normalization lookup, and one left-word absorption
lookup. Sequential reduction therefore needs `6*(N-1)` top-level reduction
lookups, while the tested power-of-two balanced tree needs `6*log2(N)`. The
seventeen nested addition definitions are shared across nodes, although their
mapping entries still grow with the number of nodes. This is an actual reduction
in top-level lookup passes, not just a relabeling of an arithmetic graph.

For this exact first compiler, counting its glyph allocations gives
`272*N + 196` glyphs and counting its emitted rules gives `1424*N - 1001` rule
statements. The width-four manifest agrees: 1,284 glyphs and 4,695 rules. These
are linear source-structure counts, not predictions of compressed font bytes or
execution time. The position tags are nevertheless expensive: width 64 needs
17,604 glyphs, and width 256 would need 69,828, above the ordinary 65,535-glyph
font limit given by the `uint16` glyph count in the
[maximum-profile table](https://learn.microsoft.com/en-us/typography/opentype/spec/maxp).
A 768-input extension of this unchanged representation cannot fit in
one ordinary font. Reusing more glyph identities is therefore a later design
requirement even if the planned width-64 gate passes.

After reduction, four digit operations and normalization compute `2*P+1`.
Final publication maps the result digits to place-value advances and separately
publishes the constant 64-pixel base. Using ordinary width addition at this final
readout is legitimate: the product and reduction glyphs before publication all
have zero advance, and the dependent operation requires the completed sum's
glyph state. No full weighted-sum answer table appears in the compiler.

The first source review caught a repeat of an earlier construction issue: an
entirely empty outline table, including `.notdef`, previously failed Chrome's
font sanitizer. The compiler author was notified before the browser gate to
restore the small `.notdef` triangle used by the working arithmetic probe. The
arithmetic glyphs themselves can stay invisible.

The [browser harness](../../tools/test_gsub_weighted_sum_probe.mjs) independently
computes `S` and `2*S+1` in the external Node process. Its correctness checks
compare source width, the decoded CSS number, and the dependent consumer width.
The consumer has enough positive offset that negative results cannot silently
clamp to zero width. The direct CSS control computes and consumes its number on
one element, avoiding the unnecessary geometry readback identified in the older
depth benchmark. Timings require a full passing correctness report for the same
font bytes and check every timed result.

## Browser correctness review

I independently read `results-correctness-w4.json` and
`results-correctness-wide.json`. Both report success with no errors. The two
width-four schedules each pass all 65,536 input vectors. Each schedule also
passes 4,245 width-eight cases, 4,373 width-16 cases, and 5,147 width-64 cases.
Those wider suites include all single-coordinate values against zero,
deterministic random inputs, extrema, cancellation, and boundary sums. They are
sampled tests, not exhaustive checks of the larger domains.

Both source geometry and native CSS consumption match exactly. Each phase can
be disabled to change a known control result. The wider results additionally
compare an intact character string against the same characters split into
atomic inline-blocks: the intact string has the expected positive width while
the split version publishes no arithmetic answer.

The [HVAR control compiler](../../tools/build_gsub_weighted_sum_hvar_control.py)
correctly folds the affine continuation into its weights. With axis range
`[-8,8]`, deltas `-16*w` and `16*w` produce `2*w*x`; the default metric contributes
the constant one. The same native numeric consumer decodes its output. The
separate HVAR correctness report passes all 65,536 width-four cases and the same
wider suites. This is a legitimate competing implementation for this affine
function, even though it does not perform separate connected GSUB stages.

## Sharing inputs among four channels

The later `w4-fanouttree` source supplies each raw input once. A product lookup
expands it into sixteen glyphs: four digits for each of four fixed products.
Two input-reduction levels then keep the four channel sums separate. Carry is
reset at each channel boundary. A following lookup exposes the four resulting
words, and two more reduction levels add the channels before the dependent
double-plus-one operation. The input is copied inside the font, not by writing
four independent CSS counter inputs.

The channel weight rows are `[3,-2,5,1]`, `[-1,4,2,-3]`, `[2,1,-2,5]`, and
`[5,-2,1,2]`. Their sum has effective weights `[9,1,6,5]`, so the harness's
collapsed arithmetic oracle is correct for the final result. However, checking
only the final sum cannot independently establish all four channel answers: a
channel permutation, for example, would preserve that sum. An additional
intermediate-glyph check was therefore requested before describing the four
channels as independently validated. That check must be distinguished from
Chrome's final native input/output test if it uses a separate HarfBuzz binary.

That additional [intermediate verifier](../../tools/audit_gsub_weighted_sum_intermediates.py)
has now passed. I reviewed both its source and `fanout-intermediate-audit.json`.
It checks all 65,536 input vectors and all four channel answers independently:
262,144 exact channel checks, with no failures. It verifies the number, order,
position tags, and values of the sixteen surviving digit glyphs before decoding
the four words. Its expected matrix and arithmetic are independent of the
compiler's collapsed final row.

This intermediate observation uses HarfBuzz 14.2.1. That local binary did not
accept WOFF2, so the verifier uses the original TTF and first checks that its GSUB
table bytes, glyph order, character mapping, and horizontal metrics exactly
match the browser WOFF2. Every equivalence check passes. This strengthens the
internal-channel evidence while remaining explicitly a separate engine build
from Chrome's native final-result test.

## Timing correction before interpretation

The first timing attempt seeded both phases with the same random input sequence.
The second phase therefore replayed the first phase's vectors. A large HVAR
improvement between those phases could reflect warmed font-variation caches;
it could not be attributed to changing the nonce. Those measurements were
preserved as an attempt and replaced by measurements with a distinct
deterministic input seed per phase, shared across the competing implementations.
The correctness results are unaffected.

The corrected harness now uses the phase name `stable-nonce`: the nonce stays
fixed while input vectors change randomly. The earlier `repeated-state` label
did not mean deliberately repeating complete input vectors. `unique-text`
changes both the random inputs and the nonce. No claim that the latter disables
all internal caches is justified.

The HVAR control also remains a synthetic workload: 256 different input vectors
produce one output each. GPT-2's real dense stages reuse one input vector across
many output rows. Its timing is therefore a comparison of mechanisms on this
experiment, not a measurement of the existing full dense layer.

I independently read the completed corrected `results-timing.json` and
`results-hvar-timing.json`. Both pass with no errors or mismatched timed outputs.
Each timing row reports 35 measured samples after five warmups, with 256 outputs
per sample. The corrected changing-nonce medians include:

| Width / function | GSUB running total | GSUB balanced tree | Direct CSS in GSUB run |
| --- | ---: | ---: | ---: |
| 4-input sum and continuation | 10.7 ms | 11.3 ms | 3.2 ms |
| 8-input sum and continuation | 16.4 ms | 17.4 ms | 4.5–4.6 ms |
| 16-input sum and continuation | 27.8 ms | 31.0 ms | 7.0–7.3 ms |
| 64-input sum and continuation | 107.8 ms | 186.6 ms | 22.1–22.3 ms |
| Four inputs, four channels, combined continuation | — | 22.8 ms | 3.0 ms |

The separate corrected HVAR run reports 28.6, 39.0, 60.7, and 286.9 ms at widths
4, 8, 16, and 64 respectively, with paired direct CSS medians 3.4, 4.6, 7.5, and
22.9 ms. These separate runs support the synthetic mechanism comparison under
their recorded conditions; they are not paired measurements of complete model
implementations.

The arithmetic and connectivity gates pass. The proposed balanced tree is
slower in this implementation despite fewer top-level lookups, and neither
GSUB schedule beats direct CSS on the tested affine function. Those are the
supported conclusions. The timing alone does not isolate whether rule matching,
glyph-buffer processing, style resolution, or another browser activity causes
the difference. A separate profile is needed for narrower cost attribution.

## Coarse profile review

The completed `results-profile.json` and `results-hvar-profile.json` both pass
with no mismatched outputs. They record Chrome performance-counter deltas over
20 measured batches after five warmup batches. Dividing those deltas by 20 gives
the following values per batch of 256 outputs at width 64:

| Implementation | Measured elapsed | Recorded style time | Recorded layout time |
| --- | ---: | ---: | ---: |
| GSUB running total | 110.9 ms | 33.3 ms | 69.6 ms |
| GSUB balanced tree | 190.8 ms | 33.8 ms | 149.1 ms |
| HVAR control | 286.8 ms | 14.0 ms | 265.8 ms |
| Direct CSS, paired with running total | 22.3 ms | 14.8 ms | 0.8 ms |
| Direct CSS, paired with tree | 21.7 ms | 14.4 ms | 0.8 ms |
| Direct CSS, paired with HVAR | 22.7 ms | 14.9 ms | 0.9 ms |

These are averages from separate profiling runs, not replacements for the
earlier timing medians. The recorded tree-versus-sequential difference is almost
entirely in the layout category: layout increases by about 79.5 ms per batch,
while style increases by about 0.5 ms. It is therefore supported to say that
the tree's extra time appears under browser layout work. These broad counters
do not isolate font matching, buffer manipulation, individual lookup costs, or
any one explanation for that work.

Across the 20 measured batches, each font path records 5,121 style recalculation
events, while its direct CSS comparison records 20. All paths record 20 layout
events. These are counts of events, not counts of individual elements restyled;
they do not establish the exact cause of the extra recalculations. The final
font-to-CSS reader remains part of the measured font paths.

The metrics use browser time counters, not a dedicated CPU profiler of the font
engine. `TaskDuration` spans more than the in-page timed region and can include
protocol work. `ScriptDuration` is zero in these reports, but that is not evidence
that the external DevTools-driven mutation and observation loops cost nothing.
The current [Chromium performance-agent implementation](https://raw.githubusercontent.com/chromium/chromium/main/third_party/blink/renderer/core/inspector/inspector_performance_agent.cc)
tracks script, layout, style, and DevTools-command accounting separately; its
source is supporting context, not a verification of the exact source revision
embedded in the tested Chrome binary.

## Final report review

The numerical ranges, font sizes, rule and glyph counts, correctness totals,
corrected timing medians, and coarse profile figures in `RESULTS.md` agree with
the reviewed source and result files. One wording distinction was sent back to
the report author: correctness cases separately observe source width, decoded
CSS number, and consumer width; timed and profiled samples validate the consumer
width. The three separate observations should not be attributed to every timed
sample.

The proposed next steps are proportionate to these results. Separating source
width measurement from complete native numeric readback can identify how much
the output boundary adds, provided the compared workloads preserve input-write
cost and output count. A diagnostic font supplied with an already computed
answer can help isolate that boundary but cannot substitute for a complete
arithmetic benchmark. A shared-input matrix comparison is also needed before
inferring anything about the existing model matmul path from the current HVAR
control. Reusing glyph identities addresses a demonstrated size limit, but
requires renewed correctness and performance checks. None of those proposed
follow-ups is recorded as a completed experiment.
