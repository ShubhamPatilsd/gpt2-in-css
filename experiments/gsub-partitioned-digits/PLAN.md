# Partial digit reuse and rule organization

Started 2026-09-17 (America/Los_Angeles). This continues the completed
[width follow-ups](../gsub-width-followups/RESULTS.md). The goal is faster,
correct autonomous GPT-2 generation in an unmodified browser with no runtime
JavaScript computation. A synthetic font result is a gate toward that goal,
not a substitute for a model measurement.

## Questions and comparisons, declared before measurements

1. Does reusing digits only within the same base-16 digit position reduce the
   matching work caused by a single global digit alphabet?
2. Can the same arithmetic be stored in fewer rule subtables without changing
   its answers, and does this repair the known 256-input rejection?
3. After those changes, does the complete operation compete with the shared
   variable-font implementation when one input vector produces many outputs?

Use a sequence of controlled comparisons: the retained position-specific
program; the previous globally shared alphabet; a position-within-number
alphabet with otherwise similar rules; and the same new alphabet with compact
class-based rule tables. A direct CSS calculation and a shared HVAR variable
font are the performance baselines. Preserve unsuccessful variants and explain
which factor differs between any two compared programs.

Arithmetic remains signed inputs from -8 through 7 and the existing weighted
sum followed by `2*sum+1`. The first comparison retains repeating weights
`[3,-2,5,1]`. A many-output test must disclose whether rows are distinct. Copies
of the same row are useful for an isolation control but do not demonstrate
general matrix performance. Do not silently compare different arithmetic.

## Gates

Build widths 4, 16 and 64. Check font structure and standalone shaping before
browser timing. Try 256 only for a structurally viable representation. Inspect
actual compiled subtable counts; compressed file size alone is not evidence
of acceptance or speed. Do not change browser validation limits.

Exhaust all 65,536 four-input vectors. At larger widths check signed extrema,
single-coordinate changes, cancellation/carry cases and deterministic random
vectors. Verify the final CSS number and a following calculation consuming it,
not only the source text width. Disable required arithmetic stages to confirm
that the page really uses the font program. Keep any failed output and its
expected value. Sampling is not an exhaustive proof at larger widths.

Only correct candidates advance to timing. Use separate correctness and timing
browsers, three fresh timing-browser repetitions, recorded independent seeds,
matched raw inputs, changing text, warmups and balanced comparison order.
Measure raw input publication through forced downstream output; generate inputs
and compute the oracle outside the timer. Retain every sample and check every
observed answer. Record font and harness hashes.

Run the cheap single-output screen first. Then use 64 inputs and 16 outputs
sharing the input vector, with the variable-font settings inherited once.
Bound slow cases by smaller equal batches or fewer predeclared samples, with
the difference disclosed. Do not allow a known slow candidate to occupy the
machine indefinitely. This is a focused experiment, not an exhaustive search
over all font encodings.

## Attribution and stopping rules

A smaller font is a storage result. Fewer rule tables are a structural result.
A correct 256-input browser answer is a capacity result. Only measured elapsed
time establishes a speed result. None alone establishes a token speedup.

If compact rules repair width but remain slower than the shared variable-font
baseline, retain the capacity finding and stop promoting this implementation
as a matrix replacement. If a candidate wins, the next gate is a real model
stage with all inputs changing and its actual downstream consumer, followed
by a matched autonomous model comparison. No production backend switch occurs
on the strength of these synthetic tests.

## Parallel work and machine isolation

Three agents independently own the compiler, browser harness, and progress/
evidence audit. The root agent owns this plan, alternative-direction research,
and the final synthesis. Builds and browser experiments use the repository's
common advisory lock, so parallel preparation does not become concurrent
performance measurement. Existing artifacts and failed runs remain intact.

The progress audit will distinguish historical system-level improvements from
recent component results, identify missing measurements, and propose a next
experiment with a clear reason it could affect token time.

## Amendments before the final correctness gate and timing

The audit identified a useful different affine control: give each encoded input
glyph the width of its fixed weighted contribution and let ordinary text layout
sum those widths. The affine continuation is folded into those advances, as it
is allowed to be folded into CSS and HVAR. This uses no digit arithmetic and
does not preserve an intermediate sum inside the font. Add it to the same
matched inputs/reader/timing protocol, explicitly labeled as a static-width
affine control. Its tiny alphabet exploits the synthetic four-weight, four-bit
domain; real-model table growth and precision remain separate questions.

A separate six-case capability screen checks whether downloaded AAT `morx`
fonts can provide a streaming alternative to GSUB. This screen has no timing
or arithmetic claims and is retained in [its own report](../aat-support-probe/RESULTS.md).

The first browser smoke exposed a packaging failure in the 256-axis HVAR
control: Chrome rejected WOFF2-to-SFNT conversion. The existing uncompressed
TTF loads and returns the expected default-axis width. Preserve both packages,
the failed smoke and the [format diagnostic](diagnosis-hvar256.json); select
that TTF for the 256-wide control. This does not alter arithmetic. Full numerical
validation is still required, and font loading is outside all timing intervals.

## Completion

Completed on 2026-09-17 (America/Los_Angeles). The final native gates pass
485,428 exact output checks and 68 required-stage controls. Three fresh-browser
timing repetitions at every declared condition pass another 72,000 output
checks, including warmups. The [results](RESULTS.md) and
[raw-data summary](results-summary.json) retain the full comparisons.

Partial symbol reuse improves the poor global-alphabet implementation but
remains slower than the retained position-specific program. Grouped rules
repair width-256 capacity without providing the needed speed. The stopping rule
therefore applies: do not promote this digit program into the model. The shared
variable-font benchmark is retained. The static product-width control is useful
for this small affine domain; its precision, table growth and real matrix cost
are not established by these results.

Two initial correctness groups exceeded their declared budgets with no observed
mismatch. They remain failed reports. Clean bounded reruns and all timing
results are described in [README.md](README.md); the reduced batches and case
sets were declared before their final runs. The support-only AAT screen also
remains a negative browser capability result, separate from arithmetic checks.

No model backend was changed and no new token-speed result is claimed. The
[progress audit](PROGRESS_AUDIT.md) and [next directions](NEXT_DIRECTIONS.md)
connect these findings to the actual model goal.
