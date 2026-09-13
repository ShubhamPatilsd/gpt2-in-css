# Signed activation bit-plane SVG dot product

This probe tests whether binary activation planes avoid the 8-bit product loss
in an SVG dot product. Runtime artifacts contain HTML, SVG, and PNG only.

| Backend | RMSE | Maximum error |
| --- | ---: | ---: |
| Ordinary signed product | **0.00417** | **0.00944** |
| Six separate signed-magnitude planes | 0.00561 | 0.01561 |
| Three RGB-packed two's-complement reductions | 0.11447 | 0.53777 |
| Two RGB-packed signed-magnitude reductions | 0.01210 | 0.01858 |

The best bit-plane form is still worse than the ordinary product. Independent
plane reductions replace product rounding with repeated reduction and merge
rounding. RGB packing reduces the number of reductions, but channel packing and
centering lose more precision. The most complete fixture uses 166 SVG filter
primitives for a `64 -> 64` dot-product bank.

Bit planes are rejected for scaling the GPT-2 projection: they add filter graph
work and do not improve the numerical result even at head width 64.

```sh
PYTHONPATH=tools uv run --with numpy --with pillow --with safetensors \
  python tools/build_svg_signed_bitplane_dot.py
node tools/test_svg_signed_bitplane_dot.mjs
```
