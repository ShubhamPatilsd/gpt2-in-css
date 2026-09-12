# Block 1 calibrated MLP

This is the centered 768→3,072 expansion and split-sign 3,072→768 projection
calibrated to block 1's real attention residual.

At centered gain 4.5, five isolated forced-recomputation measurements produced:

- median warm time: 370 ms
- final MLP/residual RMSE: 0.16198
- maximum error: 2.58801

An isolated gain sweep favored gain 3.0 with 0.10376 RMSE. That setting was
rejected after end-to-end testing: live two-block post-normalization RMSE rose
from 0.06078 at gain 4.5 to 0.06396 at gain 3.0. Upstream quantization changes
the robust optimum, so this fixture retains gain 4.5.

