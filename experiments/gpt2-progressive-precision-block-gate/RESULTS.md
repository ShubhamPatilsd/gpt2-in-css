# Progressive precision block-gate browser probe

## Result

The progressive q12 wave is correct but slower than the direct q10→q16 B=4 gate in this vertical slice; do not scale this exact browser topology yet. All 10 certified group-0 fixtures passed; every benchmark mutation matched the q16 oracle. Overall correctness pass: **true**.

| Path | Median (ms) | Mean (ms) | p95 (ms) |
| --- | ---: | ---: | ---: |
| progressive | 32.65 | 33.22 | 43.90 |
| direct | 6.20 | 6.37 | 7.80 |
| full | 159.20 | 158.88 | 172.30 |

Progressive/direct mean slowdown: **5.213×**. Full/progressive mean speedup: **4.783×**.

The progressive path shapes a mean 20.4 q12 rows and 8.4 q16 rows, versus 20.4 q16 rows in the direct B=4 gate. The q12 transport is radix-64 high/residual, three 256-axis shards per plane, at display scale 0.1.

## Correctness contract

- GPT-2 small architecture, checkpoint, and weights are unchanged; this is numerical representation and certified search only.
- q10 intervals activate contiguous four-row q12 blocks; q12 intervals activate contiguous four-row q16 blocks; q16 supplies the final exact argmax.
- Each transition uses an inclusive upper-versus-global-lower comparison and 27 outward buckets.
- The runtime HTML contains no JavaScript. The external Playwright verifier checks both gate waves, binary carriers, wrapper visibility, q16 winner/bucket, and mutation outputs.

Chrome: 153.0.8010.36. Timings use one unmeasured all-fixture warmup, then 5 alternating rounds of all ten fixture mutations per path. Raw measurements: results.json.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_progressive_precision_block_gate_probe.py
    node --check tools/test_progressive_precision_block_gate_probe.mjs
    PROGRESSIVE_PRECISION_BENCHMARK_ROUNDS=5 node tools/test_progressive_precision_block_gate_probe.mjs
