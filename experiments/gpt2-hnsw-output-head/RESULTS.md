# GPT-2 HNSW-like output-head feasibility

**Verdict: NO-GO.** Neither validation-selected budget point reaches at least 99% held-out top-1 recall under the fixed 2,048-score or 2,000 mean unique-row screen.

hnswlib 0.8.0 reaches 99.22% held-out recall at the validation-selected M=32, efSearch=1024 point. This does not change the CSS verdict because its scored-row
count is unavailable.

This offline screen leaves GPT-2-small and its 50,257 tied embedding/lm-head
rows unchanged.  It uses the existing 1,024 contextual output-head states and
their established split: 512 train, 256 validation, and 256 held-out test.
The graph itself is query-independent and uses no state split for training.
The primary operating point is selected only by validation recall among
configurations with a conservative fixed expansion cap of 2,048 row scores.

The dependency-free deterministic fallback compares exact cosine-kNN and raw
inner-product-kNN links within each of the existing 256 geometric vocabulary
partitions.  The latter is faithful to the unnormalized tied-head MIPS objective.
One real vocabulary row per partition is a gateway; gateway rows use the same
metric for deterministic cross-partition links.  At runtime all 256 gateways
are scored, then a fixed beam is expanded for a fixed number of unrolled hops.
Centroids are never scored at runtime and all accounting below counts distinct
original lm-head rows.

The fixed-cap validation-selected point uses inner-product links,
degree 16, beam 16, and 6
hops.  On held-out test it reaches
**74.61% exact top-1 recall** (191/256),
with **741.0 mean / 879 p95 /
1027 max** unique scored rows. For completeness, selecting
by validation under a 2,000 *mean unique-row* allowance chooses
cosine degree 32, beam
32, hops 8; held-out recall is
86.72% with 1913.5 mean /
2329 p95 / 2697 max rows.

## Standard hnswlib `space="ip"` diagnostic

hnswlib 0.8.0 reaches 99.22% held-out recall at the validation-selected M=32, efSearch=1024 point.

Construction used 8 threads for both insertion and queries.
Parallel insertion may not be bitwise deterministic across runs.
The M=16 curve uses efConstruction=100; the M=32 robustness curve uses efConstruction=200.

| M | efConstruction | efSearch | Validation recall | Held-out recall | Query seconds / 1,024 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 100 | 16 | 77.34% | 72.66% | 0.034 |
| 16 | 100 | 32 | 88.28% | 84.38% | 0.050 |
| 16 | 100 | 64 | 94.92% | 92.19% | 0.083 |
| 16 | 100 | 128 | 97.66% | 94.53% | 0.153 |
| 16 | 100 | 256 | 98.83% | 95.70% | 0.255 |
| 16 | 100 | 512 | 99.22% | 96.88% | 0.463 |
| 32 | 200 | 128 | 97.66% | 95.31% | 0.203 |
| 32 | 200 | 256 | 99.22% | 97.66% | 0.362 |
| 32 | 200 | 512 | 99.61% | 98.83% | 0.645 |
| 32 | 200 | 1024 | 100.00% | 99.22% | 1.088 |

This is real hierarchical HNSW over all unchanged vocabulary rows, not the
partitioned deterministic graph. It is diagnostic rather than a CSS budget
claim: hnswlib 0.8.0 does not expose the number of row-distance evaluations or
the adaptive traversal trace. Also, `efSearch` is a dynamic candidate-queue
width, not a scored-row bound. Standard HNSW therefore establishes attainable
ANN recall, but it cannot satisfy the CSS ≤2,000 scored-row gate without
exported traversal counts or an instrumented, explicitly simulated traversal.

## MIPS-faithful comparison

| Graph metric | Validation selection | Degree | Beam | Hops | Held-out recall | Test mean rows | Test p95 | Test max |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cosine | fixed cap ≤2,048 | 16 | 16 | 6 | 72.27% | 732.5 | 880 | 985 |
| cosine | validation mean ≤2,000 | 32 | 32 | 8 | 86.72% | 1913.5 | 2329 | 2697 |
| cosine | widest tested | 64 | 32 | 4 | 89.45% | 2099.0 | 2564 | 2850 |
| inner-product | fixed cap ≤2,048 | 16 | 16 | 6 | 74.61% | 741.0 | 879 | 1027 |
| inner-product | validation mean ≤2,000 | 16 | 32 | 16 | 86.72% | 1923.9 | 2245 | 2627 |
| inner-product | widest tested | 64 | 32 | 4 | 88.28% | 2148.1 | 2571 | 2822 |

Raw inner-product links improve the conservative fixed-cap point over cosine,
but do not approach the target.  At the 2,000-mean interpretation the two
metrics tie on held-out recall, and even the widest tested points remain below
90%.  Thus the rejection does not rest on row-normalized cosine topology.

## Validation Pareto frontier

| Graph metric | Degree | Beam | Hops | Validation recall | Held-out recall | Test mean rows | Test p95 | Test max |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cosine | 16 | 4 | 2 | 12.50% | 15.62% | 316.2 | 328 | 331 |
| inner-product | 16 | 4 | 2 | 23.44% | 24.22% | 318.0 | 329 | 339 |
| cosine | 16 | 4 | 4 | 37.89% | 37.89% | 359.7 | 397 | 414 |
| inner-product | 16 | 4 | 4 | 42.97% | 41.02% | 363.4 | 397 | 427 |
| inner-product | 16 | 4 | 6 | 51.17% | 48.05% | 402.8 | 460 | 499 |
| inner-product | 16 | 4 | 8 | 54.30% | 53.52% | 439.4 | 520 | 570 |
| cosine | 16 | 8 | 4 | 55.08% | 51.95% | 450.4 | 513 | 543 |
| inner-product | 16 | 8 | 4 | 57.81% | 54.69% | 457.9 | 507 | 574 |
| cosine | 16 | 8 | 6 | 59.38% | 55.86% | 510.2 | 641 | 677 |
| inner-product | 16 | 8 | 6 | 65.23% | 61.72% | 526.8 | 623 | 706 |
| inner-product | 16 | 8 | 8 | 66.80% | 64.45% | 586.5 | 719 | 801 |
| cosine | 16 | 16 | 4 | 67.19% | 63.67% | 627.4 | 714 | 787 |
| inner-product | 16 | 16 | 4 | 70.31% | 66.80% | 635.9 | 722 | 810 |
| cosine | 16 | 16 | 6 | 71.48% | 72.27% | 732.5 | 880 | 985 |
| inner-product | 16 | 16 | 6 | 76.95% | 74.61% | 741.0 | 879 | 1027 |
| inner-product | 16 | 16 | 8 | 78.52% | 77.34% | 833.0 | 1013 | 1227 |
| inner-product | 16 | 16 | 12 | 81.64% | 79.69% | 1000.2 | 1244 | 1531 |
| inner-product | 16 | 16 | 16 | 82.42% | 81.25% | 1156.9 | 1445 | 1766 |
| inner-product | 16 | 32 | 6 | 84.38% | 81.64% | 1170.6 | 1398 | 1521 |
| cosine | 16 | 32 | 8 | 85.16% | 83.59% | 1340.3 | 1620 | 1820 |
| inner-product | 16 | 32 | 8 | 86.33% | 83.59% | 1336.8 | 1602 | 1768 |
| inner-product | 16 | 32 | 12 | 87.50% | 85.94% | 1645.1 | 1936 | 2109 |
| inner-product | 32 | 32 | 6 | 87.89% | 87.89% | 1696.4 | 2040 | 2175 |
| cosine | 32 | 32 | 8 | 89.06% | 86.72% | 1913.5 | 2329 | 2697 |
| cosine | 16 | 32 | 16 | 89.45% | 87.50% | 1976.9 | 2414 | 2628 |
| cosine | 64 | 32 | 4 | 89.84% | 89.45% | 2099.0 | 2564 | 2850 |
| inner-product | 64 | 32 | 4 | 90.23% | 88.28% | 2148.1 | 2571 | 2822 |

## Oracle and interpretation

A batched float32 brute-force multiplication scores every one of the 50,257
unchanged rows for every state.  Its winners match all
1,024/1,024 saved dense winners; the graph's
reported recall is measured directly against those brute-force winners.

The fixed graph budgets are attractive only if they retain the exact output-head
winner.  The target screen is at least 99% held-out recall at roughly 2,000 or
fewer scored rows.  The verdict checks both the conservative fixed 2,048 cap and
the requested 2,000-mean interpretation; a miss is not presented as an exact or
production-ready output head.

## Validation

The full artifact-producing run completed with hnswlib 0.8.0. The script's
brute-force assertion passed all 1,024 states, Python bytecode compilation
passed, and `results.json` parses as valid JSON. The script also fails closed on
a saved-winner/oracle mismatch.

## Reproduce

```sh
uv run --with hnswlib --with numpy python3 tools/analyze_gpt2_hnsw_output_head.py
python3 -m py_compile tools/analyze_gpt2_hnsw_output_head.py
```
