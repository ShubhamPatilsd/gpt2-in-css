# GPT-2 IVF vocabulary router

This screen removes the arbitrary token-ID grouping. Six float32 k-means
iterations partition all 50,257 GPT-2 embedding rows into 256 geometric
clusters. A router scores the 256 centroids, then exactly evaluates every token
in the top clusters. It uses the same 1,024 contextual states and splits as the
supervised-router screen.

Clusters are highly imbalanced: size 1--1,891, median 115, and 95th percentile
655. Held-out centroid-dot routing gives:

| Probed clusters | Winner-cluster recall | Mean rows including 256 centroids | Dense reduction |
| ---: | ---: | ---: | ---: |
| 1 | 34.4% | 702 | 71.5x |
| 4 | 76.6% | 1,814 | 27.7x |
| 8 | 90.2% | 2,969 | 16.9x |
| 16 | 94.5% | 4,978 | 10.1x |
| 32 | 97.3% | 8,404 | 5.98x |
| 64 | 98.0% | 14,515 | 3.46x |
| 128 | 99.6% test; 99.4% train | 26,180 | 1.92x |
| 192 | 100% test; 99.6% train/validation | 38,017 | 1.32x |

The radius-based L2 upper bounds are rigorous but too loose to rank useful
clusters: the true winner cluster appears in the first 32 bounds for only
6.6% of test states. This is consistent with the earlier exact branch-and-bound
failure.

Geometric reordering is a substantially better approximate router than
contiguous groups, but it still has no exact operating point before essentially
the full scan. Keep the curve only if approximate generation becomes an
explicit goal; reject it for exact CSS inference.

## Reproduce

```sh
make analyze-gpt2-ivf-group-router
```
