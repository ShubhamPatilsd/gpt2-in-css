# GPT-2 overlapping IVF output-head screen

## Decision

**NO-GO.** Validation locked the cheapest diagnostic point reaching 99% validation recall:
`hierarchical-256x4-flat-1024` / `l2-mips` /
A=1 / P=192.
Untouched-test recall after locking is 98.047%.

The decision uses duplicated list entries, not the deduplicated union.
Test mean CSS rows including centroids are 11728.2;
the fixed padded topology is 120064 rows.
No validation configuration simultaneously reaches 99% recall
and stays below 2,000 mean CSS-realistic rows; none fits fixed 2,048.

## Validation-locked diagnostic configuration by split

| Split | Recall | Unique rows + centroids mean / p95 / max | CSS duplicate rows + centroids mean / p95 / max | Fixed padded rows |
| --- | ---: | ---: | ---: | ---: |
| train | 99.023% | 11745.8 / 13797 / 15713 | 11745.8 / 13797 / 15713 | 120064 |
| validation | 99.219% | 11686.0 / 13640 / 14855 | 11686.0 / 13640 / 14855 | 120064 |
| test | 98.047% | 11728.2 / 13946 / 14815 | 11728.2 / 13946 / 14815 | 120064 |

## Validation frontier

| Validation-only criterion | Configuration | Recall | Mean unique rows | Mean CSS rows | Max list / fixed padded rows |
| --- | --- | ---: | ---: | ---: | ---: |
| Cheapest at >=99% recall | `hierarchical-256x4-flat-1024` `l2-mips` A=1 P=192 | 99.219% | 11686.0 | 11686.0 | 620 / 120064 |
| Best below 2,000 mean rows | `ivf-256` `raw-dot` A=4 P=6 | 83.203% | 1630.6 | 1761.9 | 33335 / 200266 |
| Best within fixed 2,048 | `hierarchical-256x4-flat-1024` `l2-mips` A=1 P=1 | 39.062% | 1094.3 | 1094.3 | 620 / 1644 |

The cheapest validation recall-floor point falls back to A=1;
overlap does not buy the target operating point. The best mean-budget
point uses A=4 and exposes the deployment gap:
1630.6 deduplicated
rows versus 1761.9
actual list-entry rows, with fixed padding dominated by its
33335-entry largest list.

## What was screened

The unchanged 50,257 float32 `wte.weight` rows were assigned to their
top A=1,2,4,8 lists. `l2-mips` uses nearest-centroid L2 assignment
with centroid dot-product query routing; `raw-dot` uses dot product for
both; `cosine` normalizes rows and centers for assignment and ranks
queries by normalized-centroid dot product. The first codebook is the
existing 256-centroid index byte-for-byte. The finer codebook refines
each existing parent with four deterministic local k-means children,
then scores all 1,024 leaves flat so there is no parent-routing miss.

Every probe point in `results.json` reports exact winner inclusion and
mean/p95/max for (1) the unique union, an unattainable lower bound for
this CSS deployment, and (2) summed list entries with duplicates. It
also reports fixed padding as P times the largest list. Validation alone
chooses the configuration; test is revealed only after that lock.

## CSS scoring topology

1. Score 256 or 1,024 centroid rows against the 768-value hidden state.
2. Select the top P centroid/list banks.
3. Score each bank's original GPT-2 rows exactly. Overlapping token rows
   occupy and score duplicate DOM entries; no dynamic deduplication is
   assumed. A uniform bank allocates the global maximum list length.
4. Reduce all list-entry scores to one argmax. Duplicate token IDs are
   harmless for correctness but fully charged in deployment size.

## Oracle and reproducibility

The brute-force float32 head reproduced 1024
of 1024 saved winners. The locked diagnostic
candidate's exact scans agree with the dense winner whenever it is present.
Hashes in `results.json` bind the states, unchanged output-head rows,
starting index, and deterministic production `index.npz`.

```sh
python3 tools/analyze_gpt2_overlapping_ivf.py
python3 -m py_compile tools/analyze_gpt2_overlapping_ivf.py
python3 -m json.tool experiments/gpt2-overlapping-ivf/results.json >/dev/null
```
