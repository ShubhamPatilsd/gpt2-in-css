# Native GPT-2 in Chromium

A bounded browser implementation of GPT-2-small: **12 transformer blocks, the
full 50,257-token vocabulary, a one-token prompt picker, and up to eight greedy
output tokens.** No JavaScript, WebAssembly, WebGPU, or server-side inference.

This is a computational prototype, not a general chat interface. Arbitrary text
tokenization, long prompts, cache eviction, and generation beyond eight tokens
are not implemented. Token pieces are decoded individually, so arbitrary split
UTF-8 sequences are not guaranteed to display correctly.

Measured full pipeline: **110.8 s to the first observed result from page load,
78.0 s median between later results, and 11 min 2.5 s for all eight tokens.**
See [the complete measurements and validation limits](RESULTS.md).

The subsequent [memory and context-scaling investigation](MEMORY_AND_SPEED.md)
has a faster experimental packed-cache component, but has not established lower
resident memory or validated a new full-pipeline time. The served demo below
still uses the original validated scalar cache.

## Run

From the repository root, serve the files:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open **Chrome** at <http://127.0.0.1:8000/experiments/browser-gpt2/demo/>.
Choose a prompt and click **Run / continue**. Uncheck it to pause at a token
boundary; the current computation may finish. Recheck to continue. **Reset**
reloads the document and clears native storage. The prompt locks after Run;
reset to choose a different prompt. End-of-text stops generation early.

The HTTP server only serves static files. All matmuls, attention, K/V storage,
argmax, and token feedback happen in Chromium. The page prohibits scripts via
CSP; the test harness additionally disables Chromium script execution.

Test environment: Chrome 153.0.8010.48, Apple M2 Pro, 16 GB RAM. The model uses
large font assets and substantial CPU while computing. Keep the browser tab
foreground for predictable scheduling.

## Architecture

- Two-axis HVAR lookup supplies any GPT-2 token embedding. CSS adds the learned
  positional embedding for the current epoch.
- HVAR fonts perform the four dense matvecs in each block. Activation ranges are
  computed from the live vector, not copied from calibration/reference runs.
- Typed CSS math implements LayerNorm, causal attention, and GPT-2's tanh GELU.
- One flat K/V bank per layer retains earlier slots with delayed registered-
  property transitions. Only the currently writable slot declares live sources.
- Final LayerNorm feeds a full-vocabulary q16 head. Bounded 16-way geometry trees
  find the maximum; a second 256-row pass selects token identity without fragile
  fractional-width digits in large scores.
- CSS animation receipts and SVG SMIL events capture output IDs and advance the
  epoch. Eight native view timelines feed stored IDs back into the embedding
  lookup. There is no external token scheduler or intermediate-vector transfer.
- Font-metric witnesses block the graph until its 259 font faces are ready.
  The scorer stays hidden until its first real input, then remains live so its
  feedback sources do not disappear between tokens.

The core weights are row-quantized to 9 bits. The head uses the existing q16
weight bank, bounded font-axis coordinates, and score buckets. This is not an
exact float32 implementation of GPT-2. Numerical screens and their limits are
reported alongside the measured pipeline results.

## Build and test

The compiler reuses the model and font assets already present in this workspace.
It emits model parameters, not future tokens or reference activations.

```sh
uv run --with numpy --with fonttools --with brotli --with pillow python tools/browser_gpt2_runtime.py --blocks 12 --capacity 8 --cache-layout flat --isolate-head --output experiments/browser-gpt2/demo
uv run --with numpy --with fonttools --with brotli --with pillow python tools/test_browser_gpt2_runtime.py --directory experiments/browser-gpt2/demo --http --start --limit 1000
uv run --with numpy --with fonttools --with brotli --with pillow python tools/verify_browser_gpt2_runtime.py experiments/browser-gpt2/demo
```

Additional Python/CDP-only tests cover native controls, missing-font readiness,
unobserved progress, source invariants, the full-vocabulary head, the embedding
lookup, and K/V retention. Tests are in `tools/test_browser_gpt2_*.py`.

Pipeline measurements include page/font loading and the complete repeated
forward loop. Initial Run is the only external action. The verifier runs after
Chromium closes and does not supply anything to the browser. Geometry milestone
times are coarse observations across shared browser frames, not an exact
exclusive CPU profiler for each mathematical operation.
