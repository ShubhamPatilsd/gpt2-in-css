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

The shared 213,028,755-byte head breaks down more usefully by generated
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
48-bit integer. Python preserved it, but Chromium's registered `<number>` path
rounded the value and corrupted the low coordinates. The corrected version
packs three coordinates into a 24-bit integer. It passed the expanded browser
test with all 16 rolling-window reference winners and zero script elements.

The packed head is 128,685,887 bytes, 84,342,868 bytes (-39.59%) smaller than
the original head. The current 16-stage streaming page is 152,684,609 bytes raw
and 33,694,759 bytes under gzip level 9. In clean renderer-process samples,
the original streaming page used 2,321,629,184 bytes RSS and the packed page
used 1,663,516,672 bytes: a 658,112,512-byte (-28.35%) reduction. RSS is a
process-level observation, not a portable browser guarantee.

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
multiple graphs and occupied 291,925,867 bytes. The shared-dot head defines
each token score once and reuses it for maximum and winner recovery. It is
213,028,755 bytes, a 27.0% reduction, and remained exact in the browser tests.

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
python3 -m http.server 4173
```

Open `tinystories/step-with-shared-head.html` for the static full-token test or
`tinystories/streaming-packed8.html` for the zero-delay, script-free 16-token
text run.
Generated CSS is excluded from Git.
