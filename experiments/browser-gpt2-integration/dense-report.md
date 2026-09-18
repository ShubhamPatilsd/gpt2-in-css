# Dense-stage locality investigation

Status: four dense-component cases completed. The normalization-private variant
preserved every baseline output coordinate, but the small median differences
do not establish a speedup. Projection-list and layer-hoist measurements remain
pending; native transfer validation is owned by the full-runtime driver.

## Concrete dependency audit

The reused real-model graph nests LN1 → QKV → attention/cache → attention
projection with residual → LN2 → FC with exact GELU → MLP projection with
residual. One rendering graph selects each real layer's fonts and constants.
Dense generation receipts travel through the same layout as matrix glyph
widths, and downstream gates wait for the corresponding generation.

- QKV takes 768 normalized inputs and produces 2304 outputs. With compact
  layout its font settings are resolved on the stage and inherited by its
  metric leaves. Raw normalized inputs have no later neural consumer.
- Attention projection consumes 768 context values and fuses the original
  residual addition into its output expressions. Removing that residual
  dependency would change the arithmetic.
- FC takes 768 normalized residual inputs, emits 3072 values, and already
  evaluates exact GELU in the output readers. It does not need a separate
  GELU geometry round-trip.
- MLP projection consumes all 3072 hidden values and adds the residual. Its
  standard layout has four font-pack spans per output row, 768 rows. Pack
  font-settings expressions therefore occur on 3072 elements. Its output
  still requires the native generation receipt before layer feedback.
- Every layer's specialized dense stylesheet currently places structural
  animation/timeline/container declarations inside the layer style query,
  alongside the genuinely layer-specific fonts, bias, scale and normalization.

Sources: [matrix builder](../../tools/build_hybrid_twelve_block.py),
[reused core](../../tools/browser_gpt2_reused_core.py),
[shared registrations](../../tools/browser_gpt2_core.py).

## Existing work and new ablations

`scoped_state` already makes private timeline progress and some control state
non-inheriting. `isolate_metrics` already materializes projection pack axis
lists and then resets broad neural vectors on metric branches. `liveness`
inserts dead-state reset wrappers between stages. `global_projection` changes
font axis tags/assets to form one global-axis projection layout. None of these
existing features is presented as a new discovery.

The new helper deliberately separates smaller hypotheses:

| Variant | Opt-in change | Dependency preserved | Main risk |
|---|---|---|---|
| `norm-private` | Register `n1`, `n2`, and four normalization scalars as non-inheriting; forward each normalized vector only from LN to its immediate QKV/FC consumer. | Matrix font settings and dynamic ranges still read all 768 normalized coordinates at their actual stage. | Explicit forwarding or property registration may cost more than it saves. |
| `proj-settings` | Resolve each projection pack list on `.shared-proj`, then reference that list on the repeated pack leaves. | All 3072 coordinates, font families, scale, bias and residual remain present. | Unregistered list preparation may not remove enough repeated computed-value work. |
| `layer-hoist` | Move only verified invariant animation, timeline, container-name and display declarations outside layer queries. | Layer-specific fonts, ranges, gains, biases, viewport sizes and output arithmetic remain conditional. | Cascading or timeline lifecycle can change even when structural values match; browser validation is required. |
| `combined` | Apply these three changes together. | Same arithmetic and receipts. | Interactions may erase single-factor improvements. |
| `loop-selective` | Enable the existing selective loop-reader option independently of liveness/reset wrappers. | Sample all 768 prior-bank vector values, the prior-bank generation stamp, and the current-bank acknowledgement stamp. | Switching animation lists may alter native handoff behavior; requires native integration validation. |
| `combined-loop` | The three dense rewrites plus selective loop reads. | Same dense arithmetic and both loop stamp channels. | Separate effects and their interaction must be measured. |

Projection-list materialization is an independent ablation of a preparation
step already present inside `isolate_metrics`; the experiment's novelty is
separating it from the broad resets. The earlier native attention investigation
found that broad materialization/reset choices could increase style time, so
neither this smaller boundary nor its combination is presumed faster.

## Integration interface and safeguards

Implementation: [opt-in helper](../../tools/browser_gpt2_dense_locality.py).
Component harness: [dense-stage probe](../../tools/probe_browser_gpt2_dense_stage_locality.py).

```python
from browser_gpt2_dense_locality import dense_compile_variant

with dense_compile_variant("norm-private") as dense_stats:
    compile_runtime(...)
```

The context patches only the reused core's compile-time `shared_css`,
`specialize`, and `loop_parts` helpers. It reaches adapters that imported `compile_reused`
earlier, restores original helpers on exit, and yields JSON-safe provenance
counts. Create a new context per artifact. Compilations in one process must
be serial. The helper does not change production source or insert runtime
JavaScript, input values, scheduling ticks, or externally computed outputs.

Rewrites use bounded per-stage strings and linear scans. Property rewriting
asserts all 1540 requested registrations. Projection rewriting asserts the
four standard packs. Layer hoisting verifies each selected declaration has
the same value in every encountered layer and rejects unexpected/nested
stage rules, while preserving the known native receipt-gate container query
inside its original layer condition. Font shorthands/settings are not hoisted because a remaining
layer-specific shorthand could reset an earlier variation setting.

## Validation plan

Use real model weights and fresh inputs for two reusable component graphs:
LN1 → QKV, and LN2 → FC/GELU → MLP projection/residual. Exercise more than one
layer, distinct inputs, and revisits; compare every coordinate against an
independent floating-point calculation with the matching quantized weights.
Read native receipt freshness and retained output together. Externally driven
component timing must be labeled as such, including its observation floor.

Then root can select passing candidates through the context-manager hook for
native full-pipeline validation. Historical stage evidence and new diagnostic
results are being coordinated with the profiling agent; no performance claim
is justified by this source audit alone.

The prepared probe uses real layers 0 and 11, with reference-derived inputs
from tokens 15496 and 11. It revisits both layers after both positions. Each
fresh browser preloads every selected layer's fonts using the native font
barrier, then accepts externally written inputs and generation/layer selectors.
Dense private progress fields and the private layer selector match the reused
runtime's scope. QKV produces all 2304 coordinates; the MLP graph includes
all 3072 FC/GELU values and the full 3072→768 projection with residual addition.

Timing uses one checksum/generation geometry box, requiring the matching
native generation and three stable 25ms intervals. Every output coordinate is
read **after** timing, so enumerating computed custom properties does not enter
the timed vector readback. CDP writes, geometry reads and their induced style
or layout work still enter wall time. Renderer counters are captured before
the vector readback. First/cold samples are separated from warm updates.

Oracle RMSE must remain below 0.05, the existing reused-core sanity tolerance;
the new candidates must additionally match the corresponding baseline output
vector within 0.000001 maximum absolute difference when the baseline is saved.
The raw numerical errors remain part of the report. These component checks
do not establish full-model token quality. The default QKV screen skips
`proj-settings`, which has no effect on a graph without MLP projection.
The component screen also excludes `loop-selective` and `combined-loop`,
because these isolated graphs contain no recurrent loop. Root's native
integration driver validates the transfer option separately.

The transfer option was identified by the profiling agent in the existing
[`loop_parts(selective=True)` implementation](../../tools/probe_native_reused_loop.py).
It reduces sampled loop-reader animation channels from 1538 to 770 at width
768. Both banks' storage elements and all native capture/advance rules remain.
The previous runtime coupled this option to broader liveness resets. This
helper exposes it independently and records the exact selected channel count;
channel reduction alone is not a measured speedup.

Completed bounded command after the benchmark slot was granted:

```sh
uv run tools/probe_browser_gpt2_dense_stage_locality.py --variants baseline norm-private --stages qkv mlp --layers 0 11 --repeat 1
```

## Completed component screen

The first `baseline-qkv-l0-11-r0` fixture never passed font readiness: the
standalone wrapper omitted the `.head-reduction` display/position rule normally
provided by the full vocabulary head. It timed out before recording any dense
sample. Its [failure result](dense/baseline-qkv-l0-11-r0/results.json), generated
artifacts, and exact [pre-fix probe source](dense/baseline-qkv-l0-11-r0/source/probe_browser_gpt2_dense_stage_locality.py)
are preserved. The fix adds that base rule only to this standalone harness;
the repaired run uses a new `r1` label. This was a fixture startup failure,
not failed dense arithmetic or a candidate regression.

The repaired order was baseline QKV, normalization-private QKV, baseline MLP,
normalization-private MLP. Every case used a fresh browser. Heavy reference
calculation and font compilation finished before its browser launched; the
first sample includes cold page/font readiness, and subsequent samples are
warm updates. There was one process per case, without an order reversal or
repeat. All four cases passed all six epochs, totaling 24 checked vectors.
All candidate coordinates matched their corresponding baseline exactly.

| Component | Baseline warm median | Normalization-private | Median change | Peak renderer RSS, baseline → candidate |
|---|---:|---:|---:|---:|
| LN1 → QKV, 2304 outputs | 279.70 ms | 273.07 ms | −2.4% | 853 → 962 MiB |
| LN2 → FC/GELU → projection/residual, 768 outputs | 601.67 ms | 577.19 ms | −4.1% | 1094 → 981 MiB |

Individual epochs make the uncertainty clearer than the medians. Epoch 1 is
cold; epochs 2–6 are the five samples entering each warm median.

| Epoch | Position/layer | QKV baseline | QKV private | MLP baseline | MLP private |
|---|---|---:|---:|---:|---:|
| 1 | 0 / 0 | 1008.13 ms | 936.58 ms | 1785.95 ms | 1821.98 ms |
| 2 | 0 / 11 | 279.70 ms | 273.07 ms | 601.67 ms | 636.45 ms |
| 3 | 1 / 0 | 280.70 ms | 285.07 ms | 632.32 ms | 639.65 ms |
| 4 | 1 / 11 | 279.91 ms | 274.29 ms | 602.29 ms | 577.19 ms |
| 5 | 1 / 0, revisit | 242.93 ms | 250.92 ms | 522.59 ms | 525.96 ms |
| 6 | 1 / 11, revisit | 233.90 ms | 236.38 ms | 454.98 ms | 461.03 ms |

Only two of five QKV warm epochs and one of five MLP warm epochs were faster
with private normalization. Lower medians alone therefore do not justify a
native speedup claim. Median measured style time changed only 62.70 → 61.70 ms
for QKV and 205.48 → 203.42 ms for MLP; layout changed 34.43 → 33.57 ms and
101.35 → 99.28 ms. RSS moved in opposite directions across the components.
This option remains available for integration experiments, but is not a
demonstrated performance winner.

Worst oracle RMSE was 0.0008212 for QKV and 0.0079929 for MLP. The latter's
largest coordinate error was approximately 0.09861, so the acceptance criterion
is explicitly the existing RMSE threshold, not a claim that all coordinates
are accurate within 0.05. The private variant introduced zero additional
coordinate difference. Repeated layer switches and input changes were tested
within each component; autonomous 12-layer transitions were not part of this
screen.

The [machine-readable comparison](dense/comparison-r1.json) retains every
epoch, renderer counter delta, source-match checks, and the startup exclusion.
Each case's `fixture.json` stores exact compiler/harness hashes and generated
artifact hashes; its `source/` directory stores matching source bytes. All
four successful cases used identical recorded source hashes, including:

- `probe_browser_gpt2_dense_stage_locality.py`: `2934ee9f7e2eddd777496ae4651d9f361a1e6b2f6f76d6f924dd70197d1f3e67`
- `browser_gpt2_dense_locality.py`: `78f2b9cd53e017fbfada963d23c68e6d87290608a8f8e36c4e3e3d88c4b2279f`

Ruff passed both current source files after the screen. No production compiler
source was changed. Projection-list materialization, layer hoisting, their
combination, and selective loop reads have not been measured by this component
screen; the last requires the native driver because these fixtures have no loop.

## What the saved native timings actually support

The profiling agent's [stage-cost investigation](stage-costs.md) recovered a
matched broad span for continuing tokens 2 and 3 of capacity-four repetition
r2: embedding-ready to head-input-ready averaged 34.157 s for baseline and
31.167 s for widths, around 89% of their observed capture-to-capture span.
Whole-token renderer task shares were 52.57% style, 15.25% layout, 32.11% other
for baseline and 51.24%, 15.66%, 33.02% for widths. These are not individual
QKV, FC or projection proportions.

The subsequent native receipt diagnostic skipped many transient pass epochs;
some individual geometry reads also waited long enough to include queued
downstream work. Accordingly this report does not convert those observations
into exclusive dense-stage timing percentages. The isolated component
experiments target matched changes with explicit scope instead.
