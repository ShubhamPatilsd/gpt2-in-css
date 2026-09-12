# One complete live GPT-2 block

This page runs one complete GPT-2 block for the newest token entirely through
HTML and SVG filters:

1. centered 768→2,304 QKV projection
2. causal two-token attention
3. 768→768 attention projection and residual
4. LN2
5. centered 768→3,072 MLP expansion
6. GELU
7. split-sign 3,072→768 MLP projection
8. live residual addition

It does not bake the final residual into an image. LN2 passes the live residual
beside its normalized output, and the MLP stage rescales and adds it after the
projection.

Nine forced-recomputation measurements produced a 952 ms median. A subsequent
five-run verification produced a 968 ms median. The occasional first/cold
sample was about 1.9 seconds.

Accuracy for the final 768-value block state:

- raw RMSE: 0.33813
- raw maximum error: 4.08317
- clipped output channels: 0
- RMSE after applying the next block's LN1: 0.03595
- maximum error after the next LN1: 0.34451

The post-normalization result is the important propagation measure: the next
block receives a state with about 0.036 RMSE rather than the raw 0.338 residual
error. This is the first retained fixture that connects every operation and
both residual paths of a live multi-token GPT-2 block.

Current limitations: the input is a fixed two-token fixture, only block 0 is
connected live, and the output head/token feedback loop is not attached.
