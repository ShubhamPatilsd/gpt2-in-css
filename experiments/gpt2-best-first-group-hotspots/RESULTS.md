# Best-first exact-group visitation hotspots

## Result

Across all 1,024 corpus states, exact best-first certification visited **5,288 groups**. Fixed, deployable groups `0/1` captured **32.70% of visits** and completely covered **263/1,024 (25.68%) states**. They are therefore measured as a predeclared optimization, not inferred from the evaluated state.

The separately reported top-frequency sets are diagnostic upper bounds chosen after seeing this corpus. They must not be interpreted as a deployable fixed policy without a held-out or predeclared selection step.

**Conclusion:** within the 1,024-state corpus, the low-ID hotspot is not a ten-fixture artifact: `0` and `1` are independently the two highest-frequency groups, and the data-selected top 2/4/16 sets exactly equal contiguous low-ID sets. But `0/1` alone are not a general replacement for best-first fallback because **74.32% of states** still visit a group outside them. At size 32, data selection improves full-path coverage by only **0.68 percentage points** over predeclared `0..31`, so most measured skew is contiguous-low-ID rather than a collection of isolated corpus-specific IDs.

States visited a median of **3** groups, p95 **17**, maximum **55**. **809/1,024 (79.00%)** certified within six groups.

## Set coverage

“Fully covered” means every group in that state's ordered path through its exact stopping count belongs to the set. “Non-set visits” counts the remaining exact-group evaluations per state.

| Set | Group IDs | All visits in set | All states fully covered | Stop≤6 states fully covered | Mean non-set visits/state |
|---|---|---:|---:|---:|---:|
| fixed groups 0/1 | `0,1` | 32.70% | 25.68% | 32.51% | 3.476 |
| data-selected top 2 | `0,1` | 32.70% | 25.68% | 32.51% | 3.476 |
| data-selected top 4 | `0,1,2,3` | 44.42% | 43.36% | 54.88% | 2.870 |
| data-selected top 8 | `0,1,2,3,4,5,6,9` | 54.60% | 49.51% | 62.55% | 2.345 |
| data-selected top 16 | `0,1,2,3,4,5,6,9,7,14,8,11,13,10,15,12` | 66.49% | 57.03% | 70.70% | 1.730 |
| data-selected top 32 | `0,1,2,3,4,5,6,9,7,14,8,11,13,10,15,12,16,19,17,18,27,21,23,22,25,20,24,29,37,30,34,26` | 77.89% | 65.33% | 78.62% | 1.142 |
| contiguous low IDs 0..1 | `0,1` | 32.70% | 25.68% | 32.51% | 3.476 |
| contiguous low IDs 0..3 | `0,1,2,3` | 44.42% | 43.36% | 54.88% | 2.870 |
| contiguous low IDs 0..7 | `0,1,2,3,4,5,6,7` | 54.52% | 49.22% | 62.30% | 2.349 |
| contiguous low IDs 0..15 | `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15` | 66.49% | 57.03% | 70.70% | 1.730 |
| contiguous low IDs 0..31 | `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31` | 77.63% | 64.65% | 78.00% | 1.155 |

For fixed groups `0/1`, non-hot visits per state have median **1**, p95 **15**, maximum **53**, and mean **3.476**. Conditional on needing any non-hot group, the mean is **4.677**. The JSON contains the same distributions for every top-frequency and contiguous-low-ID set.

## Per-group visitation frequency

Each group can appear at most once per state. The state fraction is thus the probability that a corpus path visits the group; the visit fraction is its share of all 5,288 evaluations.

| Rank | Group | States/visits | Fraction of states | Fraction of all visits |
|---:|---:|---:|---:|---:|
| 1 | 0 | 935 | 91.31% | 17.68% |
| 2 | 1 | 794 | 77.54% | 15.02% |
| 3 | 2 | 387 | 37.79% | 7.32% |
| 4 | 3 | 233 | 22.75% | 4.41% |
| 5 | 4 | 173 | 16.89% | 3.27% |
| 6 | 5 | 133 | 12.99% | 2.52% |
| 7 | 6 | 121 | 11.82% | 2.29% |
| 8 | 9 | 111 | 10.84% | 2.10% |
| 9 | 7 | 107 | 10.45% | 2.02% |
| 10 | 14 | 84 | 8.20% | 1.59% |
| 11 | 8 | 82 | 8.01% | 1.55% |
| 12 | 11 | 81 | 7.91% | 1.53% |
| 13 | 13 | 77 | 7.52% | 1.46% |
| 14 | 10 | 68 | 6.64% | 1.29% |
| 15 | 15 | 66 | 6.45% | 1.25% |
| 16 | 12 | 64 | 6.25% | 1.21% |
| 17 | 16 | 64 | 6.25% | 1.21% |
| 18 | 19 | 58 | 5.66% | 1.10% |
| 19 | 17 | 51 | 4.98% | 0.96% |
| 20 | 18 | 46 | 4.49% | 0.87% |
| 21 | 27 | 39 | 3.81% | 0.74% |
| 22 | 21 | 38 | 3.71% | 0.72% |
| 23 | 23 | 36 | 3.52% | 0.68% |
| 24 | 22 | 35 | 3.42% | 0.66% |
| 25 | 25 | 35 | 3.42% | 0.66% |
| 26 | 20 | 31 | 3.03% | 0.59% |
| 27 | 24 | 30 | 2.93% | 0.57% |
| 28 | 29 | 29 | 2.83% | 0.55% |
| 29 | 37 | 29 | 2.83% | 0.55% |
| 30 | 30 | 28 | 2.73% | 0.53% |
| 31 | 34 | 28 | 2.73% | 0.53% |
| 32 | 26 | 26 | 2.54% | 0.49% |
| 33 | 28 | 26 | 2.54% | 0.49% |
| 34 | 32 | 24 | 2.34% | 0.45% |
| 35 | 44 | 24 | 2.34% | 0.45% |
| 36 | 38 | 23 | 2.25% | 0.43% |
| 37 | 43 | 23 | 2.25% | 0.43% |
| 38 | 33 | 21 | 2.05% | 0.40% |
| 39 | 35 | 21 | 2.05% | 0.40% |
| 40 | 196 | 20 | 1.95% | 0.38% |
| 41 | 50 | 19 | 1.86% | 0.36% |
| 42 | 36 | 18 | 1.76% | 0.34% |
| 43 | 55 | 18 | 1.76% | 0.34% |
| 44 | 59 | 18 | 1.76% | 0.34% |
| 45 | 31 | 17 | 1.66% | 0.32% |
| 46 | 39 | 17 | 1.66% | 0.32% |
| 47 | 41 | 17 | 1.66% | 0.32% |
| 48 | 45 | 17 | 1.66% | 0.32% |
| 49 | 48 | 17 | 1.66% | 0.32% |
| 50 | 62 | 17 | 1.66% | 0.32% |
| 51 | 64 | 16 | 1.56% | 0.30% |
| 52 | 40 | 15 | 1.46% | 0.28% |
| 53 | 46 | 15 | 1.46% | 0.28% |
| 54 | 47 | 15 | 1.46% | 0.28% |
| 55 | 51 | 15 | 1.46% | 0.28% |
| 56 | 52 | 15 | 1.46% | 0.28% |
| 57 | 58 | 15 | 1.46% | 0.28% |
| 58 | 60 | 15 | 1.46% | 0.28% |
| 59 | 68 | 15 | 1.46% | 0.28% |
| 60 | 74 | 14 | 1.37% | 0.26% |
| 61 | 42 | 13 | 1.27% | 0.25% |
| 62 | 53 | 13 | 1.27% | 0.25% |
| 63 | 67 | 13 | 1.27% | 0.25% |
| 64 | 71 | 13 | 1.27% | 0.25% |
| 65 | 54 | 12 | 1.17% | 0.23% |
| 66 | 80 | 12 | 1.17% | 0.23% |
| 67 | 105 | 12 | 1.17% | 0.23% |
| 68 | 57 | 11 | 1.07% | 0.21% |
| 69 | 69 | 11 | 1.07% | 0.21% |
| 70 | 76 | 11 | 1.07% | 0.21% |
| 71 | 88 | 11 | 1.07% | 0.21% |
| 72 | 95 | 11 | 1.07% | 0.21% |
| 73 | 99 | 11 | 1.07% | 0.21% |
| 74 | 56 | 10 | 0.98% | 0.19% |
| 75 | 66 | 10 | 0.98% | 0.19% |
| 76 | 49 | 9 | 0.88% | 0.17% |
| 77 | 61 | 9 | 0.88% | 0.17% |
| 78 | 63 | 9 | 0.88% | 0.17% |
| 79 | 77 | 9 | 0.88% | 0.17% |
| 80 | 78 | 9 | 0.88% | 0.17% |
| 81 | 81 | 9 | 0.88% | 0.17% |
| 82 | 85 | 9 | 0.88% | 0.17% |
| 83 | 79 | 8 | 0.78% | 0.15% |
| 84 | 119 | 8 | 0.78% | 0.15% |
| 85 | 123 | 8 | 0.78% | 0.15% |
| 86 | 70 | 7 | 0.68% | 0.13% |
| 87 | 73 | 7 | 0.68% | 0.13% |
| 88 | 84 | 7 | 0.68% | 0.13% |
| 89 | 86 | 7 | 0.68% | 0.13% |
| 90 | 89 | 7 | 0.68% | 0.13% |
| 91 | 115 | 7 | 0.68% | 0.13% |
| 92 | 117 | 7 | 0.68% | 0.13% |
| 93 | 133 | 7 | 0.68% | 0.13% |
| 94 | 148 | 7 | 0.68% | 0.13% |
| 95 | 65 | 6 | 0.59% | 0.11% |
| 96 | 75 | 6 | 0.59% | 0.11% |
| 97 | 90 | 6 | 0.59% | 0.11% |
| 98 | 107 | 6 | 0.59% | 0.11% |
| 99 | 118 | 6 | 0.59% | 0.11% |
| 100 | 127 | 6 | 0.59% | 0.11% |
| 101 | 135 | 6 | 0.59% | 0.11% |
| 102 | 138 | 6 | 0.59% | 0.11% |
| 103 | 146 | 6 | 0.59% | 0.11% |
| 104 | 154 | 6 | 0.59% | 0.11% |
| 105 | 164 | 6 | 0.59% | 0.11% |
| 106 | 178 | 6 | 0.59% | 0.11% |
| 107 | 72 | 5 | 0.49% | 0.09% |
| 108 | 82 | 5 | 0.49% | 0.09% |
| 109 | 83 | 5 | 0.49% | 0.09% |
| 110 | 91 | 5 | 0.49% | 0.09% |
| 111 | 103 | 5 | 0.49% | 0.09% |
| 112 | 108 | 5 | 0.49% | 0.09% |
| 113 | 111 | 5 | 0.49% | 0.09% |
| 114 | 113 | 5 | 0.49% | 0.09% |
| 115 | 120 | 5 | 0.49% | 0.09% |
| 116 | 126 | 5 | 0.49% | 0.09% |
| 117 | 132 | 5 | 0.49% | 0.09% |
| 118 | 142 | 5 | 0.49% | 0.09% |
| 119 | 151 | 5 | 0.49% | 0.09% |
| 120 | 153 | 5 | 0.49% | 0.09% |
| 121 | 161 | 5 | 0.49% | 0.09% |
| 122 | 168 | 5 | 0.49% | 0.09% |
| 123 | 169 | 5 | 0.49% | 0.09% |
| 124 | 92 | 4 | 0.39% | 0.08% |
| 125 | 94 | 4 | 0.39% | 0.08% |
| 126 | 96 | 4 | 0.39% | 0.08% |
| 127 | 98 | 4 | 0.39% | 0.08% |
| 128 | 101 | 4 | 0.39% | 0.08% |
| 129 | 106 | 4 | 0.39% | 0.08% |
| 130 | 109 | 4 | 0.39% | 0.08% |
| 131 | 110 | 4 | 0.39% | 0.08% |
| 132 | 114 | 4 | 0.39% | 0.08% |
| 133 | 125 | 4 | 0.39% | 0.08% |
| 134 | 128 | 4 | 0.39% | 0.08% |
| 135 | 129 | 4 | 0.39% | 0.08% |
| 136 | 131 | 4 | 0.39% | 0.08% |
| 137 | 134 | 4 | 0.39% | 0.08% |
| 138 | 137 | 4 | 0.39% | 0.08% |
| 139 | 143 | 4 | 0.39% | 0.08% |
| 140 | 145 | 4 | 0.39% | 0.08% |
| 141 | 152 | 4 | 0.39% | 0.08% |
| 142 | 157 | 4 | 0.39% | 0.08% |
| 143 | 159 | 4 | 0.39% | 0.08% |
| 144 | 160 | 4 | 0.39% | 0.08% |
| 145 | 193 | 4 | 0.39% | 0.08% |
| 146 | 195 | 4 | 0.39% | 0.08% |
| 147 | 93 | 3 | 0.29% | 0.06% |
| 148 | 100 | 3 | 0.29% | 0.06% |
| 149 | 102 | 3 | 0.29% | 0.06% |
| 150 | 112 | 3 | 0.29% | 0.06% |
| 151 | 121 | 3 | 0.29% | 0.06% |
| 152 | 130 | 3 | 0.29% | 0.06% |
| 153 | 140 | 3 | 0.29% | 0.06% |
| 154 | 147 | 3 | 0.29% | 0.06% |
| 155 | 170 | 3 | 0.29% | 0.06% |
| 156 | 171 | 3 | 0.29% | 0.06% |
| 157 | 177 | 3 | 0.29% | 0.06% |
| 158 | 87 | 2 | 0.20% | 0.04% |
| 159 | 97 | 2 | 0.20% | 0.04% |
| 160 | 116 | 2 | 0.20% | 0.04% |
| 161 | 136 | 2 | 0.20% | 0.04% |
| 162 | 139 | 2 | 0.20% | 0.04% |
| 163 | 141 | 2 | 0.20% | 0.04% |
| 164 | 150 | 2 | 0.20% | 0.04% |
| 165 | 156 | 2 | 0.20% | 0.04% |
| 166 | 162 | 2 | 0.20% | 0.04% |
| 167 | 163 | 2 | 0.20% | 0.04% |
| 168 | 166 | 2 | 0.20% | 0.04% |
| 169 | 167 | 2 | 0.20% | 0.04% |
| 170 | 175 | 2 | 0.20% | 0.04% |
| 171 | 176 | 2 | 0.20% | 0.04% |
| 172 | 181 | 2 | 0.20% | 0.04% |
| 173 | 182 | 2 | 0.20% | 0.04% |
| 174 | 190 | 2 | 0.20% | 0.04% |
| 175 | 191 | 2 | 0.20% | 0.04% |
| 176 | 194 | 2 | 0.20% | 0.04% |
| 177 | 104 | 1 | 0.10% | 0.02% |
| 178 | 122 | 1 | 0.10% | 0.02% |
| 179 | 124 | 1 | 0.10% | 0.02% |
| 180 | 144 | 1 | 0.10% | 0.02% |
| 181 | 149 | 1 | 0.10% | 0.02% |
| 182 | 155 | 1 | 0.10% | 0.02% |
| 183 | 158 | 1 | 0.10% | 0.02% |
| 184 | 165 | 1 | 0.10% | 0.02% |
| 185 | 172 | 1 | 0.10% | 0.02% |
| 186 | 173 | 1 | 0.10% | 0.02% |
| 187 | 174 | 1 | 0.10% | 0.02% |
| 188 | 180 | 1 | 0.10% | 0.02% |
| 189 | 183 | 1 | 0.10% | 0.02% |
| 190 | 184 | 1 | 0.10% | 0.02% |
| 191 | 186 | 1 | 0.10% | 0.02% |
| 192 | 188 | 1 | 0.10% | 0.02% |
| 193 | 189 | 1 | 0.10% | 0.02% |
| 194 | 192 | 1 | 0.10% | 0.02% |
| 195 | 179 | 0 | 0.00% | 0.00% |
| 196 | 185 | 0 | 0.00% | 0.00% |
| 197 | 187 | 0 | 0.00% | 0.00% |

## First six path positions

Frequencies below are conditional on the state still being active at that position. Top ten groups are shown; complete 197-group tables are in `results.json`.

- Position 1: 1024 active states; top groups 0 (728, 71.09%), 1 (143, 13.96%), 3 (31, 3.03%), 2 (18, 1.76%), 6 (12, 1.17%), 5 (10, 0.98%), 8 (7, 0.68%), 4 (6, 0.59%), 12 (5, 0.49%), 9 (4, 0.39%).
- Position 2: 889 active states; top groups 1 (500, 56.24%), 0 (138, 15.52%), 2 (45, 5.06%), 3 (25, 2.81%), 4 (13, 1.46%), 7 (12, 1.35%), 5 (10, 1.12%), 9 (10, 1.12%), 6 (7, 0.79%), 8 (6, 0.67%).
- Position 3: 682 active states; top groups 2 (183, 26.83%), 1 (78, 11.44%), 3 (53, 7.77%), 4 (39, 5.72%), 0 (27, 3.96%), 5 (17, 2.49%), 8 (15, 2.20%), 9 (12, 1.76%), 6 (11, 1.61%), 7 (11, 1.61%).
- Position 4: 465 active states; top groups 2 (60, 12.90%), 3 (41, 8.82%), 4 (31, 6.67%), 1 (29, 6.24%), 6 (20, 4.30%), 11 (17, 3.66%), 14 (17, 3.66%), 9 (16, 3.44%), 0 (15, 3.23%), 5 (15, 3.23%).
- Position 5: 333 active states; top groups 2 (24, 7.21%), 4 (20, 6.01%), 5 (20, 6.01%), 6 (18, 5.41%), 3 (15, 4.50%), 1 (13, 3.90%), 7 (12, 3.60%), 9 (11, 3.30%), 0 (10, 3.00%), 8 (10, 3.00%).
- Position 6: 261 active states; top groups 2 (20, 7.66%), 5 (20, 7.66%), 3 (15, 5.75%), 4 (15, 5.75%), 9 (11, 4.21%), 6 (9, 3.45%), 1 (8, 3.07%), 0 (7, 2.68%), 7 (7, 2.68%), 13 (7, 2.68%).

## Stopping distribution

The compact `groups-visited:states` histogram is:

`1:135, 2:207, 3:217, 4:132, 5:72, 6:46, 7:28, 8:32, 9:21, 10:15, 11:20, 12:15, 13:6, 14:10, 15:7, 16:6, 17:8, 18:8, 19:4, 20:5, 21:7, 22:3, 24:1, 25:3, 26:2, 28:2, 31:5, 35:2, 36:1, 40:1, 41:2, 55:1`

## Contract and validation

- Target: global-int16 weights at F2DOT14-realized hidden coordinates.
- Realization: nearest F2DOT14 grid, matching tools/analyze_gpt2_certified_tail_strategies.py.
- Coarse bound: row-wise signed int10, with 19 coarse buckets and 8 fine buckets.
- Stop rule: after each visited group, cumulative best exact group score minus the fine allowance must be strictly greater than the next group's coarse upper bound
- All 1024 target-winning groups were retained in their visited paths.
- Count conservation passed: per-group visits, per-state stopping counts, and first-six position counts agree.
- Runtime: **0.75 seconds** on the local offline NumPy analysis; no browser was used.

## Interpretation

This analysis answers where the existing exact best-first search spends group evaluations. A data-selected top-K set describes corpus skew and an optimistic static cache. In contrast, groups `0/1` and contiguous `0..K-1` are deployable predeclared choices whose IDs do not depend on this evaluation. Any production choice based on the data-selected ranking needs separate held-out validation; these 1,024 states are the measurement corpus, not that validation set.
