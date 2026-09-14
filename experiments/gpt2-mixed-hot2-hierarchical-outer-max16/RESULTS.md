# Hierarchical outer maximum, fan-in 16

Decision: **superseded by block-flow group reduction**.

The flat direct-max node reads 197 group-score anchors. This variant materializes
13 chunk maxima over at most 16 anchors each, then takes one maximum over those
chunks. Score rows, tie semantics, and all winner decoders are unchanged.

Against pruned flat direct-max, the broad run passes 30/30 exact checks.

| Metric | Fan-in 16 | Flat pruned | Ratio |
|---|---:|---:|---:|
| Mean | 3,022.1 ms | 3,099.7 ms | **0.975x** |
| Median | 3,022.5 ms | 3,054.3 ms | **0.990x** |
| p90 | 3,884.5 ms | 4,344.2 ms | **0.894x** |
| Maximum | 4,156.4 ms | 4,752.8 ms | **0.875x** |
| Cold load | 52,526 ms | 51,139 ms | 1.027x |

The extra reduction level improves mean 2.5%, median 1.0%, p90 10.6%, and
maximum 12.5%, with a 2.7% cold-load regression in this run. This is a small
throughput gain but a robust tail improvement, and unlike gating or packed
identity it adds only 13 simple fixed boxes.

## Fan-in sweep

Narrow head-to-heads against fan-in 16 reject fan-in 8 and 32: their mean ratios
are 1.034x and 1.060x and median ratios are 1.190x and 1.177x. Fan-in 64 looked
faster narrowly, but its direct 30-pair confirmation is 1.019x mean and 1.053x
median while improving p90 to 0.854x. Keep 64 only as a tail-specialized profile.

Adding `contain:size layout style` to the 13 chunk boxes is unstable. One broad
run versus uncontained improves mean 4.7%, but a direct broad run versus flat
has a 9.27 s outlier, regressing mean 2.8% and maximum 87%. Do not retain it.

Chrome: 153.0.8010.36. Primary raw results are in
`ab-broad-vs-flat-pruned.json`.

## Later decoder and expression ablations

Three attempts to remove intermediate boxes or the remaining flat decoder fail
to supersede this topology:

- Nesting the same thirteen bounded `max()` calls inside one width property is
  exact over 30/30 pairs but regresses mean 4.3% and median 6.0%.
- Four-group packed identity blocks fail initial-route checks and are 55.7%
  slower by mean in the narrow screen.
- A non-expanded 13-chunk/16-slot decoder reduces 394 leaves to 29, but dynamic
  style branches still fail initial-route checks and regress corrected-screen
  mean 26.5%.

Materialized bounded maxima remain the robust optimization; reducing DOM count
alone does not reduce Blink's live anchor dependency cost.

## Block-flow successor

The outer fan-in-16 tree remains useful, but Grid is not the fastest primitive
for each 256-row group maximum. Replacing only those overlapping Grid reducers
with zero-height in-flow block children passes 30/30 exact checks and improves
mean/median/p90/maximum by 7.9%/6.2%/8.1%/8.7%. It cuts the fixture-1 trace's
layout from 1,619.6 to 1,404.7 ms and style recalculation from 620.4 to
432.9 ms while leaving all 50,523 text-shaping calls intact. See
`../gpt2-mixed-hot2-blockflow-group-max/RESULTS.md`.
