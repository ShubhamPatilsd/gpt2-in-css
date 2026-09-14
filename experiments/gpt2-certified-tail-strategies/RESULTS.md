# Certified compact-tail strategies

This analysis keeps the retained production contract fixed: 1,024 contextual
states, a ±266.2484 input range, global-int16 weights evaluated at the same
F2DOT14-realized coordinates as the production screen, a row-wise int10 coarse
head, and the asymmetric Chromium allowances of 19 coarse buckets and 8 fine
buckets. A best-first stop therefore requires a separation strictly greater
than 27 buckets; equality remains active for score/token tie safety.

## Result

A six-group fast path followed by one **dynamic parallel uncertainty closure**
is the smallest-depth exact architecture in this screen. The six-group prefix certifies
809/1,024 states (79.0%). For the remaining 215 states, activate every unscored
group whose coarse upper bound can still beat the current refined lower bound,
score those groups exactly in parallel, and perform one final reduction.

That tail activates a median 5 additional groups, p95 25, and at most 70 among
fallback states. In row terms it scores a median 1,280 additional rows, p95
6,400, and at most 17,745. Averaged over all states, the dynamic tail adds only
415.3 exact rows. It certified all 1,024 screened states in one tail wave, and
the global-int16 target winner's group was retained by the prefix-or-candidate
set for every state at every tested prefix.

The uncertainty closure is nearly as selective as sequential best-first search:
after K=6 it selects 7.76 groups on average conditional on fallback, versus
7.60 additional groups for a sequential oracle. The small excess buys removal
of a variable-depth cascade and its repeated routing/reduction stages.

The browser probe changes the latency decision. A static 197-branch closure
passes official 0/1/2-active fixtures, but creates 159,005 elements and takes
4.125-10.073 seconds per mutation (8.592-second median). A six-active
diagnostic takes 11.015 seconds and one non-winning branch differs from the raw
float oracle. The closure is retained as a bounded-depth completeness shape,
not as the speed recommendation.

## Prefix and tail distributions

The following distributions assign zero tail work to states already certified
by the prefix. Entries are median / p95 / maximum, followed by the mean.

| K | Prefix coverage | Fallbacks | Parallel groups overall | Parallel rows overall | Sequential groups overall |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 67.5% | 333 | 0 / 13 / 72; 2.24 | 0 / 3,328 / 18,257; 570.6 | 0 / 13 / 51; 2.18 |
| 6 | 79.0% | 215 | 0 / 11 / 70; 1.63 | 0 / 2,816 / 17,745; 415.3 | 0 / 11 / 49; 1.60 |
| 8 | 84.9% | 155 | 0 / 9 / 47; 1.20 | 0 / 2,304 / 12,032; 307.0 | 0 / 9 / 47; 1.20 |
| 16 | 94.6% | 55 | 0 / 1 / 39; 0.42 | 0 / 256 / 9,984; 108.5 | 0 / 1 / 39; 0.42 |

Conditional only on states that reach the tail:

| K | Parallel groups | Additional parallel rows | Additional sequential groups |
| ---: | ---: | ---: | ---: |
| 4 | 4 / 21 / 72; 6.88 | 1,024 / 5,376 / 18,257; 1,754.7 | 4 / 21 / 51; 6.69 |
| 6 | 5 / 25 / 70; 7.76 | 1,280 / 6,400 / 17,745; 1,977.9 | 5 / 25 / 49; 7.60 |
| 8 | 6 / 23 / 47; 7.95 | 1,536 / 5,888 / 12,032; 2,028.0 | 6 / 23 / 47; 7.95 |
| 16 | 5 / 25 / 39; 7.89 | 1,280 / 6,400 / 9,984; 2,020.1 | 5 / 25 / 39; 7.89 |

The non-multiples of 256 occur when the final 81-token vocabulary group is
selected. Prefix-inclusive row distributions are available in `results.json`.

## Fixed next-batch tails

Each cell is the residual fallback rate over all 1,024 states after scoring the
next fixed batch; the parenthesized value is conditional on reaching that K
prefix's tail.

| K | +2 groups | +4 groups | +8 groups | +16 groups |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 21.00% (64.56%) | 15.14% (46.55%) | 8.20% (25.23%) | 2.93% (9.01%) |
| 6 | 15.14% (72.09%) | 11.62% (55.35%) | 6.64% (31.63%) | 1.95% (9.30%) |
| 8 | 11.62% (76.77%) | 8.20% (54.19%) | 5.37% (35.48%) | 1.86% (12.26%) |
| 16 | 3.81% (70.91%) | 2.93% (54.55%) | 1.86% (34.55%) | 0.68% (12.73%) |

Fixed batches are simple, but none closes the corpus. Even K=16 plus another 16
groups leaves seven states for a third mechanism. K=6 plus 16 leaves 20 states
while eagerly scoring 16 groups on every fallback, compared with a mean 7.76
for the exact uncertainty set.

## Repeated batched best-first tail

A better middle ground selects `B` unvisited groups with serial lightweight
upper routers, scores those `B` groups in one parallel exact wave, then checks
the certificate. The table models states that reach the K=6 fallback. “Levels”
counts one level per group selector plus one exact-score/merge level per batch;
it is a dependency-depth model, not a wall-clock claim.

| B | Batches median / p95 / max | Groups scored median / p95 / max | Over-scored groups mean | Levels median / p95 / max; mean |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 5 / 25 / 49 | 5 / 25 / 49 | 0.00 | 10 / 50 / 98; 15.20 |
| 2 | 3 / 13 / 25 | 6 / 26 / 50 | 0.53 | 9 / 39 / 75; 12.20 |
| 4 | 2 / 7 / 13 | 8 / 28 / 52 | 1.74 | 10 / 35 / 65; **11.67** |
| 8 | 1 / 4 / 7 | 8 / 32 / 56 | 4.34 | **9** / 36 / 63; 13.44 |
| 16 | 1 / 2 / 4 | 16 / 32 / 64 | 10.26 | 17 / **34** / 68; 18.98 |

`B=4` is the best balanced *dependency model*: it minimizes mean modeled depth,
cuts p95 levels 30% versus serial, and adds fewer than two unnecessary exact
groups on average. The browser result shows why this model alone is not a
latency predictor.

The implemented B=1/2/4/8 probe passes selection, two-plane merge, final winner,
next-group, and strict-certificate checks. B=2 is the widest raw-oracle-clean
fixture result, but is merely tied with serial warm latency (8.879 versus 8.842
seconds). B=4 and B=8 regress to 14.865 and 14.659 seconds versus 8.831 and
8.191 seconds serial. Their forced fixture also reaches the already-known
non-winning group-91 browser scorer drift. Parallel scoring shortens abstract
depth but Chrome still pays for every eagerly shaped group.

## Recommended CSS shape

Retain the measured serial six-stage gated prefix as the latency default. Keep
B=2 as the compact proof-grade batched primitive when bounded dependency depth
matters, but do not repeatedly batch four or eight groups for throughput. Keep
the full 197-branch uncertainty closure only as a final completeness reference;
neither form beats serial gating on warm mutations. The next useful optimization
must reduce scorer dispatch/shaping cost, not only rearrange its dependency
levels.

The analyzer also asserts two correctness invariants for every K in 4/6/8/16:

- the target winner group is present in the exact prefix or parallel candidate
  set for all 1,024 states;
- after scoring the candidate set, every excluded group remains below the final
  best lower bound, so the one-wave closure is sufficient.

```sh
make analyze-gpt2-certified-tail-strategies
```
