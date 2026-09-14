# Raster-native projection row scaling

## Question

Can a vector remain in the raster backend across GELU and a following dense
projection without paying one expensive transport per output?

The probe runs the real GPT-2 block-0 FC and GELU, keeps the result as a pixel
column, and applies independent `feConvolveMatrix` projection rows. This sweep
holds each row at 64 inputs and increases the number of arbitrary output rows.
The HTML/SVG runtime contains no JavaScript.

## Results

| Projection rows | Warm median | Filter primitives | HTML |
| ---: | ---: | ---: | ---: |
| 1 | 83.5 ms | 6 | 310 KB |
| 8 | 68.6 ms | 20 | 317 KB |
| 16 | 83.0 ms | 36 | 326 KB |
| 32 | 82.2 ms | 68 | 342 KB |
| 64 | 82.4 ms | 132 | 376 KB |
| 128 | 97.8 ms | 260 | 442 KB |
| 256 | 136.2 ms | 516 | 576 KB |
| 512 | 234.4 ms | 1,028 | 841 KB |
| 768 | 322.9 ms | 1,540 | 1.11 MB |

One row has low error, but the multi-row fixtures average roughly 0.5-1.1 RMSE
because each result is finally represented by one eight-bit pixel. The more
important scaling result is that Chrome stays nearly flat through 64 rows and
then grows approximately linearly with the number of distinct convolution rows.

A real GPT-2 `3,072 -> 768` projection cannot use a 3,072-tap convolution in
Chrome: the existing input-length sweep works through 256 taps and fails at 512
and above. It therefore needs 12 input shards for each of 768 output rows, or
9,216 row convolutions plus reduction. The 64-input sweep alone already reaches
323 ms at 768 rows, so the full structure is a multi-second backend before the
rest of the transformer block.

## Decision

Keep the single-glyph raster exporter as a fast one-way bulk operation. Reject
independent raster convolution rows as the reusable full-width GPT-2 projection:
the browser batches a modest number of rows well, but arbitrary dense rows still
scale as `O(outputs * input_shards)` in filter primitives and time.

## Reproduce

```sh
for outputs in 1 8 16 32 64 128 256 512 768; do
  HVAR_DIRECT_INPUTS=64 HVAR_DIRECT_OUTPUTS=$outputs \
    uv run --with numpy --with fonttools --with brotli --with pillow \
      --with safetensors python tools/build_hvar_raster_direct_projection_probe.py
  HVAR_DIRECT_INPUTS=64 HVAR_DIRECT_OUTPUTS=$outputs HVAR_DIRECT_ROUNDS=7 \
    node tools/test_hvar_raster_direct_projection_probe.mjs
done
```
