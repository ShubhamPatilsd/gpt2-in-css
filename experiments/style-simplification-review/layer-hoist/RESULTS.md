# Layer-invariant CSS rules: completed matched browser screen

**Moving identical structural rules outside layer selection preserved every
output, but did not produce a repeatable speedup. Leave the option disabled by
default.** This was a bounded real-weight component experiment, not a full
GPT-2 token run or a prediction of 32-token runtime.

The existing `layer-hoist` option shrinks these fixture stylesheets by 3.3–4.0%.
Fresh-input QKV timings are essentially unchanged; fresh-input MLP timings are
slightly worse in both process orders. The small reductions in total warm style
work in the first pair reverse in the second pair.

## What changed

Only the existing opt-in rewrite in
[`browser_gpt2_dense_locality.py`](../../../tools/browser_gpt2_dense_locality.py)
was selected. No production default or numerical implementation was changed.
The new work is the matched benchmark driver and its preserved evidence.

The baseline puts structural animation, timeline, container-name and display
declarations inside each layer's conditional CSS. The candidate places their
verified common values outside those conditions. Layer-dependent font families,
font settings, ranges, gains, biases, sizes and numerical expressions remain
conditional. The nested native receipt gate stays in its original layer query.

The rewrite compares every repeated `(stage, selector, property)` value across
the two selected layers and raises an error on a difference. The exact
before/after hashes, values and permitted property names are recorded in the
[QKV audit](fixtures/layer-hoist-qkv/hoist-audit.json) and
[MLP audit](fixtures/layer-hoist-mlp/hoist-audit.json). This is not a claim that
matching declaration text alone proves identical browser lifecycle behavior;
the browser correctness checks below are required as well.

| Graph | Conditional declaration occurrences removed | Unique common declarations | Stylesheet bytes, baseline → candidate |
| --- | ---: | ---: | ---: |
| LN1 → QKV | 72 | 36 | 3,192,577 → 3,086,800 |
| LN2 → FC/GELU → projection/residual | 120 | 60 | 4,262,437 → 4,093,433 |

The byte counts include the complete generated stylesheet. Source-level stage
byte deltas differ slightly because the standalone harness also changes gate
visibility declarations after the stage rewrite.

## Workload and measurement boundary

The fixture comes from the existing
[`probe_browser_gpt2_dense_stage_locality.py`](../../../tools/probe_browser_gpt2_dense_stage_locality.py),
using real quantized GPT-2 weights for layers **0 and 11**. Its inputs are the
saved reference calculation for tokens **15496 and 11**. MLP input residuals
include the real token-2 causal attention calculation in the offline fixture.
That offline computation supplies test inputs only; it is not timed.

- QKV consumes 768 inputs and exposes all 2,304 outputs.
- MLP consumes a 768-value residual, runs normalization, the full 768→3,072
  matrix, the existing exact CSS GELU expression, the 3,072→768 projection,
  and residual addition. All 768 final coordinates are demanded.
- Dynamic input ranges and the native generation-receipt protocol are enabled
  in both variants. Fonts, inputs, expected outputs and their order match.
- Epoch 1 is cold: position 0/layer 0. It includes page/font readiness.
- Epochs 2–4 are warm first visits with newly supplied inputs/layer selections:
  position 0/layer 11, then position 1/layers 0 and 11.
- Epochs 5–6 revisit position 1/layers 0 and 11 with new generation stamps.

Each update times the external raw-input/epoch/layer write through a dependent
CSS geometry consumer. That consumer reads a weighted checksum of every output
coordinate; its height also requires the fresh native receipt. Timing ends
after three stable 25 ms polling intervals. **There is a minimum 75 ms polling
floor**, plus CDP writes, reads and induced browser work. QKV used four geometry
reads per epoch; warm MLP used five in these runs. We do not subtract this floor
or describe the remainder as pure compute time.

Renderer counters are captured before enumerating output custom properties.
Every coordinate is then read and checked outside the timer. Author scripts
are prohibited by CSP and browser script execution is disabled; the CDP harness
rejects Runtime, Debugger and Profiler commands. No page or harness JavaScript
executes the arithmetic, transfers intermediate answers or schedules stages.

Cold startup is reported separately. This fixture excludes native attention/KV,
embedding, vocabulary feedback and autonomous layer-to-layer residual storage.
It therefore cannot supply a defensible full-token extrapolation.

## Correctness gate

A separate fresh-browser smoke pass completed before timing was permitted.
Timing then used four new browser profiles per graph: one baseline→candidate
pair and one candidate→baseline pair. The graph order also reverses in pair 2.
Every case runs the identical six epochs.

| Check | Smoke | Timing | Combined |
| --- | ---: | ---: | ---: |
| Complete output vectors checked | 24 | 48 | 72 |
| Output coordinates compared with the numerical oracle | 36,864 | 73,728 | 110,592 |
| Candidate coordinates compared with matched baseline | 18,432 | 36,864 | 55,296 |

**Every candidate coordinate exactly equaled its matched baseline coordinate.**
The pre-existing oracle condition was retained: finite vectors and RMSE
strictly below 0.05 against the independent calculation with reconstructed
quantized weights. The additional baseline maximum-difference limit was 1e-6;
the observed maximum difference was zero.

The maximum oracle RMSE was **0.000821157** for QKV and **0.007992865** for MLP.
Raw maximum absolute errors were **0.003200691** and **0.098606371** respectively,
identical in both variants. We did not silently replace the existing RMSE gate
with a different accuracy requirement. These checks establish preservation of
the component behavior on this fixture, not general prompt quality.

No compilation, smoke, or timing case failed. All runs remained within the
predeclared 180-second budget per browser case. Gates and complete raw vectors
are retained under [smoke](smoke/gate.json) and [timing](timing/gate.json).

## Timings

Chrome **153.0.8010.48**, headless, fresh profiles, existing
`--js-flags=--heap-growing-percent=10` setting in both variants. All compilation
and browser work used the shared advisory experiment lock; ordinary machine
activity can still occur. Existing fonts were reused and font loading occurs
in the cold sample, before warm updates.

The following are per-case medians in **milliseconds**. Fresh has three
different input/layer cases; revisit has two cases. These small, heterogeneous
sample sets are descriptive, not confidence intervals.

| Graph / process order | Cold baseline → candidate | Fresh baseline → candidate | Fresh change | Revisit baseline → candidate |
| --- | ---: | ---: | ---: | ---: |
| QKV, baseline first | 1,262.95 → 1,259.69 | 335.55 → 334.51 | −0.31% | 290.88 → 280.09 |
| QKV, candidate first | 1,256.48 → 1,268.58 | 330.40 → 331.14 | +0.23% | 287.89 → 290.91 |
| MLP, baseline first | 2,332.54 → 2,346.13 | 763.98 → 771.80 | +1.02% | 620.51 → 609.98 |
| MLP, candidate first | 2,302.49 → 2,331.12 | 760.61 → 766.37 | +0.76% | 604.03 → 618.25 |

Below are **sums over all five warm epochs**, in milliseconds. CDP style/layout
durations are browser work counters within the measured intervals, not an
exclusive decomposition of wall time.

| Graph / order | Wall baseline → candidate | Style baseline → candidate | Layout baseline → candidate |
| --- | ---: | ---: | ---: |
| QKV, baseline first | 1,595.07 → 1,562.65 | 407.99 → 395.34 | 176.00 → 171.47 |
| QKV, candidate first | 1,575.63 → 1,596.28 | 391.56 → 405.29 | 171.28 → 175.17 |
| MLP, baseline first | 3,573.83 → 3,554.64 | 1,450.28 → 1,428.03 | 501.62 → 496.83 |
| MLP, candidate first | 3,479.14 → 3,584.69 | 1,393.57 → 1,446.41 | 491.33 → 497.80 |

The candidate does not eliminate a style/layout cycle: both variants have
10 style and 10 layout updates across QKV's five warm epochs, and 20 of each
across MLP's five warm epochs. Sampled peak renderer RSS spans 903–946 MiB for
QKV and 1,141–1,143 MiB for MLP across timing cases; this 0.5-second sampling
does not establish a memory improvement.

## Decision

The proposed simplification is valid on the tested states, but a smaller set
of conditional declarations is not enough to make these real calculations
faster. Fresh MLP is slightly slower, and aggregate style/layout/time differences
reverse with process order. There is no observed benefit large enough to
justify integration or a longer full-model benchmark. Keep `layer-hoist` as an
opt-in diagnostic and pursue other boundaries.

This result does not prove that rule organization never matters with twelve
resident layers; only two selected layers were resident here. It does show that
this independent rewrite has not cleared the small real-weight stage gate.

## Reproduction and evidence

Driver: [`benchmark_layer_rule_hoist.py`](../../../tools/benchmark_layer_rule_hoist.py).
Machine-readable results: [summary.json](summary.json).
Exact input, output, artifact, source and font provenance: [manifest.json](manifest.json).
Each fixture contains generated HTML/CSS, the numerical fixture, copied source
files, and font hashes. Timing directories link the unchanged generated pages;
they retain their own output vectors and browser counters. The driver checks
source/artifact/font hashes before and after each experiment phase.

Exact commands used below. The existing paths deliberately reject overwriting
cases; rerun in a separate workspace copy with an empty experiment directory:

```sh
python3 tools/run_unconventional_isolated.py --label layer-hoist-compile -- uv run tools/benchmark_layer_rule_hoist.py compile
python3 tools/run_unconventional_isolated.py --label layer-hoist-smoke -- uv run tools/benchmark_layer_rule_hoist.py smoke
python3 tools/run_unconventional_isolated.py --label layer-hoist-timing -- uv run tools/benchmark_layer_rule_hoist.py timing
uv run tools/benchmark_layer_rule_hoist.py summarize
```

The last command is read-only aggregation of existing observations apart from
writing `summary.json`; it does not launch a browser or retime any case.
