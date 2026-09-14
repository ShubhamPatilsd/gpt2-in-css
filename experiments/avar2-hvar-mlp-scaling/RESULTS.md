# avar2 + HVAR internal MLP composition

Measured in headless Chrome 153 on macOS on September 13, 2026. Runtime pages
contain no JavaScript.

## What changed

Ordinary HVAR consumes CSS-provided font axes and returns glyph widths. OpenType
`avar` version 2 can first remap every axis using variation regions driven by
all the other axes. HVAR then sees those remapped coordinates.

The probes use that ordering to calculate this inside one font-shaping pass:

```text
x -> avar2 dense map A*x -> HVAR piecewise GELU -> HVAR projection B -> widths
```

No `A*x` value becomes a glyph width, layout box, timeline, animation, or CSS
custom property. A two-axis composition probe exactly reproduces `B*A*x`, and
the nonlinear probe reproduces `B*GELU(A*x)` to the precision represented by
the font.

## Scaling result

The scaling fixture uses dense square matrices and eight nonzero piecewise-GELU
regions per hidden coordinate.

| Width | Warm mutation median | Cold load | WOFF2 | avar2 deltas | HVAR deltas |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 2.88 ms | 22.83 ms | 2.6 KB | 512 | 2,176 |
| 32 | 3.12 ms | 23.27 ms | 5.8 KB | 2,048 | 8,448 |
| 64 | 3.10 ms | 27.29 ms | 14.9 KB | 8,192 | 33,280 |
| 128 | 3.55 ms | 37.02 ms | 46.6 KB | 32,768 | 132,096 |
| 256 | 4.19 ms | 129.92 ms | 158.5 KB | 131,072 | 526,336 |

All sizes pass within the two-font-unit tolerance required by integer HVAR
deltas. Maximum browser-to-represented error is 1.73 units on values centered
at 16,000. The nine-knot GELU approximation itself contributes about 0.5--1.0
RMSE in these synthetic projected outputs.

## Why this matters

This is a real internal numeric composition primitive, not another encoding of
one output into geometry. Within 256 axes, a dense transform, coordinate-wise
nonlinearity, and second dense transform can remain inside the font engine.
The 256-wide mutation is roughly an order of magnitude cheaper than the prior
42 ms measurement for merely gathering 768 HVAR-produced numbers into reusable
CSS state, despite also calculating the second matrix and GELU here.

## GPT-2 limitation

Chromium rejects otherwise-valid fonts above 256 axes. GPT-2-small's MLP is
`768 -> 3,072 -> 768`: every one of the 3,072 hidden values depends on all 768
inputs. A single avar2 font therefore cannot represent the real full MLP.
Splitting the 768 inputs into three fonts applies GELU to partial dot products,
which is not mathematically equivalent to applying GELU after their sum.

The result changes the architecture search but does not complete GPT-2:

- Retain avar2 as the best measured backend for self-contained subgraphs of at
  most 256 live inputs.
- Investigate attention heads and other naturally narrow subgraphs first.
- Do not replace the full GPT-2 MLP until a correct decomposition across the
  256-axis boundary is demonstrated on held-out contextual states.

## Reproduce

```sh
make test-avar2-hvar-composition
make test-avar2-hvar-mlp
make test-avar2-hvar-mlp-scaling
```
