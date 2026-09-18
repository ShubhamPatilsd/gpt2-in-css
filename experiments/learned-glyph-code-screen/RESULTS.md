# Learned glyph-code feasibility screen

This is an offline model-change experiment, not a browser speedup. It learns output-sensitive product codebooks on contextual GPT-2-small block-0 LayerNorm outputs. Each group uses k-means++ initialization and up to 24 Lloyd iterations in the FC-induced metric. Original full 768→3072 FC weights, GELU and 3072→768 projection are retained. Lookup contributions are algebraically equivalent to multiplying the reconstructed activation; explicit sums checked each split.

There are 384 contexts split by token hashes and local source files; lengths 8 and 16. Half are local text and half random-token stress inputs. Codebooks see training data only. The candidate is selected by validation error; test data does not tune its parameters.

| Group width | Codes/group | Codes/input | Validation MLP relative RMS error | Test error | Float table storage |
|---|---|---|---|---|---|
| 4 | 16 | 192 | 48.78% | 48.46% | 36.0 MiB |
| 4 | 64 | 192 | 35.33% | 36.21% | 144.0 MiB |
| 8 | 16 | 96 | 66.48% | 66.32% | 18.0 MiB |
| 8 | 64 | 96 | 54.77% | 55.24% | 72.0 MiB |
| 16 | 16 | 48 | 78.86% | 79.28% | 9.0 MiB |
| 16 | 64 | 48 | 70.43% | 70.56% | 36.0 MiB |

Selected candidate: width 4, 64 codes; held-out MLP relative RMS error **36.21%**. The predeclared 5% screening gate **fails**. The gate does not establish next-token correctness, perplexity, or full-layer equivalence. Per-kind, input, preactivation and GELU errors are in results.json.

A failed screen means these modest learned codebooks are not ready to compile into browser fonts. It does not rule out end-to-end distillation, larger training corpora or stages trained to emit codes directly. Nearest-center encoding and table summation costs remain unmeasured in the browser. Table storage here is numeric float32 storage, not a measured font size. No original model or compiler was changed.

Reproduce:

```sh
python3 tools/run_unconventional_isolated.py --label learned-codes -- env OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 tools/screen_learned_glyph_codes.py
```
