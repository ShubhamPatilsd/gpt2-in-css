# Progressive precision real-font crossover probe

## Result

At the 418→22 global B=4 budget, the extra q12 dependency does not amortize: progressive is 1.051× slower by mean. The first material tested crossover is 128 rows. Structural/live-output checks: **true**. Overall probe pass: **true**.

| Direct q16 rows / progressive q12 rows | Progressive q16 rows | Direct median (ms) | Progressive median (ms) | Direct mean (ms) | Progressive mean (ms) | Progressive/direct mean |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 128 | 7 | 67.05 | 1.90 | 46.91 | 29.77 | 0.635× |
| 256 | 13 | 151.40 | 205.70 | 153.90 | 207.83 | 1.350× |
| 418 | 22 | 310.60 | 325.30 | 310.92 | 326.75 | 1.051× |
| 640 | 34 | 471.45 | 492.00 | 472.02 | 491.38 | 1.041× |

This is a latency crossover probe, not a model-correctness result. Both paths use real GPT-2-derived 768-axis font rows and mutate all 768 hidden properties. Direct has one container/layout wave before q16 shaping. Progressive shapes radix-64 q12 rows through the first wave, then uses their max-content anchor to activate a second wave containing the reduced q16 row set.

GPT-2 architecture, checkpoint, and weights are unchanged. Runtime pages contain no JavaScript.

Chrome: 153.0.8010.48. Measurements use one unmeasured ten-fixture warmup followed by 5 alternating warm rounds. Raw data: results.json.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_progressive_precision_crossover_probe.py
    node --check tools/test_progressive_precision_crossover_probe.mjs
    PROGRESSIVE_CROSSOVER_BENCHMARK_ROUNDS=5 node tools/test_progressive_precision_crossover_probe.mjs
