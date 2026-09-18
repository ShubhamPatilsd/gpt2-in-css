# Supervised lookup-table follow-up

The centroid-only screen failed, so this follow-up learns table values themselves. It keeps the activation codes of the candidate selected on validation data and fits additive per-group/per-code corrections to the real FC preactivations by ridge regression. Original GELU and projection are applied afterward. This is a small supervised distillation experiment, not full end-to-end training or browser inference.

The normalized same-code kernel is exactly equivalent to finite additive contribution tables; an explicit held-out table sum is checked against that kernel. No pairwise comparison with the training corpus is required at runtime: its learned contribution is compiled into each code's table. Train/validation/test isolation is inherited from the first screen.

| Ridge penalty | Validation MLP relative RMS error | Test error |
|---|---|---|
| 0.001 | 34.91% | 35.82% |
| 0.01 | 34.91% | 35.82% |
| 0.1 | 34.91% | 35.82% |
| 1.0 | 35.01% | 35.90% |
| 10.0 | 35.25% | 36.13% |

Validation selects penalty 0.01; test relative RMS error is **35.82%**. The 5% screening threshold and requirements for full-model quality remain unchanged. This does not measure the native encoding/lookup/reduction cost or demonstrate a token speedup.

Reproduce after the base screen:

```sh
python3 tools/run_unconventional_isolated.py --label glyph-table-distillation -- env OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 tools/distill_learned_glyph_tables.py
```
