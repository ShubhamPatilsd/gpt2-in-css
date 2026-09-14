# GPT-2 HVAR + Grid output-head scaling

This probe evaluates the real `50,257 x 768` tied GPT-2-small output matrix.
The runtime document contains no JavaScript. Variable-font advances calculate
all logits; CSS Grid reduces them to a winning token ID.

## Correctness fix

The first three-font build used code points beginning at U+10000. Some IDs
landed in complex-script combining blocks, so Chromium joined glyphs into text
clusters and produced false multi-million-pixel scores. Moving glyphs to
shaping-safe ranges removed the overflow.

Encoding a group ID in 1/64-pixel score ties was also too fine for the view-
timeline transport. The current reducer first selects the maximum score bucket,
then independently selects the group whose exact untransported width produced
that bucket. It no longer transports subpixel group IDs.

## Measured frontier (Chrome 153)

| Weight encoding | Original GPT-2 winners | Warm radio mutation | Cold load | Runtime bundle |
| --- | ---: | ---: | ---: | ---: |
| row-wise int8, 3 fonts / 3 glyphs per token | 8 / 10 | 0.59 s | 19.4 s | 45.0 MB |
| row-wise int10 as `4 * int8 + correction`, 6 fonts / 6 glyphs per token | 10 / 10 | 0.83 s | 50.1 s | 59.4 MB |
| row-wise int10, 5 direct 160-axis fonts / 5 glyphs per token | 10 / 10 | 0.78 s | 39.1 s | 58.0 MB |

The int10 page reproduced its quantized winner in all ten browser fixtures and
all ten winners equal the dense float GPT-2 result. Its weight RMSE is
0.000330, versus 0.001326 for int8. The six-font encoding is accurate but adds
42% warm latency, 32% runtime bytes, and 158% cold-load latency.

Direct row-wise 9-bit quantization was not monotonic: it matched 7/10 winners.
Direct 10-bit quantization matched 10/10, but 256 dimensions can exceed an
OpenType face's 16-bit advance range. Five direct faces of at most 160
dimensions fit that range. This is the current accuracy-preserving winner: it
removes one shaped glyph per candidate versus coarse/correction, cuts cold load
22%, cuts the warm radio mutation about 5%, and trims 1.4 MB.

The larger `validationMutationMedianMilliseconds` in `browser-results.json`
includes the external harness assigning 768 inline properties one at a time.
The radio mutation changes the same vector through one CSS selector and is the
cleaner loaded-head timing.

Run:

```sh
make gpt2-hvar-grid-output-head
GPT2_HVAR_GRID_HEAD_ROUNDS=5 node tools/test_gpt2_hvar_grid_output_head.mjs
```

## Connected two-block result

The accurate five-face head is also connected directly to the fastest exact
two-block HVAR page. A chunked, typed CSS final layer norm consumes the live
`--b1-final-000` through `--b1-final-767` values without another geometry
transport. Browser final-layer-norm RMSE is 0.000350 and the connected page
selects dense GPT-2 token 11.

Leaving the complete vocabulary head permanently visible is catastrophic:
four lifecycle frames take about 12.75 seconds after an upstream mutation,
although the isolated two-block chain and head total under two seconds. Every
upstream pass revisits the 50,000-element head subtree.

Hiding the head with `content-visibility` while the blocks settle, then
revealing it for two scoring frames, reduces the five-round median to 1.901
seconds (1.850--2.270 seconds), a 6.7x improvement. Correctness is unchanged.
This establishes phased evaluation as an architectural requirement. The probe
uses an HTML checkbox and the external test harness toggles it; an autonomous
no-JavaScript generation page still needs a CSS-only one-shot or re-armable
phase controller.

```sh
make test-two-block-gpt2-output-head
```

## Compact global-scale A/B

A second head removes the per-token row scale and base. One global int11 scale
lets the shared constants live in one CSS rule, raw UTF-8 glyphs replace five
hexadecimal entities, and only the local tie remains inline. This reduces the
runtime bundle from 58.00 MB to 50.94 MB and the HTML from 6.62 MB to 2.49 MB.

Under the same Chrome 153 harness, the compact inline-tie head selected the
expected winner in all ten fixtures and improved warm mutation from 0.807 to
0.528 seconds. Moving the tie to 256 `:nth-child()` rules was worse (0.950
seconds), directly demonstrating selector-matching cost across 50,257 nodes.

Cold load moved in the opposite direction: 37.82 seconds for row-wise int10
versus 62.49 seconds for global int11. The smaller font files therefore do not
imply cheaper font construction/shaping. The global encoding is currently the
better repeated-inference backend, not the better first-load backend.

A 64-state offline screen also weakens the earlier ten-fixture accuracy claim.
Global int11 preserved 63/64 dense winners; row-wise int10 preserved 60/64.
The mismatches occur at extremely narrow logit margins. Neither encoding is a
general exact GPT-2 output head yet, even though both pass the browser fixture.

```sh
make test-gpt2-hvar-grid-output-head-global11-inline-tie
PYTHONPATH=tools uv run --with numpy --with safetensors \
  python tools/analyze_gpt2_global_head_precision.py
```

## CSS-only phase-controller result

The final projection's named view timeline can autonomously expose a readiness
bit, but that bit means the timeline exists—not that every upstream value is
stable. Revealing the head immediately produced the correct token only by
coincidence at score bucket zero. Deferring it one CSS lifecycle produced the
real score bucket, but took 12.6 seconds because the head still participated in
upstream settling.

Four dependent container-query/animation barriers collapse into one style
fixpoint rather than four committed frames. A 1.2-second animation delay also
expires while Chromium is blocked inside the first long style/layout pass.
Neither technique reproduces the external harness's `requestAnimationFrame`
barrier. The working 1.9--2.3-second result still requires a manual HTML state
change (or an external scheduler) between the block graph and output head.

## Coarse-to-fine precision and coordinate transport

A two-stage head now runs global-int11 over all 50,257 tokens, retains the
winning 256-token group, and runs global-int16 only inside that group. The
coarse group was correct on all 256 screened GPT-2 states even though its exact
token was wrong once. The compact version uses 256 reusable fine candidates
whose glyph strings and base corrections are selected with `if(style())`.

After two explicit lifecycle flushes, the compact cascade measured 0.592
seconds warm with 51,522 elements. The equivalent 50,257-node fine subtree was
0.619 seconds with 101,720 elements. Removing dormant fine DOM therefore helps
memory but barely changes repeated inference. A two-group lazy-font prototype
reduced the initial referenced working set from about 135 MB to 59 MB, but the
first new group cost 2.25 seconds to load and its warm median was about
0.61--0.70 seconds. Group-subset fonts are a memory/network option, not a warm
speed optimization.

The expanded browser suite includes input token 11776, whose dense winner is
11 while global-int11 chooses 13. Offline global-int16 chooses 11, but the
ordinary browser global-int16 pass still chooses 13. A two-candidate probe
located the additional error: Chrome floors normalized OpenType variation
coordinates to F2DOT14. For this near tie, the true int16 margin is 0.000622
logits while the one-phase browser readout reverses it by the equivalent of
8.26 score-width units.

Positive coordinate supersampling plus a deterministic half-F2DOT14-step bias
correction repairs this boundary. On the pair probe, 8 phases change the
browser margin from -8.26 to +0.17 and select token 11. Across 256 real final
states, the corresponding numerical model improves hidden-coordinate RMSE
from 0.002383 to 0.000298 and winner matches from 255/256 to 256/256.

Applying eight phases to all 256 finalists is not viable: it shapes 24,576
fine glyphs and measured 5.816 seconds warm. An oracle sparse page containing
only five fine candidates shapes 480 glyphs, passes all nine browser fixtures
including the deliberate 11-vs-13 failure, and measures 0.593 seconds warm.
An offline 0.02-logit near-score gate activates 1.05 candidates on average,
two at the 95th percentile, and never more than two across the 256-state
screen, while preserving every dense winner. Merely hiding a 256-by-8 subtree
still costs 4.52 seconds because its descendants continue participating in
style resolution.

The general selector is now implemented entirely in HTML/CSS. It compares all
256 ordinary fine widths against the group maximum, converts the candidates
within 24 px into low/high local IDs, substitutes those IDs into two precision
slots, and performs the final argmax there. On the adversarial state it emits
`{11, 13}` and the precision stage returns 11. Seven phases are the smallest
setting that passes both the browser pair and the 256-state numerical screen;
six repairs the pair but loses another screened state. The integrated
seven-phase cascade passes all nine browser fixtures and measures 1.258
seconds warm. Sharing token glyph/base data between the ordinary and dithered
stages reduced generated CSS from 10.76 MB to 6.70 MB and the referenced
runtime from 141.17 MB to 137.10 MB without changing correctness.

Artifacts:

```sh
make test-gpt2-hvar-grid-output-head-cascade-compact
make test-gpt2-hvar-grid-output-head-cascade-subfonts
make test-gpt2-hvar-grid-output-head-cascade-dither8
make test-gpt2-hvar-grid-output-head-cascade-dither8-sparse5
make test-gpt2-hvar-grid-output-head-cascade-near-selector
make test-gpt2-hvar-grid-output-head-cascade-near-dither7
PYTHONPATH=tools uv run --with numpy --with safetensors \
  python tools/analyze_gpt2_selective_refinement.py
node tools/test_gpt2_hvar_coordinate_dither_probe.mjs
```

## Live two-block connection

The seven-phase selective head is now connected to the live two-block HVAR
graph rather than a precomputed hidden vector. Final layer norm is evaluated as
CSS numeric state on the block output, then inherited by the coarse head, the
near-score selector, and the two precise dither slots. The page contains no
runtime JavaScript.

With the head hidden until both blocks settle, the browser returns dense token
11 correctly. Across three measured warm mutations, the median is 2.566
seconds end to end: 0.959 seconds for the two blocks and 1.607 seconds for the
head. The live final hidden vector has RMSE 0.000350 and maximum error 0.003761
against the numerical reference.

Leaving the same head active throughout block recomputation raises the warm
median to 9.083 seconds. The nominal block phase alone then consumes 8.720
seconds because every transient upstream state invalidates the vocabulary
graph. Explicit lifecycle staging is therefore a required scaling primitive,
not a small optimization: it gives a 3.54x end-to-end speedup on the identical
connected computation.

Artifacts:

```sh
make test-two-block-gpt2-selective-output-head
TWO_BLOCK_SELECTIVE_STAGED=0 TWO_BLOCK_SELECTIVE_ROUNDS=1 \
  node tools/test_two_block_gpt2_selective_output_head.mjs
```

An explicit boundary between the two transformer blocks was also tested under
identical conditions. It improves 1.009 seconds to 0.958 seconds, only 5.3%.
Block-to-block invalidation is therefore not the same scaling failure as a
live vocabulary head; inserting a manual lifecycle after every block is not a
high-value direction.

Staging inside the selective head is useful but smaller. Committing coarse,
fine, near-score, and dither stages with two reads each passes every tested
transition and lowers the standalone head from 1.258 to 1.031 seconds. In the
live two-block connection it lowers head time from 1.607 to 1.470 seconds and
end-to-end time from 2.566 to 2.432 seconds. The coarse 50,257-token scan still
dominates at roughly 0.69 seconds.

Exact geometric pruning and low-rank coarse search were screened before any
browser implementation. Ball/box bounds still evaluate at least 50,208 tokens.
Embedding PCA misses 19 of 256 groups at best. A query PCA that looks strong
on one-token states fails on held-out 2/4/8/16-token GPT-2 contexts: rank 95
retains only 59/96 winning groups. Those routes do not generalize.

The exact global-int11 scan was also repacked from five 160-axis fonts to three
256-axis fonts. This cuts glyph instances per prediction from 251,285 to
150,771 while keeping the same coefficients and winners. A settled standalone
query improves from 942.7 to 866.3 ms; replacing all 768 inputs improves from
2,078.4 to 1,630.5 ms. In the accurate staged selective head, the coarse phase
improves from 686.7 to 628.9 ms but total time remains about 1.03 seconds.
Transformer matmuls already use 256-axis shards, so this is a retained constant
factor improvement rather than a general scaling escape.
