# GPT-2 global-q16 lattice-scale Chrome probe

## Result

The strict script-free probe passed its measurement gates: **true**. Of the tested lattices, **1/16** ranked best against the shared mathematical global-q16 buckets (14/16 browser winners; maximum contender bucket error 15).

The 1/64 scale maps each residual unit to exactly one Chrome 1/64-pixel layout quantum and each high unit to 256 layout quanta. It matched 10/16 unbucketed q16 winners and 10/16 q16 bucket winners, with maximum q16 contender error 71 buckets.

Its zero-coordinate shaped width is offset from the serialized row base by -0.50000 to -0.45313px. After the 1/64 score factor, that alone implies a -60.39 to -54.73 bucket bias, explaining the observed near-uniform displacement despite clearing the advance cap.

| Display scale | q16 winner | q16 bucket winner | Float winner | Max abs. bucket error vs q16 | Max abs. bucket error vs float | Warm median (ms) | Warm p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.1 | 13/16 | 13/16 | 13/16 | 2901 | 2900 | 4.30 | 5.00 |
| 1/16 | 14/16 | 14/16 | 14/16 | 15 | 15 | 4.10 | 5.00 |
| 1/32 | 13/16 | 13/16 | 13/16 | 15 | 15 | 4.20 | 5.00 |
| 1/64 | 10/16 | 10/16 | 10/16 | 71 | 71 | 4.20 | 5.00 |

## Advance and lattice diagnostics

The retained radix-256 high/residual WOFF2 bank was referenced in place; no fonts were copied or rebuilt. The source-bank all-axis bound exceeds Chrome's approximately 32,768px adjusted-advance ceiling at 0.1 and 1/16, but clears it at 1/32 and 1/64. Browser geometry below covers all 192 contenders, 12 glyphs per row, and all 16 fixtures at every scale.

| Display scale | Residual unit (layout64) | Theoretical max adjusted advance (px) | Browser max (px) | Measurements at/above 32768 | Zero-axis base delta (px) | Clears theoretical cap |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 0.1 | 6.4 | 93747.200 | 32768.016 | 139 | -4147.20313 to 0.02188 | no |
| 1/16 | 4 | 58592.000 | 22791.938 | 0 | 0.00000 to 0.00000 | no |
| 1/32 | 2 | 29296.000 | 11395.969 | 0 | 0.00000 to 0.00000 | yes |
| 1/64 | 1 | 14648.000 | 5697.984 | 0 | -0.50000 to -0.45313 | yes |

| Display scale | q16 winner mismatches | q16 bucket-winner mismatches | Float-winner mismatches |
| --- | --- | --- | --- |
| 0.1 | 519, 493, 390 | 519, 493, 390 | 519, 493, 390 |
| 1/16 | 493, 390 | 493, 390 | 493, 390 |
| 1/32 | 493, 889, 390 | 493, 889, 390 | 493, 889, 390 |
| 1/64 | 547, 493, 621, 889, 390, 474 | 547, 493, 621, 889, 390, 474 | 547, 493, 621, 889, 390, 474 |

State 519 diagnostics (q16 and float mathematics both select token 37848):

| Display scale | Chrome winner | Chrome bucket | Error vs q16 | Error vs float |
| --- | ---: | ---: | ---: | ---: |
| 0.1 | 2032 | 2638 | -7 | -6 |
| 1/16 | 37848 | 2649 | -3 | -3 |
| 1/32 | 37848 | 2649 | -3 | -3 |
| 1/64 | 37848 | 2592 | -60 | -60 |

The fixture set contains states 519 and 547, the eight lowest-margin corpus states, and all six production fixtures. Its 192 rows are the union of every selected state's top-16 float and top-16 q16 contenders plus token 2032. The 1,024-state mathematical screen has 0 global-q16 versus float winner mismatches.

## Runtime and timing contract

All four HTML files carry CSP `script-src 'none'`; raw-source, DOM, event-handler, resource, and network audits found no runtime script. Browser automation is external to the artifacts. Each latency measurement used a dedicated single-scale page, one all-fixture warmup, and 5 measured warm rounds. Chrome: 153.0.8010.36.

Raw data: `results.json`. GPT-2 small architecture, checkpoint, and weights are unchanged.

## Reproduce

    PYTHONPATH=tools uv run --with numpy --with pillow --with fonttools python tools/build_gpt2_global_q16_lattice_scale_probe.py
    node --check tools/test_gpt2_global_q16_lattice_scale_probe.mjs
    Q16_LATTICE_BENCHMARK_ROUNDS=5 node tools/test_gpt2_global_q16_lattice_scale_probe.mjs
