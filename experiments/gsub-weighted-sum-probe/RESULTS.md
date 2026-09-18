# Connected weighted sums: the width experiment

**We widened the circuit successfully, but this implementation is slower than
direct CSS.** It now combines as many as 64 signed inputs into one exact answer
using small digit rules. A separate circuit takes four inputs, uses each input
in four different weighted calculations, then combines those four results.
Intermediate answers stay inside the font in both cases.

At 64 inputs, the running-total circuit took **107.8 ms** per batch of 256
changing outputs. The pairwise circuit took **186.6 ms**. Direct CSS took about
**22 ms**. These are complete component measurements, including entering the
font and returning a usable CSS number. They are not GPT-2 token measurements.

The result changes the question. We no longer need to ask whether more than two
inputs can interact inside the font without a giant whole-input table: they can.
We need to ask whether that internal work can become cheap enough to be useful.
This particular digit-based implementation did not meet that performance gate.

## What was built

### One shared result from several signed inputs

For four inputs the program calculates:

```
S = 3*a - 2*b + 5*c + d
F = 2*S + 1
```

Each input is a whole number in `[-8, 7]`. At widths 8, 16 and 64, the four
weights repeat. The inputs are independent: changing any one of them can change
the final answer. This is one connected calculation, not a collection of
independent two-number examples.

The second line is executed inside the font after the sum. It proves an internal
dependency, but it is still simple linear arithmetic plus a constant. It is not
a nonlinear activation or a GPT-2 layer. An optimized competitor may legally
fold it into the original weights; our controls are allowed to do that.

### How small rules replace a large table

Each input has 16 possible values. The compiler therefore needs only 16 entries
to map one input to its fixed weighted product. Four inputs need 64 such entries;
64 inputs need 1,024. Addition, carry, routing, and output rules are extra and
are included in the total counts below.

The intermediate product is stored using four base-16 digit glyphs. These are
internal font symbols with zero horizontal advance. They do not publish an
intermediate answer through the page's geometry.

To support negative products, each product is shifted by its smallest possible
value. For example, `3*a` lies between -24 and 21, so its stored value is `3*a+24`.
The four-input sum of shifted products is `P=S+86`. The internal continuation
produces `Q=2*P+1`; the final CSS reader subtracts the known offset to recover
`F=2*S+1`. This preserves signed arithmetic exactly. It does not clip, wrap or
discard negative results.

| Inputs | Signed sum S | Stored P | Largest Q | Exact signed F range |
| ---: | --- | --- | ---: | --- |
| 4 | -86 to 79 | 0 to 165 | 331 | -171 to 159 |
| 8 | -172 to 158 | 0 to 330 | 661 | -343 to 317 |
| 16 | -344 to 316 | 0 to 660 | 1,321 | -687 to 633 |
| 64 | -1,376 to 1,264 | 0 to 2,640 | 5,281 | -2,751 to 2,529 |

Four base-16 digits have enough range for every intermediate in these programs.
Their ability to hold larger values is not a claim that all possible 16-bit
arithmetic or GPT-2 numerical precision has been tested.

The font adds adjacent digit words using rules that inspect the corresponding
left digit and a carry, then update the right digit. After all four digits have
been processed, the consumed left word is removed with a legal ligature rule.
Only after the entire sum and dependent operation finish do output glyphs acquire
advances. Their weighted digit advances add up to the final number. Thus ordinary
text layout helps publish the completed answer; it is not standing in for the
missing internal arithmetic.

### Running total versus pairwise addition

Both methods perform N-1 additions for N inputs. The running-total version does
them one after another. The tree version pairs inputs, pairs those partial
answers, and continues until one answer remains.

The compiler really does combine independent additions into shared lookup passes
at each tree level. At 64 inputs this cuts the top-level passes from 385 to 43.
However, those passes do different amounts of work. Fewer passes did not produce
a lower elapsed time. The tree font was slower in this sweep.

### Four inputs feeding four different calculations

The extra circuit calculates these four internal results:

```
r0 =  3*a - 2*b + 5*c + d
r1 = -1*a + 4*b + 2*c - 3*d
r2 =  2*a +   b - 2*c + 5*d
r3 =  5*a - 2*b +   c + 2*d
F  = 2*(r0+r1+r2+r3) + 1
```

Each original input glyph expands into four distinct product words. CSS supplies
each input once; it does not calculate products or create the intermediate row
answers. The font then adds matching products for each row, combines the four
row results, and applies the final doubling operation.

Because this whole example is affine, its final answer also equals
`2*(9*a+b+6*c+5*d)+1`. The direct CSS control uses that simplified expression.
We do not force CSS to preserve unnecessary internal work just to match the font.

## Correctness evidence

The runtime browser document has `script-src 'none'` and zero script elements.
External JavaScript supplies raw input integers, observes outputs and checks
them against ordinary signed arithmetic. It never supplies a product, partial
sum or expected answer to the font.

For every browser correctness case, the harness checks three things independently:

1. The source's final font width.
2. The numerical CSS value decoded from that width.
3. A downstream element's width, calculated as a positive offset plus three
   times the decoded number.

Timed and profiled samples check the downstream width against the expected
answer; they do not repeat all three observations inside the measured interval.

The font uses 1,024 units per em at a 1,024-pixel font size, so the tested integer
metrics return exact integer CSS-pixel widths. No observation rounding or error
tolerance was added.

| Program | Input vectors checked | Result |
| --- | ---: | --- |
| 4 inputs, running total | 65,536, exhaustive | Exact |
| 4 inputs, tree | 65,536, exhaustive | Exact |
| 8 inputs, each method | 4,245 | Exact |
| 16 inputs, each method | 4,373 | Exact |
| 64 inputs, each method | 5,147 | Exact |
| Four inputs → four internal outputs → combined result | 65,536, exhaustive | Exact |

Wider cases include extremes, cancellation, seeded random vectors, carry-related
boundaries, and changing every coordinate individually across its whole domain.
These sample sets are not exhaustive checks of the wider input spaces.

Disabling product formation, connected addition, the dependent operation or
publication breaks a case that exercises that phase. Splitting the same input
characters across separate atomic inline boxes also breaks the computation.
A broken stage need not produce zero width: the ordinary program can still emit
its 64-unit baseline. The control requires an incorrect final answer, not an
arbitrary zero-width condition.

The four internal row answers also received a separate exhaustive check:
**262,144 intermediate values**, all exact. That check used HarfBuzz 14.2.1 to
observe the glyphs before the rows were combined. The verifier confirmed that
the TTF's substitution table, glyph order, character map and horizontal metrics
match the WOFF2 font used by Chrome. It complements Chrome's final-result check;
it is not a claim to have observed Chrome's internal glyph buffer.

Raw correctness reports:
[four-input](results-correctness-w4.json),
[wider circuits](results-correctness-wide.json),
[shared-input circuit](results-correctness-fanout.json), and
[internal row checks](fanout-intermediate-audit.json).

## Complete-path timings

Chrome 153.0.8010.48, Apple M2 Pro, macOS arm64, Node 26.5.0.
Each sample changes a batch of 256 independent outputs. Each condition has 40
samples; the first 5 are excluded from the reported warm median. All timed
outputs, including warmup samples, are checked for exact correctness.

The table uses the phase with a new zero-width nonce character each round.
Numbers are milliseconds per batch; lower is better.

| Inputs per output | Running-total font | Tree font | Direct CSS, paired with running total |
| ---: | ---: | ---: | ---: |
| 4 | 10.7 | 11.3 | 3.2 |
| 8 | 16.4 | 17.4 | 4.6 |
| 16 | 27.8 | 31.0 | 7.3 |
| 64 | 107.8 | 186.6 | 22.3 |

The direct CSS runs paired with the tree measured 3.2, 4.5, 7.0 and 22.1 ms.
The four-input → four-internal-output → combined circuit took 22.8 ms, compared
with 3.0 ms for its direct CSS control.

At 64 inputs the running-total font took about 4.8 times as long as its CSS control;
the tree took about 8.4 times as long as its own control. The tree had almost nine
times fewer top-level passes but still took longer. These are observations from
one corrected sweep, not confidence intervals from repeated independent runs.

The timed interval includes raw input writes, native input encoding, shaping or
CSS arithmetic, required layout/readback and forced downstream width reads. It
also includes the harness's mutation/read loop overhead. Preparing test cases,
calculating expected answers, font loading and browser-protocol transport are
outside the timed interval. CSS consumes its existing numerical result directly;
it is not forced through the font's extra geometry-to-number conversion.

Browser runs and builds used the shared advisory lock. Ordinary machine activity
was not disabled. Parallel agents developed and reviewed separate code; measured
browser work was serialized.

The raw sample arrays, p95s, backend order, seeds and correctness counts are in
[results-timing.json](results-timing.json).

### Comparison with a variable font

The existing project also performs weighted sums through variable-font widths:
each input sets one font axis, and the font's width changes by the weighted
amount. We built a control using that mechanism, called HVAR, for precisely the
same arithmetic. It uses the same final width-to-CSS-number reader. Its fixed
weights incorporate the final doubling, which is a legal simplification.

| Inputs per output | Variable-font control | Its paired direct CSS |
| ---: | ---: | ---: |
| 4 | 28.6 ms | 3.4 ms |
| 8 | 39.0 ms | 4.6 ms |
| 16 | 60.7 ms | 7.5 ms |
| 64 | 286.9 ms | 22.9 ms |

These are also warm medians per 256 changing outputs in the fresh-text phase.
All four-input combinations and the wider correctness sets pass for this
control. The fonts are small: 688, 748, 876 and 1,536 compressed bytes.

The digit circuit beat this particular variable-font control. That does not
establish that it beats the project's matrix multiplication implementation.
Here, each independent input vector produces just one output. In a matrix
multiplication, many outputs share the same input vector, allowing font settings
to be reused. That different workload needs its own comparison before choosing
a replacement. Raw reports: [correctness](results-hvar-correctness.json) and
[timings](results-hvar-timing.json).

### Where the time went

A separate profiling run measured 20 updates of 256 outputs at 64 inputs, after
five warmup updates. The browser reported these totals in milliseconds:

| Method | Measured elapsed time | Style work | Layout work |
| --- | ---: | ---: | ---: |
| Running-total digit font | 2,217.8 | 667.0 | 1,392.2 |
| Tree digit font | 3,815.8 | 676.6 | 2,982.0 |
| Variable-font control | 5,735.4 | 279.7 | 5,316.3 |
| Direct CSS, range across the three paired runs | 434.9–453.2 | 287.7–298.3 | 15.0–18.8 |

Most of the extra measured time falls under **layout**, the browser category
that includes determining text and element sizes. The tree's style time was
close to the running total's, while its layout time was much larger. This
narrows the investigation, but these broad categories do not separate time
spent executing font rules from time spent returning widths to CSS.

All three font paths reported 5,121 style recalculations, versus 20 for each
CSS control; every path reported 20 layouts. Counts alone are misleading:
the variable-font control spent slightly less total time in style work than
its CSS control, despite the much larger count. Its layout time dominated.

These are separate runs from the clean timing sweep above. The reported browser
durations are coarse categories, not an exhaustive additive decomposition of
the elapsed interval. Every profiled output was checked. Raw reports:
[digit-font profiles](results-profile.json) and
[variable-font profile](results-hvar-profile.json).

### A timing correction worth preserving

The first sweep reused the same input sequence across two nonce phases. A variable
font control showed a large second-phase improvement, making that phase comparison
confounded by input/font-instance reuse. It was not evidence that adding nonce
characters made the arithmetic faster.

Those results are retained in [attempt-reused-phase-inputs](attempt-reused-phase-inputs/).
The reported sweep uses a different deterministic input seed for each phase,
with the same seed for comparable backends at a given width. A fixed nonce means
only that the nonce stays fixed; inputs still change randomly. A changing nonce
prevents identical whole-text reuse but does not disable every internal cache.

## Size and scaling limits

| Inputs | Glyphs, either method | Rule entries, either method | Running-total WOFF2 bytes | Tree WOFF2 bytes |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 1,284 | 4,695 | 4,684 | 5,264 |
| 8 | 2,372 | 10,391 | 7,740 | 9,196 |
| 16 | 4,548 | 21,783 | 12,936 | 16,008 |
| 64 | 17,604 | 90,135 | 40,352 | 53,388 |

These are actual built artifacts. The four-input shared-output font has 4,612
glyphs, 21,703 rule entries and 16,332 WOFF2 bytes.

For the ordinary construction, source-derived counts are:

```
glyphs = 272*N + 196
rule entries = 1424*N - 1001
```

This removes the exponential whole-vector table. It still duplicates symbols
for different positions and stages. The glyph count would exceed the ordinary
65,535 limit at N=241. The current character allocation also needs changing above
N=128 to avoid the nonce range. The compiler now guards that collision. We did
not claim to run a 768-input font; reaching it requires another representation
change, not just increasing an input-count flag.

## What this means for the project

The representation idea works: small arithmetic rules can connect many inputs,
share them across several outputs, and carry results into a later calculation.
The test also falsifies a tempting performance assumption: reducing the number
of successive font passes does not necessarily make the font faster.

We should retain this as a verified building block. It has not earned a place in
the current GPT-2 pipeline yet. The next experiments should answer three narrower
questions, in this order:

1. **How much does publishing the answer cost?** Compare the same circuit with
   only its source width read against the complete numerical CSS consumer. Also
   measure the complete reader with a simple font whose width is already the
   answer. These diagnostic controls can separate costs; neither may be reported
   as a complete replacement for the real calculation. Keep the input-write
   workload and output count matched when isolating the reader's cost.
2. **Does sharing one input vector across many outputs change the result?**
   Compare the digit font, variable font and CSS with the same small matrix,
   rather than giving every output its own independent inputs. This directly
   tests the workload difference left open by the current control.
3. **Can symbols be reused across positions and stages?** Build one reusable
   digit alphabet with explicit separators or routing markers, first at a small
   width. Require exact answers before testing whether it reduces both glyph
   count and execution cost. Smaller files alone are not a performance win.

These are proposed follow-ups, not completed results. A deeper calculation with
a nonlinear step could also make internal reuse more valuable, but the current
results do not establish that advantage. These synthetic four-bit inputs and
affine calculations do not establish real-model precision, nonlinear stages or
token speed. The independent [audit](AUDIT.md) and [reproduction guide](README.md)
provide implementation details and further limits.
