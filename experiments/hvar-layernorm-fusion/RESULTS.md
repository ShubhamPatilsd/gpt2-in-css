# HVAR LayerNorm-to-matrix fusion

LayerNorm followed by a matrix can be rewritten exactly so the normalized
768-vector never has to be materialized:

```text
B = W diag(gamma) - row_mean(W diag(gamma))
b' = W beta + b
W LayerNorm(x) + b = B x / sqrt(var(x) + epsilon) + b'
```

The algebra is exact. This experiment measures the effect of quantizing the
transformed matrix `B` for HVAR, using block 0 and 18 diverse real GPT-2 token
embeddings.

| Consumer | Existing 9-bit RMSE | Fused 9-bit RMSE | Fused 10-bit RMSE |
| --- | ---: | ---: | ---: |
| LN1 to QKV | 0.00197 | 0.00441 | 0.00213 |
| LN2 to FC | 0.00391 | 0.02080 | 0.01024 |

Ten-bit fused weights fit the unsigned HVAR advance range for these matrices,
but not every MVAR metric's signed 16-bit base range. Fusion can remove 768
per-coordinate normalization expressions and one dependency boundary, but it
does not remove matrix-output transport. Its modest structural saving does not
justify the 2.2x to 5.3x 9-bit error increase as the default. Retain it only as
an optional 10-bit experiment after a faster output transport exists.

```sh
/usr/bin/python3 tools/analyze_hvar_layernorm_fusion.py
```
