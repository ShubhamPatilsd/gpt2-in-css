# Memory and context-scaling investigation — first pass

Chromium only; no JavaScript in runtime or Python/CDP harnesses. The working twelve-block demo is unchanged. These are **two-block, eight-position component tests**, not new full-pipeline token timings.

## Outcome

A native expression-packed KV prototype reduced median warm update time by 26.2–33.1% in two fresh-process comparisons. All eight states and retained-cache readbacks passed in each run. It has **not established lower resident memory**, and it is not promoted to the demo.

| Variant | Warm median (s) | Position 2 → 8 (s) | Sampled peak renderer RSS (MiB) |
| --- | ---: | ---: | ---: |
| Scalar baseline 1 | 4.220 | 3.259 → 5.292 | 2817 |
| Scalar baseline 2 | 4.621 | 3.578 → 5.751 | 2927 |
| Expression16 packed 1 | 3.114 | 2.760 → 3.360 | 3085 |
| Expression16 packed 2 | 3.091 | 2.787 → 3.385 | 2944 |
| Cache inheritance reset | 4.356 | 3.327 → 5.374 | 2621 |
| Discrete scalar | 4.556 | 3.559 → 5.749 | 2890 |
| Externally frozen cache: diagnostic only | 2.329 | 2.230 → 2.343 | 2692 |

Each run uses a fresh headless profile and the same eight input vectors, file delivery, observer, and OS sampler. The main variants were run A … B … B … A, with diagnostic variants between some runs. Two repetitions are a small screen, not a randomized performance study. Stage timings exclude subsequent numerical/cache readback checks. RSS is sampled every 0.5 seconds; it is not macOS physical footprint or exclusive/private memory. The browser's debugging agents and observer are enabled in every run. OS file caches are warm/not globally flushed. Script and V8 compilation counters were zero.

## Why context makes this implementation slower

With a KV cache, the current token's dense matrices stay fixed-size; the attention scan grows linearly with context per generated token. The current page also predeclares its bounded attention graph. It is not recomputing the entire transformer over every old token.

The browser-specific retention mechanism adds 1,536 scalar cache properties per layer per position. Each completed position across twelve layers adds up to 18,432 long-delayed transitions; by position eight there are seven completed slots, up to 129,024 retained transitions. The implementation emulates storage with animation state rather than a packed tensor buffer.

The frozen-cache ablation replaces already-computed cache values with CSS literals and disables transitions. Its vectors match the baseline readbacks while update time stays almost flat. This is strong evidence that the retention machinery causes most of the observed short-context latency growth. **The ablation uses external intermediate writes and is not an allowed inference implementation.** It is only a controlled diagnostic.

At eight positions, twelve-layer QK/PV attention is about 147,456 multiply-accumulates versus 84,934,656 in the four dense matrices per layer across the core: under 0.2%. A literal float32 KV tensor for all 96 slots would occupy 0.5625 MiB. Neither calculation estimates CSS object memory or wall time; they show why ordinary tensor intuition does not explain gigabytes of resident browser memory here. Native allocation attribution remains a separate investigation; do not label all RSS growth as the KV payload.

## New native cache representation

The successful prototype stores three signed 16-bit values and retains one dynamic scale per head/token/kind. It needs 552 retained properties per layer/slot instead of 1,536, a 64.1% reduction in storage-property count. Inputs, scales, and codes are computed live in CSS; no future activations or Python-prefilled caches enter the page.

The crucial difference is to retain the packet as an **unevaluated CSS expression** in a universal-syntax registered property with an allowed discrete transition. Decode the digits inside the consuming expression before materializing a normal CSS number. This avoids losing low-order digits when a large computed number is substituted downstream. The packet does not traverse an anchor or view-timeline.

Two ordinary 12-bit codes in a computed numeric property failed the real core (0.930 RMSE on the first state). The standalone packet probe confirms corrupted low digits for large values under both number and integer registrations. The expression-latch probe preserved and retained the tested 18–48-bit integer packets exactly, including release/restart. This is a finite probe, not proof of every CSS math expression.

Three-value expression16 caches passed all eight two-block states twice, with maximum output RMSE 0.01294 against the existing continuous-cache q9 reference and zero changed retained storage readbacks. This does not establish full-model token agreement or broad KV-quantization quality. Long expressions can cost memory and parsing even when they remove transitions; measured RSS did not improve reliably.

Resetting inherited cache properties after attention preserved exact vectors but did not improve time. Merely switching individual scalar cache values to discrete transitions also preserved exact vectors without a speed win. Neither is promoted.

A separate native allocation sample captured 2,733 allocation entries during three scalar-cache updates; the page had 40,060 DOM nodes and zero JavaScript event listeners. The stock Chrome framework did not expose useful internal symbols (local symbolication returned only ChromeMain offsets), so these stacks do not yet justify assigning memory percentages to fonts versus CSS. Raw profile: `memory-baseline/native-allocations.json`. This profiler was run separately from the latency comparisons.

## Quantization already explored

- The working model already uses row-q9 core weights and a q16 vocabulary head.
- [Packed activation studies](../packed-activation-precision/RESULTS.md) cover uniform 4–10 bits, per-channel asymmetric ranges, importance/sensitivity-ranked mixed precision, range clustering, log/mu-law companding, and multi-value geometry packets. Several numerical improvements failed after actual Chromium transport.
- [SVG dual planes](../svg-dual-plane-transport/RESULTS.md), [signed bit planes](../svg-signed-bitplane-dot/RESULTS.md), [phase dithering](../svg-rgb-dither-ensemble/RESULTS.md), and [ensembles](../svg-quantization-ensemble/RESULTS.md) were tested; extra planes/replicas did not yield a generally accurate cheap compute path.
- [Groupwise precision allocation](../gpt2-groupwise-precision-allocation/RESULTS.md) and [global head precision](../gpt2-global-precision-targets/RESULTS.md) concern vocabulary scoring, not the dominant recurrent cache-retention cost.
- KIVI-style asymmetric KV quantization has not been established for this native recurrent implementation. Simply rounding each CSS property to fewer bits does not reduce the number of objects or transitions. A useful cache quantizer must also pack the representation. [KIVI paper](https://arxiv.org/abs/2402.02750).

## FlashAttention is not an architectural change

Standard FlashAttention computes the same dense softmax attention with different tiling, fusion, and memory access; floating-point rounding can differ. It does not require changing the checkpoint or number of heads. The separate block-sparse variant is approximate. Its GPU kernel cannot be imported under the current no-JS/no-WASM/no-WebGPU-compute constraints. [Original paper](https://arxiv.org/abs/2205.14135).

For one-token decoding, Flash-Decoding is the closer analogy: partition the KV scan and merge stable softmax statistics and weighted sums. Native CSS could in principle borrow that algorithm, but it still must read the prior keys/values, and CSS evaluation is not a GPU kernel. The current attention implementation already avoids a full context-by-context attention matrix. At eight positions, fixing retained browser state is the measured priority, not adding another softmax dependency chain. [Authors' explanation](https://pytorch.org/blog/flash-decoding/).

Sliding-window attention, dropping cached tokens, replacing softmax with linear attention, or changing GPT-2 to grouped-query attention would change the computation/architecture; they are not automatically authorized optimizations of the same checkpoint.

## Next gates

1. Attribute resident/native allocations and separate CSS/style/animation data, font instances, and debugging overhead. Do not claim a low-memory runtime from lower property counts alone.
2. Reduce expression storage/decoding overhead while retaining the observed precision improvement. Compare object count, bytes, RSS, and warm latency together.
3. Before promoting any new KV quantization: verify at least 128 teacher-forced positions and 16 continuations, then run all twelve native blocks with actual browser-owned feedback. The existing 78 s/token figure remains the only validated full-pipeline timing.

## Reproduce

```sh
uv run --with numpy --with fonttools --with brotli --with pillow python tools/browser_gpt2_core.py --blocks 2 --capacity 8 --cache-layout flat --cache-codec expression16 --output experiments/browser-gpt2/memory-expression16
uv run --with numpy --with fonttools --with brotli --with pillow python tools/benchmark_browser_gpt2_memory.py experiments/browser-gpt2/memory-expression16 --output experiments/browser-gpt2/memory-expression16/new-run.json
```

Other codecs: `scalar` (default), `discrete` (control), and `numeric12` (known failing control). All raw results remain under the named experiment directories; `memory-summary.json` records the compared runs. No changes were made to the served demo.
