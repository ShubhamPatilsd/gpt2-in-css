# Block 1 centered-QKV fixture

This fixture applies GPT-2 block 1's QKV weights to the two block-0 output
states. It uses the retained centered single-convolution QKV path with gain 1.9.

- QKV RMSE: 0.03532
- QKV maximum error: 0.25297
- isolated QKV measurement: 502 ms

This page still uses fixed encoded inputs. The live propagation experiment is
in `../svg-live-two-block-attention/`.

