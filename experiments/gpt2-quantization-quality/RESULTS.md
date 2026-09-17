# GPT-2 quantization quality: matched held-out comparison

**Offline numerical screening, not a Chromium quality or speed benchmark.** No browser/runtime files were modified. No JavaScript was used.

6,144 teacher-forced next-token predictions: 256-token windows from 24 distinct WikiText-2 **test** articles. Main calibration: 4,096 tokens from 16 distinct **train** articles; the separately labeled old-range control uses the original short prompts. Same checkpoint, tokenizer, test tokens and generation prompts for every variant. No test-set scale fitting.

Lower perplexity is better. Relative perplexity measures ground-truth predictive likelihood, not a percentage of intelligence or task accuracy. Exact token agreement is only a diagnostic.

| Numerical recipe | Perplexity | Change vs FP32 | ΔNLL, nats/token (95% paired CI) | KL(FP32‖variant) | Top-1 agreement |
|---|---:|---:|---:|---:|---:|
| FP32 | 39.98 | +0.0% | +0.0000 [+0.0000, +0.0000] | 0.0000 | 100.0% |
| Naive dynamic W8A8 | 165.80 | +314.7% | +1.4224 [+1.3462, +1.4920] | 1.2908 | 39.1% |
| SmoothQuant-style W8A8 | 40.40 | +1.0% | +0.0104 [+0.0060, +0.0152] | 0.0151 | 90.8% |
| SVG-like 8-bit surfaces | 41.68 | +4.3% | +0.0417 [+0.0343, +0.0492] | 0.0339 | 86.7% |
| SVG-like, FP32 attention probabilities (diagnostic) | 41.55 | +3.9% | +0.0386 [+0.0321, +0.0454] | 0.0308 | 87.1% |
| SVG-like, old short-prompt calibration (control) | 152.05 | +280.3% | +1.3359 [+1.2499, +1.4270] | 1.2894 | 39.9% |

## What this means

The SVG-like approximation has a 4.3% perplexity increase on this sample. Its top-1 disagreement is **not** an equivalent percentage loss of model quality. This makes a calibrated SVG route worth investigating, but does not establish production acceptability or commercial-provider equivalence.

**Range calibration is a major part of the old failure:** holding the SVG approximation and evaluation text fixed, replacing the old short-prompt ranges with train-corpus ranges changes perplexity from **152.05 to 41.68**. No additional activation bits, extra planes or model finetuning were used. This isolates calibration as a large effect in the simulator; it does not prove that recalibration will repair Chromium's omitted arithmetic errors.

Removing attention-probability rounding only changes PPL from 41.68 to 41.55. Its paired ΔNLL interval is [-0.0037, +0.0091] nats/token; this run does not establish it as the dominant error source. Longer contexts than 256 tokens remain untested.

**Next acceptance test:** apply train-only calibration to the actual Chromium SVG graph and measure held-out next-token likelihoods using a Python-only diagnostic harness. Validate the graph's product/reduction and nonlinear rounding, then full cached decoding. Keep the working font/CSS pipeline unchanged until that test passes. Do not replace that acceptance test with another simplified simulator result.

Intervals resample the paired article/windows (10,000 bootstrap draws); they cover sampling uncertainty on this small corpus, not systematic simulator error. This is **not** published full-WikiText perplexity: each window starts with an empty cache and position zero.

## Recipes

- **FP32:** original checkpoint, full 12-block causal attention and 50,257-token output head.
- **Naive dynamic W8A8:** signed INT8 weights, per-output-channel scale; signed INT8 linear inputs, dynamic per-token scale. Q/DQ simulation with FP32 accumulation, bias, nonlinearities, residuals, attention and KV storage. An intentionally simple baseline, not a provider-quality implementation.
- **SmoothQuant-style W8A8:** same quantizer, with calibration-derived input-channel scaling `s = sqrt(max_abs_activation / max_abs_weight)`, then `x / s` and `s * W` before Q/DQ (alpha 0.5). Applied to all linear layers including the output head. This implements the numerical reparameterization, not an official library's kernels. No finetuning.
- **SVG-like:** existing fixed 32 log-range groups, 10% headroom, 8-bit materialization at input, normalized activations, QKV/cache, context, attention outputs, both residuals, FC, GELU, projection and final hidden vector. Attention scores use per-head calibrated surfaces; probabilities round to multiples of 1/255 without renormalization. Weights use the legacy **signed-magnitude ±255** recipe, not ordinary signed INT8. Input embeddings stay FP32 in all variants.
- **FP32-probability diagnostic:** identical SVG approximation except probability rounding is removed. This is an error-isolation experiment, **not** an implemented SVG workaround or a browser-feasible precision claim.

- **Old-range control (when present):** same SVG approximation and identical evaluation tokens, but ranges come from the original eight short calibration prompts plus eight FP32 generated tokens each. This deliberately changes calibration, not precision or arithmetic, to test the effect of range selection.

The SVG screen still uses FP32 dot-product accumulation, exact FP32 layernorm/GELU/softmax followed by the listed rounding, and an FP32-accumulated output-head dot product. It omits Chromium product/reduction/filter-boundary rounding, approximation tables and readback. Thus its error is **not** certified browser error, and it is not a proven upper or lower bound.

## Context-position breakdown

Every row below uses the same windows; early positions have less context. Do not interpret naturally falling perplexity with context as improving numerical fidelity—compare relative degradation.

| Available context | FP32 PPL | SmoothQuant-style PPL | SVG-like PPL | SVG / FP32 | SVG KL |
|---|---:|---:|---:|---:|---:|
| 1-16 tokens | 229.48 | 232.60 | 235.09 | 1.02× | 0.0322 |
| 17-64 tokens | 62.07 | 61.97 | 65.25 | 1.05× | 0.0347 |
| 65-128 tokens | 35.08 | 35.81 | 36.05 | 1.03× | 0.0320 |
| 129-256 tokens | 29.09 | 29.36 | 30.52 | 1.05× | 0.0348 |

## Clipping and attention probability rounding

### SVG-like 8-bit surfaces

77,957 / 1,142,341,632 materialized values outside calibrated bounds (0.00682%). Low clipping does not imply low rounding error.

| Surface | Clipped values | Percent of that surface |
|---|---:|---:|
| b10.gelu | 4,081 | 0.02162% |
| b9.gelu | 4,074 | 0.02158% |
| b11.gelu | 3,699 | 0.01960% |
| b8.gelu | 3,597 | 0.01906% |
| b7.gelu | 3,580 | 0.01897% |
| b6.gelu | 3,206 | 0.01699% |
| b5.gelu | 3,053 | 0.01618% |
| b3.gelu | 2,696 | 0.01428% |

Of valid attention entries, 72.72% round from positive to zero. Mean probability mass lost to those zeros: 3.020% per attention row; mean absolute row-sum error: 2.176%. These are measured approximation effects, not by themselves a quality score.

### SVG-like, FP32 attention probabilities (diagnostic)

78,482 / 1,142,341,632 materialized values outside calibrated bounds (0.00687%). Low clipping does not imply low rounding error.

| Surface | Clipped values | Percent of that surface |
|---|---:|---:|
| b10.gelu | 4,109 | 0.02177% |
| b9.gelu | 4,025 | 0.02133% |
| b8.gelu | 3,535 | 0.01873% |
| b7.gelu | 3,462 | 0.01834% |
| b11.gelu | 3,416 | 0.01810% |
| b6.gelu | 3,135 | 0.01661% |
| b5.gelu | 3,075 | 0.01629% |
| b3.gelu | 2,849 | 0.01509% |

### SVG-like, old short-prompt calibration (control)

33,912,171 / 1,142,341,632 materialized values outside calibrated bounds (2.96865%). Low clipping does not imply low rounding error.

| Surface | Clipped values | Percent of that surface |
|---|---:|---:|
| b3.scores | 3,326,060 | 35.10706% |
| b4.scores | 2,677,616 | 28.26264% |
| b7.scores | 2,050,054 | 21.63863% |
| b8.scores | 1,964,949 | 20.74033% |
| b6.scores | 1,953,928 | 20.62400% |
| b2.scores | 1,735,283 | 18.31617% |
| b5.scores | 1,500,088 | 15.83365% |
| b11.context | 1,092,894 | 23.16144% |

Of valid attention entries, 61.89% round from positive to zero. Mean probability mass lost to those zeros: 3.560% per attention row; mean absolute row-sum error: 2.464%. These are measured approximation effects, not by themselves a quality score.

## Longer greedy continuations

12 fixed prompts, up to 64 newly generated tokens each; stop on EOS. No sampling, repetition penalty or prompt-dependent tuning. All outputs are saved in `CONTINUATIONS.md`, not cherry-picked.

| Recipe | Mean repeated 4-gram fraction | EOS within budget |
|---|---:|---:|
| FP32 | 53.4% | 0/12 |
| Naive dynamic W8A8 | 62.6% | 0/12 |
| SmoothQuant-style W8A8 | 57.7% | 0/12 |
| SVG-like 8-bit surfaces | 48.8% | 0/12 |
| SVG-like, FP32 attention probabilities (diagnostic) | 52.6% | 0/12 |
| SVG-like, old short-prompt calibration (control) | 80.1% | 0/12 |

Repetition is `(total 4-grams − unique 4-grams) / total 4-grams`, computed on generated tokens only. This tiny greedy sample is **not a coherence benchmark**; GPT-2 itself can repeat or hallucinate. Divergent continuations alone are not proof of worse quality.

## Validation, provenance and limits

- Batched FP32 vs existing scalar implementation, max logit error: 0.00009918; cached vs full: 0.00011444; left padding: 0.00007629.
- Known eight-token `Hello` continuation reproduced exactly. Unit/integration tests additionally cover quantizer bounds, calibration equivalence, metrics, causality and SVG-vs-legacy simulation agreement.
- Rust `tokenizers` byte-level GPT-2 BPE uses the checkpoint vocab/merges, including Unicode splitting. The older ASCII-only helper is not used for this corpus.
- [WikiText-2 dataset](https://huggingface.co/datasets/Salesforce/wikitext), revision `b08601e04326c79dfdd32d625aee71d232d685c3`. Dataset card: CC-BY-SA 3.0 / GFDL. `manifest.json` records source hashes, checkpoint/tokenizer hashes, article selections, exact token windows and seed.
- Numerical baseline informed by [SmoothQuant](https://arxiv.org/abs/2211.10438) and its [official implementation](https://github.com/mit-han-lab/smoothquant). This test does not measure any commercial inference provider, FP8 model, INT4 model, or GPU kernel.
- Earlier **actual Chromium** one-token SVG-core tests achieved 61/84 (four GELU bands) or 63/84 (32 bands) held-out winner agreement. Those are a different workload without corpus likelihoods; see `../svg-filter-bias-correction/RESULTS.md`. They cannot be substituted for this evaluation or combined into an end-to-end speed claim.
- No matched browser perplexity run or complete SVG decoding latency was measured here. JSON execution durations are evaluator costs, **not inference speeds**. The working native font/CSS demo remains unchanged.

## Reproduce

```sh
VECLIB_MAXIMUM_THREADS=4 uv run tools/evaluate_gpt2_quantization_quality.py --variants fp32 w8a8 smoothquant_w8a8 svg svg_float_probabilities
VECLIB_MAXIMUM_THREADS=4 uv run tools/evaluate_gpt2_quantization_quality.py --variants svg_legacy_ranges --append
VECLIB_MAXIMUM_THREADS=4 uv run --with numpy==2.5.3 python -m unittest discover -s tools -p test_gpt2_quantization_quality.py -v
uv run tools/report_gpt2_quantization_quality.py
```
