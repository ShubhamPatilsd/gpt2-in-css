# Reproduce the connected MLP comparison

The [plan](PLAN.md) specifies the measurement boundary and the distinction
between a segment replay and autonomous token generation. Both pages calculate
native LN2, the MLP, residual/bias addition, and the next layer's LN1. Only raw
post-attention residual fixtures and generation changes are supplied externally.

The baseline uses the current reusable core's matrix generator with its dynamic
range and generation gates. The candidate uses existing avar2 projection assets.
Layers 0 and 1 use four actual residual vectors from the quantized model's
`[15496, 995, 11, 314]` trajectory. They are isolated layer replays, not two
connected recurrent transformer layers. Neither page contains an author script.

## Build

From the repository root, using the existing model and font assets:

```sh
uv run --with fonttools --with numpy --with pillow --with brotli python tools/run_unconventional_isolated.py --label build-native-mlp-integration -- python tools/build_native_mlp_integration.py
```

This writes four HTML pages and `manifest.json`, reusing the existing fonts.
The manifest retains raw boundary inputs, independent mathematical outputs,
the approximation differences, source/HTML/font hashes, and error thresholds.
It does not rebuild the full model or launch generation. Rebuilding replaces
the generated fixtures; preserve a copy if the recorded hashes must remain exact.

## Correctness and short timing

The complete four-variant gate reproduces the retained layer-1 candidate failure:

```sh
python3 tools/run_unconventional_isolated.py --label native-mlp-all-gate -- node tools/test_native_mlp_integration.mjs --mode gate --output experiments/native-mlp-integration/repro-all-gate.json
```

For the accepted layer-0 diagnostic comparison, run sequentially with only one
benchmark page resident:

```sh
python3 tools/run_unconventional_isolated.py --label native-mlp-layer0-gate -- node tools/test_native_mlp_integration.mjs --mode gate --variants baseline-layer0,candidate-layer0 --output experiments/native-mlp-integration/repro-gate.json
python3 tools/run_unconventional_isolated.py --label native-mlp-replay -- node tools/test_native_mlp_integration.mjs --mode timing --variants baseline-layer0,candidate-layer0 --gate experiments/native-mlp-integration/repro-gate.json --schedule replay --repeats 2 --warmups 2 --measured 8 --output experiments/native-mlp-integration/repro-timing.json
python3 tools/run_unconventional_isolated.py --label native-mlp-first-visit -- node tools/test_native_mlp_integration.mjs --mode timing --variants baseline-layer0,candidate-layer0 --gate experiments/native-mlp-integration/repro-gate.json --schedule first-visit --repeats 2 --warmups 2 --measured 3 --output experiments/native-mlp-integration/repro-first-visit.json
```

The timing command requires a passing gate for the exact fixture manifest.
The harness refuses to overwrite an existing result. Baseline/candidate order
reverses between repetitions, and each page gets a fresh browser process.
Every timed generation is checked at all output coordinates. Font loading and
all-coordinate verification are recorded separately from update latency.

The browser defaults to installed Google Chrome; `CHROME_PATH` can select a
different executable. Playwright uses the existing Codex dependency directory,
or `CODEX_NODE_MODULES`. Browser-version differences require new correctness and
timing runs. The shared advisory lock prevents simultaneous benchmark work.

These are diagnostic vector-error gates, not a claim of GPT-2 token agreement
or arbitrary-input correctness. Baseline and candidate numerical methods differ;
the report must include errors against each implementation's own oracle and the
common exact-GELU/float-projection target.

The initial state maximum-error limit of 0.1 failed on layer 1 for both backends.
The final diagnostic policy uses the existing reusable-core state RMSE < 0.05
criterion and keeps the next-LN maximum-error limit of 0.01. All maximum errors
remain visible. This acceptance change is recorded in [PLAN.md](PLAN.md), with
the failed attempts preserved; it does not make the original strict gate pass.

## Runtime-estimate backtest

This command reads saved results and launches no browser:

```sh
python3 tools/estimate_native_mlp_runtime.py --output experiments/native-mlp-integration/repro-estimation.json
```

Optionally attach fresh segment reports with `--benchmark PATH` (repeatable). The script
backtests forecasts trained only on early continuing tokens of the saved
capacity-32 run. Later continuing tokens are withheld, and terminal behavior is
reported separately. It intentionally leaves the new full-model prediction
empty until native-loop calibration exists. The checkpoint calibration plan in
its output is a specification, not an implemented checkpoint-resume runner.

## Bounded native-prefix scaffold

The new [prefix observer](../../tools/benchmark_native_token_prefix.py) leaves
the compiled capacity and generation limit at 32, but stops its browser after
observing four token captures. This avoids the allocation and terminal-token
differences introduced by recompiling a four-slot model. An independent parent
watchdog bounds wall time and terminates only its own child process group.

Inspect the plan without launching Chrome:

```sh
python3 tools/benchmark_native_token_prefix.py --directory experiments/browser-gpt2/demo-font-vector-context32 --output experiments/native-mlp-integration/native-prefix4-attempt1 --tokens 4 --wall-seconds 480 --heap-growth-percent 10 --dry-run
```

The corresponding future measurement command is:

```sh
uv run --with fonttools --with numpy --with pillow --with brotli python tools/run_unconventional_isolated.py --label native-prefix4 -- python tools/benchmark_native_token_prefix.py --directory experiments/browser-gpt2/demo-font-vector-context32 --output experiments/native-mlp-integration/native-prefix4-attempt1 --tokens 4 --wall-seconds 480 --heap-growth-percent 10
```

That command was **not executed** in this task. It requires a fresh output
directory. The runner was checked offline for syntax, argument validation,
unchanged graph planning, and normal/timeout process-group behavior. It has not
yet been validated by running the full native model in a browser. It observes
token epochs and winners but does not independently validate cache or residual
values, so a successful capture is not a numerical-quality certificate.

Its report can feed the estimator directly:

```sh
python3 tools/estimate_native_mlp_runtime.py --calibration experiments/native-mlp-integration/native-prefix4-attempt1/prefix-results.json --output experiments/native-mlp-integration/native-prefix4-estimate.json
```

The estimator requires a complete, contiguous, unchanged-source 12-layer,
capacity-32 prefix of at least four tokens and rejects segment measurements,
timeouts, wrong capacity, skipped observations, and nonfinite times. Its output
remains a **diagnostic forecast** until numerical and later-context checks
establish accuracy. It treats initialization separately and labels its terminal
estimate as an uncalibrated proxy. Historical prefix data test this code path
offline; no new model result is implied.

See [prefix checks](prefix-scaffold-offline-checks.json) and
[estimator checks](calibration-scaffold-check.json). No command above is intended
to execute all 32 generated tokens; the observer could allow work on the next
token to begin before it closes the browser.
