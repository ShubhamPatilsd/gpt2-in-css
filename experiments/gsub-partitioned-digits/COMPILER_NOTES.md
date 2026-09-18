# What compact rules still make the browser do

The new compiler shares digit symbols by their place in a number and packs its
context rules into fewer font subtables. Neither change removes the running
total: it still adds the second input, then the third, and so on. These notes
describe source structure and a possible next experiment. They do not assign
measured CPU time to individual font-engine operations.

## Work remaining in the current program

Each number has four base-16 digits. Before an addition, the text contains one
accumulator word and the remaining operand words. Every word has a marker plus
four digits. With `m` words remaining, that is `5m + 1` glyphs, including the
zero-width nonce.

Each addition uses seven top-level lookups: four digit steps, marking consumed
digits, absorbing the old word, and normalizing the new digits. The full program
has `7N` top-level calls, including its product, dependent-operation, and
publication stages. Packing the rules changes their storage, not those calls.

A digit lookup targets all glyphs for its digit slot. At that moment each of the
`m` words has one such glyph, although only the next operand should receive the
addition. Across the four digit steps and all additions, the nominal number of
eligible target positions is:

```
4 × (N + (N−1) + … + 2) = 2N² + 2N − 4
```

At 64 inputs this is 8,316 eligible positions for 252 useful digit additions.
There are also the other three passes per addition. A model in which every
lookup scans the remaining buffer therefore has quadratic scan work. These
are coverage opportunities derived from the generated program, not observed
engine visits: lookup skipping, internal caches, and buffer implementation can
change the actual work. The arithmetic itself requires only `N−1` additions of
four-digit words.

The compiled structure has these separate counts:

| Quantity | Current formula |
| --- | ---: |
| Glyphs | 406 |
| Top-level lookup calls | `7N` |
| Total lookup definitions | `7N + 82` |
| Emitted FEA rule statements | `115N + 1510` |
| Referenced subtables, coverage layout | `115N − 23` |
| Referenced subtables, packed layout | `7N + 82` |
| Peak glyph buffer | `5N + 1` |

The FEA statement count is not the number of distinct binary mapping entries.
Repeated binary data can share storage while repeated lookup references still
request execution. The two layouts have byte-identical FEA programs; packing
preserves their rule order, matches, and nested actions.

## What the earlier tree did and did not establish

The earlier node-specific tree really grouped independent additions into shared
passes. It was not merely a differently named sequential program. Nevertheless,
the 64-input measurements were:

| Quantity | Running total | Tree |
| --- | ---: | ---: |
| Additions | 63 | 63 |
| Glyphs | 17,604 | 17,604 |
| FEA rule statements | 90,135 | 90,135 |
| Top-level calls | 385 | 43 |
| Total lookup definitions | 404 | 62 |
| Referenced subtables | 407 | 65 |
| Raw GSUB bytes | 396,194 | 387,014 |
| WOFF2 bytes | 40,352 | 53,388 |
| Complete-path median, ms per 256 outputs | 107.8 | 186.6 |
| Separate profile: layout total, ms | 1,392.2 | 2,982.0 |

The timing was one corrected sweep. The profile used 20 measured updates after
five warmups; it is a separate observation, not a decomposition of the median.
See the [original results](../gsub-weighted-sum-probe/RESULTS.md).

Inspection of the actual fonts shows both already use Format 2 class-context
tables. The first tree level's digit lookup covers 512 glyphs, with 512 rules
for the low digit and 1,024 for a higher digit. The corresponding sequential
lookup covers 16 glyphs, with 16 or 32 rules. The tree groups rules into separate
first-input class sets, however: it would be incorrect to say every target
searches all 1,024 rules.

Fewer passes therefore did not remove the additions, the node-specific digit
alphabets, or the large shared constant-addition mappings. The tree made broader
tables active at once. Cache behavior and table dispatch are possible causes of
its slower result, but they have not been isolated. The profile establishes that
the additional elapsed work is largely in the browser's layout category, which
includes shaping and other work. It does not prove a specific CPU mechanism.

## One different experiment: dispatch from the accumulator marker

Instead of repeatedly scanning for any digit in a slot, make the unique
accumulator marker the first target of the calculation. One outer contextual
lookup would contain a flat ordered list of nested actions: four local digit
steps, marking, absorption, and normalization for each successive operand.
The inner arithmetic tables would be shared; the outer list would repeat action
records rather than whole top-level passes.

Each inner context would start at the marker and inspect just the nearby
accumulator and next operand. Its substitution records could still act on a
later digit in that small context. The marker survives absorption at the same
logical location. A flat action list avoids recursion depth growing with the
number of operands.

The proposed benefit is one initial scan/match plus `O(N)` local arithmetic
dispatches, with `O(N)` action records and a fixed collection of arithmetic
tables. This is not a demonstrated engine complexity bound. In particular,
deleting glyphs can make the engine update contextual input-position bookkeeping;
that could retain quadratic work. Matching the entire original input in the
outer context would keep consumed glyphs inside its matched range, but also
creates an `O(N)` context. Whether repeated actions correctly retain the marker's
position after those deletions is the first uncertainty to test.

An accept/reject sequence would be:

1. Construct only a two-addition fixture and inspect its intermediate glyphs.
   Reject the design if the second action loses its target after absorption, if
   substitutions escape their intended words, or if engine limits stop it.
2. Check all 65,536 four-input vectors, with an action-disabled control and the
   unchanged native CSS numerical reader. Require exact output and carry cases.
3. If correct, compare the same inputs at 16 and 64 against the current packed
   program, including full mutation-to-consumer time. Count actual top-level and
   nested action records. A smaller font or fewer passes alone is not success.
4. Attempt 256 only after those gates, checking every coordinate and seeded
   cases. Stop on validator, operation-budget, or correctness failure.

Even a successful implementation would still compute additions serially. It
would not automatically share arithmetic among many distinct output rows;
real rows require their own products and reductions. It would add no nonlinear
operation, and its four-digit integer contract would still not establish GPT-2
floating-point accuracy. Those remain independent problems after dispatch.

No version of this proposal has been implemented or benchmarked here.
