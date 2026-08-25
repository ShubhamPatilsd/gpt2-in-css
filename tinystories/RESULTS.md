# TinyStories recurrent CSS result

The complete width-64, eight-layer `calum/tinystories-gpt2-3M` next-token
path now runs in Chromium: token embedding, positional embedding, all
transformer blocks, a KV cache, exact full-vocabulary argmax, winning-embedding
feedback, and recurrent state latching.

The vocabulary was not reduced. Every one of the checkpoint's 50,257 tokens
remains eligible to win.

## Measured result

| Circuit | Generated CSS | Median / elapsed | Correctness |
|---|---:|---:|---:|
| Incremental transformer core | 18.0 MB | 281.5 ms median | max hidden error `0.0000799` |
| Core + shared exact output head | 231.0 MB total | 670.4–702.2 ms median | 0 wrong winners |
| Four-token recurrent generator | 234.5 MB total | 42.69 s total | 4/4 tokens correct |
| 16-token packed nested stream | 152.7 MB total | 12.86 s for 15 post-Play tokens | 16/16 tokens correct |

For the prompt `Once upon a time`, both the NumPy reference and the CSS
generator produced token IDs `[11, 612, 373, 257]`, which decode to
`, there was a`.

The recurrent page uses JavaScript only to time the run and read the final
properties. JavaScript does not calculate attention, choose tokens, or write
model state. The transformer and execute/store state machine are CSS.

There is now also a stricter `nested.html` page with no `<script>` element at
all. It removes the clock and mutable animation state. Each nested model
element inherits the previous element's winning embedding and complete KV
cache through a bridge element, then applies the same shared `.model` rules.
The cascade itself is the sequencer:

```text
model 1 output -> inherited bridge -> model 2 input -> ...
```

The expanded Chromium run rendered token IDs
`[11, 612, 373, 257, 1310, 2576, 3706, 20037, 13, 1375, 6151, 284, 711, 351, 607, 14958]`.
Because the page has no independent clock, slow evaluation delays rendering
but cannot make a later stage read half-written state. The extra handoff CSS is
2,525,724 bytes, including an exact CSS decoder for all 50,257 vocabulary
entries; the 213 MB head and 21 MB transformer circuit are still stored only
once. The page now renders the decoded completion directly as
`Once upon a time, there was a little girl named Lily. She loved to play with
her toys` and still contains no script elements.

Each token becomes visible through CSS `content` as soon as its stage's
computed winner is available. Chromium is allowed to batch style and paint
work, though, so this is live state rather than a guaranteed typewriter-like
one-token-at-a-time animation. Adding a CSS timer would only fake that pacing
and would reintroduce the unreliable clock this page was designed to remove.

`streaming.html` adds an experimental staged mode without changing the model
math. Each child handoff starts with `content-visibility: hidden`; a style
query on the parent's computed winner activates a one-millisecond registered
custom-property animation, which then makes that child visible and eligible
for style work. There is no animation delay. The 1 ms transition is only a
browser style-pass boundary, so tokens run as fast as the renderer allows.
The page starts paused after computing the comma; Play releases the remaining
15 stages. The page still reported zero script elements. This is real stage
gating, but the control cannot interrupt a style calculation already executing
on the browser main thread.

Two uninterrupted Chromium 151 full-paint runs took 12.828 and 12.891 seconds
from Play until all 16 generated pieces were visible. Because the comma was
prepared while paused, that interval covers 15 tokens: 1.17 visible
tokens/second median. This excludes stylesheet download and parse time. The
page displays the measured figure statically because CSS cannot read a wall
clock or calculate a live rate; browser automation was used only to observe
paint completion and did not choose or feed back tokens.

## Size reduction measurements

The linked CSS contains 6,911,520 decimal literals. An offline formatting and
NumPy sweep found that reducing generated model values from nine to four
decimal places would shrink the 236,988,204-byte CSS graph to an estimated
202,682,646 bytes (-14.48%). Four-decimal weights preserved all 48 greedy
tokens tested across three prompts; three decimals changed one token. This is
not ready to ship: the clustered search bounds must be rebuilt or inflated and
the four-decimal graph must still pass Chromium comparison tests.

Before lossless numeric spelling, the shared 213,028,755-byte head broke down
more usefully by generated
section: 83,862,579 bytes of token dot functions, 1,552,076 bytes of cluster
maximum functions, 5,662,448 bytes of winner recovery, 120,588,798 bytes of
embedding-feedback lookup functions, and 1,362,854 bytes of registrations and
rules. The largest immediate structural target is therefore feedback lookup,
not winner recovery. Packing several quantized embedding coordinates into each
safe integer could replace many of its 64 per-coordinate lookup tables.
Packing the winner into the reduced score may still avoid repeat score
evaluation, but it saves much less source. Both require new browser correctness
measurements rather than source-only estimates.

The first packed-feedback implementation tried six 8-bit coordinates in one
48-bit integer. The failure was narrower than first reported: Chromium
corrupted the value only after it crossed a typed `<number>` boundary. A
dedicated zero-script probe shows that the same 48-bit integer survives direct
`calc()`, an unregistered custom property, and an untyped CSS custom function;
registered `<number>`, registered `<integer>`, and a typed custom-function
return lose information. See `css-number-precision-test.html`.

An untyped six-coordinate implementation therefore works and matches all 16
reference winners. After lossless number spelling, its head is 110,903,943
bytes, 14,440,989 bytes (11.52%)
smaller than the typed 24-bit head. It is not the default because two full-paint
runs took 17.386 and 17.911 seconds for the 15 post-Play tokens, versus 12.828
and 12.891 seconds for the typed version. The smaller source rendered about 27%
slower in this measurement.

A second experiment used four 6-bit coordinates per typed 24-bit pack. It
reduced the head to 115,471,300 bytes, but browser generation diverged at token
six: reference token `2576` became `2933`. The resulting sequence was
`[11, 612, 373, 257, 1310, 2933, 3706, 5045, 13, 5045, 373, 6507, 13, 679,
2227, 284]`. This is a concrete example of why a quantization sweep over a
limited set of hidden states is not an end-to-end correctness test.

The packed head is 125,344,932 bytes, 81,119,228 bytes (-39.29%) smaller than
the equivalently formatted shared head. The current 16-stage streaming page is
148,926,533 bytes raw, 33,524,024 bytes under gzip level 9, and 28,928,806
bytes under Brotli level 9. In clean renderer-process samples,
the original streaming page used 2,321,629,184 bytes RSS and the packed page
used 1,663,516,672 bytes: a 658,112,512-byte (-28.35%) reduction. RSS is a
process-level observation, not a portable browser guarantee.

The source reduction is lossless relative to the compiler's previous numeric
values. Leading zeroes are omitted and exponent notation is used only when it
represents exactly the same nine-decimal value in fewer characters. The
browser still produced all 16 reference IDs. The output-head audit found no
identical function bodies and no unused registered properties left to remove.

The original and short numeric emitters were rebuilt side by side and served
uncompressed from the same local server. Alternating painted runs were
17.926/17.355 seconds for legacy decimals and 17.437/17.508 seconds for short
decimals and exponents. Numeric source compression did not slow inference.

The recommended head itself contains 80,638,875 bytes of token dot functions,
36,654,193 bytes of packed feedback lookup, 5,561,934 bytes of winner recovery,
1,552,076 bytes of cluster maxima, and 937,854 bytes of registrations and
runtime rules. The remaining 23.58 MB of the page is the transformer, nested
handoff/decoder, streaming rules, and HTML. The 28.93 MB figure is compressed
network transfer; the browser still processes 148.93 MB of raw source.

An untyped packed-score/token prototype removed winner recovery but added a
second packed maximum graph. It saved only 960,220 head bytes, compressed
slightly worse, and ran about 4% slower in the paired painted test. It matched
all 16 browser IDs but is retained only as a negative experiment.

Row-wise post-training score quantization attacks the larger term directly.
Eight-bit rows produced the reference browser story and ran at a 1.25
tokens/second two-run median, but diverged on two of twenty additional prompts.
Ten-bit rows matched all 320 expanded prompt decisions and all 16 browser IDs.
Its complete page is 126,338,257 bytes raw and 16,441,633 bytes under Brotli 9.
Two painted runs took 11.358 and 12.123 seconds, versus 13.640 and 13.777 for
the exact page in the same alternating session. Because the weights are still
approximated, `streaming-packed8-row-int10.html` is not yet the default.

Greedy generation remains intentional. Chromium 151 reports the draft CSS
`random()` function as unsupported, and exact cluster pruning is designed to
find one maximum rather than construct a full sampling distribution. The
zero-script probe is `css-random-test.html`.

The recurrent graph has an eight-token sliding window and stores the key and
value vectors for every layer. It computes only the newest token's transformer
path, then shifts the fixed-size cache. This replaces the earlier design that
recomputed every prefix from scratch. The expanded compiler also stopped
clamping positional embeddings at position 7: the 16-stage build includes
absolute positions 0 through 19, while only the attention KV history rolls.
The NumPy reference now mirrors that exact cache and position policy.

## Why recurrence is slower than the static token

The 0.67–0.70 second figure is a forced recomputation of a settled, static
next-token graph. Recurrent generation must also copy thousands of key/value,
embedding, and output properties through separate execute and store animation
phases. Chromium overlapped or dropped state work with four- and six-second
clocks. An eight-second clock was the first tested setting that produced all
four reference tokens reliably. Including initialization, the measured run was
42.69 seconds, or 10.67 seconds per output token.

That fixed-clock page is retained as a timing experiment, but it is not the
recommended correctness demonstration: an eight-second clock failed on a
slower run. Use `nested.html` when the requirement is deterministic HTML/CSS
only. Its limitation is that HTML must contain a model element for every
desired output token; it cannot create an unbounded number of future stages.

The linked CSS used roughly 1.4 GB of renderer RSS after the completed run.
That is an observed process value rather than a portable memory guarantee.

## Source deduplication

The original exact score/winner/embedding head repeated token dot products in
multiple graphs and now occupies 282,137,529 bytes. The shared-dot head defines
each token score once and reuses it for maximum and winner recovery. It is
206,464,160 bytes, a 26.8% reduction, and remained exact in the browser tests.

## Tighter exact search result

A two-level ball hierarchy was evaluated on 72 real model hidden states. With
256 top clusters and 16 children per top cluster, it remained exact, evaluated
6,452 token rows on average, and reduced multiply terms by 6.67x versus dense
search. The flat 256-cluster index evaluates 9,962 rows and reduces terms by
4.92x.

The ideal arithmetic win does not currently compile into a faster CSS graph.
Lazy leaf pruning requires a function-local numeric bound to control a
`style()` branch. Chromium's custom functions are lazy, but the browser probe
in `function-local-style-test.html` showed that a function-local custom
property cannot drive that query. Hoisting all leaf bounds into registered
global properties makes them eager and consumes the work the hierarchy was
meant to avoid. An axis-aligned box bound was also tested and did not prune
better than the radius-ball bound on these embeddings.

## Practical decision

This proves that an exact, full-vocabulary TinyStories transformer can generate
recurrently in CSS. It is not yet practical as a normal text-generation UI:
roughly 234 MB of source, about 1.4 GB of renderer memory, and around 10.7
seconds per token are research-demo costs.

Further cluster reshuffling is unlikely to change that conclusion. The next
large improvements require either fewer explicit model weights (structured
pruning or a checkpoint trained for CSS execution), a browser primitive that
can lazily branch on local calculated values, or a runtime with native tensor
storage and matrix multiplication.

## Reproduce

```sh
make clustered-output-head
make tinystories-step
make tinystories-recurrent
make tinystories-nested
make serve-tinystories
```

Open `tinystories/step-with-shared-head.html` for the static full-token test or
`tinystories/streaming-packed8.html` for the zero-delay, script-free 16-token
text run.
Generated CSS is excluded from Git.
