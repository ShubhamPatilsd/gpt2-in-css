# Connected MLP comparison and bounded runtime estimation

Started 2026-09-17, America/Los_Angeles. The user requests a subagent to connect
the MLP to its surrounding stages and benchmark again, with short measurements
that can support a useful runtime estimate rather than another 32-token run.

## Correction to the starting premise

The earlier recommendation read the standalone MLP result but missed
[CONNECTED_RESULTS.md](../avar2-gelu-linear-hvar-full-mlp/CONNECTED_RESULTS.md).
That existing work already connects avar2 MLPs to native normalization, residuals,
next-layer normalization, and two one-token transformer blocks. It also shows
that the isolated 251 ms MLP result is not a reliable connected latency.

The missing comparison is against the MLP path used by the current reusable
token-generation core, under the same surrounding computations and fresh input
changes. Repeating the old connected prototype would not supply that comparison.

## First measurement boundary

Use real post-attention residual vectors as the external boundary inputs:

```
raw residual → native LN2 → FC → GELU → projection
             → residual + bias → next layer's LN1 → dependent output
```

The baseline uses the current core's FC/GELU/projection implementation. The
candidate uses the existing avar2/linear-HVAR mechanism and assets. Surrounding
math, raw input states, and output demand must match. The external driver may
change the boundary inputs and observe answers; it must not supply normalized
inputs, hidden activations, or MLP results to either timed graph.

This is a connected segment replay, not autonomous token generation. Next-layer
normalization includes reductions over all 768 coordinates, making the final
consumer depend on the full residual vector. Do not rely only on a last output
glyph if it can leave part of the graph undemanded. Verify all coordinates and
changing generations separately from the compact timed observation.

Prefer block 0 plus a second layer if existing assets allow a bounded comparison.
One layer's coefficient ranges and errors cannot establish all twelve layers.
Record each backend's actual numerical approximation and compare against an
independent model reference; a faster but materially less accurate computation
is not an accepted replacement.

## Correctness before timing

Preserve parser/DOM failures, missing fonts, range violations, stale outputs,
and numerical discrepancies. Require all required fonts to load and the native
producer, MLP, residual, and consumer to agree with their declared references.
Repeated state changes must include revisiting earlier values. Check all output
coordinates outside the timed observation and retain maximum error and RMSE.
Explicitly state whether tolerances match a backend reference or full model math.

Only passing fixtures advance. Timings use separate fresh browser processes,
one benchmark page at a time, opposite baseline/candidate orders, the same state
schedule, warmups, and all raw samples. Browser/build work uses the common
advisory lock; parallel agent preparation must not create overlapping benchmarks.
Keep font loading and initialization separate from repeated update cost. Record
both the in-page input-write-through-dependent-output interval and larger driver
intervals so measurement overhead is visible. Do not serialize all 768 outputs
through DevTools inside the latency timer.

## Estimation without a full run

Use the saved complete capacity-32 trajectory as an offline validation dataset.
Predeclare constant-latency and linear-context forecasts fit only to early
continuing-token samples. Evaluate their error on later withheld continuing
tokens. Keep startup and the terminal token separate. Four-slot and eight-slot
records are different allocated graphs, not interchangeable prefixes of a
32-slot graph. A good fit to the complete historical trajectory is not a valid
test of an early forecast.

Report fresh connected-segment savings as measured savings at that boundary.
A calculation such as `32 × 12 × segment saving` is only a conditional scenario:
it assumes the saving survives every layer, token, control boundary, and memory
condition. It must not be labeled measured or calibrated model speed.

Scaffold a bounded calibration manifest for native continuing-token windows at
low, middle, and high context occupancy, always with the same allocated capacity.
Checkpoint-restored K/V must be labeled restoration, with startup/warmup outside
steady timing and independent cache/output validation. If checkpoint restoration
does not exist, a plan or schema must not be described as an implemented runner.

If the connected candidate wins substantially and passes precision checks, the
next gate is a short real-core integration with continuing tokens and native
generation control. If it loses or fails correctness, stop before a longer run.
The current task must not launch the complete 32-token run. If short data cannot
support a reliable long-run estimate, quantify that limitation instead of
manufacturing a precise forecast.

## Ownership and deliverables

- Integration worker: isolated baseline/candidate builders and generated fixtures.
- Benchmark worker: correctness/timing harness, raw samples, estimation script.
- Root: protocol, evidence review, final report, links to existing measurements.

Preserve unrelated repository edits. Reuse existing fonts to bound disk/build
cost. Final artifacts must distinguish old findings, fresh measurements,
conditional projections, and work that remains unimplemented.

## Recorded amendments before the final timing comparison

The first smoke run stalled because the external in-page animation-frame
callback did not return with page JavaScript disabled. The revised observer uses
bounded external polling and retains an in-page start timestamp. Its elapsed
interval includes the cost and scheduling effects of those browser-protocol
round trips. The final dependent width must also remain unchanged when all
coordinates are subsequently read; otherwise the timing endpoint is rejected.
All required font faces are explicitly preloaded outside timing, including
baseline projection fonts initially hidden behind generation gates.

The initial accuracy screen required residual-state maximum absolute error below
0.1 and next-LN maximum error below 0.01, for both implementations. Layer 1 failed
the state maximum check: baseline 0.277600 and candidate 0.316156, while state
RMSE was 0.013237 and 0.020955 respectively. Both next-LN maximum errors were
about 0.0014. Those are real retained failures of the original screen. An axis
rounding calculation did not explain away the discrepancy; no arithmetic fix is
claimed and thresholds must not be silently widened.

The final diagnostic comparison instead adopts the already existing reusable
core's state RMSE < 0.05 criterion, from
[test_browser_gpt2_reused_core.py](../../tools/test_browser_gpt2_reused_core.py),
plus finite values at every coordinate and the unchanged next-LN maximum-error
limit of 0.01. Absolute state errors remain reported but are not a pass criterion
under this explicitly revised policy. This is a documented change of acceptance
criterion after an initial failure, not confirmation of the original strict
gate. HTML arithmetic and font assets remain unchanged. New complete gates
must pass under the versioned policy before final timings.

The criterion supports a diagnostic comparison against the current implementation.
It is not a new all-layer quality guarantee: the existing core's aggregate
error criterion and the next normalization check do not establish future token
agreement for the candidate. Candidate precision still needs model-level checks
before adoption.

## Completion and stopping decision

Completed the two-layer segment construction, numerical gates, layer-0 matched
timings, and runtime-estimation scaffolding. Layer 1's candidate failed the
unchanged next-LN error bound under the revised policy, so it was not timed.
Layer 0's candidate was 17–19% slower on first-visit inputs in both fresh-process
orders, with about 1.8 times sampled renderer RSS. The tested implementation is
not promoted into the token generator.

The final timing plan added a first-visit schedule after repeated-state gates
showed much faster cached revisits. It warmed only the initial state and then
measured three other states once each per fresh process, reversing order in the
second pair. No vectors, HTML, fonts, arithmetic or accuracy thresholds changed.
A new layer-0 gate bound the final harness before either timing schedule ran.

No full native token run was launched. Total browser experiment time, including
preserved attempts and gates, was about 5.9 minutes. The bounded native-prefix
runner and estimator interface are implemented and tested offline; live native
execution and independent numerical validation of that new runner remain
unperformed. A checkpoint-resume engine remains unimplemented. These limits,
raw measurements and final stopping decision are in [RESULTS.md](RESULTS.md).
