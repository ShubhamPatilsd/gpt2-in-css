# HVAR embedding-to-QKV vector chain

Measured in headless Chrome 153 on macOS on September 13, 2026. Runtime pages
contain HTML, CSS, and fonts only; Playwright is an external measurement
harness.

## Question

Can the 64 glyph widths returned by the full-vocabulary token embedding lookup
be gathered into one reusable vector and drive the real first TinyStories QKV
matrix without view timelines or one DOM chain per matrix coefficient?

## Construction

Four embedding coordinates are quantized and packed into each container. In
the 12-bit version, the container width stores four low six-bit digits and its
height stores four high six-bit digits. A child decodes both dimensions with
`cqi` and `cqb`, reconstructs each 12-bit value, and uses four paused additive
animations to contribute those values to a 64-axis `font-variation-settings`
vector. Sixteen nested containers assemble all 64 axes. A 13.6 KB HVAR font
then evaluates the real `64 -> 192` first-block QKV matrix.

## Result

Both variants transported every browser result to within about `5.9e-5` RMSE
of their offline quantized reference.

| Transport | Median of three settled-mutation medians | Worst RMSE vs dense QKV | Worst absolute error |
| --- | ---: | ---: | ---: |
| 6-bit | 17.1 ms | 0.00267 | 0.0156 |
| 12-bit two-plane | 18.1 ms | 0.00159 | 0.00996 |

The 12-bit variant costs only about one millisecond more, so it is the better
default. Its page is 82.7 KB, its QKV font is 13.6 KB, and it uses 290 elements.
The shared full-vocabulary embedding lookup font is 4.21 MB.

A subsequent scaling probe in `../packed-hvar-transport-scaling/` replaced the
additive animations with registered numeric properties inherited through the
same nested carriers. At width 64 that form has comparable runtime, but at
width 768 it is 9.6x faster and makes the stylesheet 20x smaller. The connected
output-head fixture now uses the registered form.

This establishes a real local bridge:

`token ID -> 64 embedding glyph widths -> 12-bit CSS vector -> 192 QKV widths`

It does not establish that the same nested animation transport is economical
at GPT-2 width 768 or when repeated throughout 12 blocks. Those are now scaling
questions rather than a missing width-to-axis mechanism.

## Reproduce

```sh
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_hvar_embedding_qkv_chain.py
HVAR_EMBEDDING_QKV_VARIANT=b6 node tools/test_hvar_embedding_qkv_chain.mjs
HVAR_EMBEDDING_QKV_VARIANT=b12 node tools/test_hvar_embedding_qkv_chain.mjs
```
