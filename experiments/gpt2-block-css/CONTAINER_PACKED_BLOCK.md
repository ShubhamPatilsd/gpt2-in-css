# Six-output container packets through a complete GPT-2 block

This experiment applies the direct width/height container packet to every
dense stage of one GPT-2-small transformer block. Runtime is HTML/CSS-only.

Each carrier stores three 8-bit post-affine outputs in its width and three in
its height. The 3,072-output FC is split into two 1,536-output shadow stages,
because the attempted single 512-container stage corrupted its last 36
outputs at Chrome's nesting boundary.

Measured in headless Chrome 153 on macOS:

| Cumulative prefix | Containers added | Warm median |
| --- | ---: | ---: |
| composed one-token attention | 128 | 80 ms |
| plus FC outputs 0–1,535 | 256 | 434 ms |
| plus FC outputs 1,536–3,071 | 256 | 676 ms |
| plus 3,072→768 projection | 128 | 2,258 ms |

The complete browser result is 0.01035 RMSE from the numerical packed
simulation and 0.02648 RMSE from the higher-precision quantized block. The
older four-output raw-dot packet block stabilizes near 436 ms and 0.00971 RMSE
under the same mutation pattern.

## Decision

Reject six-output post-affine container packing as the transport for every
block stage. It reduces carrier count but makes the full block about five times
slower and less accurate. The wide MLP projection is the breaking point: it
must consume 3,072 inherited values across twelve font shards after two deep
packed FC stages.

Retain the method as a localized QKV optimization. Isolated QKV improves from
roughly 267 ms with 2,304 timelines to 168–197 ms with 384 containers. The next
valid integration test should replace only QKV readback in multi-token
attention, then keep native CSS for attention arithmetic and the existing
geometry-eased transport for later matrices.
