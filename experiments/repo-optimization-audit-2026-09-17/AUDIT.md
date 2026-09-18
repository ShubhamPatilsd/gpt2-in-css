**Repository optimization audit — September 17, 2026**

The reusable HVAR/CSS runtime is the strongest complete implementation supported by the saved evidence. It already combines the major architectural wins. There is no demonstrated faster combination waiting to be enabled, but there is also no evidence that the current combination is optimal. Several independent options remain unmeasured, older measurements do not consistently transfer into the reusable graph, and the repository has no single build recipe that denotes the best validated bundle.

This audit inventories **407 experiment directories, 379 Markdown reports, 237 top-level RESULTS reports, and 724 tool-directory entries**. I traced the current compilers, launcher, manifests, complete native runs, historical backend decision record, and newer acceptance/rejection reports. The [inventory](inventory.json) records every experiment directory, report hashes and available evidence paths. Generated font/image/CSS assets were inspected through their generators, manifests and relevant results; this is not a claim to have manually inspected every byte of the 27 GB repository or rerun every experiment. Existing modifications, model assets and production defaults were preserved. The only new numerical execution is the bounded offline normalization screen below.

**What “current” actually means**

There are three different entry points:

| Entry point | Actual behavior |
|---|---|
| [Launcher](../../tools/launch_browser_gpt2.py) | Opens `demo-font-vector-twelve`, the preserved 12-layer, 8-token bundle; defaults to heap growth 10%. |
| [Compiler CLI](../../tools/browser_gpt2_runtime.py) with defaults | Builds the older scalar-cache, non-reused core; `reuse-core`, `scoped-state` and `detached-output` require explicit flags. |
| Current source with the newer flags | Uses v2 font-vector operators by default; optional value-width reuse, fallback value layout, global projection and locality transforms are separate candidates. It does not reproduce the preserved v1 bundle merely by choosing font-vector storage. |

The [8-token manifest](../browser-gpt2/demo-font-vector-twelve/manifest.json) and [32-token manifest](../browser-gpt2/demo-font-vector-context32/manifest.json) establish the retained combination:

- One rendering graph reused over all 12 layers, with private layer controls and native generation/acknowledgement checks.
- Whole-head font-settings K/V storage: 48 fields per layer/position, versus 552 in the earlier packed representation and 1,536 scalar fields.
- Row-q9 dense weights, live activation ranges, exact CSS GELU, and centered context transport.
- A detached scorer/input bank and full-vocabulary q16 two-pass head with bounded reduction trees.
- Full causal attention; no sink/window approximation. The 32-token bundle separates score and epoch transport.

Saved complete native measurements:

| Bundle | Total | Reported warm median | Sampled renderer peak | Token agreement |
|---|---:|---:|---:|---|
| Original scalar, 8 outputs | 662.495 s | 77.956 s | — | 8/8 q9/q16 and original float |
| Reused font-vector v1, 8 outputs | 402.672 s | 51.310 s | 3,863 MiB | 8/8 both references |
| Reused font-vector v1, 32 outputs | 3,177.132 s | 97.694 s | 5,216 MiB | 32/32 both references |

Sources: [original results](../browser-gpt2/RESULTS.md), [8-token summary](../browser-gpt2/demo-font-vector-twelve/scaling-summary.json), [32-token summary](../browser-gpt2/demo-font-vector-context32/scaling-summary.json). These are historical runs, not randomized matched comparisons. The saved warm summaries include the terminal interval; future comparisons should separate it. Agreement on this one continuation is not general checkpoint equivalence.

Top-level [README](../../README.md), [FULL_GPT2](../../FULL_GPT2.md), and [OPTIMIZATIONS](../../OPTIMIZATIONS.md) predate major results. Even newer reports have stale “pending” sections. For example, `SCALING_WORK.md` still calls the 32-token run in progress, while its final JSON records completion. Build/source provenance should take precedence over an old recommendation paragraph.

**Why simply combining the historical winners is not the answer**

| Technique | Strongest relevant evidence | Consequence |
|---|---|---|
| Value-width reuse | About 28% less attention append time at position 32 in components; repeated 12-layer/four-token pairs move in opposite directions, −6.3% and +13.7%. | Keep opt-in; no repeatable native gain. [Scaling results](../browser-gpt2-scaling/RESULTS.md) |
| All-head private ownership | Works autonomously; 12-layer/two-token run is 99.487 s versus an earlier 82.73 s control, with higher RSS. | Not a speed winner; historical comparison is not a controlled causal estimate. [Integration results](../browser-gpt2-integration/RESULTS.md) |
| Selective feedback reads | 1,538→770 reader channels, but four paired native handoff tests are slower; median paired penalty 28.7%. | Leave off. Fewer channels do not remove update cycles. [Latest results](../style-simplification-review/RESULTS.md) |
| Layer-rule hoisting | Exact matched outputs; fresh QKV neutral and fresh MLP roughly 1% slower. | Source cleanup, not a performance promotion. [Latest results](../style-simplification-review/layer-hoist/RESULTS.md) |
| Sparse avar2 GELU MLP | Old isolated 251 ms result; current connected layer-0 first visits are 17–19% slower, roughly 1.8× renderer RSS, and layer 1 fails downstream error. | Do not substitute the isolated minimum into a token forecast. [Connected comparison](../native-mlp-integration/RESULTS.md) |
| Geometry-normalized easing | Large older two-block local win, but the 12-block screen is 39.7→39.3 s, unresolved within noise; current generator rejects easing with dynamic ranges. | Not a missing safe switch. [Hybrid results](../hybrid-12block-profile/RESULTS.md), [generator](../../tools/build_hybrid_twelve_block.py) |
| Global projection axes | Older connected layout improves; newer two-layer/four-token files show 39.917→40.146 s, with matching tokens. | No current integration win shown. [Control](../browser-gpt2/demo-widths-control4/scaling-summary.json), [candidate](../browser-gpt2/demo-widths-global4/scaling-summary.json) |
| Early V preparation | Four controlled processes: 14.2% slower mean warm attention update, outputs identical. | Leave off. [Results](../browser-gpt2/EARLY_VALUES_RESULTS.md) |
| Aggressive scalar packing, broad resets/containment, stage retirement | Precision failures or higher connected work recur across experiments. | Do not infer savings from DOM/property count. [Backend history](../numeric-backend-decision/RESULTS.md), [memory work](../browser-gpt2/MEMORY_AND_SPEED.md) |
| GSUB arithmetic, AAT, metric banks, SVG alternatives | GSUB width scaling loses; downloaded AAT fails support; direct metric banks lose at dense width; stock SVG precision remains inadequate. | No overlooked replacement demonstrated. [GSUB](../gsub-partitioned-digits/RESULTS.md), [AAT](../aat-support-probe/RESULTS.md), [metrics](../hvar-five-metric-scale/RESULTS.md), [SVG quality](../svg-w8a8-generation/RESULTS.md) |

The output-head history also contains many genuine local wins: hot-two rows, block-flow groups, bounded maxima, groupwise certificates and selective precision. Those belong to a different coarse/refinement search architecture. Its production hard tails, transport repairs and routing overhead must be included; it is not a bag of switches that can be added independently to the current full q16 scan. The full head already incorporates the integer-axis accuracy repair and bounded/two-pass identity transport. See [production-range cascade](../gpt2-groupwise-cauchy-blockflow-production-range/RESULTS.md) and [six-font repair](../gpt2-groupwise-cauchy-blockflow-production-range-q16-sixfont/RESULTS.md).

**Concrete gaps worth pursuing**

1. **Test projection settings alone.** The existing `proj-settings` transform prepares four axis lists at the projection owner without the broad resets bundled into the unsuccessful metric-isolation experiment. I found the implementation and planned protocol but no completed result for this variant. It targets repeated list preparation across 3,072 pack elements and changes no matrix weights. It is distinct from global-axis projection, which retags fonts and changes the layout. First compare real LN2→FC→GELU→projection consumers with fresh vectors and layer revisits. The browser may already share enough work that it is neutral. [Source](../../tools/browser_gpt2_dense_locality.py), [dense report](../browser-gpt2-integration/dense-report.md).

2. **Revisit normalization with centering before the font.** The recent failed preserved-weight rearrangement computes `Q @ (gamma*x)` and subtracts `mean*(Q@gamma)` afterward. I screened the unmeasured alternative below. It removes that cancellation failure but still misses the unchanged full sensitivity gate. This is a more credible numerical direction than retrying the same uncentered formula; it is not an approved replacement or an established performance gain.

3. **Preserve rendered V across layer changes, rather than only within one selected layer.** Width reuse helps a one-layer component but loses its consistent benefit when the shared surface selects different layer banks. A two-layer persistent-width experiment with the same allocated/populated slots could test whether that lost reuse explains the gap. Include delivery, layer selection, current-generation completion and RSS. This was already proposed but no completed implementation was found; it is an unfinished follow-through, not a newly invented technique. Duplicating a 12×32×768 surface could erase the gain in memory. [Recorded proposal](../gsub-partitioned-digits/NEXT_DIRECTIONS.md), [layer revisit measurements](../browser-gpt2-scaling/RESULTS.md).

4. **Change the lifecycle mechanism, not merely the number of readers.** The default and selective loop perform the same 119 style recalculations and 71 layouts in their 24-pass fixture. A static bank-specific reader arrangement or a demonstrably removable capture/receipt cycle is a different hypothesis from replacing a long animation list every pass. Narrowing residual/context timeline scope is also unmeasured by the old attention-score-timeline experiment. These must preserve both saved values and generation acknowledgements. No speedup is predicted. [Loop evidence](../style-simplification-review/selective-loop/RESULTS.md), [source review](../browser-gpt2-integration/profiling/source-review.md).

5. **Correct the universal 256-axis assumption before ruling out future fusion.** The saved [font-backend probe](../browser-gpt2/font-backend-probe/results.json) loads and checks eight outputs of 768-output fonts with 768 axes via Fontations; the original backend falls back above 256. However, its changed-state samples take approximately 462–1,352 ms at 768 axes and have roughly half a design-unit error. This does not validate a full-width fused MLP. Avar2 routing to Fontations is confirmed in the [exact tested Chromium revision](https://raw.githubusercontent.com/chromium/chromium/199a3a541d76237379e353b348e64045584db057/third_party/blink/renderer/platform/fonts/web_font_typeface_factory.cc). A small real-weight internal-fusion group is a possible research gate, conditional on overcoming that performance/precision cost; do not build a giant font bank first.

Lower-priority unfinished options include vocabulary `settings`/`private-inputs` and retuning consumer chunk size for the reusable graph. The former baseline already computes font settings on two owners, not 50,257 rows, so the expected benefit must be described accurately. The latter's historical 128-versus-512 result belongs to a different connected graph; it is a reason for a bounded sweep, not evidence that 512 is currently wrong.

**New offline result from this audit**

With the exact existing q9 matrix `Q`, the candidate is:

```text
z = gamma * (x - mean(x))
y = (Q @ z) / sigma + (Q @ beta + bias)
```

The input is centered before axis quantization. `Q @ beta + bias` is fixed and computed offline; the weights are unchanged. This still requires mean/variance and 768 input-axis values, and moves division to the output side, potentially increasing arithmetic for 2,304/3,072 outputs. It does not eliminate LayerNorm or prove fewer browser cycles.

The screen reuses the prior 44 natural inputs plus 264 shifted/low-variance stress inputs, layers 0/5/11, QKV/FC, the same six rounding models, and the same numerical policy. Baseline errors match the previous saved results exactly; matrix code/scale hashes also match.

| Numerical model | Previous uncentered proposal | Centered proposal |
|---|---|---|
| Primary floor-coordinate/continuous-advance, natural | 44/44 pass | 44/44 pass |
| Primary model, stress | 189/264 fail the relative gate | 264/264 pass |
| All six models combined | Full gate fails | 1,846/1,848 pass; full gate still fails |

The new primary worst q9-target RMSE is **0.001661**, versus **1.68533** for the prior proposal. The remaining two failures are low-variance layer-11 FC cases under nearest-coordinate/floored-pixel sensitivity: maximum error versus the float target rises from 0.010928 to 0.012196, exceeding the unchanged 10%-plus-epsilon allowance. Their q9-target RMSE is about 0.000202. All new absolute RMSE gates pass, but I did not loosen the relative gate. Resolve these cases or establish the actual browser rounding contract before treating the candidate as eligible for integration.

[Screen source](screen_centered_normalization.py), [complete results](centered-normalization-results.json), [validation](screen-validation.json). This is offline inference about numerical behavior; no browser speed, native correctness, or held-out model-quality result was produced.

**What to measure next**

Keep the preserved font-vector bundle as the reference. First run the existing projection-settings ablation; independently investigate the two normalization failures. If a candidate passes correctness and repeated complete-stage timings, compare it alone against a freshly compiled matched baseline. Only then run a small interaction test with another independently promising option, such as value-width reuse. Do not include known losing options simply to create an “all tricks” bundle.

For native acceptance, retain 12 layers and the intended 32-slot allocation even when observing only a short prefix. The existing [prefix observer](../../tools/benchmark_native_token_prefix.py) provides that scaffold but has only offline validation. Compare opposite fresh-process orders, separate first/continuing/terminal tokens, verify retained KV/final-head inputs, and retain failed runs. Later occupancy windows are required before predicting a full 32-token gain. The prior MLP backtest shows why constant early-token extrapolation fails.

The saved 32-token run has about 68% renderer task time in style work. Coarse observations put about 89% between embedding and final core/head handoff, but neither figure assigns exclusive cost to MLP, cache or head. The attempted detailed diagnostic observed **zero complete six-boundary passes out of 24**. Fix that measurement gap before declaring a specific operator the dominant target. [Stage-cost evidence](../browser-gpt2-integration/stage-costs.md).

Finally, broaden quality beyond the single repetitive `Hello` continuation: the planned teacher-forced positions and multiple continuations remain important. A faster approximate backend or bounded attention ring is a separate speed/quality tradeoff, not a same-computation improvement. F16/F32 browser work and jointly trained compact-code models remain separate research branches; their tiny feasibility probes do not supply current token-speed results.

The practical priority is a reproducible validated recipe, a few targeted unresolved ablations, and better native attribution. The evidence does not support restarting the many rejected matrix/transport families or declaring optimization finished.
