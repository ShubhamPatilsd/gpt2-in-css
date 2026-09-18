# Local-update integration results

The first twelve-layer native measurement is complete. Results below are
accepted only at their stated scope; unmeasured proposals and failed attempts
remain distinct from working changes.

## Attention ownership

The twelve-head implementation is now connected to the native pipeline. Each
head receives its own 192 Q/K/V coordinates through a native geometry boundary,
retains its own per-layer/per-slot cache, calculates its own context, and reports
a generation-tagged completion. A shared join waits for all twelve current
heads. The consumers are siblings of the dense loop, not descendants inheriting
its raw vectors. See [attention-report.md](attention-report.md).

The first autonomous acceptance case used two layers and two generated tokens,
the full vocabulary, native layer/token feedback, and zero post-navigation
writes. It completed in **29.56 seconds**, produced the reference tokens
`11, 3387` (`Hello, please` including the prompt), passed all retained-cache
checks, and had final residual RMSE **0.002043** against the independent quantized
reference. This is a working truncated-model integration, not yet a twelve-layer
speed result. [Raw case](native/owned-b2c2-r0/experiment.json).

Two separate component processes checked six generations, all twelve heads and
all 768 context coordinates. The larger fixture covered two layers, two slots
and a layer revisit. Poisoning all 2,304 upstream QKV coordinates left the held
input/context correct while all incoming readers observed the poison. These
fixtures use external input writes and are labeled accordingly.

## Dense calculations, vocabulary, and transfers

Separate ablations are being tested for normalized-input ownership, repeated
projection settings, layer-invariant declarations, raw vocabulary-input
inheritance and selective feedback-bank reads. The purpose is to identify
which changes reduce total work without bundling them with broad resets that
regressed in the preceding investigation.

The existing native feedback compiler already has a selective reader hidden
behind its larger liveness option. The new `loop-selective` ablation isolates
that reader: 768 previous-vector channels plus the previous and current stamps,
**770 instead of 1,538 reader channels**. This is a source-level count, not a
claim of a 50% runtime saving. Native numerical and timing validation is pending.

The baseline vocabulary graph already computes font settings at two scoring
owners. The new experiment keeps the 768 raw input properties private to the
input bank and forwards their axis bundle. It retains every vocabulary row,
both scoring passes and the exact reduction logic.

## Measurement limits

The new [stage diagnostic](stage-costs.md) generated the expected first two full
model tokens, but read calls missed transient boundaries. It observed no complete
six-stage pass, so it cannot support exclusive QKV/MLP/vocabulary percentages.
Its missing boundaries and observer delays are preserved rather than filled in.

All performance experiments are serialized. Source snapshots and generated
artifact hashes are retained, failed directories are immutable, and checks use
actual browser activations/caches. Native timing includes loading and observation.
At capacity two the only inter-token interval is the terminal interval; it is
not evidence of steady-state scaling.

Before the new full-model cases, acceptance thresholds were declared as exact
token agreement and final-head agreement, finite vectors, cache RMSE below 0.01,
and final residual RMSE below 0.05. The residual bound accommodates the unchanged
preserved twelve-layer baseline (0.02723 at capacity two; 0.01831 at capacity four).
Absolute errors and matched-baseline comparisons remain necessary; passing a
bound alone is not evidence that numerical behavior is unchanged.

## State at interruption

The twelve-layer/two-token owned-attention document compiled successfully as
`native/owned-b12c2-r0`, but the turn interrupted its browser process before a
pipeline result was saved. Its compiled artifacts, source snapshots and log are
preserved. No twelve-layer correctness or speed claim is made from this case.
The owned browser and runner were confirmed no longer running after interruption.

A subsequent fresh-label retry, `native/owned-b12c2-r1`, completed. It is the
first valid twelve-layer measurement of the all-head ownership implementation:

| Measurement | All-head owned attention |
| --- | ---: |
| First token | 52.116 s |
| Terminal second-token interval | 47.370 s |
| Total, two tokens | 99.487 s |
| Effective total rate | 0.0201 tokens/s |
| Peak sampled renderer RSS | 4,970.7 MiB |

Both generated tokens (`11, 314`) matched the independent quantized and original
floating-point winners. All 24 expected layer/slot cache vectors were present
and finite, the final head matched its actual input, final residual RMSE was
0.02506, and the page received zero post-navigation writes. [Verified summary](native/owned-b12c2-r1/integration-summary.json).

This result does **not** show a speedup. The earlier, non-contemporaneous
twelve-layer baseline took 82.73 s total (44.81 s first token and 37.91 s final
interval), so this owned-attention run is 20.3% slower in total. Its sampled
renderer RSS is also higher than the earlier baseline's 3,421 MiB. Because the
cases were run at different times, a fresh matched baseline is required to
estimate the causal regression precisely. Capacity two supplies no continuing
interval, so this measurement also does not establish long-context scaling.

The repaired dense component screen completed four cases and 24 fresh/revisit
epochs across real layers 0 and 11. Private normalized inputs matched every
baseline output coordinate exactly. QKV median timing changed 279.70→273.07 ms
and MLP median 601.67→577.19 ms, but paired epochs were inconsistent; these are
single-run, noise-scale differences, not demonstrated gains. The earlier fixture
startup timeout remains saved separately. See [dense-report.md](dense-report.md).

Implemented but still awaiting browser measurement: vocabulary `settings` and
`private-inputs`, dense `proj-settings` and `layer-hoist`, and native
`loop-selective`. Their source guards and harness checks are not substitutes for
numerical browser validation. The pending full-model comparison must include a
matched baseline and continuing tokens, not only the capacity-two terminal
interval. [Source review](profiling/source-review.md).
