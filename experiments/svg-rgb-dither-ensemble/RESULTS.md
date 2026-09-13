# RGB phase-dithered SVG execution

This offline screen asks whether SVG's RGB channels can act as parallel
eight-bit executions with staggered rounding thresholds. It uses 256 calibration
tokens and 512 disjoint evaluation tokens across all 12 one-token GPT-2-small
blocks and all 110 activation materializations.

| Scheme | Held-out top-1 | Natural top-1 | Final-state RMSE |
| --- | ---: | ---: | ---: |
| ordinary, headroom 1.10 | 482/512 | 53/64 | 0.2254 |
| two rotating phases, headroom 1.10 | 488/512 | 56/64 | 0.2094 |
| three rotating phases, headroom 1.10 | **492/512** | 57/64 | 0.1453 |
| two rotating phases, headroom 1.20 | 488/512 | **59/64** | 0.2684 |
| four rotating phases, headroom 1.20 | 486/512 | 58/64 | 0.1992 |

Rotating three phases gives a real but modest general gain: 1.95 percentage
points. The current bucketed SVG matrix graph already uses red and green as
positive/negative lanes, so this is not a free drop-in. The earlier real-browser
product-dither probe also showed worse product RMSE when it repacked three
dithered product surfaces.

Do not rebuild the full chain around RGB replicas. Retain this as an upper bound
for any future matrix representation that leaves all three color channels free.

```sh
uv run --with numpy python tools/screen_svg_rgb_dither_ensemble.py
```
