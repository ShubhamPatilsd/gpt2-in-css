# Real GPT-2 FC on Grid/Subgrid

This fixture runs the real quantized GPT-2-small block-0 `768 -> 3,072` FC and
GELU. The runtime page contains only HTML, CSS, and the existing matrix fonts.

Grid stores the 3,072 HVAR advances as independent track widths. A subgrid cell
turns each local width into one CSS number and applies GELU. This removes all
3,072 view timelines and animations.

## Browser result

Chrome 153 was measured with dense input mutations. Three runs of each backend
were rotated to reduce ordering effects.

| Carrier | Mutation medians | Median of runs | Hidden RMSE |
| --- | ---: | ---: | ---: |
| Grid/Subgrid | 188.9, 133.6, 141.6 ms | **141.6 ms** | 0.0000566 |
| Named view timelines | 629.8, 646.7, 477.6 ms | **629.8 ms** | 0.0001312 |

Grid is 4.45x faster on the median-of-runs comparison and slightly more
accurate. Its generated HTML is 724 KB and it reuses 2.81 MB of matrix fonts.

## Limit

The recovered number exists only inside its own subgrid cell. CSS cannot gather
3,072 sibling-local values into the single `font-variation-settings` list
needed by the following `3,072 -> 768` projection.

A counter reducer was tested as a possible escape. The local widths decoded to
the expected `3`, `5`, and `7`, and Chrome computed the requested counter
increments, but those increments did not escape the child counter scopes to a
shared result. Grid is therefore a strong coordinatewise carrier, not yet a
dense-layer-to-dense-layer carrier.

## Reproduce

```sh
PYTHONPATH=tools uv run --with numpy --with brotli --with fonttools --with pillow \
  python tools/build_grid_subgrid_gpt2_fc.py
GRID_GPT2_FC_MODE=grid node tools/benchmark_grid_subgrid_gpt2_fc.mjs
GRID_GPT2_FC_MODE=timeline node tools/benchmark_grid_subgrid_gpt2_fc.mjs
node tools/test_counter_vector_reduction.mjs
```
