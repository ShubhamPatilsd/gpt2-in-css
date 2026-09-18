# GSUB depth amortization

**Deeper connected glyph computation amortizes the transfer cost in this small
digital circuit.** At depth eight, the complete native input → glyph program →
native numeric output path took 6.2 ms versus 8.2 ms for the matched CSS control,
for 256 independent changing outputs. The unique-text diagnostic measured
6.3 versus 8.5 ms. This is roughly 24–26% less elapsed time in this one sweep.
It is not a GPT-2 layer, a dense matrix, or a token-speed result.

The earlier ReLU network was replaced by a reversible two-coordinate digital cell
because repeatedly clipping its small state would collapse many inputs to the
same output. Here all 256 possible states remain distinct at every tested depth.
This deliberately isolates depth amortization from saturation and unchanged-output
shortcuts.

## Cell and actual internal representation

Starting with two four-bit integers `x,y`, zero-indexed layer `l` computes:

```
x_next = y
y_next = (x + y*y + 3*y + l + 1) mod 16
```

The map is reversible: recover `y = x_next`, then subtract the known nonlinear
function of `y` from `y_next` modulo 16 to recover `x`. It is a digital nonlinear
cell, not a real-valued neural MLP.

Every layer uses **two separately tagged state glyphs**. A ligature consumes both
current coordinates into that layer's joint-input glyph. A multiple substitution
expands it into both next-layer coordinate glyphs. The next layer consumes that
two-glyph state. Each layer has its own 256 joint-input and 256 expansion entries;
there is no table mapping original inputs directly to the entire chain's answer.

Only the final coordinate pair is packed into one advance, `64 + 16*x + y`.
The font has zero advance for every intermediate state. It uses 1,024 units per em
at 1,024 px font size to avoid the metric-rounding issue found in the original
arithmetic probe.

Individual stylistic-set features enable individual layers. Disabling any one of
the 15 tested layers across the four programs produced zero final source width.
This demonstrates that later substitutions require the correctly tagged output
of every preceding layer. A whole-chain answer-table shortcut would not pass
these layer-specific dependency controls.

## Correctness and results

Chrome 153.0.8010.48, Apple M2 Pro, macOS arm64, Node v26.5.0. All 256 input states
at depths 1, 2, 4, and 8 passed exact checks for both coordinate outputs and the
dependent final width, in both GSUB and CSS implementations. All programs retained
256 distinct final states. All 163,840 timed output checks also passed, with no
arithmetic tolerance or rounding of observed results.

Warm medians in milliseconds for **256 independent changing outputs per sample**:

| Depth | GSUB, repeated states | CSS, repeated states | GSUB, unique text | CSS, matched unique phase |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 5.7 | 4.5 | 5.9 | 4.8 |
| 2 | 5.7 | 5.3 | 6.0 | 5.3 |
| 4 | 5.8 | 6.5 | 6.1 | 6.3 |
| 8 | 6.2 | 8.2 | 6.3 | 8.5 |

The depth-four unique-text difference is small; the depth-eight result is the
clearer crossing. Its p95 is 8.5 versus 11.4 ms for repeated states and 8.9 versus
9.5 ms for unique text. These are samples within one fresh browser process,
not independent-run confidence intervals. The sweep stops at eight because it
answers the targeted depth question; it does not establish asymptotic scaling.

| Depth | Glyphs | Lookups | WOFF2 bytes | TTF bytes |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 642 | 3 | 3,144 | 16,544 |
| 2 | 930 | 5 | 3,768 | 24,932 |
| 4 | 1,506 | 9 | 5,440 | 41,704 |
| 8 | 2,658 | 17 | 8,656 | 75,248 |

Each program additionally has 256 final readout entries. Glyph and table growth
are linear in depth here because the state remains only two four-bit values.
The largest artifact is far below the ordinary 65,535-glyph OpenType bound.
Increasing a direct table's input count changes the problem: a `k`-coordinate
four-bit joint-input table has `16^k` combinations. These small numbers do not
support compiling dense 768-input neurons in this representation. More general
bit-serial circuits would require their own lookup-count and shaping-budget tests.

## Both transfer boundaries are charged

The native GSUB path is:

```
CSS integer inputs
  → custom counters in one generated-content pseudo-element
  → repeated GSUB layers, retaining both intermediate state glyphs
  → final glyph advance
  → anchor width and size container
  → registered CSS packed number and decoded x/y
  → dependent final width
```

The CSS control evaluates the same cell at every depth with registered integer
intermediate coordinates on one element. It does not use a separate DOM/layout
boundary per layer. It emits the same final packed width and uses the exact same
anchor/container/typed-number output reader. This is a compact native CSS control,
not an artificially deep page graph.

Each timed sample writes all inputs and synchronously reads all dependent output
widths. Its time includes CSS input encoding where needed, arithmetic or shaping,
layout, native numeric decoding, and final width reads. Stimulus construction and
cross-process protocol transport are excluded. The two implementations alternate
measurement order on every sample; the starting order reverses in the second
phase. There are 40 samples per phase/configuration, with the first five omitted
from timing summaries. Fixture positions have fixed small footprints so changing
result widths do not also repack the entire page's inline flow.

Exhaustive validation can populate a text-shape cache for all 256 input states.
The second phase therefore prepends a different zero-advance nonce glyph for each
round. It changes both the source text and mapped glyph sequence while leaving
both numerical inputs and the answer unchanged. The nonce is generated natively
by a third CSS counter; its input write is charged to both implementations. This
is a unique-text diagnostic, not proof that every internal font cache is disabled.
Both phases show the same depth trend.

JavaScript is confined to the external harness: it creates fixtures, supplies
inputs and observes outputs. Expected arithmetic is computed independently outside
the page. The page has CSP `script-src 'none'` and zero script elements. It does
not autonomously generate tokens, and the original model/compiler are unchanged.

## Reproduce and evidence

```
python3 tools/run_unconventional_isolated.py --label gsub-depth-build -- uv run tools/build_gsub_arithmetic_depth_probe.py
node --check tools/test_gsub_arithmetic_depth_probe.mjs
python3 tools/run_unconventional_isolated.py --label gsub-depth -- node tools/test_gsub_arithmetic_depth_probe.mjs
python3 -m py_compile tools/build_gsub_arithmetic_depth_probe.py
```

All large builds and browser runs used the shared experiment lock. This sweep
passed on its first browser attempt. [results.json](results.json) records all raw
timings, alternating orders, exact checks, disabled-layer controls, environment,
and harness hash. [reference.json](reference.json) records per-layer table counts
and SHA-256 hashes for every font and runtime source artifact.

The result strengthens the case for keeping several operations inside glyph
state once the representation is available. It leaves the hard next question
unchanged: how to represent useful high-fan-in model computation without an
exponential table or excessive glyph work.
