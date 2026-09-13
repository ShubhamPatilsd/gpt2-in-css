# Multi-token block-0 carrier calibration

## Purpose

The earlier channel-specific block output carrier was calibrated only on one-token
states. Connecting real multi-token attention exposed values far outside those
ranges, including -22.8 at channel 64, so the browser clipped valid model state.

This experiment calibrates every one of the 768 block-0 output channels using real
causal attention over random sequences of length 2, 4, 8, 16, and 32. It uses 245
calibration sequences, a 1.5 range margin, and 125 independently generated held-out
sequences.

## Accuracy

Only 0.0135% of held-out scalar values exceeded the calibrated range. Six of 125
held-out sequences contained any clipped coordinate.

The calibrated carrier was then connected to the projected-KV attention fixture and
the matching real GPT-2 block-0 LN2/MLP:

| Context | Old one-token ranges | Global safe range | Multi-token ranges |
| ---: | ---: | ---: | ---: |
| 16 | ~1.02 RMSE | ~0.176 RMSE | 0.0882 RMSE |
| 32 | ~1.02 RMSE | ~0.176 RMSE | 0.0849 RMSE |

The isolated MLP RMSE is 0.0860 at context 16 and 0.0882 at context 32. The connected
LN2 input RMSE remains 0.00109 and 0.00390 respectively, confirming that the large
old error was output-range clipping rather than attention or layer normalization.

## Performance boundary

Warm navigation medians were 5.46 seconds at context 16 and 5.94 seconds at context
32. A traced warm context-16 load spent 3.70 seconds in layout and shaped text 50,334
times.

More importantly, persistent-page mutation measured:

| Component | Context-16 update |
| --- | ---: |
| Attention alone | 661 ms |
| MLP alone | 267 ms |
| Connected block | 2,226 ms |

The connected graph therefore pays about 1.30 seconds beyond the two isolated
calculations. Removing 1,536 residual aliases preserved accuracy but improved the
connected update by only 2.7%, to 2,166 ms. The cost is broad style/layout
invalidation across the joined dependency graph, not the aliases themselves.

CSS containment did not solve it. Seven boundaries preserved identical outputs; the
best result was 2,256 ms versus a 2,274 ms baseline, while stronger containment
slowed the update to 2.42-2.53 seconds.

Replacing the attention projection's 768 timeline conversions with 192 containers
that each carry four 12-bit values did help. It removed one layout pass, reduced warm
startup from 5.07 to 3.82 seconds, and reduced persistent updates from 2.166 to 1.929
seconds. Full-block RMSE changed only from 0.0882 to 0.0905.

Denser packets did not scale further:

| Projection carrier | Containers | Update | Full-block RMSE |
| --- | ---: | ---: | ---: |
| Timeline | 768 timelines | 2.166 s | 0.0882 |
| 12-bit packet | 192 | 1.929 s | 0.0905 |
| 8-bit packet | 128 | 1.905 s | 0.0994 |
| 6-bit packet | 96 | 1.936 s | 0.0916 |

The lower-precision values vary because the downstream packed MLP quantizes again;
the important result is that halving packet depth below 192 did not improve latency.
The 12-bit packet is therefore the best measured accuracy/speed tradeoff.

## Projected-cache score backends

The original projected-KV backend still used a 5-bit OpenType alternate lookup for
each query coordinate. A bilinear HVAR control proved that 128 live axes and 256
two-axis regions can calculate a complete 64-term dot product, including a one-glyph
variant. Both were accurate, but reducing score glyphs from 12,288 to 192 did not
reduce end-to-end latency. Chromium's variation-axis and region evaluation, rather
than the final glyph count, dominates that backend.

Once Q and K have already been exposed as CSS numbers, direct CSS arithmetic is the
better consumer. The new `css-kv` backend dots the 64-wide projected Q and K vectors
directly. Unlike the older `css` control, it does not recompute every K coordinate
from the 768-wide normalized state inside every score.

| Score backend | Context-16 attention | Context-32 attention | C16 RMSE | C32 RMSE |
| --- | ---: | ---: | ---: | ---: |
| 5-bit GSUB/HVAR | 1.679 s | 2.656 s | 0.00538 | 0.00746 |
| Bilinear HVAR, one glyph | 1.669 s | 2.064 s | 0.00447 | 0.00797 |
| Direct CSS over projected KV | **1.411 s** | **1.504 s** | **0.00122** | **0.00216** |

At context 32, direct CSS is 43% faster than the feature-selected backend and has
3.5x lower attention error. Its generated HTML plus page-specific CSS is 3.68 MB,
versus 4.54 MB for the feature-selected page, before common matrix fonts.

The improvement survives the connected MLP:

| Score backend | C16 warm block | C32 warm block | C16 live block | C32 live block |
| --- | ---: | ---: | ---: | ---: |
| 5-bit GSUB/HVAR | 3.795 s | 4.703 s | 1.286 s | 1.233 s |
| Direct CSS over projected KV | **3.661 s** | **3.452 s** | **1.018 s** | **1.071 s** |

## Current connected-graph cost

Separate mutation fixtures now isolate the major block-0 stages. At context 16,
QKV takes 138 ms, the attention output projection takes 134 ms, and the isolated
MLP tail takes 250 ms. The complete feature-selected attention update takes 510 ms,
but the connected block takes 1,286 ms. Therefore about 526 ms is neither matrix
stage in isolation: it is additional invalidation and layout propagation created by
joining the attention and MLP dependency graphs.

Direct projected-KV CSS scores reduce attention to 475 ms and the connected block to
1,018 ms. A stricter isolated replay changes the same 605-606 residual coordinates
that real attention changes, rather than changing only one MLP input. That full-vector
MLP replay takes 301 ms at context 16 and 330 ms at context 32.

After matching the mutation scope, the unexplained connected-graph overhead is about
242 ms at context 16 and 208 ms at context 32 for direct CSS scores. The comparable
feature-selected estimate is roughly 475 ms and 326 ms. Thus some of the earlier
"connection tax" was required work caused by changing most of the residual vector,
but a genuine 17-37% full-block propagation overhead remains. Removing the large
inherited font-setting score subtrees cuts that overhead substantially.

Reducing the projection packet depth does not remove it:

| CSS-KV projection carrier | Containers | C16 warm block | C32 warm block | C32 attention RMSE |
| --- | ---: | ---: | ---: | ---: |
| 12-bit packet | 192 | **3.661 s** | **3.452 s** | **0.00545** |
| 8-bit packet | 128 | 3.572 s | 3.584 s | 0.02656 |
| 6-bit packet | 96 | 3.721 s | 4.095 s | 0.02566 |

Persistent updates likewise favor 12-bit packets: 1.018/1.071 seconds at context
16/32, versus 1.026/1.167 seconds for 8-bit and 1.167/1.133 seconds for 6-bit.
Shallower inheritance alone is therefore not the missing transport primitive.

## Conclusion

Multi-token per-channel calibration, a 12-bit attention projection packet, and direct
CSS scoring over the projected KV cache are now the best measured combination. They
replace one-token ranges, the timeline projection, and feature-selected score fonts.

This still does not solve full-model latency. The largest remaining cost is the graph
connection itself: values crossing from attention into the MLP cause substantially
more work than either isolated graph. The next scalable design should keep the
768-wide residual inside one dependency backend across the attention projection,
residual addition, LN2, and MLP, or introduce a boundary that prevents upstream
invalidation from walking the entire downstream graph.
