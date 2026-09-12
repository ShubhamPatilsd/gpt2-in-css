# Live block 1 LN2

This generic layer-normalization wrapper consumes the live block-1 attention
residual and carries the residual alongside LN2 for the MLP skip connection.

Five forced-recomputation measurements produced:

- median warm time through block 1 LN2: 1,800 ms
- LN2 RMSE: 0.03245
- maximum error: 0.25023

