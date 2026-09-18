# Unconventional execution directions

Research date: 2026-09-17. This is a source-backed shortlist, not a new benchmark
or implementation. Three independent research agents reviewed font internals,
raster computation, and algebra/representation, alongside the root review of
the browser lifecycle. No browser/model code was changed for this research.

The latest owned-attention run completed two tokens through all twelve layers
in 99.487 seconds. Its renderer counters separate 45.673 seconds of style,
12.801 seconds of layout, and 40.210 seconds of other work. Those counters do
not isolate pure matmul arithmetic or prove that all style work is redundant.
The target here is eliminating intermediate representations and handoffs,
not projecting a known percentage speedup from these counters.

## 1. Fuse an attention contribution inside a font

**Proposed mechanism.** A single head's query, one cached key and one cached
value require 64+64+64=192 coordinates. Unlike GPT-2's full MLP, this fits below
the 256-axis ceiling observed in this Chromium setup, with room for temporary
axes and scale inputs. Use avar2's cross-axis remapping to form the query–key
dot product internally, then HVAR regions to approximate the exponential and
emit its product with each value coordinate. Emit a denominator contribution
as well. Sum token contributions with layout and divide once at the output.

The intended change is to remove the intermediate score readback and CSS
softmax state. It still needs real KV retention, input delivery, output
aggregation and a generation protocol. It is not a claim that an entire head
with an arbitrary history fits into one font instance.

**Basis.** The [avar2 proposal](https://raw.githubusercontent.com/harfbuzz/boring-expansion-spec/main/avar2.md)
defines a remapping pass whose results feed the font's later variation tables.
The repo already demonstrates [small internal matrix–GELU–matrix compositions](../avar2-hvar-mlp-scaling/RESULTS.md).
That synthetic primitive uses a coarse nonlinear approximation and is not a
GPT-2 accuracy or token-speed measurement. The attention composition above is
an inference from the primitive, not an existing successful probe.

**Risk.** Stable softmax is the main numerical obstacle. A bounded exponential
table must handle score range and cancellation of a common scale without
underflow or clipping. Font-instance updates may repeat the remapping work
across outputs, and changing Q may destroy useful value-rendering reuse.
The [earlier bilinear QK-only probe](../bilinear-hvar-attention/RESULTS.md)
was slower than its numeric CSS alternative, so merely putting a dot product
in a font is insufficient.

**First test.** One real 64-dimensional head with four cached tokens. Check all
64 final values against the current complete attention path, including difficult
score ranges. Time input publication, final reduction/division and output
availability together. Reject if the complete local operation is slower or
accuracy requires restoring the removed score boundary.

## 2. Compile arithmetic into glyph substitutions

**Proposed mechanism.** Encode fixed-point values as glyph strings. Compile
addition, carry propagation, multiplication by constants and activation lookup
into ordered GSUB substitutions. Intermediate results remain glyph identities
inside shaping; CSS supplies an input stream and receives final results.

**Basis.** The [GSUB specification](https://learn.microsoft.com/en-us/typography/opentype/spec/gsub)
allows contextual rewrites and successive lookups that consume prior lookup
results. [CSS counters](https://www.w3.org/TR/css-counter-styles-3/) offer a
possible declarative input encoding. This is a proposed finite circuit compiler,
not a proven general neural runtime. Existing repo GSUB work performs
[selection and graph lookup](../gsub-graph-selector-probe/RESULTS.md), not the
numeric carry circuits proposed here.

**Risk.** Font tables, glyph streams and lookup counts could become enormous.
Generated content may split into shaping runs, output routing may require new
boundaries, and [HarfBuzz has operation/context limits](https://raw.githubusercontent.com/harfbuzz/harfbuzz/main/src/hb-limits.hh).
No bypass of those limits is proposed. A smaller precision changes the model's
numerical behavior; a fixed-point proof is not a full GPT-2 equivalence result.

**First test.** Exhaustive 8-bit addition with carry and a nonlinear lookup,
followed by an 8→8→8 fixed-point chain inside one styled text run. Include input
encoding and final decoding in timing. Track font bytes and operation growth
before increasing matrix width. This is the most unusual stock-browser option,
but also one of the least certain to scale.

## 3. Build a digital circuit from transparent and opaque pixels

**Proposed mechanism.** Represent each bit as a pixel's alpha: transparent is
zero, opaque black is one. Keep all intermediate activations as bit planes in
a static SVG filter graph. Compose Boolean gates and explicit carry networks
instead of accumulating approximate brightness values.

For inputs RGBA=(0,0,0,a) and (0,0,0,b), ordinary compositing gives:

| Gate | Operation | Output alpha |
| --- | --- | --- |
| AND | `in` | ab |
| XOR | `xor` | a(1-b)+b(1-a) |
| NOT | opaque-black flood `out` a | 1-a |
| OR | `over` | a+b(1-a) |

These follow the [compositing specification](https://www.w3.org/TR/compositing-1/#porterduffcompositingoperators)
and are exposed by [SVG feComposite](https://www.w3.org/TR/filter-effects-1/#feCompositeElement).
This establishes a valid gate construction, not measured Chromium exactness.
Alpha encoding is deliberate: arithmetic XOR applied to RGB bits in two opaque
images would also set output alpha to zero, invalidating that naive encoding.

This is different from the [old signed-bitplane experiment](../svg-signed-bitplane-dot/RESULTS.md),
which still used analog reductions and lost precision. [BISMO](https://arxiv.org/abs/1806.08862)
provides bit-serial matrix architecture ideas, but its FPGA performance does not
predict browser performance.

**Risk.** One bit per pixel, many filter passes and large temporary surfaces.
Integer-aligned samples, full filter bounds and no resampling are necessary.
Nonlinearities, normalization, argmax and pixel-to-next-token feedback all need
working implementations. Avoiding style updates may simply move the bottleneck
to rasterization and memory.

**First test.** Verify gate truth tables and long carry chains after forced
materialization, then a signed 64×64 integer matvec feeding a nonlinear operation
and second matvec without CSS readback. Include enough accumulator bits, extreme
cancellation inputs, surface memory and transfer costs. Reject early if pass
count makes even this graph slow.

## 4. Train a model to communicate through glyph codes

**This changes the model/checkpoint.** Learn short integer codes representing
activation groups, with tables for their contributions to following operations.
Map codes to glyphs and sum their static advance contributions. The ambitious
form trains adjacent stages to consume and produce codes directly, avoiding
reconstruction and transmission of every floating-point coordinate.

[LUT-NN](https://arxiv.org/abs/2302.03213) learns centroids for lookup inference;
[MADDNESS](https://proceedings.mlr.press/v139/blalock21a.html) explores cheap routing;
[LUT-LLM](https://arxiv.org/abs/2511.06174), revised March 2026, demonstrates
activation/weight codebooks and table computation on a language model using
an FPGA. The browser/glyph application is our proposal. Their performance
figures cannot be transferred to this renderer.

An alternative model co-design is independently computable MLP groups with
at most 256 live font inputs. The existing font-internal composition then
becomes directly applicable. This cannot be obtained by arbitrarily splitting
the original dense MLP: GELU must follow the sum of all input contributions.

**Risk.** Code assignment may be more expensive than the operation it replaces;
tables can balloon and quality can degrade. The repo's
[post-training structured-weight approximations](../structured-css-matrices/RESULTS.md)
and [rank-256 FC approximation](../gpt2-fc-lowrank/RESULTS.md) already failed.
This direction requires learning/distillation and held-out quality evaluation,
not relabeling those failed approximations.

**First test.** Learn one matrix's compact input interface with its next nonlinear
consumer retained. Measure the connected encoding→glyph lookup→result path
on unseen real activations, including routing and table memory. Do not begin
whole-model conversion if that connected component already loses.

## 5. Make the SVG backend numerically suitable

**This changes the browser.** Keep vectors in image/filter storage across stages,
but patch Chromium/Skia so filter intermediates use RGBA16F and nonlinear
operations avoid eight-bit lookup-table truncation.

This is a revival of an existing investigated direction, not a new discovery.
The [F16 audit](../chromium-f16-svg-filter/RESULTS.md) identifies possible scoped
patch sites and independent precision traps. Current
[Skia source](https://skia.googlesource.com/skia/+/refs/heads/main/src/core/SkCanvas.cpp)
still exposes F16 save-layer allocation. Ordinary CSS or an HDR input does not
guarantee that every computed intermediate uses that path.

**Risk.** F16 surfaces alone do not fix byte-based component-transfer tables,
coefficient representations, reductions or accumulation error. Existing SVG
model fixtures had unreliable decisions; their fast timings are not valid
full-model generation speed claims. Building a custom browser also needs a
different build/storage setup from the small existing experiment artifacts.

**First test.** Carry 64 closely spaced values through multiply, reduction,
nonlinear transfer and residual addition with forced intermediate surfaces.
Instrument actual formats and verify the values survive before model tests.
Then require held-out decisions and autonomous next-token feedback, not only
a rendered output image.

## Selection

For the present unmodified-browser/no-runtime-JS rules, start with the small
fused-attention probe: it is naturally narrow and directly targets a boundary
in the existing system. GSUB arithmetic is the most unusual alternative and
deserves a tiny compiler proof; alpha-bit circuits are a separate, riskier
execution backend. If model changes are acceptable, learned glyph-code
interfaces may remove more of the existing computation/communication pattern.
If browser changes are acceptable, the F16 path has a concrete source-level
starting point, but no validated token speedup yet.

Avoid presenting `contain: style`, compositor promotion, generic packing,
HDR sources, TrueType bytecode or simple avar2 tiling as untested shortcuts.
Containment does not generally stop custom-property inheritance, geometry
readback defeats a compositor-only pipeline, and the repo already contains
negative or limited results for the remaining mechanisms. The
[font metric chain](../font-metric-chain-probe/RESULTS.md) works for five values
but does not solve the wide gather; the [connected avar2 MLP](../avar2-gelu-linear-hvar-full-mlp/CONNECTED_RESULTS.md)
already explores tiling and its transport costs. The
[TrueType probe](../truetype-bytecode/RESULTS.md) was ignored by the tested
Chrome/macOS font path.

All proposed performance tests must measure a changing input through a useful
downstream consumer, including readback and retention when needed. A faster
isolated glyph or filter is insufficient evidence for faster token generation.
