# CSS-unrollable batched frontier on real HNSW layer 0

**Mean-2,000 target: NO-GO.** No validation-selected point reaches 99% untouched-test recall under 2,000 mean optimistic unique rows.

This experiment uses the previously exported real hnswlib 0.8.0 layer-0 graph,
all 50,257 unchanged GPT-2-small tied output rows, and the established 1,024
hidden states. Fresh float32 brute force reproduces all 1,024 saved winners.
No model weight, architecture, state, split, or graph edge is changed.

Every query first scores a fixed 256-row seed bank. Each of the fixed rounds
then expands the highest-scoring B discovered but unexpanded nodes in parallel,
scores previously unseen layer-0 neighbors by raw inner product, and retains
all discovered candidates for later top-B selection. The optimistic algorithm
deduplicates globally. A literal CSS schedule cannot cheaply do that, so the
tables separately report duplicate adjacency references and padding to B x 64
neighbor slots per round.

## Validation-only selections

**Optimistic validation mean <=2,000:** `ivf-medoid-256-b8-r16` reaches 98.44% validation and 95.70% untouched-test recall. Test optimistic unique rows are 1893.7 mean / 2639 p95 / 3056 max; duplicate adjacency entries are 1344.1 mean, padding is 5210.2 mean, and the fixed padded schedule is 8448 rows.

**Literal fixed padded <=2,048:** `ivf-medoid-256-b2-r12` reaches 87.50% validation and 84.77% untouched-test recall. Test optimistic unique rows are 642.2 mean / 948 p95 / 1061 max; duplicate adjacency entries are 182.5 mean, padding is 967.3 mean, and the fixed padded schedule is 1792 rows.

**Best broader frontier:** `ivf-medoid-256-b32-r12` reaches 100.00% validation and 98.44% untouched-test recall. Test optimistic unique rows are 4400.9 mean / 5642 p95 / 6369 max; duplicate adjacency entries are 4924.1 mean, padding is 15507.0 mean, and the fixed padded schedule is 24832 rows.

Selection uses validation recall only. Test is revealed only after locking each
point. Ties prefer lower validation optimistic mean rows, then fewer fixed
padded slots, rounds, and beam width.

## Full sweep

Test row values are mean / p95 / max for optimistic unique rows. Duplicate
entries are the mean layer-0 references that a no-dedup CSS schedule would
rescore. Fixed padded rows include the 256 seeds and every B x 64 round slot.

| Entry strategy | B | Rounds | Train recall | Validation recall | Test recall | Test unique rows | Test duplicate entries | Fixed padded rows |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- | ---: | ---: |
| ivf-medoid-256 | 1 | 2 | 23.05% | 18.75% | 24.61% | 299.8 / 336 / 349 | 2.3 | 384 |
| ivf-medoid-256 | 1 | 4 | 44.53% | 42.97% | 48.05% | 343.3 / 407 / 431 | 16.0 | 512 |
| ivf-medoid-256 | 1 | 6 | 56.25% | 58.20% | 59.38% | 376.3 / 460 / 512 | 32.1 | 640 |
| ivf-medoid-256 | 1 | 8 | 61.91% | 66.41% | 66.02% | 408.4 / 533 / 583 | 47.6 | 768 |
| ivf-medoid-256 | 1 | 12 | 73.44% | 75.78% | 72.66% | 469.0 / 639 / 741 | 80.5 | 1024 |
| ivf-medoid-256 | 1 | 16 | 78.52% | 81.25% | 78.12% | 526.4 / 749 / 880 | 112.2 | 1280 |
| ivf-medoid-256 | 2 | 2 | 31.45% | 31.25% | 32.03% | 344.3 / 404 / 424 | 6.8 | 512 |
| ivf-medoid-256 | 2 | 4 | 63.48% | 68.36% | 62.50% | 419.4 / 533 / 605 | 43.4 | 768 |
| ivf-medoid-256 | 2 | 6 | 73.44% | 80.08% | 74.61% | 478.9 / 655 / 728 | 76.5 | 1024 |
| ivf-medoid-256 | 2 | 8 | 80.08% | 84.77% | 78.52% | 533.2 / 751 / 838 | 110.2 | 1280 |
| ivf-medoid-256 | 2 | 12 | 85.35% | 87.50% | 84.77% | 642.2 / 948 / 1061 | 182.5 | 1792 |
| ivf-medoid-256 | 2 | 16 | 90.23% | 90.62% | 88.67% | 749.4 / 1124 / 1303 | 258.5 | 2304 |
| ivf-medoid-256 | 4 | 2 | 43.36% | 43.75% | 45.31% | 430.0 / 533 / 582 | 18.6 | 768 |
| ivf-medoid-256 | 4 | 4 | 75.59% | 78.91% | 76.56% | 560.7 / 750 / 865 | 100.8 | 1280 |
| ivf-medoid-256 | 4 | 6 | 83.20% | 86.33% | 85.55% | 665.3 / 957 / 1063 | 173.3 | 1792 |
| ivf-medoid-256 | 4 | 8 | 88.28% | 89.84% | 89.84% | 769.9 / 1141 / 1264 | 247.7 | 2304 |
| ivf-medoid-256 | 4 | 12 | 92.77% | 93.75% | 92.58% | 968.5 / 1428 / 1675 | 412.0 | 3328 |
| ivf-medoid-256 | 4 | 16 | 95.70% | 96.09% | 93.75% | 1157.2 / 1723 / 1981 | 585.8 | 4352 |
| ivf-medoid-256 | 8 | 2 | 53.12% | 55.86% | 54.69% | 592.5 / 752 / 814 | 49.6 | 1280 |
| ivf-medoid-256 | 8 | 4 | 87.50% | 90.62% | 88.28% | 821.0 / 1140 / 1249 | 229.2 | 2304 |
| ivf-medoid-256 | 8 | 6 | 92.38% | 94.14% | 91.80% | 1008.3 / 1444 / 1671 | 388.1 | 3328 |
| ivf-medoid-256 | 8 | 8 | 95.51% | 95.70% | 94.53% | 1190.2 / 1711 / 1967 | 563.6 | 4352 |
| ivf-medoid-256 | 8 | 12 | 96.88% | 97.66% | 95.70% | 1549.1 / 2200 / 2495 | 938.1 | 6400 |
| ivf-medoid-256 | 8 | 16 | 97.85% | 98.44% | 95.70% | 1893.7 / 2639 / 3056 | 1344.1 | 8448 |
| ivf-medoid-256 | 16 | 2 | 63.28% | 67.19% | 65.62% | 913.9 / 1126 / 1241 | 125.8 | 2304 |
| ivf-medoid-256 | 16 | 4 | 93.55% | 96.09% | 93.36% | 1304.7 / 1741 / 1976 | 520.9 | 4352 |
| ivf-medoid-256 | 16 | 6 | 96.48% | 97.27% | 95.70% | 1632.3 / 2227 / 2565 | 889.2 | 6400 |
| ivf-medoid-256 | 16 | 8 | 97.46% | 98.44% | 96.09% | 1959.5 / 2687 / 3030 | 1288.6 | 8448 |
| ivf-medoid-256 | 16 | 12 | 98.05% | 99.22% | 96.09% | 2592.5 / 3518 / 4005 | 2163.7 | 12544 |
| ivf-medoid-256 | 16 | 16 | 99.22% | 99.61% | 97.66% | 3190.0 / 4283 / 4815 | 3086.3 | 16640 |
| ivf-medoid-256 | 32 | 2 | 73.05% | 79.30% | 71.88% | 1518.3 / 1787 / 1963 | 321.3 | 4352 |
| ivf-medoid-256 | 32 | 4 | 96.68% | 97.66% | 96.48% | 2166.2 / 2762 / 3169 | 1193.8 | 8448 |
| ivf-medoid-256 | 32 | 6 | 98.05% | 99.61% | 96.48% | 2740.1 / 3613 / 4028 | 2046.1 | 12544 |
| ivf-medoid-256 | 32 | 8 | 98.63% | 99.61% | 97.27% | 3308.9 / 4348 / 4870 | 2969.0 | 16640 |
| ivf-medoid-256 | 32 | 12 | 99.41% | 100.00% | 98.44% | 4400.9 / 5642 / 6369 | 4924.1 | 24832 |
| ivf-medoid-256 | 32 | 16 | 99.80% | 100.00% | 99.22% | 5403.9 / 6822 / 7516 | 6975.8 | 33024 |
| layer0-degree-hub-256 | 1 | 2 | 4.10% | 2.73% | 1.95% | 347.0 / 371 / 380 | 4.8 | 384 |
| layer0-degree-hub-256 | 1 | 4 | 16.80% | 14.06% | 15.23% | 398.4 / 443 / 462 | 11.8 | 512 |
| layer0-degree-hub-256 | 1 | 6 | 32.42% | 32.81% | 28.52% | 443.4 / 504 / 547 | 24.3 | 640 |
| layer0-degree-hub-256 | 1 | 8 | 43.16% | 44.14% | 39.84% | 483.3 / 560 / 603 | 37.7 | 768 |
| layer0-degree-hub-256 | 1 | 12 | 60.16% | 59.77% | 57.03% | 552.8 / 676 / 735 | 68.4 | 1024 |
| layer0-degree-hub-256 | 1 | 16 | 69.53% | 68.75% | 65.23% | 615.5 / 785 / 884 | 102.0 | 1280 |
| layer0-degree-hub-256 | 2 | 2 | 7.62% | 7.81% | 5.08% | 434.7 / 467 / 485 | 11.3 | 512 |
| layer0-degree-hub-256 | 2 | 4 | 30.66% | 33.20% | 31.25% | 533.2 / 595 / 616 | 32.8 | 768 |
| layer0-degree-hub-256 | 2 | 6 | 51.17% | 54.69% | 50.00% | 612.9 / 717 / 752 | 66.0 | 1024 |
| layer0-degree-hub-256 | 2 | 8 | 62.89% | 68.75% | 64.45% | 678.0 / 822 / 889 | 99.9 | 1280 |
| layer0-degree-hub-256 | 2 | 12 | 78.32% | 82.42% | 75.78% | 793.3 / 999 / 1088 | 168.7 | 1792 |
| layer0-degree-hub-256 | 2 | 16 | 85.35% | 87.89% | 83.98% | 899.7 / 1181 / 1282 | 245.5 | 2304 |
| layer0-degree-hub-256 | 4 | 2 | 11.91% | 12.11% | 9.77% | 607.3 / 654 / 669 | 29.3 | 768 |
| layer0-degree-hub-256 | 4 | 4 | 48.24% | 46.09% | 46.48% | 785.5 / 877 / 922 | 89.6 | 1280 |
| layer0-degree-hub-256 | 4 | 6 | 70.12% | 71.88% | 67.58% | 913.3 / 1063 / 1158 | 163.6 | 1792 |
| layer0-degree-hub-256 | 4 | 8 | 80.47% | 81.25% | 80.08% | 1022.1 / 1239 / 1401 | 238.4 | 2304 |
| layer0-degree-hub-256 | 4 | 12 | 92.77% | 90.23% | 91.02% | 1218.7 / 1544 / 1724 | 402.8 | 3328 |
| layer0-degree-hub-256 | 4 | 16 | 95.70% | 93.75% | 94.53% | 1400.5 / 1823 / 2017 | 574.2 | 4352 |
| layer0-degree-hub-256 | 8 | 2 | 17.19% | 19.14% | 15.23% | 937.2 / 1004 / 1028 | 76.6 | 1280 |
| layer0-degree-hub-256 | 8 | 4 | 64.45% | 67.19% | 65.23% | 1252.1 / 1379 / 1449 | 232.8 | 2304 |
| layer0-degree-hub-256 | 8 | 6 | 86.91% | 86.33% | 83.98% | 1454.7 / 1680 / 1849 | 396.2 | 3328 |
| layer0-degree-hub-256 | 8 | 8 | 93.95% | 92.58% | 90.23% | 1631.0 / 1953 / 2093 | 570.0 | 4352 |
| layer0-degree-hub-256 | 8 | 12 | 96.48% | 97.66% | 95.31% | 1967.8 / 2432 / 2639 | 942.1 | 6400 |
| layer0-degree-hub-256 | 8 | 16 | 97.66% | 98.44% | 95.70% | 2288.0 / 2874 / 3173 | 1342.4 | 8448 |
| layer0-degree-hub-256 | 16 | 2 | 24.02% | 24.22% | 21.88% | 1567.4 / 1664 / 1701 | 200.0 | 2304 |
| layer0-degree-hub-256 | 16 | 4 | 79.69% | 83.59% | 76.17% | 2102.3 / 2288 / 2439 | 579.8 | 4352 |
| layer0-degree-hub-256 | 16 | 6 | 94.53% | 93.75% | 92.97% | 2428.2 / 2748 / 2961 | 941.1 | 6400 |
| layer0-degree-hub-256 | 16 | 8 | 97.66% | 98.44% | 96.09% | 2724.0 / 3179 / 3390 | 1334.6 | 8448 |
| layer0-degree-hub-256 | 16 | 12 | 99.02% | 99.22% | 97.27% | 3308.5 / 3956 / 4263 | 2206.5 | 12544 |
| layer0-degree-hub-256 | 16 | 16 | 99.61% | 99.22% | 98.05% | 3871.3 / 4617 / 5037 | 3136.5 | 16640 |
| layer0-degree-hub-256 | 32 | 2 | 33.59% | 32.03% | 31.64% | 2735.4 / 2872 / 2937 | 514.9 | 4352 |
| layer0-degree-hub-256 | 32 | 4 | 88.67% | 90.23% | 83.59% | 3603.2 / 3933 / 4129 | 1400.6 | 8448 |
| layer0-degree-hub-256 | 32 | 6 | 98.24% | 98.44% | 97.27% | 4124.4 / 4626 / 4856 | 2210.1 | 12544 |
| layer0-degree-hub-256 | 32 | 8 | 99.22% | 99.22% | 98.05% | 4635.3 / 5269 / 5649 | 3121.0 | 16640 |
| layer0-degree-hub-256 | 32 | 12 | 99.61% | 99.22% | 98.44% | 5643.9 / 6503 / 7066 | 5091.4 | 24832 |
| layer0-degree-hub-256 | 32 | 16 | 99.61% | 99.61% | 99.22% | 6590.6 / 7610 / 8283 | 7165.1 | 33024 |

## Interpretation

The optimistic unique-row count is an algorithmic lower-work view with a visited
set. The fixed padded count is the clean CSS-unrollable bound: exactly 256 +
rounds x B x 64 row-score slots and `rounds` sequential graph stages. Actual
degrees below 64 become padding; already visited or same-round repeated neighbor
IDs become duplicate scores without a dynamic deduplicator. `results.json`
contains mean/p50/p95/max distributions for every accounting category and split.

Two query-independent 256-row entries are screened: one actual vocabulary row
nearest each existing IVF centroid, and the 256 highest-degree layer-0 nodes.
Neither uses train, validation, or test states. The export did not contain the
HNSW upper levels or entry point, so this does not claim to reproduce the native
hierarchical descent.

## Validation and artifacts

- `trace.npz` stores per-state predictions and all accounting counters.
- `seed_banks.npz` stores internal IDs and token IDs for both fixed banks.
- Every accounting row satisfies `unique + duplicates + padding = fixed padded`.
- CSR bounds, token permutation, split isolation, seed uniqueness, and all 1,024
  brute-force winners are validated in `validation.json`.

## Reproduce

```sh
python3 tools/analyze_gpt2_hnsw_batched_frontier.py
python3 -m py_compile tools/analyze_gpt2_hnsw_batched_frontier.py
python3 -m json.tool experiments/gpt2-hnsw-batched-frontier/results.json >/dev/null
python3 -m json.tool experiments/gpt2-hnsw-batched-frontier/validation.json >/dev/null
```
