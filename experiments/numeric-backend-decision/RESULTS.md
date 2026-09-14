# Numeric backend decision

Measured in headless Chrome on macOS on September 12, 2026. Runtime pages are
HTML/CSS-only; JavaScript is used only by the external measurement harnesses.

## Decision

Do not carry GPT-2 hidden state through SVG filter pixels. Use:

- direct HVAR variable fonts for dense affine maps and dot products;
- registered CSS numbers and native CSS math for bias, residuals, LayerNorm,
  GELU, and attention arithmetic;
- paired width/height container geometry to expose each font result to CSS;
- SVG only as an optional visualization surface, not as numerical storage.

This is an accuracy decision, not yet a speed victory. HVAR avoids the repeated
8-bit filter-surface quantization that makes a twelve-block SVG pipeline drift,
but font shaping and geometry-to-number transport remain expensive.

The strongest block-state transport found so far packs four calibrated output
channels into one timeline using asymmetric 8/9-bit ranges. On the real block-0
browser fixture it reduces total timelines from 1,536 to 960, keeps RMSE at
0.03777 versus 0.03101, and improves warm latency from 1,048.8 ms to 960.3 ms.
This is a useful boundary optimization, not a solution to the overall scaling
problem: a full 12-block token still contains thousands of font-shaping and
timeline operations.

The packed state has also been consumed by a subsequent real matrix. A live
block-0 → block-1 LayerNorm/attention page retained 0.03826 RMSE, essentially
identical to its 0.03834 input error. Its 1,395 ms warm median compares with
869 ms for block 0 and 312 ms for the isolated block-1 prefix, exposing roughly
214 ms of additional cross-boundary dependency cost. The transport is therefore
functionally reusable, though repeated dependency depth remains a latency risk.

That chain now extends through a second complete transformer block. Keeping
all 3,072 post-GELU values as separate CSS numbers required 5,568 total
timelines and took 5,033 ms warm for two connected blocks. Packing four hidden
values per carrier reduced the page to 3,264 timelines and 3,921 ms, a 22.1%
improvement, while retaining 0.05490 RMSE against the block reference. The same
packed block ran in 1,275 ms with its input fixed, so the remaining connected
dependency chain adds far more work than the isolated matrix stages alone.

## Evidence

### Attempts to recover SVG precision

| Experiment | Result |
| --- | --- |
| RGB offset/dither through 12 scalar affine boundaries | 2.85x lower RMSE than one channel |
| RGB offset/dither through two real 64x64 GPT matrices | only 1.12x lower RMSE |
| Dither each product before a 64-term reduction | RMSE regressed from 0.0191 to 0.1013 |
| Pack matrix rows into one `feConvolveMatrix` | Chrome fails once the kernel exceeds roughly 256 coefficients; a 16x16 case already needs 272 |
| Coarse plus correction images | preserves stored inputs, but each later SVG boundary creates a new discarded remainder |

The common failure is that an SVG filter output is quantized again before the
next primitive consumes it. Extra planes can preserve an existing number, but
they cannot recover a remainder that the browser has already rounded away.

### HVAR plus CSS transport

Two chained real GPT-2-small 768x768 projections, using signed 9-bit weights:

| Transport | Warm median | RMSE vs quantized reference | Maximum error |
| --- | ---: | ---: | ---: |
| container-query readback | 525.8 ms | 0.0032007 | 0.06636 |
| direct container-unit readback | 516.3 ms | 0.0032007 | 0.06636 |

The direct form removes 1,536 query rules from that two-matrix fixture, but the
roughly 2% timing change shows that query-rule dispatch is not the bottleneck.

On the six-stage one-token composed GPT-2 block, direct readback again produced
exactly the same browser values as query readback:

| Transport | Short-run warm median | RMSE vs quantized reference | Maximum error |
| --- | ---: | ---: | ---: |
| container-query readback | 3.760 s | 0.0025449 | 0.02854 |
| direct container-unit readback | 3.875 s | 0.0025449 | 0.02854 |

Direct readback reduced the six stage stylesheets from 1,093,989 bytes to
923,529 bytes and removed 4,608 query rules, but it did not improve block
latency. The dominant work is font shaping and transporting thousands of font
results through layout.

A dedicated FC control now separates those two costs. All fixtures shape the
same 9,216 glyphs for the real 768→3,072 matrix:

| FC work retained | Warm median |
| --- | ---: |
| three continuous font runs, no numeric exposure | 136.3 ms |
| 3,072 ordinary output spans, no numeric exposure | 111.3 ms |
| 3,072 named timelines | 588.5 ms |
| timelines plus CSS decode and GELU | 1,074.3 ms |

Plain HVAR shaping stays near 100–135 ms even with thousands of elements.
Timeline exposure adds about 477 ms and CSS numeric decoding adds about another
486 ms. The exposed stage is 9.7× the shared-span shaping control. This revises
the diagnosis: font shaping is viable; geometry-to-number exposure and the
resulting CSS dependency graph dominate. See
`../gpt2-block-css/HVAR_SHAPING_EXPOSURE.md`.

### Attempts to increase outputs per font/layout object

| Experiment | Measured result | Decision |
| --- | --- | --- |
| Four-dimensional view-timeline carrier | 3,072 values with 768 subjects instead of 1,536; only 4.8% faster | Animation/property count still dominates |
| Native font metrics (`ex`, `cap`, `ch`, `ic`, `lh`) | Five independent dot products from one font instance; those five metrics feed a child font's axes directly, but a real `768x768` projection takes 934.5 ms, 924 fonts, 224 MB expanded font data, and 2.83 GB Chrome RSS | Reject for dense GPT-2 matrices; retain direct chaining only as a small-row primitive |
| Multi-face metric bank with shifted axes | Full `256→768` output in CSS without timelines; 0.37 s uncached and 155 MB expanded | Three shards take 1.10 s and about 465 MB per unique square matrix; reject for dense GPT-2 |
| Standard OpenType feature selection | All tested substitutions change rendered glyphs, but none change `1ch` or `1ic` | Cannot multiplex numeric metric rows |
| Row-selector variation axis | 768 outputs mutate/read in ~0.44 ms, but measured full-model projections require 5.9–47.4 GB decompressed fonts and 0.24–1.93M row nodes | Reject the dense row-axis representation |
| Shared-table TTC metric bank | 143,628-byte collection for 64 variable faces, but Chrome returned face 0 for every fragment | Blocked by Chrome collection-member selection |
| Grid/subgrid track vector | 256 live outputs plus coordinatewise GELU in 14.8 ms versus 28.2 ms for the nested chain | 1.9x local transport win; sibling values still cannot be gathered into the next dense matrix |
| Shifted-log six-value packet | 96.68% vs 95.80% numerical token agreement, but browser RMSE 1.436 vs 1.240 and 2.4% slower | Reject; nonlinear decoding amplifies geometry error |
| Sensitivity-tiered 3/4/5/6 packet | 416 FC timelines and 845.8 ms, but 0.826 RMSE and 9.23 maximum error | Only 5% faster than uniform six; reject |
| Seven-value 5/6-bit packet | 439 FC timelines; 23-bit coordinate produced 20.75 RMSE even after viewport correction | View-timeline packing exceeds its reliable geometry precision; reject |
| Radix-packed HVAR metrics | Exact toy and 1.38x warm / 2.25x mutation speedup for 1,024 small integer outputs | Real 8-bit-activation GPT-2 pairs need 27–32 bits; one advance has 16 |
| Six-value post-GELU timeline packet | 512 rather than 768 FC timelines; 13-17% block speedup | Uniform six is the best aggressive variant, but block RMSE rises from 0.031 to 0.122 |
| Heterogeneous 5/8-bit timeline packet | 640 timelines; 7.5% block speedup, 0.133 RMSE | Dominated by uniform six on speed and average error; reject as preferred path |
| Complete second block, four-value MLP packet | 3,264 rather than 5,568 total timelines; 22.1% connected-chain speedup | Current full-chain winner, but still 3.92 s for only two blocks |
| Cache packed MLP values as 3,072 registered CSS numbers | Identical output, but 4.7% slower connected and 13.5% slower isolated | Reject; inherited typed properties are not an effective memoization layer |
| Keep vectors as anchor widths and compile the next matrix into balanced `anchor-size()` sums | Exact chaining without timelines; 1.25 s loaded evaluation and 28.8 MB source for one 768x768 matrix | Accurate, but coefficient-by-coefficient CSS expansion scales worse than HVAR |
| Additive `font-variation-settings` matvec | Exact `3,072→768` synthetic projection in 598 ms after load | First whole-vector gather primitive; direct animation inputs only |
| Four-value 24-bit container packet | Exact 6-bit decoding through a single width; five-value packet loses its low digit | Retain four values per dimension |
| Real HVAR → anchor packet → GELU → additive projection | Complete `768→3,072→768` GPT-2 MLP, 0.00069 browser RMSE | Correct vector handoff; 2.27 s and 65.4 MB raw remain slower/larger than flat timelines |
| Two-dimensional anchor packets | Eight 6-bit FC values per carrier; depth 388 and 2.27 s versus depth 772 and 3.12 s | Retain over one-dimensional packing |
| Packed preactivation precision sweep | Exact 48-bit width/height payload; 3/4/6/8/10-bit real MLP paths take 863/814/962/1,124/1,183 ms, with full-precision RMSE 0.241/0.0637/0.0155/0.00455/0.00276 | Six bits is the best speed/accuracy compromise, but packing leaves all 3,072 FC and 768 projection glyph operations |
| Four-bit two-dimensional packets | Depth 260 and 2.14 s, but activation RMSE rises from ~0.03 to ~0.12 | Speed gain too small for the precision loss |
| Single additive sink after 3,072 typed captures | Correct full MLP in 1.59–1.62 s | Best anchor variant, but still 4.7x slower than a loaded flat timeline MLP |
| One typed 24-bit packet per width/height | Lowest six-bit digit is corrupted at multi-million-pixel widths | CSS numeric capture loses the carrier's low-order precision |
| Split low-digit plus 18-bit packet capture | Exact with 1,536 rather than 3,072 registered values; 2.308 s median | Fewer registered properties do not offset centralized decode/GELU cost; reject |
| Loaded flat view-timeline MLP mutation | 341 ms median after the two frames required for fresh progress; 0.00545 RMSE | Current isolated real-MLP speed winner |
| TrueType `GETVARIATION` bytecode | Font loaded, but constant and axis-dependent glyph programs were both ignored in Chrome/macOS | Reject; the browser target does not expose the font VM |
| Direct `anchor-size()` font-axis gather | Chrome computes the 3,072-axis declaration as `normal`; the apparent ~20 ms projection is the zero-axis baseline | Reject; anchor geometry cannot directly inhabit `font-variation-settings` |
| Isolated width+height additive gather | Halves carriers and depth, but exact `3,072→768` mutation improves only 689.1→649.7 ms (1.06x) | Animation contribution count, not carrier count, dominates |
| Two-lane SWAR anchor dot products | Bit-exact; 768→768 improves 1,136→650 ms and 3,072→128 improves 3,384→617 ms; Brotli size also falls | Retain for composable reductions, but projected dense 3,072→768 latency still loses to HVAR |
| Real HVAR FC → GELU → SWAR projection slice | `calc-size()` fusion improves a real 3,072→128 slice from 1,701→1,489 ms; approximate GELU reaches 1,404 ms | Reject for dense MLP (~4.5 s projected); retain SWAR for smaller reductions |
| Dynamic Q·K with paired anchor SWAR | Exact and 4–6x faster than scalar CSS, but 12 heads × 64 keys still needs 24,960 sources and 8.63 s | Reject the per-coordinate anchor key cache |
| Bilinear HVAR Q·K | 128 axes/256 two-axis regions cut 12 heads × 64 keys from 8.63 s with paired anchors to 675 ms | Real primitive, but reject after numeric capture: native CSS takes only 49 ms |
| Native CSS-number Q·K | Exact 12 heads × 64-key cached-query update in 49.43 ms; 195.90 ms when every key changes | Attention-score winner once QKV is numeric; optimize QKV transport instead |
| Native CSS dense QKV | Real 768→2,304 warm mutation takes 958 ms and 30.9 MB CSS | Reject for dense matrices despite fast 64-term attention math |
| HVAR QKV + shared geometry easing | Real 768→2,304 in 254 ms; 0.000107 RMSE; 0.37 MB CSS + 2.13 MB fonts | Dense QKV winner; remaining cost is 2,304 animation samples |
| Orthogonal `cqw`/`cqh` transport | One descendant reads and multiplies independent outer-width and inner-height values exactly | Valid local two-input primitive; vector reduction still lacks an escape dimension |
| Six-output direct container packet | Real QKV in 168–197 ms using 384 containers; 0.00353 two-case RMSE | Fastest QKV transport; validate 8-bit error through a full block |
| Fractional 10-bit container packet | 200 ms but 0.0179 RMSE | Large layout coordinates discard the intended subpixel bits; reject |
| Four-output 12-bit container packet | Tail outputs become zero after roughly 512 of 576 nested containers | Reject the over-depth chain |
| Six-output packets through a full block | 0.02648 RMSE and 2.26 s warm versus 0.00971 and 436 ms for four-output raw packets | Reject globally; projection dependency graph erases the carrier-count win |
| Six-output QKV packets inside real two-token attention | 1.420 s warm versus 2.691 s with timeline QKV; 1.90x faster; 0.001330 residual RMSE | Retain as a localized QKV transport; do not generalize it to the MLP projection |
| General-calibrated QKV packets at 1/2/4/8-token context | 0.606/1.196/3.213/13.728 s versus timeline 1.043/2.365/6.227/23.639 s | Packet win survives context growth, but unique inherited QKV state makes both graphs superlinear; stream K/V state |
| Online-softmax K/V streaming | 1/2/4/8 tokens in 0.629/0.964/2.047/6.249 s; eight-token bundle 10.02 MB | Reusing one K/V bank removes accumulated per-token QKV state; retain |
| Direct K-width scores + streamed V | 1/2/4/8 tokens in about 0.58/1.02/1.64/3.5-4.1 s; eight-token bundle 8.64 MB; residual RMSE 0.00139 | 768 K values become 12 score timelines per source; superseded at longer contexts by geometry accumulation |
| Direct-K streaming at 16 tokens | 10.8-11.1 s full; profile attributes about 10.21 s to attention and 1.46 s to projection/consumption | Curve bends beyond eight tokens; remove V packet and registered-accumulator boundaries |
| Geometry-native online-softmax accumulator | General 12-bit projected attention at 2/4/8/16 tokens in 1.092/1.843/3.027/7.090 s; context RMSE about 0.000165 and no clipping | Context-scaling winner; final transport is general rather than fixture-specific |
| Attention shaping ablation | Axes-off saves 9-10%; system-font fallback still retains 79-87% of wall time | The element/dependency/layout graph, not HVAR arithmetic, now dominates |
| Bilinear composed QK font | Four glyphs/source but 197,120 HVAR regions/source; 1.036 s versus 0.251 s direct geometry and RMSE 0.171 | Reject: 4.13x slower, huge raw fonts, and WOFF2 rejected by Chrome |
| Flat attention value reduction | 1.060/1.608/2.576/6.270 s at 2/4/8/16 tokens; 29.6% fewer `i` elements at 16 | New winner: 1.03-1.19x faster than recurrent geometry while preserving the 12-bit transport |
| Packet-inlined attention reduction | 0.984/1.568/2.666/7.033 s at 2/4/8/16 tokens | Reject for scale: deep repeated packet expressions erase the short-context win |
| Native-CSS K/QK score | Correct but 3.013/6.811 s at 2/4 tokens and 23 MB of CSS | Reject: 2.8-4.2x slower than font K and grows per source |
| Shallow sibling attention graph | 0.785/1.376/2.100/3.889/10.342 s at 2/4/8/16/32 tokens; browser RMSE at most 0.00115 | Current winner; 1.46x faster than matched nested flat at 16 tokens |
| Horizontal/vertical pseudo K/V carrier | Cuts 16-token `i` nodes 27,392 to 15,104 but takes 6.43 s vs 6.27 s | Reject: DOM count falls, layout-box work does not |
| Shifted exact composed QK | 50,176 regions/source; 0.586 s versus 0.246 s direct K; RMSE 0.259 | Reject: 4x region reduction is still 2.38x slower and WOFF2 is rejected |
| Query-coordinate binning | Four-bit residual RMSE 0.0285 / 94.9% attention-winner agreement; five-bit 0.0149 / 97.6% | Reject without retraining; storage multiplies while accuracy falls |
| Per-head low-rank attention | Rank 63/64 residual RMSE 0.0618 for only 1.6% fewer boxes | Reject: checkpoint uses effectively full-rank maps |
| 12-bit output-projection packets | 3.917 s vs 3.895 s timelines at 16 tokens, with higher RMSE | Reject as the default transport |
| Per-source CSS containment | 3.93-3.98 s vs 3.92 s control | Reject |
| HVAR-to-SVG QKV raster | 4,608 QKV values in 296 ms at 0.00572 RMSE, but the next SVG QK stage collapses to zero | Retain as one-way bulk transport; reject the current reusable attention handoff |
| Full GPT-2 HVAR + Grid output head | Five direct 160-axis int10 faces select the dense GPT-2 winner in 10/10 browser cases; 0.78 s warm, 58.0 MB runtime | Current accurate vocabulary-head winner; int8 is 0.59 s / 45.0 MB but only 8/10 |
| Two live blocks + final LN + full GPT-2 head | Permanently connected: ~12.75 s; staged with `content-visibility`: 1.901 s median, same token and 0.000350 final-LN RMSE | Future stages must remain inactive until their inputs settle |
| Cross-shard font-internal composition | Fallback shaping sums independent face advances, but `1ch` sees only one face and direct width-to-font-axis declarations are unsupported | Exact `GELU(shard0 + shard1 + shard2)` first exists in layout; current fonts cannot remove the FC scalar boundary |
| Original vector-boundary oracle | Exact browser-captured values replace selected handoffs; the old two-block graph falls from 2,392.0 to 476.6 ms | Superseded: that “projection-only” floor still repeated sparse `avar2` GELU 768 times |
| Radix-packed HVAR rows | Two/four FC outputs per advance reduce carriers and improve 61.5 ms to 33.5/18.8 ms | Reject: continuous high lanes contaminate lower digits, causing catastrophic 60.01/24.63 RMSE |
| Single-glyph COLRv1 vector raster | One glyph emits 3,072 independent outputs and an SVG filter reuses them with 22 elements; 722.8 KB WOFF2, 366.4 ms | Functional but reject for scale: existing one-outline `gvar` export is 84.7 ms and raster cannot feed arbitrary dense rows |
| Compute-once inherited CSS GELU | 3,072 exact typed GELUs on one ancestor + pure HVAR projection takes 111.4 ms versus 463.7 ms for per-output `avar2`; RMSE improves 0.0520 to 0.0180 | New projection winner; exact `exp`/`pow` beats 8/16/32-knot hinge approximations |
| Compute-once GELU in two live blocks | Fresh-graph median falls 2,410.6 to 1,810.8 ms with the same 23,528 elements; exact-float RMSE improves 0.05113 to 0.03792 | Adopt: 1.33x end-to-end gain for +0.416 MB and no runtime JavaScript |
| Exact-GELU vector-boundary oracle | Exact handoffs reduce the retained two-block graph from 1,710.6 to 64.2 ms; GELU + projection is 88.6 ms and pure projection is 64.2 ms | Transport is now the dominant blocker; perfect boundaries give a 26.6x upper-bound speedup |
| Typed `@function(anchor-size())` readback | Two live anchor widths remain at registered-property initial values and cannot drive a font axis | Reject: custom functions do not make used geometry available at computed-value time |
| Width → container unit → automatic `opsz` | Exact scalar geometry-to-font-axis handoff; 768 fresh values take 35.3 ms, but 3,072 take 262.5 ms | Retain locally; full width is only 7.6% faster than the 284 ms four-value timeline fixture and cannot gather into one dense font |
| Four inherited standard font axes | Exact `wght`/`wdth`/`slnt`/`opsz` gather into one shape; 3,072 source values take 916.9 ms | Reject for bulk vectors; nested positioned containers scale worse than independent scalar handoffs |
| Timeline-driven CSS counter matrix | Exact five-bit integer 768×768 transform with 768 timelines and 505,444 weighted counter updates | Reject: 1.233 s warm and 29.8 MB, about 19× slower than the pure-HVAR projection oracle |
| CSS event → SVG SMIL class → HTML `:has()` stage signal | Exact two-block graph falls from 5.83-6.06 to 4.46-4.63 s; five dependency signals run two blocks plus the internally staged accurate head in 78.12-78.15 s cold | Retain for one-shot declarative staging; upstream timeline/container completion replaces guessed delays, but it does not re-arm for later token mutations |
| Output-head group containment | `contain:layout` and `contain:layout style` finish in 67.54/67.84 s versus a 67.71 s paired control | Reject: layout stays at 65.6-66.1 s and all variants retain the full score graph |
| Multiline intrinsic-width output head | Newline-only `max-content` sums all 256 lines; explicit `<br>` selects the right group in 65.70 s with 64.06 s of layout | Reject: slower than the ~61.7 s three-shard Grid baseline, still ~50k line elements, and local identity is missing |
| Supervised contiguous-group router | On 256 held-out 2/4/8/16-token states, 151k-weight ridge reaches 62.9%/74.6% top-1/top-2; scoring 37,824 learned representatives reaches 95.3%/96.1% | Reject: exactness returns only when all 256 rows/group are retained; zero-error margin fallback covers only 6.6% |
| Nonlinear ReLU group router | Deployable `768→128/256→197` models reach at best 59.8%/73.4% top-1/top-2 on the 1,024-state screen | Reject: worse than linear despite 247k parameters; validation-zero-error confidence accepts 9.4% and is only 83.3% precise |
| K-means IVF vocabulary router | Centroid routing reaches 97.3% at 8,404 mean rows and 98.0% at 14,515; 128/192 probes still miss train/validation states | Approximate-only: geometric clusters beat token-ID groups but provide no correctness-preserving reduction for the frozen checkpoint |
| Certified query-aware vocabulary ball tree | Query-fitted k-means hierarchy plus L2, rank-8/16/32 subspace, and 4/8/16 spherical-cap bounds retain 1,024/1,024 row-int10 winners, but the best median is 50,118 leaf rows plus 1,392 internal nodes | Reject the exact-index family: 99.72% of the full scan remains even before bound-evaluation overhead |
| Certified quantized best-first head | Int10 upper routing and two reusable int16 group stages pass in Chrome; 52.66 s cold, 2.95-6.38 s mutations, 10/10 dense winners | New exact search winner: later groups add 399 routing + 256 scoring nodes and reuse the 5 MB dispatch CSS/79 MB fonts; prove browser score allowance before full unroll |
| Packed visited-set cascade | Thirteen 16-bit CSS integers replace expanded history; a forced 16-stage traversal keeps all groups unique and the exact dense winner | Retain as the compact serial state encoding; it halves 61-stage CSS but does not fix the >3-minute cold path |
| Six-stage prefix + 197-way parallel uncertainty tail | Official 0/1/2-active cases pass; 41.95 s cold+first and 4.13-10.07 s mutations; six-active diagnostic takes 11.02 s with one non-winning oracle drift | Retain as a bounded-depth completeness topology, not a speed win; production ±266 tails still require browser-realized calibration |
| Batched certified tail | B=1/2/4/8 all select and merge correctly; B=2 ties serial at 8.88 s warm, while B=4/B=8 regress to 14.86/14.66 s | Reject repeated batching for latency; retain B=2 only when bounded dependency depth matters more than throughput |
| Native `position-try-order: most-width` router | Parses 197 fallbacks and is 2.05x faster in isolation, but a unique maximum at fallback 9 selects fallback 4 | Reject: it ranks fitting placement space rather than arbitrary anchor score width, so it cannot implement general argmax |
| Full-vocabulary GSUB-indexed fine scorer | Switches groups in 21.9 ms versus 226.0 ms for CSS dispatch, but pure winner agreement is 98.73%; an observed three-bucket margin gate accepts 88.53% with zero accepted errors | Reject pure GSUB; retain it as the fast side of the measured hybrid below |
| CSS-composed GSUB top-two/exact hybrid | Direct full screen passes 1,970/1,970 final winners with zero unsafe accepts; 87.97% accept / 12.03% fallback measures 135.74 ms mean versus 220.16 ms exact (1.62x), but fallback worsens p95 from 238.80 to 456.70 ms | Current strongest empirical output switch; retain while integrating into the six-stage head, but the six-bucket error radius is a Chrome-153 observation rather than a portable proof |
| Unsplit hybrid in the six-stage head | 30/30 final winners and every stage check pass, but upper routing sends 51/54 active stages to forced groups-0/1 fallback; warm median is 7.64 s hybrid versus 5.55 s exact | Reject this composition: the uniform full-screen group rate does not transfer to best-first search; retry with the split groups-0/1 bank |
| Split-aware full-bank hybrid in the six-stage head | Group-0/1 repair flips the route to 17/18 accepts and keeps all 10 winners exact, but warm median is still 7.14 s versus 5.99 s exact and cold load is 70.4 s versus 59.2 s | Reject the dual-bank topology: conditional split/full top-two grids cost more than the exact work they suppress; test a compact groups-0/1-only hot path |
| Best-first group-hotspot corpus screen | Across 1,024 states and 5,288 exact-group visits, fixed groups 0/1 are the two most frequent and capture 32.70% of visits, but fully cover only 25.68% of states; 79.00% stop within six groups | Low-ID skew is real, especially in the first two stages, but hot-two must remain an early-stage optimization with exact fallback rather than a general replacement |
| Groups-0/1-only GSUB hot path | Removes every full-bank GSUB reference and routes 16/18 stages through the compact split bank with all 10 winners exact, but warm median is 7.88 s versus 5.21 s exact | Reject: even the focused two-grid certificate adds more dependency/layout work than it removes from the composed head |
| Root-precomputed exact groups 0/1 | Full 10-fixture semantic screen and all 18 stages pass, including group 1→0 and non-hot group 5; clean fixture 0 is 932.1 ms versus 519.7 ms exact | Reject: two eager 256-row grids do speculative work on every mutation and are 1.79x slower even when the route is hot |
| In-place exact upper rows for groups 0/1 | Three rounds pass 30/30 fixtures and 39/39 stage gates; replacing 512 existing upper rows removes 36/39 fine grids and improves warm mean 5.340→3.844 s, with per-round ratios 0.677x/0.790x/0.690x | Retain: this is the first composed head optimization that removes demanded layout work without adding a parallel scorer or grid |
| Hot-two exact-font subset profile | 24/24 mutations and 48/48 stages pass; startup WOFF2 falls 130.61→65.32 MB and conditional cold mean 61.45→49.11 s, but hot mutation is 5.7% slower and first non-hot use lazily requests 66.18 MB | Retain only as a cold/hot-route profile; keep the full-bank mixed head as the loaded-throughput default |
| In-place exact upper hot-K sweep | K=1/2/4/8 all pass 40/40 fixture gates; normalized warm ratios are 0.806x/0.641x/0.729x/0.711x and K=2 is fastest at 3.496 s mean | Keep K=2: wider hot sets reduce routes but the extra twelve-glyph exact upper rows cost more than the removed fine stages |
| Attempted in-place GSUB hot-two upper | GSUB still needs 512 Grid candidates for argmax, adds a 256-row runner-up certificate, and raises glyphs 12→13 per candidate | Reject offline: group selection is not argmax, so the scorer cannot replace the existing rows and only adds work |
| Mixed exact-upper group-size sweep | G128/256/512/1024 retain 1,024/1,024 targets offline, but G128 browser score buckets keep exact while local token IDs drift at 4/8/16/32 px strides | Keep G256: alternate group widths lack a proven identity handoff, so their timing is invalid despite favorable source/work proxies |
| Hybrid exact-stage presentation gate | `content-visibility` stays correct but projects 107.91 ms full-bank versus 106.31 ms for conditional `display`; `visibility` forces exact work and projects 508.47 ms | Retain `display:none/grid`; changing the presentation gate does not remove the fallback-transition penalty |
| Forty-face constant-base GSUB | Shrinks the bounded DOM to 263 elements, but reaches only 97.5% winner agreement, max bucket delta 8,711, and 16.6 ms switching versus 13.3 ms CSS dispatch | Reject: removing complement glyphs trades them for too many independently rounded faces and is slower |
| Lattice-scaled GSUB at 0.03125 | Clears the advance ceiling and matches its rescaled exact page in 80/80 winners, but both retain only 78/80 model-oracle winners; 5.7 ms versus 7.5 ms is only 24% faster | Reject: lattice alignment changes the quantized winner semantics and misses the speed gate |
| Merged-base GSUB at 0.0625 | Folding each static complement into its score glyph gives 80/80 winners and at most one bucket error against a matched-scale exact page, with 4.6 ms switching versus 12.9 ms dispatch | Reject for production semantics: avoiding the advance cap removes clamp behavior present at scale 0.1 and preserves only 78/80 production-baseline winners |
| Split h3 complement for GSUB groups 0/1 | Production-scale split fixes all five overflowing rows; 5,120 candidates have max error 2 and 20/20 winners, while margin >4 accepts 19/20 with zero unsafe accepts; 5.5 ms versus 12.4 ms dispatch | Retain and integrate: one extra glyph/candidate removes the unconditional fallback on the groups that dominate the six-stage search |
| CMAP format-14 indexed fine scorer | A 50 px salvage avoids the 32,768 px advance ceiling, but reaches only 97.5% winner agreement, max candidate delta 8,714, and 37.8 ms switching versus 12.8 ms CSS dispatch | Reject: halving geometry amplifies layout quantization and is slower even before full-vocabulary scaling |
| `sibling-index()` plus locally scoped upper router | Exact across all 197 winner locations, ties, and visited masks; source falls 48.4%, but cold is 32.1 vs 31.4 ms and warm is 1.690 vs 1.613 ms | Retain only as a source-compaction technique; reject as a cold or warm latency optimization |
| Direct 197-way output-head maximum | 30/30 paired routes/tokens pass; full-hot-grid warm mean 4.189→3.234 s, median 3.913→3.110 s, and p90 7.146→4.956 s | New loaded-output-head winner; maximum transport, not hot-row shaping, was the dominant cost |
| Dead output timeline graph pruning | 30/30 checks pass; warm mean is neutral at 1.003x while paired cold load falls 50.51→32.78 s | Retain as the cold-start profile; keep unpruned direct-max as the conservative warm result |
| Physical dead-timeline CSS stripping | Removes 197 registrations/rules and about 53 KB; 6/6 checks pass, but cold changes less than 1% and warm mean is 1.028x runtime-pruned | Reject as a latency strategy; the live dependency graph, not dead stylesheet bytes, produced the pruning win |
| Co-activation B=4 quartets | Holdout shaped rows fall 145.05→93.42 across groups 0/1, but browser mean/median are 1.086x/1.402x direct-max full-grid | Reject: 128 gate containers and interval reductions cost more than the eliminated shaping |
| Packed bucket+group argmax | Removes 198 decoder nodes; 30/30 pass, mean is 0.991x and median 1.021x flat-pruned while p90/max improve to 0.824x/0.805x | Tail-only data point; expanded-width operand arithmetic is not the balanced winner |
| Two-level output maximum, fan-in 16 | 13 chunk maxima plus one root pass 30/30; mean/median/p90/max are 0.975x/0.990x/0.894x/0.875x pruned flat-direct | New balanced loaded winner; Blink benefits from bounded max fan-in |
| Output maximum fan-in 64 | 30/30 pass versus fan-in 16; mean/median regress 1.9%/5.3%, p90/max improve 14.6%/16.6% | Retain only when tail latency dominates |
| Containment on fan-in-16 chunks | Exact, but a direct broad run has a 9.27 s outlier and regresses mean 2.8% and max 87% versus flat | Reject as unstable; keep uncontained reduction nodes |
| Nested functional fan-in-16 maximum | 30/30 exact with no added boxes; p90 is 0.955x materialized, but mean/median regress to 1.043x/1.060x | Reject: syntactic nesting does not replace materialized reduction anchors |
| Packed-four identity decoder | Shrinks both 197-leaf banks, but fails 0/6 initial routes and is 1.557x mean fan-in-16 | Reject: packed arithmetic and dependencies dominate box reduction |
| Chunk/slot identity decoder | Shrinks 394 leaves to 29 and keeps widths below 68 px, but corrected screen fails 0/2 initial routes and is 1.265x mean | Reject: dynamic style branches keep upstream anchors live |
| Block-flow vocabulary-group maximum | 30/30 exact; mean/median/p90/max are 0.921x/0.938x/0.919x/0.913x fan-in-16 Grid | New balanced loaded winner; avoid Grid track sizing while retaining intrinsic-width max semantics |
| Three 256-axis row-wise-int10 coarse shards | 30/30 composed checks; 40% fewer coarse glyphs, loaded mean/median/p90 are 0.980x/0.983x/0.881x five-shard block flow, but cold is 1.111x | New balanced loaded/tail winner; retain five-shard block flow as the cold-start profile |
| Hidden/fast-text score-row hints | 2/2 exact but 1.060x mean and 1.125x median block flow | Reject: hiding paint and disabling font features do not remove anchor/layout work |
| Block-flow dynamic fine stages | 2/2 exact but 1.046x mean group-only block flow; the non-hot fixture is 1.196x | Reject: keep Grid for the selectively active 256-row exact reducer |
| Scrollless block-flow bank | 2/2 exact but 1.104x mean group-only block flow | Reject: the dead-timeline scroll wrapper remains a useful layout boundary |
| One-text-node `min-content` vocabulary groups | Correct local winner on 10/10 vectors, but production bucket/tie decoding fails; 64 groups are 1.239x slower warm and the full 197-group layout exceeds 180 s | Reject: fewer candidate elements do not reduce shaping/layout work and lose the exact identity contract |
| Firefox vector-backend screen | Sub-eight-bit SVG signals survive 0/6 reusable boundaries; 256-axis HVAR loads but the equivalent 257-axis font falls back | Reject engine switching: Firefox provides neither floating filter intermediates nor a wider font-axis bank |
| Production-range homogeneous output head | Reuses all q10/q16 WOFF2 banks at ±266.248; six difficulty-selected Chrome fixtures pass through 23/13/7/1/1/1 active stages with exact final tokens | Retain as the production correctness proof; range/storage scaling is solved, but hard-tail latency remains 8.5–14.2 s |
| Calibrated global q15, six-glyph contender | Two corpus-targeted code moves recover all 1,024 mathematical winners, but real Chrome reaches only 14/16 adversarial winners and is no faster than q16 | Reject as an exact production backend; offline decision calibration does not remove browser transport error |
| Global-q16 display-lattice sweep | Scales 0.1, 1/16, 1/32, and 1/64 remove the catastrophic 32,768 px clamp at aligned scales, but peak at 14/16 adversarial winners | Reject scale tuning as the fix; it removes overflow, not fractional-axis error |
| Final-LayerNorm-bounded q16 with integer user axes | The full 50,257-row, six-font bank keeps all 301,542 measured glyphs below 1,336 px with zero collapse; exhaustive width scans recover 38/38 q16 winners, including every stored state within two production buckets, with maximum candidate error one bucket | Promote the scorer into the retained on-demand cascade; reject the standalone monolithic reducer, whose 197-way outer maximum collapses to 0 px |
| Six-font integer-q16 production cascade | All six production fixtures and every selected group winner match mathematical q16/original float; forced state519 repairs token 2032→37848. Cold load improves 13.6%, but one paired warm round regresses mean 7.7% and median 28.7%; the 23/11-stage fixtures are slightly faster while 7/1-stage fixtures regress | Accept and certify as the accuracy + cold-start profile; reject as the loaded-throughput default and retain the existing q16 backend for warm use |

The native-metric row was also tested with a four-output layout that drops the
outline-backed `ex` metric and doubles each font shard from 128 to 256 axes.
Although that reduces the bank from 924 to 576 fonts, it regresses full-vector
recomputation to 1.169 s and expands the font data to 465 MB. Variation-region
storage grows with axis width, so fewer wide fonts are worse than more narrow
fonts here. Both layouts retain excellent browser transport accuracy; the
failure is runtime and memory scaling, not numeric correctness. See
`../hvar-five-metric-scale/RESULTS.md`.

Font-relative units do offer one useful local composition rule. A nested child
font can use its parent's `1ex`, `1cap`, `1ch`, `1ic`, and `1lh` expressions
directly as five variation-axis values. A live `5x5 -> 1x5` chain works without
geometry, timelines, animations, or registered properties. The rule does not
generalize to a dense vector: a child sees only its immediate parent's metric
set and cannot gather 154 sibling five-value producers. See
`../font-metric-chain-probe/RESULTS.md`.

The cross-shard composition probe establishes a structural lower bound for the
retained exact architecture. Three 256-axis FC faces can contribute to one
fallback run, and normal shaping correctly adds their widths. Font-relative
units still expose one face rather than the summed run; `anchor-size()` and
`calc-size()` are also invalid inside `font-variation-settings`. Because
`GELU(a + b + c)` is not separable into per-shard GELUs, all 3,072 complete FC
preactivations must exist independently before the nonlinearity. With one run
per scalar and width/height pairing, the minimum current geometry bridge is
3,072 shaped run widths plus 1,536 capture boxes. Removing that boundary needs
a new vector-valued browser primitive, a backend retaining more than 256
computed coordinates through GELU, or a changed shard-separable model. See
`../cross-shard-font-composition/RESULTS.md`.

The original boundary oracle measured the older repeated-`avar2` projection.
Its 476.6 ms “projection-only” floor still performed all 3,072 GELU mappings in
each of 768 output runs, so the reported 5.02x ceiling was not a linear-matrix
limit. It remains documented in `../hvar-vector-oracle/REPORT.md`.

Repeating the oracle after the compute-once GELU change reverses that
conclusion. All oracle pages again match all 768 captured widths exactly across
four cases. The retained two-block graph measures 1,710.6 ms, while supplying
post-GELU values leaves a 64.2 ms pure projection. Supplying preactivations
instead takes 88.6 ms, so all 3,072 exact CSS GELUs add only 24.4 ms. Removing
both expensive vector boundaries leaves attention, GELU, and projection at
180.4 ms. Perfect handoffs therefore have a 26.6x measured upper-bound effect;
the general geometry-to-number carrier is now decisively the main blocker. See
`../exact-gelu-vector-oracle/REPORT.md`.

The deconfounded ideal-carrier microbenchmark distinguishes cached revisits
from genuinely new activations. Its original 11.2 ms FC and 5.7 ms projection
figures are shaped-result cache hits. Sixteen never-before-shaped vectors take
38.9 and 52.3 ms through CSS variables, or 91.2 ms per MLP for the two shallow
matrix banks. Literal axis lists take 88.0 ms, so variable substitution adds
only 3.2 ms; fresh shaping is the real matrix-local cost. Repeating just these
two matrix banks across 12 blocks is already about 1.09 seconds per token,
before GELU, transport, attention, normalization, or the output head. See
`../ideal-vector-carrier/RESULTS.md`.

Packing several HVAR output rows into one glyph confirms that output
multiplicity directly controls speed, but also establishes the arithmetic
limit. Two lanes cut the real FC bank from 61.5 to 33.5 ms and four lanes to
18.8 ms. Their RMSE is 60.01 and 24.63, however, versus 0.0003 for one output
per advance. HVAR forms one continuous linear sum; it cannot round each dot
product before radix packing, so every fractional high lane spills into the
lower lane's digits. CSS `round()` and `mod()` run only after the values are
already mixed. Row packing is therefore usable only for values quantized
before shaping, which would recreate the missing per-output boundary. See
`../hvar-packed-output-rows/RESULTS.md`.

COLRv1 supplies a genuine one-object vector output, but moving objects into the
font does not eliminate their internal cost. One variable color glyph emits
3,072 independent axis-driven bars, and one SVG filter immediately reduces the
bars, applies a nonlinear component map, and consumes the result in another
convolution. The page has only 22 live elements and 0.00249 vector RMSE, but
Chrome still walks 3,072 paint layers: it takes 366.4 ms. The existing complex
`gvar` outline emits the same-sized raster in 84.7 ms, despite a larger font.
Keep `gvar` as the bulk one-way exporter. Neither form can turn the raster into
font axes/CSS numbers, and SVG's shared spatial kernel cannot express 768
different dense projection rows without thousands of primitives. See
`../single-glyph-vector-raster/RESULTS.md`.

Registered inheritance removes a large hidden repetition in the retained MLP
projection. The old sparse `avar2` map is evaluated inside every one of 768
output runs. Computing all 3,072 exact GELU values once on an ancestor as typed
custom properties, then inheriting them into a pure linear HVAR projection,
reduces a fresh-vector projection from 463.7 to 111.4 ms (4.16x). Its maximum
output RMSE is also lower, 0.0180 versus 0.0520. An ideal post-GELU vector takes
86.8 ms, so exact CSS `exp`/`pow` adds only 24.6 ms. A control that repeats the
same CSS GELU expressions on every output takes 20.14 seconds, confirming that
the registered ancestor really shares the computed values. Piecewise-linear
8/16/32-knot `max()` forms are slower and less accurate than exact GELU. See
`../css-gelu-projection/REPORT.md`.

The compute-once GELU topology also survives integration into the current real
two-block graph. With attention, FC, residuals, transport, and final extraction
unchanged, a controlled fresh-graph benchmark falls from 2,410.6 to 1,810.8 ms
(1.33x, or 24.9% less latency). Both variants contain 23,528 elements and no
runtime JavaScript. Maximum RMSE against exact float GPT-2 improves from
0.05113 to 0.03792. The bundle grows from 19.403 to 19.819 MB; pure projection
fonts shrink slightly, while registered GELU declarations add net bytes. This
is now the retained two-block architecture. See
`../avar2-gelu-linear-hvar-full-mlp-g13/EXACT_CSS_GELU_TWO_BLOCK.md`.

A marker-bounded Chrome trace of the older two-block HVAR path makes the
remaining cost more precise. Warm mutation is 2.06 s median. Each toggle already
causes exactly one forced layout, with 80-85% of wall time in layout and 15-20%
in style recalculation. Explicit shaping accounts for 32-651 ms depending on
cache reuse, while the generic `performLayout` self time remains near 2.0 s.
The page has 33,471 shadow-tree elements, no anchor-positioning calls, and no
slot reassignment during inference. The terminal-serial/layoutless successor
cuts the graph to 23,528 elements and improves the measured median to 1.615 s,
but still spends nearly the entire traced 1.832 s sample in the same single
style/layout cascade. The next optimization must therefore remove
layout-dependent result carriers and inherited-value fan-out; reducing layout
pass count, anchor lookup, slot churn, or stylesheet bytes cannot remove this
floor. See `../hvar-two-block-toggle-trace/REPORT.md`.

The last row is the arithmetic-coding boundary. Packing works only after values
are discrete and jointly fit the carrier. HVAR is linear and cannot round two
independent real dot products before combining them. The existing post-GELU
timeline packing remains legitimate; packing matrix rows directly inside the
font is not a general replacement for readback.

The geometry-native experiment removes readback altogether, which makes it an
important independent negative result. A left-deep anchor sum fails at 99
inputs; balancing the expression tree makes all 768 inputs resolve accurately
and cuts a hierarchical-anchor implementation from 28.4 seconds to 4.68
seconds per warm navigation. After the page is loaded, changing all inputs and
forcing one 768x768 matrix still takes 1.25 seconds. See
`../anchor-geometry-chain/RESULTS.md`.

Grid/subgrid removes the serial chain for coordinatewise work. It stores a
256-value HVAR output as parallel track widths and cuts unique-input transport
from 28.2 ms to 14.8 ms with identical decoded values. The unresolved boundary
is now narrower: CSS cannot gather the 256 sibling-local numbers into the one
axis list required by the next dense HVAR matrix. See
`../grid-subgrid-vector/RESULTS.md`.

TrueType hinting bytecode was tested as a possible way to keep arithmetic and
intermediate state inside the font engine. A generated variable font used a
constant `SCFS` control and a `GETVARIATION`/`DIV`/`MUL`/`ADD` program across
three pixel sizes. Chrome loaded the font but rendered both instructed glyphs
exactly like the uninstructed control. The official RasterInfo diagnostic also
reported an inactive interpreter in the same browser environment. This rules
out the font VM for the deployed target even though ordinary `gvar`
interpolation remains available. See `../truetype-bytecode/RESULTS.md`.

### Loaded exact-block scaling

Navigation timings above include parsing, font loading, and the first browser
lifecycle. A newer mutation harness keeps the page loaded, changes all 768
inputs, waits until timeline output is fresh, and reads the complete vector.
This gives a cleaner runtime scaling measurement:

| Exact fixture | Warm median | RMSE | Required frames |
| --- | ---: | ---: | ---: |
| block 0, isolated | 363.4 ms | 0.00532 | 2 |
| block 1, isolated | 383.4 ms | 0.0053 class | 2 |
| two isolated blocks, summed | 746.8 ms | — | 4 total |
| two blocks, directly connected | 1,410–1,458 ms | 0.01276 | 4 |

The directly connected pair is almost twice the isolated-work lower bound. A
trace explains the gap. The connected document contains 37,144 layout objects.
After an input mutation, successive layouts touch approximately 23,120,
18,512, 16,206, and 6,914 dirty objects. In one traced run, layout consumed
747 ms, style recalculation 535 ms, font shaping 253 ms, and timeline service
50 ms. Future stages already enlarge the document traversed by earlier
lifecycle passes, so naïvely appending blocks trends toward quadratic work.

The following attempts did not remove that penalty:

| Connected exact variant | Warm median | Result |
| --- | ---: | --- |
| 64 outputs per animation consumer | 1,482 ms | Slightly slower |
| 128 outputs per consumer | 1,458 ms | Best tested chunk size |
| 256 outputs per consumer | 1,604 ms | Slower |
| 512 outputs per consumer | 1,587 ms | Slower |
| all 3,072 FC outputs on one consumer | 2,312 ms | Large animation lists are expensive |
| reset block-0 temporary properties at block 1 | 1,460 ms | Inherited unused values are not the cause |
| layout containment on stages/scrollers | 1,503–1,522 ms | No improvement |
| nested 768-value timeline boundary | 1,677 ms | Adds work without isolating the graph |
| sibling 768-value timeline boundary | 1,529 ms | Truly isolates inheritance, still slower |

`content-visibility` establishes both an upper bound and a limited valid win.
Keeping block 1 hidden cuts a trace from 747 to 304 ms of layout and from 535
to 240 ms of style work. Forced computed-style reads can obtain the right
vector in roughly 0.8–0.9 seconds, but that permanently hidden form is not a
valid page. A valid TinyStories-style handoff now uses a parent style query to
start a 1 ms registered-property animation, which reveals block 1 with the
correct output. It reduces cached-font navigation from 6,667 to 6,077 ms
(8.8%). The 1 ms is a lifecycle boundary, not artificial pacing.

Once revealed, that same block instance remains visible, so later live input
mutations return to the 1.4–1.5 second baseline. Fresh unrolled token stages can
use the one-shot gate directly; a recurrent graph that reuses the same block
needs a re-armable gate. A checkbox-driven re-arm probe now resets the upstream
projection, hides the complete graph, and reproduces the exact alternating
outputs without JavaScript in the page. It does not improve latency: 1–400 ms
handoffs expire inside the roughly 700 ms first lifecycle, while 800 ms finally
keeps block 1 hidden for frame one but still reaches the correct output in
about 1.51 seconds. A 1,200 ms gate is slower. Timer-based scheduling is
therefore rejected; a useful scheduler must be driven by a browser lifecycle
boundary or change the document traversal itself.

#### Geometry-normalized easing transport

A new exact-HVAR variant removes most of the CSS numeric decode work without
changing the matrix backend. For each FC row, `calc-size()` affinely transforms
the glyph's intrinsic width so all 3,072 rows share one geometry-to-
preactivation mapping. A shared 513-stop `linear()` animation easing then maps
timeline progress directly to GELU and writes the registered hidden value. The
projection uses the same idea with a 257-stop curve: its metric geometry
includes the live residual, so the animation writes the final output rather
than exposing progress for a later CSS inversion/scale/bias expression. These
runtime pages remain HTML/CSS-only.

| Loaded exact fixture | Warm median | RMSE vs reference |
| --- | ---: | ---: |
| isolated block, original decode | 369.4 ms | 0.00532 |
| isolated block, FC/GELU easing | 252.6 ms | 0.00542 |
| isolated block, FC + projection easing | 231.1 ms | 0.00402 |
| connected two blocks, original decode | 1,498.7 ms | 0.01276 |
| connected two blocks, FC/GELU easing in both | 1,026.7 ms | 0.00867 |
| plus projection easing in block 1 | 989.6 ms | 0.00824 |
| FC + projection easing in both blocks | **930.1 ms** | **0.00921** |
| plus one global-axis projection run per output | **884.9 ms** | **0.00726** |

The fully eased pair is 38% faster than the same exact-HVAR connected baseline;
global-axis projection runs increase the reduction to 41%.
The small approximation error from the piecewise curves is lower than the
existing font-geometry error in this fixture, so total RMSE also improves. A
matched trace shows where the time changed:

A fresh rebuild and matched Chrome 153 warm-mutation run on September 13, 2026
confirmed the direction after the shared generated CSS changed. With eleven
measured mutations and four animation frames per mutation, the exact baseline
was 1,721.6 ms median at 0.01276 RMSE. The fully eased global-axis pair was
977.2 ms at 0.00726 RMSE: a 1.76x speedup, or 43.2% less warm latency. These
current results are stored in
`view-timeline-two-block-full-exact-current-browser.json` and
`view-timeline-two-block-full-exact-both-global-projection-current-browser.json`.
The older 884.9 ms result used an earlier lifecycle/timing configuration; the
fresh matched comparison is the authoritative number for present sources.

The packed-four hidden-state transport can now be combined correctly with the
global-axis projection and projection easing. A generator bug had previously
emitted global-projection HTML with per-shard keyframes and fonts, leaving all
768 outputs at zero; the combined fixture now produces finite, input-dependent
outputs. Across three fresh browser processes, the process-median warm time was
1,047.8 ms for the exact pair and 956.0 ms for packed-four. Packing therefore
saved only 8.8% even though it cut the live timeline count from 5,568 to 3,264
(41.4%). Its RMSE increased from 0.00726 to 0.04538, or 6.3x. Retain this as a
scaling fixture, but not as the default numerical route: reducing timeline
count does not proportionally reduce the connected layout/font dependency
work.

| Trace phase | Original pair | Fully eased pair | Change |
| --- | ---: | ---: | ---: |
| style recalculation | 534.6 ms | 240.9 ms | -54.9% |
| layout | 747.3 ms | 533.6 ms | -28.6% |
| font shaping | 253.1 ms | 204.7 ms | -19.1% |
| timeline service | 50.0 ms | 49.3 ms | -1.4% |

This validates a useful general rule: normalize row-specific geometry before
the timeline, then share one transport curve, instead of reconstructing every
number with separate CSS math afterward. Giving each projection shard globally
unique variation-axis tags also lets one element shape all 12 shard glyphs.
That reduces the connected document from 37,144 to 27,928 layout objects. It is
still a constant-factor improvement rather than a solution to repeated
whole-document layout.

#### Three-stage structural scaling

A structural third-stage fixture repeats the real block-1 MLP and projection
after the two-block exact chain. It is deliberately a lifecycle scaling probe,
not a claim that repeated block-1 weights are GPT-2 block 2. Every runtime page
is still static HTML/CSS with no JavaScript.

| Three-stage organization | Warm median | Result |
| --- | ---: | --- |
| nested stage, shared block-1 identifiers | 2,007.4 ms | finite, deterministic |
| nested stage, unique block-2 identifiers | **1,969.1 ms** | finite, deterministic |
| final MLP inside declarative Shadow DOM | 2,056.5 ms | slower |
| sibling stage through a new 768-value timeline handoff | 2,165.1 ms | slower |

Renaming every timeline, animation, and property for the repeated stage saves
only about 2%, so identifier collisions are not the scaling problem. Shadow DOM
does not create a cheaper style/layout boundary. Moving the stage to a sibling
does isolate its inheritance subtree, but the added 768-value conversion costs
more than the isolation saves.

The unique nested page contains 41,799 layout objects. Its trace recorded about
1.178 seconds of layout, 680 ms of style recalculation, 475 ms of font shaping,
and 150 ms of timeline service. The third structural stage adds roughly 1.08
seconds beyond the 884.9 ms pair: more than the first two stages together. This
is direct evidence that appending the present representation scales
superlinearly through the browser lifecycle.

Two smaller lifecycle changes were also rejected on the fastest pair:
`visibility:hidden` on the computation scrollers measured 883.8 ms and
`contain:size layout paint` measured 884.3 ms, both indistinguishable from the
884.9 ms baseline. Invisible painting and ordinary containment are not the
remaining cost.

## Consequence

SVG arithmetic is not generally broken. It is appropriate when 8-bit image
precision is acceptable, and scalar RGB dithering can improve it. It is the
wrong numerical backbone for a deep language model because the hidden state is
re-quantized after every filter boundary.

The next optimization target is therefore not another SVG encoding or fewer
font runs. The anchor experiments show that merely reducing carriers and
registered properties is also insufficient: their local anchor scopes require
a 388-level dependency chain. Geometry-normalized easing is now the preferred
exact-HVAR decode path, but its trace leaves layout as the dominant cost. The
next useful experiment must reduce the number of independently laid-out metric
subjects or keep multiple stages within one lifecycle/backend operation. The
tested geometry, metric-bank, collection, and radix variants provide
constant-factor improvements or hit browser-format limits; none yet removes
that requirement.

Until such a primitive or scheduler exists, the hybrid backend is substantially
more faithful than SVG but too slow to scale directly to twelve GPT-2 blocks.
The loaded exact fixtures lower the optimistic isolated-work estimate to about
4.5 seconds for twelve blocks before attention-length growth and the output
head. The connected two-block penalty shows that a naïve full document would
be considerably worse.

## Bulk geometry-to-raster update

Later experiments found a new one-way transport that supersedes the assumption
that every HVAR output needs its own laid-out metric subject. A solid CSS bar's
width can be reduced into one SVG pixel with a 256-tap horizontal convolution.
The synthetic 3,072-value transport took 50.8 ms at 0.00167 RMSE without any
timelines, animations, or per-coordinate custom properties.

Applied to the real GPT-2 FC, ordinary HVAR bars produced all 3,072 post-GELU
values in 99.95 ms at 0.02344 RMSE. Connecting that column to the real SVG
3,072→768 projection kept the full MLP path near 100.10 ms, but projection
error remained 0.40298 RMSE. The equivalent all-SVG fixture was approximately
234 ms at 0.41454 RMSE, so the handoff is faster and is not the source of the
large error. Projection shards of 128 and 64 and 4–16 output range groups did
not materially improve accuracy; 16 groups raised latency to 510.84 ms.

A more compact `gvar` representation puts 3,072 independently varying
rectangles inside one glyph. Its warm time was 84.69 ms versus 81.69 ms for 256
rectangles, with 12 live elements in either case. Three such glyphs implement
the real 768→3,072 FC and feed GELU in 116.19 ms at 0.02753 calibration RMSE and
0.02791 held-out RMSE. The page uses 30 elements and 9.61 MB of WOFF2 assets,
versus 3,090 elements in the ordinary HVAR-bar bridge.

This changes the backend decision in one important way: a font can expose a
whole matrix-output vector to raster geometry without one glyph or DOM node per
output. It does not yet solve reusable state transport. The compact glyph ends
in an SVG pixel column, while a following variable font needs numeric variation
axes. The remaining decisive problem is either a raster-to-axis conversion or
an accurate raster-native matrix product that avoids the measured 8-bit product
surface.

A later row-scaling sweep tested that second option directly. Keeping only 64
inputs per arbitrary projection row stayed near 82 ms through 64 rows, then grew
to 136 ms at 256 rows, 234 ms at 512, and 323 ms at 768. Chrome's convolution
length limit means a real 3,072-wide row needs 12 such shards, producing 9,216
convolutions. Raster-native arbitrary dense projection therefore remains a
multi-second structure even though the first few dozen rows batch efficiently.
See `../hvar-raster-direct-projection/SCALE-RESULTS.md`.

General asymmetric SVG ranges were also screened on 512 disjoint token states.
Two-dimensional range clustering at reusable block-state boundaries reduced
final-state RMSE from 0.225 to 0.097 and improved held-out top-1 from 482/512 to
489/512. The per-channel upper bound reached only 488/512. This is a valid later
accuracy refinement, but not a precision escape hatch; no additional information
survives each eight-bit materialization. See `../svg-asymmetric-ranges/RESULTS.md`.

Two further general corrections also produced only constant-factor accuracy
gains. Three ideal RGB executions with rotating quantization thresholds improved
held-out top-1 from 482/512 to 492/512, but the deployed matrix graph consumes
red/green for signed arithmetic and the real product-dither probe is worse.
A rank-128 final-state error map, folded into the output head at zero runtime
depth, reached 488/512. Neither approaches exact behavior or removes an eight-bit
boundary. See `../svg-rgb-dither-ensemble/RESULTS.md` and
`../svg-output-head-calibration/RESULTS.md`.

The twelve-block activation screen also shows that smarter quantization cannot
be judged before browser transport. Per-channel asymmetric six-bit activations
retained 94.5% of next-token winners numerically, but the corresponding
six-value geometric carrier amplified packet-reconstruction error to 1.24
block RMSE. The browser representation, not only the nominal bit count, is part
of the numerical method.

A Chrome engine trace now locates the superlinear two-block cost more directly.
The connected packed page spent 2.256 seconds in completed layout events and
1.302 seconds in style recalculation, versus 0.350 seconds in font shaping. One
forced layout during parser completion lasted 1.747 seconds. Containment did not
improve a focused run, preloading 36 fonts made it slower, and removing typed
state registrations either had no effect or made dependency expressions more
expensive. The remaining wall is the connected layout dependency graph itself.

## Reproduce

```sh
node tools/test_svg_dither_transport.mjs
node tools/test_svg_dither_matrix.mjs
node tools/test_svg_product_dither.mjs
HVAR_BENCHMARK_PAIRS=10 node tools/test_gpt2_hvar_chain_browser.mjs
HVAR_BLOCK_BENCHMARK_PAIRS=3 node tools/test_gpt2_block_direct_cqi.mjs
TWO_BLOCK_FULL_ROUNDS=4 node tools/test_view_timeline_two_block_full.mjs
VIEW_TIMELINE_TWO_BLOCK_FILE=view-timeline-two-block-full-exact.html \
VIEW_TIMELINE_TWO_BLOCK_REFERENCE=view-timeline-two-block-full-exact-reference.json \
VIEW_TIMELINE_TWO_BLOCK_MUTATION_ROUNDS=7 \
node tools/test_view_timeline_two_block_mutation.mjs

VIEW_TIMELINE_BLOCK_FILE=view-timeline-block-hybrid-fc-projection-easing.html \
VIEW_TIMELINE_BLOCK_RESULT=view-timeline-block-hybrid-fc-projection-easing-mutation-browser.json \
VIEW_TIMELINE_BLOCK_MUTATION_ROUNDS=9 \
node tools/test_view_timeline_block_mutation.mjs

VIEW_TIMELINE_TWO_BLOCK_FILE=view-timeline-two-block-full-exact-b0-all-easing-fc-easing-gelu-s513-projection-easing-s257.html \
VIEW_TIMELINE_TWO_BLOCK_REFERENCE=view-timeline-two-block-full-exact-b0-all-easing-fc-easing-gelu-s513-projection-easing-s257-reference.json \
VIEW_TIMELINE_TWO_BLOCK_MUTATION_ROUNDS=11 \
node tools/test_view_timeline_two_block_mutation.mjs

VIEW_TIMELINE_TWO_BLOCK_FILE=view-timeline-two-block-full-exact-b0-global-projection-fc-easing-gelu-s513-projection-easing-s257-global-projection.html \
VIEW_TIMELINE_TWO_BLOCK_REFERENCE=view-timeline-two-block-full-exact-b0-global-projection-fc-easing-gelu-s513-projection-easing-s257-global-projection-reference.json \
VIEW_TIMELINE_TWO_BLOCK_MUTATION_ROUNDS=11 \
node tools/test_view_timeline_two_block_mutation.mjs

python3 tools/build_view_timeline_three_stage_scale_probe.py
VIEW_TIMELINE_SCALE_FILE=view-timeline-three-block-unique-scale.html \
VIEW_TIMELINE_SCALE_OUTPUT_ID=three-block-unique-full \
VIEW_TIMELINE_SCALE_OUTPUT_PREFIX=b2-final \
VIEW_TIMELINE_SCALE_FRAMES=6 VIEW_TIMELINE_SCALE_ROUNDS=7 \
node tools/test_view_timeline_scale_mutation.mjs

VIEW_TIMELINE_SCALE_FILE=view-timeline-three-block-sibling-boundary.html \
VIEW_TIMELINE_SCALE_OUTPUT_ID=three-block-unique-full \
VIEW_TIMELINE_SCALE_OUTPUT_PREFIX=b2-final \
VIEW_TIMELINE_SCALE_FRAMES=7 VIEW_TIMELINE_SCALE_ROUNDS=7 \
node tools/test_view_timeline_scale_mutation.mjs

node tools/test_geometry_raster_vector_probe.mjs
node tools/test_hvar_raster_fc_probe.mjs
node tools/test_hvar_raster_mlp_probe.mjs
GVAR_VECTOR_OUTPUTS=3072 node tools/test_gvar_vector_glyph_probe.mjs
node tools/test_gvar_vector_fc_probe.mjs
```

## Connected attention-to-MLP scaling

The shallow-sibling attention backend was connected to a real packed GPT-2 MLP
tail. The isolated tail is about 1.03 seconds, while the valid direct connection
takes 2.96/4.30/6.82/14.19 seconds at 2/8/16/32 tokens. Its excess over the sum
of isolated stages grows from 0.96 to 2.70 seconds.

Adding a fresh 768-timeline materialization boundary is worse:
+0.14/+0.86/+2.28 seconds at 2/8/16 tokens. Direct inherited numeric state
remains preferable, but the connected layout dependency graph is itself a
measured scaling wall.

Packed stage boundaries do not currently escape that wall. A 192-timeline
four-value carrier loses too much precision, a 384-timeline two-value scalar
carrier loses low bits in its 16.7-million-pixel packed coordinate, and an
accurate 384-element `left`/`width` carrier is still 0.43/1.12 seconds slower
than direct inheritance at 8/16 tokens. The necessary bulk transport must
remove boxes and decode expressions along with timeline count.

CSS phase gating also fails that requirement. Holding the MLP at
`display:none` until attention completes preserves the output exactly, but
adds 0.12 seconds at eight tokens and 0.32 seconds at sixteen. It avoids one
large simultaneous layout only by introducing additional style/layout
lifecycles, so it is not a route around the dependency-graph cost.

The cold-load curve is not the whole generation curve. Mutating a live
sixteen-token graph takes 2.38 seconds for attention and 3.68 seconds through
the MLP, roughly 1.8x faster than reconstructing the connected page. Chrome is
reusing unchanged K/V geometry. Resetting inherited Q properties around those
cached boxes saves 5.7% on attention-only query mutation but loses end to end,
so accidental inheritance is measurable but not the dominant transport wall.

Fewer formatting contexts are not automatically better. Grouping multiple
token sources into shared score tracks monotonically worsens a sixteen-token
query update from 2.25 seconds (existing per-source tracks) to 2.55 seconds for
two-source groups and 4.14 seconds for one global track. The extra scroller
objects are acting as effective layout partitions; collapsing them enlarges
each invalidated formatting context.

## Output-head representation and scheduling

The full 50,257-row GPT-2 head now selects tokens entirely in HTML/CSS. A
row-wise int10/five-font version is 58.00 MB and measured 0.807 seconds warm,
37.82 seconds cold. A global int11 version folds the row base and scale into one
rule and uses raw glyph text plus one inline tie. It is 50.94 MB and 0.528
seconds warm, but 62.49 seconds cold. Replacing the inline tie with 256
`:nth-child()` selectors slowed the same math to 0.950 seconds, so fewer bytes
can lose to repeated selector matching.

The connected two-block graph proves that lifecycle isolation is essential.
Manual `content-visibility` staging measures about 1.9--2.3 seconds, whereas a
permanently active head takes roughly 12.75 seconds. CSS-only readiness,
container-query chains, and a 1.2-second animation delay do not create a
committed-frame boundary; Chromium resolves them within or after the same
blocked style pass. A later SVG-SMIL experiment found a no-JavaScript
scheduler: Chrome applies an animated SVG `class` value to selector matching,
so `<set>` can make an HTML `:has()` condition true on a later rendering
opportunity. Keeping block 1 at `display:none` for 50-250 ms reduced repeated
fresh exact two-block runs by 21-26% with identical outputs. More importantly,
a CSS animation following the last upstream view timeline can emit
`animationend`, which starts the SMIL signal without a guessed delay.
Container-query activation supplies the same event at coarse/fine/near/dither
boundaries. Five such signals automatically run the complete internally staged
fixture, return token 11 in two of two runs, and finish in 78.12-78.15 seconds;
69.94-70.12 seconds is layout. Targeting HTML directly from SMIL fails, and
wrapping the block in `foreignObject` loses. The retained form is an offscreen
SVG signal plus an ordinary HTML selector. It is one-shot, so recurrent-token
re-arming remains open; internal output-head sequencing is now solved. See
`../smil-stage-scheduler/RESULTS.md`.

On 64 real one-token GPT-2 final states, global int11 retained 63 winners and
row-wise int10 retained 60. Quantization errors are small in RMSE but can flip
near-tied logits. The current browser fixture is correct, but exact general
GPT-2 ranking needs higher-precision output transport or a precise close-score
refinement.

The close-score route is now quantified. A global-int11 coarse head followed
by a selected 256-token global-int16 group measures 0.592--0.619 seconds warm,
but a new adversarial browser fixture shows that OpenType's F2DOT14 coordinate
flooring can still reverse a 0.000622-logit margin. Eight-phase positive
coordinate dithering with a half-step floor-bias correction restores all
256/256 screened numerical winners and repairs the browser fixture. Running it
over all 256 candidates costs 5.816 seconds; running the identical corrected
math over a five-candidate oracle set costs 0.593 seconds. A 0.02-logit gate
needs only 1.05 candidates on average and at most two on the 256-state screen.
The output-head priority is therefore dynamic near-score materialization, not
more global precision or another full-vocabulary font encoding.

That materialization now works in CSS. A 256-carrier geometry reducer exports
the lowest and highest candidate within a 24 px score window; two downstream
precision slots dynamically select those tokens' glyph/base data. Seven-phase
coordinate dithering is the minimum that passes both the adversarial browser
pair and all 256 offline states. The complete dynamic head passes nine browser
fixtures at 1.258 seconds warm. It is slower than the 0.528-second coarse head,
but it is the first general browser implementation here that corrects the
measured coarse/HVAR near-tie failure without evaluating high precision over
the whole vocabulary or relying on a fixture-specific candidate list.

The accurate head now also consumes a live two-block HVAR result. Staged
execution measures 2.566 seconds warm (0.959 seconds blocks, 1.607 seconds
head) and returns dense token 11. Permanently connecting the identical graph
costs 9.083 seconds. This isolates scheduling from arithmetic: the head can
compose with live CSS numeric state, but downstream graphs must not observe
the transient states generated while an upstream matrix chain settles.

Follow-up staging tests narrow that rule. A lifecycle boundary between two
transformer blocks improves 1.009 to 0.958 seconds (5.3%), while internal
coarse/fine/near/dither head staging improves the standalone head from 1.258
to 1.031 seconds. Connected end-to-end time becomes 2.432 seconds. Staging is
essential before a large fan-out and modest inside it, but is not a substitute
for a faster block or coarse-score backend.

Two search-based attempts to avoid the 50,257-row coarse scan are rejected.
Exact L2/box branch-and-bound evaluates at least 50,208 rows on every screened
state. Low-rank query search does not generalize to context: on 96 held-out
2/4/8/16-token states, rank 95 preserves only 59 winning groups and can rank
the true token 3,306th. Full-row evaluation remains necessary with these
representations.

Supervised routing does not change that conclusion. A new 1,024-state screen
uses both random-token and local-text contexts at lengths 2/4/8/16. A linear
768-to-197 group router reaches only 62.9% top-1 and 74.6% top-2 recall. A
deployable 768-to-128/256-to-197 ReLU router is no better, topping out at
59.8%/73.4%. Learning representative rows inside the existing groups misses 3.9% of
held-out winners after scoring 37,824 rows. Reordering the vocabulary into 256
k-means clusters is a better approximate index: probing 32 clusters averages
8,404 exact rows at 97.3% recall, and 64 clusters average 14,515 rows at 98.0%.
However, even 128 or 192 probes miss training/validation states; the only
verified exact point is the full scan. Confidence thresholds either retain
errors or fall back on at least 93% of states. These indexes are useful only if
approximate generation becomes an explicit product choice.

A stronger exact index does not rescue this route. A k-means vocabulary tree
fitted only on training queries combines valid full-space balls, rank-8/16/32
query-subspace interval/residual bounds, and 4/8/16 spherical-cap bounds. All
node bounds are exhaustively valid and all 1,024 row-int10 winners are retained,
but the best configuration still scores a median 50,118 leaf rows (99.72% of
the full scan) plus 1,392 internal nodes. Close frozen-checkpoint exact MIPS
indexing; see `../gpt2-certified-vocabulary-ball-tree/RESULTS.md`.

Quantization-error certification produces a different result because it uses
proof bounds instead of learned confidence. For every row, Cauchy's inequality
bounds the original logit around its quantized score by
`||h||₂ ||w-wq||₂`. A best-first procedure evaluates the group with the largest
upper bound exactly and stops when the best exact score exceeds every remaining
group bound. Across 1,024 contextual states, row-wise int10 needs a median of
three groups, p95 15, and 1,212 exact rows on average; row-wise int11 needs a
median of two groups, p95 five, and 557 rows on average. The true winner is
mathematically retained. This is the first useful exact search frontier for the
frozen head. Its unresolved cost is the full low-precision coarse pass and the
declarative unrolling of up to 49/17 exact-group stages.

The first browser cascade validates that unrolling structure. The int10 upper
head matches all 10 fixture groups in 36.66 seconds cold. Masking the selected
group and recovering the next upper group costs 399 geometry elements and does
not rescore any token. A second exact group reuses the first stage's fonts and
5 MB dispatch table, adding only 256 candidates, 25.4 KB HTML, and 1.5 KB CSS.
The two-stage page reaches all 10 dense winners in 52.66 seconds cold with
2.95-6.38 second fixture mutations.

A six-stage continuation validates the full best-first mechanism: unique group
selection, exact group winners, accumulated tie-broken winner, and final dense
winner all pass 10/10. Chrome reaches the 24-bucket-per-side stop in one to
three groups, but the ungated page still evaluates all six and takes 7.936
seconds median warm. Applying the stop flag to `display` prunes the nested
suffix, correctly reopens it for later harder inputs, and cuts warm median to
4.806 seconds and mean by 42.3%. This is the retained unrolling structure.

Full-depth unrolling is not the one-shot fallback. Expanding to the corpus
maximum of 61 stages keeps only one to three stages active and remains correct
10/10, but repeated visited-group expressions grow CSS from 5.689 to 24.100 MB
and cold plus first result from 49.10 to 199.41 seconds. A two-bank incremental
mask halves CSS to 11.969 MB yet is slower cold at 228.47 seconds because every
boundary inherits 197 mask properties. Retain a shallow gated fast path; the
rare tail needs a different compact fallback or a cached recurrent setting.

A 16-bit packed visited set is better than both representations: thirteen CSS
integers plus `pow`/`mod` preserve exact group order and reduce 61-stage CSS to
11.354 MB. It still takes 214.56 seconds cold because every dormant stage
duplicates the full 197-way router. At six stages it matches 10/10 with
4.68-5.17 second warm medians, statistically indistinguishable from the 4.81
second expanded run. Keep the packed mask for compact state, but use it only
inside a shallow prefix; it does not rescue monolithic full-depth unrolling.

Sibling parallel exact scoring is valid, but its merge must be two-plane. A
single width using 1,024 pixels per score bucket and 1/64 pixel per global-token
tie loses up to 0.234375 pixels at 4-13 million pixel widths and decodes 0/10
tokens. Encoding score plus group in the first plane, then selecting the
already-small winning token anchor in a second plane, passes 10/10 fixtures and
2/2 forced equal-score ties. Current 5.81-7.82 second medians do not beat the
4.81-second gated serial cascade, so keep it as a correct batching primitive,
not the chosen path.

The fast-path cutoff is now measured against corpus coverage. Realized-coordinate
int10 certifies 79.0% of states within six groups, 84.9% within eight, 94.6%
within sixteen, and 99.3% within thirty-two. A 16-stage browser page remains
correct 10/10 but raises cold plus first result from 49.10 to 86.94 seconds and
warm median from 4.81 to 5.63 seconds. Choose six stages for latency; choose
sixteen only when reducing the fallback rate from 21.0% to 5.4% is worth the
startup cost.

The compact-tail screen resolves what the fallback should compute. After six
groups, 215/1,024 states remain. Activating every unvisited group whose upper
bound can still beat the current exact lower bound closes all of them in one
parallel wave: median/p95/max 5/25/70 groups conditional on fallback, or 1,280/
6,400/17,745 exact rows. The conditional mean is 7.76 groups versus 7.60 for a
serial oracle, so the small over-activation is a good trade for constant depth.
Fixed 2/4/8/16-group batches all leave residual fallback states. Build the
parallel uncertainty closure next.

The original ±135.309 font-axis range is also too narrow for the broad corpus:
only 70/1,024 states fit, versus a guarded requirement of ±266.248. A rerun at
that range shows the search remains useful under explicit score allowances.
At 24 buckets per side, int10 rises to median/p95/max 3/18/61 exact groups;
int11 remains at 2/6/22. The browser comparison still chooses int10 for
one-shot inference: the required ten 80-axis int11 faces double shaped glyphs
and take 104.80 seconds cold, versus 36.66 seconds for certified int10. Int11
is retained only for warm recurrent inference, where fewer refinement stages
may offset its 3.17-4.11 second mutation cost.

The allowance's contract is now explicit. At ±266.248, 19 coarse buckets and
8 fine buckets cover the observed Chromium F2DOT14-floor plus 1/64-pixel metric
model when the certified target is global-int16 scoring at browser-realized
coordinates; symmetric 24-per-side is sufficient. Certifying the original
unrounded hidden vector needs a worst-case gap above 589 buckets and is not
portable from current web-font specifications. Keep the realized-coordinate
contract for the CSS pipeline, and describe float-checkpoint exactness as a
separate residual-refinement problem.

The corpus screen makes that choice concrete. Conditional realized-coordinate
int10 needs median/p95/max 3/17/55 groups and 1,322 exact rows on average. The
unrounded-coordinate Chromium bound raises this to 16/117.7/194 and 8,216
rows; the specification-level model reaches 26/161.9/197 and 11,776 rows. Both
strict variants also need an intra-group near-tie refinement, so widening the
cross-group stop alone cannot deliver float-checkpoint exactness.

Packing the same exact scan into three 256-axis fonts instead of five 160-axis
fonts reduces shaped glyph instances by 40%. It improves the coarse selective
stage by about 8% (686.7 to 628.9 ms) but leaves the full accurate head near
1.03 seconds. The coefficient count and argmax element count are unchanged,
and transformer HVAR matrices already use 256-axis shards. Keep the packing,
but do not mistake it for the missing vector-level primitive.

Two layout-only attempts confirm that the remaining cold cost is not ordinary
style isolation. Adding `contain:layout` or `contain:layout style` to all 197
score groups changes a paired 67.71-second cold run by less than 0.3 seconds.
Collapsing each group's 256 candidates into a multiline text run also fails:
newline-only `max-content` sums line widths in Chrome, while explicit `<br>`
elements recover the correct winning group but take 65.70 seconds, slower than
the existing three-shard Grid page. The latter still creates about 50,000 line
break elements and spends 64.06 seconds in layout. Reducing shaped rows, not
changing their formatting wrapper, remains the output-head priority.

## Font-internal composition with avar2

Chrome 153 now accepts an `avar` version 2 mapping whose output coordinates are
consumed directly by HVAR. A browser probe exactly evaluates a cross-axis
`B*A*x` composition without materializing `A*x`. A second probe encodes GELU
as piecewise HVAR regions and evaluates `B*GELU(A*x)` in the same shaping pass.

Dense square scaling is promising: a 256-wide transform/GELU/transform takes
4.19 ms warm and uses a 158.5 KB WOFF2 font. This is the first tested backend
here that keeps a genuine intermediate vector inside a browser-native numeric
engine instead of converting it through layout.

The browser's 256-axis font ceiling prevents a direct full GPT-2-small MLP:
the real `768 -> 3,072 -> 768` graph needs every hidden coordinate to see all
768 inputs before GELU. Avar2 is therefore the preferred backend for naturally
narrow subgraphs, while full-MLP use remains conditional on finding a validated
cross-shard decomposition.

### Validated full-MLP decomposition

The required decomposition is now proven without low-rank compression. Three
ordinary 256-axis HVAR shards form each FC preactivation; the 3,072 hidden
coordinates are divided into twelve parallel groups of 256. Each group carries
only its own preactivations into a projection font, and twelve geometry widths
are added for each of the 768 final outputs.

Putting the nonlinear map directly in every HVAR output row works but repeats
the same GELU table 768 times. It measures 314.4 ms and needs 12.53 MB of
projection fonts. A sparse diagonal avar2 table now transforms each axis from
`z` to `GELU(z)` once; a two-region-per-axis HVAR then performs the linear
projection. The full real `768 -> 3,072 -> 768` block-0 MLP measures 251.0 ms
(248-251 ms across repeated profiles),
uses 3.64 MB of projection fonts, and has 0.0203-0.0249 output RMSE across four
real token states. Browser error against the represented piecewise model is at
most 0.0223.

This changes the backend decision: sparse coordinatewise avar2 followed by
linear HVAR is the preferred MLP projection form. The remaining performance
cost is the 3,072 FC geometry boundary plus twelve parallel font shapes, not
the 256-axis ceiling itself. See `../avar2-gelu-linear-hvar-full-mlp/RESULTS.md`.

## Exact-GELU topology follow-up

After replacing repeated avar2 GELU with one exact typed-CSS GELU per hidden
coordinate, projection parallelism was tested from one to thirteen branches.
The fully parallel graph is slower: it raises the live graph from 23,528 to
33,487 elements and takes about 2.27 seconds versus 1.69 seconds in the matched
screen. Four-branch and five-branch hybrids are also slower. Two- and
three-branch same-tree forms exceed Chromium's effective parser nesting depth
and are numerically invalid.

Nested shadow stages can reset that parser depth while preserving slotted
light-DOM anchor visibility. This makes two- through four-branch hybrids exact,
but the best one-branch shadow form is only 1.0% faster over eight rounds, within
noise. The serial aggregation topology therefore remains the baseline.

Removing all 3,310 registered GELU results and placing typed function calls
directly in the inherited font-axis lists saves 351 KB but is 2.1% slower over
eight rounds. Registered numeric state is not the measured scaling wall.

The backend frontier is now explicit. The bucketed SVG chain recomputes a
12-block single-token state in about 1.15 seconds on the same Chrome build, but
the calibrated natural-token screen retains only 52/64 reference winners. The
exact HVAR/CSS path is much more numerically faithful but needs about 1.77
seconds for two blocks. SVG is the speed branch; exact HVAR is the accuracy
branch. A scalable solution still requires either general higher-precision SVG
surfaces or a bulk geometry-to-CSS numeric transport, not more rearrangement of
the current scalar layout graph. See
`../avar2-gelu-linear-hvar-full-mlp-g13/TOPOLOGY-RESULTS.md`.

## Full multi-token SVG numerical screen

The same SVG-style W8A8 representation has now been screened through full
twelve-block causal GPT-2-small generation, including KV caches, the output
head, and greedy token feedback. On six held-out prompts and eight predictions
per prompt, it preserves 28/48 teacher-forced next-token winners (58.3%). A
free-running quantized sequence diverges from exact GPT-2 after 2.0 tokens on
average.

This is an offline numerical screen rather than the complete browser graph, so
it is optimistic about runtime overhead. Its accuracy failure is enough to
reject blindly extending the current eight-bit SVG chain. The fast branch now
needs a generally reusable higher-precision activation representation before
more end-to-end browser wiring is worthwhile. See
`../svg-w8a8-generation/RESULTS.md`.

## SVG primitive-boundary precision

A sub-8-bit amplification probe now distinguishes SVG operations that retain
internal precision from those that force a quantized image boundary. Adjacent
color matrices, zero offsets, one-input merges, and tiny blurs preserve all
64 tested sub-8-bit values. Two-input arithmetic addition or multiplication,
blend, convolution, and component transfer collapse them to one level.

The result is identical in sRGB and linearRGB, with Display-P3 or Rec.2020
source colors, with Chrome forced to a Display-P3 output profile, and when the
values are carried in alpha. The surviving cases are unary chains Chromium can
keep internal or fuse. The current SVG matrix algorithm necessarily combines
activation and weight images and reduces products, so it crosses the lossy
boundaries. Wide-gamut or alpha-backed SVG is not a hidden higher-precision
backend. See `../svg-internal-precision/RESULTS.md`.

## 12-bit HDR AVIF follow-up

Actual PQ-tagged 12-bit AVIF sources expose more precision than the earlier SDR
and wide-gamut probes: local amplification recovers 2,069 levels across the
4,096-code ramp, with about 970 usable levels in the selected matrix range. An
all-HDR identity-like arithmetic/convolution chain keeps its 32-level narrow
ramp intact across twelve stages under scRGB/HDR output.

The decisive real `64x64` GPT-2 tile still rejects the approach. On default
sRGB Chrome, ordinary 8-bit operands produce 0.02158 RMSE, while 12-bit HDR
activation and weight images produce 0.02212. Adding an ordinary computed
correction to an HDR carrier also retains no extra levels. HDR preserves
precision inherited from decoded source pixels but does not turn newly
computed SVG matrix outputs into a general high-precision vector transport.
See `../svg-hdr-matvec/RESULTS.md`.

## HVAR signed-result range follow-up

Chrome 153 does not clamp HVAR results to the stored uint16 advance range during
shaping. Negative advances subtract inside a positive-width run, results above
65,535 survive, and multiple regions can create a roughly 500k-unit virtual
base before signed contributions are summed. This removes the file-format range
objection to a one-plane int16 scorer.

The first production-shaped use still loses: a six-glyph virtual-base hot row
differs from the retained twelve-glyph high/residual row by one live score bucket
on fixture 1 group 1 and is 1.152x slower in the two-fixture falsification.
HVAR remains the exact numeric backend, but its browser metric rounding is part
of the transport contract. See `../hvar-resulting-advance-range/RESULTS.md`,
`../hvar-virtual-base/RESULTS.md`, and
`../gpt2-virtual-base-oneplane-hot2/RESULTS.md`.

The signed-run primitive is local to a font-shaped run. A single 45,121-unit
compensator covers the measured score domain algebraically, but placing it after
six different fallback-font score glyphs yields 0/2 correct browser routes.
Cross-font negative advances are not recovered by a later positive run; see
`../gpt2-compensated-oneplane-hot2/RESULTS.md`.

Likewise, exact integer decomposition does not imply an exact CSS sum after
layout. Adding a separately shaped aligned-int10 width to a three-glyph exact
residual mismatches 2,397/2,560 live candidate buckets and costs 1.255x the
unchanged twelve-glyph grid. Browser metric snapping is non-distributive across
this boundary; see `../gpt2-aligned-residual-group/RESULTS.md`.

Keeping the old exact rows and pruning candidates is numerically safer, but the
CSS selection graph is not free. A certified group-0 gate reduces 256 exact rows
to 3-15 and passes all browser semantics, yet takes 165.4 ms median versus
160.65 ms for the full grid over 50 balanced mutations. The 256 bound carriers
and hierarchical maxima erase the saved shaping; see
`../gpt2-token-uncertainty-gate/RESULTS.md`.

The common-wrapper version proves the right local topology: B=4/B=8 reduce the
gate graph to 64/32 containers and measure 16.2x/15.2x faster than the fixed
full group by mean while preserving all winners and buckets. On the 1,024-state
group-0 corpus they shape 55.1/68.3 rows on average. However, composing that
gate with the retained hot-2 route duplicates 512 coarse centers. Corrected
direct A/B rejects both integrations: B=4 is 4.5% slower by mean and B=8 is
31.7% slower. This separates a reusable CSS pruning primitive from a losing
placement in the current graph; see
`../gpt2-token-uncertainty-block-gate/RESULTS.md` and
`../gpt2-mixed-hot2-block-gate-b4/RESULTS.md`.

A zero-additional-center integration now succeeds by reusing the paid int10
upper rows as the block-bound source and replacing the outer 197 timeline
inversions with one direct anchor maximum. It preserves every generated route
and exact final token in 30/30 paired checks. B=4 improves the retained
mixed-hot2 warm mean from 4.186 to 3.850 seconds and median from 3.903 to 3.227
seconds, though cold load rises from 40.06 to 51.33 seconds and tail noise
remains. This gate is exact but is superseded by the direct-maximum ablation;
see
`../gpt2-mixed-hot2-reused-upper-block-gate-b4/RESULTS.md`.

The ablation leaves all hot rows eager and replaces only the 197 timeline
inversions with one direct anchor maximum. It passes 30/30 checks and improves
warm mean 22.8%, median 20.5%, and p90 30.6% against mixed-hot2. In a direct
30-pair comparison it is also 5.8% faster by mean than B=4. Removing the dead
timeline elements is warm-neutral but cuts paired cold load 35.1%.
Physically deleting the remaining 197 registrations and proxy rules removes
only about 53 KB, leaves cold load neutral, and regresses warm mean 2.8%.
Therefore the graph removal rather than CSS transfer/parse size explains the
cold benefit. Co-activation clustering reduces untouched-holdout B=4 row work
by 35.6% and still loses to the full grid, isolating gate dependency cost as the remaining
penalty. The full-grid direct maximum is the loaded winner and the pruned form
is the cold-start profile; see
`../gpt2-mixed-hot2-direct-outer-max/RESULTS.md`.

The next router step changes only reduction shape. Thirteen maxima over at most
16 score anchors feed one root, preserving every bucket and tie rule. It passes
30/30 checks and improves mean 2.5%, median 1.0%, p90 10.6%, and maximum 12.5%
against pruned flat direct-max. Smaller fan-in 8 adds too many boxes; fan-in 32
loses narrowly; fan-in 64 improves tail further but regresses mean and median.
Packing group identity removes nodes but is only mean-neutral, and chunk
containment is outlier-prone. Fan-in 16 is therefore the balanced loaded winner;
see `../gpt2-mixed-hot2-hierarchical-outer-max16/RESULTS.md`.

Attempts to compress the remaining identity decoder confirm that live
dependency structure matters more than element count. Four-group packed blocks
and a 13-chunk/16-slot quotient-remainder decoder both preserve the later exact
winner but violate the initial route contract and regress latency sharply. A
single width with nested fan-in-16 `max()` functions remains exact but regresses
mean 4.3% and median 6.0% versus explicit intermediate anchors. The retained
fan-in-16 materialized tree remains the balanced topology.

The 256-token reducer beneath that tree has a better native layout form.
In-flow block children with zero block-size contribute their maximum intrinsic
inline width without Grid track sizing. The direct broad comparison passes all
30 checks and improves mean/median/p90/maximum by 7.9%/6.2%/8.1%/8.7%.
Fixture-1 tracing reduces layout from 1,619.6 to 1,404.7 ms and style
recalculation from 620.4 to 432.9 ms, while text shaping remains approximately
50.5k calls. Block flow is now the balanced loaded output-head topology; the
next scaling problem is row shaping rather than maximum routing. See
`../gpt2-mixed-hot2-blockflow-group-max/RESULTS.md`.

Widening the row-wise-int10 coarse faces attacks glyph work within those same
50.5k runs. Three 256-axis glyphs replace five 160-axis glyphs on 49,745
ordinary rows, while the 512 hot exact rows remain unchanged. The composed
head passes 30/30; loaded mean improves 2.0%, p90 improves 11.9%, and traced
shaping time falls from 667.1 to 468.0 ms. The trade is an 11.1% paired cold
regression. This is now the balanced loaded/tail profile; five-shard block
flow remains the startup profile. See
`../gpt2-mixed-hot2-blockflow-group-max-shard256/RESULTS.md`.

Even preserving the high/residual arithmetic is insufficient if shard packing
changes. Three 256-axis pairs fit the relaxed advance range without bias axes,
but the six-run result moves one live score bucket relative to six 128-axis
pairs. Browser HVAR transport therefore includes per-font-run snapping as part
of its numeric behavior; see `../gpt2-twoplane-256axis-hot2/RESULTS.md`.

## Fixed-checkpoint graph-search follow-up

A full-vocabulary dynamic row selector is no longer the blocking primitive.
Chrome truncates a single numbered GSUB feature value to eight bits, so a
direct 50,257-way `cv00` selector fails above value 255. Splitting the token ID
in radix 255 fixes the limit: `cv01` selects one of 255 low digits and `cv02`
selects one of 198 high digits. The strict CSS-only probe passes nodes 0, 1,
32,767, and 50,256 through two live declarative hops. Its warm switch median is
0.3 ms and its font is 308,432 bytes WOFF2. See
`../gsub-graph-selector-probe/RESULTS.md`.

The selector does not by itself make vocabulary search scalable. A fixed-hop,
CSS-unrollable graph screen over the unchanged GPT-2 embedding rows reaches
only 86.72% held-out top-1 recall at 1,913 mean scored rows; the raw-inner-
product configuration under a fixed 2,048-score cap reaches 74.61%. Standard
`hnswlib` inner-product HNSW reaches 99.22% held-out recall only at `M=32` and
`efSearch=1024`. That implementation exposes neither its row-distance count nor
a fixed-hop trace, and its priority-queue traversal is not the shallow CSS
graph tested here. Retain the radix GSUB selector as a new reusable primitive,
but reject HNSW as a demonstrated <=2k-row CSS output head. See
`../gpt2-hnsw-output-head/RESULTS.md`.

Instrumenting the real `hnswlib` traversal removes the remaining ambiguity.
At the validation-selected `M=32`, `efSearch=1024` point, untouched-test recall
is 99.22%, but the search expands about 1,028 adjacency lists sequentially and
attempts roughly 24.2k 768-dimensional row scores on average (32.4k p95). Thus
`efSearch` is not a candidate-row count: the high-recall point retains about
half a dense scan and adds a thousand data-dependent stages. The exported real
layer-0 graph remains useful for testing a fixed-round batched CSS traversal;
standard priority-queue HNSW itself is rejected. See
`../gpt2-hnsw-trace/RESULTS.md`.

Replacing that priority queue with a fixed-round CSS-native frontier over the
exported real HNSW layer-0 graph removes the thousand-stage chain but not the
work. The best validation-selected point below 2,000 optimistic unique rows
reaches 95.70% held-out recall and requires 8,448 literal padded CSS slots. The
best fixed <=2,048-slot schedule reaches 84.77%; reaching 99.22% test recall
requires 33,024 slots. This closes both sequential and batched HNSW variants
under the target budget; see `../gpt2-hnsw-batched-frontier/RESULTS.md`.

Two shallower candidate generators confirm that this is not merely a poor
graph construction. Overlapping IVF with the existing 256 centroids and a
hierarchical 1,024-leaf refinement reaches only 83.20% validation recall below
2,000 duplicate-aware rows. Its cheapest >=99% validation point costs 11,686
rows and falls to 98.05% on untouched test states. Asymmetric norm-lifted MIPS
LSH is much worse: the validation-selected <=2,000-row point reaches 2.34%
held-out recall, while the best tested point reaches 76.17% at roughly 41,246
rows. Both screens include duplicate list/bucket entries and fixed-slot padding
rather than assuming a free dynamic union. See
`../gpt2-overlapping-ivf/RESULTS.md` and `../gpt2-mips-lsh/RESULTS.md`.

## Structural attention-reduction follow-up

Native inline layout can perform the attention weighted sum directly, but it
does not improve the graph shape. Both `font-size` and `zoom` carriers match a
real block-0 reference accurately and react to independent score and value
mutations. At context 16, however, the better `font-size` route takes 1069.2 ms
versus 823.0 ms for the retained flat reduction and materializes 12,288 value
spans. This rejects the carrier on speed and O(context * width) DOM scaling,
not correctness; see `../inline-attention-reducer/RESULTS.md`.

## Certified blockwise vocabulary bound

Splitting each tied output row into 96 eight-coordinate residual blocks makes
the Cauchy certificate dramatically tighter without changing GPT-2's
architecture or checkpoint. It retains the float winner on all 1,024 saved
states and reduces test exact work to a mean 364 rows (maximum 1,536), compared
with 1,164 mean rows for the global certificate. The current browser encoding
is still rejected: one 96-axis residual glyph per row makes a 64-group mutation
2113.9 ms versus 399.6 ms for the global control, while the saved exact groups
are worth at most about 102 ms under the measured upper bound. Retain the
mathematical certificate, reject the per-row carrier; see
`../gpt2-blockwise-cauchy-head/RESULTS.md`.

Moving that 96-block certificate to the 256-row group level fixes the carrier
economics. One residual glyph per group (197 total) retains all 1,024 oracle
winners and reduces test exact work from 1,164 to 567 mean rows. The live full
coarse pass is at performance parity with the global certificate: 1049.8 ms
versus 1085.3 ms mutation and 40.40 s versus 41.27 s cold layout. All 96 axes
and all 197 glyph geometries were verified live against independently predicted
outward buckets. Retain this representation for an integrated exact-group
cascade; see `../gpt2-groupwise-cauchy-head/RESULTS.md`.

The first integrated three-stage cascade attempt is rejected without
discarding the carrier. It inserted the group bounds into the older
scroll-timeline one-step topology; the live bound geometry remained outward
safe, but the outer selector collapsed to the same three groups for every
fixture and passed 0/6 route/fine/stop/winner checks. Its 2918.5 ms loaded
median is diagnostic only because broken routing forced all stages active and
the exact fallback was absent. Do not extend that base. Any later integration
must begin with a small correctness gate on the retained block-flow/fan-in-16
topology; see `../gpt2-groupwise-cauchy-cascade/RESULTS.md`.

That replacement gate now passes. A strict 16-group page combines the retained
zero-height block-flow reducer and fan-in-16 maximum with one live 96-axis
Cauchy glyph per group. Six fixtures, including a 14-way browser tie, select
the same group as a live-control-plus-independent-bound oracle; all 96 axes and
16 group glyphs react, and all 96 measured bounds are exact and outward-safe.
The candidate's five loaded mutations average 49.6 ms versus 85.7 ms for the
otherwise identical no-bound control, which is evidence of no composition
penalty rather than a speedup claim. Retain this composition as the base for a
new exact cascade; it has not yet demonstrated vocabulary selection or
end-to-end inference. See
`../gpt2-groupwise-cauchy-blockflow-gate/RESULTS.md`.

The resulting direct-target cascade is the first retained full integration.
Instead of bounding float-minus-int10 and spending slack around a different
target, it builds the 96-block group certificate directly from
global-int16-minus-rowwise-int10 residuals. The strict script-free browser page
passes 10/10 live route, exact-shadow, incumbent, stop, and final-token checks;
all fixtures certify within three stages. All 96 axes and 195 non-hot bound
glyphs are live, and 1,950/1,950 measured bounds are conservative. Four paired
mutations average 1,979 ms versus 2,858 ms for the retained scalar-bound head
(0.693x), with a 0.903x median ratio. Retain this as the best fixture-range
output head. A production-range 1,024-state screen retains every target and
averages 1.996 exact groups at the conservative 48-bucket margin, but only
984/1,024 states close within six stages; production still needs ±266.248
score fonts and an exact tail. See
`../gpt2-groupwise-cauchy-blockflow-cascade/RESULTS.md`.

A 22-stage gated variant tests the cheapest corpus-complete serial tail. It
also passes 10/10 browser fixtures, and the production-range screen's worst
saved state needs exactly 22 groups. The longer page grows routing CSS from
0.76 MB to 3.87 MB and cold load from a saved 45.12 s to 52.51 s; its four
loaded samples remain faster than the corresponding 22-stage scalar control
but are too noisy for a stable comparison with the six-stage direct page.
Retain 22 stages as the completeness topology, while keeping six stages as the
loaded fast-path default. See
`../gpt2-groupwise-cauchy-blockflow-cascade-unrolled22/RESULTS.md`.

The production-range follow-up removes the supposed need for another large
font bank. HVAR's quantized weight deltas are independent of hidden range; the
range enters through normalized CSS coordinates and output gain. Widening the
axis denominator to ±266.248 while retaining the source gain scales every
logit by the same positive 0.508206, preserving argmax and the source carrier
error envelope. A naive version that also multiplied row factors by 1.9677
failed 3/6 fixtures because it amplified interpolation error. The corrected
23-stage page passes 6/6 difficulty-selected Chrome fixtures, including the
worst 1,024-state corpus member, generates only a 16.8 KB bound font, and
reuses all large q10/q16 assets. The full corpus averages 2.402 exact groups,
has p95 7 and maximum 23 at the calibrated 49-bucket stop. Retain this as the
production correctness/range milestone, not as the low-latency loaded default:
the 23- and 13-stage mutations still take 14.2 and 8.5 seconds. See
`../gpt2-groupwise-cauchy-blockflow-production-range/RESULTS.md`.

Selective rowwise-q12 precision is the first retained hard-tail latency
improvement on that production page. Replacing q10 rows in the 32 groups most
often visited by baseline tail states adds 24,576 shaped glyphs and 10.77 MB
of radix-64 two-plane fonts, but reduces the 27-bucket-safe corpus route to
mean 1.912 / p95 5 / max 16. Six paired live routes fall from
19/18/17/13/10/1 stages to 17/14/13/11/8/1; four timing samples improve from
12.489 s to 9.674 s mean (0.775x). All six final browser outputs and buckets
match the retained page. One state makes both pages choose token 2032 instead
of the original/global-q16 mathematical winner 37848, exposing an inherited
q16 font-transport hole rather than a q12 regression. Retain selective q12 as
a backend-equivalent latency candidate, not a stronger mathematical-target
proof. See
`../gpt2-groupwise-cauchy-blockflow-production-selective-q12-top32/RESULTS.md`.

A more ambitious fixed-depth q10 -> q12 -> q16 closure looks excellent
offline but loses in Chrome. With 27 buckets at both transitions, B=4 retains
all 1,024 q16 targets and models 2,771 dynamic glyphs versus 5,012 for a direct
q10 -> q16 closure and 7,380 for the serial exact path. The real-font browser
crossover still favors the one-wave path at every tested scale: at the global
418-row -> 22-row budget, progressive takes 277.57 ms versus 259.67 ms, a
1.069x regression. The extra layout dependency dominates the saved shaping.
Reject this topology unless the two precision transitions can be fused. See
`../gpt2-progressive-precision-closure/RESULTS.md`,
`../gpt2-progressive-precision-block-gate/RESULTS.md`, and
`../gpt2-progressive-precision-crossover/RESULTS.md`.

## Custom-browser F16 filter audit

A source-level audit finds a credible non-model moonshot: force image-filter
save layers to RGBA16F at Chromium's two paint-op raster playback sites. Skia
already propagates the destination filter color type to materialized
intermediates, so this directly attacks the fast SVG backend's observed 8-bit
surface failure without changing GPT-2 architecture or checkpoint weights.
It is not a complete one-line fix: general `feComponentTransfer` still uses
8-bit LUTs, and large convolution kernels use an A8 coefficient texture. The
first build gate is therefore a fully instrumented 1/65535 survival chain,
not another screenshot-only HDR probe. This workstation has no Chromium
checkout and only 4.9 GiB free versus Chromium's documented 100 GB minimum,
so implementation needs different build storage or a remote builder. See
`../chromium-f16-svg-filter/RESULTS.md`.
