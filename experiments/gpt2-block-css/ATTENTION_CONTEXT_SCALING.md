# Attention context scaling

This probe computes the final token's real block-0 GPT-2-small attention over
1, 2, 4, 8, 16, and 32 source tokens. Dense QKV and output projection use the same HVAR
fonts. Q·K, online softmax, and value mixing use native CSS math. The only
changed boundary is HVAR QKV output transport.

Unlike the original two-token demo, direct packets use per-channel ranges
calibrated on 4,096 random GPT-2 token/position states with a 20% margin.

Measured in headless Chrome 153 on macOS on September 12, 2026:

| Context | Timeline QKV | Accumulated QKV packets | Streamed K/V packets | Direct-K + streamed V | Geometry K/V + accumulator |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1.043 s | 0.606 s | 0.629 s | 0.578 s | — |
| 2 | 2.365 s | 1.196 s | 0.964 s | **1.020 s** | 1.075 s |
| 4 | 6.227 s | 3.213 s | 2.047 s | 1.639 s | **1.535 s** |
| 8 | 23.639 s | 13.728 s | 6.249 s | 3.5-4.1 s | **3.209 s** |
| 16 | — | — | — | 10.8-11.1 s | **7.020 s** |

The packet optimization is not a two-token artifact: accumulated packets remain
1.72-1.98x faster than timelines at all tested lengths. But carrying every
source's 2,304 uniquely named QKV values is superlinear because every later
descendant inherits the accumulated state.

Online softmax fixes most of that transport problem. The streamed variant
computes the target query once, reuses one K/V property bank per source, and
carries only a 768-value numerator plus 12 maxima and denominators. At eight
tokens it is 2.20x faster than accumulated packets and 19% smaller.

The strongest variant avoids transporting K altogether. Each head's 64-term
Q·K result is formed directly as a CSS width from the K glyph widths. Twelve
view timelines convert those score widths into numbers, while only the 768 V
values cross direct containers. This is correct: at two tokens, an expected
score of 9.3735 is observed as 9.3730, and final residual RMSE remains 0.00306.
At eight tokens it is roughly 3.3x faster than accumulated packets and 5.7x
faster than timeline QKV. Bundle size falls from 12.42 MB to 8.64 MB after removing
2,340 unnecessary typed registrations.

The 1/2/4/8 direct-K timings initially fit a line closely, but a 16-token check
takes roughly 10.8 seconds and shows the curve bending again. A matched profile
places most of the remaining cost in attention itself: 3.15 s attention + 0.34
s output projection at eight tokens, and 10.21 s + 1.46 s at sixteen. The next
test keeps the running 768-vector as geometry and updates it directly from V
glyph widths, removing 128 V packet containers and 768 registered accumulator
calculations per source.

That geometry-native accumulator succeeds. A final packet converts the
completed geometry vector to CSS numbers once, after all sources. General
context ranges were calibrated on 1,024 random sequences through length 32 and
held out on 256 more. A 1.5 margin leaves a tiny held-out clipping tail. The
preferred 2.0-margin, 12-bit packet stores four values in each of 192 containers
and has 0.000216 held-out context RMSE, 0.001023 maximum error, and no clipping.

With that general 12-bit packet, the real HVAR `768 -> 768` output projection
and residual take 1.092/1.843/3.027/7.090 seconds at 2/4/8/16 tokens. Transport
adds only 0.00061-0.00072 residual RMSE and clips no held-out values. A shaping
ablation shows that disabling variation-axis arithmetic saves only 9-10%, while
replacing the custom fonts with a system font still leaves 79-87% of wall time.
The remaining cost is therefore the browser's element/dependency/layout graph,
not primarily the matrix multiplication.

## Rejected: bilinear composed QK font

The `experiments/composed-qk-probe` experiment fused one `768 -> 64` key
projection and the following query/key dot product into four 256-axis variable
fonts. For a 16-token, one-head fixture this reduced each source from 192 key
glyphs to four glyphs, but moved the work into 197,120 bilinear HVAR regions.

Fresh-page Chrome measurements (seven rounds, fonts awaited) were:

| Backend | Warm median | RMSE | Maximum error |
| --- | ---: | ---: | ---: |
| Direct K geometry | 251 ms | 0.000220 | 0.000400 |
| Composed QK TTF | 1,036 ms | 0.170557 | 0.300005 |

The composed font is **4.13x slower** despite using far fewer DOM objects. Each
raw font is about 72 MB, and Chrome rejects the approximately 136 KB WOFF2 form
after its extreme variation table expands. This rules out trading glyph count
for a quadratic number of HVAR regions. Future object reductions must keep font
variation work linear in the matrix coefficients.

## Flat versus recurrent value reduction

The online-softmax scores do not require a 768-value numerator after every
source. Keeping the small set of per-head scores and reducing all weighted V
values once removes most intermediate accumulator objects while preserving the
same stable softmax equation.

Matched five-round warm medians were:

| Context | Recurrent geometry | Flat final reduction | Speedup |
| ---: | ---: | ---: | ---: |
| 2 | 1.092 s | 1.060 s | 1.03x |
| 4 | 1.807 s | 1.608 s | 1.12x |
| 8 | 3.062 s | 2.576 s | 1.19x |
| 16 | 7.127 s | 6.270 s | 1.14x |

At 16 tokens the flat page has 27,392 `i` elements rather than 38,912, a 29.6%
reduction. The smaller runtime gain shows that the surviving K/V metric boxes
and their dependency edges dominate. The flat reducer is now the preferred
attention path.

Inlining those weighted sums directly into the 12-bit packet is not better at
scale. It improves 2/4-token runs to 0.984/1.568 seconds, but grows to
2.666/7.033 seconds at 8/16 tokens because the long expressions are duplicated
inside packet sizing. One explicit geometry boundary is cheaper than repeated
deep expressions.

A second alternative replaced projected K glyphs with native CSS calculations.
It was correct but required a shared 23 MB rule containing 589,824 terms per
source. It took 3.013 seconds at two tokens and 6.811 seconds at four, versus
1.060 and 1.608 seconds for font K. Native CSS dense score evaluation is
therefore rejected.

## Current winner: shallow source graph

The largest valid improvement came from changing graph topology rather than
the arithmetic. Every source now owns a sibling K/V and score stage. One final
reducer scopes all score timelines and performs the weighted V reduction. This
removes the deep chain in which each source inherited every earlier source's
state while preserving the same HVAR rows, softmax, and 12-bit context packet.

Five-round warm results with the real output projection were:

| Context | Shallow siblings | Browser residual RMSE |
| ---: | ---: | ---: |
| 2 | 0.785 s | 0.000770 |
| 4 | 1.376 s | 0.000947 |
| 8 | 2.100 s | 0.001141 |
| 16 | 3.889 s | 0.000852 |
| 32 | 10.342 s | 0.000899 |

A matched nine-round 16-token comparison measured 5.684 seconds for nested
flat reduction and 3.895 seconds for siblings, a 1.46x speedup. The 32-token
curve still bends: attention-only takes 8.39 seconds and the full page 10.32
seconds. A fixed independent projection adds 1.71 seconds, while making that
projection depend on the live attention vector adds only another 0.22 seconds.
The long-context penalty is therefore broad layout work rather than one bad
cross-stage edge.

At 16 tokens, normal shaping takes 3.890 seconds, disabling variation axes
takes 3.349 seconds, and replacing the custom font with a system font still
takes 3.139 seconds. Roughly 81% of the time remains after font arithmetic is
removed. The actual layout boxes and dependency traversal are the current
bottleneck.

## Additional rejected reductions

- A horizontal/vertical pseudo-element carrier cuts 16-token `i` nodes from
  27,392 to 15,104, but takes 6.43 seconds versus 6.27 seconds. Pseudo-elements
  still create layout boxes.
- Shifting both inputs of the exact composed-QK font cuts regions per source
  from 197,120 to 50,176, but remains 2.38x slower than direct K and has 0.259
  RMSE. Chrome still rejects the compressed WOFF2.
- Query-coordinate binning loses too much checkpoint behavior: four-bit bins
  give 0.0285 projected residual RMSE and 94.9% attention-winner agreement;
  five-bit bins give 0.0149 and 97.6%, while multiplying stored key rows.
- Per-head SVD confirms that the checkpoint maps are effectively full rank.
  Rank 63 of 64 has 0.0618 residual RMSE for only 1.6% fewer boxes.
- Four-output 12-bit packets for the final projection take 3.917 seconds versus
  3.895 seconds for timelines and are less accurate.
- Per-source `size`, `layout`, and `style` containment measures 3.93-3.98
  seconds versus a 3.92-second control.

## HVAR-to-SVG raster handoff

A new hybrid flattens 4,608 real two-token QKV outputs into a 64x72 SVG raster.
The accurate grouped form has 0.00572 QKV RMSE and a 296 ms seven-round warm
median. It proves that HVAR geometry can be converted to one compact raster
without thousands of timelines.

That surface is not reusable by SVG attention in the tested Chrome path.
Feeding 72 independently filtered row fragments into a second filter makes all
Q/K dot products collapse to zero, so the probabilities become approximately
0.5. A monolithic sampler is slower and less accurate (about 657 ms and 0.0325
QKV RMSE). Fusing the sampler and attention into one filter did not complete in
more than three minutes. This rejects the hybrid as a current attention backend:
the bulk one-way handoff is real, but Chrome still lacks a cheap reusable raster
boundary for the next arithmetic stage.

## Live MLP-tail connection

The shallow-sibling attention was connected directly to a real GPT-2
`LN2 -> 768x3072 FC -> GELU -> 3072x768 projection -> residual` tail. The tail
alone remains near 1.03 seconds, but the valid connected page takes 2.963,
4.299, 6.822, and 14.194 seconds at 2, 8, 16, and 32 tokens. The corresponding
dependency premium above the sum of the isolated stages grows from 0.964 to
2.699 seconds.

Materializing the 768-value boundary with fresh view timelines makes the page
slower rather than isolating it: +0.142 seconds at two tokens, +0.857 at eight,
and +2.277 at sixteen. Direct inheritance remains the best connection tested.
See `GEOMETRY_FULL_TAIL.md` for correctness checkpoints and reproduction.

Packing the boundary does not reverse this result. Four 9-bit values per
carrier reduce the count to 192 timelines but lose accuracy and show no
consistent speedup. Two independent 12-bit `left`/`width` values reduce it to
384 timelines with acceptable accuracy, yet remain 0.430/1.119 seconds slower
than direct inheritance at 8/16 tokens. Packing two 12-bit values into one huge
width fails because timeline progress loses the low-order geometry digits.

Deferring the MLP subtree does not remove the connected cost either. A strict
CSS style-query gate keeps it at `display:none` until the last attention output
exists, but is 0.119/0.316 seconds slower than direct connection at 8/16
tokens. The browser performs extra lifecycle passes when the subtree appears;
the expensive dependency work is postponed, not eliminated.

Warm mutation is materially better than rebuilding the page. At sixteen
tokens, changing the live query and newest K/V source takes 2.38 seconds for
attention and 3.68 seconds through the connected MLP, versus 4.02 and 6.47
seconds for warm-cache navigation. This validates persistent K/V reuse as the
right generation architecture, although the query still has to rescore every
past token and remains superlinear in browser layout work.

Combining token sources into fewer score tracks makes both navigation and warm
mutation slower. At sixteen tokens, the existing per-source topology takes
2.25 seconds for a query mutation; grouping 1/2/4/8 sources behind Q-reset K/V
wrappers takes 2.40/2.55/2.73/3.28 seconds, and one global track takes 4.14
seconds. The browser is using the separate tracks as useful layout partitions.
