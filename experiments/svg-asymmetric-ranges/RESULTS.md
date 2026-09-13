# Asymmetric SVG activation ranges

## Question

Can the SVG backend use its fixed 256 code values more efficiently by learning
non-zero-centered activation ranges instead of mapping every surface around
code 128?

The screen uses 256 calibration tokens and 512 disjoint evaluation tokens,
including the 64-token natural-language suite. All 110 activation boundaries in
the twelve one-token GPT-2-small blocks are materialized to eight bits. Weights
use the same PNG quantization model as the current SVG backend.

## Results

| Scheme | Held-out top-1 | Natural top-1 | Final-state RMSE |
| --- | ---: | ---: | ---: |
| current symmetric 32 groups | 482/512 | 53/64 | 0.2254 |
| asymmetric 16 groups, all surfaces | 480/512 | 55/64 | 0.0777 |
| asymmetric 32 groups, all surfaces | 484/512 | 54/64 | 0.0736 |
| asymmetric 32 groups, state only | 483/512 | 56/64 | 0.0918 |
| 2D range-clustered 32 groups, state only | **489/512** | 54/64 | 0.0971 |
| per-channel asymmetric upper bound | 488/512 | 55/64 | 0.0801 |

The reusable 768-value residual/state boundaries account for most of the RMSE
improvement. Making only post-GELU surfaces asymmetric has little effect.
Clustering on both range midpoint and span improves general held-out agreement,
but only from 94.14% to 95.51%. The per-channel upper bound is no better.

## Decision

Asymmetric range transport is legitimate and can be implemented by folding each
group's decode offset into the following affine bias. It is a useful accuracy
refinement, not the missing scalable precision transport: it does not add bits,
and the top-1 gain is small and inconsistent on the 64 natural cases.

Do not rebuild the full SVG chain around this yet. Retain the 2D-clustered,
state-only form as a later refinement if the SVG backend becomes the selected
runtime. The present scaling decision should continue to focus on avoiding
materialized eight-bit boundaries rather than optimizing their ranges.

## Reproduce

```sh
uv run --with numpy python tools/screen_svg_asymmetric_ranges.py
```
