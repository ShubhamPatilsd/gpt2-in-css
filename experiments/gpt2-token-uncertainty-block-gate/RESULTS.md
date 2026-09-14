# Token uncertainty block-gate browser probe

## Result

B=4 has the lowest mean and B=8 the lowest median; both decisively beat the full-grid control in this fixed-group screen. All 30 block-size/fixture correctness cases passed; benchmark winners matched the oracle. Overall probe pass: **true**.

| Block size | Gate carriers | Mean shaped rows | Gated median (ms) | Full median (ms) | Full/gated |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 64 | 20.4 | 6.40 | 160.00 | 25.000× |
| 8 | 32 | 28.8 | 6.10 | 159.70 | 26.180× |
| 16 | 16 | 48.0 | 33.70 | 161.00 | 4.777× |

A ratio above 1 means the block gate is faster. Timings use 10 alternating rounds of all ten mutations per mode. The fixed group-0 probe includes all 256 int10 coarse rows in every gated variant, so it measures the actual gate/reduction overhead plus surviving global-int16 row shaping.

## Correctness contract

- One inclusive carrier per contiguous block: `max(block upper) >= max(token lower)`.
- The common exact-block wrapper is `display:none` while inactive; active exact rows overlap as in-flow grid children so each block anchor exposes their exact maximum.
- Block and final reductions have fan-in at most 16.
- Every carrier was required to be binary, every wrapper display state to match the offline oracle, and gated winner/bucket to match the full grid.
- Equality inclusion, strict-below exclusion, and lower-token tie behavior were tested synthetically.

Chrome: 153.0.8010.36. Raw measurements: `results.json`.

## Reproduce

```bash
PYTHONPATH=tools uv run --with numpy --with fonttools --with brotli --with pillow python tools/build_token_uncertainty_block_gate_probe.py
node --check tools/test_token_uncertainty_block_gate_probe.mjs
BLOCK_GATE_BENCHMARK_ROUNDS=10 node tools/test_token_uncertainty_block_gate_probe.mjs
```
