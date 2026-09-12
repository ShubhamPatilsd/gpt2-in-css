# Spatially batched token QKV

This experiment computes both two-token QKV projections side-by-side in each
SVG convolution. It is HTML/SVG only at runtime.

The design reduces QKV convolutions from 144 to 72 and preserves the accepted
decoded result exactly:

- QKV RMSE: 0.0237515;
- context RMSE: 0.00481946;
- probability maximum error: 0.0132019.

Nine alternating warm rounds show that the 128-pixel-wide raster is slower than
two separate 64-pixel-wide token paths:

| layout | QKV median | connected median | QKV HTML | connected HTML |
| --- | ---: | ---: | ---: | ---: |
| Separate tokens | **668.3 ms** | **1,183.1 ms** | 585,289 B | 1,118,372 B |
| Batched tokens | 903.6 ms | 1,565.5 ms | **501,567 B** | **1,034,650 B** |

Decision: reject spatial token batching. It saves 14% of QKV HTML but makes QKV
1.35x slower. Keep each token on the 64-wide Chromium fast path.

Rebuild and benchmark with:

```sh
SVG_MULTITOKEN_OUT=experiments/svg-multitoken-attention-rgb-token-batch \
SVG_QKV_LAYOUT=rgb \
SVG_RGB_QKV_TOKEN_BATCH=1 \
SVG_RGB_ATTENTION_BROADCAST=tile \
  python3 tools/build_svg_multitoken_attention.py

SVG_QKV_BENCH_SET=rgbbatch SVG_QKV_BENCH_ROUNDS=9 \
  node tools/benchmark_svg_multitoken_qkv_layouts.mjs
```

