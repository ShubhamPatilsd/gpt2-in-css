# Packed score-bucket and group argmax

Decision: **reject as the default; retain as a tail-latency data point**.

This corrected hybrid packs only the 4 px score bucket and descending group
identity into one maximum. It removes 197 match carriers plus their group-choice
maximum, while retaining the original selected-group carrier bank for precise
local-token recovery.

Against pruned flat direct-max, the broad run passes 30/30 exact checks.

| Metric | Packed group | Flat pruned | Ratio |
|---|---:|---:|---:|
| Mean | 3,064.2 ms | 3,090.9 ms | 0.991x |
| Median | 3,065.3 ms | 3,003.4 ms | 1.021x |
| p90 | 3,916.7 ms | 4,755.6 ms | **0.824x** |
| Maximum | 4,072.6 ms | 5,061.1 ms | **0.805x** |

The 17.6% p90 and 19.5% maximum improvements are real in this run, but mean is
effectively neutral and median regresses 2.1%. The simpler fan-in-16 reduction
tree improves all four warm metrics against the same baseline, so packed group
identity is not the balanced winner.

Raw results are in `ab-broad-vs-direct-max-pruned.json`.
