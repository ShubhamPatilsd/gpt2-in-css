# Low-rank and sparse native-CSS GPT-2 matrices

## Question

Can the four real dense matrices in one GPT-2-small block be approximated well
enough that spelling their products out as native CSS becomes practical?

The offline analyzer uses block 0 from `openai-community/gpt2` and 18 diverse
real token embeddings. The one-token attention path is exact: causal attention
has one entry, so its softmax is one and only the value slice of QKV is needed.
LayerNorm, biases, GELU, and residual additions remain exact float64. Only the
four dense weights are approximated.

The dense reference has 5,898,240 multiply terms:

- value projection: 768 x 768;
- attention output projection: 768 x 768;
- feed-forward expansion: 768 x 3,072;
- feed-forward projection: 3,072 x 768.

## Results

The exact block outputs have RMS magnitude 5.107. Errors below compare the
complete approximate block output with the complete exact block output.

### Truncated SVD on every matrix

| Rank | Arithmetic compression | Block RMSE | Relative RMSE | Mean cosine | Worst absolute error |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 32 | 17.14x | 3.1876 | 62.41% | 0.887758 | 83.87 |
| 64 | 8.57x | 2.4996 | 48.94% | 0.943063 | 64.70 |
| 128 | 4.29x | 1.8797 | 36.80% | 0.963988 | 47.66 |
| 256 | 2.14x | 1.0112 | 19.80% | 0.984645 | 19.14 |
| 384 | 1.43x | 0.6983 | 13.67% | 0.990887 | 7.00 |

The feed-forward matrices are not strongly low-rank. Rank 384 retains only
80.34% of expansion weight energy and 79.39% of projection weight energy,
while already retaining 70% of the original multiply count.

### Row-wise magnitude sparsity on every matrix

| Removed weights | Arithmetic compression | Block RMSE | Relative RMSE | Mean cosine | Worst absolute error |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 50% | 2.00x | 0.7796 | 15.26% | 0.994770 | 21.06 |
| 75% | 4.00x | 2.6836 | 52.54% | 0.952929 | 74.00 |
| 90% | 9.99x | 3.9011 | 76.38% | 0.828716 | 96.99 |

Every output row keeps the same number of its largest-magnitude weights. Even
the mild 50% case is far outside the accuracy of the existing HVAR block,
whose measured browser RMSE is 0.00254.

### Low rank plus a sparse residual

Keeping the largest residual weights after SVD improves the Pareto frontier
slightly, but not enough:

| Rank | Residual removed | Compression | Block RMSE | Relative RMSE |
| ---: | ---: | ---: | ---: | ---: |
| 32 | 90% | 6.31x | 1.9804 | 38.78% |
| 64 | 90% | 4.61x | 1.6045 | 31.42% |
| 128 | 90% | 3.00x | 1.3842 | 27.10% |
| 64 | 95% | 6.01x | 2.0796 | 40.72% |
| 128 | 95% | 3.53x | 1.7818 | 34.89% |
| 128 | 97.5% | 3.87x | 1.8135 | 35.51% |

## Browser scaling estimate

The existing expanded native-CSS block uses 5,252,351 nonzero terms, produces
a 94.3 MB stylesheet, and takes 2.48--2.66 seconds for a same-page recompute.
Linear term-count scaling gives optimistic estimates:

- rank 32: about 6.2 MB and 168 ms, but 62% relative RMSE;
- rank 64: about 12.4 MB and 337 ms, but 49% relative RMSE;
- 50% sparsity: about 53.0 MB and 1.44 s, with 15% relative RMSE.

No browser fixture was generated because no approximation is credible. The
only candidates fast enough to alter browser feasibility corrupt the block by
roughly 40--76%. The relatively accurate candidates still retain enough terms
to remain well above the project's per-block target. Low-rank forms also add an
extra dependency boundary for every factorized matrix, so linear estimates are
optimistic.

## Decision

Naive post-training SVD and magnitude pruning do not solve CSS inference
scaling for an unmodified GPT-2 checkpoint. They exchange the HVAR transport
problem for millions of native CSS terms while producing errors hundreds of
times larger than the current accurate backend.

This path could become viable only with retraining or distillation that makes
the model explicitly low-rank/sparse. That conflicts with the goal of running
the actual pretrained GPT-2 weights. Keep compact matrix representations and
continue targeting vector-level result transport instead.

## Reproduce

```sh
python3 tools/analyze_lowrank_sparse_css.py
```

Machine-readable measurements are in `results.json`; browser extrapolations
are in `browser-estimate.json`.
