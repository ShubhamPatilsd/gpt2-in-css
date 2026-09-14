# GSUB-certified hybrid composition

Decision: **retain as the strongest empirical output switch; correctness passes**.

Page geometry returned the exact final token in 20/20 comparisons across the
bounded and full banks. Six cases accepted GSUB with the exact stage at
`display:none`; fourteen cases, including groups 0/1 and the near ties,
activated the exact stage as `grid`. JavaScript only supplied the hidden
vector, score floor, and group, then observed layout.

| Median mutation | Time |
| --- | ---: |
| Bounded pure GSUB, accepted cases | 37.79 ms |
| Bounded hybrid, accepted cases (cold one-round harness) | 219.19 ms |
| Bounded accepted topology overhead (cold one-round harness) | 181.40 ms |
| Full pure GSUB, accepted cases | 40.42 ms |
| Full hybrid, accepted cases (cold one-round harness) | 225.05 ms |
| Full accepted topology overhead (cold one-round harness) | 184.63 ms |
| Exact CSS-dispatched baseline, all cases | 228.58 ms |
| Bounded hybrid, fallback cases | 463.46 ms |
| Full hybrid, fallback cases | 470.04 ms |

Those one-round values include cold samples and Playwright boundaries and are
not steady-state topology costs. The seven-round in-page ablation in
`ABLATION-RESULTS.md` measures accepted paths at 14.5 ms bounded and 24.1 ms
full. The second grid/readback accounts for 7.1/12.0 ms and is the dominant
incremental component.

The adversarial mixed-transition stress intentionally sends 7/10 cases to
fallback. Its fallback medians are 440.0/452.7 ms versus 231.85 ms exact, while
accepted medians are 41.0/45.1 ms. The later direct full-screen run supersedes
the earlier 86.77-104.79 ms projection: all 1,970 cases matched the separate
exact page, with zero unsafe accepts and eleven conservative extra fallbacks.
The CSS route accepted 1,733 cases (87.97%) and fell back on 237 (12.03%). Mean
in-page time was 135.74 ms hybrid versus 220.16 ms exact, a 1.62x speedup and
38.3% reduction. Median improved from 220.10 to 47.20 ms, while p95 regressed
from 238.80 to 456.70 ms because the fallback evaluates both paths. See
`full-screen/RESULTS.md`.

Changing the exact-stage presentation gate does not improve the full-bank
projection. Conditional `content-visibility` remains correct but projects
107.91 ms versus 106.31 ms for the current `display:none/grid`; conditional
`visibility` keeps exact layout live and projects 508.47 ms. Retain the current
display gate. See `FALLBACK-GATING-RESULTS.md`.

## Readback clarification

In this saved one-round result, `comparison.exactWinner` is the hybrid page's
internal exact readback. It is expected to be default/stale when the accepted
path makes `#exact-stage` `display:none`. Correctness did not use that stale
field: it compared `finalWinner` with the separately loaded exact-baseline
page before the diagnostic object spread overwrote the same JSON key. The
harness source now names these values `activeExactWinner` and
`baselineWinner` separately. Accepted cases also match their offline expected
local winner.

## Limitations

The six-bucket threshold is empirical, not a portable proof. The direct
full-screen coverage is ten fixtures across all 197 groups in Chrome 153; it
does not certify arbitrary hidden vectors, font banks, browsers, or versions.

## Six-stage composition

The first full output-head integration is semantically valid but loses on its
actual route distribution. Across three fresh rounds and 30 fixture mutations,
all final winners and stage checks pass, yet only 3/54 active fine stages accept
GSUB. The int10 upper router selects groups 0/1 in 51/54 stages, and this
unsplit hybrid forces both exceptional groups to exact. Warm median is therefore
7.64 seconds hybrid versus 5.55 seconds exact (0.73x); reject that composition.
The production-scale split-complement repair bounds groups 0/1 to two buckets
and accepts 19/20 focused cases at margin >4. Its integration flips the route
to 17/18 GSUB accepts and keeps all 10 final winners exact, but the conditional
split/full dual-grid page still takes 7.14 seconds versus 5.99 seconds exact
and raises cold load from 59.2 to 70.4 seconds. Reject both six-stage full-bank
compositions; the remaining targeted test keeps only the compact groups-0/1
bank and routes all other groups directly to exact. See
`../gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hybrid/RESULTS.md`,
its `UNSPLIT-RESULTS.md`, and
`../gsub-split-complement-fine-scorer/RESULTS.md`.

Dropping the full bank entirely also loses. A compact groups-0/1-only variant
uses the split scorer for 16/18 active stages, sends one near-margin and one
non-hot stage to exact, and matches all ten final winners. Warm median is still
7.88 seconds versus 5.21 seconds exact. This isolates the scaling failure to
the two-grid certificate/dependency topology rather than the full 197-group
assets. See
`../gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hot2/RESULTS.md`.

Precomputing exact groups 0/1 at the root also fails despite passing the full
10-fixture, 18-stage semantic screen. Its clean hot fixture takes 932.1 ms
versus 519.7 ms exact because both 256-row grids run on every mutation. The
follow-up changes the topology rather than the scorer: replace those groups'
existing coarse rows with exact rows and reuse the selected group maximum, so
no parallel fine grid is added.

That in-place upper-row replacement succeeds. A robust three-round screen
passes 30/30 fixtures and 39/39 live exact stage checks, removes 36/39 fine-grid
evaluations, and improves warm mean from 5.340 to 3.844 seconds (28.0%). All
three load-order/fixture-order rotations win. This confirms the broader lesson
from the GSUB failures: the scalable optimization is not merely a faster local
scorer; it must remove an existing composed layout stage without adding a
parallel certificate graph. See `../gpt2-mixed-precision-hot2-upper/RESULTS.md`.

A hot-two exact-font subset is useful only as a deployment profile. It passes
24/24 mutations and cuts startup WOFF2 requests from 130.61 MB to 65.32 MB,
but hot mutation is 5.7% slower and first non-hot use defers 66.18 MB. Keep the
full-bank mixed head for loaded throughput; use the subset only when cold start
and predominantly hot routing dominate. See
`../gpt2-mixed-precision-hot2-upper-subset/RESULTS.md`.
