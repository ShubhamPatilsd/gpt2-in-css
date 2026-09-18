# Early value preparation: no speed improvement

Measured September 17, 2026, in Chrome/153.0.8010.48. No runtime or harness
JavaScript; Python/CDP supplies component-test QKV inputs and observes results.
This is an attention component experiment, not autonomous generation timing.

## Change tested

Control: the existing fixed-width V implementation waits for fresh attention
scores before opening the value-rendering subtree.

Candidate: render that subtree early, allowing fixed V fonts to prepare while
scores are calculated. Its outgoing generation marker stays zero until the
score receipt is ready, so early geometry does not intentionally release the
downstream consumer. The early subtree can also perform provisional weighted
layout; this is not an isolated font-only prefetch experiment.

Both variants use the same v2 fonts, 32 full-causal slots, 12 heads, 64 values
per head, and layer-0 QKV fixtures from
`scaling-integer10-context32/reference.json`.

## Measurements

Four fresh Chromium processes, serial order B1, A1, A2, B2; A is control and B
is early preparation. Every run completed all 32 updates. Warm means exclude
position 1; pooled means contain 62 updates per variant at matched positions.

| Measurement | Control | Early preparation | Change |
|---|---:|---:|---:|
| Mean warm update | 831.6 ms | 949.4 ms | 14.2% slower |
| Mean update at position 32 | 1055.0 ms | 1220.1 ms | 15.6% slower |
| Mean updates at positions 25–32 | 1027.0 ms | 1164.2 ms | 13.4% slower |

| Run | Mean warm update | Position 32 | Peak renderer RSS |
|---|---:|---:|---:|
| A1 | 824.1 ms | 1061.4 ms | 1115.3 MiB |
| A2 | 839.2 ms | 1048.6 ms | 1076.9 MiB |
| B1 | 945.8 ms | 1200.2 ms | 1058.3 MiB |
| B2 | 952.9 ms | 1239.9 ms | 1096.7 MiB |

All 128 numerical checks passed. The settled output vectors were identical
across all four runs; maximum per-update reference RMSE was 0.00006101.
Four source-contract tests also passed.

Timing includes matching CDP observation/settling overhead. The probe now
requires a visible output marker with the current generation before settling
the numeric vector, for both variants. Therefore these timings should not be
directly compared with older probe runs lacking that extra readiness check.
No full-model speed or autonomous scheduling correctness claim follows from
these component checks.

## Decision

Do not promote this scheduling variant. Early work may be adding provisional
layout instead of overlapping useful work; that explanation is a hypothesis,
not an exclusive profile. This result does not disprove all parallelization
or a more selective font-only preparation design.

The option remains experimental and off by default. The full runtime and
previously measured demo artifacts were not changed.

Reports:

- `font-vector-early-values32-a1/results.json`
- `font-vector-early-values32-a2/results.json`
- `font-vector-early-values32-b1/results.json`
- `font-vector-early-values32-b2/results.json`

Reproduce a candidate run (omit `--prewarm-values` for control):

```sh
uv run --with numpy --with fonttools --with brotli --with pillow python tools/probe_browser_gpt2_geometry_attention.py --backend font-vector --value-layout widths --prewarm-values --capacity 32 --heads 12 --head-width 64 --real-inputs experiments/browser-gpt2/scaling-integer10-context32/reference.json --output experiments/browser-gpt2/font-vector-early-values32-new-run
```
