# Packed timeline FC -> HVAR projection

## Question

Can the fast packed view-timeline FC boundary feed the `3,072 -> 768`
projection directly, without materializing 3,072 properties or converting the
768 projection results through another bank of view timelines?

## Runtime path

`768 input -> attention prefix -> 3,072 FC/GELU -> 768 packed timelines -> one
3,072-axis HVAR declaration -> 768 projection glyph widths`

The runtime page contains HTML and CSS only. JavaScript is used only by the
external Playwright measurement harness.

## Result

Chrome 153, nine measured alternating-input mutations after two warmups. Each
mutation includes two animation frames so scroll-driven state is settled.

Three fresh browser processes produced these medians:

| Process | FC transport only | HVAR projection | Old output timelines |
|---|---:|---:|---:|
| 1 | 186.0 ms | 197.9 ms | 280.4 ms |
| 2 | 185.8 ms | 184.5 ms | 277.4 ms |
| 3 | 169.8 ms | 183.1 ms | 276.5 ms |

Median across processes:

- packed FC transport: **185.8 ms**
- packed FC plus HVAR projection: **184.5 ms**
- packed FC plus old 768-timeline output readback: **277.4 ms**
- same-fixture speedup: **1.50x**

The HVAR projection cost is within run-to-run noise (roughly 0-13 ms). The old
output transport consistently costs about 92-107 ms.

The final verification run reported 0.0305 RMSE and 0.1523 maximum error versus
the dense 9-bit-weight reference. The old output-timeline path reported 0.0310
RMSE and 0.1615 maximum error. HVAR therefore does not introduce the dominant
error; the packed FC timeline boundary does.

## Size

- HTML: 464,897 bytes
- CSS: 2,091,443 bytes (81,154 bytes at Brotli quality 5)
- FC plus projection fonts: 5,760,728 bytes
- FC timelines: 768
- output timelines: 0
- projection glyphs: 9,216

The old output-timeline page uses 561,146 bytes of HTML and 2,512,994 bytes of
CSS (110,785 bytes Brotli). The new endpoint is smaller despite holding the
complete 3,072-axis expression once.

## Decision

Use the packed timeline FC -> HVAR projection topology. It removes a real
serial boundary and is both faster and slightly more accurate than feeding the
projection through another 768 timelines.

This page exposes projection results as widths. Follow-up block-boundary tests
showed that the registered gather is not the right continuation at GPT-2 width:

| Boundary | Total settled mutation | Dense RMSE | Maximum error |
|---|---:|---:|---:|
| HVAR widths only | 183.3 ms | 0.0305 | 0.1523 |
| 12-bit registered gather | 331.8 ms | 0.0306 | 0.1537 |
| 8-bit registered gather | 300.7 ms | 0.0461 | 0.7924 |
| Existing output timelines | 266.2 ms | 0.0310 | 0.1615 |

The 12-bit gather preserves accuracy but its 192 serial carriers add about 148
ms. Packing six eight-bit values per carrier reduces the chain to 128 levels,
but remains slower than the existing timeline boundary and damages outlier
channels. A flat-anchor gather was faster but incorrect because those sibling
anchors are not acceptable from the nested containing blocks; making every
element fixed restored correctness and lost the speedup.

An attempted direct width-to-LayerNorm fusion is also invalid. `anchor-size()`
can participate in sizing expressions, but Chrome does not resolve it into a
registered numeric custom property. Mean and variance therefore fall back to
their initial values. It cannot bypass geometry transport this way.

Use HVAR widths when the projection is a terminal/observable result. For a
following transformer block, keep the existing output-timeline numeric
boundary until a non-serial gather is found.

## Reproduce

```sh
make test-timeline-hvar-projection
```

Artifacts:

- `view-timeline-block-hybrid-fc-packed4-hvar.html`
- `view-timeline-block-hybrid-fc-packed4-hvar.css`
- `view-timeline-block-hybrid-fc-packed4-hvar-reference.json`
- `view-timeline-block-hybrid-fc-packed4-hvar-browser.json`
