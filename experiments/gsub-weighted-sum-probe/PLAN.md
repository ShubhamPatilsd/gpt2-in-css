# Connected weighted sums inside a font

This is a new experiment, separate from prior GPT-2 measurements.
The earlier depth circuit carried two four-bit integers; this experiment makes
several signed inputs contribute to one result, using small digit operations.

## Questions

1. Can four signed inputs produce an exact weighted sum inside glyph state,
   without a lookup table covering all input combinations?
2. Can that sum feed another operation inside the same shaping run before it
   becomes a numerical CSS value?
3. Does a running total or a pairwise reduction scale better in this browser?
4. Can several outputs reuse the same inputs and feed a following calculation?

## Execution plan

### A. Establish a numerical and browser contract

- Start with four integers in [-8, 7] and weights [3, -2, 5, 1].
- Store products and intermediate sums with multiple small digit glyphs, with
  enough signed range for all tested inputs. Document carries and sign handling.
- Generate the multiplication mappings from each fixed weight individually.
  Do not tabulate answers for all four inputs jointly.
- Apply a second dependent operation in the font. Its exact definition and
  range will be recorded in the generated manifest before testing.
- Feed inputs through native CSS counters. Decode the final font measurement
  into a CSS number and consume that number in a dependent width.
- Use CSP script-src 'none' for the runtime page. External harness JavaScript
  may prepare cases, supply raw inputs, observe results, and check correctness.

### B. Exhaustive correctness before timing

- Check all 16^4 = 65,536 input vectors against an independent arithmetic oracle.
- Observe both the CSS number and dependent final width exactly.
- Break the connecting font feature and require the final result to fail.
- Include checks that distinguish internal arithmetic from merely adding final
  glyph advances in ordinary text layout.
- Preserve failed attempts and explain fixes; do not loosen tolerances.

### C. Widen and compare ways of adding

- Target widths 4, 8, 16, and 64 with repeating fixed weights.
- Compare a sequential running total with pairwise addition where the same
  numerical representation permits both.
- Wider tests include seeded random inputs, extremes, cancellation, long carries,
  and individual input changes that must affect the selected output.
- Record font bytes, glyphs, rules, lookups, and shaping buffer growth.
- If building or shaping exceeds a practical bound, preserve that failure as
  a scaling result rather than silently substituting a different computation.

### D. Fair complete-path measurements

- Compare with direct CSS for the same arithmetic and result range. CSS consumes
  its final numbers directly; do not add an unnecessary font-style round trip.
- Time native input writes through forced reads of the dependent output.
- Prepare stimuli and reference answers outside the interval. Report batch size,
  warmup, raw samples, medians, and measurement order.
- Alternate backend order and separate correctness from timing runs. Include
  fresh text if practical; do not claim that a nonce disables all internal caches.
- Run browser experiments one at a time with run_unconventional_isolated.py.
  Parallel agents may develop and review independent code, but must not compete
  for CPU during measured browser runs.
- Also include a context control using the existing variable-font (HVAR)
  mechanism. The initial function 2*sum(w*x)+1 is affine and can be folded into
  fixed font weights. Let that control perform this legal simplification; do
  not force it to emulate the internal digit circuit.

### E. Test sharing and a second connected calculation

- After the basic representation works, attempt four inputs producing several
  weighted outputs that feed one more calculation without intermediate CSS reads.
- Check numerical correctness, the internal connection, and growth separately
  from whether the construction is fast.
- A practical failure in the earlier gates may change the representation here;
  document that decision explicitly rather than claiming model integration.

## Initial decisions and correctness gate

The chosen dependent operation is `F = 2*S + 1`. It is a routing/dependency test,
not a nonlinear activation. Each fixed weighted product is shifted by its
minimum possible value so all internal digits are nonnegative; subtracting the
known combined offset at the final reader recovers the exact signed result.
Products and intermediate sums use four base-16 digits with zero advance.

At width four, both sequential and tree programs passed all 65,536 input vectors
and feature-disable controls. The tree batches independent additions at each
level into six top-level passes. The running-total program uses six passes for
each successive addition. Detailed correctness data is retained in
`results-correctness-w4.json`; timings are a separate stage.

The current construction uses position-tagged symbols, with `272*N+196` glyphs
for N inputs. This is linear growth, but it would exceed the ordinary 65,535
glyph limit at N=241. Passing width 64 would not justify saying this exact
representation can reach 768; reducing symbol duplication would be another step.

## Deliverables and interpretation

Generated fonts and rule files, an executable compiler and browser harness,
machine-readable results, an independent audit, and a report explaining the
observed limit in plain language. Retain source/artifact hashes and environment.

Passing arithmetic proves connectivity under this numerical contract. It does
not establish GPT-2 precision. Beating direct CSS on this operation establishes
a component result only. Any replacement for existing model matmuls also needs
a comparison against the current HVAR font path and a full model measurement.

## Completion

All five stages above were run. Both addition methods passed through 64 inputs;
the four-input sharing circuit and variable-font control also passed. The new
digit circuit was slower than direct CSS in this sweep. Separate profiles place
most additional time in layout. See [RESULTS.md](RESULTS.md) for measurements,
the corrected timing methodology, size limits, and proposed next experiments.
