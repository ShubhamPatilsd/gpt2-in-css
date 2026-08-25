# MNIST in HTML + CSS

This is the first step toward expressing a neural network in HTML and CSS: a
784-to-32-to-10 ReLU MNIST MLP whose forward pass is evaluated by the browser's
CSS engine. The page includes ten selectable test images—one of each digit—and
recomputes the classifier whenever the selected radio button changes.

There is no JavaScript in the generated page. Python is used at build time to:

1. download MNIST,
2. train a multinomial linear classifier,
3. export its weights and ten test images as CSS custom properties, and
4. write the static HTML visualization.

At runtime, each hidden activation and class score is a CSS expression:

```css
--hidden-pre-00: calc(
  var(--hidden-bias-00)
  + var(--x-000) * var(--hidden-w-00-000)
  + var(--x-001) * var(--hidden-w-00-001)
  /* ... */
);

--hidden-00: max(0, var(--hidden-pre-00));
```

The class with the longest bar is the CSS prediction. Python's reference
prediction is shown only as a correctness check. Selecting an image is handled
with radio inputs and `:has()`; there is still no JavaScript at runtime.

## Build

```sh
make build
open index.html
```

The first build downloads `mnist.npz` (about 11 MB) and trains the model. The
dataset is cached under `data/` and excluded from version control.

Requirements: Python 3 and NumPy. The generated page needs a browser supporting
CSS typed arithmetic (`*` in `calc()`). The transformer pages additionally use
CSS custom functions, available in Chromium 139 and newer.

## Tiny transformer

The second experiment compiles a GPT-2-style transformer block and three
autoregressive generation steps to CSS:

```sh
make transformer
open transformer/index.html
```

It uses a seven-token toy vocabulary and a fitted language head so the complete
attention/GELU/residual/argmax/feedback circuit remains small enough to inspect
in a browser.

## Pretrained GPT-2 checkpoint

The third experiment downloads and compiles the `sshleifer/tiny-gpt2` test
checkpoint, including its 50,257-token language-model head:

```sh
make pretrained
open pretrained/index.html
```

The checkpoint is cached under `data/`. Its legacy PyTorch format is decoded by
the build script without requiring PyTorch, and the generated page has no
runtime JavaScript. The tied language head is two-dimensional, so an exact
convex-hull pass proves that only 16 of its 50,257 token embeddings can ever win
an argmax; the compiler omits the other mathematically dead logits.

This checkpoint has only two hidden dimensions and two transformer layers. It
is useful for verifying the compiler, but it is not a usable language model:
greedy generation collapses to repeated `stairs` or `factors` tokens even in
the Python reference implementation.

To inspect four chained CSS inference passes:

```sh
make benchmark
python3 -m http.server 4173
```

Open `http://localhost:4173/pretrained/benchmark.html` and choose a prompt.
Every CSS argmax selects the embedding consumed by the next transformer pass.
The page contains no script. It intentionally recomputes every causal prefix
instead of using a KV cache, and therefore cannot measure its own wall-clock
throughput. Exact convex-hull elimination reduces its four-step stylesheet to
about 561 KB.

For a CSS-only prompt picker with one through four initial tokens:

```sh
make interactive
python3 -m http.server 4173
```

Then open `http://localhost:4173/pretrained/interactive.html`. Choose the prompt
length and select GPT-2 token pieces; native select menus support type-to-search.
CSS observes each selected `option:checked` and maps it to a raw embedding.
Press **start / resume generation** to start a four-phase CSS animation clock.
Every 1.2-second cycle evaluates one transformer pass, latches the winning
embedding into model state, and appends the decoded token to a CSS content
buffer. The bounded picker exposes 2,066 useful/common/example token pieces;
the output argmax remains exact over the full 50,257-token vocabulary because
only 16 embeddings are geometrically capable of winning for this checkpoint.

The page no longer precomputes future tokens. It contains one 1.51 MB recurrent
transformer circuit and animation-latched state copied through execute/store
custom-property banks. Generation can continue indefinitely. To keep the
state fixed-size, the model uses a 16-token sliding context: after it fills,
each cycle discards the oldest embedding, shifts the window, and appends the
new winner. **Pause generation** preserves state; **reset** reloads the page.

There is intentionally no ordinary text field. CSS selectors cannot read a
text input's live string, and `attr()` reads markup attributes rather than the
mutable form-control value. Without JavaScript or a server, arbitrary text
cannot be BPE-tokenized. Selected `<option>` elements do expose dynamic
`:checked` state, so token selection is the honest zero-script workaround. See
the [Selectors input-state specification](https://www.w3.org/TR/selectors-4/#input-value-states)
and [`attr()` definition](https://www.w3.org/TR/css-values-5/#attr-notation).

## GPT-2 small scaling result

`make analyze-full` runs the real 124M GPT-2-small checkpoint for one token and
calculates the size of the equivalent CSS circuit. See
[`FULL_GPT2.md`](FULL_GPT2.md) for the measured limit: 123.55 million CSS MAC
terms and a projected 3.16–6.12 GB stylesheet per unrolled token. The research
and implemented optimizations are recorded in
[`OPTIMIZATIONS.md`](OPTIMIZATIONS.md).

## TinyStories exact output head

The full width-64, eight-layer TinyStories model now generates recurrently in
CSS with a real rolling KV cache and an exact 50,257-token output head. The
current zero-script page predeclares 16 output stages and renders `Once upon a
time, there was a little girl named Lily. She loved to play with her toys`.

The optimized static transformer-plus-head path takes 670–702 ms median. The
complete recurrent run takes 42.69 seconds for four tokens because Chromium
also has to latch thousands of cache properties through safe execute/store
phases. The linked graph is about 234 MB of CSS and used roughly 1.4 GB of
renderer memory. This is a conclusive systems demonstration, not yet a
practical text-generation UI.

See [`tinystories/RESULTS.md`](tinystories/RESULTS.md) for the end-to-end result
and [`output-head-benchmark/RESULTS.md`](output-head-benchmark/RESULTS.md) for
the output-search experiments.

For the strict zero-JavaScript version, build and open the nested page:

```sh
make tinystories-all
make serve-tinystories
```

Open `http://localhost:4173/tinystories/nested.html`. It contains no
`<script>` element and uses no animation clock. Sixteen nested model elements
reuse the same CSS circuit; each child inherits the previous model element's
winning embedding and KV cache. The normal parent-to-child CSS cascade enforces
the evaluation order, so a slow calculation cannot corrupt the next state.
An exact CSS decoder covering all 50,257 tokens renders the generated text as
`Once upon a time, there was a little girl named Lily. She loved to play with
her toys`. Generated pieces reflect live computed CSS state, although the
browser may batch several stages into one paint.

For actual staged painting with a CSS-only Pause/Play control, open
`http://localhost:4173/tinystories/streaming.html`. Later model subtrees use
`content-visibility: hidden` until the previous computed winner starts their
one-millisecond CSS gate. The gate has zero delay; the 1 ms duration is the
smallest practical animation tick that keeps stages in separate style passes.
The page starts paused after preparing the first token. Press Play to run the
remaining 15 stages as quickly as Chromium can evaluate and paint them. A
currently-running style calculation can still block the UI. The optional
“Show token IDs” control exposes the computed winners alongside their decoded
text.

`http://localhost:4173/tinystories/streaming-packed8.html` is the recommended
compressed experiment. It quantizes only the embedding fed from one generated
token into the next and packs three 8-bit coordinates into each 24-bit CSS
number. It preserves all 50,257 output candidates. The expanded 16-token run
matched all 16 rolling-window reference IDs. The complete page is 148,926,533
bytes raw, 33,524,024 bytes with gzip level 9, and 28,928,806 bytes with
Brotli level 9, versus 236,991,550 raw for the earlier four-token uncompressed
streaming page.
A clean renderer comparison measured about 1.66 GB RSS packed versus 2.32 GB
unpacked. Two full-paint measurements took 12.828 and 12.891 seconds for the
15 tokens generated after Play: 1.17 visible tokens/second median. The first
token is prepared while paused, and stylesheet loading is excluded.

The compiler writes the same nine-decimal values using their shortest
equivalent CSS spelling. All 16 browser token IDs remain unchanged. Run
`make precompress-tinystories` to create deterministic `.gz` and `.br` files;
the HTTP server must select them and send the matching `Content-Encoding`.
For local testing, `make serve-tinystories` serves those precompressed static
files at `http://127.0.0.1:4173` with immutable caching on versioned CSS. The
server performs no inference and adds no client-side code.

An alternating painted A/B test found no runtime penalty from the shorter
numeric spelling. The legacy formatter took 17.926 and 17.355 seconds; the
short formatter took 17.437 and 17.508 seconds. The roughly one-percent median
difference favored the short formatter and is within renderer noise.

`streaming-packed8x6.html` is a smaller experimental alternative. It packs six
8-bit coordinates into an untyped 48-bit CSS value. All 16 token IDs match, and
the rebuilt complete raw page is 134,485,605 bytes, but painted generation
slowed to
0.85 tokens/second in the measured runs. The typed 24-bit page remains the
recommended balance of size, correctness, and speed.

Three additional output-head candidates remain opt-in:

- `streaming-packed8-score-token.html` carries a quantized score and token ID
  through one untyped maximum. It is 0.96 MB smaller raw, but its two-run
  painted median was about 4% slower and its Brotli file was slightly larger.
- `streaming-packed8-row-int8.html` replaces full-precision score weights with
  row-wise 8-bit codes. It is much smaller and faster, but diverged on two of
  twenty expanded prompt tests, so it is not a faithful checkpoint build.
- `streaming-packed8-row-int10.html` uses the safer 10-bit version. It matched
  320/320 tested autoregressive decisions and all 16 browser tokens. The full
  page is 126,338,257 bytes raw and 16,441,633 bytes with Brotli level 9. Its
  two painted runs took 11.358 and 12.123 seconds versus 13.640 and 13.777 for
  the exact baseline measured alongside it. This still changes the checkpoint
  numerically and therefore remains experimental.

Run `python3 tools/analyze_row_score_quantization.py --bits 10` to repeat the
expanded prompt check. None of these pages contains JavaScript.

Greedy generation remains the reference mode. Chromium 151 does not implement
the draft CSS `random()` function (`tinystories/css-random-test.html` reports
`unsupported`), and full-vocabulary sampling would require substantially more
output-head work than exact argmax. No JavaScript fallback is used.
