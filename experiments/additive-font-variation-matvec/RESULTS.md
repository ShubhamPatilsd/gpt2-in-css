# Additive font-variation matvec

This experiment asks whether additive CSS animations can gather a dense matrix
result directly into one `font-variation-settings` vector. Runtime fixtures are
HTML/CSS-only; the external Playwright harness mutates inputs and reads results.

## Results

With scalar inputs supplied directly as paused-animation delays, Chrome 153
evaluated a dense `768→768` matrix in about 149–165 ms and a `3,072→768`
matrix in 591 ms. RMSE was approximately `1e-6`. The latter stylesheet was
47.3 MB because each of 3,072 keyframes contains a 768-number column.

Container widths can drive the same additive accumulation without animation-
tainted custom properties. One XHTML carrier per input worked through 768
levels. A four-value radix-64 packet is better: every carrier width stores four
6-bit inputs as one exact 24-bit integer, so `768→768` needs 192 levels and
`3,072→768` needs 768. Chrome produced the correct vectors with maximum errors
of `5.5e-6` and `7.1e-6`, respectively. Warm mutation medians were roughly
151 ms and 598 ms.

A five-value packet failed because its lowest digit lived in a fractional
`1/64px` at widths near `2^24px`; Chromium's float-backed layout rounded that
digit away. Four 6-bit digits are the exact reliable capacity of one width.

Using both width and height stores eight exact 6-bit values per carrier and
cuts the `3,072→768` chain from 768 carriers/depth 772 to 384 carriers/depth
388. In alternating, repeatedly mutated warm pages, the median changed only
from 689.1 ms to 649.7 ms: a 1.06x speedup. Both variants remained exact to
approximately `1e-6` RMSE. Halving carrier count and dependency depth therefore
does not halve execution time; the 3,072 additive animation contributions are
the dominant cost of this gather primitive.

Declarative shadow-root chunking did not extend the accumulator. The composed
animation-effect chain stopped after 512 contributions even though parser
depth reset at each shadow root.

Raw paired measurements are in `packed-1d-vs-2d-browser-results.json`.
