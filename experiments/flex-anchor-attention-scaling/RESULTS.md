# Chromium attention-reducer ablation

Runtime pages are HTML/CSS only. The Python harness uses CDP DOM, CSS, and
Performance commands; it never enables the Runtime domain or evaluates
JavaScript. Measurements are from Google Chrome 153.0.8010.48 (Chromium), with
12 heads, 64 channels per head, and 768 live output coordinates.

## September 16 timing audit: repeated versus fresh inputs

The table below alternates between two fixed input states. Its `4.40 ms` result
at context 64 describes revisiting those states, not the cost of a new token's
attention reduction. The first alternate input in that same saved run took
`54.85 ms`. Consequently the earlier 47.5x comparison must not be used as an
inference-speed estimate.

A follow-up diagnostic applied four distinct input states per variant through
CDP DOM attribute writes. It tested both changing all values and a cached-K/V
scenario that changes all scores plus only the final source's 768 value
coordinates. It checked five output coordinates after every update against
fresh scalar references; maximum error was below `2.9e-6` across these probes.
This is sampled mutation validation, not validation of every updated output.

Median style-plus-layout time in milliseconds, excluding Python input
generation, protocol serialization, and output validation:

| Context | Fresh input change | Typed stages | Flex + anchors |
|---:|---|---:|---:|
| 16 | All scores and values | ~12 | ~50 |
| 16 | All scores + last source's values | ~13 | ~49 |
| 64 | All scores and values | ~56 | ~202 |
| 64 | All scores + last source's values | ~54 | ~199 |

These are reducer-only browser costs. They exclude Q/K score construction,
font projections, MLP, LayerNorm, and vocabulary selection. Their inputs are
synthetic score/value states at a fixed context length, not a growing live KV
cache. The typed reducer remains the strongest tested candidate, but its fresh
input advantage here is approximately 4x over flex, not 47x.

The real two-token hybrid attention fixture below remains a different test:
it mutates one normalized input coordinate and includes the font projections.
Its `213.5 ms` must not be presented as a full transformer block or token
generation latency. No full 12-block timing for this new combination has been
measured.

## Result

The strongest reducer is not flexbox. It is a deliberately staged graph of
registered numeric custom properties:

1. registered per-head maximum;
2. registered exponentials;
3. one registered denominator;
4. registered probabilities;
5. the final weighted value sum.

`@property` boundaries make Chromium materialize typed numbers instead of
recursively substituting the entire upstream expression into every consumer.
That acts like explicit common-subexpression elimination.

Two-state repeated-mutation median, milliseconds (see fresh-input audit above):

| Context | Untyped probabilities | Fused numerator | Typed probabilities | Fully typed stages | Flex + anchors |
|---:|---:|---:|---:|---:|---:|
| 2 | 1.54 | 1.48 | 1.37 | 1.84 | 8.90 |
| 8 | 2.19 | 1.56 | 3.10 | 2.07 | 26.72 |
| 16 | 552.18 | 1.72 | 10.76 | 2.16 | 51.09 |
| 32 | 4020.62 | 175.00 | 74.30 | 2.75 | 103.82 |
| 64 | invalid | 884.02 | 489.13 | 4.40 | 208.96 |

On these repeated states at 64 tokens, fully typed staging is about 47.5x faster than flex + anchors,
201x faster than fused arithmetic, and the original untyped probability graph
does not produce a valid width. Its maximum decoded error is `1.73e-6`, versus
`1.60e-6` for flex + anchors.

The untyped graph has a sharp cliff because each `--prob` textually contains
the denominator and each of 768 value sums references every probability. The
fused form removes that quadratic expansion, but repeats `exp()` in every
output. Typed staging computes each shared scalar at an explicit browser dataflow
boundary.

## Real two-token GPT-2 integration

The real fixture keeps the existing HVAR Q/K/V and output projection. All four
new reducer backends are selectable from `build_multitoken_attention_css.py`:

- `--mix-backend css-fused`
- `--mix-backend css-typed-staged`
- `--mix-backend flex-prob`
- `--mix-backend flex-anchor`

All variants match the reference end to end. The typed staged variant has
context RMSE `5.28e-5` and residual RMSE `3.47e-4`. At two tokens, total warm
cost is dominated by the two font projections: original CSS is `207.7 ms`,
typed staged CSS is `213.5 ms`, and full flex + anchors is `243.1 ms`.

Flex normalization and anchor-weighted geometry are therefore valid, but they
are fallback tools rather than the primary attention reducer. One Chromium
quirk matters: a view-timeline subject whose width is a bare `anchor-size()`
sampled the initial equal-flex state. Wrapping it as
`calc(1 * anchor-size(...))` made the live width propagate correctly.

## Recommended split

- Use fully typed CSS stages for softmax and token-axis value reduction.
- Keep fonts for dense learned Q/K/V and output projections.
- Keep flex + anchors for terminal geometry-native reductions or places where
  a numeric readback is not required.
- Avoid unregistered reusable arithmetic expressions on high-fan-out paths.

Raw measurements are in `results.json`. The full-flow measurements are in
`../gpt2-block-css/view-timeline-attention-flex-reducers-chromium.json`.
