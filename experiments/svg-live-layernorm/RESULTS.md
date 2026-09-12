# Live attention residual to LN2

This runtime-only HTML/SVG page connects the retained centered-QKV attention
path to the second layer normalization in GPT-2 block 0. It also carries the
unmodified attention residual in a neighboring pixel column for the later MLP
skip connection.

The source residual has a different numeric scale for each of its 768 channels.
The LN2 stage first converts those channels to one common range, then calculates
the mean, variance, reciprocal square root, learned scale, and learned bias in
SVG filters.

Five forced-recomputation measurements produced:

- median warm time: 928 ms
- LN2 RMSE: 0.08234
- maximum error: 0.19939
- added LN2 primitives: 36
- generated HTML: 2,023,196 bytes

The test mutates the original input image URL before each screenshot so the
measurement cannot be satisfied by Chromium's cached raster.

