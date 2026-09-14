# Contained hierarchical outer maximum, fan-in 16

Decision: **reject as unstable**.

Containment only on the 13 fixed reduction boxes remains exact (30/30), but its
timing is inconsistent. Versus uncontained fan-in 16 it improves mean 4.7% and
p90 7.2%; versus flat pruned direct-max, one 9.27 s candidate outlier regresses
mean 2.8% and maximum 87.0%. The uncontained tree has the more robust distribution.

Raw results are in `ab-broad-vs-uncontained.json` and
`ab-broad-vs-flat-pruned.json`.
