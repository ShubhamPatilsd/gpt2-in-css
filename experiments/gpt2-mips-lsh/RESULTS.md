# GPT-2 asymmetric MIPS LSH candidate screen

**Verdict: NO-GO.** No validation-selected point reaches at least 99% untouched-test recall while staying under 2,000 mean duplicate-aware runtime rows. No validation-selected fixed-slot padded point also meets 99%.

This offline screen uses the standard asymmetric norm lift followed by seeded
Gaussian random-hyperplane hashing. GPT-2-small, its architecture, and all
50,257 tied `wte`/`lm_head` rows remain unchanged. The input is the existing
1,024-state corpus with its established 512 train / 256 validation / 256
untouched-test split. LSH itself is unsupervised and query-independent; every
reported operating point was selected using validation only.

## Validation-selected operating points

Costs are shown as mean/p95/max over the untouched test split. The unique union
is an optimistic lower bound. The deployment gate uses selected bucket entries
with duplicates retained, plus all `T*b` hash-projection rows. The stricter
fixed-slot estimate pads every selected bucket in a table to that table's
largest indexed bucket.

| Validation gate | Configuration | Validation recall | Test recall | Unique candidates | Duplicate entries | Fixed-slot rows incl. projections |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| mean duplicate rows <=2,000 | T32-b14-r1 | 3.52% | 2.34% | 1326.4/4431/6640 | 1338.2/4455/6866 | 1,203,598 |
| observed duplicate max <=2,048 | T32-b12-r0 | 0.39% | 0.00% | 182.1/899/953 | 182.3/902/958 | 129,425 |
| fixed-slot padded rows <=2,048 | none eligible | | | | | |

The mean-budget choice reaches only **2.34% test
recall** at 1786.2 mean
duplicate-aware rows; its p95/max are
4903/
7314. The highest-validation-recall
point anywhere in the sweep is `T32-b8-r1`. It reaches
83.20% validation and
76.17% test recall, but costs
41245.5 mean duplicate-aware rows
and 3,055,639
fixed-slot rows. More work therefore does not rescue this family to 99%.

## Validation Pareto frontier

| Configuration | Validation recall | Test recall | Test unique candidates | Test duplicate entries | Test duplicate runtime rows | Fixed-slot rows |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| T4-b10-r0 | 0.00% | 0.00% | 7.9/3/852 | 7.9/3/856 | 47.9/43/896 | 22,367 |
| T32-b12-r0 | 0.39% | 0.00% | 182.1/899/953 | 182.3/902/958 | 566.3/1286/1342 | 129,425 |
| T8-b14-r1 | 1.95% | 1.17% | 664.4/4162/4176 | 664.6/4162/4176 | 776.6/4274/4288 | 302,767 |
| T8-b12-r1 | 2.73% | 2.73% | 1396.4/8098/8160 | 1397.7/8099/8168 | 1493.7/8195/8264 | 470,839 |
| T32-b14-r1 | 3.52% | 2.34% | 1326.4/4431/6640 | 1338.2/4455/6866 | 1786.2/4903/7314 | 1,203,598 |
| T32-b8-r0 | 6.64% | 6.64% | 3134.9/8627/9648 | 3211.4/8916/10214 | 3467.4/9172/10470 | 339,743 |
| T32-b12-r1 | 14.06% | 10.94% | 4185.1/9780/13126 | 4323.7/10114/14295 | 4707.7/10498/14679 | 1,677,917 |
| T8-b8-r1 | 23.05% | 16.80% | 11285.1/33100/34493 | 11993.7/34636/38670 | 12057.7/34700/38734 | 712,297 |
| T16-b8-r1 | 23.83% | 17.97% | 12515.1/33876/35207 | 13635.8/36879/40916 | 13763.8/37007/41044 | 1,525,115 |
| T32-b10-r1 | 28.12% | 25.78% | 14726.5/20719/21918 | 16711.0/24764/26779 | 17031.0/25084/27099 | 2,216,721 |
| T32-b8-r1 | 83.20% | 76.17% | 29260.1/40672/42933 | 40989.5/64393/72179 | 41245.5/64649/72435 | 3,055,639 |

`Tn-bm-r0` means `n` tables, `m` bits/table, and exact-bucket lookup. `r1`
adds all Hamming-distance-one buckets. Full per-split mean/p95/max counts,
empty-bucket behavior, per-table maximum bucket sizes, and all 32 swept points
are in `results.json`.

## Accounting and interpretation

For each query, the candidate generator takes the union only to measure the
best possible deduplicated lower bound. Strict CSS cannot cheaply form that
arbitrary union, so feasibility is judged on the sum of actual bucket lengths
including cross-table duplicates. Runtime work adds the unique `T*b` projection
rows needed to compute the hashes. Fixed-slot work is still more conservative:
for each configuration, every selected bucket uses the measured maximum
population of its own table as its capacity. Radius-one multiprobe selects
`1+b` such slots per table. The direct positive-tail lift produces severely
imbalanced buckets, which is why no tested configuration fits a 2,048-row
fixed-slot layout even when its typical queried buckets are small.

Candidate recall means that the fresh brute-force top-1 token is present in the
bucket union. Exact rescoring of unchanged rows would therefore recover that
same winner whenever inclusion succeeds. No approximate score is called exact.

## Oracle and determinism

The brute-force float32 oracle matches all
1,024/1,024 saved winners. Random planes
come from NumPy `default_rng` seed 20260914; table and bit sweeps use nested
prefixes so every comparison is deterministic. The selected index artifact is
`experiments/gpt2-mips-lsh/index.npz` (SHA-256
`28fb05c8f3f67e0baf8164dc359fc1325932246871e7ce7e4652b09bcea23ebf`). It contains projection planes and
bucket membership by unchanged token ID, not copied or modified model rows.

## Reproduce and validate

```sh
python3 tools/analyze_gpt2_mips_lsh.py
python3 -m py_compile tools/analyze_gpt2_mips_lsh.py
python3 -m json.tool experiments/gpt2-mips-lsh/results.json >/dev/null
```
