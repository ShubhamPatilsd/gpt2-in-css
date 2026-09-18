# Smaller rule tables let the wider calculation run, but do not make it fast

Selective symbol sharing makes the previous globally shared digit program about
3.3 times faster at 64 inputs. It is still about ten times slower than the older
position-specific digit program. Grouping the new rules repairs the 256-input
capacity failure, but does not improve speed in the matched 64-input comparison.
Keep the shared variable-font method as the model benchmark; these results do
not justify replacing it with this digit program. This report concerns synthetic
small integer arithmetic, not a new GPT-2 token-generation measurement.

## What changed

The previous globally reused digit alphabet was small, slow, and rejected at
256 inputs. Its program had 29,359 references to rule subtables, exceeding the
confirmed 16,384-reference validation boundary. We tested two changes separately.

First, share symbols only within the same digit position. For example, the low
digit of every number shares one alphabet, while the next digit uses another.
The corresponding temporary digits and arithmetic mappings follow that division.
This gives a rule fewer initially eligible positions without creating a new
digit alphabet for every input and intermediate result.

Second, group the same context rules into class-based tables. The two new
variants have byte-identical arithmetic source. The conversion preserves rule
matching, order and nested actions, and removes no rules. Their compiled table
organization differs. Independent source and binary checks are in the
[audit](PROGRESS_AUDIT.md).

| Program | Inputs | Glyphs | Referenced rule subtables | WOFF2 bytes |
| --- | ---: | ---: | ---: | ---: |
| Previous global reuse | 64 | 262 | 7,279 | 2,664 |
| Share by digit position, separate context tables | 64 | 406 | 7,337 | 3,252 |
| Same symbols and arithmetic, grouped context tables | 64 | 406 | 530 | 3,244 |
| Previous global reuse, rejected | 256 | 262 | 29,359 | 3,664 |
| New grouped context tables | 256 | 406 | 1,874 | 4,220 |

The new 256-input program passes its browser gate: 663 vectors covering extrema,
carry boundaries, cancellation, both signed extremes at every individual input,
and seeded random inputs. Source width, the decoded CSS number and a dependent
CSS width all match exactly. Disabling each of its four required font stages
changes the answer. This is a sampled capacity result, not exhaustive validation
of all 16^256 input vectors, and not evidence of GPT-2 numerical precision.

## A different affine control: let text layout add the products

We also built a font with no substitution or variation tables. Each input symbol
has the width of its fixed weighted contribution. Normal text layout adds those
advances. The affine continuation is folded into the widths, just as CSS and
HVAR are allowed to fold it into their calculation.

For input `x` and its fixed weight `w`, the product glyph's width is
`2*(w*x - minimumContribution)`. A leading nonce glyph contributes 65. Subtracting
the known output offset recovers `2*sum(w*x)+1`. Only individual products are
tabulated; the font does not contain a table of complete input-vector answers.
It has 130 glyphs and is 720 WOFF2 bytes, reused for all four tested widths.

This control does not keep an internal running sum that another font operation
can consume. Its sum is the text's geometric width. It therefore tests a
different implementation of this affine operation, not an internally connected
nonlinear layer. The four small weights and sixteen-value input domain are
especially favorable to this representation.

## Matched performance results

Each cell is the median of three fresh-browser run medians, in milliseconds per
**32 completed outputs**. The bracketed range is the smallest and largest run
median. Every output includes a subsequent CSS calculation consuming the answer.
The shared column publishes two vectors with sixteen identical output rows each;
the other columns publish 32 independent vectors.

| Method | 4 inputs, one output/vector | 16 inputs, one output/vector | 64 inputs, one output/vector | 64 inputs, sixteen outputs/vector |
| --- | ---: | ---: | ---: | ---: |
| Older position-specific digits | 2.1 [2.1–2.2] | 4.8 [4.8–4.8] | 17.4 [17.0–17.4] | 15.7 [15.3–15.9] |
| Previous globally shared digits | 4.0 [4.0–4.1] | 40.5 [40.0–40.6] | 594.5 [589.9–595.8] | 593.9 [593.2–595.4] |
| Share by digit position | 2.6 [2.6–2.7] | 14.5 [14.4–14.6] | 179.9 [178.2–181.1] | 178.8 [178.5–178.9] |
| Same arithmetic, grouped rules | 2.6 [2.6–2.7] | 15.6 [15.3–15.6] | 194.4 [193.0–195.4] | 193.8 [193.4–193.9] |
| Static product widths | 1.9 [1.8–1.9] | 3.7 [3.4–3.8] | 10.2 [10.2–10.2] | 8.6 [8.6–8.7] |
| Shared variable font (HVAR) | 5.1 [5.0–5.2] | 9.3 [9.2–9.6] | 41.2 [40.2–41.2] | 8.0 [7.9–8.0] |
| Direct CSS arithmetic | 0.7 [0.7–0.7] | 1.2 [1.2–1.3] | 3.1 [3.0–3.3] | 0.5 [0.4–0.5] |

At 64 inputs, partitioning the shared alphabet reduces 594.5 ms to 179.9 ms,
about 70% less time. However, 179.9 ms is still 10.3 times the older program's
17.4 ms. Grouping those same new rules reduces subtable references from 7,337
to 530, yet takes 194.4 ms, about 8% longer. Smaller structural counts therefore
do not establish less execution work.

Static product widths outperform the digit programs here. With one output per
vector they also beat the variable-font control. With sixteen shared outputs,
the variable font takes 8.0 ms and static widths take 8.6 ms. These are repeated
coefficient rows and a tiny input/weight alphabet; neither comparison establishes
a winner for a real learned matrix. Direct CSS is fastest in all these small
synthetic conditions. The cross-column improvement for shared inputs includes
fewer vector publications, not just a change inside the font engine.

### Wider capacity test

The width-256 runs use **16 outputs per batch**, so their batch times must not
be compared directly with the 32-output table above. All three repetitions pass.

| Method | Median ms / 16 outputs | Range of run medians |
| --- | ---: | ---: |
| Share by digit position, grouped rules | 1,473.1 | 1,445.1–1,475.6 |
| Static product widths | 14.5 | 13.8–14.7 |
| Shared variable font (HVAR), TTF | 38.7 | 37.2–39.6 |
| Direct CSS arithmetic | 5.8 | 5.7–5.8 |

The grouped digit program is about 38 times slower than the variable font in
this matched width-256 condition. It now works, but its execution cost is a
clear rejection of this implementation as the matrix replacement. Dividing
by outputs gives about 92.1 ms per output here and 6.1 ms at width 64; that
describes these batches, not an isolated latency measurement or a proven
scaling law.

The machine-readable [summary](results-summary.json) recomputes these medians
from all raw samples and checks font hashes against the accepted gates.
Raw timings are retained for [4/16/64 inputs](results-timing-main.json) and
[256 inputs](results-timing-256.json), alongside their separate
[main correctness gate](results-correctness-main.json) and
[256-input gate](results-correctness-256.json).

## Workload and interpretation

All conditions compute `F=2*sum(w[i]*x[i])+1`, with independent integer inputs
from -8 through 7 and weights repeating `[3,-2,5,1]`. The digit programs perform
their dependent affine operation inside the font. CSS, variable fonts and static
advances can simplify that affine expression; they are not forced to repeat
unnecessary work to resemble the digit program.

The N64 shared condition has two input vectors, each feeding sixteen outputs,
for 32 total outputs. All sixteen coefficient rows are identical. Each row uses
a shifted nonce, so the complete digit-font text differs among rows, but this
does not disable all caches. This is an isolation test of shared input/font
state, not a general matrix with distinct output rows. The earlier
[distinct-row study](../gsub-shared-matrix-probe/RESULTS.md) remains the relevant
evidence for that broader comparison.

The single-row N4/N16/N64 cases have 32 independent vectors per batch. N256 has
16. Every compared backend receives identical raw inputs and the same parent
property writes within its condition. Do not compare a 16-output batch time to
a 32-output batch time as equal work. Per-output division describes batched
work, not isolated single-vector latency or an asymptotic scaling proof.

Each font method must return its width as a CSS number and feed a following
calculation, `positiveOffset + 3*F`. Direct CSS already has that number and uses
it directly. Pages have no script elements and prohibit author scripts; the
external driver supplies raw inputs and checks answers, never products or sums.

## Correctness and measurement protocol

The accepted gates contain 485,428 exact output checks:

- N4: all 65,536 possible input vectors for each of seven backends.
- N16: 1,108 vectors per backend.
- N64: 1,300 single-row vectors per backend, plus 64 vectors with sixteen
  repeated output rows per backend.
- N256: 663 vectors for each of four backends. The prior position-specific font
  is not built at this width; the previously rejected global program is not
  treated as a competitor with a valid answer.

All 68 required-stage disabling controls distinguish the intact digit program.
Static advances have no font stages to disable; their complete mapping and all
observed answers are checked instead. The variable-font control at N256 now
has changing-input evidence, not merely a font-loading check.

Timing requires complete passing gates and matching font hashes. Full correctness
runs separately from three fresh timing browsers. Each condition has five warmup
and twenty measured rounds, independently seeded by repetition and condition,
with cyclic backend order and rotated condition order. All 72,000 timed outputs,
including warmups, match exactly. The reported per-run median is the upper middle
of twenty samples; the center across repetitions is the median of three run
medians. Ranges describe observed variation, not confidence intervals.

The measured interval includes parent input writes, native encoding, font/CSS
calculation, numerical readback, and forced dependent widths, plus driver loop
overhead inside the page evaluation. Font loading, input generation, the oracle
and browser-protocol transfer are outside it. Builds and browser work use the
common advisory lock. Ordinary host activity and power state are not controlled.

## Retained failed attempts

The first smoke tests failed when Chrome could not convert the N256 HVAR WOFF2
package to SFNT. The identical program's existing TTF loads; the final control
uses it and passes changing-input checks. Both packages, the original manifest,
and the [format diagnostic](diagnosis-hvar256.json) remain. Loading is excluded
from timing; no browser setting, arithmetic rule or validation limit was changed.

The initial 512-vector shared-output correctness group exceeded its 180-second
budget. The original N256 group also exceeded that budget after 2,048 of 2,071
vectors, with zero mismatches. They remain failed attempts and did not authorize
timing. Clean reruns use the declared stratified 64-vector shared gate and
663-vector N256 gate. Their source snapshots and hashes are retained. Main
single-row case sets did not shrink.

Timing batches were reduced before timing to 32 outputs for the main conditions
and 16 at N256, keeping all backends matched within each condition. The evaluation
deadline is 90 seconds for a full 25-round timing group, rather than mistaking
that group's expected aggregate work for a single short update.

## Relation to the model goal

This experiment has not changed the native GPT-2 runtime or produced a new token
speed. The [progress audit](PROGRESS_AUDIT.md) distinguishes earlier system-level
improvements from the recent absence of a repeatable full-model gain.

There has been real progress. Earlier saved twelve-layer, eight-token runs took
662.495 seconds with the original scalar cache and 402.672 seconds with the
whole-head font-vector cache, about 39% less time at the same nominal scope.
Those are historical runs, not a newly randomized paired comparison. The last
saved twelve-layer, 32-token run still took 3,177.132 seconds, about 53 minutes.
Its post-first-token median was 97.694 seconds as the history grew. These
eight-token and 32-token workloads should not be compared as interchangeable.

Recent progress has plateaued in **demonstrated complete-model speed**, while
capacity and diagnosis have improved. There is no evidence yet of a fundamental
browser speed limit. Several local wins either left out required handoffs and
layer switching or used small synthetic workloads with fewer outputs, lower
precision and easier arithmetic than the model. Sometimes the supposedly new
optimization was already present in the model's benchmark. Those are reasons
to improve the experiment-to-model connection, not to infer that all approaches
have been exhausted.

The previous recommendation to focus on producing widths needs a scope limit:
the small digit sum's final reader was inexpensive. That does not make the
model's thousands of intermediate coordinate handoffs inexpensive. An older
real 768→3,072 FC study measured 111.3 ms for plain output spans and 1,074.3 ms
with timeline exposure, decoding and GELU. These are different workloads and
boundaries, not contradictory estimates of one cost.

[NEXT_DIRECTIONS.md](NEXT_DIRECTIONS.md) gives concrete gates for three paths.
The priority for model progress is to connect the existing real 768→3,072→768
MLP component to its native producer and consumer, so any saving includes the
work of using its answer. A bounded font research branch can test instructions
starting at a unique running-total marker rather than repeatedly scanning the
whole input. A separate attention test can keep each layer's old values rendered
across layer switches, measuring both total delivery cost and memory. None is
claimed as a demonstrated speedup here. The separate
[AAT support screen](../aat-support-probe/RESULTS.md) rejects one streaming-font
route at its browser capability gate, before arithmetic compilation.

See [README.md](README.md) for reproduction, [PLAN.md](PLAN.md) for the declared
questions and amendments, and [COMPILER_NOTES.md](COMPILER_NOTES.md) for source
work counts and the limits of the earlier pairwise-addition comparison.
