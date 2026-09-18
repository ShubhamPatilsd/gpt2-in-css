# Experiments to explain and reduce the cost of wider font calculations

The previous experiment established exact arithmetic through 64 inputs, but its
complete font path was slower than direct CSS. Fewer successive font passes did
not predict speed. These experiments separate three questions rather than infer
an explanation from one broad browser timing category.

## Shared rules for all three experiments

- Preserve the previous fonts and reports. Write new experiments separately.
- Use signed integer inputs from -8 to 7 and independent integer arithmetic as
  the oracle. Every measured output must match exactly; no tolerance changes.
- Browser computation pages contain no scripts. External drivers supply raw
  inputs and observe results. Any control supplied with an answer is explicitly
  a diagnostic, never a native computation result.
- Check new representations exhaustively at four inputs. At wider sizes, check
  extremes, every coordinate individually, carry boundaries, cancellation and
  independently seeded random vectors. Wider checks are not exhaustive.
- Run font builds and browser experiments under the common advisory lock.
  Agents may edit and review concurrently; CPU-heavy measurements are serial.
- Use at least three fresh-browser repetitions, independently seeded inputs,
  five warmup rounds and at least twenty measured rounds. Balance condition
  order and retain raw samples, seeds, hashes and browser/machine versions.
- Close the exhaustive-correctness browser before timing. Use the same small
  precheck in every fresh timed browser, avoiding asymmetric cache warming.
- For single-vector latencies, aggregate 32 changing updates per sample,
  forcing every answer on each update and checking them all outside the timer.
  Divide by 32; do not derive ratios from individual zero-duration samples.
- Distinguish total inputs written, independent vectors, outputs, and internal
  arithmetic. These must be matched within a claimed comparison.
- Report repeated-run ranges and direction consistency. Small or inconsistent
  differences are inconclusive; do not select one favorable run.
- Use coarse browser profiles only to locate categories of work. Layout is not
  a direct measurement of font CPU time, and style-event counts are not counts
  of affected elements.

## 1. Separate internal computation from returning a number to CSS

Root owns `tools/test_gsub_reader_isolation.mjs`, its simple-font builder and
`experiments/gsub-reader-isolation/`.

For each of 4, 16 and 64 inputs, compare the retained running-total font,
pairwise font, and variable font using two separate fixture documents:

1. **Source width only:** supply raw inputs and force the source's width.
2. **Complete reader:** supply identical raw inputs, convert source width through
   anchor size and container units to a CSS number, and force the same dependent
   consumer used previously.

Only the second path supplies a reusable CSS number. The first is a diagnostic
endpoint, not a replacement implementation. Keeping paths in separate pages
prevents an unused reader from executing in the source-only condition.

Add two controls receiving the precomputed answer outside the timed interval:
one ordinary static font whose selected glyph already has the answer's width,
and one CSS width already containing the answer. Both still receive all raw
input writes. Source/full pairs have identical writes, including the additional
answer property. Their subtraction estimates the reader's incremental cost
under those specific fixtures; it is not a pure isolation of font execution.

Also retain direct CSS arithmetic, consuming its number directly, as a complete
computing baseline. This keeps a diagnostic source-only shortcut from being
mistaken for an end-to-end speedup.

Decision: if most time remains with no reader, focus on the source font path.
If the reader adds most of the time consistently, focus on numerical transport.
If costs interact, report that rather than assuming independent additive costs.

## 2. Many outputs sharing one input vector

The shared-matrix worker owns `experiments/gsub-shared-matrix-probe/` and its new
builder/harness. Detailed local plan records the final matrix sizes.

Compare input counts 4, 16 and 64 and output counts 1, 4 and 16. Each row of
weights must be distinct. Each vector's raw inputs are written once to a parent;
its outputs inherit them. HVAR uses one font with many output glyphs, permitting
font settings to be shared. The GSUB implementation must document how it shares
inputs and whether separate rows still require separate shaping programs.

Run two workload views: 256 total outputs, so vector count is 256/output-count,
and one vector producing the selected number of outputs. The former controls
total outputs; the latter shows practical per-vector cost. Neither comparison
should silently conflate fewer input writes with faster arithmetic.

Every output returns a usable CSS number. Compare the same matrix using direct
CSS, GSUB and HVAR. Let competitors simplify the final affine expression. Check
all rows independently, not only a combined sum that could hide row errors.

Decision: establish whether the earlier one-output HVAR result survives this
more relevant workload. Identify crossover only within measured sizes.

## 3. Reuse digit symbols instead of naming every intermediate position

The reusable-symbol worker owns `experiments/gsub-reusable-digits/` and its new
compiler/harness. Begin with shared digit symbols and explicit routing markers,
keeping the signed range and internal dependent calculation unchanged.

First prove four-input arithmetic, carries, and phase dependence. Then compare
4, 16 and 64 inputs with the retained running-total circuit under the same
native input encoding and full CSS reader. Record actual glyph counts, rule
counts, compressed bytes and successive lookup passes separately from speed.

If correctness and size gates pass, build and test 256 inputs, beyond the old
representation's glyph limit. Preserve any compiler or browser limit as an
observed result. Reaching 256 is not permission to claim 768-input support or
GPT-2 precision. No whole-input answer tables are allowed.

Decision: determine independently whether symbols can be reduced, whether that
permits a wider exact calculation, and whether it improves total update time.

## Final synthesis

An independent agent reviews the controls, numerical gates and conclusions.
The final report states what each intervention caused in the measured browser,
what cannot yet be separated, and which next implementation is justified.
These experiments can settle the local design choices. They cannot establish
full-model token speed without integrating and measuring the model.

## Completion

The three planned experiments were implemented and run. Each timing comparison
has three fresh-browser repetitions. Reader and matrix gates pass; the reused
digit program passes through 64 inputs but its unmodified 256-input font fails.
Additional controlled probes identify rejection at 16,384 referenced GSUB
subtables. They diagnose the failure without substituting a weakened arithmetic
program for the requested calculation. See [RESULTS.md](RESULTS.md) for the
combined decisions and [AUDIT.md](AUDIT.md) for independent review.
