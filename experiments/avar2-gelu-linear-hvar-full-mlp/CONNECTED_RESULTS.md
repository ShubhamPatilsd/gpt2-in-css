# Live-input MLP transport results

All fixtures execute with HTML/CSS/fonts only. JavaScript is used only by the
external Playwright measurement harness.

## Failure diagnosis

Putting the original `12 x 256` MLP below one 384-level, width/height input
capture chain produced a 513-level DOM path. Chromium's HTML parser capped the
path: `.projection-0` was reparented below `.probe-0-122`, while probes
123-127 became siblings. The projection therefore inherited an incomplete
activation vector and returned its zero-axis advance.

This was a DOM-depth failure, not a matrix or precision failure. All 768 input
values and the FC preactivations were correct before the truncated projection.

## Working connectors

| connector | deepest path | elements | HTML | projection fonts | max transport error | max output RMSE |
|---|---:|---:|---:|---:|---:|---:|
| `12 x 256`, three parallel input shards | 133 | 25,003 | 3.50 MB | 3.64 MB | 0.0348 | 0.0257 |
| `13 x 236-238`, one deep input chain | 509 | 16,551 | 2.52 MB | 3.65 MB | 0.0213 | 0.0252 |
| `16 x 192`, one deep input chain | 486 | 18,861 | 2.78 MB | 3.67 MB | 0.0260 | 0.0253 |

All three passed all 768 outputs on four real GPT-2 activation fixtures.

## Controlled performance comparison

Twenty rounds alternated four loaded pages in one Chrome 153 process. Four
warm-up rounds were discarded. Keeping all pages resident inflated absolute
times, so these numbers are useful primarily as a relative comparison.

| implementation | median | p90 | relative to direct input |
|---|---:|---:|---:|
| `12 x 256`, values directly in font settings | 815 ms | 1,056 ms | baseline |
| `13 x 236-238`, deep connector | 962 ms | 1,310 ms | +18% median |
| `16 x 192`, deep connector | 1,033 ms | 1,129 ms | +27% median |
| `12 x 256`, three-shard connector | 1,147 ms | 1,427 ms | +41% median |

Single-page forced-layout runs were noisy and ranged from about 0.45 to 0.70
seconds for the complete MLP. The earlier 0.25-second result remains a best
warm run rather than a stable latency claim.

## Decision

Use the `13 x 236-238` connector. It is the smallest grouping that stays below
Chromium's nesting cap, has the fewest objects and smallest page of the working
connectors, and won the controlled median comparison. The `16 x 192` variant
has a somewhat better observed p90 but adds three font shards and 2,310 DOM
objects.

The live-vector boundary is now functional. The dominant scaling cost remains
shaping thousands of projection glyphs, not getting the 768 input values into
the MLP.

## Nonlinear and dense predecessor chain

The 13-group connector was extended twice:

1. A real block-0 LayerNorm computes all 768 normalized coordinates with CSS
   `calc()` and `sqrt()` before the MLP.
2. A real 768x768 HVAR attention projection feeds the residual and LayerNorm.
   For a one-token context only, attention returns V, so V and the output
   projection can be composed into this one affine map.

Both pages pass all 768 MLP outputs on all four fixtures. The complete
attention-to-MLP page has 17,707 elements, 2.90 MB of HTML, a 10.06 MB total
runtime bundle, at most 0.0286 transport error, and 0.0253 maximum output RMSE.

An alternating three-page, 20-round comparison measured:

| live prefix before the same MLP | median |
|---|---:|
| direct normalized input | 600 ms |
| residual + live LayerNorm | 703 ms |
| one-token attention projection + residual + LayerNorm | 1,035 ms |

Paired per-round differences put LayerNorm at roughly 70-94 ms and the dense
attention predecessor at roughly 344-380 ms. A separate single-page forced
layout run measured 923 ms for the complete attention-to-MLP chain.

LayerNorm exposed an important implementation rule. If its 768-term mean is an
unregistered custom property, substituting it twice into every variance term
creates roughly a million-term computed expression and Chrome invalidates the
variance. Registering mean and variance as typed `<number>` properties makes
each an actual scalar boundary; the full LayerNorm then works without changing
the MLP's numerical error.

This proves that declarative shadow roots can reset the DOM-depth budget between
dense stages while typed CSS numbers carry nonlinear scalar reductions across
the boundary. Full multi-token Q/K/softmax/V attention is still not part of
this page.

## Removing a redundant geometry round-trip

The first attention chain did this after LayerNorm:

`CSS numbers -> 768 widths -> 384 paired containers -> 768 CSS numbers -> FC font`

That conversion is required when the producer exposes only geometry. It is
redundant here because LayerNorm already produces CSS numbers. A direct variant
now puts those numbers immediately into the FC `font-variation-settings`.

The direct page passes every output on all four fixtures. It reduces the page
from 17,707 to 16,554 elements, reduces the runtime bundle from 10.06 MB to
9.80 MB, and retains 0.0253 maximum output RMSE.

Two controlled sweeps consistently selected 13 groups for the direct-number
path. In the larger four-page sweep:

| implementation | median | p90 |
|---|---:|---:|
| `13 x 236-238`, direct CSS numbers | 720 ms | 824 ms |
| `16 x 192`, direct CSS numbers | 923 ms | 1,197 ms |
| `12 x 256`, direct CSS numbers | 1,109 ms | 1,284 ms |
| `13 x 236-238`, geometry round-trip | 1,375 ms | 1,635 ms |

Multiple resident pages inflate the absolute values, but the relative result
is strong: removing the round-trip cut the controlled median by 48%, and the
shallower 236-238-axis font groups beat both 256- and 192-axis groups. The
current connected winner is therefore the 13-group direct-number path. Geometry
capture remains the fallback only for stages that cannot already expose typed
CSS numbers.

## Complete block state and the next-block handoff

The direct-number chain now adds the live post-attention residual and GPT-2's
MLP projection bias, producing the actual 768-coordinate block-0 output rather
than only the MLP contribution. All 768 complete outputs pass on four fixtures;
maximum transport error is 0.0249 and maximum RMSE is 0.0252.

A second page converts all 768 final widths back into inherited, registered
`--state-000` through `--state-767` CSS numbers using one 384-level paired
container chain. Those numbers are reusable by the next transformer block.
The captured state also passes all 768 coordinates with 0.0253 maximum error.

In a 16-round alternating comparison that forced one final coordinate:

| complete block boundary | median | p90 |
|---|---:|---:|
| final width only | 572.1 ms | 1,024.2 ms |
| reusable 768-number state | 621.2 ms | 1,081.7 ms |

On this fixture the full-vector handoff adds 49.1 ms median, or 8.6%. That is
material but not the dominant per-block cost. The 13 HVAR projection groups
remain the main target. The captured page adds 1,153 elements and about 251 kB
of HTML.

Group-level `contain: layout` and `contain: style` were also tested. Both were
pathological: the control completed its warm toggles while either containment
variant failed to finish the same small sweep after more than two minutes.
Layout containment changes containing-block behavior in the deep fixed-position
chains; style containment adds expensive boundaries across thousands of
inherited registered values. Neither is a viable optimization here.

The captured variables were then consumed by block 1's real LayerNorm 1. All
768 normalized coordinates pass with 0.00141 maximum error and 0.000313 RMSE.
In a three-page alternating sweep, adding this nonlinear calculation increased
the median from 752.8 ms to 775.8 ms; paired differences were noisy but centered
around 38 ms. This establishes a real cross-block chain:

`block 0 -> 768 captured CSS numbers -> block 1 LayerNorm`

The next expensive step is therefore block 1's font-backed attention/MLP, not
the LayerNorm or the state handoff itself.

## Two complete connected blocks

A first nested two-block topology failed at the browser parser boundary. The
block-1 projection glyphs were silently reparented at probe 114 because their
shadow host still sat below the preceding 384-level light-DOM state chain.
Declarative shadow content does not reset Chromium's parser-depth accounting
when its host is already deeply nested.

The working topology puts each deep producer inside its own shadow root and
assigns the next shallow light-DOM host to a terminal slot. CSS custom
properties inherit through that slot, but the next host retains its shallow
actual DOM ancestry. This permits independent 384-level attention/state stages
and 119-level MLP groups without crossing the roughly 512-level ceiling.

Block 1 also required general range calibration:

- its real MLP preactivations reach 17.91, so its GELU axes use a 19.0 range
  instead of block 0's 12.5;
- whole projection-group outputs range from -31.21 to 245.91;
- the HVAR output scale is therefore 66 rather than 192, keeping every summed
  glyph advance below Chromium's 32,768 ceiling.

The staged page passes every coordinate for four fixtures. After block 2,
maximum transport error is 0.267, maximum model error is 0.953, and maximum
RMSE is 0.0510. It contains no runtime JavaScript. The runtime assets total
about 16.45 MB: 3.16 MB HTML, 6.90 MB of projection fonts, 5.66 MB of FC fonts,
and 1.44 MB of attention fonts.

A paired one-output benchmark measured 607 ms median for one complete block
and 2.55 seconds for two connected blocks. Absolute values were inflated by
keeping both pages resident, but the second block added about 1.94 seconds in
that comparison. A same-page stage exposure sweep was more informative:

| demanded boundary | median |
|---|---:|
| block-0 final output | 963 ms |
| reusable block-0 state | 1,009 ms |
| block-1 attention | 1,044 ms |
| block-1 FC | 1,482 ms |
| block-1 projection, 3 groups | 1,434 ms |
| block-1 projection, 6 groups | 1,772 ms |
| block-1 projection, 13 groups | 2,147 ms |
| block-1 final anchor sum | 1,961 ms |

The individual measurements are noisy and were run sequentially on one page,
but the trend is clear. State capture and attention add tens of milliseconds;
FC shaping adds roughly 0.4 seconds, and projection cost grows with visible
group count by roughly another 0.6-0.7 seconds. Repeating the current groups
through 12 blocks is functionally possible but not fast enough.

The next high-value experiment is a serial shadow-slot projection pipeline:
each FC group passes its 236-238 GELU axes to the next shallow host, then one
final fallback-font run sums all 13 groups using 768 elements rather than
9,984 separately anchored projection glyph elements. This preserves the legal
per-font axis count while attacking the dominant DOM/anchor graph directly.

## Serial shadow-slot projection result

That pipeline now works end to end. Each of the 13 FC groups has globally
unique variation-axis tags and passes its normalized GELU values to the next
shallow host through a terminal shadow slot. The final stage uses 13 fonts with
non-overlapping private Unicode ranges. One element per output contains one
glyph from each font, so normal fallback shaping sums all 13 projection pieces
without 13 separately anchored elements per coordinate.

The serial page passes all 768 block-1 outputs on all four fixtures. Its maximum
transport error is 0.269 and maximum RMSE is 0.0511, effectively unchanged from
the 13-anchor topology.

| two-block implementation | old anchors | serial fallback | change |
|---|---:|---:|---:|
| DOM elements | 33,487 | 23,528 | -29.7% |
| HTML | 3.16 MB | 2.94 MB | -7.0% |
| load time in controlled run | 8.98 s | 7.17 s | -20.1% |
| one-output warm median | 2.80 s | 2.32 s | -17.1% |
| all-output verifier median | 7.28 s | 3.22 s | -55.8% |

Projection font bytes remain essentially unchanged at 3.25 MB because the
number of glyphs and weights is unchanged. The gain comes from deleting 9,216
DOM/anchor objects and the 13-way anchor dependency for every output. This is
the current best architecture for extending additional transformer blocks.

Serial projection should not be applied indiscriminately. A fully serial
two-block page reduced the graph again—from 23,528 to 13,569 elements and from
2.94 MB to 2.80 MB HTML—but made the first block's 13 FC groups sequential
before its complete 768-vector capture. In a direct 10-round pair:

| topology | warm median | load |
|---|---:|---:|
| parallel intermediate block + serial terminal block | 1.81 s | 7.15 s |
| serial groups in both blocks | 2.79 s | 12.33 s |

The fully serial form is 54% slower. Its RMSE remains acceptable at 0.0517,
but worst transport error rises from 0.269 to 0.329 through the extra geometry
boundary. The scaling rule is therefore positional:

- intermediate blocks should keep their FC/projection groups parallel because
  the next state requires all 768 outputs;
- the terminal block can use serial fallback projection because it removes the
  large anchor graph when exposing final demanded outputs.

## Twelve versus thirteen groups

Shadow staging makes both layouts legal, but one fewer projection group did
not win. In a direct 12-round comparison, 12 groups of 256 measured a 2.473 s
warm median and 3.239 s p90. Thirteen groups of 236-238 measured 2.436 s and
3.135 s respectively. The thirteen-group probe error was also about half as
large (0.0152 versus 0.0304). Retain thirteen groups.

## Layoutless transport hosts

Serial group hosts exist only to carry inherited custom properties through a
shadow slot. Setting those hosts to `display: contents` preserves the shadow
trees, slots, typed values, and all 768 outputs while removing their ordinary
layout boxes.

An exploratory 12-round comparison showed a 1.799 s layoutless median versus
2.164 s for the original, but a longer direct 16-round rerun gave the more
conservative result: 1.873 s versus 1.969 s, a 4.9% median improvement. P90
improved from 2.285 s to 2.089 s, and load time fell from 7.455 s to 6.611 s.
Output values and the 0.0131 maximum probe error were identical.

The same rule does not help the parallel intermediate topology: its layoutless
variant measured 2.442 s versus 2.383 s for the control, within noise but not
an improvement. A fully serial layoutless page improved from 3.082 s to 2.684
s, yet remains much slower than the terminal-serial hybrid. Retain layoutless
transport only around serial group chains; it is a modest repeatable terminal
path improvement, not a replacement for parallel intermediate blocks.

## Content-visibility staging does not help this chain

Block 1 was also hidden and revealed through a CSS-only discrete animation
after 0, 16, 50, 100, and 200 ms. Every delay preserved the same output, but
all were slower. In the direct two-page 200 ms comparison, the connected page
measured 2.658 s and the staged page measured 5.190 s. The five-page sweep was
consistent: even the best short-delay variant remained substantially slower
than its connected control.

Unlike the scroll-timeline vocabulary-head pipeline, this synchronous HVAR
graph does not leave behind a cheaply reusable upstream cache while the child
is hidden. Revealing the child triggers the downstream demand and adds another
style/layout activation. Reject fixed-delay `content-visibility` staging for
transformer blocks.
