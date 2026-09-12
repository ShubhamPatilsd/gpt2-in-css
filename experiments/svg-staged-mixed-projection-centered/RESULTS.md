# Centered-QKV direct residual path

This page connects the centered single-convolution QKV implementation to live
two-token attention, direct mixed-context `c_proj`, and the attention residual.
It is HTML/SVG only at runtime.

A forced-recomputation benchmark changes the input image URL before every
measurement. This prevents Chrome from satisfying screenshots with a cached
raster.

| run order | split-sign QKV | centered QKV | speedup |
| --- | ---: | ---: | ---: |
| Split-sign first, 8 rounds | 1,154.0 ms | 563.2 ms | 2.05x |
| Centered first, 10 rounds | 1,158.1 ms | 583.5 ms | 1.98x |

Residual RMSE is 0.03490 versus 0.03343 for split-sign QKV. Both have the same
0.36910 maximum error. The centered implementation is the retained path.

See `../svg-multitoken-attention-rgb-centered/RESULTS.md` for the QKV algebra,
gain sweep, and isolated attention measurements.

