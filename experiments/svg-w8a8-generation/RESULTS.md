# Full GPT-2 W8A8 generation screen

This screen asks whether the fast SVG numerical representation remains useful
after connecting all twelve GPT-2-small blocks, causal multi-token attention,
KV caches, the output head, and greedy token feedback.

It runs the real pretrained GPT-2-small tensors in an offline numerical model
of the browser representation. Weights use signed nine-bit row quantization
followed by an eight-bit normalized image. Every major activation boundary,
attention score, and attention-probability boundary is materialized at eight
bits using 32 calibration-derived range groups. This is a backend feasibility
screen, not a claim that the complete browser graph has already been built.

## Result

| Metric | Result |
|---|---:|
| Held-out prompts | 6 |
| Generated tokens per prompt | 8 |
| Teacher-forced next-token matches | 28 / 48 (58.3%) |
| Mean first free-running divergence | 2.0 tokens |

The quantized path can still produce locally plausible text, but it does not
preserve GPT-2's token decisions reliably enough. For example, it exactly
matches four initial predictions for `In the future, computers`, while it
diverges on the first prediction for `Hello, my name is` and `The quick brown
fox`.

## Decision

Do not spend time extending the current eight-bit SVG graph through all twelve
blocks yet. The complete numerical screen fails before browser overhead is
considered, so merely connecting the existing pages cannot produce faithful
GPT-2 generation.

The remaining useful directions are:

1. find a general higher-precision activation representation whose operations
   retain the extra precision, or
2. reduce the font backend's bulk shaping and geometry-to-CSS readback cost.

The raw prompt-by-prompt token IDs, generated text, clipping counts, and run
configuration are in `results.json`.
