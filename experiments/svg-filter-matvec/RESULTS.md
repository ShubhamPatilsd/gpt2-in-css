# SVG filter tensor backend

## Result

SVG filter buffers can carry a whole vector across matrix and nonlinear stages
without converting every coordinate into a CSS custom property. This is the
first tested backend to remove the geometry/timeline boundary rather than only
packing it more densely.

The working matrix primitive is:

1. Store matrix weights in an image and repeat the input vector across its rows.
2. Use arithmetic `feComposite` for pixelwise products.
3. Use `feConvolveMatrix` with an all-ones kernel to reduce each row.
4. Restrict the convolution primitive subregion to the one output strip, so the
   browser does not render unused sliding-window results.

The pages contain HTML and SVG only. Browser automation is external and is used
only to force paint, capture output pixels, and measure time.

## Platform boundary

Square unsigned probes were accurate through a 256-entry convolution kernel.
The 512- and 768-entry probes returned zero in Chrome 152. GPT-2 matrices must
therefore use 256-wide shards, just like the 256-axis variable-font backend.

| Input width | Result |
| ---: | --- |
| 4–256 | Correct; roughly 0.0011–0.0029 RMSE from 8-bit image quantization |
| 512 | Zero output |
| 768 | Zero output |

`svg-filter-fc/index.html` evaluates an unsigned 768→3,072 matrix as three
256-wide shards. It returned every output with 0.001995 RMSE. Six paints ranged
from 38 to 281 ms, with a roughly 124 ms median; GPU scheduling made cold paint
variance high.

## Real GPT-2 values

`../svg-filter-gpt2-fc/index.html` uses the actual quantized GPT-2-small FC
weights, signed post-attention layer-normalized input, learned bias, and
per-output-row weight scales. Positive and negative products travel in the red
and green channels and one convolution reduces both simultaneously.

The retained per-shard version produced:

| Measurement | Result |
| --- | ---: |
| FC preactivation max error | 0.31097 |
| FC preactivation RMSE | 0.04669 |
| Error after GELU, evaluated offline | 0.14363 max / 0.01409 RMSE |
| Warm paints after compilation | mostly 53–58 ms |

`../svg-filter-gpt2-fc/full.html` continues inside the same filter graph. A
transfer table applies GELU to the 3,072-value vertical strip, twelve projection
weight images consume it, and a 768-pixel row carries projection + bias +
residual output. No numeric CSS readback occurs between the matrices.

| Measurement | Result |
| --- | ---: |
| Full MLP output max error | 3.2115 |
| Full MLP output RMSE | 0.4145 |
| Output range | about -72 to 104 |
| Cold navigation + forced paint median | about 286 ms |
| Same-page input swap median after first transition | about 103 ms |

The input-swap benchmark alternated six `feImage` sources between two different
signed vectors. Output checksums alternated between 98,617 and 98,276, proving
that the filter recomputed rather than returning a cached screenshot.

`../svg-filter-gpt2-attention/index.html` evaluates the real composed one-token
768→768 attention affine map plus residual. Its max error was 0.4818, RMSE
0.05863, and same-page recomputation median about 34 ms.

The measured matrix budget is therefore about 137 ms warm: 34 ms attention +
103 ms MLP. Relative to the 2.24-second unpaired HVAR/timeline block, that is a
16.4× matrix-path improvement. It is not yet a full-block inference claim:
both probes currently receive precomputed layer-normalized input images, and
the attention output is not yet connected through dynamic layer normalization
to the MLP.

## Rejected variants

- Centering every signed product before convolution accumulated the 128/255
  surface midpoint error 256 times. Separating positive and negative channels
  until after reduction fixed it.
- One global FC weight scale gave 0.274 preactivation RMSE. Per-row scales cut
  that to 0.0467 without adding browser operations.
- Fusing all FC shards before convolution reduced three convolutions to one but
  raised FC RMSE to 1.28.
- Projection fusion groups of 2, 3, 4, 6, and 12 were measured. They raised full
  MLP RMSE to 0.77, 0.62, 0.69, 0.80, and 1.45 respectively and did not provide
  a stable median win. The accurate one-shard-per-convolution form remains the
  default.

## Connected block and 13× result

`../svg-filter-full-block/chain.html` connects both layer normalizations,
composed one-token attention, FC, GELU, and projection in one browser image
pipeline. The page contains no JavaScript. CSS applies five SVG filters in
sequence, and each filter consumes the previous filter's pixels as
`SourceGraphic`.

Layer normalization originally failed because its normalized variance occupied
only 1–2 of the 256 available pixel levels. The retained implementation scales
the mean and variance only after each 256-value convolution reduction, then
compensates for that scale in the following arithmetic. This reduced LN1 RMSE
from about 0.021 to 0.0066 and prevented the attention matrix from amplifying a
rounded mean.

The accurate filter chain must preserve the union of the incoming and outgoing
vector strips at every orientation-changing boundary. Its transition regions
are therefore 768×768 for attention and 3,072×768 for FC and projection. With
those regions, Chrome 152 produced:

| Stage | Maximum error | RMSE |
| --- | ---: | ---: |
| LN1 | 0.0191 | 0.00662 |
| Attention + live residual | 0.620 | 0.0945 |
| LN2 | 0.174 | 0.0473 |
| FC + GELU | 0.711 | 0.0656 |
| Full block | 8.062 | 0.688 |

The final browser output retained the activation range approximately, reaching
-66.7 to 95.8 against the reference's large positive outlier near 103.8. The
larger maximum error than the fixed-residual fixture is the accumulated effect
of carrying every residual through 8-bit image surfaces; whole-vector RMSE is
still below one activation unit.

A same-page alternating-input benchmark forced a screenshot after every source
change. The output PNG checksums alternate between two stable values, so the
browser recomputes the graph. The builder also emits an independent reference
for the negated input: the browser reached 0.775 RMSE and 8.916 maximum error
against that alternate reference. This verifies that the input residual and
the attention-to-output residual are live, rather than fixed values that merely
produce different screenshots.

Three independent 20-transition live-residual trials had warm medians of 82.74,
76.31, and 75.30 ms. The median trial is 29.4× faster than the 2.241-second
unpaired HVAR/timeline block and clears both the literal 172 ms 13× gate and the
historical 130 ms stretch threshold. Fresh navigation plus first paint remains
noisier because it includes loading and filter compilation.

The live residuals use extra spatial lanes. LN1 emits its normalized vector and
the original input on two rows. LN2 emits its normalized vector and the live
attention residual on two columns. FC emits the hidden vector on a row and
carries the residual in column 3,072. Projection reads both strips and performs
the final addition in SVG arithmetic.

## Connected transport attempts

- One monolithic 3,072×768 filter was correct in structure but took roughly
  28 seconds because Chromium allocated the large filter surface throughout the
  graph.
- Five separate SVG roots initially appeared to take about 120 ms, but a stage
  trace showed that filtered root references arrived as black pixels. That
  number was rejected.
- Referencing a filtered `<rect>` works for one handoff, as demonstrated by
  `../svg-filter-element-chain-probe.html`, but a second filtered-reference hop
  does not preserve the computed pixels reliably.
- Putting all referenced rectangles in one SVG made Chromium build a recursive
  paint graph; the test exceeded a minute and was rejected.
- A CSS filter list with small stage-local regions ran near 260 ms but silently
  kept only the intersection of adjacent regions: 256/768 LN values and
  256/3,072 hidden values reached their matrices. Its final RMSE was about 4.9
  and its activation outlier disappeared, so it was rejected.
- Nested filtered groups showed the same intersection loss.
- Enlarging only the orientation-changing transition regions preserved every
  vector, produced the accuracy table above, and retained 142 ms warm
  recomputation. This is the current implementation.

## Twelve-block gate

`../svg-filter-full-block/chain-12blocks.html` now connects all twelve genuine
GPT-2-small transformer blocks. Each block uses its own checkpoint weights and
the output pixels of one block are the input pixels of the next. The generated
assets occupy about 110 MB and the full HTML filter graph is about 1.5 MB.

Chrome 152 recomputed the twelve-block graph in a 251 ms warm median. A fresh
navigation, asset decode, filter compilation, and first paint took about 1.75
seconds. Adding the checkpoint's real final layer normalization is implemented
in `chain-12blocks-final-ln.html`.

The scale test also exposed the next correctness boundary. GPT-2 produces a few
very large residual-stream coordinates. A single range per 768-value strip
therefore leaves only 4–20 distinct 8-bit values after successive blocks. The
original fixture ended at 3.48 RMSE before final LN and 1.01 RMSE after it; the
negated-input fixture diverged to 22.41 and 7.01 RMSE respectively. The browser
selected token ID 13 for the original fixture while the independent reference
selected ID 11, so the vocabulary head must not be connected to this lossy
state yet.

Using `linearRGB` filter interpolation did not preserve extra numeric bits. It
slowed warm recomputation to about 306 ms and slightly increased final-LN error,
so sRGB remains the retained backend. Uniform activation clipping also changed
the token winner and was rejected.

A CPU quantization sweep found a narrower remedy: keep residual dimensions 138
and 447 on a separate high-range plane while encoding the other 766 dimensions
on a tighter range. That two-scale simulation preserved the reference winner
for both validation inputs without retraining. The next implementation gate is
therefore two-scale residual transport and a grouped layer normalization. Only
after that passes should the 50,257-row vocabulary head and autoregressive
feedback be attached.

This matches established outlier-aware quantization rather than inventing a
model-specific exception. [LLM.int8](https://arxiv.org/abs/2208.07339) separates
persistent outlier feature dimensions into a higher-precision multiplication,
while [OCP microscaling](https://www.opencompute.org/documents/ocp-microscaling-formats-mx-v1-0-spec-final-pdf)
assigns shared scales to smaller blocks instead of forcing a whole tensor to
share one scale. [SmoothQuant](https://arxiv.org/abs/2211.10438) moves
per-channel activation scale into adjacent weights, but GPT-2's live residual
still crosses layer normalization; that boundary requires an explicitly
scale-aware normalization in this CSS backend.

`grouped-layernorm.html` is the first browser implementation of that boundary.
The retained four-coordinate mask is 138, 378, 447, and 481. It stores the dense
coordinates and those outlier coordinates in separate RG scale planes,
calculates their mean and variance contributions separately, and joins them only
after normalization. Chrome reached 0.00989 RMSE for the original block-0
residual and 0.01211 for the negated-input residual. The probe is input-dependent
and changes when its source image changes; its values are not folded into static
biases.

The two-plane format still accumulated too much error across twelve blocks. Its
final browser state selected token 13 instead of reference token 11 for the
original fixture, and the alternate fixture also missed. An attempted RG16
packing probe established why another byte cannot simply be appended after a
calculation: Chromium quantizes each SVG-filter primitive before a computed
scalar can be split into high and low channels. The probe is retained at
`../svg-rg16-transport/index.html`.

`bucket-chain-12blocks-final-ln.html` implements the working remedy. Every live
vector uses 32 shared magnitude bands. The relevant scale is folded into each
matrix column, and layer normalization computes the weighted first and second
moments directly (`mean(x²) - mean(x)²`) instead of creating 32 separate
normalization graphs. GELU alone uses one lookup table per magnitude band. The
orientation-changing identity transport also compensates its measured 18/17
gain.

Chrome 152 completed the real twelve-block chain and final layer normalization
for both validation inputs. The final-LN RMSE was 0.735 for the original fixture
and 3.323 for the alternate fixture. More importantly, scoring the browser
vectors with the checkpoint's real embedding matrix produced token ID 11 for
the original input and token ID 477 for the alternate input, exactly matching
the independent reference. `tools/verify_svg_filter_bucketed_tokens.py` asserts
those winners rather than accepting RMSE as a proxy.

This is a correctness backend, not yet the demo backend. Its generated HTML is
about 3 MB, the current experiment directory includes roughly 310 MB of all
regular, grouped, and bucketed assets, and warm recomputation was approximately
1.1 seconds for the twelve-block state plus 3.0 seconds for the final-LN page in
the retained validation run. The next optimization target is deduplicating old
probe assets and reducing the 32 GELU lookup/mask paths without returning to a
single lossy tensor-wide scale.

## Full GPT-2 output head

`../svg-filter-output-head/connected.html` appends the checkpoint's complete
50,257×768 tied-embedding matrix to the twelve-block bucketed chain. The output
rows are divided into 197 groups of 256, so no filter surface exceeds Chromium's
working dimensions. All vocabulary rows are evaluated; this is not a reduced
vocabulary or a preselected candidate list.

The first direct version lost the alternate winner because absolute logits
spent most of the 8-bit surface range on a shared negative offset. Subtracting
the mean embedding row from every vocabulary row preserves argmax exactly and
reduced the required score range from about 177 to 28. Sorting rows by their
numeric error scale then groups similarly ranged dot products together. This
does not change any score or omit any token; `reference.json` stores the inverse
position-to-token mapping.

Chrome selected token 11 for the original browser-computed final state and token
477 for the alternate state, matching dense NumPy scoring in both cases. The
standalone head was about 1.5 seconds cold and 0.67 seconds warm in the retained
run. The fully connected transformer-plus-head page was about 10.1 seconds cold
and 10.3 seconds after changing the source input. Its two generated HTML pages
total about 7.9 MB, its live PNG assets are about 49 MB, and the complete cleaned
experiment directory is about 57 MB.

A single 768-wide convolution would remove two quantized partial-sum boundaries,
but Chromium returned an empty surface for `feConvolveMatrix order="768 1"`.
Doubling the number of groups or adding a second dithered convolution also made
the combined filter fail, even though each standalone head worked. The retained
197-group graph is therefore the current Chromium complexity boundary.

## Multi-token causal attention

`../svg-multitoken-attention/index.html` implements the nonlinear core of real
two-token, 12-head GPT-2 causal attention. For the second position it computes
both 64-value Q·K scores in every head, applies the exact two-item softmax as a
sigmoid of their difference, and mixes the two V vectors. The first position is
causally restricted to its own V vector. These probabilities and contexts are
computed by browser filter primitives; they are not constants baked into the
output image.

The retained browser run produced context RMSE 0.00111, maximum context error
0.00781, and maximum attention-probability error 0.00712 across all twelve
heads. The filter took about 0.38 seconds including navigation and screenshot.
Chromium did not reliably reduce a 64-pixel head directly. Padding each head to
the already-proven 256-pixel convolution width works, but the padded reduction
must set `preserveAlpha="false"`; otherwise the transparent target pixel erases
the valid RGB sum.

`connected-qkv.html` now begins with both 768-value normalized token states and
computes the full 768→2,304 QKV projection in the browser before entering the
same causal mixer. In the retained 256-term-shard run, the connected attention
context had 0.00791 RMSE and the largest attention-probability error was 0.0319.
The isolated graph took about 2.3 seconds including navigation and capture.

`connected-attention-residual.html` continues the live graph through the real
768→768 `c_proj` matrix and adds the current token's residual. The 768 result is
kept as twelve 64-value native-coordinate chunks because Chromium can display a
relocated or merged surface but later filter primitives sometimes read that
surface as transparent. Consuming the head and output chunks directly avoids
that false handoff. The browser test selects each chunk independently and
checks all 768 values.

An exact-input projection fixture now separates QKV error from projection error.
Before range bucketing, the projection had 0.20696 RMSE even when its Q, K, V,
and attention inputs came from reference images; the live-input version was
0.20855 RMSE. QKV error was therefore not the main cause of the failed block.
The problem was the projection's per-output scale transport. Within one 64-value
chunk, the largest required scale was as much as 1,310 times the smallest. An
8-bit scale image rounded eleven of those dimensions to zero or one.

The projection now divides output rows into power-of-two range bands. Rows in a
band share the expensive dot-product pass, and non-overlapping band results are
combined afterward. A fixed budget of 32 bands is the largest connected graph
that remained reliable in Chromium. The retained allocation reduced exact-input
projection RMSE to 0.03032 and live-input projection RMSE to 0.03571, with a
0.2361 maximum live error. Changing residual addition from one 768-value scale
to twelve local 64-value scales reduced final residual RMSE from 0.05423 to
0.03744 and its maximum error from 0.6619 to 0.2261. The retained test took
about 3.7 seconds for the isolated exact-input projection, 13.0 seconds for the
live projection, and 15.2 seconds for the chunk-by-chunk residual validation.
All three measurements include twelve screenshots and are not token rates.

Narrowing every range band further improved the isolated projection to 0.02861
RMSE, but increased the graph from 32 to 45 bands. The connected graph then
returned corrupted values at 0.239 RMSE and took about 19 seconds. Even adding
only a 33rd band caused the same failure. This is a browser graph-complexity
boundary, not an arithmetic trade worth retaining.

Several correction transports were tested and rejected. A separately normalized
coarse-weight and weight-error dot product was mathematically accurate before
rendering, but its small correction coefficient rounded away when converted
back through an 8-bit SVG surface. Packing the two results in separate color
channels preserved the correction itself, but using one accumulator scale for
all 64 rows increased ordinary dot-product rounding and made QKV worse. A
one-pass two-byte high/low scale image also failed because rescaling the low byte
creates another sub-1/255 intermediate that Chromium rounds to zero.

`../svg-magnitude-plane-dot/index.html` isolates a real 64x64 `c_proj` slice and
compares three magnitude-plane encodings against the ordinary signed RG dot
product. The ordinary path had 0.01738 RMSE. A centered RGB plane path had
0.02176 RMSE, a positive/negative path with one shared accumulator scale had
0.01971 RMSE, and independently scaled planes had 0.02133 RMSE. Extra stored
weight digits therefore do not solve this dot product: product and accumulator
surface quantization dominate, and combining multiple planes adds more rounded
boundaries.

The useful correction point was narrower. Some QKV outputs used less than 1%
of their 64-row group's scale range, so their final scale image had only one or
two meaningful codes. Encoding that scale as an 8-bit coarse value plus a
separately normalized 8-bit remainder reduced isolated QKV RMSE from 0.03028 to
0.02239 when enabled everywhere. Applying it only to Q and K groups whose scale
fell below 4% retained most of the benefit: QKV RMSE 0.02404, maximum error
0.2380, and roughly 0.8 seconds for the isolated validation instead of 0.61
seconds. V remains on the ordinary path because it was already accurate and is
consumed directly by the projection.

Appending even the selective correction to the monolithic QKV-to-projection
filter exposed another Chromium dependency-graph boundary. The named QKV
surfaces were correct, but late projection chunks became unreliable. The staged
pages fix that structurally: `attention-projection-staged.html` renders the
72-row QKV surface with one filter, then a second filter consumes it as
`SourceGraphic` and performs attention plus projection. The corresponding
`connected-attention-residual-staged.html` continues through residual addition.
With 31 projection range bands, staged projection RMSE was 0.03771 and residual
RMSE was 0.03924. Twelve-capture validation took about 8.8 and 9.2 seconds,
respectively, versus about 19.8 and 18.3 seconds for the stable monolithic
comparison run. Those totals force twelve separate renders and are not
single-inference latency or token rates.

These errors are primarily 8-bit materialized-surface quantization and clamping,
not ordinary IEEE floating-point roundoff. That distinction matters: the
expanded `svg-16bit-precision` probe creates `1/65535` directly with `feFlood`
and successfully amplifies it to a visible value when the flood and color
matrix can be fused. Passing the same value through `feOffset`,
`feConvolveMatrix`, `feComponentTransfer`, or `feComposite` first reduces it to
zero; `feTile` remains fuseable. A 16-bit PNG source also becomes identical to
its 8-bit version before filter math. Switching among `sRGB`, `linearRGB`, the
default interpolation mode, forced GPU rasterization, scRGB-linear display, and
HDR10 display did not change that result.

`svg-magnitude-plane-dot` also tests putting full-precision weights directly in
64 separate `feConvolveMatrix` kernels, avoiding the quantized weight-image
product surface. Its RMSE was 0.02392 because the activation source was still
8-bit. Representing each activation with four dithered pixels and averaging all
four inside a 256-tap kernel improved that direct path to 0.02237, but still did
not beat the ordinary range-scaled path's 0.01738 and used four times the input
pixels. This demonstrates that spatial oversampling can recover bits, but not
cheaply enough to replace the retained backend.

The practical remedies are independently scaled range groups,
coarse-plus-remainder transport only at narrow high-loss boundaries, explicit
filter-stage boundaries, and—where the graph budget permits—moving constants
into a primitive's numeric attributes so multiplication and accumulation happen
before a materialized surface. Whole-matrix bit planes and spatial oversampling
are too expensive for the measured accuracy they recover. A true general fix
would require Chromium to expose an F16 SVG-filter backing format; display HDR
flags do not select one for this path.

### Quantization-strategy screen

`tools/analyze_svg_quantization_strategies.py` runs the real tied output head
after all twelve one-token GPT-2-small blocks while approximating the SVG
backend's 8-bit activation surfaces and normalized 8-bit weight images. It is a
screening model, not a substitute for Chromium validation. The two retained
fixtures have reference winners 11 and 477.

The screen rejected SmoothQuant-style per-channel rescaling for this backend.
Across the tested 4-, 8-, and 16-group layouts, alpha values from 0.25 through
1.0 increased final error compared with no rescaling. Reducing activation
outliers was outweighed by the extra error created when the inversely rescaled
weights were converted to normalized 8-bit PNGs. Logarithmically uniform range
groups also consistently beat naive k-means clustering of log ranges.

The offline screen predicted that 16 logarithmic groups might retain both token
winners, so 16 and 24 groups were generated and tested in Chromium. Both failed:
16 groups changed the alternate winner from 477 to 410, while 24 groups changed
the original winner from 11 to 13. The retained 32-group page again selected 11
and 477. Aggregate RMSE did not reliably predict these failures.

| Groups | Final-page HTML | Referenced PNGs | Filter primitives | Token result |
| ---: | ---: | ---: | ---: | --- |
| 16 | 2,953,494 bytes | 80,604,392 bytes | 9,231 | alternate failed: 410 vs 477 |
| 24 | 3,327,892 bytes | 80,615,589 bytes | 9,999 | original failed: 13 vs 11 |
| 32 | 3,703,034 bytes | 80,506,949 bytes | 10,767 | both passed: 11 and 477 |

This shows that fewer range groups reduce HTML and filter-graph size but barely
affect the weight-dominated image payload. The rounding error is non-monotonic
because changing group boundaries changes many later materialized values. The
32-group layout remains the smallest tested layout that passes both browser
fixtures; selective correction at demonstrably lossy boundaries remains safer
than duplicating every tensor plane.

### Prompt-robustness and boundary localization

The original 32-group graph was calibrated from `Hello` and its negation. A
16-token check showed why that proof did not generalize: 15 inputs exceeded the
first image's per-coordinate ranges, and Chromium retained only 11 of 16 output
token winners. Recalibrating the input surface across those 16 tokens removed
all input clipping but still retained only 11 winners; it changed which cases
failed instead of solving the downstream quantization problem.

The expanded check takes 64 distinct GPT-2 tokens from short natural story
sentences. This remains a one-token model test, not a claim that the current
graph handles the full sentence as context. With the input surface calibrated
on all 64 values, Chromium matched 34 of 64 reference winners. No input value
clipped. Mean final-state RMSE was 0.48360, and mean warm render time was 1.544
seconds. Full per-token results are in
`../svg-filter-full-block/natural64-browser-report.json`.

Stopping the actual Chromium chain after each block, then running only the
untouched suffix numerically, localized five representative ranking changes.
The first harmful surfaces were: block 1 output for `I`, block 8 output for
` a`, block 1 MLP hidden output for ` This`, block 1 LN2 output for `This`, and
block 5 output for ` little`. Sparse exact-value intervention restored three
cases with one or two coordinates and the two `This` cases with four
coordinates at their specific internal surfaces. These interventions are a
screening result, not an implemented browser correction plane. The measurements
are recorded in `../svg-filter-full-block/failing-surface-report.json`.

An offline screen then calibrated all 110 materialized activation surfaces on
the same 64-token set while retaining 32 logarithmic range groups. It preserved
61 of 64 winners, with final-state RMSE 0.16337. This result is not yet Chromium
validation, but it changes the implementation order: calibration must cover
every internal surface before adding correction planes. A global correction
for dimensions 138 and 447 would overfit the earlier fixtures because the
larger suite also exposes LN2 and 3,072-wide MLP-hidden failures.

The generator now accepts a batch of calibration token IDs and propagates all
of their states through every scale decision. This changes build-time range
selection only; the generated page still uses 32 groups and the same runtime
graph. Actual Chromium accuracy improved from 34/64 to 52/64, while mean warm
render time remained effectively flat (1.544 to 1.532 seconds). Aggregate RMSE
rose to 0.76974, another demonstration that the winner is a better acceptance
metric than average coordinate error. The browser results are in
`../svg-filter-full-block/natural64-batch-calibrated-browser-report.json`.
This calibration is not retained as the default: an explicit anchor recheck
changed the original `Hello` winner from 11 to 13. Future calibration reports
must separate calibration and held-out tokens and must retain the original
positive and negative fixtures as acceptance gates.

The twelve residual failures were traced through every block and then through
the five surfaces inside the earliest harmful block. Four first fail at the
3,072-value MLP hidden surface, four at a block output, three at an attention
residual, and one at LN2. Restoring the largest-error coordinates required from
1 to 1,536 values depending on the case. Selective correction is therefore
valid for a few cases but is not yet a general fix. The full traces are in
`../svg-filter-full-block/natural64-boundary-report.json` and
`../svg-filter-full-block/natural64-failing-surface-report.json`. The next
accuracy work should target the three repeated transport types and validate on
held-out tokens; weight compression remains deferred until rankings stabilize.

`../svg-16bit-precision/index.html` tests native 16-bit PNG samples directly.
Chrome produced the same result for the 16-bit and 8-bit sources: values below
one 8-bit step became zero before filter arithmetic. PNG can legally carry
16-bit samples, but this SVG path does not preserve them. The remaining useful
directions are therefore (1) compact range bucketing that stays below the graph
limit, (2) bit-serial or magnitude-plane products that sum before rescaling, or
(3) a spatial/unary representation that trades pixels for accumulator precision.
LN2, MLP, twelve-block repetition, and in-page argmax/token feedback remain
unconnected until the live residual is reliably below the precision gate.

## RGB group packing update

A later browser experiment rejected affine bias correction as a general fix,
but found a useful performance direction. Three independently scaled GELU
range groups can share the R, G, and B channels of one filter branch. With 32
groups this reduced a warm twelve-block pass from 1.299 seconds to 0.714
seconds, while winner accuracy changed from 46/64 to 44/64. Reducing the model
to eight groups reached 0.622 seconds but only 10/64 winners, so channel packing
has a much better speed/accuracy tradeoff than deleting scale groups. Full
method, reports, and caveats are in
`../svg-filter-bias-correction/RESULTS.md`.

Spatially batching all twelve two-token attention heads produced a different
kind of win. The retained mixer reduced top-level primitives from 615 to 116
and its referenced runtime bundle from 540 KB to 53 KB, while remaining
accurate. Warm latency was unchanged at about 140 ms, proving that convolution
and raster work—not repeated markup—dominate this mixer. Details and rejected
layouts are in `../svg-multitoken-attention-batched/RESULTS.md`.

Connecting that compact mixer to the live QKV graph by relocating and merging
72 named result surfaces failed. Chromium emitted zero probabilities and warm
latency increased from 1.44 to 2.38 seconds despite a smaller graph. The
connected failure is retained and documented in
`../svg-connected-batched-attention/RESULTS.md`; live inference should preserve
head-local dependency surfaces until a different transport exists.

Stage profiling of the successful 32-group RGB-packed chain identified FC/GELU
as the remaining dominant isolated stage. A new vector-wide re-encoding maps
the 3,072 preactivations onto four shared GELU scales with one ratio image and
one arithmetic filter, while retaining 32 groups everywhere else. It reduces
GELU from eleven RGB passes to two. In Chromium it cut warm time from about
714 ms to 469 ms on the calibration suite and retained 61/84 held-out output
winners versus 63/84 for the 32-band control. The four-band page is 2.77x
faster than the original 1.299-second separate-branch graph. Two bands fell to
30/64 winners, establishing the current accuracy cliff. Full results are in
`../svg-filter-bias-correction/RESULTS.md`.

## Standards

- Filter Effects Level 1: https://www.w3.org/TR/filter-effects-1/
- `feConvolveMatrix`: https://www.w3.org/TR/filter-effects-1/#feConvolveMatrixElement
- arithmetic `feComposite`: https://www.w3.org/TR/filter-effects-1/#feCompositeElement
- PNG 3, including 16-bit sample depths: https://www.w3.org/TR/png-3/
- Low-bit quantization with multiple low-precision tensors:
  https://arxiv.org/abs/1902.06822
