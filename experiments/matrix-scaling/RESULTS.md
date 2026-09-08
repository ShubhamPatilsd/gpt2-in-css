# Variable-font matrix scaling results

Measured in Chromium on macOS on August 26, 2026. Every test page is HTML/CSS-only.

## Browser results

| Matrix | Font layout | Browser result | Max absolute error | Runtime bundle (raw / Brotli) |
| --- | --- | --- | ---: | ---: |
| 64×64 | one 64-axis font | accepted; 64/64 outputs | 0.2383 | 34,251 B / 6,738 B |
| 128×128 | one 128-axis font | accepted; 128/128 outputs | 0.2422 | 72,801 B / 18,102 B |
| 256×256 | one 256-axis font | accepted; 256/256 outputs | 0.2420 | 168,476 B / 59,365 B |
| 257×257 | one 257-axis font | rejected before rendering | n/a | 234,656 B / 125,126 B |
| 384×384 | one 384-axis font | rejected before rendering | n/a | 434,172 B / 270,657 B |
| 768×768 | one 768-axis font | rejected before rendering | n/a | 1,383,027 B / 1,055,983 B |
| 768×768 | three 256-axis fonts | accepted; 768/768 outputs | 0.6600 | 918,889 B / 475,312 B |

The direct-compiled 768-wide sharded page took a median 217 ms over five warm end-to-end navigations. This includes HTML parsing, font loading from cache, style calculation, layout, 589,824 weight applications, and reading one result. It is not an isolated matmul benchmark.

## What was learned

### The practical browser axis ceiling is 256

The 256-axis font works and the otherwise equivalent 257-axis font does not load. The CSS declaration itself remains intact at 257 axes, so this is font-platform rejection rather than CSS parsing. This is an empirical Chromium/macOS limit, not an OpenType file-format limit: the OpenType `fvar` table stores `axisCount` as a `uint16` ([specification](https://learn.microsoft.com/en-us/typography/opentype/otspec183/fvar)).

A GPT-2-small hidden vector has width 768, so it must be represented as three 256-number shards on this path.

### Sharding works without changing the math

Each font stores all 768 output rows but only 256 input columns. For output `i`, three glyph advances encode the three partial dot products. CSS lays those glyphs next to each other and measures their combined width, which directly yields the complete 768-term dot product after subtracting three base advances.

The browser accepted all three fonts and returned all 768 numeric CSS custom properties. The maximum browser error was 0.66 font unit and the mean was 0.253. Direct evaluation of the stored HVAR data matches the NumPy result exactly; the browser error is introduced when font-unit widths are converted through pixel layout.

### A single layer should stay sharded

HTML parsing limits element nesting to 512 levels in this browser. One 2,304-step reduction chain was truncated. The working one-layer page uses three independent 256-output chains, each 259 DOM levels deep. The three 256-axis font shards remain useful for the next layer, but the three independent output branches do not.

That last sentence has an important qualification: independent size-container branches cannot later be joined with CSS anchors. `container-type` adds size containment, so anchor geometry produced inside one branch is deliberately hidden from its siblings. An isolated anchor-width merger works, but the same merger cannot cross the containers used to recover matrix results.

### Three shards can share one text run

The initial sharded backend used one element per output per font shard. A packed fallback-font run can instead contain three characters whose glyphs come from three disjoint variable fonts. Their advances add inside one measured text box, so a three-shard dot product needs no child shard elements.

Chromium only resolved the first three variable fonts when all twelve MLP shards were placed in one fallback run. Four independent three-font runs work: an eight-output, 3,072-input probe recovered all outputs with 0.61 maximum browser error. This is normal font-layout rounding at twelve summed shards.

Applied to the faithful block, packing removes every child shard element from the three-shard projections. Only the twelve-shard MLP output projection needs children: four packed runs for each of 768 outputs, or 3,072 elements total instead of 23,040.

### Two values per container make a real 768-wide chain possible

The working two-layer page carries one output in a container's width and a second output in its height. One layer therefore needs 384 nested containers instead of 768. After the first layer, four independent 192-output branches compute the final layer in 96 paired steps each. The deepest path is about 480 containers, below the HTML parser limit, and every second-layer glyph inherits all 768 first-layer values.

The chain uses two actual 768×768 `attn.c_proj` matrices from GPT-2 small, split into six 256-axis fonts. This is a matrix-backend test, not a complete transformer-block forward pass: layer normalization, QKV attention, residuals, and the MLP are not inserted between the two projections.

| Result | Value |
| --- | ---: |
| Weight precision | signed 9-bit, symmetric per output row |
| Offline HVAR vs quantized NumPy | 7.1e-14 max error |
| Chromium vs quantized NumPy | 0.0313 max error |
| Quantized chain vs original float matrices | 0.4191 max error |
| Six-font build | 8.75 s |
| Runtime bundle | 2,574,724 B raw / 1,496,572 B Brotli |

Eight-bit weights produced 0.7578 maximum error and 0.0677 RMSE after the second matrix. Nine bits reduced those to 0.4191 and 0.0308. Ten bits reduced them again to 0.1389 and 0.0144, but its worst 256-column row needs more advance-width headroom than an unsigned 16-bit OpenType metric can safely provide with the current signed-base encoding.

The generated HTML content-addresses every font URL. This prevents a rebuilt page from silently mixing new CSS bases with stale cached font weights.

### Slotted shadow roots remove the per-page depth ceiling

Declarative shadow roots alone do not reset Chromium's HTML parser depth. A 400-level outer tree followed by a 400-level shadow tree was still flattened near 512 total parser levels.

The working transport puts the next light-DOM stage through a `<slot>` at the bottom of each shadow computation tree. The light DOM remains shallow while the flattened CSS tree places the continuation after the complete reduction chain. A registered value measured from a 37 px container crossed two separate 400-level trees as exactly `37`. A second probe forwards an outer slot through an internal stage slot; a measured value crossed two block boundaries as exactly `41` while the final light-DOM depth remained five.

This means matrix stages can be repeated without spending another 384 light-DOM levels each, and complete transformer blocks can forward their result while adding only one outer level per block.

### One faithful GPT-2-small block now compiles

`experiments/gpt2-block-css/index.html` implements block 0 for a one-token causal context:

- both learned layer normalizations using native CSS multiplication and `sqrt()`;
- the real attention value projection (one-token softmax is exactly 1), attention output projection, and residual;
- the real 768→3072 MLP projection;
- GPT-2's GELU approximation using native CSS `exp()`;
- the real 3072→768 MLP projection and final residual.

Twenty-one signed HVAR fonts contain the actual block-0 weights. The first version processed the MLP hidden state in twelve 256-value slices, crossing one slotted boundary after every first-projection slice and every partial output projection. The current compiler instead emits all 3,072 GELU values in four 768-output stages, keeps them as inherited custom properties, and sums all twelve output-projection font shards in one stage.

| One-token block result | Value |
| --- | ---: |
| Signed weight precision | 9-bit per output row |
| HVAR pipeline vs quantized NumPy | 5.68e-14 max error |
| Quantized block vs original float block | 0.1559 max error |
| Font build | 54.6 s in the latest run |
| Peak build RSS | 421.6 MB |
| Fonts | 21 |
| Slotted matrix stages | 7, down from 26 |
| Paired size-container readbacks | 2,688, down from 6,912 |
| Child shard elements | 3,072, down from 23,040 |
| Generated HTML after stylesheet extraction | 595,684 B, down 75.4% |
| Runtime bundle | 11,332,546 B raw / 7,415,148 B Brotli |
| Chromium completion | 9.42 s in the browser harness |
| Chromium vs quantized NumPy | 0.006713 max error / 0.001631 RMSE |

Stage collapse plus packed font runs reduce raw runtime bytes by 27.6%, but only reduce Brotli bytes by 1.7% because the 21 weight fonts are unchanged. They also remove eleven intermediate 768-value accumulation rules and nineteen shadow-root stylesheet/readback boundaries.

The complete seven-stage page now finishes in Chromium. A repeated browser run returned all 768 final values with 0.006713 maximum error and 0.001631 RMSE against the quantized NumPy result, and completed in 9.42 seconds in the browser harness.

The earlier crash was a layout-stack failure, not a failed matmul. Prefixes of one, two, and three matrix stages loaded; adding the fourth crashed the renderer. Removing fonts, container queries, or the model stylesheet did not save it. Removing all stage CSS did. A 329-byte layout-only variant still crashed, while changing the measuring boxes from nested absolute positioning to fixed positioning survived. This matches Chromium's documented inability to protect the renderer from stack overflow in sufficiently deep block-layout trees ([Chromium issue 466692313](https://issues.chromium.org/issues/466692313)).

The working backend keeps the logical slot/custom-property pipeline but removes the geometric dependency between stages: every metric and readback probe is fixed to the viewport. The boxes remain nested for value propagation, but layout no longer recursively asks each box to resolve through every ancestor's positioned containing block. Font faces also live in the document stylesheet instead of a shadow-root stylesheet, so the slotted light-DOM glyphs consistently receive the HVAR fonts. With the dangerous layout recursion gone, the metric font can stay at 512 px for high readback precision.

This changes the practical scaling limit. Adding stages is now approximately additive in parsing, style calculation, font loading, and layout work instead of also increasing one renderer-stack path. Full GPT-2 still needs separate weights and declarations for eleven more blocks, so its transfer and evaluation cost remains roughly linear in block count; the immediate renderer crash is no longer the blocker.

### The next scaling probes identify a serial-state limit

Warm, cached Chromium navigations of the correct stage prefixes measured 0.245, 0.468, 1.030, 1.954, 3.132, 4.700, and 8.313 seconds for prefixes one through seven. The marginal stage cost rises from roughly 0.22 seconds to 3.61 seconds. This is not explained by additional weights alone: every stage inherits through the preceding size-container chain, so the style/layout dependency path grows throughout the block.

A four-branch MLP prototype cut navigation to about 5.2 seconds, but it was numerically invalid. Plain sibling anchors can be added successfully, including across ordinary size containment. The real branch outputs end at the bottom of nested size containers, however, and those anchor boxes are not acceptable to a merger outside that containing-block chain. The merger width resolved to zero. The prototype remains as `gpt2-block-css/parallel.html` and labels itself as a negative experiment.

CSS counters carry an integer from an ordinary deep descendant to a later sibling, but a slotted descendant's counter state does not escape its shadow host. The shadow boundary that keeps each 384-container stage parseable therefore also prevents counters from flattening this pipeline.

Packing four signed results into one container's width and height also loses too much information. At an 8.77-million-pixel packed width, Chromium preserved the high packed integer but changed the low integer by 111 units. At 11.73 million pixels the low integer changed by 210 units. Large CSS layout values do not retain enough mantissa bits to encode four roughly 17-bit matrix results in two dimensions. The existing two-result width/height transport is the exact path.

These measurements set a go/no-go threshold for further model compilation. A block should be below 500 ms after assets are cached before compiling all twelve GPT-2 blocks. That still projects to more than six seconds per token before the output head. A useful CSS demo target is 200–250 ms per block; an approximately one-token-per-second target needs roughly 50 ms per block after reserving time for attention and vocabulary selection. The faithful seven-stage block is 19–38 times above the first two thresholds.

### One-token affine composition removes a complete stage

For a one-token causal context, attention has one score and softmax is exactly one. The value projection and attention output projection are therefore two consecutive affine maps. `composed.html` multiplies those weights and biases at build time, quantizes the resulting 768×768 affine map once, and evaluates it as one matrix stage. This is exactly the same float operation for the stated one-token context; only the position of 9-bit quantization changes.

The composed block uses six stages and eighteen fonts. It completed in 6.481 seconds versus 9.42 seconds for the seven-stage version, a 31% reduction. Its runtime bundle is 10,315,693 bytes raw / 6,653,967 bytes Brotli. Chromium returned all 768 values with 0.019843 maximum error and 0.001762 RMSE against the composed quantized NumPy reference. Quantized-versus-original-float maximum error changed from 0.155901 to 0.163464; RMSE is 0.016323 and cosine similarity is 0.9999952.

This optimization does not generalize to multi-token attention: once the context contains multiple keys and values, QK scores and softmax sit between the projections. It is useful for the current block benchmark and confirms that early dependency depth, not font bytes, is the dominant runtime cost.

### Expanded CSS arithmetic misses the 13× target

`direct-css-block/block.html` expresses the same composed one-token block as native registered custom properties and `calc()`, `sqrt()`, and `exp()` expressions. It removes fonts and container-query readback from the arithmetic path entirely. Chromium returned all 768 outputs with 0.000140 maximum error and 0.00000748 RMSE against the quantized NumPy reference. The residual difference is computed-style decimal serialization.

The initial test found that once the stylesheet and dependency graph were already evaluated, reading all 768 cached outputs took about 20 ms. A later same-page mutation test showed why that must not be called inference: changing one input and then forcing all outputs took 2.48–2.66 seconds on every alternating update. Encoding 5,252,351 nonzero matrix terms as CSS expands the compact stylesheet to 94,323,192 raw bytes. Brotli quality 5 reduces it to 19,618,890 bytes, but Chromium must still parse the 94 MB token stream and re-evaluate its dependency graph. End-to-end local navigation took about 5.0 seconds, versus 6.481 seconds for the composed HVAR block: approximately 1.3×, not the required 13×.

Short single-letter state names and base-36 indices cut the first direct version from 125.2 MB to 94.3 MB without materially changing runtime. Splitting the same declarations into sixteen byte-balanced stylesheets (largest 6.05 MB) reduced the observed load from about 5.0 to 4.7 seconds. This rules out source minification and parallel stylesheet parsing as a route to the 500 ms block gate.

`direct-anchor-readback-probe.html` also tests the hoped-for bridge between the compact HVAR representation and native CSS arithmetic. Chromium accepts `anchor-size()` for element sizing, but it does not resolve the anchor length inside a registered numeric custom property or `font-variation-settings`. The size-container readback boundary therefore cannot currently be removed that way.

The result is a useful boundary: use direct CSS for O(width) operations such as layer normalization, GELU, bias, and residuals, but not for O(width²) weight matrices. Reaching the target still requires flattening or reducing HVAR's serial metric-readback dependency, rather than spelling millions of products out as CSS.

### Four-output HVAR readback halves the transport depth

`gpt2-block-css/composed-packed.html` keeps all 5,252,351 nonzero matrix coefficients in the compact HVAR tables. A glyph width still evaluates one complete dot product. The change is only at the CSS boundary: each size container now transports four rounded matrix outputs—two packed into width and two into height—instead of transporting two unrounded outputs.

This reduces the composed block from 2,304 to 1,152 readback containers. Chromium completed the packed block in roughly 3.5–3.8 seconds, versus 6.481 seconds for the ordinary composed block: about 1.8× faster. All 768 outputs remained finite. Against the composed quantized NumPy reference, maximum error was 0.09943 and RMSE was 0.00938. Maximum error against the original float block was 0.20091.

Packed prefix timings were approximately 0.4, 0.8, 1.2, 1.7, 2.3, and 3.8 seconds for one through six stages. Halving the per-stage chain helps almost proportionally at first, but the complete inherited dependency still grows superlinearly. Four-output packing is therefore a valid speed/accuracy option, but it does not approach the 500 ms gate by itself.

Collapsing all four FC slices into one 3,072-output stage is invalid. Although the source contains all 768 packed containers, Chromium only propagates values through roughly 506 nested containers: FC outputs 0–2,023 are present and outputs 2,024–3,071 fall back to zero. The resulting block took about 3.9 seconds but had 11.43 maximum error. `composed-packed-collapsed-fc.html` is retained and labeled as a negative nesting-limit probe.

A valid middle case uses two 1,536-output FC stages, each 384 containers deep. `composed-packed-two-fc.html` returns the same output and 0.09943 maximum error as the four-slice packed page, but took about 4.2 seconds—slower than the 3.5–3.8-second four-slice version. This isolates the bottleneck: shadow/stage boundaries are not the dominant cost. Longer serial container chains cost more, and chains beyond roughly 506 containers cannot be represented reliably by the parsed DOM. Future work must reduce or parallelize the total readback dependency, not merely regroup it into fewer stages.

`typographic-branch-merge-probe.html` tests whether `display: contents` can bypass the failed anchor merger by letting four branch-result widths add in a shared inline formatting context. Each isolated branch correctly transports its value through a size container and shadow slot: the four result spans resolve to 37, 41, 43, and 47 pixels. A direct inline-flex control sums those widths to 168 pixels, but the branch merger resolves to zero width. The result boxes remain inside their fixed size-container formatting contexts and do not become children of the common inline box. Changing the readback container itself to `display: contents` is not an alternative because it removes the size box—and therefore the container units—needed to recover the numeric value. Typography does not provide an exact cross-branch merger for the current transport.

### Named view timelines provide a parallel geometry-to-number bridge

`view-timeline-readback-probe.html` uses the progress of a named view timeline to encode a subject's width. With a subject starting at the leading edge of a 100-pixel scrollport, cover progress is `100 / (100 + width)`, so native CSS arithmetic recovers `width = 100 / progress - 100`. `timeline-scope` lets animations on a separate shared consumer reference timelines defined by sibling subjects.

Two fixed widths, 37 and 41 pixels, were recovered as exactly 37 and 41 on two registered custom properties of one consumer. Replacing the fixed boxes with real output glyphs from the 64×64 HVAR matmul recovered the first two expected outputs, -109.75 and 69.25, as -109.612 and 69.3231. The timeline values also inherited unchanged into a child of the consumer, which is the property needed to drive the next matrix stage.

Static HTML/CSS-only scale probes then attached every timeline to one consumer:

| Parallel results | Raw page | Warm local navigation | Sampled values |
| ---: | ---: | ---: | --- |
| 64 | 15,219 B | 33 ms | first and last correct |
| 768 | 183,189 B | 61 ms | first, middle, and last correct |
| 3,072 | 750,423 B | 260 ms | first, middle, and last correct |

These scale probes use fixed-width subjects, not 3,072 HVAR glyphs, so 260 ms is not yet a matrix-stage benchmark. They do establish the missing transport operation: thousands of independent geometry results can merge onto one inheritable state without a nested size-container chain. A complete HVAR stage should now be rebuilt around flat glyph subjects plus named view timelines. If that remains correct and fast, six matrix stages require only about six inheritance levels instead of 1,152 serial readback containers.

The real follow-up is `gpt2-block-css/view-timeline-fc.html`. It evaluates the actual quantized GPT-2-small `mlp.c_fc` matrix (`768→3,072`), converts every HVAR glyph width through a named view timeline, adds the learned bias, and applies GELU. The page is static HTML/CSS with no script. Twenty-four shallow consumer elements each receive 128 timeline animations; their nested inheritance leaves the final consumer with all 3,072 hidden values.

All 3,072 Chromium outputs were finite. Against the quantized NumPy reference, maximum error was 0.001028, RMSE was 0.0001193, and the 99th-percentile absolute error was 0.000532. Native CSS `@function` reduced the generated FC stylesheet from 1.92 MB to 1.19 MB by sharing the GELU expression without changing those values.

Warm component medians on the same Chromium run were 115 ms for HVAR glyph layout, 551 ms through timeline readback, and 966 ms for the complete FC + bias + GELU stage. A directly comparable existing packed prefix took 85 ms for composed attention alone and 1,010 ms through all four FC slices, implying roughly 925 ms for the existing FC path. Named timelines therefore flatten the dependency graph and remain promising for avoiding downstream chain compounding, but they do not make this isolated FC stage faster. The measured 966 ms result misses the 500 ms go/no-go target.

Several refinements were tested. Moving the 768-axis `font-variation-settings` declaration from every glyph to one inherited stage declaration reduced the flat stage from about 3.17 seconds to 1.60 seconds. Splitting one 3,072-animation consumer into groups reduced it again; 96–256 animations per consumer clustered around 1.0–1.1 seconds, with 128 retained as the default. A font-size reduction from 512 px to 32 px was slower and less accurate. Routing widths through ordinary anchors before the timelines was correct only when each anchor stayed inside its scroller, and was slower at about 3.84 seconds.

### Flat FC chained directly into the projection

`gpt2-block-css/view-timeline-mlp.html` connects the 3,072 CSS values produced by the flat FC + GELU stage directly to the real quantized GPT-2-small `mlp.c_proj` matrix (`3,072→768`), then adds the learned bias and the 768-value residual. The projection font axes reference the inherited `--hidden-*` properties; the page contains no precomputed replacement for those activations and no JavaScript. The offline reference exactly matches the pre-existing composed quantized block reference.

Chromium produced all 768 finite outputs. Against that quantized reference, the complete browser chain had maximum absolute error 0.10474 and RMSE 0.008738. Most of that is projection timeline readback error after the already accurate FC values: recomputing the projection from the 3,072 browser-produced hidden values reduced the isolated FC discrepancy to maximum 0.001028, while the projection transport contributed maximum 0.09904 and RMSE 0.008672. For scale, the existing 9-bit quantized reference itself differs from the unquantized block by maximum 0.16346 and RMSE 0.01632.

In an eight-round alternating same-browser benchmark, the flat MLP page took a 1.738-second median from navigation through reading all 768 outputs. The existing packed full-block page took 2.159 seconds. Since the flat test begins from a fixed post-attention normalized state while the packed page also performs the roughly 85 ms composed-attention prefix, the like-for-like estimate is about 2.074 seconds for the old MLP path versus 1.738 seconds for the flat chain: roughly a 1.19× improvement, not the hoped-for 13×. The new raw bundle is 695,090 bytes of HTML, 1,629,407 bytes of CSS, and 5,742,116 bytes of fonts, or 8,066,613 bytes total.

Splitting each projection result into four separate timeline reads was also tested to reduce numerical cancellation. It regressed the warm median to 3.27 seconds and failed to resolve the final projection reliably at 3,072 additional timelines, so the one-timeline-per-output design remains the generated default. The result answers the stage-boundary question: flattening prevents some downstream compounding, but the dominant cost is still the amount of HVAR layout and timeline transport, not merely the number of sequential wrapper stages.

The direct HVAR compiler now also accepts one safe base advance per output glyph. Projection fonts built this way subtract each row's own baseline instead of the worst baseline across all 768 rows. That reduced complete-chain maximum error from 0.10474 to 0.04404 and RMSE from 0.008738 to 0.004852 without adding timelines. Sharing all subjects of a matrix stage in one scroll container preserved every value and improved the real FC median by about 6%; pairing two outputs onto the width and height axes of one subject was correct but improved only about 3%, while combining both ideas was slower.

`view-timeline-block.html` removes the offline MLP input entirely and computes LN1, the real quantized one-token attention matrix, its residual, LN2, FC, GELU, projection, and the final residual in CSS. Chromium returned finite values at every stage; final maximum error was 0.04214 and RMSE 0.004912. Flattening the smaller attention matrix was counterproductive, however: the complete flat block took about 2.35 seconds versus roughly 2.15 seconds for the earlier packed block.

`view-timeline-block-hybrid.html` therefore keeps the fast packed attention prefix and attaches the shared-scroller MLP directly through inherited `--r1-*`/`--n2-*` state. A slim 595 KB attention-prefix stylesheet replaces the old 2.1 MB full-model stylesheet. The hybrid produced all 768 outputs with maximum error 0.04214 and RMSE 0.005317, and its seven-run warm median was 1.667 seconds. This is about a 1.29× improvement over the roughly 2.15-second packed complete block, but still more than twelve times slower than the 130 ms per-block threshold needed for the original 13× target.

`view-timeline-block-hybrid-fc-paired.html` halves the FC transport objects by carrying two matrix results on each named timeline. The first glyph controls the timeline subject's inline position and the second controls its width; `cover` and `entry` progress recover both values in CSS. This reduces the 3,072 FC subjects, timelines, and animations to 1,536 without changing the font matmul or substituting precomputed activations.

In a Chrome 152 three-way alternating run, the unpaired hybrid had a 2.241-second warm median and the FC-paired hybrid had a 1.886-second median, a 15.8% reduction. All 768 outputs remained finite and the maximum absolute error stayed exactly 0.04214; RMSE changed from 0.005317 to 0.005309. Pairing the final 768-output projection as well reduced its subjects to 384, but regressed the median to 1.972 seconds and increased maximum error to 0.09270 because reconstructing two large projection widths magnified timeline-progress rounding. The retained design therefore pairs only the FC boundary. Its generated HTML is 501,866 bytes and its stage stylesheet is 1,739,350 bytes.

The next experiment packs quantized post-GELU activations into intrinsic-size digits before timeline transport. Four values share one timeline, and the projection decodes the packets directly instead of materializing 3,072 hidden properties. The retained importance-aware 9/8-bit version cuts the FC boundary to 768 timelines and measured 1.005 seconds versus 1.851 seconds for the accurate paired page in the same alternating run. Its maximum block error is 0.15988 and RMSE is 0.03101. This is the first transport denser than the two geometric degrees of freedom, but remains 7.7× above the 130 ms target. Precision limits and rejected variants are documented in [the packed timeline results](../packed-timeline-precision/RESULTS.md).

Packing the projection output as 192 signed square-root packets reduced the warm median again from 967 ms to 875 ms. The block is now about 2.56× faster than the 2.24-second unpaired hybrid in these Chrome 152 runs, but still 6.7× above target. This second lossy boundary had 2.82 maximum error and 0.222 RMSE, so it is retained as a cross-block transport experiment rather than the accuracy default.

The replacement SVG-filter backend finally clears the order-of-magnitude gate.
`../svg-filter-full-block/chain.html` keeps vectors and both live residual paths
as image strips through layer normalization, attention, FC, GELU, and
projection. The connected block has 0.688 RMSE and 8.062 maximum error, while
an independently referenced alternate input has 0.775 RMSE. Three independent
20-transition runs measured 75.30–82.74 ms warm medians. Against this section's
2.241-second unpaired HVAR baseline, the median trial is 29.4× faster. The complete sequence
of failed transport designs and the retained filter-region layout are recorded
in [the SVG-filter results](../svg-filter-matvec/RESULTS.md).

### Real two-token causal attention

`view-timeline-attention-2token.html` is the first real multi-token attention path. For GPT-2 tokens 15496 and 995 (`Hello world`) it evaluates both tokens' quantized Q/K/V projections, all 12 heads' scaled dot products, the causal mask, stable two-way softmax for the second token, both weighted value vectors, both attention-output projections, and both residuals. Everything runs in HTML/CSS; the page contains no script and does not substitute precomputed attention probabilities or context vectors.

Chromium returned all 4,608 Q/K/V values and both 768-value residual states. Worst residual error was 0.00391; the second token's context-vector maximum error was 0.000264. The page is 586,868 bytes of HTML, 2,930,320 bytes of CSS, and 2,849,620 bytes of fonts. A seven-run output-only benchmark had a 3.899-second warm median for attention alone.

This closes the context-scaling question for the current backend. Two tokens' attention plus two shared-scroller MLP passes would put a single block near seven seconds; twelve blocks project to roughly 80–90 seconds before final layer norm and the 50,257-token output head. Longer prompts also add Q/K/V subjects and attention-score arithmetic. Repeating this implementation twelve times is therefore rejected by the measured scaling gate. Full GPT-2 requires a new way to expose many font-matmul results with substantially fewer geometry/timeline evaluations; wrapper flattening, shared scrollers, two-axis subjects, and row-specific baselines do not supply the missing order-of-magnitude improvement.

### Direct HVAR compilation removes the waste

The original designspace compiler put the matrix in `HVAR` but also emitted redundant phantom-point variation data in `gvar`. Simply deleting that data from an already compiled font broke metric instancing. The working direct compiler constructs `fvar`, `HVAR`, and a structurally valid empty `gvar` together. Chromium applies the HVAR widths correctly without the duplicate data.

| Build | Master compiler | Direct HVAR compiler |
| --- | ---: | ---: |
| 64×64 build | 0.761 s | 0.042 s |
| 128×128 build | 3.474 s | 0.140 s |
| 256×256 build | 19.958 s | 0.375 s |
| Three 768×256 shards | about 121 s | 1.708 s |
| Three-shard WOFF2 total | 1,044,340 B | 459,672 B |
| Three-shard peak build RSS | about 622 MB | about 172 MB |

The generic FontTools designspace builder creates one complete master font per axis. The direct writer builds one static base font and writes the matrix straight into a single HVAR item-variation store. It avoids hundreds of temporary fonts and is now the default for browser-safe matrices of at most 256 input axes.

## Reproduce

```sh
make matrix-scaling
make test-matrix-scaling
make matrix-shards
make test-matrix-shards
make packed-font-shards
make signed-hvar-chain
make test-signed-hvar-chain
make gpt2-hvar-chain
make test-gpt2-hvar-chain
make shadow-depth-probe
make gpt2-block-css
make test-gpt2-block-css
make test-view-timeline-fc
make test-multitoken-attention
make test-direct-css-block
python3 -m http.server 4177
```

Open:

- `http://127.0.0.1:4177/experiments/matrix-scaling/index.html`
- `http://127.0.0.1:4177/experiments/matrix-scaling/768-sharded/index.html`
- `http://127.0.0.1:4177/experiments/packed-font-shards/index.html`
- `http://127.0.0.1:4177/experiments/signed-hvar-chain/index.html`
- `http://127.0.0.1:4177/experiments/gpt2-hvar-chain/index.html`
- `http://127.0.0.1:4177/experiments/gpt2-block-css/index.html`
- `http://127.0.0.1:4177/experiments/gpt2-block-css/view-timeline-mlp.html`
- `http://127.0.0.1:4177/experiments/gpt2-block-css/view-timeline-block-hybrid.html`
- `http://127.0.0.1:4177/experiments/gpt2-block-css/view-timeline-block-hybrid-fc-paired.html`
- `http://127.0.0.1:4177/experiments/gpt2-block-css/view-timeline-block-hybrid-paired.html`
- `http://127.0.0.1:4177/experiments/gpt2-block-css/view-timeline-block-hybrid-fc-packed4.html`
- `http://127.0.0.1:4177/experiments/gpt2-block-css/view-timeline-block-hybrid-packed4-chain.html`
- `http://127.0.0.1:4177/experiments/gpt2-block-css/view-timeline-attention-2token.html`
- `http://127.0.0.1:4177/experiments/direct-css-block/block.html`
