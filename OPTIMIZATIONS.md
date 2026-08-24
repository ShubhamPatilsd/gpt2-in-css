# CSS inference optimization research

This audit looked for techniques that could reduce the generated circuit, not
just make its source prettier. The measured before/after results are:

| Circuit | Before | After | Change |
|---|---:|---:|---:|
| Pretrained `model.css` | 28,662,934 bytes | 10,903,438 bytes | -62.0% |
| Pretrained typed properties | 154,197 | 51,980 | -66.3% |
| Toy transformer `model.css` | 1,646,406 bytes | 1,330,393 bytes | -19.2% |
| Toy transformer typed properties | 4,509 | 3,069 | -31.9% |

A later checkpoint-specific exact optimization reduced the pretrained
one-token stylesheet further to 23,968 bytes and the four-token autoregressive
stylesheet to 561,026 bytes. Interactive graphs for one through four prompt
lengths now share one 1,508,399-byte recurrent stylesheet.

## Applied

### Native CSS custom functions

CSS `@function` can take typed arguments, define local custom properties, and
return a calculated value. It shipped in Chromium 139. The compilers now emit
one reusable `--gelu()` function, so every GELU activation needs one registered
output instead of six globally registered intermediates. Deep autoregressive
graphs materialize those intermediates because Chromium invalidated the reused
function after several chained dependency levels.

Sources: [W3C CSS Functions and Mixins](https://www.w3.org/TR/css-mixins-1/),
[Chrome 139 release notes](https://developer.chrome.com/release-notes/139).

### Finite-domain dead-output elimination

Before the convex-hull pass, the pretrained page computed every one of its
50,257 logits and their exact maximum. Its finite UI only needed equality checks
for the two tokens produced by its three build-time prompts, so the compiler
removed 50,257 one-hot properties, 50,257 weighted token-ID properties, and a
summation tree. The later hull optimization supersedes the remaining dense
logit calculation.

This optimization is valid for a finite set of controls.

### Two-dimensional convex-hull language head

`tiny-gpt2` ties its language head to 50,257 two-dimensional token embeddings.
A token can maximize a dot product only if its embedding lies on the convex
hull. Just 16 embeddings meet that condition; the other 50,241 logits cannot
win for any hidden state. The compiler now uses those vertices for an exact
arbitrary-token decoder and autoregressive embedding selection.

This is special to the width-two test checkpoint. It is not expected to reduce
ordinary 768-dimensional GPT-2 meaningfully, because high-dimensional point
sets commonly place most points on the hull.

### Zero-script prompt state

CSS cannot inspect a text input's live string, so the interactive pages expose
native token `<select>` controls instead. A selected option has dynamic
`:checked` state; generated `:has()` rules map 2,066 selectable token IDs to
their two raw embedding values. Each prompt position adds about 253 KB
of lookup CSS. The model graph and full-vocabulary output argmax remain exact;
only the available prompt-token UI is bounded.

### Animation-latched autoregressive stream

The interactive compiler emits one transformer step over a fixed 16-token
window. A four-phase animation clock alternates paused `execute` and `store`
animations. Unregistered custom-property banks latch the winning embedding,
context count, and growing `<content-list>` between cycles. Each state update
forces the same circuit to resolve the next token; future tokens are not
present in the initial dependency graph. This follows the state-bank technique
demonstrated by [x86CSS](https://github.com/rebane2001/x86CSS).

## Investigated but not applied

### CSS CPU/state-machine emulation

[x86CSS](https://github.com/rebane2001/x86CSS) also demonstrates a complete
CSS-only x86 emulator. This project applies its animation clock and state-latch
idea directly to a transformer step instead of interpreting x86 instructions.
It does not remove GPT-2's weights; applying the same recurrent structure to
GPT-2 Small would still make each clock cycle resolve its enormous matrix graph.

### Model pruning

[SparseGPT](https://arxiv.org/abs/2301.00774) reports at least 50% one-shot
sparsity for large GPT-family models with minimal accuracy loss. Zero weights
could be omitted from generated dot products, so this is a genuine future
factor-of-about-two optimization. It is not applied to the two-dimensional
`tiny-gpt2` checkpoint: pruning would change the reference model, requires a
calibration/quality study, and still leaves the dense 50,257 by 768 language
head as a major cost unless that head is pruned too.

### Weight quantization

[GPTQ](https://arxiv.org/abs/2210.17323) can compress ordinary model storage to
three or four bits per weight. CSS has no packed numeric array or fused integer
matrix kernel, so each weight must still appear as an arithmetic literal in a
separate product. Quantization can shorten literals somewhat, but it does not
reduce the 123.55 million term count and introduces scale/dequantization work.

### SVG convolution and typed `attr()`

SVG's [`feConvolveMatrix`](https://www.w3.org/TR/filter-effects-1/#feConvolveMatrixElement)
accelerates a shift-invariant image kernel, not an arbitrary dense matrix, and
its output pixels cannot feed CSS numeric custom properties. Typed `attr()` can
read one number from markup, but CSS has no list indexing or reduction loop, so
moving weights into HTML attributes only relocates the same data.

## Remaining asymptotic boundary

The applied work removes dead nodes and repeated nonlinear scaffolding. It does
not change the dominant cost: GPT-2 small still requires 123,550,464 explicit
multiply-accumulate terms for a one-position transformer pass and language
head. A major next leap needs either model-level structure/sparsity or a runtime
with tensor storage and matrix operations.
