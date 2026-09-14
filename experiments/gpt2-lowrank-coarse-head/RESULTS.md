# GPT-2 coarse-search pruning

The output head's dominant warm stage is the full 50,257-token global-int11
scan. Three ways of reducing that scan were evaluated without removing tokens
or changing the checkpoint.

## Exact branch and bound

A 2,047-node vocabulary tree used valid L2-ball and axis-aligned-box upper
bounds. Across 256 real one-token final states, the combined bound still had to
score 50,208 of 50,257 tokens at 64-token leaves; larger leaves scored the
entire vocabulary. High-dimensional bounds are too loose to prune GPT-2.

## Embedding subspaces

Centered vocabulary PCA was tested at ranks 16--384. Its best winning-group
recall was 237/256, and retaining one approximate representative from every
256-token group preserved only 151/256 dense winners. This is not accurate
enough for exact group refinement.

## Query-distribution subspaces

A query PCA can fold the mean hidden-state contribution into each token's
fixed score base. On held-out one-token states, rank 127 retained 124/128
winning groups but only 111/128 true tokens as their group's representative.

The stronger test uses real 12-head causal attention through all 12 GPT-2
blocks for random contexts of lengths 2, 4, 8, and 16. The implementation
matches the established one-token reference with RMSE 1.26e-7. On 96 held-out
multi-token states, rank 95 retains only 59 winning groups; the true token can
fall to global rank 3,306 and local rank 57. The apparent one-token compression
does not generalize to contextual inference.

## Decision

Neither exact geometric pruning nor post-hoc low-rank coarse search replaces
the global scorer. The next output-head optimization must reduce the cost of
evaluating all rows—packing or a different native browser primitive—rather
than attempting to avoid rows through this kind of search index.

A later query-aware certified tree closes the obvious stronger follow-up. Its
k-means partition and valid subspace/spherical-cap bounds retain all 1,024
row-int10 winners, but still score 50,118 of 50,257 leaf rows at the median,
plus 1,392 internal nodes. See
`../gpt2-certified-vocabulary-ball-tree/RESULTS.md`.

Reproduce:

```sh
PYTHONPATH=tools python3 tools/analyze_gpt2_mips_pruning.py
PYTHONPATH=tools python3 tools/analyze_gpt2_lowrank_coarse_head.py
PYTHONPATH=tools python3 tools/analyze_gpt2_multitoken_query_subspace.py
```
