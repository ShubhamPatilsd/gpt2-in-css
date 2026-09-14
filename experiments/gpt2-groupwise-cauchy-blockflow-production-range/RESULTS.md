# Production-range homogeneous groupwise cascade

## Decision

**Retain as the production-range exact-output-head proof.** This keeps the
OpenAI GPT-2-small architecture and checkpoint unchanged. It also reuses the
existing row-wise-int10 and global-int16 WOFF2 banks without rebuilding or
copying them.

The key range trick is positive homogeneity. The font-axis denominator grows
from 135.309 to the observed production range 266.248, but the post-font score
gain stays at its old value. Every logit is therefore multiplied by the same
positive factor, 0.508206, so argmax is unchanged. Unlike multiplying the row
factors by 1.9677, this does not amplify HVAR's integer interpolation error.

The first attempted zero-copy rescale did multiply those row factors. Its axes
and bounds were live, but only 3/6 difficulty-selected fixtures passed: the
doubled carrier error caused a false one-stage stop on the hardest state. That
variant is rejected.

## Browser proof

Chrome 153 passes all six selected fixtures on the corrected page. The set
contains production-corpus states requiring 23, 17, 7, 1, 1, and 1 groups in
the conservative offline screen. Browser-realized active counts are
23, 13, 7, 1, 1, and 1; every visited group matches the composed route,
non-hot scores match the independent exact shadow, hot scores stay within
their existing 24-bucket allowance with the same winner, every incumbent and
stop recomputes, and all final global-int16 winners match.

The hardest state traverses all 23 stages and selects token 1899. All 96 block
norms and font axes change across inputs, all 195 non-hot bound glyphs are
live, and 1,170/1,170 measured bounds are conservative: 1,165 exact and five
one-bucket outward. The page contains no scripts and loads with JavaScript
disabled.

Chrome exposed a bounded one-bucket downward transport error in the
remaining-upper readback at two intermediate stages. The production page
therefore raises the stopping margin from 48 to 49 buckets. Requiring a
reported gap greater than 49 ensures that the underlying gap still exceeds
48 even at the measured one-bucket shortfall.

## Corpus and cost

Across all 1,024 saved production states, the homogeneous 49-bucket screen
needs 2.402 exact groups on average, median 2, p95 7, and maximum 23. It closes
961 states within six groups, 1,007 within twelve, 1,023 within twenty-two,
and all 1,024 within twenty-three. This is corpus completeness, not a proof for
every mathematically possible hidden vector.

The candidate is 8.07 MB HTML plus 4.12 MB routing CSS. It generates only a
16.8 KB production bound font; the large q10/q16 font banks are shared. Four
production mutations take 14.20 s, 8.48 s, 1.86 s, and 2.14 s. The 23- and
13-stage tails dominate, so this is a correctness/range milestone rather than
the new low-latency default. Cold candidate load is 51.97 s.

The scaling conclusion is asymmetric: positive-homogeneous range expansion
solves font-bank duplication, while serial exact-stage depth still scales
poorly in the hard tail. The next ambitious target should reduce that tail's
dependency depth without reintroducing a dense 50,257-row fallback.

Nothing was committed or pushed.
