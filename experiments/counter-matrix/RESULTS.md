# Timeline-driven CSS counter matrix

Measured in headless Chrome 153 on macOS. Runtime fixtures contain HTML, CSS,
and fonts only; JavaScript is external verification and timing instrumentation.

## Idea

CSS counters provide a browser-native integer accumulator. An additive counter
style can then turn the integer back into geometry: each power of two maps to a
private-use glyph whose advance equals that power.

The successful matrix topology uses one view timeline per input:

```text
input subject width
  -> timeline progress on a sibling element
  -> one counter-increment list updates every output counter
  -> counter(y, binary-width) emits power-of-two glyphs
  -> glyph-run width is the integer matrix output
```

The matrix weights are signed integers in `[-3, 3]`; inputs are five-bit
integers. A positive reset keeps every output counter above zero. The final
widths recover the exact counter values on the browser's 1/64 px layout grid.

## Correctness and scaling

| Matrix | Nonzero weighted terms | Runtime HTML | Warm mutation median | Maximum width error |
| ---: | ---: | ---: | ---: | ---: |
| 4×4 | 15 | 4.0 KB | 33.3 ms | 0.0125 px |
| 16×16 | 224 | 21.5 KB | 33.2 ms | 0.0150 px |
| 64×64 | 3,501 | 230 KB | 33.6 ms | 0.0150 px |
| 256×256 | 56,210 | 3.37 MB | 133.9 ms | 0.0150 px |
| 768×768 | 505,444 | 29.83 MB | **1,233.1 ms** | 0.0150 px |

The first three sizes sit at the required two-animation-frame update floor.
Beyond that, counter fan-out dominates and the curve becomes strongly
superlinear.

The 768×768 result is about 19× slower than the 64.2 ms pure-HVAR projection
oracle. GPT-2's 768→3,072 FC expansion has roughly four times as many weighted
terms and counter updates, so extending this representation would move in the
wrong direction before the nonlinear boundary is considered.

## Rejected direct-container topology

The first version used an anchor-sized container for every input and placed
`counter-increment` on its `cqi`-reading child. Chromium computed the dynamic
increments correctly; for example the first four-output declaration changed
from `y0 -69 y1 46 y2 -69 y3 -46` to
`y0 -78 y1 52 y2 -78 y3 -52` after mutation.

Those increments do not reach a later sibling because counter changes in a
child are lexically scoped. Nesting all children does not fix it:
`container-type` implies style containment, and every input container starts a
new counter scope. The deepest result therefore loses the outer reset and all
earlier increments.

The view-timeline version works because all incrementing elements are siblings
inside one counter scope. Its cost is reintroducing one animation per input.

## Decision

Reject CSS counters as the dense matrix backend. They provide exact integer
reduction and require only one timeline per input, but half a million counter
updates already take 1.2 seconds and 30 MB at 768×768.

Retain two narrower primitives:

- additive counter styles are an exact integer-to-width decoder using only
  `O(log value)` glyphs;
- timeline-driven sibling counters can cheaply reduce small integer fan-outs
  and may be useful for selection or bookkeeping stages.

They do not improve the current HVAR/CSS architecture for transformer affine
maps.

## Reproduce

```sh
make test-counter-matrix
```

Raw successful measurements are in `timeline-browser-results.json`; the
counter/container scope failures are in `scope-browser-results.json`.
