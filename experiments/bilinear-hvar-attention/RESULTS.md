# Bilinear HVAR attention scores

Measured in headless Chrome 153 on macOS on September 12, 2026. Runtime pages
are HTML/CSS-only; JavaScript exists only in the external measurement harness.

## Primitive

An OpenType variation region that mentions two axes has a support scalar equal
to the product of the two individual axis supports. Four regions encode the
four sign quadrants for one coordinate:

| Query sign | Key sign | HVAR delta |
| --- | --- | ---: |
| positive | positive | +961 |
| positive | negative | -961 |
| negative | positive | -961 |
| negative | negative | +961 |

With query and key values normalized by 31, the four regions contribute exactly
`q[i] * k[i]`. Sixty-four coordinate pairs therefore use 128 axes and 256
regions. Four glyphs each accumulate 16 products; their combined advance is the
complete live 64-dimensional dot product.

## Result against geometry-backed arithmetic

The `exact4` font is 3,052 bytes as WOFF2. Its maximum browser error over initial,
query-only, and full key updates is 0.54 raw dot-product units. GPT-2 divides
attention logits by `sqrt(64) = 8`, so that bound is below 0.067 in the scaled
attention score.

| Heads × keys | Scores | DOM elements | HTML | Cached-query update | Full query+key update |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 × 4 | 4 | 12 | 9.9 KB | 5.96 ms | 5.99 ms |
| 1 × 16 | 16 | 24 | 27.0 KB | 15.67 ms | 18.50 ms |
| 1 × 64 | 64 | 72 | 95.0 KB | 57.87 ms | 71.08 ms |
| 12 × 4 | 48 | 67 | 87.4 KB | 46.07 ms | 57.62 ms |
| 12 × 16 | 192 | 211 | 291.5 KB | 169.63 ms | 207.36 ms |
| 12 × 64 | 768 | 787 | 1.11 MB | **664.46 ms** | **832.07 ms** |

At 12 heads × 64 keys, the corrected two-lane CSS-anchor implementation needs
25,735 elements and 8,626.53 ms for the same cached-query update. Bilinear HVAR
uses 787 elements and is **12.98x faster**. Its 1.11 MB HTML is 6.2x smaller than
the 6.88 MB anchor page.

This is a valid improvement over geometry-backed multiplication, but it is not
the winning comparison once Q and K have already crossed into CSS numeric state.

## Native CSS-number control

A matched page gives every score element the same 64-term balanced `calc()` and
stores Q on its head parent and K on the score itself. It uses exactly the same
number of elements and the same input mutations as the HVAR page.

| Heads × keys | Native CSS query | HVAR query | Native CSS full | HVAR full |
| --- | ---: | ---: | ---: | ---: |
| 1 × 4 | 1.96 ms | 21.84 ms | 2.30 ms | 18.80 ms |
| 1 × 16 | 2.41 ms | 16.43 ms | 5.36 ms | 21.01 ms |
| 1 × 64 | 5.41 ms | 59.07 ms | 18.60 ms | 72.48 ms |
| 12 × 4 | 6.68 ms | 49.05 ms | 14.40 ms | 56.67 ms |
| 12 × 16 | 15.70 ms | 170.79 ms | 52.29 ms | 218.88 ms |
| 12 × 64 | **49.43 ms** | **674.66 ms** | **195.90 ms** | **817.26 ms** |

Native CSS is bit-exact in this six-bit fixture. At 12 × 64 it is 13.65x faster
for a cached-query update and 4.17x faster when all keys change. It also avoids
the font's roughly half-unit width error.

## Glyph-count control

Chrome clamps an individual glyph advance near 32,767 font units, so exact
six-bit accumulation needs four glyph shards. Two lower-range controls trade
precision for two or one glyph. They remain numerically sound, but do not
improve the realistic 12 × 64 update:

| Encoding | Glyphs per score | Cached-query update | Maximum error |
| --- | ---: | ---: | ---: |
| exact4 | 4 | 681.74 ms | 0.531 |
| scaled2 | 2 | 675.46 ms | 0.531 |
| scaled1 | 1 | 690.63 ms | 0.529 |

The cost is dominated by evaluating 128 axes and 256 regions for every score,
not by shaping the final one to four glyphs.

## Real two-token integration

The bilinear backend was inserted between the real GPT-2 QKV timelines and the
existing softmax/value/output-projection stages. It reproduces all 24 attention
scores with 0.00075 RMSE and all 1,536 final residual values with 0.00032 RMSE.
However, its 2,685 ms warm end-to-end median is slightly slower than the native
CSS score page's 2,640 ms. At two tokens there are only 1,536 scalar products;
the additional shaping and score-readback timeline offsets the arithmetic saved.

## Real projected-KV integration at 16 and 32 tokens

The primitive was also connected to the current projected-KV attention graph. A
one-glyph-per-score font reduced the context-32 score markup from 4,992 child runs
to zero and reduced score glyphs from 24,576 to 384. The full attention result
remained accurate, but the variation engine still evaluated 128 axes and 256
regions for every score.

| Backend | Context 16 | Context 32 | C16 RMSE | C32 RMSE |
| --- | ---: | ---: | ---: | ---: |
| 5-bit GSUB/HVAR | 1.679 s | 2.656 s | 0.00538 | 0.00746 |
| Bilinear HVAR, one glyph | 1.669 s | 2.064 s | 0.00447 | 0.00797 |
| Direct CSS over projected KV | **1.411 s** | **1.504 s** | **0.00122** | **0.00216** |

The one-glyph bilinear form scales better than GSUB/HVAR, but direct CSS remains
faster and more accurate once the projected cache is numeric. This integration
confirms the earlier synthetic control under the actual QKV, softmax, value-mixing,
context-packing, and output-projection graph.

## Decision and boundary

This is the first tested browser primitive that computes a live-live bilinear
reduction without expanding it into one CSS multiplication per coordinate, but
**reject it for Q·K when Q and K are already CSS numbers**. Native CSS math is
substantially faster and exact.

It also does **not** solve the general transport problem. An `anchor-size()`
result cannot be substituted directly into `font-variation-settings`, so HVAR
or geometry output from the QKV projection must first be exposed as CSS numeric
state. Once that cost has been paid, native CSS is the better consumer.

Retain bilinear HVAR only as a conditional option if a future backend can keep Q
and K as font axes without a geometry-to-number or score readback boundary.
