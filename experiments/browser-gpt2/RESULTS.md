# Complete Chromium pipeline results

Measured September 16, 2026, on Apple M2 Pro / 16 GB RAM, Chrome 153.0.8010.48.
Fresh headless Chromium profile, ordinary static HTTP delivery, scripts disabled.
One initial native Run click; no further input mutations, stage scheduling, or intermediate-vector transfers.

Scope: one selected prompt token, browser-owned prefill and K/V, all twelve blocks, full vocabulary selection, token feedback, and eight generated tokens.

## Actual end-to-end times

| Measurement | Seconds |
| --- | ---: |
| Page navigation → first result observed | 110.819 |
| Initial Run click → first result observed | 73.611 |
| Subsequent result interval, median | 77.956 |
| Subsequent result interval, min–max | 62.301–91.287 |
| Page navigation → all eight tokens captured | 662.495 (11 min 2.5 s) |

The follow-up intervals were: 62.301, 69.011, 75.689, 77.956, 85.459, 91.287, 89.970 seconds.
These are complete recurrent intervals, not sums of separate matrix benchmarks. This is **not 13 seconds/token**.
The initial click occurred after 37.208 s of loading/initial layout. Page-level startup and native font readiness are included; disk caches were not globally flushed.

## Where the warm interval goes

| Observed boundary interval | Share |
| --- | ---: |
| Handoff / observer boundary | 14.8% |
| Embedding handoff | 1.9% |
| 12-block core + KV | 80.0% |
| Final bridge, norm and full head | 3.2% |

These coarse native-geometry milestones span shared rendering frames. In particular, the handoff bucket includes observation/queue delay, and the final-head bucket cannot cleanly separate work performed in the same frame. Do not interpret them as an exclusive mathematical-operation profiler.

Renderer counters across the seven warm intervals: Style recalculation 37.5%, Layout 7.7%, Other renderer tasks 54.8%, CDP command handling 0.1%. Script execution and V8 compilation time were zero.

## Optimizations retained and rejected

- Retained a flat per-layer cache: only the active slot declares live sources. The four-state sequence had zero retention error; its three fresh-input comparisons were approximately 11–22% faster than the same states with a nested bank. This was a small screen, not a randomized multi-run benchmark.
- Isolated the scorer from core scratch/cache inheritance, and delayed its initial layout until the first real hidden vector. Subsequent token feedback stays alive.
- Replaced the fragile large-width fractional token decoder with an integer second pass and bounded 16-way reduction trees. All 50,257 candidates are scored; there is no shortlist or search timeout.
- Rejected every-matrix and whole-block retirement. In the two-block screen they were much slower than keeping the live timelines.
- The earlier full nested-cache run took 789.316 s. It used local-file delivery and a different readout harness, so the difference is an observed system-level comparison, not a clean isolated cache-speedup claim.

## Correctness and limits

- Produced `Hello, I'm sorry, but I'm`.
- 8/8 decisions matched the independent q9/q16 reference; 8/8 also matched the original floating-point checkpoint on the generated context.
- 147,456 K/V coordinates across 96 slots: 0 differing CSS readbacks versus the completed nested-cache baseline. Final residual and normalized hidden readbacks are also identical.
- Final residual versus the continuous-activation q9 reference: RMSE 0.024831, max error 0.221885. The font/core path is therefore not advertised as exact float32 arithmetic.
- Head-only screen: 38/38 difficult fixtures. Embedding lookup: 16/16 fixtures, including vocabulary/group boundaries.
- Unobserved full-model progression passed: after the initial Run click, 180 seconds without DOM/style/layout observations produced two correct tokens. The harness is not required to advance the loop.
- Native control fixtures passed pause/prompt locking, resume, form reset, and end-of-text stopping. A separate font-readiness fixture passed both available-font and deliberately blocked-font cases. These are focused control fixtures, not additional full-model continuations.
- This is a bounded implementation, not broad held-out model certification. The planned 128-position / 16-continuation expansion has not been run; no further quantization is promoted on these results.
- Context is eight positions, no eviction. Storage uses a 24-hour delayed-transition horizon. Prompt input is a fixed one-token picker, not arbitrary text tokenization.

Raw evidence: `demo/pipeline-results.json`, `demo/timing-summary.json`, `demo/numerical-results.json`, `demo/verification-vectors.json`, `demo/screenshot.png`, `demo/unobserved-results.json`, `controls/results.json`, and `font-barrier-probe/results.json`.

Remaining performance priority: reduce core animation/style propagation and native handoff cost. A faster head alone cannot remove the dominant core cost. Broader context, arbitrary text input, and stronger numerical coverage remain separate follow-ups.
