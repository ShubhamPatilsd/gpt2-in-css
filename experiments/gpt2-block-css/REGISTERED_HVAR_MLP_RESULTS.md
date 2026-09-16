# Registered HVAR GPT-2 MLP

Measured in headless Chrome 153 on macOS on September 13, 2026. The runtime
page contains XHTML, CSS, and fonts only; Playwright is an external harness.

## Connected computation

This is the real GPT-2-small block-0 MLP path:

`768 normalized inputs -> 3,072 FC outputs -> GELU -> 768 projection outputs`

The FC matrix is evaluated by three HVAR font shards. Four 6-bit FC/GELU
results are packed per physical container dimension, giving eight values in
each of 384 nested two-dimensional carriers. Each child freezes its local
decoded values into registered numeric properties. At the final element, all
3,072 inherited properties form one variation-axis list for the real
`3,072 -> 768` projection.

The projection uses 12-bit per-row weights split into 24 HVAR font shards of
128 axes each. Narrower shards keep signed glyph-advance deltas inside the
OpenType 16-bit range.

## Result

Three independent nine-round processes produced settled mutation medians of
804.8, 813.3, and 812.6 ms. The median run is **812.6 ms**.

| Path | Warm mutation | CSS | HTML | Projection fonts |
| --- | ---: | ---: | ---: | ---: |
| Previous single-sink additive animations | 1,598.6 ms | 65.59 MB | 270 KB | none |
| Registered properties + HVAR projection | 812.6 ms | 1.35 MB | 475 KB | 3.58 MB |

The new path is about **2x faster** and reduces raw CSS by about **49x**. Its
CSS compresses to 185 KB with Brotli q5. The three shared FC fonts add about
2.7 MB.

Browser output differs from its offline quantized HVAR reference by at most
0.000683 RMSE. Relative to the previous quantized dense projection, worst-case
RMSE is 0.00272 and maximum coordinate error is 0.0136.

## Precision sweep

| Projection weights | Shard width | Warm mutation | RMSE vs dense | Projection fonts |
| ---: | ---: | ---: | ---: | ---: |
| 11-bit | 256 | 791 ms | 0.00575 | 3.07 MB |
| 12-bit | 128 | 815 ms | 0.00272 | 3.58 MB |
| 13-bit | 32 | 914 ms | 0.00155 | 4.40 MB |

Twelve bits is the best measured tradeoff: it halves 11-bit error for roughly
3% more runtime, while 13-bit needs 96 font shards and costs another 12%.

## Remaining cost

The 812 ms is no longer dominated by axis-list construction. Ablations show
that the 384-level nested layout dependency is the dominant cost; bypassing
font shaping or GELU changes much less. The packed view-timeline FC -> HVAR
projection experiment removes that serial chain and reaches a 184.5 ms median
on its same-fixture mutation benchmark, at the cost of higher activation error
(0.0305 dense-reference RMSE). See `TIMELINE_HVAR_PROJECTION_RESULTS.md`.

## Reproduce

```sh
ANCHOR_PACKED_MLP_LAYOUT=local-2d ANCHOR_PACKED_SINK=hvar \
ANCHOR_PACKED_HVAR_BITS=12 ANCHOR_PACKED_HVAR_SHARD=128 PYTHONPATH=tools \
uv run --with numpy --with fonttools --with brotli --with pillow --with safetensors \
  python tools/build_anchor_packed_full_mlp.py
REGISTERED_HVAR_MLP_ROUNDS=9 node tools/test_registered_hvar_full_mlp.mjs
```
