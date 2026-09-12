# Live propagation into block 1 attention

This page connects the complete live output of block 0 to block 1 LN1, centered
QKV, causal two-token attention, attention projection, and the attention
residual. It contains no JavaScript.

The first token's normalized block-1 input is a fixed cache entry. The second
token is computed live by block 0 and normalized live before block 1 QKV.

Nine forced-recomputation measurements produced:

- median warm time: 1,504 ms
- minimum warm time: 1,434 ms
- one slow sample: 2,800 ms
- block-1 residual RMSE: 0.20989
- block-1 residual maximum error: 3.79674
- RMSE after block 1 LN2: 0.01898
- maximum error after block 1 LN2: 0.23046
- generated HTML: 4,066,685 bytes

The post-LN2 error is lower than block 0's post-normalization error. This is
evidence that the current 8-bit SVG transport does not necessarily accumulate
raw residual error from block to block; layer normalization suppresses most of
it before the next learned matrix.

Remaining work: attach block 1's MLP, repeat the generic block wrapper through
blocks 2–11, replace the fixed first-token cache entry with a live/cache
transport, and attach the final layer norm and output head.
