# Live-QKV connection test for spatially batched attention

This experiment connects the existing live two-token `768 → 2304` QKV SVG
projection to the compact spatially batched attention mixer. The runtime page
contains HTML/SVG only.

## Attempted transport

The live QKV graph exposes 72 separate 64-value named surfaces: two tokens ×
Q/K/V × twelve heads. The adapter attempted to turn each set of twelve head
surfaces into one contiguous 768-value vector, then split that merged vector
once for the compact attention core.

Two variants were tested:

1. crop and move each live surface with one `feOffset`;
2. crop first and move with a second `feOffset`, matching the workaround used
   by earlier successful fixed-surface transports.

Both variants rendered all twelve attention probabilities as zero. The fixed
Q/K/V compact mixer itself remains correct, so the failure is specifically at
the live QKV relocation/merge boundary.

## Browser result

The second variant was compared with the existing connected-QKV page in the
same Chrome process:

| Connected page | warm mean | context RMSE | max probability error | valid |
| --- | ---: | ---: | ---: | --- |
| Existing head-local graph | 1,436.7 ms | 0.00765 | 0.03188 | yes |
| Merged-vector adapter | 2,376.6 ms | 0.30348 | 0.96270 | no |

The invalid adapter was also slower despite being smaller:

| Connected page | primitives | raw HTML | Brotli q5 |
| --- | ---: | ---: | ---: |
| Existing | 4,218 | 1,706,770 B | 38,935 B |
| Merged-vector adapter | 3,791 | 1,248,370 B | 22,200 B |

This is direct evidence that fewer SVG objects do not guarantee lower latency.
The merged vector creates a wide fan-in dependency on all QKV branches, while
the original graph preserves head-local dependencies. Chromium both fails to
transport the combined live surface correctly and performs substantially more
work evaluating it.

## Decision

Reject live QKV-to-vector merging through `feOffset` plus `feMerge`. Keep the
spatially batched attention result as a bundle-size technique only when its
inputs already exist in a compatible surface. For connected inference,
preserve head-local surfaces and optimize within each valid surface boundary;
RGB packing of independent nonlinear branches is currently the proven example.

`results.json` contains the authoritative browser comparison. The invalid page
is retained as a regression fixture for future transport mechanisms.
