# Certified query-aware vocabulary ball tree

## Result

The strongest measured configuration retained the exact row-int10 winner for **1024/1,024 states**. It scored a median **50118** leaf rows, p95 **50118**, and maximum **50144**, versus **50,257 rows** for the full int10 scan. Median retained row work was **99.72%** of baseline.

This is materially stronger than the prior axis-split full-space L2/box screen: the new hierarchy is k-means-partitioned in a training-query metric, and its strongest bound takes the minimum of a full L2 ball, a rank-16 query-subspace residual bound, and eight spherical-cap residual bounds. The index was fitted only on the saved 512-state training split; validation and test states were not used to fit its basis, anchors, or partition.

## Measurements

| Tree | Certified bound | Leaf threshold | Exact winners | Median rows | p95 rows | Max rows | Median internal nodes | p95 internal nodes |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| kmeans-b8-minleaf32 | l2Ball | 32 | 1024/1024 | 50176 | 50177 | 50177 | 1392 | 1392 |
| kmeans-b8-minleaf32 | l2Ball | 64 | 1024/1024 | 50205 | 50206 | 50206 | 397 | 397 |
| kmeans-b8-minleaf32 | l2Ball | 128 | 1024/1024 | 50223 | 50224 | 50224 | 220 | 220 |
| kmeans-b8-minleaf32 | l2Ball | 256 | 1024/1024 | 50244 | 50245 | 50245 | 103 | 103 |
| kmeans-b8-minleaf32 | querySubspaceR8 | 32 | 1024/1024 | 50118 | 50118 | 50144 | 1392 | 1392 |
| kmeans-b8-minleaf32 | querySubspaceR8 | 64 | 1024/1024 | 50205 | 50205 | 50206 | 397 | 397 |
| kmeans-b8-minleaf32 | querySubspaceR8 | 128 | 1024/1024 | 50223 | 50223 | 50224 | 220 | 220 |
| kmeans-b8-minleaf32 | querySubspaceR8 | 256 | 1024/1024 | 50244 | 50245 | 50245 | 103 | 103 |
| kmeans-b8-minleaf32 | querySubspaceR16 | 32 | 1024/1024 | 50118 | 50118 | 50144 | 1392 | 1392 |
| kmeans-b8-minleaf32 | querySubspaceR16 | 64 | 1024/1024 | 50205 | 50205 | 50206 | 397 | 397 |
| kmeans-b8-minleaf32 | querySubspaceR16 | 128 | 1024/1024 | 50223 | 50223 | 50224 | 220 | 220 |
| kmeans-b8-minleaf32 | querySubspaceR16 | 256 | 1024/1024 | 50244 | 50244 | 50245 | 103 | 103 |
| kmeans-b8-minleaf32 | querySubspaceR32 | 32 | 1024/1024 | 50118 | 50118 | 50144 | 1392 | 1392 |
| kmeans-b8-minleaf32 | querySubspaceR32 | 64 | 1024/1024 | 50205 | 50205 | 50206 | 397 | 397 |
| kmeans-b8-minleaf32 | querySubspaceR32 | 128 | 1024/1024 | 50223 | 50223 | 50224 | 220 | 220 |
| kmeans-b8-minleaf32 | querySubspaceR32 | 256 | 1024/1024 | 50244 | 50244 | 50245 | 103 | 103 |
| kmeans-b8-minleaf32 | sphericalCaps4 | 32 | 1024/1024 | 50144 | 50144 | 50145 | 1392 | 1392 |
| kmeans-b8-minleaf32 | sphericalCaps4 | 64 | 1024/1024 | 50205 | 50206 | 50206 | 397 | 397 |
| kmeans-b8-minleaf32 | sphericalCaps4 | 128 | 1024/1024 | 50223 | 50224 | 50224 | 220 | 220 |
| kmeans-b8-minleaf32 | sphericalCaps4 | 256 | 1024/1024 | 50244 | 50245 | 50245 | 103 | 103 |
| kmeans-b8-minleaf32 | sphericalCaps8 | 32 | 1024/1024 | 50119 | 50144 | 50145 | 1392 | 1392 |
| kmeans-b8-minleaf32 | sphericalCaps8 | 64 | 1024/1024 | 50205 | 50206 | 50206 | 397 | 397 |
| kmeans-b8-minleaf32 | sphericalCaps8 | 128 | 1024/1024 | 50223 | 50224 | 50224 | 220 | 220 |
| kmeans-b8-minleaf32 | sphericalCaps8 | 256 | 1024/1024 | 50244 | 50245 | 50245 | 103 | 103 |
| kmeans-b8-minleaf32 | sphericalCaps16 | 32 | 1024/1024 | 50118 | 50144 | 50145 | 1392 | 1392 |
| kmeans-b8-minleaf32 | sphericalCaps16 | 64 | 1024/1024 | 50205 | 50206 | 50206 | 397 | 397 |
| kmeans-b8-minleaf32 | sphericalCaps16 | 128 | 1024/1024 | 50223 | 50224 | 50224 | 220 | 220 |
| kmeans-b8-minleaf32 | sphericalCaps16 | 256 | 1024/1024 | 50244 | 50245 | 50245 | 103 | 103 |
| kmeans-b8-minleaf32 | combinedR16Caps8 | 32 | 1024/1024 | 50118 | 50118 | 50144 | 1392 | 1392 |
| kmeans-b8-minleaf32 | combinedR16Caps8 | 64 | 1024/1024 | 50205 | 50205 | 50206 | 397 | 397 |
| kmeans-b8-minleaf32 | combinedR16Caps8 | 128 | 1024/1024 | 50223 | 50223 | 50224 | 220 | 220 |
| kmeans-b8-minleaf32 | combinedR16Caps8 | 256 | 1024/1024 | 50244 | 50244 | 50245 | 103 | 103 |
| kmeans-b16-minleaf32 | l2Ball | 32 | 1024/1024 | 50187 | 50188 | 50188 | 1288 | 1288 |
| kmeans-b16-minleaf32 | l2Ball | 64 | 1024/1024 | 50212 | 50213 | 50213 | 288 | 288 |
| kmeans-b16-minleaf32 | l2Ball | 128 | 1024/1024 | 50218 | 50219 | 50219 | 139 | 139 |
| kmeans-b16-minleaf32 | l2Ball | 256 | 1024/1024 | 50225 | 50225 | 50226 | 89 | 89 |
| kmeans-b16-minleaf32 | querySubspaceR8 | 32 | 1024/1024 | 50128 | 50128 | 50129 | 1286 | 1286 |
| kmeans-b16-minleaf32 | querySubspaceR8 | 64 | 1024/1024 | 50212 | 50212 | 50213 | 288 | 288 |
| kmeans-b16-minleaf32 | querySubspaceR8 | 128 | 1024/1024 | 50218 | 50218 | 50219 | 139 | 139 |
| kmeans-b16-minleaf32 | querySubspaceR8 | 256 | 1024/1024 | 50225 | 50225 | 50226 | 89 | 89 |
| kmeans-b16-minleaf32 | querySubspaceR16 | 32 | 1024/1024 | 50126 | 50128 | 50129 | 1286 | 1286 |
| kmeans-b16-minleaf32 | querySubspaceR16 | 64 | 1024/1024 | 50212 | 50212 | 50213 | 288 | 288 |
| kmeans-b16-minleaf32 | querySubspaceR16 | 128 | 1024/1024 | 50218 | 50218 | 50219 | 139 | 139 |
| kmeans-b16-minleaf32 | querySubspaceR16 | 256 | 1024/1024 | 50225 | 50225 | 50226 | 89 | 89 |
| kmeans-b16-minleaf32 | querySubspaceR32 | 32 | 1024/1024 | 50125 | 50128 | 50129 | 1286 | 1286 |
| kmeans-b16-minleaf32 | querySubspaceR32 | 64 | 1024/1024 | 50210 | 50212 | 50213 | 288 | 288 |
| kmeans-b16-minleaf32 | querySubspaceR32 | 128 | 1024/1024 | 50218 | 50218 | 50219 | 139 | 139 |
| kmeans-b16-minleaf32 | querySubspaceR32 | 256 | 1024/1024 | 50225 | 50225 | 50226 | 89 | 89 |
| kmeans-b16-minleaf32 | sphericalCaps4 | 32 | 1024/1024 | 50128 | 50130 | 50158 | 1288 | 1288 |
| kmeans-b16-minleaf32 | sphericalCaps4 | 64 | 1024/1024 | 50212 | 50213 | 50213 | 288 | 288 |
| kmeans-b16-minleaf32 | sphericalCaps4 | 128 | 1024/1024 | 50218 | 50219 | 50219 | 139 | 139 |
| kmeans-b16-minleaf32 | sphericalCaps4 | 256 | 1024/1024 | 50225 | 50225 | 50226 | 89 | 89 |
| kmeans-b16-minleaf32 | sphericalCaps8 | 32 | 1024/1024 | 50128 | 50130 | 50158 | 1288 | 1288 |
| kmeans-b16-minleaf32 | sphericalCaps8 | 64 | 1024/1024 | 50212 | 50213 | 50213 | 288 | 288 |
| kmeans-b16-minleaf32 | sphericalCaps8 | 128 | 1024/1024 | 50218 | 50219 | 50219 | 139 | 139 |
| kmeans-b16-minleaf32 | sphericalCaps8 | 256 | 1024/1024 | 50225 | 50225 | 50226 | 89 | 89 |
| kmeans-b16-minleaf32 | sphericalCaps16 | 32 | 1024/1024 | 50128 | 50129 | 50130 | 1286 | 1288 |
| kmeans-b16-minleaf32 | sphericalCaps16 | 64 | 1024/1024 | 50212 | 50213 | 50213 | 288 | 288 |
| kmeans-b16-minleaf32 | sphericalCaps16 | 128 | 1024/1024 | 50218 | 50219 | 50219 | 139 | 139 |
| kmeans-b16-minleaf32 | sphericalCaps16 | 256 | 1024/1024 | 50225 | 50225 | 50226 | 89 | 89 |
| kmeans-b16-minleaf32 | combinedR16Caps8 | 32 | 1024/1024 | 50126 | 50128 | 50129 | 1286 | 1286 |
| kmeans-b16-minleaf32 | combinedR16Caps8 | 64 | 1024/1024 | 50212 | 50212 | 50213 | 288 | 288 |
| kmeans-b16-minleaf32 | combinedR16Caps8 | 128 | 1024/1024 | 50218 | 50218 | 50219 | 139 | 139 |
| kmeans-b16-minleaf32 | combinedR16Caps8 | 256 | 1024/1024 | 50225 | 50225 | 50226 | 89 | 89 |

The complete split distributions, all per-state raw counts, tree geometry, and bound checks are in `results.json` and `raw-results.json`.

## Certification contract

- Target rows are the checkpoint's 50,257 output embeddings after independent symmetric signed-int10 quantization per row (code range -511..511).
- Full-scan winners and leaf scores use the same realized row-int10 matrix and saved float32 hidden states.
- For node representative `c`, the plain bound is `h·c + ||h||₂ r`.
- The subspace bound stores rigorous coordinate intervals and an orthogonal residual radius; the cap bound stores a scalar interval and perpendicular residual radius for each unit anchor. Taking the minimum of valid upper bounds remains valid.
- Ties are resolved by the lowest token id, matching `argmax`; pruning is strict below the incumbent score.
- Every stored node bound was checked against that node's exact maximum for every one of the 1,024 queries. Maximum observed bound violation was **0**.

## Interpretation

This is an offline feasibility screen, not a claim that CSS can branch dynamically at this cost. Internal-node bounds have nontrivial arithmetic and storage: subspace/cap bounds exchange vocabulary-row dot products for representative dots plus interval/radius terms. The separate internal-node and leaf-row distributions make that tradeoff explicit. Query fitting is corpus-specific, while correctness is geometric for any query evaluated against the stored bounds.

Runtime was **596.14s** with offline NumPy; no browser was used.
