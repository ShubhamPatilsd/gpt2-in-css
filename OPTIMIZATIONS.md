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

### Exact lazy clustered TinyStories output head

The width-64 TinyStories language head cannot use the width-two convex-hull
shortcut. An exact ball-cluster index instead computes a safe upper bound for
each token cluster and invokes only the CSS custom functions that can still
contain the winner. On 35 deliberately hard real hidden states, the complete
50,257-token score, winner ID, and 64-number feedback embedding took 743–755 ms
median, down from 4.28–4.36 seconds for the eager registered-property feedback
graph. All measured winner IDs matched NumPy. The tradeoff is 292 MB of CSS and
about 1.28 GB of renderer RSS. Full measurements are in
[`output-head-benchmark/RESULTS.md`](output-head-benchmark/RESULTS.md).

### Shared output-head token functions

The first clustered feedback graph repeated the same token dot products in its
maximum and winner-recovery functions. Defining one shared lazy dot function
per token reduces the losslessly formatted exact score/winner/embedding head
from 282,137,529 to 206,464,160 bytes (-26.8%). A complete
transformer-plus-shared-head update took
670–702 ms median with zero wrong winners in the browser tests.

### TinyStories incremental transformer and KV cache

The TinyStories compiler now emits one width-64, eight-layer transformer pass
for only the newest position. Each layer consumes stored keys and values from
an eight-token sliding window, then the animation state machine appends the new
key/value vectors and winning token embedding. This avoids recomputing every
causal prefix. For `Once upon a time`, the recurrent CSS graph matched NumPy's
four greedy token IDs and produced `, there was a`.

The transformer/cache source is 21,433,725 bytes; with the shared exact head,
the linked graph is 234,462,480 bytes. Chromium required an eight-second clock
to keep the execute/store phases stable. The full measured run took 42.69
seconds for four outputs and used roughly 1.4 GB of renderer RSS. Details are
in [`tinystories/RESULTS.md`](tinystories/RESULTS.md).

### Timer-free nested CSS state propagation

The fixed animation clock is not reliable across browser load levels: a later
eight-second-clock run reset its state bank mid-generation. The strict
HTML/CSS-only page instead nests predeclared model elements with bridge elements
between them. Each bridge snapshots its parent's typed output properties; the
child consumes those inherited values as its embedding and per-layer KV-cache
input. All model elements reuse the same CSS declarations and output-head
functions, so only the small state-handoff rule and HTML nodes grow per token.

The current build predeclares 16 stages and produced all 16 rolling-window
reference IDs with zero script elements and no animation clock. This
turns slow evaluation into a render delay instead of state corruption. A
bucketed CSS decoder now maps every possible winner ID back to its GPT-2 token
text. The staged page uses a zero-delay, 1 ms gate only to separate style
passes. Two full-paint runs measured 1.17 visible tokens/second for the 15
tokens after Play. The tradeoff is finite generation: pure HTML must predeclare
one nested element per output token.

## Compression results and next work

### Precision and output-state packing

The current linked graph contains 6,911,520 decimal literals. A source sweep
estimates that four-decimal model values would reduce linked CSS from
236,988,204 to 202,682,646 bytes (-14.48%). A NumPy probe over 16 generated
tokens for each of three prompts matched all 48 reference tokens at four
decimals; three decimals matched 47/48. This does not establish browser or
adversarial correctness, and exact cluster bounds must be regenerated or
conservatively inflated before applying the change.

The shared output head spends 83,862,579 bytes on token dot functions but
120,588,798 bytes on mapping the winner ID back to 64 embedding coordinates.
That repeated feedback table is the largest structural target. Safe-integer
packing can store several quantized feedback coordinates per winner lookup,
then recover them with division and `mod()`. A second packed-pair experiment
can quantize each score finely, reserve low digits for its token ID, and avoid
a separate winner pass, though winner-recovery source itself is only 5,662,448
bytes in the shared design. Packing reduces parsed expression count, so it has
a better chance of lowering renderer memory than merely shortening decimal
strings.

The 8-bit feedback packing experiment is now implemented. The default stores
three coordinates per typed 24-bit number. It reduced the head from
206,464,160 to 125,344,932 bytes after lossless number spelling and matched all
16 browser reference tokens.
A clean process comparison reduced renderer RSS from 2,321,629,184 to
1,663,516,672 bytes (-28.35%).

The original six-coordinate 48-bit failure came from typed CSS conversion, not
from `calc()` arithmetic itself. Untyped custom properties and untyped CSS
custom-function results preserve the tested 48-bit integer exactly. Using that
path reduced the head again to 110,903,943 bytes and remained token-correct,
but full painted generation slowed from 1.17 to 0.85 tokens/second. A typed
four-coordinate/6-bit variant reached 115,471,300 bytes but changed the sixth
generated token. The typed 24-bit/8-bit path therefore remains the practical
default. The remaining large target is the 80.6 MB token-dot table.

The numeric emitter now selects the shortest CSS syntax that is exactly equal
to its previous nine-decimal output: for example, `0.5` becomes `.5` and
`0.000001` becomes `1e-6`. This reduced the complete recommended page from
152,684,609 to 148,926,533 raw bytes (-2.46%) without changing any of the 16
browser winners. Brotli level 9 is 28,928,806 bytes. A graph audit found zero
duplicate output-function bodies and zero unused registered properties, so no
additional exact removal was available from those two mechanical passes.

An alternating full-paint A/B test ruled out a runtime regression from numeric
spelling. Legacy decimal runs took 17.926 and 17.355 seconds; equivalent short
decimal/exponent runs took 17.437 and 17.508 seconds. The short median was about
one percent faster, which is within normal renderer variation.

The 148,926,533 raw bytes and 28,928,806 Brotli bytes describe different
stages of the same bundle. The raw graph breaks down as follows:

| Component | Raw bytes |
|---|---:|
| Full-vocabulary token dot functions | 80,638,875 |
| Packed winning-embedding lookup | 36,654,193 |
| Incremental transformer and KV cache | 21,049,908 |
| Per-token winner recovery | 5,561,934 |
| Nested state handoff and decoder | 2,525,724 |
| Cluster maxima | 1,552,076 |
| Registrations, runtime rules, streaming CSS, and HTML | 943,823 |

Brotli reduces network transfer, but Chromium still expands and parses the raw
CSS and constructs a substantially larger runtime graph.

Packing a quantized score and token ID into one untyped maximum removed the
5.56 MB recovery table but added 4.74 MB of packed maximum machinery. The head
fell only from 125,344,932 to 124,384,712 bytes. All 16 browser IDs matched,
but two alternating runs had a 14.245-second median versus 13.709 seconds for
the existing head. Brotli was also 79 KB larger, so this is not the default.

The exact token table has 3,216,448 nonzero products. Same-dimension repeated
weights can share only 27,164 of them (0.84%), and an SVD required full rank 64
to preserve all 72 stored winners. Exact mechanical compression is therefore
exhausted. A post-training row-wise integer experiment is more effective:

- 8-bit rows reduced the head to 100,334,943 bytes and the full Brotli bundle
  to 14,760,651 bytes, but diverged on 2/20 expanded prompts.
- 10-bit rows reduced the head to 102,756,721 bytes and the full bundle to
  126,338,257 raw / 16,441,633 Brotli bytes. It matched 320/320 expanded prompt
  decisions and all 16 browser IDs. Two painted runs took 11.358 and 12.123
  seconds, about 17% higher throughput than the exact baseline measured beside
  it.

The 10-bit result needs a much broader quality evaluation before adoption. It
does not require fine-tuning, but it is still an approximate checkpoint.

### Dynamic prompt transport

The font tokenizer is integrated into `tinystories/dynamic.html` without
adding 64 coordinate fonts or a second full embedding table. One token-ID
advance overflowed above 32,767 in HarfBuzz, so two fonts encode the ID as
base-32,767 digits. Container queries recover the two digits, and a 1.51 MB
token-to-cluster map routes the ID through the output head's existing packed
embedding functions.

The full dynamic page is 131,313,662 raw / 17,550,232 Brotli bytes, only about
1.11 MB more compressed than the fixed row-int10 page. The cost is numerical:
the existing feedback table stores embeddings at 8 bits per coordinate. The
default prompt's first nine decisions matched the fixed reference, then it
diverged. The next targeted experiment is a 10- or 12-bit prompt-only feedback
table, measured against the 8-bit path for bundle size, prompt fidelity,
renderer memory, and tokens per second. After that, increasing the predeclared
stage ceiling from 32 to 64 is meaningful only if renderer memory remains
stable; CSS cannot make the sequence truly unbounded because it cannot append
new stage elements.

The prompt wrappers deliberately do not use `.model`: that class activates
the entire recurrent transformer stylesheet. The generated handoff chain also
uses valid inline nesting. Together these details keep the initial paused page
from resolving the transformer repeatedly or releasing all stages before the
user presses Play.

For a larger architectural reduction without removing vocabulary entries,
train a checkpoint with a factorized vocabulary embedding: project the
64-number hidden state into an 8- or 16-number token space before the 50,257
token scores. That preserves the complete vocabulary while reducing the
dominant per-token CSS dot product by roughly 4-8x. Cross-layer parameter
sharing and structured sparsity are complementary ways to reduce the 21 MB
transformer circuit.

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

### Two-level exact cluster hierarchy

An offline 256-by-16 ball hierarchy remained exact across 72 real hidden
states and improved the theoretical multiply reduction from 4.92x to 6.67x,
evaluating 6,452 rather than 9,962 token rows on average. It is not compiled
into the runtime because its useful second-level pruning needs a
function-local calculated bound to control a lazy `style()` branch. The browser
probe showed that function-local custom properties cannot drive those queries.
Registering all leaf bounds globally makes them eager and spends the work the
hierarchy is intended to avoid. Axis-aligned box bounds were also tested and
did not tighten pruning on these embeddings.

## Remaining asymptotic boundary

The applied work removes dead nodes and repeated nonlinear scaffolding. It does
not change the dominant cost: GPT-2 small still requires 123,550,464 explicit
multiply-accumulate terms for a one-position transformer pass and language
head. A major next leap needs either model-level structure/sparsity or a runtime
with tensor storage and matrix operations.

For the 3M TinyStories checkpoint specifically, exact clustered search and KV
caching make the complete system run, but do not make it practical. The current
limits are about 234 MB of CSS, roughly 1.4 GB of renderer memory, and a stable
eight-second recurrent clock. The tested hierarchy is arithmetically tighter
but blocked by CSS's local-query semantics. A major next step therefore needs
fewer explicit weights (for example structured pruning or a purpose-trained
checkpoint), a new browser primitive for lazy local numeric branches, or a
runtime with native tensor operations.
