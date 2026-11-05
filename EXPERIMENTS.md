# Experiment index

Every experiment, optimisation round and audit in this repository, in date order. One line per entry.
The date is the last time a source file in the entry changed. The title is the first heading of its notes,
if it has notes. Entries from the same day and topic share one commit in `git log`, with that date.

- `experiments/`: single probes and studies (fonts, SVG filters, anchors, timelines, ...).
- `work/2026-09-19/`: the speed rounds (B = baseline/bench, F/R2–R8 = rounds) for the shipped page.
- `audit/`: profiling audits and write-ups.

Generated files (fonts, built CSS/HTML bundles, Chrome traces, logs) are not in git. The scripts in each folder
or in `tools/` build them again.

## 2026-08-25

| Time | Entry | Notes title |
|---|---|---|
| 02:37 | [`experiments/editable-style-input.html`](experiments/editable-style-input.html) |  |
| 02:38 | [`experiments/direct-embedding-tokenizer.html`](experiments/direct-embedding-tokenizer.html) |  |
| 02:39 | [`experiments/CSS_TOKENIZER_FEASIBILITY.md`](experiments/CSS_TOKENIZER_FEASIBILITY.md) | CSS-only GPT-2 tokenizer: implemented path |

## 2026-08-26

| Time | Entry | Notes title |
|---|---|---|
| 16:32 | [`experiments/anchor-merge-probe.html`](experiments/anchor-merge-probe.html) |  |
| 16:47 | [`experiments/matrix-backends`](experiments/matrix-backends) | HTML/CSS-only 64×64 matrix backend results |
| 16:47 | [`experiments/signed-hvar-chain`](experiments/signed-hvar-chain) |  |
| 17:03 | [`experiments/forwarded-depth-probe.html`](experiments/forwarded-depth-probe.html) |  |
| 17:03 | [`experiments/shadow-depth-probe.html`](experiments/shadow-depth-probe.html) |  |
| 17:03 | [`experiments/slotted-depth-probe.html`](experiments/slotted-depth-probe.html) |  |
| 17:58 | [`experiments/packed-font-shards`](experiments/packed-font-shards) |  |
| 18:44 | [`experiments/parallel-anchor-merge-probe.html`](experiments/parallel-anchor-merge-probe.html) |  |
| 18:49 | [`experiments/slotted-anchor-merge-probe.html`](experiments/slotted-anchor-merge-probe.html) |  |
| 18:52 | [`experiments/counter-state-escape-probe.html`](experiments/counter-state-escape-probe.html) |  |
| 18:53 | [`experiments/counter-shadow-escape-probe.html`](experiments/counter-shadow-escape-probe.html) |  |
| 18:54 | [`experiments/packed-container-readback-probe.html`](experiments/packed-container-readback-probe.html) |  |
| 18:56 | [`experiments/inherit-function-probe.html`](experiments/inherit-function-probe.html) |  |
| 19:18 | [`experiments/direct-anchor-readback-probe.html`](experiments/direct-anchor-readback-probe.html) |  |

## 2026-08-29

| Time | Entry | Notes title |
|---|---|---|
| 05:18 | [`experiments/typographic-branch-merge-probe.html`](experiments/typographic-branch-merge-probe.html) |  |
| 05:28 | [`experiments/view-timeline-readback-probe.html`](experiments/view-timeline-readback-probe.html) |  |
| 05:29 | [`experiments/view-timeline-scale-3072.html`](experiments/view-timeline-scale-3072.html) |  |
| 05:29 | [`experiments/view-timeline-scale-64.html`](experiments/view-timeline-scale-64.html) |  |
| 05:29 | [`experiments/view-timeline-scale-768.html`](experiments/view-timeline-scale-768.html) |  |

## 2026-09-06

| Time | Entry | Notes title |
|---|---|---|
| 22:30 | [`experiments/css-function-gelu-probe.html`](experiments/css-function-gelu-probe.html) |  |

## 2026-09-07

| Time | Entry | Notes title |
|---|---|---|
| 13:09 | [`experiments/view-timeline-2d-probe.html`](experiments/view-timeline-2d-probe.html) |  |

## 2026-09-08

| Time | Entry | Notes title |
|---|---|---|
| 00:11 | [`experiments/font-metric-vector`](experiments/font-metric-vector) | Four-output font-metric transport |
| 02:50 | [`experiments/view-timeline-two-value-probe.html`](experiments/view-timeline-two-value-probe.html) |  |
| 02:53 | [`experiments/additive-font-vector`](experiments/additive-font-vector) | Geometry-to-vector transport results |
| 03:19 | [`experiments/intrinsic-width-pack-probe.html`](experiments/intrinsic-width-pack-probe.html) |  |
| 03:49 | [`experiments/anchor-font-transport-probe.html`](experiments/anchor-font-transport-probe.html) |  |
| 03:53 | [`experiments/svg-filter-fc`](experiments/svg-filter-fc) |  |
| 04:11 | [`experiments/svg-filter-gpt2-attention`](experiments/svg-filter-gpt2-attention) |  |
| 04:11 | [`experiments/svg-filter-gpt2-fc`](experiments/svg-filter-gpt2-fc) |  |
| 04:12 | [`experiments/svg-filter-layernorm`](experiments/svg-filter-layernorm) |  |
| 04:17 | [`experiments/svg-filter-element-chain-probe.html`](experiments/svg-filter-element-chain-probe.html) |  |
| 09:24 | [`experiments/matrix-scaling`](experiments/matrix-scaling) | Variable-font matrix scaling results |

## 2026-09-10

| Time | Entry | Notes title |
|---|---|---|
| 22:24 | [`experiments/svg-filter-output-head`](experiments/svg-filter-output-head) |  |
| 23:39 | [`experiments/svg-16bit-precision`](experiments/svg-16bit-precision) |  |

## 2026-09-11

| Time | Entry | Notes title |
|---|---|---|
| 01:36 | [`experiments/svg-multitoken-attention`](experiments/svg-multitoken-attention) |  |
| 23:16 | [`experiments/svg-dual-plane-transport`](experiments/svg-dual-plane-transport) | General higher-precision SVG transport |
| 23:48 | [`experiments/svg-linear-fusion-scale`](experiments/svg-linear-fusion-scale) | Linear fusion scaling probe |

## 2026-09-12

| Time | Entry | Notes title |
|---|---|---|
| 02:01 | [`experiments/svg-layernorm-matrix-fusion`](experiments/svg-layernorm-matrix-fusion) |  |
| 02:08 | [`experiments/svg-layernorm-matrix-fusion-bucketed`](experiments/svg-layernorm-matrix-fusion-bucketed) | LayerNorm-to-matrix fusion A/B |
| 02:25 | [`experiments/svg-rg16-transport`](experiments/svg-rg16-transport) |  |
| 02:26 | [`experiments/svg-magnitude-plane-dot`](experiments/svg-magnitude-plane-dot) |  |
| 02:27 | [`experiments/svg-rgb-precision-transport`](experiments/svg-rgb-precision-transport) | RGB coarse-plus-correction transport |
| 02:48 | [`experiments/anchor-geometry-matmul`](experiments/anchor-geometry-matmul) | Anchor geometry numeric backend |
| 02:49 | [`experiments/svg-w8a8-screen`](experiments/svg-w8a8-screen) |  |
| 02:55 | [`experiments/svg-dither-transport`](experiments/svg-dither-transport) |  |
| 03:02 | [`experiments/svg-dither-matrix`](experiments/svg-dither-matrix) |  |
| 03:05 | [`experiments/svg-packed-kernel-matrix`](experiments/svg-packed-kernel-matrix) |  |
| 03:07 | [`experiments/svg-product-dither`](experiments/svg-product-dither) |  |
| 03:09 | [`experiments/direct-container-unit-readback-probe.html`](experiments/direct-container-unit-readback-probe.html) |  |
| 03:13 | [`experiments/gpt2-hvar-chain`](experiments/gpt2-hvar-chain) |  |
| 04:32 | [`experiments/view-timeline-4d-probe.html`](experiments/view-timeline-4d-probe.html) |  |
| 04:34 | [`experiments/lowrank-sparse-css`](experiments/lowrank-sparse-css) | Low-rank and sparse native-CSS GPT-2 matrices |
| 04:35 | [`experiments/css-axis-list-pingpong-probe.html`](experiments/css-axis-list-pingpong-probe.html) |  |
| 04:35 | [`experiments/font-multimetric-probe`](experiments/font-multimetric-probe) | Variable-font multimetric probe |
| 04:37 | [`experiments/feature-metric-readback`](experiments/feature-metric-readback) | Feature-indexed font metric readback |
| 04:39 | [`experiments/css-axis-list-pingpong-probe.html`](experiments/css-axis-list-pingpong-probe.html) | Aggregate axis-list ping-pong |
| 04:39 | [`experiments/hvar-layernorm-fusion`](experiments/hvar-layernorm-fusion) | HVAR LayerNorm-to-matrix fusion |
| 04:39 | [`experiments/view-timeline-4d-scale`](experiments/view-timeline-4d-scale) | Four-value two-axis view-timeline transport |
| 04:54 | [`experiments/font-packed-metrics`](experiments/font-packed-metrics) | Packed font-metric transport |
| 04:55 | [`experiments/ttc-metric-bank`](experiments/ttc-metric-bank) | TTC metric-bank probe |
| 05:00 | [`experiments/font-metric-standard-features`](experiments/font-metric-standard-features) | Standard-feature font-unit multiplexing |
| 06:03 | [`experiments/row-axis-multimetric`](experiments/row-axis-multimetric) | ROW-axis multimetric font bank |
| 06:53 | [`experiments/anchor-geometry-chain`](experiments/anchor-geometry-chain) | Geometry-native dense matrix chain |
| 07:00 | [`experiments/svg-filter-full-block`](experiments/svg-filter-full-block) |  |
| 07:46 | [`experiments/svg-connected-batched-attention`](experiments/svg-connected-batched-attention) | Live-QKV connection test for spatially batched attention |
| 08:30 | [`experiments/svg-filter-matvec`](experiments/svg-filter-matvec) | SVG filter tensor backend |
| 08:31 | [`experiments/svg-filter-bias-correction`](experiments/svg-filter-bias-correction) | SVG calibration and RGB group-packing results |
| 08:40 | [`experiments/svg-contiguous-qkv-batched-part`](experiments/svg-contiguous-qkv-batched-part) |  |
| 08:40 | [`experiments/svg-contiguous-qkv-batched-vector`](experiments/svg-contiguous-qkv-batched-vector) |  |
| 08:40 | [`experiments/svg-multitoken-attention-partized`](experiments/svg-multitoken-attention-partized) |  |
| 08:40 | [`experiments/svg-multitoken-attention-vectorized`](experiments/svg-multitoken-attention-vectorized) |  |
| 08:42 | [`experiments/svg-contiguous-qkv-batched-native-part`](experiments/svg-contiguous-qkv-batched-native-part) |  |
| 08:42 | [`experiments/svg-multitoken-attention-batched-y255`](experiments/svg-multitoken-attention-batched-y255) |  |
| 08:44 | [`experiments/svg-multitoken-attention-batched-convolve`](experiments/svg-multitoken-attention-batched-convolve) |  |
| 08:45 | [`experiments/svg-multitoken-attention-batched-y255-convolve`](experiments/svg-multitoken-attention-batched-y255-convolve) |  |
| 08:47 | [`experiments/svg-contiguous-qkv-batched-native-convolve`](experiments/svg-contiguous-qkv-batched-native-convolve) | Contiguous live QKV into native-position batched attention |
| 08:49 | [`experiments/svg-multitoken-attention-group2`](experiments/svg-multitoken-attention-group2) |  |
| 08:49 | [`experiments/svg-multitoken-attention-group3`](experiments/svg-multitoken-attention-group3) |  |
| 08:49 | [`experiments/svg-multitoken-attention-group4`](experiments/svg-multitoken-attention-group4) |  |
| 08:49 | [`experiments/svg-multitoken-attention-group6`](experiments/svg-multitoken-attention-group6) |  |
| 08:52 | [`experiments/svg-multitoken-attention-shard128`](experiments/svg-multitoken-attention-shard128) |  |
| 08:52 | [`experiments/svg-multitoken-attention-shard192`](experiments/svg-multitoken-attention-shard192) |  |
| 08:52 | [`experiments/svg-multitoken-attention-shard384`](experiments/svg-multitoken-attention-shard384) |  |
| 09:01 | [`experiments/svg-multitoken-attention-rgb`](experiments/svg-multitoken-attention-rgb) |  |
| 09:06 | [`experiments/svg-multitoken-attention-batched`](experiments/svg-multitoken-attention-batched) | Spatially batched GPT-2 attention heads |
| 09:34 | [`experiments/svg-staged-mixed-projection-rgb`](experiments/svg-staged-mixed-projection-rgb) |  |
| 09:40 | [`experiments/svg-multitoken-attention-rgb-token-batch`](experiments/svg-multitoken-attention-rgb-token-batch) | Spatially batched token QKV |
| 09:54 | [`experiments/svg-multitoken-attention-rgb-centered`](experiments/svg-multitoken-attention-rgb-centered) | Centered single-convolution QKV |
| 09:54 | [`experiments/svg-multitoken-attention-rgb-tile`](experiments/svg-multitoken-attention-rgb-tile) | RGB-packed live QKV with raster-staged attention |
| 09:54 | [`experiments/svg-staged-mixed-projection`](experiments/svg-staged-mixed-projection) | Direct mixed-context attention projection |
| 09:54 | [`experiments/svg-staged-mixed-projection-centered`](experiments/svg-staged-mixed-projection-centered) | Centered-QKV direct residual path |
| 10:03 | [`experiments/svg-filter-gpt2-fc-split`](experiments/svg-filter-gpt2-fc-split) |  |
| 10:05 | [`experiments/svg-filter-gpt2-fc-centered`](experiments/svg-filter-gpt2-fc-centered) | Centered-product GPT-2 MLP |
| 10:07 | [`experiments/svg-filter-gpt2-fc-live-calibrated`](experiments/svg-filter-gpt2-fc-live-calibrated) |  |
| 10:15 | [`experiments/svg-block1-attention-reference.json`](experiments/svg-block1-attention-reference.json) |  |
| 10:18 | [`experiments/svg-block1-staged-mixed-projection`](experiments/svg-block1-staged-mixed-projection) |  |
| 10:22 | [`experiments/svg-block1-attention-rgb-centered`](experiments/svg-block1-attention-rgb-centered) | Block 1 centered-QKV fixture |
| 10:26 | [`experiments/svg-filter-gpt2-fc-block1-gain-sweep`](experiments/svg-filter-gpt2-fc-block1-gain-sweep) |  |
| 10:34 | [`experiments/svg-filter-gpt2-fc-block1-live-calibrated`](experiments/svg-filter-gpt2-fc-block1-live-calibrated) | Block 1 calibrated MLP |
| 10:34 | [`experiments/svg-live-two-block-attention-fused-input`](experiments/svg-live-two-block-attention-fused-input) | Rejected: fuse block 1 LN1 into QKV |
| 10:39 | [`experiments/svg-live-two-complete-blocks-gpu-veto`](experiments/svg-live-two-complete-blocks-gpu-veto) |  |
| 10:49 | [`experiments/svg-live-block1-input`](experiments/svg-live-block1-input) | Live block 0 output to block 1 LN1 |
| 10:49 | [`experiments/svg-live-complete-block`](experiments/svg-live-complete-block) | One complete live GPT-2 block |
| 10:49 | [`experiments/svg-live-layernorm`](experiments/svg-live-layernorm) | Live attention residual to LN2 |
| 10:49 | [`experiments/svg-live-two-block-attention`](experiments/svg-live-two-block-attention) | Live propagation into block 1 attention |
| 10:49 | [`experiments/svg-live-two-block-layernorm`](experiments/svg-live-two-block-layernorm) | Live block 1 LN2 |
| 10:51 | [`experiments/svg-live-layernorm-full`](experiments/svg-live-layernorm-full) |  |
| 10:52 | [`experiments/svg-live-layernorm-r128`](experiments/svg-live-layernorm-r128) |  |
| 10:52 | [`experiments/svg-live-layernorm-r192`](experiments/svg-live-layernorm-r192) |  |
| 10:52 | [`experiments/svg-live-layernorm-r256`](experiments/svg-live-layernorm-r256) |  |
| 10:52 | [`experiments/svg-live-layernorm-r384`](experiments/svg-live-layernorm-r384) |  |
| 10:52 | [`experiments/svg-live-layernorm-r768`](experiments/svg-live-layernorm-r768) |  |
| 10:54 | [`experiments/svg-live-layernorm-moments`](experiments/svg-live-layernorm-moments) |  |
| 10:58 | [`experiments/svg-live-layernorm-gaussian`](experiments/svg-live-layernorm-gaussian) |  |
| 10:59 | [`experiments/svg-live-layernorm-gaussian500`](experiments/svg-live-layernorm-gaussian500) |  |
| 11:01 | [`experiments/svg-fragment-reduction-probe`](experiments/svg-fragment-reduction-probe) |  |
| 11:01 | [`experiments/svg-live-layernorm-gaussian-tiled`](experiments/svg-live-layernorm-gaussian-tiled) |  |
| 11:03 | [`experiments/svg-live-block1-input-gaussian-tiled`](experiments/svg-live-block1-input-gaussian-tiled) |  |
| 11:03 | [`experiments/svg-live-complete-block-gaussian-tiled`](experiments/svg-live-complete-block-gaussian-tiled) |  |
| 11:03 | [`experiments/svg-live-two-block-attention-gaussian-tiled`](experiments/svg-live-two-block-attention-gaussian-tiled) |  |
| 11:03 | [`experiments/svg-live-two-block-layernorm-gaussian-tiled`](experiments/svg-live-two-block-layernorm-gaussian-tiled) |  |
| 11:03 | [`experiments/svg-live-two-complete-blocks-gaussian-tiled`](experiments/svg-live-two-complete-blocks-gaussian-tiled) |  |
| 11:05 | [`experiments/svg-live-layernorm-gaussian-t3-s384`](experiments/svg-live-layernorm-gaussian-t3-s384) |  |
| 11:05 | [`experiments/svg-live-layernorm-gaussian-t3-s500`](experiments/svg-live-layernorm-gaussian-t3-s500) |  |
| 11:05 | [`experiments/svg-live-layernorm-gaussian-t5-s384`](experiments/svg-live-layernorm-gaussian-t5-s384) |  |
| 11:06 | [`experiments/svg-live-block1-input-gaussian-all`](experiments/svg-live-block1-input-gaussian-all) |  |
| 11:08 | [`experiments/svg-live-block1-input-gaussian-all-retained`](experiments/svg-live-block1-input-gaussian-all-retained) |  |
| 11:08 | [`experiments/svg-live-complete-block-gaussian-all`](experiments/svg-live-complete-block-gaussian-all) |  |
| 11:08 | [`experiments/svg-live-two-block-attention-gaussian-all`](experiments/svg-live-two-block-attention-gaussian-all) |  |
| 11:08 | [`experiments/svg-live-two-block-layernorm-gaussian-all`](experiments/svg-live-two-block-layernorm-gaussian-all) |  |
| 11:08 | [`experiments/svg-live-two-complete-blocks-gaussian-all`](experiments/svg-live-two-complete-blocks-gaussian-all) |  |
| 11:12 | [`experiments/svg-layernorm-scale-chain-gaussian`](experiments/svg-layernorm-scale-chain-gaussian) |  |
| 11:12 | [`experiments/svg-layernorm-scale-chain-sharded`](experiments/svg-layernorm-scale-chain-sharded) |  |
| 11:14 | [`experiments/svg-multitoken-attention-rgb-centered-gaussian`](experiments/svg-multitoken-attention-rgb-centered-gaussian) |  |
| 11:15 | [`experiments/svg-live-layernorm-hier16`](experiments/svg-live-layernorm-hier16) |  |
| 11:15 | [`experiments/svg-live-layernorm-hier4`](experiments/svg-live-layernorm-hier4) |  |
| 11:17 | [`experiments/svg-multitoken-attention-rgb-centered-hier4`](experiments/svg-multitoken-attention-rgb-centered-hier4) |  |
| 11:18 | [`experiments/svg-multitoken-attention-rgb-centered-hier4-scaled`](experiments/svg-multitoken-attention-rgb-centered-hier4-scaled) |  |
| 11:19 | [`experiments/svg-live-block1-input-hier4`](experiments/svg-live-block1-input-hier4) |  |
| 11:20 | [`experiments/svg-live-block1-input-hier4-all`](experiments/svg-live-block1-input-hier4-all) |  |
| 11:20 | [`experiments/svg-live-complete-block-hier4`](experiments/svg-live-complete-block-hier4) |  |
| 11:20 | [`experiments/svg-live-two-block-attention-hier4`](experiments/svg-live-two-block-attention-hier4) |  |
| 11:20 | [`experiments/svg-live-two-block-layernorm-hier4`](experiments/svg-live-two-block-layernorm-hier4) |  |
| 11:20 | [`experiments/svg-live-two-complete-blocks-hier4`](experiments/svg-live-two-complete-blocks-hier4) |  |
| 11:21 | [`experiments/svg-reduction-alternatives`](experiments/svg-reduction-alternatives) | SVG reduction alternatives |
| 11:22 | [`experiments/svg-live-two-complete-blocks`](experiments/svg-live-two-complete-blocks) | Two complete live GPT-2 blocks |
| 11:26 | [`experiments/multiface-metric-bank-lean`](experiments/multiface-metric-bank-lean) |  |
| 11:26 | [`experiments/multiface-metric-bank-lean-woff`](experiments/multiface-metric-bank-lean-woff) |  |
| 11:28 | [`experiments/multiface-metric-bank-shifted-64`](experiments/multiface-metric-bank-shifted-64) |  |
| 11:31 | [`experiments/multiface-metric-bank-256x768-woff`](experiments/multiface-metric-bank-256x768-woff) |  |
| 11:33 | [`experiments/multiface-metric-bank-sharded-smoke`](experiments/multiface-metric-bank-sharded-smoke) |  |
| 11:38 | [`experiments/multiface-metric-bank-768x768-reused`](experiments/multiface-metric-bank-768x768-reused) |  |
| 11:40 | [`experiments/multiface-metric-bank-768x768-s128-reused`](experiments/multiface-metric-bank-768x768-s128-reused) |  |
| 11:42 | [`experiments/gsub-metric-bank-32x64`](experiments/gsub-metric-bank-32x64) |  |
| 11:44 | [`experiments/multiface-metric-bank`](experiments/multiface-metric-bank) | Multi-face metric bank |
| 11:51 | [`experiments/font-extra-numeric-probe`](experiments/font-extra-numeric-probe) | Additional font-relative numeric outputs |
| 11:51 | [`experiments/font-line-components-probe`](experiments/font-line-components-probe) | Independent line-metric components |
| 11:51 | [`experiments/font-ttc-shared-bank`](experiments/font-ttc-shared-bank) | Shared TTC metric bank |
| 11:51 | [`experiments/structured-css-matrices`](experiments/structured-css-matrices) | Structured post-training GPT-2 matrix representations |
| 11:52 | [`experiments/svg-residual-rotation`](experiments/svg-residual-rotation) |  |
| 11:57 | [`experiments/anchor-axis-gather-probe.html`](experiments/anchor-axis-gather-probe.html) |  |
| 12:05 | [`experiments/grid-subgrid-vector`](experiments/grid-subgrid-vector) | Grid/subgrid vector transport |
| 12:40 | [`experiments/packed-activation-precision`](experiments/packed-activation-precision) | Packed activation precision |
| 13:16 | [`experiments/additive-font-variation-vector`](experiments/additive-font-variation-vector) | Additive font-variation vector probe |
| 13:16 | [`experiments/anchor-packed-hvar`](experiments/anchor-packed-hvar) | Real-HVAR anchor packing |
| 13:16 | [`experiments/anchor-packed-vector`](experiments/anchor-packed-vector) | Anchor-packed vector transport |
| 14:50 | [`experiments/css-compositor-vector`](experiments/css-compositor-vector) |  |
| 14:52 | [`experiments/geometry-raster-vector`](experiments/geometry-raster-vector) |  |
| 15:13 | [`experiments/gvar-vector-glyph`](experiments/gvar-vector-glyph) |  |
| 15:20 | [`experiments/gvar-vector-fc`](experiments/gvar-vector-fc) | One-glyph vector matvec |
| 15:20 | [`experiments/hvar-raster-fc`](experiments/hvar-raster-fc) | HVAR geometry to SVG raster transport |
| 15:29 | [`experiments/truetype-bytecode`](experiments/truetype-bytecode) | TrueType bytecode as an internal numeric backend |
| 15:35 | [`experiments/anchor-axis-vector-gather`](experiments/anchor-axis-vector-gather) | Direct anchor geometry to font axes |
| 15:40 | [`experiments/additive-font-variation-matvec`](experiments/additive-font-variation-matvec) | Additive font-variation matvec |
| 15:48 | [`experiments/anchor-swar-matvec`](experiments/anchor-swar-matvec) | Two-lane SWAR anchor matrix multiplication |
| 15:57 | [`experiments/hvar-swar-mlp-slice`](experiments/hvar-swar-mlp-slice) | Real GPT-2 HVAR to SWAR MLP slice |
| 16:24 | [`experiments/anchor-swar-attention`](experiments/anchor-swar-attention) | Dynamic attention with CSS SWAR |
| 16:35 | [`experiments/direct-css-block`](experiments/direct-css-block) |  |
| 16:40 | [`experiments/orthogonal-container-2d-probe-results.md`](experiments/orthogonal-container-2d-probe-results.md) | Orthogonal container-unit probe |
| 18:29 | [`experiments/composed-qk-probe`](experiments/composed-qk-probe) |  |
| 18:35 | [`experiments/lowrank-attention`](experiments/lowrank-attention) |  |
| 19:13 | [`experiments/hvar-raster-qkv-attention`](experiments/hvar-raster-qkv-attention) | HVAR-to-SVG QKV raster attention |
| 20:24 | [`experiments/feature-selected-metric-pair`](experiments/feature-selected-metric-pair) |  |
| 20:38 | [`experiments/feature-selected-qk`](experiments/feature-selected-qk) |  |
| 21:07 | [`experiments/query-binned-attention`](experiments/query-binned-attention) |  |
| 21:21 | [`experiments/feature-selected-qk-all-heads-range-0p6`](experiments/feature-selected-qk-all-heads-range-0p6) |  |
| 21:36 | [`experiments/feature-selected-qk-all-heads`](experiments/feature-selected-qk-all-heads) | Feature-selected QK and mixed-V results |
| 22:18 | [`experiments/projected-kv-qk`](experiments/projected-kv-qk) | Projected KV cache attention |
| 22:39 | [`experiments/bilinear-hvar-dot`](experiments/bilinear-hvar-dot) |  |
| 22:41 | [`experiments/bilinear-projected-kv-qk`](experiments/bilinear-projected-kv-qk) |  |
| 22:45 | [`experiments/bilinear-sum-projected-kv-qk`](experiments/bilinear-sum-projected-kv-qk) |  |
| 23:00 | [`experiments/bilinear-hvar-attention`](experiments/bilinear-hvar-attention) | Bilinear HVAR attention scores |
| 23:06 | [`experiments/multitoken-block0-ranges`](experiments/multitoken-block0-ranges) | Multi-token block-0 carrier calibration |
| 23:17 | [`experiments/counter-vector-reduction-probe.html`](experiments/counter-vector-reduction-probe.html) |  |

## 2026-09-13

| Time | Entry | Notes title |
|---|---|---|
| 00:52 | [`experiments/grid-subgrid-gpt2-fc`](experiments/grid-subgrid-gpt2-fc) | Real GPT-2 FC on Grid/Subgrid |
| 00:52 | [`experiments/svg-signed-bitplane-dot`](experiments/svg-signed-bitplane-dot) | Signed activation bit-plane SVG dot product |
| 01:05 | [`experiments/grid-hierarchical-argmax`](experiments/grid-hierarchical-argmax) |  |
| 01:10 | [`experiments/grid-hierarchical-output-head`](experiments/grid-hierarchical-output-head) |  |
| 01:33 | [`experiments/grid-argmax-group-sweep`](experiments/grid-argmax-group-sweep) | Hierarchical Grid argmax group-size sweep |
| 01:37 | [`experiments/hvar-token-embedding-lookup`](experiments/hvar-token-embedding-lookup) |  |
| 02:00 | [`experiments/sparse-additive-font-settings-probe.html`](experiments/sparse-additive-font-settings-probe.html) |  |
| 02:08 | [`experiments/hvar-grid-output-head`](experiments/hvar-grid-output-head) |  |
| 02:09 | [`experiments/grid-argmax`](experiments/grid-argmax) | CSS Grid argmax |
| 02:09 | [`experiments/hvar-embedding-qkv-chain`](experiments/hvar-embedding-qkv-chain) | HVAR embedding-to-QKV vector chain |
| 02:10 | [`experiments/packed-hvar-transport-scaling`](experiments/packed-hvar-transport-scaling) | Packed HVAR transport scaling |
| 02:50 | [`experiments/packed-timeline-precision`](experiments/packed-timeline-precision) | Packed timeline transport |
| 03:46 | [`experiments/gpt2-hvar-grid-output-head`](experiments/gpt2-hvar-grid-output-head) | GPT-2 HVAR + Grid output-head scaling |
| 05:08 | [`experiments/css-if-multibranch-probe.html`](experiments/css-if-multibranch-probe.html) |  |
| 05:15 | [`experiments/gpt2-hvar-grid-output-head-cascade`](experiments/gpt2-hvar-grid-output-head-cascade) |  |
| 05:15 | [`experiments/gpt2-hvar-grid-output-head-cascade-compact`](experiments/gpt2-hvar-grid-output-head-cascade-compact) |  |
| 05:15 | [`experiments/gpt2-hvar-grid-output-head-global11-inline-tie`](experiments/gpt2-hvar-grid-output-head-global11-inline-tie) |  |
| 05:15 | [`experiments/gpt2-hvar-grid-output-head-global16-twoplane`](experiments/gpt2-hvar-grid-output-head-global16-twoplane) |  |
| 05:16 | [`experiments/gpt2-hvar-grid-output-head-cascade-subfonts`](experiments/gpt2-hvar-grid-output-head-cascade-subfonts) |  |
| 05:18 | [`experiments/gpt2-hvar-grid-output-head-global16-pair-probe`](experiments/gpt2-hvar-grid-output-head-global16-pair-probe) |  |
| 05:26 | [`experiments/gpt2-hvar-grid-output-head-cascade-dither8`](experiments/gpt2-hvar-grid-output-head-cascade-dither8) |  |
| 05:33 | [`experiments/gpt2-hvar-grid-output-head-cascade-dither8-sparse5`](experiments/gpt2-hvar-grid-output-head-cascade-dither8-sparse5) |  |
| 05:36 | [`experiments/gpt2-hvar-grid-output-head-cascade-near-selector`](experiments/gpt2-hvar-grid-output-head-cascade-near-selector) |  |
| 05:40 | [`experiments/gpt2-hvar-coordinate-dither`](experiments/gpt2-hvar-coordinate-dither) |  |
| 05:40 | [`experiments/gpt2-hvar-grid-output-head-cascade-near-dither8`](experiments/gpt2-hvar-grid-output-head-cascade-near-dither8) |  |
| 05:44 | [`experiments/gpt2-hvar-grid-output-head-cascade-near-dither7`](experiments/gpt2-hvar-grid-output-head-cascade-near-dither7) |  |
| 06:07 | [`experiments/gpt2-hvar-grid-output-head-cascade-near-dither7-staged`](experiments/gpt2-hvar-grid-output-head-cascade-near-dither7-staged) |  |
| 06:11 | [`experiments/gpt2-mips-pruning`](experiments/gpt2-mips-pruning) |  |
| 06:23 | [`experiments/gpt2-hvar-grid-output-head-global11`](experiments/gpt2-hvar-grid-output-head-global11) |  |
| 06:27 | [`experiments/gpt2-hvar-grid-output-head-cascade-near-dither7-shard256`](experiments/gpt2-hvar-grid-output-head-cascade-near-dither7-shard256) |  |
| 06:27 | [`experiments/gpt2-hvar-grid-output-head-global11-shard256`](experiments/gpt2-hvar-grid-output-head-global11-shard256) |  |
| 06:27 | [`experiments/gpt2-hvar-grid-output-head-global11-shard256-inline-tie`](experiments/gpt2-hvar-grid-output-head-global11-shard256-inline-tie) |  |
| 06:28 | [`experiments/gpt2-hvar-grid-output-head-cascade-near-dither7-shard256-staged`](experiments/gpt2-hvar-grid-output-head-cascade-near-dither7-shard256-staged) |  |
| 06:34 | [`experiments/avar2-hvar-composition`](experiments/avar2-hvar-composition) |  |
| 06:35 | [`experiments/avar2-hvar-mlp`](experiments/avar2-hvar-mlp) |  |
| 06:38 | [`experiments/avar2-hvar-mlp-scaling`](experiments/avar2-hvar-mlp-scaling) | avar2 + HVAR internal MLP composition |
| 06:41 | [`experiments/avar2-hvar-real-gpt2-tile`](experiments/avar2-hvar-real-gpt2-tile) |  |
| 06:46 | [`experiments/anchor-registered-axis-gather-probe.html`](experiments/anchor-registered-axis-gather-probe.html) |  |
| 06:48 | [`experiments/hvar-parallel-mlp-group`](experiments/hvar-parallel-mlp-group) |  |
| 07:17 | [`experiments/anchor-registered-axis-gather-probe.html`](experiments/anchor-registered-axis-gather-probe.html) | Registered anchor-size to font-axis gather |
| 07:17 | [`experiments/avar2-gelu-linear-hvar-group`](experiments/avar2-gelu-linear-hvar-group) |  |
| 07:17 | [`experiments/gpt2-fc-lowrank`](experiments/gpt2-fc-lowrank) | GPT-2 FC axis-ceiling alternatives |
| 07:17 | [`experiments/hvar-parallel-full-mlp`](experiments/hvar-parallel-full-mlp) |  |
| 07:40 | [`experiments/avar2-gelu-linear-hvar-full-mlp-g16`](experiments/avar2-gelu-linear-hvar-full-mlp-g16) |  |
| 09:42 | [`experiments/avar2-gelu-linear-hvar-full-mlp`](experiments/avar2-gelu-linear-hvar-full-mlp) | Live-input MLP transport results |
| 09:43 | [`experiments/hvar-five-metric-fullwidth`](experiments/hvar-five-metric-fullwidth) | Full-width five-metric HVAR/MVAR transport |
| 09:54 | [`experiments/hvar-five-metric-scale`](experiments/hvar-five-metric-scale) | Five-metric dense-matrix scaling test |
| 10:02 | [`experiments/cross-shard-font-composition`](experiments/cross-shard-font-composition) | Cross-shard variable-font composition |
| 10:03 | [`experiments/font-metric-chain-probe`](experiments/font-metric-chain-probe) | Direct font-metric to font-axis chaining |
| 10:10 | [`experiments/transport-free-timing-model`](experiments/transport-free-timing-model) | Transport-free timing model |
| 10:28 | [`experiments/hvar-packed-output-rows`](experiments/hvar-packed-output-rows) | Packing multiple HVAR output rows into one advance |
| 10:30 | [`experiments/single-glyph-vector-raster`](experiments/single-glyph-vector-raster) | Single-glyph vector raster |
| 10:35 | [`experiments/ideal-vector-carrier`](experiments/ideal-vector-carrier) | Ideal vector carrier: deconfounded result |
| 10:55 | [`experiments/css-gelu-projection`](experiments/css-gelu-projection) | CSS GELU before pure HVAR projection |
| 11:15 | [`experiments/exact-gelu-vector-oracle`](experiments/exact-gelu-vector-oracle) | Exact-GELU vector-boundary oracle |
| 11:16 | [`experiments/anchor-function-number-probe-results.json`](experiments/anchor-function-number-probe-results.json) |  |
| 11:16 | [`experiments/hvar-vector-oracle`](experiments/hvar-vector-oracle) | HVAR vector-primitive upper bound |
| 11:51 | [`experiments/avar2-gelu-linear-hvar-full-mlp-g13`](experiments/avar2-gelu-linear-hvar-full-mlp-g13) | Exact ancestor CSS GELU in the two-block HVAR path |
| 12:02 | [`experiments/hvar-raster-direct-projection`](experiments/hvar-raster-direct-projection) | Raster-native projection row scaling |
| 12:02 | [`experiments/svg-asymmetric-ranges`](experiments/svg-asymmetric-ranges) | Asymmetric SVG activation ranges |
| 12:02 | [`experiments/svg-quantization-ensemble`](experiments/svg-quantization-ensemble) | SVG quantization ensemble |
| 12:08 | [`experiments/svg-output-head-calibration`](experiments/svg-output-head-calibration) | SVG output-head calibration |
| 12:08 | [`experiments/svg-rgb-dither-ensemble`](experiments/svg-rgb-dither-ensemble) | RGB phase-dithered SVG execution |
| 12:13 | [`experiments/svg-w8a8-generation`](experiments/svg-w8a8-generation) | Full GPT-2 W8A8 generation screen |
| 12:24 | [`experiments/svg-avif-precision`](experiments/svg-avif-precision) |  |
| 12:31 | [`experiments/svg-hdr-carrier-transport`](experiments/svg-hdr-carrier-transport) |  |
| 12:32 | [`experiments/svg-hdr-compute-chain`](experiments/svg-hdr-compute-chain) |  |
| 12:38 | [`experiments/svg-hdr-codebook`](experiments/svg-hdr-codebook) | 12-bit PQ codebook calibration |
| 12:39 | [`experiments/svg-hdr-matvec`](experiments/svg-hdr-matvec) | HDR SVG precision and real matvec |
| 12:58 | [`experiments/opsz-container-handoff`](experiments/opsz-container-handoff) | Container width to automatic font-axis handoff |
| 13:11 | [`experiments/counter-matrix`](experiments/counter-matrix) | Timeline-driven CSS counter matrix |
| 13:55 | [`experiments/smil-stage-scheduler`](experiments/smil-stage-scheduler) | SVG SMIL as a CSS-only stage scheduler |
| 14:08 | [`experiments/gpt2-hvar-grid-output-head-containment`](experiments/gpt2-hvar-grid-output-head-containment) | GPT-2 output-head group containment |
| 14:08 | [`experiments/gpt2-hvar-grid-output-head-multiline`](experiments/gpt2-hvar-grid-output-head-multiline) | Multiline intrinsic-width output-head probe |
| 14:21 | [`experiments/gpt2-ivf-group-router`](experiments/gpt2-ivf-group-router) | GPT-2 IVF vocabulary router |
| 14:21 | [`experiments/gpt2-nonlinear-group-router`](experiments/gpt2-nonlinear-group-router) | Nonlinear GPT-2 vocabulary-group router |
| 14:21 | [`experiments/gpt2-supervised-group-router`](experiments/gpt2-supervised-group-router) | Supervised GPT-2 vocabulary-group router |
| 14:47 | [`experiments/gpt2-hvar-grid-output-head-certified-upper-int10`](experiments/gpt2-hvar-grid-output-head-certified-upper-int10) | Certified row-wise int10 upper head |
| 14:47 | [`experiments/gpt2-hvar-grid-output-head-certified-upper-int10-one-step`](experiments/gpt2-hvar-grid-output-head-certified-upper-int10-one-step) | Certified int10 plus one exact group |
| 14:47 | [`experiments/gpt2-hvar-grid-output-head-certified-upper-int10-remaining-upper`](experiments/gpt2-hvar-grid-output-head-certified-upper-int10-remaining-upper) | Masked remaining-upper-group readback |
| 14:47 | [`experiments/gpt2-hvar-grid-output-head-certified-upper-int10-two-step`](experiments/gpt2-hvar-grid-output-head-certified-upper-int10-two-step) | Two-step certified-group exact probe |
| 15:00 | [`experiments/gpt2-hvar-grid-output-head-certified-upper-rowwise11-range266`](experiments/gpt2-hvar-grid-output-head-certified-upper-rowwise11-range266) | Certified row-wise int11 upper head, ±266 range |
| 15:00 | [`experiments/gpt2-hvar-grid-output-head-rowwise11-shard80-range266`](experiments/gpt2-hvar-grid-output-head-rowwise11-shard80-range266) | Row-wise int11, ten 80-axis shards, ±266 range |
| 15:25 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-parallel-pair`](experiments/gpt2-hvar-grid-output-head-certified-int10-parallel-pair) | Parallel two-group exact refinement probe |
| 15:25 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6) | Six-stage certified int10 cascade |
| 15:29 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-linear-mask`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-linear-mask) |  |
| 15:32 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-parallel-pair-twoplane`](experiments/gpt2-hvar-grid-output-head-certified-int10-parallel-pair-twoplane) | Parallel pair two-plane merge probe |
| 15:34 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled61-gated`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled61-gated) | Gated 61-stage structural scaling probe |
| 15:34 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled61-gated-linear-mask`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled61-gated-linear-mask) | Incremental-mask 61-stage cascade |
| 15:38 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled16-gated`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled16-gated) | Gated 16-stage coverage/latency probe |
| 15:47 | [`experiments/gpt2-browser-certification-budget`](experiments/gpt2-browser-certification-budget) | Browser certification budget |
| 15:47 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated) | Gated six-stage certified int10 cascade |
| 15:47 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled61-gated-packed-mask`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled61-gated-packed-mask) | Packed-mask 61-stage cascade |
| 16:01 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled16-gated-force16-expanded`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled16-gated-force16-expanded) | Forced 16-stage expanded-history control |
| 16:01 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled16-gated-packed-mask-force16`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled16-gated-packed-mask-force16) | Forced 16-stage packed-mask traversal |
| 16:01 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-packed-mask`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-packed-mask) | Packed-mask six-stage cascade |
| 16:26 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-parallel-tail`](experiments/gpt2-hvar-grid-output-head-certified-int10-parallel-tail) | Six-stage certified int10 prefix plus parallel uncertainty tail |
| 16:46 | [`experiments/position-try-upper-router`](experiments/position-try-upper-router) | Native position-try upper router |
| 16:59 | [`experiments/gpt2-certified-tail-strategies`](experiments/gpt2-certified-tail-strategies) | Certified compact-tail strategies |
| 17:28 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-batched-tail`](experiments/gpt2-hvar-grid-output-head-certified-int10-batched-tail) | Certified int10 batched-tail probe |
| 17:53 | [`experiments/sibling-index-upper-router`](experiments/sibling-index-upper-router) | Sibling-index/local-anchor upper router |
| 18:06 | [`experiments/cmap14-indexed-fine-scorer`](experiments/cmap14-indexed-fine-scorer) | CMAP format-14 indexed fine-scorer probe |
| 18:34 | [`experiments/gsub-constant-base-fine-scorer`](experiments/gsub-constant-base-fine-scorer) | Constant-base GSUB fine-scorer probe |
| 18:38 | [`experiments/gsub-lattice-scale-fine-scorer`](experiments/gsub-lattice-scale-fine-scorer) | GSUB lattice-scale fine-scorer probe |
| 19:12 | [`experiments/gsub-merged-base-fine-scorer`](experiments/gsub-merged-base-fine-scorer) | GSUB merged-base fine-scorer probe |
| 19:28 | [`experiments/gsub-split-complement-fine-scorer`](experiments/gsub-split-complement-fine-scorer) | GSUB split-complement fine-scorer probe |
| 19:29 | [`experiments/gsub-indexed-fine-scorer`](experiments/gsub-indexed-fine-scorer) | Real-dummy AlternateSet targeted result |
| 19:39 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hybrid`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hybrid) | Six-stage GSUB hybrid output-head probe |
| 19:43 | [`experiments/gpt2-best-first-group-hotspots`](experiments/gpt2-best-first-group-hotspots) | Best-first exact-group visitation hotspots |
| 19:47 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hot2`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-gsub-hot2) | Hot-two six-stage GSUB output-head probe |
| 20:12 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-hot2-precomputed`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled6-gated-hot2-precomputed) | Hot-2 root-precomputed exact six-stage result |
| 20:58 | [`experiments/gpt2-mixed-precision-hot2-upper-subset`](experiments/gpt2-mixed-precision-hot2-upper-subset) | Mixed-precision hot-2 upper: static exact-font subset |
| 20:59 | [`experiments/gsub-certified-hybrid`](experiments/gsub-certified-hybrid) | GSUB-certified hybrid topology ablation |
| 21:27 | [`experiments/gpt2-gsub-inplace-hot2-upper`](experiments/gpt2-gsub-inplace-hot2-upper) | In-place GSUB hot-2 upper/fine feasibility |
| 21:28 | [`experiments/gpt2-mixed-precision-hotk-sweep`](experiments/gpt2-mixed-precision-hotk-sweep) | Mixed-precision hot-K sweep |
| 22:15 | [`experiments/gpt2-mixed-precision-group-size-sweep`](experiments/gpt2-mixed-precision-group-size-sweep) | Mixed exact-upper group-size browser screen |
| 22:24 | [`experiments/hvar-resulting-advance-range`](experiments/hvar-resulting-advance-range) | HVAR resulting-advance range probe |
| 22:24 | [`experiments/hvar-virtual-base`](experiments/hvar-virtual-base) | HVAR virtual-base probe |
| 22:37 | [`experiments/gpt2-aligned-residual-group`](experiments/gpt2-aligned-residual-group) | Aligned int10 + exact residual group probe |
| 22:40 | [`experiments/gpt2-compensated-oneplane-hot2`](experiments/gpt2-compensated-oneplane-hot2) | Screen-compensated one-plane hot-2 rows |
| 22:40 | [`experiments/gpt2-virtual-base-oneplane-hot2`](experiments/gpt2-virtual-base-oneplane-hot2) | Virtual-base one-plane hot-2 exact rows |
| 22:53 | [`experiments/gpt2-token-uncertainty-gate`](experiments/gpt2-token-uncertainty-gate) | Fixed-group token uncertainty gate |
| 23:02 | [`experiments/gpt2-twoplane-256axis-hot2`](experiments/gpt2-twoplane-256axis-hot2) | Three-pair 256-axis two-plane hot-2 rows |
| 23:06 | [`experiments/gpt2-token-uncertainty-block-sweep`](experiments/gpt2-token-uncertainty-block-sweep) | Token uncertainty block-size sweep |
| 23:29 | [`experiments/gpt2-mixed-hot2-block-gate-b4`](experiments/gpt2-mixed-hot2-block-gate-b4) | Mixed hot-2 block-gate A/B |
| 23:29 | [`experiments/gpt2-mixed-hot2-block-gate-b8`](experiments/gpt2-mixed-hot2-block-gate-b8) | Mixed hot-2 block-gate A/B |
| 23:29 | [`experiments/gpt2-token-uncertainty-block-gate`](experiments/gpt2-token-uncertainty-block-gate) | Token uncertainty block-gate browser probe |

## 2026-09-14

| Time | Entry | Notes title |
|---|---|---|
| 00:21 | [`experiments/gpt2-mixed-hot2-reused-upper-block-gate-b8`](experiments/gpt2-mixed-hot2-reused-upper-block-gate-b8) | Mixed hot-2 block-gate A/B |
| 00:50 | [`experiments/gpt2-mixed-hot2-coactivation-block-gate-b4`](experiments/gpt2-mixed-hot2-coactivation-block-gate-b4) | Mixed hot-2 block-gate A/B |
| 00:50 | [`experiments/gpt2-mixed-hot2-reused-upper-block-gate-b4`](experiments/gpt2-mixed-hot2-reused-upper-block-gate-b4) | Mixed hot-2 block-gate A/B |
| 00:55 | [`experiments/gpt2-mixed-hot2-direct-outer-max-stripped`](experiments/gpt2-mixed-hot2-direct-outer-max-stripped) | Mixed hot-2 block-gate A/B |
| 01:42 | [`experiments/gpt2-mixed-hot2-direct-outer-max`](experiments/gpt2-mixed-hot2-direct-outer-max) | Mixed hot-2 block-gate A/B |
| 01:42 | [`experiments/gpt2-mixed-hot2-packed-group-argmax`](experiments/gpt2-mixed-hot2-packed-group-argmax) | Mixed hot-2 block-gate A/B |
| 01:43 | [`experiments/gpt2-mixed-hot2-direct-outer-max-pruned`](experiments/gpt2-mixed-hot2-direct-outer-max-pruned) | Mixed hot-2 block-gate A/B |
| 01:43 | [`experiments/gpt2-mixed-hot2-packed-direct-argmax`](experiments/gpt2-mixed-hot2-packed-direct-argmax) | Mixed hot-2 block-gate A/B |
| 02:07 | [`experiments/gpt2-mixed-hot2-hierarchical-outer-max16-contained`](experiments/gpt2-mixed-hot2-hierarchical-outer-max16-contained) | Mixed hot-2 block-gate A/B |
| 02:07 | [`experiments/gpt2-mixed-hot2-hierarchical-outer-max32`](experiments/gpt2-mixed-hot2-hierarchical-outer-max32) | Mixed hot-2 block-gate A/B |
| 02:07 | [`experiments/gpt2-mixed-hot2-hierarchical-outer-max64`](experiments/gpt2-mixed-hot2-hierarchical-outer-max64) | Mixed hot-2 block-gate A/B |
| 02:07 | [`experiments/gpt2-mixed-hot2-hierarchical-outer-max8`](experiments/gpt2-mixed-hot2-hierarchical-outer-max8) | Mixed hot-2 block-gate A/B |
| 02:08 | [`experiments/gpt2-mixed-hot2-chunk-slot-decoder`](experiments/gpt2-mixed-hot2-chunk-slot-decoder) | Mixed hot-2 block-gate A/B |
| 02:08 | [`experiments/gpt2-mixed-hot2-nested-functional-max16`](experiments/gpt2-mixed-hot2-nested-functional-max16) | Mixed hot-2 block-gate A/B |
| 02:08 | [`experiments/gpt2-mixed-hot2-packed4-hierarchical-argmax`](experiments/gpt2-mixed-hot2-packed4-hierarchical-argmax) | Mixed hot-2 block-gate A/B |
| 02:28 | [`experiments/gpt2-mixed-hot2-blockflow-fast-text`](experiments/gpt2-mixed-hot2-blockflow-fast-text) |  |
| 02:28 | [`experiments/gpt2-mixed-hot2-blockflow-hidden`](experiments/gpt2-mixed-hot2-blockflow-hidden) |  |
| 02:31 | [`experiments/gpt2-mixed-hot2-hierarchical-outer-max16`](experiments/gpt2-mixed-hot2-hierarchical-outer-max16) | Mixed hot-2 block-gate A/B |
| 02:37 | [`experiments/gpt2-mixed-hot2-all-blockflow`](experiments/gpt2-mixed-hot2-all-blockflow) | Mixed hot-2 block-gate A/B |
| 02:37 | [`experiments/gpt2-mixed-hot2-blockflow-fast-text-hidden`](experiments/gpt2-mixed-hot2-blockflow-fast-text-hidden) | Mixed hot-2 block-gate A/B |
| 02:37 | [`experiments/gpt2-mixed-hot2-blockflow-scrollless`](experiments/gpt2-mixed-hot2-blockflow-scrollless) | Mixed hot-2 block-gate A/B |
| 02:45 | [`experiments/gpt2-hvar-grid-output-head-certified-upper-int10-one-step-shard256`](experiments/gpt2-hvar-grid-output-head-certified-upper-int10-one-step-shard256) |  |
| 02:45 | [`experiments/gpt2-hvar-grid-output-head-certified-upper-int10-shard256`](experiments/gpt2-hvar-grid-output-head-certified-upper-int10-shard256) |  |
| 02:45 | [`experiments/gpt2-mixed-precision-hot2-upper-shard256`](experiments/gpt2-mixed-precision-hot2-upper-shard256) | Mixed-precision hot-2 upper-head feasibility |
| 02:56 | [`experiments/gpt2-hvar-grid-output-head-int10-shard256`](experiments/gpt2-hvar-grid-output-head-int10-shard256) | Row-wise int10 output head with 256-axis shards |
| 02:56 | [`experiments/gpt2-hvar-grid-output-head-shard-sweep`](experiments/gpt2-hvar-grid-output-head-shard-sweep) | GPT-2 output-head HVAR shard width |
| 02:56 | [`experiments/gpt2-mixed-hot2-blockflow-group-max`](experiments/gpt2-mixed-hot2-blockflow-group-max) | Mixed hot-2 block-gate A/B |
| 02:56 | [`experiments/gpt2-mixed-precision-hot2-upper`](experiments/gpt2-mixed-precision-hot2-upper) | Mixed-precision hot-2 upper-head feasibility |
| 02:56 | [`experiments/gpt2-quantized-head-certification`](experiments/gpt2-quantized-head-certification) | Certified quantized GPT-2 output head |
| 03:01 | [`experiments/gpt2-hvar-grid-output-head-certified-upper-int10-one-step-shard192`](experiments/gpt2-hvar-grid-output-head-certified-upper-int10-one-step-shard192) |  |
| 03:01 | [`experiments/gpt2-hvar-grid-output-head-certified-upper-int10-shard192`](experiments/gpt2-hvar-grid-output-head-certified-upper-int10-shard192) |  |
| 03:01 | [`experiments/gpt2-hvar-grid-output-head-int10-shard192`](experiments/gpt2-hvar-grid-output-head-int10-shard192) |  |
| 03:01 | [`experiments/gpt2-mixed-precision-hot2-upper-shard192`](experiments/gpt2-mixed-precision-hot2-upper-shard192) | Mixed-precision hot-2 upper-head feasibility |
| 03:05 | [`experiments/gpt2-mixed-hot2-blockflow-group-max-shard192`](experiments/gpt2-mixed-hot2-blockflow-group-max-shard192) | Mixed hot-2 block-gate A/B |
| 03:05 | [`experiments/gpt2-mixed-hot2-blockflow-group-max-shard256`](experiments/gpt2-mixed-hot2-blockflow-group-max-shard256) | Mixed hot-2 block-gate A/B |
| 03:15 | [`experiments/gpt2-certified-vocabulary-ball-tree`](experiments/gpt2-certified-vocabulary-ball-tree) | Certified query-aware vocabulary ball tree |
| 03:16 | [`experiments/gpt2-lowrank-coarse-head`](experiments/gpt2-lowrank-coarse-head) | GPT-2 coarse-search pruning |
| 03:24 | [`experiments/css-native-grouped-mlp`](experiments/css-native-grouped-mlp) | CSS-native grouped GPT-2 MLP feasibility |
| 03:24 | [`experiments/css-native-grouped-mlp-browser`](experiments/css-native-grouped-mlp-browser) | CSS-native grouped MLP browser probe |
| 03:45 | [`experiments/gsub-graph-selector-probe`](experiments/gsub-graph-selector-probe) | GSUB graph selector probe results |
| 03:53 | [`experiments/gpt2-hnsw-output-head`](experiments/gpt2-hnsw-output-head) | GPT-2 HNSW-like output-head feasibility |
| 04:01 | [`experiments/gpt2-mips-lsh`](experiments/gpt2-mips-lsh) | GPT-2 asymmetric MIPS LSH candidate screen |
| 04:03 | [`experiments/gpt2-overlapping-ivf`](experiments/gpt2-overlapping-ivf) | GPT-2 overlapping IVF output-head screen |
| 04:16 | [`experiments/gpt2-hnsw-batched-frontier`](experiments/gpt2-hnsw-batched-frontier) | CSS-unrollable batched frontier on real HNSW layer 0 |
| 04:49 | [`experiments/gpt2-mincontent-word-argmax`](experiments/gpt2-mincontent-word-argmax) | GPT-2 min-content word argmax |
| 04:53 | [`experiments/svg-internal-precision`](experiments/svg-internal-precision) | SVG internal precision by primitive |
| 04:59 | [`experiments/svg-cross-browser-precision`](experiments/svg-cross-browser-precision) | Cross-browser vector-backend gate |
| 05:13 | [`experiments/inline-attention-reducer`](experiments/inline-attention-reducer) | Native inline attention reducer |
| 05:20 | [`experiments/gpt2-blockwise-cauchy-head`](experiments/gpt2-blockwise-cauchy-head) | GPT-2 blockwise-Cauchy output-head experiment |
| 05:38 | [`experiments/gpt2-groupwise-cauchy-head`](experiments/gpt2-groupwise-cauchy-head) | GPT-2 group-level blockwise-Cauchy output-head experiment |
| 05:48 | [`experiments/gpt2-groupwise-cauchy-cascade`](experiments/gpt2-groupwise-cauchy-cascade) | Groupwise 96-block Cauchy integrated cascade gate |
| 06:00 | [`experiments/chromium-f16-svg-filter`](experiments/chromium-f16-svg-filter) | Chromium F16 SVG-filter moonshot audit |
| 06:06 | [`experiments/gpt2-groupwise-cauchy-blockflow-gate`](experiments/gpt2-groupwise-cauchy-blockflow-gate) | GPT-2 16-group Cauchy block-flow composition gate |
| 06:33 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled22-gated`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled22-gated) |  |
| 06:34 | [`experiments/gpt2-mixed-hot2-blockflow-group-max-shard256-unrolled22`](experiments/gpt2-mixed-hot2-blockflow-group-max-shard256-unrolled22) |  |
| 06:34 | [`experiments/gpt2-mixed-precision-hot2-upper-shard256-unrolled22`](experiments/gpt2-mixed-precision-hot2-upper-shard256-unrolled22) | Mixed-precision hot-2 upper-head feasibility |
| 07:05 | [`experiments/gpt2-groupwise-cauchy-blockflow-cascade-unrolled23`](experiments/gpt2-groupwise-cauchy-blockflow-cascade-unrolled23) |  |
| 07:05 | [`experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled23-gated`](experiments/gpt2-hvar-grid-output-head-certified-int10-unrolled23-gated) |  |
| 07:05 | [`experiments/gpt2-mixed-hot2-blockflow-group-max-shard256-unrolled23`](experiments/gpt2-mixed-hot2-blockflow-group-max-shard256-unrolled23) |  |
| 07:05 | [`experiments/gpt2-mixed-precision-hot2-upper-shard256-unrolled23`](experiments/gpt2-mixed-precision-hot2-upper-shard256-unrolled23) | Mixed-precision hot-2 upper-head feasibility |
| 07:27 | [`experiments/gpt2-groupwise-cauchy-blockflow-cascade-unrolled22`](experiments/gpt2-groupwise-cauchy-blockflow-cascade-unrolled22) | 22-stage groupwise Cauchy block-flow cascade |
| 07:28 | [`experiments/gpt2-groupwise-cauchy-blockflow-production-range`](experiments/gpt2-groupwise-cauchy-blockflow-production-range) | Production-range homogeneous groupwise cascade |
| 07:32 | [`experiments/gpt2-groupwise-cauchy-blockflow-production-range-prefix6`](experiments/gpt2-groupwise-cauchy-blockflow-production-range-prefix6) |  |
| 07:33 | [`experiments/gpt2-groupwise-cauchy-blockflow-cascade`](experiments/gpt2-groupwise-cauchy-blockflow-cascade) | Direct-target groupwise Cauchy block-flow cascade |
| 10:01 | [`experiments/gpt2-groupwise-cauchy-blockflow-production-batch17`](experiments/gpt2-groupwise-cauchy-blockflow-production-batch17) | Production batch-17 exact tail |
| 10:33 | [`experiments/gpt2-progressive-precision-block-gate`](experiments/gpt2-progressive-precision-block-gate) | Progressive precision block-gate browser probe |
| 10:38 | [`experiments/gpt2-progressive-precision-closure`](experiments/gpt2-progressive-precision-closure) | Fixed-depth progressive-precision closure |
| 10:54 | [`experiments/gpt2-groupwise-cauchy-blockflow-production-selective-q12-top32`](experiments/gpt2-groupwise-cauchy-blockflow-production-selective-q12-top32) | Production selective-rowwise-q12 groupwise cascade |
| 10:54 | [`experiments/gpt2-groupwise-precision-allocation`](experiments/gpt2-groupwise-precision-allocation) | Groupwise coarse-precision allocation screen |
| 10:55 | [`experiments/gpt2-global-precision-targets`](experiments/gpt2-global-precision-targets) | Global output-target precision screen |
| 11:02 | [`experiments/gpt2-q15-decision-calibration`](experiments/gpt2-q15-decision-calibration) | Q15 decision-aware calibration |
| 11:05 | [`experiments/gpt2-global-q16-lattice-scale`](experiments/gpt2-global-q16-lattice-scale) | GPT-2 global-q16 lattice-scale Chrome probe |
| 11:20 | [`experiments/gpt2-global-q15-contender`](experiments/gpt2-global-q15-contender) | GPT-2 global-q15 contender browser probe |
| 11:23 | [`experiments/gpt2-global-q16-layernorm-bound`](experiments/gpt2-global-q16-layernorm-bound) | GPT-2 global-q16 final-LayerNorm-bound Chrome probe |
| 12:05 | [`experiments/gpt2-global-q16-layernorm-integer-full`](experiments/gpt2-global-q16-layernorm-integer-full) | Full-vocabulary GPT-2 global-q16 integer-axis output head |
| 13:22 | [`experiments/gpt2-groupwise-cauchy-blockflow-production-range-q16-sixfont`](experiments/gpt2-groupwise-cauchy-blockflow-production-range-q16-sixfont) | Focused six-font integration diagnostic |
| 13:22 | [`experiments/numeric-backend-decision`](experiments/numeric-backend-decision) | Numeric backend decision |

## 2026-09-15

| Time | Entry | Notes title |
|---|---|---|
| 14:13 | [`experiments/guarded-timeline-capacity`](experiments/guarded-timeline-capacity) |  |
| 14:27 | [`experiments/direct-2d-packet-capacity`](experiments/direct-2d-packet-capacity) | Direct two-dimensional packet capacity |
| 14:27 | [`experiments/preactivation-packet-transport`](experiments/preactivation-packet-transport) | Packed preactivation transport |
| 14:54 | [`experiments/gpt2-progressive-precision-crossover`](experiments/gpt2-progressive-precision-crossover) | Progressive precision real-font crossover probe |
| 15:02 | [`experiments/gpt2-flat-12block-chain`](experiments/gpt2-flat-12block-chain) | Twelve-block flat-MLP run |
| 21:35 | [`experiments/browser-native-compute`](experiments/browser-native-compute) | Browser-native compute probes |
| 22:00 | [`experiments/gpt2-block-css`](experiments/gpt2-block-css) | Anchor-packed full GPT-2 MLP |

## 2026-09-16

| Time | Entry | Notes title |
|---|---|---|
| 13:05 | [`experiments/flex-anchor-attention-scaling`](experiments/flex-anchor-attention-scaling) | Chromium attention-reducer ablation |
| 16:27 | [`experiments/hybrid-12block-profile`](experiments/hybrid-12block-profile) | Getting GPT-2 generation working in Chromium, without JavaScript |
| 20:23 | [`experiments/gpt2-quantization-quality`](experiments/gpt2-quantization-quality) | All greedy continuations |
| 21:16 | [`experiments/svg-causal-chromium-quality`](experiments/svg-causal-chromium-quality) |  |
| 21:30 | [`experiments/css-vector-latch`](experiments/css-vector-latch) |  |
| 21:35 | [`experiments/native-reused-loop`](experiments/native-reused-loop) |  |
| 21:36 | [`experiments/native-reused-loop-centered`](experiments/native-reused-loop-centered) |  |
| 21:42 | [`experiments/native-reused-loop-factored`](experiments/native-reused-loop-factored) |  |
| 21:49 | [`experiments/native-reused-loop-selective`](experiments/native-reused-loop-selective) |  |
| 22:02 | [`experiments/css-numeric-packets`](experiments/css-numeric-packets) |  |
| 22:47 | [`experiments/css-remembered-size`](experiments/css-remembered-size) |  |

## 2026-09-17

| Time | Entry | Notes title |
|---|---|---|
| 00:55 | [`experiments/browser-gpt2`](experiments/browser-gpt2) | Native GPT-2 in Chromium |
| 02:35 | [`experiments/browser-gpt2-scaling`](experiments/browser-gpt2-scaling) | Scaling figure and reproducible data |
| 03:04 | [`experiments/browser-gpt2-integration`](experiments/browser-gpt2-integration) | Integrating local updates into the real browser model |
| 03:29 | [`experiments/gsub-arithmetic-probe`](experiments/gsub-arithmetic-probe) | Digital arithmetic inside GSUB |
| 03:32 | [`experiments/svg-alpha-circuit-probe`](experiments/svg-alpha-circuit-probe) | Alpha-only Boolean SVG circuit experiment |
| 03:33 | [`experiments/fused-attention-font-probe`](experiments/fused-attention-font-probe) | Fused QK → exponential → weighted V inside one font |
| 03:36 | [`experiments/learned-glyph-code-screen`](experiments/learned-glyph-code-screen) | Supervised lookup-table follow-up |
| 03:36 | [`experiments/skia-f16-materialization-probe`](experiments/skia-f16-materialization-probe) | Standalone Skia materialization precision probe |
| 03:39 | [`experiments/skia-f16-real-matvec`](experiments/skia-f16-real-matvec) | Real GPT-2 weight slices on explicit Skia float surfaces |
| 03:43 | [`experiments/gsub-arithmetic-depth-probe`](experiments/gsub-arithmetic-depth-probe) | GSUB depth amortization |
| 18:22 | [`experiments/gsub-width-explainer`](experiments/gsub-width-explainer) | The width problem: interactive explainer |
| 18:48 | [`experiments/gsub-weighted-sum-probe`](experiments/gsub-weighted-sum-probe) | Connected arithmetic inside a font |
| 19:11 | [`experiments/gsub-reader-isolation`](experiments/gsub-reader-isolation) | Isolating the font-to-CSS reader |
| 19:11 | [`experiments/gsub-shared-matrix-probe`](experiments/gsub-shared-matrix-probe) | One input vector, several distinct outputs |
| 20:06 | [`experiments/gsub-reusable-digits`](experiments/gsub-reusable-digits) | Reproduce the shared-digit experiment |
| 20:13 | [`experiments/aat-support-probe`](experiments/aat-support-probe) | A streaming font machine fails the downloaded-font support gate |
| 21:04 | [`experiments/gsub-width-followups`](experiments/gsub-width-followups) | Independent audit of the width follow-ups |
| 21:12 | [`experiments/gsub-partitioned-digits`](experiments/gsub-partitioned-digits) | Reproduce the partitioned-digit experiment |
| 21:28 | [`experiments/native-mlp-integration`](experiments/native-mlp-integration) | Reproduce the connected MLP comparison |
| 21:41 | [`experiments/style-simplification-review`](experiments/style-simplification-review) | Three attempts to remove repeated CSS work |
| 21:45 | [`experiments/repo-optimization-audit-2026-09-17`](experiments/repo-optimization-audit-2026-09-17) |  |

## 2026-09-18

| Time | Entry | Notes title |
|---|---|---|
| 01:59 | [`experiments/optimization-followups-2026-09-17`](experiments/optimization-followups-2026-09-17) |  |
| 12:00 | [`audit/2026-09-18/C1-cost-model.md`](audit/2026-09-18/C1-cost-model.md) | C1 — Per-token cost model of the recommended CSS-only TinyStories pipeline |
| 12:00 | [`audit/2026-09-18/C2-demo-cost-model.md`](audit/2026-09-18/C2-demo-cost-model.md) | C2 — Structural cost model of the validated 12-layer no-JS GPT-2 bundle(s) |
| 12:00 | [`audit/2026-09-18/E1-experiments-001-075.md`](audit/2026-09-18/E1-experiments-001-075.md) | E1 — experiments index entries 1–75 |
| 12:00 | [`audit/2026-09-18/E2-experiments-076-150.md`](audit/2026-09-18/E2-experiments-076-150.md) | E2 — experiments index lines 76–150 (75 entries) |
| 12:00 | [`audit/2026-09-18/E3-experiments-151-225.md`](audit/2026-09-18/E3-experiments-151-225.md) | E3 — experiments index lines 151–225 |
| 12:00 | [`audit/2026-09-18/E4-experiments-226-300.md`](audit/2026-09-18/E4-experiments-226-300.md) | E4 — experiments index lines 226–300 (75 entries) |
| 12:00 | [`audit/2026-09-18/E5-experiments-301-375.md`](audit/2026-09-18/E5-experiments-301-375.md) | E5 — experiments index lines 301–375 |
| 12:00 | [`audit/2026-09-18/E6-experiments-376-451.md`](audit/2026-09-18/E6-experiments-376-451.md) | E6 — experiments index lines 376–451 (76 entries) |
| 12:00 | [`audit/2026-09-18/M1-microbench`](audit/2026-09-18/M1-microbench) | M1 micro-benchmarks: isolating the atomic Blink costs |
| 12:00 | [`audit/2026-09-18/P1-profile.md`](audit/2026-09-18/P1-profile.md) | P1 — Where the wall-clock goes when `tinystories/streaming-packed8.html` generates tokens |
| 12:00 | [`audit/2026-09-18/README.md`](audit/2026-09-18/README.md) | Audit run 2026-09-18 |
| 12:00 | [`audit/2026-09-18/SYNTHESIS.md`](audit/2026-09-18/SYNTHESIS.md) | Why the CSS GPT-2 plateaued, where the time really goes, and the atomic fix |
| 12:00 | [`audit/2026-09-18/experiments-index.txt`](audit/2026-09-18/experiments-index.txt) |  |
| 12:00 | [`work/2026-09-19/PLAN-round4.md`](work/2026-09-19/PLAN-round4.md) | Implementation plan: fixes 1–6 from audit/2026-09-18/SYNTHESIS.md |
| 12:00 | [`work/2026-09-19/RESULTS-round1.md`](work/2026-09-19/RESULTS-round1.md) | Round 1 results (2026-09-18/19) |
| 13:26 | [`audit/2026-09-18/P1-profile.md`](audit/2026-09-18/P1-profile.md) |  |
| 14:42 | [`audit/2026-09-18/P2-scratch`](audit/2026-09-18/P2-scratch) | full: per-token phase split (ms; % of window wall) |
| 17:15 | [`work/2026-09-19/B0`](work/2026-09-19/B0) | B0 — baseline + bench (status report; updated after each bundle) |
| 18:07 | [`work/2026-09-19/F2`](work/2026-09-19/F2) | F2 — Fix 2: slim the dense leaf populations (proj packs, V glyphs) + inline GELU |
| 18:10 | [`work/2026-09-19/F5`](work/2026-09-19/F5) | F5 — Fix 5 (narrow the write points) + Fix 4 (cheapest latch) — report |
| 19:26 | [`work/2026-09-19/F3`](work/2026-09-19/F3) | F3 — Fix 3 + Fix 6: take frames out of the loop (anchor → size-container gather) |
| 19:55 | [`work/2026-09-19/combined2`](work/2026-09-19/combined2) |  |
| 20:18 | [`work/2026-09-19/F4`](work/2026-09-19/F4) | F4 — Fix 4: cut the retained-transition count (+ the `combined` bundle = F2 + F5 + F4) |
| 20:29 | [`work/2026-09-19/F3b`](work/2026-09-19/F3b) | F3b — Fix 3 (+ Fix 6 for the MLP hops) integrated into the 12-layer emitter: frameless fc→proj→out transport |

## 2026-09-19

| Time | Entry | Notes title |
|---|---|---|
| 02:43 | [`work/2026-09-19/R2B`](work/2026-09-19/R2B) | R2B — round-2 micro-benchmarks MB6–MB9 (written before running) |
| 09:58 | [`work/2026-09-19/R2D`](work/2026-09-19/R2D) | R2D — round 2: lock the output head outside its own pass, and cheap per-frame knobs — report |
| 10:07 | [`work/2026-09-19/R2F`](work/2026-09-19/R2F) | R2F — remove the pure-handshake frames (E, G) and fold the pass advance (F) into hop frame D |
| 12:00 | [`work/2026-09-19/HOSTING-PLAN.md`](work/2026-09-19/HOSTING-PLAN.md) | Hosting plan: Cloudflare R2 + custom domain (fallback: GitHub Release) |
| 12:00 | [`work/2026-09-19/R2A`](work/2026-09-19/R2A) | R2A — round-2 trace anatomy of the `combined` bundle (no Chromium runs) |
| 12:00 | [`work/2026-09-19/R2E-design.md`](work/2026-09-19/R2E-design.md) | R2E design — hop-gated view-timeline animations (design report BEFORE building, as requested) |
| 12:00 | [`work/2026-09-19/RESULTS-round2.md`](work/2026-09-19/RESULTS-round2.md) | Round 2 results (2026-09-19/20) — CONFIRMED by interleaved paired pass (B3, bench/paired.md) |

## 2026-09-20

| Time | Entry | Notes title |
|---|---|---|
| 12:00 | [`work/2026-09-19/B2`](work/2026-09-19/B2) | Process hygiene at takeover (12:22) |
| 12:00 | [`work/2026-09-19/B3`](work/2026-09-19/B3) | B3 — interleaved paired confirmation bench (2026-09-20) |
| 12:00 | [`work/2026-09-19/B4`](work/2026-09-19/B4) | B4 — round-3 interleaved paired bench queue (2026-09-20) |
| 12:00 | [`work/2026-09-19/R2I`](work/2026-09-19/R2I) | R2I — recovery of deleted rowbase fonts (experiments/gpt2-flat-12block-chain/layer01..10) |
| 12:00 | [`work/2026-09-19/R3P`](work/2026-09-19/R3P) | R3P — round 3: pack two values per view-timeline carrier (exactness gate) — 2026-09-20 |
| 12:00 | [`work/2026-09-19/R4A`](work/2026-09-19/R4A) | 0. Verdict |
| 12:00 | [`work/2026-09-19/RESULTS-round3.md`](work/2026-09-19/RESULTS-round3.md) | Attribution of the remaining ≈23.6 s (R3A trace of R2F) |
| 14:10 | [`work/2026-09-19/R2C`](work/2026-09-19/R2C) | R2C — hoist per-axis arithmetic out of consumer `font-variation-settings` lists |
| 16:22 | [`work/2026-09-19/R2H`](work/2026-09-19/R2H) | R2H — round-2 merge: `bundles/combined3` = F4 `combined` + R2C hoist + R2F lean handshake + R2D knobs |
| 16:46 | [`work/2026-09-19/R2G`](work/2026-09-19/R2G) | R2G — why the loop-handshake passes (357 / 485 elements) cost 3–6× the cost model |
| 19:05 | [`work/2026-09-19/R3H`](work/2026-09-19/R3H) | R3H — the output-head frame, dissected (round 3, analysis only, no Chrome) |
| 21:15 | [`work/2026-09-19/R3F`](work/2026-09-19/R3F) | R3F — fold the remaining hop frames (round 3) |
| 21:24 | [`work/2026-09-19/R3A`](work/2026-09-19/R3A) | R3A — round-3 diagnostic trace of `bundles/R2F` (2026-09-20) |
| 21:39 | [`work/2026-09-19/R3K`](work/2026-09-19/R3K) | R3K — harness fix: keyboard trigger removes the forced per-frame hover pass |
| 21:58 | [`work/2026-09-19/R3R`](work/2026-09-19/R3R) | R3R — one geometry→number hop less per layer: the loop-transport hop folds into the proj readback |
| 22:02 | [`work/2026-09-19/R3L`](work/2026-09-19/R3L) | R3L — round 3: cut the loop-bank latch cost by packing two values per latched `<number>` |
| 22:13 | [`work/2026-09-19/R3M`](work/2026-09-19/R3M) | 0. Headline |
| 23:53 | [`work/2026-09-19/R4C`](work/2026-09-19/R4C) | 0. Headline |

## 2026-09-21

| Time | Entry | Notes title |
|---|---|---|
| 00:05 | [`work/2026-09-19/R4S`](work/2026-09-19/R4S) | 0. Headline |
| 00:43 | [`work/2026-09-19/R4D`](work/2026-09-19/R4D) | R4D — flatten the capacity-32 cost without changing the model (2026-09-21) |
| 01:03 | [`work/2026-09-19/R4X`](work/2026-09-19/R4X) | R4X — readback / vector primitives not in the catalog: is there anything that beats view-timelines? |
| 03:24 | [`work/2026-09-19/R4M`](work/2026-09-19/R4M) | 0. Headline |
| 03:49 | [`work/2026-09-19/R4V`](work/2026-09-19/R4V) | 0. Headline |
| 03:51 | [`work/2026-09-19/R4T`](work/2026-09-19/R4T) | Demo topology measured from bundles/combined4 (index.html / runtime.css) |
| 05:57 | [`work/2026-09-19/R4W`](work/2026-09-19/R4W) | R4W — cut the ∝ p per-pass allocation of the V leaves without changing numerics (R4V §5.1 fix) |
| 12:00 | [`work/2026-09-19/B5`](work/2026-09-19/B5) | B5 — round-4 interleaved paired bench queue (2026-09-21) |
| 12:00 | [`work/2026-09-19/PLAN-round4.md`](work/2026-09-19/PLAN-round4.md) | Round 4 plan (2026-09-21) |
| 12:00 | [`work/2026-09-19/R4P`](work/2026-09-19/R4P) | R4P — a better single-token prompt for the 32-token greedy demo (offline, NumPy only) |

## 2026-09-24

| Time | Entry | Notes title |
|---|---|---|
| 12:00 | [`work/2026-09-19/B6`](work/2026-09-19/B6) | B6 — round-5 interleaved paired bench queue (2026-09-24), reference `bundles/combined7` |
| 12:00 | [`work/2026-09-19/PLAN-round5.md`](work/2026-09-19/PLAN-round5.md) | Round 5 plan (2026-09-24) — lower s/token AND memory for `combined7` (cap 8, ≈16.0 s/token, RSS peak ≈6 GB) |
| 12:00 | [`work/2026-09-19/RESULTS-round5.md`](work/2026-09-19/RESULTS-round5.md) | Round 5 (2026-09-24) — lower s/token and memory for `combined7` (≈16.0 s/token, RSS ≈6 GB at token 8) |
| 14:26 | [`work/2026-09-19/R5A`](work/2026-09-19/R5A) | R5A — where combined7's ≈16 s/token and ≈6 GB go (2026-09-24) |
| 14:36 | [`work/2026-09-19/R5M`](work/2026-09-19/R5M) | R5M — what memory can be cut from `combined7` (cap 8) without touching numerics or ids |
| 14:54 | [`work/2026-09-19/R5H`](work/2026-09-19/R5H) | 0. Headline |
| 15:32 | [`work/2026-09-19/R5F`](work/2026-09-19/R5F) | R5F — shrinking the decoded weight fonts without changing a single advance |
| 15:34 | [`work/2026-09-19/R5C`](work/2026-09-19/R5C) | 0. Headline — CLOSED (works, exact, 2.0 frames/layer, but a net regression of +1.6 s/token) |
| 16:00 | [`work/2026-09-19/R5E`](work/2026-09-19/R5E) | R5E — element/declaration floor: what every style pass re-applies for nothing at capacity 8 (2026-09-24) |
| 17:14 | [`work/2026-09-19/R5X`](work/2026-09-19/R5X) | 0. Headline |
| 17:33 | [`work/2026-09-19/bench`](work/2026-09-19/bench) | combined (mouseoff) |
| 17:58 | [`work/2026-09-19/R5G`](work/2026-09-19/R5G) | R5G — stock Chrome launch flags vs the renderer's memory footprint (combined7, 8 tokens) — 2026-09-24 |

## 2026-09-30

| Time | Entry | Notes title |
|---|---|---|
| 12:00 | [`work/2026-09-19/PLAN-round6.md`](work/2026-09-19/PLAN-round6.md) | Round 6 plan (2026-09-30) — make `combined8-c32` a shareable demo: free-text prompt, visible progress, faster load |
| 12:00 | [`work/2026-09-19/RESULTS-round6.md`](work/2026-09-19/RESULTS-round6.md) | Round 6 (2026-09-30) — shareable demo: prompt input, progress UI, load time (plan: PLAN-round6.md) |
| 19:20 | [`work/2026-09-19/R6L`](work/2026-09-19/R6L) | R6L — load time of `combined8-c32` (≈34 s blank tab) and the distribution question — report |
| 20:01 | [`work/2026-09-19/R6P`](work/2026-09-19/R6P) | 0. Headline |
| 20:06 | [`work/2026-09-19/R6V`](work/2026-09-19/R6V) | 0. Headline |

## 2026-10-01

| Time | Entry | Notes title |
|---|---|---|
| 11:38 | [`work/2026-09-19/R7S`](work/2026-09-19/R7S) | R7S — sampling instead of argmax, in pure HTML+CSS (research + gated fixture) — 2026-10-01 |
| 12:00 | [`work/2026-09-19/R7P.md`](work/2026-09-19/R7P.md) | R7P — parallel prefill and the "32 new tokens" budget (2026-10-01) |
| 14:09 | [`work/2026-09-19/R6X`](work/2026-09-19/R6X) | 0. Headline |
| 14:26 | [`work/2026-09-19/R7T`](work/2026-09-19/R7T) | R7T — can exact capacity-8 go clearly below 15 s/token in stock Chrome? (2026-10-01) |
| 16:18 | [`work/2026-09-19/R7H`](work/2026-09-19/R7H) | R7H — the winner → token-id hop: map, the off-by-one, and a self-checking guard (round 7, 2026-10-01) |
| 20:09 | [`work/2026-09-19/R7B`](work/2026-09-19/R7B) | R7B — prefill head skip, capacity 36 + "32 new tokens" stop rule, Gumbel-max sampling (2026-10-01) |
| 21:16 | [`work/2026-09-19/R7X`](work/2026-09-19/R7X) | R7X — next live demo: R7B's capacity-36 features + R7H's id guard in one bundle (2026-10-01) |

## 2026-10-02

| Time | Entry | Notes title |
|---|---|---|
| 12:00 | [`audit/2026-10-02/I1-how-it-works-datapath.md`](audit/2026-10-02/I1-how-it-works-datapath.md) | I1 — "How it actually works": the data path of one token through demo-c32 |
| 12:00 | [`audit/2026-10-02/I2-how-it-works-control.md`](audit/2026-10-02/I2-how-it-works-control.md) | I2 — "How it actually works": the control path and I/O of the live demo |
| 12:00 | [`audit/2026-10-02/N1-tricks-aug24-sep13.md`](audit/2026-10-02/N1-tricks-aug24-sep13.md) | N1 — Tricks & hacks, 2026-08-24 → 2026-09-13 (first half) |
| 12:00 | [`audit/2026-10-02/N2-tricks-sep13-sep18.md`](audit/2026-10-02/N2-tricks-sep13-sep18.md) | N2 — Tricks and hacks, 2026-09-13 (evening) → 2026-09-18 (the audit) |
| 12:00 | [`audit/2026-10-02/N3-rounds-sep19-oct01.md`](audit/2026-10-02/N3-rounds-sep19-oct01.md) | N3: From 40 s/token research to a shareable demo (rounds 2026-09-19 → 2026-10-01) |
| 12:00 | [`work/2026-09-19/R8H.md`](work/2026-09-19/R8H.md) | R8H — where to host the demo-c32 bundle (research only, 2026-10-02; all prices "as of 2026-10-02", sources in Appendix) |
| 13:05 | [`work/2026-09-19/R8U`](work/2026-09-19/R8U) | R8U — production page layout for demo-c32 / demo-8 (round 8, 2026-10-02) |
| 13:05 | [`work/2026-09-19/bundles`](work/2026-09-19/bundles) | bundles/baseline — current-source rebuild of the pinned capacity-8 bundle (v2 operator fonts) |
| 13:11 | [`work/2026-09-19/R8D`](work/2026-09-19/R8D) |  |
| 15:21 | [`work/2026-09-19/B1`](work/2026-09-19/B1) | B1 — round-2 bench queue (status; a section is appended after each bundle's row is written) |
| 15:21 | [`work/2026-09-19/populations.json`](work/2026-09-19/populations.json) |  |

## 2026-10-05

| Time | Entry | Notes title |
|---|---|---|
| 00:41 | [`audit/2026-10-05/T3-rerun.md`](audit/2026-10-05/T3-rerun.md) |  |
| 00:42 | [`audit/2026-10-05/T3-rerun.md`](audit/2026-10-05/T3-rerun.md) | T3: re-running the toy transformer end to end, compared with MNIST |
| 00:44 | [`audit/2026-10-05/T1-code-walkthrough.md`](audit/2026-10-05/T1-code-walkthrough.md) | T1 — Code walkthrough: MNIST MLP → toy CSS transformer |
| 00:45 | [`audit/2026-10-05/T2-history.md`](audit/2026-10-05/T2-history.md) | T2 — History of the toy transformer (2026-08-24), from MNIST to tiny-gpt2 to GPT-2 |
