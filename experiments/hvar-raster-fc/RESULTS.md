# HVAR geometry to SVG raster transport

These no-script pages test a one-way handoff from exact variable-font matrix
geometry into an SVG pixel vector. JavaScript is used only by the external
Playwright measurement harnesses.

## Results

| Path | Warm mutation median | Accuracy | Live elements |
| --- | ---: | ---: | ---: |
| 3,072 ordinary HVAR bars → one raster column | 99.95 ms | hidden RMSE 0.02344 | 3,090 |
| Per-channel HVAR bars → one raster column | 149.36 ms | calibration RMSE 0.00831; held-out RMSE 0.02481 | 3,090 |
| HVAR bars → raster hidden → real 3,072→768 SVG projection | 100.10 ms | output RMSE 0.40298 | 3,235 |

The connected hybrid is about 2.3 times faster than the retained all-SVG FC +
projection fixture's roughly 234 ms median, and its error is slightly lower
than that fixture's 0.41454 RMSE. This isolates the remaining error to the SVG
projection rather than the new geometry-to-raster handoff.

Changing the projection reduction width did not help:

| Projection shard | Warm median | Initial RMSE |
| ---: | ---: | ---: |
| 256 | 100.10 ms | 0.40298 |
| 128 | 79.22 ms | 0.42612 |
| 64 | 98.24 ms | 0.45573 |

Automatically grouping output rows by their calibrated numeric ranges also had
poor returns:

| Range groups | Warm median | Initial RMSE | Elements |
| ---: | ---: | ---: | ---: |
| 1 | 100.10 ms | 0.40298 | 3,235 |
| 4 | 121.87 ms | 0.38745 | 3,673 |
| 8 | 210.82 ms | 0.38688 | 4,257 |
| 16 | 510.84 ms | 0.38319 | 5,425 |

The failure is therefore not primarily a shard-size or output-range problem.
The signed weight × activation product is materialized as an 8-bit SVG surface
before reduction, so small products disappear. More range groups replicate the
graph without removing that boundary.

`hvar-raster-direct-projection` tested putting weights directly in
`feConvolveMatrix` kernels so multiplication and reduction remain one browser
operation. Chromium produced correct results through 256 kernel inputs, then
returned clamped/invalid results at 512, 1,024, 2,048, and 3,072 inputs. A full
direct projection would therefore need 12 kernels per output, or 9,216 separate
convolution primitives, which does not solve the object-scaling problem.

## Decision

Geometry-to-raster is a useful bulk, one-way transport. It eliminates thousands
of timelines and CSS variables and can hand a whole FC vector to an SVG
consumer. It does not provide a raster-to-CSS return path, and the conventional
SVG image-product projection remains too inaccurate for a deep exact chain.

## Reproduce

```sh
uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors \
  python tools/build_hvar_raster_fc_probe.py
node tools/test_hvar_raster_fc_probe.mjs
node tools/test_hvar_raster_fc_per_channel.mjs

uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors \
  python tools/build_hvar_raster_mlp_probe.py
node tools/test_hvar_raster_mlp_probe.mjs
```
