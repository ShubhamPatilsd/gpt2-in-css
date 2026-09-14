# Certified quantized GPT-2 output head

A quantized coarse score can drive an exact head if every row carries a
rigorous error radius. For query `h`, original row `w`, and represented row
`wq`, Cauchy gives:

```text
h·w ∈ [h·wq - ||h||₂ ||w-wq||₂,
       h·wq + ||h||₂ ||w-wq||₂]
```

The row error norm is precomputed; runtime needs one query norm and one scalar
bound addition per coarse candidate. The experiment covers all 1,024 saved
2/4/8/16-token states and asserts that every candidate set contains the dense
winner.

Activating every group whose upper bound exceeds the best coarse lower bound
is safe but conservative. Best-first refinement is much tighter: rank groups
by maximum upper bound, exact-score one whole group at a time, and stop once
the best exact score exceeds the next group's upper bound. This stopping rule
is also rigorous.

| Encoding | Approx. top 1 | Single-winner certified | Best-first groups median / p95 / max | Mean exact rows | Dense reduction |
| --- | ---: | ---: | ---: | ---: | ---: |
| Global int10 | 94.3% | 0% | 57 / 195 / 197 | 19,760 | 2.54x |
| Global int11 | 97.3% | 0.5% | 6 / 43 / 126 | 2,998 | 16.8x |
| Row-wise int8 | 72.4% | 0% | 196 / 197 / 197 | 41,836 | 1.20x |
| Row-wise int9 | 83.4% | 0.1% | 17 / 113 / 197 | 7,925 | 6.34x |
| Row-wise int10 | 93.5% | 2.0% | **3 / 15 / 49** | **1,212** | **41.5x** |
| Row-wise int11 | 96.1% | 9.7% | **2 / 5 / 17** | **557** | **90.3x** |

At token granularity, best-first int10/int11 need median 11/4 exact scores
and p95 37/12. Group activation inflates those counts but remains small enough
to unroll declaratively, especially for int11.

This is the first frozen-checkpoint search method here with an exact stopping
condition and a useful retained-row frontier. It does not remove the initial
50,257-row low-precision scan.

The browser implementation now passes its first two search steps. The
row-wise int10 upper head matches all 10 upper-group oracles in 36.66 seconds
cold. A 399-element masked reducer recovers the next group without rescoring
tokens, and a second 256-node int16 stage reuses the same fonts and dispatch
CSS. Best-of-two matches all 10 dense winners in 52.66 seconds cold; each
fixture mutation takes 2.95-6.38 seconds. Retain and continue unrolling.

The browser-realization audit now gives a conditional bound. At the production
±266.248 axis range, 19 coarse buckets and 8 fine buckets cover the observed
Chromium F2DOT14-floor plus 1/64-pixel metric model, so the existing symmetric
24-bucket allowance is sufficient relative to global-int16 weights at the
browser-realized coordinates. It is not a portable proof relative to the
original unrounded hidden vector, which needs a worst-case gap above 589
buckets plus a final int16 residual check.

A broader browser-budget screen also finds that the current ±135.309 axis
range covers only 70/1,024 saved states; ±266.248 is required with a 1% guard.
The search frontier survives this correction. With a conservative 24-bucket
allowance on both coarse and exact scores, int10 needs median/p95/max 3/18/61
groups, while int11 needs 2/6/22. See
`../gpt2-browser-certification-budget/RESULTS.md`.

A six-stage browser cascade now composes all routing, exact scoring,
best-so-far selection, and stopping logic. It matches all ten dense winners;
Chrome reaches the empirical stop in one to three groups. Hiding the remaining
nested stages after that flag cuts warm median latency from 7.936 to 4.806
seconds and mean latency by 42.3%, while correctly reopening for harder later
inputs. See
`../gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated/RESULTS.md`.

Naïvely extending that page to the int10 corpus maximum of 61 groups is not a
one-shot solution. It remains correct and warm-gated, but quadratic history
masks produce 24.100 MB of CSS and a 199.411-second first result. Incremental
two-bank masks reduce CSS to 11.969 MB but worsen first result to 228.468
seconds because each boundary carries 197 inherited mask properties. The
retained architecture is therefore a shallow gated fast path plus a future
compact tail fallback, not a monolithic 61-stage document.

Parallelizing exact groups is structurally possible but not yet faster. A
one-plane merge that packed score and global token into a multi-million-pixel
width lost subpixel token precision. Splitting the merge into a score/group
plane and a selected-token-anchor plane fixes that completely: 10/10 model
fixtures and 2/2 synthetic equal-score ties pass. Its 5.81-7.82 second measured
medians do not beat the 4.81-second gated serial cascade, so retain the
two-plane merge primitive for future batched/reduction-tree experiments rather
than the current default.

The production realized-coordinate corpus quantifies fast-path coverage: int10
certifies 79.0% within six groups, 84.9% within eight, 94.6% within sixteen,
and 99.3% within thirty-two. The 16-stage browser probe remains correct 10/10
but increases cold plus first result from 49.10 to 86.94 seconds and warm
median from 4.81 to 5.63 seconds. Six stages is the latency default; sixteen is
the high-coverage option before a compact tail fallback.

That tail can be exact in one wave. For the 215 states unresolved after six
groups, activate every remaining group whose upper bound is at least the
current best lower bound. This selects median/p95/max 5/25/70 groups and
retains/certifies the target winner on all 1,024 states. Its conditional mean
of 7.76 groups is nearly the 7.60-group sequential oracle, while removing up to
49 additional serial stages. Fixed-size batches do not close the corpus.

The full 197-branch browser topology now exists. A six-stage prefix plus gated
parallel tail passes an easy bypass, the one natural hard state inside the
current ±135.309 axis range, and a forced two-active-group merge. The page is
13.348 MB HTML / 6.011 MB CSS; cold plus first evaluation is 41.953 seconds,
and mutations span 4.125-10.073 seconds. A six-active diagnostic also
completes in 11.015 seconds, but one non-winning branch differs from the raw
float oracle. Retain this as the bounded-depth completeness topology, not the
latency default or a production-range proof: the ±266.248 corpus still needs a
browser-realized oracle/calibration for its p95 25 and maximum 70 active-group
tails. See
`../gpt2-hvar-grid-output-head-certified-int10-parallel-tail/RESULTS.md`.

Repeated small batches looked like the next latency candidate. For K=6 fallback states,
selecting four groups serially but exact-scoring them in one parallel wave
reduces the modeled critical path from mean 15.20 to 11.67 levels and p95 50 to
35, while over-scoring only 1.74 groups on average. Batches of 8 or 16 reduce
some depth percentiles further but waste 4.34 or 10.26 exact groups. Browser
evidence rejects that depth-only prediction: B=2 ties serial warm latency
(8.879 versus 8.842 seconds), while B=4/B=8 take 14.865/14.659 seconds versus
8.831/8.191 serial. B=2 remains the strongest proof-grade batch primitive, but
serial gating remains the latency default.

Moving exact-group selection into a numbered GSUB feature attacks a different
bottleneck: selecting among all 197 fine-score row banks takes 21.9 ms versus
226.0 ms with the 5.00 MB CSS dispatcher. Pure GSUB is not exact (98.73%
winner agreement), but its error is locally bounded to three score buckets for
groups 2 through 196 on the ten-fixture browser screen. Always falling back for
groups 0/1 and falling back whenever the GSUB top-two margin is at most six
buckets accepts 88.53% of cases with zero accepted winner errors. A CSS-only
second GSUB grid now extracts the runner-up, derives the margin, and
conditionally displays the exact scorer. It returns the exact final token in
20/20 selected bounded/full comparisons. Warm in-page ablation measures
14.5/24.1 ms accepted paths and identifies the second grid as the largest
incremental cost. The direct ten-fixture x 197-group screen then passes all
1,970 final-winner comparisons with zero unsafe accepts and eleven conservative
extra fallbacks. Its actual route accepts 87.97% and falls back on 12.03%; mean
time is 135.74 ms hybrid versus 220.16 ms exact (1.62x, 38.3% less), while the
fallback tail worsens p95 from 238.80 to 456.70 ms. Retain this as the strongest
empirical output switch. The six-bucket error radius remains a Chrome-153
observation rather than a portable proof. See
`../gsub-certified-hybrid/RESULTS.md`.

Three attempts to remove the fallback entirely do not improve that decision.
Forty-face constant-base GSUB reduces the bounded scorer to 263 DOM elements
but is 24.8% slower than CSS dispatch and still swaps 2/80 winners. A
0.03125 lattice scale clears the 32,768 px glyph-advance ceiling and makes GSUB
match a rescaled exact page in 80/80 cases, but both rescaled paths preserve
only 78/80 model-oracle winners and the GSUB advantage is just 24%. Keep the
score-plus-complement hybrid construction at the original scale. Merging each
static complement into its score glyph also reaches 80/80 winners and at most
one bucket error against a matched 0.0625-scale exact page, while switching in
4.6 ms versus 12.9 ms dispatch. It still matches only 78/80 production-scale
winners because lowering the scale removes Chrome clamp behavior already
present in the 0.1-scale exact comparator, so it is not a semantic replacement.

The overflow can instead be repaired without changing production scale. Split
only the h3 static complement into two integer advances: all five over-cap rows
become safe, groups 0/1 match 20/20 exact winners with maximum candidate error
two, and a margin greater than four accepts 19/20 cases with zero unsafe
accepts. Switching takes 5.5 ms versus 12.4 ms exact dispatch and adds one
glyph per candidate. This matters disproportionately because the first valid
six-stage integration sends 17/18 active stages through groups 0/1. That
unsplit composition is semantically correct across three rounds and 30 fixture
evaluations, but 51/54 active stages fall back and warm median regresses from
5.55 to 7.64 seconds. Reject the unsplit composition and integrate the split
bank before judging the hybrid architecture itself. The split-aware integration
then flips the route to 17/18 accepts and preserves all 10 final winners, yet
the conditional split/full dual-grid topology still takes 7.14 seconds versus
5.99 seconds exact and raises cold load from 59.2 to 70.4 seconds. The next
test should keep only the compact groups-0/1 hot bank and route every other
group directly to exact, removing the unused full-vocabulary GSUB grids.

The 1,024-state corpus confirms that this hotspot is real but not universal.
Groups 0/1 are independently the two most visited groups and account for
32.70% of all 5,288 exact-group evaluations; they fully cover 25.68% of state
paths. They dominate the first two positions, while 74.32% of states eventually
need a non-hot group. Treat hot-two as a predeclared early-stage accelerator
with exact fallback, not as a corpus-complete scorer. See
`../gpt2-best-first-group-hotspots/RESULTS.md`.

Removing the full GSUB bank does not rescue the composed topology. A focused
groups-0/1-only page sends 16/18 active stages through the compact split scorer,
uses one margin and one non-hot exact fallback, and remains exact on all ten
fixtures. It still takes 7.88 seconds warm versus 5.21 seconds exact (0.66x).
The cost is therefore the two-grid certificate and its dependency graph, not
merely the full-vocabulary bank. Reject this hot-two GSUB composition.

Exact root precomputation preserves the complete browser path: all 10 fixtures,
18 active stages, the group-1-to-0 route, and the non-hot group-5 fallback match
the live exact baseline. It is still the wrong scaling shape. Evaluating both
fixed 256-row hot grids for every mutation makes the clean fixture-0 case take
932.1 ms versus 519.7 ms exact, a 1.79x slowdown. Reuse cannot repay work that
was not demanded. The next probe therefore replaces the existing coarse rows
for groups 0/1 with exact rows in place and reuses their already-required group
maximum, adding no speculative grid.

That in-place mixed-precision upper head is the first composed optimization to
survive a robust screen. It replaces 512 existing int10 upper rows with exact
global-int16 rows, keeps the upper-row count unchanged, and reuses the selected
hot group anchor as its exact fine result. Across three rounds, all 30 fixtures
and 39 active-stage gates match live exact shadows and all dense winners. It
removes 36/39 fine-grid evaluations and improves warm mean from 5.340 to 3.844
seconds (0.720x, 28.0% faster); each round wins independently. Cold load also
wins in all three rounds. Retain this topology. A 512-glyph exact-font subset
is a separate cold-start profile: it reduces startup WOFF2 requests from
130.61 MB to 65.32 MB and conditional cold mean from 61.45 to 49.11 seconds,
while passing 24/24 mutations and 48/48 stage gates. It does not replace the
warm default: hot mutation is 5.7% slower and the first non-hot transition
defers 66.18 MB of full-bank requests. Keep the full-bank mixed head for loaded
throughput and the subset profile for cold, predominantly hot routing.

A hot-K sweep confirms that two exact upper groups are the useful precision
knee rather than an arbitrary first choice. Recomputing routes for 1,024 states
keeps all targets for K=0/1/2/4/8/16/32. In a paired ten-fixture browser screen,
K=1/2/4/8 all pass exact stage gates, with normalized warm ratios
0.806x/0.641x/0.729x/0.711x. K=2 is also fastest in absolute time (3.496 s
mean). K=8 removes the final dynamic fine grid on these fixtures, but its 2,048
always-on exact upper rows cost more than that last serial stage saves. Keep K=2.

Replacing those 512 exact upper rows with the split GSUB scorer is not an
in-place optimization. GSUB selects metrics but does not compute argmax, so
groups 0/1 still require 512 Grid candidates; certification adds a 256-row
runner-up pass and the split representation increases glyphs from 12 to 13 per
candidate. The offline gate therefore rejects this route without a browser run.

Changing the group size also fails to displace the retained 256-token geometry.
An offline 128/256/512/1024 sweep retains all 1,024 targets and suggests G128 as
a narrow work-proxy win, but the browser cannot transport its local winner
exactly. G128 preserves score buckets yet shifts token identity at 4, 8, 16,
and 32 px score strides, even when the tie step grows from 1/32 to 1/4 px.
Because the error grows with total anchor geometry rather than disappearing
with wider spacing, G512/G1024 do not receive a timing screen. Keep G256.

The TrueType advance fields are less restrictive than the original builder
assumed. Chrome preserves signed out-of-range HVAR results inside a compensated
run and can accumulate an effective base near 500,000 units from always-on
regions. A six-glyph direct-int16 hot row therefore serializes and shapes. It is
not an exact replacement for the retained twelve-glyph high/residual row:
fixture 1 group 1 moves by one score bucket, and the two-fixture warm screen is
15.2% slower. Keep the two-plane scorer until an encoding reproduces its
browser-realized rounding, not merely its algebraic dot product. See
`../hvar-resulting-advance-range/RESULTS.md`,
`../hvar-virtual-base/RESULTS.md`, and
`../gpt2-virtual-base-oneplane-hot2/RESULTS.md`.

One shared fixed compensator cannot remove the expensive virtual-base regions.
Although 45,121 units cover the full corpus/fixture screen and the resulting
eight-glyph row is preliminarily 22.3% faster, compensation does not cross font
fallback-run boundaries. Both tested fixtures choose wrong routes by thousands
of buckets. One compensator per 128-axis shard would return to the original
twelve-glyph floor. See `../gpt2-compensated-oneplane-hot2/RESULTS.md`.

An aligned exact residual does not bypass that floor either. Global-int16 codes
decompose exactly into an aligned int10 row plus a three-glyph residual with
coefficients in [-32,32], but CSS adds two already-snapped live widths. Group 0
then differs from the twelve-glyph shadow on 2,397/2,560 candidate buckets and
10/10 winner buckets. The residual grid is 1.255x slower. See
`../gpt2-aligned-residual-group/RESULTS.md`.

Per-token uncertainty closure is semantically sound but not a scaling win in
its direct CSS form. A two-level 256-carrier gate keeps only 3-15 group-0 exact
rows (mean 7.6) and passes every active-set, bucket, winner, equality, and tie
check. Across 50 order-balanced mutations it is nevertheless slower on median,
mean, and p95 (165.4 ms versus 160.65 ms full median). See
`../gpt2-token-uncertainty-gate/RESULTS.md`.

Gating contiguous exact-row blocks fixes the carrier topology in isolation.
B=4/B=8 use 64/32 carriers and shape 20.4/28.8 fixture rows; both pass all 30
browser cases. Over ten rounds B=4 measures 9.84 ms mean versus 159.66 ms full
(16.2x), while B=8 measures 10.31 versus 156.58 ms (15.2x). Corpus group-0
means are 55.1/68.3 shaped rows. But the full hot-2 integration must restore
512 five-glyph centers to drive those bounds. Direct A/B then makes B=4 4.5%
slower and B=8 31.7% slower than retained mixed-hot2. Keep the block-wrapper
primitive, reject this duplicated-center integration; see
`../gpt2-token-uncertainty-block-sweep/RESULTS.md`,
`../gpt2-token-uncertainty-block-gate/RESULTS.md`, and
`../gpt2-mixed-hot2-block-gate-b4/RESULTS.md`.

The winning composition derives each token interval from the already-paid int10
upper width instead of restoring another center bank. A direct 197-anchor
maximum replaces the outer view-timeline bucket extraction, allowing gated
exact maxima to participate in the unchanged best-first decoder without an
intrinsic-width cycle. B=4 passes 30/30 full-route checks and improves warm mean
8.0% and median 17.3% against mixed-hot2. Its 51.33-second cold load is 28.1%
worse and its observed maximum is noisy, so it is retained specifically for
loaded recurrent inference in that comparison. It is subsequently superseded:
holding the direct maximum constant, the original full hot grids are 5.8%
faster by mean and 5.2% by median. B=8 is not promoted. See
`../gpt2-mixed-hot2-reused-upper-block-gate-b4/RESULTS.md`.

The direct-maximum ablation is the stronger general result. One 197-way anchor
maximum replaces all outer view-timeline inversions while every score row and
downstream decoder stays unchanged. It passes 30/30 broad checks and improves
warm mean 22.8%, median 20.5%, and p90 30.6% against mixed-hot2. Pruning the
dead timeline graph is warm-neutral but improves paired cold load 35.1%.
Physically stripping the leftover dead CSS is not additive: a 6/6 exact screen
changes cold load by less than 1% and regresses warm mean 2.8%.
Co-activation quartet clustering removes another 35.3% of holdout hot-row work
but remains slower in Chrome, confirming that gate dependencies dominate row
shaping after the router fix. See
`../gpt2-mixed-hot2-direct-outer-max/RESULTS.md`.

Materializing the direct maximum as 13 fan-in-16 chunks plus one root is a
further exact improvement. Against the pruned flat node, 30/30 checks pass and
mean/median/p90/maximum improve 2.5%/1.0%/10.6%/12.5%. Packing group identity
into the maximum is mean-neutral and median-negative; simple hierarchical
reduction is the better balanced topology. See
`../gpt2-mixed-hot2-hierarchical-outer-max16/RESULTS.md`.

Further first-stage compression is negative. Packed-four and chunk/slot
identity decoders preserve the eventual exact final token but fail the initial
route contract and are substantially slower. A zero-node nested functional
maximum passes 30/30 but is 1.043x by mean and 1.060x by median versus the
materialized tree. Keep explicit fan-in-16 reduction anchors.

Grid is not required inside each 256-row score group. A zero-height in-flow
block container has the same max-content maximum, preserves all 30/30 routes
and winners, and improves mean 7.9% and median 6.2% versus the fan-in-16 Grid
page. Trace evidence attributes the gain to 13.3% less layout and 30.2% less
style recalculation; all roughly 50.5k row-shaping calls remain. Keep the
fan-in-16 outer tree but use block flow for group reduction; see
`../gpt2-mixed-hot2-blockflow-group-max/RESULTS.md`.

Do not propagate that change into the conditional exact reducer or delete the
old scroll boundary: their exact two-fixture screens regress mean 4.6% and
10.4%, respectively.

Widening only the row-wise-int10 coarse carrier from five 160-axis faces to
three 256-axis faces is exact at the composed-head boundary. Chrome accepts the
required greater-than-65,535 shaped HVAR results; all 30 routes, buckets, and
final winners pass. Loaded mean improves 2.0%, p90 improves 11.9%, and traced
shaping time drops 29.8%, although paired cold load regresses 11.1%. Retain the
three-shard page for loaded inference and the five-shard block-flow page for
cold startup; see
`../gpt2-mixed-hot2-blockflow-group-max-shard256/RESULTS.md`.

The most conservative six-glyph repack also fails exact identity. Keeping the
same high/residual split but merging adjacent shards into three 256-axis pairs
needs no virtual bias and is preliminarily 2.8% faster. It nevertheless moves
fixture 1 group 1 from bucket 12,620 to 12,621, proving that the number of font
run snaps is itself observable. Keep the twelve-glyph 128-axis-pair transport;
see `../gpt2-twoplane-256axis-hot2/RESULTS.md`.

## Reproduce

```sh
make analyze-gpt2-quantized-head-certification
```
