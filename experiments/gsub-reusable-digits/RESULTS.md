# A smaller alphabet makes a smaller, slower program

**The shared-symbol representation is exact through 64 tested inputs, but it
is much slower than the retained position-specific representation. Its complete
256-input font is rejected before arithmetic starts.** Three timing repetitions
and independent review support those conclusions. No model speedup is claimed.

## The same calculation, different symbols

Both versions compute `S=sum(w[i]*x[i])`, followed internally by `F=2*S+1`.
Inputs are integers from -8 through 7; weights repeat `[3,-2,5,1]`. Each product
is shifted by its known minimum so intermediate digits are nonnegative. The
final reader subtracts the fixed offset and recovers the signed answer exactly.

The retained version gives positions and intermediate results distinct digit
glyphs. The new version shares sixteen ordinary digit glyphs and thirty-two
temporary digit glyphs throughout the program. One accumulator marker identifies
the running total; operand markers identify remaining four-digit words. Each
addition consumes one operand and restores exactly one accumulator. A later
font operation doubles the completed sum and adds one before publication.

Raw CSS properties feed native counters. Only the completed font width becomes
a CSS number through the existing anchor/container reader. A final element uses
that number in a dependent width. The external driver supplies raw inputs and
checks answers; it does not supply products or partial sums. Runtime documents
have zero scripts and `script-src 'none'`.

## Size and logical work

| Inputs | Reused glyphs | Total lookups | Referenced subtables | Reused WOFF2 bytes | Retained WOFF2 bytes |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 262 | 53 | 379 | 2,448 | 4,684 |
| 16 | 262 | 137 | 1,759 | 2,528 | 12,936 |
| 64 | 262 | 473 | 7,279 | 2,664 | 40,352 |
| 256 | 262 | 1,817 | 29,359 | 3,664 | Not built |

The retained glyph counts at 4, 16 and 64 inputs are 1,284, 4,548 and 17,604.
These byte counts are compressed file sizes, not browser memory measurements.
The 256 row describes a built artifact, not a successful calculation.

Source and binary inspection give:

```text
glyphs = 262
top-level lookup calls = 7*N
total lookup entries = 7*N + 25
source rule statements = 115*N + 454
referenced GSUB subtables = 115*N - 81
peak glyph buffer = 5*N + 1
```

Repeated lookup entries can share serialized bodies and compress very well.
That does not eliminate their execution or validation references. The longest
contextual backtrack is nine glyphs. Every addition still needs another set of
passes, and the buffer grows with input count.

## Correctness and measured speed

The new and retained versions both pass all 65,536 four-input vectors, 4,373
sixteen-input vectors and 5,147 sixty-four-input vectors. Correctness checks
source width, decoded numerical CSS value and dependent consumer width exactly.
The wider suites include extrema, cancellation, carry-related sums, each input
varied individually and seeded random vectors; they are not exhaustive.

Disabling stages changes the exercised answer. Removing the first input's
accumulator role while preserving its numerical value breaks the calculation.
Splitting the text into atomic inline boxes also breaks the intended complete
answer. A split may expose a partial result, so zero width is not required of
that particular control.

Fresh-text timings below are milliseconds per batch of 256 outputs. Each cell
is one fresh browser's upper-middle observation among twenty measured samples,
after five warmups. Every timed output, including warmups, matched exactly.

| Inputs | New, run 1 | Retained, run 1 | New, run 2 | Retained, run 2 | New, run 3 | Retained, run 3 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 19.3 | 13.5 | 26.6 | 9.8 | 27.0 | 10.6 |
| 16 | 219.5 | 31.2 | 311.0 | 27.6 | 310.7 | 26.5 |
| 64 | 3,395.0 | 122.9 | 4,743.2 | 127.7 | 4,767.3 | 106.2 |

The 64-input replacement is approximately 28–45 times slower in the respective
runs. Its compressed file is about 93% smaller. File size and runtime plainly
move in different directions here. Direct CSS controls are retained beside every
font condition in the raw reports and are faster than either font implementation.

The first run measured fixed-nonce and fresh-text phases; the later runs measured
fresh text only because the new program was slow. The table compares fresh-text
phases throughout. Input seeds differ between repetitions and phases; methods
at a given width/phase receive the same sequence. The seed bases are 104729,
130363 and 155921. The second run reverses variant order. Each font is alternated
with its direct-CSS control within a sample; new and retained fonts are separate
variant blocks, not interleaved on every sample.

Full correctness runs use separate browsers before timing. Timed runs use the
same small precheck and five warmups. Font loading, expected-answer preparation
and browser transport are excluded; raw writes, native computation, numerical
readback and forced consumer reads are included. The harness loops are included.
The shared advisory lock serializes builds and browser runs. Other activity and
power state were not controlled. A run spanned the user interruption; all raw
samples and the substantial variation are preserved rather than discarded.

Chrome 153.0.8010.48, Apple M2 Pro, macOS arm64, Node v26.5.0. Harness hashes differ
as phase-selection and profiling options were added; each report records the
source used for that run. The arithmetic font bytes are unchanged and their
hashes match their full correctness gates.

## Why a small program can do more work

The old compiler's target classes identify the intended digit partly by its
unique glyph identity. The replacement targets a common ordinary-digit class;
many positions qualify initially, and surrounding markers must reject the wrong
ones. It also adds one top-level step per addition. These are inspected source
facts and a plausible explanation for the tradeoff, not an exact attribution
of browser CPU time to individual matching operations.

A separate short 64-input profile used one warmup and three measured batches:

| Method | Total measured elapsed | Browser style duration | Browser layout duration |
| --- | ---: | ---: | ---: |
| Reused digits | 14,317.8 ms | 126.3 ms | 14,166.4 ms |
| Retained digits | 318.0 ms | 96.4 ms | 201.6 ms |

Both report 769 style events and three layouts. The extra time is overwhelmingly
in layout, not explained by counting more style events. These coarse categories
do not isolate pure font-engine CPU, and this short profile does not replace the
three timing repetitions.

## Why the 256-input font fails

The unmodified font's first eight browser smoke cases all return source width
zero. The minimum-product case should return 65 pixels; direct CSS returns the
correct answers. The numerical range is safe: the largest internal final value
is 21,121, within four base-16 digits. There are no recorded loading or console
errors.

The counter-generated content is present and literal text also fails, including
browser probes with reduction disabled. HarfBuzz 14.2.1 returns all original input
glyphs unchanged with the complete feature set. Its API exposes the raw GSUB
table but reports zero validated lookups. This is table rejection before the
first product substitution, not a partially completed sum or CSS decoding error.

The cause is a cumulative subtable-reference limit. HarfBuzz's validator rejects
16,384 or more references. The full font has 29,359. Adding 262 KB of unused
GSUB bytes does not rescue it, ruling out the tested table-length padding remedy.

Controlled diagnostic fonts preserve all 1,817 lookup entries but deliberately
remove rules to vary their reference count. At 16,383 references HarfBuzz accepts
the table; at 16,384 it rejects it. Chrome shows the same boundary in a simple
two-character Products→Publish presence probe: width 64 versus zero. All probe
fonts load. The diagnostic variants omit necessary arithmetic rules and are
**not repaired or validated 256-input circuits**. Original fonts are preserved.

Primary source: [HarfBuzz 14.2.1 table validation](https://github.com/harfbuzz/harfbuzz/blob/14.2.1/src/hb-ot-layout-common.hh#L1380-L1396)
and [the count bound](https://github.com/harfbuzz/harfbuzz/blob/14.2.1/src/hb-sanitize.hh#L140-L143).
Chrome was tested independently; its embedded library revision was not inferred.

The emitted `115*N-81` count predicts crossing this guard at 144 inputs, the
first such multiple of four. That is not a claim that width 140 works. Full
correctness is established through 64; intermediate widths remain untested.

## Decision and evidence

Keep this as a documented failed performance approach. It removes the glyph
growth problem but increases execution cost and runs into another table limit.
A future representation would need fewer repeated rule checks and references,
not just fewer glyph names. No production model code was replaced.

- [Correctness at four inputs](correctness-w4.json)
- [Correctness at sixteen and sixty-four](correctness-w16-w64.json)
- [Run 1](timing-rep1.json), [run 2](timing-rep2.json), [run 3](timing-rep3.json)
- [Coarse profile](profile-w64.json)
- [Preserved 256-input failure](smoke-w256.json)
- [Input-delivery diagnostics](diagnosis-w256.json)
- [HarfBuzz table-boundary probes](diagnosis-subtables.json)
- [Chrome table-boundary probes](diagnosis-browser-subtables.json)
- [Independent audit](../gsub-width-followups/AUDIT.md)
- [Reproduction guide](README.md)
