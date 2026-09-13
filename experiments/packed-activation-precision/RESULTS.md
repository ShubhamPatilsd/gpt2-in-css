# Packed activation precision

## Question

How far can the 3,072-value GPT-2 MLP boundary be compressed before either
model accuracy or Chromium's view-timeline geometry becomes unusable?

Runtime fixtures contain HTML and CSS only. JavaScript is used only by the
external Playwright measurement harness.

## Twelve-block numerical screen

The screen uses all twelve GPT-2-small blocks, signed 9-bit row-quantized
weights, and the real tied output head. Calibration and evaluation use
disjoint sets of 256 one-token states; 64 evaluation states come from natural
prompt tokens. This is not yet multi-token causal attention.

Uniform precision at every transported residual, hidden, and block-state
boundary produced:

| Bits per value | Exact top-1 token | Natural subset | In reference top 5 |
| ---: | ---: | ---: | ---: |
| 4 | 68.8% | 68.8% | 94.9% |
| 5 | 84.8% | 75.0% | 100% |
| 6 | 86.3% | 81.3% | 99.6% |
| 7 | 91.0% | 84.4% | 100% |
| 8 | 93.8% | 84.4% | 100% |
| 9 | 94.1% | 87.5% | 100% |
| 10 | 95.3% | 89.1% | 100% |

Keeping the 768-wide residual/state path continuous and quantizing only the
3,072-wide post-GELU vector is much more favorable. With fixed per-channel
asymmetric calibration ranges:

| Hidden allocation | Implied FC timelines | Exact top-1 token | Natural subset | In reference top 5 |
| --- | ---: | ---: | ---: | ---: |
| uniform 6-bit | 512 | 94.5% | 87.5% | 100% |
| importance 5/6/6 | 512 | 94.9% | 87.5% | 100% |
| low half 5-bit, important half 8-bit | 640 | 94.5% | 89.1% | 100% |
| low half 4-bit, important half 8-bit | 640 | 93.4% | 87.5% | 100% |

The 5/8 layout uses six low-importance values and four high-importance values
per timeline. It was subsequently implemented as a real browser page.

## Real Chrome block

Chrome 153 loaded complete block-0 pages in rotating order. Each measurement
waits for fonts and two animation frames, then reads all 768 final CSS numeric
outputs. A focused eight-round comparison retained seven warm samples for the
three useful frontier points:

| FC payload | Timelines | Warm median | Block RMSE | Maximum error |
| --- | ---: | ---: | ---: | ---: |
| proven packed four | 768 | 1,034.3 ms | 0.0310 | 0.1599 |
| heterogeneous 5/8 | 640 | 957.2 ms | 0.1326 | 0.3755 |
| uniform 6-bit, six values | 512 | 881.9 ms | 0.1220 | 0.8310 |

The heterogeneous page is valid but not a useful frontier: it is only 7.5%
faster than packed four, while uniform six is 14.7% faster and has slightly
lower average error. Heterogeneous 5/8 does halve the maximum error relative to
uniform six, but it still has four times packed-four's average error.

A separate four-round exploratory sweep records the rejected 512-timeline
variants in `browser-results-all.json`. Mixed 4/5/7 had 0.1862 RMSE, uniform
seven 0.2438, per-channel asymmetric six 1.2404, and importance-aware 5/6/6
3.6682. Timing differences among those equally sized pages were small compared
with their correctness differences.

## Packed block-state output

The next experiment compressed the 768-value block output itself rather than
only the 3,072-value hidden layer. Four output values share one timeline: two
8-bit values and two 9-bit values. Channels are paired by calibrated range so
the wider-range half receives 9 bits. This keeps the output stage at 192
timelines instead of 768.

An eight-round rotating Chrome 153 run retained seven warm samples:

| Block output transport | Total block timelines | Warm median | Block RMSE | Maximum error |
| --- | ---: | ---: | ---: | ---: |
| numeric output baseline | 1,536 | 1,048.8 ms | 0.03101 | 0.15988 |
| per-channel symmetric 8/9-bit, 1.5x headroom | 960 | 925.7 ms | 0.03896 | 0.22096 |
| per-channel asymmetric 8/9-bit, 1.5x headroom | 960 | 960.3 ms | 0.03777 | 0.15304 |

The asymmetric packet is the best accuracy-preserving transport: it removes
37.5% of all block timelines, is 8.4% faster, and its maximum error is slightly
lower than the numeric baseline. The symmetric packet is the faster operating
point at 11.7%, with a modestly larger maximum error.

The old global signed-square output packet also used 960 timelines, but had
0.22193 RMSE and 2.82066 maximum error. Per-channel ranges therefore improve
average error by roughly 5.9x without adding browser objects. Increasing the
packet to 9/10 bits enlarged its geometry fourfold and worsened browser RMSE to
0.04715; extra nominal precision was lost to view-timeline reconstruction.
That branch is rejected.

The stable reports are `browser-results-output-transport-final.json` and
`browser-results-output-channel89-asym-final.json`.

## Live cross-block reuse

`../gpt2-block-css/view-timeline-two-block-attention-probe.html` connects the
browser-produced 768-value output of block 0 directly to block 1 LayerNorm and
the real quantized block-1 composed attention map. The values cross the boundary
through inherited registered CSS properties. No harness readback, fixed
replacement activation, or JavaScript exists between the two computations.

An eight-round rotating Chrome 153 run retained seven warm samples:

| Page | Warm median | RMSE | Maximum error |
| --- | ---: | ---: | ---: |
| packed block 0 only | 868.7 ms | 0.03834 | 0.23108 |
| isolated block-1 LayerNorm + attention residual | 311.9 ms | 0.00055 | 0.00382 |
| connected block 0 → block-1 attention residual | 1,394.7 ms | 0.03826 | 0.19132 |

The second matrix does not amplify the state-packet error: connected RMSE is
essentially the input RMSE. The connected page is about 214 ms, or 18%, slower
than the sum of the two isolated medians. That is the measured cost of resolving
the extra live dependency boundary at this depth. It is material but not yet a
superlinear failure.

This proves the transport is genuinely reusable. The attention-only browser
report is `../packed-activation-precision/two-block-attention-browser.json`.

## Two complete live blocks

`../gpt2-block-css/view-timeline-two-block-full.html` extends that same live
chain through block 1's second LayerNorm, 768→3,072 FC, GELU, 3,072→768
projection, and residual. Its 3,072 post-GELU values are individually
materialized. `view-timeline-two-block-full-packed4.html` instead puts four
post-GELU values into each geometric carrier and decodes them directly in the
projection font settings. Neither page contains JavaScript or replaces the
browser-produced block-0 state.

A four-round rotating Chrome 153 run measured:

| Complete block-1 transport | Total live timelines | Isolated block 1 | Connected two blocks | RMSE vs block reference |
| --- | ---: | ---: | ---: | ---: |
| 3,072 materialized hidden numbers | 5,568 | 1,760 ms | 5,033 ms | 0.03712 |
| four-value post-GELU packet | 3,264 | 1,275 ms | 3,921 ms | 0.05490 |

The packed form removes 41.4% of the timelines, makes the isolated second
block 27.6% faster, and makes the complete connected chain 22.1% faster. Its
pure packet approximation contributes 0.01922 RMSE; the complete browser
result remains finite in all 768 channels and has 0.05490 RMSE. The incoming
packed block-0 state has 0.03834 RMSE, so neither complete implementation shows
catastrophic two-block error growth.

The important negative result is latency scaling. The materialized connected
page takes about 2.31 seconds longer than the sum of the isolated block-0 and
block-1 medians. Even the packed page retains about 1.69 seconds of excess
dependency cost. Counting only isolated work gives an unrealistically
optimistic lower bound near 15 seconds for twelve packed blocks, before the
output head. Therefore four-value packing is the current constant-factor
winner, but the timeline dependency chain is still not a scalable GPT-2
backend.

The complete report is `two-block-full-browser.json`.

### Decoding directly versus caching 3,072 CSS numbers

The packed projection normally uses each decoded activation expression directly
as a font-axis value. A second fixture registers all 3,072 decoded activations
as inherited CSS numbers first, then lets the projection read those simpler
variables. This tests whether repeated expression resolution or CSS-state
materialization is more expensive without changing the timelines or result.

A six-round comparison produced bit-identical final vectors:

| Packed decode | Connected median | Isolated median | Combined CSS |
| --- | ---: | ---: | ---: |
| direct expression | 4,107 ms | 1,246 ms | 5.78 MB |
| cached registered numbers | 4,300 ms | 1,414 ms | 6.13 MB |

Caching is 4.7% slower in the connected chain and 13.5% slower in isolation,
while adding 350 KB of CSS. Registered inherited properties are not a useful
memoization layer here; keep compact decoded expressions inside the consuming
font settings. The report is `two-block-packed-cache-browser.json`.

The per-channel and importance encodings look good in numerical simulation but
fail in the actual six-value carrier. Their larger, less uniformly occupied
packets amplify view-timeline reconstruction error. An earlier carrier window
also allowed some subjects to begin outside the viewport, yielding zero/zero
milestones; sizing the window from the packet's real maximum fixes that failure
but not the underlying geometric precision loss.

### Nonlinear and unequal six-value encodings

A larger held-out screen evaluated 1,024 states through all twelve blocks while
quantizing only the post-GELU vectors. Shifted logarithmic companding with
six-bit codes and 2x range headroom improved exact next-token agreement from
95.80% for linear asymmetric codes to 96.68%. Unequal 4/6/8-, 5/6/7-, and
4/7/7-bit allocations did not beat the uniform linear baseline, even when
channels were ranked by calibrated range times projection norm.

The logarithmic result did not survive the browser carrier. With the same 512
FC timelines, Chrome measured:

| Six-value encoding | Warm median | Block RMSE | Maximum error |
| --- | ---: | ---: | ---: |
| linear per-channel asymmetric | 865.1 ms | 1.2404 | 6.5795 |
| shifted log, mu=4 | 885.6 ms | 1.4360 | 14.0210 |

The exponential decoder magnifies small recovered-code errors at the high end.
This is another case where a better abstract quantizer is worse after geometric
transport. The validation data is in `log-validation.json`; the browser run is
in `browser-results-logasym4.json`.

### Sensitivity tiers, range clusters, and a seventh value

A 416-timeline carrier assigned 3/4/5/6 bits to sensitivity-ranked channel
quartiles. Numerically, per-channel ranges retained 974 of 1,024 held-out
next-token winners (95.12%) and 57 of 64 natural cases. In Chrome, however, the
same block had 0.8260 RMSE and 9.232 maximum error. Its 845.8 ms warm median was
only 5.0% faster than the 889.9 ms uniform-six control. Per-channel affine
decoding again amplified small geometry-code errors.

Sharing ranges avoids that amplification but loses too much model information.
One range per precision tier retained only 71.39% of held-out winners. Sorting
channels by calibrated span and using 2, 4, 8, 16, or 32 range clusters improved
agreement to 80.47%, 84.18%, 88.09%, 91.89%, and 92.58%, respectively, but none
reached the 95.12% per-channel result. Range clustering therefore moves along
the same accuracy-versus-carrier-error tradeoff rather than escaping it.

A separate packet tested whether the geometry could carry more useful bits
instead. It placed seven activations on one timeline: two low-sensitivity
values at five bits and five values at six bits. This would reduce the FC from
512 to 439 timelines. The four-digit side requires a 23-bit coordinate. With a
two-pixel guard it produced 45.24 block RMSE; halving the coordinate scale still
produced 44.63 RMSE. Making the viewport wider than the subject fixed the
entry/cover overlap, but RMSE remained 20.75 with 116.13 maximum error. Its
882.7 ms median was within 2% of the 898.4 ms uniform-six control. This is a
measured geometry-precision ceiling: the current view-timeline inversion is
usable near 18 guarded bits per coordinate, not 23 bits.

The reports are `browser-results-sensitivity3456.json`,
`browser-results-packed7-56.json`, `browser-results-packed7-56-scale1.json`,
and `browser-results-packed7-56-wideviewport.json`.

### Chromium dependency trace and engine ablations

Chrome tracing separated layout dependency work from font shaping for warmed
pages:

| Fixture | Wall time | Completed layout events | Style recalculation | Font shaping |
| --- | ---: | ---: | ---: | ---: |
| packed block 0 | 0.923 s | 0.509 s | 0.178 s | 0.093 s |
| packed block 1, isolated | 1.203 s | 0.369 s | 0.602 s | 0.138 s |
| two connected packed blocks | 4.062 s | 2.256 s | 1.302 s | 0.350 s |

The connected page contains one 1.747-second forced layout during parser
completion. Trace categories overlap, so their columns should not be summed,
but the comparison is decisive: the superlinear connected cost is mainly
layout/style dependency resolution; font shaping is secondary. The raw trace
summary is `dependency-trace.json`.

Focused ablations did not remove that cost. `contain: style` was
indistinguishable from baseline at roughly 3.54 seconds. Preloading all 36 WOFF2
files made the median worse, from 3.49 to 4.16 seconds. Removing LayerNorm
registrations did not help, while removing block-state or all intermediate
registrations slowed the chain to roughly 4.45-4.49 seconds. Typed state
boundaries cost properties, but they also keep inherited expressions from
growing without bound.

## Decision

- Keep packed four as the accuracy baseline.
- Keep uniform six as the aggressive 512-timeline speed baseline.
- Reject heterogeneous 5/8 as a preferred implementation: its small speed gain
  does not compensate for its error and additional machinery.
- Reject uniform seven and six-value per-channel/mixed-radix encodings in their
  current geometry form.
- Reject shifted-log and unequal importance-bit six-value encodings for the
  current carrier. They do not improve the measured browser frontier.
- Reject the 416-timeline 3/4/5/6 sensitivity carrier and its shared-range
  variants: the small speed gain does not survive their browser/model error.
- Treat six values / roughly 18 guarded bits per geometric coordinate as the
  current reliable packing ceiling. The seven-value 23-bit carrier is invalid.
- Use asymmetric per-channel 8/9-bit packets when a following block needs a
  reusable 768-value state; use the symmetric form only when minimum latency is
  more important than maximum error.
- The asymmetric packet is now proven across a live block boundary; continue
  with it at block boundaries.
- Use four-value post-GELU packing inside the MLP: it reduced complete
  two-block latency by 22.1% and is the best measured full-chain variant.
- Do not materialize the packed hidden vector as 3,072 registered properties;
  direct decoding is faster and smaller with identical output.
- Reject the larger 9/10-bit geometry: more packed bits do not produce more
  effective browser precision.
- None of these is the missing order-of-magnitude optimization. Even a 41.4%
  timeline reduction translated into only 22.1% complete-chain latency.
- Engine traces confirm that connected layout/style dependency resolution, not
  HVAR shaping, is the dominant remaining scaling failure.

## Reproduce

```sh
uv run --with numpy python tools/analyze_packed_activation_precision.py

VIEW_TIMELINE_PACKED6_SCHEME=uniform6 \
  uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_view_timeline_fc.py

PACKED6_BENCHMARK_ROUNDS=8 \
PACKED6_BENCHMARK_VARIANTS=packed4,heterogeneous-5-8,uniform6 node \
  tools/test_view_timeline_packed6_variants.mjs

VIEW_TIMELINE_OUTPUT_PACK_SCHEME=channel89asym \
VIEW_TIMELINE_OUTPUT_PACK_HEADROOM=1.5 \
  uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_view_timeline_fc.py

uv run --with numpy --with fonttools --with brotli --with pillow \
  python tools/build_view_timeline_two_block_probe.py

TWO_BLOCK_FULL_ROUNDS=4 node tools/test_view_timeline_two_block_full.mjs
```
