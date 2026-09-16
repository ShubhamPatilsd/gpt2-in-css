# Anchor-packed full GPT-2 MLP

`anchor-packed-full-mlp-local-2d-literal-zero.xhtml` connects the real
quantized GPT-2-small `768→3,072` FC matrix, GELU and `3,072→768` projection.
The page contains no JavaScript.

Each FC result is a real HVAR glyph width. CSS uses `anchor-size()` to quantize
it, packs four 6-bit values in width and four in height, decodes those eight
values through `cqi`/`cqb`, applies GELU, and adds eight projection columns to
one 768-axis vector. There are 384 carriers instead of 3,072 scalar readbacks.

## Chrome 153 results

| Variant | Carriers / depth | Raw CSS | Live mutation | Browser RMSE | Offline activation RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 6-bit, one dimension | 768 / 772 | 65.6 MB | 3.12 s | 0.00052–0.00069 | 0.0248–0.0305 |
| 6-bit, two dimensions, literal zero | 384 / 388 | 65.4 MB | 2.27 s | 0.00052–0.00069 | 0.0248–0.0305 |
| 6-bit, two dimensions, shared zero | 384 / 388 | 44.2 MB | 2.53 s | 0.00052–0.00069 | 0.0248–0.0305 |
| 4-bit, two dimensions, literal zero | 256 / 260 | 65.4 MB | 2.14 s | 0.00056–0.00156 | 0.107–0.128 |
| 6-bit, two dimensions, one typed value per FC result, one sink | 384 / 388 | 65.4 MB | 1.59–1.62 s | 0.00052–0.00069 | 0.0248–0.0305 |
| 6-bit, two dimensions, split packet capture, one sink | 384 / 388 | 65.6 MB | 2.31 s | 0.00052–0.00069 | 0.0248–0.0305 |

The browser RMSE compares the rendered vector with the identical offline
quantized transport. The offline activation RMSE measures the actual loss from
quantizing FC activations instead of transport implementation error.

Repeated zero vectors compress extremely well. Brotli quality 6 produced
15.90 MB for the 65.4 MB literal stylesheet and 15.65 MB for the 44.2 MB shared
stylesheet. The literal form is therefore the better current trade: about
250 KB more compressed but roughly 10% faster in the focused run.

Keeping all 3,072 source glyphs flat fails: nested carriers cannot resolve
those out-of-scope anchors, even with `anchor-scope:all` or fixed positioning.
Putting each group of source glyphs immediately before its carrier makes every
anchor local and restores correctness, but the resulting nested shaping/layout
is the dominant cost.

The best anchor variant captures all 3,072 decoded FC results as typed numbers
and applies their projection columns at one final additive-animation sink. This
removes the 384 intermediate animation boundaries and cuts live mutation from
2.27 seconds to about 1.6 seconds.

Capturing one complete 24-bit width or height packet as a typed CSS number is
not exact: at multi-million-pixel widths Chromium loses the lowest six-bit
digit. Capturing that digit separately from the remaining 18-bit packet fixes
the error and halves the registered state from 3,072 properties to 1,536, but
moving all decode and GELU expressions to the final sink raises mutation time
to a 2.308-second median. Property count is therefore not the dominant cost.

An apples-to-apples loaded-page test of the older flat view-timeline MLP waits
for the two animation frames required to expose fresh timeline progress. Five
alternating input mutations took 458, 362, 341, 325 and 322 ms (341 ms median),
and the changed output matched the offline quantized MLP with 0.00545 RMSE.
Reading immediately after mutation misleadingly reports about 150 ms but
returns the unchanged cached vector.

The flat view-timeline backend is consequently about 4.7 times faster than the
best anchor-packed backend for this isolated real MLP, while also producing a
smaller runtime. Anchor packing proves that one carrier can expose eight values
and that a complete vector can feed one additive projection, but its deeply
nested local anchor/layout dependency chain is not currently the scaling path.
