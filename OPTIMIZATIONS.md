# CSS inference optimization research

This audit looked for techniques that could reduce the generated circuit, not
just make its source prettier. The measured before/after results are:

| Circuit | Before | After | Change |
|---|---:|---:|---:|
| Pretrained `model.css` | 28,662,934 bytes | 10,903,438 bytes | -62.0% |
| Pretrained typed properties | 154,197 | 51,980 | -66.3% |
| Toy transformer `model.css` | 1,646,406 bytes | 1,330,393 bytes | -19.2% |
| Toy transformer typed properties | 4,509 | 3,069 | -31.9% |

## Applied

### Native CSS custom functions

CSS `@function` can take typed arguments, define local custom properties, and
return a calculated value. It shipped in Chromium 139. The compilers now emit
one reusable `--gelu()` function, so every GELU activation needs one registered
output instead of six globally registered intermediates. The pretrained
decoder also uses a reusable `--is-maximum()` predicate.

Sources: [W3C CSS Functions and Mixins](https://www.w3.org/TR/css-mixins-1/),
[Chrome 139 release notes](https://developer.chrome.com/release-notes/139).

### Finite-domain dead-output elimination

The pretrained page still computes every one of its 50,257 logits and their
exact maximum. Its UI, however, only accepts three build-time prompts whose
winners comprise two distinct tokens. The compiler now emits equality checks
for those two candidates instead of 50,257 one-hot properties, 50,257 weighted
token-ID properties, and a summation tree. Each candidate contains its static
token ID, and the exact CSS maximum comparison determines which one is visible.

This optimization is valid for a finite set of controls. An arbitrary-text or
fully autoregressive interface still needs a general token decoder and an
embedding-selection stage.

## Investigated but not applied

### CSS CPU/state-machine emulation

[x86CSS](https://github.com/rebane2001/x86CSS) demonstrates a real CSS-only x86
emulator, including a JavaScript-free clock built from animation and style
container queries. That is useful proof that CSS can execute a serial machine,
but it does not remove GPT-2's weights. Serially interpreting 123.55 million
multiply-accumulate terms would also trade the current parallel style graph for
an enormous number of browser restyles.

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
