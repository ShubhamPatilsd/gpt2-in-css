# GSUB depth amortization

**At depth sixteen, the complete GSUB circuit is faster than the direct native
CSS control in this small experiment.** For 256 changing outputs, it measures
6.5 ms versus 10.2 ms with repeated states and 7.0 versus 10.2 ms with unique text:
approximately 31–36% less elapsed time. Both native integer input encoding and
required native numeric output readback are included. This is a reversible
two-coordinate digital circuit, **not a GPT-2 layer, dense matrix, or token-speed
result**.

The corrected direct CSS baseline consumes its final CSS numbers directly; it
does not unnecessarily send them through geometry and decode them again. Direct
CSS wins at depths one, two, and four; depth eight does not show a reliable GSUB
advantage. One separately preserved final depth-sixteen point establishes the
observed crossing. No larger depths or model integration were tested.

The first sweep found a 24–26% GSUB advantage over a CSS control forced through
the same geometry roundtrip. An independent audit identified that roundtrip as
unnecessary for CSS, which already has numeric output. Those results are retained
in `attempt-matched-geometry-control/` and are **not evidence of beating the best
native CSS path**. One follow-up sweep added the direct control and corrected the
conclusion through depth eight. The additional depth-sixteen point then compared
against that direct control, using the same circuit and measurement protocol.

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
the 31 tested layers across the five programs produced zero final source width.
This demonstrates that later substitutions require the correctly tagged output
of every preceding layer. A whole-chain answer-table shortcut would not pass
these layer-specific dependency controls.

## Correctness and results

Chrome 153.0.8010.48, Apple M2 Pro, macOS arm64, Node v26.5.0. All 256 input states
at depths 1, 2, 4, 8, and 16 passed exact checks for both coordinate outputs and the
dependent final width, in GSUB, CSS with matched geometry, and direct CSS. All
programs retained 256 distinct final states. All 245,760 timed output checks
in the corrected depth-one-to-eight sweep and the additional 61,440 depth-sixteen
checks passed, with no
arithmetic tolerance or rounding of observed results.

Warm medians in milliseconds for **256 independent changing outputs per sample**:

| Depth | GSUB, repeated states | Direct CSS, repeated states | GSUB, unique text | Direct CSS, matched unique phase |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 5.6 | 2.5 | 5.9 | 2.6 |
| 2 | 5.9 | 3.1 | 6.2 | 3.1 |
| 4 | 6.0 | 4.2 | 6.3 | 4.3 |
| 8 | 6.1 | 6.2 | 6.8 | 6.3 |
| 16 | 6.5 | 10.2 | 7.0 | 10.2 |

The 0.1 ms repeated-state difference at depth eight is too small to support a
speedup claim, particularly because the unique-text phase reverses its direction.
For comparison, the retained matched-geometry CSS control in the same follow-up
measured 4.6, 5.5, 6.8, and 8.6 ms at depths 1, 2, 4, and 8. This explains how the
unnecessary output roundtrip produced an apparently favorable crossing.
Depth sixteen was measured in a separate fresh browser process, with each GSUB
measurement paired with direct CSS in that same process. Its repeated-state p95s
are 7.1 ms GSUB versus 12.0 ms direct CSS; unique-text p95s are 9.3 versus 11.1 ms.
Every sample is recorded in the separate JSON. Samples within one
process are not independent-run confidence intervals, and the extension does not
establish asymptotic scaling.

| Depth | Glyphs | Lookups | WOFF2 bytes | TTF bytes |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 642 | 3 | 3,144 | 16,544 |
| 2 | 930 | 5 | 3,768 | 24,932 |
| 4 | 1,506 | 9 | 5,440 | 41,704 |
| 8 | 2,658 | 17 | 8,656 | 75,248 |
| 16 | 4,962 | 33 | 13,868 | 144,124 |

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

All CSS controls evaluate the same cell at every depth with registered integer
intermediate coordinates on one element. There is no separate DOM/layout boundary
per layer. The main **direct-css** control consumes its existing final `--xN` and
`--yN` values in one dependent output width. Its typed numeric outputs are verified
directly, without a geometry-to-number receiver. GSUB still requires and pays for
its native counter encoding and geometry-to-number receiver.

The secondary **control** mode retains the same anchor/container/typed-number
output reader as GSUB. It is useful for isolating computation under an identical
boundary, but cannot establish the fastest complete native CSS implementation.

Each timed sample writes all inputs and synchronously reads all dependent output
widths in the same units. Its time includes CSS input encoding where needed,
arithmetic or shaping, required layout/numeric decoding, and final width reads.
Stimulus construction and cross-process protocol transport are excluded. GSUB and
direct CSS alternate first/last measurement order on every sample, with the
matched-geometry control between them; the starting order reverses in the second
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
python3 tools/run_unconventional_isolated.py --label gsub-depth-direct-css -- node tools/test_gsub_arithmetic_depth_probe.mjs
python3 tools/run_unconventional_isolated.py --label gsub-depth16-build -- uv run tools/build_gsub_arithmetic_depth_probe.py --depth16
python3 tools/run_unconventional_isolated.py --label gsub-depth16 -- node tools/test_gsub_arithmetic_depth_probe.mjs --depth16
python3 -m py_compile tools/build_gsub_arithmetic_depth_probe.py
```

All large builds and browser runs used the shared experiment lock. The initial
matched-geometry sweep, direct-CSS follow-up, and final depth-sixteen point each
passed on their first browser attempt. [results.json](results.json) records the
corrected depth-one-to-eight sweep; [depth16/results.json](depth16/results.json)
records the extension. Both contain raw
timings, alternating orders, exact checks, disabled-layer controls, environment,
and harness hash. [reference.json](reference.json) records per-layer table counts
and SHA-256 hashes for every font and runtime source artifact. Exact source
snapshots for the earlier direct-CSS sweep are in `attempt-direct-css-control/`;
the current source adds only the separately selected depth-sixteen build/run mode.

The experiment demonstrates that enough genuine internal glyph computation can
amortize its input/output transfers, even against a direct CSS consumer. It leaves
the hard next question unchanged: how to represent useful high-fan-in model
computation without an exponential table or excessive glyph work. The result is
restricted to the small reversible cell and observed depth-sixteen crossover;
no further depths or architectures were benchmarked.
