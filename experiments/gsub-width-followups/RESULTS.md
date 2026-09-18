# What the three experiments establish

All three experiments are complete and independently reviewed. Returning the
answer to CSS is a small part of the wide digit circuit's cost. Sharing inputs
substantially helps the variable-font method, and the model already uses that
mechanism. Reusing every digit symbol makes a much smaller but much slower
program, and the 256-input version exceeds a confirmed font-validation limit.

The three questions are different. A small font file need not execute quickly;
sharing inputs can change the ranking between implementations; and expensive
browser layout need not mean that the final CSS reader is expensive.

## 1. Returning the answer to CSS is not the main wide-circuit cost

We compared two versions of the same calculation. One stops after measuring
the font's answer as a width. The other turns that width into a CSS number and
uses it in a following calculation. Both receive identical raw inputs; each
observer reads one output per case. Only the second version supplies a reusable
CSS number, so the first is a diagnostic, not a replacement implementation.

At 64 inputs, in milliseconds per 256 outputs:

| Addition method | Stop at source width | Return and consume CSS number | Paired additional cost, range across three runs |
| --- | ---: | ---: | --- |
| Running total | 73.0 | 76.6 | 3.10–4.20 |
| Add in pairs | 130.8 | 135.3 | 3.30–5.10 |

Displayed totals are medians across independent browser-run medians. The paired
cost comes from matched individual samples, not subtraction of the displayed
totals. Ordinary fonts given an already-computed answer also showed a few-ms
reader cost. Those controls are explicitly diagnostic: they receive an answer
from the test driver and do not perform native arithmetic.

The variable-font pairs remained around 200 ms even without the reader. Their
small source/full differences changed sign between repetitions, so their exact
reader increment is unresolved. They also reject the explanation that returning
the answer accounts for most of the total.

The source-only path still includes raw writes, input encoding, styles, font
shaping and measuring the source. This experiment isolates the reader's effect;
it does not measure pure font CPU time. A separate profile confirms that the
large difference between the two addition methods remains under layout even
when the reader is removed.

**Decision:** optimizing the final reader alone cannot solve this wide-circuit
slowdown. It matters more for small calculations, where a few ms is a larger
fraction of the total. See the [reader report](../gsub-reader-isolation/RESULTS.md)
for all widths, controls, per-run values and profiles.

## 2. Sharing inputs changes which font method is faster

The previous comparison made each independent input vector produce just one
answer. A matrix calculation usually asks the same inputs to produce many
answers with different weights.

We tested that explicitly. Each vector's inputs are written once to a parent,
and every output inherits them. The variable font has one set of input axes
and several output glyphs. The digit-based font method uses a separate arithmetic
font for each row. Direct CSS calculates the same rows directly. All methods
return and consume numerical answers.

At 64 inputs, keeping the batch at 256 total output numbers:

| Outputs produced by each vector | Independent vectors | Direct CSS | Digit-based row fonts | Shared variable font |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 256 | 18.1 ms | 81.3 ms | 216.3 ms |
| 4 | 64 | 11.3 ms | 73.8 ms | 64.0 ms |
| 16 | 16 | 9.2 ms | 72.2 ms | 24.8 ms |

The font-method ranking reverses. With sixteen outputs sharing each input
vector, the variable font is about 2.9 times faster than the tested digit fonts.
Direct CSS remains fastest on this small synthetic arithmetic.

Increasing outputs per vector also reduces input writes in the fixed-output
batch: from 16,384 input properties to 1,024 at these two endpoints. All methods
get the same reduction. We therefore also tested one vector updated repeatedly,
forcing every answer after every update. Its complete 64-input, sixteen-output
cost was about 0.56 ms for CSS, 4.48 ms for digit fonts and 1.46 ms for the
variable font. Each timing sample aggregates 32 changing updates to reduce
clock rounding; this is steady update cost, not a cold latency distribution.

This result is **a correction to the comparison, not a newly added model
optimization**. The current GPT-2 code already shares input-derived font
settings across output glyphs. The matrix [report](../gsub-shared-matrix-probe/RESULTS.md)
links the concrete compiler/runtime locations, including the four shared input
packs used by a 3,072-input stage.

**Decision:** retain the shared variable-font path as the relevant matrix
baseline. The independent-one-output test understated that mechanism's value.
There is no measured reason here to replace it with separate digit-font programs.

## 3. Reusing all digit symbols removes a size problem but creates a costly program

The original font used different symbols for each position and intermediate
result. The new version uses one common digit alphabet and markers identifying
the active running total and next number. The arithmetic and final CSS reader
remain the same.

At 64 inputs, the original font has 17,604 glyphs and a 40,352-byte compressed
file. The replacement has 262 glyphs and a 2,664-byte file. It passes all 65,536
four-input vectors, plus the sampled sixteen- and sixty-four-input suites and
controls that break the markers or arithmetic stages.

All three fresh-text timing repetitions are substantially slower. Times are
milliseconds per 256 outputs; brackets give the range of browser-run medians.

| Inputs | Original position-specific symbols | Reused symbols |
| ---: | ---: | ---: |
| 4 | 10.6 [9.8–13.5] | 26.6 [19.3–27.0] |
| 16 | 27.6 [26.5–31.2] | 310.7 [219.5–311.0] |
| 64 | 122.9 [106.2–127.7] | 4,743.2 [3,395.0–4,767.3] |

At 64 inputs, the new representation took approximately 28–45 times as long
as the retained representation in their respective runs. Machine conditions
varied, including a run spanning the user interruption. The large direction
is consistent; the exact multiplier is not a universal constant. These
comparisons are within this experiment; absolute values should not be mixed
with the reader experiment's different fixture setup.
The first run included a fixed-nonce phase before its fresh-text phase; later
runs measured fresh text only because this version was slow. The comparison
above uses fresh-text results throughout, with independently seeded inputs.
The local report preserves that protocol change and each harness hash.

The source code gives a reason that fewer glyphs need not mean less work. The
original rules identify the intended operand partly through its unique glyph
identity. The replacement's target class contains every ordinary digit, so
many positions qualify initially; surrounding markers must reject the wrong
ones. It also adds a step to each addition. These are source facts and a
plausible explanation, not a measured attribution of each CPU cycle. The
separate browser profile puts nearly all the extra time under layout.

The 256-input font builds with 262 glyphs and a 3,664-byte compressed file, but
its browser smoke test fails. The first eight cases all produce zero source
width, including a case whose correct width is 65 pixels. Direct CSS returns
the correct answers. The arithmetic range fits the four-digit representation,
and the error precedes the final CSS reader. Literal-text delivery fails too,
including browser probes with the reduction phase disabled. The separate
HarfBuzz engine leaves all input glyphs unchanged. Its table-availability probe
confirms rejection of the calculation table before arithmetic starts.

We narrowed that rejection to a specific limit. The 256-input program has
29,359 references to substitution subtables. A subtable is a group of rules;
referencing the same group repeatedly still counts repeatedly. The corresponding
64-input program has 7,279 references. Small physical size does not remove
this logical repetition.

The independent HarfBuzz 14.2.1 library rejects a cumulative count of 16,384 or
more. Controlled diagnostic fonts kept all 1,817 lookup entries but removed
rules to vary the subtable-reference count: 16,383 was accepted, while 16,384
was rejected. A Chrome probe showed the same boundary: accepted diagnostic
fonts executed a simple product/publication path; rejected ones returned zero
width. Adding unused table bytes did not rescue the complete 256-input program.

These diagnostic fonts deliberately omit arithmetic rules. They identify the
rejection and are **not repairs or successful 256-input calculations**. The
complete program remains unchanged and failing. The limit is documented in
[HarfBuzz's table validator](https://github.com/harfbuzz/harfbuzz/blob/14.2.1/src/hb-ot-layout-common.hh#L1380-L1396)
and [its count bound](https://github.com/harfbuzz/harfbuzz/blob/14.2.1/src/hb-sanitize.hh#L140-L143);
the browser behavior was checked separately rather than assumed from that
library version.

For this compiler, the reference count is `115*N-81`. That predicts this guard
will be exceeded at 144 inputs, the first such multiple of four. It does not
prove that every smaller width works: full correctness was established through
64, and intermediate widths were not tested.

**Decision:** do not substitute this globally reused-symbol program for the
existing calculation. It saves file space while greatly increasing runtime,
and its current rule organization cannot reach the intended width. A further
experiment would need to reduce repeated rule checks and table references,
not merely shrink the alphabet. Partial reuse within small groups or a different
organization of the rule tables are hypotheses to test, not demonstrated fixes.
See the [compact-symbol report](../gsub-reusable-digits/RESULTS.md) for retained
attempts, hashes, diagnostics and reproduction commands.

## How strong the conclusions are

All three experiments preserve exact signed integer inputs from -8 through 7.
The reader and reusable-symbol studies use repeating weights `[3,-2,5,1]`;
the matrix study uses distinct deterministic rows from `{-3,-2,-1,1,2,3}`.
Their timing tables therefore answer their own controlled comparisons; they
are not three measurements of an identical workload.

Correctness runs precede timing and use separate browsers. Timings use fresh
browser repetitions, distinct input seeds, warmups and matched stimuli between
compared implementations. Every timed answer is checked. Browser work and font
builds use the common advisory lock. Other activity and machine power state
remain uncontrolled, so per-run variation is retained rather than hidden.

The matrix study alone checks 3,263,232 full-gate outputs and 972,000 timed
outputs. Reader correctness checks all four-input combinations for each
condition and samples wider inputs. Wider domains are not exhaustively tested.
The independent [audit](AUDIT.md) checks controls, raw samples, summaries and
the distinction between source evidence and performance attribution.

These tests resolve local representation and measurement choices. They do not
establish GPT-2 numerical accuracy, nonlinear-layer performance or token speed.
The full [plan](PLAN.md) and separate reports retain the reproduction commands,
font/source hashes, raw timings, successful gates and failed attempts.

## Completed follow-up

The subsequent [partial-reuse and rule-organization experiment](../gsub-partitioned-digits/RESULTS.md)
tests the recommendation above. Partial reuse improves the slow global alphabet,
and grouping rules repairs the 256-input capacity failure, but the resulting
digit program remains too slow to replace the shared variable-font benchmark.
The follow-up also corrects the scope of the cheap-reader finding: one final
sum reader does not represent the model's thousands of intermediate handoffs.
