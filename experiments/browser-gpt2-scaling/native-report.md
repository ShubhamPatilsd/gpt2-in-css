# Native pipeline scaling ablations

Status: all 15 native cases completed and were independently verified; one
case's timing is excluded for known host CPU contention. The combined
candidate was slower in the initial 12-layer run, and materialization alone
reproduced much of its added style cost. Widths looked promising in a single
run, but two fresh capacity-four comparisons reversed direction: 6.3% faster
in one pair, 13.7% slower in the other. There is no repeatable native speedup
or memory reduction established by this investigation, and no 32-position
native scaling claim is made.

## Question and scope

Do attention-component improvements survive integration with native layer
switching, retained KV state, embedding, projection, MLP, final normalization,
the 50,257-token vocabulary head, and autoregressive feedback?

The initial comparison used two real GPT-2 layers and four generated tokens.
That tests the native layer/token handshakes but is a truncated model, not a
full GPT-2 quality result. Follow-up comparisons used all 12 layers with two
and four generated tokens. All pages start from token 15496 (`Hello`).

The candidate `lean` combines stable V widths, disabling empty slots,
materializing QKV-derived inputs before clearing raw QKV inheritance, and a
local attention-internal timeline scope. Baseline and single-factor `widths`
and `empty` runs distinguish the combined result from its causes when feasible.
Selective non-inherited cache aliases are omitted from the initial integration
set because the parent's component screen found a substantial regression.

## Reproduction

From the repository root, using the source tree recorded in `experiment.json`:

```sh
uv run tools/investigate_browser_gpt2_scaling_native.py --phase compile --variants baseline lean --blocks 2 --capacity 4
uv run tools/investigate_browser_gpt2_scaling_native.py --phase run --variants baseline lean --blocks 2 --capacity 4 --limit 900
uv run tools/investigate_browser_gpt2_scaling_native.py --phase verify --variants baseline lean --blocks 2 --capacity 4
```

The executed two-layer command included all four candidates:

```sh
uv run tools/investigate_browser_gpt2_scaling_native.py --variants baseline widths empty lean --blocks 2 --capacity 4 --limit 900
uv run tools/investigate_browser_gpt2_scaling_native.py --variants baseline lean --blocks 12 --capacity 2 --limit 900
```

`--phase all` performs all three phases sequentially. `--repeat 1` creates
distinct immutable case directories and reverses variant order. `--blocks 12
--capacity 2` selects the short full-model follow-up. Existing generated cases
and measurements are preserved; choose another repeat index to rerun.

An optional `--quiet N` creates a distinct case and inserts N seconds without
CDP observation after initial observer setup. Native inference continues;
the independent OS memory sampler continues. First observed completion is an
upper bound, so this run tests progress without observation and is not an
ordinary latency comparison.

## Controlled configuration and fidelity

- One reused rendering graph, flat native font-vector cache, scoped state,
  isolated vocabulary head, detached native output feedback.
- Original model fonts are referenced in place, without copying large assets.
- The production compiler is unchanged. A scoped Python compile-time patch
  replaces only the attention builder for the selected experiment.
- Generated HTML has `script-src 'none'` and is checked for script tags. The
  existing CDP recorder prohibits Runtime, Debugger and Profiler domains.
- Autostart is enabled. No activation, token, query, cache, scheduling tick or
  initial Run click is supplied after navigation.
- The Python verifier runs after browser shutdown. It independently evaluates
  the matching quantized reference, compares generated token IDs, final
  residuals, and retained K/V values, and checks the head against its actual
  final input. For 12 layers it additionally checks floating-point winners.
- Source hashes cover all Python tools present at compile time. Generated
  HTML, CSS and manifest hashes are checked again before measurement and by
  the existing verifier. Each case preserves browser version, arguments,
  memory samples, stage observations, measured timings and verification data.

## Interpretation limits

Cold wall time includes navigation and font loading. Warm intervals use
successive observed generated tokens and include CDP observation overhead.
Stage observations are boundaries, not exclusive stage timings. Renderer
style and layout percentages are diagnostic metrics. Serial browser runs
avoid direct benchmark contention from other agents; compilation is also
coordinated because it can interfere with a running renderer.

A two-layer test establishes only truncated native pipeline behavior. A
12-layer test of two tokens establishes integration on that sequence, not
32-position scaling. Agreement on these samples is not a general accuracy
claim. All proposed performance conclusions must preserve that distinction.

## Two-layer, four-token results

Run order: baseline, widths, empty, lean. One fresh Chromium process per case,
one run per variant, with no competing browser benchmark. These are all eight
real layer passes and four native vocabulary/feedback passes. Every case
generated `[11, 3387, 3387, 3387]`, matching its independently evaluated
two-layer reference: `Hello, please please please`.

| Variant | Cold first token (s) | Total four-token run (s) | Median observed warm interval (s) | Intervals to tokens 2, 3, 4 (s) | Peak renderer RSS (MiB) |
|---|---:|---:|---:|---|---:|
| baseline | 16.95 | 47.23 | 10.59 | 10.59, 11.57, 8.12 | 3142 |
| widths | 19.44 | 47.68 | 9.81 | 9.81, 9.89, 8.53 | 3204 |
| empty | 16.41 | 44.68 | 10.21 | 10.35, 10.21, 7.72 | 3190 |
| lean | 16.26 | 43.44 | 9.94 | 9.94, 10.02, 7.20 | 3229 |

`lean` had an 8.0% lower total wall time and a 6.1% lower median interval than
baseline in this run. This is encouraging integration evidence, but the
comparison has no independent repeats or reversed order. `widths` had a lower
warm median while total wall time was slightly higher; its first token took
longer. The native run does not reproduce the isolated 27% attention speedup
as a full-pipeline improvement.

Every variant's final interval is shorter than its preceding intervals. These
measurements include a terminal token with no continuing next-token feedback,
so the median is not a long-run steady-state rate. Peak memory increased
slightly for every candidate; there is no measured memory improvement.

| Variant | Final residual RMSE | Final residual max absolute error | Worst retained-cache RMSE | Retained layer/slot pairs checked |
|---|---:|---:|---:|---:|
| baseline | 0.002570 | 0.041445 | 0.001284 | 8 |
| widths | 0.002527 | 0.041445 | 0.001165 | 8 |
| empty | 0.002452 | 0.035098 | 0.001274 | 8 |
| lean | 0.002552 | 0.041445 | 0.001274 | 8 |

All 768 final residual coordinates were finite in all cases. All four token
IDs and each final vocabulary winner evaluated against its actual browser
input matched. Cache errors are reported numerically rather than called exact.
Native layer transitions are exercised: layer zero writes its cache, layer one
executes, the native head supplies the next token, and both layers revisit their
own retained prior-token state. There are zero post-navigation writes and no
page or harness JavaScript in any case.

Warm renderer task shares remained broadly similar: baseline style 46.19%,
layout 22.99%; lean style 45.66%, layout 21.22%. The percentage denominator is
renderer task time, not end-to-end wall time. This tiny capacity configuration
does not have the same cost distribution as the historical 32-token run.

The coarse stage observer rejected the terminal epoch as missing or
nonmonotonic for baseline, empty and lean. It accepted all three warm epochs
for widths. Therefore their coarse stage-share percentages do not cover the
same epoch set and are not a sound stage-by-stage comparative benchmark.

Saved evidence:

- [Baseline summary](native/baseline-b2-c4-r0/scaling-summary.json), [numerical checks](native/baseline-b2-c4-r0/numerical-results.json).
- [Widths summary](native/widths-b2-c4-r0/scaling-summary.json), [numerical checks](native/widths-b2-c4-r0/numerical-results.json).
- [Empty-slot summary](native/empty-b2-c4-r0/scaling-summary.json), [numerical checks](native/empty-b2-c4-r0/numerical-results.json).
- [Lean summary](native/lean-b2-c4-r0/scaling-summary.json), [numerical checks](native/lean-b2-c4-r0/numerical-results.json).
- [Full two-layer console log](native-two-layer.log).

Each case also contains `experiment.json` for source hashes/configuration,
`pipeline-results.json` for native observations/RSS samples, and
`verification-vectors.json` for independent post-run verification inputs.

## Twelve-layer, two-token results

Run order: baseline, lean, immediately after the two-layer suite. Both execute
24 real layer passes and two full-vocabulary/feedback passes. Both generated
`[11, 314]` (`Hello, I`), matching both independently evaluated quantized and
original floating-point references for this sequence. All 24 retained
layer/slot pairs were checked, final-head winners matched their actual inputs,
and every final residual coordinate was finite. Neither run received any
post-navigation write.

| Variant | Cold first token (s) | Total two-token run (s) | Sole observed warm/final interval (s) | Peak renderer RSS (MiB) | Final residual RMSE | Worst retained-cache RMSE |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 44.81 | 82.73 | 37.91 | 3421 | 0.027228 | 0.004203 |
| lean | 44.54 | 91.97 | 47.43 | 3168 | 0.030822 | 0.004269 |

The combined candidate took **11.2% longer overall** and **25.1% longer for its
sole warm/final interval**. Cold first-token times were similar. Peak renderer
RSS was about 7.4% lower, the opposite direction from the two-layer result.
This is one pair at capacity two; do not present either the slowdown percentage
or the memory decrease as a repeatable property yet. It directly rules out
claiming that the component or two-layer result already demonstrated a
full-model speedup.

The recorded browser task counters place much of the observed additional work
in style recalculation:

| Counter over token 1 → token 2 observations | baseline | lean |
|---|---:|---:|
| Renderer task duration (s) | 37.784 | 46.748 |
| Style recalculation duration (s) | 19.267 | 26.257 |
| Style recalculation count | 175 | 185 |
| Layout duration (s) | 5.664 | 6.144 |
| Layout count | 101 | 104 |
| Other task duration (s) | 12.820 | 14.313 |
| JavaScript duration (s) | 0 | 0 |

Style grew by about 6.99 seconds of the 8.96-second task-duration increase.
That locates observed cost; it does not identify the particular selector,
property, layer transition, garbage-collection effect, or combined ablation
responsible. No native fine-grained trace was taken. The later single-factor
12-layer follow-up is documented below.

The one reusable graph changes its selected V font locations on every layer
transition. Consequently, retaining each layer's numerical K/V does not imply
that this graph can keep that layer's rendered V unchanged while another layer
uses it. The candidate remains correct through these transitions, but this
experiment does not show successful persistent reuse of rendered V across all
12 layers. That mechanism is an investigation target, not a measured cause of
this particular slowdown.

Saved evidence:

- [Baseline summary](native/baseline-b12-c2-r0/scaling-summary.json), [numerical checks](native/baseline-b12-c2-r0/numerical-results.json), [source/configuration](native/baseline-b12-c2-r0/experiment.json).
- [Lean summary](native/lean-b12-c2-r0/scaling-summary.json), [numerical checks](native/lean-b12-c2-r0/numerical-results.json), [source/configuration](native/lean-b12-c2-r0/experiment.json).
- [Full 12-layer console log](native-twelve-layer.log).

## Source identity, limitations and next decision

All native cases used `Chrome/153.0.8010.48`, revision
`@199a3a541d76237379e353b348e64045584db057`, with
`--js-flags=--heap-growing-percent=10`. The repository HEAD was
`8945a2d9fb75d3b100f6c9a82f9c64e01fe4728e`, with existing uncommitted work;
HEAD alone is therefore not sufficient to recreate the experiment. Each case
records all Python-tool SHA-256 hashes and generated artifact hashes. The
central sources were identical across this suite:

| Source | SHA-256 |
|---|---|
| `browser_gpt2_font_vector_cache.py` | `7041e23cecef6e80fef0feb37f93231f31132458ae193ebaa750a40e46b66bdf` |
| `browser_gpt2_scaling_variants.py` | `5e25c189780d89fd33222af29778567022977e3918d60acbe797a4e55e79b971` |
| `investigate_browser_gpt2_scaling_native.py` | `2dc069620cfdb11f5fd2a4863a35ed9cb428c645f95f8cf1f29325728b28f773` |

The initial suite establishes that these candidates can run through native
layer and token transitions and the full vocabulary head on the tested
sequences. It does not establish a useful full-model speed improvement from
the combined candidate. Keep the production default unchanged. The subsequent
single-factor follow-up and repeated short comparison are described below; a
large-context native comparison would still be required to establish scaling.

The first six cases included no no-observation quiet interval, repeats,
reversed native runs, 32-position native run, or native fine-grained trace.
The benchmark slot was then released so the independent component
investigation could measure full-capacity scaling. The driver supports a
separate quiet-interval validation; it remains unmeasured here.

## Follow-up: attribute the 12-layer regression

Status: all four cases completed after the full-capacity component matrix and
the locality experiment released the shared benchmark slot. Central compiler
and harness hashes were rechecked immediately before launch and matched the
original baseline. The executed command was:

```sh
uv run tools/investigate_browser_gpt2_scaling_native.py --variants widths empty materialize timelines --blocks 12 --capacity 2 --limit 900
```

This selects new case directories and the same two native generated positions,
12 layers, vocabulary head, prompt, browser flag, and post-run verifier as the
existing baseline/lean pair. All central compiler and harness source hashes
were checked against the saved baseline provenance before preparation and
matched. No extra capacity-two baseline was run. The order was widths, empty,
materialize, timelines; these later single runs cannot remove temporal drift
from comparisons against the earlier baseline.

Static code inspection suggests four distinguishable hypotheses. These are
questions for the measurements, not causal conclusions:

| Single-factor case | Actual change | Why the complete native runtime could differ from a query-only component |
|---|---|---|
| `widths` | Each V glyph keeps probability axis `P000` at 1 and uses an additional intrinsic-width `calc-size` expression to apply its weight. | Every native layer transition selects different V axes in the shared graph. Font locations can change despite retained numerical caches, limiting the shaping reuse that benefits repeated queries within one layer; intrinsic-size work remains. |
| `empty` | Two validity properties and container queries hide score/V elements before their positions exist; output rows subtract only active glyph bases. | One slot is empty during the first token and none is empty during the second. The second token still uses the additional container-query dependencies and crosses the display-activation boundary, so its benefit and cost need separate observation. |
| `materialize` | At the first `.fvs-bank`, 2,304 raw QKV custom properties are reset to their initial values after axis-list/scale derivation. | This removes raw input propagation into attention but introduces a large explicit reset declaration at a boundary recalculated on every layer pass. Whether inherited-data savings exceed boundary style work is browser-dependent. |
| `timelines` | Score timeline scope moves from `html` to `.fvs-query`; output/context timelines keep their existing cross-stage scope. | Native layer feedback repeatedly changes the score producers and generation receipts. A narrower scope may alter lookup/update work or scheduling while the separate downstream completion requirements remain. |

### Single-factor results

All four candidates completed and generated `[11, 314]`, matching quantized and
floating-point reference winners. Each also passed final-head consistency,
returned finite residuals, and had all 24 retained layer/slot pairs checked.
There was no JavaScript and zero post-navigation writes in every case.

| Variant | First token (s) | Total (s) | Sole terminal interval (s) | Peak renderer RSS (MiB) | Final residual RMSE | Worst cache RMSE |
|---|---:|---:|---:|---:|---:|---:|
| Earlier baseline | 44.81 | 82.73 | 37.91 | 3421 | 0.027228 | 0.004203 |
| Earlier lean | 44.54 | 91.97 | 47.43 | 3168 | 0.030822 | 0.004269 |
| widths | 38.66 | 70.09 | 31.43 | 4239 | 0.029140 | 0.004269 |
| empty | 38.36 | 77.47 | 39.10 | 3662 | 0.026849 | 0.003875 |
| materialize | 41.05 | 87.24 | 46.18 | 3228 | 0.027228 | 0.004203 |
| timelines | 41.22 | 81.24 | 40.01 | 3610 | 0.027228 | 0.004203 |

| Variant | Style duration (s) | Style count | Layout duration (s) | Layout count | Renderer task duration (s) |
|---|---:|---:|---:|---:|---:|
| Earlier baseline | 19.267 | 175 | 5.664 | 101 | 37.784 |
| Earlier lean | 26.257 | 185 | 6.144 | 104 | 46.748 |
| widths | 15.888 | 181 | 4.381 | 104 | 31.031 |
| empty | 20.670 | 181 | 5.234 | 104 | 38.675 |
| materialize | 27.458 | 181 | 5.242 | 104 | 45.726 |
| timelines | 23.473 | 179 | 4.630 | 102 | 39.338 |

Counters span observations of tokens one and two. `materialize` alone
reproduced the large style-time increase, whereas `widths` alone reduced both
style and layout durations in its run. The materialization/reset change is
therefore a plausible contributor to the combined regression. This does not
exclude interactions or temporal host effects, and it does not identify an
engine-internal cause for the boundary cost.

`widths` was 15.3% lower in total time and 17.1% lower in terminal-interval time
than the earlier baseline, but its peak renderer RSS was 23.9% higher. Those
are exploratory single-run comparisons with a stale control. Empty-slot
suppression improved cold time without improving the fully populated terminal
interval. Local timeline scope did not improve that interval either.

Saved summaries and their adjacent source/protocol, pipeline and numerical
artifacts:

- [widths](native/widths-b12-c2-r0/scaling-summary.json).
- [empty](native/empty-b12-c2-r0/scaling-summary.json).
- [materialize](native/materialize-b12-c2-r0/scaling-summary.json).
- [timelines](native/timelines-b12-c2-r0/scaling-summary.json).
- [Attribution console log](native-twelve-layer-attribution.log).

Passing a single factor does not prove the combination must pass at the same
speed: interactions remain possible. The two-token terminal-interval and
single-run limitations apply to every comparison above.

## Follow-up: fresh controls and continuing intervals

Status: completed. The width-only result justified a bounded contemporary
comparison at 12 layers and four generated tokens. The initial baseline r0
is preserved for correctness but excluded from the primary timing comparison:
another agent reported a CPU-heavy source-analysis regex using approximately
one core for 40 seconds during that case before termination. Its
[`interference.json`](native/baseline-b12-c4-r0/interference.json) records the
audit. The reported conservative affected window was 2026-09-17
08:25:00–08:27:37 UTC; the native driver began at approximately 08:25:12 UTC.
The external process was PID 74321 and was terminated with SIGTERM. This is
host workload contamination, not a browser failure; no competing browser
was launched.

The replacement clean sequence is baseline r2, widths r2, widths r1, baseline
r1: two fresh-process repetitions in opposite orders. Widths r0 is skipped.
This adds two continuing intervals per process and retains one terminal
interval. It does not test 32-position native scaling.

```sh
uv run tools/investigate_browser_gpt2_scaling_native.py --variants baseline --blocks 12 --capacity 4 --repeat 2 --limit 900
uv run tools/investigate_browser_gpt2_scaling_native.py --variants widths --blocks 12 --capacity 4 --repeat 2 --limit 900
uv run tools/investigate_browser_gpt2_scaling_native.py --variants widths --blocks 12 --capacity 4 --repeat 1 --limit 900
uv run tools/investigate_browser_gpt2_scaling_native.py --variants baseline --blocks 12 --capacity 4 --repeat 1 --limit 900
```

Each process was launched only after the preceding case passed completion,
quantized and floating-point token checks, and final-head consistency. Relevant
source hashes were checked against the prior baseline and disk availability
was monitored. All cases passed; no further expansion is scheduled. Disk
space fell to roughly 0.7 GiB during the final case, but output writes
completed normally and no cleanup ran during the timing window.

### Repeated capacity-four results

The four clean runs are listed in chronological order. Every run executed
48 real layer passes with native feedback and generated `[11, 314, 1101,
7926]` (`Hello, I'm sorry`). All four generated IDs matched quantized and
original floating-point references. Every final vocabulary winner matched its
actual browser input, all 48 retained layer/slot pairs were checked, and no
post-navigation writes or JavaScript occurred.

| Run | First token (s) | Total (s) | Continuing interval to token 2 (s) | Continuing interval to token 3 (s) | Terminal interval to token 4 (s) | Peak renderer RSS (MiB) |
|---|---:|---:|---:|---:|---:|---:|
| baseline r2 | 41.20 | 162.13 | 36.34 | 40.55 | 44.03 | 3601 |
| widths r2 | 39.54 | 151.95 | 33.67 | 36.97 | 41.76 | 4236 |
| widths r1 | 42.06 | 163.91 | 35.35 | 44.79 | 41.70 | 3969 |
| baseline r1 | 42.56 | 144.10 | 32.94 | 33.65 | 34.96 | 4844 |

| Pair | Widths change in total time | Widths change in mean continuing interval | Widths change in terminal interval | Widths change in peak renderer RSS |
|---|---:|---:|---:|---:|
| r2: baseline then widths | −6.3% | −8.1% | −5.1% | +17.7% |
| r1: widths then baseline | +13.7% | +20.4% | +19.3% | −18.1% |

The direction reverses for both continuing and terminal timing comparisons.
Memory also reverses direction and varies substantially for unchanged
artifacts. The initial single-run gain is therefore insufficient to establish
a repeatable native runtime optimization. Averaging these runs into one
headline percentage would conceal the contradiction.

Renderer counters exhibit the same variability; the following values cover
all three observed post-first-token intervals and are not exclusive
end-to-end wall times:

| Run | Renderer task time (s) | Style time (s) | Style count | Layout time (s) | Layout count |
|---|---:|---:|---:|---:|---:|
| baseline r2 | 120.063 | 65.135 | 553 | 17.698 | 322 |
| widths r2 | 111.852 | 58.742 | 555 | 17.867 | 324 |
| widths r1 | 121.596 | 65.100 | 551 | 19.306 | 321 |
| baseline r1 | 100.984 | 52.196 | 555 | 15.073 | 324 |

The style/layout counts are similar while durations change. The evidence does
not identify the source of the runtime and RSS variation. No engine-level
allocation or native trace was taken, so allocator/collection policy and host
effects remain hypotheses rather than explanations established by this suite.

Baseline residual error was identical across its clean repetitions: RMSE
0.018306, maximum absolute error 0.118800, worst retained-cache RMSE 0.004467.
Widths also repeated identically: residual RMSE 0.020590, maximum absolute
error 0.252111, worst cache RMSE 0.004549. The wider maximum error should remain
visible even though the four token IDs match; short token agreement does not
establish general model quality.

The compiled HTML, CSS and manifest hashes are identical between repetitions
of each variant. The HTML itself is also identical between baseline and widths.
All runtime artifacts were rehashed after measurement and remained unchanged.
Unrelated analysis/plotting tools were added during the investigation; the
complete source inventories are preserved per case, while relevant compiler
and harness hashes were explicitly checked before each run.

Evidence:

- [Combined comparison, exact values, hashes and exclusions](native/capacity4-comparison.json).
- [baseline r2](native/baseline-b12-c4-r2/scaling-summary.json), [widths r2](native/widths-b12-c4-r2/scaling-summary.json).
- [widths r1](native/widths-b12-c4-r1/scaling-summary.json), [baseline r1](native/baseline-b12-c4-r1/scaling-summary.json).
- [Excluded baseline r0 summary](native/baseline-b12-c4-r0/scaling-summary.json), [contention audit](native/baseline-b12-c4-r0/interference.json). It completed in 153.99 s and passed correctness; its timing is absent from all primary comparisons above.

The full pipeline validates native integration of the ablations and rejects
promoting the combined candidate as an established improvement. The repeated
widths comparison remains inconclusive for performance. Keep the production
default unchanged. The investigation ends with this bounded comparison; no
32-token native rerun, quiet-interval run, further repeats, or native
fine-grained trace was performed.

## Post-measurement lint cleanup

After every measurement and verification above had finished, the native
driver's standard-library imports were reordered and its executable file bit
was enabled to satisfy Ruff I001 and EXE001. No compiler behavior, experiment
configuration, numerical data or generated runtime was changed, and no browser
or numerical rerun was performed. `uvx ruff check
tools/investigate_browser_gpt2_scaling_native.py` passed.

The [archived pre-lint driver](source-before-final-lint/investigate_browser_gpt2_scaling_native.py)
and [snapshot manifest](source-before-final-lint/manifest.json) preserve the
authoritative bytes used in these measurements. Its recorded SHA-256 remains
`2dc069620cfdb11f5fd2a4863a35ed9cb428c645f95f8cf1f29325728b28f773`.
The import-order-only file now has SHA-256
`b88de808dcb7736a66126fbf43ba62063dc194c6959b88cf7d1865910a4bd773`.
The old source hashes in individual run records intentionally remain unchanged.
