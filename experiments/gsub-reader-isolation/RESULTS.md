# The final CSS reader is a small part of the wide calculation

**Removing the final reader leaves almost all the time at 64 inputs.** Across
three fresh-browser runs, adding it cost about 3–4 ms for the running-total font
and 3–5 ms for the pairwise font, per 256 outputs. The source paths already took
72–75 ms and 128–131 ms respectively.

This rejects the explanation that the final conversion from width to CSS number
caused most of the wide circuit's slowdown. It does not isolate pure font CPU
time: the source path still includes raw input writes, native input encoding,
style resolution, shaping and measuring the source width.

The reader can matter for small circuits. Its approximately fixed few-ms cost
is a much larger fraction of the four-input circuit than of the 64-input one.

## The intervention

The **source-only page** has the calculation and its text source, with no reader
DOM. The harness changes the raw inputs and forces the source's width.

The **full page** adds the existing anchor-size receiver, size container and
dependent consumer. It converts the source width into a CSS number, then uses
that number in another width calculation. The harness changes exactly the same
inputs and forces that final width.

Each pair uses separate pages and browser contexts, the same inputs and nonce,
the same number of writes, and one forced geometry read per output. Thus its
difference measures the effect of adding this reader and its dependencies. The
source-only condition is a diagnostic endpoint, not a substitute for providing
a numerical result to later CSS calculations.

## Complete measurements

All times below are milliseconds per update of 256 independent outputs. Each
number is the median of three browser-run medians. The paired increase is
calculated from matching sample pairs within each run, then summarized across
runs; it need not equal a subtraction of the two displayed medians.
For each run's 20 elapsed samples, the harness selects the upper-middle observed
sample. The separate paired-difference summary averages the two middle values.

| Inputs | Method | Source only | Full reader | Paired increase, median [range across runs] |
| ---: | --- | ---: | ---: | --- |
| 4 | Running total | 5.8 | 8.7 | 2.75 [2.65–2.90] |
| 4 | Pairwise addition | 5.9 | 9.0 | 3.05 [2.80–3.10] |
| 4 | Variable font | 21.1 | 24.2 | 3.00 [2.40–3.20] |
| 16 | Running total | 17.6 | 20.6 | 2.95 [2.50–3.10] |
| 16 | Pairwise addition | 20.1 | 23.5 | 3.30 [3.15–3.45] |
| 16 | Variable font | 38.9 | 42.2 | 3.15 [2.95–3.20] |
| 64 | Running total | 73.0 | 76.6 | 3.25 [3.10–4.20] |
| 64 | Pairwise addition | 130.8 | 135.3 | 4.40 [3.30–5.10] |
| 64 | Variable font | 212.0 | 206.6 | Unresolved: signs differ across runs |

The 64-input variable-font pairs deserve explicit treatment:

| Browser run | Source median | Full median | Median of paired full-minus-source samples |
| ---: | ---: | ---: | ---: |
| 1 | 214.1 | 206.1 | -6.35 |
| 2 | 198.6 | 208.7 | 3.90 |
| 3 | 212.0 | 206.6 | -3.05 |

That variability does not establish that adding the reader makes HVAR faster,
or give a reliable estimate of its small incremental cost at this width. It
does establish that removing the reader leaves roughly 200 ms of work. Reader
dominance is inconsistent with all three runs even though the small difference
is unresolved.

Direct CSS calculates and consumes the same answer directly. Its run-median
results are 2.4 ms at four inputs, 5.1 ms at sixteen, and 15.2 ms at sixty-four.
The 64-input range is 15.1–15.3 ms. None of the computing font paths beats it.

These are new matched comparisons. Their absolute times must not be subtracted
from the previous experiment's combined-page times as though the two harnesses
were one decomposition of the same measurement.

## A reader with the answer already available

Two controls receive an externally prepared answer, plus every otherwise-unused
raw input write. One selects an ordinary glyph with the correct width. The
other directly supplies a CSS width. They do not perform native arithmetic and
are not candidate model implementations.

| Inputs | Source of precomputed width | Source only | Full reader | Paired increase, median [range] |
| ---: | --- | ---: | ---: | --- |
| 4 | Static font | 3.5 | 6.4 | 2.85 [2.75–3.55] |
| 16 | Static font | 5.0 | 7.8 | 2.70 [2.65–2.90] |
| 64 | Static font | 10.6 | 13.7 | 3.00 [2.60–3.05] |
| 4 | CSS width | 1.7 | 4.0 | 2.35 [2.35–2.50] |
| 16 | CSS width | 3.3 | 5.8 | 2.35 [2.30–2.60] |
| 64 | CSS width | 9.1 | 11.4 | 2.50 [2.20–2.60] |

These own-pair differences corroborate a few-ms reader cost with a cheap source.
Do not subtract the controls from GSUB and call the remainder exact arithmetic
cost: their dependencies and text encoding differ. Their source cost also grows
with width because the diagnostic deliberately retains all raw input writes.

## Where the browser still spends time

Separate 64-input profiles used another input sequence, five warmups and ten
measured updates. These are average milliseconds per batch from those profiles,
not replacements for the timing medians above.

| Method and endpoint | Browser style time | Browser layout time |
| --- | ---: | ---: |
| Running total, source | 21.73 | 46.05 |
| Running total, full | 23.97 | 49.06 |
| Pairwise, source | 22.40 | 104.08 |
| Pairwise, full | 24.04 | 106.38 |
| Variable font, source | 8.63 | 192.55 |
| Variable font, full | 9.70 | 188.98 |
| Static precomputed font, source | 4.54 | 1.23 |
| Static precomputed font, full | 6.10 | 3.19 |
| Precomputed CSS width, source | 3.58 | 0.49 |
| Precomputed CSS width, full | 4.44 | 1.93 |
| Direct CSS calculation | 9.76 | 0.47 |

The pairwise circuit retains much more layout work even when the reader is
absent. The costly difference therefore precedes the final return to CSS.
These broad categories do not identify an individual font-engine routine or
separate font shaping from all other source-layout work.

The font source-only profiles report ten style recalculation events; their full
counterparts report 2,567. That large count change buys only a small change in
elapsed time. Event count is not a useful substitute for measured duration.

## Correctness, replication and artifacts

Chrome 153.0.8010.48 on Apple M2 Pro, macOS arm64, Node 26.5.0. The run finished
2026-09-18 at 02:03:11 UTC. Browser work used the common advisory lock; ordinary
activity elsewhere on the machine was not disabled.

The full correctness browser closes before any timed browser starts. It checked
all 65,536 four-input vectors for every condition, 2,315 sixteen-input vectors
and 3,083 sixty-four-input vectors per condition: 780,274 case/condition checks.
Full-reader correctness separately observes source width, decoded number and
consumer width. Every check was exact. Wider spaces were sampled, not exhausted.

Each fresh timed browser uses the same small precheck, independently seeded
stimuli, five warmups and twenty measured rounds. Width order rotates; backend
block order rotates; source/full order alternates each round. All 633,600 timed
outputs, including warmups, match. The profiling outputs also match. There are
no reported browser errors.

Inputs and expected answers are prepared outside timing. The interval includes
raw writes and forced reads, including the harness mutation/read loops. The
three computing font conditions never receive a precomputed answer property.
The two diagnostic controls explicitly do. Served pages contain zero scripts
and use `script-src 'none'`; an external test driver supplies and observes inputs.

- [Raw cases, samples, profiles and provenance](results.json)
- [Summary preserving separate browser runs](summary.json)
- [Method and reproduction commands](README.md)
- [Harness](../../tools/test_gsub_reader_isolation.mjs)
- [Diagnostic font builder](../../tools/build_gsub_reader_control.py)
- [Summary calculation](../../tools/summarize_gsub_reader_isolation.py)

**Decision:** for these wide font circuits, focus performance work on the source
calculation path. Optimizing the final reader alone cannot remove the large
slowdown. Keep the smaller reader cost in mind when evaluating much cheaper or
very narrow circuits.
