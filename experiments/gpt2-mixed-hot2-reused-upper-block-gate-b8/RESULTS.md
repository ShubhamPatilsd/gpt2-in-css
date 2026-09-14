# Reused-upper hot-2 block gate, B=8

Decision: **reject as the default; keep B=4**.

B=8 uses the same direct 197-way outer maximum and exact reused-upper bound
derivation as B=4. It halves the gate containers, but retains substantially
more exact rows: fixture means are 28.8/96.0 for groups 0/1, and 1,024-state
corpus means are 68.38/153.01. Every offline winner is retained.

The rotated two-fixture A/B passes 6/6 semantic checks. Against the retained
mixed-hot2 page, its six-sample mean is 2,369.8 versus 2,785.5 ms (0.851x), but
its median is 2,878.9 versus 2,627.8 ms (1.096x). In the corresponding B=4
screen, B=4 is faster on both mean (2,206.7 ms) and median (2,551.6 ms).

The looser group-1 pruning and slower median do not justify a broad B=8 run.
Retain B=4 for the loaded warm path. Chrome: 153.0.8010.36. Raw measurements
are in `ab-results.json`.
