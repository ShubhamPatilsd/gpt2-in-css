# GPT-2 FC axis-ceiling alternatives

Two possible ways to force 768 MLP inputs through 256 font axes were screened
against ten real GPT-2 prompts before building browser assets.

## Rank-256 FC approximation

Replacing every `768 -> 3,072` FC matrix with its rank-256 SVD approximation
retains 65.8% of weight energy on average but preserves 0/10 next-token
winners. The exact winner falls as low as rank 2,318. Even rank 512 preserves
only 2/10 winners.

Decision: reject low-rank FC compression without retraining.

## Packing three quantized activations per axis

An avar2 lookup can theoretically decode three discrete activations from one
axis while computing a dot product. Its region count grows with the cube of
the states per activation.

| Precision | Best top-1 matches | Packed states per axis | Deltas per 256-hidden shard |
| ---: | ---: | ---: | ---: |
| 2-bit signed | 3/10 | 27 | 1,769,472 |
| 3-bit signed | 3/10 | 343 | 22,478,848 |
| 4-bit signed | 4/10 | 3,375 | 221,184,000 |
| 5-bit signed | 6/10 | 29,791 | 1,952,382,976 |
| 6-bit signed | 7/10 | 250,047 | 16,387,080,192 |
| 8-bit signed | 9/10 | 16,581,375 | 1,086,676,992,000 |

Low precision is unusable and useful precision makes the lookup exponential.
Decision: reject packed-axis avar2 decoding as the general MLP path.

The retained solution is exact hidden-dimension sharding: twelve parallel
256-wide groups with sparse coordinatewise avar2 GELU and linear HVAR
projection.

```sh
make analyze-gpt2-fc-lowrank
make analyze-gpt2-mlp-input-quantization
```
