# Three-pair 256-axis two-plane hot-2 rows

Decision: **reject-transport**.

The retained global-int16 high/residual decomposition is unchanged. Adjacent 128-axis shards are merged, reducing each retained group-0/1 exact row from twelve glyphs to six (three high/residual font pairs), with no virtual-bias axes.

## Exactness gate

- Two-fixture falsification: 1/2 exact live route identities.
- The 3×10 screen was not run because falsification failed.
- Compared exactly at every live stage: group, fine code/local, fine bucket/winner, best bucket/winner, next upper, certificate gap, and done state.
- 256-axis L1 maxima: H0 2,672, R0 35,682, H1 2,643, R1 35,999, H2 2,562, R2 35,803; maximum positive resulting advance 72,030.
- Stored bases use L1 + 32, all at or below 65,535.

### Exact mismatches

- two-fixture-falsification, round 0, fixture 1, stage 0 `certificateGap`: candidate `-205`, retained `-204`.
- two-fixture-falsification, round 0, fixture 1, stage 0 `nextUpperBucket`: candidate `12645`, retained `12644`.
- two-fixture-falsification, round 0, fixture 1, stage 1 `fineBucket`: candidate `12621`, retained `12620`.
- two-fixture-falsification, round 0, fixture 1, stage 1 `bestBucket`: candidate `12621`, retained `12620`.
- two-fixture-falsification, round 0, fixture 1, stage 1 `certificateGap`: candidate `45`, retained `44`.
- two-fixture-falsification, round 0, fixture 1, stage 2 `bestBucket`: candidate `12621`, retained `12620`.
- two-fixture-falsification, round 0, fixture 1, stage 2 `certificateGap`: candidate `250`, retained `249`.
- two-fixture-falsification, round 0, fixture 1, final `finalBucket`: candidate `12621`, retained `12620`.

The root mismatch is fixture 1, stage 1, group 1: token 477 is still selected, but its bucket is 12,621 instead of the retained 12,620. That one-bucket difference is already visible as the preceding stage's next-upper value and then propagates through best-bucket and certificate-gap state. Groups, winners, and done states happen to remain unchanged, but the required exact live identity does not.

## Preliminary falsification timing

| Metric | Three-pair 256-axis | Retained twelve-glyph |
| --- | ---: | ---: |
| warm mean (2 paired samples) | 3737.9 ms | 3844.6 ms |
| warm median | 3867.3 ms | 4230.1 ms |
| warm p90 | 3867.3 ms | 4230.1 ms |

Mean ratio: **0.972x** (2.8% faster).

| Round | Page load order | Three-pair mean | Retained mean | Ratio |
| ---: | --- | ---: | ---: | ---: |
| 0 | three-pair-256-axis then retained-twelve-glyph | 3737.9 ms | 3844.6 ms | 0.972x |

The browser-realized route is not exactly identical, so timing is preliminary and no scaling claim is made.

Chrome: 153.0.8010.36. Raw observations, request failures, cold loads, and exact mismatch records are in `browser-results.json`.
