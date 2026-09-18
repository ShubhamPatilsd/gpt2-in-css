# Digital arithmetic inside GSUB

**The symbolic execution primitive works exactly, but is not a speed win over
native CSS at this scale.** Chrome 153.0.8010.48 on an Apple M2 Pro passed every
8-bit addition, every following nonlinear result, and every tiny two-layer network
state with native CSS-counter inputs. Intermediate arithmetic stays inside GSUB.
Input encoding and final native readback make the complete path slower than the
matched CSS control. Retain this as a building block for a model designed around
glyph/code state; do not replace the current GPT-2 arithmetic with it.

## Measured results

| Operation | Direct glyph input | Native CSS-counter input | Native CSS control |
| --- | ---: | ---: | ---: |
| Unsigned 8-bit addition, including carry | 65,536 / 65,536 exact | 65,536 / 65,536 exact | 65,536 / 65,536 exact |
| Addition followed by nonlinear substitution | 65,536 / 65,536 exact | 65,536 / 65,536 exact | 65,536 / 65,536 exact |
| Two-layer integer network | 256 / 256 exact | 256 / 256 exact | 256 / 256 exact |

All comparisons use exact integer widths, with zero maximum error. The explicit
255+1 negative controls produced 320 px with the GSUB program enabled and 0 px with
`rlig` disabled. Splitting the four inputs across atomic inline-blocks also produced
0 px, confirming that internal glyph results cannot cross those shaping boundaries.

The font contains 1,635 glyphs and 13 lookups, occupying 7,508 WOFF2 bytes or 47,580
TTF bytes. The adder invokes six top-level lookups plus a nested carry lookup; the
nonlinear stage adds one; the network invokes five. Runtime HTML and CSS are 225 and
2,175 bytes. The final fresh browser's navigation plus explicit font wait took
28.11 ms. This startup result is not a repeatability estimate.

Warm median milliseconds for **256 independent changing outputs per sample**:

| Operation | Prepared characters → final width | CSS integers → GSUB → final width | CSS arithmetic → final width |
| --- | ---: | ---: | ---: |
| Addition | 0.9 | 3.4 | 1.0 |
| Addition + nonlinear lookup | 0.9 | 3.4 | 1.3 |
| Tiny network | 0.7 | 1.9 | 1.5 |

The 1-output samples often have a zero median because of browser timer resolution;
they must not be interpreted as zero-cost execution. The JSON also contains all
64-output timings, p95s, per-sample durations, and validation checksums.

A second set includes an actual native numeric consumer after the font: anchor
width → size container → registered `--gsub-decoded` number → dependent width.
Every one of its 61,440 observed outputs matched exactly, and final computed-style
readback confirmed all 1,536 typed numbers. The matched CSS control uses the same
output boundary.

| Operation | Native inputs → GSUB → native numeric output | Native inputs → CSS arithmetic → same output boundary |
| --- | ---: | ---: |
| Addition | 5.0 ms | 2.5 ms |
| Addition + nonlinear lookup | 4.9 ms | 2.7 ms |
| Tiny network | 3.4 ms | 3.1 ms |

The p95s for those GSUB paths are 7.0, 5.8, and 4.0 ms respectively. The apparent
prepared-glyph advantage disappears when the input representation and output
boundary are charged. A deeper circuit might amortize them, but this experiment
does not establish that scaling result. It also does not simulate a GPT-2 layer:
its integer domain and two-input network are intentionally small feasibility gates.

Machine-readable measurements and environment are in [results.json](results.json),
with font/source hashes in [reference.json](reference.json). The earlier complete
passing run without native readback is preserved in `attempt-no-native-readback/`.
Both browser runs used independent fresh processes and the same font bytes.

## Question and kill criteria

Can a browser carry intermediate results as glyph identities, execute multiple
arithmetic/nonlinear steps inside one shaping operation, and expose only the final
answer? The first gate is exhaustive unsigned 8-bit addition, including carry out
to nine bits. If it fails, stop. The second gate applies a nonlinear lookup to the
sum glyph without reading the sum into CSS. The third gate is a tiny connected
two-layer integer network. Only passing primitives receive timing tests.

Both direct-text stimulation and native CSS-counter-generated text are checked.
The latter includes converting two CSS integer inputs into the character sequence
consumed by the font. Four separate inline-blocks are a deliberate negative control
for shaping boundaries. Disabling `rlig` must also disable the arithmetic result.

## Programs

The adder starts with four position-tagged nibble characters:

1. A ligature substitutes the low input pair with a low sum glyph, retaining carry.
2. A ligature substitutes the high input pair with a high sum glyph.
3. A contextual lookup increments the high sum when the low sum carries.
4. Single substitutions normalize the resulting low and high digits.
5. A final ligature combines the digits into one sum glyph, including the ninth bit.

This uses 256 low-pair rules, 256 high-pair rules, and 512 final digit-pair rules.
It does not tabulate all 65,536 whole-byte input pairs. The final glyph's advance is
`64 + sum` pixels at the declared 1,024-unit font size. Intermediate glyphs have
zero advance, and no intermediate value crosses into CSS or the observation harness.

The optional following substitution evaluates
`min(255, floor((sum - 128)^2 / 128))` from the sum glyph. This intentionally
non-monotonic nonlinear function catches accidental direct width addition.

The tiny network takes `x,y` in `[0,15]`:

```
h0 = max(0, 2*x + y - 16)
h1 = max(0, x - 2*y + 8)
out = max(0, 3*h0 - 2*h1 + 5)
```

A joint input glyph expands into two preactivation glyphs; following lookups apply
ReLU, combine the two hidden glyphs, and apply the final ReLU. These are five
successive GSUB lookups. The first affine map has 256 joint input cases and the
second has 720 hidden-state pairs. Those tables implement the network weights and
activation, not answers injected by the measurement harness.

## Method

The runtime is HTML, CSS, and a font, with CSP `script-src 'none'`. JavaScript runs
only in the external harness to create fixtures, stimulate input values, and read
final geometry. Independent expected arithmetic is evaluated in the Node harness,
outside the page. This is a native component experiment, not autonomous generation.

Direct input uses position-tagged characters prepared by the harness. Native input
uses registered CSS integers, `mod`/`round`, six custom counter styles, and one
generated-content pseudo-element. A matched CSS control computes the same arithmetic
directly from the same two integer inputs and emits the same width.

Timing batches contain 1, 64, or 256 independent outputs. Each sample changes every
input, synchronously forces the dependent widths, and includes the input writes,
browser CSS encoding where used, shaping, layout, and width reads. Timing excludes
stimulus preparation and cross-process protocol transport. Direct-text timings
therefore exclude external integer-to-character conversion; the native-input route
is the complete input-encoding comparison. Each configuration has 40 samples; the
first five are excluded from summary statistics. This is a small screening run,
not a hardware-independent throughput estimate.

Browser work and font builds run under the shared advisory serialization lock:

```
python3 tools/run_unconventional_isolated.py --label gsub-arithmetic-build -- uv run tools/build_gsub_arithmetic_probe.py
node --check tools/test_gsub_arithmetic_probe.mjs
python3 tools/run_unconventional_isolated.py --label gsub-arithmetic -- node tools/test_gsub_arithmetic_probe.mjs
python3 tools/run_unconventional_isolated.py --label gsub-arithmetic-readback -- node tools/test_gsub_arithmetic_probe.mjs
```

## Preserved construction failures

The first harness attempt served a missing favicon after sending success headers;
its exception handler then attempted to send a second set of headers. This caused
`ERR_HTTP_HEADERS_SENT` before arithmetic testing. The server now reads files before
sending headers. No arithmetic result was obtained from that attempt.

The next attempt correctly reported Chrome's `OTS parsing error: glyf: zero-length
table`. All glyphs were intentionally invisible, which produced an empty outline
table. The prior font, source, manifest, and error JSON are preserved in
`attempt-ots-zero-glyf/`. A one-unit triangle was added only to `.notdef`, following
the existing graph-selector probe. This does not alter the arithmetic glyph metrics.

The first exhaustive adder with UPEM/font-size 1,000 passed 65,138/65,536 exact width
checks; the remaining 398 results differed by precisely 1/64 px. It is preserved in
`attempt-upem1000-rounding/`. The adder's strict gate stopped downstream tests, and
the font size and units per em were both changed to 1,024. This power-of-two scale
removed every observed readback discrepancy. No tolerance or rounding of observed
answers was added to the successful tests.

## Scaling boundary

A working tiny digital network would demonstrate internal symbolic execution, not
a dense GPT-2 compiler. Direct multidimensional lookup tables grow exponentially
with input fan-in; the tiny network deliberately has only two inputs per neuron.
General bit-serial circuits avoid that truth-table expansion but introduce many
glyphs, substitutions, carry dependencies, and shaping work. The font's glyph and
lookup limits and the browser's shaping work budget must be measured before any
large circuit claim. Independent inline-blocks cannot communicate intermediate
glyph identities; crossing those boundaries would reintroduce numeric readback.
